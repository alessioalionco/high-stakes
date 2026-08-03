#!/usr/bin/env python3
"""test_render_gate.py — executable suite for the render gate (project convention: PASS/exit≠0).

Uses the check(md) API directly (reentrant); 1 case via CLI covers the exit codes. Includes
regressions from the 20/Jul review findings (substring false negatives, jargon by family,
adjacent quotes, lists as prose, '6.5x' vs the 6.5 heading).
"""
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from high_stakes.render_gate import check

ROOT = Path(__file__).resolve().parents[1]
# Invocation via `-m` is the package CONTRACT (relative imports): running the file standalone
# must fail, and that is what the last case in this test verifies.
GATE = [sys.executable, "-m", "high_stakes.render_gate"]

PARAGRAPH = ("Dense prose paragraph with enough facts to count as a block of real analysis in the "
        "dossier, with mechanism and number, written for the decision-maker in clear, direct words.")
Q = ('> "Verbatim quote from a card with enough content." — **The Unit Economist** '
     '(simulated lens · GPT-5.6 Sol)')
Q2 = '> "Second verbatim quote, another lens." — **The Model Theorist** (simulated lens · Kimi K3)'
SUG = ("**1. Detailed suggestion.** 🚩 Problem described with the damage mechanism and enough "
       "context for the decision-maker to understand what breaks and for whom, without leaning "
       "on internal engineering jargon. ✅ How to execute in concrete steps, with a named owner "
       "and an explicit gate for when it is done, plus the source on the map. Owner: you. "
       "Source: test item with enough characters to clear the four-hundred-character floor of "
       "the contract ratified by the decision-maker in July, guaranteeing minimum depth that is "
       "verifiable by code.")

GOOD = f"""# Test dossier
{PARAGRAPH}

## §0 Executive summary
{PARAGRAPH}

{PARAGRAPH}

{PARAGRAPH}

{PARAGRAPH}

{PARAGRAPH}

## §Scope of the exercise
The lenses are simulated by models; they are not the real people.
{PARAGRAPH}

## §1 Convergent points
### 1.1 Convergent item
{PARAGRAPH}

{Q}

{PARAGRAPH}

## §2 Forks
### 2.1 Contested fork
{PARAGRAPH}

**🐂 Thesis: side A.** {PARAGRAPH}

{Q}

**🐻 Anti-thesis: side B.** {PARAGRAPH}

{Q2}

**Why they diverge:** different yardsticks. **Cost of being wrong per side:** high. **What resolves:** data.

### 2.2 Valuation anchor
**Context.** Conditional fork — the jury converges; the branch lives in the world. Precondition and
trigger described here.

## §3 Unique views
### 3.1 Unique item
{PARAGRAPH}

**Why it matters:** changes the decision. **Testability:** immediate.

## §4 The board
### 4.1 The Unit Economist — lens
*"Aphoristic verbatim epigraph from the card."*

{PARAGRAPH}

**Questions:** (1) a? (2) b? (3) c?
**Suggestions:** x · y · z.
**Strip:** 1/2/3 → 4/5/6.
**In one sentence: the lens's verdict.**

### 4.2 Anti-thesis — premise
*"Epigraph of the anti-thesis."*

{PARAGRAPH}

**In one sentence: the question is a different one.**

## §5 Investigation agenda
{PARAGRAPH}

## §6 Chairman synthesis
### 6.1 Convergences
{PARAGRAPH}

### 6.4 Suggestions
{SUG}

{SUG.replace('**1.', '**2.')}

{SUG.replace('**1.', '**3.')}

{SUG.replace('**1.', '**4.')}

{SUG.replace('**1.', '**5.')}

### 6.5 Questions
**1.** Question with its why.

### 6.6 Guardrails
| Guardrail | Trigger | Action |
|---|---|---|
| a | b | c |

## §7 Appendix
**7.1 Discarded** — item and why. **7.2 Method honesty** — noise floor not measured.
**7.3 Drill-down** — cards in cells/.
"""


