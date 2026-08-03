# High Stakes — methodology (neutral core)

> **Status: v2.1 (neutral core).** Body migrated from the adapter into a harness-neutral
> structure. This file is the **engine**: the 3 organs, the flow, board formation + floor-check,
> real brand-blinding and the lossless digest contract.
> It is **self-contained** and only references other files INSIDE `core/` (R4). The harness (Claude
> Code, a future shim) is a **thin adapter** that does the glue and points at the instance's paths.
>
> **Mother principle: "checking means evidence, not confidence"** — confident-and-wrong output is
> risk #1; this is a loop-with-a-bar for decisions. It is a **structured adversarial red-team**,
> NOT an outcome oracle — it finds weakness + RELATIVE signal, never an absolute forecast. gstack
> does this for code; this does it for decisions.
>
> **What was measured, and what was not.** The apparatus went through a test built to kill it: a
> strong, well-armed model against the persona panel. The panel survived — it produced items worth
> adopting that the baseline did not find, one of them capable of changing the decision. But the
> lean summary won on FORM. It is small-n, measured by the person who built the engine: read it as
> signal, not proof.
>
> The operational consequences shape the rest of this document: **consensus does not add truth**
> (similar models err together) · **persona scores are caricature** (different lenses score almost
> identically — the signal lives in the CONTENT of the cards, never in the number) · **evidence
> calibrates more than it discovers** · the panel's value is **precision and filtering**, not
> creativity. And the bottleneck is the summary, not the engine.

## How the core is read (hard instruction, do not work from memory)

Each step of the flow points to the core section that governs it. **Before executing a step, READ
the corresponding section — do not work from memory.** The sections:

- **`core/sections/interactive-gates.md`** — v2 flow (Gate A/Gate B for a new problem · recurring menu) + quick×full presets + cost/egress + cascade.
- **`core/sections/output-contract.md`** — the A–F taxonomy of the readback + the A–F→§0–§7 render map + `needs-human`.
- **`core/sections/run-persistence.md`** — where each real decision writes to disk (layout, sensitivity knob, manifest with hashes).
- **`core/execution.md`** — the execution contract: capabilities required of the harness, OpenRouter, degradation, cost.

## When to activate
- **Explicit trigger:** "enter high stakes mode", "high stakes mode", "high stakes".
- **Auto-suggest** (ask before turning on) when ALL THREE triggers hit:
  1. **High stakes** — it goes outside (investor, board, client) or is expensive to redo.
  2. **Real ambiguity** — several valid interpretations, taste-driven.
  3. **Context in the decider's head** — cannot be inferred from the available material.

## Do NOT activate (redirect)
- Mechanical / already-specified / low-risk task → execute directly with defaults and **show the assumption**, no brief.
- Code / build / config → **engineering pipeline** (investigate→plan→implement→review→ship).
- Never turn into a blank questionnaire. If no context is missing, do not ask.

---

# The flow: 3 organs

```
FLOW v2 (2 gates; see core/sections/interactive-gates.md):
Gate A: pre-filled ★ questions + material requests + THE MODERATOR'S RESEARCH AGENDA
        (target belief ONLY for a persuasion artifact; novelty rule: new topic → full
        research; repeated within validity → cache)
   ↓ user returns answers + materials
Gate B: sharpened brief + board + the archetype's default readback + PIN roster + cost → GO
   ↓ (no more stops)
Organ 2: GROUNDS the inputs (automatic kill-switches) + EVIDENCE BLOCK
Organ 3: BLIND adversarial panel ((N+1)×M matrix) × scenarios (optional, full mode)
         → refutation (external family) → 3-layer synthesis → code-verified dossier
Recurring: load decision from disk → menu (loop/quick/drill-down/outcome/close)
Presets: QUICK (3 lenses+generalist · M=3 from the pin · moderator's agenda · 1 gate) ×
         FULL (5-7 lenses · M=4 · advisor pre-pass if new domain · 2 gates)
```

The **format in which each step is DISPLAYED** (headings, numbering, gates) lives in
`core/sections/interactive-gates.md`. Here is the METHODOLOGY (what each organ does and why).

