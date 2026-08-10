#!/usr/bin/env python3
"""render_dossier.py — physical render of the dossier: report.md (SoR) → single-file HTML.

The "Physical" layer of the contract (output-contract.md): the ADAPTER's responsibility, code in
the engine (deliverables are data, not code — no renderer copied per run). CSS comes STRAIGHT from
the reference sample (assets/dossier.css) — single source; no per-run CSS copies.

Why this file was rewritten (Aug 2026). The ratified format defines 53 CSS classes; the previous
renderer emitted 12. Fork cards, advisor blocks, the executive box, named camps, the checkmark
matrix, weight bars, evidence chips, score strips, the source trail on each Chairman suggestion
and the solid-vs-dashed groundedness legend were specified, approved, styled — and never emitted.
No test went red, because the structural gate measures DEPTH and the quote verifier measures
FIDELITY: neither one sees FORM. `format_gate.py` now closes that hole, and this renderer emits
the vocabulary the gate checks for.

Markdown conventions it reads (all of them plain markdown — nothing invisible):
  §2  `🐂 **Thesis: …**` / `🐻 **Antithesis: …**` → .side.bull / .side.bear with an h5
      `**Camp:** …`                              → .camp (who stands on each side)
      `**Why they diverge:** …` and siblings     → the card's .foot
  §4  `*"epigraph"*`                             → .thesis
      `**Questions:** a · b`                     → .qa
      `**Strip:** a · b · c`                     → .scorestrip
      `**In one sentence:** …`                   → .quote.big (the verdict close)
  §6  `**N. Title.** body ←source · owner · when`→ ol.fifteen > li + .src
  any `**Weight:** 7/8 lenses`                   → .pesobar
      lines opening with ⚠️                      → .caveat
      lines opening with 🚩 / ✅                 → .reco
      tables carrying ✓ / ·                      → .check / .nocheck
Shares the attributed-quote shape (ATTRIB_RE) with render_gate.py — gate and render never
disagree about what an attribution is.

Usage: python3 -m high_stakes.render_dossier <report.md> [out.html]
"""
from __future__ import annotations

import html
import re
import sys
from pathlib import Path

from . import paths
from .render_gate import ATTRIB_RE  # shared gate↔render shape

CSS_PATH = paths.ASSETS / "dossier.css"

# Section titles are matched by the leading §N, so the label may be written in any language.
NAV = [("s0", "Summary"), ("sscope", "Scope"), ("s1", "1 Convergent"), ("s2", "2 Forks"),
       ("s3", "3 Unique"), ("s4", "4 Board"), ("s5", "5 Agenda"), ("s6", "6 Synthesis"),
       ("s7", "7 Appendix")]

# A bold lead-in label maps to a component. The literal stays in the markdown (the structural
# gate looks for it); the renderer decides how it is DISPLAYED. That is what lets a dossier be
# written in the decider's language while the gate keeps checking one canonical string.
LABEL_COMPONENT = {
    "camp": "camp", "campo": "camp",
    "weight": "pesobar", "peso": "pesobar",
    "strip": "scorestrip", "placar": "scorestrip",
    "in one sentence": "verdict", "em uma frase": "verdict",
    "questions": "qa", "perguntas": "qa",
    "suggestions": "qa", "sugestões": "qa", "sugestoes": "qa",
}
CHIP_RE = re.compile(r"\{chip:([^}]{1,40})\}")
BADGE_RE = re.compile(r"\{badge:([a-z-]{2,20})(?::([^}]{1,30}))?\}")
CONTRACT_RE = re.compile(r"^contract:\s*(\d+)\s*$", re.M)
LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
# Link safety for markdown links. The dossier quotes model output verbatim and then CIRCULATES
# as a file someone opens in a browser, so an unvalidated href is an LLM-output trust-boundary
# hole: `[click](javascript:…)` would render as a live link.
# The rule is stated as a DENY on schemes rather than an allow on path shapes: an allowlist of
# shapes rejected legitimate drill-down links like `rounds/r1/cells/`, and a link the reader
# needs is as much a defect as a link they must not click.
HAS_SCHEME = re.compile(r"^[a-z][a-z0-9+.\-]*:", re.I)
SAFE_SCHEME = re.compile(r"^(?:https?|mailto):", re.I)

