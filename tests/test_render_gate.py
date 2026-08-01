#!/usr/bin/env python3
"""test_render_gate.py — suíte executável do gate de render (convenção deste projeto: PASS/exit≠0).

Usa a API check(md) direto (reentrante); 1 caso via CLI cobre exit codes. Inclui regressões
dos findings do review de 20/Jul (falso-negativos por substring, jargão por família,
quotes adjacentes, listas como prosa, '6.5x' vs heading 6.5).
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from high_stakes.render_gate import check

ROOT = Path(__file__).resolve().parents[1]
# Invocação por `-m` é o CONTRATO do pacote (imports relativos): rodar o arquivo solto
# tem de falhar, e é isso que o último caso deste teste verifica.
GATE = [sys.executable, "-m", "high_stakes.render_gate"]

PARA = ("Parágrafo denso de prosa com fatos suficientes para contar como bloco de análise real "
        "do dossiê, com mecanismo e número, escrito para o decisor em linguagem clara e direta.")
Q = ('> "Quote verbatim de card com conteúdo suficiente." — **The Unit Economist** '
     '(lente simulada · GPT-5.6 Sol)')
Q2 = '> "Segunda quote verbatim, outra lente." — **The Model Theorist** (lente simulada · Kimi K3)'
SUG = ("**1. Sugestão detalhada.** 🚩 Problema descrito com mecanismo do dano e contexto "
       "suficiente para o decisor entender o que quebra e para quem, sem depender de jargão "
       "interno de engenharia. ✅ Como executar em passos concretos, com dono nomeado e gate "
       "explícito de quando está feito, mais a fonte no mapa. Dono: você. Fonte: item de teste "
       "com caracteres suficientes para passar o piso de quatrocentos caracteres do contrato "
       "ratificado pelo decisor em julho, garantindo profundidade mínima verificável por código.")

GOOD = f"""# Dossiê teste
{PARA}

## §0 Resumo executivo
{PARA}

{PARA}

{PARA}

{PARA}

{PARA}

## §Escopo do exercício
As lentes são simuladas por modelos; não são as pessoas reais.
{PARA}

## §1 Convergentes
### 1.1 Item convergente
{PARA}

{Q}

{PARA}

## §2 Forks
### 2.1 Fork contestado
{PARA}

**🐂 Tese: lado A.** {PARA}

{Q}

**🐻 Antítese: lado B.** {PARA}

{Q2}

**Por que divergem:** réguas diferentes. **Custo de errar por lado:** alto. **O que resolve:** dado.

### 2.2 Âncora de valuation
**Contexto.** Fork condicional — o júri converge; a bifurcação está no mundo. Pré-condição e
trigger descritos aqui.

## §3 Visões únicas
### 3.1 Item único
{PARA}

**Por que importa:** muda a decisão. **Testabilidade:** imediata.

## §4 Conselho
### 4.1 The Unit Economist — lente
*"Epígrafe aforística verbatim do card."*

{PARA}

**Perguntas:** (1) a? (2) b? (3) c?
**Sugestões:** x · y · z.
**Strip:** 1/2/3 → 4/5/6.
**Em uma frase: veredito da lente.**

### 4.2 Anti-tese — premissa
*"Epígrafe da anti-tese."*

{PARA}

**Em uma frase: a pergunta é outra.**

## §5 Agenda
{PARA}

## §6 Síntese do Chairman
### 6.1 Convergências
{PARA}

### 6.4 Sugestões
{SUG}

{SUG.replace('**1.', '**2.')}

{SUG.replace('**1.', '**3.')}

{SUG.replace('**1.', '**4.')}

{SUG.replace('**1.', '**5.')}

### 6.5 Perguntas
**1.** Pergunta com porquê.

### 6.6 Guardrails
| Guardrail | Trigger | Ação |
|---|---|---|
| a | b | c |

