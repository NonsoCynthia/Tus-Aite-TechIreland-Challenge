# Architecture Decision Records

**Track:** `coordinating-agent_20260906`

> Numbering continues from ADR-002 (`explainable-agent-based-triage_20260828/decisions.md`).
> Each entry: date, decision, rationale, trade-off accepted.

---

### ADR-003: CPC ordering uses `severity_rank`, never the raw code value

**Date:** 2026-09-06
**Status:** accepted

**Context:** `GET /hospitals/.../cohort/...` returns `cpc` as the NTPF code value. Those codes do
not sort in clinical order: `core.ref_codes` gives Urgent = 1, **Semi-Urgent = 3**, **Routine = 2**,
Excluded = 4. Sorting a cohort on `cpc` ascending therefore places every routine referral above
every semi-urgent one. `dataset/docs/GETTING_THE_DATA.md` §4 already names this as the trap it is,
and it is silent: the ranking looks plausible, the numbers are in range, and a `RULE-ORDER` check
written against the same wrong key passes.

**Decision:** The coordinator orders on `severity_rank` (1→1, 3→2, 2→3, Excluded→none), held as a
module-level constant with a test asserting it against `core.ref_codes`. `cpc` is carried through
to `RankingIn.triage_category` for display, and is never a sort key.

**Consequences:** A change to the national code table fails a test rather than silently reordering
patients. The cohort response does not carry `severity_rank`, so the mapping lives in the agent —
duplication of a fact that exists in Postgres, accepted because ADR-002 bars the agent from
querying it directly, and the test pins the two together.

---

### ADR-004: Clinical priority is a non-compensatory band; scores order within it

**Date:** 2026-09-06
**Status:** accepted

**Context:** `explainable-agent-based-triage_20260828` FR3 specifies the tie-break as CPC → CRT
breach → oldest-first, with no score in the chain, while `RankingIn` makes `urgency_score` and
`capacity_score` required fields. Read literally, the agent scores would be evidence and display
only, contradicting the proposal's framing of urgency-driven prioritisation. Read the other way —
scores able to move a referral anywhere — a high-scoring semi-urgent referral could outrank a
low-scoring urgent one, which FR3's own final bullet and `RULE-ORDER` both forbid.

**Decision:** CPC severity is a **hard band boundary that no score may cross**. Within a band,
ordering is by breach status, then by the composite priority of ADR-005, then oldest-first. Scores
genuinely change the queue; `RULE-ORDER` cannot fail by construction.

**Rationale:** This is the standard MCDA distinction between compensatory and non-compensatory
aggregation. Compensatory techniques — the additive weighted sum being the common default — let a
high score on one criterion offset a low score on another, and require preferential independence
between criteria to be valid. Clinical priority and operational scores are not exchangeable in that
way: no capacity value should make an urgent patient rank behind a routine one. Where trade-offs
between criteria are not acceptable, non-compensatory techniques are the appropriate family.

**Trade-off accepted:** Within-band ordering is where all the intelligence lives; across bands, the
system is a rules engine. That is less impressive as an "AI" story and more defensible as a
clinical one, which is the trade this project has made everywhere else.

---

### ADR-005: Capacity modulates the weights, never an individual referral's score

**Date:** 2026-09-06
**Status:** accepted

**Context:** The intent is that scarcer capacity should make urgency matter more. The obvious
implementation — adding capacity to each referral's score — does not express that. `capacity_score`
is a property of a **specialty**, not a patient (parent FR2: the capacity agent reads the
referral's specialty's wards, bed status and clinic sessions). It is constant within a specialty and
varies only across them, so putting it in the per-patient sort key has exactly one effect: it
reorders patients by which department they were referred to.

Both directions of that are indefensible. If availability raises rank, patients in uncongested
specialties advance and the system serves whoever is cheapest to serve — the cream-skimming
distortion that waiting-list target regimes are criticised for. If scarcity raises rank, patients in
congested specialties advance on a system property they did not cause and cannot affect. Neither
survives being said to a patient.

Note also that the stated intent — *the importance of urgency depends on capacity* — is an
interaction between criteria, and preferential independence is precisely the condition an additive
weighted sum requires. The intent as stated rules out the aggregation it appears to suggest.

**Decision:** The interaction goes in the **weights**, not the values:

```
priority = α · urgency + (1 − α) · wait_normalised
α        = α_min + (α_max − α_min) · scarcity
```

`scarcity` is computed **once per decision** at hospital level, from the distinct specialty capacity
scores in the cohort, and is identical for every referral in it. Under pressure α rises and clinical
need dominates; under slack α falls and queue fairness gets more say. No referral is advantaged or
disadvantaged by its department. `wait_normalised` is min–max normalised within band, since
ordering only ever happens within a band.

