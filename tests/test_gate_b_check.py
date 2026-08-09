#!/usr/bin/env python3
"""test_gate_b_check.py — executable suite for the mechanical Gate B checklist.

What is locked down: the Gate B checklist/cost DERIVES from the preset by code (not
from memory) — a missing step becomes a VISIBLE error (exit ≠0), never an incomplete
plan presented as complete (the composition layer of the failure class).
"""
import json
import shutil
import sys
import tempfile
from pathlib import Path

from high_stakes.flow_gate import FlowGateError
from high_stakes.gate_b_check import (COST_REFUTER, check_cost_lines,
                                      derive_checklist, main)


def main_() -> int:
    tmp = Path(tempfile.mkdtemp())
    results: list[bool] = []

    def case(name, cond):
        print(("PASS " if cond else "FAIL ") + name)
        results.append(bool(cond))

    try:
        # ---- derivation per preset ----
        c = derive_checklist({"preset": "quick"})
        case("quick: components = research+cells+refuter+chairman",
             c["cost_components"] == ["research", "cells", "refuter", "chairman"])
        case("quick: no pre-pass", c["prepass_required"] is False)
        case("quick: gated render is the last step", "gated render" in c["steps"][-1])

        c = derive_checklist({"preset": "quick", "research": "waived"})
        case("waived: research is OUT of the cost", "research" not in c["cost_components"])
        case("waived: a step marks the explicit waiver",
             any("WAIVED" in s for s in c["steps"]))

        c = derive_checklist({"preset": "full", "domain_new": True})
        case("full + new domain: the pre-pass is the 1st step",
             c["prepass_required"] is True and "pre-pass" in c["steps"][0])
        c = derive_checklist({"preset": "full", "domain_new": True, "pool": "x"})
        case("full with a pool: no pre-pass", c["prepass_required"] is False)
        c = derive_checklist({"preset": "full", "domain_new": False})
        case("full on a known domain: no pre-pass", c["prepass_required"] is False)

        # ---- fail closed: a missing field is an error, never a partial checklist ----
        for fields, name in [({}, "no preset"),
                             ({"preset": "full"}, "full without domain_new"),
                             ({"preset": "quick", "research": "x"}, "invalid research")]:
            try:
                derive_checklist(fields)
                case(f"fail closed: {name} raises", False)
            except FlowGateError:
                case(f"fail closed: {name} raises", True)

        # ---- cost coverage ----
        c = derive_checklist({"preset": "quick"})
        missing = check_cost_lines(c, ["research (2 asks) $1.20", "cells 4×3 $2.40",
                                       "chairman $0.30"])
        case("a component missing from the estimate is NAMED", missing == [COST_REFUTER])
        case("full coverage passes",
             check_cost_lines(c, ["research", "cells", "refuter", "chairman"]) == [])
        case("matching is case-insensitive substring",
             check_cost_lines(c, ["Research deep", "CELLS", "refuter x",
                                  "Chairman synthesis"]) == [])

        # ---- CLI (the adapter contract: the exit code is the rule) ----
        man = tmp / "manifest.yaml"
        man.write_text("preset: full\ndomain_new: true\n")
        case("CLI: a valid manifest → exit 0", main([str(man)]) == 0)
        legacy = tmp / "legacy.yaml"
        legacy.write_text("decision: old\n")
        case("CLI: a legacy manifest → exit 1 (Gate B incomplete)",
             main([str(legacy)]) == 1)
        lines = tmp / "cost.json"
        lines.write_text(json.dumps(["cells", "chairman"]))
        case("CLI: a cost plan with a missing component → exit 1",
             main([str(man), "--cost-lines", str(lines)]) == 1)
        lines.write_text(json.dumps(["research+prepass", "cells 8×4",
                                     "refuter", "chairman"]))
        case("CLI: a complete cost plan → exit 0",
             main([str(man), "--cost-lines", str(lines)]) == 0)
        lines.write_text("{ not json")
        case("CLI: corrupted cost-lines → exit 2 (usage error, not a gate verdict)",
             main([str(man), "--cost-lines", str(lines)]) == 2)

        print(f"{sum(results)}/{len(results)} tests ok")
        return 0 if all(results) else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main_())