# Card type → the ratified badge class. The taxonomy is the contract's (flaw, assumption, risk,
# open_question, decision-changing, adopted); the CSS colours are already in dossier.css.
BADGE_CLASS = {
    "flaw": "b-flaw", "deal-breaker": "b-flaw", "dud": "b-flaw",
    "assumption": "b-assum", "premise": "b-assum",
    "risk": "b-risk", "objection": "b-risk",
    "question": "b-oq", "open-question": "b-oq", "needs-human": "b-oq",
    "decision-changing": "b-dc", "strength": "b-dc",
    "adopted": "b-acatado", "keep": "b-acatado",
}


def load_css() -> str:
    """CSS packaged with the code — always exists. It used to be extracted by regex from the
    example HTML, which is doc: anyone installing without `examples/` would break at render,
    with the panel already paid for."""
    return CSS_PATH.read_text()


def contract_version(md: str) -> int:
    """Contract the dossier declares. Absent = 1 (pre-Aug-2026): those are frozen, not rewritten."""
    m = CONTRACT_RE.search(md)
    return int(m.group(1)) if m else 1


def derive_lead(report: Path) -> str:
    """'Decision Dossier · round N · <run slug>' from the run-persistence layout."""
    parts = report.resolve().parts
    round_ = next((p for p in parts if re.fullmatch(r"r\d+", p)), None)
    run_dir = next((p for p in parts if re.match(r"\d{4}-\d{2}-\d{2}-", p)), None)
    bits = ["Decision Dossier"]
    if round_:
        bits.append(f"round {round_[1:]}")
    if run_dir:
        bits.append(run_dir)
    return " · ".join(bits)


def _link(m: re.Match) -> str:
    """Markdown link → anchor, but only for a safe scheme. A rejected link degrades to its
    visible text plus the URL in parentheses: the reader still sees where it pointed, and
    nothing clickable is fabricated out of model output.

    The control-character strip is not decoration. Browsers implement the WHATWG URL parser,
    which removes ASCII tab and newline and strips leading C0 bytes BEFORE resolving the
    scheme, so `java<TAB>script:` reaches the deny check looking like an ordinary relative
    path and reaches the browser as script. Both reviewers found this independently."""
    label, href = m.group(1), m.group(2)
    href = re.sub(r"[\x00-\x20\x7f]", "", href)
    if not HAS_SCHEME.match(href) or SAFE_SCHEME.match(href):
        rel = ' rel="noopener noreferrer"' if href.lower().startswith("http") else ""
        return f'<a href="{html.escape(href, quote=True)}"{rel}>{label}</a>'
    return f"{label} ({href})"


def anchor_id(title: str, prefix: str = "") -> str:
    """Slug for an `id=` attribute. NEVER interpolate heading text raw: an unnumbered heading
    like `x" onmouseover="alert(1)` broke out of the attribute and, worse, could inject a class
    name that the format gate then counted as present. Both reviewers flagged it as the most
    exploitable finding in the diff."""
    m = re.match(r"(\d+\.\d+)", title)
    if m:
        return f"i{m.group(1)}"
    return (prefix + re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:32]) or "sec"


