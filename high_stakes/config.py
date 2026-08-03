"""high-stakes config: precedence, safe defaults, and where the user keeps theirs.

    explicit argument  >  env var  >  ./.high-stakes.toml  >  $HOME/config.toml  >  default

TOML via the stdlib (`tomllib`, py3.11+) — no new dependency, which is the D8 promise.

**The API key does not live here, on purpose.** It comes from `OPENROUTER_API_KEY` in the
environment (or from a gitignored `.env`). A key in a config file is an invitation to an
accidental commit, and this file is meant to be versioned along with the user's project.
"""
from __future__ import annotations

import os
import sys
import tomllib
from pathlib import Path
from typing import Any

from . import paths

DEFAULTS: dict[str, Any] = {
    "runs_dir": "./high-stakes-runs",   # where the decision is recorded
    "boards_dir": None,                  # None -> $HOME/boards, falling back to shipped
    "pin_path": None,                    # None -> $HOME/roster-pin.yaml, likewise
    "cap_usd": 15.0,                     # cap PER RUN
    "concurrency": 8,                    # simultaneous cells
    "timeout_s": 1200,                   # per call
    "on_model_unavailable": "abort",     # "abort" | "skip-cell" (declared in the dossier)
}

_INT_KEYS = {"concurrency", "timeout_s"}
_FLOAT_KEYS = {"cap_usd"}
_ENUMS = {"on_model_unavailable": {"abort", "skip-cell"}}

CONFIG_NAME = "config.toml"
LOCAL_CONFIG = ".high-stakes.toml"


def home() -> Path:
    """The user's directory: their config, boards, and pin. `HIGH_STAKES_HOME` overrides."""
    env = os.environ.get("HIGH_STAKES_HOME")
    return Path(env).expanduser() if env else Path.home() / ".high-stakes"


def _read_toml(p: Path) -> dict:
    try:
        with open(p, "rb") as f:
            return tomllib.load(f)
    except FileNotFoundError:
        return {}
    except (tomllib.TOMLDecodeError, OSError) as e:
        # an unreadable config must not silently become "ran with defaults": the cap is one of them
        raise RuntimeError(f"invalid config at {p}: {e}") from e


def _coerce(key: str, value: Any) -> Any:
    if value is None:
        return None
    if key in _INT_KEYS:
        return int(value)
    if key in _FLOAT_KEYS:
        return float(value)
    if key in _ENUMS and str(value) not in _ENUMS[key]:
        raise ValueError(f"{key}={value!r} is invalid (use one of {sorted(_ENUMS[key])})")
    return value


def load(overrides: dict[str, Any] | None = None, *, cwd: Path | None = None) -> dict:
    """The effective config, precedence already applied. `overrides` = the CLI arguments."""
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
    if unknown:  # a misspelled key name must not pass as "I used the default"
        raise ValueError(f"unknown config key(s): {sorted(unknown)}")
    return {k: _coerce(k, v) for k, v in cfg.items()}


def _user_or_shipped(user: Path, shipped: Path) -> Path:
    """The user's wins if it exists; otherwise what shipped with the install (read-only)."""
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
    """`python -m high_stakes.config` shows the effective config and where each value came from."""
    cfg = load()
    print(f"HIGH_STAKES_HOME : {home()}{'' if home().exists() else '  (does not exist yet)'}")
    print(f"boards_dir       : {boards_dir(cfg)}")
    print(f"pin_path         : {pin_path(cfg)}")
    print(f"runs_dir         : {runs_dir(cfg)}")
    for k in ("cap_usd", "concurrency", "timeout_s", "on_model_unavailable"):
        print(f"{k:<17}: {cfg[k]}")
    key = "set" if os.environ.get("OPENROUTER_API_KEY") else "MISSING"
    print(f"OPENROUTER_API_KEY: {key} (env — never in the config)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
