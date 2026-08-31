# Track: Knowledge Graph Foundation

**ID:** `graph-foundation_20260826`
**Type:** feature
**Status:** pending
**Created:** 2026-08-26

## Summary

The graph substrate every other component depends on: an OWL ontology formalising the triage domain
as the `dataset/` schema models it, a bootstrapped Oxigraph triple store, a Postgres database loaded
at a pinned version, and a projection layer emitting RDF from `core.*`.

Maps to proposal §14 Days 1–2. Completing this track unblocks the urgency, capacity, and coordinator
developers simultaneously.

**Revised 2026-08-31** against [ADR-001](./decisions.md): the cohort generator and bed simulation
originally planned here are delivered by the `dataset/` pipeline. Postgres is the source of record;
the graph is a derived projection.

## Documents

- [Specification](./spec.md) — requirements and acceptance criteria
- [Plan](./plan.md) — six phases, TDD-structured
- [Decisions](./decisions.md) — ADRs and carried-over open questions
- [Metadata](./metadata.json)

## Phases

1. Project Skeleton, Triple Store, and Dataset Load
2. OWL Ontology
3. Projection From Postgres to RDF
4. Seeded Graph and Handoff

Three original phases — calibration data, the synthetic generator, and the SimPy bed simulation — are
closed as delivered by `dataset/`. See `plan.md` for the mapping and the tests that cover them.

## Project Context

- [Product Definition](../../product.md)
- [Tech Stack](../../tech-stack.md)
- [Workflow](../../workflow.md)
