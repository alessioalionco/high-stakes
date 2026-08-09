#!/usr/bin/env python3
"""
gate_b_check.py — the Gate B checklist DERIVED FROM THE CONTRACT by code, not from
memory (attacks the composition layer of the failure class: a cost gate assembled
from memory presents an incomplete plan as complete).

Usage (adapter, when assembling Gate B — the output is PASTED into the gate; the
model fills in the numbers over code-emitted lines):

    python3 -m high_stakes.gate_b_check <manifest.yaml>
    python3 -m high_stakes.gate_b_check <manifest.yaml> --cost-lines <plan.json>

Without --cost-lines: prints the flow STEP checklist + the mandatory cost COMPONENTS
for the preset declared in the manifest (exit 0; manifest missing fields → exit ≠0,
same rule as the flow gate). With --cost-lines (JSON: list of component names the
estimate covers): verifies coverage — a mandatory component absent from the list →
exit ≠0 naming what is missing. A missing step becomes VISIBLE in the gate instead of
silently absent from the cost.

Source of steps/components: core/sections/interactive-gates.md (quick×full presets) +
core/execution.md (total-cost formula). This module is the EXECUTABLE version of that
table — when the contract changes, this changes with it (and the test locks the
correspondence).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from .flow_gate import FlowGateError, parse_manifest_fields, validate_gate_b_fields

# components of the total-cost formula (core/execution.md §estimate)
COST_CELLS = "cells"
COST_RESEARCH = "research"
COST_FLOORCHECK = "floor-check"
COST_CHAIRMAN = "chairman"
COST_REFUTER = "refuter"


def derive_checklist(fields: dict) -> dict:
    """Derives {steps, cost_components} from the declared preset. Field validation is
    the SAME rule as the flow gate (shared `validate_gate_b_fields` — the same
    contract is not validated twice with different wording); fails closed on invalid."""
    gb = validate_gate_b_fields(fields)
    preset, research = gb["preset"], gb["research"]

    prepass_required = (preset == "full" and gb["domain_new"] is True
                        and not gb["pool"])

    steps: list[str] = []
    if prepass_required:
        steps.append("board pre-pass (forward; full + new domain without a pool)")
    if research == "waived":
        steps.append("research: WAIVED (declared at Gate B — no evidence pack)")
    else:
        steps.append("research (moderator agenda"
                     + (" + pre-pass requests" if prepass_required else "") + ")")
        steps.append("evidence pack (write_pack → automatic flow receipt)")
        steps.append("★ facts only the decider has (reconciliation before the cells)")
    steps.append("panel cells (N personas × M models — the flow gate arms here)")
    steps.append("refuter (external family)")
    steps.append("Chairman synthesis (brand-blind)")
    steps.append("gated render (render_gate + qverify, exit 0 required)")

    components = []
    if research != "waived":
        components.append(COST_RESEARCH)  # includes the pre-pass — the expensive leg
    components += [COST_CELLS, COST_REFUTER, COST_CHAIRMAN]
    # floor-check only fires under a pin trigger (expired/release/domain) — conditional
    return {"preset": preset, "prepass_required": prepass_required,
            "research": research, "steps": steps,
            "cost_components": components,
            "cost_conditional": [COST_FLOORCHECK + " (only under a pin trigger)"]}


def check_cost_lines(checklist: dict, cost_lines: list[str]) -> list[str]:
    """Mandatory components that do NOT appear in the declared cost lines
    (case-insensitive substring match — 'cells 8×3' covers 'cells')."""
    declared = [str(line).lower() for line in cost_lines]
    return [comp for comp in checklist["cost_components"]
            if not any(comp.lower() in d for d in declared)]


def render(checklist: dict) -> str:
    out = [f"GATE B · checklist derived from the contract (preset={checklist['preset']}, "
           f"research={checklist['research']}, "
           f"pre-pass={'YES' if checklist['prepass_required'] else 'no'})",
           "", "Post-GO flow steps (transcribe into the run's README journal; strike an "
           "item only when its artifact exists on disk):"]
    out += [f"  {i}. {s}" for i, s in enumerate(checklist["steps"], 1)]
    out += ["", "MANDATORY components of the cost estimate:"]
    out += [f"  - {c}" for c in checklist["cost_components"]]
    # conditional in its OWN block: inside the mandatory list, the suffix was the
    # only cue and readers treated floor-check as mandatory (review finding)
    out += ["Conditional (outside the --cost-lines rule):"]
    out += [f"  - {c}" for c in checklist["cost_conditional"]]
    return "\n".join(out)


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    manifest = Path(argv[0])
    cost_file = None
    if "--cost-lines" in argv:
        idx = argv.index("--cost-lines")
        if idx + 1 >= len(argv):
            print("gate_b_check: --cost-lines requires a JSON file", file=sys.stderr)
            return 2
        cost_file = Path(argv[idx + 1])
    try:
        checklist = derive_checklist(parse_manifest_fields(manifest))
    except FlowGateError as e:
        print(f"GATE B INCOMPLETE: {e}", file=sys.stderr)
        return 1
    print(render(checklist))
    if cost_file is not None:
        try:
            cost_lines = json.loads(cost_file.read_text())
        except (OSError, json.JSONDecodeError) as e:
            print(f"gate_b_check: unreadable cost-lines: {e}", file=sys.stderr)
            return 2
        if not isinstance(cost_lines, list):
            print("gate_b_check: cost-lines must be a LIST of lines", file=sys.stderr)
            return 2
        missing = check_cost_lines(checklist, cost_lines)
        if missing:
            print("\nINCOMPLETE COST — contract components MISSING from the estimate: "
                  + ", ".join(missing), file=sys.stderr)
            return 1
        print("\ncost OK: every mandatory component covered.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
