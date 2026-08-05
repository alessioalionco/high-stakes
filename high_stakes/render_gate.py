#!/usr/bin/env python3
"""render_gate.py — mechanical verifier for the render gate (core/sections/output-contract.md).

STRUCTURAL floor of the §0-§7 dossier + internal-jargon ban in the body (§0-§6; §7/appendix is a
declared exception — method honesty may name builds). Does not measure voice/nuance/quote fidelity —
that stays under R1-R4 of the contract; this gate guarantees what code can guarantee.

Floors = the ones defined in the reference format (≥1 attributed quote per convergent point — "1-2
reference quotes"; questions/suggestions by presence — the "up to 5" is a ceiling, not a floor). The
gate never tightens the ratified bar on its own.

Usage: python3 render_gate.py <report.md>   → exit 0 = green; exit 1 = red; exit 2 = usage.
API: check(md) -> list[str] (empty = green). Reentrant, no global state.
Exists because of a concrete failure mode: a shallow dossier, written from the aggregated
tallies instead of the cards. The prose contract already forbade it and did not hold.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# R3 — internal jargon forbidden in the body (§0-§6). Code FAMILIES, not instances:
# a denylist of instances rots (just invent the next code). References to
# editions and to sections remain allowed. Fork labels F1..Fn too
# (the ratified mock names forks that way) — which is why F\d codes are NOT banned.
JARGON_PATTERNS = [
    (r"X-[A-Z]{1,3}\d*", "X-* experiment code"),
    (r"EV\d+", "EV* evidence-item code"),
    (r"B-(?:qverify|vers|ledger|lens|route)", "B-* build code"),
    (r"D-[A-Z]\d+", "D-* decision code"),
    (r"R-GATE", "R-GATE mechanism code"),
]

# R7 — the dossier CIRCULATES. The "— **Name**" attribution uses real citation typography, and the
# a lens can carry the name of a real person: whoever receives the PDF in a meeting reads "<Name>
# said this about our deck". Quote verification guarantees fidelity to the CELL, not to the
# person — a strong guarantee about the wrong thing, if the reader does not know what they are reading.
# `\s+` and not " ": the sentence frequently wraps across two lines in markdown, and a rule
# that fails on a line break is a trap, not rigor (that is how it failed the project's own
# example dossier the first time it ran).
DISCLOSURE_RE = re.compile(
    r"are\s+not\s+the\s+real\s+people", re.I)

# Attributed quote = blockquote line whose "— **Name**" attribution is on the SAME line.
ATTRIB_RE = re.compile(r"—\s*\*\*.+?\*\*")

# R8 — the simulation marker travels WITH the attribution, on the same line. The §Scope
# disclosure (R7) protects the document; it does not protect the FRAGMENT. A quote cropped for a
# slide or a screenshot leaves without the §Scope, and what remains is a real-looking citation
# attributed to a person who exists. The providers' usage policies describe exactly
# this: attributing content in a way that misleads about its origin.
SIM_MARKER_RE = re.compile(r"\(simulated lens[^)]*\)")
# Prose: excludes headings, quotes, tables and ANY list (-, *, +, "1.").
NOT_PROSE_RE = re.compile(r"^(\s*#|\s*>|\s*\||\s*[-*+]\s|\s*\d+\.\s)")


def split_sections(md: str) -> dict[str, str]:
    """Map '§N'/'scope' -> section body (## delimits)."""
    out: dict[str, str] = {}
    cur, buf = None, []
    for ln in md.splitlines():
        if ln.startswith("## "):
            if cur is not None:
                out[cur] = "\n".join(buf)
            m = re.match(r"## §(\d)", ln)
            cur = f"§{m.group(1)}" if m else ("scope" if "Scope" in ln else ln[3:40])
            buf = []
        else:
            buf.append(ln)
    if cur is not None:
        out[cur] = "\n".join(buf)
    return out


def subsections(body: str) -> list[tuple[str, str]]:
    """[(heading '### ...', body)] within a section."""
    out, cur, buf = [], None, []
    for ln in body.splitlines():
        if ln.startswith("### "):
            if cur is not None:
                out.append((cur, "\n".join(buf)))
            cur, buf = ln[4:], []
        else:
            buf.append(ln)
    if cur is not None:
        out.append((cur, "\n".join(buf)))
    return out


def paragraphs(body: str) -> list[str]:
    """Blocks of DENSE prose (>80 chars; lists/quotes/tables don't count)."""
    paras, buf = [], []
    for ln in body.splitlines():
        if ln.strip() == "" or NOT_PROSE_RE.match(ln):
            if buf:
                paras.append(" ".join(buf))
                buf = []
        else:
            buf.append(ln.strip())
    if buf:
        paras.append(" ".join(buf))
    return [p for p in paras if len(p) > 80]


def quotes(body: str) -> int:
    """Number of ATTRIBUTED quotes: each '> ...— **Name**...' line counts as 1 (adjacent quotes
    without a blank line count separately — that's normal markdown)."""
    return sum(1 for ln in body.splitlines()
               if ln.startswith(">") and ATTRIB_RE.search(ln))


def check(md: str) -> list[str]:
    """Validates the dossier; returns the list of failures (empty = green gate). No global state."""
    fails: list[str] = []
    secs = split_sections(md)
    for s in ["§0", "§1", "§2", "§3", "§4", "§5", "§6", "§7"]:
        if s not in secs:
            fails.append(f"{s}: section missing")
    if fails:
        return fails  # without the skeleton there is nothing to measure

    if len(paragraphs(secs["§0"])) < 5:
        fails.append(f"§0: {len(paragraphs(secs['§0']))} dense prose paragraphs (<5; "
                     "lists don't count)")
    if "scope" not in secs:
        fails.append("§Scope: section missing")
    elif not DISCLOSURE_RE.search(secs["scope"]):
        fails.append(
            "§Scope: missing the disclosure that the personas are simulated (R7). The dossier "
            "circulates and the '— **Name**' attribution reads like a real citation. Write in "
            "the §Scope: \"the advisors are lenses simulated by language models; they ARE NOT "
            "THE REAL PEOPLE, and no sentence attributed to them was said by them\".")

    subs1 = [(h, b) for h, b in subsections(secs["§1"]) if re.match(r"1\.\d", h)]
    if not subs1:
        fails.append("§1: no 1.N item")
    for h, b in subs1:
        item = h.split(" ")[0]
        if quotes(b) < 1:  # ratified floor: "1-2 attributed reference quotes"
            fails.append(f"§1 {item}: no attributed quote (ratified floor: ≥1)")
        if len(paragraphs(b)) < 2:
            fails.append(f"§1 {item}: {len(paragraphs(b))} prose paragraphs (<2)")

    for h, b in [(h, b) for h, b in subsections(secs["§2"]) if re.match(r"2\.\d", h)]:
        item = h.split(" ")[0]
        # CONDITIONAL fork (board converges; no 🐂/🐻 by contract): requires the EXPLICIT
        # "conditional fork" marker in the heading or the 1st block — a loose "conditional"
        # in the prose does NOT exempt (otherwise any mention bypasses the gate).
        head_zone = (h + "\n" + b.split("\n\n")[0]).lower()
        if "conditional fork" in head_zone:
            continue
        if "🐂" not in b or "🐻" not in b:
            fails.append(f"§2 {item}: contested fork without both essays 🐂/🐻 "
                         "(conditional? mark 'conditional fork' in the context)")
        if quotes(b) < 2:
            fails.append(f"§2 {item}: {quotes(b)} attributed quotes (<2 — minimum 1 per side)")
        low = b.lower()
        for field in ["why they diverge", "cost of being wrong", "what resolves"]:
            if field not in low:
                fails.append(f"§2 {item}: missing '{field}'")

    for h, b in [(h, b) for h, b in subsections(secs["§3"]) if re.match(r"3\.\d", h)]:
        item = h.split(" ")[0]
        low = b.lower()
        if "why it matters" not in low:
            fails.append(f"§3 {item}: missing 'why it matters'")
        if "testability" not in low:
            fails.append(f"§3 {item}: missing 'testability'")

    for h, b in [(h, b) for h, b in subsections(secs["§4"]) if re.match(r"4\.\d", h)]:
        item = h.split(" ")[0]
        anti = "anti-thesis" in h.lower()
        if not re.search(r'^\*["“].+["”]\*\s*$', b, re.MULTILINE):
            fails.append(f"§4 {item}: no epigraph in the lens's own voice (line *\"...\"*)")
        if not re.search(r"\*\*In one sentence", b):
            fails.append(f"§4 {item}: no verdict close in bold")
        if not anti:
            for field in ["**Questions:**", "**Suggestions:**", "**Strip:**"]:
                if field not in b:  # presence; "up to 5" is a ratified ceiling, not a floor
                    fails.append(f"§4 {item}: missing {field}")

    b6 = secs["§6"]
    for sub in ["6.5", "6.6"]:
        if not re.search(rf"^### {re.escape(sub)}", b6, re.MULTILINE):
            fails.append(f"§6: missing the '### {sub}' heading "
                         "(a loose substring like '6.5x' does not count)")
    m64 = re.search(r"### 6\.4(.*?)(?=### 6\.5|$)", b6, re.DOTALL)
    if not m64:
        fails.append("§6: missing 6.4 (ranked suggestions)")
    else:
        items = re.split(r"\n\*\*\d+\.", m64.group(1))[1:]
        if len(items) < 5:
            fails.append(f"§6.4: {len(items)} suggestions (<5)")
        for i, it in enumerate(items, 1):
            if len(it.strip()) < 400:
                fails.append(f"§6.4 suggestion {i}: {len(it.strip())} chars "
                             "(<400 — mechanism+how+owner/gate)")

    low7 = secs["§7"].lower()
    for field in ["discarded", "onesty", "drill-down"]:
        if field not in low7:
            fails.append(f"§7: missing '{field}'")

    # R8 — every ATTRIBUTED quote carries the marker on its very line
    missing_marker = []
    for s in ["§1", "§2", "§3", "§4", "§5", "§6"]:
        for ln in secs[s].splitlines():
            if ln.startswith(">") and ATTRIB_RE.search(ln) and not SIM_MARKER_RE.search(ln):
                missing_marker.append(f"{s}: {ln.strip()[:70]}")
    for x in missing_marker[:5]:
        fails.append(f"attributed quote missing '(simulated lens · <model>)' on the SAME line "
                     f"(R8 — the quote circulates cropped, without the §Scope) — {x}")

    body = "\n".join(secs[s] for s in ["§0", "§1", "§2", "§3", "§4", "§5", "§6"])
    body += "\n" + secs.get("scope", "")
    for pat, desc in JARGON_PATTERNS:
        hits = re.findall(rf"(?<![\w-]){pat}(?!\w)", body)
        if hits:
            uniq = sorted(set(hits))
            fails.append(f"internal jargon in the body (§0-§6): {desc} — {', '.join(uniq[:5])} "
                         f"×{len(hits)} — gloss in plain English or remove (R3)")
    return fails


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: render_gate.py <report.md>")
        return 2
    path = Path(sys.argv[1])
    if not path.exists():
        print(f"RENDER GATE RED: {path} does not exist")
        return 1
    fails = check(path.read_text())
    if fails:
        print(f"RENDER GATE RED — {len(fails)} failure(s):")
        for f in fails:
            print(f"  ✗ {f}")
        print("Fix and re-run. Delivering with a red gate = contract violation, "
              "not editorial judgment.")
        return 1
    print("RENDER GATE GREEN — structural floor ok "
          "(voice, nuance and quote fidelity are not measured here).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
