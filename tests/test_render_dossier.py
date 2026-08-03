#!/usr/bin/env python3
"""test_render_dossier.py — executable suite for the render (project convention: PASS/exit≠0).

Locks the boundary between the GATE and the RENDER. The structural gate only requires the
PRESENCE of the 🐂/🐻 emojis in a contested fork; the renderer needs to style them. When the two
rules disagree, the dossier passes the gate and loses the visual block **without warning** — that
is what the synthetic example exposed, and it is the class of silent failure this project refuses.
"""
import sys
import tempfile
from pathlib import Path

from high_stakes.render_dossier import load_css, render

ROOT = Path(__file__).resolve().parents[1]

MD = """# Case — decide?

## Scope
Some scope for the render to exercise.

## §2 Forks

### 2.1 The fork

**🐂 Essay in favor.** Bold before the emoji.

🐻 **Essay against.** Emoji before the bold.

*"An epigraph in the lens's own voice."*

**In one sentence:** the verdict close.
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
        case("verdict close becomes a verdict line", "verdict-line" in h)
        case("sticky nav present", "<nav>" in h)

        print(f"{sum(results)}/{len(results)} tests ok")
        return 0 if all(results) else 1
    finally:
        __import__("shutil").rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
