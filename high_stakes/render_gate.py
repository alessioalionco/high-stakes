#!/usr/bin/env python3
"""render_gate.py — verificador mecânico do gate de render (core/sections/output-contract.md).

Piso ESTRUTURAL do dossiê §0-§7 + ban de jargão interno no corpo (§0-§6; §7/apêndice é exceção
declarada — honestidade de método pode nomear builds). Não mede voz/nuance/fidelidade de quote —
isso segue no R1-R4 do contrato; este gate garante o que código consegue garantir.

Pisos = os definidos no formato de referência (≥1 quote atribuída por convergente — "1-2 quotes de
referência"; perguntas/sugestões por presença — o "até 5" é teto, não piso). O gate nunca aperta
a barra ratificada por conta própria.

Uso: python3 render_gate.py <report.md>   → exit 0 = verde; exit 1 = vermelho; exit 2 = uso.
API: check(md) -> list[str] (vazia = verde). Reentrante, sem estado global.
Existe por causa de um modo de falha concreto: dossiê raso, escrito das contagens
agregadas em vez dos cards. O contrato em prosa já o proibia e não segurou.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# R3 — jargão interno proibido no corpo (§0-§6). FAMÍLIAS de código, não instâncias:
# uma denylist de instâncias apodrece (basta inventar o código seguinte). Referências a
# edições e a seções seguem permitidas. Rótulos de fork F1..Fn também
# (o mock ratificado nomeia forks assim) — por isso códigos F\d NÃO são banidos.
JARGON_PATTERNS = [
    (r"X-[A-Z]{1,3}\d*", "código de experimento X-*"),
    (r"EV\d+", "código de item de evidência EV*"),
    (r"B-(?:qverify|vers|ledger|lens|route)", "código de build B-*"),
    (r"D-[A-Z]\d+", "código de decisão D-*"),
    (r"R-GATE", "código de mecanismo R-GATE"),
]

# R7 — o dossiê CIRCULA. A atribuição "— **Nome**" usa a tipografia de citação real, e as
# lentes levam nomes de pessoas de verdade: quem recebe o PDF numa reunião pode ler "The Unit Economist
# disse isto sobre o nosso deck". A verificação de quotes garante fidelidade à CÉLULA, não à
# pessoa — garantia forte sobre a coisa errada, se o leitor não souber o que está lendo.
# `\s+` e não " ": a frase quebra em duas linhas no markdown com frequência, e uma regra
# que reprova por quebra de linha é armadilha, não rigor (foi como ela reprovou o próprio
# dossiê de exemplo da primeira vez que rodou).
DISCLOSURE_RE = re.compile(
    r"não\s+são\s+as\s+pessoas\s+reais|are\s+not\s+the\s+real\s+people", re.I)

# Quote atribuída = linha de blockquote cuja atribuição "— **Nome**" está na PRÓPRIA linha.
ATTRIB_RE = re.compile(r"—\s*\*\*.+?\*\*")

# R8 — o marcador de simulação viaja COM a atribuição, na mesma linha. A declaração do
# §Escopo (R7) protege o documento; ela não protege o FRAGMENTO. Quote recortada para um
# slide ou um print sai sem o §Escopo, e o que resta é uma citação com cara de real
# atribuída a uma pessoa que existe. As políticas de uso dos provedores descrevem
# exatamente isso: atribuir conteúdo de forma a enganar sobre a origem.
SIM_MARKER_RE = re.compile(r"\(lente simulada[^)]*\)")
# Prosa: exclui headings, quotes, tabelas e QUALQUER lista (-, *, +, "1.").
NOT_PROSE_RE = re.compile(r"^(\s*#|\s*>|\s*\||\s*[-*+]\s|\s*\d+\.\s)")


def split_sections(md: str) -> dict[str, str]:
    """Mapa '§N'/'escopo' -> corpo da seção (## delimita)."""
    out: dict[str, str] = {}
    cur, buf = None, []
    for ln in md.splitlines():
        if ln.startswith("## "):
            if cur is not None:
                out[cur] = "\n".join(buf)
            m = re.match(r"## §(\d)", ln)
            cur = f"§{m.group(1)}" if m else ("escopo" if "Escopo" in ln else ln[3:40])
            buf = []
        else:
            buf.append(ln)
    if cur is not None:
        out[cur] = "\n".join(buf)
    return out


def subsections(body: str) -> list[tuple[str, str]]:
    """[(heading '### ...', corpo)] dentro de uma seção."""
    out, cur, buf = [], None, []
    for ln in body.splitlines():
        if ln.startswith("### "):
            if cur is not None:
                out.append((cur, "\n".join(buf)))
            cur, buf = ln[4:], []
        else:
            buf.append(ln)
    if cur is not None:
        out.append((cur, "\n".join(buf)))
    return out


def paragraphs(body: str) -> list[str]:
    """Blocos de PROSA densa (>80 chars; listas/quotes/tabelas não contam)."""
    paras, buf = [], []
    for ln in body.splitlines():
        if ln.strip() == "" or NOT_PROSE_RE.match(ln):
            if buf:
                paras.append(" ".join(buf))
                buf = []
        else:
            buf.append(ln.strip())
    if buf:
        paras.append(" ".join(buf))
    return [p for p in paras if len(p) > 80]


def quotes(body: str) -> int:
    """Nº de quotes ATRIBUÍDAS: cada linha '> ...— **Nome**...' conta 1 (quotes adjacentes
    sem linha em branco contam separado — é markdown normal)."""
    return sum(1 for ln in body.splitlines()
               if ln.startswith(">") and ATTRIB_RE.search(ln))


def check(md: str) -> list[str]:
    """Valida o dossiê; retorna a lista de falhas (vazia = gate verde). Sem estado global."""
    fails: list[str] = []
    secs = split_sections(md)
    for s in ["§0", "§1", "§2", "§3", "§4", "§5", "§6", "§7"]:
        if s not in secs:
            fails.append(f"{s}: seção ausente")
    if fails:
        return fails  # sem esqueleto não há o que medir

    if len(paragraphs(secs["§0"])) < 5:
        fails.append(f"§0: {len(paragraphs(secs['§0']))} parágrafos densos de prosa (<5; "
                     "listas não contam)")
    if "escopo" not in secs:
        fails.append("§Escopo: seção ausente")
    elif not DISCLOSURE_RE.search(secs["escopo"]):
        fails.append(
            "§Escopo: falta a declaração de personas simuladas (R7). O dossiê circula e a "
            "atribuição '— **Nome**' parece citação real. Escreva no §Escopo: \"os "
            "conselheiros são lentes simuladas por modelos de linguagem; NÃO SÃO AS PESSOAS "
            "REAIS, e nenhuma frase atribuída a eles foi dita por elas\".")

    subs1 = [(h, b) for h, b in subsections(secs["§1"]) if re.match(r"1\.\d", h)]
    if not subs1:
        fails.append("§1: nenhum item 1.N")
    for h, b in subs1:
        item = h.split(" ")[0]
        if quotes(b) < 1:  # piso ratificado: "1-2 quotes de referência atribuídas"
            fails.append(f"§1 {item}: nenhuma quote atribuída (piso ratificado: ≥1)")
        if len(paragraphs(b)) < 2:
            fails.append(f"§1 {item}: {len(paragraphs(b))} parágrafos de prosa (<2)")

    for h, b in [(h, b) for h, b in subsections(secs["§2"]) if re.match(r"2\.\d", h)]:
        item = h.split(" ")[0]
        # Fork CONDICIONAL (board converge; sem 🐂/🐻 por contrato): exige o marcador
        # EXPLÍCITO "fork condicional" no heading ou no 1º bloco — palavra solta
        # "condicional" na prosa NÃO isenta (senão qualquer menção bypassa o gate).
        head_zone = (h + "\n" + b.split("\n\n")[0]).lower()
        if "fork condicional" in head_zone:
            continue
        if "🐂" not in b or "🐻" not in b:
            fails.append(f"§2 {item}: fork contestado sem os dois ensaios 🐂/🐻 "
                         "(condicional? marque 'fork condicional' no contexto)")
        if quotes(b) < 2:
            fails.append(f"§2 {item}: {quotes(b)} quotes atribuídas (<2 — mínimo 1 por lado)")
        low = b.lower()
        for campo in ["por que divergem", "custo de errar", "o que resolve"]:
            if campo not in low:
                fails.append(f"§2 {item}: falta '{campo}'")

    for h, b in [(h, b) for h, b in subsections(secs["§3"]) if re.match(r"3\.\d", h)]:
        item = h.split(" ")[0]
        low = b.lower()
        if "por que importa" not in low:
            fails.append(f"§3 {item}: falta 'por que importa'")
        if "testabilidade" not in low:
            fails.append(f"§3 {item}: falta 'testabilidade'")

    for h, b in [(h, b) for h, b in subsections(secs["§4"]) if re.match(r"4\.\d", h)]:
        item = h.split(" ")[0]
        anti = "anti-tese" in h.lower()
        if not re.search(r'^\*["“].+["”]\*\s*$', b, re.MULTILINE):
            fails.append(f"§4 {item}: sem epígrafe em voz própria (linha *\"...\"*)")
        if not re.search(r"\*\*Em uma frase", b):
            fails.append(f"§4 {item}: sem fecho-veredito em bold")
        if not anti:
            for campo in ["**Perguntas:**", "**Sugestões:**", "**Strip:**"]:
                if campo not in b:  # presença; "até 5" é teto ratificado, não piso
                    fails.append(f"§4 {item}: falta {campo}")

    b6 = secs["§6"]
    for sub in ["6.5", "6.6"]:
        if not re.search(rf"^### {re.escape(sub)}", b6, re.MULTILINE):
            fails.append(f"§6: falta o heading '### {sub}' "
                         "(substring solta tipo '6.5x' não conta)")
    m64 = re.search(r"### 6\.4(.*?)(?=### 6\.5|$)", b6, re.DOTALL)
    if not m64:
        fails.append("§6: falta 6.4 (sugestões ranqueadas)")
    else:
        itens = re.split(r"\n\*\*\d+\.", m64.group(1))[1:]
        if len(itens) < 5:
            fails.append(f"§6.4: {len(itens)} sugestões (<5)")
        for i, it in enumerate(itens, 1):
            if len(it.strip()) < 400:
                fails.append(f"§6.4 sugestão {i}: {len(it.strip())} chars "
                             "(<400 — mecanismo+como+dono/gate)")

    low7 = secs["§7"].lower()
    for campo in ["descartados", "onestidade", "drill-down"]:
        if campo not in low7:
            fails.append(f"§7: falta '{campo}'")

    # R8 — toda quote ATRIBUÍDA carrega o marcador na própria linha
    sem_marcador = []
    for s in ["§1", "§2", "§3", "§4", "§5", "§6"]:
        for ln in secs[s].splitlines():
            if ln.startswith(">") and ATTRIB_RE.search(ln) and not SIM_MARKER_RE.search(ln):
                sem_marcador.append(f"{s}: {ln.strip()[:70]}")
    for x in sem_marcador[:5]:
        fails.append(f"quote atribuída sem '(lente simulada · <modelo>)' na MESMA linha "
                     f"(R8 — a quote circula recortada, sem o §Escopo) — {x}")

    corpo = "\n".join(secs[s] for s in ["§0", "§1", "§2", "§3", "§4", "§5", "§6"])
    corpo += "\n" + secs.get("escopo", "")
    for pat, desc in JARGON_PATTERNS:
        hits = re.findall(rf"(?<![\w-]){pat}(?!\w)", corpo)
        if hits:
            uniq = sorted(set(hits))
            fails.append(f"jargão interno no corpo (§0-§6): {desc} — {', '.join(uniq[:5])} "
                         f"×{len(hits)} — glosar em português ou remover (R3)")
    return fails


def main() -> int:
    if len(sys.argv) != 2:
        print("uso: render_gate.py <report.md>")
        return 2
    path = Path(sys.argv[1])
    if not path.exists():
        print(f"GATE DE RENDER VERMELHO: {path} não existe")
        return 1
    fails = check(path.read_text())
    if fails:
        print(f"GATE DE RENDER VERMELHO — {len(fails)} falha(s):")
        for f in fails:
            print(f"  ✗ {f}")
        print("Corrigir e re-rodar. Entregar com gate vermelho = violação de contrato.")
        return 1
    print("GATE DE RENDER VERDE — piso estrutural ok "
          "(voz, nuance e fidelidade de quote não são medidos aqui).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
