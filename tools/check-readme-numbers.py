#!/usr/bin/env python3
"""Confere que os números do README batem com a realidade do repo.

Por que existe: a contagem de testes no README já esteve errada DUAS vezes (dizia 219, e
depois 191, quando eram outros). Atualizar à mão não resolve — o número muda a cada suíte
nova e ninguém lembra. E não é preciosismo: é a primeira afirmação verificável que alguém
lê no repositório. Número errado ali é a assinatura de um projeto que não confere o que
afirma, num motor cujo argumento inteiro é conferir o que se afirma.

Fica FORA da suíte de propósito: rodar as suítes de dentro de uma suíte recursa.

Uso:  python3 tools/check-readme-numbers.py      → exit 0 = bate; 1 = não bate.
"""
import re
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
PADRAO = r"\*\*(\d+) testes em (\d+) suítes — todos os (\d+) módulos"


def main() -> int:
    readme = (RAIZ / "README.md").read_text(encoding="utf-8")
    m = re.search(PADRAO, readme)
    if not m:
        print("README: não achei a frase de cobertura "
              "('**N testes em M suítes — todos os K módulos').")
        return 1

    suites = sorted((RAIZ / "tests").glob("test_*.py"))
    testes = 0
    for t in suites:
        r = subprocess.run([sys.executable, "-m", f"tests.{t.stem}"],
                           cwd=RAIZ, capture_output=True, text=True)
        mm = re.search(r"(\d+)/(\d+) testes ok", r.stdout)
        if not mm:
            print(f"não consegui contar {t.stem} (a suíte imprimiu o total?)")
            return 1
        testes += int(mm.group(2))
    modulos = [p for p in (RAIZ / "high_stakes").glob("*.py") if p.stem != "__init__"]

    real = (testes, len(suites), len(modulos))
    dito = tuple(int(x) for x in m.groups())
    if dito != real:
        print(f"README DESATUALIZADO: diz {dito[0]} testes / {dito[1]} suítes / "
              f"{dito[2]} módulos; real é {real[0]} / {real[1]} / {real[2]}.")
        return 1
    print(f"README bate: {real[0]} testes · {real[1]} suítes · {real[2]} módulos.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
