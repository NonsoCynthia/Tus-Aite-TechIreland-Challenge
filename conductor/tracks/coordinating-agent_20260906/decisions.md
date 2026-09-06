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

**Superseded in part by ADR-010:** `wait_normalised` is no longer min-max normalisation of
`adjusted_wait_days` within band. The real 9004 cohort showed min-max compresses most of the queue
into a narrow low band while a handful of outliers occupy the top, defeating the purpose of
normalising at all. `wait_normalised` is now the referral's percentile rank within its band — see
ADR-010 for the data and the replacement. The rest of this ADR's reasoning (capacity in the
weights, not the values; scarcity computed once per decision; `α_min`/`α_max` values) is unaffected
and stands as written above.

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

**Note (2026-09-06):** Excluded (`cpc` 4) is defined in `core.ref_codes` but does not occur
anywhere in data v1.1. `SELECT triage_category, count(*) FROM core.triage_events` returns only
categories 1 (1,248), 2 (1,586) and 3 (1,378) across 4,212 rows. The excluded-tail branch therefore
exists for correctness against `ref_codes`, not against observed data, and is exercised only by
hand-built test fixtures. It is kept deliberately: a regenerated or real dataset could contain
Excluded referrals, and the coordinator must not break on the first one. Do not delete it as dead
code.

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

---

### Reference: `EvidenceType` and `CitationRole` (from `retrieval/app/schemas.py`)

**Date:** 2026-09-06
**Status:** recorded (task 1.1) — read directly from source, not guessed

`retrieval/app/schemas.py` lines 27–28:

```python
EvidenceType = Literal["observation", "condition", "triage_event", "bed_status", "clinic_session"]
CitationRole = Literal["urgency", "capacity", "timeframe", "multi_list"]
```

- **`EvidenceType`** permitted values: `observation`, `condition`, `triage_event`, `bed_status`,
  `clinic_session`.
- **`CitationRole`** permitted values: `urgency`, `capacity`, `timeframe`, `multi_list` — matching
  the four `eat:cites` role subproperties named in FR7.

Used at `evidence_type` (line 37, `ScoreCitationIn`; line 120, referenced by the ranking citation
schema) and `role` (line 124). Any citation the coordinator builds must use exactly one of each of
these value sets; `iri.validate_segment` (task 1.2) governs the `evidence_key` format separately.

---

### ADR-009: What a `RankedPlacement` cites, given `EvidenceType` can't express it

**Date:** 2026-09-06
**Status:** **open** — pending the retrieval service change

**Context:** `retrieval/app/schemas.py` defines `EvidenceType` as a closed `Literal` of five
primary-input types (`observation`, `condition`, `triage_event`, `bed_status`, `clinic_session`).
Roles and types are independent axes, so of the four `CitationRole` values, `urgency` and
`timeframe` have no evidence type that fits. The coordinator's real evidence for a position is the
urgency `Score` node and the `ReferralState` carrying the wait against the CRT. Both are already
minted — `namespaces.md` defines both IRI templates, `iri.py` already builds both (`score_iri`,
`referral-state`) — only the `Literal` omits them. A change request has been raised with the
retrieval service's author.

**Decision:** Build against the proposed enum. The coordinator emits `score` and `referral_state`
citations. `POST /decisions` will reject them with `422` until the `Literal` is widened, which is
visible rather than silent. A `--legacy-citations` flag falls back to copying the urgency agent's
own citations onto the placement for the `urgency` role and omitting `timeframe` entirely, so there
is a working path if the change is declined.

**Consequences:** The fallback loses one hop of provenance — the audit trail reads "ranked here
because of these vitals" rather than "because of this score, which cited these vitals". Omitting
`timeframe` is safe because `RankingIn.citations` requires `min_length=1`, not one per role. Citing
a `triage_event` for `timeframe` was rejected as inaccurate, not merely imprecise: it records when
triage happened, not how long someone waited against their CRT.

