# Track: Knowledge Graph Foundation

**ID:** `graph-foundation_20260826`
**Type:** feature
**Status:** pending
**Created:** 2026-08-26

## Summary

The data and graph substrate every other component depends on: an OWL ontology formalising the triage
domain, a bootstrapped Oxigraph triple store, a synthetic patient and referral generator calibrated to
HIPE and NTPF statistics, and a SimPy bed occupancy simulation calibrated to HSE/INMO figures.

Maps to proposal §14 Days 1–2, plus the capacity agent's Day 3 input model. Completing this track
unblocks the urgency, capacity, and coordinator developers simultaneously.

## Documents

- [Specification](./spec.md) — requirements and acceptance criteria
- [Plan](./plan.md) — six phases, TDD-structured
- [Decisions](./decisions.md) — ADRs and carried-over open questions
- [Metadata](./metadata.json)

## Phases

1. Project Skeleton and Triple Store
2. OWL Ontology
3. Calibration Data
4. Synthetic Patient and Referral Generator
5. SimPy Bed Occupancy Simulation
6. Seeded Graph and Handoff

## Project Context

- [Product Definition](../../product.md)
- [Tech Stack](../../tech-stack.md)
- [Workflow](../../workflow.md)
