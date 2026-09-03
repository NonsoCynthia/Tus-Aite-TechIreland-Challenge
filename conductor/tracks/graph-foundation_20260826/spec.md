# Spec: Knowledge Graph Foundation

**Track:** `graph-foundation_20260826`
**Type:** feature
**Maps to:** Proposal §14 Day 1 and Day 2
**Revised:** 2026-08-31, reconciled against [ADR-001](./decisions.md) — the graph is a projection of
the `dataset/` Postgres pipeline, not an independent generator.

## Overview

Build the graph substrate every other component depends on: an OWL ontology formalising the triage
domain **as the `dataset/` schema actually models it**, a running Oxigraph triple store, a loaded
Postgres database at a pinned version, and a projection layer that emits RDF from `core.*`.

The track ends when the urgency, capacity, and coordinator developers can all start work
simultaneously against a seeded, queryable graph without waiting on each other.

## Background

This track was planned on 2026-08-26, before the `dataset/` pipeline was merged. That pipeline
delivers, in Postgres, the substance of three originally planned phases — calibration config, the
synthetic cohort, and the bed occupancy series. ADR-001 closes those phases and makes Postgres the
source of record with Oxigraph holding a derived projection.

What remains genuinely undone is the graph itself: the ontology, the store, and the projection. The
projection is new work the original plan had no phase for, because that plan assumed a generator
writing triples directly.

The graph is not merely a data store — it is the explainability mechanism, so the schema must double
as an audit log from the first commit. Retrofitting auditability later is what produces the black box
this project exists to avoid.

## Domain Corrections From the Dataset Schema

The original spec described the domain from the proposal. The delivered schema models three things
differently, and the ontology must follow the schema, not the prose.

| Original assumption | What `dataset/` actually does | Consequence |
|---|---|---|
| `ClinicalPrioritisationCategory` is a first-class entity | CPC is `core.triage_events.triage_category`, an integer 1–4, attached to a triage event rather than to the referral | Model CPC as a property of a `TriageEvent`, not a standalone class. A referral awaiting triage has no category at all — `rd_awaiting_triage_has_no_event` guarantees it |
| Overcrowding means occupancy >100% | `bs_occupancy_range` **forbids** `occupancy_pct > 100`. Pressure is carried by `outliers`, `surge_capacity_in_use`, `delayed_transfers_of_care`, `awaiting_admission_over_9h` / `_over_24h`, and `gar_status` (G/A/R) | The ontology must expose the trolley and surge measures. Any downstream rule keyed on ">100% occupancy" is unsatisfiable against this data |
| CRT is measured against referral age | `core.referral_daily.adjusted_wait_days` is the suspension-adjusted clock, constrained `<= days_since_received`. Migration 008 asserts stored waits equal their date arithmetic | CRT breach must be computed from `adjusted_wait_days`, never from raw date subtraction |

Two further facts shape later tracks and are recorded here so they are not rediscovered:

- **MTS, ICTS and NEWS2 are already computed** in `core.observations` (`mts_category`, `icts_category`,
  `news2`) alongside the raw components (`hr`, `sbp`, `rr`, `temp`, `spo2`, `avpu`). The urgency agent
  can therefore recompute and cross-check rather than compute blind. `obs_one_scale_only` enforces
  that MTS and ICTS are mutually exclusive — adult and paediatric paths never both apply.
- **The CRT rules are seeded data, not code.** `core.ref_rules` holds `RULE-CRT-URGENT` (28 days),
  `RULE-CRT-SEMI` (91 days), `RULE-TRIAGE-TURNAROUND` (21 days), `RULE-ORDER` and `RULE-TIEBREAK`.
  `agent.rule_checks` carries a foreign key to it. Rule identifiers belong in the graph so a cited
  violation names the same `rule_id` the database does.

## Functional Requirements

### FR1 — OWL Ontology

Formalise the domain as the schema models it.

**Entities:** `Patient`, `Referral`, `TriageEvent`, `Condition`, `Observation`, `Specialty`,
`Hospital`, `Ward`, `BedStatus`, `Rule`, `Agent`, `Decision`, `Clinician`.

**Relationships:** `presentsWith` (Patient→Condition), `hasObservation` (Referral→Observation),
`hasTriageEvent` (Referral→TriageEvent), `assignedTo` (Referral→Specialty), `locatedAt`
(Ward→Hospital), `servesSpecialty` (Ward→Specialty), `hasStatus` (Ward→BedStatus), `scored`
(Agent→Referral, **score carried as an edge property**), `ranks` (Decision→Referral), and `cites`
(Decision→Observation | TriageEvent | BedStatus | Condition).

`cites` is the audit trail. Walking backward from any ranked position must reconstruct exactly which
evidence nodes produced it, without leaving the store.

Requirements:

- Referral identity is the composite `(hospital_hipe, pathway_number)`. IRI minting must be a single
  documented function over that pair, used everywhere, so an IRI is reversible to its Postgres row.
- Declare the CPC/CRT ordering constraint, keyed to `Rule` individuals carrying the `rule_id` values
  from `core.ref_rules`.
- SNOMED CT and HL7 FHIR RDF vocabularies layered on for `Condition` and patient/encounter structure.
- Model triage status (`awaiting_triage`, `triaged`, `redirected`, `rejected`, `removed`) — an
  untriaged referral is a distinct and rankable state, not missing data.

### FR2 — Oxigraph Bootstrap

- Oxigraph runs via Docker Compose with a persistent volume, alongside the existing `dataset/`
  Postgres service