def inline(s: str) -> str:
    """Inline markdown → HTML. Evidence chips survive escaping (they are our markup, not the
    author's content), so `{chip:deck s.20}` becomes a chip instead of literal braces."""
    s = s.replace("\x00", "")   # our sentinels are NUL-delimited; author NULs would collide
    chips = CHIP_RE.findall(s)
    for i, _ in enumerate(chips):
        s = CHIP_RE.sub(f"\x00CHIP{i}\x00", s, count=1)
    badges = BADGE_RE.findall(s)
    for i, _ in enumerate(badges):
        s = BADGE_RE.sub(f"\x00BADGE{i}\x00", s, count=1)
    s = html.escape(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"(?<!\w)\*(.+?)\*(?!\w)", r"<i>\1</i>", s)
    s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
    s = LINK_RE.sub(_link, s)
    s = re.sub(r"§(\d+\.\d+)", r'<a class="anchor" href="#i\1">§\1</a>', s)
    for i, c in enumerate(chips):
        s = s.replace(f"\x00CHIP{i}\x00", f'<span class="chip">{html.escape(c)}</span>')
    for i, (kind, label) in enumerate(badges):
        cls = BADGE_CLASS.get(kind, "b-oq")
        s = s.replace(f"\x00BADGE{i}\x00",
                      f'<span class="badge {cls}">{html.escape(label or kind)}</span>')
    return s


# ---------- structural split (two passes: the line-by-line state machine could not tell
# where an item ended, which is why fork cards and advisor blocks were impossible) ----------

def split_by(md: str, marker: str):
    """[(title|None, body)] split on a heading marker. None = text before the first heading."""
    out, cur, buf = [], None, []
    for ln in md.splitlines():
        if ln.startswith(marker):
            out.append((cur, "\n".join(buf)))
            cur, buf = ln[len(marker):], []
        else:
            buf.append(ln)
    out.append((cur, "\n".join(buf)))
    return out


def blocks(text: str):
    """Groups lines into ('p'|'quote'|'table'|'list', [lines])."""
    out, kind, buf = [], None, []

    def flush():
        nonlocal kind, buf
        if buf and any(x.strip() for x in buf):
            out.append((kind, buf))
        kind, buf = None, []

    for ln in text.splitlines():
        if not ln.strip():
            flush()
            continue
        k = ("quote" if ln.startswith(">") else "table" if ln.startswith("|")
             else "list" if re.match(r"^[-*] ", ln) else "p")
        if kind and k != kind:
            flush()
        kind = k
        buf.append(ln)
    flush()
    return out


# ---------- component renderers ----------

def render_table(lines: list[str]) -> str:
    """Markdown table → HTML. A ✓ cell becomes a checkmark, `n/m` becomes a weight bar: that is
    the convergence matrix of the ratified format, expressed in plain markdown."""
    rows = [[c.strip() for c in ln.strip("|").split("|")] for ln in lines]
    if len(rows) < 2:
        # A malformed table used to return "" and the author's row vanished. Degrade to prose:
        # losing the grid is a formatting problem, losing the content is a correctness one.
        return "".join(f"<p>{inline(' · '.join(r))}</p>" for r in rows)

    def cell(c: str) -> str:
        if c == "✓":
            return '<td class="center check">✓</td>'
        if c in ("·", "-"):
            return '<td class="center nocheck">·</td>'
        if re.fullmatch(r"\d+/\d+", c):
            return f'<td class="center"><span class="pesobar">{html.escape(c)}</span></td>'
        return f"<td>{inline(c)}</td>"

    head = "".join(f"<th>{inline(c)}</th>" for c in rows[0])
    body = "".join("<tr>" + "".join(cell(c) for c in r) + "</tr>" for r in rows[2:])
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def render_quote(lines: list[str]) -> str:
    """Blockquote → one .quote per ATTRIBUTED quote.

    Closing only at the end merged adjacent quotes and kept the LAST attribution, silently
    reassigning one advisor's words to another. In a dossier whose entire claim is
    code-verified attribution that is the worst possible defect, and the quote verifier cannot
    see it: both strings are verbatim, only the name moved."""
    out, txt = [], []

    def flush(who: str = "") -> None:
        body = " ".join(t for t in txt if t)
        txt.clear()
        if not body and not who:
            return
        w = f'<span class="who">{inline(who)}</span>' if who else ""
        out.append(f'<p class="quote">{inline(body)}{w}</p>')

    for ln in lines:
        b = ln.lstrip("> ").rstrip()
        mq = (re.match(r"(.*?)\s*—\s*\*\*(.+?)\*\*\s*(\([^)]*\))?\s*$", b)
              if ATTRIB_RE.search(b) else None)
        if mq:
            txt.append(mq.group(1).strip())
            flush(f"{mq.group(2)} {mq.group(3) or ''}".strip())
        else:
            txt.append(b)
    flush()
    return "".join(out)


