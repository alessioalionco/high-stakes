"""
aggregate.py — generic DETERMINISTIC aggregations (generalizes layer 1 of the
prototype): counts by field, mean+spread by dimension,
noise floor. Zero LLM, zero case-specific code.
"""

from __future__ import annotations

import math
import statistics
from collections import Counter
from typing import Any, Callable, Iterable


def is_num(x: Any) -> bool:
    """A REAL number: rejects bool (float(True)==1.0 is a trap) and
    non-finites (nan/inf would silently ruin mean/spread)."""
    if isinstance(x, bool):
        return False
    try:
        return math.isfinite(float(x))
    except (TypeError, ValueError):
        return False


def stats(values: list[float]) -> dict:
    """mean/min/max/spread/stdev of a numeric list (spread = divergence signal)."""
    if not values:
        return {"n": 0}
    return {
        "n": len(values),
        "mean": round(statistics.mean(values), 1),
        "min": min(values),
        "max": max(values),
        "spread": round((max(values) - min(values)), 1),
        "stdev": round(statistics.pstdev(values), 2) if len(values) > 1 else 0.0,
    }


def count_by(records: Iterable[dict], getter: Callable[[dict], Any]) -> Counter:
    """Count by field value (getter). None counts as None (does not vanish)."""
    return Counter(getter(r) for r in records)


def dim_stats(records: Iterable[dict], dims: list[str],
              getter: Callable[[dict, str], Any]) -> dict[str, dict]:
    """mean+spread by dimension: getter(record, dim) -> value (non-numeric ignored)."""
    recs = list(records)
    out = {}
    for d in dims:
        vals = [float(getter(r, d)) for r in recs if is_num(getter(r, d))]
        out[d] = stats(vals)
    return out


def paired_abs_deltas(main: list[dict], rerun: list[dict],
                      key_fn: Callable[[dict], Any],
                      value_fn: Callable[[dict], Any]) -> list[float]:
    """Absolute deltas between pairs (same key) of two sets of records.
    Core of the noise floor: identical re-run -> how much the value moves on its own."""
    main_i = {key_fn(r): r for r in main}
    rerun_i = {key_fn(r): r for r in rerun}
    deltas = []
    for k, b in rerun_i.items():
        a = main_i.get(k)
        if a is None:
            continue
        va, vb = value_fn(a), value_fn(b)
        if is_num(va) and is_num(vb):
            deltas.append(abs(float(va) - float(vb)))
    return deltas


def noise_floor(main: list[dict], rerun: list[dict],
                key_fn: Callable[[dict], Any],
                value_fns: dict[str, Callable[[dict], Any]]) -> dict:
    """Generic noise floor: for each named metric, mean of the |deltas| between
    the main run and the identical re-run. Only a delta ABOVE the floor counts as signal."""
    n_pairs = len({key_fn(r) for r in rerun} & {key_fn(r) for r in main})
    out: dict[str, Any] = {"n_pairs": n_pairs}
    for name, vfn in value_fns.items():
        deltas = paired_abs_deltas(main, rerun, key_fn, vfn)
        out[name] = round(statistics.mean(deltas), 2) if deltas else None
    return out


def jaccard(a: set, b: set) -> float | None:
    """Set stability (e.g. cards) between run and re-run."""
    if not a and not b:
        return None
    return round(len(a & b) / len(a | b), 2)
