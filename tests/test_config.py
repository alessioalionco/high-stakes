#!/usr/bin/env python3
"""test_config.py — suíte executável de config e paths (convenção deste projeto: PASS/exit≠0).

Por que existe: `config.py` governa o **teto de gasto** e **onde a decisão é gravada**. Uma
precedência errada não crasha — ela troca o cap por outro número e escreve o run em outro
lugar, silenciosamente. É a última superfície de dinheiro sem rede depois que o ledger
ganhou a dele.

`paths.py` existe para que nada calcule caminho relativo ao layout do repo de quem
escreveu; se ele apontar errado, o erro só aparece no render — com o painel já pago.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from high_stakes import config, paths

ROOT = Path(__file__).resolve().parents[1]
ENV_KEYS = ["HIGH_STAKES_HOME"] + [f"HIGH_STAKES_{k.upper()}" for k in config.DEFAULTS]


class clean_env:
    """Isola as variáveis do produto: teste que vaza env contamina o seguinte."""

    def __enter__(self):
        self._saved = {k: os.environ.pop(k, None) for k in ENV_KEYS}
        return self

    def __exit__(self, *a):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def main() -> int:
    results: list[bool] = []

    def case(name, cond):
        print(("PASS " if cond else "FAIL ") + name)
        results.append(bool(cond))

    tmp = Path(tempfile.mkdtemp())
    try:
        with clean_env():
            home = tmp / "hs-home"
            home.mkdir()
            os.environ["HIGH_STAKES_HOME"] = str(home)
            cwd = tmp / "projeto"
            cwd.mkdir()

            # ---- defaults ----
            cfg = config.load(cwd=cwd)
            case("defaults: cap_usd = 15.0", cfg["cap_usd"] == 15.0)
            case("defaults: on_model_unavailable = abort", cfg["on_model_unavailable"] == "abort")
            case("HIGH_STAKES_HOME é respeitado", config.home() == home)

            # ---- precedência, camada a camada ----
            (home / "config.toml").write_text('cap_usd = 9.0\nconcurrency = 2\n')
            cfg = config.load(cwd=cwd)
            case("config do HOME vence o default", cfg["cap_usd"] == 9.0)

            (cwd / ".high-stakes.toml").write_text('cap_usd = 5.0\n')
            cfg = config.load(cwd=cwd)
            case("config LOCAL vence o do HOME", cfg["cap_usd"] == 5.0)
            case("chave só no HOME sobrevive ao merge do local", cfg["concurrency"] == 2)

            os.environ["HIGH_STAKES_CAP_USD"] = "3.5"
            cfg = config.load(cwd=cwd)
            case("env vence o config local", cfg["cap_usd"] == 3.5)

            cfg = config.load({"cap_usd": 1.25}, cwd=cwd)
            case("argumento explícito vence o env (topo da precedência)", cfg["cap_usd"] == 1.25)

            cfg = config.load({"cap_usd": None}, cwd=cwd)
            case("override None NÃO apaga a camada de baixo", cfg["cap_usd"] == 3.5)
            del os.environ["HIGH_STAKES_CAP_USD"]

            # ---- tipos: env chega como string e o cap é aritmética ----
            os.environ["HIGH_STAKES_CAP_USD"] = "7"
            os.environ["HIGH_STAKES_CONCURRENCY"] = "4"
            cfg = config.load(cwd=cwd)
            case("REGRESSÃO: cap vindo do env vira float (string quebraria a comparação do cap)",
                 isinstance(cfg["cap_usd"], float) and cfg["cap_usd"] == 7.0)
            case("concurrency vira int", isinstance(cfg["concurrency"], int) and cfg["concurrency"] == 4)
            del os.environ["HIGH_STAKES_CAP_USD"], os.environ["HIGH_STAKES_CONCURRENCY"]

            # ---- erro de config NÃO pode virar "rodou com defaults" ----
            try:
                config.load({"on_model_unavailable": "talvez"}, cwd=cwd)
                case("valor fora do enum reprova", False)
            except ValueError:
                case("valor fora do enum reprova", True)

            try:
                config.load({"cap_usdd": 1.0}, cwd=cwd)
                case("REGRESSÃO: chave com nome errado REPROVA (não vira default silencioso)", False)
            except ValueError:
                case("REGRESSÃO: chave com nome errado REPROVA (não vira default silencioso)", True)

            (cwd / ".high-stakes.toml").write_text("cap_usd = = 3\n")
            try:
                config.load(cwd=cwd)
                case("REGRESSÃO: TOML inválido REPROVA (o cap é uma das chaves)", False)
            except RuntimeError:
                case("REGRESSÃO: TOML inválido REPROVA (o cap é uma das chaves)", True)
            (cwd / ".high-stakes.toml").unlink()

            # ---- resolução de boards/pin: usuário ganha, embarcado é o fallback ----
            cfg = config.load(cwd=cwd)
            case("sem boards do usuário, cai no embarcado da instalação",
                 config.boards_dir(cfg) == paths.SHIPPED_BOARDS)
            case("sem pin do usuário, cai no embarcado",
                 config.pin_path(cfg) == paths.SHIPPED_BOARDS / "roster-pin.yaml")

            (home / "boards").mkdir()
            (home / "roster-pin.yaml").write_text("pinned: 2026-01-01\n")
            cfg = config.load(cwd=cwd)
            case("boards do usuário vencem o embarcado", config.boards_dir(cfg) == home / "boards")
            case("pin do usuário vence o embarcado", config.pin_path(cfg) == home / "roster-pin.yaml")

            cfg = config.load({"pin_path": "~/pin-explicito.yaml"}, cwd=cwd)
            case("pin_path explícito vence tudo e expande ~",
                 config.pin_path(cfg) == Path.home() / "pin-explicito.yaml")

            cfg = config.load({"runs_dir": "~/runs"}, cwd=cwd)
            case("runs_dir expande ~", config.runs_dir(cfg) == Path.home() / "runs")

            # ---- a chave de API não pertence ao config ----
            (home / "config.toml").write_text('cap_usd = 9.0\napi_key = "sk-vazando"\n')
            try:
                config.load(cwd=cwd)
                case("REGRESSÃO: chave de API no config REPROVA (não pode ser aceita em silêncio)",
                     False)
            except ValueError:
                case("REGRESSÃO: chave de API no config REPROVA (não pode ser aceita em silêncio)",
                     True)
            (home / "config.toml").write_text("cap_usd = 9.0\n")

        # ---- paths: o pacote sabe onde ele mesmo está ----
        case("core/ existe e traz os contratos",
             (paths.CORE / "methodology.md").exists()
             and (paths.CORE / "sections" / "output-contract.md").exists())
        case("assets/ traz o CSS (dependência de código)", (paths.ASSETS / "dossier.css").exists())
        case("boards embarcados existem", (paths.SHIPPED_BOARDS / "roster-pin.yaml").exists())
        try:
            paths.get("inexistente")
            case("path desconhecido levanta KeyError", False)
        except KeyError:
            case("path desconhecido levanta KeyError", True)

        r = subprocess.run([sys.executable, "-m", "high_stakes.paths", "core"],
                           cwd=ROOT, capture_output=True, text=True)
        case("CLI de paths imprime caminho absoluto existente",
             r.returncode == 0 and Path(r.stdout.strip()).is_dir())
        r = subprocess.run([sys.executable, "-m", "high_stakes.paths"],
                           cwd=ROOT, capture_output=True, text=True)
        case("CLI de paths sem argumento sai 2 (uso)", r.returncode == 2)

        print(f"{sum(results)}/{len(results)} testes ok")
        return 0 if all(results) else 1
    finally:
        __import__("shutil").rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
