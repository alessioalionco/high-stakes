# Execution contract — what the engine requires from the harness (neutral core)

> **The core defines CAPABILITIES, not a host.** Any harness that offers the 3 capabilities below can
> run the engine. A specific host (a VPS, a local machine, a CI runner) is **one possible host,
> not the definition.** A runbook tied to a specific host was deliberately kept out of here:
> it describes a place where the capabilities exist, not what they are.

## The 3 capabilities required from the harness

1. **Isolated parallel calls.** The matrix is `(N+1)×M` cells, each one **1 call with a clean
   context** — no cell reads another (`core/methodology.md` §3b). The harness must fire N calls
   in parallel and guarantee context isolation between them. This includes the brand-blinding
   separation (§3e): the `label_to_model` map must **not** enter the Chairman/refuter's context —
   it is the harness's responsibility to keep that file out of the judgment context and hand it
   only to the render step.
   **What is verified and what is not:** the isolation between cells is real and comes from
   CONSTRUCTION — `build_quick_tasks` assembles each message only from the material, the persona
   suffix and the ask; there is no path by which one cell's output enters another's prompt. The
   brand-blinding, however, **is verified by nothing** (see the roadmap at the end of this file):
   if the map leaks into the judgment context, the run continues in silence.
2. **Budget tracking with a cap (best-effort, not "hard").** All spend goes through a **reserve-then-reconcile** ledger:
   it pre-debits the estimated ceiling BEFORE dispatch; if the reservation would blow the **cap
   ($15 default)**, it raises before sending the request (overshoot = 0 even with N calls in
   flight). Post-response it reconciles estimate → real cost. The cap is **persistent
   cross-process** (accumulated spend survives re-invocations, otherwise every run would get a
   fresh $cap).
3. **Disk writes.** The engine writes the layout from `core/sections/run-persistence.md` (cells
   full-log, cards, report, manifest with hashes). Atomic writes (tmp + rename) for the ledger
   and the manifest.

> **Reference implementation:** the instance's execution client (pointed at by the adapter) performs
> (1)–(3) over OpenRouter — reserve-then-reconcile cap, retry with backoff, cost via `usage.cost`,
> catalog snapshot for reproducibility. It is a contract reference in the instance, not part of the neutral core.

## Prefix caching (v2 — structural input savings)
The shared material (deck/artifact/evidence pack, identical in every cell) must come as an
**IDENTICAL PREFIX of the prompt** (short generic system + material at the start of the user turn;
the persona-specific content comes AFTER). Providers with prefix caching (OpenAI, Google, Anthropic
and others, via OpenRouter) charge a fraction for repeated input — since the material is the
largest slice of a cell's cost, the run gets cheaper without changing the method. Invariant: the
prefix must be byte-identical across cells of the same model; a persona in the prefix breaks the cache.

## Pinned roster (v2)
The pin (an adapter file) carries judges/refuter/Chairman with date and validity; the harness reads
the pin and only fires a floor-check on trigger (`core/methodology.md` §3a-ter). Each run's
manifest records the EFFECTIVE slug+provider (what actually ran), as always.

## Provider dependency: OpenRouter (named)
The default provider is **OpenRouter** (aggregates the model families into a single endpoint + returns
the real `usage.cost`, which includes internal search cost that token-math misses).
- **Key via env:** `OPENROUTER_API_KEY`, read from the environment or from a gitignored `.env` of the
  instance — **never hardcoded, never logged.**
- **Slugs resolved at run time** by the floor-check (`core/methodology.md` §3a-ter), not written into
  the core — the model catalog comes from the provider and is snapshotted for reproducibility.
- **Pricing fallback:** if `usage.cost` does not come back, fall back to the catalog snapshot's
  token-math. A model with no pricing in the catalog → **fail-closed** (refuses the dispatch; without
  an estimate there is no cap).
- Switching providers = swapping this layer; the rest of the engine does not change (the boundary
  already sits in the client).

## Degradation (the engine degrades gracefully, never simulates)
- **Dead leg** (one cell/model fails — HTTP error, empty, timeout): **continue with the rest + a note
  in the journal** (which leg fell and why). One leg does not take down the run.
