# Decisions: Knowledge Graph Foundation

> Architecture Decision Records for this track. One entry per decision that a future reader would
> otherwise have to reverse-engineer from the code.

## Template

### ADR-NNN: [Title]

**Date:** YYYY-MM-DD
**Status:** proposed | accepted | superseded by ADR-NNN

**Context:** What forced a decision.

**Decision:** What was decided.

**Consequences:** What this makes easier, and what it makes harder.

---

## Open Questions Carried From the Proposal

Two annotations in the source proposal are unresolved and should be closed out during this track:

1. **What exactly constitutes a "referral" record?** (proposal §6, marginal note) — the generator
   cannot be built without a settled field list. Resolve in Phase 3 and record as an ADR.
2. **How is urgency ascertained — does medical science have a way to measure urgency signals of
   emergencies?** (proposal §6, marginal note) — MTS and NEWS2 are the answer the project has already
   committed to. Record the rationale as an ADR so the compliance lead can point at it.

---

### ADR-001: The graph is projected from Postgres, not independently generated

**Date:** 2026-08-31
**Status:** accepted

**Context:** This track was planned on 2026-08-26, before the `dataset/` pipeline was merged into
`main` and from there into the feature branches. That pipeline delivers, in Postgres, the substance of
three of this track's six phases:

| Planned here | Already delivered by `dataset/` |
|---|---|
| Phase 3 — HIPE/NTPF calibration config | `dataset/generator/calibration/` |
| Phase 4 — synthetic patient and referral generator | `core.patients`, `core.referrals`, `core.conditions`, `core.observations` |
| Phase 5 — SimPy bed occupancy simulation | `core.bed_status`, `core.wards`, `core.ward_specialty` |

Building the planned generator and simulation anyway would produce a second synthetic cohort
alongside the published one. `dataset/docs/GETTING_THE_DATA.md` §7 argues the case against exactly
that: two people silently holding different data is harder to notice than a failed download, and much
worse when someone presents a result from it. The same argument applies to two cohorts inside one
repository.

**Decision:** Postgres is the source of record. Oxigraph holds a **derived projection** of it. A new
projection layer reads `core.*` and emits RDF conforming to the OWL ontology; nothing in this track
generates cohort data of its own.

Phases 3, 4 and 5 are closed as delivered by `dataset/`. Phases 1, 2 and 6 stand as written. The
projection layer is new work the original plan has no phase for, because the plan assumed the
generator would write triples directly.

**Consequences:**

Easier: one cohort and one set of numbers, so a figure in the UI can be traced to a row in Postgres.
The dataset's determinism and referential-closure guarantees are inherited rather than reimplemented.
The `eval.ground_truth` role barrier from migration 007 keeps holding, because the projection reads
through a role that cannot see that schema — a second generator would have had to re-earn that
guarantee.

Harder: the graph is now downstream of a load step, so a teammate needs Hugging Face access and a
loaded database before they can seed a graph. That lengthens the clone-to-seeded-graph path that NFR1
caps at five minutes, and the projection has to be measured against that cap rather than assumed
inside it. Schema migrations in `dataset/db/migrations/` become upstream of the ontology, so a column
change can now break the projection; `versions.yml` pins the schema version the projection targets.

Acceptance criteria 3, 4 and 5 in `spec.md` refer to the generator and simulation this ADR removes.
They are satisfied by the dataset's own suites (`dataset/tests/test_determinism.py`,
`test_plausibility.py`) rather than by tests written here, and should be read that way when the track
is walked for acceptance.
