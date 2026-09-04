# Track: Retrieval Service

**ID:** `retrieval-service_20260904`
**Type:** feature
**Status:** done
**Created:** 2026-09-04
**Completed:** 2026-09-04 (reopened once same day, for Phase 6)

## Summary

A standalone FastAPI retrieval service, its own container in the (now consolidated, single) root
`docker-compose.yml` alongside `db` (Postgres) and `oxigraph`, mediating every read and write between
Postgres `core`/`agent` and the Oxigraph knowledge graph for the not-yet-built urgency/capacity/
coordinator agents and the clinician UI. This is the concrete implementation of **ADR-002** (confirmed
and recorded 2026-09-04): Postgres is the system of record; the graph gets a synchronous, single-writer
projection on successful Postgres commit. The service's port is published to the host and every
endpoint (except `/health`) requires bearer-token auth.

**Delivered 2026-09-04, Phases 1-5.** `POST /scores`/`/decisions`/`/overrides` implement the
write-projector; `GET` endpoints cover wait counters (wrapping `kg/queries/wait_counters.rq`
unmodified), decision/evidence audit-trail lookup, and role-scoped evidence lookup. Also consolidated
`dataset/docker-compose.yml` into the root compose file (one project, one network, one `.env`) at the
user's request, and closed a real gap found along the way: `eat:cites`' 1..n cardinality on
`RankedPlacement` wasn't enforced at the API layer.

**Reopened and delivered same day, Phase 6.** Three follow-up corrections, all from the user: `/health`
no longer required auth and now explicitly checks Postgres/Oxigraph connectivity (`200`/`503`); every
citation returned by the read endpoints is now resolved to its actual properties inline (not just an
IRI, and not a separate round-trip endpoint — folded directly into `GET /decisions`/`GET /evidence`);
every IRI in every response is short (namespace prefix stripped) rather than the full
`https://nonsocynthia.github.io/...` form; `/docs` now shows a real Authorize button
(`fastapi.security.HTTPBearer` instead of a plain header parameter) and every endpoint has a
`summary`/`description`.

**Final state:** 388 tests, 97% coverage on `app/`, 14 acceptance criteria met against the running
system (11 original + 3 added in Phase 6), `ruff`/`mypy` clean. See
[`retrieval/README.md`](../../../retrieval/README.md) for the endpoint list and how to run it.

Completing this track resolves the blocker recorded against
[`explainable-agent-based-triage_20260828`](../explainable-agent-based-triage_20260828/index.md) — its
decisions.md now records ADR-002, and its agents should call this service's write endpoints rather
than writing to Postgres or the graph directly.

## Documents

- [Specification](./spec.md) — requirements and acceptance criteria
- [Plan](./plan.md) — six phases, TDD-structured
- [Metadata](./metadata.json)

## Phases

1. ADR-002 record + service scaffold
2. Fixture decision generator
3. Write endpoints — the ADR-002 projector
4. Read endpoints
5. Integration and acceptance pass
6. Evidence resolution (reopened) — citations resolved to real properties inline, IRIs shortened in
   every response, `/health` dependency-checked, `/docs` given real Authorize support and per-endpoint
   descriptions

## Project Context

- [Product Definition](../../product.md)
- [Tech Stack](../../tech-stack.md)
- [Workflow](../../workflow.md)
- [Retrieval service reference index](../../retrieval-service-references.md)
- [Retrieval/database onboarding briefing](../../retrieval-database-onboarding.md)
