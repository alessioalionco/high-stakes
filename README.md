# high-stakes

A virtual board of experts for decisions that are expensive to redo.

## The idea

Nobody serious makes a high-stakes decision alone. Companies answer to boards. Medicine
runs on second opinions — doctors with different training and different protocols looking
at the same case. Products have customer advisory boards; careers have mentors. The
pattern shows up everywhere because it works: decision quality goes up when independent
perspectives with different backgrounds attack the same problem.

Multi-model adversarial review already proved the pattern transfers to AI — code reviewed
by several models from different vendors catches what any single model misses.
high-stakes applies it to decisions.

You bring the question — a board deck, a positioning narrative, a strategic call,
something that ships to the outside world and cannot be unshipped. The engine **builds
the board for your problem**: it classifies what kind of panel the decision needs, maps
what must be covered, and proposes one seat per axis, which you ratify or swap. Each seat
is a lens on a sharp public thinker, and each lens runs on a different model family. A
starter board of thirteen SaaS operators and investors ships in the box, and any board
you build from scratch can be saved to your pool and reused.

It is not one AI opinion. It is a panel engineered to disagree — and it does not predict
how the room will react. It measures **where your decision breaks under attack**, which
is the useful question before you walk into the room.

**About the advisors, said plainly:** the lenses carry names of real people, but they are
**simulations by language models**, drawing on what the models know of each person's
published thinking. The real people said none of this, and no curated index of their work
is involved. The engine forces every dossier to declare this and rejects the ones that
don't: the artifact circulates, and `— **Name**` looks exactly like a real citation.

## The board is built for the problem

You don't pick from a fixed cast. Formation is task-driven, and it is the part of the
method with the most thought in it:

- **First question of every run:** use a board you've already curated, or build one from
  scratch for this problem?
- **The problem is classified by archetype** — expert panel (cover the necessary
  disciplines), adversarial panel (cover the ways this can fail), or audience proxy
  (cover the segments of whoever you need to convince). Most real cases are hybrids.
- **Then a coverage matrix:** list what must be covered, one seat per axis. Seats qualify
  by peer recognition — cited by experts, guideline authorship, track record. Fame is not
  authority.
