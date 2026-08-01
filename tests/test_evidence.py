#!/usr/bin/env python3
"""test_evidence.py — suíte executável do no-leak do evidence (convenção deste projeto).

Por que existe (T6): o no-leak é a trava que impede material sensível de sair pra um
provider externo. Ele já funcionava — mas SEM teste, e é exatamente a classe de código
onde a falha é silenciosa: se alguém reordenar a checagem pra depois do dispatch, ou se a
denylist chegar vazia por misconfiguração, nada quebra, nada avisa, e o material já foi.

O que se trava aqui:
  - a recusa acontece ANTES de qualquer chamada (espião conta dispatches: tem de ser 0);
  - `denylist=[]` é misconfiguração e falha FECHADA (≠ `None`, que é "público de propósito");
  - a chave de cache inclui a denylist — endurecer a denylist não pode ser burlado por
    cache velho;
  - `leak_suspect` é RE-derivado com a blocklist ATUAL ao ler do cache.
"""
import json
import shutil
import sys
import tempfile
from pathlib import Path

from high_stakes.evidence import (LeakBlocked, _cache_filename, body_leak_suspect,
                      check_no_leak, is_blocked_domain, load_reuse, research,
                              run_asks, tier_for)


class SpyClient:
    """Cliente falso que CONTA dispatches. Se o no-leak falhar, calls > 0 denuncia."""

    def __init__(self, text="resposta", citations=None):
        self.calls = 0
        self._text = text
        self._citations = citations or ["https://www.gartner.com/x"]

    def chat(self, model, messages, **kw):
        self.calls += 1
        return {"text": self._text, "cost_usd": 0.01, "provider": "spy",
                "raw": {"citations": self._citations}}


ASK = {"id": "a1", "natureza": "publica",
       "query": "qual o NRR mediano de SaaS B2B em 2026?"}
SECRET_ASK = {"id": "a2", "natureza": "sensivel",
              "query": "o NRR da Acme Corp caiu abaixo de 100% no Q2?"}


