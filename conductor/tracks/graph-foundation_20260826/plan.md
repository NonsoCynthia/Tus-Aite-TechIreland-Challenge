# Plan: Knowledge Graph Foundation

**Track:** `graph-foundation_20260826`
**Workflow:** tiered TDD per `conductor/workflow.md`. Tier 1 = strict TDD, 80%. Tier 2 = tests
required, 60%. Tier 3 = smoke tests only.
**Revised:** 2026-08-31 against [ADR-001](./decisions.md).

## Phases Closed by ADR-001

The original plan had six phases. Three are closed as delivered by the `dataset/` pipeline and are
retained here as a record, not as work:

| Original phase | Delivered by | Verified by |
|---|---|---|
| ~~Phase 3 — Calibration Data~~ | `dataset/generator/calibration/` | `dataset/tests/test_plausibility.py` |
| ~~Phase 4 — Synthetic Patient and Referral Generator~~ | `dataset/generator/generate.py`, `core.patients` / `referrals` / `conditions` / `observations` | `dataset/tests/test_determinism.py`, `test_referential.py` |
| ~~Phase 5 — SimPy Bed Occupancy Simulation~~ | `core.wards`, `ward_specialty`, `bed_status` | `dataset/tests/test_plausibility.py` |

Do not reopen these. Building a second cohort alongside the published one is the specific failure
ADR-001 exists to prevent.

---

## Phase 1: Project Skeleton, Triple Store, and Dataset Load

- [ ] Task: Scaffold the Python project
    - [ ] Sub-task: `pyproject.toml` with `uv`, Python 3.12, package `triage`
    - [ ] Sub-task: Add `rdflib`, `httpx`, `psycopg[binary]`, `pydantic`, `pyyaml`, `fastapi`, `uvicorn`, `jinja2`, `anthropic`
    - [ ] Sub-task: Dev deps `pytest`, `pytest-cov`, `ruff`, `mypy`; commit the lockfile
    - [ ] Sub-task: Configure `ruff`, `mypy`, and per-tier coverage thresholds
    - [ ] Sub-task: Confirm no dependency overlap conflicts with `dataset/requirements.txt`
- [ ] Task: Load Postgres at the pinned version (Tier 2 — test first)
    - [ ] Sub-task: Write a failing test asserting the loaded schema version is `008` and data version `v1.1`
    - [ ] Sub-task: Follow `dataset/docs/GETTING_THE_DATA.md` to obtain Hugging Face access
    - [ ] Sub-task: Load via `dataset/`'s existing Makefile targets — do not reimplement fetch or load
    - [ ] Sub-task: Read the pin from `dataset/versions.yml` at runtime rather than duplicating the values
    - [ ] Sub-task: Run `dataset/tests/test_schema.py` and `test_referential.py` against the loaded database
- [ ] Task: Stand up Oxigraph
    - [ ] Sub-task: Add the `oxigraph/oxigraph` service with a persistent volume, port 7878
    - [ ] Sub-task: Resolve the container-name clash noted in `dataset/docs/` before it bites two people
    - [ ] Sub-task: Verify the SPARQL endpoint answers `SELECT (1 AS ?x) {}`
- [ ] Task: Graph client (Tier 2 — test first)
    - [ ] Sub-task: Write failing tests for `query()` and `update()` against a live container
    - [ ] Sub-task: Implement `triage.graph.client` reading `OXIGRAPH_QUERY_URL` / `OXIGRAPH_UPDATE_URL`
    - [ ] Sub-task: Add a pytest fixture resetting the store between tests
- [ ] Task: Postgres client bound to the role barrier (Tier 1 — strict TDD)
    - [ ] Sub-task: Write a failing test asserting the connection **cannot** read `eval.ground_truth`
    - [ ] Sub-task: Implement a read-only connection running as `agent_rw`
- [ ] Task: CI pipeline
    - [ ] Sub-task: GitHub Actions with both Postgres and Oxigraph service containers
    - [ ] Sub-task: Cache the dataset sample so CI does not re-download on every run
