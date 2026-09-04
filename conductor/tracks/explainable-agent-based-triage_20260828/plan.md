# Plan: Explainable Agent-Based Triage System — full build

**Track:** `explainable-agent-based-triage_20260828`
**Workflow:** tiered TDD per `conductor/workflow.md`. Tier 1 = strict TDD, 80%. Tier 2 = tests
required, 60%. Tier 3 = smoke tests only. Depends on `graph-foundation_20260826` being seeded and
queryable.

**Per ADR-002** (`decisions.md`, accepted 2026-09-04): agents never write to Postgres or the graph
directly. `retrieval-service_20260904` is the single write path — `POST /scores`/`/decisions`/
`/overrides` write `agent.*` first, then synchronously project the matching triples into the graph on
success (never a separate batch mapping step). Every "write scored/Decision/cites edges" task below is
superseded by "call the retrieval service's write endpoint"; the graph projection is already handled by
that service, so no separate "project `agent.*` into the graph" task is needed here.

---

## Phase 1: Urgency Agent (Tier 1)

- [ ] Task: MTS scoring logic
    - [ ] Sub-task: Write failing tests for MTS category assignment, cited to the MTS rubric
    - [ ] Sub-task: Implement deterministic MTS scorer reading `UrgencySignal` via SPARQL
- [ ] Task: NEWS2 scoring logic
    - [ ] Sub-task: Write failing tests for NEWS2 score computation, cited to the NEWS2 rubric
    - [ ] Sub-task: Implement deterministic NEWS2 scorer
- [ ] Task: Write scores via retrieval-service_20260904 (Tier 2)
    - [ ] Sub-task: Round-trip test — score, `POST /scores`, read back via `GET /runs/{run_id}/
          hospitals/{hospital_hipe}/scores`, compare
    - [ ] Sub-task: Implement `triage.agents.urgency` calling `POST /scores` with its evidence
          citations (gather context first via `GET /referrals/{hospital_hipe}/{pathway_number}/
          context`, ADR-002)
- [ ] Task: Conductor - User Manual Verification 'Urgency Agent' (Protocol in workflow.md)

---

## Phase 2: Capacity Agent (Tier 1)

- [ ] Task: Constraint reasoning logic
    - [ ] Sub-task: Write failing tests for available-capacity and overcrowding-state scoring
    - [ ] Sub-task: Implement deterministic capacity scorer reading `BedStatus` via SPARQL
- [ ] Task: Write scores via retrieval-service_20260904 (Tier 2)
    - [ ] Sub-task: Round-trip test — score, `POST /scores`, read back via `GET /runs/{run_id}/
          hospitals/{hospital_hipe}/scores`, compare
    - [ ] Sub-task: Implement `triage.agents.capacity` calling `POST /scores` with its evidence
          citations (gather context first via `GET /referrals/{hospital_hipe}/{pathway_number}/
          context`, ADR-002)
- [ ] Task: Conductor - User Manual Verification 'Capacity Agent' (Protocol in workflow.md)

---

## Phase 3: Coordinating Agent and Audit Trail (Tier 1)

- [ ] Task: Ranking query and tie-breaking
    - [ ] Sub-task: Write failing tests for tie-break order (CPC, then CRT breach, then oldest-first)
    - [ ] Sub-task: Implement ranking logic over both agents' scores, gathered via
          `GET /hospitals/{hospital_hipe}/cohort/{as_of_date}` (which already includes CPC and
          computed `crt_breached`/`crt_threshold_days`, spec.md FR10) and
          `GET /runs/{run_id}/hospitals/{hospital_hipe}/scores`
- [ ] Task: CPC/CRT ordering constraint enforcement
    - [ ] Sub-task: Write failing tests asserting an urgent referral is never ranked behind an
          in-window semi-urgent one
    - [ ] Sub-task: Implement the enforcement check against the OWL constraint from `graph-foundation`,
          using the cohort endpoint's already-computed `crt_breached` rather than re-deriving it
- [ ] Task: Decision materialisation via retrieval-service_20260904 (Tier 2)
    - [ ] Sub-task: Write a test walking `decision_citations` back to its evidence rows via
          `GET /decisions/{hospital_hipe}/{as_of_date}` (evidence resolved inline, spec.md FR8)
    - [ ] Sub-task: Implement `triage.agents.coordinator` calling `POST /decisions` with rankings,
          citations, and rule checks in one call (ADR-002) — the graph projection (`eat:Decision`/
          `eat:RankedPlacement`/`eat:RuleCheck`/`eat:cites`) happens synchronously inside that call,
          no separate mapping step needed
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
