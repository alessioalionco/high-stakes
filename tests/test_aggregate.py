#!/usr/bin/env python3
"""test_aggregate.py — executable suite for the deterministic aggregations.

`aggregate.py` implements the concepts the contracts use to decide how to read results:
**spread as a divergence signal** and the **noise floor** — the number that separates
"the edit helped" from "the model moved on its own". It is statistics without an LLM, and
therefore the kind of code where a mistake does not show up as a failure: it shows up as
a plausible, wrong number.
"""
import sys

from high_stakes.aggregate import (count_by, dim_stats, is_num, jaccard, noise_floor,
                                   paired_abs_deltas, stats)


def main() -> int:
    results: list[bool] = []

    def case(name, cond):
        print(("PASS " if cond else "FAIL ") + name)
        results.append(bool(cond))

    # ---- is_num: the traps it exists to avoid ----
    case("int and float are numbers", is_num(3) and is_num(2.5))
    case("REGRESSION: bool is NOT a number (float(True)==1.0 would enter the mean as 1)",
         not is_num(True) and not is_num(False))
    case("REGRESSION: nan and inf are NOT numbers (they would silently poison mean/spread)",
         not is_num(float("nan")) and not is_num(float("inf")))
    case("a numeric string IS accepted, on purpose (a model returns '4' as text)",
         is_num("4") and is_num("2.5"))
    case("None and non-numeric text are not numbers", not is_num(None) and not is_num("high"))

    # ---- stats: the spread is the signal, not the level ----
    s = stats([3.0, 4.0, 5.0, 4.0])
    case("stats carries n, mean and the extremes",
         s["n"] == 4 and s["mean"] == 4.0 and s["min"] == 3.0 and s["max"] == 5.0)
    case("spread = max - min (the divergence across lenses)", s["spread"] == 2.0)
    case("an empty list returns n=0 without crashing", stats([]) == {"n": 0})
    case("a single value has zero spread and zero deviation",
         stats([5.0])["spread"] == 0.0 and stats([5.0])["stdev"] == 0.0)
    case("total agreement has zero spread", stats([4.0, 4.0, 4.0])["spread"] == 0.0)

    # ---- count_by ----
    recs = [{"v": "yes"}, {"v": "no"}, {"v": "yes"}, {"v": None}]
    c = count_by(recs, lambda r: r["v"])
    case("count_by counts by field value", c["yes"] == 2 and c["no"] == 1)
    case("REGRESSION: None counts as its own category (does not vanish from the count)", c[None] == 1)

    # ---- dim_stats: non-numeric is ignored, does not become zero ----
    recs = [{"d1": 3, "d2": 5}, {"d1": 5, "d2": 5}, {"d1": 4, "d2": "n/a"}]
    ds = dim_stats(recs, ["d1", "d2"], lambda r, d: r.get(d))
    case("dim_stats aggregates by dimension", ds["d1"]["n"] == 3 and ds["d1"]["mean"] == 4.0)
    case("REGRESSION: non-numeric is IGNORED, does not become 0 (0 would drag the mean down)",
         ds["d2"]["n"] == 2 and ds["d2"]["mean"] == 5.0)

    # ---- noise floor: decides whether a delta is improvement or variance ----
    r1 = [{"id": "a", "s": 3}, {"id": "b", "s": 4}]
    r2 = [{"id": "a", "s": 4}, {"id": "b", "s": 4}]
    kf, vf = (lambda r: r["id"]), (lambda r: r["s"])

    case("deltas pair by key, not by position",
         sorted(paired_abs_deltas(r1, r2, kf, vf)) == [0.0, 1.0])
    case("REGRESSION: a run compared against itself gives a ZERO floor "
         "(otherwise every delta would become noise and nothing would be signal)",
         paired_abs_deltas(r1, r1, kf, vf) == [0.0, 0.0])
    case("REGRESSION: an item without a pair is ignored, never compared against the wrong one",
         paired_abs_deltas(r1, [{"id": "z", "s": 9}], kf, vf) == [])
    case("a non-numeric value in the pair is discarded, does not become 0",
         paired_abs_deltas(r1, [{"id": "a", "s": "high"}], kf, vf) == [])

    nf = noise_floor(r1, r2, kf, {"score": vf})
    case("noise_floor reports how many pairs it compared", nf["n_pairs"] == 2)
    case("noise_floor is the mean of the absolute deltas", nf["score"] == 0.5)
    case("REGRESSION: with no comparable pair the floor is None, NOT 0 "
         "(0 would say any delta is signal)",
         noise_floor(r1, [{"id": "z", "s": 1}], kf, {"score": vf})["score"] is None)

    # ---- jaccard ----
    case("jaccard of equal sets is 1", jaccard({1, 2}, {1, 2}) == 1.0)
    case("jaccard of disjoint sets is 0", jaccard({1}, {2}) == 0.0)
    case("REGRESSION: two empty sets return None, not division by zero",
         jaccard(set(), set()) is None)

    print(f"{sum(results)}/{len(results)} tests ok")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