- [ ] Task: Conductor - User Manual Verification 'Project Skeleton, Triple Store, and Dataset Load' (Protocol in workflow.md)

---

## Phase 2: OWL Ontology

- [ ] Task: Define the namespace and vocabulary reuse
    - [ ] Sub-task: Choose and document a base IRI
    - [ ] Sub-task: Map `Condition` to SNOMED CT; patient/encounter structure to HL7 FHIR RDF
    - [ ] Sub-task: Record the mapping decisions in `decisions.md`
- [ ] Task: IRI minting (Tier 1 — strict TDD)
    - [ ] Sub-task: Write failing tests asserting an IRI is reversible to its `(hospital_hipe, pathway_number)` pair
    - [ ] Sub-task: Implement one documented minting function; assert every projector uses it
    - [ ] Sub-task: Cover the composite keys — observations key on `obs_datetime`, bed status on `(ward_id, snapshot_datetime)`
- [ ] Task: Declare entity classes matching the delivered schema
    - [ ] Sub-task: `Patient`, `Referral`, `TriageEvent`, `Condition`, `Observation`
    - [ ] Sub-task: `Specialty`, `Hospital`, `Ward`, `BedStatus`
    - [ ] Sub-task: `Rule`, `Agent`, `Decision`, `Clinician`
    - [ ] Sub-task: Model CPC as `triage_category` on `TriageEvent`, **not** as a standalone class — a referral awaiting triage has no category
    - [ ] Sub-task: Model triage status as a state, so `awaiting_triage` is rankable rather than missing
- [ ] Task: Declare relationships (Tier 2 — test first)
    - [ ] Sub-task: Write failing tests asserting each property's domain and range
    - [ ] Sub-task: `presentsWith`, `hasObservation`, `hasTriageEvent`, `assignedTo`
    - [ ] Sub-task: `locatedAt`, `servesSpecialty`, `hasStatus`
    - [ ] Sub-task: `scored`, with the score as an **edge property**, not a bare literal node
    - [ ] Sub-task: `ranks` and `cites` — model `cites` before anything writes to it
- [ ] Task: Declare bed pressure measures faithfully (Tier 2)
    - [ ] Sub-task: Expose `outliers`, `surge_capacity_in_use`, `delayed_transfers_of_care`, `awaiting_admission_over_9h` / `_over_24h`, `gar_status`
    - [ ] Sub-task: Document that `occupancy_pct` is capped at 100 by `bs_occupancy_range`, so overcrowding is expressed through these measures and never as occupancy >100%
- [ ] Task: Declare CRT rules as individuals (Tier 2 — test first)
    - [ ] Sub-task: Write a failing test asserting every `rule_id` in `core.ref_rules` has a matching `Rule` individual
    - [ ] Sub-task: Mint `RULE-CRT-URGENT` (28d), `RULE-CRT-SEMI` (91d), `RULE-TRIAGE-TURNAROUND` (21d), `RULE-ORDER`, `RULE-TIEBREAK`
    - [ ] Sub-task: Express the ordering constraint against `adjusted_wait_days`, never raw date arithmetic
    - [ ] Sub-task: Document that the constraint is declared here and enforced in a later track
- [ ] Task: Idempotent ontology loader (Tier 2 — test first)
    - [ ] Sub-task: Write a failing test asserting loading twice yields no duplicate triples
    - [ ] Sub-task: Implement `triage.graph.bootstrap`
- [ ] Task: Conductor - User Manual Verification 'OWL Ontology' (Protocol in workflow.md)

---

## Phase 3: Projection From Postgres to RDF

> New work. ADR-001 removed the generator this plan originally assumed would write triples directly,
> and the graph now needs a projection layer instead.

- [ ] Task: Projection framework (Tier 1 — strict TDD)
    - [ ] Sub-task: Write failing tests for a table-to-triples contract covering one simple table
    - [ ] Sub-task: Implement batched SPARQL Update writes
    - [ ] Sub-task: Assert idempotence — projecting twice yields identical triples
- [ ] Task: Project reference and structural tables (Tier 2 — test first)
    - [ ] Sub-task: `ref_specialty`, `ref_rules`, `hospitals`, `hospital_specialty`
    - [ ] Sub-task: `wards`, `ward_specialty`
