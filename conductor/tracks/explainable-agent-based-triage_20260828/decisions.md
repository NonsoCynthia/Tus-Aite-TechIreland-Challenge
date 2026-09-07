# Architecture Decision Records

**Track:** `explainable-agent-based-triage_20260828`

> Log decisions here as they're made during implementation. Each entry: date, decision, rationale,
> trade-off accepted.

---

### ADR-002: Where agent outputs get written

**Date:** 2026-09-04
**Status:** accepted

**Context:** Raised 2026-08-31 while reconciling `graph-foundation_20260826` against ADR-001 (see that
track's `decisions.md` for the full options analysis carried forward from there). Migration 006
already models the entire agent output surface in Postgres (`agent.agent_scores`, `agent_citations`,
`decisions`, `decision_rankings`, `decision_citations`, `rule_checks`, `overrides`), with `agent_rw`
holding `INSERT` on all of them. The proposal (§9) says agents write scores back to the graph "as graph
nodes and edges... which is what keeps the trail auditable," but is silent on whether Postgres or the
graph is authoritative. Three options were on the table: Postgres as record with the graph a copy,
graph-only, or both independently — the last of these was rejected outright, since it repeats the exact
divergence-risk failure mode that decisions 1 and 2 (the shared wait-counter fragment, the shared SHACL
shape file) were explicitly designed to prevent.

**Decision:** **Postgres is the system of record.** The graph receives a **synchronous, single-writer
projection**: one code path writes to Postgres first, and only pushes the corresponding RDF triples
(`eat:Score`, `eat:Decision`, `eat:RankedPlacement`, `eat:cites` + its four role subproperties) into
the appropriate named graph (`…/kg/graph/run/{run_id}` or `…/kg/graph/overrides`) if that Postgres
write succeeds. This does not reuse the Morph-KGC mapping files, which are built for batch runs, not
low-latency single-row writes — it is a small, purpose-built writer applying the same deterministic IRI
conventions from `conductor/kg/namespaces.md` via SPARQL Update, immediately after each Postgres
commit.

**Implementation:** `retrieval-service_20260904` — a standalone FastAPI service that is the single
write path for every agent and clinician-UI output, implementing exactly this Postgres-then-graph
sequence. See that track's `spec.md` FR2 for the endpoint-level contract, including how a Postgres
commit that succeeds but a graph write that then fails is surfaced (never a silent success).

**Consequences:** Real transactional constraints (`dr_unique_position`, `dc_role_valid`, the FK from
`rule_checks` to `core.ref_rules`) keep doing real work, for free, on the authoritative copy — this was
option A's advantage and it is kept. The literal claim "the graph is where the audit trail lives" is
now "the graph is a synchronous, faithful projection of the audit trail" — a real but small narrowing
of the pitch, accepted because the alternative (graph-only) forfeits those constraints unless
hand-rebuilt in application code or SHACL, and "both, independently" was rejected as a repeat of a
failure mode this project has twice already designed against. A graph-projection failure after a
successful Postgres commit is a detectable, recoverable inconsistency (the row stands, the failure is
reported) rather than data loss — but it is a new failure mode this codebase did not previously have,
and retry/reconciliation beyond detect-and-report is explicitly out of scope for
`retrieval-service_20260904`.

**Note on a since-superseded write-up:** `origin/main` briefly recorded a different resolution to this
same question — Postgres as write target with a *batch* Morph-KGC-style mapping file
(`kg/mappings/agent_outputs.rml.ttl`, never built) projecting `agent.*` into the graph, rather than a
synchronous per-write projection. That version was written independently of
`retrieval-service_20260904` and predates its delivery; this merge keeps the synchronous-projection
decision above because it is what was actually built, tested (411 tests), and is now the real write
path every agent and the clinician UI use — recording an ADR that contradicted the shipped service
would leave this document wrong the moment it merged.

---

### ADR-003: `capacity_score` polarity — pressure, not availability

**Date:** 2026-09-05
**Status:** accepted

**Context:** spec.md FR2 says the capacity agent "applies deterministic constraint reasoning
(available capacity, overcrowding state)" and writes a score, but neither the spec, the ontology
(`conductor/kg/ontology.md`), nor `product.md` states which direction the number runs — a `Score`
node's `eat:scoreValue` is just a decimal, undocumented in polarity. Two readings were both
plausible: `1.0` = "plenty of room" (an availability score) or `1.0` = "severely constrained" (a
pressure score). Nobody was available to ask before this needed resolving, unlike
`retrieval-service_20260904`'s comparable IRI-convention gaps (`conductor/kg/namespaces.md`'s own
"stop and ask" instruction), so this is recorded here for the coordinator's implementer and the
compliance lead to review, rather than left undocumented in `capacity_agent/scoring.py` alone.

