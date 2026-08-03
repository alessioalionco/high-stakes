#!/usr/bin/env python3
"""test_config.py — executable config and paths suite (this project's convention: PASS/exit≠0).

Why it exists: `config.py` governs the **spend cap** and **where the decision is
recorded**. A wrong precedence does not crash — it swaps the cap for another number and
writes the run somewhere else, silently. It is the last money surface without a net now
that the ledger has one of its own.

`paths.py` exists so that nothing computes paths relative to the repo layout of whoever
wrote it; if it points wrong, the error only shows up at render time — with the panel
already paid for.
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
    """Isolates the product's variables: a test that leaks env contaminates the next one."""

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
            cwd = tmp / "project"
            cwd.mkdir()

            # ---- defaults ----
            cfg = config.load(cwd=cwd)
            case("defaults: cap_usd = 15.0", cfg["cap_usd"] == 15.0)
            case("defaults: on_model_unavailable = abort", cfg["on_model_unavailable"] == "abort")
            case("HIGH_STAKES_HOME is honored", config.home() == home)

            # ---- precedence, layer by layer ----
            (home / "config.toml").write_text('cap_usd = 9.0\nconcurrency = 2\n')
            cfg = config.load(cwd=cwd)
            case("HOME config beats the default", cfg["cap_usd"] == 9.0)

            (cwd / ".high-stakes.toml").write_text('cap_usd = 5.0\n')
            cfg = config.load(cwd=cwd)
            case("LOCAL config beats the HOME one", cfg["cap_usd"] == 5.0)
            case("a key set only in HOME survives the local merge", cfg["concurrency"] == 2)

            os.environ["HIGH_STAKES_CAP_USD"] = "3.5"
            cfg = config.load(cwd=cwd)
            case("env beats the local config", cfg["cap_usd"] == 3.5)

            cfg = config.load({"cap_usd": 1.25}, cwd=cwd)
            case("explicit argument beats env (top of the precedence)", cfg["cap_usd"] == 1.25)

            cfg = config.load({"cap_usd": None}, cwd=cwd)
            case("a None override does NOT erase the layer below", cfg["cap_usd"] == 3.5)
            del os.environ["HIGH_STAKES_CAP_USD"]

            # ---- types: env arrives as a string and the cap is arithmetic ----
            os.environ["HIGH_STAKES_CAP_USD"] = "7"
            os.environ["HIGH_STAKES_CONCURRENCY"] = "4"
            cfg = config.load(cwd=cwd)
            case("REGRESSION: a cap coming from env becomes a float (a string would break the cap comparison)",
                 isinstance(cfg["cap_usd"], float) and cfg["cap_usd"] == 7.0)
            case("concurrency becomes an int", isinstance(cfg["concurrency"], int) and cfg["concurrency"] == 4)
            del os.environ["HIGH_STAKES_CAP_USD"], os.environ["HIGH_STAKES_CONCURRENCY"]

            # ---- a config error must NOT become "ran with defaults" ----
            try:
                config.load({"on_model_unavailable": "maybe"}, cwd=cwd)
                case("a value outside the enum fails", False)
            except ValueError:
                case("a value outside the enum fails", True)

            try:
                config.load({"cap_usdd": 1.0}, cwd=cwd)
                case("REGRESSION: a misspelled key FAILS (does not become a silent default)", False)
            except ValueError:
                case("REGRESSION: a misspelled key FAILS (does not become a silent default)", True)

            (cwd / ".high-stakes.toml").write_text("cap_usd = = 3\n")
            try:
                config.load(cwd=cwd)
                case("REGRESSION: invalid TOML FAILS (the cap is one of the keys)", False)
            except RuntimeError:
                case("REGRESSION: invalid TOML FAILS (the cap is one of the keys)", True)
            (cwd / ".high-stakes.toml").unlink()

            # ---- boards/pin resolution: the user wins, shipped is the fallback ----
            cfg = config.load(cwd=cwd)
            case("without user boards, falls back to the shipped ones",
                 config.boards_dir(cfg) == paths.SHIPPED_BOARDS)
            case("without a user pin, falls back to the shipped one",
                 config.pin_path(cfg) == paths.SHIPPED_BOARDS / "roster-pin.yaml")

            (home / "boards").mkdir()
            (home / "roster-pin.yaml").write_text("pinned: 2026-01-01\n")
            cfg = config.load(cwd=cwd)
            case("user boards beat the shipped ones", config.boards_dir(cfg) == home / "boards")
            case("the user pin beats the shipped one", config.pin_path(cfg) == home / "roster-pin.yaml")

            cfg = config.load({"pin_path": "~/pin-explicit.yaml"}, cwd=cwd)
            case("an explicit pin_path beats everything and expands ~",
                 config.pin_path(cfg) == Path.home() / "pin-explicit.yaml")

            cfg = config.load({"runs_dir": "~/runs"}, cwd=cwd)
            case("runs_dir expands ~", config.runs_dir(cfg) == Path.home() / "runs")

            # ---- the API key does not belong in the config ----
            (home / "config.toml").write_text('cap_usd = 9.0\napi_key = "sk-leaking"\n')
            try:
                config.load(cwd=cwd)
                case("REGRESSION: an API key in the config FAILS (must not be accepted in silence)",
                     False)
            except ValueError:
                case("REGRESSION: an API key in the config FAILS (must not be accepted in silence)",
                     True)
            (home / "config.toml").write_text("cap_usd = 9.0\n")

        # ---- paths: the package knows where it itself is ----
        case("core/ exists and carries the contracts",
             (paths.CORE / "methodology.md").exists()
             and (paths.CORE / "sections" / "output-contract.md").exists())
        case("assets/ carries the CSS (a code dependency)", (paths.ASSETS / "dossier.css").exists())
        case("shipped boards exist", (paths.SHIPPED_BOARDS / "roster-pin.yaml").exists())
        try:
            paths.get("nonexistent")
            case("an unknown path raises KeyError", False)
        except KeyError:
            case("an unknown path raises KeyError", True)

        r = subprocess.run([sys.executable, "-m", "high_stakes.paths", "core"],
                           cwd=ROOT, capture_output=True, text=True)
        case("the paths CLI prints an existing absolute path",
             r.returncode == 0 and Path(r.stdout.strip()).is_dir())
        r = subprocess.run([sys.executable, "-m", "high_stakes.paths"],
                           cwd=ROOT, capture_output=True, text=True)
        case("the paths CLI without an argument exits 2 (usage)", r.returncode == 2)

        print(f"{sum(results)}/{len(results)} tests ok")
        return 0 if all(results) else 1
    finally:
        __import__("shutil").rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
