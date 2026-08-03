# Meridian — move from per-seat pricing to hybrid in the coming renewal cycle?

> **Synthetic example.** The company, numbers, advisors, and quotes are invented to
> demonstrate the format. The advisors are **fictional archetypes** on purpose: a public
> example must not fabricate quotes attributed to real people.

## §Scope

**Decision:** should Meridian (legal contract management, US$ 12M in recurring revenue,
240 customers, 108% net retention) replace per-seat pricing with a hybrid model — a fixed
platform fee plus consumption per AI-processed document — in the renewal cycle that starts
in 90 days?

**Out of scope:** the price points of the new table, channel strategy, and the decision to
build versus buy the extraction engine. The panel was instructed to treat those three as
givens.

**Reversibility:** low within the cycle. Annual contracts signed under the new model lock
the company in for 12 months; walking it back midway costs credibility with everyone who
already migrated.

**About the advisors:** they are **lenses simulated by language models**. They
are not the real people, and no sentence attributed to them in this dossier was said by
them. What quote verification guarantees is fidelity to what the model wrote in that lens
— nothing beyond that.

**Board:** 4 coverage lenses plus one anti-thesis, each run against 3 models from distinct
families, with no cell seeing the others.

## §0 Executive summary

**The recommendation is to migrate — but not in 90 days, and not for everyone.** The panel
converged with unusual force on one point: the per-seat model is already misaligned with
value delivery, and that misalignment gets worse every month the AI processes more
documents per user. What the panel does not support is the timeline. Three of the four
lenses treated the 90-day deadline as the real risk of the decision — not the change itself.

**The cost of being wrong is asymmetric, and the asymmetry argues against haste.**
Migrating slowly costs a few quarters of margin that could have been better. Migrating
fast and wrong costs renewals in a cycle where 40% of the base sits in a simultaneous
renewal window. The panel was unanimous that these two losses are not of the same order of
magnitude, and that treating them as equivalent is the most likely framing error here.

**The sharpest divergence is not whether, but who pays for the transition.** The lenses
split cleanly between protecting near-term margin and protecting the buyer's budget
predictability. That divergence is real and does not resolve by argument — it resolves
with a piece of data Meridian has and has not looked at: the dispersion of documents
processed per customer within each contract tier. If dispersion is high, the hybrid is
urgent. If it is low, it is cosmetic and the effort should go elsewhere.

**One risk surfaced in a single lens and survived refutation.** The legal-software buyer
is averse to budget variability in a way that economics does not explain — how their
budget gets approved internally does. A consumption model can be rationally better for the
customer and still be rejected, because the person who signs is not the person who uses.
No other lens raised this, and the refutation could not knock it down.

**What changes the recommendation:** a consumption floor high enough that 90% of customers
see their invoice land within a predictable band turns the hybrid from a bet into a
commercial non-event. Without that floor, the decision becomes a test of variance
tolerance in a segment that historically has none. This is the item the panel would put
ahead of everything else.

**How to read this dossier:** §1 covers where the lenses agreed and why the damage
mechanism is the same; §2 covers the two forks, with both sides argued in the voice of
whoever argued them; §3 covers what surfaced in a single lens; §4 covers each advisor in
full. Convergence here **is not proof** — similar models fail together, and three lenses
agreeing can be a single error repeated three times.

## §1 Convergent points

### 1.1 Per-seat pricing is already misaligned with value delivery

All four lenses reached the same diagnosis by different routes, which is the kind of
convergence worth more: not the same chain of reasoning repeated, but independent chains
ending in the same place. The damage mechanism is direct — cost to serve grows with
documents processed, revenue grows with seats filled, and the two curves came apart when
automated extraction started replacing human work instead of assisting it.

> "You're charging for the seat in a product the customer bought precisely so they'd need
> fewer people in seats. That's not a pricing problem, it's a contradiction in the
> model." — **The Margin Operator** (simulated lens · GPT-5.6 Sol)
What gives this item weight is that it is verifiable today, with no new research. Meridian
has the processed-documents telemetry and the contract base; crossing the two answers
whether the decoupling is theoretical or already hitting margin. Two lenses noted that
this check should precede any decision, and that it costs days, not quarters.

### 1.2 The 90-day deadline is the dominant risk, not the change