## §7 Apêndice
**7.1 Descartados** — item e porquê. **7.2 Honestidade de método** — piso de ruído não medido.
**7.3 Drill-down** — cards em cells/.
"""


def expect(name: str, md: str, want_fail: str | None) -> bool:
    fails = check(md)
    if want_fail is None:
        ok = not fails
        why = "" if ok else f" gate disse: {fails}"
    else:
        ok = any(want_fail in f for f in fails)
        why = "" if ok else f" esperava falha contendo '{want_fail}'; falhas: {fails[:4]}"
    print(("PASS" if ok else "FAIL"), name + why)
    return ok


def expect_cli() -> bool:
    """Cobertura do contrato de exit code via CLI (1 caso; temp limpo)."""
    fd, p = tempfile.mkstemp(suffix=".md")
    try:
        Path(p).write_text(GOOD)
        ok0 = subprocess.run(GATE + [p], cwd=ROOT).returncode == 0
        ok1 = subprocess.run(GATE + [p + ".nope"], cwd=ROOT,
                             capture_output=True).returncode == 1
        ok2 = subprocess.run(GATE, cwd=ROOT, capture_output=True).returncode == 2
        # T2: módulo COM import relativo não roda como arquivo solto — só por `-m`.
        # (render_gate é autocontido, então o alvo aqui é o render_dossier.)
        solto = subprocess.run([sys.executable, str(ROOT / "high_stakes" / "render_dossier.py")],
                               cwd=ROOT, capture_output=True)
        ok3 = solto.returncode != 0 and b"relative import" in solto.stderr
        ok = ok0 and ok1 and ok2 and ok3
        print(("PASS" if ok else "FAIL"),
              f"CLI por -m: exit codes (0/1/2) = ({ok0}/{ok1}/{ok2})")
        print(("PASS" if ok3 else "FAIL"),
              "T2: módulo com import relativo só roda por -m (arquivo solto falha)")
        return ok
    finally:
        os.close(fd)
        os.unlink(p)


def main() -> int:
    results = [
        expect("doc completo passa", GOOD, None),
        expect("check é reentrante (2ª chamada limpa)", GOOD, None),
        expect("secao ausente reprova", GOOD.replace("## §7 Apêndice", "## Apendice"), "§7"),
        # R8 — o marcador tem de viajar COM a atribuição. A quote sai do dossiê recortada
        # (slide, print) e o §Escopo não vai junto; sem o marcador, sobra uma citação com
        # cara de real atribuída a alguém que existe.
        expect("R8: atribuição sem o marcador de simulação REPROVA",
               GOOD.replace(" (lente simulada · GPT-5.6 Sol)", ""), "sem '(lente simulada"),
        expect("R8: o formato antigo '(via <modelo>)' NÃO satisfaz — 'via' identifica o "
               "modelo, não avisa que a persona é simulada",
               GOOD.replace("(lente simulada · GPT-5.6 Sol)", "(via GPT-5.6 Sol)"),
               "sem '(lente simulada"),
        expect("R8: marcador presente passa", GOOD, None),
        # R7 — o dossiê circula e a atribuição "— **Nome**" parece citação real. Sem a
        # declaração, entrega-se garantia de verbatim sobre a CÉLULA como se fosse sobre a
        # PESSOA. É a regra que o exemplo sintético motivou.
        expect("R7: §Escopo sem declaração de persona simulada REPROVA",
               GOOD.replace("As lentes são simuladas por modelos; não são as pessoas reais.\n", "", 1),
               "personas simuladas"),
        expect("R7: declaração quebrada em duas linhas é aceita (armadilha real da estreia)",
               GOOD.replace("As lentes são simuladas por modelos; não são as pessoas reais.",
                            "As lentes são simuladas por modelos; não são as\npessoas reais."), None),
        expect("R7: variante em inglês é aceita",
               GOOD.replace("As lentes são simuladas por modelos; não são as pessoas reais.",
                            "The advisors are simulated lenses and are not the real people."), None),
        expect("R7: frase vaga sobre 'simulação' NÃO basta (marcador é explícito)",
               GOOD.replace("As lentes são simuladas por modelos; não são as pessoas reais.",
                            "As lentes são uma simulação aproximada dos conselheiros."),
               "personas simuladas"),
        expect("§0 raso reprova",
               GOOD.replace(f"{PARA}\n\n{PARA}\n\n{PARA}\n\n{PARA}\n\n{PARA}\n\n## §Escopo",
                            f"{PARA}\n\n## §Escopo", 1), "§0"),
        expect("§0 de listas numeradas reprova (lista ≠ prosa)",
               GOOD.replace(f"## §0 Resumo executivo\n{PARA}",
                            f"## §0 Resumo executivo\n1. {PARA}", 1), "§0"),
        expect("convergente sem quote reprova", GOOD.replace(f"{Q}\n\n{PARA}\n\n## §2", f"{PARA}\n\n## §2", 1),
               "nenhuma quote atribuída"),
        expect("1 quote atribuída BASTA (piso ratificado)", GOOD, None),
        expect("quotes adjacentes contam separado (2.1 com Q colada em Q2 segue ok)",
               GOOD.replace(f"{Q}\n\n**🐻", f"{Q}\n{Q2}\n\n**🐻", 1), None),
        expect("heading com 'Reforçar' NÃO é isento de quote",
               GOOD.replace("### 1.1 Item convergente", "### 1.1 Reforçar o orçamento")
                   .replace(f"{Q}\n\n{PARA}\n\n## §2", f"{PARA}\n\n## §2", 1),
               "nenhuma quote atribuída"),
        expect("fork sem bear reprova", GOOD.replace("**🐻 Antítese: lado B.**", "", 1), "🐂/🐻"),
        expect("'condicional' solto na prosa NÃO isenta o fork",
               GOOD.replace("**🐂 Tese: lado A.**",
                            "A aprovação é condicional à DD.\n\n**🐂 Tese: lado A.**", 1)
                   .replace("**🐻 Antítese: lado B.** " + PARA, "", 1), "🐂/🐻"),
        expect("'Fork condicional' explícito isenta (2.2 do GOOD)", GOOD, None),
        expect("única sem testabilidade reprova",
               GOOD.replace("**Testabilidade:** imediata.", ""), "testabilidade"),
        expect("conselheiro sem epígrafe reprova",
               GOOD.replace('*"Epígrafe aforística verbatim do card."*', ""), "epígrafe"),
        expect("sugestão curta reprova",
               GOOD.replace(SUG.replace('**1.', '**5.'), "**5. Curta.** Só isso."), "6.4 sugestão"),
        expect("'6.5x' no texto não satisfaz o heading 6.5",
               GOOD.replace("### 6.5 Perguntas\n**1.** Pergunta com porquê.",
                            "múltiplo de 6.5x EV/ARR e ver 6.6 depois."), "### 6.5"),
        expect("jargão por FAMÍLIA reprova (X-LK3, não listado literalmente)",
               GOOD.replace("muda a decisão.", "muda a decisão (X-LK3)."), "X-LK3"),
        expect("jargão EV7 reprova (família EV\\d)",
               GOOD.replace("muda a decisão.", "muda a decisão (EV7)."), "EV7"),
        expect("edições E1-E6 e forks F1..Fn são permitidos",
               GOOD.replace("muda a decisão.", "muda a decisão (E4 e o fork F8)."), None),
        expect("jargão no §7 é permitido",
               GOOD.replace("piso de ruído não medido",
                            "piso de ruído não medido; X-B3 e B-qverify"), None),
        expect_cli(),
    ]
    print(f"{sum(results)}/{len(results)} testes ok")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
