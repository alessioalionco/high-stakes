#!/usr/bin/env python3
"""xverify.py — per-item refutation as a DEPTH GENERATOR (not as a judge).

Per-item refutation has a measured PRO-REFUTED BIAS (8 of 8 in the
experiment; the batch, on the same claims, gave 2 REFUTED / 2 PARTIAL / 1 sustained) — the
"build the case against" role turns into an advocate. But the per-item DEPTH pays: in the
measurement it found a fact in the material that the batch and the Chairman himself had missed
(and that corrected the published dossier).

The contract therefore:
- each item yields {case_against, what_survives (MANDATORY concession), new_facts (checkable,
  with where-in-the-material), suggested_verdict};
- `suggested_verdict` is INPUT for the Chairman, never the final decision — verdict calibration
  comes from the batch/Chairman; the `new_facts` are the main product and MUST be verified
  against the material before entering the dossier (they are checkable by construction).

Programmatic use: refute_items(client, material, items, model=...) -> list[dict]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from .cells import run_cells
from .or_client import SchemaInvalid

DEFAULT_MODEL = "google/gemini-3.1-pro-preview"

SYS = ("You are an independent, blind REFUTER in an adversarial process. You receive ONE claim "
       "about the material. Your case-against must be as strong as possible — but you are an "
       "instrument of discovery, not an advocate: the CONCESSION is mandatory (what survives of "
       "the claim even if your case-against is right) and every fact from the material that you "
       "use must be listed as checkable (with where it is). Answer ONLY valid JSON:\n"
       '{"case_against": "the argument, specific, with numbers from the material",\n'
       ' "what_survives": "MANDATORY and non-empty: what remains standing of the claim",\n'
       ' "new_facts": [{"fact": "checkable", "where": "slide/page/table"}],\n'
       ' "suggested_verdict": "REFUTED|PARTIAL|SUSTAINED"}\n'
       "English. Never invent a number.")


def _parse(text: str) -> dict:
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    m = re.search(r"\{.*\}", t, re.DOTALL)
    if not m:
        raise SchemaInvalid("no JSON object")
    try:
        obj = json.loads(re.sub(r",\s*([}\]])", r"\1", m.group(0)))
    except json.JSONDecodeError as e:
        raise SchemaInvalid(f"invalid JSON: {e}") from e
    for k in ("case_against", "what_survives", "suggested_verdict"):
        if not obj.get(k):
            raise SchemaInvalid(f"field '{k}' missing/empty (the concession is mandatory)")
    if obj["suggested_verdict"] not in ("REFUTED", "PARTIAL", "SUSTAINED"):
        raise SchemaInvalid("invalid suggested_verdict")
    obj.setdefault("new_facts", [])
    return obj


def build_refute_tasks(material: str, items: dict[str, str], model: str = DEFAULT_MODEL,
                       max_tokens: int = 8000, timeout: int = 900,
                       prompt_version: str = "xverify-v1") -> list[dict]:
    """items = {item_id: claim}. max_tokens HIGH by default: models with reasoning burn the
    budget before the text (sonar/gemini lesson — silent truncation)."""
    return [{
        # the "refuter" prefix (not "refute") is a CONTRACT: it is how qverify.cell_corpus
        # recognizes the refuter's cell. See test_qverify (refuter contract regression).
        "cell_id": f"refuter_{k}",
        "model": model,
        "messages": [{"role": "system", "content": SYS},
                     {"role": "user",
                      "content": f"=== MATERIAL ===\n{material}\n=== END ===\n\nCLAIM: {claim}"}],
        "parse": _parse,
        "request": {"max_tokens": max_tokens, "temperature": 0.3, "timeout": timeout},
        "meta": {"item": k, "role": "refuter-per-item", "prompt_version": prompt_version},
    } for k, claim in items.items()]


def refute_items(client, material: str, items: dict[str, str], out_dir,
                 model: str = DEFAULT_MODEL, concurrency: int = 8) -> list[dict]:
    """Runs the per-item refutation (persisted in out_dir via run_cells; resume active)."""
    tasks = build_refute_tasks(material, items, model=model)
    return run_cells(client, tasks, out_dir, concurrency=concurrency, label="xverify")
