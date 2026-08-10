#!/usr/bin/env python3
"""format_gate.py — the gate that was missing: does the DELIVERED dossier have the ratified form?

Why it exists. Between July and August 2026 the renderer went from emitting the ratified format to
emitting 12 of its 53 classes. No test went red, no gate complained, and the regression surfaced
only when the decider read a dossier and said the older reference had been better. It had. The
structural gate measures DEPTH (paragraph floors, required sections) and the quote verifier
measures FIDELITY (verbatim against the raw card). Neither one can see FORM, so form rotted in
silence — the exact failure class this project refuses everywhere else.

Two mechanical checks:
  1. FORMAT COVERAGE — every `required` class in assets/format-inventory.json appears in the
     rendered HTML. Adding a component to the contract without emitting it now fails loudly.
  2. PROSE BAND — sentence length, em-dash density, paragraph length and per-UNIT size stay
     inside the band measured on the ratified exemplar.

Calibration rule, and it is load-bearing: **if the gate rejects the RATIFIED artifact, the gate is
wrong, not the artifact.** That rule caught two real bugs in this file (the last suggestion, and
the last item of a section, each swallowing the text that followed).

The cap lives on the UNIT (advisor, fork, suggestion), never on the section: §4 grows with the
number of lenses, and §6.4 has a contractual FLOOR of 400 characters per suggestion — capping the
section would have contradicted a floor that already existed.

Contract versioning: a dossier declaring `contract: 2` is held to the inventory. One without the
marker is contract 1 and is SKIPPED — rewriting a delivered dossier would destroy the provenance
of what was decided at the time.

Usage:
    python3 -m high_stakes.format_gate <report.md> <report.html>   # both checks
    python3 -m high_stakes.format_gate --prose <report.md>         # prose only, while writing
Exit 0 green, 1 red, 2 usage. Zero dependencies.
"""
from __future__ import annotations

import json
import re
import statistics
import sys
from pathlib import Path

from . import paths

INVENTORY_PATH = paths.ASSETS / "format-inventory.json"
NOT_PROSE = re.compile(r"^(\s*#|\s*>|\s*\||\s*[-*+]\s|\s*\d+\.\s|\s*<)")
# The marker is only honoured in the header: the first 5 lines, right after the H1. Matched
# anywhere with re.search, a stray `contract: 1` further down silently downgraded the document
# and switched the gate off.
CONTRACT_RE = re.compile(r"^contract:\s*(\d+)\s*$", re.M)
HEADER_LINES = 5
COMMENT_RE = re.compile(r"<!--.*?-->", re.S)


def inventory() -> dict:
    return json.loads(INVENTORY_PATH.read_text())


def contract_version(md: str) -> int:
    """Contract the dossier DECLARES, read only from the header.

    Absence used to mean 1, which meant "skip the gate" — so deleting one line disabled the
    whole thing, and the default state of any dossier that forgot the header was ungated. Both
    reviewers found it independently and both called it a merge blocker. Now absence means the
    CURRENT contract: the gate applies, and opting out requires writing `contract: 1` on
    purpose, where a reader can see it."""
    head = "\n".join(md.splitlines()[:HEADER_LINES])
    m = CONTRACT_RE.search(head)
    return int(m.group(1)) if m else inventory().get("contract_version", 2)


def content_region(html: str) -> str:
    """The HTML the AUTHOR produced, without the page chrome the renderer always emits.

    Counting the whole document made 13 of the required classes unfalsifiable: header, title
    block and the groundedness legend are hardcoded, so they were green on a document with one
    sentence and zero components. A check that cannot go red is decoration."""
    body = html.split("</header>", 1)[-1]
    body = re.sub(r'<div class="titleblock">.*?</div>\s*(?=<section)', "", body, flags=re.S)
    return COMMENT_RE.sub("", body)   # a comment listing every class must not vouch for it


def classes_in(html: str) -> set[str]:
    out: set[str] = set()
    for v in re.findall(r'class="([^"]+)"', COMMENT_RE.sub("", html)):
        out.update(v.split())
    return out


