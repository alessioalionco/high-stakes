#!/usr/bin/env python3
"""test_quick_panel.py — suíte executável do preset quick (convenção: PASS/exit≠0)."""
import sys
import tempfile
from datetime import date
from pathlib import Path

from high_stakes import config as hs_config
from high_stakes.quick_panel import (DEFAULT_PIN, MATERIAL_HEADER, build_quick_tasks, load_pin,
                         pin_expired)

PIN_FIXTURE = """# comentário
pinned: "2026-07-21"
ttl_days: 30
chairman: {model: anthropic/claude-fable-5, family: anthropic, votes: false}
quick_judges:
  - {model: openai/gpt-5.6-sol, family: openai}
  - {model: x-ai/grok-4.5, family: xai}
  - {model: z-ai/glm-5.2, family: zai, reasoning: off}
full_extra_judge: {model: moonshotai/kimi-k3, family: moonshot, reasoning: off}
refuter: {model: google/gemini-3.1-pro-preview, family: google}
source: "AA Index #jul e X-J1"  # comentário real
"""


def case(name, cond):
    print(("PASS" if cond else "FAIL"), name)
    return cond


def main() -> int:
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
        f.write(PIN_FIXTURE)
        pin_path = Path(f.name)
    try:
        pin = load_pin(pin_path)
        personas = {"unit economist": "Você é The Unit Economist. PACK…", "generalista": "Você é o generalista."}
        tasks = build_quick_tasks("DECK XYZ 123", personas,
                                  ask_builder=lambda k: f"ASK({k})",
                                  parse=lambda t: {"ok": t}, pin=pin)
        tasks_full = build_quick_tasks("DECK XYZ 123", personas, lambda k: "A",
                                       lambda t: t, pin=pin, full=True)
        from high_stakes.quick_panel import MATERIAL_FOOTER
        shared = MATERIAL_HEADER + "DECK XYZ 123" + MATERIAL_FOOTER
        prefixes = {t["messages"][1]["content"][:len(shared)] for t in tasks}
        systems = {t["messages"][0]["content"] for t in tasks}
        glm = [t for t in tasks if t["model"] == "z-ai/glm-5.2"]
        sol = [t for t in tasks if t["model"] == "openai/gpt-5.6-sol"]
        results = [
            case("pin: 3 juízes quick + famílias", len(pin["quick_judges"]) == 3
                 and {j["family"] for j in pin["quick_judges"]} == {"openai", "xai", "zai"}),
            case("pin: extra judge e refuter lidos",
                 pin["full_extra_judge"]["model"] == "moonshotai/kimi-k3"
                 and pin["refuter"]["family"] == "google"),
            case("pin do repo carrega e é coerente com a fixture",
                 {j["model"] for j in load_pin(DEFAULT_PIN)["quick_judges"]}
                 == {j["model"] for j in pin["quick_judges"]}),
            case("quick = personas × 3 juízes", len(tasks) == 6),
            case("full soma o 4º juiz (M=4)", len(tasks_full) == 8),
            case("CACHING: prefixo do user byte-idêntico em todas as células",
                 len(prefixes) == 1 and next(iter(prefixes)) == shared),
            case("CACHING: system idêntico e genérico (persona no sufixo)",
                 len(systems) == 1 and "The Unit Economist" not in next(iter(systems))),
            case("persona/ask presentes no sufixo",
                 any("Você é The Unit Economist" in t["messages"][1]["content"]
                     and "ASK(unit economist)" in t["messages"][1]["content"] for t in tasks)),
            case("reasoning off só onde o pin manda",
                 all("extra_body" in t["request"] for t in glm)
                 and all("extra_body" not in t["request"] for t in sol)),
            case("pin válido dentro do TTL", not pin_expired(pin, today=date(2026, 8, 1))),
            case("pin vencido após TTL", pin_expired(pin, today=date(2026, 8, 25))),
            case("REGRESSÃO: data com aspas não quebra pin_expired",
                 not pin_expired(pin, today=date(2026, 7, 22))),
            case("REGRESSÃO: 'votes: false' vira bool",
                 pin["chairman"]["votes"] is False),
            case("REGRESSÃO: '#' dentro de valor citado é preservado",
                 pin.get("source") == "AA Index #jul e X-J1"),
            case("REGRESSÃO: juízes da MESMA família não colidem cell_id",
                 len({t2["cell_id"] for t2 in build_quick_tasks(
                     "M", {"p1": "P"}, lambda k: "A", lambda x: x,
                     pin={"quick_judges": [
                         {"model": "openai/gpt-5.6-sol", "family": "openai"},
                         {"model": "openai/gpt-5.6-luna", "family": "openai"}],
                          "ttl_days": 30})}) == 2),
            # REGRESSÃO: o pin EMBARCADO tem data-placeholder. Se o parser crashar nela,
            # quem instala e roda sem fixar o próprio roster quebra na primeira decisão.
            case("data ilegível no pin conta como VENCIDO, não crasha",
                 pin_expired({"pinned": "0000-00-00", "ttl_days": 30}) is True),
            case("pin sem campo de data conta como VENCIDO",
                 pin_expired({"ttl_days": 30}) is True),
            case("ttl ilegível conta como VENCIDO",
                 pin_expired({"pinned": "2026-01-01", "ttl_days": "x"}) is True),
            case("o pin que VEM na instalação carrega e é avaliável sem crash",
                 pin_expired(load_pin(hs_config.pin_path())) is True),
        ]
        # ATENÇÃO a quem adicionar teste daqui pra baixo: `results` acima é uma LISTA
        # LITERAL. Um `case(...)` solto depois dela IMPRIME PASS/FAIL e não entra na
        # contagem nem no exit code — a suíte fica verde com o teste vermelho. Use
        # `results.append(case(...))`, como abaixo. (Foi exatamente assim que a checagem
        # de isolamento passou a reportar 19/19 com um FAIL na tela.)

        # ---- ISOLAMENTO ENTRE JUÍZES: a invariante que o produto vende ----
        # O painel adversarial só vale se ninguém se lê. Se a resposta de um conselheiro
        # entra no prompt de outro, o consenso vira eco e a confirmação é FALSA — e isso é
        # pior que um bug comum, porque o dossiê sai bonito e mais confiante, não quebrado.
        # Hoje o isolamento é verdade por CONSTRUÇÃO (a mensagem é montada só de material +
        # persona + ask), mas nada travava a invariante: quem adicionasse um "round 2"
        # realimentando saídas não veria nada ficar vermelho. Isto trava.
        RESPOSTA_DE_OUTRO = "VEREDITO DO UNIT ECONOMIST: o NRR não sustenta a tese."
        marcadores = ["DECK XYZ 123"]  # o material compartilhado é o ÚNICO texto comum
        contaminadas = [t["cell_id"] for t in tasks
                        if RESPOSTA_DE_OUTRO in t["messages"][1]["content"]]
        results.append(case("isolamento: nenhuma célula carrega a resposta de outra", not contaminadas))

        # e a prova positiva de que o teste sabe detectar: a MESMA checagem, contra uma
        # tarefa deliberadamente contaminada, tem de acusar. Sem isto o teste acima passa
        # trivialmente e vira decorativo (foi assim que o teste de cobrança de retry passou
        # por meses satisfeito por outro caminho).
        envenenada = dict(tasks[0])
        envenenada["messages"] = [tasks[0]["messages"][0],
                                  {"role": "user",
                                   "content": tasks[0]["messages"][1]["content"]
                                   + "\n\n" + RESPOSTA_DE_OUTRO}]
        results.append(case("isolamento: a checagem ACUSA quando há contaminação (não é decorativa)",
             RESPOSTA_DE_OUTRO in envenenada["messages"][1]["content"]))

        # o conteúdo de uma célula, tirando o material compartilhado e a persona dela, não
        # pode aparecer em outra: é o que garante que a divergência é do modelo/persona e
        # não de contexto herdado.
        sufixos = {}
        for t in tasks:
            corpo = t["messages"][1]["content"][len(shared):]
            sufixos[t["cell_id"]] = corpo
        vazou = [(a, b) for a, ca in sufixos.items() for b, cb in sufixos.items()
                 if a != b and sufixos[a] != sufixos[b] and ca in cb]
        results.append(case("isolamento: o sufixo de uma célula não está contido no de outra", not vazou))
        results.append(case("isolamento: o único texto comum entre células é o material compartilhado",
             all(m in t["messages"][1]["content"] for t in tasks for m in marcadores)))

        print(f"{sum(results)}/{len(results)} testes ok")
        return 0 if all(results) else 1
    finally:
        pin_path.unlink()


if __name__ == "__main__":
    sys.exit(main())
