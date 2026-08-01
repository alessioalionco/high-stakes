"""
aggregate.py — agregações DETERMINÍSTICAS genéricas (generaliza a camada 1 do
protótipo): contagens por campo, mean+spread por dimensão,
piso de ruído. Zero LLM, zero específico-de-caso.
"""

from __future__ import annotations

import math
import statistics
from collections import Counter
from typing import Any, Callable, Iterable


def is_num(x: Any) -> bool:
    """Número DE VERDADE: rejeita bool (float(True)==1.0 é armadilha) e
    não-finitos (nan/inf estragariam mean/spread silenciosamente)."""
    if isinstance(x, bool):
        return False
    try:
        return math.isfinite(float(x))
    except (TypeError, ValueError):
        return False


def stats(values: list[float]) -> dict:
    """mean/min/max/spread/stdev de uma lista numérica (spread = sinal de divergência)."""
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
    """Contagem por valor de campo (getter). None conta como None (não some)."""
    return Counter(getter(r) for r in records)


def dim_stats(records: Iterable[dict], dims: list[str],
              getter: Callable[[dict, str], Any]) -> dict[str, dict]:
    """mean+spread por dimensão: getter(record, dim) -> valor (não-num ignorado)."""
    recs = list(records)
    out = {}
    for d in dims:
        vals = [float(getter(r, d)) for r in recs if is_num(getter(r, d))]
        out[d] = stats(vals)
    return out


def paired_abs_deltas(main: list[dict], rerun: list[dict],
                      key_fn: Callable[[dict], Any],
                      value_fn: Callable[[dict], Any]) -> list[float]:
    """Deltas absolutos entre pares (mesma chave) de dois conjuntos de records.
    Núcleo do piso de ruído: re-run idêntico -> quanto o valor mexe sozinho."""
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
    """Piso de ruído genérico: p/ cada métrica nomeada, média dos |deltas| entre
    o run principal e a re-rodada idêntica. Só delta ACIMA do piso conta como sinal."""
    n_pairs = len({key_fn(r) for r in rerun} & {key_fn(r) for r in main})
    out: dict[str, Any] = {"n_pairs": n_pairs}
    for name, vfn in value_fns.items():
        deltas = paired_abs_deltas(main, rerun, key_fn, vfn)
        out[name] = round(statistics.mean(deltas), 2) if deltas else None
    return out


def jaccard(a: set, b: set) -> float | None:
    """Estabilidade de conjuntos (ex: cards) entre run e re-run."""
    if not a and not b:
        return None
    return round(len(a & b) / len(a | b), 2)