**Decision:** `capacity_score` is a resource-**pressure** score: `0.0` = ample capacity, no
constraint pressure; `1.0` = severe constraint pressure — the same polarity as the urgency agent's
score, where `1.0` is always "more clinically urgent," never the reverse for one agent and not the
other.

**Rationale:** `tech-stack.md`'s Agent Reasoning Model has the coordinating agent "combine urgency
and capacity scores into a ranked list" (`product.md` #8). A combiner (sum, weighted average, or
max) only produces a sensible ranking if both inputs point the same way — if capacity meant
"availability," a coordinator naively summing the two would rank a low-urgency referral at an
empty, ample-capacity ward *above* a high-urgency one at a severely overcrowded ward, which is
backwards. Pressure-polarity means "higher combined score = more reason to prioritise" holds for
both agents uniformly, whatever combination function Phase 3 ultimately picks.

**Trade-off accepted:** if the coordinator's implementer intended availability-as-score, this ADR
is the place that surfaces the mismatch before Phase 3 ships, not a silent sign error discovered
against real rankings. `capacity_agent/scoring.py`'s module docstring and `capacity-agent/README.md`
both restate this polarity where a reader of just the code would otherwise have to infer it.

---

### ADR-004: `urgency_score` v1 is NEWS2-only — an incomplete signal, knowingly shipped

**Date:** 2026-09-07 (revised same day, see *Correction* below)
**Status:** **open** — needs a clinician / the responsible-AI lead

**Context:** spec.md FR1 says the urgency agent "computes MTS category and NEWS2 score
deterministically from that data," and plan.md Phase 1 carries a task for each. Neither instrument
in `core.observations` identifies referral urgency on its own, for different reasons.

**MTS cannot be computed here at all.** Two independent reasons, both from
`dataset/generator/generate.py`:

1. **Its starting input is absent.** Real Manchester triage selects a presentation flowchart from
   the chief complaint, then applies discriminators. The generator writes `chiefcomplaint` as the
   empty string on every observation (`generate.py:553`). There is no flowchart to select.
2. **The stored `mts_category` is drawn from the CPC band, not from the patient.**
   `generate.py:538` picks a colour uniformly from `MTS_BY_RANK[rank]`, keyed on the referral's own
   `SEVERITY_RANK`: `{1: ["red","orange"], 2: ["orange","yellow"], 3: ["yellow","green","blue"]}`.
   It carries no information beyond CPC plus noise — at most ~1.6 bits, all of it already in the
   band, and lossy even about that (an `orange` may be Urgent or Semi-Urgent). Since the coordinator
   already treats CPC as a non-compensatory band (`coordinating-agent_20260906` ADR-004), scoring
   the colour would **double-count CPC**: once as the band that orders the list, once inside the
   score that orders within it.

**NEWS2 can be computed, but it is a weak urgency signal — and this is measured, not suspected.**
`dataset/docs/HOW_THE_DATA_WAS_MADE.md` §4 lists it under "Three things the data disproved":

- The build spec required `news2` x `severity_rank` correlation in 0.35–0.65. A sweep across the one
  free parameter **never exceeded 0.253**, at any value.
- The best possible rule on `news2` alone recovers the triage category only **17.5 percentage
  points** better than guessing the most common one.
- **54–59% of the highest-acuity patients score `news2 <= 2`.**

This is deliberate, not a defect: `latent_hazard` in `ground_truth.csv` is never computed from
`news2` (`generate.py:767`), so an agent reading vitals cannot be graded against its own input.
`DATASET_README.md` §7.6 carries the worked case — a suspected melanoma, every vital normal,
clinically urgent. This agent scores that patient **0.0**.

That same section states the requirement directly: *"an urgency agent must read condition, pathway,
referral source and the high-needs flag, not just physiology."* Three of those four are not
currently reachable — see ADR-008.

**Decision:** v1 scores on NEWS2 alone, and is documented everywhere as an **incomplete** urgency
signal rather than a triage judgement. `score_urgency()` is built with the capacity agent's
weight-renormalisation shape (`capacity_agent/scoring.py:score_capacity`) so further components add
without restructuring. `method` is `urgency-news2-v1`, naming the single component explicitly, so a
v1 score can never be mistaken for one written under a later multi-component calibration.

