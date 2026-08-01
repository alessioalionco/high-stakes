#!/usr/bin/env python3
"""test_or_client.py — suíte executável do caminho do DINHEIRO (convenção deste projeto).

Cobre três lacunas que eram falhas SILENCIOSAS (o motor seguia rodando e dando cap por
bom, gastando 2x):

  T11 — cliente HTTP sobre a stdlib. Contra um servidor http.server de verdade, não mock:
        se `urllib` divergir do contrato que o retry espera (não-2xx tem de voltar como
        RESPOSTA, com Retry-After legível), o 429 vira erro terminal e o run morre.
  T4  — cap CROSS-PROCESSO. Dois processos no mesmo run liam `spent=0` e o último write
        vencia: cap furado em 2x, sem sinal nenhum.
  T5  — cobrança no fracasso. Stream dropado pode ter sido cobrado upstream; se a falha
        não debitar, o cap superestima o orçamento restante.
"""
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from high_stakes import or_client
from high_stakes.or_client import BudgetExceeded, BudgetLedger, ORClient
from high_stakes.http_client import RequestException, Session

ROOT = Path(__file__).resolve().parents[1]  # raiz do repo/plugin


# ---------------------------------------------------------------- servidor de teste
class Handler(BaseHTTPRequestHandler):
    """mode é de CLASSE: cada teste ajusta antes de chamar."""
    mode = "ok"
    hits = 0

    def log_message(self, *a):  # silencia o log do http.server
        pass

    def _send(self, code, body: bytes, headers: dict | None = None):
        self.send_response(code)
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.endswith("/models"):
            body = json.dumps({"data": [
                {"id": "test/model", "pricing": {"prompt": "0.000001",
                                                 "completion": "0.000002"}},
            ]}).encode()
            return self._send(200, body, {"Content-Type": "application/json"})
        if self.path == "/echo-headers":
            return self._send(200, json.dumps(dict(self.headers)).encode())
        if self.path == "/429":
            return self._send(429, b"slow down", {"Retry-After": "7"})
        if self.path == "/400":
            return self._send(400, b"bad request")
        if self.path == "/lines":
            return self._send(200, b"alpha\nbeta\r\ngamma\n")
        return self._send(404, b"nope")

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n)
        if self.path == "/echo":
            return self._send(200, raw, {"Content-Type": "application/json"})
        Handler.hits += 1
        if Handler.mode == "always_500":
            return self._send(500, b"upstream boom")
        sse = (
            b'data: {"choices":[{"delta":{"content":"oi"}}]}\n\n'
            b'data: {"choices":[{"delta":{"content":" mundo"}}],'
            b'"usage":{"cost":0.5,"prompt_tokens":10,"completion_tokens":2}}\n\n'
            b"data: [DONE]\n\n"
        )
        return self._send(200, sse, {"Content-Type": "text/event-stream"})


def start_server() -> tuple[HTTPServer, str]:
    srv = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_port}"


# ---------------------------------------------------------------- T4: subprocessos
# Roda em processo separado: reserva, segura a reserva, e só então reconcilia — a janela
# em que o OUTRO processo precisa enxergar a reserva pra não furar o cap.
CHILD = """
import sys, time, json
sys.path.insert(0, {root!r})
from high_stakes.or_client import BudgetLedger, BudgetExceeded
led = BudgetLedger(cap_usd={cap}, ledger_path=__import__("pathlib").Path({path!r}))
try:
    led.reserve({amount})
except BudgetExceeded:
    print("BLOCKED"); sys.exit(0)
time.sleep({hold})
led.reconcile({amount}, {amount})
print("SPENT")
"""