def check_coverage(html: str, inv: dict | None = None, md: str = "") -> list[str]:
    """Required classes must appear in the CONTENT region; conditional ones only when the
    markdown carries their trigger. A conditional fork omits bull/bear BY CONTRACT, so
    demanding them unconditionally is a guaranteed false red on a legitimate dossier."""
    inv = inv or inventory()
    have = classes_in(content_region(html))
    fails = []
    chrome = inv.get("chrome") or {}
    if chrome.get("classes"):
        missing = [c for c in chrome["classes"] if c not in classes_in(html)]
        if missing:
            fails.append(f"FORM · chrome: page furniture not emitted: {', '.join(missing)}")
    for group, cls in inv["required"].items():
        missing = [c for c in cls if c not in have]
        if missing:
            fails.append(f"FORM · {group}: ratified class(es) not emitted: {', '.join(missing)}")
    for group, spec in (inv.get("conditional") or {}).items():
        if group.startswith("_") or not isinstance(spec, dict):
            continue
        if spec["trigger"] not in md:
            continue
        missing = [c for c in spec["classes"] if c not in have]
        if missing:
            fails.append(f"FORM · {group} (triggered by '{spec['trigger']}'): "
                         f"not emitted: {', '.join(missing)}")
    return fails


def paragraphs(md: str) -> list[str]:
    ps, buf = [], []
    for ln in md.splitlines():
        if not ln.strip() or NOT_PROSE.match(ln):
            if buf:
                ps.append(" ".join(buf))
                buf = []
        else:
            buf.append(ln.strip())
    if buf:
        ps.append(" ".join(buf))
    return [p for p in ps if len(p) > 80]


def units(md: str) -> dict[str, tuple[str, int]]:
    """Words per UNIT, typed. A unit closes at the next `### ` AND at the next `## ` — without
    the second condition the last item of every section swallows the whole next section and the
    gate reports bloat that is not there."""
    out: dict[str, tuple[str, int]] = {}
    cur, buf, seen = None, [], 0

    def words(lines: list[str]) -> int:
        # Verbatim quotes are excluded from EVERY prose measurement, including this one. They
        # cannot be edited to satisfy a cap without breaking the quote verifier — and a single
        # long advisor quote was enough to blow the 550-word cap on a legitimate block.
        return len(" ".join(l for l in lines if not l.lstrip().startswith(">")).split())

    def kind(t: str) -> str:
        return "advisor" if t.startswith("4.") else "fork" if t.startswith("2.") else "item"

    for ln in md.splitlines():
        if ln.startswith("### ") or ln.startswith("## "):
            if cur:
                out[f"{seen}|{cur}"] = (kind(cur), words(buf))
            seen += 1
            cur, buf = (ln[4:80], []) if ln.startswith("### ") else (None, [])
        elif cur:
            buf.append(ln)
    if cur:
        out[f"{seen}|{cur}"] = (kind(cur), words(buf))

    # Each numbered Chairman suggestion is its own unit. The LAST one has no successor to bound
    # it: close it on the following heading, never on an arbitrary character count (that is what
    # made this gate reject the exemplar that calibrated it).
    # Only inside §6 — a numbered bold paragraph elsewhere is prose, not a ranked suggestion.
    six = md.find("## §6")
    scope = md[six:] if six >= 0 else ""
    marks = list(re.finditer(r"^\*\*(\d+)\.\s", scope, re.M))
    for i, m in enumerate(marks):
        if i + 1 < len(marks):
            end = marks[i + 1].start()
        else:
            nxt = re.search(r"^#{2,3} ", scope[m.start():], re.M)
            end = m.start() + (nxt.start() if nxt else len(scope) - m.start())
        # keyed by POSITION, not by the printed number: two "**1." in the document collided and
        # the oversized one was erased from the measurement by the small one.
        out[f"suggestion #{i + 1} ({m.group(1)})"] = (
            "suggestion", words(scope[m.start():end].splitlines()))
    return out


