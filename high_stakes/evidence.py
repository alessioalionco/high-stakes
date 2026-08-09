"""
evidence.py — generic evidence layer (sonar deep-research via OpenRouter).

Extracted from the prototype. EVERYTHING case-specific became a PARAMETER
(rule 1A′): evidence model, cache/pack paths, domain blocklist —
they live in the experiment config, never here.

EGRESS — why there is NO content filter on the way out
-------------------------------------------------------
This module once had a `check_no_leak`: a denylist of sensitive terms that
refused the query if it contained any of them. It was REMOVED, and the removal
is the decision, not a pending item.

The guard protected the owner's data from the owner. Whoever writes the query,
owns the material and runs the tool is the SAME person; the providers are chosen
by them and the product's eligibility criterion already says, up front, that
using this means sending material to multiple providers. There is no adversary
on this path — and without an adversary, hardening against evasion (homoglyphs,
zero-width, hyphen-split tokens) is pure cost.

The cost was measured, not estimated: four rounds of adversarial review
concentrated on that matcher, each closing one evasion class and opening
another. What it actually produced was false refusal on legitimate queries —
`["São Paulo"]` refused "climate in São Tomé", `["C++"]` refused "the C language" —
and a false refusal here is worse than it looks: it breaks the expensive leg of
the run (the deep research) and teaches the user to empty their own denylist.

What stays in its place, and is stronger: **Gate B**
(`core/sections/interactive-gates.md`) shows the user exactly what will go
out and asks for an OK before firing. A human deciding with the list in front
of them is worth more than a substring heuristic — and it is honest about who
is deciding.

What this module STILL protects (and these are other problems, real ones): the
domain blocklist on the response (`leak_suspect`), and `load_reuse`, which
refuses paths outside `base_dir` — including via symlink. That one does have an
adversary: a file that enters the prefix of every paid cell.

Gates:
  - per-ask cache in `cache_dir`: a re-run does not re-bill.
  - tiering by domain (primary > analyst > press > vendor/blog) — generic.
  - `domain_blocklist` marks citations of forbidden source domains
    (blocked=True) and the item gets leak_suspect=True — the consumer excludes
    it from accuracy and reports the flag (never silent).
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from .flow_gate import RECEIPT_FILENAME
from .naming import SAFE_FILENAME as _SAFE_FILENAME


# trust hierarchy by domain (primary > analyst > press > vendor/blog)
_TIER_RULES = [
    ("high", ["sec.gov", "arxiv.org", "nber.org", ".edu", "iso.org", "nist.gov"]),
    ("medium", ["gartner.com", "forrester.com", "bvp.com", "a16z.com",
                "battery.com", "scalevp.com", "kbcm.com", "meritechcapital",
                "iconiq", "bcg.com", "saas-capital.com", "benchmarkit.ai"]),
    ("press", ["bloomberg.com", "ft.com", "wsj.com", "reuters.com",
               "techcrunch.com", "theinformation.com", "fortune.com"]),
    ("low", ["medium.com", "substack.com", "reddit.com", "linkedin.com",
             "blog.", "/blog"]),
]

_DEFAULT_SYSTEM = (
    "You are a rigorous research analyst. Answer the question "
    "with concrete, sourced facts and numbers. Prefer primary "
    "sources, recognized analysts, and audited data over blogs. "
    "Always cite sources with URLs. Be concise and factual."
)


def tier_for(url: str) -> str:
    u = (url or "").lower()
    for tier, needles in _TIER_RULES:
        if any(n in u for n in needles):
            return tier
    return "low"  # conservative default: an unknown domain does not ground a number


def is_blocked_domain(url: str, domain_blocklist: list[str]) -> bool:
    """True if the URL matches (substring, case-insensitive) a blocked domain."""
    u = (url or "").lower()
    return any(b.lower() in u for b in domain_blocklist or [])


def body_leak_suspect(text: str, domain_blocklist: list[str] | None) -> bool:
    """The BODY of the answer mentions a blocked domain (even without a
    formal citation) -> leak_suspect."""
    t = (text or "").lower()
    return any(b.lower() in t for b in domain_blocklist or [])


def _cache_filename(ask: dict, evidence_model: str,
                    domain_blocklist: list[str] | None) -> str:
    """Cache name = sanitized id + hash10(query+model+blocklist):
    any input change INVALIDATES the cache (never reuses a stale answer)."""
    blob = json.dumps({
        "query": ask.get("query"),
        "evidence_model": evidence_model,
        "blocklist": sorted(domain_blocklist or []),
    }, ensure_ascii=False, sort_keys=True)
    h = hashlib.sha256(blob.encode("utf-8")).hexdigest()[:10]
    safe_id = _SAFE_FILENAME.sub("-", str(ask["id"]))
    return f"{safe_id}__{h}.json"


def extract_citations(raw: dict, domain_blocklist: list[str] | None = None) -> list[dict]:
    """Citations from the sonar answer (`citations` field or annotations) + tier + blocking."""
    cites: list[dict] = []
    for c in raw.get("citations") or []:
        url = c if isinstance(c, str) else c.get("url", "")
        if url:
            cites.append({"url": url, "tier": tier_for(url),
                          "blocked": is_blocked_domain(url, domain_blocklist or [])})
    # annotations (url_citation format) as fallback
    for choice in raw.get("choices", []):
        for ann in (choice.get("message", {}) or {}).get("annotations", []) or []:
            url = (ann.get("url_citation") or {}).get("url", "")
            if url and url not in {x["url"] for x in cites}:
                cites.append({"url": url, "tier": tier_for(url),
                              "blocked": is_blocked_domain(url, domain_blocklist or [])})
    return cites


def research(client, ask: dict, *, evidence_model: str,
             domain_blocklist: list[str] | None = None,
             system_prompt: str = _DEFAULT_SYSTEM,
             max_tokens: int = 4000, temperature: float = 0.2,
             timeout: int = 600) -> dict:
    """Runs 1 ask via deep-research. Returns an evidence-pack item.

    There is no content filter on the way out, and that is on purpose — see the egress
    note at the top of this module. What enters the query is what the material's owner
    chose to send; the decision to send belongs to Gate B, with a human looking.
    """
    query = ask["query"]

    out = client.chat(
        evidence_model,
        [{"role": "system", "content": system_prompt},
         {"role": "user", "content": query}],
        max_tokens=max_tokens,
        temperature=temperature,
        timeout=timeout,
    )
    citations = extract_citations(out["raw"], domain_blocklist)
    return {
        "id": ask["id"],
        "nature": ask.get("nature"),
        "query": query,
        "answer": out["text"],
        "citations": citations,
        # blocked citation OR body mentioning a blocked domain
        "leak_suspect": (any(c.get("blocked") for c in citations)
                         or body_leak_suspect(out["text"], domain_blocklist)),
        "cost_usd": out["cost_usd"],
        "provider": out["provider"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def load_reuse(ask: dict, base_dir: Path, domain_blocklist: list[str] | None = None) -> dict:
    """Ask with `reuse`: reads local material (no call spent). Path relative to base_dir."""
    base = Path(base_dir).resolve()
    target = Path(ask["reuse"])
    # `base / "/abs"` DISCARDS the base; `../..` escapes. The content read here enters the
    # shared prefix of every paid cell and goes to the external provider — and
    # `check_no_leak` never sees it. Confirmed in review: it read OPENROUTER_API_KEY from
    # outside.
    if target.is_absolute():
        raise ValueError(f"reuse cannot be an absolute path: {ask['reuse']!r}")
    reuse_dir = (base / target).resolve()
    try:
        reuse_dir.relative_to(base)
    except ValueError:
        raise ValueError(
            f"reuse {ask['reuse']!r} escapes {base} — reused material enters the paid "
            "prompt without going through no-leak.") from None
    # Containing the directory is not enough: `read_text()` follows FILE symlinks, and a
    # *.md inside the base pointing outside was read in full. The review reproduced this,
    # leaking OPENROUTER_API_KEY exactly here.
    files = []
    if reuse_dir.exists():
        for f in sorted(reuse_dir.glob("*.md")):
            try:
                f.resolve().relative_to(base)
            except ValueError:
                raise ValueError(
                    f"{f} points outside {base} — reused material enters the paid "
                    "prompt without going through no-leak.") from None
            files.append(f)
    body = "\n\n".join(f"### {f.name}\n{f.read_text()[:6000]}" for f in files)
    return {
        "id": ask["id"],
        "nature": ask.get("nature"),
        "query": "(reuse of local material — no new call)",
        "answer": body or "(reuse material not found)",
        # missing material = FAILED ask (declared gap in the pack + outside the
        # receipt's asks_ok) — a placeholder must not count as grounded evidence.
        "failed": not body,
        "citations": [{"url": str(reuse_dir), "tier": "medium", "blocked": False}],
        # reused material is content like any other: if it cites a blocked domain, it is
        # suspect. It used to be a fixed False, contradicting the module's contract.
        "leak_suspect": body_leak_suspect(body, domain_blocklist),
        "cost_usd": 0.0,
        "provider": "local-reuse",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def run_asks(client, asks: list[dict], *, evidence_model: str,
             cache_dir: Path, base_dir: Path,
             domain_blocklist: list[str] | None = None,
             only_first: bool = False) -> list[dict]:
    """Runs the asks (cache keyed by id+input hash in cache_dir; `reuse` reads locally).

    Cache: filename = sanitized id + hash10(query+model+blocklist) — any change
    invalidates. Corrupted cache -> re-fetch (no crash). When READING from the cache,
    blocked/leak_suspect are RE-derived with the CURRENT blocklist."""
    cache_dir = Path(cache_dir)
    asks = asks[:1] if only_first else asks
    items = []
    for ask in asks:
        if ask.get("reuse"):
            print(f"[reuse] {ask['id']}")
            items.append(load_reuse(ask, base_dir, domain_blocklist))
            continue
        cached = cache_dir / _cache_filename(ask, evidence_model, domain_blocklist)
        if cached.exists():  # never re-bill what we already have
            try:
                item = json.loads(cached.read_text())
            except json.JSONDecodeError:
                print(f"[cache] {ask['id']}: cache CORRUPTED — re-fetching.")
                item = None
            if item is not None and not (item.get("answer") or "").strip():
                # read-guard: cache poisoned by an empty answer (a dead research leg
                # cached as valid) — re-fetch instead of re-serving the defect.
                print(f"[cache] {ask['id']}: cached answer is EMPTY — re-fetching.")
                item = None
            if item is not None:
                # re-applies the CURRENT blocklist to what came from the cache
                for c in item.get("citations", []):
                    c["blocked"] = is_blocked_domain(c.get("url", ""),
                                                     domain_blocklist or [])
                item["leak_suspect"] = (
                    any(c.get("blocked") for c in item.get("citations", []))
                    or body_leak_suspect(item.get("answer", ""), domain_blocklist))
                print(f"[cache] {ask['id']} (already on disk — no new call)")
                items.append(item)
                continue
        print(f"[sonar] {ask['id']} ... (deep research, may take 1-3min)")
        item = research(client, ask, evidence_model=evidence_model,
                        domain_blocklist=domain_blocklist)
        print(f"        cost ${item['cost_usd']:.4f} · {len(item['citations'])} sources "
              f"· provider {item['provider']}"
              + ("  ⚠️ leak_suspect" if item["leak_suspect"] else ""))
        if not (item.get("answer") or "").strip():
            # write-guard: an empty answer NEVER becomes cache (a re-run would
            # cache-hit the defect). The item stays in the list FLAGGED — write_pack
            # declares the gap.
            item["failed"] = True
            print(f"        ⚠️ {ask['id']}: EMPTY answer — not cached; the gap will "
                  "be DECLARED in the pack.")
            items.append(item)
            continue
        cache_dir.mkdir(parents=True, exist_ok=True)
        cached.write_text(json.dumps(item, indent=2))
        items.append(item)
    return items


def write_pack(items: list[dict], pack_path: Path, title: str) -> None:
    pack_path = Path(pack_path)
    pack_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# {title}",
        f"\n> Generated {datetime.now(timezone.utc).isoformat()} · RAW material, "
        "identical for all cells. Low tier does NOT ground a number.\n",
    ]
    total = 0.0
    asks_ok = asks_failed = 0
    for it in items:
        total += it["cost_usd"]
        failed = bool(it.get("failed")) or not (it.get("answer") or "").strip()
        lines.append(f"\n## {it['id']}  ·  nature: {it['nature']}")
        lines.append(f"*query:* {it['query']}")
        if failed:
            # a failed ask becomes a DECLARED gap — never a silent empty section
            # (house kill-switch: an ungrounded number → declared gap, never mute).
            asks_failed += 1
            lines.append("\n**⚠️ DECLARED GAP: ask failed — no answer.** This "
                         "dimension is NOT grounded; the panel must not invent a "
                         "number here.\n")
        else:
            asks_ok += 1
            lines.append(f"\n{it['answer']}\n")
        if it["citations"]:
            lines.append("**Sources:**")
            for c in it["citations"]:
                flag = " ⚠️BLOCKED" if c.get("blocked") else ""
                lines.append(f"- [{c['tier']}]{flag} {c['url']}")
    lines.append(f"\n---\n*total pack cost: ${total:.4f}*")
    text = "\n".join(lines)
    pack_path.write_text(text)
    # The receipt is emitted BY CODE on the mandatory assembly path — the flow gate
    # verifies sha + asks_ok before releasing the panel. No extra runner step.
    receipt = {
        "pack_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "asks_ok": asks_ok,
        "asks_failed": asks_failed,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }
    (pack_path.parent / RECEIPT_FILENAME).write_text(json.dumps(receipt, indent=2))
    print(f"\nevidence-pack written: {pack_path} · total cost ${total:.4f} "
          f"· receipt: {asks_ok} ok / {asks_failed} failed")