def run_children(path: Path, cap: float, amount: float, hold: float, n: int = 2):
    procs = [subprocess.Popen(
        [sys.executable, "-c", CHILD.format(root=str(ROOT), cap=cap, path=str(path),
                                            amount=amount, hold=hold)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(n)]
    return [p.communicate()[0].strip().splitlines()[-1] for p in procs]


def main() -> int:
    srv, base = start_server()
    tmp = Path(tempfile.mkdtemp())
    results: list[bool] = []

    def case(name, cond):
        print(("PASS " if cond else "FAIL ") + name)
        results.append(bool(cond))

    try:
        s = Session()

        # ---- T11: cliente HTTP contra servidor real ----
        r = s.get(f"{base}/api/v1/models", timeout=5)
        case("GET 200 + .json() decodifica",
             r.status_code == 200 and r.json()["data"][0]["id"] == "test/model")

        r = s.post(f"{base}/echo", json={"a": 1, "b": "ç"}, timeout=5)
        case("POST envia JSON (round-trip preserva unicode)", r.json() == {"a": 1, "b": "ç"})

        r = s.post(f"{base}/echo", headers={"X-Title": "hs"}, json={}, timeout=5)
        case("POST seta Content-Type sozinho", r.status_code == 200)

        r = s.get(f"{base}/429", timeout=5)
        case("REGRESSÃO T11: 429 volta como RESPOSTA, não exceção (senão o retry morre)",
             r.status_code == 429)
        case("REGRESSÃO T11: Retry-After legível na resposta de erro",
             r.headers.get("Retry-After") == "7")
        case("corpo do erro de 429 legível em .text", "slow down" in r.text)

        r = s.get(f"{base}/400", timeout=5)
        case("4xx terminal também volta como resposta com corpo",
             r.status_code == 400 and "bad request" in r.text)

        r = s.get(f"{base}/lines", timeout=5)
        case("iter_lines devolve linhas sem terminador (\\n e \\r\\n)",
             list(r.iter_lines()) == [b"alpha", b"beta", b"gamma"])

        try:
            s.get("http://127.0.0.1:1/nada", timeout=2)
            case("erro de transporte vira RequestException", False)
        except RequestException:
            case("erro de transporte vira RequestException", True)
        except Exception as e:
            case(f"erro de transporte vira RequestException (veio {type(e).__name__})", False)

        r = s.get(f"{base}/echo-headers", timeout=5)
        case("Accept-Encoding: identity é explícito (urllib não descomprime)",
             r.json().get("Accept-Encoding") == "identity")

        # ---- integração: chat() completo contra o servidor ----
        or_client.OPENROUTER_BASE = f"{base}/api/v1"
        or_client.ORClient._sleep_backoff = staticmethod(lambda *a, **k: None)  # sem espera

        led = BudgetLedger(cap_usd=10.0, ledger_path=tmp / "run1" / "cost-ledger.json")
        c = ORClient(ledger=led, api_key="k", outputs_dir=tmp / "run1")
        out = c.chat("test/model", [{"role": "user", "content": "oi"}], max_tokens=16)
        case("chat() acumula SSE e devolve texto", out["text"] == "oi mundo")
        case("chat() usa usage.cost do provider", out["cost_usd"] == 0.5)
        case("ledger contabiliza o custo real", abs(led.spent - 0.5) < 1e-9)
        case("reserva foi solta após reconcile", led.snapshot()["reserved_usd"] == 0.0)

        disk = json.loads((tmp / "run1" / "cost-ledger.json").read_text())
        case("ledger no DISCO reflete o gasto", abs(disk["spent_usd"] - 0.5) < 1e-9)
        case("reserva não fica órfã no disco", not disk.get("reservations"))

        # ---- T5: falha pós-dispatch é COBRADA ----
        Handler.mode = "always_500"
        led2 = BudgetLedger(cap_usd=10.0, ledger_path=tmp / "run2" / "cost-ledger.json")
        c2 = ORClient(ledger=led2, api_key="k", outputs_dir=tmp / "run2")
        Handler.hits = 0
        try:
            c2.chat("test/model", [{"role": "user", "content": "oi"}], max_tokens=16)
            case("REGRESSÃO T5: falha propaga", False)
        except RuntimeError:
            case("REGRESSÃO T5: falha propaga", True)
        case("REGRESSÃO T5: 500 é retriável (tentou MAX_RETRIES vezes)",
             Handler.hits == or_client.MAX_RETRIES)
        case("REGRESSÃO T5: estimativa é COBRADA no fracasso (stream pode ter sido cobrado)",
             led2.spent > 0)
        d2 = json.loads((tmp / "run2" / "cost-ledger.json").read_text())
        case("REGRESSÃO T5: cobrança do fracasso PERSISTE no disco", d2["spent_usd"] > 0)
        case("REGRESSÃO T5: reserva do fracasso não fica órfã", not d2.get("reservations"))
        led2b = BudgetLedger(cap_usd=10.0, ledger_path=tmp / "run2" / "cost-ledger.json")
        case("REGRESSÃO T5: instância nova herda o gasto (cap não reseta)",
             abs(led2b.spent - led2.spent) < 1e-9)
        Handler.mode = "ok"

        # ---- T4: cap cross-processo ----
        p4 = tmp / "run4" / "cost-ledger.json"
        outs = run_children(p4, cap=1.0, amount=0.6, hold=1.0)
        case(f"REGRESSÃO T4: 2 processos, cap $1, $0.60 cada -> só 1 gasta (veio {outs})",
             sorted(outs) == ["BLOCKED", "SPENT"])
        d4 = json.loads(p4.read_text())
        case("REGRESSÃO T4: disco não excede o cap", d4["spent_usd"] <= 1.0)

        p5 = tmp / "run5" / "cost-ledger.json"
        outs = run_children(p5, cap=10.0, amount=0.3, hold=0.3)
        d5 = json.loads(p5.read_text())
        case("REGRESSÃO T4: gastos de 2 processos SOMAM (não last-write-wins)",
             outs == ["SPENT", "SPENT"] and abs(d5["spent_usd"] - 0.6) < 1e-6
             and d5["calls"] == 2)

        # ---- reservas: visibilidade e higiene ----
        pr = tmp / "run6" / "cost-ledger.json"
        a = BudgetLedger(cap_usd=1.0, ledger_path=pr)
        a.reserve(0.8)
        b = BudgetLedger(cap_usd=1.0, ledger_path=pr)
        try:
            b.reserve(0.5)
            case("reserva em voo de OUTRO processo bloqueia o dispatch", False)
        except BudgetExceeded:
            case("reserva em voo de OUTRO processo bloqueia o dispatch", True)
        a.release(0.8)
        try:
            b.reserve(0.5)
            case("release devolve o orçamento aos outros processos", True)
        except BudgetExceeded:
            case("release devolve o orçamento aos outros processos", False)

        # órfã de processo morto não pode travar o run pra sempre
        po = tmp / "run7" / "cost-ledger.json"
        po.parent.mkdir(parents=True)
        po.write_text(json.dumps({
            "spent_usd": 0.0, "calls": 0, "cap_usd": 1.0,
            "reservations": {"999999-dead": {
                "usd": 0.9, "ts": time.time() - or_client.RESERVATION_TTL_S - 10}},
        }))
        o = BudgetLedger(cap_usd=1.0, ledger_path=po)
        try:
            o.reserve(0.5)
            case("reserva órfã (processo morto) expira pelo TTL", True)
        except BudgetExceeded:
            case("reserva órfã (processo morto) expira pelo TTL", False)

        # ---- fail-closed que já existia: não regredir ----
        c._catalog = {"neg/model": {"pricing": {"prompt": "-1", "completion": "-1"}}}
        try:
            c._estimate("neg/model", [{"role": "user", "content": "x"}], 10)
            case("pricing sentinela -1/-1 segue fail-closed", False)
        except RuntimeError:
            case("pricing sentinela -1/-1 segue fail-closed", True)

        led9 = BudgetLedger(cap_usd=10.0, persist=False)
        led9.reserve(1.0)
        led9.reconcile(1.0, -5.0)
        case("custo REAL negativo não deflaciona o gasto", abs(led9.spent - 1.0) < 1e-9)

        print(f"{sum(results)}/{len(results)} testes ok")
        return 0 if all(results) else 1
    finally:
        srv.shutdown()
        __import__("shutil").rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
