# Tus-Aite-TechIreland-Challenge

Explainable, agent-based triage support for Irish hospital patient flow, built for the
TechIreland National AI Challenge 2026.

The project turns fragmented referral, urgency, and bed-capacity data into a ranked, evidence-backed
shortlist that a clinician can inspect, accept, reorder, or override. The system does not admit,
schedule, diagnose, or make final clinical decisions. It provides auditable decision support.

## Working with the dataset

The synthetic dataset described in feature 1 below is built, tested and published from
[`dataset/`](dataset/). It lives on Hugging Face as a tagged release and is pulled in by
`make load`.

```bash
cd dataset
cp .env.example .env      # add your Hugging Face token
make up                   # Postgres and pgAdmin
make load                 # download and load
```

Start with [dataset/docs/GETTING_THE_DATA.md](dataset/docs/GETTING_THE_DATA.md).

---

## Product Features

### 1. Synthetic Irish Patient and Referral Dataset

- Generates synthetic patients, referrals, conditions, specialties, referral dates, and urgency
  signals.
- Calibrates case mix against Irish healthcare structures, including HIPE specialty, age, sex, and
  length-of-stay statistics.
- Calibrates list volumes and waiting-time bands against NTPF Open Data.
- Labels every generated record as synthetic in the graph and the UI.
- Uses seeded random generation so the same seed produces the same cohort for testing and demos.

Implementation tools: Python 3.12, Pydantic v2, pandas, numpy, rdflib.

### 2. Bed Occupancy and Patient Flow Simulation

- Simulates arrivals, admissions, ward capacity, length of stay, discharge, and overcrowding.
- Models ward-level `BedStatus` time series for use by the capacity agent.
- Includes sustained-overcrowding scenarios where occupancy can exceed 100 percent.
- Calibrates stress scenarios against HSE and INMO trolley/occupancy figures.

Implementation tools: SimPy, Python 3.12, pandas, numpy.

### 3. Knowledge Graph and Audit Trail

- Uses an RDF/OWL knowledge graph as both the data layer and the explainability layer.
- Represents `Patient`, `Referral`, `Condition`, `UrgencySignal`, `ClinicalPrioritisationCategory`,
  `Specialty`, `Hospital`, `Ward`, `BedStatus`, `Agent`, `Decision`, `Clinician`, and override events.
- Stores relationships such as `hasSignal`, `assignedTo`, `locatedAt`, `hasStatus`, `scored`,
  `ranks`, and `cites`.
- Makes `cites` the audit trail: walking backwards from a ranked decision reveals the exact evidence
  behind it.
- Declares CPC/CRT ordering constraints in the ontology.

Implementation tools: Oxigraph, Docker Compose, RDF, OWL, SPARQL 1.1, rdflib, httpx.

### 4. Urgency Agent

- Reads referrals, conditions, vitals, and urgency signals from the graph.
- Applies deterministic Manchester Triage System and NEWS2 scoring logic.
- Writes urgency scores back as graph evidence.
- Keeps scoring reproducible and unit-testable.

Implementation tools: Python 3.12, SPARQL, Pydantic, pytest.

### 5. Capacity Agent

- Reads specialty, ward, and bed-status data from the graph.
- Reasons over bed pressure, resource contention, and expected availability.
- Writes capacity scores and cited capacity evidence back to the graph.

Implementation tools: Python 3.12, SimPy outputs, SPARQL, pytest.

### 6. Coordinating Agent

- Combines urgency-agent and capacity-agent outputs into a ranked list.
- Uses deterministic tie-breaking based on CPC, CRT breach status, and referral age.
- Materialises `Decision` nodes and `cites` relationships in the graph.
- Produces rankings that can be reconstructed from graph evidence.

Implementation tools: Python 3.12, SPARQL over Oxigraph, rdflib/httpx.

### 7. Explainable Rationale Generation

- Generates short, clinician-readable rationales for each ranked referral.
- Uses only evidence already cited in the graph.
- Names the exact urgency signals, capacity constraints, CPC category, and CRT status.
- Prevents the language model from changing scores, changing rank, or introducing unsupported facts.

Implementation tools: Anthropic Python SDK, `claude-opus-5`, prompt caching, Message Batches API for
bulk validation runs.

### 8. Clinician Interface

- Shows the ranked referral list as the main product surface.
- Allows clinicians to expand each row and inspect the cited evidence.
- Provides visible accept, reorder, and override controls.
- Logs every clinician action back into the graph.
- Shows CPC/CRT rule violations prominently.
- Provides JSON API endpoints alongside the server-rendered UI.

