#!/usr/bin/env python3
"""quick_panel.py — células do preset QUICK com caching de prefixo + roster do PIN.

Contrato (core/execution.md §caching + interactive-gates v2):
- o MATERIAL compartilhado (artefato/evidência) entra como PREFIXO byte-idêntico do user em toda
  célula (system genérico curto e idêntico) — persona/ask vão no SUFIXO. É a pré-condição do
  cache de prefixo dos providers (persona no prefixo quebra o cache).
- o júri vem do PIN da instância (roster-pin.yaml): M=3 no quick; M=4 no cheio (extra judge).
Zero dependência nova: o pin é lido por um parser mínimo do formato da casa (chave: valor e
listas de dicts inline `- {k: v, ...}`), sem pyyaml.
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path

from . import config

# Sem caminho fixo: o pin do usuário ($HIGH_STAKES_HOME) ganha do embarcado. O antigo
# `parents[2]/.claude/skills/...` só resolvia dentro do repo de quem escreveu.
DEFAULT_PIN = None

SYSTEM_QUICK = ("Você é um conselheiro num painel adversarial CEGO (ninguém lê ninguém). "
                "Julgue o material com rigor, cite números dele, nunca invente dado.")

MATERIAL_HEADER = "=== MATERIAL COMPARTILHADO (idêntico para todo o painel) ===\n"
MATERIAL_FOOTER = "\n=== FIM DO MATERIAL ===\n\n"


def _clean(v: str):
    """Valor escalar: tira aspas; true/false viram bool (o resto fica string)."""
    v = v.strip().strip("'\"")
    if v.lower() == "true":
        return True
    if v.lower() == "false":
        return False
    return v


def _strip_comment(line: str) -> str:
    """Remove comentário fora de aspas (um '#' dentro de valor citado é preservado)."""
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
    """`{model: x, family: y, reasoning: off}` -> dict (escalares limpos)."""
    out = {}
    for part in s.strip().strip("{}").split(","):
        if ":" in part:
            k, v = part.split(":", 1)
            out[k.strip()] = _clean(v)
    return out


def load_pin(path: Path | None = None) -> dict:
    """Lê o roster-pin.yaml (formato da casa). Retorna dict com quick_judges (lista de dicts),
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
    """True se o pin venceu (gatilho de floor-check — methodology §3a-ter).

    Data ausente ou ilegível conta como VENCIDO, nunca como erro: derrubar o run por causa
    de um typo no arquivo de config seria pior, e "vencido" é a direção segura — força
    re-verificar o roster em vez de confiar nele em silêncio."""
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
    """Monta as células do quick: personas = {key: sufixo-da-persona-SEM-o-material};
    ask_builder(key) -> texto do ask/schema daquele arquétipo. O material entra UMA vez,
    como prefixo idêntico. `full=True` soma o extra judge do pin (M=4)."""
    pin = pin or load_pin()
    judges = list(pin["quick_judges"])
    if full and pin.get("full_extra_judge"):
        judges.append(pin["full_extra_judge"])
    prefix = MATERIAL_HEADER + material + MATERIAL_FOOTER
    tasks = []
    for key, persona_suffix in personas.items():
        for j in judges:
            mkey = j["model"].split("/")[-1]  # único por juiz (família repetida não colide)
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
                         "papel": "cobertura",
                         "prompt_version": prompt_version},
            })
    return tasks
