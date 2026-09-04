# Tracks Registry

> This file tracks all development tracks (features, bugfixes, refactors, etc.)

## Active Tracks

| Track | Type | Status | Description |
|---|---|---|---|
| [explainable-agent-based-triage_20260828](./tracks/explainable-agent-based-triage_20260828/index.md) | feature | pending; ADR-002 resolved and implemented by `retrieval-service_20260904` — agents should call that service's write endpoints | Full build on top of graph-foundation: urgency agent, capacity agent, coordinator + audit trail, rationale layer, clinician UI + override loop, CPC/CRT compliance validation (proposal §14 Days 3–6) |
| [retrieval-service_20260904](./tracks/retrieval-service_20260904/index.md) | feature | reopened 2026-09-04; Phase 6 in progress (evidence resolution) | Retrieval service mediating Postgres `core`/`agent` and the Oxigraph graph for agents and the clinician UI; implements ADR-002 (Postgres-first writes, synchronous graph projection on success) |

## Planned Tracks

| Track | Maps to | Depends on |
|---|---|---|
| Rehearsal and submission package | Day 7 | explainable-agent-based-triage_20260828 |

---

## Completed Tracks

| Track | Type | Description |
|---|---|---|
| [graph-foundation_20260826](./tracks/graph-foundation_20260826/index.md) | feature | Knowledge graph foundation: OWL ontology, Oxigraph bootstrap, RDF projection (Morph-KGC/R2RML) over the `dataset/` Postgres pipeline. 590,814 triples, 19 SHACL shapes, `kg_loader` role isolated from `eval`. See [`kg/README.md`](../kg/README.md) |
| [add-missing-data-layer_20260903](./tracks/add-missing-data-layer_20260903/index.md) | chore | Add missing data-layer literal properties to the ontology |
| [complete-eat-ttl-owl_20260903](./tracks/complete-eat-ttl-owl_20260903/index.md) | chore | Complete the `eat.ttl` OWL ontology |
| [complete-exclusions-dictionary-test_20260903](./tracks/complete-exclusions-dictionary-test_20260903/index.md) | chore | Complete `EXCLUSIONS` dictionary in `test_column_coverage.py` |
| [extend-structural-shapes-every_20260903](./tracks/extend-structural-shapes-every_20260903/index.md) | feature | Extend structural SHACL shapes to every class |
| [map-cancellation-events-suspension_20260903](./tracks/map-cancellation-events-suspension_20260903/index.md) | feature | Map `cancellation_events` and `suspension_events` to RDF |
| [map-conditions-observations-rdf_20260903](./tracks/map-conditions-observations-rdf_20260903/index.md) | feature | Map conditions and observations to RDF |
| [map-reference-layer-rdf_20260903](./tracks/map-reference-layer-rdf_20260903/index.md) | feature | Map the reference layer to RDF |
| [map-referral-daily-triage_20260903](./tracks/map-referral-daily-triage_20260903/index.md) | feature | Map `referral_daily`, `triage_events`, `patients` and `persons` to RDF |
| [map-six-capacity-tables_20260903](./tracks/map-six-capacity-tables_20260903/index.md) | feature | Map the six capacity tables to RDF |
| [record-wait-counter-findings_20260903](./tracks/record-wait-counter-findings_20260903/index.md) | chore | Record wait-counter findings in the normative docs |
| [write-validate-queries-wait_20260903](./tracks/write-validate-queries-wait_20260903/index.md) | chore | Write and validate `kg/queries/wait_counters.rq` |

`wait-counter-sparql-fragment_20260903` is marked `superseded` in its own `metadata.json` (folded
into `write-validate-queries-wait_20260903`) and is intentionally omitted here.