## Organ 1 — Pre-filled brief (premise)

Fill each field with what is already known from the material and the conversation; mark with ★ only
what is missing and **moves the ceiling**. The 6 fields:

1. **Target belief** — the ONE sentence the reader/decider should walk away with. I propose a default; I ask to sharpen it. (change one word, change the frame)
2. **Who is in the room + what they index on ★** — decider(s), what they historically buy/value, relevant portfolio. *(Becomes the panel roster in Organ 3.)*
3. **The artifact's neighbors ★** — what comes before/after (titles/function), for the handoff.
4. **What external DD/validation will confirm ★** — which clients/refs will be consulted and each one's strongest sentence. Unlocks "the reader concludes on their own".
5. **Competitive benchmark** — who it will be compared against (default: the obvious competitors).
6. **Freedom + constraints** — break the structure? format/size? brand now or later? forbidden claims?

**Minimum viable:** fields **2, 3, 4 + confirm 1**. The rest runs on defaults (and I say which I used).
Present as pre-filled prose with the ★ highlighted — never a wall of questions.

## Organ 2 — Ground the inputs in truth (GATE, what defines honesty)

**Before the panel.** A synthetic score on top of a false number = optimizing a beautiful deck
propped on a lie. Every number/claim in the artifact carries `{value, source, status}`:
- **grounded** — reconciled with the canonical source of truth (financial data, own base). Goes in.
- **unverified** — no source → flagged, does NOT become a premise.
- **suspected-fabricated** — contradicts the source → **stop and raise**.

**Kill-switches (load-bearing):**
- ungrounded number → **refuses to run the panel** on it (flags, does not fabricate).
- claim without a source → "unverified", not a premise.
- contradiction with the canonical source → stop.

*(Example of the format: "reconcile the retention metric with the canonical financial source; do
NOT fabricate a partner percentage, a payback period, or a market benchmark".)* It is the hardest
organ to generalize — it depends on a canonical source of truth existing. When it exists, it is
enforceable; when it does not, the number does not ground and the dossier has to say so.

### Board pre-pass — sets the evidence agenda (before the research runs)
> ⚠️ **v2: the agenda's DEFAULT is the MODERATOR** (backward generators + benchmark, at Gate A) — the
> advisors' pre-pass (forward) runs only in FULL mode on a new domain, where the 3rd layer of
> "I don't know what I don't know" pays for the cost/latency. When it runs, the below applies.
> ⚠️ **Order:** board formation (§3a) and the preset (§3a-bis) **move up to here** — the board must exist
> to be consulted. Form the board right after the brief.

A **LIGHT and blind** pass (each member 1×, single model — the goal is the UNION of the requests, not
measuring divergence; the full matrix is for judgment). Ask each board member:
- **(a)** what evidence/refs/facts would you need to see in order to evaluate this?
- **(b)** along which dimensions would you judge it? *(feeds the scorecard block)*

The requests from (a) go to **two destinations**:
- **→ deep-research/search:** "average price per m² in the area", "S&M efficiency benchmark", "clinical studies of XYZ".
- **→ the user:** private facts — "what is your income? family profile?" — which feed Organ 2's grounding (the board says which fact is missing, instead of me guessing).

Dedup + **prioritize by the number of members who asked** + **research budget ceiling**. Each request is
**routed to the right nature** (see the evidence block); unanswered requests feed the **completeness
critic**. **Runs blind to the target belief** (firewall §3a). It is the 3rd layer of the "I don't know
what I don't know" defense (orchestrator's benchmark → board sets the agenda → board surfaces gaps in
the run).

### Evidence block (part of Organ 2)
**A router by NATURE, not 2 tiers of depth** (quick/deep depth is an orthogonal axis).
**5 natures**, each with its own source/trust/form:
| Nature | Source | Trust |
|---|---|---|
| Academic/scientific | PubMed/Semantic Scholar/Scholar | peer review + citations |
| Industry benchmark | Gartner/Forrester/SaaS benchmarks | analyst reputation (⚠ vendor-sponsored) |
| Structured data | APIs/DBs: FipeZap/Crunchbase/IBGE | data provenance |
| Current/news | recent web | recency + outlet |
| Private/internal | own data and user-injected documents | maximum (goes through the gate) |

