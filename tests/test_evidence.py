#!/usr/bin/env python3
"""test_evidence.py — suíte executável do evidence (convenção deste projeto).

O que se trava aqui:
  - `load_reuse` não lê fora do `base_dir` — nem por `..`, nem por caminho absoluto,
    nem por SYMLINK de arquivo. Este é o caminho com adversário de verdade: o material
    reusado entra no prefixo de TODAS as células pagas e vai ao provedor externo;
  - a blocklist de DOMÍNIO na resposta marca `leak_suspect` (nunca silencioso), e a
    marca é RE-derivada com a blocklist ATUAL ao ler do cache — cache adulterado ou
    antigo dizendo "limpo" não passa;
  - cache por ask: mesma política não re-billa, política nova invalida e re-busca.

Não há mais teste de no-leak de egress: o guard foi REMOVIDO. O porquê está no
cabeçalho de `high_stakes/evidence.py` — não havia adversário nesse caminho, e o
Gate B (humano vendo o que sai) é a trava que ficou.
"""
import json
import shutil
import sys
import tempfile
from pathlib import Path

from high_stakes.evidence import (_cache_filename, body_leak_suspect,
                                  is_blocked_domain, load_reuse, run_asks,
                                  tier_for)


class SpyClient:
    """Cliente falso que CONTA dispatches — é como se mede cache hit vs. re-fetch."""

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


def main() -> int:
    tmp = Path(tempfile.mkdtemp())
    results: list[bool] = []

    def case(name, cond):
        print(("PASS " if cond else "FAIL ") + name)
        results.append(bool(cond))

    try:
        # ---- REGRESSÃO: reuse não pode ler fora do base_dir ----
        # O material reusado entra no prefixo de TODAS as células pagas e vai ao provedor
        # externo. O review leu OPENROUTER_API_KEY por aqui — este caminho TEM adversário.
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

        # ---- run_asks: cache hit não re-billa, e re-deriva leak_suspect ----
        cache = tmp / "c2"
        spy = SpyClient(citations=["https://blog.concorrente.com/post"])
        items = run_asks(spy, [ASK], evidence_model="m", cache_dir=cache,
                         base_dir=tmp, domain_blocklist=None)
        case("sem blocklist, item não é suspeito", items[0]["leak_suspect"] is False)
        case("resposta foi cacheada em disco", any(cache.glob("*.json")))

        # blocklist DIFERENTE = chave de cache diferente = re-fetch (não é cache hit).
        # É o desenho: política nova nunca herda resposta julgada pela política velha.
        before = spy.calls
        items = run_asks(spy, [ASK], evidence_model="m", cache_dir=cache,
                         base_dir=tmp, domain_blocklist=["concorrente.com"])
        case("blocklist nova invalida o cache e re-busca", spy.calls == before + 1)
        case("F7: citação de domínio bloqueado marca leak_suspect",
             items[0]["leak_suspect"] is True
             and items[0]["citations"][0]["blocked"] is True)

        # MESMA política -> cache hit de verdade: nem gasta call, nem perde o leak_suspect
        before = spy.calls
        items = run_asks(spy, [ASK], evidence_model="m", cache_dir=cache,
                         base_dir=tmp, domain_blocklist=["concorrente.com"])
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
                         base_dir=tmp, domain_blocklist=["concorrente.com"])
        case("T6: cache dizendo 'limpo' NÃO é aceito — blocklist atual é reaplicada",
             items[0]["leak_suspect"] is True
             and items[0]["citations"][0]["blocked"] is True)

        # cache corrompido re-busca em vez de crashar
        for p in cache.glob("*.json"):
            p.write_text("{ não é json")
        spy2 = SpyClient()
        items = run_asks(spy2, [ASK], evidence_model="m", cache_dir=cache,
                         base_dir=tmp)
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

        print(f"{sum(results)}/{len(results)} testes ok")
        return 0 if all(results) else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
