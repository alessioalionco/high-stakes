---
name: high-stakes
description: "High Stakes mode: a rigor engine for high-stakes, ambiguous DECISIONS (deck/slide for an investor, board, or client; narrative; positioning; strategic decision). Refines the ask with a pre-filled brief, grounds the inputs in truth, runs a blind adversarial panel (personas × models from different families) over counterfactual scenarios, refutes its own consensus, and returns a dossier with code-verified quotes. Use when the user says 'enter high stakes mode', 'high stakes mode', 'high stakes', or asks for an artifact/decision that goes out the door and is expensive to redo."
---

# High Stakes mode — adapter

> This file is the **adapter**: triggers, glue, and this installation's paths. The
> entire methodology lives in the core, which is harness-neutral. **This adapter does not
> duplicate the engine — it points to it.**

## The core (read these files — do not work from memory)

The core travels inside the Python package. Find out where it is:

```bash
<plugin-root>/bin/high-stakes paths core
```

> **The plugin root** is two levels above this file (this is
> `<root>/skills/high-stakes/SKILL.md`). Use `${CLAUDE_PLUGIN_ROOT}` if the harness
> exposes it. **Always invoke through `bin/high-stakes`**: `python3 -m high_stakes.X` only
> works if the package is already on `sys.path`, which is false on a clean install.

**Before executing each step, read the corresponding section.** This is a hard
instruction: reading at the start and working from memory afterward is how shallow
dossiers get produced.

| When | Read |
|---|---|
| Always, on activation | `methodology.md` — the 3 organs, floor-check, brand blinding, lossless synthesis |
| At the gates | `sections/interactive-gates.md` — Gate A/Gate B, quick×full presets, cost |
| At the report and the render | `sections/output-contract.md` — taxonomy, the §0–§7 map, the render gate |
| When recording a decision | `sections/run-persistence.md` — layout, sensitive material, manifest |
| When firing paid calls | `execution.md` — capabilities, provider, degradation, cost |

## Entry modes

- **NEW problem** → 2 gates. Gate A: essential questions + materials + investigation
  agenda. Gate B: sharpened brief + board composition + standard report + roster + estimated
  cost → GO.
- **ALREADY-WORKED problem** ("load problem X") → reload the recorded run
  (brief, board, roster, dossier, ledger) and offer the menu: new round · quick run ·
  go deeper on one item · record the real-world outcome · close out.
- **Quick preset** (recurring topic): 3 lenses + generalist, jury of 3, single scenario.
  **Full preset** (novel or irreversible): 5–7 lenses, jury of 4, both gates.

## This installation's paths and commands

```bash
bin/high-stakes config          # effective config + where each value came from
bin/high-stakes paths core      # contracts       (inside the package)
bin/high-stakes paths boards    # lenses that ship with the installation
bin/high-stakes paths examples  # the reference dossier that rule R1 says to open
```

- **Model roster:** `bin/high-stakes config` shows the `pin_path` in effect. The
  user's file (`$HIGH_STAKES_HOME/roster-pin.yaml`, default `~/.high-stakes/`) wins
  over the shipped one. **Freeze it inside a loop** — swapping a judge mid-way kills the
  comparison across rounds.
- **Where the decision is recorded:** the config's `runs_dir` (default `./high-stakes-runs`).
- **Lens pool:** the config's `boards_dir`. When a board is formed from scratch, offer
  to save the pool there for reuse.
- **API key:** `OPENROUTER_API_KEY` in the environment. Never in the config, never in the repo.

## When to activate / NOT activate

- **Explicit trigger:** "enter high stakes mode", "high stakes mode", "high stakes".
- **Auto-suggest** (asking first) only when ALL THREE hold: high stakes (it goes out
  the door or is expensive to redo) · genuine ambiguity (a matter of taste/judgment, not
  fact) · context that lives in the user's head and cannot be inferred from the repository.
- **Do NOT activate → redirect:** mechanical or low-risk task → execute directly with
  defaults and show the assumption · code, build, or config → the normal engineering
  pipeline. Never turn into a blank questionnaire.

## Guardrails

### The dossier render goes through code gates

The rules live in the core (`sections/output-contract.md`, render-gate section) and must
be **re-read at render time** — having read them at the start of the flow does not count.
The three commands, all required to exit 0 before delivering:

```bash
bin/high-stakes render_gate    <report.md>              # §0–§7 structure + jargon
bin/high-stakes qverify        <report.md> <cells_dir>  # every quote is verbatim
bin/high-stakes render_dossier <report.md>              # single-file HTML
```

**Every attributed quote carries `(simulated lens · <model>)` on the attribution line**, and the
§Scope carries the full disclosure. The first protects the clipped fragment; the second,
the document. The gate fails without either of the two.

**The §Scope declares that the personas are simulated.** The lenses carry the names of
real people and the `— **Name**` attribution has the typography of a real citation — and
the dossier circulates. Quote verification guarantees fidelity to what the MODEL wrote
under that lens, never that the person said it. Without the disclosure, the gate fails.

The dossier is written **from the raw cards**, never from aggregate counts. This is the
failure that gave birth to the gate: a dossier assembled from tallies loses the advisors'
voices and turns into an unreadable technical report.

### Mechanism without a build → DECLARE and degrade, never simulate

Wherever a mechanism described in the contract is not built, **declare the degradation
explicitly** and proceed. Never present a contract as if the build existed, and never
pretend a step ran.

### The panel is a stress tool, not an oracle

The engine measures how a decision **withstands attack**; it does not predict how a room
will react. The skeptical lens always runs — including when the audience is friendly. A
panel calibrated to please has no value as a test.