Three lenses treated the timeline as the real object of the decision. The shared argument:
a pricing-model change does not fail by being wrong, it fails by being communicated badly,
and 90 days is not enough time to discover the communication is bad before it reaches the
entire base.

> "A price change doesn't die in the spreadsheet. It dies on the first call where the
> customer asks 'how much will I pay in March?' and the rep can't answer." — **The Customer Advocate** (simulated lens · Grok-4.5)
The renewal concentration compounds the problem in a specific way: with 40% of the base
renewing in the same window, there is no natural control group. The company finds out it
was wrong after already being wrong with nearly half its revenue, and with no
counterfactual to size the error. One lens called this "testing the parachute after
jumping."

### 1.3 Without a consumption floor, the model shifts variance onto whoever tolerates it least

The consensus here was less about economics and more about buyer behavior. A pure
consumption model is fairer on average and worse in the tail — and the legal buyer buys
precisely to have no tail.

> "Fair on average and unpredictable at the edge is exactly the product this buyer does
> not want. He pays a premium for predictability; you're proposing to hand the premium
> back and keep the variance." — **The Category Strategist** (simulated lens · GLM-5.2)
The floor resolves most of this without undoing the value alignment, and it was the only
mitigation that surfaced independently in more than one lens. The concrete design — where
to set the floor, and whether it is per customer or per tier — was left open, and it is
the kind of detail that decides whether the change is a non-event or a crisis.

## §2 Forks

### 2.1 Protect margin now or protect the buyer's predictability

This is the dossier's underlying fork, and it does not dissolve with more analysis: the
two positions start from different premises about what is scarcest at Meridian today.

🐂 **Essay for moving now, prioritizing margin.** Every quarter on the old model is margin
that never comes back, and the decoupling between cost and revenue is accelerating. The
current base was sold on an efficiency promise that is being kept — customers are using
more and paying the same. Delaying is not neutral: it is choosing to subsidize growing
usage with your own margin, and to keep doing it in the name of a comfort the customer
never even asked for.

> "Every quarter you delay is margin you hand over for free to a customer who is already
> happy. Buyer comfort is a choice someone is paying for — in this case, you."
> — **The Margin Operator** (simulated lens · Kimi K3)
🐻 **Essay for holding, prioritizing predictability.** The 108% net retention is the
company's most fragile and most valuable asset, and it rests on accumulated trust. Price
is the one point in the relationship where the customer feels they have lost control.
Touching it in a concentrated renewal window, without having tested the communication,
risks the entire asset to gain margin points the company can capture later, at lower risk.

> "Margin you recover the next quarter. A legal buyer's trust you recover in years, if at
> all. They are not interchangeable quantities." — **The Customer Advocate** (simulated lens · GPT-5.6 Sol)
**Why they diverge:** it is not a disagreement about the facts — both lenses read the same
numbers. It is a disagreement about which resource is the bottleneck. One sees cash and
margin as the active constraint; the other sees customer trust. Whoever is right about the
bottleneck is right about the decision.

**Cost of being wrong per side:** erring on the margin side costs renewals in a
concentrated cycle, with compounding effects on net retention and on the next fundraise.
Erring on the predictability side costs two to three quarters of inferior margin and the
risk of the competitive window closing. The first error is harder to undo.

**What resolves it:** the dispersion of documents processed per customer within each
contract tier. High dispersion means the current model is already mischarging too many
people, and the urgency is real. Low dispersion means the hybrid reorganizes little and
the haste is unjustified. The data exists and has not been consulted.

### 2.2 Migrate the whole base or only the high-consumption segment — conditional fork

This fork is conditional: it only exists if the answer to item 2.1 is "move." If the
decision is to hold, the segment cut never comes up. That is why there are no two essays
argued here — there is a precondition and a trigger.

**Precondition:** migration decision made, with the consumption floor defined.

**Trigger:** if the dispersion measured in 2.1 concentrates in the top usage quartile, the
segment cut starts to dominate — you migrate whoever is already outside the band, and the
rest stays on the old model until natural renewal. If dispersion is uniform, the segment
cut creates two pricing models coexisting with no proportional gain, and the broad
migration wins.

> "Two pricing models coexisting is operational debt nobody puts in the spreadsheet and
> everybody pays in support." — **The Category Strategist** (simulated lens · Grok-4.5)
## §3 Unique views

