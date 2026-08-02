#!/usr/bin/env python3
"""test_qverify.py — suíte executável da verificação de quotes (convenção deste projeto: PASS/exit≠0).

Inclui as 6 regressões do review de 21/Jul (todas eram rotas de falso-VERDE confirmadas
por execução: cola-entre-campos, cauda curta pós-elipse, splice entre células/fora de
ordem, travessão+bold interno, Antítese acentuada, epígrafe ausente/quebrada)."""
import json
import shutil
import sys
import tempfile
from pathlib import Path

from high_stakes.qverify import _advisor_for, verify

CELL_UNIT ECONOMIST = {
    "advisor": "unit economist", "status": "ok",
    "result": {
        "veredito_prosa": ("Não confundam reclassificação com crescimento, consumo com gross "
                           "profit ou pipeline com forecast — o ônus da prova é do deck."),
        "items": [{"titulo": "A ponte precisa de números",
                   "analise": ("Na economia de tokens, revenue pode ser apenas revenda de "
                               "compute; a análise correta começa por gross profit, não ARR."),
                   "falsifier": "cohort provando margem"}],
        "dud_flags": {"comentario": "Eu tiraria E4 na forma proposta."},
        "perguntas_ao_fundador": ["Qual o coverage global do forecast?"],
    },
}
CELL_UNIT ECONOMIST2 = {
    "advisor": "unit economist", "status": "ok",
    "result": {"veredito_prosa": "O mercado premia margem, não promessa vazia de categoria.",
               "items": [], "dud_flags": {}, "perguntas_ao_fundador": []},
}
CELL_MODEL_THEORIST = {
    "advisor": "model theorist", "status": "ok",
    "result": {"veredito_prosa": "O as-is tenta obter crédito de empresa AI-native.",
               "items": [], "dud_flags": {}, "perguntas_ao_fundador": [],
               "posturas": {"condicoes": "Condição exclusiva de um esquema novo de células."}},
}
REFUTER = {"cell_id": "refuter_gemini", "papel": "refutador",
           "text": "A complexidade do material exige a voz do fundador guiando a narrativa."}


def refuter_contract_ok() -> bool:
    """REGRESSÃO cross-módulo (A1): a célula que o xverify PRODUZ tem de ser reconhecida
    pelo qverify como do refutador, e seu corpus tem de sair do schema real (`result.*`).

    O bug original tinha as DUAS pontas quebradas e nenhum teste as cruzava: o xverify
    escrevia `refute_*` enquanto o qverify procura `refuter*` (miss silencioso), e —
    corrigido só o prefixo — o corpus viria do campo plano `text`, que essas células não
    têm, logo VAZIO: falso VERMELHO em toda quote do refutador."""
    from high_stakes.cells import cell_filename
    from high_stakes.qverify import cell_corpus
    from high_stakes.xverify import build_refute_tasks

    tmp = Path(tempfile.mkdtemp())
    try:
        cid = build_refute_tasks("MATERIAL", {"i1": "claim um"})[0]["cell_id"]
        d = tmp / "cells"
        d.mkdir()
        # o formato que run_cells persiste (cells.py:173) com o schema do xverify
        (d / cell_filename(cid)).write_text(json.dumps({
            "cell_id": cid, "status": "ok",
            "result": {"caso_contra": "A ponte do Q4 não se sustenta sem coorte.",
                       "o_que_sobrevive": "O sinal de expansão é real.",
                       "veredito_sugerido": "ENFRAQUECIDO"},
        }, ensure_ascii=False))
        corpus = cell_corpus(d)
        return ("refuter" in corpus
                and any("ponte do q4 não se sustenta" in c for c in corpus["refuter"]))
    finally:
        shutil.rmtree(tmp)


def make_cells(tmp: Path) -> Path:
    d = tmp / "cells"
    d.mkdir()
    (d / "cell_unit_economist_sol.json").write_text(json.dumps(CELL_UNIT ECONOMIST, ensure_ascii=False))
    (d / "cell_unit_economist_glm.json").write_text(json.dumps(CELL_UNIT ECONOMIST2, ensure_ascii=False))
    (d / "cell_model_theorist_glm.json").write_text(json.dumps(CELL_MODEL_THEORIST, ensure_ascii=False))
    (d / "refuter_gemini.json").write_text(json.dumps(REFUTER, ensure_ascii=False))
    return d


