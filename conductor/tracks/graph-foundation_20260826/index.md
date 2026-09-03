# Track: Knowledge Graph Foundation

**ID:** `graph-foundation_20260826`
**Type:** feature
**Status:** done
**Created:** 2026-08-26
**Completed:** 2026-09-03 (merged to `main` in [PR #2](https://github.com/NonsoCynthia/Tus-Aite-TechIreland-Challenge/pull/2))

## Summary

The graph substrate every other component depends on: an OWL ontology formalising the triage domain
as the `dataset/` schema models it, a bootstrapped Oxigraph triple store, a Postgres database loaded
at a pinned version, and a projection layer emitting RDF from `core.*`.

Maps to proposal §14 Days 1–2. Completing this track unblocks the urgency, capacity, and coordinator
developers simultaneously.

**Revised 2026-08-31** against [ADR-001](./decisions.md): the cohort generator and bed simulation
originally planned here are delivered by the `dataset/` pipeline. Postgres is the source of record;
the graph is a derived projection.

**Delivered 2026-09-03.** The projection layer shipped as five declarative R2RML mapping files run
through Morph-KGC, not the custom Python projection framework Phase 3 of `plan.md` originally
scoped — see [kg/README.md](../../../kg/README.md) for what actually exists: **590,814 triples**
across the input and reference graphs, 19 SHACL shapes, the shared wait-counter SPARQL fragment, and
a `kg_loader` role with no grant on `eval`. The normative spec, namespaces, decisions and ontology
docs live in [`conductor/kg/`](../../kg/). `plan.md`'s phase checklist is kept as a historical record
of what was scoped, not a checklist of what shipped — the two diverged once Morph-KGC replaced the
planned Python client.

One item from Phase 4 remains genuinely open, not just superseded: **ADR-002**, where agent outputs
(scores, citations, rankings) get written — Postgres `agent.*`, the graph, or both. This blocks
`explainable-agent-based-triage_20260828` and should be the first thing that track resolves. See
[decisions.md](./decisions.md) and `spec.md`'s "Unresolved" section.

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