**Rationale:** NEWS2 is the only component available today that is both computable and auditable
end to end — a clinician can re-add the six numbers by hand and check the result, and
`test_real_fixture_news2_matches_the_generators_own_value` checks recomputation against the
generator's own stored column. That is worth shipping as a first slice. It is not worth
*presenting* as urgency. `conditions` is already returned by the context endpoint and is the
obvious next component; the remaining three fields need ADR-008 resolved first.

**Trade-off accepted:** spec.md FR1 and plan.md Phase 1's first task are not met, and roughly half
of genuinely urgent referrals will score at or near zero. **No ranked list built on v1 alone should
be described as clinically prioritised**, in the UI, in the pitch, or in the rationale text.
`workflow.md` puts the responsible-AI review at the moment an agent first produces output — this is
that moment, and this ADR is what that review should read first.

**Correction (2026-09-07).** The first version of this ADR justified NEWS2-only partly on the
grounds that NEWS2 "works" while MTS does not. That was wrong, and it was wrong for a reason worth
recording: it was reasoned from `generate.py` — the code that *makes* the data — without reading
`dataset/docs/` or the data itself. The generator shows NEWS2 is computable; it does not show
whether the result discriminates urgency. The dataset team had already measured that it does not.
**Reading the code that produces a dataset is not the same as meeting the dataset**
(`BUILDING_AN_AGENT_WITH_CONDUCTOR.md` Step 7), and the three tests still skipping for want of a
captured fixture are the same gap in a different form.

---

### ADR-005: The most recent observation is the one scored

**Date:** 2026-09-07
**Status:** accepted

**Context:** `GET /referrals/{hospital_hipe}/{pathway_number}/context` returns
`observations` `ORDER BY obs_datetime` ascending (`retrieval/app/db.py:342-351`) and a referral may
carry more than one. Nothing in spec.md says which to score.

**Decision:** the **last** element — the most recent observation — is scored, and its columns are
the cited evidence.

