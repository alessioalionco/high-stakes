"""
cells.py — runner GENÉRICO de células sobre eixos arbitrários (contrato 2A do bench-plan).

Generaliza a maquinaria do protótipo (paralelo, skip-existing/resume,
repair-retry 1x, custo, proveniência, failed explícito) sem NADA específico-de-caso:
o experimento constrói as messages e o parse; o engine só executa.

    run_cells(client, tasks, out_dir, concurrency=6) -> list[dict]

    CellTask (dict) = {
      "cell_id": str,            # único no run; vira o nome do arquivo em out_dir
      "model": str,              # slug OpenRouter
      "messages": list[dict],    # PRONTAS (o experimento constrói; engine não monta prompt)
      "parse": Callable[[str], dict],  # levanta SchemaInvalid -> engine faz repair-retry 1x
      "request": dict,           # max_tokens, temperature, response_format, extra_body, timeout
      "meta": dict,              # proveniência extra do experimento (arm, persona, item_id, seed...)
    }

ENGINE garante: paralelo c/ cap, skip-existing/resume gated por input_hash+prompt_version
(por hash de input, nunca só por filename), repair-retry 1x, custo/célula, proveniência base
(status, retries, latency, usage, timestamp, input_hash), failed explícito (célula
que falha NÃO some). Saída: 1 JSON por célula em out_dir + lista em memória.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .or_client import SchemaInvalid

DEFAULT_CONCURRENCY = 6

# truncamentos (constantes nomeadas, não números mágicos)
REPAIR_ECHO_MAX_CHARS = 2000   # eco da resposta ruim no repair-retry
RAW_TEXT_MAX_CHARS = 3000      # raw_text persistido em célula failed/exception

# proveniência que o ENGINE carimba; meta do experimento não pode sobrescrever
_ENGINE_KEYS = {
    "cell_id", "model", "status", "result", "error", "raw_text", "cost_usd",
    "input_hash", "retries", "latency_s", "usage", "provider", "timestamp",
    "_skipped",
}

_SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._@-]+")


def cell_filename(cell_id: str) -> str:
    """Nome de arquivo seguro/estável a partir do cell_id (slug de modelo tem '/')."""
    return _SAFE_FILENAME.sub("-", cell_id) + ".json"


def write_json_atomic(path: Path, obj: dict) -> None:
    """Write atômico (tmp + os.replace): nunca deixa JSON meio-escrito em disco."""
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False))
    os.replace(tmp, path)


def load_cells(out_dir: Path) -> list[dict]:
    """Inverso de run_cells: lê TODAS as células persistidas em out_dir (inclui
    failed e exception — célula que falha NÃO some). Dir ausente -> []."""
    out_dir = Path(out_dir)
    if not out_dir.exists():
        return []
    return [json.loads(p.read_text()) for p in sorted(out_dir.glob("*.json"))]


def _check_unique(tasks: list[dict]) -> None:
    """Rejeita cell_ids duplicados E colisões de filename pós-sanitização ANTES
    do dispatch (senão células se sobrescrevem silenciosamente em disco)."""
    seen_ids: set[str] = set()
    seen_files: dict[str, str] = {}
    for t in tasks:
        cid = t["cell_id"]
        if cid in seen_ids:
            raise ValueError(f"cell_id duplicado: {cid!r}")
        seen_ids.add(cid)
        fn = cell_filename(cid)
        if fn in seen_files:
            raise ValueError(
                f"colisão de filename pós-sanitização: {cid!r} e "
                f"{seen_files[fn]!r} -> ambos viram {fn!r}"
            )
        seen_files[fn] = cid


def input_hash_for(model: str, messages: list[dict], request: dict | None = None) -> str:
    """Hash canônico do INPUT da célula (modelo + messages + request relevante).

    É este hash (junto com prompt_version do meta) que gateia o reuso
    skip-existing — nunca só o filename.
    """
    req = {k: v for k, v in (request or {}).items()
           if k in ("max_tokens", "temperature", "response_format", "extra_body")}
    blob = json.dumps({"model": model, "messages": messages, "request": req},
                      ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def _reusable(path: Path, input_hash: str, prompt_version: Any) -> dict | None:
    """Reuso: só se status ok E input_hash E prompt_version armazenados batem."""
    if not path.exists():
        return None
    try:
        prev = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None  # corrompida -> re-roda
    if prev.get("status") != "ok":
        return None
    if prev.get("input_hash") != input_hash:
        return None
    if prev.get("prompt_version") != prompt_version:
        return None
    return prev


def run_cell(client, task: dict, out_dir: Path) -> dict:
    """Executa UMA célula: chat -> parse (repair-retry 1x) -> JSON em disco."""
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
    cell_cost = 0.0  # acumula AMBAS as tentativas (o ledger já bilou as 2)
    out: dict = {}
    cur_messages = messages
    try:
        for _attempt in range(2):  # 1 tentativa + 1 repair
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
                        f"Sua resposta não seguiu o formato exigido ({e}). "
                        "Responda AGORA somente no formato exigido, nada mais."},
                ]
    except Exception as e:  # noqa: BLE001 — chat levantou, ou parse levantou ≠ SchemaInvalid
        exception_err = f"{type(e).__name__}: {e}"

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
        # invariante: célula que falha NÃO some — exception também PERSISTE em disco
        base["status"] = "exception"
        base["error"] = exception_err
        if out.get("text"):  # houve resposta paga -> preserva o material
            base["raw_text"] = out["text"][:RAW_TEXT_MAX_CHARS]
    elif parsed is None:
        base["status"] = "failed"  # 3º estado: não-parseável, explícito, nunca some
        base["error"] = last_err or "parse inválido após repair"
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
    """Roda a lista de células em paralelo (cap `concurrency`). Falha vira
    status=exception PERSISTIDA em disco (não derruba as demais); célula failed
    persiste. cell_ids duplicados/colisão de filename -> ValueError ANTES do dispatch."""
    _check_unique(tasks)
    out_dir.mkdir(parents=True, exist_ok=True)
    if not quiet:
        print(f"[{label}] {len(tasks)} células (cap {concurrency} simultâneas)")
    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futs = {pool.submit(run_cell, client, t, out_dir): t["cell_id"] for t in tasks}
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
            except Exception as e:  # noqa: BLE001 — 1 célula não derruba o run
                if not quiet:
                    print(f"  ERRO   {cid}: {type(e).__name__}: {e}")
                rec = {"cell_id": cid, "status": "exception",
                       "error": f"{type(e).__name__}: {e}",
                       "timestamp": datetime.now(timezone.utc).isoformat()}
                try:  # backstop: mesmo erro fora do run_cell PERSISTE (não some)
                    write_json_atomic(out_dir / cell_filename(cid), rec)
                except OSError:
                    pass  # sem disco não há o que persistir; fica na lista em memória
                results.append(rec)
    return results
