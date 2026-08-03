#!/usr/bin/env python3
"""test_xverify.py — executable suite for X-verify (convention: PASS/exit≠0)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from high_stakes.or_client import SchemaInvalid  # noqa: E402
from high_stakes.xverify import _parse, build_refute_tasks  # noqa: E402


def case(name, cond):
    print(("PASS" if cond else "FAIL"), name)
    return cond


def fails(text, frag):
    try:
        _parse(text)
        return False
    except SchemaInvalid as e:
        return frag in str(e)


GOOD = ('{"case_against": "The material shows 2.6x with named deals.", '
        '"what_survives": "The missing error margin still stands.", '
        '"new_facts": [{"fact": "15m runway in Q4", "where": "quarterly board"}], '
        '"suggested_verdict": "PARTIAL"}')


def main() -> int:
    tasks = build_refute_tasks("MATERIAL X", {"i1": "claim one", "i2": "claim two"})
    results = [
        case("parse ok with concession", _parse(GOOD)["suggested_verdict"] == "PARTIAL"),
        case("code fence tolerated", bool(_parse("```json\n" + GOOD + "\n```")["new_facts"])),
        case("REGRESSION X-V1: empty concession FAILS (anti-advocate-bias)",
             fails(GOOD.replace("The missing error margin still stands.", ""), "what_survives")),
        case("verdict outside the enum fails",
             fails(GOOD.replace("PARTIAL", "DESTROYED"), "suggested_verdict")),
        case("new_facts optional (default [])",
             _parse(GOOD.replace('"new_facts": [{"fact": "15m runway in Q4", "where": "quarterly board"}], ', ""))["new_facts"] == []),
        case("1 task per item, material in user message, unique ids",
             len(tasks) == 2 and {t["cell_id"] for t in tasks} == {"refuter_i1", "refuter_i2"}
             and all("MATERIAL X" in t["messages"][1]["content"] for t in tasks)),
        case("truncation REGRESSION: default max_tokens high (>=8000)",
             all(t["request"]["max_tokens"] >= 8000 for t in tasks)),
    ]
    print(f"{sum(results)}/{len(results)} tests ok")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
