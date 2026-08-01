#!/usr/bin/env python3
"""render_dossier.py — render físico do dossiê: report.md (SoR) → single-file HTML.

Camada "Físico" do contrato (output-contract.md): responsabilidade do ADAPTER, código no engine
(deliverables são dados, não código — nada de renderer copiado por run). CSS vem DIRETO do sample
de referência (assets/dossier.css) — fonte única; sem cópias de CSS por run.

Uso: python3 render_dossier.py <report.md> [out.html]
  - out default: <report.md com sufixo .html>
  - lead/rodada derivados do path (rounds/rN) e da data do run dir; título = H1 do report.
Compartilha com render_gate.py o shape de quote atribuída (ATTRIB_RE) — gate e render nunca
divergem sobre o que é uma atribuição.
"""
from __future__ import annotations

import html
import re
import sys
from pathlib import Path

from .render_gate import ATTRIB_RE  # shape compartilhado gate↔render

from . import paths

CSS_PATH = paths.ASSETS / "dossier.css"

EXTRA_CSS = """
.verdict-line{font-weight:700;border-left:3px solid var(--brand);padding-left:10px}
.thesis{font-size:1.05em}
blockquote.quote{border-left:3px solid var(--accent);background:var(--surface-2);margin:10px 0;padding:10px 14px;border-radius:6px}
blockquote.quote .who{display:block;margin-top:6px;color:var(--muted);font-size:.85em;font-style:normal}
p.side{padding:10px 14px;border-radius:8px;margin:10px 0}
p.side.bull{background:var(--bull-bg);border-left:3px solid var(--bull)}
p.side.bear{background:var(--bear-bg);border-left:3px solid var(--bear)}
h2{margin-top:2.4em}
table{font-size:.88em}
"""

NAV = ('<a href="#s0">Resumo</a><a href="#s0b">Escopo</a><a href="#s1">1 Convergentes</a>'
       '<a href="#s2">2 Forks</a><a href="#s3">3 Únicas</a><a href="#s4">4 Conselho</a>'
       '<a href="#s5">5 Agenda</a><a href="#s6">6 Síntese</a><a href="#s7">7 Apêndice</a>')


def load_css() -> str:
    """CSS empacotado com o código — sempre existe. Antes era extraído por regex do
    HTML de exemplo, que é doc: quem instalasse sem o `examples/` quebrava no render,
    já com o painel pago. O exemplo continua existindo, mas só como âncora procedural do gate de render."""
    return CSS_PATH.read_text()


def derive_lead(report: Path) -> str:
    """'Dossiê da Decisão · rodada N · <slug do run>' a partir do layout run-persistence."""
    parts = report.resolve().parts
    round_ = next((p for p in parts if re.fullmatch(r"r\d+", p)), None)
    run_dir = next((p for p in parts if re.match(r"\d{4}-\d{2}-\d{2}-", p)), None)
    bits = ["Dossiê da Decisão"]
    if round_:
        bits.append(f"rodada {round_[1:]}")
    if run_dir:
        bits.append(run_dir)
    return " · ".join(bits)


def inline(s: str) -> str:
    s = html.escape(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"(?<!\w)\*(.+?)\*(?!\w)", r"<i>\1</i>", s)
    s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
    s = re.sub(r"§(\d+\.\d+)", r'<a class="anchor" href="#i\1">§\1</a>', s)
    return s


