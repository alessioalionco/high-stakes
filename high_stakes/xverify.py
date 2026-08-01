#!/usr/bin/env python3
"""xverify.py — refutação POR ITEM como GERADOR DE PROFUNDIDADE (não como juiz).

A refutação por-item tem VIÉS PRÓ-REFUTADO medido (8 de 8 no
experimento; o lote, nos mesmos claims, deu 2 REFUTADO / 2 PARCIAL / 1 sustentado) — o papel
"monte o caso contra" vira advogado. Mas a PROFUNDIDADE por-item paga: na medição ela achou um fato
do material que o lote e o próprio Chairman tinham perdido (e que corrigiu o dossiê publicado).

Contrato portanto:
- cada item rende {caso_contra, o_que_sobrevive (concessão OBRIGATÓRIA), fatos_novos (checáveis,
  com onde-no-material), veredito_sugerido};
- `veredito_sugerido` é INSUMO do Chairman, nunca decisão final — a calibração de veredito vem
  do lote/Chairman; os `fatos_novos` são o produto principal e DEVEM ser verificados contra o
  material antes de entrar no dossiê (são checáveis por construção).

Uso programático: refute_items(client, material, items, model=...) -> list[dict]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from .cells import run_cells
from .or_client import SchemaInvalid

DEFAULT_MODEL = "google/gemini-3.1-pro-preview"

SYS = ("Você é um REFUTADOR independente e cego num processo adversarial. Recebe UM claim sobre "
       "o material. Seu caso-contra tem que ser o mais forte possível — mas você é um "
       "instrumento de descoberta, não um advogado: a CONCESSÃO é obrigatória (o que sobrevive "
       "do claim mesmo se o seu caso-contra estiver certo) e todo fato do material que você usar "
       "deve ser listado como checável (com onde ele está). Responda SOMENTE um JSON válido:\n"
       '{"caso_contra": "o argumento, específico, com números do material",\n'
       ' "o_que_sobrevive": "OBRIGATÓRIO e não-vazio: o que segue de pé do claim",\n'
       ' "fatos_novos": [{"fato": "checável", "onde": "slide/página/tabela"}],\n'
       ' "veredito_sugerido": "REFUTADO|PARCIAL|SUSTENTADO"}\n'
       "Português. Nunca invente número.")


def _parse(text: str) -> dict:
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    m = re.search(r"\{.*\}", t, re.DOTALL)
    if not m:
        raise SchemaInvalid("sem objeto JSON")
    try:
        obj = json.loads(re.sub(r",\s*([}\]])", r"\1", m.group(0)))
    except json.JSONDecodeError as e:
        raise SchemaInvalid(f"JSON inválido: {e}") from e
    for k in ("caso_contra", "o_que_sobrevive", "veredito_sugerido"):
        if not obj.get(k):
            raise SchemaInvalid(f"campo '{k}' ausente/vazio (concessão é obrigatória)")
    if obj["veredito_sugerido"] not in ("REFUTADO", "PARCIAL", "SUSTENTADO"):
        raise SchemaInvalid("veredito_sugerido inválido")
    obj.setdefault("fatos_novos", [])
    return obj


def build_refute_tasks(material: str, items: dict[str, str], model: str = DEFAULT_MODEL,
                       max_tokens: int = 8000, timeout: int = 900,
                       prompt_version: str = "xverify-v1") -> list[dict]:
    """items = {item_id: claim}. max_tokens ALTO por padrão: modelos com reasoning consomem o
    budget antes do texto (lição sonar/gemini — truncamento silencioso)."""
    return [{
        # prefixo "refuter" (não "refute") é CONTRATO: é como o qverify.cell_corpus
        # reconhece a célula do refutador. Ver test_qverify.test_refuter_prefix_contract.
        "cell_id": f"refuter_{k}",
        "model": model,
        "messages": [{"role": "system", "content": SYS},
                     {"role": "user",
                      "content": f"=== MATERIAL ===\n{material}\n=== FIM ===\n\nCLAIM: {claim}"}],
        "parse": _parse,
        "request": {"max_tokens": max_tokens, "temperature": 0.3, "timeout": timeout},
        "meta": {"item": k, "papel": "refutador-por-item", "prompt_version": prompt_version},
    } for k, claim in items.items()]


def refute_items(client, material: str, items: dict[str, str], out_dir,
                 model: str = DEFAULT_MODEL, concurrency: int = 8) -> list[dict]:
    """Roda a refutação por-item (persistida em out_dir via run_cells; resume ativo)."""
    tasks = build_refute_tasks(material, items, model=model)
    return run_cells(client, tasks, out_dir, concurrency=concurrency, label="xverify")
