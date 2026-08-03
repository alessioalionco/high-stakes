# Output contract — A–F taxonomy + §0–§7 render (neutral core)

> Types what the board DELIVERS (6 forms A–F, chosen in the Gate B readback — v2 flow) and how that becomes
> the personified RENDER (fixed skeleton §0–§7). Harness-neutral: the core fixes the CONTRACT; the adapter
> generates the physical HTML. The summary that
> feeds this render obeys the lossless contract of `core/methodology.md` §3f.

## Layer 0 — the atomic unit is the ITEM (card)
The unit of output is the **item/card** (each weakness, question, premise, strength — with its tags). The
headlines are **aggregated views on top of the cards**, not a separate unit. The individual card is what
the human validates at the gate ("real objection or LLM artifact?") and what the loop subtracts.

**Spine (Decision Quality — Stanford/SDG):** every item threatens 1 of the 6 links → it turns "there are
holes" into "WHERE the decision is fragile": 1 Frame (the anti-thesis seat) · 2 Alternatives · 3 Information
(missing evidence + investigate) · 4 Values/trade-offs · 5 Reasoning · 6 Commitment. *A decision is only as
strong as the weakest link in the chain.*

**Item type (by ACTION):** flaw→fix · objection→preempt · assumption→test ·
open_question/unknown→**investigate** · missing_evidence→ground · risk→mitigate · dud→cut ·
**strength**→lead/protect · keep→don't-over-invest · **indifferent/noise**→cut (the slimmer).

**⚠️ Epistemic lock:** the board is LESS reliable at CONFIRMING what is right than at finding what is
wrong (confirming = the direction that pleases the proxy/Goodhart). Hence the **positive ships labeled as
LOWER-confidence** — a hypothesis about what works, a record of feedback, never a validated verdict on par
with the weaknesses.

**Attributes (5 tags per card):** decision_impact (deal-breaker/material/cosmetic) · groundedness
(evidence-anchored vs hunch · checkable-vs-subjective) · consensus_vs_contested (number of lenses +
spread) · actionability + cost · provenance + seat bias.

## Layer 1 — the taxonomy of 6 output forms (A–F)
Every case is a combo. The Gate B readback (`core/sections/interactive-gates.md`; archetype default in the
quick flow, ratified in the full one) chooses the forms; they type the CONTENT of the render slots.

| Form | What it is |
|---|---|
| **A** Verdicts | binary/categorical ("would you hand over the term sheet?") |
| **B** Quantities | **always a range, never a point** (valuation range) |
| **C** Ranked change list | the N actionable suggestions, ranked |
| **D** Protocols/forks | mutually exclusive + precondition |
| **E** Red flags / needs-human | deal-breakers + limits of the board's authority |
| **F** Questions to carry | when the board is not the final authority |

## Layer 2 — the FIXED render skeleton (§0–§7)
Fixed structure, **hierarchical §N.M numbering on EVERY item** (anchors + cross-refs — conversational
drill-down: "on 2.3, I'm left with doubt X"):

- **§0 Executive summary** — 5+ dense paragraphs, facts in bold, anticipates the recommendation + how-to-read (with the caveat that errors correlate across similar models).
- **§Scope (E1-E4):** E1 evaluation dimensions + RESULT per dimension · E2 inputs provided · E3 what the advisors ASKED FOR and was missing (→ feeds the agenda) · E4 method in 1 line.
- **§1 Convergent points:** checkmark matrix (weight = DISTINCT advisors, not cells) + up to 3 quotes/item + damage-mechanism in prose + error-correlation caveat.
- **§2 Forks:** per fork — context + 🐂 essay + 🐻 essay (up to 3 quotes each) + why-they-diverge + cost-of-being-wrong-per-side + what-resolves (links to the agenda) + preconditions.
- **§3 Unique views per advisor:** item + tags + up to 3 quotes + why-it-matters + testability. *(Highest expected-value bucket — the decision-changing items came from here.)*
- **§4 The board:** per advisor — 1 thesis paragraph (50% larger) + up to 5 questions + up to 5 suggestions + score strip on the dimensions (E1). Verbatim quotes. Spread = signal, level = weak weight.
- **§5 Investigation agenda:** summary table + each open item (what it is / why it comes first / which test resolves it / what it unlocks).
- **§6 Chairman synthesis (AT THE END):** 6.1 convergences · 6.2 sequenceable divergences · 6.3 collective verdict (case dimensions) · 6.4 the DETAILED suggestions (mechanism+how+owner/gate, grouped Hygiene/Proof/Narrative/Process) · 6.5 the Chairman's questions (with the why) · **6.6 guardrails/triggers** (canonical home of aggregated form E).
- **§7 Appendix:** discarded-and-why · method-honesty · drill-down to the raw cards.

