# Track: Explainable Agent-Based Triage System — full build

**ID:** `explainable-agent-based-triage_20260828`
**Type:** feature
**Status:** pending
**Branch:** `feature/explainable-triage-system`

## Documents

- [Specification](./spec.md)
- [Implementation Plan](./plan.md)
- [Decisions](./decisions.md)
- [Metadata](./metadata.json)

## Summary

Builds the urgency agent, capacity agent, coordinating agent, rationale layer, clinician UI with
override loop, and CPC/CRT compliance validation on top of `graph-foundation_20260826`. Maps to
proposal §14 Days 3–6.

**2026-09-04:** ADR-002 (where agent outputs get written) is recorded in [decisions.md](./decisions.md)
— Postgres is the system of record, the graph gets a synchronous projection on commit. The write path
itself is implemented in `retrieval-service_20260904`, not in this track; agents built here call that
service rather than writing to Postgres or the graph directly.