def render_para(ln: str) -> str:
    if ln.startswith("⚠️"):
        return f'<span class="caveat">{inline(ln)}</span>'
    if ln.startswith("🚩") or ln.startswith("✅"):
        return f'<div class="reco">{inline(ln)}</div>'

    # Chairman suggestion: **N. Title.** body ←source · owner · when
    m = re.match(r"^\*\*(\d+)\.\s(.+?)\*\*\s*(.*)$", ln)
    if m:
        rest, src = m.group(3), ""
        ms = re.search(r"←(.+)$", rest)
        if ms:
            rest, src = rest[:ms.start()].rstrip(), f'<span class="src">←{inline(ms.group(1))}</span>'
        return f'<li data-n="{m.group(1)}"><b>{inline(m.group(2))}</b> {inline(rest)}{src}</li>'

    m = re.match(r"^\*\*([^*:]{2,44}):\*\*\s*(.*)$", ln)
    if m:
        label, rest = m.group(1), m.group(2)
        comp = LABEL_COMPONENT.get(label.strip().lower())
        if comp == "camp":
            return f'<div class="camp">{inline(rest)}</div>'
        if comp == "pesobar":
            return f'<p><span class="pesobar">{inline(rest)}</span></p>'
        if comp == "scorestrip":
            sc = "".join(f'<div class="sc">{inline(p.strip())}</div>' for p in rest.split("·"))
            return f'<div class="scorestrip">{sc}</div>'
        if comp == "verdict":
            return f'<p class="quote big">{inline(rest)}</p>'
        if comp == "qa":
            items = "".join(f"<li>{inline(x.strip())}</li>" for x in rest.split("·"))
            return f'<div><h6>{inline(label)}</h6><ul>{items}</ul></div>'
        return f"<p><b>{inline(label)}:</b> {inline(rest)}</p>"

    if re.match(r"(\*\*\s*)?🐂", ln) or re.match(r"(\*\*\s*)?🐻", ln):
        return f"<h5>{inline(ln)}</h5>"
    if re.match(r'^\*["“]', ln) and ln.rstrip().endswith(('"*', '”*')):
        return f'<p class="thesis">{inline(ln)}</p>'
    return f"<p>{inline(ln)}</p>"


def wrap_fifteen(parts: list[str]) -> list[str]:
    """Runs of <li data-n=…> become one <ol class="fifteen"> (the Chairman's ranked list)."""
    out, buf = [], []
    for h in parts:
        if h.startswith("<li data-n="):
            buf.append(h)
            continue
        if buf:
            out.append(f'<ol class="fifteen">{"".join(buf)}</ol>')
            buf = []
        out.append(h)
    if buf:
        out.append(f'<ol class="fifteen">{"".join(buf)}</ol>')
    return out


# A line that OPENS its own component; anything else is a continuation of the paragraph above.
COMPONENT_START = re.compile(
    r"^(⚠️|🚩|✅|(\*\*\s*)?🐂|(\*\*\s*)?🐻|\*\*\d+\.\s|\*\*[^*:]{2,44}:\*\*|\*[\"“])")