def render_body(md: str, lead: str) -> list[str]:
    out: list[str] = []
    state = {"ul": False, "tab": False, "q": False}
    tabrows: list[list[str]] = []

    def close(*names: str):
        for n in names or ("ul", "tab", "q"):
            if n == "ul" and state["ul"]:
                out.append("</ul>")
                state["ul"] = False
            if n == "q" and state["q"]:
                out.append("</blockquote>")
                state["q"] = False
            if n == "tab" and state["tab"]:
                if tabrows:
                    out.append("<table><thead><tr>"
                               + "".join(f"<th>{inline(c)}</th>" for c in tabrows[0])
                               + "</tr></thead><tbody>")
                    for r in tabrows[2:]:
                        out.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>")
                    out.append("</tbody></table>")
                tabrows.clear()
                state["tab"] = False

    for ln in md.splitlines():
        if ln.startswith("## "):
            close()
            title = ln[3:]
            m = re.match(r"§(\d)", title)
            sid = f"s{m.group(1)}" if m else ("s0b" if "Escopo" in title else "sx")
            out.append(f'<h2 id="{sid}"><span class="secnum">{inline(title)}</span></h2>')
        elif ln.startswith("### "):
            close()
            t = ln[4:]
            m = re.match(r"(\d+\.\d+)", t)
            aid = f"i{m.group(1)}" if m else re.sub(r"[^a-z0-9]+", "-", t.lower())[:30]
            head = inline(t[len(m.group(1)):]) if m else inline(t)
            tag = inline(t.split(" ")[0]) if m else ""
            out.append(f'<h3 id="{aid}"><span class="idtag">{tag}</span> {head}</h3>')
        elif ln.startswith("> "):
            close("ul", "tab")  # quote fecha tabela/lista abertas (bug do v1: não fechava)
            body = ln[2:]
            if not state["q"]:
                out.append('<blockquote class="quote">')
                state["q"] = True
            if ATTRIB_RE.search(ln):
                mq = re.match(r"(.*?)\s*—\s*\*\*(.+?)\*\*\s*(\((?:via|lente simulada)[^)]*\))?\s*$",
                              body)
                if mq:
                    out.append(f'{inline(mq.group(1))}<span class="who">{inline(mq.group(2))} '
                               f'{inline(mq.group(3) or "")}</span>')
                    continue
            out.append(inline(body) + " ")
        elif ln.startswith("|"):
            close("ul", "q")
            state["tab"] = True
            tabrows.append([c.strip() for c in ln.strip("|").split("|")])
        elif ln.startswith("- "):
            close("tab", "q")  # lista fecha tabela aberta (bug do v1: não fechava)
            if not state["ul"]:
                out.append("<ul>")
                state["ul"] = True
            out.append(f"<li>{inline(ln[2:])}</li>")
        elif ln.strip() == "":
            close()
        elif ln.startswith("# "):
            out.append(f'<header><p class="lead">{html.escape(lead)}</p>'
                       f'<h1>{inline(ln[2:].split("—")[-1].strip())}</h1></header>')
        else:
            close("tab", "q")
            cls = ""
            # Aceita as DUAS ordens (`**🐂 …` e `🐂 **…`): o gate estrutural só exige a
            # presença do emoji, então casar só uma ordem faria o dossiê passar no gate e
            # perder o bloco visual em silêncio.
            if re.match(r"(\*\*\s*)?🐂", ln):
                cls = ' class="side bull"'
            elif re.match(r"(\*\*\s*)?🐻", ln):
                cls = ' class="side bear"'
            elif re.match(r'^\*["“]', ln) and ln.rstrip().endswith(('"*', '”*')):
                cls = ' class="thesis"'
            elif ln.startswith("**Em uma frase"):
                cls = ' class="verdict-line"'
            out.append(f"<p{cls}>{inline(ln)}</p>")
    close()
    return out


def render(report: Path, out_path: Path | None = None) -> Path:
    md = report.read_text()
    body = render_body(md, derive_lead(report))
    page = (f'<!DOCTYPE html><html lang="pt-BR" data-theme="light"><head><meta charset="UTF-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1.0">'
            f'<title>Dossiê da Decisão · high-stakes</title>'
            f'<style>{load_css()}\n{EXTRA_CSS}</style></head><body><nav>{NAV}</nav>'
            f'<main class="wrap" style="max-width:880px;margin:0 auto;padding:22px 20px 90px">'
            f'{chr(10).join(body)}</main></body></html>')
    out_path = out_path or report.with_suffix(".html")
    out_path.write_text(page)
    return out_path


def main() -> int:
    if len(sys.argv) not in (2, 3):
        print("uso: render_dossier.py <report.md> [out.html]")
        return 2
    report = Path(sys.argv[1])
    if not report.exists():
        print(f"report não existe: {report}")
        return 1
    out = render(report, Path(sys.argv[2]) if len(sys.argv) == 3 else None)
    print(f"render ok: {out} ({out.stat().st_size // 1000} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
