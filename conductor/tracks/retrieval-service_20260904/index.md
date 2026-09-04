# Track: Retrieval Service

**ID:** `retrieval-service_20260904`
**Type:** feature
**Status:** in progress (reopened)
**Created:** 2026-09-04
**First completed:** 2026-09-04 — reopened same day for Phase 6 (evidence resolution)

## Summary

A standalone FastAPI retrieval service, its own container in the (now consolidated, single) root
`docker-compose.yml` alongside `db` (Postgres) and `oxigraph`, mediating every read and write between
Postgres `core`/`agent` and the Oxigraph knowledge graph for the not-yet-built urgency/capacity/
coordinator agents and the clinician UI. This is the concrete implementation of **ADR-002** (confirmed
and recorded 2026-09-04): Postgres is the system of record; the graph gets a synchronous, single-writer
projection on successful Postgres commit. The service's port is published to the host and every
endpoint requires bearer-token auth.

**Delivered 2026-09-04.** `POST /scores`/`/decisions`/`/overrides` implement the write-projector; `GET`
endpoints cover wait counters (wrapping `kg/queries/wait_counters.rq` unmodified), decision/evidence
audit-trail lookup, and role-scoped evidence lookup. Also consolidated `dataset/docker-compose.yml`
into the root compose file (one project, one network, one `.env`) at the user's request, and closed a
real gap found along the way: `eat:cites`' 1..n cardinality on `RankedPlacement` wasn't enforced at the
API layer. 372 tests, 97% coverage on `app/`, 11/11 acceptance criteria met against the running system.
See [`retrieval/README.md`](../../../retrieval/README.md) for the endpoint list and how to run it.

Completing this track resolves the blocker recorded against
[`explainable-agent-based-triage_20260828`](../explainable-agent-based-triage_20260828/index.md) — its
decisions.md now records ADR-002, and its agents should call this service's write endpoints rather
than writing to Postgres or the graph directly.

## Documents

- [Specification](./spec.md) — requirements and acceptance criteria
- [Plan](./plan.md) — five phases, TDD-structured
- [Metadata](./metadata.json)

## Phases

1. ADR-002 record + service scaffold
2. Fixture decision generator
3. Write endpoints — the ADR-002 projector
4. Read endpoints
5. Integration and acceptance pass
6. Evidence resolution (reopened) — `GET /evidence/resolve`, the second hop a UI needs to turn a
   cited evidence IRI into the actual data behind it (e.g. a `ClinicSession`'s slot counts), since
   walking `eat:cites` only gets you *which* node was cited, not *what it says*

## Project Context

- [Product Definition](../../product.md)
- [Tech Stack](../../tech-stack.md)
- [Workflow](../../workflow.md)
- [Retrieval service reference index](../../retrieval-service-references.md)
- [Retrieval/database onboarding briefing](../../retrieval-database-onboarding.md)
