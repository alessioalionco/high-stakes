#!/usr/bin/env python3
"""test_qverify.py — executable suite for quote verification (project convention: PASS/exit≠0).

Includes the 6 regressions from the 21/Jul review (all were false-GREEN routes confirmed
by execution: gluing-across-fields, short fabricated tail after ellipsis, splice across
cells/out of order, internal em-dash+bold, accented role heading, missing/broken epigraph)."""
import json
import shutil
import sys
import tempfile
from pathlib import Path

from high_stakes.qverify import _advisor_for, verify

CELL_UNIT ECONOMIST = {
    "advisor": "unit economist", "status": "ok",
    "result": {
        "verdict_prose": ("Do not confuse reclassification with growth, consumption with "
                          "gross profit or pipeline with forecast — the burden of proof "
                          "is on the deck."),
        "items": [{"title": "The bridge needs numbers",
                   "analysis": ("In the token economy, revenue may be mere compute resale; "
                                "the correct analysis starts with gross profit, not ARR."),
                   "falsifier": "cohort proving margin"}],
        "dud_flags": {"comment": "I would cut E4 as proposed."},
        "questions_to_founder": ["What is the global forecast coverage?"],
    },
}
CELL_UNIT ECONOMIST2 = {
    "advisor": "unit economist", "status": "ok",
    "result": {"verdict_prose": "The market rewards margin, not empty category promise.",
               "items": [], "dud_flags": {}, "questions_to_founder": []},
}
CELL_MODEL_THEORIST = {
    "advisor": "model theorist", "status": "ok",
    "result": {"verdict_prose": "The as-is tries to claim credit as an AI-native company.",
               "items": [], "dud_flags": {}, "questions_to_founder": [],
               "stances": {"conditions": "Exclusive condition of a new cell schema."}},
}
REFUTER = {"cell_id": "refuter_gemini", "role": "refuter",
           "text": "The complexity of the material demands the founder's voice guiding the narrative."}


def refuter_contract_ok() -> bool:
    """Cross-module REGRESSION (A1): the cell that xverify PRODUCES must be recognized by
    qverify as the refuter's, and its corpus must come from the real schema (`result.*`).

    The original bug had BOTH ends broken and no test crossed them: xverify wrote
    `refute_*` while qverify looks for `refuter*` (silent miss), and — with only the
    prefix fixed — the corpus would come from the flat `text` field, which these cells
    don't have, hence EMPTY: false RED on every refuter quote."""
    from high_stakes.cells import cell_filename
    from high_stakes.qverify import cell_corpus
    from high_stakes.xverify import build_refute_tasks

    tmp = Path(tempfile.mkdtemp())
    try:
        cid = build_refute_tasks("MATERIAL", {"i1": "claim one"})[0]["cell_id"]
        d = tmp / "cells"
        d.mkdir()
        # the format run_cells persists (cells.py:173) with the xverify schema
        (d / cell_filename(cid)).write_text(json.dumps({
            "cell_id": cid, "status": "ok",
            "result": {"case_against": "The Q4 bridge does not hold without a cohort.",
                       "what_survives": "The expansion signal is real.",
                       "suggested_verdict": "WEAKENED"},
        }, ensure_ascii=False))
        corpus = cell_corpus(d)
        return ("refuter" in corpus
                and any("q4 bridge does not hold" in c for c in corpus["refuter"]))
    finally:
        shutil.rmtree(tmp)


def make_cells(tmp: Path) -> Path:
    d = tmp / "cells"
    d.mkdir()
    (d / "cell_unit_economist_sol.json").write_text(json.dumps(CELL_UNIT ECONOMIST, ensure_ascii=False))
    (d / "cell_unit_economist_glm.json").write_text(json.dumps(CELL_UNIT ECONOMIST2, ensure_ascii=False))
    (d / "cell_model_theorist_glm.json").write_text(json.dumps(CELL_MODEL_THEORIST, ensure_ascii=False))
    (d / "refuter_gemini.json").write_text(json.dumps(REFUTER, ensure_ascii=False))
    return d


REPORT = """# Test
## §1 Convergents
### 1.1 Item
> "In the token economy, revenue may be mere compute resale; the correct analysis starts
> with gross profit, not ARR." — **The Unit Economist** (simulated lens · GPT-5.6 Sol)

> "DO NOT CONFUSE reclassification with growth…   the burden of proof is on the deck." — **The Unit Economist**

> "A completely fabricated quote that is not in any card of the panel." — **The Unit Economist**

> "The as-is tries to claim credit as an AI-native company." — **The Unit Economist** (via GLM-5.2)

> "The complexity of the material demands the founder's voice guiding the narrative." — **Refuter**

> "is on the deck. The bridge needs numbers" — **The Unit Economist**

> "compute resale … it is all garbage" — **The Unit Economist**

> "The market rewards margin, not empty … the burden of proof is on the deck" — **The Unit Economist**

> "gross profit, not ARR … In the token economy" — **The Unit Economist**

> "The risk — **churn** — is what kills the retention thesis" — **The Unit Economist**

> "Exclusive condition of a new cell schema." — **The Model Theorist**

## §4 Board
### 4.1 The Unit Economist — lens
*"I would cut E4 as proposed."*

Opinion.

### 4.2 Antithesis — premise
*"The as-is tries to claim credit
as an AI-native company."*

Opinion with an epigraph BROKEN across two lines (and the wrong advisor on purpose? no — model theorist).

### 4.3 The Model Theorist — lens
Opinion with NO epigraph at all.
"""