### 3.1 The person who approves the budget is not the person who uses the product

This surfaced in a single lens, and it survived refutation — the refuter tried to reduce
it to generic risk aversion and could not, because the proposed mechanism is structural,
not psychological. At the corporate legal buyer, the budget is typically approved once a
year by someone who does not use the product and whose success metric is not blowing the
forecast. For that person, a variable invoice is not a better price — it is a career
risk.

**Why it matters:** because it flips the sign of the economic analysis. A model that is
rationally cheaper for the customer company can be rejected by the approver, and the
rejection shows up in no value model. If this mechanism is real, the consumption floor
stops being a mitigation and becomes the product: what you sell is the predictability,
with the consumption behind it.

**Testability:** high and cheap. Five conversations with budget approvers — not users —
asking how a variable invoice would enter their approval process. If three or more
describe structural friction, the mechanism is confirmed and the design changes. It costs
a week.

### 3.2 The extraction engine can become hostage to the price

One lens noted that tying revenue to documents processed creates a perverse internal
incentive: the product team acquires a reason not to improve extraction efficiency,
because higher efficiency means fewer billable documents for the same customer work.

**Why it matters:** it is a medium-term risk that does not show up in the first year and
is expensive to undo later, because it requires reopening the price all over again.
Companies that fell into this discovered too late that the revenue model was fighting the
roadmap.

**Testability:** medium. It cannot be observed before it happens, but it can be designed
against: defining the billable unit in terms of value delivered to the customer (contract
analyzed) instead of work consumed (pages processed) disarms the incentive at the source.
The choice of unit is reversible today and expensive later.

## §4 The board

### 4.1 The Margin Operator

*"Buyer comfort is a choice, and someone is paying for it."*

This lens reads Meridian as subsidizing growing usage with its own margin and calling it
retention. The 108% net retention looks healthy until you ask how much of it comes from
seat expansion versus how much comes from customers using far more for the same price. If
it is mostly the latter, the number is measuring tolerance, not value captured, and it
will get worse on its own as the product improves.

The opinion does not treat the 90-day deadline as a serious problem, and this is where it
diverges from the rest of the panel. The argument is that the communication cost is fixed
and does not shrink with time — delaying only postpones the discomfort, while the lost
margin is permanent.

**Questions:** How much of net retention comes from seat expansion? · What is the gross
margin per customer in the top usage decile? · In how many months does inference cost
overtake incremental revenue at the current pace? · Was the new price table tested against
the installed base or only against new customers?

**Suggestions:** Measure usage dispersion before anything else · Set the consumption
floor at the 90th percentile of the base, not the average · Separate the platform price
from the consumption price in the communication, even if the invoice is single.

**Strip:** margin 4/5 · urgency 4/5 · execution risk 2/5.

**In one sentence:** the current model is wrong and gets worse on its own, so the only
honest argument for delaying is execution risk — which this lens considers overestimated.

### 4.2 The Customer Advocate

*"Margin comes back next quarter; trust comes back in years, if it comes back at all."*

This lens agrees that the model must change and disagrees head-on with the timeline. The
central reasoning is about risk concentration: with 40% of the base renewing in the same
window, Meridian loses the ability to learn from the first mistakes before they reach
most of the revenue. It is not an objection to the change, it is an objection to making it
without a control group.

The concrete recommendation is to stagger by renewal window rather than by segment —
start with the contracts that expire latest, learn from them, and arrive at the
concentrated window with the communication already tested. It costs two quarters and buys
the information the current timeline does not allow.

**Questions:** How many customers would see their invoice rise more than 20% under the new
model? · Can the sales team answer "how much will I pay in March" today? · Is there a cap
clause in current contracts that blocks the migration? · Who in the base is a reference
for the others?

**Suggestions:** Stagger by renewal window, not by segment · Offer an invoice cap in the
first year to whoever migrates early · Train the sales team on the variance conversation
before announcing, not after.

**Strip:** churn risk 4/5 · urgency 2/5 · execution risk 4/5.

**In one sentence:** the change is right and the calendar is wrong, and the calendar is
what will determine the outcome.

### 4.3 The Category Strategist

*"The market will read this change as a signal, not as a price table."*

