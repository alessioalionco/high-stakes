#!/usr/bin/env python3
"""test_aggregate.py — suíte executável das agregações determinísticas.

`aggregate.py` implementa os conceitos que os contratos usam para decidir leitura:
**spread como sinal de divergência** e **piso de ruído** — o número que separa "a edição
ajudou" de "o modelo mexeu sozinho". É estatística sem LLM, e portanto o tipo de código
onde um erro não aparece como falha: aparece como número plausível e errado.
"""
import sys

from high_stakes.aggregate import (count_by, dim_stats, is_num, jaccard, noise_floor,
                                   paired_abs_deltas, stats)


def main() -> int:
    results: list[bool] = []

    def case(name, cond):
        print(("PASS " if cond else "FAIL ") + name)
        results.append(bool(cond))

    # ---- is_num: as armadilhas que ele existe para evitar ----
    case("int e float são números", is_num(3) and is_num(2.5))
    case("REGRESSÃO: bool NÃO é número (float(True)==1.0 entraria na média como 1)",
         not is_num(True) and not is_num(False))
    case("REGRESSÃO: nan e inf NÃO são números (envenenariam mean/spread em silêncio)",
         not is_num(float("nan")) and not is_num(float("inf")))
    case("string numérica É aceita, de propósito (modelo devolve '4' como texto)",
         is_num("4") and is_num("2.5"))
    case("None e texto não-numérico não são números", not is_num(None) and not is_num("alto"))

    # ---- stats: o spread é o sinal, não o nível ----
    s = stats([3.0, 4.0, 5.0, 4.0])
    case("stats traz n, mean e os extremos",
         s["n"] == 4 and s["mean"] == 4.0 and s["min"] == 3.0 and s["max"] == 5.0)
    case("spread = max - min (a divergência entre lentes)", s["spread"] == 2.0)
    case("lista vazia devolve n=0 sem crashar", stats([]) == {"n": 0})
    case("um valor só tem spread e desvio zero",
         stats([5.0])["spread"] == 0.0 and stats([5.0])["stdev"] == 0.0)
    case("concordância total tem spread zero", stats([4.0, 4.0, 4.0])["spread"] == 0.0)

    # ---- count_by ----
    recs = [{"v": "sim"}, {"v": "não"}, {"v": "sim"}, {"v": None}]
    c = count_by(recs, lambda r: r["v"])
    case("count_by conta por valor de campo", c["sim"] == 2 and c["não"] == 1)
    case("REGRESSÃO: None conta como categoria própria (não some da contagem)", c[None] == 1)

    # ---- dim_stats: não-numérico é ignorado, não vira zero ----
    recs = [{"d1": 3, "d2": 5}, {"d1": 5, "d2": 5}, {"d1": 4, "d2": "n/a"}]
    ds = dim_stats(recs, ["d1", "d2"], lambda r, d: r.get(d))
    case("dim_stats agrega por dimensão", ds["d1"]["n"] == 3 and ds["d1"]["mean"] == 4.0)
    case("REGRESSÃO: não-numérico é IGNORADO, não vira 0 (0 puxaria a média para baixo)",
         ds["d2"]["n"] == 2 and ds["d2"]["mean"] == 5.0)

    # ---- piso de ruído: decide se um delta é melhora ou variância ----
    r1 = [{"id": "a", "s": 3}, {"id": "b", "s": 4}]
    r2 = [{"id": "a", "s": 4}, {"id": "b", "s": 4}]
    kf, vf = (lambda r: r["id"]), (lambda r: r["s"])

    case("deltas pareiam por chave, não por posição",
         sorted(paired_abs_deltas(r1, r2, kf, vf)) == [0.0, 1.0])
    case("REGRESSÃO: run comparado consigo mesmo dá piso ZERO "
         "(senão todo delta viraria ruído e nada seria sinal)",
         paired_abs_deltas(r1, r1, kf, vf) == [0.0, 0.0])
    case("REGRESSÃO: item sem par é ignorado, nunca comparado com o errado",
         paired_abs_deltas(r1, [{"id": "z", "s": 9}], kf, vf) == [])
    case("valor não-numérico no par é descartado, não vira 0",
         paired_abs_deltas(r1, [{"id": "a", "s": "alto"}], kf, vf) == [])

    nf = noise_floor(r1, r2, kf, {"score": vf})
    case("noise_floor reporta quantos pares comparou", nf["n_pairs"] == 2)
    case("noise_floor é a média dos deltas absolutos", nf["score"] == 0.5)
    case("REGRESSÃO: sem par comparável o piso é None, NÃO 0 "
         "(0 diria que qualquer delta é sinal)",
         noise_floor(r1, [{"id": "z", "s": 1}], kf, {"score": vf})["score"] is None)

    # ---- jaccard ----
    case("jaccard de conjuntos iguais é 1", jaccard({1, 2}, {1, 2}) == 1.0)
    case("jaccard de disjuntos é 0", jaccard({1}, {2}) == 0.0)
    case("REGRESSÃO: dois vazios devolvem None, não divisão por zero",
         jaccard(set(), set()) is None)

    print(f"{sum(results)}/{len(results)} testes ok")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