def main() -> int:
    tmp = Path(tempfile.mkdtemp())
    try:
        cells = make_cells(tmp)
        f = verify(REPORT, cells)

        def find(sub, kind="quote"):
            for x in f:
                if x["type"] == kind and sub.lower() in x["quote"].lower():
                    return x
            return None

        def case(name, cond):
            print(("PASS" if cond else "FAIL"), name)
            return cond

        results = [
            case("multi-line verbatim verifies",
                 find("In the token economy")["status"] == "verified"),
            case("normalization (case/…/whitespace, in order) verifies",
                 find("DO NOT CONFUSE")["status"] == "verified"),
            case("fabricated fails", find("fabricated")["status"] == "unverified"),
            case("The Model Theorist's quote attributed to The Unit Economist = divergent",
                 find("claim credit as")["status"] == "divergent_attribution"),
            case("refuter (flat text field) verifies",
                 find("complexity of the material")["status"] == "verified"),
            case("REGRESSION: gluing across fields fails",
                 find("on the deck. The bridge")["status"] == "unverified"),
            case("REGRESSION: short fabricated tail after ellipsis fails",
                 find("all garbage")["status"] == "unverified"),
            case("REGRESSION: splice across cells fails",
                 find("market rewards margin")["status"] == "unverified"),
            case("REGRESSION: out-of-order segments fail",
                 find("gross profit, not ARR …")["status"] == "unverified"),
            case("REGRESSION: internal em-dash+bold does not become attribution (and fails)",
                 find("churn") is not None and find("churn")["status"] == "unverified"),
            case("REGRESSION: recursive corpus covers a new-schema field",
                 find("new cell schema")["status"] == "verified"),
            case("verbatim epigraph verifies",
                 find("I would cut E4", "epigraph")["status"] == "verified"),
            case("REGRESSION: 'Antithesis' resolves the role (broken epigraph extracted; "
                 "match on model theorist = divergent)",
                 find("credit", "epigraph") is not None
                 and find("credit", "epigraph")["status"] == "divergent_attribution"),
            case("REGRESSION: §4 with no epigraph = FAILURE (not a skip)",
                 find("4.3", "epigraph") is not None
                 and find("4.3", "epigraph")["status"] == "missing_epigraph"),
            case("REGRESSION A1: xverify's cell is recognized as the refuter's and has a corpus",
                 refuter_contract_ok()),
            # REGRESSION: the render gate counts as attributed any line with "— **Name**";
            # strict parsing requires end of line. The difference made the quote VANISH
            # from the verifier, which then printed GREEN without having checked it. Found
            # in a real dossier: 18 attributed lines, 17 extracted, 1 invisible.
            case("REGRESSION: an attribution the gate counts and the parser misses becomes "
                 "malformed_attribution (does not vanish)",
                 any(f["status"] == "malformed_attribution" for f in verify(
                     '## §1 x\n### 1.1 y\n> "A quote with a broken parenthesis." '
                     '— **The Unit Economist** (via Gemini 3.1\n', cells))),
            case("REGRESSION: a lens OUTSIDE the old fixed list resolves via the corpus "
                 "(the embedded pool has 13, the list had 7)",
                 _advisor_for("The Movement Builder", ["movement builder", "unit economist"]) == "movement builder"),
            case("role still beats the name inside the heading",
                 _advisor_for("Anti-thesis of The Unit Economist", ["unit economist"]) == "antithesis"),
            # REGRESSION: an attribution in PROSE was invisible to BOTH gates (both
            # required startswith('>')), so a fabricated quote outside a blockquote passed
            # as long as any legitimate quote kept `findings` non-empty.
            case("REGRESSION: an attribution OUTSIDE a blockquote is flagged",
                 any(f["status"] == "attribution_outside_quote" for f in verify(
                     '## §1 x\n### 1.1 y\nLoose text — **The Unit Economist** (simulated lens · X)\n',
                     cells))),
            # REGRESSION: a TWO-line quote with internal bold had its 1st line accused of
            # being malformed and the SAME quote right below as verified — contradictory red.
            case("REGRESSION: internal bold in a multi-line quote does NOT become malformed",
                 not any(f["status"] == "malformed_attribution" for f in verify(
                     '## §1 x\n### 1.1 y\n> "He said the **burden of proof** is on the deck\n'
                     '> and nobody objected." — **The Unit Economist** (simulated lens · X)\n', cells))),
        ]
        # WARNING: `results` above is a LITERAL LIST. A loose `case(...)` after it prints
        # PASS/FAIL and does NOT enter the count nor the exit code. Use results.append(...).

        # ---- W1: the per-BLOCK gate washes the malformed attribution ----
        # `_malformed_attributions` decides per whole block: if ANY line of the block has
        # a strict attribution, the block passes — and a second, malformed attribution in
        # the same block vanishes. It is fail-open in a gate whose job is to keep an
        # invented sentence from going out with a real person's name on it. A blockquote
        # can contain several quotes: each one must be judged on its own.
        mixed_block = ('> a legitimate sentence here\n'
                       '> — **The Unit Economist** (simulated lens · Sol)\n'
                       '> another sentence, attributed in a malformed way — **Somebody** mid-line\n')
        results.append(case(
            "W1: a malformed attribution is NOT washed by a valid one in the same block",
            any(f["status"] == "malformed_attribution"
                for f in verify(mixed_block, cells))))
        # and the legitimate case that motivated the per-block gate must not flag again
        results.append(case(
            "W1b: internal bold in a multi-line quote is still NOT malformed",
            not any(f["status"] == "malformed_attribution" for f in verify(
                '> "He said the **burden of proof** is on the deck\n'
                '> and nobody objected." — **The Unit Economist** (simulated lens · X)\n', cells))))

        # ---- W2: false reds that teach the user to ignore the gate ----
        # A gate that flags correct text red is worse than no gate: the user learns to
        # walk past it, and then the real red walks past too.
        results.append(case(
            "W2a: common prose emphasis does not become an attribution",
            not verify("The team discussed — **at length** — the quarter's roadmap.\n", cells)))
        results.append(case(
            "W2b: em-dash + bold mid-sentence in prose does not become an attribution",
            not verify("The bar — **our own bar** — moved mid-quarter.\n",
                       cells)))
        # an indented blockquote is valid markdown (up to 3 spaces); today it became "prose"
        indented = ('  > In the token economy, the marginal cost of rigor fell.\n'
                    '  > — **The Unit Economist** (simulated lens · X)\n')
        results.append(case(
            "W2c: an indented blockquote is treated as a blockquote, not as prose",
            not any(f["status"] == "attribution_outside_quote"
                    for f in verify(indented, cells))))
        # lazy continuation: a line without '>' inside the block continues the quote (CommonMark)
        lazy = ('> In the token economy, the marginal cost\n'
                'of rigor fell.\n'
                '> — **The Unit Economist** (simulated lens · X)\n')
        results.append(case(
            "W2d: lazy continuation does not split the quote into a piece too short",
            not any(f["status"] == "too_short_to_verify" for f in verify(lazy, cells))))

        # ===== findings from the MUTATION AUDIT (lines no test covered) =====
        # The auditor breaks the code one line at a time and runs the 11 suites. A
        # mutation that SURVIVES = a line with no test. These four survived; three were
        # a real gap.

        # M1 (qverify.py, `if not segs`) — §4 calls `_match` WITHOUT the MIN_QUOTE cutoff
        # that quotes have. An epigraph that normalizes to nothing has empty segments, and
        # `_in_one_cell_ordered([], ...)` walks zero segments, never breaks, and returns
        # True: the epigraph comes out VERIFIED. Fail-open on the path nobody looked at.
        empty_epigraph = ('## §4 x\n### 4.1 The Unit Economist\n*"..."*\n')
        results.append(case(
            "M1: an epigraph that normalizes to nothing does NOT come out verified",
            all(f["status"] != "verified" for f in verify(empty_epigraph, cells))))

        # M2 (qverify.py, the "empty green" guard) — this guard was written ON PURPOSE
        # against a false green: "GREEN — 0/0" on a dossier that HAS attributions means
        # the verifier understood none of them, not that they are all correct. It never
        # had a test — an anti-false-green guard that was itself unverified.
        import io, contextlib
        from high_stakes import qverify as _qv

        def run_cli(md_text):
            rep = tmp / "cli.md"
            rep.write_text(md_text, encoding="utf-8")
            buf = io.StringIO()
            argv = sys.argv
            sys.argv = ["qverify.py", str(rep), str(cells)]
            try:
                with contextlib.redirect_stdout(buf):
                    rc = _qv.main()
            finally:
                sys.argv = argv
            return rc, buf.getvalue()

        rc_empty, out_empty = run_cli(
            'Prose with a wrongly-shaped attribution: — **The Unit Economist** said it.\n')
        results.append(case(
            "M2: a dossier WITH attributions and ZERO extracted is RED (empty green is false)",
            rc_empty != 0 and "RED" in out_empty))

        # M3 (qverify.py, CLI path validation) — the CLI is what the user actually runs
        # (`high-stakes qverify report.md cells/`) and it had no test at all.
        argv = sys.argv
        sys.argv = ["qverify.py", str(tmp / "does-not-exist.md"), str(cells)]
        try:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc_missing = _qv.main()
        finally:
            sys.argv = argv
        results.append(case("M3: CLI with a missing report exits RED, does not crash",
                            rc_missing == 1 and "RED" in buf.getvalue()))

        print(f"{sum(results)}/{len(results)} tests ok")
        return 0 if all(results) else 1
    finally:
        shutil.rmtree(tmp)


if __name__ == "__main__":
    sys.exit(main())