def logical_paragraphs(lines: list[str]) -> list[str]:
    """Joins soft-wrapped lines into ONE logical paragraph.

    The previous renderer emitted one <p> per SOURCE LINE, so every wrapped paragraph shattered
    into fragments: 287 <p> tags in the reference dossier, 240 of them under 90 characters. That
    is markdown's oldest rule (a blank line separates paragraphs, a newline does not) and it made
    every dossier read choppy no matter how well it was written."""
    out: list[str] = []
    for ln in lines:
        if not out or COMPONENT_START.match(ln):
            out.append(ln)
        else:
            out[-1] += " " + ln.strip()
    return out


def render_body(text: str, group_qa: bool = False) -> str:
    out, qabuf = [], []
    for kind, lines in blocks(text):
        if kind == "quote":
            out.append(render_quote(lines))
        elif kind == "table":
            out.append(render_table(lines))
        elif kind == "list":
            items = "".join(f"<li>{inline(re.sub(r'^[-*] ', '', x))}</li>" for x in lines)
            out.append(f"<ul>{items}</ul>")
        else:
            for ln in logical_paragraphs(lines):
                h = render_para(ln)
                (qabuf if (group_qa and h.startswith("<div><h6>")) else out).append(h)
    if qabuf:
        out.append(f'<div class="qa">{"".join(qabuf)}</div>')
    return "".join(wrap_fifteen(out))


def render_fork(title: str, body: str) -> str:
    """A §2 item is a CARD: header with the question, body with the two camps, foot with the
    fields that resolve it. The previous renderer emitted three loose paragraphs."""
    m = re.match(r"(\d+\.\d+)\s*(.*)", title)
    iid = anchor_id(title, "fork-")
    num, head = (m.group(1), m.group(2)) if m else ("", title)
    ctx, foot, sides, cur = [], [], [], None
    for _, lines in blocks(body):
        chunk, first = "\n".join(lines), lines[0]
        if re.match(r"(\*\*\s*)?🐂", first):
            cur = "bull"
            sides.append([cur, [chunk]])
        elif re.match(r"(\*\*\s*)?🐻", first):
            cur = "bear"
            sides.append([cur, [chunk]])
        elif re.match(r"^\*\*(Why they diverge|Cost of being wrong|What resolves)", first, re.I):
            cur = "foot"
            foot.append(chunk)
        elif cur in ("bull", "bear") and sides:
            sides[-1][1].append(chunk)
        elif cur == "foot":
            foot.append(chunk)
        else:
            ctx.append(chunk)
    # Blocks were split on BLANK lines, so they must be rejoined with a blank line. Joining with
    # a single "\n" re-merged them and the whole essay was appended onto the `**Camp:**` line —
    # 516 characters of the bull thesis rendered as camp metadata in the shipped exemplar, with
    # the format gate green over it. Content loss that no gate could see: the exact failure this
    # module exists to prevent, reproduced on day one.
    body_html = render_body("\n\n".join(ctx)) + "".join(
        f'<div class="side {k}">{render_body((chr(10) * 2).join(v))}</div>' for k, v in sides)
    foot_html = f'<div class="foot">{render_body((chr(10) * 2).join(foot))}</div>' if foot else ""
    return (f'<div class="fork" id="{iid}"><div class="hd"><h3>'
            f'<span class="idtag">{html.escape(num)}</span>{inline(head)}</h3></div>'
            f'<div class="body">{body_html}</div>{foot_html}</div>')


def render_advisor(title: str, body: str) -> str:
    """A §4 item is an advisor BLOCK: axis line, name, epigraph, opinion, Q&A, score strip."""
    m = re.match(r"(\d+\.\d+)\s*(.*)", title)
    iid = anchor_id(title, "adv-")
    num, head = (m.group(1), m.group(2)) if m else ("", title)
    name, role = (head.split(",", 1) + [""])[:2] if "," in head else (head, "")
    role_line = f'<p class="role">{html.escape(num)} · {inline(role.strip())}</p>' if num else ""
    return (f'<div class="advisor" id="{iid}">{role_line}'
            f"<h3>{inline(name.strip())}</h3>{render_body(body, group_qa=True)}</div>")


