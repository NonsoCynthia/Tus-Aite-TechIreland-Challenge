# Tech Stack

> Chosen 2026-08-26 during Conductor setup. Optimised for a nine-person team shipping a demo-ready
> prototype in seven days, with the compliance story intact.

## Languages

- **Python 3.12** — single language for data generation, simulation, all three agents, and the web
  service. Deliberately one language: cross-language handoffs are the most likely thing to burn a day
  in a seven-day build.
- **HTML + Jinja2 templates + HTMX** for the clinician interface. No JS build step, no separate repo.

## Frameworks

| Concern | Choice | Notes |
|---|---|---|
| Web service | **FastAPI** | Serves both the HTMX-rendered clinician UI and a JSON API |
| Templating | **Jinja2** | Server-rendered ranked list |
| Interactivity | **HTMX** | Accept / reorder / override without a SPA |
| Discrete-event simulation | **SimPy** | Bed occupancy and arrivals queue |
| Data manipulation | **pandas** | HIPE/NTPF calibration statistics |
| RDF handling | **rdflib** | Graph construction and serialisation client-side |
| Validation | **Pydantic v2** | Request/response models, generator config |
| LLM access | **anthropic** (official Python SDK) | Rationale text generation only |

## Database

**Oxigraph, run in Docker**, as the RDF triple store. Speaks SPARQL 1.1 Query and Update over HTTP.

Rationale over the proposal's named candidates: Apache Jena Fuseki and Eclipse RDF4J are both JVM
services, which would put a second runtime on nine laptops for no modelling benefit. Oxigraph exposes
the **same SPARQL 1.1 HTTP protocol**, so the wire format is identical and swapping to Fuseki later
is a container change plus an endpoint URL — not a rewrite. If a judge or pilot partner requires
Jena specifically, that swap is a sub-day task.

- Store: `oxigraph/oxigraph` container, persistent volume
- Query endpoint: `POST /query` (SPARQL Query)
- Update endpoint: `POST /update` (SPARQL Update)
- Ontology: OWL, formalising the entity classes and the constraint that a `Decision` citing an urgent
  `Referral` cannot rank it behind a semi-urgent one still inside its CRT
- Vocabularies: SNOMED CT and HL7 FHIR RDF representations layered on for `Condition` and for
  patient/encounter structure — positions the prototype to plug into HSE Shared Care Record work later

### Graph Schema (from proposal §10)

**Entities:** `Patient`, `Referral`, `Condition` (ICD-10-AM coded, matching HIPE), `UrgencySignal`
(vitals, MTS/NEWS2 category), `ClinicalPrioritisationCategory`, `Specialty`, `Hospital`/`Ward`,
`BedStatus`, `Agent`, `Decision`, `Clinician`.

**Relationships:** `presentsWith`, `hasSignal`, `assignedTo`, `locatedAt`, `hasStatus`, `scored`
(score stored as an **edge property**, not a free-floating number), `ranks`, and `cites`.

`cites` is the audit trail itself. Walking backward from any ranked position reconstructs exactly
which evidence nodes produced it, without leaving the store.

## Agent Reasoning Model

**Deterministic scoring cores, LLM-generated rationale.** This is the central architectural decision
and it is a compliance decision as much as a technical one.

- **Urgency agent** — MTS and NEWS2 logic implemented as deterministic, unit-tested Python. Same
  inputs always yield the same score. Writes scored edges to the graph.
- **Capacity agent** — deterministic constraint reasoning over the SimPy occupancy model. Writes
  scored edges to the graph.
- **Coordinating agent** — ranking is a **SPARQL query** over both sets of triples plus deterministic
  tie-breaking (CPC, then CRT breach, then oldest referral first). Materialises `Decision` nodes and
  `cites` edges.
- **LLM layer** — takes the already-cited graph evidence for one ranked position and writes the
  human-readable rationale. It explains a decision it did not make. It cannot alter scores or ranks.

This keeps every score reproducible and auditable under EU AI Act framing, while still producing the
natural-language explainability the challenge is about. An LLM that produced the scores would make
"why is this patient #3" unanswerable across two runs.

### LLM Configuration

- Model: **`claude-opus-5`** (Anthropic Python SDK, `anthropic`)
- `thinking: {"type": "adaptive"}` — do **not** pass `budget_tokens`; it is rejected on Opus 5
- Prompt carries only the cited evidence for that ranked position; the model is instructed it may not
  introduce facts outside the supplied evidence
