"""Where the package's resources are.

It exists for one reason only: NOTHING in the engine may compute a path relative to the
repo layout of whoever wrote it. Outside that repo, `parents[2] / ".claude" / ...` points
at nothing — and the error only shows up at render time, after the money is spent. Here
the package answers where it itself lives.

Command-line use (this is how the adapter finds the contracts):
    python -m high_stakes.paths core
    python -m high_stakes.paths assets
"""
from __future__ import annotations

import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
CORE = PACKAGE_ROOT / "core"
ASSETS = PACKAGE_ROOT / "assets"

# Install root (= plugin root): where the boards/ and examples/ that ship with the
# distribution live. It is read-only — what the user edits lives in their HIGH_STAKES_HOME.
INSTALL_ROOT = PACKAGE_ROOT.parent
SHIPPED_BOARDS = INSTALL_ROOT / "boards"
EXAMPLES = INSTALL_ROOT / "examples"

_NAMES = {
    "package": PACKAGE_ROOT, "core": CORE, "assets": ASSETS,
    "install": INSTALL_ROOT, "boards": SHIPPED_BOARDS, "examples": EXAMPLES,
}


def get(name: str) -> Path:
    if name not in _NAMES:
        raise KeyError(f"unknown path: {name!r} (use one of {sorted(_NAMES)})")
    return _NAMES[name]


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] in {"-h", "--help"}:
        print(f"usage: python -m high_stakes.paths <{'|'.join(sorted(_NAMES))}>")
        return 2
    try:
        print(get(argv[1]))
    except KeyError as e:
        print(e, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