Pack = **raw shared material IDENTICAL across all cells** (divergence in the judgment, not in the
facts). Each item: `{nature, source, trust-tier, timestamp+half-life, raw-vs-synthesized,
conflicts-with}`. **Guards:**
- **Raw + synthesis with the line drawn:** synthesis ABOUT the evidence OK, **about the artifact/decision NO**; every claim links to the primary (traversable) + tag; the panel judges against the primaries; **grounding only counts the primary**.
- **Conflicting = both + flag** (evidence divergence is signal; never choose in silence).
- **Trust hierarchy** (the panel weighs by it): primary/peer-reviewed > analyst/official statistics > press > vendor/sponsored > blog/forum. **Strong flag** on low-tier/contested; **low tier does NOT ground a number**.
- **No-leak default + ask-gate:** external queries **abstract** (never our number); to send a sensitive excerpt, **I show what I am about to send and ask for OK**; private facts stay internal. *(The egress gate is formalized in `core/sections/interactive-gates.md`.)* ⚠️ **"sensitive → no-retention provider only" was removed from here:** it is a promise without a mechanism — the engine does not consult any provider's retention policy. It is on the roadmap in `execution.md`. And there is no content filter on the way out: a term denylist existed and was **removed** on purpose (the why is in the header of `high_stakes/evidence.py`). The guard that remains is human, and it is Gate B.
- **Agenda = 3 generators (v1.7):** forward (the board asks in the pre-pass) + **backward (the structure of the decision/claims — what is logically necessary to know, independent of what the board asked)** + the orchestrator's benchmark.
- **Source self-verification loop (v1.7) — ⚠️ NOT BUILT:** the LLM fabricates sources that look real (dead link / one that does not support the claim) and stays confident. The design: the evidence self-verifies as a loop — open each source, confirm it supports the claim, discard the fabricated/dead ones, find a substitute, and only stop when everything checks out. **None of this runs.** What the engine does today is COLLECT the citation and classify the domain by tier (`evidence.py`); nobody opens the source or checks that it supports the claim. Until it exists, the checking is yours — and a high-tier citation can still be invented. It is on the roadmap in `execution.md`.
- **Completeness critic (checklist):** after the pack, before the panel — checks the **3 generators** for unanswered items → **gaps go to you** (attach/accept), no auto-fill. Generalist = backstop in the run.
- **Per-nature TTL in the loop:** half-life by nature (m² days-weeks · news very short · benchmark ~1yr · academic years); a re-run only re-searches what expired (per-item caching).
- **NOVELTY rule (v2, the decider's words):** full research fires when "the topic is new and there
  is a risk of missing outside knowledge"; a repeated topic within validity → cache. Advisor packs
  with a STABLE corpus (book-only) use cheap delta-mode (activating frames, no heavy research);
  heavy research is for living/spoken corpora.
- **Coupling:** the default nature is predicted by the archetype (medical→academic, deck→benchmark+data, proxy→buyer studies), adjustable by the pre-pass.
- **Ask the user:** *"Want to attach any doc for the board? (studies, internal data, non-public context — e.g., non-indexed Gartner)."* → private nature, goes through the gate.

### Scorecard block — *to be refined (open debate; will get more sophisticated)*
BEFORE running the panel: **benchmark research → PROPOSE the dimensions → ask for input** (ratify/edit).
The criterion becomes a **multi-dimensional scorecard**; **perspective ≠ persona** (persona = WHO
judges; perspective = along WHICH axis they score).

**Choosing the dimensions — triangulate 4 sources:** (1) the prior of the decision type (the world's
rubric: fundraising, ISO 42001…); (2) the audience/personas (the board's lenses are already candidate
dimensions); (3) **external benchmark** (research — defense #1 against "I don't know what I don't
know"); (4) the artifact's claims. Tests: **MECE-ish** (if you can maximize everything and still lose,
a dimension is missing) + **outcome-linked**.

**Locked rules:**
- **OPEN REGISTRY of answer types** (not a fixed list — *learning area: "I don't know what I don't know"*). Each type carries: how it **emits** · how it **aggregates** · how the **delta** is computed. Starter: binary (proportion/flips) · ordinal 1-5/1-7 (median+spread) · Likert (median+top-2-box) · quantitative $/% (range/distribution) · categorical/nominal (**mode**, no mean) · ranking (median rank) · pairwise (win-rate) · confidence (median) · free-form (cluster, do not aggregate). **Durable principle: the aggregation RESPECTS the level of measurement** (nominal→mode · ordinal→median · interval→mean) — holds even for a new type. *(Example: in an investment evaluation, "would you invest? [yes/no]" + a value range.)*
- **NO weights, NO composite score** — dimensions are incommensurable → output = **a vector per dimension**, never a scalar. Per-dimension delta, in its own unit.
- **Anchored scale** — define what 1/3/5 look like; **5 genuinely hard** (the current artifact lands in the middle, to discriminate). Without an anchor, one model's 4 ≠ another model's 4. **Anchor ≠ weight** (a marking on the scoring rubric within the dimension, not importance across dimensions). I **draft the 3 anchors**; the user **ratifies the dimensions + the "5" anchor** of each.
- **Spread is signal** — mean AND spread per dimension; high spread = where the risk lives.
- **Delta > absolute** — the primary use is comparative (run N vs N+1); the absolute is a coarse thermometer.
- **Rubric LOCKED per run** (comparable delta); dimensions surfaced by the panel enter the NEXT run's rubric (loop). **Rubrics emerge per decision — no library** (the criterion is ephemeral; the board is what is perennial).

**UX = "rules of the game" + open ask** (with provenance) — in the v2 flow the scoring rubric enters
as the archetype's default at Gate B (shape in `core/sections/interactive-gates.md` §Gate B);
ratification becomes a conversation only for an unprecedented archetype (full mode).

## Organ 3 — Blind adversarial panel + synthesis

### 3a. Forming the board (TASK-DRIVEN — archetype → skills matrix → anchoring → composition)
**Formation is ALWAYS task-driven.** What is perennial is the **library of lenses** (per-domain
pool, kept in the instance by the adapter), NOT the board — it is born/dies with the decision and
**freezes during the loop** (fresh only per new decision, otherwise the v1→v2 delta compares
different things).

**Opening question = origin of the pool:**
> *"For this decision, do I use a group/library you have already curated, or do I build the board from scratch for this problem?"*
> **[A]** curated pool · **[B]** from scratch (new problem; I propose).

Both land in the SAME engine. The old "co-formed" is not a mode — it is the **ratification gate** (Step 6), which always runs.

**Step 0 — Classify the archetype** (defines the qualification criterion; most are hybrids):
| Archetype | Covers by | Qualifies by | Members | E.g. |
|---|---|---|---|---|
| **Expert/specialty** | necessary disciplines | credential + peer recognition | complementary | tumor board, real estate |
| **Adversarial/skeptic** | ways-to-fail | axis authority | adversarial | deck, CRO plan |
| **Audience-proxy** | persona segments | **representativeness (NOT expertise)** | buyer samples | landing page |

**Step 1 — Coverage map (skills matrix):** list what NEEDS to be covered — disciplines /
ways-to-fail / persona segments. **This is where the intelligence lives** (an unlisted axis = blind
spot → the generalist's job).
**Step 2 — 1 seat per item.**
**Step 3 — Qualify:** the signal is **recognition-BY-peers** (cited by experts, guideline
authorship, track record, h-index), **NOT volume** of output nor fame. **Fame ≠ authority.**
**Step 4 — Anchor** (the same machine for all 3, only the target changes):
- high named density → **name-anchor** (the name = seasoning) **+ the axis spec underneath** (substance; never the name alone).
- low density (local/niche/regional) → **spec-anchor is PRIMARY** (from guidelines/data).
- audience-proxy → **archetype profile** (buyer studies and public reviews, filtered) + **a private layer (brain win/loss)** that localizes and kills the stereotype.

> **Anchoring the persona in the advisor's real material — measured, NOT built.** The pattern
> observed in 2 experiments: when the advisor is heavily documented, anchoring **sharpens**
> (calibrates better, attributes better, brings in the recent); when thinly documented, it
> **discovers** (new objection categories appear, and genuine divergence between the lenses). Two
> experiments are not a law — treat it as a hypothesis with supporting evidence. **Since it is not
> built, do not simulate it:** run without anchoring and declare that you ran without.

**Step 5 — Composition (coverage + 3 standing roles):**
- coverage lenses: **3** (simple) → **5** → **7** (complex);
- **+ generalist ×M** (1/model — the forgotten axis; divergence across the M = anti-groupthink);
- **+ anti-thesis ×1** (attacks the premise/"is this even the right question?");
- **bull/bear on the crux axis** (a pair on the SAME axis — does not break orthogonality: opposite vector = high spread = "the risk lives here"; only on the crux).
- **Two dials:** coverage scales with *complexity*; adversarial depth (bull/bear+anti-thesis+M+loop) scales with *risk/reversibility*.

**Step 6 — Ratification gate:** show the roster + the axes + **each seat's known bias** +
provenance → you swap/confirm. Deep co-forming only if audience-specific or on push-back. *(Bias =
feature: the urologist pushes toward surgery, the radiation oncologist cancels it out.)*

**Firewall:** the cells see the **charter** (what/who/job) + artifact + evidence pack — **NEVER the
target belief** (it stays with me; otherwise it contaminates). The pre-pass also runs blind.

### 3a-bis. Presets — QUICK × FULL (v2, Jul 22; supersedes the "always max" of Jul 02)
Two presets, both a blind `(N+1)×M` matrix with anti-thesis, refuter and brand-blind synthesis
(what is NEVER cut): **QUICK** (recurring/reversible topic — 3 lenses + generalist, M=3 from the
pin, moderator's agenda, single scenario, default readback, 1 gate, ~$1.5-2.5) and **FULL**
(unprecedented and/or irreversible — 5-7 lenses, M=4 with the pin's 4th family, advisor pre-pass
if the domain is new, scenarios+dud-screen when there are moves to weigh, 2 gates). Full table in
`core/sections/interactive-gates.md`. The **$15 hard cap** remains as the guard (the harness
enforces it; see `core/execution.md`). The routing rule stands: a question of FACT/verifiable → 1
model, no panel, always stating the cut (sovereignty > economy). The additional structural saving
comes from **prefix caching** (shared material first in the prompt — see `core/execution.md`).

### 3a-ter. MODEL roster — PIN with validity + floor-check on trigger (v2) [M1]
> **The roster lives in an install pin, with validity (~30 days)** — at the gate
> it is 1 confirmation line, not a research project. The floor-check method below runs on TRIGGER:
> pin expired · relevant release · a domain demanding competence the pin does not cover. **The
> pin's seats are decided BY DATA** (the seats experiment — same cells, candidates side by side,
> marginal contribution per dollar), not by index/taste.

When the floor-check runs: **I research, I recommend (how many + which), the user only approves.**
It measures QUALITY by a trustworthy source, not popularity/spend.

**Method (sources on each run):**
- **Intelligence floor:** AA Intelligence Index (or the current equivalent).
- **Domain competence:** the domain's benchmark (HealthBench for health · LegalBench for legal · finance-bench…) — the floor for *this* archetype.
- **Recency:** releases from the last few weeks (catches the new model before the default goes stale).
- **Diversity:** families of distinct lineage above the floor — **avoiding the Chairman's family** (with a Chairman from one family, do not seat a judge from the same family: it doubles the family → same-family self-preference, measured in the correlated-errors literature).

**Number of judges (M, the models — not to be confused with N=the matrix's lenses) = the 3rd dial:**
M=3 on quick (pin: flagship + 2 cheap ones of distinct lineages) → M=4 on full/irreversible (adds
the pin's 4th family). It saturates at 3 (coverage 93→99→100%; the 4th/5th ≈ +0 and correlated);
the 4th buys anti-correlation, not coverage. The number is noise; the decision divergence is the signal.

**PIN composition:** distinct families above the floor, a Chairman from a family *outside* the
judges' (the floor-check caught exactly this mistake in a previous default: judge + Chairman from
the same family). The concrete slugs live in the instance's pin, not here (otherwise the core
rots). The experimental history pins GLM as the low-cost family for **comparability** (the
experiments ran on it) — that holds for the EXPERIMENTS, which keep their own fixed roster.

**Invariant (otherwise the loop breaks):** the pin's roster **freezes within each loop** (v1→v2
demands the same judges for the delta to hold). Between decisions, the pin holds until a trigger
(validity expired · relevant release · a domain outside the pin's competence) — then the
floor-check re-runs and the pin is re-written.

### 3b. The matrix (coverage + standing roles) × M — BLIND, no rounds
- **Coverage lenses** (each persona = an AXIS, not a famous name; 3→5→7 by complexity) **+ 3 standing roles**: **generalist ×M** (anti-groupthink; the forgotten axis; auto-add, does NOT live in the pool) · **anti-thesis ×1** (attacks the premise) · **bull/bear on the crux axis** (a pair on the same axis = high spread). See §3a for the formation logic.
- **Cell = (persona × model), 1 ISOLATED PARALLEL call** (multi-agent — the orchestrator guarantees the clean context; nobody reads anybody; **no rounds**). ✅ **Verified in the code, and by CONSTRUCTION, not by a gate:** `build_quick_tasks` assembles each cell's message from three inputs and nothing else — the material (byte-identical prefix), the persona suffix and the archetype's ask. There is no path by which one cell's answer enters another's prompt; the only append is the format retry, which returns to the cell its OWN answer. Honest caveat: `ask_builder` and `parse` are functions passed in from outside, and **no test locks this invariant** — whoever adds a "round 2" tomorrow that feeds outputs back in will see nothing turn red. The divergence is the PRODUCT. Retire the "1 prompt/model with all the personas" (contaminates → kills the persona divergence). *(The "isolated parallel calls" capability is required of the harness — see `core/execution.md`.)*
- Single preset: full matrix (see §3a-bis; `value` retired).

**Each cell's output schema — a taxonomy of 6 actions + scores** (each type becomes an ACTION;
everything is clustered in the synthesis — 3 board members on 2 models asking for NRR = a
high-confidence blind spot):

| Output | Blind spot of… | Action |
|---|---|---|
| Liked it | (strength) | KEEP/amplify |
| Did not like it | artifact | FIX |
| Would do differently | artifact (alternative) | REPLACE |
| Would like to see / would ask | artifact (missing content — the NRR/GRR case) | ADD |
| Indifferent / noise | artifact (low impact) | **CUT** (rare and precious) |
| Missing dimension | rubric (meta) | RE-SCORE (loop) |
| Scores (vector per dimension + justification + spread) | measurement | thermometer + delta |

⚠️ **a RUBRIC blind spot** (a dimension was missing) ≠ **an ARTIFACT blind spot** (content was
missing — the board wanted to see NRR). The generalist = the instrument for the 1st; the whole
panel surfaces the 2nd. *(The CONSUMPTION/render A–F taxonomy that types the readback lives in
`core/sections/output-contract.md`.)*

### 3c. Counterfactual scenarios — OPTIONAL
Run the panel over alternative VERSIONS (not just "score the as-is") → relative comparison =
marginal analysis. **Only when there are moves to weigh** ("find the weaknesses of this as-is" =
zero scenarios). They run **INSIDE the cell** (the judge compares; ×1, not ×S; **randomized order**
anti-pattern-completion).
- **Who proposes:** the decider seeds the candidates + **the board proposes the ones in the decider's blind spot** (blind to the target belief) + the decider ratifies.
- **TWO BRANCHES (depends on the archetype):**
  - **Artifact-variation** (adversarial/audience): CUMULATIVE edits → **default BUNDLE** (as-is vs everything-together), **without measuring individual weight**. **Dud-screen:** the panel also answers *"is there a change you would REMOVE/that makes it worse?"* = **binary flag**; only the flagged one runs **in isolation** (confirms the dud). *(Without this the bundle smuggles in the bad change: an edit that makes things WORSE disappears inside the package.)* Isolation = **only on suspicion**, never the power set.
  - **Decision-option** (expert): mutually EXCLUSIVE forks (surgery vs radiation vs surveillance) → **collapses into the Protocol Map (§3f)**, no new mechanism.

### 3d. Refutation step (blind) — the BATCH calibrates, the PER-ITEM deepens
Before marking a consensus as a blocker/strong recommendation, a voice from a distinct family tries
to **REFUTE** it — independent, does not read the others. Consensus that survives = high confidence;
refuted → "needs human". **A 2-stage design (measured in the refutation experiment):**
(1) **BATCH** (claims side by side, 1 call) — it is what CALIBRATES verdicts (displays the 3 levels);
(2) **PER-ITEM** (mechanized in the engine) — a DEPTH generator over
the items that become blockers/forks: mandatory concession (anti-lawyer), checkable new facts
as the main product (verify against the material before the dossier), verdict only SUGGESTED.
⚠️ Measured bias: per-item with a purely adversarial role returns REFUTED on ~everything (8/8 in
the experiment) — which is why it never decides a verdict alone. In use, the per-item corrected an
error by the Chairman himself in a published dossier.

### 3e. Brand-blinding in the judgment view — procedure, not a guard [M2]

> ⚠️ **Read this before the rest of the section.** What is described below is the
> **procedure** the judgment view must follow. **Nothing in the code enforces it.** There is
> no `label_to_model` in Python, there is no check that the brand stayed out of the context,
> and the Chairman/refuter step is not code — it is contract, executed by whoever
> orchestrates. If the brand leaks into the judgment context, the run continues and nobody warns
> you. Calling this "real" blinding was too strong: it is blinding **by discipline**. It is on the
> roadmap in `execution.md`.
> Stolen from llm-council (Karpathy) + self-preference research (models inflate their own/same-family
> −38%/+90%). **Making it explicit ≠ "blind":** here "blind" means **no rounds and no brand**, not
> no instruction. The target-belief firewall (§3a) is one thing; brand-blinding is another.

Two separate views of the SAME card:
- **Judgment view (brand-blind):** the Chairman and the refuter (§3d) reason over cards identified
  by **OPAQUE IDs** (`C1`, `C2`, `C3`…) — the model's brand **does not appear** ("via <model>" is
  gone). The **`label_to_model`** map (which ID = which model) stays **OUT of the context** of the
  Chairman/refuter: it is a **separate file that only the RENDER step reads**. The judgment engine
  never receives it.
