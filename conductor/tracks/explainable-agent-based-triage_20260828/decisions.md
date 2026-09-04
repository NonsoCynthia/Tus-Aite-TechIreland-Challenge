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
