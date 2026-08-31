# Plan: Knowledge Graph Foundation

**Track:** `graph-foundation_20260826`
**Workflow:** tiered TDD per `conductor/workflow.md`. Tier 1 = strict TDD, 80%. Tier 2 = tests
required, 60%. Tier 3 = smoke tests only.

---

## Phase 1: Project Skeleton and Triple Store

- [ ] Task: Scaffold the Python project
    - [ ] Sub-task: `pyproject.toml` with `uv`, Python 3.12, package `triage`
    - [ ] Sub-task: Add `rdflib`, `httpx`, `simpy`, `pandas`, `numpy`, `pydantic`, `fastapi`, `uvicorn`, `jinja2`, `anthropic`
    - [ ] Sub-task: Dev deps `pytest`, `pytest-cov`, `ruff`, `mypy`; commit the lockfile
    - [ ] Sub-task: Configure `ruff` and `mypy`; configure per-tier coverage thresholds in `pyproject.toml`
- [ ] Task: Stand up Oxigraph
    - [ ] Sub-task: `docker-compose.yml` with `oxigraph/oxigraph`, persistent volume, port 7878
    - [ ] Sub-task: Verify the SPARQL endpoint answers `SELECT (1 AS ?x) {}`
- [ ] Task: Graph client (Tier 2 — test first)
    - [ ] Sub-task: Write failing tests for `query()` and `update()` against a live container
    - [ ] Sub-task: Implement `triage.graph.client` reading `OXIGRAPH_QUERY_URL` / `OXIGRAPH_UPDATE_URL`
    - [ ] Sub-task: Add a pytest fixture that resets the store between tests
- [ ] Task: CI pipeline
    - [ ] Sub-task: GitHub Actions running ruff, mypy, pytest with an Oxigraph service container
- [ ] Task: Conductor - User Manual Verification 'Project Skeleton and Triple Store' (Protocol in workflow.md)

---

## Phase 2: OWL Ontology

- [ ] Task: Define the ontology namespace and vocabulary reuse
    - [ ] Sub-task: Choose and document a base IRI for the project ontology
    - [ ] Sub-task: Map `Condition` to SNOMED CT; map patient/encounter structure to HL7 FHIR RDF
    - [ ] Sub-task: Record the mapping decisions in `decisions.md`
- [ ] Task: Declare entity classes
    - [ ] Sub-task: `Patient`, `Referral`, `Condition`, `UrgencySignal`, `ClinicalPrioritisationCategory`
    - [ ] Sub-task: `Specialty`, `Hospital`, `Ward`, `BedStatus`
    - [ ] Sub-task: `Agent`, `Decision`, `Clinician`
- [ ] Task: Declare relationships (Tier 2 — test first)
    - [ ] Sub-task: Write failing tests asserting each property's domain and range
    - [ ] Sub-task: `presentsWith`, `hasSignal`, `assignedTo`, `locatedAt`, `hasStatus`
    - [ ] Sub-task: `scored` with the score as an **edge property**, not a bare literal node
    - [ ] Sub-task: `ranks` and `cites` — `cites` is the audit trail, so model it before anything writes to it
- [ ] Task: Declare the CPC/CRT ordering constraint in OWL
    - [ ] Sub-task: Express that a `Decision` citing an urgent `Referral` cannot rank it behind a semi-urgent `Referral` still inside its CRT
    - [ ] Sub-task: Document that declaration here, enforcement in a later track
- [ ] Task: Idempotent bootstrap loader (Tier 2 — test first)
    - [ ] Sub-task: Write a failing test asserting that loading twice yields no duplicate triples
    - [ ] Sub-task: Implement `triage.graph.bootstrap`
- [ ] Task: Conductor - User Manual Verification 'OWL Ontology' (Protocol in workflow.md)

---

## Phase 3: Calibration Data

- [ ] Task: Assemble HIPE-derived calibration config
    - [ ] Sub-task: Extract published specialty mix, age/sex distribution, length-of-stay statistics
    - [ ] Sub-task: Store as committed, inspectable config (not hardcoded constants)
    - [ ] Sub-task: Cite the source and retrieval date for each figure in the config file
- [ ] Task: Assemble NTPF-derived list structure config
    - [ ] Sub-task: Waiting list volumes by specialty and time band
    - [ ] Sub-task: CPC definitions with CRT windows — urgent ≤28 days, semi-urgent ≤13 weeks