- Rationale generation across a synthetic batch is not latency-sensitive — use the Message Batches
  API for bulk validation runs to cut cost roughly in half
- Prompt caching on the stable system prompt + ontology description; the per-patient evidence goes
  after the last cache breakpoint

## Infrastructure

- **Docker Compose** — two services: `oxigraph` and the FastAPI `app`. One `docker compose up` is the
  whole environment; this matters when nine people set up on Day 1.
- **CI:** GitHub Actions — lint, type check, pytest, and the CPC/CRT rule-validation suite on every PR
- **Hosting:** local for the demo. No cloud deployment in scope.
- **Dependency management:** `uv` with `pyproject.toml` and a committed lockfile

## Key Libraries

| Library | Purpose |
|---|---|
| `fastapi`, `uvicorn` | Web service and ASGI server |
| `jinja2` | Server-side templates |
| `htmx` (CDN, no build) | Override / reorder interactions |
| `rdflib` | RDF graph construction, serialisation, SPARQL client helpers |
| `SPARQLWrapper` or `httpx` | Talking to Oxigraph's SPARQL endpoints |
| `simpy` | Discrete-event bed occupancy and arrivals queue |
| `pandas`, `numpy` | HIPE/NTPF calibration and synthetic generation |
| `pydantic` | Config and API models |
| `anthropic` | Rationale generation |
| `pytest`, `pytest-cov` | Test suite and coverage gate |
| `ruff` | Lint and format |
| `mypy` | Type checking |

## Architecture Decisions

### Decision 1: Oxigraph over Apache Jena Fuseki

**Date:** 2026-08-26

**Decision:** Use Oxigraph in Docker as the triple store rather than Jena Fuseki or RDF4J.

**Rationale:** The proposal names Jena/RDF4J, both JVM. Oxigraph speaks identical SPARQL 1.1 over
HTTP, starts in under a second, and keeps the team on one runtime. Because the protocol is the same,
this is a reversible decision — swapping to Fuseki is a container and URL change. Reversibility is
what makes it safe to take under time pressure.

**Trade-off accepted:** less name recognition with judges than "Apache Jena". Mitigated by documenting
the swap path explicitly.

---

### Decision 2: Deterministic scoring with LLM-generated rationale

**Date:** 2026-08-26

**Decision:** Urgency and capacity scores are deterministic rule implementations. The LLM only writes
prose explaining evidence already cited in the graph.

**Rationale:** Explainability here must survive an audit, not just read well. Deterministic scores are
reproducible, unit-testable against MTS/NEWS2 rubrics, and defensible under the EU AI Act human-oversight
framing that AI for Care mandates. An LLM-scored ranking cannot answer "why #3" identically twice.

**Trade-off accepted:** less superficially "agentic" than LLM agents end to end. Mitigated by the fact
that the multi-agent decomposition, the graph handoffs, and the audit trail are the actual agent story
— and by the LLM doing the genuinely language-shaped part of the job.

---

### Decision 3: HTMX + FastAPI over a React SPA

**Date:** 2026-08-26

**Decision:** Server-rendered Jinja2 templates with HTMX for the override interactions, inside the
same FastAPI service.

**Rationale:** No build step, no second repo, no cross-repo integration landing on Day 5 — the single
riskiest date in the schedule. The whole team reads and edits one Python codebase.

**Trade-off accepted:** less visual polish ceiling than React. Acceptable because the ranked list plus
override controls is a simple surface, and demo credibility here comes from the audit trail, not animation.

---

## Development Environment

### Prerequisites

- Python 3.12+
- `uv`
- Docker and Docker Compose

### Setup

```bash
# Start the triple store and app
docker compose up -d

# Install dependencies
uv sync

# Load ontology and seed data
uv run python -m triage.graph.bootstrap

# Run the app
uv run uvicorn triage.web.app:app --reload

# Tests
uv run pytest
```

### Environment Variables

| Variable | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | Rationale generation (or use `ant auth login`) |
| `OXIGRAPH_QUERY_URL` | Defaults to `http://localhost:7878/query` |
| `OXIGRAPH_UPDATE_URL` | Defaults to `http://localhost:7878/update` |
