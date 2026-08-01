#!/usr/bin/env python3
"""test_xverify.py — suíte executável do X-verify (convenção: PASS/exit≠0)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from high_stakes.or_client import SchemaInvalid  # noqa: E402
from high_stakes.xverify import _parse, build_refute_tasks  # noqa: E402


def case(name, cond):
    print(("PASS" if cond else "FAIL"), name)
    return cond


def fails(text, frag):
    try:
        _parse(text)
        return False
    except SchemaInvalid as e:
        return frag in str(e)


GOOD = ('{"caso_contra": "O material mostra 2.6x com deals nomeados.", '
        '"o_que_sobrevive": "A falta de margem de erro segue de pé.", '
        '"fatos_novos": [{"fato": "runway 15m no Q4", "onde": "quadro trimestral"}], '
        '"veredito_sugerido": "PARCIAL"}')


def main() -> int:
    tasks = build_refute_tasks("MATERIAL X", {"i1": "claim um", "i2": "claim dois"})
    results = [
        case("parse ok com concessão", _parse(GOOD)["veredito_sugerido"] == "PARCIAL"),
        case("cerca de código tolerada", bool(_parse("```json\n" + GOOD + "\n```")["fatos_novos"])),
        case("REGRESSÃO X-V1: concessão vazia REPROVA (anti-viés-advogado)",
             fails(GOOD.replace("A falta de margem de erro segue de pé.", ""), "o_que_sobrevive")),
        case("veredito fora do enum reprova",
             fails(GOOD.replace("PARCIAL", "DESTRUIDO"), "veredito_sugerido")),
        case("fatos_novos opcional (default [])",
             _parse(GOOD.replace('"fatos_novos": [{"fato": "runway 15m no Q4", "onde": "quadro trimestral"}], ', ""))["fatos_novos"] == []),
        case("1 task por item, material no user, ids únicos",
             len(tasks) == 2 and {t["cell_id"] for t in tasks} == {"refuter_i1", "refuter_i2"}
             and all("MATERIAL X" in t["messages"][1]["content"] for t in tasks)),
        case("REGRESSÃO truncamento: max_tokens default alto (>=8000)",
             all(t["request"]["max_tokens"] >= 8000 for t in tasks)),
    ]
    print(f"{sum(results)}/{len(results)} testes ok")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