Implementation tools: FastAPI, Jinja2, HTMX, Uvicorn, HTML, CSS.

### 9. Frontend Aesthetics and Interaction Design

- Clinical, calm, and high-contrast interface designed for fast scanning.
- Dense ranked-list layout rather than a marketing-style dashboard.
- White and light-grey clinical base with restrained use of blue for structure, amber/red for rule
  warnings, and labelled MTS category colours.
- No urgency is communicated by colour alone; every colour signal has text beside it.
- Evidence appears one interaction away through row expansion, not on a separate page.
- Override controls are always visible and treated as first-class clinician judgement, not errors.
- UI copy avoids diagnostic claims and avoids implying the system has acted on a patient.
- Designed for WCAG 2.2 AA contrast and keyboard operation.

### 10. CPC/CRT Compliance Validation

- Checks rankings against NTPF Clinical Prioritisation Category rules.
- Flags urgent referrals outside the 28-day Clinically Recommended Timeframe.
- Flags semi-urgent referrals outside the 13-week Clinically Recommended Timeframe.
- Validates same-category ordering by oldest referral first.
- Produces evidence-backed rule-violation output for review.

Implementation tools: Python 3.12, pytest, SPARQL queries, CI validation suite.

### 11. Developer Workflow and Quality Gates

- Uses `uv` for dependency management and a committed lockfile.
- Uses Docker Compose for local Oxigraph and app services.
- Uses pytest, pytest-cov, ruff, and mypy for quality control.
- Uses tiered TDD: strict TDD for scoring/config logic, tests required for graph helpers and
  generators, smoke tests for demo wiring.
- Uses GitHub Actions for linting, type checking, tests, and rule-validation checks.

Implementation tools: uv, Docker Compose, pytest, pytest-cov, ruff, mypy, GitHub Actions.

## Architecture Summary

```text
Synthetic referrals + bed simulation
        |
        v
RDF/OWL knowledge graph in Oxigraph
        |
        +--> Urgency agent: MTS/NEWS2 scoring
        |
        +--> Capacity agent: bed/resource pressure scoring
        |
        v
Coordinating agent: ranked list + Decision/cites triples
        |
        v
FastAPI + Jinja2 + HTMX clinician interface
        |
        v
Clinician accept/reorder/override, logged back to graph
```

## Primary Stack

| Area | Choice |
|---|---|
| Language | Python 3.12 |
| Web service | FastAPI |
| Templates | Jinja2 |
| Interactivity | HTMX |
| Frontend | HTML + CSS, no SPA build step |
| Triple store | Oxigraph |
| Graph standards | RDF, OWL, SPARQL 1.1 |
| Graph client/building | rdflib, httpx |
| Simulation | SimPy |
| Data/calibration | pandas, numpy, Pydantic v2 |
| LLM rationale layer | Anthropic Python SDK, `claude-opus-5` |
| Dependency management | uv |
| Local services | Docker Compose |
| Testing | pytest, pytest-cov |
| Quality | ruff, mypy |
| CI | GitHub Actions |

## Current Build Track

The dataset pipeline and the knowledge graph foundation are both done: a synthetic Irish outpatient
waiting list loaded in Postgres, and an OWL ontology plus RDF projection (Morph-KGC/R2RML) over it in
Oxigraph — 590,814 triples, 19 SHACL shapes. See `kg/README.md` and `dataset/README.md`.

The active track is `explainable-agent-based-triage_20260828`: the urgency agent, capacity agent,
coordinating agent, rationale layer, clinician UI, and CPC/CRT compliance validation built on top of
the graph. Per ADR-002, agents never write to Postgres or the graph directly — `retrieval-service_20260904`
(already built) is the single mediator: `POST /scores`/`/decisions`/`/overrides` write `agent.*` first,
then synchronously project the matching triples into the graph on success.

## Rationale Layer Change

The rationale layer can now be run through Docker Compose as a CLI container:

```bash
docker compose run --rm rationale \
  --hospital 9001 \
  --as-of 2026-08-30 \
  --pathway PW-9001-000007
```

Retrieval now exposes `referral_state_valid_from` in coordinator cohort rows, and the coordinator uses
that value when citing `ReferralState` evidence. This was added for rationale so CPC/CRT evidence points
at real KG state nodes rather than using `referral_date`, which is not the `ReferralState` identifier.

See `conductor/product.md`, `conductor/tech-stack.md`, and
`conductor/tracks/explainable-agent-based-triage_20260828/spec.md` for the detailed project plan.