def expect(name: str, md: str, want_fail: str | None) -> bool:
    fails = check(md)
    if want_fail is None:
        ok = not fails
        why = "" if ok else f" gate said: {fails}"
    else:
        ok = any(want_fail in f for f in fails)
        why = "" if ok else f" expected a failure containing '{want_fail}'; failures: {fails[:4]}"
    print(("PASS" if ok else "FAIL"), name + why)
    return ok


def expect_cli() -> bool:
    """Coverage of the exit-code contract via CLI (1 case; clean temp)."""
    fd, p = tempfile.mkstemp(suffix=".md")
    try:
        Path(p).write_text(GOOD)
        ok0 = subprocess.run(GATE + [p], cwd=ROOT).returncode == 0
        ok1 = subprocess.run(GATE + [p + ".nope"], cwd=ROOT,
                             capture_output=True).returncode == 1
        ok2 = subprocess.run(GATE, cwd=ROOT, capture_output=True).returncode == 2
        # T2: a module WITH relative imports does not run as a standalone file — only via `-m`.
        # (render_gate is self-contained, so the target here is render_dossier.)
        standalone = subprocess.run([sys.executable, str(ROOT / "high_stakes" / "render_dossier.py")],
                                    cwd=ROOT, capture_output=True)
        ok3 = standalone.returncode != 0 and b"relative import" in standalone.stderr
        ok = ok0 and ok1 and ok2 and ok3
        print(("PASS" if ok else "FAIL"),
              f"CLI via -m: exit codes (0/1/2) = ({ok0}/{ok1}/{ok2})")
        print(("PASS" if ok3 else "FAIL"),
              "T2: a module with relative imports only runs via -m (standalone file fails)")
        return ok
    finally:
        os.close(fd)
        os.unlink(p)


