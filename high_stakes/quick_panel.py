#!/usr/bin/env python3
"""quick_panel.py — QUICK preset cells with prefix caching + roster from the PIN.

Contract (core/execution.md §caching + interactive-gates v2):
- the shared MATERIAL (artifact/evidence) enters as a byte-identical user PREFIX in every
  cell (short, identical, generic system) — persona/ask go in the SUFFIX. This is the
  precondition for the providers' prefix cache (a persona in the prefix breaks the cache).
- the jury comes from the instance's PIN (roster-pin.yaml): M=3 in quick; M=4 in the full
  run (extra judge).
Zero new dependencies: the pin is read by a minimal parser for the house format (key: value
and lists of inline dicts `- {k: v, ...}`), no pyyaml.
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path

from . import config

# No hard-coded path: the user's pin ($HIGH_STAKES_HOME) wins over the bundled one. The old
# `parents[2]/.claude/skills/...` only resolved inside the author's own repo.
DEFAULT_PIN = None

SYSTEM_QUICK = ("You are an advisor on a BLIND adversarial panel (no one reads anyone else). "
                "Judge the material rigorously, cite its numbers, never invent data.")

MATERIAL_HEADER = "=== SHARED MATERIAL (identical for the whole panel) ===\n"
MATERIAL_FOOTER = "\n=== END OF MATERIAL ===\n\n"


def _clean(v: str):
    """Scalar value: strips quotes; true/false become bool (everything else stays a string)."""
    v = v.strip().strip("'\"")
    if v.lower() == "true":
        return True
    if v.lower() == "false":
        return False
    return v


def _strip_comment(line: str) -> str:
    """Removes a comment outside quotes (a '#' inside a quoted value is preserved)."""
    in_q = None
    for i, ch in enumerate(line):
        if in_q:
            if ch == in_q:
                in_q = None
        elif ch in "'\"":
            in_q = ch
        elif ch == "#":
            return line[:i]
    return line


def _parse_inline_dict(s: str) -> dict:
    """`{model: x, family: y, reasoning: off}` -> dict (cleaned scalars)."""
    out = {}
    for part in s.strip().strip("{}").split(","):
        if ":" in part:
            k, v = part.split(":", 1)
            out[k.strip()] = _clean(v)
    return out


def load_pin(path: Path | None = None) -> dict:
    """Reads roster-pin.yaml (house format). Returns a dict with quick_judges (list of dicts),
    full_extra_judge, refuter, chairman, pinned (date), ttl_days (int)."""
    path = Path(path) if path else config.pin_path()
    pin: dict = {"quick_judges": []}
    cur_list = None
    for raw in path.read_text().splitlines():
        line = _strip_comment(raw).rstrip()
        if not line.strip():
            continue
        if re.match(r"^quick_judges:\s*$", line):
            cur_list = "quick_judges"
            continue
        m = re.match(r"^\s+-\s+(\{.*\})\s*$", line)
        if m and cur_list:
            pin[cur_list].append(_parse_inline_dict(m.group(1)))
            continue
        m = re.match(r"^(\w+):\s*(\{.*\})\s*$", line)
        if m:
            cur_list = None
            pin[m.group(1)] = _parse_inline_dict(m.group(2))
            continue
        m = re.match(r"^(\w+):\s*(.+?)\s*$", line)
        if m:
            cur_list = None
            pin[m.group(1)] = _clean(m.group(2))
    pin["ttl_days"] = int(pin.get("ttl_days", 30))
    return pin


def pin_expired(pin: dict, today: date | None = None) -> bool:
    """True if the pin has expired (floor-check trigger — methodology §3a-ter).

    A missing or unreadable date counts as EXPIRED, never as an error: taking the run down
    because of a typo in a config file would be worse, and "expired" is the safe direction —
    it forces re-verifying the roster instead of silently trusting it."""
    try:
        pinned = date.fromisoformat(str(pin.get("pinned", "")))
    except (ValueError, TypeError):
        return True
    try:
        ttl = int(pin.get("ttl_days", 0))
    except (ValueError, TypeError):
        return True
    return (today or date.today()) > pinned + timedelta(days=ttl)


def _request_for(judge: dict, max_tokens: int, timeout: int) -> dict:
    req = {"max_tokens": max_tokens, "temperature": 0.7, "timeout": timeout}
    if judge.get("reasoning") == "off":
        req["extra_body"] = {"reasoning": {"enabled": False}}
    return req


def build_quick_tasks(material: str, personas: dict[str, str], ask_builder, parse,
                      pin: dict | None = None, full: bool = False,
                      max_tokens: int = 8000, timeout: int = 1200,
                      prompt_version: str = "quick-v1") -> list[dict]:
    """Builds the quick cells: personas = {key: persona-suffix-WITHOUT-the-material};
    ask_builder(key) -> the ask/schema text for that archetype. The material enters ONCE,
    as an identical prefix. `full=True` adds the pin's extra judge (M=4)."""
    pin = pin or load_pin()
    judges = list(pin["quick_judges"])
    if full and pin.get("full_extra_judge"):
        judges.append(pin["full_extra_judge"])
    prefix = MATERIAL_HEADER + material + MATERIAL_FOOTER
    tasks = []
    for key, persona_suffix in personas.items():
        for j in judges:
            mkey = j["model"].split("/")[-1]  # unique per judge (a repeated family does not collide)
            tasks.append({
                "cell_id": f"cell_{key}_{mkey}",
                "model": j["model"],
                "messages": [
                    {"role": "system", "content": SYSTEM_QUICK},
                    {"role": "user", "content": prefix + persona_suffix + "\n\n" + ask_builder(key)},
                ],
                "parse": parse,
                "request": _request_for(j, max_tokens, timeout),
                "meta": {"advisor": key, "model_key": mkey, "family": j.get("family", ""),
                         # "role" is a provenance field shared with xverify.py.
                         "role": "coverage",
                         "prompt_version": prompt_version},
            })
    return tasks
