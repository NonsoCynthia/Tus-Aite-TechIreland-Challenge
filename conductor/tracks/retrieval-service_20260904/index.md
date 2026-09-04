# Track: Retrieval Service

**ID:** `retrieval-service_20260904`
**Type:** feature
**Status:** new
**Created:** 2026-09-04

## Summary

A standalone FastAPI retrieval service, its own container on the docker-compose network alongside
`db` (Postgres) and `oxigraph`, mediating every read and write between Postgres `core`/`agent` and the
Oxigraph knowledge graph for the not-yet-built urgency/capacity/coordinator agents and the clinician
UI. This is the concrete implementation of **ADR-002** (confirmed 2026-09-04): Postgres is the system
of record; the graph gets a synchronous, single-writer projection on successful Postgres commit. The
service's port is published to the host and every endpoint requires bearer-token auth.

Building this track resolves the blocker recorded against
[`explainable-agent-based-triage_20260828`](../explainable-agent-based-triage_20260828/index.md).

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

## Project Context

- [Product Definition](../../product.md)
- [Tech Stack](../../tech-stack.md)
- [Workflow](../../workflow.md)
- [Retrieval service reference index](../../retrieval-service-references.md)
- [Retrieval/database onboarding briefing](../../retrieval-database-onboarding.md)
