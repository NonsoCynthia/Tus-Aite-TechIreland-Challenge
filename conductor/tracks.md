# Tracks Registry

> This file tracks all development tracks (features, bugfixes, refactors, etc.)

## Active Tracks

| Track | Type | Status | Description |
|---|---|---|---|
| [explainable-agent-based-triage_20260828](./tracks/explainable-agent-based-triage_20260828/index.md) | feature | pending; ADR-002 resolved and implemented by `retrieval-service_20260904` — agents should call that service's write endpoints | Full build on top of graph-foundation: urgency agent, capacity agent, coordinator + audit trail, rationale layer, clinician UI + override loop, CPC/CRT compliance validation (proposal §14 Days 3–6). Write target settled by ADR-002 (Postgres, graph projects it) |
| [coordinating-agent_20260906](./tracks/coordinating-agent_20260906/index.md) | feature | pending; unblocked except final live-integration — ADR-007 (capacity sign convention) open, awaiting the capacity agent's author | Coordinating agent carved out of `explainable-agent-based-triage_20260828` FR3/FR6 so it can be built independently of the in-parallel urgency and capacity agents. Ranks one hospital-day cohort deterministically and writes it via `POST /decisions`. CPC as a non-compensatory band ordered by `severity_rank` (never the raw code), cohort-level scarcity modulating the urgency/waiting weight, CPC/CRT rule checks, citations, atomic write-back with 207 handling. No LLM; determinism is a tested property |

## Planned Tracks

| Track | Maps to | Depends on |
|---|---|---|
| Rehearsal and submission package | Day 7 | explainable-agent-based-triage_20260828 |

---

## Completed Tracks

| Track | Type | Description |
|---|---|---|
| [retrieval-service_20260904](./tracks/retrieval-service_20260904/index.md) | feature | Retrieval service mediating Postgres `core`/`agent` and the Oxigraph graph for agents and the clinician/hospital UI. Implements ADR-002: `POST /scores`/`/decisions`/`/overrides`/`/referrals`, plus read endpoints (wait counters wrapping `wait_counters.rq` unmodified, decision/evidence-audit-trail lookup with citations resolved inline to real values, role-scoped evidence lookup, agent-input endpoints for referral context/cohort/scores-for-run with computed CRT breach). Also consolidated the dataset + app docker-compose stacks into one project. Reopened repeatedly the same day: evidence resolution, IRI shortening, `/health` dependency checks (Phase 6); referral-context and coordinator-input agent-input endpoints (Phases 7-8); CRT breach flag (Phase 9); new-referral intake for the clinician/hospital UI, plus a UI-vs-agent labelling fix (post-completion). 411 tests, 97% coverage, 19 acceptance criteria met. See [`retrieval/README.md`](../retrieval/README.md) |
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