- **< 3 live families:** the minimum quorum is **3 distinct families** (models from the same family err in
  correlated ways, so 2 families produce false confidence, not confirmation). If fewer than 3 remain → **abort BEFORE spending more** and report
  (do not run a panel already known to be compromised).
  ⚠️ **Not built** (see the roadmap at the end of this file): the family is recorded in each
  cell's meta, but **nobody counts and nothing aborts**. Today this is what YOU do by looking
  at the journal, not what the engine does for you.
- **The real cost passes the cap mid-run:** the ledger reconciles real > cap → records (flush) and
  **stops the next dispatches** (the estimate can undershoot the real).
- **A mechanism described in the contract but not built** (see the roadmap at the end of this file):
  **DECLARE the degradation and continue** — for example, mark a quote as unverified instead of
  pretending the verification ran. **Never simulate.** A step that pretends to have run is worse
  than a missing step: the signal that something was missing disappears.

## TOTAL cost estimate (for the cost/egress gate — in the v2 flow, inside Gate B)
The cost gate (`core/sections/interactive-gates.md`, §Gate B) shows the sum of ALL paid calls,
not just the cells:

```
total_cost ≈ cells (N personas × M models)
           + research (the pre-pass's deep-research/search — the expensive leg)
           + floor-check (cheap; model research)
           + Chairman (synthesis)
           + refuter (when on)
```

Each component uses the pessimistic per-call ceiling (prompt_tokens × in_price + max_tokens × out_price).
Estimated max run ~$5-8 on the full matrix; **$15 ceiling** (best-effort — see the note at the end
of this file: the estimate can undershoot the real). Only ask the user if the estimate passes
the cap; below it, inform and continue.

## Roadmap — what this contract describes but does NOT exist yet

Listed here so that the degradation above is verifiable instead of vague. Nothing on this list
should be presented as if it worked.

| Not built | What it would do | What to do while it does not exist |
|---|---|---|
| Delta between rounds | compare round N with N−1 (resolved / new / reappeared) | write the delta by hand, or declare there is none |
| Prediction ledger | accumulate micro-predictions × real outcome over months | record the falsifier on each card; the ledger accumulates once there is an outcome |
| Persona grounding | anchor each lens in that advisor's real material | run without grounding and say you ran without |
| Resuming an interrupted **run** (the orchestration) | pick the gated flow back up where it stopped — Gate A, Gate B, panel, refutation, render | restart the round. The PAID part is not lost: `cells.py` skips any cell already on disk whose `input_hash` and `prompt_version` match, so a re-run re-dispatches only what is missing. What is missing is the orchestration state, not the money |
| Adapter for a 2nd harness | run outside this environment | the core/adapter boundary is ready; the adapter is missing |
| No-retention routing | send sensitive material only to a provider with a no-retention policy | pick the provider by hand before the run, or do not send the excerpt — the engine checks nobody's retention policy |
| Source self-verification | open each cited source, confirm it supports the claim, discard the dead/fabricated ones and find a substitute | check the sources by hand; what the engine does today is COLLECT the citation and classify the domain by tier, not verify that the source supports what was said |
| Aborting with fewer than 3 live families | count distinct families among the cells that answered and stop before spending more | check in the journal which legs fell and decide by hand whether the panel still holds; the family is recorded in each cell's meta, but nobody counts |
| Enforced brand-blinding | guarantee the `label_to_model` map does not enter the Chairman/refuter's context | assemble the judgment view with opaque IDs by hand and keep the map in a separate file — nothing verifies the brand did not leak into the context |

**A note on the cap.** The spending ceiling **exists and is code** (reservation before dispatch,
on-disk accounting valid across processes, and an attempt is charged when the provider
produced something or the state was left ambiguous — an explicit refusal is not charged). Even so,
calling it *hard* is too strong: the **estimate can undershoot** the real cost, and what stops
the run in that case is the reconciliation, after the call has already been paid for. Read it as
**best-effort with a ceiling**, not as a guarantee.