**Trade-off accepted:** The coordinator ships against an enum that does not yet validate, so early
runs surface a `422` until the retrieval service is updated — an explicit, tracked gap rather than a
silently wrong citation.

---

### ADR-010: `wait_normalised` uses percentile rank within band, not min-max

**Date:** 2026-09-06
**Status:** accepted

**Context:** ADR-005 specified min-max normalisation of `adjusted_wait_days` within band. The real
9004/2026-08-30 cohort shows why that fails. Every band runs from 0 to roughly 870 days with a
median around 150-180, so min-max puts the median referral at about 0.18 and compresses the bulk of
the queue into the bottom fifth of the range while a handful of 800+ day referrals occupy the top.
Per band (min/median/max, in days): `cpc 1` (n=131) 0/158/849, `cpc 2` (n=141) 0/179/893, `cpc 3`
(n=133) 0/151/871, null (n=95) 0/135/887. The distribution is right-skewed by construction — the
generator draws from NTPF's published band distribution, and that skew is a preserved property of
the data, not an artefact.

**Decision:** `wait_normalised` is the referral's percentile rank among the waits in its own band,
scaled 0 to 1. Ties share a percentile — this is specified and tested, since letting rank depend on
input order would break NFR4 determinism.

**Rationale:** Percentile rank measures position among peers rather than distance from the single
longest waiter, so one outlier cannot flatten the band. It restores a full 0-1 spread, without which
`α` has nothing to trade and ADR-005's mechanism is decorative. It is also directly explainable —
"waited longer than 70% of others in their category" — which matters because it reaches the
clinician through `rationale_summary` (FR8).

**Rejected alternative:** log-scaled min-max, which keeps magnitude and puts the median near 0.55,
but produces a number no clinician can state plainly. Recorded here as the fallback if magnitude is
later judged clinically necessary.

**Trade-off accepted:** Percentile rank discards magnitude, so a 400-day and an 800-day wait become
adjacent ranks when nothing sits between them. In bands of 130+ referrals from a continuous
distribution this is rare, and the ordering remains correct, only not proportionate.
`wait_normalised` is used for sorting and is never displayed as a number.

---

### ADR-011: CRT breach is a hard tier above priority, not a weighted factor

**Date:** 2026-09-06
**Status:** **OPEN** — needs a clinical decision, not an engineering one

**Context:** The sort key is `(severity_rank, crt_breached desc, priority desc, referral_date asc,
pathway_number asc)`. Because `crt_breached` sits above `priority`, it is a hard tier: within a
band, every breached referral outranks every non-breached one at any score values. A referral with
urgency 0.99 one day inside its 28-day CRT ranks below one with urgency 0.05 one day past it. `α`
cannot affect this — it only orders within a breach tier.

This was not a decision anyone made. FR3 specified CPC then CRT breach then oldest-first at a time
when scores were not in the ordering at all; ADR-004 later put priority into the chain, which made
the relative standing of breach and clinical urgency a live question that has never been asked.

The data makes it acute. Per `dataset/docs/HOW_THE_DATA_WAS_MADE.md`, NTPF's published bands imply
91.2% of urgent referrals breach the 28-day CRT and the generator produces 90.0%. So the breached
tier holds almost the entire urgent band, and the few non-breached urgent referrals — the recent
ones, who may be the acutely unwell — sit at the bottom of it. Observed in the Phase 4 verification:
all top-20 positions were breached, with `wait_normalised` mostly above 0.7.

**Options:**

- **(a)** Keep breach as a hard tier, on the grounds that a CRT is an obligation rather than a
  preference.
- **(b)** Fold breach magnitude into the priority score so a sufficiently high urgency can outweigh
  a marginal breach.
- **(c)** Keep the tier but only for breaches beyond some margin.

**Status:** Open, referred to the responsible-AI/compliance lead and to clinical input. The code
currently implements **(a)** because that is what FR3 specifies. No decision written under (a)
should be presented as final until this is resolved.