REPORT = """# Teste
## §1 Convergentes
### 1.1 Item
> "Na economia de tokens, revenue pode ser apenas revenda de compute; a análise correta começa
> por gross profit, não ARR." — **The Unit Economist** (lente simulada · GPT-5.6 Sol)

> "NÃO CONFUNDAM reclassificação com crescimento…   o ônus da prova é do deck." — **The Unit Economist**

> "Quote completamente inventada que não está em card nenhum do painel." — **The Unit Economist**

> "O as-is tenta obter crédito de empresa AI-native." — **The Unit Economist** (via GLM-5.2)

> "A complexidade do material exige a voz do fundador guiando a narrativa." — **Refutador**

> "é do deck. A ponte precisa de números" — **The Unit Economist**

> "revenda de compute … é tudo lixo" — **The Unit Economist**

> "O mercado premia margem, não promessa … o ônus da prova é do deck" — **The Unit Economist**

> "gross profit, não ARR … Na economia de tokens" — **The Unit Economist**

> "O risco — **churn** — é o que mata a tese da retenção" — **The Unit Economist**

> "Condição exclusiva de um esquema novo de células." — **The Model Theorist**

## §4 Conselho
### 4.1 The Unit Economist — lente
*"Eu tiraria E4 na forma proposta."*

Parecer.

### 4.2 Antítese — premissa
*"O as-is tenta obter crédito
de empresa AI-native."*

Parecer com epígrafe QUEBRADA em duas linhas (e advisor errado de propósito? não — model theorist).

### 4.3 The Model Theorist — lente
Parecer SEM epígrafe nenhuma.
"""


