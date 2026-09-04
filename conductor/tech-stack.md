# Tech Stack

> Chosen 2026-08-26 during Conductor setup. Optimised for a nine-person team shipping a demo-ready
> prototype in seven days, with the compliance story intact.
>
> **Updated 2026-09-03** for the knowledge graph build. Decisions 4 and 5 below supersede parts of
> this file that predate them; superseded passages are marked in place. The normative source for
> classes, properties, IRIs and shapes is
> `conductor/kg/` — where that directory and this file disagree, the
> track files win.
>
> **Updated 2026-09-04** for the retrieval service (Decision 6, ADR-002's implementation). The
> Infrastructure and Setup sections' docker-compose description is corrected in place, not marked
> superseded, since the two-project layout they described no longer exists at all.

## Languages

- **Python 3.12** — single language for data generation, simulation, all three agents, and the web
  service. Deliberately one language: cross-language handoffs are the most likely thing to burn a day
  in a seven-day build.
- **HTML + Jinja2 templates + HTMX** for the clinician interface. No JS build step, no separate repo.
- **SQL** for change detection over the input data. See Decision 4 — this is deliberate and scoped:
  logic that needs window functions lives in a Postgres view, never in a mapping or an agent.

## Frameworks

| Concern | Choice | Notes |
|---|---|---|
| Web service | **FastAPI** | Serves both the HTMX-rendered clinician UI and a JSON API |
| Templating | **Jinja2** | Server-rendered ranked list |
| Interactivity | **HTMX** | Accept / reorder / override without a SPA |
| Discrete-event simulation | **SimPy** | Bed occupancy and arrivals queue |
| Data manipulation | **pandas** | HIPE/NTPF calibration statistics |
| **Graph construction** | **Morph-KGC** | Declarative R2RML/RML mappings over Postgres → RDF. See Decision 4 |
| **Constraint validation** | **pySHACL** | Structural shapes and `sh:sparql` rule constraints. See Decision 5 |
| **Inference closure** | **owlrl** | Materialised at build time into a separate named graph; Oxigraph has no reasoner |
| RDF handling | **rdflib** | Serialisation and SPARQL client helpers. **No longer the construction path** — see Decision 4 |
| Validation | **Pydantic v2** | Request/response models, generator config |
| LLM access | **anthropic** (official Python SDK) | Rationale text generation only |

## Databases

Two stores, with different jobs. This is not redundancy: Postgres holds the published dataset as
distributed, and the graph is built from it.

### Postgres — the input layer

The dataset ships as a gated Hugging Face release loaded into Postgres by `dataset/`. It is the
source of every input-layer triple, and it is where two guarantees are enforced structurally rather
than by convention:

- **`kg.v_referral_state`** — the Type-2 change-detection view. Window functions cannot be expressed
  in a mapping language, so this logic lives in SQL, is committed at `kg/sql/001_…`, and is testable
  in psql independently of any mapping.
- **`kg_loader`** — a read-only role with **no grant on schema `eval`**. Mappings connect as
  `kg_loader`, so a mapping that references `eval.ground_truth` fails with a permission error rather
  than succeeding quietly. `kg/tests/test_loader_isolation.sh` asserts this.

Host port `5433` from your own machine; `db:5432` from inside Docker. Same database, two addresses.

### Oxigraph — the triple store

**Oxigraph, run in Docker.** Speaks SPARQL 1.1 Query and Update over HTTP.

Rationale over the proposal's named candidates: Apache Jena Fuseki and Eclipse RDF4J are both JVM
services, which would put a second runtime on nine laptops for no modelling benefit. Oxigraph exposes
the **same SPARQL 1.1 HTTP protocol**, so the wire format is identical and swapping to Fuseki later
is a container change plus an endpoint URL — not a rewrite. If a judge or pilot partner requires
Jena specifically, that swap is a sub-day task.

- Store: `oxigraph/oxigraph` container, persistent volume
- Query endpoint: `POST /query` (SPARQL Query)
- Update endpoint: `POST /update` (SPARQL Update)
- **Ontology:** OWL, formalising the entity classes and property structure.
  *Superseded correction:* this file previously said OWL would formalise the constraint that a
  `Decision` cannot rank an urgent `Referral` behind a semi-urgent one. **OWL cannot express that.**
  It is open-world: it infers what must be true and never objects to what you have not said. That
  constraint is a SHACL shape. See Decision 5 and `decisions.md` §2.
- **Vocabularies:** PROV-O, SOSA, OWL-Time, SKOS, QUDT, SHACL, DCAT/VoID.
  *Superseded correction:* this file previously said SNOMED CT and HL7 FHIR RDF would be "layered
  on". Neither is. SNOMED is **referenced** by `sct:` IRI and never imported — the ontology is
  licensed and enormous. FHIR RDF is deliberately not used: there is no interop requirement in this
  challenge and it would double every class. Field names stay MDS-aligned so a FHIR mapping remains
  possible later. See `ontology.md` §1.
- No built-in reasoner and no SHACL engine. Both jobs run at build time — which suits a project whose
  claim is reproducibility.

### Graph Schema

*Superseded.* The entity and relationship list previously given here came from proposal §10 and
predates the ontology work. It named `UrgencySignal`, `presentsWith` and `hasSignal`, none of which
exist, and described `scored` as an **edge property** — RDF has no edge properties.

**The normative schema is `conductor/kg/ontology.md`**, which gives
every class and property with domain, range and cardinality.

Two points from it that contradict what was here before, and matter most:

- **A score is a node, not an edge property.** `eat:Score` has its own IRI, `eat:scoreValue`,
  `eat:method`, `eat:agentVersion`, `prov:wasGeneratedBy` an activity, and one `eat:cites` edge per
  evidence row. Reification and RDF-star were both considered and rejected — the first is painful to
  query, the second is only preliminarily supported in Oxigraph.
- **`cites` is `rdfs:subPropertyOf prov:used`**, with four sub-properties carrying the `role` column
  of `decision_citations`: `citesUrgencyEvidence`, `citesCapacityEvidence`,
  `citesTimeframeEvidence`, `citesMultiListEvidence`. One query gets the whole explanation; the same
  query with a sub-property gets one section of the clinician's expander.

`cites` is still the audit trail itself. Walking backward from any ranked position reconstructs
exactly which evidence nodes produced it, without leaving the store.

## Agent Reasoning Model

**Deterministic scoring cores, LLM-generated rationale.** This is the central architectural decision
and it is a compliance decision as much as a technical one.

- **Urgency agent** — MTS and NEWS2 logic implemented as deterministic, unit-tested Python. Same
  inputs always yield the same score. Writes `eat:Score` nodes and `eat:cites` edges to the graph.
- **Capacity agent** — deterministic constraint reasoning over the SimPy occupancy model. Same.
- **Coordinating agent** — ranking is a **SPARQL query** over both sets of triples plus deterministic
  tie-breaking (CPC, then CRT breach, then oldest referral first). Materialises `Decision` nodes,
  `RankedPlacement` nodes and `cites` edges.
- **LLM layer** — takes the already-cited graph evidence for one ranked position and writes the
  human-readable rationale. It explains a decision it did not make. It cannot alter scores or ranks.

**Wait times are never recalculated by an agent.** The four wait counters are derived from one shared
SPARQL fragment in `kg/queries/`, used unmodified by every agent and by the rule checker, so they
cannot disagree about a wait. `adjusted_wait_days` subtracts suspended time, which is why
`eat:SuspensionEvent` carries a `time:Interval`.

**No agent reads `…/graph/rationale`.** Generated prose must never re-enter as evidence.

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
- **Every rationale stores its `prov:used` citation set, model version string and prompt hash.** The
  containment check — every entity named in the sentence appears in the citation set — is what turns
  "the model cannot introduce unsupported facts" from a claim into a CI test

## Infrastructure

- **Docker Compose** — one compose project at the repo root runs everything: `db` (Postgres),
  `pgadmin`, the `loader` (profile `tools`), `oxigraph`, and the `retrieval` service (Decision 6), on
  one default network, addressable by service name (`db`, `oxigraph`, `retrieval`). A root `Makefile`
  orchestrates the whole stack (`make up`, `make load`, `make kg-views`, `make retrieval-test`, ...);
  `dataset/Makefile` forwards its targets there so `cd dataset && make up` still works.
  *Superseded 2026-09-04:* this file previously described two separate compose projects
  (`dataset/docker-compose.yml` for `db`/`pgadmin`, a root file for `oxigraph`/`app`). They were
  merged into one project during `retrieval-service_20260904` — see that track's `plan.md` Phase 1
  for why (the retrieval service needed to reach `db` by hostname across what were two independent
  compose networks; consolidating was simpler than the external-network workaround first tried).
  **Postgres runs once, from the main checkout.** Never `docker compose up` in a second git worktree:
  the container name `/triage_db` is pinned and the second copy collides. Conductor workspaces
  connect to `localhost:5433`.
- **CI:** GitHub Actions — lint, type check, pytest, pySHACL structural shapes, the loader-isolation
  test, and the CPC/CRT rule-validation suite on every PR
- **Hosting:** local for the demo. No cloud deployment in scope.
- **Dependency management:** `uv` with `pyproject.toml` and a committed lockfile

## Key Libraries

| Library | Purpose |
|---|---|
| `fastapi`, `uvicorn` | Web service and ASGI server |
| `jinja2` | Server-side templates |
| `htmx` (CDN, no build) | Override / reorder interactions |
| `morph-kgc` | R2RML/RML materialisation from Postgres to RDF |
| `pyshacl` | SHACL validation, structural and `sh:sparql` |
| `owlrl` | OWL-RL closure at build time |
| `psycopg` (v3, `[binary]`) | Postgres driver for Morph-KGC, and for the retrieval service's writes (Decision 6) |
| `sqlalchemy` (**≥ 2.0**) | Required by Morph-KGC; older versions have no `postgresql+psycopg` dialect |
| `rdflib` | RDF serialisation, SPARQL client helpers |
| `SPARQLWrapper` or `httpx` | Talking to Oxigraph's SPARQL endpoints. The retrieval service uses `httpx` (async, matches its FastAPI handlers) |
| `pydantic-settings` | Retrieval service's environment-variable config (Decision 6) |
| `pyoxigraph` (**==0.3.22, pinned**) | In-memory RDF store for `kg/tests/test_wait_counters_sample.py`. `kg/queries/wait_counters.rq` documents a workaround for a version-specific engine quirk — don't bump without re-verifying it still applies |
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

### Decision 4: Declarative R2RML mapping over a Python loader

**Date:** 2026-09-03

**Supersedes:** the "RDF handling: rdflib, graph construction client-side" row in Frameworks.

**Decision:** Input-layer triples are produced by Morph-KGC from committed R2RML mappings over
Postgres, not by a hand-written rdflib script. Logic that a mapping language cannot express lives in
a committed Postgres view, not in the mapping.

**Rationale:** For a project whose selling point is auditability, "here is the mapping that produced
this triple" is worth more than a loader script. The mapping is a reviewable artifact that diffs in a
PR. The split also puts change-detection SQL somewhere it can be tested in psql, independently of
any RDF tooling — which is how the Type-2 state counts were verified before a single triple existed.

**Trade-off accepted:** a mapping language is less flexible than Python, and Morph-KGC has sharp
edges — notably it materialises SQL NULLs as the literal string `"None"`, so nullable columns need a
separate triples map filtering on `IS NOT NULL`. Those edges are documented in `spec.md` §4 so each
agent does not rediscover them. Accepted because the alternative — logic distributed through a
loader nobody reviews — is the failure this project exists to argue against.

---

### Decision 5: SHACL for constraints, OWL for structure

**Date:** 2026-09-03

**Supersedes:** the claim that the OWL ontology formalises the ranking-order constraint.

**Decision:** OWL describes classes, properties, domains and ranges. Every constraint that can be
*violated* — `RULE-ORDER`, `RULE-TIEBREAK`, interval integrity, required properties — is a SHACL
shape validated by pySHACL.

**Rationale:** OWL reasons under the open-world assumption. Declare that Urgent outranks Semi-Urgent,
then produce a ranking that ignores it, and OWL reports nothing: no statement said positions must
respect that order, so there is no contradiction to find. This is not a gap in OWL — inference and
validation are different jobs. A rule check needs the second.

The deeper reason is that SHACL validation reports are themselves RDF: `sh:ValidationReport`,
`sh:focusNode`, `sh:sourceShape`. That structure converts directly into `rule_checks` rows with the
focus node as the citation. A pure-Python rule checker means building that plumbing by hand.

**Which rules fail the build:** `RULE-ORDER` and `RULE-TIEBREAK` describe defects in our own output
and fail CI. `RULE-CRT-*` and turnaround describe facts about the hospital, not invalid graphs, and
are recorded as `passed=false` with detail. Shapes target `eat:Decision` in the run graph and never
the override graph, since a clinician may break `RULE-ORDER` knowingly.

**Trade-off accepted:** `sh:sparql` constraints are slow — rdflib evaluates them per focus node, and
13,772 nodes took minutes on 50k triples. Mitigated by running structural shapes per mapping and
`sh:sparql` constraints once at integration, scoped per hospital-day.

---

### Decision 6: Standalone retrieval service, bearer-token auth, one code path per write

**Date:** 2026-09-04

**Decision:** ADR-002 (where agent outputs get written — Postgres system of record, synchronous graph
projection on success, `conductor/tracks/explainable-agent-based-triage_20260828/decisions.md`) is
implemented as `retrieval/`, a **standalone FastAPI service** — its own container on the docker-compose
network, not an in-process library the agents and UI import. Its port is **published to the host**,
and because that means it's reachable from outside the trusted compose network, every endpoint
requires a shared static `Authorization: Bearer` token, checked before any handler logic runs.

**Rationale:** Decision 3 rejected a client/server split for the *clinician UI* specifically, to avoid
cross-repo integration risk landing on Day 5. That reasoning doesn't transfer here: the retrieval
service's callers (the urgency/capacity/coordinator agents, the clinician UI backend) are processes
that need to share one write path regardless of language or deployment shape, and a standalone service
callable over HTTP is the natural way to guarantee "one code path" when multiple future components
need to hit it — an in-process library only enforces that discipline within a single process. The
bearer token is the minimum viable authentication for a service that left the trusted network,
scoped deliberately: one shared secret, no per-caller identity, no rotation — proportionate to a
one-week prototype, not a production deployment (`product.md`'s own non-goal).

**Trade-off accepted:** No production-grade auth (per-caller keys, rotation, TLS termination) — see
`retrieval/README.md`'s NFR4. Every write endpoint does its own Postgres-then-graph sequence rather
than reusing Morph-KGC's batch mapping files, which are the wrong tool for low-latency single-row
writes (same reasoning as Decision 4's mapping-vs-loader split, applied to the write side instead of
the read side). Two IRI-scheme gaps `conductor/kg/namespaces.md` didn't cover (citation-evidence
target IRIs, Activity/Agent IRIs for `prov:wasGeneratedBy`) were filled with a documented convention
during this work rather than left blocking — see `retrieval-service_20260904/plan.md` Phase 3 for the
specifics; worth a second pair of eyes from whoever owns `conductor/kg/`.

---

## Development Environment

### Prerequisites

- Python 3.12+
- `uv`
- Docker and Docker Compose
- A Hugging Face account with approved access to the gated dataset

### Setup

```bash
# 1. Whole stack -- Postgres, pgAdmin, Oxigraph, retrieval -- one compose project at the repo root
cp .env.example .env          # add your own HF read token
make up
make load FETCH_PROFILE=full
make verify

# 2. Knowledge graph database objects (from the repo root; delegates into kg/)
cd kg && cp .env.example .env && cd ..   # loader password
make kg-views                            # applies sql/001 and sql/002
# then set the role password from kg/.env:
#   ALTER ROLE kg_loader PASSWORD '<KG_LOADER_PASSWORD>';
kg/tests/test_loader_isolation.sh

# 3. Materialise and validate (run from kg/ -- paths in each .ini are relative to cwd)
cd kg
python -m morph_kgc mappings/<track>.ini
pyshacl -s shapes/structural.ttl -df nt out/<track>.nt
cd ..

# 4. Retrieval service (Decision 6) -- ADR-002's implementation, already built
cp retrieval/.env.example retrieval/.env   # bearer token + retrieval_rw password
docker compose exec db psql -U triage_admin -d triage \
  -c "ALTER ROLE retrieval_rw PASSWORD '<value from retrieval/.env>';"
make retrieval-build && docker compose up -d retrieval
make retrieval-test

# 5. Clinician UI app -- not yet built (explainable-agent-based-triage_20260828)
```

`make reset` in `dataset/` drops the `kg` schema and the loader role along with everything else. Run
`make kg-views` afterwards and re-set the role password.

### Environment Variables

| Variable | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | Rationale generation (or use `ant auth login`) |
| `HF_TOKEN` | Your own read token for the gated dataset. `dataset/.env` |
| `KG_LOADER_PASSWORD` | Password for the read-only `kg_loader` role. `kg/.env` |
| `KG_DB_URL` | `postgresql+psycopg://kg_loader:…@localhost:5433/triage`. `kg/.env` |
| `OXIGRAPH_QUERY_URL` | Defaults to `http://localhost:7878/query` |
| `OXIGRAPH_UPDATE_URL` | Defaults to `http://localhost:7878/update` |
| `RETRIEVAL_DB_URL` | `postgresql://retrieval_rw:…@db:5432/triage`. `retrieval/.env` |
| `RETRIEVAL_BEARER_TOKENS` | Comma-separated shared bearer token(s), Decision 6. `retrieval/.env` |
| `RETRIEVAL_PORT` | Host port the retrieval service is published on. Defaults to `8000` |

`kg/mappings/*.ini` carries the loader password and is git-ignored. No password belongs in a `.sql`
or `.ttl` file.
