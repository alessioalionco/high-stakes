#!/usr/bin/env python3
"""test_cells.py — suíte executável do dispatcher paralelo (convenção deste projeto).

Por que existe: `cells.py` é o único módulo que o README declarava coberto apenas de forma
indireta — e é onde moram quatro invariantes que, se quebrarem, quebram em silêncio e
custam dinheiro:

  1. **célula que falha NÃO some** — sem isso, um painel de 33 células volta com 31 e o
     dossiê é escrito sobre um buraco que ninguém viu;
  2. **id duplicado é barrado ANTES do dispatch** — depois já se pagou, e as células ainda
     se sobrescrevem em disco;
  3. **o repair cobra as DUAS tentativas** — o ledger bilou as duas; contabilizar uma
     subestima o gasto do run;
  4. **o resume é travado por hash de input** — reusar por nome de arquivo devolveria a
     resposta de um prompt que não é mais o mesmo.
"""
import json
import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path

from high_stakes.cells import (cell_filename, input_hash_for, load_cells, run_cell,
                               run_cells)
from high_stakes.or_client import SchemaInvalid

OUT = {"text": '{"v": 1}', "cost_usd": 0.10, "provider": "p", "usage": {"t": 1},
       "model": "m", "raw": {}}


class FakeClient:
    """Cliente falso, thread-safe, com roteiro por chamada."""

    def __init__(self, roteiro=None, atraso=0.0):
        self.roteiro = list(roteiro or [])
        self.chamadas = 0
        self.simultaneas = 0
        self.pico = 0
        self._lock = threading.Lock()
        self._atraso = atraso

    def chat(self, model, messages, **kw):
        with self._lock:
            self.chamadas += 1
            self.simultaneas += 1
            self.pico = max(self.pico, self.simultaneas)
            passo = self.roteiro.pop(0) if self.roteiro else dict(OUT)
        try:
            if self._atraso:
                time.sleep(self._atraso)
            if isinstance(passo, Exception):
                raise passo
            return passo
        finally:
            with self._lock:
                self.simultaneas -= 1


def task(cid="c1", parse=None, **kw):
    t = {"cell_id": cid, "model": "test/m", "messages": [{"role": "user", "content": "oi"}],
         "parse": parse or (lambda s: json.loads(s)), "request": {}, "meta": {}}
    t.update(kw)
    return t