- **Display view (personified):** the reattribution (`C2` → "The Unit Economist (via Opus 4.8)") happens **only at
  render**, for the user. Personification and groundedness stay intact.

It complements the family rule (§3a-ter, which takes the family out of the ROOM): this one **blinds
the brand INSIDE the room**. Implementation invariant: if `label_to_model` leaks into the judgment
context, the blinding is broken — the harness must guarantee the separation (see `core/execution.md`).

### 3f. 3-layer synthesis (divergence is the product; recommendation ON TOP, not instead)
Do NOT collapse into a "golden path". In this order:
1. **Protocol Map** — the divergence preserved: each cluster of views = one coherent protocol, with a precondition + what it optimizes ("follow A if you want speed; B if you want safety").
2. **Red-team + marginal analysis** — each protocol's weakness, what moves the needle, what is a dud, honest ceiling vs anchor.
3. **Chairman's recommendation** (the host model) — "I incorporate this, I drop that, and why", SITTING on top of the visible map. It is opinionated — but **the pen stays in the decider's hand**. ⚠️ The host model's prior does NOT get extra weight (it already has a generalist in the matrix); the Chairman arbitrates, does not re-vote.

**The summary contract — lossless:**
1. **Convergence → compress with weight** (N cells repeating = 1 item, weight N; the repetition is noise, the weight is the signal).
2. **Divergence → structured fork, never an average/choice** (opposing theses + precondition). It is the anti-collapse guard: mediating two opposing theses produces a third one that nobody defends.
3. **A unique item survives on MERIT, not by vote** (in the experiment, the item that changed the decision was nearly invisible in frequency — it would have died in a vote count).
4. **Merge preserves the more SPECIFIC version** (nuance beats generic).
5. **Digest = attention, not storage** — every item links to the raw cards (drill-down); discard only by factual refutation, and it goes to the "discarded and why" appendix.
6. **Verbatim quotes verified by code** (built; see the render gate on
   trigger): every attributed quote + the dossier's epigraph is checked as a substring of the
   advisor's raw card (quote/emphasis/whitespace normalization; ellipses verified per segment; a
   match on the wrong advisor = `divergent_attribution`). The mechanical verifier is pointed at by
   the adapter and runs alongside the render gate. It has already rejected 18 of 35 quotes in a finished dossier, all distorted by the editor itself.