def main() -> int:
    results = [
        expect("complete doc passes", GOOD, None),
        expect("check is reentrant (2nd call clean)", GOOD, None),
        expect("missing section fails", GOOD.replace("## §7 Appendix", "## Appendix"), "§7"),
        # R8 — the marker has to travel WITH the attribution. The quote leaves the dossier
        # cropped (slide, screenshot) and the §Scope does not go along; without the marker, what
        # remains is a real-looking citation attributed to someone who exists.
        expect("R8: attribution without the simulation marker FAILS",
               GOOD.replace(" (simulated lens · GPT-5.6 Sol)", ""), "missing '(simulated lens"),
        expect("R8: the old '(via <model>)' format does NOT satisfy — 'via' identifies the "
               "model, it does not warn that the persona is simulated",
               GOOD.replace("(simulated lens · GPT-5.6 Sol)", "(via GPT-5.6 Sol)"),
               "missing '(simulated lens"),
        expect("R8: marker present passes", GOOD, None),
        # R7 — the dossier circulates and the "— **Name**" attribution looks like a real
        # citation. Without the disclosure, a verbatim guarantee about the CELL is delivered as
        # if it were about the PERSON. It is the rule the synthetic example motivated.
        expect("R7: §Scope without the simulated-persona disclosure FAILS",
               GOOD.replace("The lenses are simulated by models; they are not the real people.\n", "", 1),
               "personas are simulated"),
        expect("R7: disclosure wrapped across two lines is accepted (real trap from the debut)",
               GOOD.replace("The lenses are simulated by models; they are not the real people.",
                            "The lenses are simulated by models; they are not the\nreal people."), None),
        expect("R7: uppercase variant is accepted",
               GOOD.replace("The lenses are simulated by models; they are not the real people.",
                            "The advisors ARE NOT THE REAL PEOPLE; every line is model-simulated."), None),
        expect("R7: a vague sentence about 'simulation' is NOT enough (the marker is explicit)",
               GOOD.replace("The lenses are simulated by models; they are not the real people.",
                            "The lenses are an approximate simulation of the advisors."),
               "personas are simulated"),
        expect("shallow §0 fails",
               GOOD.replace(f"{PARAGRAPH}\n\n{PARAGRAPH}\n\n{PARAGRAPH}\n\n{PARAGRAPH}\n\n{PARAGRAPH}\n\n## §Scope",
                            f"{PARAGRAPH}\n\n## §Scope", 1), "§0"),
        expect("§0 made of numbered lists fails (list ≠ prose)",
               GOOD.replace(f"## §0 Executive summary\n{PARAGRAPH}",
                            f"## §0 Executive summary\n1. {PARAGRAPH}", 1), "§0"),
        expect("convergent point without a quote fails", GOOD.replace(f"{Q}\n\n{PARAGRAPH}\n\n## §2", f"{PARAGRAPH}\n\n## §2", 1),
               "no attributed quote"),
        expect("1 attributed quote is ENOUGH (ratified floor)", GOOD, None),
        expect("adjacent quotes count separately (2.1 with Q glued to Q2 still ok)",
               GOOD.replace(f"{Q}\n\n**🐻", f"{Q}\n{Q2}\n\n**🐻", 1), None),
        expect("a heading with 'Reinforce' is NOT exempt from quotes",
               GOOD.replace("### 1.1 Convergent item", "### 1.1 Reinforce the budget")
                   .replace(f"{Q}\n\n{PARAGRAPH}\n\n## §2", f"{PARAGRAPH}\n\n## §2", 1),
               "no attributed quote"),
        expect("fork without a bear fails", GOOD.replace("**🐻 Anti-thesis: side B.**", "", 1), "🐂/🐻"),
        expect("a loose 'conditional' in the prose does NOT exempt the fork",
               GOOD.replace("**🐂 Thesis: side A.**",
                            "Approval is conditional on the DD.\n\n**🐂 Thesis: side A.**", 1)
                   .replace("**🐻 Anti-thesis: side B.** " + PARAGRAPH, "", 1), "🐂/🐻"),
        expect("an explicit 'Conditional fork' exempts (2.2 of GOOD)", GOOD, None),
        expect("unique view without testability fails",
               GOOD.replace("**Testability:** immediate.", ""), "testability"),
        expect("advisor without an epigraph fails",
               GOOD.replace('*"Aphoristic verbatim epigraph from the card."*', ""), "epigraph"),
        expect("short suggestion fails",
               GOOD.replace(SUG.replace('**1.', '**5.'), "**5. Short.** Nothing more."), "6.4 suggestion"),
        expect("'6.5x' in the text does not satisfy the 6.5 heading",
               GOOD.replace("### 6.5 Questions\n**1.** Question with its why.",
                            "a multiple of 6.5x EV/ARR and see 6.6 later."), "### 6.5"),
        expect("jargon by FAMILY fails (X-LK3, not literally listed)",
               GOOD.replace("changes the decision.", "changes the decision (X-LK3)."), "X-LK3"),
        expect("EV7 jargon fails (EV\\d family)",
               GOOD.replace("changes the decision.", "changes the decision (EV7)."), "EV7"),
        expect("editions E1-E6 and forks F1..Fn are allowed",
               GOOD.replace("changes the decision.", "changes the decision (E4 and fork F8)."), None),
        expect("jargon in §7 is allowed",
               GOOD.replace("noise floor not measured",
                            "noise floor not measured; X-B3 and B-qverify"), None),
        expect_cli(),
    ]
    # ===== findings of the MUTATION AUDIT: gate checks without a test =====
    # Four gate conditions could be DELETED without any suite going red.
    # It is the worst class of gap a gate can have: it fails the wrong document and
    # nobody notices when it stops failing — the gate becomes decoration and the dossier ships.
    results += [
        expect("§1 with no 1.N item fails",
               re.sub(r"### 1\.\d[^\n]*", "### A block without a number", GOOD),
               "§1"),
        expect("§4 without the verdict close in bold fails",
               GOOD.replace("**In one sentence", "**Summing up"),
               "verdict close"),
        expect("§6 without the 6.4 subsection fails",
               re.sub(r"### 6\.4", "### 6.9", GOOD),
               "6.4"),
    ]

    print(f"{sum(results)}/{len(results)} tests ok")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