def main() -> int:
    tmp = Path(tempfile.mkdtemp())
    try:
        cells = make_cells(tmp)
        f = verify(REPORT, cells)

        def find(sub, tipo="quote"):
            for x in f:
                if x["tipo"] == tipo and sub.lower() in x["quote"].lower():
                    return x
            return None

        def case(name, cond):
            print(("PASS" if cond else "FAIL"), name)
            return cond

        results = [
            case("verbatim multi-linha verifica",
                 find("Na economia de tokens")["status"] == "verified"),
            case("normalização (caixa/…/espaço, em ordem) verifica",
                 find("NÃO CONFUNDAM")["status"] == "verified"),
            case("fabricada reprova", find("inventada")["status"] == "unverified"),
            case("quote do The Model Theorist atribuída ao The Unit Economist = divergente",
                 find("crédito de empresa")["status"] == "atribuicao_divergente"),
            case("refutador (campo text) verifica",
                 find("complexidade do material")["status"] == "verified"),
            case("REGRESSÃO: cola entre campos reprova",
                 find("é do deck. A ponte")["status"] == "unverified"),
            case("REGRESSÃO: cauda curta fabricada pós-elipse reprova",
                 find("é tudo lixo")["status"] == "unverified"),
            case("REGRESSÃO: splice entre células reprova",
                 find("mercado premia margem")["status"] == "unverified"),
            case("REGRESSÃO: segmentos fora de ordem reprovam",
                 find("gross profit, não ARR …")["status"] == "unverified"),
            case("REGRESSÃO: travessão+bold interno não vira atribuição (e reprova)",
                 find("churn") is not None and find("churn")["status"] == "unverified"),
            case("REGRESSÃO: corpus recursivo cobre campo de esquema novo",
                 find("esquema novo")["status"] == "verified"),
            case("epígrafe verbatim verifica",
                 find("Eu tiraria E4", "epigrafe")["status"] == "verified"),
            case("REGRESSÃO: 'Antítese' acentuada resolve o papel (epígrafe quebrada extraída; "
                 "match no model theorist = divergente)",
                 find("crédito", "epigrafe") is not None
                 and find("crédito", "epigrafe")["status"] == "atribuicao_divergente"),
            case("REGRESSÃO: §4 sem epígrafe = FALHA (não skip)",
                 find("4.3", "epigrafe") is not None
                 and find("4.3", "epigrafe")["status"] == "epigrafe_ausente"),
            case("REGRESSÃO A1: célula do xverify é reconhecida como refutador e tem corpus",
                 refuter_contract_ok()),
            # REGRESSÃO: o gate de render conta como atribuída qualquer linha com
            # "— **Nome**"; o parse estrito exige fim de linha. A diferença fazia a quote
            # SUMIR do verificador, que então imprimia VERDE sem tê-la checado. Achado em
            # dossiê real: 18 linhas atribuídas, 17 extraídas, 1 invisível.
            case("REGRESSÃO: atribuição que o gate conta e o parse não captura vira "
                 "atribuicao_malformada (não some)",
                 any(f["status"] == "atribuicao_malformada" for f in verify(
                     '## §1 x\n### 1.1 y\n> "Uma quote com parêntese quebrado." '
                     '— **The Unit Economist** (via Gemini 3.1\n', cells))),
            case("REGRESSÃO: lente FORA da lista fixa antiga resolve pelo corpus "
                 "(o pool embarcado tem 13, a lista tinha 7)",
                 _advisor_for("The Movement Builder", ["movement builder", "unit economist"]) == "movement builder"),
            case("papel ainda vence o nome dentro do heading",
                 _advisor_for("Anti-tese do The Unit Economist", ["unit economist"]) == "antitese"),
            # REGRESSÃO: atribuição em PROSA era invisível aos DOIS gates (ambos exigiam
            # startswith('>')), então uma quote fabricada fora de blockquote passava
            # enquanto qualquer quote legítima mantinha `findings` não-vazio.
            case("REGRESSÃO: atribuição FORA de blockquote é acusada",
                 any(f["status"] == "atribuicao_fora_de_quote" for f in verify(
                     '## §1 x\n### 1.1 y\nTexto solto — **The Unit Economist** (lente simulada · X)\n',
                     cells))),
            # REGRESSÃO: quote de DUAS linhas com bold interno tinha a 1ª linha acusada de
            # malformada e a MESMA quote logo abaixo como verificada — vermelho contraditório.
            case("REGRESSÃO: bold interno em quote multi-linha NÃO vira malformada",
                 not any(f["status"] == "atribuicao_malformada" for f in verify(
                     '## §1 x\n### 1.1 y\n> "Ele disse que o **ônus da prova** é do deck\n'
                     '> e ninguém contestou." — **The Unit Economist** (lente simulada · X)\n', cells))),
        ]
        # ATENÇÃO: `results` acima é LISTA LITERAL. `case(...)` solto depois dela imprime
        # PASS/FAIL e NÃO entra na contagem nem no exit code. Use results.append(...).

        # ---- W1: o gate por BLOCO lava a atribuição malformada ----
        # `_malformed_attributions` decide por bloco inteiro: se QUALQUER linha do bloco
        # tem atribuição estrita, o bloco passa — e uma segunda atribuição malformada no
        # mesmo bloco some. É fail-open num gate cujo trabalho é impedir que uma frase
        # inventada saia com nome de gente real em cima. Um blockquote pode conter várias
        # quotes: cada uma tem de ser julgada sozinha.
        bloco_misto = ('> frase legitima aqui\n'
                       '> — **The Unit Economist** (lente simulada · Sol)\n'
                       '> outra frase, atribuida de forma malformada — **Fulano** no meio\n')
        results.append(case(
            "W1: atribuição malformada NÃO é lavada por outra válida no mesmo bloco",
            any(f["status"] == "atribuicao_malformada"
                for f in verify(bloco_misto, cells))))
        # e o caso legítimo que motivou o gate por bloco não pode voltar a acusar
        results.append(case(
            "W1b: bold interno em quote multi-linha segue NÃO sendo malformada",
            not any(f["status"] == "atribuicao_malformada" for f in verify(
                '> "Ele disse que o **ônus da prova** é do deck\n'
                '> e ninguém contestou." — **The Unit Economist** (lente simulada · X)\n', cells))))

        # ---- W2: falsos vermelhos que ensinam o usuário a ignorar o gate ----
        # Gate que dá vermelho em texto correto é pior que gate ausente: o usuário aprende
        # a passar por cima, e aí o vermelho de verdade também passa.
        results.append(case(
            "W2a: ênfase comum do português em prosa não vira atribuição",
            not verify("O time discutiu — **muito** — o roadmap do trimestre.\n", cells)))
        results.append(case(
            "W2b: travessão + bold no meio de frase em prosa não vira atribuição",
            not verify("A régua — **a nossa régua** — mudou no meio do trimestre.\n",
                       cells)))
        # blockquote indentado é markdown válido (até 3 espaços); hoje vira "prosa"
        indentado = ('  > Na economia de tokens, o custo marginal do rigor caiu.\n'
                     '  > — **The Unit Economist** (lente simulada · X)\n')
        results.append(case(
            "W2c: blockquote indentado é tratado como blockquote, não como prosa",
            not any(f["status"] == "atribuicao_fora_de_quote"
                    for f in verify(indentado, cells))))
        # continuação lazy: linha sem '>' dentro do bloco continua a quote (CommonMark)
        lazy = ('> Na economia de tokens, o custo marginal\n'
                'do rigor caiu.\n'
                '> — **The Unit Economist** (lente simulada · X)\n')
        results.append(case(
            "W2d: continuação lazy não parte a quote em pedaço curto demais",
            not any(f["status"] == "curta_nao_verificavel" for f in verify(lazy, cells))))

        print(f"{sum(results)}/{len(results)} testes ok")
        return 0 if all(results) else 1
    finally:
        shutil.rmtree(tmp)


if __name__ == "__main__":
    sys.exit(main())
