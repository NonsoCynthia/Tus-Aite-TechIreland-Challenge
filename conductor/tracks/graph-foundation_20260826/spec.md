# Spec: Knowledge Graph Foundation

**Track:** `graph-foundation_20260826`
**Type:** feature
**Maps to:** Proposal §14 Day 1 and Day 2, plus the Day 3 capacity-agent input model

## Overview

Build the data and graph substrate every other component depends on: an OWL ontology formalising the
triage domain, a running Oxigraph triple store bootstrapped with that ontology, a synthetic patient
and referral generator calibrated to Irish statistics, and a SimPy bed occupancy simulation calibrated
to published HSE/INMO figures.

The track ends when the urgency, capacity, and coordinator developers can all start work
simultaneously against a seeded, queryable graph without waiting on each other.

## Background

There is no single Irish dataset linking referrals, urgency, and live bed capacity. That gap is why
simulation is necessary, and why real datasets are used to keep the simulation grounded rather than
arbitrary. The graph is not merely a data store — it is the explainability mechanism, so the schema
must double as an audit log from the first commit. Retrofitting auditability later is what produces
the black box this project exists to avoid.

Per proposal §14, agent development on Days 3–4 depends on schema and seed data from Days 1–2, so
this track must not slip. Folding the bed simulation in here (rather than leaving it to Day 3) removes
a further dependency for the capacity agent developer.

## Functional Requirements

### FR1 — OWL Ontology

Formalise the entity classes and relationships from proposal §10.

**Entities:** `Patient`, `Referral`, `Condition` (ICD-10-AM coded), `UrgencySignal`,
`ClinicalPrioritisationCategory`, `Specialty`, `Hospital`, `Ward`, `BedStatus`, `Agent`, `Decision`,
`Clinician`.

**Relationships:** `presentsWith` (Patient→Condition), `hasSignal` (Referral→UrgencySignal),
`assignedTo` (Referral→Specialty), `locatedAt` (Specialty→Ward), `hasStatus` (Ward→BedStatus),
`scored` (Agent→Referral, **score carried as an edge property**), `ranks` (Decision→Referral),
`cites` (Decision→UrgencySignal | BedStatus).

The ontology must express the constraint that a `Decision` citing an urgent `Referral` cannot rank it
behind a semi-urgent `Referral` still inside its CRT. Encoding it in OWL is required even though
enforcement lands in a later track — the constraint must be declared where the schema lives.

SNOMED CT and HL7 FHIR RDF vocabularies are layered on for `Condition` and for patient/encounter
structure.

### FR2 — Oxigraph Bootstrap

- Oxigraph runs via Docker Compose with a persistent volume
- A bootstrap command loads the ontology and named graphs, and is idempotent — re-running it must not
  duplicate triples
- Thin Python client exposing `query(sparql)` and `update(sparql)` against the SPARQL 1.1 HTTP endpoints
- Endpoints configurable via `OXIGRAPH_QUERY_URL` / `OXIGRAPH_UPDATE_URL` so the Fuseki swap path
  documented in tech-stack.md stays open

### FR3 — Synthetic Patient and Referral Generator

- Parameterised by HIPE published specialty mix, age and sex distribution, and length-of-stay
  statistics, so case mix looks Irish though no individual record is real
- List size and specialty volume calibrated to NTPF Open Data structure
- Each referral carries: a CPC (urgent / semi-urgent / routine), a referral date, an assigned specialty,
  at least one `Condition` with an ICD-10-AM code, and urgency signals sufficient to compute MTS and NEWS2
- **Seeded and reproducible** — the same seed yields the same cohort, so downstream test failures are
  reproducible
- Calibration inputs live in committed config, not hardcoded, so the compliance lead can inspect them
- Every generated entity is labelled synthetic in the graph itself, not only in the UI

### FR4 — SimPy Bed Occupancy Simulation

- Discrete-event model of arrivals, admissions, length of stay, and discharge per ward
- Calibrated to published HSE/INMO daily trolley and occupancy figures, so the capacity agent is
  stress-tested against realistic contention rather than a comfortable synthetic average
- Produces a time series of `BedStatus` per `Ward`, written into the graph
- Capable of a sustained-overcrowding scenario (occupancy >100%) — the condition the capacity agent
  exists to reason about
- Seeded and reproducible on the same terms as FR3

### FR5 — Seeded Graph

A single command takes a clean checkout to a queryable graph containing the ontology, a synthetic
cohort, and a bed-status time series. Documented SPARQL examples demonstrate:
- retrieving a referral with its conditions and urgency signals
- retrieving current bed status for a specialty's ward

## Non-Functional Requirements

- **NFR1** — Bootstrap from clean checkout to seeded graph in under five minutes on a laptop. Nine
  people do this on Day 1; a slow path costs the team hours in aggregate.
- **NFR2** — Generating 1,000 referrals completes in under 60 seconds.
- **NFR3** — Tier 1 coverage ≥80% on calibration and scoring-input logic; Tier 2 ≥60% on graph
  helpers and the generator, per `workflow.md`.
- **NFR4** — No real patient data, no PII, at any point.
- **NFR5** — `ruff` and `mypy` clean.

## Acceptance Criteria

1. `docker compose up -d` starts Oxigraph and it answers a SPARQL query.
2. The bootstrap command loads the ontology; running it twice produces no duplicate triples.
3. Generating with a fixed seed twice produces byte-identical output.
4. A generated cohort's specialty mix matches the HIPE-derived config within a documented tolerance,
   asserted by a test.
5. The bed simulation produces a `BedStatus` series that reaches >100% occupancy in the overcrowding
   scenario, asserted by a test.
6. A SPARQL query returns a referral with its conditions, urgency signals, CPC, and referral date.
7. A SPARQL query returns current bed status for a given specialty's ward.
8. Every generated node is identifiable as synthetic via a graph predicate.
9. The OWL ontology declares the CPC/CRT ordering constraint.
10. A README section lets a teammate go from clone to seeded graph unaided.

## Out of Scope

- Urgency scoring logic (MTS/NEWS2 computation) — next track
- Capacity constraint reasoning — next track
- Coordinator ranking, `Decision` node materialisation, `cites` edge construction — later track
- Clinician UI and override write-back — later track
- CPC/CRT violation *enforcement* — declared in OWL here, enforced later
- LLM rationale generation
- Any live or real-world data source