The render that consumes this contract (§0–§7, personified) is specified in
`core/sections/output-contract.md`.

### 3g. Loop mode — ask after the 1st round
Offer to iterate: *"Want to enter loop mode? You bring the new version incorporating what you
decided, I re-run the panel and show the DELTA on the scorecard."*
- The user brings the **new version of the inputs** → **re-run** → the synthesis shows the **delta per dimension** (defensibility 2.8→4.1 etc.). Up = it helped; flat/down = the edit did not pay off.
- **Research is CACHED** on the re-run (the evidence did not change; only the panel re-judges the new artifact) → fast and cheap.
- **Loop charter (v1.7, `/goal`-style — until plateau, not on a cadence):** GOAL (measurable end state) / WHERE / HOW TO WORK / **HOW TO CHECK YOURSELF** (evidence, not confidence) / HOW TO REMEMBER (state file = persistence between runs, see `core/sections/run-persistence.md`) / WHEN TO STOP (success · no-op · blocker · plateau=noise floor · limit). **"Needs me" list:** a human-only decision item (spending capital, deleting, sending outside) → stop at it, log, move on = the ask-gate inside the loop.
- **Noise floor:** re-running a subset with the SAME inputs measures the reproduction variance = the floor; only a delta that **clears the floor AND moves multiple cells** counts as improvement (otherwise 3.2→3.5 = false precision).
- **The loop's MUST-HAVE = attribution split** (not A/B inside the cell): **(1) a FRESH-BLIND score** of v2 (the cell does not see v1; the **orchestrator** computes the delta) → a clean number; **(2) a light attribution pass** (shows v1+v2 → "why did it change?", dimension by dimension; clustered = high confidence). A/B-in-the-cell is rejected: it introduces a systematic pro-improvement bias that the noise floor does NOT catch. The delta is the product → it cannot be contaminated. *(The version comparator and the prediction ledger are NOT built; the disk contract for both is in `core/sections/run-persistence.md`.)*
- The **delta is the robust relative signal** — it replaces the absolute forecast (which the external red-team killed).

---

## Run with the loop open
Front-load the context-constraints at the start **AND** keep the loop open for mid-course corrections —
that is where the gold shows up (the quality jump usually comes from a mid-flight correction, not from
the perfect brief). Defaults unless instructed: I may break the structure if I find a better frame;
visual identity comes later; never invent a number.

## Success criterion — how to know the engine is worth the cost
The panel **finds the weaknesses that a human expert (or the real outcome) would also point out**, and
the **relative ranking of scenarios holds** across re-runs and models. It does NOT "predict the absolute
result" (rejected as non-validatable). If the panel misses the obvious weaknesses OR the ranking is
unstable → it is theater, do not use it.

## Principle
Define the evaluation criteria (category framing): do not claim we are the winner — **frame the
problem along the axes where we are strongest**, so that the reader's DD converges on us. "Enterprise
work demands X" (a domain truth) carries the product without turning into a pitch.