- [ ] Task: Project the patient and referral core (Tier 1 — strict TDD)
    - [ ] Sub-task: Write failing round-trip tests — project, query back, compare to source columns
    - [ ] Sub-task: `patients`, `referrals`, `conditions`
    - [ ] Sub-task: `triage_events` with `triage_category` and `triage_outcome`
- [ ] Task: Project observations (Tier 1 — strict TDD)
    - [ ] Sub-task: Write failing tests covering nullable vitals — absent is not zero
    - [ ] Sub-task: Project raw components and the precomputed `news2`, `mts_category`, `icts_category`
    - [ ] Sub-task: Assert `obs_one_scale_only` survives projection — MTS and ICTS never both present
- [ ] Task: Decide and implement `referral_daily` snapshot handling (Tier 1 — strict TDD)
    - [ ] Sub-task: Decide whether to pin one `as_of_date` or model the full series; record as an ADR
    - [ ] Sub-task: Write a failing test asserting `adjusted_wait_days` survives projection exactly
    - [ ] Sub-task: Assert `adjusted_wait_days <= days_since_received` still holds in the graph
- [ ] Task: Project bed status (Tier 1 — strict TDD)
    - [ ] Sub-task: Write failing tests for the trolley and surge measures
    - [ ] Sub-task: Assert wards under real pressure — `gar_status = 'R'`, surge in use, or 24h waits — are present and reachable
- [ ] Task: Provenance stamping (Tier 2 — test first)
    - [ ] Sub-task: Write a failing test asserting every projected node carries synthetic provenance
    - [ ] Sub-task: Stamp `data_version` and `schema_version` read from `dataset/versions.yml`
- [ ] Task: Measure the projection against NFR2
    - [ ] Sub-task: Assert the `sample` profile projects in under 60 seconds
- [ ] Task: Conductor - User Manual Verification 'Projection From Postgres to RDF' (Protocol in workflow.md)

---

## Phase 4: Seeded Graph and Handoff

- [ ] Task: Single-command seed path (Tier 3)
    - [ ] Sub-task: One command from a loaded database to a fully seeded graph
    - [ ] Sub-task: Measure clone-to-seeded-graph end to end and assert the fifteen-minute NFR1 cap
    - [ ] Sub-task: If the cap is breached, record the actual figure and raise it with the team rather than quietly relaxing it
- [ ] Task: Documented SPARQL examples for downstream developers
    - [ ] Sub-task: Referral with conditions, observations, triage category, and `adjusted_wait_days`
    - [ ] Sub-task: Current bed status for a ward serving a specialty, including trolley and surge measures
    - [ ] Sub-task: Walk `cites` backward from a `Decision` — proves the audit path before anything writes to it
    - [ ] Sub-task: Referrals in `awaiting_triage` with no triage event — the state the ontology must not lose
- [ ] Task: README handoff section
    - [ ] Sub-task: Clone-to-seeded-graph instructions a teammate can follow unaided
    - [ ] Sub-task: Hugging Face access steps, pointing at `dataset/docs/GETTING_THE_DATA.md` rather than restating it
    - [ ] Sub-task: Note the Oxigraph→Fuseki swap path from `tech-stack.md`
    - [ ] Sub-task: State the version pin and that schema 008 with data v1.0 will not load
- [ ] Task: Verify acceptance criteria
    - [ ] Sub-task: Walk all twelve acceptance criteria in `spec.md`, recording the result of each
    - [ ] Sub-task: Confirm the `agent_rw` role barrier holds — the projection cannot read `eval.ground_truth`
    - [ ] Sub-task: Compliance lead confirms no real data or PII is present
- [ ] Task: Resolve the open question blocking the next track
    - [ ] Sub-task: Decide whether agents write scores to Postgres `agent.*`, to the graph, or both
    - [ ] Sub-task: Record as an ADR before the specialist-agents track opens
- [ ] Task: Conductor - User Manual Verification 'Seeded Graph and Handoff' (Protocol in workflow.md)
