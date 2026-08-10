#!/usr/bin/env python3
"""test_format_gate.py — executable suite for the format gate (project convention: PASS/exit≠0).

The gate exists because form rotted in silence: the renderer went from the ratified format to 12
of its 53 classes with no test going red. These cases lock the two properties that make the gate
worth having.

  1. It must PASS the ratified exemplar. The calibration rule is explicit in the module: if the
     gate rejects the ratified artifact, the gate is wrong, not the artifact. Two real bugs were
     caught by that rule — the last suggestion and the last item of a section, each swallowing
     the text that followed and inflating a unit past its cap.
  2. It must FAIL a dossier that lost the form. A gate that only ever prints green is decoration.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

from high_stakes.format_gate import (check, check_coverage, check_prose, contract_version,
                                     inventory, units)

ROOT = Path(__file__).resolve().parents[1]
SAMPLE_MD = ROOT / "examples" / "sample-dossier.md"
SAMPLE_HTML = ROOT / "examples" / "sample-dossier.html"
GATE = [sys.executable, "-m", "high_stakes.format_gate"]

BLOATED = """# Case
contract: 2

## §0 Summary
""" + ("A sentence that runs on and on and on with many words indeed — and another clause — and "
       "yet another clause that keeps going well past any reasonable length for a single "
       "sentence in a document meant to be read by a busy human being who has other things. " * 6)


def main() -> int:
    results: list[bool] = []

    def case(name, cond):
        print(("PASS " if cond else "FAIL ") + name)
        results.append(bool(cond))

    inv = inventory()

    # ---- 1. the ratified exemplar must pass ----
    md, html = SAMPLE_MD.read_text(), SAMPLE_HTML.read_text()
    case("the ratified exemplar declares the current contract",
         contract_version(md) == inv["contract_version"])
    case("CALIBRATION RULE: the ratified exemplar passes the gate that was calibrated on it "
         "(if this goes red, the gate is wrong, not the exemplar)", check(md, html) == [])

    # ---- 2. a dossier that lost the form must fail ----
    stripped = html
    for cls in ("fork", "advisor", "camp", "pesobar", "scorestrip", "chip", "fifteen"):
        stripped = stripped.replace(f'class="{cls}"', 'class="x"')
    fails = check_coverage(stripped, inv, md)
    case("a render that stopped emitting fork cards / advisor blocks / camps is caught",
         len(fails) >= 3)

    prose_fails, profile = check_prose(BLOATED, inv)
    case("bloated prose (long sentences + em-dash pile-up) is caught",
         any("mean sentence" in f for f in prose_fails)
         and any("em-dash" in f for f in prose_fails))

    # ---- 3. the unit-boundary bugs the calibration rule caught ----
    u = units("### 4.1 A lens\nword\n## §5 Next section\n" + "filler " * 400)
    case("REGRESSION: the LAST item of a section closes at the next `## ` — it used to swallow "
         "the whole following section and report bloat that was not there",
         all(n < 50 for k, (_, n) in u.items() if k.endswith("4.1 A lens")))

    md_last = ("## §6 Synthesis\n\n**1. First.** body\n\n**2. Last one.** short body\n\n"
               "## §7 Appendix\n" + "x " * 500)
    u2 = units(md_last)
    last = [n for k, (_, n) in u2.items() if k.startswith("suggestion #2")]
    case("REGRESSION: the LAST numbered suggestion closes at the next heading, not at an "
         "arbitrary character count (that is what made the gate reject its own exemplar)",
         last and last[0] < 30)

    # ---- 4. contract versioning: absence must FAIL CLOSED ----
    # Deleting one line used to switch the whole gate off, so the default state of any dossier
    # that forgot the header was ungated. Both reviewers called it a merge blocker.
    no_marker = md.replace("contract: 2\n", "", 1)
    case("REGRESSION: a dossier with NO contract marker is still judged (absence fails closed)",
         contract_version(no_marker) == inv["contract_version"])
    case("opting out is explicit and visible: `contract: 1` in the header skips the gate",
         check("# T\ncontract: 1\n\n## §0 x\n", "<html></html>") == [])
    case("the marker is only honoured in the HEADER — a stray `contract: 1` further down "
         "cannot downgrade the document", contract_version(md + "\n\ncontract: 1\n") == 2)

    # ---- 4b. the checks the reviewers proved were spoofable ----
    empty = ('<header class="top"><div class="brand"></div></header><div class="wrap">'
             '<div class="titleblock"><div class="kicker"></div><p class="sub"></p>'
             '<div class="meta"></div></div><section><p>one sentence</p></section></div>')
    case("REGRESSION: a document with chrome but ZERO components is RED "
         "(chrome used to vouch for content)", len(check_coverage(empty, inv, md)) >= 4)
    spoof = empty + "<!-- " + " ".join(f'class="{c}"' for c in
            ["exec", "fork", "hd", "body", "foot", "advisor", "role", "qa", "reco"]) + " -->"
    case("REGRESSION: an HTML comment listing every class does not buy green",
         len(check_coverage(spoof, inv, md)) >= 4)
    conditional_only = md.replace("🐂", "X").replace("🐻", "Y")
    case("REGRESSION: a dossier whose forks are all CONDITIONAL is not failed for missing "
         "bull/bear — the contract says a conditional fork omits them",
         not any("contested_fork" in f for f in check_coverage(html, inv, conditional_only)))
    dup = "## §6 S\n\n**1. " + "w " * 300 + "**\n\n**1. short.** ok\n"
    case("REGRESSION: two suggestions numbered '1.' are both measured "
         "(the small one used to erase the oversized one)",
         len([k for k in units(dup) if "suggestion" in k]) == 2)
    quoted = ("### 4.1 Lens\n\n> " + "word " * 600
              + "— **X** (simulated lens · M)\n\nshort prose.\n")
    case("REGRESSION: a long verbatim quote does not blow the advisor cap — quotes are "
         "excluded from EVERY prose measurement, as the docstring claims",
         [v for k, v in units(quoted).items() if k.endswith("4.1 Lens")][0][1] < 50)

    # ---- 5. quotes are excluded from the prose measurement ----
    with_quote = ("# T\ncontract: 2\n\n## §0 S\n> "
                  + "a very long verbatim quote — with em-dashes — that cannot be rewritten " * 8
                  + '— **A Lens** (simulated lens · X)\n')
    qf, _ = check_prose(with_quote, inv)
    case("verbatim quotes are excluded from the prose band (they cannot be edited to satisfy "
         "style without breaking the quote verifier)", not any("em-dash" in f for f in qf))

    # ---- 6. CLI contract ----
    tmp = Path(tempfile.mkdtemp())
    try:
        bad = tmp / "bad.md"
        bad.write_text(BLOATED)
        badhtml = tmp / "bad.html"
        badhtml.write_text("<html></html>")
        ok0 = subprocess.run(GATE + [str(SAMPLE_MD), str(SAMPLE_HTML)], cwd=ROOT,
                             capture_output=True).returncode == 0
        ok1 = subprocess.run(GATE + [str(bad), str(badhtml)], cwd=ROOT,
                             capture_output=True).returncode == 1
        ok2 = subprocess.run(GATE, cwd=ROOT, capture_output=True).returncode == 2
        case(f"CLI exit codes (0 green / 1 red / 2 usage) = ({ok0}/{ok1}/{ok2})",
             ok0 and ok1 and ok2)
    finally:
        __import__("shutil").rmtree(tmp, ignore_errors=True)

    print(f"{sum(results)}/{len(results)} tests ok")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
