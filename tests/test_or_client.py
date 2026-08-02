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

        # ---- REGRESSÃO: o cap efetivo é o MENOR, não o maior ----
        # cap_usd era escrito no ledger e nunca lido de volta. Reproduzido no review:
        # instância com cap $5 bloqueava em $4; outra com cap $100 gastava $50 no mesmo run.
        pm = tmp / "cap" / "cost-ledger.json"
        pm.parent.mkdir(parents=True)
        a5 = BudgetLedger(cap_usd=5.0, ledger_path=pm)
        a5.reserve(4.0); a5.reconcile(4.0, 4.0)
        b100 = BudgetLedger(cap_usd=100.0, ledger_path=pm)
        try:
            b100.reserve(50.0)
            case("REGRESSÃO: cap maior NÃO sobrepõe o cap já gravado no run", False)
        except BudgetExceeded:
            case("REGRESSÃO: cap maior NÃO sobrepõe o cap já gravado no run", True)

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

        # ================== LOTE QUE FOI ANUNCIADO E NUNCA APLICADO ==================
        # Três correções que eu reportei como feitas e não estavam no arquivo: o script
        # que as aplicaria abortou no primeiro assert e o write nunca rodou. Estas são as
        # red tests que deveriam ter existido na primeira vez — um teste teria denunciado
        # o anúncio falso na hora.

        # ---- L1: o cap EFETIVO tem de ser o que fica no disco ----
        # _effective_cap já existia e era calculado num lugar só (o ramo lento do
        # reserve), e _write_disk gravava self.cap_usd por cima. Efeito: o piso do run
        # sobe. Processo com cap $5 fixa o teto do run em $5; um processo com cap $50
        # entra, respeita o $5 para si (min), mas GRAVA $50 — e o próximo processo lê $50
        # como se fosse o teto do run. O cap volta a ser por-processo, que é exatamente o
        # que o T4 existe para impedir.
        lp = tmp / "cap-efetivo.json"
        baixo = BudgetLedger(cap_usd=5.0, persist=True, ledger_path=lp)
        baixo.reserve(1.0)
        baixo.reconcile(1.0, 1.0)
        alto = BudgetLedger(cap_usd=50.0, persist=True, ledger_path=lp)
        alto.reserve(1.0)
        alto.reconcile(1.0, 1.0)
        no_disco = json.loads(lp.read_text())["cap_usd"]
        case("L1: cap gravado no disco é o EFETIVO (o menor), não o da instância",
             abs(no_disco - 5.0) < 1e-9)
        terceiro = BudgetLedger(cap_usd=100.0, persist=True, ledger_path=lp)
        try:
            terceiro.reserve(10.0)   # já gastou 2; 2+10=12 > piso do run (5)
            case("L1: terceiro processo herda o piso do run, não o teto inflado", False)
        except BudgetExceeded:
            case("L1: terceiro processo herda o piso do run, não o teto inflado", True)

        # L1c: o cap efetivo tem de mandar no RECONCILE também, não só no reserve.
        # Achado por mutação: trocar `self._cap_efetivo` por `self.cap_usd` no reconcile
        # não derrubava teste nenhum. É o ponto onde o custo REAL (que pode passar da
        # estimativa) interrompe o run — usar o cap da instância ali deixa um processo
        # de cap alto seguir gastando acima do piso que o run já fixou.
        lp_r = tmp / "cap-reconcile.json"
        BudgetLedger(cap_usd=5.0, persist=True, ledger_path=lp_r)._commit(0.0, 0)
        folgado = BudgetLedger(cap_usd=50.0, persist=True, ledger_path=lp_r)
        folgado.reserve(1.0)
        try:
            folgado.reconcile(1.0, 6.0)  # real 6 > piso do run (5), < cap da instância (50)
            case("L1c: reconcile interrompe pelo cap EFETIVO, não pelo da instância", False)
        except BudgetExceeded:
            case("L1c: reconcile interrompe pelo cap EFETIVO, não pelo da instância", True)

        # ---- L2: ledger que PARSEIA mas tem lixo tipado é corrupção, não run novo ----
        # O fail-closed só cobria JSON ilegível. `{"spent_usd": "muito"}` e
        # `{"spent_usd": null}` parseiam, caem no `except (TypeError, ValueError)` /
        # no `or 0.0`, viram 0.0 em silêncio — e devolvem o cap INTEIRO. É o mesmo
        # fail-open que o LedgerCorrupted existe para fechar, entrando pela outra porta.
        from high_stakes.or_client import LedgerCorrupted
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