- **Three standing roles always sit:** a generalist per model (catches the axis everyone
  forgot), an anti-thesis seat (attacks the premise — "is this even the right
  question?"), and a bull/bear pair on the crux axis when the risk warrants it.
- **You ratify.** The engine shows the roster, each seat's axis, and each seat's known
  bias — then you swap or confirm. Bias is a feature, not a bug: the urologist pushes
  toward surgery, and the radiation oncologist cancels it out.
- **Boards die with the decision; lenses persist.** A board is frozen while a decision
  loops (swapping a seat mid-loop breaks the round-to-round comparison) and born fresh
  for the next one. The lenses you build get saved to your pool
  (`~/.high-stakes/boards`) for reuse. The shipped SaaS board is a starter, not the
  product.

## Why this beats pasting the same prompt into a chat

You could ask your favorite model to "act as a board of The Unit Economist, The Model Theorist and The Wartime Operator." Here
is what that doesn't get you, and what this engine was built for:

**1. One model, one prompt, gets you the average.** Ask an LLM for an opinion and you
get the center of its training distribution — the most popular answer, smoothed. But
there are many ways to get from A to B: you can lose weight with more exercise, a
ketogenic diet, or medication, and each is a different protocol with different costs and
failure modes. The average of them is not a protocol. A named lens with a defined axis
pulls the model out of the average and into one way of thinking — a CEO asking "a CEO"
for feedback gets generic advice; a board seating the world's sharpest CFO, CTO and CMO
answers the same question three different ways. Convergence across seats validates the
decision. Divergence is where you learn — it maps the options you didn't know you had.

**2. Different model families, on purpose.** Two models from the same family fail
together — same data, same method, same blind spots. A panel that fails together isn't a
panel; it's one advisor with accents. Here each seat runs on a different family, with
different training corpora and different training methods, so when the seats agree
independently, the agreement carries information.

**3. Isolation you can verify.** Each advisor × model pair is one API call with a clean
context. No cell sees another's answer, and there are no rounds — an advisor who reads
the previous answer converges to it, and convergence only counts as signal when it is
independent. This is not a promise: it is a tested invariant. There is no code path by
which one cell's output can enter another's prompt.

**4. Evidence before opinions.** Before the panel runs, a deep-research pass builds an
evidence pack for the questions your decision actually depends on, with every source
classified by trust tier (primary > analyst > press > vendor blog) and a domain blocklist
that flags leaks. The board argues over the same grounded material — not over whatever
each model happens to remember.

**5. Opinions are forced into falsifiable calls.** Commentary is cheap — "interesting,
but I'd worry about churn" costs an advisor nothing. So the asks force commitment:
predict the valuation range. Would you sign this term sheet, yes or no? What number
would change your mind? When I stress-tested a fundraise narrative, every seat had to
commit to a valuation and a term-sheet verdict before writing a single line of
commentary. Forced calls make seats comparable on the same question, turn disagreement
into a measurable spread, and give you something to score against reality later —
instead of a pile of opinions everyone remembers fondly. A simulation helps here, not
hurts: a polite human advisor hedges; a lens has no reputation to protect.

**6. The engine attacks its own output.** After the panel, a separate model is paid to
refute the consensus, item by item. Unanimity is usually an echo of the prompt, not
signal. The refuter exists to find the case where the whole board is wrong together.

**7. Quotes verified by code — the 18-of-35 problem.** While building this, I checked a
finished dossier against the raw panel outputs: **18 of 35 quotes had been silently
altered** — trims, splices, one entire sentence nobody ever said. None of it intentional:
a model paraphrases what it read and hands it back inside quotation marks. So `qverify`
matches every attributed quote against the raw cell of that specific advisor — verbatim,
segments in order, within a single cell — and rejects the dossier otherwise. A real
sentence attributed to the wrong advisor fails too.

## What comes back

A dossier (§0–§7, structure enforced by a code gate), organized by what actually matters
in a board's output:

- **Convergent points** — what every lens hit independently. The closest thing to signal
  a panel can give.
- **Forks** — where the board splits: thesis, antithesis, why they diverge, the cost of
  being wrong on each side, and what evidence would resolve it.
- **Unique views** — what only one lens saw. Often the most valuable section: a blind
  spot has no majority.
- **Refutation results** — which consensus survived attack, and which folded.
- **A chairman synthesis** — ranked suggestions, open questions, guardrails.

## How I use it

- **Preparing for my own board meetings.** It has been precise at anticipating the
  questions I actually get, and at finding where the material is fragile before anyone in
  the room does.
- **Stress-testing projects my team proposes**, before we commit money and quarters to
  them.
- **Throwing a hard problem, plus the data I have, at the board** — and reading where the
  forks land.

## Is this for you?

You need all of these at once:

- a decision that **ships externally** and is expensive to redo (board deck, positioning,
  fundraise narrative) — for anything else, this is overkill;
- **Claude Code** and Python 3.11+;
- an **OpenRouter** key with credit, and willingness to spend per decision (the real cost
  of your case shows up in preflight, before anything is dispatched — don't trust a fixed
  range; the estimate can undershoot);
- **willingness to send your material to multiple model and search providers.** There is
  no content filter on the way out (see "What leaves your machine"). If this material
  cannot leave your machine, stop here — this tool is not for your case, and no
  configuration changes that.

## Install

```
/plugin marketplace add alessioalionco/high-stakes
/plugin install high-stakes@high-stakes
```

The `@high-stakes` is the marketplace name, not a typo: the first command registers the
catalog, the second installs the plugin from it.

That's it. **Zero dependencies** — stdlib only, Python 3.11+. There is no `pip install`
in this flow on purpose: a missing dependency would fail after you had already written
the brief and approved the cost.

```bash
export OPENROUTER_API_KEY=...
```

## Use

```
/high-stakes should I circulate this deck to the board now, or wait for the quarter to close?
```

The engine drives the rest: refines the ask into a pre-filled brief, proposes the board
composition, shows the estimated cost, and only dispatches after your GO.

## How a run works

```
        your problem
             │
        Gate A  ── essential questions + materials + research agenda
             │
        Gate B  ── sharpened brief + proposed board + cost → you say GO
             │
             ▼
   BLIND adversarial panel
   personas × models from different families, no cell sees another
             │
             ▼
   per-item refutation ── a separate model attacks the panel's consensus
             │
             ▼
   ┌── three code gates, all must exit 0 ─────────────┐
   │  render_gate     dossier structure + jargon      │
   │  qverify         every quote is verbatim         │
   │  render_dossier  single-file HTML                │
   └──────────────────────────────────────────────────┘
             │
             ▼
       dossier §0–§7
```

## Configuration

```bash
bin/high-stakes config     # shows effective config and where each value came from
```

Commands go through `bin/high-stakes`, which resolves the package root from its own
location — works from any directory, no install, no `PYTHONPATH`.

Precedence: explicit argument > environment variable > `./.high-stakes.toml` >
`~/.high-stakes/config.toml` > default.

| Key | Default | Governs |
|---|---|---|
| `runs_dir` | `./high-stakes-runs` | where the decision is recorded |
| `boards_dir` | `~/.high-stakes/boards` | your pool of lenses |
| `pin_path` | `~/.high-stakes/roster-pin.yaml` | which models judge |
| `cap_usd` | `15.0` | spending cap **per run** |
| `concurrency` | `8` | simultaneous cells |
| `timeout_s` | `1200` | per call |

The API key never enters the config file, on purpose — config files get committed, and a
key in a repository is an accident waiting to happen.

### The spending cap, and where it does not hold

The engine reserves the estimated cost **before** dispatching and refuses the call if it
would blow the cap. Accounting is per run and works across processes: spend accumulates
in one ledger, so two terminals attacking the same decision don't each get the full cap,
and in-flight reservations are visible between them. A network failure after dispatch is
charged conservatively — a dropped stream may have been billed on the other side.

**It is best-effort, not a guarantee**, and the difference matters when it's your card:

- reservations use an **estimate**. If the real cost comes in higher, what stops the run
  is reconciliation — **after** the call has been paid for;
- the cap binds each instance against accumulated spend. A second process asking for a
  higher cap honors **its own** — that is an operator decision, and the engine warns
  instead of choosing for you.

Treat it as the seatbelt that prevents the common accident (a loop dispatching a
thousand cells), not a lock that makes overspending impossible.

## What leaves your machine

Running this engine means sending your material to model and search providers — that is
the premise, not a side effect. **There is no content filter on the way out.** There used
to be one: a denylist that refused queries containing sensitive terms. It was removed on
purpose. It protected the owner's data from the owner — the person writing the query,
owning the material, and choosing the providers is the same person — and what it actually
produced was false refusals on legitimate queries.

What replaced it is **Gate B**: before any paid dispatch, the engine shows you exactly
what will leave and waits for your OK. A human with the list in front of them beats a
substring heuristic, and it is honest about who is deciding.

## Tests

No framework: each suite is an executable script that prints `PASS` and exits non-zero
on failure.

```bash
for t in tests/test_*.py; do python3 -m "tests.$(basename "$t" .py)" || exit 1; done
```

**304 tests across 11 suites — all 12 modules covered.** The money path (per-run cap,
conservative charging on post-dispatch failure, a non-finite number from a provider
cannot disable the cap), the parallel dispatcher (a failing cell doesn't vanish,
duplicate ids blocked before spend, resume keyed by input hash, judge isolation), reuse
containment (no reads outside the run directory, symlinks included), quote verification
(a fabricated quote next to a real one does not pass), domain blocklist, config
precedence, aggregations, render gates, and a smoke test that runs the product like
someone who just installed it.

A green suite measures what the author thought to test. So the critical guards also go
through **mutation testing**: break the guard on purpose, confirm a suite turns red. A
guard that survives its own removal was never tested — that is how five of them were
found uncovered after months of looking covered.

The zero-dependency promise is **checked by AST** on every suite run, not trusted: add an
`import requests` anywhere and a test fails, naming the module.

## What the contract describes that does not exist yet

The engine is specified by contracts in `high_stakes/core/`, and not everything specified
is built. The list lives in **`core/execution.md`**, in the table at the end, with what
to do while each thing doesn't exist. Today it includes: grounding each lens in that
person's actual published material (today the lens runs on what the model already knows),
routing to no-retention providers, automatic verification that a cited source supports
the claim, aborting when fewer than 3 model families are alive, and enforcement of
brand-blinding in the judgment view.

Nothing on that list should be presented — by this README, by the contract, or by a
dossier — as if it worked.

See `examples/sample-dossier.html` for the output format.

## PS

This started as a weekend of vibe-coding that got out of hand — and then the
adversarial-review habit it preaches got turned on its own code. I would genuinely love
feedback: issues and PRs welcome, and the most useful kind tells me where it is wrong.

## License

Apache-2.0 — see [LICENSE](LICENSE).