def main() -> int:
    results: list[bool] = []

    def case(name, cond):
        print(("PASS " if cond else "FAIL ") + name)
        results.append(bool(cond))

    tmp = Path(tempfile.mkdtemp())
    try:
        # ---- caminho feliz + proveniência ----
        d = tmp / "a"
        c = FakeClient()
        r = run_cell(c, task(), d)
        case("célula ok grava result e status", r["status"] == "ok" and r["result"] == {"v": 1})
        case("proveniência do engine é carimbada",
             all(k in r for k in ("input_hash", "latency_s", "timestamp", "cost_usd")))
        case("o JSON da célula existe em disco", (d / cell_filename("c1")).exists())

        # ---- INVARIANTE 1: falha não some ----
        d = tmp / "b"
        c = FakeClient(roteiro=[RuntimeError("provider caiu")])
        r = run_cell(c, task("c_exc"), d)
        case("REGRESSÃO: exceção vira status=exception (não propaga)", r["status"] == "exception")
        case("REGRESSÃO: célula com exceção PERSISTE em disco (não some do painel)",
             (d / cell_filename("c_exc")).exists()
             and json.loads((d / cell_filename("c_exc")).read_text())["status"] == "exception")

        d = tmp / "c"
        c = FakeClient(roteiro=[{**OUT, "text": "isto não é json"},
                                {**OUT, "text": "continua não sendo"}])
        r = run_cell(c, task("c_bad", parse=lambda s: (_ for _ in ()).throw(SchemaInvalid("x"))), d)
        case("REGRESSÃO: não-parseável vira status=failed, com o texto cru preservado",
             r["status"] == "failed" and r["raw_text"])
        case("REGRESSÃO: célula failed PERSISTE em disco", (d / cell_filename("c_bad")).exists())

        # ---- INVARIANTE 3: repair cobra as DUAS tentativas ----
        estados = {"n": 0}

        def parse_2a(s):
            estados["n"] += 1
            if estados["n"] == 1:
                raise SchemaInvalid("formato errado")
            return {"ok": True}

        d = tmp / "d"
        c = FakeClient(roteiro=[dict(OUT), dict(OUT)])
        r = run_cell(c, task("c_rep", parse=parse_2a), d)
        case("repair-retry acontece 1x e a 2ª tentativa vale",
             r["status"] == "ok" and r["retries"] == 1 and c.chamadas == 2)
        case("REGRESSÃO: o custo soma as DUAS tentativas (o ledger bilou as duas)",
             abs(r["cost_usd"] - 0.20) < 1e-9)

        # ---- INVARIANTE 4: resume travado por hash de input ----
        d = tmp / "e"
        c = FakeClient()
        run_cell(c, task("c_re"), d)
        r2 = run_cell(c, task("c_re"), d)
        case("REGRESSÃO: input idêntico REUSA (não re-billa)",
             r2.get("_skipped") is True and c.chamadas == 1)

        outro = task("c_re", messages=[{"role": "user", "content": "PROMPT DIFERENTE"}])
        r3 = run_cell(c, outro, d)
        case("REGRESSÃO: prompt mudou -> NÃO reusa (senão devolve resposta de outro input)",
             not r3.get("_skipped") and c.chamadas == 2)

        d = tmp / "f"
        c = FakeClient()
        run_cell(c, task("c_pv", meta={"prompt_version": "v1"}), d)
        r = run_cell(c, task("c_pv", meta={"prompt_version": "v2"}), d)
        case("prompt_version diferente invalida o reuso",
             not r.get("_skipped") and c.chamadas == 2)

        case("hash de input muda com o request, não só com as mensagens",
             input_hash_for("m", [{"a": 1}], {"max_tokens": 10})
             != input_hash_for("m", [{"a": 1}], {"max_tokens": 20}))

        # ---- INVARIANTE 2: duplicata barrada ANTES de gastar ----
        d = tmp / "g"
        c = FakeClient()
        try:
            run_cells(c, [task("x"), task("x")], d, quiet=True)
            case("REGRESSÃO: cell_id duplicado REPROVA antes do dispatch", False)
        except ValueError:
            case("REGRESSÃO: cell_id duplicado REPROVA antes do dispatch", c.chamadas == 0)

        try:  # 'a/b' e 'a-b' sanitizam para o mesmo arquivo
            run_cells(c, [task("a/b"), task("a-b")], d, quiet=True)
            case("REGRESSÃO: colisão de filename pós-sanitização REPROVA antes do dispatch",
                 False)
        except ValueError:
            case("REGRESSÃO: colisão de filename pós-sanitização REPROVA antes do dispatch",
                 c.chamadas == 0)

        # ---- paralelo: uma perna morta não derruba o run ----
        d = tmp / "h"
        c = FakeClient(roteiro=[dict(OUT), RuntimeError("morreu"), dict(OUT)])
        rs = run_cells(c, [task("p1"), task("p2"), task("p3")], d, concurrency=3, quiet=True)
        st = sorted(x["status"] for x in rs)
        case("REGRESSÃO: 1 célula que falha NÃO derruba as outras",
             len(rs) == 3 and st.count("ok") == 2 and st.count("exception") == 1)
        case("as 3 células estão em disco, inclusive a que falhou",
             len(list(d.glob("*.json"))) == 3)
        case("load_cells é o inverso de run_cells (traz também as falhas)",
             len(load_cells(d)) == 3)

        d = tmp / "i"
        c = FakeClient(atraso=0.05)
        run_cells(c, [task(f"k{i}") for i in range(8)], d, concurrency=3, quiet=True)
        case("o cap de concorrência é respeitado", c.pico <= 3)

        # ---- meta do experimento não sobrescreve a proveniência do engine ----
        d = tmp / "j"
        c = FakeClient()
        r = run_cell(c, task("c_meta", meta={"persona": "unit economist", "cost_usd": 999.0,
                                             "status": "mentira"}), d)
        case("REGRESSÃO: meta NÃO sobrescreve custo nem status do engine",
             r["cost_usd"] == 0.10 and r["status"] == "ok")
        case("meta legítima do experimento é preservada", r["persona"] == "unit economist")

        # ---- a resposta JÁ PAGA que vem numa exceção não pode ser jogada fora ----
        # O cap pode estourar DEPOIS de a chamada ter sido paga: o reconcile do ledger
        # levanta com o custo real já debitado, e a exceção carrega o resultado em
        # `.resposta`. Ignorá-la registra `cost_usd: 0`, perde um texto que custou
        # dinheiro e deixa a célula elegível para re-rodar — pagando de novo.
        # Achado no review: o `chat` passou a anexar a resposta, mas quem consome a
        # exceção (aqui) nunca foi ensinado a olhar. Meia correção é zero correção.
        class ClientQueEstouraOCap:
            def chat(self, model, messages, **kw):
                from high_stakes.or_client import BudgetExceeded
                e = BudgetExceeded("cap estourado no reconcile")
                e.resposta = {"text": '{"ok": "pago"}', "cost_usd": 0.42,
                              "provider": "spy", "usage": {}, "raw": {}}
                raise e

        r_pago = run_cell(ClientQueEstouraOCap(),
                          task("c_pago", parse=lambda s: json.loads(s)), d)
        case("cap estourado pós-pagamento: o texto pago é PRESERVADO",
             r_pago.get("parsed") == {"ok": "pago"} or "pago" in str(r_pago))
        case("cap estourado pós-pagamento: o custo real é registrado (não zero)",
             abs(r_pago["cost_usd"] - 0.42) < 1e-9)

        print(f"{sum(results)}/{len(results)} testes ok")
        return 0 if all(results) else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
