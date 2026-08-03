#!/usr/bin/env python3
"""test_or_client.py — executable suite for the MONEY path (this project's convention).

Covers three gaps that used to be SILENT failures (the engine kept running and called
the cap good, spending 2x):

  T11 — HTTP client on top of the stdlib. Against a real http.server, not a mock:
        if `urllib` diverges from the contract the retry expects (non-2xx must come
        back as a RESPONSE, with a readable Retry-After), the 429 becomes a terminal
        error and the run dies.
  T4  — CROSS-PROCESS cap. Two processes in the same run read `spent=0` and the last
        write won: cap breached 2x, with no signal at all.
  T5  — billing on failure. A dropped stream may have been billed upstream; if the
        failure does not debit, the cap overestimates the remaining budget.
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

ROOT = Path(__file__).resolve().parents[1]  # repo/plugin root


# ---------------------------------------------------------------- test server
class Handler(BaseHTTPRequestHandler):
    """mode is CLASS-level: each test sets it before calling."""
    mode = "ok"
    hits = 0
    trap_url = ""
    trap_headers = None

    def log_message(self, *a):  # silences http.server's log
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
        if self.path == "/redirect-to-trap":
            return self._send(302, b"", {"Location": Handler.trap_url})
        if self.path == "/trap":
            Handler.trap_headers = dict(self.headers)
            return self._send(200, b"gotcha")
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
        if Handler.mode == "cut_midstream":
            # headers + PARTIAL body, then drops: the dominant failure in a long
            # streaming call. A Content-Length larger than what is sent forces a read
            # error.
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
        if Handler.mode == "error_429_in_body":
            # 200 in the header, a 429 error IN THE BODY of the stream. Rate limit =
            # the provider REFUSED; nothing was generated and nothing was billed
            # there. The first two attempts refuse, the third answers for real.
            if Handler.hits <= 2:
                body = (b'data: {"error":{"code":429,"message":"rate limited"}}\n\n')
                return self._send(200, body, {"Content-Type": "text/event-stream"})
            sse_ok = (
                b'data: {"choices":[{"delta":{"content":"hi"}}],'
                b'"usage":{"cost":0.5,"prompt_tokens":10,"completion_tokens":2}}\n\n'
                b"data: [DONE]\n\n"
            )
            return self._send(200, sse_ok, {"Content-Type": "text/event-stream"})
        if Handler.mode == "only_429_always":
            # a clean 429 in the HEADER, on every attempt: the provider SAYS it
            # refused. Nothing generated, nothing billed up there.
            return self._send(429, b"slow down", {"Retry-After": "0"})
        if Handler.mode == "content_then_429":
            # REAL content and ONLY THEN the 429 in the body: it was generated (and
            # billed) before the refusal. The error code alone would say "do not
            # charge" — and it would be wrong.
            body = (b'data: {"choices":[{"delta":{"content":"a real answer"}}]}\n\n'
                    b'data: {"error":{"code":429,"message":"rate limited"}}\n\n')
            return self._send(200, body, {"Content-Type": "text/event-stream"})
        if Handler.mode == "cost_nan":
            # the provider reports a NaN cost in usage: the other door (besides
            # pricing) through which a non-finite number gets in and turns off the
            # ceiling.
            body = (b'data: {"choices":[{"delta":{"content":"hi"}}],'
                    b'"usage":{"cost":NaN,"prompt_tokens":10,"completion_tokens":2}}\n\n'
                    b"data: [DONE]\n\n")
            return self._send(200, body, {"Content-Type": "text/event-stream"})
        if Handler.mode == "no_done":
            # generates real content and the stream ends WITHOUT [DONE]: there was
            # generation (and billing up there), but the response never closes. Always.
            body = b'data: {"choices":[{"delta":{"content":"partial"}}]}\n\n'
            return self._send(200, body, {"Content-Type": "text/event-stream"})
        sse = (
            b'data: {"choices":[{"delta":{"content":"hi"}}]}\n\n'
            b'data: {"choices":[{"delta":{"content":" world"}}],'
            b'"usage":{"cost":0.5,"prompt_tokens":10,"completion_tokens":2}}\n\n'
            b"data: [DONE]\n\n"
        )
        return self._send(200, sse, {"Content-Type": "text/event-stream"})


def start_server() -> tuple[HTTPServer, str]:
    srv = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_port}"


# ---------------------------------------------------------------- T4: subprocesses
# Runs in a separate process: reserves, holds the reservation, and only then
# reconciles — the window in which the OTHER process must see the reservation so it
# does not breach the cap.
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

        # ---- T11: HTTP client against a real server ----
        r = s.get(f"{base}/api/v1/models", timeout=5)
        case("GET 200 + .json() decodes",
             r.status_code == 200 and r.json()["data"][0]["id"] == "test/model")

        r = s.post(f"{base}/echo", json={"a": 1, "b": "ü"}, timeout=5)
        case("POST sends JSON (round-trip preserves unicode)", r.json() == {"a": 1, "b": "ü"})

        r = s.post(f"{base}/echo", headers={"X-Title": "hs"}, json={}, timeout=5)
        case("POST sets Content-Type on its own", r.status_code == 200)

        r = s.get(f"{base}/429", timeout=5)
        case("REGRESSION T11: 429 comes back as a RESPONSE, not an exception (else the retry dies)",
             r.status_code == 429)
        case("REGRESSION T11: Retry-After readable on the error response",
             r.headers.get("Retry-After") == "7")
        case("429 error body readable via .text", "slow down" in r.text)

        r = s.get(f"{base}/400", timeout=5)
        case("terminal 4xx also comes back as a response with a body",
             r.status_code == 400 and "bad request" in r.text)

        r = s.get(f"{base}/lines", timeout=5)
        case("iter_lines yields lines without the terminator (\\n and \\r\\n)",
             list(r.iter_lines()) == [b"alpha", b"beta", b"gamma"])

        try:
            s.get("http://127.0.0.1:1/nothing", timeout=2)
            case("transport error becomes RequestException", False)
        except RequestException:
            case("transport error becomes RequestException", True)
        except Exception as e:
            case(f"transport error becomes RequestException (got {type(e).__name__})", False)

        r = s.get(f"{base}/echo-headers", timeout=5)
        case("Accept-Encoding: identity is explicit (urllib does not decompress)",
             r.json().get("Accept-Encoding") == "identity")

        # ---- SECURITY REGRESSION: the key must not travel on a redirect ----
        # urllib's default handler re-sends ALL headers to the 3xx destination,
        # including Authorization — and the destination can be another host. `requests`
        # strips auth cross-host; reimplementing without that guard leaked the key to
        # whoever controlled the redirect. PoC confirmed before the fix: the 2nd host
        # received the Bearer.
        srv2, base2 = start_server()
        try:
            Handler.trap_url = f"{base2}/trap"
            Handler.trap_headers = None
            r = s.get(f"{base}/redirect-to-trap",
                      headers={"Authorization": "Bearer sk-MUST-NOT-LEAK"}, timeout=5)
            case("REGRESSION: redirect is NOT followed — 3xx comes back as a terminal response",
                 r.status_code == 302)
            leaked = (Handler.trap_headers or {}).get("Authorization")
            case(f"CRITICAL REGRESSION: the key does NOT reach the redirect target"
                 f"{' — LEAKED: ' + str(leaked) if leaked else ''}",
                 Handler.trap_headers is None)
        finally:
            srv2.shutdown()

        case("the client uses its OWN opener, not the process-global one",
             Session._get_opener() is not urllib.request._opener)

        # ---- REGRESSION: the remote body has a ceiling ----
        case("per-line and per-body ceilings exist (DoS via body with no newline)",
             http_client.MAX_LINE_BYTES > 0 and http_client.MAX_BODY_BYTES > 0)

        # ---- REGRESSION: WALL-CLOCK deadline, not just socket timeout ----
        r = s.get(f"{base}/lines", timeout=5)
        r._deadline = time.monotonic() - 1  # already expired
        try:
            list(r.iter_lines())
            case("REGRESSION: an expired wall-clock deadline interrupts the read", False)
        except DeadlineExceeded:
            case("REGRESSION: an expired wall-clock deadline interrupts the read", True)

        # REGRESSION: the deadline is TERMINAL. If it inherited from RequestException,
        # the retry would treat it as transient and the wait would become 4× the
        # timeout, burning 4 generations.
        case("REGRESSION: the wall-clock deadline is NOT transport (does not enter the retry)",
             not issubclass(DeadlineExceeded, (RequestException, OSError)))

        # REGRESSION: .text is read on every 429/5xx — it honors the deadline too
        r = s.get(f"{base}/429", timeout=5)
        r._deadline = time.monotonic() - 1
        try:
            _ = r.text
            case("REGRESSION: .text honors the wall-clock deadline", False)
        except DeadlineExceeded:
            case("REGRESSION: .text honors the wall-clock deadline", True)

        # ---- integration: full chat() against the server ----
        or_client.OPENROUTER_BASE = f"{base}/api/v1"
        or_client.ORClient._sleep_backoff = staticmethod(lambda *a, **k: None)  # no waiting

        led = BudgetLedger(cap_usd=10.0, ledger_path=tmp / "run1" / "cost-ledger.json")
        c = ORClient(ledger=led, api_key="k", outputs_dir=tmp / "run1")
        out = c.chat("test/model", [{"role": "user", "content": "hi"}], max_tokens=16)
        case("chat() accumulates SSE and returns text", out["text"] == "hi world")
        case("chat() uses the provider's usage.cost", out["cost_usd"] == 0.5)
        case("ledger books the real cost", abs(led.spent - 0.5) < 1e-9)
        case("reservation released after reconcile", led.snapshot()["reserved_usd"] == 0.0)

        disk = json.loads((tmp / "run1" / "cost-ledger.json").read_text())
        case("ledger on DISK reflects the spend", abs(disk["spent_usd"] - 0.5) < 1e-9)
        case("no reservation left orphaned on disk", not disk.get("reservations"))

        # ---- T5: post-dispatch failure is CHARGED ----
        Handler.mode = "always_500"
        led2 = BudgetLedger(cap_usd=10.0, ledger_path=tmp / "run2" / "cost-ledger.json")
        c2 = ORClient(ledger=led2, api_key="k", outputs_dir=tmp / "run2")
        Handler.hits = 0
        try:
            c2.chat("test/model", [{"role": "user", "content": "hi"}], max_tokens=16)
            case("REGRESSION T5: failure propagates", False)
        except RuntimeError:
            case("REGRESSION T5: failure propagates", True)
        case("REGRESSION T5: 500 is retriable (tried MAX_RETRIES times)",
             Handler.hits == or_client.MAX_RETRIES)
        case("REGRESSION T5: the estimate is CHARGED on failure (the stream may have been billed)",
             led2.spent > 0)
        d2 = json.loads((tmp / "run2" / "cost-ledger.json").read_text())
        case("REGRESSION T5: the failure charge PERSISTS on disk", d2["spent_usd"] > 0)
        case("REGRESSION T5: the failure's reservation is not left orphaned",
             not d2.get("reservations"))
        led2b = BudgetLedger(cap_usd=10.0, ledger_path=tmp / "run2" / "cost-ledger.json")
        case("REGRESSION T5: a new instance inherits the spend (cap does not reset)",
             abs(led2b.spent - led2.spent) < 1e-9)
        Handler.mode = "ok"

        # ---- REGRESSION: an unreadable ledger FAILS CLOSED ----
        # Treating a corrupted ledger as "zero spend" gave the whole cap back — the
        # opposite of what reserve-then-reconcile exists to guarantee. Reproduced in
        # review: $54 spent became $0 and the process reserved again.
        pc = tmp / "corr" / "cost-ledger.json"
        pc.parent.mkdir(parents=True)
        lc = BudgetLedger(cap_usd=10.0, ledger_path=pc)
        lc.reserve(4.0); lc.reconcile(4.0, 4.0)
        pc.write_text('{"spent_usd": 4.0, "cal')  # truncated mid-write
        try:
            BudgetLedger(cap_usd=10.0, ledger_path=pc)
            case("REGRESSION: a truncated ledger REFUSES dispatch (does not return the cap)", False)
        except or_client.LedgerCorrupted:
            case("REGRESSION: a truncated ledger REFUSES dispatch (does not return the cap)", True)

        pv = tmp / "empty" / "cost-ledger.json"
        pv.parent.mkdir(parents=True); pv.write_text("")
        case("an ABSENT or empty ledger is still a legitimate new run",
             BudgetLedger(cap_usd=10.0, ledger_path=pv).spent == 0.0)

        # ---- What the per-run cap protects: the SPEND accumulates ----
        # This block used to test `min(instance cap, cap on disk)`. That design was
        # REVERTED — see the note in BudgetLedger's __init__. It poisoned the ledger
        # irreversibly and did not protect in the case where the low-cap instance was
        # refused. What must hold, and does, is spend accumulation across instances:
        # each one stops at ITS OWN ceiling against the run's total already spent.
        pm = tmp / "cap" / "cost-ledger.json"
        pm.parent.mkdir(parents=True)
        a5 = BudgetLedger(cap_usd=5.0, ledger_path=pm)
        a5.reserve(4.0); a5.reconcile(4.0, 4.0)
        a5b = BudgetLedger(cap_usd=5.0, ledger_path=pm)   # same ceiling, same run
        try:
            a5b.reserve(2.0)   # 4 already spent + 2 = 6 > 5
            case("per-run cap: another instance's spend COUNTS against my ceiling", False)
        except BudgetExceeded:
            case("per-run cap: another instance's spend COUNTS against my ceiling", True)

        # ---- REGRESSION: extra_body must not bypass the estimate ----
        led_x = BudgetLedger(cap_usd=10.0, persist=False)
        cx = ORClient(ledger=led_x, api_key="k", outputs_dir=tmp / "x")
        cx._catalog = {"test/model": {"pricing": {"prompt": "0.000001",
                                                  "completion": "0.000002"}}}
        for field, value in (("max_tokens", 200000), ("model", "expensive/model")):
            try:
                cx.chat("test/model", [{"role": "user", "content": "hi"}], max_tokens=16,
                        extra_body={field: value})
                case(f"REGRESSION: extra_body['{field}'] is REJECTED (would breach the cap)", False)
            except ValueError:
                case(f"REGRESSION: extra_body['{field}'] is REJECTED (would breach the cap)",
                     led_x.snapshot()["reserved_usd"] == 0.0)

        # ---- REGRESSION: a failure MID-stream re-enters the retry ----
        Handler.mode = "cut_midstream"; Handler.hits = 0
        led_m = BudgetLedger(cap_usd=10.0, ledger_path=tmp / "mid" / "cost-ledger.json")
        cm = ORClient(ledger=led_m, api_key="k", outputs_dir=tmp / "mid")
        try:
            cm.chat("test/model", [{"role": "user", "content": "hi"}], max_tokens=16)
        except Exception:
            pass
        case("REGRESSION: a drop mid-stream is RETRIED, not 1 attempt out of 4",
             Handler.hits == or_client.MAX_RETRIES)
        Handler.mode = "ok"

        # ---- REGRESSION: the reservation TTL covers a call's worst case ----
        case("REGRESSION: TTL > MAX_RETRIES × max timeout (does not prune an in-flight reservation)",
             or_client.RESERVATION_TTL_S >= or_client.MAX_RETRIES * 1200)

        # ---- REGRESSION: attempts that ALREADY GENERATED are charged ----
        # The retry re-dispatches up to MAX_RETRIES full generations and the ledger
        # booked ONE: an undercount of up to 4x, invisible to the cap. Reproduced in
        # review with a complete stream missing only the [DONE]: 4 real dispatches,
        # $0.20 recorded.
        Handler.mode = "cut_midstream"; Handler.hits = 0
        led_g = BudgetLedger(cap_usd=50.0, ledger_path=tmp / "gen" / "cost-ledger.json")
        cg = ORClient(ledger=led_g, api_key="k", outputs_dir=tmp / "gen")
        before = led_g.spent
        try:
            cg.chat("test/model", [{"role": "user", "content": "hi"}], max_tokens=16)
        except Exception:
            pass
        case("REGRESSION: all 4 generated attempts add to the spend, not 1",
             led_g.spent > before and Handler.hits == or_client.MAX_RETRIES)
        Handler.mode = "ok"

        # ---- T4: cross-process cap ----
        p4 = tmp / "run4" / "cost-ledger.json"
        outs = run_children(p4, cap=1.0, amount=0.6, hold=1.0)
        case(f"REGRESSION T4: 2 processes, $1 cap, $0.60 each -> only 1 spends (got {outs})",
             sorted(outs) == ["BLOCKED", "SPENT"])
        d4 = json.loads(p4.read_text())
        case("REGRESSION T4: disk does not exceed the cap", d4["spent_usd"] <= 1.0)

        p5 = tmp / "run5" / "cost-ledger.json"
        outs = run_children(p5, cap=10.0, amount=0.3, hold=0.3)
        d5 = json.loads(p5.read_text())
        case("REGRESSION T4: 2 processes' spends ADD UP (not last-write-wins)",
             outs == ["SPENT", "SPENT"] and abs(d5["spent_usd"] - 0.6) < 1e-6
             and d5["calls"] == 2)

        # ---- reservations: visibility and hygiene ----
        pr = tmp / "run6" / "cost-ledger.json"
        a = BudgetLedger(cap_usd=1.0, ledger_path=pr)
        a.reserve(0.8)
        b = BudgetLedger(cap_usd=1.0, ledger_path=pr)
        try:
            b.reserve(0.5)
            case("an in-flight reservation from ANOTHER process blocks dispatch", False)
        except BudgetExceeded:
            case("an in-flight reservation from ANOTHER process blocks dispatch", True)
        a.release(0.8)
        try:
            b.reserve(0.5)
            case("release gives the budget back to the other processes", True)
        except BudgetExceeded:
            case("release gives the budget back to the other processes", False)

        # an orphan from a dead process must not lock the run forever
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
            case("an orphaned reservation (dead process) expires via the TTL", True)
        except BudgetExceeded:
            case("an orphaned reservation (dead process) expires via the TTL", False)

        # ---- fail-closed that already existed: do not regress ----
        c._catalog = {"neg/model": {"pricing": {"prompt": "-1", "completion": "-1"}}}
        try:
            c._estimate("neg/model", [{"role": "user", "content": "x"}], 10)
            case("sentinel -1/-1 pricing remains fail-closed", False)
        except RuntimeError:
            case("sentinel -1/-1 pricing remains fail-closed", True)

        led9 = BudgetLedger(cap_usd=10.0, persist=False)
        led9.reserve(1.0)
        led9.reconcile(1.0, -5.0)
        case("a negative REAL cost does not deflate the spend", abs(led9.spent - 1.0) < 1e-9)

        # ==== review #4: the billing counter was wrong in BOTH directions ====
        # The old rule looked at the error CODE. The code does not know what happened.

        # G1 — a clean 429 on ALL attempts: the provider refused everything, nothing
        # was generated, nothing was billed. The failure path used to charge one
        # estimate "just in case" — inflating the ledger with no real cent behind it,
        # which makes the engine stop early and refuse legitimate calls later.
        Handler.mode, Handler.hits = "only_429_always", 0
        led_g1 = BudgetLedger(cap_usd=50.0, persist=False)
        c_g1 = ORClient(ledger=led_g1, api_key="k", outputs_dir=tmp / "g1")
        c_g1._catalog = {"test/model": {"pricing": {"prompt": "0.001",
                                                    "completion": "0.002"}}}
        try:
            c_g1.chat("test/model", [{"role": "user", "content": "hi"}], max_tokens=100)
        except Exception:
            pass
        case("G1: a clean 429 on every attempt charges NOTHING",
             abs(led_g1.spent) < 1e-9 and Handler.hits == or_client.MAX_RETRIES)

        # G2 — content and ONLY THEN the 429 in the body: it generated before refusing,
        # hence it billed. The rule by error code would mark it non-chargeable and
        # undercount.
        Handler.mode, Handler.hits = "content_then_429", 0
        led_g2 = BudgetLedger(cap_usd=50.0, persist=False)
        c_g2 = ORClient(ledger=led_g2, api_key="k", outputs_dir=tmp / "g2")
        c_g2._catalog = {"test/model": {"pricing": {"prompt": "0.001",
                                                    "completion": "0.002"}}}
        est_g2 = c_g2._estimate("test/model", [{"role": "user", "content": "hi"}], 100)
        try:
            c_g2.chat("test/model", [{"role": "user", "content": "hi"}], max_tokens=100)
        except Exception:
            pass
        case("G2: content BEFORE the 429 in the body IS charged (it generated, hence billed)",
             abs(led_g2.spent - est_g2 * or_client.MAX_RETRIES) < 1e-9)

        # G3 — a stream cut in the middle of the JSON: no text gets parsed, but the
        # BYTES were on the wire. Measuring by the parse undercounted exactly the most
        # common streaming failure in a long call.
        Handler.mode, Handler.hits = "cut_midstream", 0
        led_g3 = BudgetLedger(cap_usd=50.0, persist=False)
        c_g3 = ORClient(ledger=led_g3, api_key="k", outputs_dir=tmp / "g3")
        c_g3._catalog = {"test/model": {"pricing": {"prompt": "0.001",
                                                    "completion": "0.002"}}}
        est_g3 = c_g3._estimate("test/model", [{"role": "user", "content": "hi"}], 100)
        try:
            c_g3.chat("test/model", [{"role": "user", "content": "hi"}], max_tokens=100)
        except Exception:
            pass
        case("G3: a stream truncated mid-JSON counts as chargeable (bytes on the wire)",
             led_g3.spent >= est_g3 - 1e-9)
        Handler.mode = "ok"

        # ---- MUTATION AUDIT: two money guards with no test ----
        # A1 — a non-finite `usage.cost` coming from the provider. There was a test for
        # non-finite catalog PRICING (N3), none for the REAL cost of the response,
        # which is the other way the poisoned number gets in: from there it goes
        # straight to the ledger.
        Handler.mode, Handler.hits = "cost_nan", 0
        led_cn = BudgetLedger(cap_usd=5.0, persist=False)
        c_cn = ORClient(ledger=led_cn, api_key="k", outputs_dir=tmp / "costnan")
        c_cn._catalog = {"test/model": {"pricing": {"prompt": "0.000001",
                                                    "completion": "0.000002"}}}
        out_cn = c_cn.chat("test/model", [{"role": "user", "content": "hi"}], max_tokens=10)
        case("A1: a non-finite usage.cost becomes the estimate, does not poison the ledger",
             math.isfinite(led_cn.spent) and math.isfinite(out_cn["cost_usd"]))

        # A2 — a ledger whose top level is not a JSON object (a list, for example).
        # Before, this raised a raw AttributeError in the middle of `_read_disk`, which
        # is not an error anyone knows how to interpret; and the fail-closed only
        # covered the fields, not the shape.
        lp_list = tmp / "top-list.json"
        lp_list.write_text('[{"spent_usd": 1.0}]')
        try:
            BudgetLedger(cap_usd=5.0, persist=True, ledger_path=lp_list)
            case("A2: a ledger whose top level is not an object fails CLOSED (not AttributeError)",
                 False)
        except LedgerCorrupted:
            case("A2: a ledger whose top level is not an object fails CLOSED (not AttributeError)",
                 True)

        # ---- Q8: the allowlist must not admit PAID add-ons ----
        # `plugins` is how OpenRouter enables web search and the like. The add-on fee
        # does not enter `_estimate`, so the caller reserves only the token cost and
        # finds out the rest on the bill — which is exactly the hole the allowlist
        # exists to close.
        c_pl = ORClient(ledger=BudgetLedger(cap_usd=5.0, persist=False),
                        api_key="k", outputs_dir=tmp / "plug")
        c_pl._catalog = {"test/model": {"pricing": {"prompt": "0.000001",
                                                    "completion": "0.000002"}}}
        try:
            c_pl.chat("test/model", [{"role": "user", "content": "hi"}],
                      extra_body={"plugins": [{"id": "web"}]})
            case("Q8: extra_body rejects 'plugins' (paid add-on outside the estimate)", False)
        except ValueError:
            case("Q8: extra_body rejects 'plugins' (paid add-on outside the estimate)", True)
        except Exception:
            case("Q8: extra_body rejects 'plugins' (paid add-on outside the estimate)", False)

        # ---- Q10: a timeout larger than the reservation TTL is refused ----
        # The reservation expires via the TTL. If one attempt can last longer than
        # that, the reservation vanishes with the call still ALIVE and another process
        # spends the same budget. `timeout` is a free parameter and cells.py forwards
        # the task's request.
        try:
            c_pl.chat("test/model", [{"role": "user", "content": "hi"}],
                      timeout=or_client.RESERVATION_TTL_S)  # x MAX_RETRIES blows the TTL
            case("Q10: a timeout that blows the reservation TTL is refused BEFORE dispatch",
                 False)
        except ValueError:
            case("Q10: a timeout that blows the reservation TTL is refused BEFORE dispatch",
                 True)
        except Exception:
            case("Q10: a timeout that blows the reservation TTL is refused BEFORE dispatch",
                 False)

        # ---- Q3: the failure charge is ONE commit, not two ----
        # charge_failure and charge_extra were two writes, each taking the lock.
        # Between them the disk showed LOWER spend than the real one, and another
        # process read that number and reserved on top of it. Each write was atomic;
        # the MATH was not.
        lp_q3 = tmp / "q3.json"
        l_q3 = BudgetLedger(cap_usd=100.0, persist=True, ledger_path=lp_q3)
        l_q3.reserve(1.0)
        calls_before = json.loads(lp_q3.read_text())["calls"] if lp_q3.exists() else 0
        l_q3.charge_failure(1.0, extra_usd=3.0)
        d_q3 = json.loads(lp_q3.read_text())
        case("Q3: failure + earlier generations become ONE write (correct sum)",
             abs(d_q3["spent_usd"] - 4.0) < 1e-9 and d_q3["calls"] == calls_before + 1)

        # ================== NaN: THE NUMBER THAT TURNS OFF THE CEILING ==================
        # Found in the adversarial review and reproduced before becoming a test.
        # `nan > cap` is False, so EVERY ceiling comparison becomes a no-op once a
        # non-finite gets in. And the clamp's `max(0.0, nan)` returns 0.0 — a ledger
        # with a NaN spent_usd loads as ZERO spend and the whole run recovers its
        # budget. The worst kind of bug in this file: it breaks nothing, logs nothing,
        # it just turns off the guard.
        nan, inf = float("nan"), float("inf")

        # The invariant is NOT "it raises" — it is that the ceiling keeps existing. The
        # right treatment is the conservative one (the reservation stands), same as for
        # the negative cost. I wrote this case expecting an exception and the code was
        # right, not the test.
        led_nan = BudgetLedger(cap_usd=1.0, persist=False)
        led_nan.reserve(0.5)
        led_nan.reconcile(0.5, nan)   # non-finite REAL cost coming from the provider
        case("N1: a NaN cost becomes the estimate (conservative), not NaN",
             math.isfinite(led_nan.spent) and abs(led_nan.spent - 0.5) < 1e-9)
        led_nan.reserve(0.4)          # 0.5 + 0.4 = 0.9 < 1.0, still fits
        try:
            led_nan.reserve(0.3)      # 0.9 + 0.3 = 1.2 > 1.0
            case("N1b: the ceiling STILL holds after a NaN cost", False)
        except BudgetExceeded:
            case("N1b: the ceiling STILL holds after a NaN cost", True)

        # NaN on disk: `json.loads` accepts the NaN literal without complaint.
        for text, desc in [('{"spent_usd": NaN, "calls": 1, "reservations": {}}', "spent NaN"),
                           ('{"spent_usd": Infinity, "calls": 1, "reservations": {}}',
                            "spent Infinity"),
                           ('{"spent_usd": 1.0, "calls": 1, "cap_usd": NaN, '
                            '"reservations": {}}', "cap NaN"),
                           ('{"spent_usd": 1.0, "calls": 1, "reservations": '
                            '{"x": {"usd": NaN, "ts": 1}}}', "reservation NaN")]:
            lpn = tmp / f"nan-{desc.replace(' ', '-')}.json"
            lpn.write_text(text)
            try:
                l_ = BudgetLedger(cap_usd=15.0, persist=True, ledger_path=lpn)
                case(f"N2: a ledger with {desc} fails CLOSED (does not zero the spend)",
                     False if desc.startswith("spent") else math.isfinite(l_.spent))
            except LedgerCorrupted:
                case(f"N2: a ledger with {desc} fails CLOSED (does not zero the spend)", True)

        # N2b — the `parse_constant` and the `isfinite` look redundant and are not. The
        # isfinite only looks at the fields I validated (spent_usd, calls,
        # reservations); the parse_constant refuses the NaN literal in ANY field,
        # including one that only exists in the future. Without it, a NaN enters the
        # dict and waits for someone to read it.
        lp_x = tmp / "nan-unknown-field.json"
        lp_x.write_text('{"spent_usd": 1.0, "calls": 1, "reservations": {}, '
                        '"some_future_field": NaN}')
        try:
            BudgetLedger(cap_usd=15.0, persist=True, ledger_path=lp_x)
            case("N2b: a NaN in a NOT-yet-validated field is still refused (parse_constant)", False)
        except LedgerCorrupted:
            case("N2b: a NaN in a NOT-yet-validated field is still refused (parse_constant)", True)

        # and the catalog pricing, the other entry door for numbers from the provider
        c_nan = ORClient(ledger=BudgetLedger(cap_usd=5.0, persist=False),
                         api_key="k", outputs_dir=tmp / "nanprice")
        c_nan._catalog = {"nan/model": {"pricing": {"prompt": "nan", "completion": "1"}}}
        try:
            c_nan._estimate("nan/model", [{"role": "user", "content": "x"}], 10)
            case("N3: non-finite pricing in the catalog is fail-closed", False)
        except RuntimeError:
            case("N3: non-finite pricing in the catalog is fail-closed", True)

        # ============ MONEY PATH: RETRY, BILLING, AND THE PAID RESPONSE ============

        # M1 (#3) — a 429 in the body is NOT a generation. `generated` counted every
        # `_Retriable`, and the rate limit comes in as _Retriable — but a rate limit is
        # the provider REFUSING: nothing was generated and nothing was billed there.
        # Each false `generated` charges one full ESTIMATE extra; with 2 refusals the
        # ledger inflates the run with no real cent behind it.
        Handler.mode, Handler.hits = "error_429_in_body", 0
        led_429 = BudgetLedger(cap_usd=100.0, persist=False)
        c429 = ORClient(ledger=led_429, api_key="k", outputs_dir=tmp / "r429")
        c429._catalog = {"test/model": {"pricing": {"prompt": "0.000001",
                                                    "completion": "0.000002"}}}
        out429 = c429.chat("test/model", [{"role": "user", "content": "hi"}],
                           max_tokens=10)
        case("M1: a 429 in the stream body does not count as a billed generation",
             abs(led_429.spent - out429["cost_usd"]) < 1e-9)

        # M2 (#4) — on the FAILURE path, what was already generated has to be charged.
        # `charge_extra` is only reached on the SUCCESS path: if the retry runs out,
        # `generated` dies inside the exception (becomes text in the message) and the
        # ledger charges only one estimate, when the provider generated and billed
        # MAX_RETRIES times. It is the undercount charge_extra exists to prevent, in
        # the branch where it is largest.
        Handler.mode, Handler.hits = "no_done", 0
        led_f = BudgetLedger(cap_usd=100.0, persist=False)
        cf = ORClient(ledger=led_f, api_key="k", outputs_dir=tmp / "failure")
        cf._catalog = {"test/model": {"pricing": {"prompt": "0.000001",
                                                  "completion": "0.000002"}}}
        est_f = cf._estimate("test/model", [{"role": "user", "content": "hi"}], 10)
        try:
            cf.chat("test/model", [{"role": "user", "content": "hi"}], max_tokens=10)
        except Exception:
            pass
        # EQUALITY, not `>=`. The `>=` I had written here let the WRONG result pass:
        # with charge_failure + charge_extra adding est*(generated+1), the total was 5
        # estimates for 4 attempts and the test passed happily. A billing test that
        # accepts "at least X" does not test billing — it tests that some happened.
        case("M2: an exhausted retry charges EXACTLY one estimate per generation",
             abs(led_f.spent - est_f * or_client.MAX_RETRIES) < 1e-9)

        # M3 (#5) — an ALREADY-PAID response must not vanish when the cap blows. The
        # `reconcile` raises BudgetExceeded after the call has been billed; if the
        # exception bubbles up bare, the paid text goes in the trash and the run
        # reprocesses (and pays) again. The money is already gone: the caller must be
        # able to save the result.
        Handler.mode, Handler.hits = "ok", 0
        led_c = BudgetLedger(cap_usd=0.2, persist=False)  # lower than the cost (0.5)
        cc = ORClient(ledger=led_c, api_key="k", outputs_dir=tmp / "capblown")
        cc._catalog = {"test/model": {"pricing": {"prompt": "0.000001",
                                                  "completion": "0.000002"}}}
        try:
            cc.chat("test/model", [{"role": "user", "content": "hi"}], max_tokens=10)
            case("M3: a cap blown in reconcile raises BudgetExceeded", False)
        except BudgetExceeded as e:
            case("M3: a cap blown in reconcile raises BudgetExceeded", True)
            # `response` is the attribute's cross-file API name (read by cells.py too)
            case("M3: the ALREADY-PAID response travels in the exception (not thrown away)",
                 getattr(e, "response", None) is not None
                 and e.response.get("text") == "hi world")

        # M4 (#9) — reading a 429's `.text` must not turn retriable into terminal.
        # With stream=True the body is still open; if the read blows the deadline, the
        # exception rises from inside the 429 branch and the retry NEVER happens. The
        # engine gives up on a call the provider told it to repeat.
        class _PoisonedResp:
            status_code = 429
            headers = {"Retry-After": "0"}

            @property
            def text(self):
                raise DeadlineExceeded("deadline blew while reading the 429 body")

            def close(self):
                pass

        class _PoisonedSession:
            def __init__(self):
                self.posts = 0

            def post(self, *a, **kw):
                self.posts += 1
                return _PoisonedResp()

        sv = _PoisonedSession()
        led_v = BudgetLedger(cap_usd=100.0, persist=False)
        cv = ORClient(ledger=led_v, api_key="k", session=sv, outputs_dir=tmp / "poison")
        cv._catalog = {"test/model": {"pricing": {"prompt": "0.000001",
                                                  "completion": "0.000002"}}}
        try:
            cv.chat("test/model", [{"role": "user", "content": "hi"}], max_tokens=10)
        except Exception:
            pass
        case("M4: a 429 whose body cannot be read is still RETRIED",
             sv.posts == or_client.MAX_RETRIES)

        # ================== THE BATCH THAT WAS ANNOUNCED AND NEVER APPLIED ==================
        # Three fixes I reported as done that were not in the file: the script that
        # would apply them aborted on the first assert and the write never ran. These
        # are the red tests that should have existed the first time — a test would have
        # exposed the false announcement on the spot.

        # ---- L1: the ledger does NOT get pinned to the lowest ceiling that ever passed through it ----
        # I had implemented `min(this instance's cap, cap on disk)` and persisted the
        # lower one. That created a poisoned ledger: a $0.50 typo in one run blocked a
        # legitimate $50 run later, and the only way out was deleting the file — which
        # deletes the spend history with it. The cap is the policy of whoever is
        # running NOW; the spend is what is run state.
        lp = tmp / "effective-cap.json"
        low = BudgetLedger(cap_usd=5.0, persist=True, ledger_path=lp)
        low.reserve(1.0)
        low.reconcile(1.0, 1.0)
        high = BudgetLedger(cap_usd=50.0, persist=True, ledger_path=lp)
        try:
            high.reserve(10.0)   # 1 spent + 10 = 11, below THIS instance's ceiling (50)
            case("L1: an earlier instance's cap does not become the file's permanent ceiling",
                 True)
        except BudgetExceeded:
            case("L1: an earlier instance's cap does not become the file's permanent ceiling",
                 False)
        high.release(10.0)

        # L1c: the reconcile interrupts at THIS instance's ceiling against the run's
        # accumulated spend. It is the point where the REAL cost (which can exceed the
        # estimate) stops the run — and it has to look at the file's total, not just
        # what this process spent, otherwise two instances breach the ceiling together.
        lp_r = tmp / "cap-reconcile.json"
        r1 = BudgetLedger(cap_usd=5.0, persist=True, ledger_path=lp_r)
        r1.reserve(3.0); r1.reconcile(3.0, 3.0)          # the run already has 3 spent
        r2 = BudgetLedger(cap_usd=5.0, persist=True, ledger_path=lp_r)
        r2.reserve(1.0)
        try:
            r2.reconcile(1.0, 2.5)   # real 2.5; total 3 + 2.5 = 5.5 > 5
            case("L1c: reconcile stops at the run's ACCUMULATED spend, not just the local one",
                 False)
        except BudgetExceeded:
            case("L1c: reconcile stops at the run's ACCUMULATED spend, not just the local one",
                 True)

        # ---- L2: a ledger that PARSES but holds typed junk is corruption, not a new run ----
        # The fail-closed only covered unreadable JSON. `{"spent_usd": "a lot"}` and
        # `{"spent_usd": null}` parse, fall into the `except (TypeError, ValueError)` /
        # the `or 0.0`, silently become 0.0 — and give back the WHOLE cap. It is the
        # same fail-open that LedgerCorrupted exists to close, coming in through the
        # other door.
        for junk, desc in [('{"spent_usd": "a lot", "calls": 1}', "string"),
                           ('{"spent_usd": null, "calls": 1}', "null"),
                           ('{"spent_usd": [1,2], "calls": 1}', "list"),
                           ('{"spent_usd": true, "calls": 1}', "bool"),
                           ('{"spent_usd": 1.0, "calls": "two"}', "calls string")]:
            lp2 = tmp / f"junk-{desc.replace(' ', '-')}.json"
            lp2.write_text(junk)
            try:
                BudgetLedger(cap_usd=5.0, persist=True, ledger_path=lp2)
                case(f"L2: a ledger with {desc} in place of the number fails CLOSED", False)
            except LedgerCorrupted:
                case(f"L2: a ledger with {desc} in place of the number fails CLOSED", True)
        # L2c: a MALFORMED reservation is corruption; an EXPIRED one is an orphan. The
        # difference matters because discarding a reservation gives its budget back to
        # the cap — in-flight money vanishes from the books. Also found by mutation:
        # neutralizing the check knocked nothing over, because every reservation test
        # used well-formed input.
        for junk, desc in [('{"spent_usd": 1.0, "reservations": {"x": "not-a-dict"}}',
                            "reservation that is not an object"),
                           ('{"spent_usd": 1.0, "reservations": {"x": {"usd": 2.0}}}',
                            "reservation without ts"),
                           ('{"spent_usd": 1.0, "reservations": {"x": {"usd": "abc", "ts": 1}}}',
                            "reservation with unreadable usd"),
                           ('{"spent_usd": 1.0, "reservations": "not-an-object"}',
                            "reservations that is not an object")]:
            lpr = tmp / f"res-{desc.replace(' ', '-')}.json"
            lpr.write_text(junk)
            try:
                BudgetLedger(cap_usd=5.0, persist=True, ledger_path=lpr)
                case(f"L2c: {desc} fails CLOSED (does not give the budget back to the cap)", False)
            except LedgerCorrupted:
                case(f"L2c: {desc} fails CLOSED (does not give the budget back to the cap)", True)

        # L2d — `reservations: null` used to be converted to {} ON PURPOSE by me, and
        # that is fail-open: another process's in-flight reservation is precisely what
        # keeps two runs from spending the same money. Erasing them gives everything
        # back to the cap.
        for txt, d in [('{"spent_usd":1.0,"calls":1,"reservations":null}', "reservations null"),
                       ('{"spent_usd":1.0,"calls":2.7,"reservations":{}}', "fractional calls"),
                       ('{"spent_usd":1.0,"calls":1,"reservations":{"x":{"usd":"2.0","ts":1}}}',
                        "usd as string")]:
            f_ = tmp / f"l2d-{d.replace(' ', '-')}.json"
            f_.write_text(txt)
            try:
                BudgetLedger(cap_usd=15.0, persist=True, ledger_path=f_)
                case(f"L2d: {d} fails CLOSED", False)
            except LedgerCorrupted:
                case(f"L2d: {d} fails CLOSED", True)

        # and the legitimate case stays legitimate: absent/empty = new run
        lp3 = tmp / "new.json"
        try:
            led_new = BudgetLedger(cap_usd=5.0, persist=True, ledger_path=lp3)
            case("L2: an absent ledger is still a new run (not corruption)",
                 led_new.spent == 0.0)
        except LedgerCorrupted:
            case("L2: an absent ledger is still a new run (not corruption)", False)

        # ---- L3: extra_body via ALLOWLIST, not a 5-key denylist ----
        # The denylist blocked model/messages/max_tokens/stream/usage and let through
        # `models` (fallback list — CHANGES which model bills), `provider` (route and
        # price), `route`, and `n` (multiplies the generation and the bill). All enter
        # the payload AFTER the estimate that reserved the budget, so the cap is
        # breached by an arbitrary factor with no error at all. cells.py forwards a
        # `request` coming from the task: it is reachable via ordinary data, not just
        # malice.
        c_ab = ORClient(ledger=BudgetLedger(cap_usd=5.0, persist=False),
                        api_key="k", outputs_dir=tmp / "ab")
        for key, value in [("models", ["openai/gpt-5.6"]), ("provider", {"order": ["x"]}),
                           ("route", "fallback"), ("n", 4),
                           ("max_completion_tokens", 99999)]:
            try:
                c_ab.chat("z/m", [{"role": "user", "content": "hi"}],
                          extra_body={key: value})
                case(f"L3: extra_body rejects {key!r} (swaps model/route/volume)", False)
            except ValueError:
                case(f"L3: extra_body rejects {key!r} (swaps model/route/volume)", True)
            except Exception:
                # any other exception means it got past the validation
                case(f"L3: extra_body rejects {key!r} (swaps model/route/volume)", False)

        print(f"{sum(results)}/{len(results)} tests ok")
        return 0 if all(results) else 1
    finally:
        srv.shutdown()
        __import__("shutil").rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