This lens focuses on how the change is interpreted by whoever is not a customer:
competitors, analysts, and prospects. Moving to consumption at a moment when the entire
category is debating AI pricing positions Meridian as the one who charges for what it
delivers — which is favorable. But doing it in a rush and then retreating positions it as
the one who does not know what it is selling, which is worse than never having moved.

The lens also raises the operational debt of keeping two models coexisting, which tends
to be underestimated because it appears in no spreadsheet and shows up in support, in
billing, and in revenue forecasting.

**Questions:** How do the two closest competitors price AI today? · Would the change be
announced publicly or only at renewal? · Is there a risk of a competitor using the
variance as a sales argument? · How long can the company afford to run two models?

**Suggestions:** Announce the change as predictability with consumption behind it, not as
consumption with a floor · Set the end date for the two models' coexistence before
starting · Prepare the answer to the "unpredictable invoice" argument before the
competitor uses it.

**Strip:** positioning 4/5 · urgency 3/5 · execution risk 3/5.

**In one sentence:** the direction strengthens the company's position in the category,
provided the execution does not turn the change into a signal of hesitation.

### 4.4 The Financial Skeptic — anti-thesis

*"Nobody asked whether the price change solves the problem the company actually has."*

The anti-thesis does not defend the current model. It questions the framing: the entire
panel accepted that the problem is the alignment between price and value, when the
evidence presented is equally compatible with a unit-cost-of-inference problem that
pricing does not solve, only passes through. If the cost to serve is growing faster than
any price table can keep up with, migrating to consumption buys time and postpones the
hard conversation.

The second point is about the 108% net retention: the panel treated the number as an
asset to protect. The anti-thesis observes that 108% in an AI product with growing
adoption is a weak number, not a strong one — and that if it is being propped up by
customers who use a lot and pay little, the migration will expose that all at once, and
not as a success.

**In one sentence:** the pricing decision may be being used to avoid making the cost
decision, and the entire dossier would read differently if the unit cost of inference
were on the table.

## §5 Investigation agenda

The scores below are **weak signal** and are labeled as such. What matters in them is the
spread, not the level: different lenses tend to score similarly even when they disagree on
substance, so a high number does not mean agreement. Where the spread is large, there is
real divergence behind it — and that divergence is already described in §2, which is
where it should be read.

| Lens | Direction | Urgency | Execution risk |
|---|---|---|---|
| The Margin Operator | migrate | 4/5 | 2/5 |
| The Customer Advocate | migrate | 2/5 | 4/5 |
| The Category Strategist | migrate | 3/5 | 3/5 |
| The Financial Skeptic | reframe | — | — |

The spread in urgency (2 to 4) and in execution risk (2 to 4) is the map of the fork in
§2.1, and it is the only content in this table that deserves weight.

## §6 Chairman synthesis

### 6.1 The recommendation

Migrate, with a consumption floor, staggered by renewal window, and not in 90 days. The
direction is supported by independent convergence across all four lenses; the timeline is
supported by none of them except one.

### 6.2 What needs to be true

The recommendation depends on usage dispersion being high. If the measurement shows low
dispersion, the urgency disappears and the effort should go to unit cost — which is the
anti-thesis's point.

### 6.3 What to watch

The first staggered cohort is the instrument: if the variance conversation stalls in the
first ten renewals, the problem is the communication and it is fixable. If it stalls in
the customer's budget approval, the problem is structural and the design needs to change.

### 6.4 Ranked suggestions

**1. Measure the dispersion of documents processed per customer, within each contract
tier, before any decision.** It is the data point that resolves the dossier's central
fork, and the company already has it — it sits in product telemetry crossed with the
contract base. The mechanism: if usage is widely dispersed within a single price tier, the
current model is already mischarging a lot of people, and the urgency of the migration is
real and measurable. If it is uniform, the hybrid reorganizes little and the haste is
unjustified. Owner: product and finance jointly. Gate: no timeline decision before this
number exists. It costs days, not quarters, and it is the only suggestion on this list
that cannot be done in parallel with the others — it comes first.

