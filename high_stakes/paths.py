"""Onde estão os recursos do pacote.

Existe por um motivo só: NADA no motor pode calcular caminho relativo a partir do
layout do repo de quem escreveu. Fora dali, `parents[2] / ".claude" / ...` aponta pro
nada — e o erro só aparece na hora do render, depois do dinheiro gasto. Aqui o pacote
responde onde ele mesmo está.

Uso na linha de comando (o adapter descobre os contratos assim):
    python -m high_stakes.paths core
    python -m high_stakes.paths assets
"""
from __future__ import annotations

import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
CORE = PACKAGE_ROOT / "core"
ASSETS = PACKAGE_ROOT / "assets"

# Raiz da instalação (= raiz do plugin): onde vivem boards/ e examples/ que acompanham
# a distribuição. É só-leitura — o que o usuário edita mora no HIGH_STAKES_HOME dele.
INSTALL_ROOT = PACKAGE_ROOT.parent
SHIPPED_BOARDS = INSTALL_ROOT / "boards"
EXAMPLES = INSTALL_ROOT / "examples"

_NAMES = {
    "package": PACKAGE_ROOT, "core": CORE, "assets": ASSETS,
    "install": INSTALL_ROOT, "boards": SHIPPED_BOARDS, "examples": EXAMPLES,
}


def get(name: str) -> Path:
    if name not in _NAMES:
        raise KeyError(f"path desconhecido: {name!r} (use um de {sorted(_NAMES)})")
    return _NAMES[name]


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] in {"-h", "--help"}:
        print(f"uso: python -m high_stakes.paths <{'|'.join(sorted(_NAMES))}>")
        return 2
    try:
        print(get(argv[1]))
    except KeyError as e:
        print(e, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