- [ ] Task: Assemble HSE/INMO occupancy calibration config
    - [ ] Sub-task: Daily trolley and occupancy figures for the bed simulation
    - [ ] Sub-task: Define an explicit sustained-overcrowding scenario
- [ ] Task: Validate configs on load (Tier 1 — strict TDD)
    - [ ] Sub-task: Write failing tests for malformed and out-of-range config
    - [ ] Sub-task: Pydantic models that reject distributions not summing to 1 and negative windows
- [ ] Task: Conductor - User Manual Verification 'Calibration Data' (Protocol in workflow.md)

---

## Phase 4: Synthetic Patient and Referral Generator

- [ ] Task: Deterministic seeding (Tier 1 — strict TDD)
    - [ ] Sub-task: Write a failing test asserting identical output for identical seed
    - [ ] Sub-task: Implement explicit seed threading; no reliance on global RNG state
- [ ] Task: Patient generation (Tier 2 — test first)
    - [ ] Sub-task: Age and sex drawn from the HIPE distribution
    - [ ] Sub-task: Conditions drawn with ICD-10-AM codes
    - [ ] Sub-task: Every node tagged synthetic via a graph predicate
- [ ] Task: Referral generation (Tier 1 — strict TDD)
    - [ ] Sub-task: Write failing tests for CPC assignment and referral-date distribution
    - [ ] Sub-task: Assign CPC, referral date, and specialty
    - [ ] Sub-task: Generate urgency signals sufficient to compute both MTS and NEWS2 downstream
    - [ ] Sub-task: Ensure some referrals breach their CRT — the interesting case must be reachable
- [ ] Task: Calibration fidelity test (Tier 1 — strict TDD)
    - [ ] Sub-task: Assert a generated cohort's specialty mix matches config within a documented tolerance
    - [ ] Sub-task: Document why that tolerance was chosen
- [ ] Task: Write generated cohort to the graph (Tier 2)
    - [ ] Sub-task: Batch SPARQL Update writes
    - [ ] Sub-task: Assert 1,000 referrals generate and load in under 60 seconds
- [ ] Task: Conductor - User Manual Verification 'Synthetic Patient and Referral Generator' (Protocol in workflow.md)

---

## Phase 5: SimPy Bed Occupancy Simulation

- [ ] Task: Model arrivals and length of stay (Tier 1 — strict TDD)
    - [ ] Sub-task: Write failing tests for arrival rate and length-of-stay distributions
    - [ ] Sub-task: Implement the SimPy process for arrival, admission, stay, discharge
- [ ] Task: Ward and bed resources (Tier 1 — strict TDD)
    - [ ] Sub-task: Write failing tests for occupancy accounting including >100% (trolley) conditions
    - [ ] Sub-task: Model wards as constrained resources per specialty
- [ ] Task: Calibrate to HSE/INMO figures (Tier 1 — strict TDD)
    - [ ] Sub-task: Assert simulated occupancy tracks published figures within tolerance
    - [ ] Sub-task: Assert the overcrowding scenario sustains >100% occupancy
- [ ] Task: Emit BedStatus into the graph (Tier 2)
    - [ ] Sub-task: Write a `BedStatus` time series per `Ward` via `hasStatus`
    - [ ] Sub-task: Round-trip test — simulate, write, query back, compare
- [ ] Task: Conductor - User Manual Verification 'SimPy Bed Occupancy Simulation' (Protocol in workflow.md)

---

## Phase 6: Seeded Graph and Handoff

- [ ] Task: Single-command seed path (Tier 3)
    - [ ] Sub-task: One command from clean checkout to fully seeded graph
    - [ ] Sub-task: Assert the whole path completes in under five minutes
- [ ] Task: Documented SPARQL examples for downstream developers
    - [ ] Sub-task: Query returning a referral with conditions, urgency signals, CPC, referral date
    - [ ] Sub-task: Query returning current bed status for a specialty's ward
    - [ ] Sub-task: Query walking `cites` backward — proves the audit path before anything writes to it
- [ ] Task: README handoff section
    - [ ] Sub-task: Clone-to-seeded-graph instructions a teammate can follow unaided
    - [ ] Sub-task: Note the Oxigraph→Fuseki swap path from tech-stack.md
- [ ] Task: Verify acceptance criteria
    - [ ] Sub-task: Walk all ten acceptance criteria in `spec.md` and record the result of each
    - [ ] Sub-task: Compliance lead confirms no real data or PII is present
- [ ] Task: Conductor - User Manual Verification 'Seeded Graph and Handoff' (Protocol in workflow.md)
