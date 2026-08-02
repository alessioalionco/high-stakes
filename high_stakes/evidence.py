"""
evidence.py — camada de evidência genérica (sonar deep-research via OpenRouter).

Extraída do protótipo. TUDO específico-de-caso virou PARÂMETRO
(regra 1A′): modelo de evidência, paths de cache/pack, blocklist de domínios —
moram no config do experimento, nunca aqui.

EGRESS — por que NÃO existe filtro de conteúdo na saída
-------------------------------------------------------
Este módulo já teve um `check_no_leak`: uma denylist de termos sensíveis que
recusava a query se ela contivesse algum deles. Foi REMOVIDO, e a remoção é a
decisão, não uma pendência.

O guard protegia o dado do dono contra o dono. Quem escreve a query, quem é dono
do material e quem roda a ferramenta são a MESMA pessoa; os provedores são
escolhidos por ela e o critério de elegibilidade do produto já diz, na cara, que
usar isto significa mandar material a múltiplos providers. Não existe adversário
neste caminho — e sem adversário, blindar contra evasão (homoglifo, zero-width,
token partido por hífen) é custo puro.

O custo foi medido, não estimado: quatro rodadas de review adversarial
concentradas nesse matcher, cada uma fechando uma classe de evasão e abrindo
outra. O que ele produzia de verdade era recusa falsa em query legítima —
`["São Paulo"]` recusava "clima em São Tomé", `["C++"]` recusava "a linguagem C" —
e recusa falsa aqui é pior do que parece: quebra a perna cara do run (o deep
research) e ensina o usuário a esvaziar a própria denylist.

O que fica no lugar, e é mais forte: o **Gate B**
(`core/sections/interactive-gates.md`) mostra ao usuário exatamente o que vai
sair e pede OK antes do disparo. Um humano decidindo com a lista na frente vale
mais que uma heurística de substring — e é honesto sobre quem está decidindo.

O que este módulo AINDA protege (e são outros problemas, de verdade): a blocklist
de domínio na resposta (`leak_suspect`), e o `load_reuse`, que recusa caminho
fora do `base_dir` — inclusive por symlink. Esse sim tem adversário: um arquivo
que entra no prefixo de todas as células pagas.

Gates:
  - cache por ask em `cache_dir`: re-run não re-billa.
  - tiering por domínio (primária > analista > imprensa > vendor/blog) — genérico.
  - `domain_blocklist` marca citação de domínio-fonte proibido
    (blocked=True) e o item ganha leak_suspect=True — o consumidor exclui da
    acurácia e reporta a flag (nunca silencioso).
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

_SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._@-]+")  # mesma regra do engine.cells

# hierarquia de confiança por domínio (primária > analista > imprensa > vendor/blog)
_TIER_RULES = [
    ("alta", ["sec.gov", "arxiv.org", "nber.org", ".edu", "iso.org", "nist.gov"]),
    ("media", ["gartner.com", "forrester.com", "bvp.com", "a16z.com",
               "battery.com", "scalevp.com", "kbcm.com", "meritechcapital",
               "iconiq", "bcg.com", "saas-capital.com", "benchmarkit.ai"]),
    ("imprensa", ["bloomberg.com", "ft.com", "wsj.com", "reuters.com",
                  "techcrunch.com", "theinformation.com", "fortune.com"]),
    ("baixa", ["medium.com", "substack.com", "reddit.com", "linkedin.com",
               "blog.", "/blog"]),
]

_DEFAULT_SYSTEM = (
    "You are a rigorous research analyst. Answer the question "
    "with concrete, sourced facts and numbers. Prefer primary "
    "sources, recognized analysts, and audited data over blogs. "
    "Always cite sources with URLs. Be concise and factual."
)


def tier_for(url: str) -> str:
    u = (url or "").lower()
    for tier, needles in _TIER_RULES:
        if any(n in u for n in needles):
            return tier
    return "baixa"  # default conservador: domínio desconhecido não aterra número


def is_blocked_domain(url: str, domain_blocklist: list[str]) -> bool:
    """True se a URL bate (substring, case-insensitive) num domínio bloqueado."""
    u = (url or "").lower()
    return any(b.lower() in u for b in domain_blocklist or [])


def body_leak_suspect(text: str, domain_blocklist: list[str] | None) -> bool:
    """O CORPO da resposta menciona domínio bloqueado (mesmo sem
    citation formal) -> leak_suspect."""
    t = (text or "").lower()
    return any(b.lower() in t for b in domain_blocklist or [])


def _cache_filename(ask: dict, evidence_model: str,
                    domain_blocklist: list[str] | None) -> str:
    """Nome de cache = id sanitizado + hash10(query+modelo+blocklist):
    qualquer mudança de input INVALIDA o cache (não reusa resposta obsoleta)."""
    blob = json.dumps({
        "query": ask.get("query"),
        "evidence_model": evidence_model,
        "blocklist": sorted(domain_blocklist or []),
    }, ensure_ascii=False, sort_keys=True)
    h = hashlib.sha256(blob.encode("utf-8")).hexdigest()[:10]
    safe_id = _SAFE_FILENAME.sub("-", str(ask["id"]))
    return f"{safe_id}__{h}.json"


def extract_citations(raw: dict, domain_blocklist: list[str] | None = None) -> list[dict]:
    """Citations da resposta sonar (campo `citations` ou annotations) + tier + bloqueio."""
    cites: list[dict] = []
    for c in raw.get("citations") or []:
        url = c if isinstance(c, str) else c.get("url", "")
        if url:
            cites.append({"url": url, "tier": tier_for(url),
                          "blocked": is_blocked_domain(url, domain_blocklist or [])})
    # annotations (formato url_citation) como fallback
    for choice in raw.get("choices", []):
        for ann in (choice.get("message", {}) or {}).get("annotations", []) or []:
            url = (ann.get("url_citation") or {}).get("url", "")
            if url and url not in {x["url"] for x in cites}:
                cites.append({"url": url, "tier": tier_for(url),
                              "blocked": is_blocked_domain(url, domain_blocklist or [])})
    return cites


def research(client, ask: dict, *, evidence_model: str,
             domain_blocklist: list[str] | None = None,
             system_prompt: str = _DEFAULT_SYSTEM,
             max_tokens: int = 4000, temperature: float = 0.2,
             timeout: int = 600) -> dict:
    """Roda 1 ask via deep-research. Retorna item do evidence-pack.

    Não existe filtro de conteúdo na saída, e é de propósito — ver a nota de egress
    no topo deste módulo. O que entra na query é o que o dono do material escolheu
    mandar; a decisão de mandar é do Gate B, com um humano olhando.
    """
    query = ask["query"]

    out = client.chat(
        evidence_model,
        [{"role": "system", "content": system_prompt},
         {"role": "user", "content": query}],
        max_tokens=max_tokens,
        temperature=temperature,
        timeout=timeout,
    )
    citations = extract_citations(out["raw"], domain_blocklist)
    return {
        "id": ask["id"],
        "natureza": ask.get("natureza"),
        "query": query,
        "answer": out["text"],
        "citations": citations,
        # citação bloqueada OU corpo mencionando domínio bloqueado
        "leak_suspect": (any(c.get("blocked") for c in citations)
                         or body_leak_suspect(out["text"], domain_blocklist)),
        "cost_usd": out["cost_usd"],
        "provider": out["provider"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def load_reuse(ask: dict, base_dir: Path, domain_blocklist: list[str] | None = None) -> dict:
    """Ask com `reuse`: lê material local (não gasta call). Path relativo a base_dir."""
    base = Path(base_dir).resolve()
    alvo = Path(ask["reuse"])
    # `base / "/abs"` DESCARTA a base; `../..` escapa. O conteúdo lido daqui entra no
    # prefixo compartilhado de todas as células pagas e vai para o provedor externo — e
    # `check_no_leak` nunca o vê. Confirmado no review: lia OPENROUTER_API_KEY de fora.
    if alvo.is_absolute():
        raise ValueError(f"reuse não pode ser caminho absoluto: {ask['reuse']!r}")
    reuse_dir = (base / alvo).resolve()
    try:
        reuse_dir.relative_to(base)
    except ValueError:
        raise ValueError(
            f"reuse {ask['reuse']!r} escapa de {base} — material reusado entra no prompt "
            "pago sem passar pelo no-leak.") from None
    # Conter o diretório não basta: `read_text()` segue symlink de ARQUIVO, e um *.md
    # dentro do base apontando para fora era lido inteiro. O review reproduziu vazando
    # OPENROUTER_API_KEY exatamente por aqui.
    files = []
    if reuse_dir.exists():
        for f in sorted(reuse_dir.glob("*.md")):
            try:
                f.resolve().relative_to(base)
            except ValueError:
                raise ValueError(
                    f"{f} aponta para fora de {base} — material reusado entra no prompt "
                    "pago sem passar pelo no-leak.") from None
            files.append(f)
    body = "\n\n".join(f"### {f.name}\n{f.read_text()[:6000]}" for f in files)
    return {
        "id": ask["id"],
        "natureza": ask.get("natureza"),
        "query": "(reuso de material local — sem call nova)",
        "answer": body or "(material de reuso não encontrado)",
        "citations": [{"url": str(reuse_dir), "tier": "media", "blocked": False}],
        # o material reusado é conteúdo como qualquer outro: se cita domínio bloqueado,
        # é suspeito. Antes vinha False fixo, contrariando o contrato do módulo.
        "leak_suspect": body_leak_suspect(body, domain_blocklist),
        "cost_usd": 0.0,
        "provider": "local-reuse",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def run_asks(client, asks: list[dict], *, evidence_model: str,
             cache_dir: Path, base_dir: Path,
             domain_blocklist: list[str] | None = None,
             only_first: bool = False) -> list[dict]:
    """Roda os asks (cache keyed por id+hash de input em cache_dir; `reuse` lê local).

    Cache: filename = id sanitizado + hash10(query+modelo+blocklist) — qualquer
    mudança invalida. Cache corrompido -> re-fetch (não crash). Ao LER do cache,
    blocked/leak_suspect são RE-derivados com a blocklist ATUAL."""
    cache_dir = Path(cache_dir)
    asks = asks[:1] if only_first else asks
    items = []
    for ask in asks:
        if ask.get("reuse"):
            print(f"[reuse] {ask['id']}")
            items.append(load_reuse(ask, base_dir, domain_blocklist))
            continue
        cached = cache_dir / _cache_filename(ask, evidence_model, domain_blocklist)
        if cached.exists():  # não re-billa o que já temos
            try:
                item = json.loads(cached.read_text())
            except json.JSONDecodeError:
                print(f"[cache] {ask['id']}: cache CORROMPIDO — re-buscando.")
                item = None
            if item is not None:
                # re-aplica a blocklist ATUAL no que veio do cache
                for c in item.get("citations", []):
                    c["blocked"] = is_blocked_domain(c.get("url", ""),
                                                     domain_blocklist or [])
                item["leak_suspect"] = (
                    any(c.get("blocked") for c in item.get("citations", []))
                    or body_leak_suspect(item.get("answer", ""), domain_blocklist))
                print(f"[cache] {ask['id']} (já em disco — sem call nova)")
                items.append(item)
                continue
        print(f"[sonar] {ask['id']} ... (deep research, pode levar 1-3min)")
        item = research(client, ask, evidence_model=evidence_model,
                        domain_blocklist=domain_blocklist)
        print(f"        custo ${item['cost_usd']:.4f} · {len(item['citations'])} fontes "
              f"· provider {item['provider']}"
              + ("  ⚠️ leak_suspect" if item["leak_suspect"] else ""))
        cache_dir.mkdir(parents=True, exist_ok=True)
        cached.write_text(json.dumps(item, indent=2))
        items.append(item)
    return items


def write_pack(items: list[dict], pack_path: Path, title: str) -> None:
    pack_path = Path(pack_path)
    pack_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# {title}",
        f"\n> Gerado {datetime.now(timezone.utc).isoformat()} · material BRUTO, "
        "idêntico pra todas as células. Tier-baixo NÃO aterra número.\n",
    ]
    total = 0.0
    for it in items:
        total += it["cost_usd"]
        lines.append(f"\n## {it['id']}  ·  natureza: {it['natureza']}")
        lines.append(f"*query:* {it['query']}")
        lines.append(f"\n{it['answer']}\n")
        if it["citations"]:
            lines.append("**Fontes:**")
            for c in it["citations"]:
                flag = " ⚠️BLOCKED" if c.get("blocked") else ""
                lines.append(f"- [{c['tier']}]{flag} {c['url']}")
    lines.append(f"\n---\n*custo total do pack: ${total:.4f}*")
    pack_path.write_text("\n".join(lines))
    print(f"\nevidence-pack escrito: {pack_path} · custo total ${total:.4f}")
