"""
evidence.py — camada de evidência genérica (sonar deep-research via OpenRouter).

Extraída do protótipo. TUDO específico-de-caso virou PARÂMETRO
(regra 1A′): denylist de no-leak, modelo de evidência, paths de cache/pack,
blocklist de domínios — moram no config do experimento, nunca aqui.

Gates:
  - no-leak (falha FECHADA): query não pode conter token da `denylist` passada.
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
import unicodedata
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


class LeakBlocked(RuntimeError):
    """Query externa contém token sensível -> recusa rodar (no-leak fechado)."""


# Letras latinas que o NFKD NÃO decompõe: sem isto elas caem no `[^0-9a-z]` e são
# APAGADAS, e apagar uma letra fura o match ("Ørsted" virava "rsted"). São a grafia real
# de nomes nórdicos, turcos e poloneses — mesma família do "São Paulo" que motivou o fix.
# A decisão 4 da spec do ticket mandava deixar SÓ o bloco latino aqui. Ela está errada, e
# a verificação é de uma linha: sem os homoglifos cirílicos, `_fold("dados de Aсme Cоrp")`
# (com с e о cirílicos) é `"dados de a me c rp"`, que NÃO contém "acme corp" — o disfarce
# por homoglifo volta a passar, e a regressão que existe para isso fica vermelha.
# O que estilhaçava o token em fragmento de 1-2 chars não eram estes mapeamentos (são
# equivalências 1:1, o token sobrevive inteiro): eram as letras SEM forma ASCII, que o
# `[^0-9a-z]` apagava. Essas saem pelo `_lost_info`, não daqui.
_TRANSLIT = str.maketrans({
    "ø": "o", "æ": "ae", "œ": "oe", "ł": "l", "đ": "d", "ð": "d", "þ": "th",
    "ı": "i", "ħ": "h", "ß": "ss", "ŋ": "n", "ſ": "s",
    # homoglifos cirílicos/gregos de uso comum em disfarce (equivalência 1:1 — a letra
    # vira um ASCII único e o token inteiro sobrevive; não "estilhaça" como as sem forma)
    "а": "a", "е": "e", "о": "o", "с": "c", "р": "p", "х": "x", "у": "y", "к": "k",
    "α": "a", "ε": "e", "ο": "o", "ρ": "p", "τ": "t", "υ": "u", "κ": "k",
})


def _norm_pre(s: str) -> str:
    """NFKD + tira acentos/invisíveis + casefold + translitera — ANTES de apagar não-ASCII.

    Parada aqui (antes do `re.sub`) porque é aqui que dá pra distinguir "token perdeu
    letra real" de "token virou ASCII limpo": se sobrar algum char >127 depois do
    translit, é cirílico/CJK/grego que o `[^0-9a-z]` ia simplesmente APAGAR — e apagar
    vira fragmento curto que casa com quase tudo. Ver `_lost_info`.
    """
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if unicodedata.category(c) not in ("Mn", "Cf"))
    return s.casefold().translate(_TRANSLIT)


def _fold(s: str) -> str:
    """Forma canônica ASCII para comparar: NFKD + sem acentos/invisíveis + translit.

    Confirmado no review: com denylist ["Acme Corp"], passavam "Acme  Corp" (espaço
    duplo), "Acme\nCorp", "Acme-Corp", "Acme\u200bCorp" (zero-width) e "Acme\xa0Corp"
    (NBSP); com ["Sao Paulo"], passava "São Paulo". Todas reescritas naturais, nenhuma
    exótica — e o guard tem UM trabalho.

    Falso positivo aqui é seguro (recusa enviar); falso negativo vaza.
    """
    return re.sub(r"[^0-9a-z]+", " ", _norm_pre(s)).strip()


def _squash(s: str) -> str:
    """Como _fold, mas SEM separador — para casar palavra colada por invisível.

    Apagar um invisível JUNTA as palavras: "Acme\u200bCorp" vira "acmecorp", que não
    contém "acme corp". Comparar também a forma colada fecha o bypass — mas colar contra
    a QUERY inteira colava toda fronteira de palavra e dava +10pp de recusa falsa. Aqui o
    squash só casa contra PALAVRAS inteiras da query (fronteira de palavra), não contra a
    query colada — é a fronteira que evita o falso positivo, não o corte por comprimento
    que o patch antigo usava (>=7 chars) e que deixava token curto vazar (C3).
    """
    return re.sub(r"[^0-9a-z]+", "", _norm_pre(s))


def _lost_info(s: str) -> bool:
    """A forma ASCII do token PERDEU informação?

    True quando, depois de NFKD + translit, ainda resta algum char >127: é
    cirílico/CJK/grego que `_fold` ia APAGAR, transformando o token num fragmento curto
    que casa com quase tudo (`denylist=["Ямал"]` recusava "SaaS B2B em 2025"). Nesses
    casos a forma ASCII é DESCARTADA e o token vai pelo caminho amplo (`_fold_amplo`).
    """
    return any(ord(c) > 127 for c in _norm_pre(s))


def _fold_amplo(s: str) -> str:
    """Fallback amplo: NFKC + sem invisíveis + casefold — PRESERVA não-ASCII.

    É o caminho do token cirílico/CJK/grego: o que foi DESCARTADO da forma ASCII é
    comparado AQUI, palavra a palavra, contra a query na mesma forma ampla. A regressão
    que este guard já teve: `_fold("Сбербанк")==""` e o teste `if tf` PULAVA o token,
    ficando estritamente mais fraco que o `token.lower()` antigo. Um guard que ignora em
    silêncio é pior que um guard ingênuo.
    """
    s = unicodedata.normalize("NFKC", s)
    s = "".join(c for c in s if unicodedata.category(c) not in ("Mn", "Cf"))
    return re.sub(r"\s+", " ", s.casefold()).strip()


def check_no_leak(query: str, denylist: list[str]) -> None:
    """Recusa enviar `query` se ela contiver qualquer token da `denylist`.

    Comparação ADITIVA (decisão 2): as formas ASCII dobrada, colada-com-fronteira e a
    ampla são testadas TODAS para cada token; basta UMA casar para bloquear. O gate
    antigo `not tf and ta and ta in qa` era o bug: token misto ("Сбербанк SA") tinha
    `tf='sa'` (ASCII usável) e PULAVA o caminho amplo, deixando o pedaço não-latino sem
    checagem nenhuma. Agora o caminho amplo é sempre avaliado quando o token tem parte
    não-ASCII (independente do pedaço ASCII casar ou não).

    Falso positivo é seguro (recusa enviar); falso negativo vaza. Na dúvida, bloquear.
    """
    qf, qa = _fold(query), _fold_amplo(query)
    qwords = qf.split()      # fronteira de palavra para o squash
    qsquash = _squash(query)  # query colada, para o token longo embutido num run maior
    for token in denylist:
        tf, ta = _fold(token), _fold_amplo(token)
        ascii_usable = bool(tf) and not _lost_info(token)
        # (1) forma ASCII dobrada, COM fronteira de palavra — só se o token não perdeu
        # informação. `tf in qf` (substring crua, como estava desde o código original)
        # recusa a query inocente que apenas contém a sigla dentro de uma palavra:
        # denylist ["SA"] barrava "casa", ["Co"] barrava "compra", ["res"] barrava
        # "resultado". O `\b` dos dois lados resolve sem perder nada de multi-palavra:
        # `tf` já está dobrado para [0-9a-z ] com espaço simples, e `qf` também, então
        # "acme corp" casa em "resumo da acme corp hoje" e em "acme-corp" (o separador
        # já virou espaço no fold). O token embutido num run maior ("AcmeCorpLtda") não
        # vem daqui — vem do passo (2b), que é onde ele sempre esteve.
        #
        # O que se perde, dito na cara: token CURTO de palavra única deixa de casar com
        # a forma sufixada ("Acme" não pega mais "Acmes"). É o preço da fronteira, e o
        # >=7 do (2b) cobre o caso realista, porque denylist de verdade traz o nome
        # inteiro ("Acme Corp"), não o radical.
        if ascii_usable and re.search(rf"\b{re.escape(tf)}\b", qf):
            raise LeakBlocked(
                f"query bloqueada: contém token sensível {token!r}. "
                "Abstraia a query antes de enviar (no-leak)."
            )
        # (2) forma colada. Duas comparações, com alcances deliberadamente diferentes:
        #
        #   (2a) IGUALDADE com uma palavra inteira da query, para QUALQUER comprimento.
        #        É o que pega o join com invisível sem o corte por comprimento que
        #        deixava token curto vazar (C3). Igualdade, e não `in`: `ts in w` casa
        #        DENTRO da palavra, sem fronteira nenhuma — a denylist ["SA"] recusaria
        #        "casa", que é exatamente a recusa falsa proibida pelo C4. A fronteira é
        #        o ponto; sem ela o passo (2) vira o corte por comprimento outra vez, só
        #        que implícito e invisível.
        #
        #   (2b) SUBSTRING na query inteira colada, só para token longo (>=7). Aqui a
        #        colisão é improvável (medido no review: ~0 em >=7, +10pp em 4 chars) e
        #        é o que pega o token embutido num run maior ("AcmeCorpLtda"), que a
        #        igualdade sozinha perderia. Mantido do desenho anterior de propósito:
        #        trocar `in` por `==` sem isto seria trocar um falso positivo por um
        #        vazamento silencioso.
        if ascii_usable:
            ts = _squash(token)
            if ts and (any(ts == w for w in qwords)
                       or (len(ts) >= 7 and ts in qsquash)):
                raise LeakBlocked(
                    f"query bloqueada: contém token sensível {token!r}. "
                    "Abstraia a query antes de enviar (no-leak)."
                )
        # (3) caminho amplo: cada PALAVRA não-ASCII do token, contra a query ampla.
        # Sempre avaliado (aditivo) — fecha o buraco do token misto, cujo pedaço ASCII
        # não cobre o pedaço cirílico/CJK/grego.
        for w in ta.split():
            if any(ord(c) > 127 for c in w) and w in qa:
                raise LeakBlocked(
                    f"query bloqueada: contém token sensível {token!r}. "
                    "Abstraia a query antes de enviar (no-leak)."
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


_DENYLIST_OMITIDA = object()  # sentinela: distingue "não passou" de "passou None"


def _resolve_denylist(denylist):
    """Omitir a denylist era o caminho PERMISSIVO: o default `None` desligava o guard, e
    quem esquecesse o kwarg despachava sem checagem nenhuma — enquanto o erro mais
    inocente (`[]`) falhava duro. Agora omitir é erro; `None` tem de ser digitado."""
    if denylist is _DENYLIST_OMITIDA:
        raise ValueError(
            "denylist é obrigatória. Passe a lista de tokens sensíveis, ou passe "
            "explicitamente denylist=None para declarar que esta query é pública. "
            "Omitir não é uma opção: o silêncio não pode ser o caminho que despacha.")
    return denylist


def _check_denylist_config(denylist: list[str] | None) -> None:
    """Distingue None (público — no-leak desligado DE PROPÓSITO) de []
    (misconfiguração: quis no-leak mas passou lista vazia) — falha FECHADA."""
    if denylist is not None and len(denylist) == 0:
        raise ValueError(
            "denylist=[] é misconfiguração: lista VAZIA não protege nada. "
            "Use denylist=None para claims públicas (no-leak desligado de "
            "propósito) ou uma lista não-vazia de tokens sensíveis."
        )


def _cache_filename(ask: dict, evidence_model: str,
                    denylist: list[str] | None,
                    domain_blocklist: list[str] | None) -> str:
    """Nome de cache = id sanitizado + hash10(query+modelo+blocklist+denylist):
    qualquer mudança de input INVALIDA o cache (não reusa resposta obsoleta)."""
    blob = json.dumps({
        "query": ask.get("query"),
        "evidence_model": evidence_model,
        "blocklist": sorted(domain_blocklist or []),
        "denylist": sorted(denylist) if denylist is not None else None,
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
             denylist=_DENYLIST_OMITIDA,
             domain_blocklist: list[str] | None = None,
             system_prompt: str = _DEFAULT_SYSTEM,
             max_tokens: int = 4000, temperature: float = 0.2,
             timeout: int = 600) -> dict:
    """Roda 1 ask via deep-research. Retorna item do evidence-pack.

    `denylist=None` desliga o no-leak (claims públicas vão verbatim);
    lista não-vazia = falha FECHADA se a query contiver token sensível.
    """
    denylist = _resolve_denylist(denylist)
    _check_denylist_config(denylist)  # []=misconfig, falha FECHADA
    query = ask["query"]
    if denylist:
        check_no_leak(query, denylist)  # falha FECHADA antes de qualquer envio

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
             denylist=_DENYLIST_OMITIDA,
             domain_blocklist: list[str] | None = None,
             only_first: bool = False) -> list[dict]:
    """Roda os asks (cache keyed por id+hash de input em cache_dir; `reuse` lê local).

    Cache: filename = id sanitizado + hash10(query+modelo+blocklist+denylist) —
    qualquer mudança invalida. Cache corrompido -> re-fetch (não crash). Ao LER
    do cache, blocked/leak_suspect são RE-derivados com a blocklist ATUAL."""
    denylist = _resolve_denylist(denylist)
    _check_denylist_config(denylist)
    cache_dir = Path(cache_dir)
    asks = asks[:1] if only_first else asks
    items = []
    for ask in asks:
        if ask.get("reuse"):
            print(f"[reuse] {ask['id']}")
            items.append(load_reuse(ask, base_dir, domain_blocklist))
            continue
        cached = cache_dir / _cache_filename(ask, evidence_model, denylist,
                                             domain_blocklist)
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
                        denylist=denylist, domain_blocklist=domain_blocklist)
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
