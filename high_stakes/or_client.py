"""
or_client.py — Cliente OpenRouter compartilhado do motor high-stakes.

ZERO dependência externa [D8]: só stdlib. O transporte HTTP vem de
`http_client.py` (urllib), com a interface do `requests` preservada.

Responsabilidades:
  - chat(model, messages, ...) -> dict com {text, usage, cost_usd, provider, raw}.
  - Custo via `usage.cost` do OpenRouter (pega o custo de busca interna do sonar,
    que NÃO aparece no token-math). Fallback = pricing do catalog-snapshot.
  - Budget cap HARD reserve-then-reconcile [D1+D3]: pré-debita o teto estimado
    ANTES do dispatch; se reservado > CAP -> levanta BudgetExceeded antes de
    mandar a request. Pós-resposta reconcilia reservado -> custo real. Protege
    mesmo com N calls em voo (overshoot = 0). Lição Fugu.
  - Retry com backoff em 429/5xx, honra Retry-After.
  - catalog-snapshot na 1ª chamada (reprodutibilidade).
  - Key lida de .env (nunca hardcoded, nunca logada).

         budget ledger (thread-safe)
         ┌─────────────────────────────────────────────┐
   chat()│  reserve(est)  ──>  cap check  ──> dispatch   │
         │      │ (pré-débito)      │ raise       │      │
         │      │                   │ BudgetExc.  v      │
         │      └──── reconcile(est, real) <── resposta  │
         └─────────────────────────────────────────────┘
"""

from __future__ import annotations

import contextlib
import json
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from .http_client import RequestException, Response, Session

try:  # POSIX (macOS/Linux). Sem fcntl o lock degrada p/ no-op — ver _file_lock.
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None

OPENROUTER_BASE = "https://openrouter.ai/api/v1"
DEFAULT_CAP_USD = 15.0
DEFAULT_TIMEOUT = 300  # s; sonar-deep-research é lento. Override por-call.
MAX_RETRIES = 4

# Paths (lib-ready, 1A′-ii): TODOS injetáveis por parâmetro — ledger_path
# (BudgetLedger), outputs_dir (ORClient), env_path (load_api_key). O default de
# ESCRITA é CWD/outputs (convenção deste projeto: `cd <experimento> && python3 run.py`
# -> ledger/catalog caem NO experimento). O engine NUNCA escreve dentro de si.
_HERE = Path(__file__).resolve().parent
_ENV_PATH = _HERE.parent / ".env"  # raiz da instalação (gitignored; só leitura)


def _default_outputs() -> Path:
    return Path.cwd() / "outputs"


class BudgetExceeded(RuntimeError):
    """Levantada ANTES do dispatch quando a reserva estouraria o cap."""


class SchemaInvalid(ValueError):
    """JSON da célula não valida contra o schema esperado (estado terminal)."""


def load_api_key(env_path: Path | None = None) -> str:
    """Lê OPENROUTER_API_KEY do .env local (KEY=value). Nunca loga o valor."""
    env_path = env_path or _ENV_PATH
    env_key = os.environ.get("OPENROUTER_API_KEY")
    if env_key:
        return env_key.strip()
    if not env_path.exists():
        raise RuntimeError(
            f"sem OPENROUTER_API_KEY no env nem em {env_path}. "
            "Puxe a key do VPS pro .env (gitignored)."
        )
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line.startswith("OPENROUTER_API_KEY="):
            return line.split("=", 1)[1].strip()
    raise RuntimeError(f"OPENROUTER_API_KEY não achado em {env_path}")


RESERVATION_TTL_S = 3600  # reserva órfã (processo morto) some depois disto


@contextlib.contextmanager
def _file_lock(path: Path):
    """Lock EXCLUSIVO entre processos no arquivo `path`.

    Sem fcntl (não-POSIX) degrada p/ no-op: o cap volta a valer só por processo. É
    aviso explícito, não falha silenciosa — o motor roda em macOS/Linux.
    """
    if fcntl is None:  # pragma: no cover
        yield
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    f = open(path, "a+")
    try:
        fcntl.flock(f, fcntl.LOCK_EX)
        yield
    finally:
        try:
            fcntl.flock(f, fcntl.LOCK_UN)
        finally:
            f.close()