**2. Set the consumption floor at the 90th percentile of the installed base, not the
average.** The floor is what turns the change from a bet into a commercial non-event, and
calibrating it by the average is the mistake that defeats its purpose: half the base would
sit above it and see variance anyway. Calibrated at the 90th percentile, nine out of ten
customers get a predictable invoice and the company still captures the surplus from heavy
consumers. The mechanism is psychological and budgetary, not economic: what the floor buys
is the absence of a hard conversation at renewal. Owner: finance. Gate: the floor must be
defined before any customer communication, because the communication sells the floor, not
the consumption.

**3. Stagger by renewal window, starting with the contracts that expire latest.** The
concentration of 40% of the base in a single window eliminates the natural control group,
and without a control group the company finds out it was wrong after already being wrong
with nearly half its revenue. Starting with the distant expirations creates the learning
cohort the current timeline does not allow: the communication gets tested, adjusted, and
only then reaches the concentrated window. The cost is two quarters of inferior margin;
the return is the information. Owner: sales. Gate: the concentrated window is not touched
before ten staggered renewals have been closed and analyzed.

**4. Interview five budget approvers — not users — about how a variable invoice would
enter their approval process.** This is the test of the §3.1 risk, which surfaced in a
single lens and survived refutation. The mechanism is structural: whoever approves budget
at a legal buyer tends to be evaluated on not blowing the forecast, and for that person
variability is a career risk, not a better price. If three or more describe structural
friction in the process, the floor stops being a mitigation and becomes the product — the
entire communication changes axis. Owner: sales or research. Gate: results on the table
before the launch message is locked. It costs a week.

**5. Define the billable unit in terms of value delivered, not work consumed.** Billing
per page processed creates an internal incentive not to improve extraction efficiency,
because higher efficiency means fewer billable units for the same value delivered to the
customer. Billing per contract analyzed disarms this at the source: the product can get
arbitrarily more efficient without revenue falling. The risk is medium-term, does not
appear in the first year, and is expensive to undo because it requires touching the price
yet again. Owner: product. Gate: the choice of unit is reversible now and expensive later
— decide before launch, not during.

### 6.5 What this dossier does not resolve

The unit cost of inference, raised by the anti-thesis, was out of scope by instruction
and is the item with the greatest potential to flip the recommendation. If it is growing
faster than any price table can track, the pricing decision is being used to postpone the
cost decision. The panel did not have the data to judge this.

Nor does it resolve the price points of the new table — only the architecture of the
model. And it does not assess whether Meridian has the billing operations capacity to
support consumption, which is an engineering question, not a strategy question.

### 6.6 Falsifiers

Each item below is a prediction that can be checked, and that, if it fails, takes down
part of this dossier. The usage dispersion measured in 6.4.1 will be high enough to
justify the migration. At least three of the five approvers interviewed will describe
structural friction with a variable invoice. In the first ten staggered renewals, fewer
than two customers will ask to stay on the old model. If the first two fail together, the
entire recommendation should be reopened, not adjusted.

## §7 Appendix

**Discarded and why.** Three items from the panel did not make it into the body of the
dossier. One of them — the suggestion to test pricing on prospects before the base — was
discarded because prospects do not have the switching cost that defines the problem, so
the test would not be informative. Another, about packaging consumption as prepaid
credit, was absorbed into the floor suggestion, which solves the same problem with less
machinery. The third was a restatement of item 1.1 in other words, coming from a second
lens.

**Where this dossier is weak — method honesty requires saying this before anyone asks.** The anti-thesis was not answered, it was recorded — the panel did not
have unit-cost data to judge it, and that is a real gap, not a detail. The convergence in
§1 comes from four lenses run against three models, which reduces but does not eliminate
the risk of correlated error: models trained in similar ways can fail together, and three
lenses agreeing can be a single error repeated. The scores in §5 are weak signal and are
labeled as such in the text itself.

**Refutation and what it did.** Every convergent item and every unique view went through
a refutation pass in a model from a distinct family, instructed to build the case
against. That pass has a measured bias toward refuting — it fails more than it should —
so its result was used as a depth generator, not as a judge. The §3.1 item is the only
one that survived intact; the §3.2 item was weakened from "likely risk" to "design risk,"
and the text reflects that.

**Drill-down.** Every quote in this dossier was verified by code against the original
response of the advisor it is attributed to, and the full text of every cell is stored
with the run — the items above can be opened down to the source. No quote was edited to
fit the text; wherever there was a cut, it is marked with an ellipsis.
