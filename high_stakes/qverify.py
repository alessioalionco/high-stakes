#!/usr/bin/env python3
"""qverify.py — quote verification by CODE (lossless-summary contract, §3f item 6).

Every attributed quote in the dossier ("> ... — **Name** (via Model)") and every §4 epigraph
(*"..."*) must be a VERBATIM excerpt from a raw cell of that advisor. This verifier
checks by code — it kills a measured error class (5% fabrication in cells with
a pack) and retires the global `quote_unverified` flag.

Usage: python3 qverify.py <report.md> <cells_dir>   → exit 0 = all verified; 1 = failures.
API: verify(report_md, cells_dir) -> list[dict] (one per quote: {quote, advisor, status, where}).

Match rules (hardened in the 21/Jul review — 6 false-green routes closed):
- normalization (lowercase, collapsed whitespace, unified quotes/dashes/markdown emphasis);
- cell fields separated by \\n AFTER normalizing — a quote cannot "glue" the end of one
  field to the start of another;
- match within ONE cell only, and with segments IN ORDER (ellipsis "…"/"[...]" splits into
  segments; all mandatory, including the short ones; no splicing across cells);
- attribution = "— **Name**" anchored at the END of the line (em-dash+bold mid-quote is
  content, not attribution);
- §4: missing/unextractable epigraph = FAILURE (never a silent skip);
- match on the wrong advisor = `divergent_attribution` (the voice matters as much as the text).
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from typing import Iterable
from pathlib import Path

# Display name -> advisor key. ROLES first: "Anti-thesis of X" resolves to the role,
# not to the name that appears inside the heading.
# ROLES: resolve before the lens key ("Anti-thesis of X" is the role, not the lens X).
ROLE_KEYS = [
    ("anti-thesis", "antithesis"), ("antithesis", "antithesis"),
    ("refuter", "refuter"), ("generalist", "generalist"),
]
# There is NO fixed advisor list. There used to be one, with 7 surnames, while the
# embedded pool has 13 and the user can write their own: any lens outside the list
# resolved to None and EVERY quote of theirs became "divergent_attribution" — permanent
# red in a gate that should be silent. The keys come from the cell corpus.

# Attribution ONLY at end of line (with optional "(via ...)" after the name).
ATTRIB_END_RE = re.compile(
    r"—\s*\*\*([^*]+?)\*\*\s*(?:\((?:via|simulated lens)[^)]*\))?\s*$")
ELLIPSIS_RE = re.compile(r"…|\[\.\.\.\]|\[…\]|\.\.\.")
MIN_QUOTE = 15   # a quote/epigraph shorter than this does not discriminate -> explicit failure
MIN_SEGMENT = 4  # minimum ellipsis segment AFTER strip; all are mandatory


def normalize(s: str) -> str:
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    s = s.replace("–", "-").replace("—", "-")
    s = re.sub(r"[*_`]", "", s)  # markdown emphasis is not content
    s = re.sub(r"[ \t]+", " ", s).strip().lower()
    return s.strip(' "\'.,;:!?-')


def cell_corpus(cells_dir: Path) -> dict[str, list[str]]:
    """advisor_key -> [normalized text PER CELL] (fields separated by \\n — no gluing)."""
    corpus: dict[str, list[str]] = {}
    for p in sorted(cells_dir.glob("*.json")):
        try:
            d = json.loads(p.read_text())
        except json.JSONDecodeError:
            continue
        # The ROLE decides only the key. The corpus is built the same way for everyone:
        # RECURSIVE collection of every string — schema-agnostic (real bug from the 2nd
        # use: a fixed field list left a new schema out of the corpus and failed a
        # legitimate quote). The refuter had its own branch reading the flat `text` field,
        # which the xverify cells (schema `result.case_against`…) don't have -> empty
        # corpus -> false RED.
        key = "refuter" if p.name.startswith("refuter") else (
            d.get("advisor") or d.get("lente") or p.stem)  # "lente" = legacy PT cell key
        parts: list[str] = []

        def walk(x):
            if isinstance(x, str):
                parts.append(x)
            elif isinstance(x, dict):
                for v in x.values():
                    walk(v)
            elif isinstance(x, list):
                for v in x:
                    walk(v)

        walk(d.get("result") or {})
        for flat in ("text", "raw_text"):  # legacy cell formats
            if d.get(flat):
                parts.append(str(d[flat]))
        cell_text = "\n".join(normalize(str(x)) for x in parts if str(x).strip())
        corpus.setdefault(key, []).append(cell_text)
    return corpus


def _quote_lines(report_md: str):
    """Iterates (is_quote, body) per line, resolving the two blockquote forms that a raw
    `startswith(">")` did not see and that produced RED on a correct document:

      · indentation of up to 3 spaces (valid markdown; 4+ is already a code block);
      · lazy continuation (CommonMark): inside a blockquote, a non-empty line without `>`
        continues the quote. Without this the quote was split and the piece became
        `too_short_to_verify`.

    It lives here, and is not duplicated, because `_joined_quotes` and
    `_malformed_attributions` must agree on what a blockquote is — if they diverge, a
    quote is extracted by one and treated as prose by the other, and the report
    contradicts itself.
    """
    inside = False
    for ln in report_md.splitlines():
        stripped = re.sub(r"^ {0,3}", "", ln)  # up to 3 spaces; 4+ is a code block
        is_quote = stripped.startswith(">")
        if not is_quote and inside and ln.strip():
            is_quote, stripped = True, "> " + ln.strip()
        if is_quote:
            inside = True
            yield True, stripped.lstrip("> ").rstrip()
        else:
            inside = False
            yield False, ln


def _joined_quotes(report_md: str) -> list[tuple[str, str]]:
    """[(quote_text, attributed_name)] — joins multi-line blockquotes; attribution only at
    the end of a line (internal em-dash+bold is content)."""
    out = []
    buf: list[str] = []
    for is_quote, body in _quote_lines(report_md):
        if not is_quote:
            buf = []
            continue
        m = ATTRIB_END_RE.search(body)
        if m:
            text = " ".join(buf + [body[:m.start()]])
            out.append((text.strip(), m.group(1)))
            buf = []
        else:
            buf.append(body)
    return out


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn")


def _advisor_for(name: str, corpus_keys: Iterable[str] = ()) -> str | None:
    """Display name -> advisor key. Roles first, then the REAL keys from that run's
    cells (sorted longest to shortest, so that a longer key is not shadowed by a
    shorter one that is its prefix)."""
    n = normalize(name)
    ns = _strip_accents(n)
    for token, key in ROLE_KEYS:
        if token in n or token in ns:
            return key
    for key in sorted(corpus_keys, key=len, reverse=True):
        k = normalize(str(key))
        if k and (k in n or _strip_accents(k) in ns):
            return key
    return None


def _segments(qnorm: str) -> list[str]:
    segs = [s.strip(' "\'.,;:!?-') for s in ELLIPSIS_RE.split(qnorm)]
    return [s for s in segs if len(s) >= MIN_SEGMENT]


def _in_one_cell_ordered(segs: list[str], cells: list[str]) -> bool:
    """All segments, IN ORDER, within ONE SINGLE cell."""
    for text in cells:
        pos = 0
        for s in segs:
            i = text.find(s, pos)
            if i < 0:
                break
            pos = i + len(s)
        else:
            return True
    return False


def _match(qnorm: str, corpus: dict[str, list[str]], advisor: str | None) -> tuple[str, str]:
    segs = _segments(qnorm)
    if not segs:
        return "too_short_to_verify", ""
    if advisor and advisor in corpus and _in_one_cell_ordered(segs, corpus[advisor]):
        return "verified", advisor
    for key, cells in corpus.items():
        if key != advisor and _in_one_cell_ordered(segs, cells):
            return "divergent_attribution", key
    return "unverified", ""


# LOOSE detection — the same shape the render gate uses to count quotes. It serves to
# find lines that ARE attributions; strict parsing comes later. Without this, a line with
# any text after the parenthesis passed the gate and was INVISIBLE here: the verifier
# printed "GREEN — 0/0" without having verified anything. An anti-fabrication gate
# failing OPEN.
ATTRIB_LOOSE_RE = re.compile(r"—\s*\*\*.+?\*\*")


def _malformed_attributions(report_md: str) -> list[tuple[str, str]]:
    """[(status, line)] of the attributions that strict parsing does NOT capture.

    Works per blockquote BLOCK, not per line: a legitimate two-line quote with internal
    bold had its 1st line accused of being malformed while the SAME quote appeared right
    below as verified — red with a contradictory message.

    And it also sweeps OUTSIDE the blockquote: an attribution in prose was invisible to
    both gates (both required `startswith(">")`), so a fabricated quote outside `>`
    passed as long as any legitimate quote in the document kept `findings` non-empty.
    """
    bad: list[tuple[str, str]] = []
    segment: list[str] = []   # the CURRENT quote, not the whole block

    def flush(seg: list[str]) -> None:
        """Judges ONE quote. Per block, one valid attribution washed the malformed one
        next to it.

        The gate was per block because a legitimate two-line quote with internal bold had
        its 1st line accused of being malformed. But a blockquote can contain SEVERAL
        quotes, and per block a single strict attribution on any line was enough for the
        whole block to pass — the second, malformed one vanished. Fail-open in a gate
        whose job is to keep an invented sentence from going out with a real person's
        name on it.
        Per SEGMENT solves both: internal bold remains content of the segment that ends
        in a strict attribution, and a segment that does not end in a strict attribution
        is judged on its own.
        """
        if not seg:
            # Purely defensive guard, and the mutation audit confirms it: neutralizing it
            # breaks no test, because `any()` over an empty list is already False. It
            # stays for readability, not semantics — and this note exists so the next
            # auditor doesn't waste time trying to write a test that doesn't exist.
            return
        if any(ATTRIB_LOOSE_RE.search(l) for l in seg):
            bad.append(("malformed_attribution", seg[-1].strip()))

    for is_quote, body in _quote_lines(report_md):
        if is_quote:
            segment.append(body)
            if ATTRIB_END_RE.search(body):
                segment = []   # quote closed by a strict attribution: in order
            continue

        ln = body
        flush(segment); segment = []
        # Attribution in PROSE: quote typography without being a quote. Anchored at the
        # END of the line, like a real attribution — the loose `ATTRIB_LOOSE_RE` matched
        # common mid-sentence emphasis ("discussed — **at length** — the roadmap") and
        # flagged correct text red. A gate that errs like this teaches people to ignore
        # it, and then the real red slips through with it.
        if ATTRIB_END_RE.search(ln.rstrip()):
            bad.append(("attribution_outside_quote", ln.strip()))
    flush(segment)
    return bad


def verify(report_md: str, cells_dir: Path) -> list[dict]:
    corpus = cell_corpus(cells_dir)
    findings = []
    for status, ln in _malformed_attributions(report_md):
        findings.append({"type": "quote", "advisor": "?", "status": status,
                         "where": "", "quote": ln[:120]})
    for text, name in _joined_quotes(report_md):
        qnorm = normalize(text)
        advisor = _advisor_for(name, corpus.keys())
        if len(qnorm) < MIN_QUOTE:
            findings.append({"type": "quote", "advisor": advisor or name,
                             "status": "too_short_to_verify", "where": "",
                             "quote": text[:120]})
            continue
        status, where = _match(qnorm, corpus, advisor)
        findings.append({"type": "quote", "advisor": advisor or name, "status": status,
                         "where": where, "quote": text[:120]})
    # §4 epigraphs (contractually verbatim; absence = FAILURE, never a skip)
    sec4 = re.search(r"## §4(.*?)(?=\n## §|\Z)", report_md, re.DOTALL)
    if sec4:
        for h, b in re.findall(r"### (4\.\d[^\n]*)\n(.*?)(?=\n### |\Z)", sec4.group(1),
                               re.DOTALL):
            advisor = _advisor_for(h, corpus.keys())
            m = re.search(r'\*["“]([^*]+?)["”]\*', b, re.DOTALL)  # tolerates a broken epigraph
            if not m:
                findings.append({"type": "epigraph", "advisor": advisor or h[:20],
                                 "status": "missing_epigraph", "where": "",
                                 "quote": h[:120]})
                continue
            qnorm = normalize(re.sub(r"\s+", " ", m.group(1)))
            status, where = _match(qnorm, corpus, advisor)
            findings.append({"type": "epigraph", "advisor": advisor or h[:20],
                             "status": status, "where": where, "quote": m.group(1)[:120]})
    return findings


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: qverify.py <report.md> <cells_dir>")
        return 2
    report, cells_dir = Path(sys.argv[1]), Path(sys.argv[2])
    if not report.exists() or not cells_dir.is_dir():
        print(f"QUOTE VERIFICATION RED: invalid path ({report} / {cells_dir})")
        return 1
    findings = verify(report.read_text(), cells_dir)
    bad = [f for f in findings if f["status"] != "verified"]
    ok = len(findings) - len(bad)
    if bad:
        print(f"QUOTE VERIFICATION RED — {len(bad)} of {len(findings)} not verified:")
        for f in bad:
            extra = f" (matched in '{f['where']}')" if f["status"] == "divergent_attribution" else ""
            print(f"  ✗ [{f['type']}|{f['advisor']}|{f['status']}]{extra} \"{f['quote']}\"")
        print("Fix to the card's verbatim (or remove) and re-run. "
              "An unverified quote does not reach the decision-maker.")
        return 1
    if not findings and ATTRIB_LOOSE_RE.search(report.read_text()):
        # "GREEN — 0/0" on a dossier THAT HAS attributions means the verifier understood
        # none of them, not that they are all correct. An empty green is a false green.
        print("QUOTE VERIFICATION RED: the dossier has attributed quotes and NONE "
              "were extracted — the attribution form does not match the contract "
              '(> "text." — **Name** (simulated lens · <model>)).')
        return 1
    print(f"QUOTE VERIFICATION GREEN — {ok}/{len(findings)} verified by code.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