class BudgetLedger:
    """Ledger de spend com reserva pessimista (reserve-then-reconcile), seguro entre
    THREADS (lock em memória) e entre PROCESSOS (flock + read-modify-write).

    O cap é POR RUN, não por processo. Manter só `self._spent` em memória e sobrescrever
    o arquivo no flush fazia dois processos no mesmo run lerem `spent=0`, gastarem o cap
    inteiro cada um e o último write vencer — cap furado em 2x, silenciosamente. Por isso
    toda mutação relê o disco sob lock, e as RESERVAS também são persistidas: uma call em
    voo no processo A precisa ser visível pro cap do processo B antes do dispatch.
    """

    def __init__(self, cap_usd: float = DEFAULT_CAP_USD, persist: bool = True,
                 ledger_path: Path | None = None):
        self.cap_usd = cap_usd
        self._reserved = 0.0
        self._spent = 0.0
        self._calls = 0
        self._lock = threading.Lock()
        self._persist = persist
        self._ledger_path = ledger_path or (_default_outputs() / "cost-ledger.json")
        self._lock_path = self._ledger_path.with_name(self._ledger_path.name + ".lock")
        # identidade desta instância no arquivo compartilhado (dono das suas reservas)
        self._owner = f"{os.getpid()}-{uuid.uuid4().hex[:8]}"
        if self._persist and self._ledger_path.exists():
            with _file_lock(self._lock_path):
                d = self._read_disk()
                self._spent = d["spent_usd"]
                self._calls = d["calls"]

    # ---- disco (SEMPRE chamado sob _file_lock) ----
    def _read_disk(self) -> dict:
        """{spent_usd, calls, reservations} do disco, saneado. Ledger ilegível não
        aborta o run: avisa e trata como zerado (o cap segue valendo daí pra frente)."""
        try:
            raw = json.loads(self._ledger_path.read_text())
        except (json.JSONDecodeError, OSError) as e:
            if self._ledger_path.exists():
                print(f"[ledger] AVISO: ledger corrompido em {self._ledger_path} "
                      f"({type(e).__name__}) — começando gasto em 0.")
            raw = {}
        except ValueError:
            raw = {}
        try:  # ledger pré-fix pode ter spend negativo (sentinela -1/-1 do catálogo)
            spent = max(0.0, float(raw.get("spent_usd", 0.0) or 0.0))
        except (TypeError, ValueError):
            spent = 0.0
        try:
            calls = int(raw.get("calls", 0) or 0)
        except (TypeError, ValueError):
            calls = 0
        res, now = {}, time.time()
        for k, v in (raw.get("reservations") or {}).items():
            try:
                usd, ts = float(v["usd"]), float(v["ts"])
            except (TypeError, ValueError, KeyError, IndexError):
                continue
            if usd > 0 and now - ts < RESERVATION_TTL_S:  # descarta órfã de processo morto
                res[k] = {"usd": usd, "ts": ts}
        return {"spent_usd": spent, "calls": calls, "reservations": res}

    def _write_disk(self, spent: float, calls: int, reservations: dict) -> None:
        payload = json.dumps({
            "spent_usd": round(spent, 6),
            "calls": calls,
            "cap_usd": self.cap_usd,
            "reservations": reservations,
        }, indent=2)
        self._ledger_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._ledger_path.with_name(f"{self._ledger_path.name}.{self._owner}.tmp")
        tmp.write_text(payload)
        os.replace(tmp, self._ledger_path)  # write atômico

    def _commit(self, delta_spent: float, delta_calls: int) -> None:
        """Read-modify-write sob lock: soma o delta DESTE processo ao que está no disco
        e adota o resultado como verdade. Chamado com self._lock já tomado."""
        with _file_lock(self._lock_path):
            d = self._read_disk()
            # arredonda AQUI, não só na serialização: memória e disco têm de ser o mesmo
            # número, senão o gasto lido por outro processo diverge do local por ~1e-8.
            spent = round(d["spent_usd"] + delta_spent, 6)
            calls = d["calls"] + delta_calls
            res = d["reservations"]
            if self._reserved > 0:
                res[self._owner] = {"usd": round(self._reserved, 6), "ts": time.time()}
            else:
                res.pop(self._owner, None)
            self._write_disk(spent, calls, res)
            self._spent, self._calls = spent, calls

    def reserve(self, est_usd: float) -> None:
        """Pré-debita `est_usd`. Levanta BudgetExceeded ANTES do dispatch se estourar.

        Persistente: a checagem consulta o DISCO — gasto acumulado do run MAIS as reservas
        em voo de OUTROS processos. É isso que faz o cap valer por run, não por processo.
        """
        with self._lock:
            if not self._persist:
                projected = self._reserved + self._spent + est_usd
                if projected > self.cap_usd:
                    raise BudgetExceeded(
                        f"reserva ${est_usd:.4f} estouraria o cap "
                        f"(spent ${self._spent:.4f} + reserved ${self._reserved:.4f} "
                        f"+ est = ${projected:.4f} > ${self.cap_usd:.2f})"
                    )
                self._reserved += est_usd
                return
            with _file_lock(self._lock_path):
                d = self._read_disk()
                others = sum(v["usd"] for k, v in d["reservations"].items()
                             if k != self._owner)
                self._spent, self._calls = d["spent_usd"], d["calls"]
                projected = d["spent_usd"] + others + self._reserved + est_usd
                if projected > self.cap_usd:
                    raise BudgetExceeded(
                        f"reserva ${est_usd:.4f} estouraria o cap "
                        f"(spent ${d['spent_usd']:.4f} + reserved ${self._reserved:.4f} "
                        f"+ outros processos ${others:.4f} "
                        f"+ est = ${projected:.4f} > ${self.cap_usd:.2f})"
                    )
                self._reserved += est_usd
                d["reservations"][self._owner] = {
                    "usd": round(self._reserved, 6), "ts": time.time()}
                self._write_disk(d["spent_usd"], d["calls"], d["reservations"])

    def reconcile(self, est_usd: float, real_usd: float) -> None:
        """Solta a reserva e contabiliza o custo real. Se o gasto REAL acumulado
        ultrapassar o cap, REGISTRA (flush) e levanta BudgetExceeded — interrompe
        os próximos dispatches (a reserva-estimativa pode subestimar o real)."""
        # Mesma classe do sentinela -1/-1 do catálogo: custo REAL negativo vindo
        # do provider deflacionaria o spent e inflaria o cap. Nunca é legítimo.
        if real_usd < 0:
            real_usd = est_usd  # conservador: mantém a reserva como gasto
        with self._lock:
            self._reserved = max(0.0, self._reserved - est_usd)
            if self._persist:
                self._commit(real_usd, 1)
            else:
                self._spent += real_usd
                self._calls += 1
            if self._spent > self.cap_usd:
                raise BudgetExceeded(
                    f"custo REAL acumulado ${self._spent:.4f} ultrapassou o cap "
                    f"${self.cap_usd:.2f} — interrompendo próximos dispatches"
                )

    def charge_failure(self, est_usd: float) -> None:
        """Call falhou pós-dispatch: contabiliza a ESTIMATIVA como gasto
        (conservador — stream dropado pode ter sido cobrado). Sem cap-raise aqui
        (o erro original propaga); o cap pega no próximo reserve/reconcile."""
        with self._lock:
            self._reserved = max(0.0, self._reserved - est_usd)
            if self._persist:
                self._commit(est_usd, 1)
            else:
                self._spent += est_usd
                self._calls += 1

    def release(self, est_usd: float) -> None:
        """Solta a reserva sem cobrar (call NUNCA foi despachada)."""
        with self._lock:
            self._reserved = max(0.0, self._reserved - est_usd)
            if self._persist:  # some do disco: outros processos recuperam o orçamento
                self._commit(0.0, 0)

    @property
    def spent(self) -> float:
        with self._lock:
            return self._spent

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "spent_usd": round(self._spent, 6),
                "reserved_usd": round(self._reserved, 6),
                "calls": self._calls,
                "cap_usd": self.cap_usd,
            }