`α_min = 0.5`, `α_max = 0.9` — urgency never counts for less than waiting time, and waiting time
never leaves the ordering entirely. Both are `modelled` parameters in the dataset's labelling sense:
deliberate choices with a stated reason, not fitted quantities. No published source sets them.

**Rationale:** This is the move the scarce-resource-allocation literature makes. Under crisis
standards of care, the excess mortality that first-come-first-served would produce is mitigated by
shifting to formal triage protocols based on patient status and potential benefit, and
first-come-first-served is treated as suboptimal specifically as resource constraints emerge.
Scarcity shifts weight from queue order toward clinical need — at the level of the allocation
policy, not the individual patient.

It is also one sentence to a clinician: *the hospital is under pressure today, so clinical urgency
is weighted more heavily than waiting time across this whole list.*

**Trade-off accepted:** Capacity has no effect on a single-specialty cohort, since scarcity is then
constant and α is the same either way. That is correct behaviour, not a defect: with one specialty
there is no cross-specialty comparison for capacity to inform.

---

### ADR-006: Uncategorised and Excluded referrals are ranked last, as two groups

**Date:** 2026-09-06
**Status:** accepted

**Context:** Two groups have no `severity_rank`: referrals with `cpc: null`, and Excluded (code 4).
The real 9004 cohort contains referrals with `triage_status: "triaged"` and no CPC.

**Decision:** Both are ranked, never dropped, after every categorised referral, in two
distinguishable groups — uncategorised first, Excluded last. Both are ordered internally by the same
breach → priority → oldest-first chain. `position` is a flat unique integer across the decision, so
the grouping is presentational; the UI renders the boundary.

**Rationale:** Merging them would collapse "this pathway deliberately does not apply" together with
"nobody recorded a category," and only the second is a defect someone needs to fix. A triaged
referral with no CPC has fallen through triage; burying it in one undifferentiated tail is how that
stays invisible. `RULE-TRIAGE-TURNAROUND` (21 days) is evaluated against the uncategorised group.

**Trade-off accepted:** The clinician UI must render two tail groups rather than one, and must not
present the uncategorised group as merely low priority — it is unknown priority, which is a
different and more urgent thing.

---

### ADR-007: `capacity_score` direction is required configuration

**Date:** 2026-09-06
**Status:** **open** — awaiting the capacity agent's author

**Context:** `RankingIn.capacity_score` is a 0–1 float with no documented direction. Whether 1.0
means "most beds free" or "maximum pressure" is owned by the capacity agent, which is being built in
parallel and does not yet exist. Read backwards, `scarcity` inverts, α inverts, and the system
weights urgency *least* when the hospital is under most pressure — exactly wrong, with every number
still in range and every ranking still superficially plausible. No test catches it without the
convention being stated.

**Decision (interim):** The direction is **required configuration with no default**. The agent
refuses to start unconfigured rather than guessing. Accepted values: `availability`
(`scarcity = 1 − capacity`) and `pressure` (`scarcity = capacity`). The configured value is recorded
in `coordinator_version` on every decision, so any ranking ever written is traceable to the
assumption it was made under.

**To close this ADR:** confirm the convention with the capacity agent's author, record it here, and
set the project default. Until then no decision written by this agent should be treated as final.

**Trade-off accepted:** An extra required flag, and a startup failure for anyone who forgets it. A
loud failure is the cheapest possible version of this problem; the alternative is a silently
inverted priority system.

---

### ADR-008: Scores are read through a replaceable seam

**Date:** 2026-09-06
**Status:** accepted

**Context:** `agent.agent_scores` is empty; the urgency and capacity agents are being built in
parallel. `RankingIn.urgency_score` and `capacity_score` are required with no defaults, so
`POST /decisions` is unwritable until those agents produce output. Waiting is not an option on a
seven-day build.

**Decision:** Scores are fetched through one interface with two implementations — a live client
calling `GET /runs/{run_id}/hospitals/{hospital_hipe}/scores`, and a deterministic fixture source.
Selection is explicit configuration, live is the default, and the choice is recorded in
`coordinator_version` so a decision written from stub scores can never be mistaken for a real one.

A referral with **no urgency score is excluded from the decision and reported**, never defaulted to
zero: a missing score is missing information, not low urgency. A referral missing only its capacity
score is ranked normally, since capacity affects only the cohort-level weight (ADR-005).

**Trade-off accepted:** One layer of indirection that would be unnecessary in a finished system,
kept because it is also what makes the ranking logic unit-testable without network I/O (NFR5).