**Physical** (the adapter's responsibility): single-file HTML, document measure (~880px), dark mode, sticky
nav, @media print (⌘P → PDF), groundedness rendered (**solid border = verified, dashed =
claim/suppressed**), zero external dependency.

## Layer 3 — the A–F → § map (the stitching)
The §0–§7 skeleton **never changes**; the A–F contract types the CONTENT of the slots. The readback's
backward generator generates upstream (seats, yardstick, agenda); at render it only parameterizes.

- **A/B → E1 + Tier 0 + §6.3 + §4 score strip.** The E1 dimensions ARE the typed A/B contract. A type-B dimension yields a **RANGE in every slot, never a point**; the collective range of §6.3 = envelope of the advisors' ranges, spread = signal.
- **C → §6.4** (raw material: §4 suggestions; kill-list/cut-rethink as views). The 1-N numbering is the Chairman's RANK (impact×cost); Hygiene/Proof/Narrative/Process = secondary tags. The sample's "15" is the case's caliber, not an invariant.
- **D → §2 + Tier 0 + §6.2.** §2 admits TWO types:
  - **contested fork** (board diverges): full 🐂/🐻 apparatus + why-they-diverge + cost-per-side.
  - **conditional fork** (board CONVERGES on the branch; the precondition lives in the WORLD, not in the board): yields precondition + branches + trigger, **without 🐂/🐻**, weight cited as convergent. **Fabricating a bear where there was no divergence is rigor theater.**
- **E → `deal-breaker`/`flaw` tags (§1–§3) + §6.6 guardrails/triggers table + 🚩 on the agenda.** Canonical aggregated home = §6.6.
- **F → routed by addressee:** §4 (what the lens would dig into) · E3→§5 (unknowns→test) · §6.5 (decision-maker, incl. pre-registration).
- **`needs-human` marker:** a §5 item or §6.5 question whose resolution requires **external human authority** (a doctor, a lawyer, the real investor) carries the marker — the board declares the limit of its own authority. Covers the needs-human half of E and the defining condition of F.

**Invariant:** a form absent from the contract → the slot **collapses with a 1-line note** ("contract
without C — no ranked list"), it **never disappears silently** nor gets filled by inertia.

## Personification (render rules)
1. **Identity = persona; model = parenthesis.** "The Unit Economist (via Opus 4.8)". The advisor is the lens; the model is which brain ran it. *(The attribution only appears at RENDER — in the judgment view the card is an opaque ID, `core/methodology.md` §3e.)*
2. **Weight counts DISTINCT advisors, not cells.** 4 models of the same persona = 1 lens, not 4 votes.
3. **An advisor's quote = verbatim excerpt from the raw card** (drill-down preserved). On merge, the most SPECIFIC quote wins.
4. **Epigraph in the lens's own voice** (verbatim aphoristic quote, NEVER generated at synthesis) + **verdict close** in bold per advisor block.
5. **Anti-thesis RENDERED, not run:** the fork already IS the antithesis; juxtapose the real quotes from the independent cells (🐂/🐻). Actual debate between cells remains forbidden: a cell that reads a cell converges, and induced convergence is not signal.
6. **Scores WITH spread as signal + "weak weight" label:** the spread between advisors is real signal (fork detected); the absolute level is caricature — different personas score nearly identically — and is labeled as such.
7. **Honest footer:** "advisors are synthetic personas — the signature belongs to the lens, not to the real human who names it."

## Depth (the digest EXPANDS from the cards, it does not summarize)
The output costs more than deep research and must go DEEPER: each convergent point = 2-3 paragraphs
(damage mechanism, nuance, the fix and what it does not solve); each fork = context + bull essay + bear
essay + why-they-diverge + cost-of-being-wrong-per-side + what-resolves; each unique view = analysis +
testability; each advisor = an opinion in the lens's voice. EVERY claim carries number/source/confidence.
The Chairman SYNTHESIZES the lens's cells (does not invent); quotes always verbatim.

## Render gate — runs BEFORE delivering the dossier (do not skip)

> **This gate exists because of a concrete failure mode.** A dossier was
> written from the aggregated tallies instead of the cards, came out shallow, and leaked engineering
> jargon into the text delivered to the decision-maker. The prose contract already forbade both things
> and did not hold — which is why there is a mechanical bar here, not just instruction. The principle
> applied to the engine itself: **verifying means evidence, not confidence.**

**R1 — Mandatory re-read at render time.** Before writing the first line of the
dossier, re-read this entire section and OPEN a reference dossier (the physical bar; the concrete
path comes from the adapter). Having read the contract way back, at the gates, does NOT count — hours
and an entire context separate the two moments, and it is at render that the bar needs to be in front
of your eyes.

**R2 — Mandatory source = raw cards.** The dossier is written FROM THE CARDS (drill-down open per
item), never from the aggregates/tallies alone. Tallies give the skeleton (weights, flips, medians); the
flesh (mechanism, nuance, quote) comes from the full text of the cells. If a section was written without
opening the corresponding cards, it is wrong by construction — even if it looks good.

**R3 — The decision-maker's language.** The dossier is for the one who DECIDES, not for the one who
built the engine. Internal codes — for experiments, mechanisms, evidence items, decisions — are
**forbidden in the body**. Either the idea is said in plain English, or the term enters glossed at its
first occurrence. The method warnings remain mandatory (that errors correlate, that scores are
caricature), but said in human language. The mechanical verifier fails by code FAMILY,
not by a list of instances: a list of instances rots as soon as someone invents the next
code.

**R4 — Measurable checklist (floors = the ones defined in the reference format; the sample defines the
ceiling — the gate never tightens the defined bar on its own):**
- §0: ≥5 dense paragraphs of PROSE (lists don't count), facts in bold, anticipates the recommendation +
  how-to-read.
- §1: each convergent point ≥2 paragraphs of prose + **≥1 attributed verbatim quote** (defined:
  "1-2 reference quotes"; the most SPECIFIC one wins — never pad to score) + the refutation
  result when there is one; per-advisor weight matrix present.
- §2: each CONTESTED fork with BOTH essays (🐂 and 🐻) + ≥1 quote per side + why-they-diverge +
  cost-of-being-wrong-per-side + what-resolves. CONDITIONAL fork: no 🐂/🐻, with precondition+trigger,
  **explicitly marked with the phrase "conditional fork"** in the heading or in the context block
  (that is the marker the verifier reads; a loose word does not exempt).
- §3: each unique view with analysis + why-it-matters + testability.
- §4: each advisor with a verbatim epigraph + an opinion of ≥1 paragraph IN THE VOICE + questions and
  suggestions present (up to 5 each — a ceiling, not a floor; never fabricate to fill) +
  score strip + verdict close in bold.
- §6.4: each suggestion ≥400 chars with mechanism+how+owner/gate (reference caliber ~550c).
  §6.5 and §6.6 present as their own headings.
- §7: discarded-and-why + method-honesty + drill-down.

**R5 — Mandatory mechanical validation.** Run the **structural verifier pointed to by the adapter**
and get **exit 0** before delivering. Red gate =
fix and re-run; delivering with a red gate is a contract violation, not editorial judgment.
The verifier is the floor (structure + jargon by code family); R1-R4 keep applying to what
code does not measure (voice, nuance, altitude) — quote fidelity IS measured by code, in R6.

**R8 — The marker travels WITH the attribution.** Every attributed quote carries, **on the very
same line**, the marker `(simulated lens · <model>)`:

```
> "quote text." — **The Unit Economist** (simulated lens · GPT-5.6 Sol)
```

> Rule R7 protects the DOCUMENT; it does not protect the FRAGMENT. A quote cropped for a
> slide, a screenshot or a message leaves without the §Scope — and what remains is a sentence with
> quotation typography, attributed to someone who actually exists. The model providers' usage
> policies describe this case almost literally: attributing content in a way that
> **misleads about its origin**. Where there is explicit disclosure, they do not apply; the
> disclosure needs to be where the reader is.
>
> The old `(via <model>)` is still accepted by the quote verifier, so as not to
> break already-recorded dossiers — but it does not satisfy this rule: "via" identifies the model, it
> does not warn that the person is simulated.

**R7 — Declare that the personas are simulated.** The §Scope mandatorily carries a
sentence saying that the advisors are **lenses simulated by language models, that they ARE
NOT THE REAL PEOPLE**, and that no sentence attributed to them was said by them.

> This is not legal formality: it is a consequence of the format itself. The lenses carry the names of
> real people, the `— **Name**` attribution uses real citation typography, and the
> dossier **circulates** — it goes to meetings, to people who do not know what this engine is.
> Rule R6 guarantees the quote is verbatim from the CELL; it guarantees nothing about the person.
> Without the declaration, you deliver a strong guarantee about the wrong thing.
>
> The `(via <model>)` in the attribution does not substitute for this: it reads as engineering
> metadata, not as a warning. The mechanical verifier fails the dossier without the sentence.

**R6 — Quotes verified by code.** When the raw cells exist (always, in a real run),
EVERY attributed quote and every epigraph goes through the quote verifier: verbatim against the card of
the advisor it was attributed to, exit 0 mandatory. An unverified quote does not reach the decision-maker
— fix it to the verbatim or remove it.

> When verifying a finished dossier, **18 of 35 quotes failed**: cuts that changed
> the meaning, splices between distant passages, and an entire sentence added to an epigraph.
> None of the alterations had been intentional. That is why this rule is code and not recommendation.


## Open items
Not built, and therefore must not be presented as existing: card JSON schema ·
deterministic computation of the headlines · card versioning across the loop · the
`indifferent` type in the mapping.