- A bootstrap command loads the ontology, and is idempotent — re-running must not duplicate triples
- Thin Python client exposing `query(sparql)` and `update(sparql)` against the SPARQL 1.1 HTTP endpoints
- Endpoints configurable via `OXIGRAPH_QUERY_URL` / `OXIGRAPH_UPDATE_URL`, keeping the Fuseki swap
  path in `tech-stack.md` open

### FR3 — Dataset Acquisition and Load

- Load Postgres from the published dataset using `dataset/`'s own Makefile targets — do not
  reimplement fetch or load
- Pin to `dataset/versions.yml`: schema `008`, data `v1.1`, revision tag `v1.1`. Never a branch,
  never `latest`. Schema 008 and data v1.0 are incompatible.
- The projection reads through the `agent_rw` role, which cannot see `eval.ground_truth`. That role
  barrier from migration 007 must hold end to end — a projection running as a superuser would
  silently forfeit it.
- Default to the `sample` profile (~1.3 MB, referentially closed) for local work; `full` is opt-in.

### FR4 — Projection Layer

A new component reads `core.*` and emits RDF conforming to the ontology.

- Covers `hospitals`, `hospital_specialty`, `patients`, `referrals`, `referral_daily`,
  `triage_events`, `conditions`, `observations`, `wards`, `ward_specialty`, `bed_status`, and
  `ref_rules`
- Projects `as_of_date` snapshots faithfully — `referral_daily` is a daily time series, so the
  projection must either pin one `as_of_date` or model the series explicitly. Collapsing it silently
  would make wait clocks wrong.
- Stamps synthetic provenance on the named graph, plus the `data_version` and `schema_version` it was
  projected from, so a graph can always be traced to the dataset revision that produced it
- Re-projection is idempotent: projecting twice yields the same triples
- Reads only. The projection never writes to Postgres.

### FR5 — Seeded Graph and Handoff

A documented path takes a clean checkout to a queryable graph. Documented SPARQL examples demonstrate:

- retrieving a referral with its conditions, observations, triage category, and adjusted wait days
- retrieving current bed status for a ward serving a given specialty, including trolley and surge measures
- walking `cites` backward from a `Decision`, proving the audit path before anything writes to it

## Non-Functional Requirements

- **NFR1** — Clean checkout to seeded graph in under **fifteen** minutes on a laptop, of which the
  projection step itself is under five. Revised from the original five-minute total: ADR-001 puts a
  Hugging Face download and a database load upstream of the graph, and that cost must be measured
  rather than assumed away. Nine people do this on Day 1.
- **NFR2** — Projecting the `sample` profile completes in under 60 seconds.
- **NFR3** — Tier 1 coverage ≥80% on IRI minting and projection correctness; Tier 2 ≥60% on graph
  helpers, per `workflow.md`.
- **NFR4** — No real patient data, no PII, at any point.
- **NFR5** — `ruff` and `mypy` clean.

## Acceptance Criteria

1. `docker compose up -d` starts Oxigraph and it answers a SPARQL query.
2. The bootstrap command loads the ontology; running it twice produces no duplicate triples.
3. Postgres loads at the pinned schema `008` / data `v1.1`, verified by `dataset/`'s own
   `tests/test_schema.py` and `test_referential.py`. Cohort determinism is covered by
   `dataset/tests/test_determinism.py` and is **not** re-tested here — per ADR-001 this track
   generates no cohort of its own.
4. Cohort plausibility and calibration fidelity are satisfied by `dataset/tests/test_plausibility.py`.
   This track asserts only that the projection preserves what Postgres holds: for a sampled set of
   referrals, the projected triples round-trip back to identical column values.
5. Bed pressure is projected faithfully. Because `bs_occupancy_range` caps `occupancy_pct` at 100,
   the overcrowding case is asserted on the trolley and surge measures instead — a test confirms
   that wards with `gar_status = 'R'`, non-zero `surge_capacity_in_use`, or non-zero
   `awaiting_admission_over_24h` are present in the projection and reachable by SPARQL.
6. A SPARQL query returns a referral with its conditions, observations, triage category, and
   `adjusted_wait_days`.
7. A SPARQL query returns current bed status for a ward serving a given specialty, including trolley
   and surge measures.
8. Every projected node carries synthetic provenance, plus the `data_version` and `schema_version`
   it came from.
9. The OWL ontology declares the CPC/CRT ordering constraint, keyed to `rule_id` values matching
   `core.ref_rules`.
10. A README section lets a teammate go from clone to seeded graph unaided, including obtaining
    Hugging Face access.
11. The projection runs as `agent_rw` and a test confirms it cannot read `eval.ground_truth`.
12. Re-running the projection produces no duplicate or conflicting triples.

## Out of Scope

Closed by ADR-001 as delivered by `dataset/`:

- Synthetic patient and referral generation
- HIPE/NTPF calibration configuration
- SimPy bed occupancy simulation

Belonging to later tracks:

- Urgency scoring logic — next track
- Capacity constraint reasoning — next track
- Coordinator ranking, `Decision` materialisation, `cites` construction — later track
- Clinician UI and override write-back — later track
- CPC/CRT violation *enforcement* — declared in OWL here, enforced later
- LLM rationale generation
- Any live or real-world data source

## Unresolved

**Where do agent outputs live?** Migration 006 already models `agent.agent_scores`,
`agent_citations`, `decisions`, `decision_rankings`, `decision_citations`, `rule_checks` and
`overrides` in Postgres, with `agent_rw` holding INSERT on them. ADR-001 makes Postgres the source of
record for cohort data but does not say whether agents write scores to Postgres, to the graph, or to
both. The proposal (§9) says agents write to the graph, and that this is what keeps the trail
auditable. This track does not need the answer, but the next one does. Recorded in `decisions.md`.
