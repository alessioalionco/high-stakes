"""
build_gate.py — the opt-in lock on "is this the build you think it is?".

Why it exists: the engine installs as a plugin, and the installed copy DERIVES from what
was published — it drifts. A paid panel run on a build you never published is a mistake
that only surfaces in the invoice, long after the decision it fed.

The design problem. The obvious fix — read the harness's plugin registry and compare —
would make a harness-NEUTRAL engine depend on one harness's on-disk layout (see the note
at the top of `paths.py`). So this module knows nothing about plugins. It knows two
things, and neither is a path:

  1. `require_build_check` in the CONFIG — the user's opt-in. It lives in the config, not
     in the environment, on purpose: an env-var opt-in is defeated by NOT setting it,
     which is precisely what bypassing the launcher does.
  2. `HIGH_STAKES_BUILD_ATTESTATION` in the ENVIRONMENT — written by whatever launcher the
     user trusts, AFTER that launcher verified the build. The launcher is harness-specific;
     the engine is not.

Opted in and no attestation -> refuse. That asymmetry is the whole mechanism: calling the
engine directly instead of through the launcher produces no attestation, and gets refused.

HONEST ABOUT THE THREAT MODEL: the attestation is a plain environment variable. It detects
DRIFT for an operator who wants to be caught; it does not resist an adversary who types the
variable by hand. Anything stronger needs signing, and signing is not what this is for.

Zero engine dependencies beyond `config` (stdlib only).
"""

from __future__ import annotations

import os
import re
from typing import Any

ATTESTATION_ENV = "HIGH_STAKES_BUILD_ATTESTATION"
OPT_IN_KEY = "require_build_check"

# STRICT grammar. Two forms pass the parser, one of which still refuses; everything else
# — empty, truncated, misspelled, a form from some future version — falls through to
# BuildUnverified. An attestation the engine cannot READ is not an attestation.
_OK_RE = re.compile(r"^ok:(\S+)$")
_DRIFT_RE = re.compile(r"^drift:(\S+?)!=(\S+)$")


class BuildUnverified(RuntimeError):
    """Opted in, but nothing vouched for this build — dispatch blocked (fail closed)."""


class BuildDrift(RuntimeError):
    """The launcher vouched and found a MISMATCH — dispatch blocked, both shas reported."""


def _opted_in(cfg: dict[str, Any] | None) -> bool:
    """The opt-in flag, with the config loaded lazily only when the caller passed none.

    A MALFORMED config is allowed to raise, on purpose. `config.load()` already decided
    that case is fatal ("an unreadable config must not silently become 'ran with
    defaults': the cap is one of them"), and swallowing it here would contradict that
    module while producing the worse failure: the operator who opted IN gets the gate
    silently switched off by a typo, and believes they are still covered.

    An ABSENT config does not raise — `_read_toml` returns `{}` for a missing file — so
    the no-opt-in majority is untouched. The only way through here is a config that
    exists and is broken, which is a thing to fix, not to route around.
    """
    if not cfg:
        from . import config
        cfg = config.load()
    return bool(cfg.get(OPT_IN_KEY))


def check_build(cfg: dict[str, Any] | None = None, env: dict[str, str] | None = None) -> None:
    """Verify the build attestation before a paid dispatch. Returns None when it passes.

    No-op unless `require_build_check` is true in the config — that is the path of
    everybody who did not opt in, and it costs one dict lookup and cannot raise.

    When opted in, reads `HIGH_STAKES_BUILD_ATTESTATION` from `env` (default `os.environ`):
      `ok:<sha>`                  -> passes
      `drift:<expected>!=<found>` -> BuildDrift, carrying BOTH shas so the operator can act
      anything else, or absent    -> BuildUnverified
    """
    if not _opted_in(cfg):
        return None

    raw = (os.environ if env is None else env).get(ATTESTATION_ENV) or ""
    value = raw.strip()

    m = _OK_RE.match(value)
    if m:
        return None

    m = _DRIFT_RE.match(value)
    if m:
        expected, found = m.group(1), m.group(2)
        raise BuildDrift(
            f"BUILD DRIFT: the running build does not match the published one "
            f"(expected {expected}, found {found}). The launcher verified and said so "
            f"BEFORE any paid call — $0 spent. Re-install/update the plugin so the "
            f"installed copy is {expected}, then run again."
        )

    detail = (f"{ATTESTATION_ENV} is not set" if not value
              else f"{ATTESTATION_ENV}={raw!r} is not a form this engine understands")
    raise BuildUnverified(
        f"BUILD UNVERIFIED: {detail}. This run has `{OPT_IN_KEY} = true` in its config, "
        f"which means no paid dispatch happens until something vouches for the build. "
        f"Launch through the launcher that sets {ATTESTATION_ENV} "
        f"(`ok:<sha>` when it matches, `drift:<expected>!=<found>` when it does not), "
        f"or set `{OPT_IN_KEY} = false` in the config to turn this gate off. "
        f"Fail closed: an unrecognized attestation never passes."
    )
