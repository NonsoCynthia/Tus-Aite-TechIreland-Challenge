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
   committed to. Largely answered by the delivered schema: `core.observations` carries `news2`,
   `mts_category` and `icts_category` already computed, alongside the raw components. Record the
   rationale as an ADR so the compliance lead can point at it.

3. **Where do agent outputs live — Postgres, the graph, or both?** Raised 2026-08-31 while
   reconciling this track against ADR-001. **Resolved 2026-09-04 as ADR-002** in
   `explainable-agent-based-triage_20260828/decisions.md` — Postgres is the write target, the graph
   projects it. Left below as the record of the options considered.

   Migration 006 already models the entire agent output surface in Postgres — `agent.agent_scores`,
   `agent_citations`, `decisions`, `decision_rankings`, `decision_citations`, `rule_checks` and
   `overrides` — with `agent_rw` holding INSERT on all of them, and `rule_checks` carrying a foreign
   key to `core.ref_rules`. The proposal (§9) says agents write scores back to the graph "as graph
   nodes and edges, not just as messages passed between agents, which is what keeps the trail
   auditable". ADR-001 settled the cohort data direction but is silent on outputs.

   Three options, none yet chosen:

   - **Postgres is the write target, graph projects it.** Consistent with ADR-001's one-source-of-record
     logic, and relational constraints do real work here — `dr_unique_position` makes two patients at
     the same rank impossible, `dc_role_valid` constrains why evidence was cited, and the FK to
     `ref_rules` means a violation cannot name a rule that does not exist. Costs the proposal's claim
     that the graph is where the audit trail lives; the graph becomes a query surface.
   - **Graph is the write target.** Matches the proposal and the pitch. Forfeits the constraints above
     unless they are reimplemented in SHACL or application code, and leaves `agent.*` an unused schema.
   - **Both, with one designated primary.** Most faithful to the demo narrative, most integration
     surface to maintain in a week, and creates a divergence risk between two audit trails — the exact
     failure ADR-001 argued against for cohort data.

   Whoever opens the specialist-agents track should decide this first and record it as ADR-002.

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
