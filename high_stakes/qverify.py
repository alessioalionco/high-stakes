#!/usr/bin/env python3
"""qverify.py — verificação de quote por CÓDIGO (contrato do resumo sem perda, §3f item 6).

Toda quote atribuída do dossiê ("> ... — **Nome** (via Modelo)") e toda epígrafe de §4
(*"..."*) devem ser trecho VERBATIM de uma célula crua daquele conselheiro. Este verificador
confere por código — mata uma classe de erro medida (5% de fabricação em células com
pack) e aposenta o flag global `quote_unverified`.

Uso: python3 qverify.py <report.md> <cells_dir>   → exit 0 = todas verificadas; 1 = falhas.
API: verify(report_md, cells_dir) -> list[dict] (um por quote: {quote, advisor, status, onde}).

Regras de match (endurecidas no review de 21/Jul — 6 rotas de falso-verde fechadas):
- normalização (minúsculas, espaço colapsado, aspas/travessões/ênfase-markdown unificados);
- campos da célula separados por \\n APÓS normalizar — quote não pode "colar" fim de um campo
  com começo de outro;
- match dentro de UMA célula só, e com segmentos EM ORDEM (elipse "…"/"[...]" divide em
  segmentos; todos obrigatórios, inclusive os curtos; nada de splice entre células);
- atribuição = "— **Nome**" ancorada no FIM da linha (travessão+bold no meio da quote é
  conteúdo, não atribuição);
- §4: epígrafe ausente/inextraível = FALHA (nunca skip silencioso);
- match no conselheiro errado = `atribuicao_divergente` (a voz importa tanto quanto o texto).
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from typing import Iterable
from pathlib import Path

# Nome exibido -> advisor key. PAPÉIS primeiro: "Anti-tese do The Unit Economist" resolve pro papel,
# não pro nome que aparece dentro do heading.
# PAPÉIS: resolvem antes do nome ("Anti-tese do The Unit Economist" é o papel, não o The Unit Economist).
ROLE_KEYS = [
    ("anti-tese", "antitese"), ("antítese", "antitese"), ("antitese", "antitese"),
    ("refutador", "refuter"), ("generalista", "generalista"),
]
# NÃO existe lista fixa de conselheiros. Havia uma, com 7 sobrenomes, enquanto o pool
# embarcado tem 13 e o usuário pode escrever os dele: qualquer lente fora da lista
# resolvia para None e TODA quote dela virava "atribuicao_divergente" — vermelho
# permanente num gate que deveria ser silencioso. As chaves vêm do corpus das células.

# Atribuição SÓ no fim da linha (com "(via ...)" opcional depois do nome).
ATTRIB_END_RE = re.compile(
    r"—\s*\*\*([^*]+?)\*\*\s*(?:\((?:via|lente simulada)[^)]*\))?\s*$")
ELLIPSIS_RE = re.compile(r"…|\[\.\.\.\]|\[…\]|\.\.\.")
MIN_QUOTE = 15   # quote/epígrafe menor que isso não discrimina -> falha explícita
MIN_SEGMENT = 4  # segmento de elipse mínimo APÓS strip; todos são obrigatórios


def normalize(s: str) -> str:
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    s = s.replace("–", "-").replace("—", "-")
    s = re.sub(r"[*_`]", "", s)  # ênfase markdown não é conteúdo
    s = re.sub(r"[ \t]+", " ", s).strip().lower()
    return s.strip(' "\'.,;:!?-')


def cell_corpus(cells_dir: Path) -> dict[str, list[str]]:
    """advisor_key -> [texto normalizado POR CÉLULA] (campos separados por \\n — não colam)."""
    corpus: dict[str, list[str]] = {}
    for p in sorted(cells_dir.glob("*.json")):
        try:
            d = json.loads(p.read_text())
        except json.JSONDecodeError:
            continue
        # O PAPEL decide só a chave. O corpus se monta igual pra todo mundo: coleta
        # RECURSIVA de toda string — schema-agnóstico (bug real do 2º uso: lista fixa de
        # campos deixava schema novo fora do corpus e reprovava quote legítima). O
        # refutador tinha um ramo próprio lendo o campo plano `text`, que as células do
        # xverify (schema `result.caso_contra`…) não têm -> corpus vazio -> falso VERMELHO.
        key = "refuter" if p.name.startswith("refuter") else (
            d.get("advisor") or d.get("lente") or p.stem)
        parts: list[str] = []

        def walk(x):
            if isinstance(x, str):
                parts.append(x)
            elif isinstance(x, dict):
                for v in x.values():
                    walk(v)
            elif isinstance(x, list):
                for v in x:
                    walk(v)

        walk(d.get("result") or {})
        for flat in ("text", "raw_text"):  # formatos antigos de célula
            if d.get(flat):
                parts.append(str(d[flat]))
        cell_text = "\n".join(normalize(str(x)) for x in parts if str(x).strip())
        corpus.setdefault(key, []).append(cell_text)
    return corpus


def _joined_quotes(report_md: str) -> list[tuple[str, str]]:
    """[(texto_da_quote, nome_atribuído)] — junta blockquote multi-linha; atribuição só no
    fim de linha (travessão+bold interno é conteúdo)."""
    out = []
    buf: list[str] = []
    for ln in report_md.splitlines():
        if not ln.startswith(">"):
            buf = []
            continue
        body = ln.lstrip("> ").rstrip()
        m = ATTRIB_END_RE.search(body)
        if m:
            text = " ".join(buf + [body[:m.start()]])
            out.append((text.strip(), m.group(1)))
            buf = []
        else:
            buf.append(body)
    return out


def _sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn")


def _advisor_for(name: str, corpus_keys: Iterable[str] = ()) -> str | None:
    """Nome exibido -> chave de conselheiro. Papéis primeiro, depois as chaves REAIS
    das células daquele run (ordenadas da mais longa para a mais curta, para que
    'unit economist-antitese' não case antes com 'unit economist')."""
    n = normalize(name)
    ns = _sem_acento(n)
    for token, key in ROLE_KEYS:
        if token in n or token in ns:
            return key
    for key in sorted(corpus_keys, key=len, reverse=True):
        k = normalize(str(key))
        if k and (k in n or _sem_acento(k) in ns):
            return key
    return None


def _segments(qnorm: str) -> list[str]:
    segs = [s.strip(' "\'.,;:!?-') for s in ELLIPSIS_RE.split(qnorm)]
    return [s for s in segs if len(s) >= MIN_SEGMENT]


def _in_one_cell_ordered(segs: list[str], cells: list[str]) -> bool:
    """Todos os segmentos, EM ORDEM, dentro de UMA MESMA célula."""
    for text in cells:
        pos = 0
        for s in segs:
            i = text.find(s, pos)
            if i < 0:
                break
            pos = i + len(s)
        else:
            return True
    return False


def _match(qnorm: str, corpus: dict[str, list[str]], advisor: str | None) -> tuple[str, str]:
    segs = _segments(qnorm)
    if not segs:
        return "curta_nao_verificavel", ""
    if advisor and advisor in corpus and _in_one_cell_ordered(segs, corpus[advisor]):
        return "verified", advisor
    for key, cells in corpus.items():
        if key != advisor and _in_one_cell_ordered(segs, cells):
            return "atribuicao_divergente", key
    return "unverified", ""


# Detecção FROUXA — a mesma forma que o gate de render usa para contar quotes. Serve para
# achar linhas que SÃO atribuição; o parse estrito vem depois. Sem isto, uma linha com
# qualquer texto após o parêntese passava no gate e era INVISÍVEL aqui: o verificador
# imprimia "VERDE — 0/0" sem ter verificado nada. Gate anti-fabricação falhando ABERTO.
ATTRIB_LOOSE_RE = re.compile(r"—\s*\*\*.+?\*\*")


def _malformed_attributions(report_md: str) -> list[str]:
    """Linhas de quote que o gate conta como atribuídas e o parse estrito não captura."""
    ruins = []
    for ln in report_md.splitlines():
        if ln.startswith(">") and ATTRIB_LOOSE_RE.search(ln):
            if not ATTRIB_END_RE.search(ln.lstrip("> ").rstrip()):
                ruins.append(ln.strip())
    return ruins


def verify(report_md: str, cells_dir: Path) -> list[dict]:
    corpus = cell_corpus(cells_dir)
    findings = []
    for ln in _malformed_attributions(report_md):
        findings.append({"tipo": "quote", "advisor": "?", "status": "atribuicao_malformada",
                         "onde": "", "quote": ln[:120]})
    for text, name in _joined_quotes(report_md):
        qnorm = normalize(text)
        advisor = _advisor_for(name, corpus.keys())
        if len(qnorm) < MIN_QUOTE:
            findings.append({"tipo": "quote", "advisor": advisor or name,
                             "status": "curta_nao_verificavel", "onde": "",
                             "quote": text[:120]})
            continue
        status, onde = _match(qnorm, corpus, advisor)
        findings.append({"tipo": "quote", "advisor": advisor or name, "status": status,
                         "onde": onde, "quote": text[:120]})
    # Epígrafes de §4 (contratualmente verbatim; ausência = FALHA, nunca skip)
    sec4 = re.search(r"## §4(.*?)(?=\n## §|\Z)", report_md, re.DOTALL)
    if sec4:
        for h, b in re.findall(r"### (4\.\d[^\n]*)\n(.*?)(?=\n### |\Z)", sec4.group(1),
                               re.DOTALL):
            advisor = _advisor_for(h, corpus.keys())
            m = re.search(r'\*["“]([^*]+?)["”]\*', b, re.DOTALL)  # tolera epígrafe quebrada
            if not m:
                findings.append({"tipo": "epigrafe", "advisor": advisor or h[:20],
                                 "status": "epigrafe_ausente", "onde": "",
                                 "quote": h[:120]})
                continue
            qnorm = normalize(re.sub(r"\s+", " ", m.group(1)))
            status, onde = _match(qnorm, corpus, advisor)
            findings.append({"tipo": "epigrafe", "advisor": advisor or h[:20],
                             "status": status, "onde": onde, "quote": m.group(1)[:120]})
    return findings


def main() -> int:
    if len(sys.argv) != 3:
        print("uso: qverify.py <report.md> <cells_dir>")
        return 2
    report, cells_dir = Path(sys.argv[1]), Path(sys.argv[2])
    if not report.exists() or not cells_dir.is_dir():
        print(f"VERIFICAÇÃO DE QUOTES VERMELHA: caminho inválido ({report} / {cells_dir})")
        return 1
    findings = verify(report.read_text(), cells_dir)
    bad = [f for f in findings if f["status"] != "verified"]
    ok = len(findings) - len(bad)
    if bad:
        print(f"VERIFICAÇÃO DE QUOTES VERMELHA — {len(bad)} de {len(findings)} não verificadas:")
        for f in bad:
            extra = f" (match em '{f['onde']}')" if f["status"] == "atribuicao_divergente" else ""
            print(f"  ✗ [{f['tipo']}|{f['advisor']}|{f['status']}]{extra} \"{f['quote']}\"")
        print("Corrigir pro verbatim do card (ou remover) e re-rodar. "
              "Quote não-verificada não vai pro decisor.")
        return 1
    if not findings and ATTRIB_LOOSE_RE.search(report.read_text()):
        # "VERDE — 0/0" num dossiê QUE TEM atribuições significa que o verificador não
        # entendeu nenhuma delas, não que estão todas certas. Verde vazio é falso verde.
        print("VERIFICAÇÃO DE QUOTES VERMELHA: o dossiê tem quotes atribuídas e NENHUMA "
              "foi extraída — a forma da atribuição não bate com o contrato "
              '(> "texto." — **Nome** (lente simulada · <modelo>)).')
        return 1
    print(f"VERIFICAÇÃO DE QUOTES VERDE — {ok}/{len(findings)} verificadas por código.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