def main() -> int:
    tmp = Path(tempfile.mkdtemp())
    results: list[bool] = []

    def case(name, cond):
        print(("PASS " if cond else "FAIL ") + name)
        results.append(bool(cond))

    try:
        # ---- a trava, no ponto que importa: ANTES do dispatch ----
        spy = SpyClient()
        try:
            research(spy, SECRET_ASK, evidence_model="m", denylist=["Acme"])
            case("T6: query com token sensível é BLOQUEADA", False)
        except LeakBlocked:
            case("T6: query com token sensível é BLOQUEADA", True)
        case("T6: bloqueio acontece ANTES de qualquer call (zero dispatch)", spy.calls == 0)

        spy = SpyClient()
        try:  # o token no ask está capitalizado; a denylist, não
            research(spy, SECRET_ASK, evidence_model="m", denylist=["acme"])
            case("T6: match é case-insensitive", False)
        except LeakBlocked:
            case("T6: match é case-insensitive", spy.calls == 0)

        # ---- REGRESSÃO: o guard tinha bypass trivial por unicode e espaço ----
        # Todas estas passavam antes. Nenhuma é exótica: são reescritas naturais.
        for variante, desc in [
            ("o NRR da Acme  Corp caiu?", "espaço duplo"),
            ("o NRR da Acme-Corp caiu?", "hífen no lugar do espaço"),
            ("o NRR da Acme\u200bCorp caiu?", "zero-width space"),
            ("o NRR da Acme\xa0Corp caiu?", "NBSP"),
            ("o NRR da ACME CORP caiu?", "caixa alta"),
        ]:
            spy = SpyClient()
            try:
                research(spy, {"id": "v", "query": variante}, evidence_model="m",
                         denylist=["Acme Corp"])
                case(f"REGRESSÃO: bypass por {desc} é BLOQUEADO", False)
            except LeakBlocked:
                case(f"REGRESSÃO: bypass por {desc} é BLOQUEADO", spy.calls == 0)

        spy = SpyClient()
        try:  # acento: "Sao Paulo" na denylist tem de pegar "São Paulo"
            research(spy, {"id": "v", "query": "faturamento em São Paulo"},
                     evidence_model="m", denylist=["Sao Paulo"])
            case("REGRESSÃO: bypass por acento é BLOQUEADO", False)
        except LeakBlocked:
            case("REGRESSÃO: bypass por acento é BLOQUEADO", spy.calls == 0)

        # ---- REGRESSÃO QUE EU INTRODUZI: token sem letra ASCII era IGNORADO ----
        # _fold("Сбербанк") == "" e o teste `if tf and tf in q` pulava o token: o guard
        # ficou estritamente MAIS FRACO que o `token.lower()` que ele substituiu.
        for tok, q in [("Сбербанк", "receita do Сбербанк"),
                       ("北京字节跳动", "dados de 北京字节跳动"),
                       ("Ακμή", "o caso Ακμή")]:
            try:
                check_no_leak(q, [tok]); case(f"REGRESSÃO: token {tok!r} bloqueia", False)
            except LeakBlocked:
                case(f"REGRESSÃO: token não-ASCII {tok!r} bloqueia (não é ignorado)", True)

        # letras latinas que o NFKD não decompõe eram APAGADAS -> furavam o match
        for tok, q, desc in [("Orsted", "receita da Ørsted", "Ø"),
                             ("Lodz", "escritório em Łodz", "Ł"),
                             ("Thor", "projeto Þor", "Þ")]:
            try:
                check_no_leak(q, [tok]); case(f"REGRESSÃO: disfarce com {desc} bloqueia", False)
            except LeakBlocked:
                case(f"REGRESSÃO: disfarce com {desc} bloqueia", True)
        try:
            check_no_leak("dados de Aсme Cоrp", ["Acme Corp"])  # с e о cirílicos
            case("REGRESSÃO: homoglifo cirílico bloqueia", False)
        except LeakBlocked:
            case("REGRESSÃO: homoglifo cirílico bloqueia", True)

        # e o custo de usabilidade medido: token curto NÃO pode recusar texto inocente
        try:
            check_no_leak("qual o custo de aquisicao", ["oc"])
            case("REGRESSÃO: token curto não gera recusa falsa (squash só p/ token longo)",
                 True)
        except LeakBlocked:
            case("REGRESSÃO: token curto não gera recusa falsa (squash só p/ token longo)",
                 False)

        # ---- REGRESSÃO: omitir a denylist não pode ser o caminho permissivo ----
        spy = SpyClient()
        try:
            research(spy, SECRET_ASK, evidence_model="m")   # kwarg esquecido
            case("REGRESSÃO: OMITIR a denylist é ERRO (antes era o caminho que despachava)",
                 False)
        except ValueError:
            case("REGRESSÃO: OMITIR a denylist é ERRO (antes era o caminho que despachava)",
                 spy.calls == 0)
        spy = SpyClient()
        try:
            run_asks(spy, [ASK], evidence_model="m", cache_dir=tmp / "om", base_dir=tmp)
            case("REGRESSÃO: run_asks também exige a denylist explícita", False)
        except ValueError:
            case("REGRESSÃO: run_asks também exige a denylist explícita", spy.calls == 0)

        # ---- REGRESSÃO: reuse não pode ler fora do base_dir ----
        # O material reusado entra no prefixo de TODAS as células pagas e vai ao provedor
        # externo — e check_no_leak nunca o vê. O review leu OPENROUTER_API_KEY por aqui.
        base = tmp / "runbase"
        (base / "mat").mkdir(parents=True)
        (base / "mat" / "ok.md").write_text("material legítimo do run")
        (tmp / "segredo.md").write_text("OPENROUTER_API_KEY=sk-nao-pode-sair")
        case("reuse dentro do base_dir funciona",
             "material legítimo" in load_reuse({"id": "r", "reuse": "mat"}, base)["answer"])
        for escape, desc in [("..", "escapa com .."), ("/etc", "é caminho absoluto")]:
            try:
                load_reuse({"id": "r", "reuse": escape}, base)
                case(f"REGRESSÃO: reuse que {desc} é RECUSADO", False)
            except ValueError:
                case(f"REGRESSÃO: reuse que {desc} é RECUSADO", True)

        # REGRESSÃO: conter o diretório não bastava — read_text() segue symlink de ARQUIVO
        import os as _os
        (base / "mat" / "link.md").parent.mkdir(parents=True, exist_ok=True)
        _os.symlink(tmp / "segredo.md", base / "mat" / "roubado.md")
        try:
            r = load_reuse({"id": "r", "reuse": "mat"}, base)
            case("REGRESSÃO: symlink de ARQUIVO apontando pra fora é RECUSADO",
                 "sk-nao-pode-sair" not in r["answer"])
        except ValueError:
            case("REGRESSÃO: symlink de ARQUIVO apontando pra fora é RECUSADO", True)

        # ---- misconfiguração falha FECHADA ----
        spy = SpyClient()
        try:
            research(spy, ASK, evidence_model="m", denylist=[])
            case("T6: denylist=[] é misconfiguração e falha FECHADA", False)
        except ValueError:
            case("T6: denylist=[] é misconfiguração e falha FECHADA", spy.calls == 0)

        spy = SpyClient()
        try:
            run_asks(spy, [ASK], evidence_model="m", cache_dir=tmp / "c1",
                     base_dir=tmp, denylist=[])
            case("T6: run_asks também recusa denylist=[]", False)
        except ValueError:
            case("T6: run_asks também recusa denylist=[]", spy.calls == 0)

        # ---- None = público de propósito (F9), não pode virar bloqueio ----
        spy = SpyClient()
        item = research(spy, ASK, evidence_model="m", denylist=None)
        case("T6: denylist=None (público) despacha normalmente",
             spy.calls == 1 and item["id"] == "a1")

        spy = SpyClient()
        item = research(spy, ASK, evidence_model="m", denylist=["Acme"])
        case("T6: denylist não-vazia sem match na query despacha", spy.calls == 1)

        # ---- cache não pode burlar denylist mais dura ----
        f_none = _cache_filename(ASK, "m", None, None)
        f_deny = _cache_filename(ASK, "m", ["Acme"], None)
        f_deny2 = _cache_filename(ASK, "m", ["Acme", "ARR"], None)
        case("T6: mudar a denylist INVALIDA o cache (não reusa resposta de outra política)",
             len({f_none, f_deny, f_deny2}) == 3)
        case("cache também é keyed por blocklist de domínio",
             _cache_filename(ASK, "m", None, ["x.com"]) != f_none)

        # ---- run_asks: cache hit não re-billa, e re-deriva leak_suspect ----
        cache = tmp / "c2"
        spy = SpyClient(citations=["https://blog.concorrente.com/post"])
        items = run_asks(spy, [ASK], evidence_model="m", cache_dir=cache,
                         base_dir=tmp, denylist=None, domain_blocklist=None)
        case("sem blocklist, item não é suspeito", items[0]["leak_suspect"] is False)
        case("resposta foi cacheada em disco", any(cache.glob("*.json")))

        # blocklist DIFERENTE = chave de cache diferente = re-fetch (não é cache hit).
        # É o desenho: política nova nunca herda resposta julgada pela política velha.
        before = spy.calls
        items = run_asks(spy, [ASK], evidence_model="m", cache_dir=cache,
                         base_dir=tmp, denylist=None, domain_blocklist=["concorrente.com"])
        case("blocklist nova invalida o cache e re-busca", spy.calls == before + 1)
        case("F7: citação de domínio bloqueado marca leak_suspect",
             items[0]["leak_suspect"] is True
             and items[0]["citations"][0]["blocked"] is True)

        # MESMA política -> cache hit de verdade: nem gasta call, nem perde o leak_suspect
        before = spy.calls
        items = run_asks(spy, [ASK], evidence_model="m", cache_dir=cache,
                         base_dir=tmp, denylist=None, domain_blocklist=["concorrente.com"])
        case("cache hit (mesma política) não gasta call nova", spy.calls == before)
        case("T6: leak_suspect sobrevive ao round-trip do cache",
             items[0]["leak_suspect"] is True
             and items[0]["citations"][0]["blocked"] is True)

        # a re-derivação (evidence.py:213-219) é a rede: cache adulterado/antigo dizendo
        # "limpo" não passa — a blocklist ATUAL é reaplicada na leitura.
        hit = max(cache.glob("*.json"), key=lambda p: p.stat().st_mtime)
        d = json.loads(hit.read_text())
        d["leak_suspect"] = False
        d["citations"][0]["blocked"] = False
        hit.write_text(json.dumps(d))
        items = run_asks(spy, [ASK], evidence_model="m", cache_dir=cache,
                         base_dir=tmp, denylist=None, domain_blocklist=["concorrente.com"])
        case("T6: cache dizendo 'limpo' NÃO é aceito — blocklist atual é reaplicada",
             items[0]["leak_suspect"] is True
             and items[0]["citations"][0]["blocked"] is True)

        # cache corrompido re-busca em vez de crashar
        for p in cache.glob("*.json"):
            p.write_text("{ não é json")
        spy2 = SpyClient()
        items = run_asks(spy2, [ASK], evidence_model="m", cache_dir=cache,
                         base_dir=tmp, denylist=None)
        case("cache corrompido re-busca (não crasha)", spy2.calls == 1 and len(items) == 1)

        # ---- corpo menciona domínio bloqueado mesmo sem citation formal ----
        case("F7: corpo citando domínio bloqueado vira leak_suspect",
             body_leak_suspect("segundo a concorrente.com o número é X", ["concorrente.com"]))
        case("F7: sem blocklist, corpo nunca é suspeito",
             body_leak_suspect("qualquer texto", None) is False)
        case("F7: is_blocked_domain é case-insensitive",
             is_blocked_domain("https://WWW.Concorrente.COM/a", ["concorrente.com"]))

        # ---- tier: domínio desconhecido não aterra número ----
        case("tier de domínio desconhecido é 'baixa' (conservador)",
             tier_for("https://blog-aleatorio.xyz/post") == "baixa")

        # ---- check_no_leak isolado ----
        try:
            check_no_leak("nada sensível aqui", ["segredo"])
            case("check_no_leak passa quando não há token", True)
        except LeakBlocked:
            case("check_no_leak passa quando não há token", False)

        print(f"{sum(results)}/{len(results)} testes ok")
        return 0 if all(results) else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