LEGEND = ('<div class="legend"><span><span class="pesobar">7/8</span> weight counts distinct lenses, not cells</span></div>')
# The solid-vs-dashed groundedness swatches were REMOVED from this legend. The renderer
# never applied either border to an item, so the legend explained a convention the
# document did not follow: a promise rendered as if it were a feature.


def render_body_doc(md: str, lead: str) -> str:
    title = next((l[2:].strip() for l in md.splitlines() if l.startswith("# ")), "Dossier")
    sub = ""
    m = re.search(r"^> (.+?)(?:\n\n|\n#)", md, re.S | re.M)
    if m:
        sub = " ".join(x.lstrip("> ").strip() for x in m.group(1).splitlines())

    out = [f'<div class="titleblock"><div class="kicker">{html.escape(lead)}</div>'
           f"<h1>{inline(title)}</h1>"
           f'<p class="sub">{inline(sub)}</p>'
           f'<div class="meta"><span><b>Panel</b> blind cells, no rounds</span>'
           f"<span><b>Refutation</b> external family</span>"
           f"<span><b>Quotes</b> code-verified</span></div>{LEGEND}</div>"]

    for h2, sec in split_by(md, "## "):
        if h2 is None:
            continue
        mm = re.match(r"§?(\d)\s*(.*)", h2)
        sid = f"s{mm.group(1)}" if mm else "sscope"
        label = (mm.group(2) or h2) if mm else re.sub(r"^§?\s*", "", h2)
        num = f'<span class="secnum">§{mm.group(1)}</span>' if mm else ""
        out.append(f'<section id="{sid}"><h2>{num}{inline(label)}</h2>')
        for h3, item in split_by(sec, "### "):
            if h3 is None:
                if item.strip():
                    inner = render_body(item)
                    out.append(f'<div class="exec">{inner}</div>' if sid == "s0" else inner)
                continue
            if sid == "s2":
                out.append(render_fork(h3, item))
            elif sid == "s4":
                out.append(render_advisor(h3, item))
            else:
                im = re.match(r"(\d+\.\d+)\s*(.*)", h3)
                iid = anchor_id(h3)
                tag = f'<span class="idtag">{im.group(1)}</span>' if im else ""
                out.append(f'<h3 id="{iid}">{tag}{inline(im.group(2) if im else h3)}</h3>'
                           f"{render_body(item)}")
        out.append("</section>")
    return "".join(out)


def render(report: Path, out_path: Path | None = None) -> Path:
    md = report.read_text()
    nav = "".join(f'<a href="#{i}">{t}</a>' for i, t in NAV)
    js = ("const d=document.documentElement;document.getElementById('thm').onclick=()=>"
          "{d.dataset.theme=d.dataset.theme==='dark'?'light':'dark'};")
    page = (f'<!DOCTYPE html><html lang="en" data-theme="light"><head><meta charset="UTF-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1.0">'
            f"<title>Decision Dossier · high-stakes</title>"
            f"<style>{load_css()}</style></head><body>"
            f'<header class="top"><div class="in">'
            f'<div class="brand"><span class="dot"></span>high-stakes</div>'
            f'<nav>{nav}</nav><button class="iconbtn" id="thm">theme</button></div></header>'
            f'<div class="wrap">{render_body_doc(md, derive_lead(report))}</div>'
            f"<script>{js}</script></body></html>")
    out_path = out_path or report.with_suffix(".html")
    out_path.write_text(page)
    return out_path


def main() -> int:
    if len(sys.argv) not in (2, 3):
        print("usage: render_dossier.py <report.md> [out.html]")
        return 2
    report = Path(sys.argv[1])
    if not report.exists():
        print(f"report does not exist: {report}")
        return 1
    out = render(report, Path(sys.argv[2]) if len(sys.argv) == 3 else None)
    print(f"render ok: {out} ({out.stat().st_size // 1000} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
