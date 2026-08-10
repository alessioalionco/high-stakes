#!/usr/bin/env python3
"""test_cells.py — executable suite for the parallel dispatcher (this project's convention).

Why it exists: `cells.py` was the only module the README declared as covered only
indirectly — and it is where four invariants live that, if broken, break silently and
cost money:

  1. **a failing cell does NOT vanish** — without this, a 33-cell panel comes back with 31
     and the dossier is written over a hole nobody saw;
  2. **a duplicate id is blocked BEFORE dispatch** — afterwards the money is already spent,
     and the cells still overwrite each other on disk;
  3. **the repair bills BOTH attempts** — the ledger billed both; counting one
     underestimates the run's spend;
  4. **resume is locked by input hash** — reusing by filename would return the
     answer of a prompt that is no longer the same.
"""
import os as _os
import tempfile as _tempfile

# Isolation from the DEVELOPER's configuration, and it must run before high_stakes is imported.
# `config.home()` falls back to ~/.high-stakes, so a machine with `require_build_check = true`
# in its own config made this suite fail on code that is fine — the suite measured the
# environment, not the change. A previous commit claimed to isolate every suite and missed this
# one; the claim is only true when each entry point sets the variable itself.
_os.environ["HIGH_STAKES_HOME"] = _tempfile.mkdtemp(prefix="hs-test-home-")

import json
import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path

from high_stakes.cells import (cell_filename, input_hash_for, load_cells, run_cell,
                               run_cells)
from high_stakes.or_client import SchemaInvalid

OUT = {"text": '{"v": 1}', "cost_usd": 0.10, "provider": "p", "usage": {"t": 1},
       "model": "m", "raw": {}}


class FakeClient:
    """Fake, thread-safe client with a per-call script."""

    def __init__(self, script=None, delay=0.0):
        self.script = list(script or [])
        self.calls = 0
        self.in_flight = 0
        self.peak = 0
        self._lock = threading.Lock()
        self._delay = delay

    def chat(self, model, messages, **kw):
        with self._lock:
            self.calls += 1
            self.in_flight += 1
            self.peak = max(self.peak, self.in_flight)
            step = self.script.pop(0) if self.script else dict(OUT)
        try:
            if self._delay:
                time.sleep(self._delay)
            if isinstance(step, Exception):
                raise step
            return step
        finally:
            with self._lock:
                self.in_flight -= 1


def task(cid="c1", parse=None, **kw):
    t = {"cell_id": cid, "model": "test/m", "messages": [{"role": "user", "content": "hi"}],
         "parse": parse or (lambda s: json.loads(s)), "request": {}, "meta": {}}
    t.update(kw)
    return t


