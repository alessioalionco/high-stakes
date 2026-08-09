# Interactive gates v2 — new flow (2 gates) + recurring flow (neutral core)

> Captures the **user experience** decisions of the gates — how the flow is DISPLAYED, not the
> methodology (which lives in `core/methodology.md`). Harness-neutral: the adapter serves the
> prompts, the core defines each gate's CONTRACT. **v2 redesign** (a redesign
> after 2 real uses): the v1 5-gate flow collapses into **2 gates for a new problem** and **1 for a
> recurring problem**, without losing the kill-switches (which become automatic, not questions).

## Global conventions (hold in every gate)
- **Every user choice comes out numbered** (`1 / 2 / 3`).
- **2 heading levels only:** `## High Stakes Mode · <gate>` + `### section`.
- **Reconciliation flags:** what I assume appears as a correctable ASSERTION ("I assumed X —
  correct only if it is not 100%"), never as a question that blocks the flow.
- **Automatic roles stay HIDDEN** (generalist, anti-thesis, refuter, cell count,
  firewall) → report appendix or on demand.
- **Kill-switches never become a question:** ungrounded number → gap declared in the dossier; egress →
  queries abstracted by default; render gates → code. This runs on its own.

## NEW FLOW (unprecedented problem) — 2 gates

### Gate A — questions + materials + research agenda
Fired by the user's problem. ONE message with three blocks:
1. **Questions that move the ceiling** (★, 3-6, pre-filled with what I already know — the user
   corrects instead of drafting; each with 1 line of "why I ask"). Archetype-aware.
   **The target belief only appears when the object is a PERSUASION ARTIFACT** (deck, narrative,
   positioning — it is the artifact's communication spec, not a verdict expectation; in the other
   archetypes the field does not exist).
2. **Material requests** (docs, internal data, non-public context). Explicit destination
   rule: material and factual answers GO to the advisors (identical evidence pack);
   the target belief and the orchestrator's prior stay with the Chairman (firewall).
3. **Deep-research agenda proposed BY THE MODERATOR** (backward: what the structure of the
   decision demands to know + the orchestrator's benchmark), with the novelty rule: **new topic or
   relevant risk of outside knowledge → full research; repeated topic within validity → cache.**
   The user cuts/adds agenda items.

The user answers (step 3 of the decider's design) and the flow goes straight to Gate B.

### Gate B — pre-dispatch (board + models + cost → GO)
ONE message with the complete picture, everything correctable, nothing re-asked:
- 🎯 **Sharpened brief** (Gate A's readback in a table + reconciliation flags).
- 👥 **Suggested board** (numbered lenses with "what it embodies"; sizing 3→5→7 by complexity;
  standing roles hidden). Curated pool when one exists; from scratch when not.
- 📤 **The archetype's default readback** (A–F forms + default scoring rubric — 1 correctable
  block; becomes a conversation ONLY if the archetype is unprecedented). "Rules of the game"
  shape when the scoring rubric needs ratification (full/new archetype):
  > *"Each advisor's evaluation rules will be: (a) the decision in binary [yes/no]
  > (b) the estimated amount [range] (c) the dimension that weighs most in this case [1-5]. Any
  > rule to add or remove?"*
- 🤖 **PIN roster** (see "Pinned roster" below): 1 confirmation line, not a research project.
- 💰 **Estimated cost DERIVED FROM THE CONTRACT, not from memory** [flow gate]: the adapter runs
  the executable checklist (`python3 -m high_stakes.gate_b_check <manifest.yaml>`) and PASTES its
  output into the gate — the flow steps and the mandatory cost components come from code; the
  model fills in the NUMBERS over code-emitted lines, never composes the list from memory (that
  is exactly how a step ends up silently missing from the cost). Formula in `core/execution.md`;
  passes the cap → stop and ask; below → inform. + egress policy (1 line).
- 📁 **Where it writes** (layout in `core/sections/run-persistence.md`).
- 🔒 **Machine-readable fields in the manifest (the flow gate's contract):** at the GO, the
  adapter writes what Gate B ratified at the top of `manifest.yaml` (column 0):
  `preset: quick|full` · `domain_new: true|false` · `pool: <name>` (if any) ·
  `research: full|waived` (a waiver is a DECLARED decision by the decider, never a default).
  These are the fields the code gate reads before releasing the panel — Gate B without them =
  panel blocked (fail closed).
- Actions: `1 Run · 2 Adjust (say what) · 3 See full charter`.

After the GO: research (if any) + panel + refutation + synthesis + code-verified render — no more stops;
the dossier arrives ready. **The GO→execution hand-off is GATED BY CODE** (the flow gate in the
cell runner, automatic): the panel only fires with an evidence pack that exists, is intact
(write_pack receipt, matching sha, ≥1 successful ask), is CONSUMED in every cell's prompt, and —
on full + new domain without a pool — with an executed pre-pass (≥1 ok cell). After the GO,
transcribe the `gate_b_check` checklist into the run README's journal; strike an item only when
its artifact exists on disk. **Board formed from scratch and accepted → 1 line after the GO:** `1 Save as
pool · 2 This time only` (the library of lenses accumulates; the adapter writes it in the house format).

## RECURRING FLOW (a problem already worked) — 1 gate
Fired by "load problem X". The engine reloads the decision's directory (brief, frozen board,
roster, dossier, ledger — `core/sections/run-persistence.md`) and asks **what to do**,
with a menu adapted to the state:
- `1` **New round / loop** (artifact v2 → same frozen jury, cached research, delta per dimension)
- `2` **Quick run** on new material from the same topic (quick preset; single message → `1 Run`)
- `3` **Drill-down** into the existing dossier (by §N.M anchor)
- `4` **Record the outcome** in the ledger (real calibration of the engine)
- `5` **Close** the decision

## Presets — QUICK × FULL (calibrated by measuring the seats' cost-benefit)

| | **quick** (recurring, reversible topic) | **full** (unprecedented and/or irreversible) |
|---|---|---|
| Lenses | 3 from the pool + generalist | 5-7 + generalist ×M + bull/bear on the crux |
| Jury | **M=3 from the pin** (flagship + 2 cheap) | **M=4** (pin + 4th family) |
| Agenda | moderator (backward+benchmark) | + advisor pre-pass (forward) if the domain is new |
| Research | by novelty/cache (TTL) | same, with the full agenda |
| Scenarios | single (as-is) | in-cell A/B + dud-screen when there are moves to weigh |
| Readback | archetype default | A–F contract ratified at Gate B |
| Gates | 1 (single message → GO) | 2 (Gate A → Gate B) |
| Always, in both | anti-thesis ×1 · external-family refuter · brand-blind synthesis · code render gates · run persistence |

## Pinned roster [replaces v1's per-run floor-check]
The model roster lives in an **instance PIN** (an adapter file) with date, roles and
**validity (~30 days)**. At Gate B it appears as 1 confirmation line. Re-research (the floor-check
method in `core/methodology.md` §3a-ter) runs only when: the pin expires · a relevant release
ships · the domain demands specific competence the pin does not cover. **Invariant intact: the
roster FREEZES within a loop** (the v1→v2 delta demands the same judges). The pin's seats are
decided BY DATA (the seats experiment; see the instance) — not by taste nor by index alone.

## Cost and data-egress gate — lives inside Gate B
- **Cost:** the TOTAL estimate (research + cells + refuter) appears at Gate B, before any
  paid call. Above the cap ($15 default) → stop and ask; below → inform and, with the
  GO, continue with no further stops.
- **Egress:** default = external queries ABSTRACT (never a number/sensitive excerpt); to send a
  sensitive excerpt, show exactly what leaves and ask for OK. Private facts stay internal (cells
  via API, never in external search).
  ⚠️ **This gate is the ONLY egress guard that exists** — and it is human. There is no content
  filter in the code (the denylist that existed was removed; see the header of
  `high_stakes/evidence.py`), and **no-retention routing does not exist**: the engine does not
  consult any provider's retention policy. If you show it and the human OKs it, it leaves.

## Invalidation cascade
With 2 gates, the cascade operates inside Gate B: an edit re-derives the affected blocks and the
gate is re-presented ONLY with what changed (never the whole picture again):
```
brief → board → agenda/evidence → readback/scoring rubric → cost → GO
```
- Brief changed → re-derive board + agenda + default readback.
- Board changed → re-derive agenda (and cost).
- Agenda/evidence changed → re-check readback (new dimension) and cost.
- Readback/scoring rubric changed → cost only.
Rule: declare what was re-derived; never leave a stale block in the gate.

## Origin
Original interactive-flow design, redesigned after the first real uses and the measurement
of the jury's seats. The cost gates and the invalidation cascade were preserved.