**Rationale:** it is the only choice that is stable under new data arriving. "Worst in window" is
arguably the safer clinical reading, but it is not reproducible: a referral's score would change
when a *newer, better* observation arrives, because the historic worst stays in the window and keeps
winning. Reproducibility is a compliance property here, not a convenience
(`tech-stack.md`'s Agent Reasoning Model), so it takes precedence.

**Trade-off accepted:** a patient who deteriorated sharply and then partially recovered scores on
the recovery, not the deterioration. In this dataset that is close to moot — the generator writes
exactly one observation per referral (`generate.py:460`) — but it will not stay moot
against real time-series data, and this ADR should be revisited before any such data is used.

---

### ADR-006: NEWS2 is normalised through its clinical escalation bands, not linearly

**Date:** 2026-09-07
**Status:** accepted (pending distribution check against real data)

**Context:** `ScoreIn.score` is constrained to `[0, 1]`, so a raw NEWS2 (0–20 as the generator caps
it) must be mapped. The obvious `news2 / 20` is a trap with precedent in this repo: the coordinator's
min–max normalisation of waiting time put the median referral at 0.18 in every band, leaving its
weighting parameter with nothing to trade (`BUILDING_AN_AGENT_WITH_CONDUCTOR.md` Step 7, "the
distribution defect"). NEWS2 here will behave the same way — the cap is 20, but air-breathing scale-1
scores top out near 18 and cluster low, so a linear map compresses almost every referral into the
bottom fifth of the range and the score stops discriminating where it matters.

**Decision:** NEWS2 maps to `[0, 1]` through the **clinical escalation thresholds** — low (0–4),
low-medium (5–6), high (7+) — as calibrated breakpoints in `urgency_agent/calibration.yml`, not as
constants in `scoring.py`. `product.md`'s Calibration Configuration principle: a clinician or
compliance reviewer retunes the mapping by editing committed YAML, without reading Python.

**Rationale:** the escalation bands are where clinicians actually change behaviour, so separating the
score there puts the resolution where decisions get made. It also makes the mapping defensible to a
reviewer by reference to the NEWS2 rubric itself rather than to an arbitrary divisor.

**Trade-off accepted:** a banded map is a step function — two referrals either side of a breakpoint
separate more than their one-point NEWS2 difference warrants, and two inside a band separate less.
That is deliberate, and it is why this is calibration rather than code. **The breakpoints are not
confirmed against the real distribution yet**; that check is Step 7 of the build process and this
ADR's status should be revisited when the fixture is captured.

---

### ADR-007: Paediatric referrals are refused, not scored

**Date:** 2026-09-07
**Status:** **open** — needs a clinician

**Context:** NEWS2 is validated for **adults**. It is explicitly not a paediatric tool; children
compensate and then decompensate abruptly, which is why PEWS exists as a separate instrument with
age-banded physiological ranges. Specialty `0601` in this dataset is paediatric
(`generate.py:50`), and its patients are generated at ages **2–14** (`generate.py:405`). Applying
adult NEWS2 thresholds to a 4-year-old produces a number that is in range, ordinally plausible, and
clinically meaningless — a resting heart rate of 120 scores 2 in an adult and is unremarkable in a
toddler.

Note that `specialty_hipe` is the *only* paediatric signal the agent can see. The generator does
carry a `dob` on each referral, but `GET /referrals/.../context` does not return it
(`retrieval/app/db.py:330-331` selects no patient demographics), so age-based detection is not
available to this agent even in principle — the specialty code is the whole test.

**Decision:** the urgency agent **refuses to score** any referral whose `specialty_hipe` is `0601`,
raising `InsufficientUrgencyEvidenceError` with the paediatric reason named. Nothing is written for
that referral: no score, no citations.

**Rationale:** the coordinator already handles this correctly downstream —
`coordinating-agent_20260906` ADR-008 excludes a referral with no urgency score from the decision and
**reports** it, explicitly refusing to default it to zero, because "a missing score is missing
information, not low urgency." Refusing therefore surfaces as a named exclusion a reviewer can see,
whereas emitting an adult-scaled NEWS2 would surface as an ordinary-looking rank nobody would ever
question. Given the choice between a visible gap and an invisible error, this system's whole framing
takes the visible gap.

**Trade-off accepted:** every paediatric referral falls out of the ranked list until a paediatric
pathway exists, which is a real loss of coverage and must be visible in the clinician UI rather than
silent. Whether the right answer is PEWS, an age-banded NEWS2 variant, or a separate paediatric
agent is a clinical decision. Until it is made, no ranked list produced by this system should be
described as covering paediatric referrals.

---

### ADR-008: The context endpoint does not expose the fields urgency actually needs

**Date:** 2026-09-07
**Status:** **open** — a change request against `retrieval-service_20260904`, not this track's to decide

**Context:** `dataset/docs/HOW_THE_DATA_WAS_MADE.md` §4 states, as a measured finding rather than a
design preference, that *"an urgency agent must read condition, pathway, referral source and the
high-needs flag, not just physiology"* — because NEWS2 alone recovers triage category only 17.5
percentage points better than guessing (ADR-004).

All four fields exist in `core.referral_daily`, and `retrieval-service_20260904` itself writes three
of them on intake (`POST /referrals`, `retrieval/app/db.py:283-300`). But
`GET /referrals/{hospital_hipe}/{pathway_number}/context` does not return them. Its referral SELECT
(`retrieval/app/db.py:330-331`) is:

```sql
SELECT hospital_hipe, pathway_number, specialty_hipe, clinic_code,
       referral_date, referral_received_date, triage_status, as_of_date
```

Present in the table, absent from the response:

| Field | Why urgency needs it |
|---|---|
| `priority_level_gp` | The referring GP's own priority — a clinical judgement made with the patient present |
| `referral_source` | A consultant or ED referral is not an equivalent signal to a routine GP one |
| `high_clinical_or_social_needs` | An explicit vulnerability flag; ~7% of referrals (`generate.py:746`) |

`conditions` **is** returned and needs no change. Per ADR-002 the agent may not read
`core.referral_daily` directly to work around this, and doing so would be the wrong fix regardless:
the mediator exists so that every agent input is one reviewable contract.

**Decision:** the gap is recorded here and the fields are **not** worked around. v1 ships NEWS2-only
(ADR-004) and the next component will be built from `conditions`, which is already reachable. The
change request is: add `priority_level_gp`, `referral_source` and `high_clinical_or_social_needs` to
the `referral` object returned by `GET /referrals/.../context`.

**Rationale:** additive, three columns from a row the query already reads, and every one of them is
already written by that same service — so this is exposure, not new plumbing. Raising it while the
scorer is still one component is far cheaper than reweighting a finished multi-component model
around a late-arriving input (`BUILDING_AN_AGENT_WITH_CONDUCTOR.md` Step 9).

**Trade-off accepted:** until this lands, the urgency agent cannot implement what the dataset's own
documentation says it must, and ADR-004's incompleteness cannot be fully remedied no matter how
much work happens inside `urgency-agent/`. That dependency should be visible on the track board
rather than discovered when the scores look wrong.
