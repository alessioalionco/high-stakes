# Lens library: B2B SaaS (curated pool)

> **This is a LENS LIBRARY, not a "board".** It is the **pool** (perennial) the task selects from — the board itself is formed *fresh for each decision* by the `high-stakes` skill (archetype → matrix lens selection → composition; see `SKILL.md §3a` / FR4). It covers the **adversarial/skeptical archetype** of B2B SaaS decisions (raise, pricing, GTM, scaling, cash crisis, retention, M&A). **DATA, not a skill** — just the pool; the methodology belongs entirely to `high-stakes`. (Renamed from `saas-board` in v1.4: you don't save a board, you grow a per-domain library.)

## How this library is used (non-obvious — read first)
- **Each lens = an AXIS, and the archetype names the axis.** The value is axis diversity: each lens finds the weakness along its own axis.
- **Qualification = axis authority** — the axis has to be a real way this class of decision fails, not a topic. Coverage beats coloring.
- **BLIND, no rounds.** The lenses do NOT read each other or debate. Genuine divergence opens up the spectrum — convergence forced through debate is the anti-pattern.
- **Task-driven selection, not all 13.** Build the coverage map (the decision's ways-to-fail) → select the ~5 lenses that cover it (heuristic below) → prune redundancy. Running all 13 dilutes and costs.
- **Standing roles are auto-added by the engine, they do NOT live here:** generalist (1/model), anti-thesis (1), and the bull/bear pair on the crux axis when the bet warrants it.

## On naming (read before adding a lens)

The pool that ships is **archetypes**. Pointing a lens at a real, named public thinker is a
legitimate and supported technique, and it does sharpen the lens: a model knows far more
about how a specific practitioner attacks a number than about a title. **That anchor is
yours to add, in your own pool** (`$HIGH_STAKES_HOME/boards`, default `~/.high-stakes/boards`,
which overrides this one). What ships in the box does not carry real people's names.

Two mechanical constraints when you add a lens, both enforced by `tests/test_boards.py`
because getting either wrong fails **silently**:

1. **The key must be a normalized substring of the display name.** `qverify` resolves an
   attribution back to its lens by substring match after normalization, and normalization
   does NOT turn a hyphen into a space. Key `unit economist` resolves `The Unit Economist`;
   key `unit-economist` resolves to **nothing**, and every quote from that lens comes back
   `unverified`.
2. **No lens name may contain a role token** (`anti-thesis`, `antithesis`, `refuter`,
   `generalist`). Roles resolve BEFORE lens keys, so "The Generalist Operator" would read as
   the generalist role and every quote of that lens would be flagged
   `divergent_attribution`.

## The lenses (roster)

| # | Lens | Key | Axis | Tone |
|---|---|---|---|---|
| 1 | **The Movement Builder** | `movement builder` | Category creation · obsessive Customer Success · ecosystem/events | visionary, evangelist |
| 2 | **The Market Maximalist** | `market maximalist` | Extreme PMF · market dominance · aggressive pricing | macro, blunt |
| 3 | **The Platform Steward** | `platform steward` | Culture/growth-mindset · transformation · strategic partnerships | wise, systemic |
| 4 | **The Execution Hardliner** | `execution hardliner` | Speed · narrowing the focus · war on incrementalism · execution | impatient, direct |
| 5 | **The Wartime Operator** | `wartime operator` | Crisis management · founder psychology · deciding with no good option | raw, honest about the hard stuff |
| 6 | **The Scaling Mechanic** | `scaling mechanic` | Scaling mechanics (10→1000) · org/reorg · M&A · exec structuring | operator, pragmatic |
| 7 | **The Loop Architect** | `loop architect` | Market-product-channel-model fit · growth loops · retention as the engine | systemic, anti-funnel |
| 8 | **The Pipeline Engineer** | `pipeline engineer` | Sales specialization (SDR/AE/CS) · pipeline engineering · outbound | methodical, process-driven |
| 9 | **The Inbound Advocate** | `inbound advocate` | Inbound · sales-marketing alignment · culture-as-product · customer focus | optimistic, customer-first |
| 10 | **The Benchmark Operator** | `benchmark operator` | The $1M→$100M ARR playbook · operational benchmarks · VP hiring | practical, benchmark-driven |
| 11 | **The Cohort Analyst** | `cohort analyst` | Sales data science · capital efficiency · cohort analysis · trends | analytical, quantitative |
| 12 | **The Unit Economist** | `unit economist` | Unit economics · real LTV/CAC · diminishing returns · financial risk | skeptical, disciplined |
| 13 | **The Model Theorist** | `model theorist` | The SaaS business model and its structural metrics · unit economics of the MODEL (≠ 12, which is risk; ≠ 11, which is sales) · canonical measurement frameworks | professorial, framework-builder |

## Quorum heuristic (pick ~5)
- **Cash crisis / runway:** Execution Hardliner, Wartime Operator, Unit Economist, Cohort Analyst (+ Scaling Mechanic if there is an org cut).
- **Raise / valuation / board:** Unit Economist, Benchmark Operator, Cohort Analyst, Model Theorist (the metrics DD the investor will run), Market Maximalist.
- **GTM / pricing / channel:** Loop Architect, Pipeline Engineer, Inbound Advocate, Market Maximalist, Benchmark Operator.
- **Scaling / org / M&A:** Scaling Mechanic, Execution Hardliner, Platform Steward, Wartime Operator.
- **Retention / NRR / churn:** Loop Architect, Benchmark Operator, Cohort Analyst, Unit Economist, Model Theorist (negative churn is the model question).
- **Category / positioning:** Movement Builder, Market Maximalist, Platform Steward.

> **Fundraising decision?** This pool covers the operator angle. For a round it is worth composing a
> separate board of investor lenses — the questions are different, and the lenses above do not cover them.

## Language/style
- English; technical terms as-is (Churn, Burn Rate, ARR, NRR, Rule of 40).
- Each lens's verdict is **quantified against the criterion** when applicable (yes/no decision · range) + the weakness/objection that lens raises.

## Origin
Ported from a SaaS advisor board, **removing the anti-pattern**: no rounds where the
advisors read each other, no Chairman "golden path" as absolute truth. The synthesis
is the engine's 3-layer one (map → red-team → recommendation), and the final pen belongs to whoever decides.
