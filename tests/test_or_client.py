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
import math
import os
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from high_stakes import or_client
from high_stakes.or_client import (BudgetExceeded, BudgetLedger,
                                   LedgerCorrupted, ORClient)
import urllib.request

from high_stakes import http_client
from high_stakes.http_client import DeadlineExceeded, RequestException, Session

ROOT = Path(__file__).resolve().parents[1]  # raiz do repo/plugin


# ---------------------------------------------------------------- servidor de teste
class Handler(BaseHTTPRequestHandler):
    """mode é de CLASSE: cada teste ajusta antes de chamar."""
    mode = "ok"
    hits = 0
    trap_url = ""
    trap_headers = None

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
        if self.path == "/redirect-para-armadilha":
            return self._send(302, b"", {"Location": Handler.trap_url})
        if self.path == "/armadilha":
            Handler.trap_headers = dict(self.headers)
            return self._send(200, b"peguei")
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
        if Handler.mode == "corta_no_meio":
            # headers + corpo PARCIAL, depois derruba: a falha dominante numa chamada
            # longa de streaming. Content-Length maior que o enviado força erro de leitura.
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Content-Length", "9999")
            self.end_headers()
            self.wfile.write(b'data: {"choices":[{"delta":{"content":"me')
            self.wfile.flush()
            self.close_connection = True
            return
        if Handler.mode == "always_500":
            return self._send(500, b"upstream boom")
        if Handler.mode == "erro_429_no_corpo":
            # 200 no header, erro 429 NO CORPO do stream. Rate limit = o provedor
            # RECUSOU; nada foi gerado e nada foi cobrado lá. As duas primeiras
            # tentativas recusam, a terceira responde de verdade.
            if Handler.hits <= 2:
                body = (b'data: {"error":{"code":429,"message":"rate limited"}}\n\n')
                return self._send(200, body, {"Content-Type": "text/event-stream"})
            sse_ok = (
                b'data: {"choices":[{"delta":{"content":"oi"}}],'
                b'"usage":{"cost":0.5,"prompt_tokens":10,"completion_tokens":2}}\n\n'
                b"data: [DONE]\n\n"
            )
            return self._send(200, sse_ok, {"Content-Type": "text/event-stream"})
        if Handler.mode == "sem_done":
            # gera conteúdo de verdade e o stream acaba SEM [DONE]: houve geração
            # (e cobrança lá em cima), mas a resposta não fecha. Sempre.
            body = b'data: {"choices":[{"delta":{"content":"parcial"}}]}\n\n'
            return self._send(200, body, {"Content-Type": "text/event-stream"})
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

        # ---- REGRESSÃO DE SEGURANÇA: a chave não pode viajar num redirect ----
        # O handler padrão do urllib reenvia TODOS os headers ao destino do 3xx, inclusive
        # Authorization — e o destino pode ser outro host. O `requests` remove auth
        # cross-host; reimplementar sem essa trava vazava a chave para quem controlasse o
        # redirect. PoC confirmado antes do fix: o 2º host recebeu o Bearer.
        srv2, base2 = start_server()
        try:
            Handler.trap_url = f"{base2}/armadilha"
            Handler.trap_headers = None
            r = s.get(f"{base}/redirect-para-armadilha",
                      headers={"Authorization": "Bearer sk-NAO-PODE-VAZAR"}, timeout=5)
            case("REGRESSÃO: redirect NÃO é seguido — 3xx volta como resposta terminal",
                 r.status_code == 302)
            vazou = (Handler.trap_headers or {}).get("Authorization")
            case(f"REGRESSÃO CRÍTICA: a chave NÃO chega ao destino do redirect"
                 f"{' — VAZOU: ' + str(vazou) if vazou else ''}",
                 Handler.trap_headers is None)
        finally:
            srv2.shutdown()

        case("o cliente usa opener PRÓPRIO, não o global do processo",
             Session._get_opener() is not urllib.request._opener)

        # ---- REGRESSÃO: corpo remoto tem teto ----
        case("existe teto por linha e por corpo (DoS por corpo sem newline)",
             http_client.MAX_LINE_BYTES > 0 and http_client.MAX_BODY_BYTES > 0)

        # ---- REGRESSÃO: prazo de PAREDE, não só timeout de socket ----
        r = s.get(f"{base}/lines", timeout=5)
        r._deadline = time.monotonic() - 1  # já vencido
        try:
            list(r.iter_lines())
            case("REGRESSÃO: prazo de parede vencido interrompe a leitura", False)
        except DeadlineExceeded:
            case("REGRESSÃO: prazo de parede vencido interrompe a leitura", True)

        # REGRESSÃO: o prazo é TERMINAL. Se herdasse de RequestException, o retry o
        # trataria como transiente e a espera viraria 4× o timeout, queimando 4 gerações.
        case("REGRESSÃO: prazo de parede NÃO é transporte (não entra no retry)",
             not issubclass(DeadlineExceeded, (RequestException, OSError)))

        # REGRESSÃO: .text é lido em todo 429/5xx — também respeita o prazo
        r = s.get(f"{base}/429", timeout=5)
        r._deadline = time.monotonic() - 1
        try:
            _ = r.text
            case("REGRESSÃO: .text respeita o prazo de parede", False)
        except DeadlineExceeded:
            case("REGRESSÃO: .text respeita o prazo de parede", True)

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

        # ---- REGRESSÃO: ledger ilegível FALHA FECHADO ----
        # Tratar ledger corrompido como "gasto zero" devolvia o cap inteiro — o oposto do
        # que o reserve-then-reconcile existe para garantir. Reproduzido no review:
        # $54 gastos viravam $0 e o processo reservava de novo.
        pc = tmp / "corr" / "cost-ledger.json"
        pc.parent.mkdir(parents=True)
        lc = BudgetLedger(cap_usd=10.0, ledger_path=pc)
        lc.reserve(4.0); lc.reconcile(4.0, 4.0)
        pc.write_text('{"spent_usd": 4.0, "cal')  # truncado no meio de um write
        try:
            BudgetLedger(cap_usd=10.0, ledger_path=pc)
            case("REGRESSÃO: ledger truncado RECUSA dispatch (não devolve o cap)", False)
        except or_client.LedgerCorrupted:
            case("REGRESSÃO: ledger truncado RECUSA dispatch (não devolve o cap)", True)

        pv = tmp / "vazio" / "cost-ledger.json"
        pv.parent.mkdir(parents=True); pv.write_text("")
        case("ledger AUSENTE ou vazio segue sendo run novo legítimo",
             BudgetLedger(cap_usd=10.0, ledger_path=pv).spent == 0.0)

        # ---- O que o cap por-run protege: o GASTO acumula ----
        # Este bloco testava `min(cap da instância, cap no disco)`. Esse desenho foi
        # REVERTIDO — ver a nota no __init__ do BudgetLedger. Ele envenenava o ledger de
        # forma irreversível e não protegia no caso em que a instância de cap baixo era
        # recusada. O que precisa valer, e vale, é o acúmulo do gasto entre instâncias:
        # cada uma para no teto DELA contra o total já gasto no run.
        pm = tmp / "cap" / "cost-ledger.json"
        pm.parent.mkdir(parents=True)
        a5 = BudgetLedger(cap_usd=5.0, ledger_path=pm)
        a5.reserve(4.0); a5.reconcile(4.0, 4.0)
        a5b = BudgetLedger(cap_usd=5.0, ledger_path=pm)   # mesmo teto, mesmo run
        try:
            a5b.reserve(2.0)   # 4 já gastos + 2 = 6 > 5
            case("cap por-run: o gasto de outra instância CONTA contra o meu teto", False)
        except BudgetExceeded:
            case("cap por-run: o gasto de outra instância CONTA contra o meu teto", True)

        # ---- REGRESSÃO: extra_body não pode furar a estimativa ----
        led_x = BudgetLedger(cap_usd=10.0, persist=False)
        cx = ORClient(ledger=led_x, api_key="k", outputs_dir=tmp / "x")
        cx._catalog = {"test/model": {"pricing": {"prompt": "0.000001",
                                                  "completion": "0.000002"}}}
        for campo, valor in (("max_tokens", 200000), ("model", "caro/model")):
            try:
                cx.chat("test/model", [{"role": "user", "content": "oi"}], max_tokens=16,
                        extra_body={campo: valor})
                case(f"REGRESSÃO: extra_body['{campo}'] é REJEITADO (furaria o cap)", False)
            except ValueError:
                case(f"REGRESSÃO: extra_body['{campo}'] é REJEITADO (furaria o cap)",
                     led_x.snapshot()["reserved_usd"] == 0.0)

        # ---- REGRESSÃO: falha NO MEIO do stream re-entra no retry ----
        Handler.mode = "corta_no_meio"; Handler.hits = 0
        led_m = BudgetLedger(cap_usd=10.0, ledger_path=tmp / "mid" / "cost-ledger.json")
        cm = ORClient(ledger=led_m, api_key="k", outputs_dir=tmp / "mid")
        try:
            cm.chat("test/model", [{"role": "user", "content": "oi"}], max_tokens=16)
        except Exception:
            pass
        case("REGRESSÃO: queda no meio do stream é RETENTADA, não 1 tentativa de 4",
             Handler.hits == or_client.MAX_RETRIES)
        Handler.mode = "ok"

        # ---- REGRESSÃO: o TTL da reserva cobre o pior caso de uma chamada ----
        case("REGRESSÃO: TTL > MAX_RETRIES × timeout máximo (não poda reserva em voo)",
             or_client.RESERVATION_TTL_S >= or_client.MAX_RETRIES * 1200)

        # ---- REGRESSÃO: tentativas que JÁ GERARAM são cobradas ----
        # O retry redispara até MAX_RETRIES gerações completas e o ledger contabilizava
        # UMA: subcontagem de até 4x, invisível para o cap. Reproduzido no review com um
        # stream completo faltando só o [DONE]: 4 dispatches reais, $0.20 registrado.
        Handler.mode = "corta_no_meio"; Handler.hits = 0
        led_g = BudgetLedger(cap_usd=50.0, ledger_path=tmp / "ger" / "cost-ledger.json")
        cg = ORClient(ledger=led_g, api_key="k", outputs_dir=tmp / "ger")
        antes = led_g.spent
        try:
            cg.chat("test/model", [{"role": "user", "content": "oi"}], max_tokens=16)
        except Exception:
            pass
        case("REGRESSÃO: as 4 tentativas geradas somam no gasto, não 1",
             led_g.spent > antes and Handler.hits == or_client.MAX_RETRIES)
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

        # ---- Q8: a allowlist não pode admitir add-on PAGO ----
        # `plugins` é por onde a OpenRouter liga web search e afins. A taxa do add-on não
        # entra em `_estimate`, então o chamador reserva só o custo de token e descobre o
        # resto na fatura — que é exatamente o furo que a allowlist existe pra fechar.
        c_pl = ORClient(ledger=BudgetLedger(cap_usd=5.0, persist=False),
                        api_key="k", outputs_dir=tmp / "plug")
        c_pl._catalog = {"test/model": {"pricing": {"prompt": "0.000001",
                                                    "completion": "0.000002"}}}
        try:
            c_pl.chat("test/model", [{"role": "user", "content": "oi"}],
                      extra_body={"plugins": [{"id": "web"}]})
            case("Q8: extra_body rejeita 'plugins' (add-on pago fora da estimativa)", False)
        except ValueError:
            case("Q8: extra_body rejeita 'plugins' (add-on pago fora da estimativa)", True)
        except Exception:
            case("Q8: extra_body rejeita 'plugins' (add-on pago fora da estimativa)", False)

        # ---- Q10: timeout maior que o TTL da reserva é recusado ----
        # A reserva expira pelo TTL. Se uma tentativa pode durar mais que isso, a reserva
        # some com a chamada ainda VIVA e outro processo gasta o mesmo orçamento. `timeout`
        # é parâmetro livre e cells.py encaminha o request da tarefa.
        try:
            c_pl.chat("test/model", [{"role": "user", "content": "oi"}],
                      timeout=or_client.RESERVATION_TTL_S)  # x MAX_RETRIES estoura o TTL
            case("Q10: timeout que estoura o TTL da reserva é recusado ANTES do dispatch",
                 False)
        except ValueError:
            case("Q10: timeout que estoura o TTL da reserva é recusado ANTES do dispatch",
                 True)
        except Exception:
            case("Q10: timeout que estoura o TTL da reserva é recusado ANTES do dispatch",
                 False)

        # ---- Q3: a cobrança do fracasso é UM commit, não dois ----
        # charge_failure e charge_extra eram duas escritas, cada uma pegando o lock. Entre
        # elas o disco mostrava gasto MENOR que o real, e outro processo lia esse número e
        # reservava em cima. Cada escrita era atômica; a CONTA não era.
        lp_q3 = tmp / "q3.json"
        l_q3 = BudgetLedger(cap_usd=100.0, persist=True, ledger_path=lp_q3)
        l_q3.reserve(1.0)
        antes_calls = json.loads(lp_q3.read_text())["calls"] if lp_q3.exists() else 0
        l_q3.charge_failure(1.0, extra_usd=3.0)
        d_q3 = json.loads(lp_q3.read_text())
        case("Q3: fracasso + geradas anteriores viram UMA escrita (soma correta)",
             abs(d_q3["spent_usd"] - 4.0) < 1e-9 and d_q3["calls"] == antes_calls + 1)

        # ================== NaN: O NÚMERO QUE DESLIGA O TETO ==================
        # Achado no review adversarial e reproduzido antes de virar teste. `nan > cap` é
        # False, então TODA comparação de teto vira no-op quando um não-finito entra. E o
        # `max(0.0, nan)` do clamp devolve 0.0 — um ledger com spent_usd NaN carrega como
        # gasto ZERO e o run inteiro recupera o orçamento. Pior tipo de bug deste arquivo:
        # não quebra nada, não loga nada, só desliga a trava.
        nan, inf = float("nan"), float("inf")

        # A invariante NÃO é "levanta" — é que o teto continua existindo. O tratamento
        # certo é o conservador (vale a reserva), igual ao do custo negativo. Escrevi
        # este caso esperando exceção e o código estava certo, não o teste.
        led_nan = BudgetLedger(cap_usd=1.0, persist=False)
        led_nan.reserve(0.5)
        led_nan.reconcile(0.5, nan)   # custo REAL não-finito vindo do provedor
        case("N1: custo NaN vira a estimativa (conservador), não NaN",
             math.isfinite(led_nan.spent) and abs(led_nan.spent - 0.5) < 1e-9)
        led_nan.reserve(0.4)          # 0.5 + 0.4 = 0.9 < 1.0, ainda cabe
        try:
            led_nan.reserve(0.3)      # 0.9 + 0.3 = 1.2 > 1.0
            case("N1b: o teto SEGUE valendo depois de um custo NaN", False)
        except BudgetExceeded:
            case("N1b: o teto SEGUE valendo depois de um custo NaN", True)

        # NaN no disco: `json.loads` aceita o literal NaN sem reclamar.
        for texto, desc in [('{"spent_usd": NaN, "calls": 1, "reservations": {}}', "spent NaN"),
                            ('{"spent_usd": Infinity, "calls": 1, "reservations": {}}',
                             "spent Infinity"),
                            ('{"spent_usd": 1.0, "calls": 1, "cap_usd": NaN, '
                             '"reservations": {}}', "cap NaN"),
                            ('{"spent_usd": 1.0, "calls": 1, "reservations": '
                             '{"x": {"usd": NaN, "ts": 1}}}', "reserva NaN")]:
            lpn = tmp / f"nan-{desc.replace(' ', '-')}.json"
            lpn.write_text(texto)
            try:
                l_ = BudgetLedger(cap_usd=15.0, persist=True, ledger_path=lpn)
                case(f"N2: ledger com {desc} falha FECHADA (não zera o gasto)",
                     False if desc.startswith("spent") else math.isfinite(l_.spent))
            except LedgerCorrupted:
                case(f"N2: ledger com {desc} falha FECHADA (não zera o gasto)", True)

        # N2b — o `parse_constant` e o `isfinite` parecem redundantes e não são. O
        # isfinite só olha os campos que eu validei (spent_usd, calls, reservas); o
        # parse_constant recusa o literal NaN em QUALQUER campo, inclusive um que só
        # exista no futuro. Sem ele, um NaN entra no dict e espera alguém ler.
        lp_x = tmp / "nan-campo-desconhecido.json"
        lp_x.write_text('{"spent_usd": 1.0, "calls": 1, "reservations": {}, '
                        '"campo_novo_qualquer": NaN}')
        try:
            BudgetLedger(cap_usd=15.0, persist=True, ledger_path=lp_x)
            case("N2b: NaN em campo NÃO validado ainda é recusado (parse_constant)", False)
        except LedgerCorrupted:
            case("N2b: NaN em campo NÃO validado ainda é recusado (parse_constant)", True)

        # e o pricing do catálogo, que é a outra porta de entrada de número do provedor
        c_nan = ORClient(ledger=BudgetLedger(cap_usd=5.0, persist=False),
                         api_key="k", outputs_dir=tmp / "nanprice")
        c_nan._catalog = {"nan/model": {"pricing": {"prompt": "nan", "completion": "1"}}}
        try:
            c_nan._estimate("nan/model", [{"role": "user", "content": "x"}], 10)
            case("N3: pricing não-finito no catálogo é fail-closed", False)
        except RuntimeError:
            case("N3: pricing não-finito no catálogo é fail-closed", True)

        # ============ CAMINHO DO DINHEIRO: RETRY, COBRANÇA E RESPOSTA PAGA ============

        # M1 (#3) — 429 no corpo NÃO é geração. `geradas` conta toda `_Retriable`, e o
        # rate limit entra como _Retriable — mas rate limit é o provedor RECUSANDO: nada
        # foi gerado e nada foi cobrado lá. Cada falso `geradas` cobra uma ESTIMATIVA
        # inteira a mais; com 2 recusas o ledger infla o run sem um centavo real.
        Handler.mode, Handler.hits = "erro_429_no_corpo", 0
        led_429 = BudgetLedger(cap_usd=100.0, persist=False)
        c429 = ORClient(ledger=led_429, api_key="k", outputs_dir=tmp / "r429")
        c429._catalog = {"test/model": {"pricing": {"prompt": "0.000001",
                                                    "completion": "0.000002"}}}
        out429 = c429.chat("test/model", [{"role": "user", "content": "oi"}],
                           max_tokens=10)
        case("M1: 429 no corpo do stream não conta como geração cobrada",
             abs(led_429.spent - out429["cost_usd"]) < 1e-9)

        # M2 (#4) — no caminho de FALHA, o que já foi gerado tem de ser cobrado.
        # `charge_extra` só é alcançado no caminho de SUCESSO: se o retry esgota, o
        # `geradas` morre dentro da exceção (vira texto na mensagem) e o ledger cobra só
        # uma estimativa, quando o provedor gerou e cobrou MAX_RETRIES vezes. É a
        # subcontagem que o charge_extra existe pra impedir, no ramo onde ela é maior.
        Handler.mode, Handler.hits = "sem_done", 0
        led_f = BudgetLedger(cap_usd=100.0, persist=False)
        cf = ORClient(ledger=led_f, api_key="k", outputs_dir=tmp / "falha")
        cf._catalog = {"test/model": {"pricing": {"prompt": "0.000001",
                                                  "completion": "0.000002"}}}
        est_f = cf._estimate("test/model", [{"role": "user", "content": "oi"}], 10)
        try:
            cf.chat("test/model", [{"role": "user", "content": "oi"}], max_tokens=10)
        except Exception:
            pass
        # IGUALDADE, não `>=`. O `>=` que eu tinha escrito aqui deixava passar o
        # resultado ERRADO: com charge_failure + charge_extra somando est*(geradas+1),
        # o total era 5 estimativas para 4 tentativas e o teste passava feliz. Um teste
        # de cobrança que aceita "pelo menos X" não testa cobrança — testa que houve.
        case("M2: retry esgotado cobra EXATAMENTE uma estimativa por geração",
             abs(led_f.spent - est_f * or_client.MAX_RETRIES) < 1e-9)

        # M3 (#5) — resposta JÁ PAGA não pode sumir quando o cap estoura. O
        # `reconcile` levanta BudgetExceeded depois de a chamada ter sido cobrada; se a
        # exceção sobe pelada, o texto pago vai pro lixo e o run reprocessa (e paga) de
        # novo. O dinheiro já saiu: quem chamou tem de conseguir salvar o resultado.
        Handler.mode, Handler.hits = "ok", 0
        led_c = BudgetLedger(cap_usd=0.2, persist=False)  # menor que o custo (0.5)
        cc = ORClient(ledger=led_c, api_key="k", outputs_dir=tmp / "capestoura")
        cc._catalog = {"test/model": {"pricing": {"prompt": "0.000001",
                                                  "completion": "0.000002"}}}
        try:
            cc.chat("test/model", [{"role": "user", "content": "oi"}], max_tokens=10)
            case("M3: cap estourado no reconcile levanta BudgetExceeded", False)
        except BudgetExceeded as e:
            case("M3: cap estourado no reconcile levanta BudgetExceeded", True)
            case("M3: a resposta JÁ PAGA viaja na exceção (não é jogada fora)",
                 getattr(e, "resposta", None) is not None
                 and e.resposta.get("text") == "oi mundo")

        # M4 (#9) — ler `.text` de um 429 não pode transformar retriável em terminal.
        # Com stream=True o corpo ainda está aberto; se a leitura estourar o prazo, a
        # exceção sobe de dentro do ramo do 429 e o retry NUNCA acontece. O motor
        # desiste de uma chamada que o provedor mandou repetir.
        class _RespVenenosa:
            status_code = 429
            headers = {"Retry-After": "0"}

            @property
            def text(self):
                raise DeadlineExceeded("prazo estourou lendo o corpo do 429")

            def close(self):
                pass

        class _SessaoVenenosa:
            def __init__(self):
                self.posts = 0

            def post(self, *a, **kw):
                self.posts += 1
                return _RespVenenosa()

        sv = _SessaoVenenosa()
        led_v = BudgetLedger(cap_usd=100.0, persist=False)
        cv = ORClient(ledger=led_v, api_key="k", session=sv, outputs_dir=tmp / "venen")
        cv._catalog = {"test/model": {"pricing": {"prompt": "0.000001",
                                                  "completion": "0.000002"}}}
        try:
            cv.chat("test/model", [{"role": "user", "content": "oi"}], max_tokens=10)
        except Exception:
            pass
        case("M4: 429 cujo corpo não pode ser lido ainda assim é RE-TENTADO",
             sv.posts == or_client.MAX_RETRIES)

        # ================== LOTE QUE FOI ANUNCIADO E NUNCA APLICADO ==================
        # Três correções que eu reportei como feitas e não estavam no arquivo: o script
        # que as aplicaria abortou no primeiro assert e o write nunca rodou. Estas são as
        # red tests que deveriam ter existido na primeira vez — um teste teria denunciado
        # o anúncio falso na hora.

        # ---- L1: o ledger NÃO fica cravado no menor teto que já passou por ele ----
        # Eu tinha implementado `min(cap desta instância, cap no disco)` e persistido o
        # menor. Isso criava um ledger envenenado: um typo de $0.50 num run barrava um run
        # legítimo de $50 depois, e a única saída era apagar o arquivo — que apaga o
        # histórico de gasto junto. O cap é política de quem está rodando AGORA; o gasto é
        # que é estado do run.
        lp = tmp / "cap-efetivo.json"
        baixo = BudgetLedger(cap_usd=5.0, persist=True, ledger_path=lp)
        baixo.reserve(1.0)
        baixo.reconcile(1.0, 1.0)
        alto = BudgetLedger(cap_usd=50.0, persist=True, ledger_path=lp)
        try:
            alto.reserve(10.0)   # 1 gasto + 10 = 11, abaixo do teto DESTA instância (50)
            case("L1: cap de uma instância anterior não vira teto permanente do arquivo",
                 True)
        except BudgetExceeded:
            case("L1: cap de uma instância anterior não vira teto permanente do arquivo",
                 False)
        alto.release(10.0)

        # L1c: o reconcile interrompe pelo teto DESTA instância contra o gasto
        # acumulado do run. É o ponto onde o custo REAL (que pode passar da estimativa)
        # para o run — e ele tem de olhar o total do arquivo, não só o que este processo
        # gastou, senão duas instâncias furam o teto juntas.
        lp_r = tmp / "cap-reconcile.json"
        r1 = BudgetLedger(cap_usd=5.0, persist=True, ledger_path=lp_r)
        r1.reserve(3.0); r1.reconcile(3.0, 3.0)          # run já tem 3 gastos
        r2 = BudgetLedger(cap_usd=5.0, persist=True, ledger_path=lp_r)
        r2.reserve(1.0)
        try:
            r2.reconcile(1.0, 2.5)   # real 2.5; total 3 + 2.5 = 5.5 > 5
            case("L1c: reconcile para pelo gasto ACUMULADO do run, não só pelo local",
                 False)
        except BudgetExceeded:
            case("L1c: reconcile para pelo gasto ACUMULADO do run, não só pelo local",
                 True)

        # ---- L2: ledger que PARSEIA mas tem lixo tipado é corrupção, não run novo ----
        # O fail-closed só cobria JSON ilegível. `{"spent_usd": "muito"}` e
        # `{"spent_usd": null}` parseiam, caem no `except (TypeError, ValueError)` /
        # no `or 0.0`, viram 0.0 em silêncio — e devolvem o cap INTEIRO. É o mesmo
        # fail-open que o LedgerCorrupted existe para fechar, entrando pela outra porta.
        for lixo, desc in [('{"spent_usd": "muito", "calls": 1}', "string"),
                           ('{"spent_usd": null, "calls": 1}', "null"),
                           ('{"spent_usd": [1,2], "calls": 1}', "lista"),
                           ('{"spent_usd": true, "calls": 1}', "bool"),
                           ('{"spent_usd": 1.0, "calls": "dois"}', "calls string")]:
            lp2 = tmp / f"lixo-{desc.replace(' ', '-')}.json"
            lp2.write_text(lixo)
            try:
                BudgetLedger(cap_usd=5.0, persist=True, ledger_path=lp2)
                case(f"L2: ledger com {desc} no lugar do número falha FECHADA", False)
            except LedgerCorrupted:
                case(f"L2: ledger com {desc} no lugar do número falha FECHADA", True)
        # L2c: reserva MALFORMADA é corrupção; reserva VENCIDA é órfã. A diferença
        # importa porque descartar uma reserva devolve o orçamento dela ao cap — some
        # dinheiro em voo da conta. Também achado por mutação: neutralizar a checagem
        # não derrubava nada, porque todo teste de reserva usava entrada bem-formada.
        for lixo, desc in [('{"spent_usd": 1.0, "reservations": {"x": "nao-e-dict"}}',
                            "reserva que não é objeto"),
                           ('{"spent_usd": 1.0, "reservations": {"x": {"usd": 2.0}}}',
                            "reserva sem ts"),
                           ('{"spent_usd": 1.0, "reservations": {"x": {"usd": "abc", "ts": 1}}}',
                            "reserva com usd ilegível"),
                           ('{"spent_usd": 1.0, "reservations": "nao-e-objeto"}',
                            "reservations que não é objeto")]:
            lpr = tmp / f"res-{desc.replace(' ', '-')}.json"
            lpr.write_text(lixo)
            try:
                BudgetLedger(cap_usd=5.0, persist=True, ledger_path=lpr)
                case(f"L2c: {desc} falha FECHADA (não devolve orçamento ao cap)", False)
            except LedgerCorrupted:
                case(f"L2c: {desc} falha FECHADA (não devolve orçamento ao cap)", True)

        # L2d — `reservations: null` era convertido para {} DE PROPÓSITO por mim, e isso
        # é fail-open: reserva em voo de outro processo é justamente o que impede dois
        # runs de gastarem o mesmo dinheiro. Apagá-las devolve tudo ao cap.
        for txt, d in [('{"spent_usd":1.0,"calls":1,"reservations":null}', "reservations null"),
                       ('{"spent_usd":1.0,"calls":2.7,"reservations":{}}', "calls fracionario"),
                       ('{"spent_usd":1.0,"calls":1,"reservations":{"x":{"usd":"2.0","ts":1}}}',
                        "usd como string")]:
            f_ = tmp / f"l2d-{d.replace(' ', '-')}.json"
            f_.write_text(txt)
            try:
                BudgetLedger(cap_usd=15.0, persist=True, ledger_path=f_)
                case(f"L2d: {d} falha FECHADA", False)
            except LedgerCorrupted:
                case(f"L2d: {d} falha FECHADA", True)

        # e o caso legítimo continua legítimo: ausente/vazio = run novo
        lp3 = tmp / "novo.json"
        try:
            led_novo = BudgetLedger(cap_usd=5.0, persist=True, ledger_path=lp3)
            case("L2: ledger ausente segue sendo run novo (não é corrupção)",
                 led_novo.spent == 0.0)
        except LedgerCorrupted:
            case("L2: ledger ausente segue sendo run novo (não é corrupção)", False)

        # ---- L3: extra_body por ALLOWLIST, não denylist de 5 chaves ----
        # A denylist barrava model/messages/max_tokens/stream/usage e deixava passar
        # `models` (lista de fallback — TROCA qual modelo cobra), `provider` (rota e
        # preço), `route`, e `n` (multiplica a geração e a fatura). Todos entram no
        # payload DEPOIS da estimativa que reservou o orçamento, então o cap é furado por
        # fator arbitrário sem erro nenhum. cells.py encaminha `request` vindo da tarefa:
        # é alcançável por dado comum, não só por malícia.
        c_ab = ORClient(ledger=BudgetLedger(cap_usd=5.0, persist=False),
                        api_key="k", outputs_dir=tmp / "ab")
        for chave, valor in [("models", ["openai/gpt-5.6"]), ("provider", {"order": ["x"]}),
                             ("route", "fallback"), ("n", 4),
                             ("max_completion_tokens", 99999)]:
            try:
                c_ab.chat("z/m", [{"role": "user", "content": "oi"}],
                          extra_body={chave: valor})
                case(f"L3: extra_body rejeita {chave!r} (troca modelo/rota/volume)", False)
            except ValueError:
                case(f"L3: extra_body rejeita {chave!r} (troca modelo/rota/volume)", True)
            except Exception:
                # qualquer outra exceção significa que passou da validação
                case(f"L3: extra_body rejeita {chave!r} (troca modelo/rota/volume)", False)

        print(f"{sum(results)}/{len(results)} testes ok")
        return 0 if all(results) else 1
    finally:
        srv.shutdown()
        __import__("shutil").rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
