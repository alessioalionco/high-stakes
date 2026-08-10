#!/usr/bin/env python3
"""test_render_dossier.py — executable suite for the render (project convention: PASS/exit≠0).

Locks the boundary between the GATE and the RENDER. The structural gate only requires the
PRESENCE of the 🐂/🐻 emojis in a contested fork; the renderer needs to style them. When the two
rules disagree, the dossier passes the gate and loses the visual block **without warning** — that
is what the synthetic example exposed, and it is the class of silent failure this project refuses.

Aug 2026: two defects of exactly that class were found and are locked here forever.
  · The renderer emitted 12 of the 53 ratified classes. Fork cards, advisor blocks, camps, the
    checkmark matrix, weight bars, chips, score strips and the source trail were styled and never
    emitted. `test_format_gate.py` owns the general check; the shape cases live here.
  · The renderer emitted one <p> per SOURCE LINE, so every soft-wrapped paragraph shattered into
    fragments (287 <p> in the reference dossier, 240 of them under 90 characters).
"""
import sys
import tempfile
from pathlib import Path

from high_stakes.render_dossier import load_css, logical_paragraphs, render

ROOT = Path(__file__).resolve().parents[1]

MD = """# Case — decide?
contract: 2

## Scope
Some scope for the render to exercise.

## §2 Forks

### 2.1 The fork

**🐂 Essay in favor.** Bold before the emoji.

**Camp:** The Operator (GPT-5.6 Sol) · The Strategist (GLM-5.2)

🐻 **Essay against.** Emoji before the bold.

*"An epigraph in the lens's own voice."*

**In one sentence:** the verdict close.

## §6 Synthesis

### 6.4 Ranked suggestions

**1. Do the thing.** Because of the mechanism, with an owner and a gate. ←1.1 (4/4) · finance · days
"""

WRAPPED = """A paragraph written across
three soft-wrapped lines that
markdown says is ONE paragraph.

**Camp:** a component line, not a continuation.
"""


def main() -> int:
    results: list[bool] = []

    def case(name, cond):
        print(("PASS " if cond else "FAIL ") + name)
        results.append(bool(cond))

    tmp = Path(tempfile.mkdtemp())
    try:
        md = tmp / "r.md"
        md.write_text(MD)
        out = render(md, tmp / "r.html")
        h = out.read_text()

        case("CSS comes from the package (assets/), not from examples/", len(load_css()) > 1000)
        case("HTML is single-file: CSS inlined, zero external reference",
             "<style>" in h and "<link " not in h and 'src="http' not in h)
        case("REGRESSION: `**🐂` becomes a bull block", 'class="side bull"' in h)
        case("REGRESSION: `🐻 **` (emoji first) ALSO becomes a bear block — both orders "
             "pass the gate, so both have to render", 'class="side bear"' in h)
        case("epigraph becomes a thesis", 'class="thesis"' in h)
        case("the verdict close becomes .quote.big — the RATIFIED class. It used to emit "
             "`.verdict-line`, which the packaged stylesheet never defined: dead markup that "
             "looked styled in the author's head and rendered as a bare paragraph on screen",
             'class="quote big"' in h and "verdict-line" not in h)
        case("sticky nav present", 'class="top"' in h and "<nav>" in h)

        # the ratified vocabulary, on the shapes this fixture exercises
        case("REGRESSION: a §2 item is a fork CARD, not loose paragraphs", 'class="fork"' in h)
        case("REGRESSION: the fork card has a header holding the question",
             'class="hd"' in h and 'class="idtag"' in h)
        case("REGRESSION: `**Camp:**` names who stands on each side", 'class="camp"' in h)
        case("REGRESSION: a numbered Chairman suggestion is an ol.fifteen item",
             'class="fifteen"' in h and "data-n=" in h)
        case("REGRESSION: the `←` trail becomes the source span", 'class="src"' in h)
        case("the legend explains what the render actually DOES (weight = distinct lenses) and "
             "no longer promises solid-vs-dashed groundedness, which the renderer never applied "
             "to a single item — a legend for an unimplemented feature is the 'contract as if "
             "built' failure the core forbids",
             'class="legend"' in h and "pesobar" in h
             and "swatch solid" not in h and "swatch dash" not in h)

        # LLM-output trust boundary: the dossier quotes model text verbatim and then circulates
        # as a file someone opens in a browser. An unvalidated href turns a quoted link into a
        # live one. Found by review on the day link support was added.
        from high_stakes.render_dossier import inline
        case("SECURITY: a `javascript:` link never becomes an anchor",
             "<a href" not in inline("[click](javascript:alert(1))"))
        case("SECURITY: `data:` and `vbscript:` are refused too, case-insensitively",
             "<a href" not in inline("[c](data:text/html,x)")
             and "<a href" not in inline("[c](VBScript:m)"))
        case("a refused link still shows its target as text — the reader loses the click, "
             "never the information", "javascript:alert(1)" in inline("[c](javascript:alert(1))"))
        case("legitimate drill-down links still work (relative dir, anchor, file, http)",
             all("<a href" in inline(x) for x in
                 ["[c](rounds/r1/cells/)", "[v](#i2.1)", "[r](report.md#s6)",
                  "[r](https://example.com)"]))
        case("SECURITY: chip and badge content is escaped, not injected",
             "&lt;img" in inline("{chip:<img src=x onerror=alert(1)>}")
             and "onerror=alert(1)>" not in inline("{chip:<img src=x onerror=alert(1)>}"))

        # paragraph joining — markdown's oldest rule
        joined = logical_paragraphs(WRAPPED.strip().splitlines()[:3])
        case("REGRESSION: soft-wrapped lines join into ONE logical paragraph "
             "(the old renderer emitted one <p> per source line)",
             len(joined) == 1 and joined[0].endswith("ONE paragraph."))
        comp = logical_paragraphs(["prose line", "**Camp:** a component"])
        case("REGRESSION: a component line still OPENS its own block, it does not get "
             "swallowed by the paragraph above", len(comp) == 2)

        # the real reference must survive the real renderer
        sample = ROOT / "examples" / "sample-dossier.md"
        if sample.exists():
            sh = render(sample, tmp / "sample.html").read_text()
            frags = sh.count("<p>") and sum(
                1 for p in sh.split("<p>")[1:] if len(p.split("</p>")[0]) < 90)
            case("the reference dossier renders without shattering into fragments "
                 "(<25% of paragraphs under 90 chars)", frags < 0.25 * sh.count("<p>"))

        print(f"{sum(results)}/{len(results)} tests ok")
        return 0 if all(results) else 1
    finally:
        __import__("shutil").rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
