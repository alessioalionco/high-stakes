"""
or_client.py — Cliente OpenRouter compartilhado do motor high-stakes.

ZERO dependência externa [D8]: só stdlib. O transporte HTTP vem de
`http_client.py` (urllib), com a interface do `requests` preservada.

Responsabilidades:
  - chat(model, messages, ...) -> dict com {text, usage, cost_usd, provider, raw}.
  - Custo via `usage.cost` do OpenRouter (pega o custo de busca interna do sonar,
    que NÃO aparece no token-math). Fallback = pricing do catalog-snapshot.
  - Budget cap reserve-then-reconcile [D1+D3]: pré-debita o teto ESTIMADO ANTES
    do dispatch; se reservado > cap -> levanta BudgetExceeded antes de mandar a
    request. Pós-resposta reconcilia reservado -> custo real. Vale entre processos
    (reservas em voo são persistidas) e o teto de um run só DESCE, nunca sobe.
    **Best-effort, não "hard"**: a estimativa pode subestimar o custo real, e o
    que a interrompe é o reconcile — depois de a chamada já ter sido paga.
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
import math
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from .http_client import DeadlineExceeded, RequestException, Response, Session

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


class LedgerCorrupted(RuntimeError):
    """Ledger existe e não parseia: gasto desconhecido -> recusa dispatch (fail-closed)."""


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


_WARNED_NO_FLOCK = False

# A reserva de uma chamada EM VOO não pode expirar. O pior caso é MAX_RETRIES tentativas
# de `timeout` cada (4 × 1200s = 4800s no default do config), então um TTL de 1h podava
# reserva viva e apagava a do outro processo — dois processos reservavam o mesmo dinheiro.
RESERVATION_TTL_S = 4 * 1200 * 2  # 2h40: teto do pior caso, com folga


@contextlib.contextmanager
def _file_lock(path: Path):
    """Lock EXCLUSIVO entre processos no arquivo `path`.

    Sem fcntl (não-POSIX) degrada p/ no-op: o cap volta a valer só por processo. É
    aviso explícito, não falha silenciosa — o motor roda em macOS/Linux.
    """
    if fcntl is None:  # pragma: no cover
        global _WARNED_NO_FLOCK
        if not _WARNED_NO_FLOCK:
            _WARNED_NO_FLOCK = True
            print("[ledger] AVISO: fcntl indisponível nesta plataforma — o cap NÃO vale "
                  "entre processos. Rode um processo por vez.")
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
        # NaN e inf passavam: `nan > cap` e False, entao um ledger criado com cap NaN
        # reservava mil dolares sem erro. 0 e negativo barravam por ACIDENTE (a
        # projecao fica > cap), o que e a coisa certa pelo motivo errado -- e um cap 0
        # silencioso parece "sem orcamento", nao "config quebrada".
        if not isinstance(cap_usd, (int, float)) or isinstance(cap_usd, bool) \
                or not math.isfinite(cap_usd) or cap_usd <= 0:
            raise ValueError(
                f"cap_usd invalido: {cap_usd!r}. Precisa ser numero finito > 0 -- o cap "
                "e a unica coisa entre um bug de laco e a sua fatura.")
        self.cap_usd = cap_usd
        # O CAP NAO E ESTADO DO RUN -- o GASTO e. Isto ja foi `min(cap desta instancia,
        # cap no disco)` e a ideia estava errada nas duas pontas: uma instancia de cap
        # baixo que era RECUSADA nunca chegava a persistir o teto menor (entao o min
        # nao protegia nada), e quando persistia o ledger ficava cravado no menor teto
        # que ja passou por ali -- um typo de $0.50 barrava um run legitimo de $50 PARA
        # SEMPRE, e a unica saida era apagar o ledger, que apaga o historico de gasto
        # junto. O min protegia o dono do ledger contra ele mesmo, e cobrava isso caro.
        #
        # O que o teto por-run precisa garantir e que o GASTO acumule entre processos, e
        # disso o ledger da conta sozinho: cada instancia para no teto DELA contra o
        # total acumulado. Dois processos com tetos diferentes e um fato do operador,
        # nao um ataque.
        self._cap_efetivo = cap_usd
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
                self._cap_efetivo = self._effective_cap(d)

    # ---- disco (SEMPRE chamado sob _file_lock) ----
    def _read_disk(self) -> dict:
        """{spent_usd, calls, reservations} do disco, saneado. Ledger ilegível não
        aborta o run: avisa e trata como zerado (o cap segue valendo daí pra frente)."""
        def _sem_nao_finito(nome):
            # `json.loads` aceita os literais NaN/Infinity por default. Um ledger com
            # NaN nao "parece" corrompido: ele carrega, e a partir dai TODA comparacao
            # de teto vira no-op (`nan > cap` e False). Recusar no parse e a primeira
            # das duas redes; a segunda e o isfinite em cada numero, abaixo.
            raise ValueError(f"literal nao-finito no ledger: {nome}")

        try:
            raw = json.loads(self._ledger_path.read_text(),
                             parse_constant=_sem_nao_finito)
        except (json.JSONDecodeError, OSError) as e:
            if self._ledger_path.exists() and self._ledger_path.stat().st_size > 0:
                # FAIL CLOSED. Tratar ledger ilegível como "gasto zero" devolvia o cap
                # inteiro — é exatamente o oposto do que o reserve-then-reconcile existe
                # para garantir. Um arquivo que existe e não parseia é estado suspeito,
                # não estado inicial.
                raise LedgerCorrupted(
                    f"ledger ilegível em {self._ledger_path} ({type(e).__name__}: {e}). "
                    "O gasto acumulado é desconhecido, então nenhum dispatch é seguro. "
                    "Inspecione o arquivo e, se o gasto for aceitável, apague-o "
                    "explicitamente para recomeçar do zero.") from e
            raw = {}  # ausente ou vazio = run novo, legítimo
        except ValueError as e:
            # ValueError aqui e o literal nao-finito (ou JSON invalido que escapou do
            # ramo acima). Zerar seria devolver o cap inteiro -> fail-closed.
            if self._ledger_path.exists() and self._ledger_path.stat().st_size > 0:
                raise LedgerCorrupted(
                    f"ledger em {self._ledger_path} tem numero nao-finito ou JSON "
                    f"invalido ({e}). Gasto desconhecido: nenhum dispatch e seguro."
                ) from e
            raw = {}
        if not isinstance(raw, dict):
            raise LedgerCorrupted(
                f"ledger em {self._ledger_path} nao e um objeto JSON "
                f"({type(raw).__name__}) — estado ilegivel, fail-closed.")
        # AUSENTE é run novo; PRESENTE-E-PODRE é corrupção. O fail-closed só cobria JSON
        # ilegível, e entrava pela outra porta: `{"spent_usd": "muito"}` e
        # `{"spent_usd": null}` parseiam como JSON, caíam no `except`/no `or 0.0`, viravam
        # 0.0 em silêncio — e devolviam o CAP INTEIRO. É o mesmo fail-open que o
        # LedgerCorrupted existe para fechar. Zero por ausência é legítimo; zero por
        # "não consegui ler o número" nunca é.
        _AUSENTE = object()

        def _numero(chave, conv):
            v = raw.get(chave, _AUSENTE)
            if v is _AUSENTE:
                return conv(0)  # nunca gravado ainda: run novo
            # bool é subclasse de int em Python: `True` viraria 1.0 caladamente.
            if (isinstance(v, bool) or not isinstance(v, (int, float))
                    or not math.isfinite(v)):
                raise LedgerCorrupted(
                    f"ledger em {self._ledger_path} tem {chave}={v!r} "
                    f"({type(v).__name__}) onde devia haver número. O gasto acumulado é "
                    "desconhecido, então nenhum dispatch é seguro. Inspecione o arquivo "
                    "e, se o gasto for aceitável, apague-o explicitamente.")
            return conv(v)

        # negativo é outra história: ledger pré-fix tem o sentinela -1/-1 do catálogo.
        # É número, foi lido, e o conservador é tratar como zero — não como corrupção.
        spent = max(0.0, _numero("spent_usd", float))
        calls_bruto = _numero("calls", float)
        if calls_bruto != int(calls_bruto):
            raise LedgerCorrupted(
                f"ledger em {self._ledger_path} tem calls={calls_bruto!r}, que nao e\n"
                "inteiro. Este codigo nunca escreve fracao ali: o arquivo foi mexido.")
        calls = max(0, int(calls_bruto))
        res, now = {}, time.time()
        reservas = raw.get("reservations", _AUSENTE)
        if reservas is _AUSENTE:
            reservas = {}  # nunca gravado: run novo
        elif reservas is None:
            # `null` era convertido para {} DE PROPOSITO por mim, e e fail-open:
            # reserva em voo e o que impede dois processos de gastarem o mesmo
            # dinheiro. Apaga-las devolve tudo ao cap.
            raise LedgerCorrupted(
                f"ledger em {self._ledger_path} tem reservations=null. Reserva em voo "
                "ilegivel = nao despacha (apagar devolveria o orcamento ao cap).")
        if not isinstance(reservas, dict):
            raise LedgerCorrupted(
                f"ledger em {self._ledger_path} tem reservations={type(reservas).__name__} "
                "onde devia haver objeto. Reserva em voo de outro processo é o que impede "
                "dois runs de gastarem o mesmo dinheiro; ilegível = não despacha.")
        for k, v in reservas.items():
            # entrada MALFORMADA é corrupção (some do cálculo e AFROUXA o cap);
            # entrada bem-formada e VENCIDA é órfã de processo morto, e essa se descarta.
            if not isinstance(v, dict) or "usd" not in v or "ts" not in v:
                raise LedgerCorrupted(
                    f"ledger em {self._ledger_path}: reserva {k!r} malformada ({v!r}). "
                    "Descartá-la em silêncio devolveria o orçamento dela ao cap.")
            for campo in ("usd", "ts"):
                x = v[campo]
                if isinstance(x, bool) or not isinstance(x, (int, float)):
                    raise LedgerCorrupted(
                        f"ledger em {self._ledger_path}: reserva {k!r} tem {campo}="
                        f"{x!r} ({type(x).__name__}) onde devia haver numero. String "
                        "conversivel nao conta: quem escreveu isso nao foi este codigo.")
            try:
                usd, ts = float(v["usd"]), float(v["ts"])
            except (TypeError, ValueError) as e:
                raise LedgerCorrupted(
                    f"ledger em {self._ledger_path}: reserva {k!r} com número ilegível "
                    f"({v!r}).") from e
            if not (math.isfinite(usd) and math.isfinite(ts)):
                raise LedgerCorrupted(
                    f"ledger em {self._ledger_path}: reserva {k!r} com valor "
                    f"nao-finito ({v!r}). Reserva NaN some do somatorio e devolve o "
                    "dinheiro em voo ao cap.")
            if usd > 0 and now - ts < RESERVATION_TTL_S:  # descarta órfã de processo morto
                res[k] = {"usd": usd, "ts": ts}
        try:
            disk_cap = float(raw.get("cap_usd")) if raw.get("cap_usd") is not None else None
        except (TypeError, ValueError):
            disk_cap = None
        return {"spent_usd": spent, "calls": calls, "reservations": res,
                "cap_usd": disk_cap}

    def _effective_cap(self, disk: dict) -> float:
        """O MENOR entre o cap desta instância e o que já está no ledger.

        O cap era escrito no arquivo e nunca lido de volta: dois processos com caps
        diferentes no mesmo run davam cap efetivo = o MAIOR. Quem abriu com $5 achava que
        o teto era $5 enquanto o outro gastava $50 no mesmo ledger."""
        dc = disk.get("cap_usd")
        if dc is None or not math.isfinite(dc) or dc <= 0:
            return self.cap_usd
        if dc != self.cap_usd:
            # AVISO, nao regra. Ver a nota no __init__: transformar isto em `min`
            # envenenava o ledger de forma irreversivel.
            print(f"[ledger] nota: este ledger foi aberto antes com cap ${dc:.2f} e "
                  f"esta instância pediu ${self.cap_usd:.2f}. O GASTO acumulado é "
                  "compartilhado; cada instância para no teto dela.")
        return self.cap_usd

    def _write_disk(self, spent: float, calls: int, reservations: dict,
                    cap: float | None = None) -> None:
        """Grava o estado do run. `cap` é o teto EFETIVO — nunca `self.cap_usd`.

        Gravar o cap da instância era o bug: o piso do run SOBE. Processo A com cap $5
        fixa o teto do run em $5; processo B com cap $50 entra, respeita o $5 para si
        (o min), mas grava $50 — e o processo C seguinte lê $50 como se fosse o teto do
        run. O cap volta a ser por-processo, que é exatamente o que o teto por run
        existe para impedir. O piso de um run só pode DESCER.
        """
        payload = json.dumps({
            "spent_usd": round(spent, 6),
            "calls": calls,
            "cap_usd": self._cap_efetivo if cap is None else cap,
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
            self._cap_efetivo = self._effective_cap(d)  # o piso do run só desce
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
                if projected > self._cap_efetivo:
                    # `cap` só existe no ramo persistente abaixo. Trocar as duas ocorrências
                    # de uma vez fez este caminho levantar UnboundLocalError em vez de
                    # BudgetExceeded — e 247 testes verdes não pegaram, porque nenhum
                    # exercitava persist=False acima do cap.
                    raise BudgetExceeded(
                        f"reserva ${est_usd:.4f} estouraria o cap "
                        f"(spent ${self._spent:.4f} + reserved ${self._reserved:.4f} "
                        f"+ est = ${projected:.4f} > ${self._cap_efetivo:.2f})"
                    )
                self._reserved += est_usd
                return
            with _file_lock(self._lock_path):
                d = self._read_disk()
                others = sum(v["usd"] for k, v in d["reservations"].items()
                             if k != self._owner)
                self._spent, self._calls = d["spent_usd"], d["calls"]
                cap = self._effective_cap(d)
                self._cap_efetivo = cap
                projected = d["spent_usd"] + others + self._reserved + est_usd
                if projected > cap:
                    raise BudgetExceeded(
                        f"reserva ${est_usd:.4f} estouraria o cap "
                        f"(spent ${d['spent_usd']:.4f} + reserved ${self._reserved:.4f} "
                        f"+ outros processos ${others:.4f} "
                        f"+ est = ${projected:.4f} > ${cap:.2f})"
                    )
                self._reserved += est_usd
                d["reservations"][self._owner] = {
                    "usd": round(self._reserved, 6), "ts": time.time()}
                self._write_disk(d["spent_usd"], d["calls"], d["reservations"], cap)

    def reconcile(self, est_usd: float, real_usd: float) -> None:
        """Solta a reserva e contabiliza o custo real. Se o gasto REAL acumulado
        ultrapassar o cap, REGISTRA (flush) e levanta BudgetExceeded — interrompe
        os próximos dispatches (a reserva-estimativa pode subestimar o real)."""
        # Mesma classe do sentinela -1/-1 do catálogo: custo REAL negativo vindo
        # do provider deflacionaria o spent e inflaria o cap. Nunca é legítimo.
        if not math.isfinite(real_usd) or real_usd < 0:
            # Mesma familia do sentinela negativo, e pior: `nan > cap` e False, entao
            # um custo NaN nao deflaciona -- ele DESLIGA o teto, e o gasto vira NaN
            # para sempre. Conservador nos dois casos: vale a reserva.
            real_usd = est_usd  # conservador: mantém a reserva como gasto
        with self._lock:
            self._reserved = max(0.0, self._reserved - est_usd)
            if self._persist:
                self._commit(real_usd, 1)
            else:
                self._spent += real_usd
                self._calls += 1
            if self._spent > self._cap_efetivo:
                raise BudgetExceeded(
                    f"custo REAL acumulado ${self._spent:.4f} ultrapassou o cap "
                    f"${self._cap_efetivo:.2f} — interrompendo próximos dispatches"
                )

    def charge_extra(self, usd: float) -> None:
        """Cobra gasto SEM mexer em reserva: tentativas anteriores de um retry que já
        rodaram no provedor. O retry redispara até MAX_RETRIES gerações completas, e o
        ledger contabilizava UMA — subcontagem de até 4x, invisível para o cap."""
        if usd <= 0:
            return
        with self._lock:
            if self._persist:
                self._commit(usd, 0)
            else:
                self._spent += usd

    def charge_failure(self, est_usd: float, extra_usd: float = 0.0) -> None:
        """Call falhou pós-dispatch: contabiliza a ESTIMATIVA como gasto
        (conservador — stream dropado pode ter sido cobrado). Sem cap-raise aqui
        (o erro original propaga); o cap pega no próximo reserve/reconcile.

        `extra_usd` sao as geracoes ANTERIORES que ja rodaram no provedor. Entram AQUI,
        no mesmo commit, e nao numa chamada separada de `charge_extra`: duas escritas
        eram duas janelas de lock, e entre elas o ledger no disco mostrava gasto MENOR
        que o real -- outro processo lia esse numero e reservava em cima dele. Cada
        escrita era atomica; o que nao era atomico era a CONTA."""
        total = est_usd + max(0.0, extra_usd)
        with self._lock:
            self._reserved = max(0.0, self._reserved - est_usd)
            if self._persist:
                self._commit(total, 1)
            else:
                self._spent += total
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
                "cap_usd": self._cap_efetivo,
                "cap_solicitado_usd": self.cap_usd,
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
        if not (math.isfinite(in_price) and math.isfinite(out_price)):
            # O catalogo vem do provedor. "nan"/"Infinity" viram float sem reclamar, e
            # dai a estimativa inteira e nao-finita: a reserva passa (nan > cap e
            # False) e o cap deixa de existir para essa chamada.
            raise RuntimeError(
                f"modelo {model!r} com pricing nao-finito no catalogo "
                f"(prompt={in_price}, completion={out_price}) — recusando dispatch.")
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
        # extra_body é aplicado DEPOIS da estimativa, então uma chave que mude O QUE é
        # despachado faz o motor reservar o preço de uma chamada e disparar outra: o cap
        # é furado por fator arbitrário, sem erro nenhum. `cells.py` encaminha o `request`
        # que veio da tarefa, então isto é alcançável por dado comum, não só por malícia.
        #
        # Isto era uma DENYLIST de 5 chaves, e denylist aqui é a escolha errada: ela
        # protege do que alguém lembrou de listar. Passavam batido `models` (lista de
        # fallback — TROCA qual modelo cobra), `provider` (rota e preço), `route`, `n`
        # (multiplica a geração e a fatura) e `max_completion_tokens`. Allowlist inverte
        # o default: chave nova do provedor chega BARRADA e alguém decide, em vez de
        # chegar liberada e ninguém descobrir.
        _PERMITIDAS = {
            # amostragem e formato — não mudam qual modelo roda nem quantas gerações saem
            "temperature", "top_p", "top_k", "min_p", "top_a", "seed", "stop",
            "frequency_penalty", "presence_penalty", "repetition_penalty", "logit_bias",
            "response_format", "structured_outputs",
            # tool calling
            "tools", "tool_choice", "parallel_tool_calls",
            # raciocínio: é o que o roster usa pra desligar reasoning em modelo caro
            "reasoning", "include_reasoning",
            # metadados que não afetam custo
            "user", "metadata", "transforms",
            # `plugins` NAO entra: e por onde a OpenRouter liga add-on pago (web
            # search, por exemplo), e a taxa do add-on nao esta em `_estimate`. O
            # chamador reservaria so o custo de token e descobriria o resto na fatura.
        }
        if extra_body:
            intrusas = sorted(set(extra_body) - _PERMITIDAS)
            if intrusas:
                raise ValueError(
                    f"extra_body não permite {intrusas}. A estimativa que reserva o "
                    "orçamento roda ANTES do dispatch, então chave que troque modelo, "
                    "rota, provedor ou número de gerações fura o cap silenciosamente. "
                    f"Permitidas: {sorted(_PERMITIDAS)}. Se a chave for realmente "
                    "inofensiva, adicione-a à allowlist junto com o motivo.")
        # O TTL da reserva assume um teto de duracao por tentativa. `timeout` e
        # parametro livre e `cells.py` encaminha o `request` da tarefa, entao um timeout
        # maior que a premissa deixa a reserva EXPIRAR com a chamada ainda viva -- e ai
        # outro processo gasta o mesmo dinheiro.
        if timeout * MAX_RETRIES > RESERVATION_TTL_S:
            raise ValueError(
                f"timeout={timeout}s x {MAX_RETRIES} tentativas passa do TTL da reserva "
                f"({RESERVATION_TTL_S}s): a reserva expiraria com a chamada em voo e "
                "outro processo poderia gastar o mesmo orcamento. Suba "
                "RESERVATION_TTL_S junto se o timeout precisa ser maior.")
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

        contagem: dict = {"geradas": 0}
        try:
            data, geradas = self._post_with_retry(headers, payload, timeout, contagem)
        except Exception:
            # CONSERVADOR: streams dropados podem ter sido cobrados upstream —
            # contabiliza a ESTIMATIVA como gasto em vez de soltar a reserva.
            print(f"[ledger] call {model} falhou pós-dispatch — estimativa "
                  f"${est:.4f} contabilizada como gasto (conservador).")
            # UMA estimativa por tentativa COBRÁVEL — nem mais, nem menos. Cobrável é a
            # que produziu conteúdo ou morreu em estado desconhecido; a recusa limpa
            # (429/5xx no header) não é. Se NENHUMA foi cobrável, o provedor recusou
            # tudo e não há o que pagar: solta a reserva e pronto. Cobrar "uma por
            # garantia" ali inflava o ledger sem um centavo real por trás, e ledger
            # inflado faz o motor parar cedo e recusar chamada legítima.
            # Tudo num commit só: em duas escritas, entre elas o disco mostra gasto
            # menor que o real e outro processo reserva em cima disso.
            cobraveis = contagem.get("geradas", 0)
            if cobraveis:
                print(f"[ledger] {cobraveis} tentativa(s) cobrável(is) — "
                      f"${est * cobraveis:.4f} no total.")
                self.ledger.charge_failure(est, extra_usd=est * (cobraveis - 1))
            else:
                print(f"[ledger] o provedor recusou todas as tentativas (nada gerado) "
                      f"— soltando a reserva de ${est:.4f}.")
                self.ledger.release(est)
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
        if not math.isfinite(cost):
            # `usage.cost` vem do provedor. Nao-finito aqui envenena o ledger inteiro.
            print(f"[ledger] custo nao-finito ({cost}) reportado para {model} — "
                  f"usando a estimativa ${est:.4f} (conservador).")
            cost = est
        if geradas:
            # tentativas anteriores rodaram no provedor: estimativa cada, senão o gasto
            # real fica até 4x acima do que o ledger conhece.
            print(f"[ledger] {geradas} tentativa(s) anterior(es) já gerada(s) — "
                  f"cobrando ${est * geradas:.4f} além do custo final.")
            self.ledger.charge_extra(est * geradas)
        choice = (data.get("choices") or [{}])[0]
        text = (choice.get("message") or {}).get("content") or ""
        resposta = {
            "text": text,
            "usage": usage,
            "cost_usd": cost,
            "provider": data.get("provider"),
            "model": data.get("model", model),
            "raw": data,
        }

        # O reconcile é o ponto onde o custo REAL pode estourar o cap — e ele levanta.
        # A resposta acima JÁ FOI PAGA: deixar a exceção subir pelada joga no lixo um
        # texto que custou dinheiro, e o run que reprocessar vai pagar de novo. O cap
        # continua interrompendo (é o certo: o dinheiro acabou), mas o resultado viaja
        # junto para quem chamou poder salvá-lo.
        try:
            self.ledger.reconcile(est, cost)
        except BudgetExceeded as e:
            e.resposta = resposta
            raise

        return resposta

    class _Retriable(RuntimeError):
        """Erro transiente (429/5xx, inclusive erro-em-corpo-200) -> retenta.

        `recusa` diz se o upstream RECUSOU explicitamente (429 no corpo) — não se ele
        gerou. A diferença importa: já houve aqui um campo `gerou` decidido pelo código
        do erro, e ele errava nos dois sentidos. A conta certa combina isto com o que
        foi medido no fio:
          · recusa explícita → cobrável só se veio CONTEÚDO antes dela;
          · qualquer outro fim (truncado, erro de servidor) → cobrável se veio
            QUALQUER byte, porque chunk truncado no meio do JSON não vira texto mas
            significa que o provedor já estava gerando.
        """

        def __init__(self, msg: str, recusa: bool = False):
            super().__init__(msg)
            self.recusa = recusa

    def _post_with_retry(
        self, headers: dict, payload: dict, timeout: int,
        contagem: dict | None = None,
    ) -> tuple[dict, int]:
        """Devolve (resposta, nº de tentativas ANTERIORES que já geraram no provedor).

        `contagem` é um espelho MUTÁVEL de `geradas` para quem chama. O contador vivia
        só aqui dentro: quando o retry esgotava, ele morria com a exceção (virava texto
        na mensagem) e o caminho de falha do `chat` cobrava UMA estimativa, quando o
        provedor tinha gerado e cobrado até MAX_RETRIES vezes. `charge_extra` era
        inalcançável exatamente no ramo onde a subcontagem é maior.
        """
        contagem = {} if contagem is None else contagem
        contagem.setdefault("geradas", 0)
        last_exc: Exception | None = None
        # COBRÁVEL = a tentativa produziu conteúdo (o provedor gerou, logo cobrou) OU
        # terminou em estado AMBÍGUO (transporte caiu com o stream aberto, 5xx do
        # servidor). NÃO é cobrável só a recusa explícita: 429 é o provedor dizendo
        # que não fez. A regra antiga olhava o CÓDIGO do erro e errava nos dois
        # sentidos: stream que morre depois de 3 chunks não contava (subconta), e
        # stream vazio que termina sem [DONE] contava (sobreconta).
        geradas = 0
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
                # `.text` lê o corpo, que com stream=True ainda está aberto: se a
                # leitura estourar o prazo (DeadlineExceeded) ou o socket cair, a
                # exceção subia de DENTRO do ramo retriável e o retry nunca acontecia —
                # o motor desistia de uma chamada que o provedor mandou repetir. O
                # corpo aqui é só para a mensagem de erro; não vale o run.
                try:
                    detalhe = resp.text[:300]
                except Exception as e:  # noqa: BLE001 — corpo ilegível não é terminal
                    detalhe = f"(corpo ilegível: {type(e).__name__})"
                last_exc = RuntimeError(f"OpenRouter {resp.status_code}: {detalhe}")
                # 429 e 5xx NÃO são a mesma coisa para a cobrança, e tratá-los
                # junto foi erro meu que uma regressão pegou:
                #   429 = o provedor DIZ que recusou. Nada gerado, nada cobrado.
                #   5xx = erro de servidor. Ele pode ter gerado e falhado ao
                #         entregar; o estado é AMBÍGUO. Conservador é cobrar.
                if resp.status_code != 429:
                    geradas += 1
                    contagem["geradas"] = geradas
                retry_after = resp.headers.get("Retry-After")
                resp.close()  # stream=True: fecha o socket antes de re-tentar
                self._sleep_backoff(attempt, retry_after)
                continue
            if resp.status_code != 200:
                # 4xx não-retriable (400/401/403/404) -> erro terminal. Mesmo cuidado
                # do ramo acima: corpo ilegível não pode trocar o erro real por um
                # DeadlineExceeded que esconde o status que causou a parada.
                try:
                    detalhe = resp.text[:500]
                except Exception as e:  # noqa: BLE001
                    detalhe = f"(corpo ilegível: {type(e).__name__})"
                raise RuntimeError(
                    f"OpenRouter {resp.status_code} (terminal): {detalhe}"
                )

            progresso = {"bytes": 0, "conteudo": 0}
            try:
                return self._consume_stream(resp, progresso), geradas
            except (RequestException, OSError) as exc:
                # Transporte caiu com o stream já aberto (RST, timeout de leitura,
                # IncompleteRead). É a falha DOMINANTE numa chamada de 300-1200s, e antes
                # escapava do loop: 1 tentativa de MAX_RETRIES, cobrada como fracasso.
                # Estado DESCONHECIDO: o provedor pode ter gerado tudo e o retorno é que
                # se perdeu. Conservador é cobrar.
                geradas += 1
                contagem["geradas"] = geradas
                last_exc = exc
                resp.close()
                self._sleep_backoff(attempt, None)
                continue
            except ORClient._Retriable as exc:
                # erro-em-corpo-200 ou stream truncado. Quem decide é o que foi
                # PRODUZIDO, não o código: um 429-em-corpo pode chegar depois de
                # conteúdo (foi cobrado), e um stream vazio pode terminar sem [DONE]
                # sem nada ter sido gerado (não foi).
                cobravel = (progresso["conteudo"] > 0 if exc.recusa
                            else progresso["bytes"] > 0)
                if cobravel:
                    geradas += 1
                    contagem["geradas"] = geradas
                last_exc = exc
                resp.close()  # stream aberto -> fecha antes de re-tentar
                self._sleep_backoff(attempt, None)
                continue

        raise RuntimeError(
            f"OpenRouter falhou após {MAX_RETRIES} tentativas ({geradas} já geradas "
            f"e cobradas pelo provedor): {last_exc}")

    @staticmethod
    def _consume_stream(resp: Response, progresso: dict | None = None) -> dict:
        """Acumula SSE -> dict {choices, usage, provider, citations}.

        OpenRouter embute erro de upstream num corpo 200 (campo `error` com
        `code`). Classifica: code 429/5xx -> _Retriable; senão terminal.

        `progresso["bytes"]` conta o que ja veio NO FIO, e e atualizado a cada linha --
        inclusive quando esta funcao levanta. E o unico jeito de o laco de retry saber
        se aquela tentativa foi cobrada la em cima: o codigo do erro nao diz (um
        429-em-corpo pode chegar DEPOIS de conteudo, e um stream vazio pode terminar
        sem [DONE] sem nada ter sido gerado).

        Conta BYTE recebido, nao conteudo parseado: um chunk truncado no meio do JSON
        nao vira texto nenhum, mas os bytes estavam no fio -- o provedor gerou e
        cobrou. Medir pelo parse subcontava exatamente a falha mais comum de streaming.
        """
        progresso = {} if progresso is None else progresso
        progresso.setdefault("bytes", 0)      # veio algo no fio?
        progresso.setdefault("conteudo", 0)   # veio TEXTO, e nao so mensagem de erro?
        saw_done = False
        content_parts: list[str] = []
        usage: dict = {}
        provider: str | None = None
        model_id: str | None = None
        citations: list = []
        annotations: list = []
        for raw_line in resp.iter_lines():
            progresso["bytes"] += len(raw_line or b"")
            if not raw_line:
                continue
            line = raw_line.decode("utf-8", "replace")
            if line.startswith(": "):  # comentário keep-alive do SSE
                continue
            if not line.startswith("data: "):
                continue
            data_str = line[6:].strip()
            if data_str == "[DONE]":
                saw_done = True
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
                    # 429 = recusa (nada gerado, nada cobrado lá). 5xx = o provedor
                    # começou e morreu: conservador é assumir que gerou e cobrou.
                    raise ORClient._Retriable(f"upstream {code}: {msg}",
                                              recusa=(code == 429))
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
                    progresso["conteudo"] += len(delta["content"])
                for ann in delta.get("annotations") or []:
                    annotations.append(ann)
        # Stream que acaba SEM o [DONE] foi truncado — conexão caiu, provider morreu no
        # meio. `readline()` devolve EOF em vez de levantar, então a resposta parcial
        # passava como completa: texto cortado no meio da palavra virava célula "ok" e
        # ninguém via. Truncamento é transiente -> volta para o retry.
        if not saw_done:
            raise ORClient._Retriable(
                f"stream truncado: terminou sem [DONE] após {len(content_parts)} chunks "
                "(conexão caiu no meio da resposta)")

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
