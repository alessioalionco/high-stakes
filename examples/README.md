# examples/

## `sample-dossier.html` — the reference dossier

Open this file before writing any dossier. It is the **physical bar** the render gate
tells you to consult at render time, and the reason it exists is a concrete failure mode:
a dossier was once written from aggregate counts alone, came out shallow, and the prose
contract did not hold. A reference open on screen does.

**It is 100% synthetic material.** The company (Meridian), numbers, advisors, and quotes
are invented. The advisors are **fictional archetypes** on purpose — a public example
must not fabricate quotes attributed to real people.

## What this example demonstrates

| Where | What to look at |
|---|---|
| §0 | 5 dense paragraphs that **front-load the recommendation** instead of saving it for the end |
| §1 | convergence with the damage mechanism in prose, not just a count of who agreed |
| §2.1 | contested fork: both sides argued **in the voice of whoever defends them**, with the cost of being wrong per side |
| §2.2 | **conditional** fork — no 🐂/🐻, with an explicit precondition and trigger |
| §3.1 | an item that surfaced in a single lens and **survived refutation** — and therefore weighs more, not less |
| §4.4 | the anti-thesis attacking the **framing**, not the conclusion |
| §5 | scores labeled as weak signal, with the spread worth more than the level |
| §6.4 | suggestions with mechanism, owner, and gate — not a list of verbs |
| §7 | what was discarded, where the dossier is weak, and what the refutation changed |

## Regenerating

```bash
bin/high-stakes render_gate    examples/sample-dossier.md   # exit 0 required
bin/high-stakes render_dossier examples/sample-dossier.md examples/sample-dossier.html
```

**Nothing here may contain real data** — no real company, revenue, customer, or advisor
name.
