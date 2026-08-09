#!/usr/bin/env python3
"""test_evidence.py — executable suite for evidence (this project's convention).

What is locked down here:
  - `load_reuse` does not read outside `base_dir` — not via `..`, not via an absolute
    path, not via a FILE SYMLINK. This is the path with a real adversary: reused material
    enters the prefix of ALL paid cells and goes to the external provider;
  - the DOMAIN blocklist on the answer marks `leak_suspect` (never silent), and the mark
    is RE-derived with the CURRENT blocklist when reading from the cache — a tampered or
    stale cache saying "clean" does not pass;
  - per-ask cache: the same policy does not re-bill, a new policy invalidates and
    re-fetches.

There is no egress no-leak test anymore: the guard was REMOVED. The why is in the
header of `high_stakes/evidence.py` — there was no adversary on that path, and
Gate B (a human seeing what goes out) is the lock that stayed.
"""
import json
import shutil
import sys
import tempfile
from pathlib import Path

from high_stakes.evidence import (_cache_filename, body_leak_suspect,
                                  is_blocked_domain, load_reuse, run_asks,
                                  tier_for, write_pack)
from high_stakes.flow_gate import RECEIPT_FILENAME


class SpyClient:
    """Fake client that COUNTS dispatches — this is how cache hit vs. re-fetch is measured."""

    def __init__(self, text="answer", citations=None):
        self.calls = 0
        self._text = text
        self._citations = citations or ["https://www.gartner.com/x"]

    def chat(self, model, messages, **kw):
        self.calls += 1
        return {"text": self._text, "cost_usd": 0.01, "provider": "spy",
                "raw": {"citations": self._citations}}


ASK = {"id": "a1", "nature": "public",
       "query": "what is the median NRR of B2B SaaS in 2026?"}


