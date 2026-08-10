#!/usr/bin/env python3
"""test_flow_gate.py — executable suite for the flow gate (GO→execution hand-off).

Why it exists: GO→execution was the only hand-off without a code gate, and it is
exactly where a panel can fire without evidence (parametric opinion — the defect the
engine exists to kill). This suite locks the fix through the CONSUMER'S VALIDATOR:
the integration tests go THROUGH the real `run_cells`/`run_cell` over on-disk run
fixtures (never re-implementing the rule), with a spy that counts dispatches — a
block has to happen with $0 spent.

Regressions locked:
  - GO without a pack (and without a pre-pass on full + new domain) is refused;
  - the pre-pass is NOT blocked by the gate (the naive design's deadlock);
  - single `run_cell` is not a bypass;
  - a pack that exists but is absent from the messages (consumption) is refused;
  - an all-failed pack (asks_ok=0) does not release the panel;
  - a pack swapped mid-round (pin) or not matching the receipt (sha) is refused;
  - a legacy manifest (no fields) → error with a migration hint;
  - experiments (no manifest) stay untouched.
"""
import os as _os
import tempfile as _tempfile

# Isolation from the DEVELOPER's configuration, and it must run before high_stakes is imported.
# `config.home()` falls back to ~/.high-stakes, so a machine with `require_build_check = true`
# in its own config made this suite fail on code that is fine — the suite measured the
# environment, not the change. A previous commit claimed to isolate every suite and missed this
# one; the claim is only true when each entry point sets the variable itself.
_os.environ["HIGH_STAKES_HOME"] = _tempfile.mkdtemp(prefix="hs-test-home-")

import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

from high_stakes.cells import run_cell, run_cells
from high_stakes.flow_gate import (FlowGateError, RECEIPT_FILENAME, check_flow,
                                   panel_round_dir, run_root_for)

PACK_TEXT = "=== EVIDENCE ===\nMedian NRR 2026: 108% [source]\n"


class SpyClient:
    """Counts dispatches. A working gate = calls == 0 when it blocks."""

    def __init__(self):
        self.calls = 0

    def chat(self, model, messages, **kw):
        self.calls += 1
        return {"text": "resp", "cost_usd": 0.001, "provider": "spy",
                "usage": {}, "raw": {}}


def make_run(tmp: Path, name: str, preset="quick", domain_new=None, pool=None,
             research=None, pack=PACK_TEXT, receipt=True, asks_ok=1,
             prepass=None) -> tuple[Path, Path]:
    """Decision-run fixture in the contract layout. Returns (run_root, cells_dir)."""
    run = tmp / name
    (run / "research").mkdir(parents=True)
    man = ["decision: fixture", f"preset: {preset}"]
    if domain_new is not None:
        man.append(f"domain_new: {str(domain_new).lower()}")
    if pool:
        man.append(f"pool: {pool}")
    if research:
        man.append(f"research: {research}")
    man += ["roster_frozen:", "  chairman: {model: x}"]  # nested: the flat scan ignores
    (run / "manifest.yaml").write_text("\n".join(man) + "\n")
    if pack is not None:
        (run / "research" / "evidence-pack.md").write_text(pack)
        if receipt:
            sha = hashlib.sha256(pack.encode("utf-8")).hexdigest()
            (run / "research" / RECEIPT_FILENAME).write_text(json.dumps(
                {"pack_sha256": sha, "asks_ok": asks_ok, "asks_failed": 0}))
    cells_dir = run / "rounds" / "r1" / "cells"
    cells_dir.mkdir(parents=True)
    if prepass is not None:
        pdir = run / "rounds" / "r1" / "prepass"
        pdir.mkdir(parents=True)
        for i, status in enumerate(prepass):
            if status == "malformed":
                (pdir / f"prepass_{i}.json").write_text("{ not json")
            else:
                (pdir / f"prepass_{i}.json").write_text(
                    json.dumps({"cell_id": f"p{i}", "status": status}))
    return run, cells_dir


