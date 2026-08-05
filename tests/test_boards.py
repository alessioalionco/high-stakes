#!/usr/bin/env python3
"""test_boards.py — the shipped lens pool must be RESOLVABLE by the quote verifier.

Why this exists: both ways of getting a lens name wrong fail SILENTLY, and both produce a
red gate on a dossier that is actually correct.

1. `qverify._advisor_for` matches a lens key against the display name by substring, AFTER
   normalization — and normalization does not turn a hyphen into a space. A key written
   `unit-economist` never matches `The Unit Economist`: it resolves to None and every quote
   from that lens comes back `unverified`. This was caught in review while the archetype
   migration was still on paper; the plan had specified kebab-case keys.
2. Role tokens resolve BEFORE lens keys. A lens named "The Generalist Operator" reads as the
   generalist role, and every quote of that lens is flagged `divergent_attribution` — a real
   sentence, correctly attributed, reported as fabricated.

Both are properties of the DATA, so they are tested against the data, not against a
hand-copied list that would drift from `boards/saas.md`.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from high_stakes import paths                                  # noqa: E402
from high_stakes.qverify import ROLE_KEYS, _advisor_for, normalize  # noqa: E402

results = []


def case(name, ok, detail=""):
    results.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail and not ok else ""))


# `| N | **The Lens** | `key` | axis | tone |`
ROW = re.compile(r"^\|\s*\d+\s*\|\s*\*\*(?P<name>[^*]+)\*\*\s*\|\s*`(?P<key>[^`]+)`\s*\|")


def lenses(board: Path):
    return [(m.group("name").strip(), m.group("key").strip())
            for line in board.read_text().splitlines()
            if (m := ROW.match(line))]


def main() -> int:
    board = paths.SHIPPED_BOARDS / "saas.md"
    case("the shipped SaaS lens pool exists", board.exists())
    if not board.exists():
        print(f"{sum(results)}/{len(results)} tests ok")
        return 1

    rows = lenses(board)
    # A parser that silently matches nothing would make every case below vacuously true —
    # the same empty-green failure the quote verifier itself guards against.
    case("the roster table parses (non-empty)", len(rows) >= 5, f"parsed {len(rows)} rows")

    for name, key in rows:
        case(f"'{key}' resolves from '{name}'",
             _advisor_for(name, [key]) == key,
             f"_advisor_for -> {_advisor_for(name, [key])!r}; "
             "the key must be a normalized substring of the display name (hyphen != space)")

    role_tokens = [tok for tok, _ in ROLE_KEYS]
    for name, key in rows:
        hit = [t for t in role_tokens if t in normalize(name) or t in normalize(key)]
        case(f"'{name}' carries no role token", not hit, f"contains {hit}")

    keys = [k for _, k in rows]
    case("no lens key is a duplicate", len(keys) == len(set(keys)))

    # Longest-first ordering inside _advisor_for (qverify.py) had no coverage at all: with a
    # key that is a prefix of another, the short one would win and silently mis-attribute.
    case("a longer key is not shadowed by a shorter key that is its prefix",
         _advisor_for("The Loop Architect Emeritus",
                      ["loop architect", "loop architect emeritus"])
         == "loop architect emeritus")

    print(f"{sum(results)}/{len(results)} tests ok")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