def main() -> int:
    tmp = Path(tempfile.mkdtemp())
    results: list[bool] = []

    def case(name, cond):
        print(("PASS " if cond else "FAIL ") + name)
        results.append(bool(cond))

    try:
        # ---- REGRESSION: reuse must not read outside base_dir ----
        # Reused material enters the prefix of ALL paid cells and goes to the external
        # provider. The review read OPENROUTER_API_KEY through here — this path HAS an
        # adversary.
        base = tmp / "runbase"
        (base / "mat").mkdir(parents=True)
        (base / "mat" / "ok.md").write_text("legitimate run material")
        (tmp / "secret.md").write_text("OPENROUTER_API_KEY=sk-must-not-leak")
        case("reuse inside base_dir works",
             "legitimate run material" in load_reuse({"id": "r", "reuse": "mat"}, base)["answer"])
        for escape, desc in [("..", "escapes via .."), ("/etc", "is an absolute path")]:
            try:
                load_reuse({"id": "r", "reuse": escape}, base)
                case(f"REGRESSION: reuse that {desc} is REFUSED", False)
            except ValueError:
                case(f"REGRESSION: reuse that {desc} is REFUSED", True)

        # REGRESSION: containing the directory was not enough — read_text() follows FILE symlinks
        import os as _os
        (base / "mat" / "link.md").parent.mkdir(parents=True, exist_ok=True)
        _os.symlink(tmp / "secret.md", base / "mat" / "stolen.md")
        try:
            r = load_reuse({"id": "r", "reuse": "mat"}, base)
            case("REGRESSION: a FILE symlink pointing outside is REFUSED",
                 "sk-must-not-leak" not in r["answer"])
        except ValueError:
            case("REGRESSION: a FILE symlink pointing outside is REFUSED", True)

        # ---- run_asks: cache hit does not re-bill, and re-derives leak_suspect ----
        cache = tmp / "c2"
        spy = SpyClient(citations=["https://blog.competitor.com/post"])
        items = run_asks(spy, [ASK], evidence_model="m", cache_dir=cache,
                         base_dir=tmp, domain_blocklist=None)
        case("without a blocklist, the item is not suspect", items[0]["leak_suspect"] is False)
        case("the answer was cached on disk", any(cache.glob("*.json")))

        # a DIFFERENT blocklist = different cache key = re-fetch (not a cache hit).
        # That is the design: a new policy never inherits an answer judged by the old one.
        before = spy.calls
        items = run_asks(spy, [ASK], evidence_model="m", cache_dir=cache,
                         base_dir=tmp, domain_blocklist=["competitor.com"])
        case("a new blocklist invalidates the cache and re-fetches", spy.calls == before + 1)
        case("F7: a blocked-domain citation marks leak_suspect",
             items[0]["leak_suspect"] is True
             and items[0]["citations"][0]["blocked"] is True)

        # SAME policy -> a true cache hit: no call spent, and leak_suspect is not lost
        before = spy.calls
        items = run_asks(spy, [ASK], evidence_model="m", cache_dir=cache,
                         base_dir=tmp, domain_blocklist=["competitor.com"])
        case("cache hit (same policy) spends no new call", spy.calls == before)
        case("T6: leak_suspect survives the cache round-trip",
             items[0]["leak_suspect"] is True
             and items[0]["citations"][0]["blocked"] is True)

        # the re-derivation (run_asks cache-read path) is the net: a tampered/stale cache
        # saying "clean" does not pass — the CURRENT blocklist is re-applied on read.
        hit = max(cache.glob("*.json"), key=lambda p: p.stat().st_mtime)
        d = json.loads(hit.read_text())
        d["leak_suspect"] = False
        d["citations"][0]["blocked"] = False
        hit.write_text(json.dumps(d))
        items = run_asks(spy, [ASK], evidence_model="m", cache_dir=cache,
                         base_dir=tmp, domain_blocklist=["competitor.com"])
        case("T6: a cache saying 'clean' is NOT accepted — the current blocklist is re-applied",
             items[0]["leak_suspect"] is True
             and items[0]["citations"][0]["blocked"] is True)

        # a corrupted cache re-fetches instead of crashing
        for p in cache.glob("*.json"):
            p.write_text("{ not json")
        spy2 = SpyClient()
        items = run_asks(spy2, [ASK], evidence_model="m", cache_dir=cache,
                         base_dir=tmp)
        case("corrupted cache re-fetches (no crash)", spy2.calls == 1 and len(items) == 1)

        # ---- the body mentions a blocked domain even without a formal citation ----
        case("F7: a body citing a blocked domain becomes leak_suspect",
             body_leak_suspect("according to competitor.com the number is X", ["competitor.com"]))
        case("F7: without a blocklist, the body is never suspect",
             body_leak_suspect("any text", None) is False)
        case("F7: is_blocked_domain is case-insensitive",
             is_blocked_domain("https://WWW.Competitor.COM/a", ["competitor.com"]))

        # ---- tier: an unknown domain does not ground a number ----
        case("unknown domain tier is 'low' (conservative)",
             tier_for("https://random-site.xyz/post") == "low")

        # ---- write-guard: an EMPTY answer never becomes cache ----
        # (real failure class: a dead research leg — $0, 0 sources — cached as a valid
        # item; every re-run then cache-hits the defect)
        cache5 = tmp / "c5"
        spy_empty = SpyClient(text="   ")
        items = run_asks(spy_empty, [ASK], evidence_model="m", cache_dir=cache5,
                         base_dir=tmp)
        case("empty answer comes back FLAGGED failed", items[0].get("failed") is True)
        case("empty answer is NOT cached", not list(cache5.glob("*.json")))
        spy_ok = SpyClient(text="good answer")
        items = run_asks(spy_ok, [ASK], evidence_model="m", cache_dir=cache5,
                         base_dir=tmp)
        case("re-run after the failure RE-FETCHES (no cache-hit on the defect)",
             spy_ok.calls == 1 and items[0]["answer"] == "good answer")

        # ---- read-guard: an ALREADY poisoned cache (empty answer) re-fetches ----
        cache6 = tmp / "c6"
        cache6.mkdir(parents=True)
        poisoned = {"id": ASK["id"], "nature": ASK["nature"], "query": ASK["query"],
                    "answer": "", "citations": [], "leak_suspect": False,
                    "cost_usd": 0.0, "provider": "spy", "timestamp": "t"}
        (cache6 / _cache_filename(ASK, "m", None)).write_text(json.dumps(poisoned))
        spy_cure = SpyClient(text="cured answer")
        items = run_asks(spy_cure, [ASK], evidence_model="m", cache_dir=cache6,
                         base_dir=tmp)
        case("poisoned cache (empty answer) re-fetches on read",
             spy_cure.calls == 1 and items[0]["answer"] == "cured answer")

        # ---- reuse with MISSING material = failed ask (not counted ok in receipt) ----
        missing = load_reuse({"id": "r1", "nature": "public",
                              "reuse": "dir-that-does-not-exist"}, tmp)
        case("reuse without material comes FLAGGED failed (a placeholder is not evidence)",
             missing.get("failed") is True)

        # ---- write_pack: declared gap + receipt with sha and counts ----
        import hashlib
        pack_dir = tmp / "run" / "research"
        pack_path = pack_dir / "evidence-pack.md"
        ok_item = {"id": "ok1", "nature": "public", "query": "q1",
                   "answer": "grounded datum", "citations": [], "cost_usd": 0.01}
        bad_item = {"id": "bad1", "nature": "public", "query": "q2",
                    "answer": "", "failed": True, "citations": [], "cost_usd": 0.0}
        write_pack([ok_item, bad_item], pack_path, "test pack")
        pack_text = pack_path.read_text()
        case("a failed ask becomes a DECLARED GAP in the pack (never a silent hole)",
             "DECLARED GAP" in pack_text and "bad1" in pack_text)
        receipt = json.loads((pack_dir / RECEIPT_FILENAME).read_text())
        case("write_pack emits the receipt with the right counts",
             receipt["asks_ok"] == 1 and receipt["asks_failed"] == 1)
        case("the receipt sha matches the pack on disk",
             receipt["pack_sha256"]
             == hashlib.sha256(pack_text.encode("utf-8")).hexdigest())

        print(f"{sum(results)}/{len(results)} tests ok")
        return 0 if all(results) else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
