# Plan: Explainable Agent-Based Triage System — full build

**Track:** `explainable-agent-based-triage_20260828`
**Workflow:** tiered TDD per `conductor/workflow.md`. Tier 1 = strict TDD, 80%. Tier 2 = tests
required, 60%. Tier 3 = smoke tests only. Depends on `graph-foundation_20260826` being seeded and
queryable.

---

## Phase 1: Urgency Agent (Tier 1)

- [ ] Task: MTS scoring logic
    - [ ] Sub-task: Write failing tests for MTS category assignment, cited to the MTS rubric
    - [ ] Sub-task: Implement deterministic MTS scorer reading `UrgencySignal` via SPARQL
- [ ] Task: NEWS2 scoring logic
    - [ ] Sub-task: Write failing tests for NEWS2 score computation, cited to the NEWS2 rubric
    - [ ] Sub-task: Implement deterministic NEWS2 scorer
- [ ] Task: Write scored edges to the graph (Tier 2)
    - [ ] Sub-task: Round-trip test — score, write, query back, compare
    - [ ] Sub-task: Implement `triage.agents.urgency` writing `scored` edges (Agent→Referral, score as edge property)
- [ ] Task: Conductor - User Manual Verification 'Urgency Agent' (Protocol in workflow.md)

---

## Phase 2: Capacity Agent (Tier 1)

- [ ] Task: Constraint reasoning logic
    - [ ] Sub-task: Write failing tests for available-capacity and overcrowding-state scoring
    - [ ] Sub-task: Implement deterministic capacity scorer reading `BedStatus` via SPARQL
- [ ] Task: Write scored edges to the graph (Tier 2)
    - [ ] Sub-task: Round-trip test — score, write, query back, compare
    - [ ] Sub-task: Implement `triage.agents.capacity`
- [ ] Task: Conductor - User Manual Verification 'Capacity Agent' (Protocol in workflow.md)

---

## Phase 3: Coordinating Agent and Audit Trail (Tier 1)

- [ ] Task: Ranking query and tie-breaking
    - [ ] Sub-task: Write failing tests for tie-break order (CPC, then CRT breach, then oldest-first)
    - [ ] Sub-task: Implement SPARQL ranking query over both agents' `scored` edges
- [ ] Task: CPC/CRT ordering constraint enforcement
    - [ ] Sub-task: Write failing tests asserting an urgent referral is never ranked behind an
          in-window semi-urgent one
    - [ ] Sub-task: Implement the enforcement check against the OWL constraint from `graph-foundation`
- [ ] Task: Decision and cites materialisation (Tier 2)
    - [ ] Sub-task: Write a test walking `cites` backward from a ranked position to its evidence nodes
    - [ ] Sub-task: Implement `triage.agents.coordinator` writing `Decision` nodes and `cites` edges
- [ ] Task: Conductor - User Manual Verification 'Coordinating Agent and Audit Trail' (Protocol in workflow.md)

---

## Phase 4: Rationale Layer

- [ ] Task: Evidence-faithfulness test (non-negotiable, Tier 1 rigor)
    - [ ] Sub-task: Write a failing test asserting every claim in generated rationale maps to a `cites` edge
    - [ ] Sub-task: Run against a fixed synthetic batch for reproducibility
- [ ] Task: Rationale generation (Tier 3, prompt wiring)
    - [ ] Sub-task: Implement `triage.rationale` calling `claude-opus-5` with only cited evidence in the prompt
    - [ ] Sub-task: Prompt caching on stable system prompt + ontology description
    - [ ] Sub-task: Message Batches API path for bulk validation runs
- [ ] Task: Conductor - User Manual Verification 'Rationale Layer' (Protocol in workflow.md)

---

## Phase 5: Clinician UI and Override Loop (Tier 3, smoke-tested)

- [ ] Task: Ranked list view
    - [ ] Sub-task: FastAPI route + Jinja2 template rendering rank, rationale, cited evidence
    - [ ] Sub-task: Smoke test — route renders, no 500
- [ ] Task: Accept / reorder / override controls
    - [ ] Sub-task: HTMX-driven controls calling FastAPI endpoints
    - [ ] Sub-task: Smoke test per endpoint
- [ ] Task: Override write-back (Tier 2)
    - [ ] Sub-task: Round-trip test — override, write to graph, reload, confirm persisted
    - [ ] Sub-task: Implement write-back so future rankings can account for the correction
- [ ] Task: Conductor - User Manual Verification 'Clinician UI and Override Loop' (Protocol in workflow.md)

---

## Phase 6: CPC/CRT Compliance Validation and Hardening (Tier 1)

- [ ] Task: Batch rule-check suite
    - [ ] Sub-task: Write failing tests for known violation and known-clean scenarios
    - [ ] Sub-task: Implement the CI-run validation suite across the synthetic cohort
- [ ] Task: Responsible-AI boundary documentation
    - [ ] Sub-task: Document that the coordinator may only rank/explain — no admit, discharge, schedule,
          auto-action
    - [ ] Sub-task: Compliance lead sign-off recorded in `decisions.md`
- [ ] Task: End-to-end demo path
    - [ ] Sub-task: `docker compose up` → seeded graph → agents run → UI shows ranked list → override
          round-trips, documented as a single runnable sequence
- [ ] Task: Verify acceptance criteria
    - [ ] Sub-task: Walk all 8 acceptance criteria in spec.md and record the result of each
- [ ] Task: Conductor - User Manual Verification 'CPC/CRT Compliance Validation and Hardening' (Protocol in workflow.md)
