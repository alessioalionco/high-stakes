"""
flow_gate.py — the GO→execution hand-off lock: a decision-run panel only fires if the
evidence exists, is the RIGHT evidence, and actually REACHED the cells.

Why it exists: GO→execution was the ONLY hand-off in the engine without a code gate —
and it fell in a real run (a panel was about to fire with no evidence pack and no
pre-pass; the operator caught it by knowing the flow by heart, which an external user
would not). Where there is no code gate, the step gets skipped. This module closes the
hole in the house pattern: fail CLOSED, an error message that names the missing step,
never proceed.

How it arms (automatic and stage-scoped — no opt-in from the runner):
  - `run_cells`/`run_cell` ALWAYS call `check_flow(out_dir, tasks)`;
  - the gate only ACTIVATES when out_dir is the PANEL cells directory of a decision
    run: `<run>/rounds/rN/cells` with `manifest.yaml` at the run root. The pre-pass
    (rounds/rN/prepass), experiments (no manifest) and other stages pass untouched.

What the gate requires (when active):
  1. manifest with the Gate B fields declared (`preset`, `domain_new`, `research`) —
     missing → error with a migration hint;
  2. `research: waived` explicitly declared waives the evidence requirement (a
     VISIBLE opt-out ratified at Gate B, never a default);
  3. evidence pack + flow-receipt.json (emitted by write_pack) with matching sha and
     ≥1 successful ask — a swapped, stale or all-failed pack does not pass;
  4. round pin (`rounds/rN/pack.sha256`): the first dispatch of a round freezes the
     pack sha; the pack cannot change mid-round (new evidence = new round);
  5. preset `full` + new domain without a covering pool → ≥1 pre-pass cell with
     status "ok";
  6. consumption: the pack text is present in the user prompt of EVERY panel cell —
     evidence on disk that never reached the jury does not count.

Zero engine dependencies (stdlib only).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

RECEIPT_FILENAME = "flow-receipt.json"  # emitted by write_pack next to the pack
PACK_RELPATH = Path("research") / "evidence-pack.md"
RECEIPT_RELPATH = Path("research") / RECEIPT_FILENAME
ROUND_PIN_NAME = "pack.sha256"

_ROUND_RE = re.compile(r"r\d+$")
# FLAT (column-0) manifest fields that Gate B declares and the gate reads
_FIELD_RE = re.compile(r"^(preset|domain_new|pool|research):\s*(.+?)\s*$")

_MIGRATION_HINT = (
    "Manifest is missing the Gate B fields (post-flow-gate contract). Add at the top "
    "of manifest.yaml (column 0): `preset: quick|full`, `domain_new: true|false` and, "
    "when applicable, `pool: <name>` / `research: waived`. Legacy run: two lines migrate it."
)


class FlowGateError(RuntimeError):
    """GO→execution hand-off violated — panel dispatch blocked (fail closed)."""


def run_root_for(round_dir: Path) -> Path | None:
    """Run root derived POSITIONALLY from the layout (cells→rN→rounds→root): the
    root is rounds/'s parent, and the manifest must live THERE. No ancestor walk —
    a stray manifest.yaml in some directory above cannot arm the gate on unrelated
    work (review finding: the unbounded walk could bind the wrong manifest).
    None = no manifest at the contract position → experiment layout."""
    root = Path(round_dir).resolve().parent.parent
    if (root / "manifest.yaml").is_file():
        return root
    return None


def panel_round_dir(out_dir: Path) -> Path | None:
    """`<...>/rounds/rN` when out_dir is the PANEL cells dir (`rounds/rN/cells`);
    None for any other stage (prepass, experiment). The predicate is the POSITION
    in the disk layout — never a label/meta field (spoofable)."""
    p = Path(out_dir).resolve()
    if (p.name == "cells" and _ROUND_RE.fullmatch(p.parent.name)
            and p.parent.parent.name == "rounds"):
        return p.parent
    return None


def parse_manifest_fields(manifest_path: Path) -> dict:
    """Flat Gate B fields from the manifest (column-0 `key: value` scan — no yaml
    dependency; round-level data lives in JSON, not here). Fails CLOSED on an
    unreadable manifest or a non-boolean domain_new."""
    try:
        text = Path(manifest_path).read_text()
    except OSError as e:
        raise FlowGateError(f"unreadable manifest: {manifest_path} ({e})") from e
    fields: dict = {}
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        m = _FIELD_RE.match(line)
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip().strip("'\"")
        if key in fields:
            # a duplicate must NOT win silently: a `research: waived` pasted at the
            # end of the file would disable the evidence requirement unseen (review
            # finding). Fail closed — the manifest declares each field ONCE.
            raise FlowGateError(
                f"manifest has a DUPLICATE `{key}:` — Gate B fields appear exactly "
                "once, at the top. Remove the duplicate before running."
            )
        if key == "domain_new":
            if val.lower() not in ("true", "false"):
                raise FlowGateError(
                    f"manifest: `domain_new: {val}` is not true|false. {_MIGRATION_HINT}")
            fields[key] = val.lower() == "true"
        else:
            fields[key] = val
    return fields


def validate_gate_b_fields(fields: dict) -> dict:
    """The SINGLE rule for Gate B fields (shared with gate_b_check — the same
    contract is not validated twice with different wording). Returns a normalized
    {preset, research, domain_new, pool}; fails closed on invalid input.

    Note the deliberate value overlap: `preset: full` (the preset tier) and
    `research: full` (the research mode default) are different fields that happen
    to share the literal "full" — do not conflate their value sets when editing."""
    preset = fields.get("preset")
    if preset not in ("quick", "full"):
        raise FlowGateError(
            f"manifest has no valid `preset` (found: {preset!r}). {_MIGRATION_HINT}")
    research = fields.get("research", "full")
    if research not in ("full", "waived"):
        raise FlowGateError(
            f"manifest: `research: {research}` is not full|waived. {_MIGRATION_HINT}")
    if preset == "full" and "domain_new" not in fields:
        raise FlowGateError(
            f"preset full requires `domain_new: true|false` declared. {_MIGRATION_HINT}")
    return {"preset": preset, "research": research,
            "domain_new": fields.get("domain_new"), "pool": fields.get("pool")}


def _load_receipt(receipt_path: Path) -> dict:
    try:
        receipt = json.loads(receipt_path.read_text())
    except (OSError, json.JSONDecodeError) as e:
        raise FlowGateError(
            f"unreadable/corrupted flow-receipt: {receipt_path} ({e}). Re-generate the "
            "pack via write_pack (the receipt is emitted alongside it)."
        ) from e
    if not isinstance(receipt, dict):
        raise FlowGateError(
            f"flow-receipt is not a JSON object: {receipt_path}. Re-generate via write_pack.")
    return receipt


def _check_prepass(round_dir: Path) -> None:
    """Requires ≥1 PARSEABLE pre-pass cell with status ok — raw file existence does
    not prove the step ran (an empty/failed JSON does not count)."""
    prep_dir = round_dir / "prepass"
    ok = 0
    if prep_dir.is_dir():
        for f in sorted(prep_dir.glob("*.json")):
            try:
                data = json.loads(f.read_text())
            except (OSError, json.JSONDecodeError):
                continue  # a broken artifact does not count as a completed pre-pass
            # valid JSON that is not an object ("ok", []) does not count either —
            # without isinstance this crashed with AttributeError, not FlowGateError.
            if isinstance(data, dict) and data.get("status") == "ok":
                ok += 1
    if ok < 1:
        raise FlowGateError(
            "MISSING STEP: board pre-pass (preset full + new domain without a pool). "
            f"No ok cell in {prep_dir}/. Run the pre-pass (the advisors' forward "
            "questions) BEFORE the panel — its agenda feeds the evidence pack."
        )


def check_flow(out_dir: Path, tasks: list[dict]) -> None:
    """The GO→execution hand-off gate. No-op outside a decision run's panel dispatch;
    when active, validates the evidence→panel chain and raises FlowGateError naming
    the missing step. Called by run_cells/run_cell — requires no opt-in."""
    round_dir = panel_round_dir(out_dir)
    if round_dir is None:
        return  # not a panel dispatch (pre-pass, experiment, other stage)
    run_root = run_root_for(round_dir)
    if run_root is None:
        return  # no manifest.yaml at the contract position: experiment layout

    gb = validate_gate_b_fields(parse_manifest_fields(run_root / "manifest.yaml"))
    preset, research = gb["preset"], gb["research"]

    pack_text: str | None = None
    sha: str | None = None
    if research == "waived":
        # Declared opt-out ratified at Gate B (visible to the decider) — no pack required.
        pass
    else:
        pack_path = run_root / PACK_RELPATH
        if not pack_path.is_file():
            raise FlowGateError(
                f"MISSING STEP: evidence pack. {pack_path} does not exist. Run the "
                "research (run_asks + write_pack) before the panel — a panel without a "
                "pack is parametric opinion, the exact defect this engine exists to "
                "kill. Research genuinely unnecessary? Declare `research: waived` in "
                "the manifest (Gate B)."
            )
        receipt = _load_receipt(run_root / RECEIPT_RELPATH)
        pack_text = pack_path.read_text()
        sha = hashlib.sha256(pack_text.encode("utf-8")).hexdigest()
        if receipt.get("pack_sha256") != sha:
            raise FlowGateError(
                "evidence pack does NOT match the flow-receipt (pack edited/replaced "
                "after assembly). Re-generate via write_pack — the receipt stamps the "
                "exact pack."
            )
        try:
            asks_ok = int(receipt.get("asks_ok", 0))
        except (TypeError, ValueError):
            asks_ok = 0
        if asks_ok < 1:
            raise FlowGateError(
                "evidence pack with ZERO successful asks (receipt asks_ok=0) — an "
                "all-failed pack cannot ground a panel. Re-run the research or fix the "
                "asks; a declared gap is acceptable PER item, not as the whole pack."
            )
        pin = round_dir / ROUND_PIN_NAME
        if pin.is_file() and pin.read_text().strip() != sha:
            raise FlowGateError(
                f"the pack changed MID-round ({round_dir.name}): pin {pin} does "
                "not match the current pack. A round is an immutable snapshot — "
                "new evidence = new round (rN+1), never a silent swap."
            )

    if preset == "full" and gb["domain_new"] and not gb["pool"]:
        _check_prepass(round_dir)

    if pack_text is not None:
        # Consumption — evidence must REACH the jury, not just exist on disk.
        for t in tasks:
            user_contents = [m.get("content", "") for m in (t.get("messages") or [])
                             if m.get("role") == "user"]
            if not any(pack_text in c for c in user_contents):
                raise FlowGateError(
                    f"cell {t.get('cell_id')!r} does NOT carry the evidence pack in its "
                    "user prompt. The contract sends the raw shared material as an "
                    "identical prefix of every cell (prefix caching) — a pack on disk "
                    "that never reaches the jury does not count as evidence."
                )

    if sha is not None:
        # The pin is written ONLY after ALL checks pass (review: writing it before
        # the checks froze the sha on a BLOCKED dispatch — and remediating the
        # gate's own error then deadlocked the round). Atomic via O_EXCL: a race of
        # concurrent workers cannot overwrite; the loser compares and fails closed.
        round_dir.mkdir(parents=True, exist_ok=True)  # new round: dir may not exist
        pin = round_dir / ROUND_PIN_NAME
        try:
            fd = os.open(pin, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w") as fh:
                fh.write(sha + "\n")
        except FileExistsError:
            if pin.read_text().strip() != sha:
                raise FlowGateError(
                    f"the pack changed MID-round ({round_dir.name}): pin {pin} does "
                    "not match the current pack. A round is an immutable snapshot — "
                    "new evidence = new round (rN+1), never a silent swap."
                ) from None