def main() -> int:
    results: list[bool] = []

    def case(name, cond):
        print(("PASS " if cond else "FAIL ") + name)
        results.append(bool(cond))

    tmp = Path(tempfile.mkdtemp())
    try:
        # ---- happy path + provenance ----
        d = tmp / "a"
        c = FakeClient()
        r = run_cell(c, task(), d)
        case("ok cell records result and status", r["status"] == "ok" and r["result"] == {"v": 1})
        case("engine provenance is stamped",
             all(k in r for k in ("input_hash", "latency_s", "timestamp", "cost_usd")))
        case("the cell's JSON exists on disk", (d / cell_filename("c1")).exists())

        # ---- INVARIANT 1: a failure does not vanish ----
        d = tmp / "b"
        c = FakeClient(script=[RuntimeError("provider went down")])
        r = run_cell(c, task("c_exc"), d)
        case("REGRESSION: an exception becomes status=exception (does not propagate)", r["status"] == "exception")
        case("REGRESSION: a cell with an exception PERSISTS to disk (does not vanish from the panel)",
             (d / cell_filename("c_exc")).exists()
             and json.loads((d / cell_filename("c_exc")).read_text())["status"] == "exception")

        d = tmp / "c"
        c = FakeClient(script=[{**OUT, "text": "this is not json"},
                               {**OUT, "text": "still is not"}])
        r = run_cell(c, task("c_bad", parse=lambda s: (_ for _ in ()).throw(SchemaInvalid("x"))), d)
        case("REGRESSION: unparseable becomes status=failed, with the raw text preserved",
             r["status"] == "failed" and r["raw_text"])
        case("REGRESSION: a failed cell PERSISTS to disk", (d / cell_filename("c_bad")).exists())

        # ---- INVARIANT 3: the repair bills BOTH attempts ----
        state = {"n": 0}

        def parse_2a(s):
            state["n"] += 1
            if state["n"] == 1:
                raise SchemaInvalid("wrong format")
            return {"ok": True}

        d = tmp / "d"
        c = FakeClient(script=[dict(OUT), dict(OUT)])
        r = run_cell(c, task("c_rep", parse=parse_2a), d)
        case("repair-retry happens 1x and the 2nd attempt counts",
             r["status"] == "ok" and r["retries"] == 1 and c.calls == 2)
        case("REGRESSION: the cost sums BOTH attempts (the ledger billed both)",
             abs(r["cost_usd"] - 0.20) < 1e-9)

        # ---- INVARIANT 4: resume locked by input hash ----
        d = tmp / "e"
        c = FakeClient()
        run_cell(c, task("c_re"), d)
        r2 = run_cell(c, task("c_re"), d)
        case("REGRESSION: identical input REUSES (does not re-bill)",
             r2.get("_skipped") is True and c.calls == 1)

        other = task("c_re", messages=[{"role": "user", "content": "DIFFERENT PROMPT"}])
        r3 = run_cell(c, other, d)
        case("REGRESSION: prompt changed -> does NOT reuse (or it would return another input's answer)",
             not r3.get("_skipped") and c.calls == 2)

        d = tmp / "f"
        c = FakeClient()
        run_cell(c, task("c_pv", meta={"prompt_version": "v1"}), d)
        r = run_cell(c, task("c_pv", meta={"prompt_version": "v2"}), d)
        case("a different prompt_version invalidates the reuse",
             not r.get("_skipped") and c.calls == 2)

        case("input hash changes with the request, not just with the messages",
             input_hash_for("m", [{"a": 1}], {"max_tokens": 10})
             != input_hash_for("m", [{"a": 1}], {"max_tokens": 20}))

        # ---- INVARIANT 2: duplicate blocked BEFORE spending ----
        d = tmp / "g"
        c = FakeClient()
        try:
            run_cells(c, [task("x"), task("x")], d, quiet=True)
            case("REGRESSION: duplicate cell_id FAILS before dispatch", False)
        except ValueError:
            case("REGRESSION: duplicate cell_id FAILS before dispatch", c.calls == 0)

        try:  # 'a/b' and 'a-b' sanitize to the same file
            run_cells(c, [task("a/b"), task("a-b")], d, quiet=True)
            case("REGRESSION: post-sanitization filename collision FAILS before dispatch",
                 False)
        except ValueError:
            case("REGRESSION: post-sanitization filename collision FAILS before dispatch",
                 c.calls == 0)

        # ---- parallel: one dead leg does not take the run down ----
        d = tmp / "h"
        c = FakeClient(script=[dict(OUT), RuntimeError("died"), dict(OUT)])
        rs = run_cells(c, [task("p1"), task("p2"), task("p3")], d, concurrency=3, quiet=True)
        st = sorted(x["status"] for x in rs)
        case("REGRESSION: 1 failing cell does NOT take the others down",
             len(rs) == 3 and st.count("ok") == 2 and st.count("exception") == 1)
        case("all 3 cells are on disk, including the one that failed",
             len(list(d.glob("*.json"))) == 3)
        case("load_cells is the inverse of run_cells (brings the failures too)",
             len(load_cells(d)) == 3)

        d = tmp / "i"
        c = FakeClient(delay=0.05)
        run_cells(c, [task(f"k{i}") for i in range(8)], d, concurrency=3, quiet=True)
        case("the concurrency cap is respected", c.peak <= 3)

        # ---- experiment meta does not override engine provenance ----
        d = tmp / "j"
        c = FakeClient()
        r = run_cell(c, task("c_meta", meta={"persona": "unit economist", "cost_usd": 999.0,
                                             "status": "a lie"}), d)
        case("REGRESSION: meta does NOT override the engine's cost or status",
             r["cost_usd"] == 0.10 and r["status"] == "ok")
        case("legitimate experiment meta is preserved", r["persona"] == "unit economist")

        # ---- the ALREADY-PAID response that arrives inside an exception must not be thrown away ----
        # The cap can blow AFTER the call has been paid for: the ledger's reconcile
        # raises with the real cost already debited, and the exception carries the
        # result in `.response`. Ignoring it records `cost_usd: 0`, loses text that
        # cost money and leaves the cell eligible to re-run — paying again.
        # Found in review: `chat` started attaching the response, but the consumer of
        # the exception (here) was never taught to look. Half a fix is no fix.
        class ClientThatBlowsTheCap:
            def chat(self, model, messages, **kw):
                from high_stakes.or_client import BudgetExceeded
                e = BudgetExceeded("cap blown in reconcile")
                e.response = {"text": '{"ok": "paid"}', "cost_usd": 0.42,
                              "provider": "spy", "usage": {}, "raw": {}}
                raise e

        r_paid = run_cell(ClientThatBlowsTheCap(),
                          task("c_paid", parse=lambda s: json.loads(s)), d)
        case("cap blown after payment: the paid text is PRESERVED",
             r_paid.get("parsed") == {"ok": "paid"} or "paid" in str(r_paid))
        case("cap blown after payment: the real cost is recorded (not zero)",
             abs(r_paid["cost_usd"] - 0.42) < 1e-9)

        print(f"{sum(results)}/{len(results)} tests ok")
        return 0 if all(results) else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
