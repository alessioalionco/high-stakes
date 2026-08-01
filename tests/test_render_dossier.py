#!/usr/bin/env python3
"""test_render_dossier.py — suíte executável do render (convenção deste projeto: PASS/exit≠0).

Trava a fronteira entre o GATE e o RENDER. O gate estrutural exige apenas a PRESENÇA dos
emojis 🐂/🐻 num fork contestado; o renderer precisa estilizá-los. Quando as duas regras
discordam, o dossiê passa no gate e perde o bloco visual **sem aviso** — foi o que o
exemplo sintético expôs, e é a classe de falha silenciosa que este projeto recusa.
"""
import sys
import tempfile
from pathlib import Path

from high_stakes.render_dossier import load_css, render

ROOT = Path(__file__).resolve().parents[1]

MD = """# Caso — decidir?

## Escopo
Um escopo qualquer para o render exercitar.

## §2 Divergentes

### 2.1 O fork

**🐂 Ensaio a favor.** Negrito antes do emoji.

🐻 **Ensaio contra.** Emoji antes do negrito.

*"Uma epígrafe em voz própria."*

**Em uma frase:** o fecho-veredito.
"""


def main() -> int:
    results: list[bool] = []

    def case(name, cond):
        print(("PASS " if cond else "FAIL ") + name)
        results.append(bool(cond))

    tmp = Path(tempfile.mkdtemp())
    try:
        md = tmp / "r.md"
        md.write_text(MD)
        out = render(md, tmp / "r.html")
        h = out.read_text()

        case("CSS vem do pacote (assets/), não de examples/", len(load_css()) > 1000)
        case("HTML é single-file: CSS embutido, zero referência externa",
             "<style>" in h and "<link " not in h and 'src="http' not in h)
        case("REGRESSÃO: `**🐂` vira bloco bull", 'class="side bull"' in h)
        case("REGRESSÃO: `🐻 **` (emoji primeiro) TAMBÉM vira bloco bear — as duas ordens "
             "passam no gate, logo as duas têm de renderizar", 'class="side bear"' in h)
        case("epígrafe vira tese", 'class="thesis"' in h)
        case("fecho-veredito vira linha de veredito", "verdict-line" in h)
        case("nav sticky presente", "<nav>" in h)

        print(f"{sum(results)}/{len(results)} testes ok")
        return 0 if all(results) else 1
    finally:
        __import__("shutil").rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