def task(with_pack=True, cid="cell_a_m1"):
    """A panel cell; the material (pack) enters as the user prefix, per the contract."""
    material = (PACK_TEXT if with_pack else "(no evidence)") + "\npersona + ask"
    return {"cell_id": cid, "model": "fam/m1",
            "messages": [{"role": "system", "content": "s"},
                         {"role": "user", "content": material}],
            "parse": lambda t: {"ok": True}, "request": {}, "meta": {}}


def blocked(fn, needle: str) -> bool:
    """True when fn() raises FlowGateError whose message contains `needle`."""
    try:
        fn()
        return False
    except FlowGateError as e:
        return needle in str(e)


def main() -> int:
    tmp = Path(tempfile.mkdtemp())
    results: list[bool] = []

    def case(name, cond):
        print(("PASS " if cond else "FAIL ") + name)
        results.append(bool(cond))

    try:
        # ---- predicate: where the gate arms and where it does NOT ----
        run, cells = make_run(tmp, "r-pred")
        case("rounds/rN/cells is a panel dir", panel_round_dir(cells) is not None)
        case("rounds/rN/prepass is NOT a panel dir",
             panel_round_dir(run / "rounds" / "r1" / "prepass") is None)
        case("run_root_for derives the root POSITIONALLY (rounds/'s parent)",
             run_root_for(run / "rounds" / "r1") == run.resolve())
        exp = tmp / "experiment" / "cells_out"
        exp.mkdir(parents=True)
        # a manifest ABOVE the contract position must not arm the gate (no ancestor walk)
        stray = tmp / "stray" / "rounds" / "r1" / "cells"
        stray.mkdir(parents=True)
        (tmp / "manifest.yaml").write_text("preset: quick\n")
        case("a stray ancestor manifest does NOT arm the gate (root is positional)",
             run_root_for(stray.parent) is None)
        (tmp / "manifest.yaml").unlink()

        # ---- THE regression: GO without a pack → blocked BEFORE spending ----
        run, cells = make_run(tmp, "r-regression", preset="full", domain_new=True,
                              pack=None)
        spy = SpyClient()
        case("REGRESSION: run_cells without an evidence pack raises FlowGateError",
             blocked(lambda: run_cells(spy, [task()], cells, quiet=True),
                     "evidence pack"))
        case("REGRESSION: blocked with ZERO dispatches ($0 spent)", spy.calls == 0)
        case("REGRESSION: no cell persisted", not list(cells.glob("*.json")))

        # ---- single run_cell is not a bypass ----
        spy = SpyClient()
        case("direct run_cell is gated too",
             blocked(lambda: run_cell(spy, task(), cells), "evidence pack")
             and spy.calls == 0)

        # ---- the pre-pass is NOT blocked (the naive design's deadlock) ----
        prepass_dir = run / "rounds" / "r1" / "prepass"
        spy = SpyClient()
        out = run_cells(spy, [task(cid="prepass_x")], prepass_dir, quiet=True)
        case("the pre-pass runs WITHOUT a pack (gate does not arm outside cells/)",
             spy.calls == 1 and out[0]["status"] == "ok")

        # ---- happy path: quick with pack+receipt+consumption passes ----
        run, cells = make_run(tmp, "r-happy")
        spy = SpyClient()
        out = run_cells(spy, [task()], cells, quiet=True)
        case("quick with a consumed pack DISPATCHES normally",
             spy.calls == 1 and out[0]["status"] == "ok")
        pin = run / "rounds" / "r1" / "pack.sha256"
        case("the first dispatch writes the round pin", pin.is_file())

        # NEW round: run_cells creates out_dir itself — the gate must not crash
        # writing the pin into a not-yet-existing dir (review: raw FileNotFoundError)
        run, cells = make_run(tmp, "r-fresh")
        shutil.rmtree(cells)
        spy = SpyClient()
        out = run_cells(spy, [task()], cells, quiet=True)
        case("first dispatch of a new round (no cells/ dir yet) works without a crash",
             spy.calls == 1 and out[0]["status"] == "ok"
             and (run / "rounds" / "r1" / "pack.sha256").is_file())

        # ---- pin: pack swapped mid-round → blocked ----
        (run / "research" / "evidence-pack.md").write_text(PACK_TEXT + "\nEDITED\n")
        sha2 = hashlib.sha256((PACK_TEXT + "\nEDITED\n").encode()).hexdigest()
        (run / "research" / RECEIPT_FILENAME).write_text(json.dumps(
            {"pack_sha256": sha2, "asks_ok": 1, "asks_failed": 0}))
        case("a pack swapped MID-round blocks (pin diverges)",
             blocked(lambda: check_flow(cells, [task()]), "MID-round"))

        # ---- receipt: sha mismatch / asks_ok=0 / corrupted / missing ----
        run, cells = make_run(tmp, "r-sha")
        (run / "research" / "evidence-pack.md").write_text(PACK_TEXT + "tampered")
        case("pack ≠ receipt (sha) blocks",
             blocked(lambda: check_flow(cells, [task()]), "receipt"))
        run, cells = make_run(tmp, "r-zero", asks_ok=0)
        case("an all-failed pack (asks_ok=0) blocks",
             blocked(lambda: check_flow(cells, [task()]), "successful asks"))
        run, cells = make_run(tmp, "r-nonnum", receipt=False)
        sha_ok = hashlib.sha256(PACK_TEXT.encode()).hexdigest()
        (run / "research" / RECEIPT_FILENAME).write_text(json.dumps(
            {"pack_sha256": sha_ok, "asks_ok": "two", "asks_failed": 0}))
        case("a non-numeric asks_ok is treated as 0 and blocks (no crash)",
             blocked(lambda: check_flow(cells, [task()]), "successful asks"))
        run, cells = make_run(tmp, "r-noreceipt", receipt=False)
        case("a pack without a receipt blocks (write_pack emits it; a manual pack fails)",
             blocked(lambda: check_flow(cells, [task()]), "receipt"))
        run, cells = make_run(tmp, "r-badreceipt", receipt=False)
        (run / "research" / RECEIPT_FILENAME).write_text("{ not json")
        case("a corrupted receipt blocks (fail closed, not a generic crash)",
             blocked(lambda: check_flow(cells, [task()]), "receipt"))

        # ---- pre-pass required on full + new domain without a pool ----
        run, cells = make_run(tmp, "r-full", preset="full", domain_new=True)
        case("full + new domain WITHOUT a pre-pass blocks",
             blocked(lambda: check_flow(cells, [task()]), "pre-pass"))
        case("a BLOCKED dispatch writes no pin (the sha only freezes when firing)",
             not (run / "rounds" / "r1" / "pack.sha256").is_file())
        # remediating the gate's OWN error must not deadlock the round: the operator
        # runs the pre-pass and REGENERATES the pack (new sha) — it has to pass
        pdir = run / "rounds" / "r1" / "prepass"
        pdir.mkdir(parents=True)
        (pdir / "prepass_0.json").write_text(json.dumps({"cell_id": "p0", "status": "ok"}))
        new_pack = PACK_TEXT + "\n(pre-pass items)\n"
        (run / "research" / "evidence-pack.md").write_text(new_pack)
        (run / "research" / RECEIPT_FILENAME).write_text(json.dumps(
            {"pack_sha256": hashlib.sha256(new_pack.encode()).hexdigest(),
             "asks_ok": 2, "asks_failed": 0}))
        t_new = task()
        t_new["messages"][1]["content"] = new_pack + "\npersona + ask"
        try:
            check_flow(cells, [t_new])
            case("remediation (pre-pass + regenerated pack) passes without a deadlock", True)
        except FlowGateError:
            case("remediation (pre-pass + regenerated pack) passes without a deadlock", False)
        run, cells = make_run(tmp, "r-prepok", preset="full", domain_new=True,
                              prepass=["ok", "failed"])
        try:
            check_flow(cells, [task()])
            case("full + new domain WITH an ok pre-pass passes", True)
        except FlowGateError:
            case("full + new domain WITH an ok pre-pass passes", False)
        run, cells = make_run(tmp, "r-prepbad", preset="full", domain_new=True,
                              prepass=["failed", "malformed"])
        case("a failed/malformed-only pre-pass does NOT count (status is parsed)",
             blocked(lambda: check_flow(cells, [task()]), "pre-pass"))
        run, cells = make_run(tmp, "r-prepnondict", preset="full", domain_new=True)
        pdir = run / "rounds" / "r1" / "prepass"
        pdir.mkdir(parents=True)
        (pdir / "prepass_0.json").write_text('"ok"')  # valid JSON, not an object
        case("a non-object pre-pass JSON does not count (and no AttributeError crash)",
             blocked(lambda: check_flow(cells, [task()]), "pre-pass"))
        run, cells = make_run(tmp, "r-pool", preset="full", domain_new=True,
                              pool="saas-lenses")
        try:
            check_flow(cells, [task()])
            case("full with a covering pool passes without a pre-pass", True)
        except FlowGateError:
            case("full with a covering pool passes without a pre-pass", False)
        run, cells = make_run(tmp, "r-nodn", preset="full")
        case("full WITHOUT domain_new declared blocks (Gate B field)",
             blocked(lambda: check_flow(cells, [task()]), "domain_new"))

        # ---- consumption: a pack on disk that never reaches the jury ----
        run, cells = make_run(tmp, "r-consume")
        spy = SpyClient()
        case("a cell without the pack in its prompt blocks (names the cell)",
             blocked(lambda: run_cells(spy, [task(with_pack=False)], cells, quiet=True),
                     "cell_a_m1") and spy.calls == 0)
        case("a consumption block writes no pin either",
             not (run / "rounds" / "r1" / "pack.sha256").is_file())
        t_sys = task(with_pack=False)
        t_sys["messages"][0]["content"] = PACK_TEXT  # pack ONLY in system does not count
        case("a pack only in the system message blocks (the contract is the user prefix)",
             blocked(lambda: check_flow(cells, [t_sys]), "cell_a_m1"))

        # ---- a duplicated Gate B field in the manifest fails CLOSED ----
        run, cells = make_run(tmp, "r-dup", research="full")
        with (run / "manifest.yaml").open("a") as fh:
            fh.write("research: waived\n")  # a trailing duplicate must NOT win
        case("a duplicate field blocks (a waived pasted at the end cannot disarm the gate)",
             blocked(lambda: check_flow(cells, [task()]), "DUPLICATE"))

        # ---- waiver: a declared opt-out waives the pack ----
        run, cells = make_run(tmp, "r-waived", research="waived", pack=None)
        spy = SpyClient()
        out = run_cells(spy, [task(with_pack=False)], cells, quiet=True)
        case("research waived declared runs without a pack", spy.calls == 1
             and out[0]["status"] == "ok")

        # ---- legacy/invalid manifest: an instructive error, never a mute crash ----
        run, cells = make_run(tmp, "r-legacy")
        (run / "manifest.yaml").write_text("decision: old\nroster_frozen:\n")
        case("a legacy manifest (no preset) → error with a migration hint",
             blocked(lambda: check_flow(cells, [task()]), "migrate"))
        run, cells = make_run(tmp, "r-badbool")
        (run / "manifest.yaml").write_text("preset: full\ndomain_new: maybe\n")
        case("a non-boolean domain_new fails CLOSED",
             blocked(lambda: check_flow(cells, [task()]), "true|false"))
        run, cells = make_run(tmp, "r-badresearch", research="maybe")
        case("an invalid research value fails CLOSED",
             blocked(lambda: check_flow(cells, [task()]), "full|waived"))

        # ---- experiments stay 100% untouched ----
        spy = SpyClient()
        out = run_cells(spy, [task(with_pack=False)], exp, quiet=True)
        case("an experiment without a manifest runs as always",
             spy.calls == 1 and out[0]["status"] == "ok")

        print(f"{sum(results)}/{len(results)} tests ok")
        return 0 if all(results) else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
