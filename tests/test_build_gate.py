#!/usr/bin/env python3
"""
test_build_gate.py — contract for the opt-in build gate.

WHY THIS EXISTS. The engine can be installed as a plugin, and the installed copy drifts
from what was published. Running a paid panel on a build you did not publish is the kind
of mistake you only notice in the invoice.

THE DESIGN PROBLEM THIS SOLVES. The obvious fix — have the engine read the harness's
plugin registry and compare — would make a harness-neutral engine depend on one harness's
on-disk layout. So the engine knows NOTHING about plugins. It knows two things:

  1. `require_build_check` in the config — the user's opt-in. It lives in the CONFIG, not
     in the environment, on purpose: an env-var opt-in is defeated by not setting it, which
     is exactly what bypassing the launcher does.
  2. `HIGH_STAKES_BUILD_ATTESTATION` in the environment — supplied by whatever launcher the
     user trusts, after IT verified the build. The launcher is harness-specific; the engine
     is not.

Opted in and no attestation -> refuse. That is what makes it unbypassable: calling the
engine directly, instead of through the launcher, produces no attestation and gets refused.

HONEST ABOUT THE THREAT MODEL: the attestation is a plain environment variable. It detects
DRIFT for an operator who wants to be caught; it does not resist an adversary who sets the
variable by hand. Anything stronger needs signing, and signing is not what this is for.
"""

from __future__ import annotations

import os as _os
import tempfile as _tempfile

# Isolation from the DEVELOPER's configuration, and it must run before high_stakes is imported.
# `config.home()` falls back to ~/.high-stakes, so a machine with `require_build_check = true`
# in its own config made this suite fail on code that is fine — the suite measured the
# environment, not the change. A previous commit claimed to isolate every suite and missed this
# one; the claim is only true when each entry point sets the variable itself.
_os.environ["HIGH_STAKES_HOME"] = _tempfile.mkdtemp(prefix="hs-test-home-")

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    results = []

    def case(name, ok):
        results.append(bool(ok))
        print(f"  {'ok  ' if ok else 'FAIL'} {name}")

    try:
        from high_stakes import build_gate as bg
    except ImportError as e:
        print(f"RED: high_stakes/build_gate.py does not exist yet ({e})")
        return 1

    tmp = Path(tempfile.mkdtemp(prefix="hs-buildgate-"))
    try:
        env0 = {k: v for k, v in os.environ.items()
                if not k.startswith("HIGH_STAKES_")}

        # ── opt-out (the default): the gate is a no-op for everybody else ──────
        case("default config: check_build is a no-op",
             bg.check_build(cfg={}, env=env0) is None)
        case("require_build_check=false: no-op",
             bg.check_build(cfg={"require_build_check": False}, env=env0) is None)

        cfg_on = {"require_build_check": True}

        # ── opted in ──────────────────────────────────────────────────────────
        raised = None
        try:
            bg.check_build(cfg=cfg_on, env=env0)
        except bg.BuildUnverified as e:
            raised = e
        case("opted in + NO attestation -> refuses (this is the unbypassable part)",
             raised is not None)
        case("the refusal names the environment variable it wants",
             raised is not None and "HIGH_STAKES_BUILD_ATTESTATION" in str(raised))
        case("the refusal says how to opt out",
             raised is not None and "require_build_check" in str(raised))

        ok_env = dict(env0, HIGH_STAKES_BUILD_ATTESTATION="ok:7cc8ef6")
        case("opted in + attestation ok -> passes",
             bg.check_build(cfg=cfg_on, env=ok_env) is None)

        drift_env = dict(env0, HIGH_STAKES_BUILD_ATTESTATION="drift:7cc8ef6!=1a2b3c4")
        raised = None
        try:
            bg.check_build(cfg=cfg_on, env=drift_env)
        except bg.BuildDrift as e:
            raised = e
        case("opted in + attestation reports DRIFT -> refuses", raised is not None)
        case("the drift refusal carries both shas so the operator can act",
             raised is not None and "7cc8ef6" in str(raised) and "1a2b3c4" in str(raised))

        for bad in ("", "garbage", "ok", "maybe:7cc8ef6", "ok:"):
            raised = None
            try:
                bg.check_build(cfg=cfg_on, env=dict(env0,
                                                    HIGH_STAKES_BUILD_ATTESTATION=bad))
            except (bg.BuildUnverified, bg.BuildDrift):
                raised = True
            case(f"malformed attestation {bad!r} -> refuses (fails closed)",
                 raised is not None)

        # ── a malformed config must NOT silently disable the gate ─────────────
        # The bad version of this catches everything on config load and returns
        # "not opted in". Then a typo in the config switches the gate off for the one
        # person who asked for it, and they never find out. config.load() already
        # treats an unreadable config as fatal; this must not contradict it.
        broken = tmp / "broken-home"
        broken.mkdir()
        (broken / "config.toml").write_text("require_build_check = true\nthis is not toml [[[\n")
        r = subprocess.run(
            [sys.executable, "-c",
             "from high_stakes.build_gate import check_build; check_build()"],
            cwd=str(tmp), capture_output=True, text=True,
            env=dict(os.environ, HIGH_STAKES_HOME=str(broken), PYTHONPATH=str(ROOT)))
        case("malformed config RAISES instead of silently disabling the gate",
             r.returncode != 0)
        case("and the error names the config, not the attestation",
             "config" in (r.stdout + r.stderr).lower())

        # an ABSENT config is not an error — the no-opt-in majority is untouched
        empty = tmp / "empty-home"
        empty.mkdir()
        r = subprocess.run(
            [sys.executable, "-c",
             "from high_stakes.build_gate import check_build; check_build()"],
            cwd=str(tmp), capture_output=True, text=True,
            env=dict(os.environ, HIGH_STAKES_HOME=str(empty), PYTHONPATH=str(ROOT)))
        case("absent config is a clean no-op (nobody else is affected)",
             r.returncode == 0)

        # ── the gate is actually WIRED into the paid dispatch ─────────────────
        # A gate nobody calls is documentation. This is the part that matters.
        src = (ROOT / "high_stakes" / "cells.py").read_text()
        case("cells.py imports the build gate", "build_gate" in src)
        case("run_cells calls check_build",
             "check_build" in src.split("def run_cells")[-1][:1200])

        # ── config plumbing ───────────────────────────────────────────────────
        from high_stakes import config as cfgmod
        case("require_build_check is a known config key",
             "require_build_check" in cfgmod.DEFAULTS)
        case("it defaults to False (nobody else is affected)",
             cfgmod.DEFAULTS["require_build_check"] is False)

        home = tmp / "home"
        home.mkdir()
        (home / "config.toml").write_text("require_build_check = true\n")
        r = subprocess.run([sys.executable, "-m", "high_stakes.config"],
                           cwd=str(tmp), capture_output=True, text=True,
                           env=dict(os.environ, HIGH_STAKES_HOME=str(home),
                                    PYTHONPATH=str(ROOT)))
        case("config CLI reads require_build_check from the file",
             "require_build_check" in r.stdout and "True" in r.stdout)

        print(f"{sum(results)}/{len(results)} tests ok")
        return 0 if all(results) else 1
    finally:
        __import__("shutil").rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
