#!/usr/bin/env python3
"""Checks that the README's numbers match the reality of the repo.

Why it exists: the test count in the README has been wrong TWICE already (it said 219,
then 191, when the numbers were something else). Updating by hand does not fix it — the
number changes with every new suite and nobody remembers. And it is not nitpicking: it is
the first verifiable claim anyone reads in the repository. A wrong number there is the
signature of a project that does not check what it claims, in an engine whose entire
argument is checking what is claimed.

It stays OUT of the suite on purpose: running the suites from inside a suite recurses.

Usage:  python3 tools/check-readme-numbers.py      → exit 0 = matches; 1 = does not.
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATTERN = r"\*\*(\d+) tests across (\d+) suites — all (\d+) modules"


def main() -> int:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    m = re.search(PATTERN, readme)
    if not m:
        print("README: could not find the coverage phrase "
              "('**N tests across M suites — all K modules').")
        return 1

    suites = sorted((ROOT / "tests").glob("test_*.py"))
    tests = 0
    for t in suites:
        r = subprocess.run([sys.executable, "-m", f"tests.{t.stem}"],
                           cwd=ROOT, capture_output=True, text=True)
        mm = re.search(r"(\d+)/(\d+) tests ok", r.stdout)
        if not mm:
            print(f"could not count {t.stem} (did the suite print its total?)")
            return 1
        tests += int(mm.group(2))
    modules = [p for p in (ROOT / "high_stakes").glob("*.py") if p.stem != "__init__"]

    actual = (tests, len(suites), len(modules))
    stated = tuple(int(x) for x in m.groups())
    if stated != actual:
        print(f"README OUT OF DATE: it says {stated[0]} tests / {stated[1]} suites / "
              f"{stated[2]} modules; reality is {actual[0]} / {actual[1]} / {actual[2]}.")
        return 1
    print(f"README matches: {actual[0]} tests · {actual[1]} suites · {actual[2]} modules.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