class ORClient:
    """Cliente OpenRouter com cap, retry e cálculo de custo via usage.cost."""

    def __init__(
        self,
        ledger: BudgetLedger | None = None,
        cap_usd: float = DEFAULT_CAP_USD,
        api_key: str | None = None,
        session: Session | None = None,
        outputs_dir: Path | None = None,
    ):
        self._outputs = outputs_dir or _default_outputs()
        self.ledger = ledger or BudgetLedger(
            cap_usd=cap_usd, ledger_path=self._outputs / "cost-ledger.json")
        self._api_key = api_key or load_api_key()
        self._session = session or Session()
        self._catalog: dict[str, dict] | None = None
        self._catalog_lock = threading.Lock()  # check-then-set thread-safe

    # ---- catálogo (pricing fallback + snapshot p/ reprodutibilidade) ----
    def catalog(self) -> dict[str, dict]:
        with self._catalog_lock:
            if self._catalog is not None:
                return self._catalog
            resp = self._session.get(f"{OPENROUTER_BASE}/models", timeout=30)
            resp.raise_for_status()
            data = resp.json().get("data", [])
            self._catalog = {m["id"]: m for m in data}
            self._outputs.mkdir(parents=True, exist_ok=True)
            (self._outputs / "catalog-snapshot.json").write_text(
                json.dumps(
                    {
                        mid: {
                            "pricing": m.get("pricing", {}),
                            "context_length": m.get("context_length"),
                            "created": m.get("created"),
                        }
                        for mid, m in self._catalog.items()
                    },
                    indent=2,
                )
            )
            return self._catalog

    def _price(self, model: str) -> tuple[float, float]:
        """(in_$/tok, out_$/tok) do catálogo. (0,0) se desconhecido."""
        m = self.catalog().get(model, {})
        p = m.get("pricing", {})
        return float(p.get("prompt", 0) or 0), float(p.get("completion", 0) or 0)

    def _estimate(self, model: str, messages: list[dict], max_tokens: int) -> float:
        """Teto pessimista de custo p/ a reserva: prompt_tokens*in + max_tokens*out.

        FAIL-CLOSED: modelo sem pricing no catálogo -> raise (recusa dispatch).
        Um floor arbitrário ($0.01) subestimaria modelos caros e furaria o cap.
        """
        m = self.catalog().get(model)
        pricing = (m or {}).get("pricing") or {}
        if m is None or ("prompt" not in pricing and "completion" not in pricing):
            raise RuntimeError(
                f"modelo {model!r} sem pricing no catálogo OpenRouter — "
                "recusando dispatch (fail-closed; sem estimativa não há cap)."
            )
        in_price, out_price = self._price(model)
        if in_price < 0 or out_price < 0:
            # Sentinela do catálogo (ex.: openrouter/fusion publica -1/-1): estimativa
            # negativa vira reserva negativa -> o cap deixa de existir e charge_failure
            # grava spend negativo (modo de falha já observado). Preço zero é legítimo
            # (modelos :free); negativo nunca é.
            raise RuntimeError(
                f"modelo {model!r} com pricing sentinela/negativo no catálogo "
                f"(prompt={in_price}, completion={out_price}) — recusando dispatch "
                "(fail-closed; estimativa negativa desligaria o cap)."
            )
        # ~4 chars/token (estimativa grosseira, conservadora-alta no out via max_tokens).
        prompt_chars = sum(len(str(msg.get("content", ""))) for msg in messages)
        prompt_tokens = prompt_chars / 4
        return prompt_tokens * in_price + max_tokens * out_price

    # ---- a chamada ----
    def chat(
        self,
        model: str,
        messages: list[dict],
        *,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        response_format: dict | None = None,
        extra_body: dict | None = None,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> dict[str, Any]:
        """Uma completion. Retorna {text, usage, cost_usd, provider, raw}.

        Cap reserve-then-reconcile: reserva o teto estimado ANTES de mandar.
        """
        est = self._estimate(model, messages, max_tokens)
        self.ledger.reserve(est)  # pode levantar BudgetExceeded -> não dispara

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,  # streaming: deep-research não-streamed estoura o gateway (502)
            "usage": {"include": True},  # pede o custo real (inclui busca do sonar)
        }
        if response_format:
            payload["response_format"] = response_format
        if extra_body:
            payload.update(extra_body)

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/alessioalionco/high-stakes",
            "X-Title": "high-stakes",
        }

        try:
            data = self._post_with_retry(headers, payload, timeout)
        except Exception:
            # CONSERVADOR: streams dropados podem ter sido cobrados upstream —
            # contabiliza a ESTIMATIVA como gasto em vez de soltar a reserva.
            print(f"[ledger] call {model} falhou pós-dispatch — estimativa "
                  f"${est:.4f} contabilizada como gasto (conservador).")
            self.ledger.charge_failure(est)
            raise

        usage = data.get("usage", {}) or {}
        cost = usage.get("cost")
        if cost is None:
            # fallback: token-math do catálogo (não pega busca do sonar, mas é o que há)
            in_price, out_price = self._price(model)
            cost = (
                usage.get("prompt_tokens", 0) * in_price
                + usage.get("completion_tokens", 0) * out_price
            )
        cost = float(cost or 0.0)
        self.ledger.reconcile(est, cost)

        choice = (data.get("choices") or [{}])[0]
        text = (choice.get("message") or {}).get("content") or ""
        return {
            "text": text,
            "usage": usage,
            "cost_usd": cost,
            "provider": data.get("provider"),
            "model": data.get("model", model),
            "raw": data,
        }

    class _Retriable(RuntimeError):
        """Erro transiente (429/5xx, inclusive erro-em-corpo-200) -> retenta."""

    def _post_with_retry(
        self, headers: dict, payload: dict, timeout: int
    ) -> dict:
        last_exc: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                resp = self._session.post(
                    f"{OPENROUTER_BASE}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=timeout,
                    stream=True,
                )
            except RequestException as exc:
                last_exc = exc
                self._sleep_backoff(attempt, None)
                continue

            if resp.status_code == 429 or 500 <= resp.status_code < 600:
                last_exc = RuntimeError(f"OpenRouter {resp.status_code}: {resp.text[:300]}")
                retry_after = resp.headers.get("Retry-After")
                resp.close()  # stream=True: fecha o socket antes de re-tentar
                self._sleep_backoff(attempt, retry_after)
                continue
            if resp.status_code != 200:
                # 4xx não-retriable (400/401/403/404) -> erro terminal
                raise RuntimeError(
                    f"OpenRouter {resp.status_code} (terminal): {resp.text[:500]}"
                )

            try:
                return self._consume_stream(resp)
            except ORClient._Retriable as exc:
                # erro-em-corpo-200 com code transiente (ex: 502 'connection lost')
                last_exc = exc
                resp.close()  # stream aberto -> fecha antes de re-tentar
                self._sleep_backoff(attempt, None)
                continue

        raise RuntimeError(f"OpenRouter falhou após {MAX_RETRIES} tentativas: {last_exc}")

    @staticmethod
    def _consume_stream(resp: Response) -> dict:
        """Acumula SSE -> dict {choices, usage, provider, citations}.

        OpenRouter embute erro de upstream num corpo 200 (campo `error` com
        `code`). Classifica: code 429/5xx -> _Retriable; senão terminal.
        """
        content_parts: list[str] = []
        usage: dict = {}
        provider: str | None = None
        model_id: str | None = None
        citations: list = []
        annotations: list = []
        for raw_line in resp.iter_lines():
            if not raw_line:
                continue
            line = raw_line.decode("utf-8", "replace")
            if line.startswith(": "):  # comentário keep-alive do SSE
                continue
            if not line.startswith("data: "):
                continue
            data_str = line[6:].strip()
            if data_str == "[DONE]":
                break
            try:
                obj = json.loads(data_str)
            except json.JSONDecodeError:
                continue
            err = obj.get("error")
            if err:
                code = err.get("code")
                msg = err.get("message", "")
                if code == 429 or (isinstance(code, int) and 500 <= code < 600):
                    raise ORClient._Retriable(f"upstream {code}: {msg}")
                raise RuntimeError(f"OpenRouter erro-em-corpo {code} (terminal): {msg}")
            provider = obj.get("provider", provider)
            model_id = obj.get("model", model_id)
            nu = obj.get("usage")
            # não deixa uma chunk de usage SEM cost sobrescrever uma que já tem cost
            if nu and (nu.get("cost") is not None or usage.get("cost") is None):
                usage = nu
            if obj.get("citations"):
                citations = obj["citations"]
            for ch in obj.get("choices", []):
                delta = ch.get("delta") or {}
                if delta.get("content"):
                    content_parts.append(delta["content"])
                for ann in delta.get("annotations") or []:
                    annotations.append(ann)
        message = {"content": "".join(content_parts)}
        if annotations:
            message["annotations"] = annotations
        return {
            "choices": [{"message": message}],
            "usage": usage,
            "provider": provider,
            "model": model_id,
            "citations": citations,
        }

    @staticmethod
    def _sleep_backoff(attempt: int, retry_after: str | None) -> None:
        if retry_after:
            try:
                time.sleep(min(float(retry_after), 30))
                return
            except ValueError:
                pass
        time.sleep(min(2 ** attempt, 30))


# ---- helper p/ Step 1 e smoke-tests manuais ----
def _cli_smoke() -> None:
    """`python3 or_client.py` -> 1 call barata de fumaça (GLM, ~$0.0001)."""
    client = ORClient(cap_usd=1.0)
    out = client.chat(
        "z-ai/glm-5.2",
        [{"role": "user", "content": "Responda só com a palavra: ok"}],
        max_tokens=16,
        extra_body={"reasoning": {"enabled": False}},
    )
    print("text:", repr(out["text"]))
    print("provider:", out["provider"])
    print("cost_usd:", out["cost_usd"])
    print("ledger:", client.ledger.snapshot())


if __name__ == "__main__":
    _cli_smoke()