def check_prose(md: str, inv: dict | None = None) -> tuple[list[str], dict]:
    inv = inv or inventory()
    md = md.replace("\r\n", "\n")   # CRLF left the \r on quote lines and the exclusion never matched
    band, ref = inv["prosa"]["banda"], inv["prosa"]["referencia"]
    # Quotes are verbatim by contract and cannot be rewritten to satisfy style — they are
    # excluded from every prose measurement.
    quotes = set(re.findall(r"^>.*$", md, re.M))
    prose = "\n".join(l for l in md.splitlines() if l not in quotes)
    sents = [s for s in re.split(r"(?<=[.!?])\s+", prose) if len(s.split()) > 2]
    lens = [len(s.split()) for s in sents] or [0]
    mean_len = statistics.mean(lens)
    dash = 1000 * prose.count("—") / max(len(prose.split()), 1)
    long_paras = [p for p in paragraphs(prose) if len(p) > 900]
    caps = {"advisor": band["palavras_por_conselheiro_max"],
            "fork": band["palavras_por_fork_max"],
            "suggestion": band["palavras_por_sugestao_max"],
            "item": band.get("palavras_por_item_max", 10 ** 6)}
    oversized = {k: n for k, (t, n) in units(md).items() if n > caps[t]}

    fails = []
    if mean_len > band["palavras_por_frase_max"]:
        fails.append(f"PROSE · mean sentence {mean_len:.1f} words > cap "
                     f"{band['palavras_por_frase_max']} (exemplar: {ref['palavras_por_frase']})")
    if dash > band["travessoes_por_mil_max"]:
        fails.append(f"PROSE · {dash:.1f} em-dashes per 1000 words > cap "
                     f"{band['travessoes_por_mil_max']} (exemplar: {ref['travessoes_por_mil']})")
    if len(long_paras) > band["paragrafos_acima_900c_max"]:
        fails.append(f"PROSE · {len(long_paras)} paragraph(s) over 900 characters "
                     f"(exemplar: {ref['paragrafos_acima_900c']})")
    for k, n in list(oversized.items())[:5]:
        fails.append(f"PROSE · '{k}' has {n} words (unit cap exceeded)")
    profile = {"words": len(md.split()), "mean_sentence": round(mean_len, 1),
               "dashes_per_1k": round(dash, 1), "long_paragraphs": len(long_paras),
               "units_over_cap": len(oversized)}
    return fails, profile


def check(md: str, html: str | None = None) -> list[str]:
    """Public entry point. Returns the list of failures (empty = green)."""
    inv = inventory()
    if contract_version(md) < inv.get("contract_version", 2):
        return []  # frozen dossier from an earlier contract: not held to this inventory
    fails, _ = check_prose(md, inv)
    if html is not None:
        fails = check_coverage(html, inv, md) + fails
    return fails


def main() -> int:
    args = sys.argv[1:]
    if args and args[0] == "--prose" and len(args) == 2:
        md, html = Path(args[1]).read_text(), None
    elif len(args) == 2:
        md, html = Path(args[0]).read_text(), Path(args[1]).read_text()
    else:
        print("usage: format_gate.py <report.md> <report.html>  |  --prose <report.md>")
        return 2

    inv = inventory()
    ver = contract_version(md)
    fails, profile = check_prose(md, inv)
    if html is not None:
        fails = check_coverage(html, inv, md) + fails
    print(f"profile: {profile['words']} words · sentence {profile['mean_sentence']} · "
          f"em-dash {profile['dashes_per_1k']}/1k · long paragraphs "
          f"{profile['long_paragraphs']} · units over cap {profile['units_over_cap']}")
    if ver < inv.get("contract_version", 2):
        print(f"FORMAT GATE SKIPPED — dossier declares contract {ver}; this inventory is "
              f"contract {inv.get('contract_version', 2)}. Delivered dossiers are frozen, not "
              "rewritten.")
        return 0
    if fails:
        print(f"\nFORMAT GATE RED — {len(fails)} problem(s):")
        for f in fails:
            print(f"  ✗ {f}")
        print("Fix and re-run. The ratified format is the floor, not a suggestion.")
        return 1
    print("FORMAT GATE GREEN — ratified form intact, prose inside the exemplar's band.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
