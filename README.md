# high-stakes

A rigor engine for decisions that are expensive to redo.

You have a board deck, a positioning narrative, a strategic call — something that ships
to the outside world and cannot be unshipped. Ask a model for an opinion and you get a
friendly advisor. This engine does the opposite: it runs a **blind adversarial panel** —
each advisor attacks your material without seeing what the others said — then **refutes
its own consensus**, and returns a dossier where every attributed quote was verified by
code against the original answer.

It does not predict how the room will react. It measures **where your decision breaks
under attack** — which is the useful question before you walk into the room.

## The 18-of-35 problem

While building this, I checked a finished dossier against the raw panel outputs. **18 of
35 quotes had been silently altered** — trims, splices, one entire sentence nobody ever
said. None of it was intentional: a language model paraphrases what it read and hands it
back inside quotation marks.

So quotes are verified by code, not by trust. `qverify` matches every attributed quote
against the raw cell of that specific advisor — verbatim, segments in order, within a
single cell — and rejects the dossier otherwise. Wrong voice fails too: a real sentence
attributed to the wrong advisor does not pass.

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

## How it works

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

**Why different model families:** two models from the same family fail together. A panel
that fails together isn't a panel — it's one advisor with accents.

**Why blind:** an advisor who sees the previous answer converges to it. Convergence only
counts as signal if it is independent.

**Why refute your own consensus:** unanimity is usually an echo of the prompt, not
signal. The refuter exists to find the case where the whole panel is wrong together.

**About the advisors:** the lenses carry names of real people, but they are **simulations
by language models** — the real people said none of this. The engine forces every dossier
to declare that, and rejects the ones that don't: the artifact circulates, and
`— **Name**` looks exactly like a real citation.

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
to do while each thing doesn't exist. Today it includes: routing to no-retention
providers, automatic verification that a cited source supports the claim, aborting when
fewer than 3 model families are alive, and enforcement of brand-blinding in the judgment
view.

Nothing on that list should be presented — by this README, by the contract, or by a
dossier — as if it worked.

See `examples/sample-dossier.html` for the output format.

## License

Apache-2.0 — see [LICENSE](LICENSE).
