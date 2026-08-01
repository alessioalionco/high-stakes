"""Config do high-stakes: precedência, defaults seguros e onde o usuário guarda o dele.

    argumento explícito  >  env var  >  ./.high-stakes.toml  >  $HOME/config.toml  >  default

TOML pela stdlib (`tomllib`, py3.11+) — nenhuma dependência nova, que é a promessa do D8.

**A chave de API não mora aqui, de propósito.** Ela vem de `OPENROUTER_API_KEY` no
ambiente (ou de um `.env` gitignorado). Chave em arquivo de config é convite a commit
acidental, e este arquivo é feito pra ser versionado junto com o projeto do usuário.
"""
from __future__ import annotations

import os
import sys
import tomllib
from pathlib import Path
from typing import Any

from . import paths

DEFAULTS: dict[str, Any] = {
    "runs_dir": "./high-stakes-runs",   # onde a decisão é gravada
    "boards_dir": None,                  # None -> $HOME/boards, com fallback pro embarcado
    "pin_path": None,                    # None -> $HOME/roster-pin.yaml, idem
    "cap_usd": 15.0,                     # teto POR RUN
    "concurrency": 8,                    # células simultâneas
    "timeout_s": 1200,                   # por chamada
    "on_model_unavailable": "abort",     # "abort" | "skip-cell" (declarado no dossiê)
}

_INT_KEYS = {"concurrency", "timeout_s"}
_FLOAT_KEYS = {"cap_usd"}
_ENUMS = {"on_model_unavailable": {"abort", "skip-cell"}}

CONFIG_NAME = "config.toml"
LOCAL_CONFIG = ".high-stakes.toml"


def home() -> Path:
    """Diretório do usuário: config, boards e pin dele. `HIGH_STAKES_HOME` sobrescreve."""
    env = os.environ.get("HIGH_STAKES_HOME")
    return Path(env).expanduser() if env else Path.home() / ".high-stakes"


def _read_toml(p: Path) -> dict:
    try:
        with open(p, "rb") as f:
            return tomllib.load(f)
    except FileNotFoundError:
        return {}
    except (tomllib.TOMLDecodeError, OSError) as e:
        # config ilegível não pode virar "rodou com defaults" silencioso: o cap é um deles
        raise RuntimeError(f"config inválido em {p}: {e}") from e


def _coerce(key: str, value: Any) -> Any:
    if value is None:
        return None
    if key in _INT_KEYS:
        return int(value)
    if key in _FLOAT_KEYS:
        return float(value)
    if key in _ENUMS and str(value) not in _ENUMS[key]:
        raise ValueError(f"{key}={value!r} inválido (use um de {sorted(_ENUMS[key])})")
    return value


def load(overrides: dict[str, Any] | None = None, *, cwd: Path | None = None) -> dict:
    """Config efetivo, já na precedência. `overrides` = os argumentos de CLI."""
    cfg = dict(DEFAULTS)
    cfg.update(_read_toml(home() / CONFIG_NAME))
    cfg.update(_read_toml((cwd or Path.cwd()) / LOCAL_CONFIG))
    for key in DEFAULTS:  # env: HIGH_STAKES_CAP_USD, HIGH_STAKES_RUNS_DIR, ...
        env = os.environ.get(f"HIGH_STAKES_{key.upper()}")
        if env is not None:
            cfg[key] = env
    for k, v in (overrides or {}).items():
        if v is not None:
            cfg[k] = v
    unknown = set(cfg) - set(DEFAULTS)
    if unknown:  # errar o nome da chave não pode passar por "usei o default"
        raise ValueError(f"chave(s) de config desconhecida(s): {sorted(unknown)}")
    return {k: _coerce(k, v) for k, v in cfg.items()}


def _user_or_shipped(user: Path, shipped: Path) -> Path:
    """O do usuário ganha se existir; senão o que veio na instalação (só-leitura)."""
    return user if user.exists() else shipped


def boards_dir(cfg: dict | None = None) -> Path:
    cfg = cfg or load()
    if cfg.get("boards_dir"):
        return Path(cfg["boards_dir"]).expanduser()
    return _user_or_shipped(home() / "boards", paths.SHIPPED_BOARDS)


def pin_path(cfg: dict | None = None) -> Path:
    cfg = cfg or load()
    if cfg.get("pin_path"):
        return Path(cfg["pin_path"]).expanduser()
    return _user_or_shipped(home() / "roster-pin.yaml",
                            paths.SHIPPED_BOARDS / "roster-pin.yaml")


def runs_dir(cfg: dict | None = None) -> Path:
    cfg = cfg or load()
    return Path(cfg["runs_dir"]).expanduser()


def main(argv: list[str]) -> int:
    """`python -m high_stakes.config` mostra o config efetivo e de onde cada coisa veio."""
    cfg = load()
    print(f"HIGH_STAKES_HOME : {home()}{'' if home().exists() else '  (não existe ainda)'}")
    print(f"boards_dir       : {boards_dir(cfg)}")
    print(f"pin_path         : {pin_path(cfg)}")
    print(f"runs_dir         : {runs_dir(cfg)}")
    for k in ("cap_usd", "concurrency", "timeout_s", "on_model_unavailable"):
        print(f"{k:<17}: {cfg[k]}")
    key = "definida" if os.environ.get("OPENROUTER_API_KEY") else "AUSENTE"
    print(f"OPENROUTER_API_KEY: {key} (env — nunca no config)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
