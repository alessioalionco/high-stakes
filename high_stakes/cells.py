"""
cells.py — GENERIC cell runner over arbitrary axes (bench-plan contract 2A).

Generalizes the prototype's machinery (parallel, skip-existing/resume,
1x repair-retry, cost, provenance, explicit failed) with NOTHING case-specific:
the experiment builds the messages and the parse; the engine only executes.

    run_cells(client, tasks, out_dir, concurrency=6) -> list[dict]

    CellTask (dict) = {
      "cell_id": str,            # unique within the run; becomes the filename in out_dir
      "model": str,              # OpenRouter slug
      "messages": list[dict],    # READY-MADE (the experiment builds them; the engine never assembles prompts)
      "parse": Callable[[str], dict],  # raises SchemaInvalid -> engine does 1x repair-retry
      "request": dict,           # max_tokens, temperature, response_format, extra_body, timeout
      "meta": dict,              # extra experiment provenance (arm, persona, item_id, seed...)
    }

The ENGINE guarantees: parallelism with a cap, skip-existing/resume gated by
input_hash+prompt_version (by input hash, never by filename alone), 1x repair-retry,
per-cell cost, base provenance (status, retries, latency, usage, timestamp,
input_hash), explicit failed (a failing cell does NOT vanish). Output: 1 JSON per
cell in out_dir + in-memory list.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .flow_gate import check_flow
from .naming import SAFE_FILENAME
from .or_client import SchemaInvalid

DEFAULT_CONCURRENCY = 6

# truncations (named constants, not magic numbers)
REPAIR_ECHO_MAX_CHARS = 2000   # echo of the bad reply in the repair-retry
RAW_TEXT_MAX_CHARS = 3000      # raw_text persisted for a failed/exception cell

# provenance the ENGINE stamps; experiment meta must not override it
_ENGINE_KEYS = {
    "cell_id", "model", "status", "result", "error", "raw_text", "cost_usd",
    "input_hash", "retries", "latency_s", "usage", "provider", "timestamp",
    "_skipped",
}


def cell_filename(cell_id: str) -> str:
    """Safe/stable filename derived from the cell_id (model slugs contain '/')."""
    return SAFE_FILENAME.sub("-", cell_id) + ".json"


def write_json_atomic(path: Path, obj: dict) -> None:
    """Atomic write (tmp + os.replace): never leaves half-written JSON on disk."""
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False))
    os.replace(tmp, path)


def load_cells(out_dir: Path) -> list[dict]:
    """Inverse of run_cells: reads ALL cells persisted in out_dir (including
    failed and exception — a failing cell does NOT vanish). Missing dir -> []."""
    out_dir = Path(out_dir)
    if not out_dir.exists():
        return []
    return [json.loads(p.read_text()) for p in sorted(out_dir.glob("*.json"))]


def _check_unique(tasks: list[dict]) -> None:
    """Rejects duplicate cell_ids AND post-sanitization filename collisions BEFORE
    dispatch (otherwise cells silently overwrite each other on disk)."""
    seen_ids: set[str] = set()
    seen_files: dict[str, str] = {}
    for t in tasks:
        cid = t["cell_id"]
        if cid in seen_ids:
            raise ValueError(f"duplicate cell_id: {cid!r}")
        seen_ids.add(cid)
        fn = cell_filename(cid)
        if fn in seen_files:
            raise ValueError(
                f"post-sanitization filename collision: {cid!r} and "
                f"{seen_files[fn]!r} -> both become {fn!r}"
            )
        seen_files[fn] = cid


def input_hash_for(model: str, messages: list[dict], request: dict | None = None) -> str:
    """Canonical hash of the cell's INPUT (model + messages + relevant request).

    It is this hash (together with the meta's prompt_version) that gates
    skip-existing reuse — never the filename alone.
    """
    req = {k: v for k, v in (request or {}).items()
           if k in ("max_tokens", "temperature", "response_format", "extra_body")}
    blob = json.dumps({"model": model, "messages": messages, "request": req},
                      ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def _reusable(path: Path, input_hash: str, prompt_version: Any) -> dict | None:
    """Reuse: only if the stored status is ok AND input_hash AND prompt_version match."""
    if not path.exists():
        return None
    try:
        prev = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None  # corrupted -> re-run
    if prev.get("status") != "ok":
        return None
    if prev.get("input_hash") != input_hash:
        return None
    if prev.get("prompt_version") != prompt_version:
        return None
    return prev


def run_cell(client, task: dict, out_dir: Path) -> dict:
    """Runs ONE cell: chat -> parse (1x repair-retry) -> JSON on disk.

    Flow-gate ALWAYS (here too, not only in run_cells): run_cell is public and
    would dispatch directly — the gate's bypass. No-op outside a decision run's
    panel dispatch."""
    check_flow(Path(out_dir), [task])
    return _dispatch_cell(client, task, out_dir)


def _dispatch_cell(client, task: dict, out_dir: Path) -> dict:
    """run_cell's body AFTER the gate. run_cells dispatches through here: the gate
    already ran once over ALL tasks — re-running it per cell in the pool would mean
    N+1 pack reads + N pin writes racing across threads (review finding)."""
    cell_id = task["cell_id"]
    model = task["model"]
    messages = task["messages"]
    parse: Callable[[str], dict] = task["parse"]
    request = dict(task.get("request") or {})
    meta = dict(task.get("meta") or {})

    path = out_dir / cell_filename(cell_id)
    ihash = input_hash_for(model, messages, request)
    prompt_version = meta.get("prompt_version")

    prev = _reusable(path, ihash, prompt_version)
    if prev is not None:
        prev["_skipped"] = True
        return prev

    started = time.time()
    retries = 0
    parsed = None
    last_err = None
    exception_err = None
    cell_cost = 0.0  # accumulates BOTH attempts (the ledger already billed both)
    out: dict = {}
    cur_messages = messages
    try:
        for _attempt in range(2):  # 1 attempt + 1 repair
            out = client.chat(model, cur_messages, **request)
            cell_cost += out["cost_usd"]
            try:
                parsed = parse(out["text"])
                break
            except SchemaInvalid as e:
                last_err = str(e)
                retries += 1
                cur_messages = messages + [
                    {"role": "assistant", "content": out["text"][:REPAIR_ECHO_MAX_CHARS]},
                    {"role": "user", "content":
                        f"Your reply did not follow the required format ({e}). "
                        "Reply NOW in the required format only, nothing else."},
                ]
    except Exception as e:  # noqa: BLE001 — chat raised, or parse raised something ≠ SchemaInvalid
        exception_err = f"{type(e).__name__}: {e}"
        # The cap can blow AFTER the call has been paid for: the ledger's `reconcile`
        # raises with the real cost already debited. In that case the exception carries
        # the response in `.response` — and ignoring it throws away text that cost money,
        # records `cost_usd: 0`, and leaves the cell eligible to re-run (and pay again).
        # The assignment to `out` inside the `try` never completed, so without this it
        # stays `{}`.
        paid = getattr(e, "response", None)
        if isinstance(paid, dict) and paid.get("text") is not None:
            out = paid
            cell_cost += paid.get("cost_usd", 0.0) or 0.0
            try:
                parsed = parse(paid["text"])
            except Exception:  # noqa: BLE001 — saving the paid text is worth it even unparsed
                pass

    base = {k: v for k, v in meta.items() if k not in _ENGINE_KEYS}
    base.update({
        "cell_id": cell_id,
        "model": model,
        "provider": out.get("provider"),
        "cost_usd": cell_cost,
        "input_hash": ihash,
        "retries": retries,
        "latency_s": round(time.time() - started, 1),
        "usage": out.get("usage"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    if exception_err is not None:
        # invariant: a failing cell does NOT vanish — exceptions PERSIST to disk too
        base["status"] = "exception"
        base["error"] = exception_err
        if out.get("text"):  # there was a paid response -> preserve the material
            base["raw_text"] = out["text"][:RAW_TEXT_MAX_CHARS]
    elif parsed is None:
        base["status"] = "failed"  # 3rd state: unparseable, explicit, never vanishes
        base["error"] = last_err or "invalid parse after repair"
        base["raw_text"] = (out.get("text") or "")[:RAW_TEXT_MAX_CHARS]
    else:
        base["status"] = "ok"
        base["result"] = parsed
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json_atomic(path, base)
    return base


def run_cells(client, tasks: list[dict], out_dir: Path,
              concurrency: int = DEFAULT_CONCURRENCY,
              label: str = "cells", quiet: bool = False) -> list[dict]:
    """Runs the list of cells in parallel (cap `concurrency`). A failure becomes
    status=exception PERSISTED to disk (does not take the others down); a failed
    cell persists. Duplicate cell_ids/filename collision -> ValueError BEFORE dispatch.

    The flow gate (GO→execution) runs BEFORE any paid call: a decision-run panel
    dispatch without a consumed evidence pack (+ pre-pass when the preset requires
    it) raises FlowGateError — fail closed, $0 spent. Experiments and other stages
    (pre-pass, refuter) pass untouched (the predicate is the disk-layout position)."""
    _check_unique(tasks)
    check_flow(Path(out_dir), tasks)
    out_dir.mkdir(parents=True, exist_ok=True)
    if not quiet:
        print(f"[{label}] {len(tasks)} cells (cap {concurrency} concurrent)")
    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futs = {pool.submit(_dispatch_cell, client, t, out_dir): t["cell_id"]
                for t in tasks}
        for fut in as_completed(futs):
            cid = futs[fut]
            try:
                cell = fut.result()
                if not quiet:
                    skip = " SKIP" if cell.get("_skipped") else ""
                    print(f"  {cell['status']:6}{skip} {cid}  "
                          f"${cell.get('cost_usd', 0):.4f}"
                          + (f"  (retries {cell['retries']})" if cell.get("retries") else ""))
                results.append(cell)
            except Exception as e:  # noqa: BLE001 — 1 cell does not take the run down
                if not quiet:
                    print(f"  ERROR  {cid}: {type(e).__name__}: {e}")
                rec = {"cell_id": cid, "status": "exception",
                       "error": f"{type(e).__name__}: {e}",
                       "timestamp": datetime.now(timezone.utc).isoformat()}
                try:  # backstop: even an error outside run_cell PERSISTS (does not vanish)
                    write_json_atomic(out_dir / cell_filename(cid), rec)
                except OSError:
                    pass  # with no disk there is nothing to persist; it stays in the in-memory list
                results.append(rec)
    return results
