# Spec: Retrieval Service

**Track:** `retrieval-service_20260904`
**Type:** feature
**Maps to:** implements ADR-002 (agent-output write path) and the read-side retrieval layer named as
"database and retrieval" work in `conductor/retrieval-service-references.md` /
`conductor/retrieval-database-onboarding.md`.

## Overview

Build a standalone FastAPI **retrieval service** — its own container on the docker-compose network,
alongside `db` (Postgres) and `oxigraph` — that mediates every read and write between the Postgres
`core`/`agent` schemas and the Oxigraph knowledge graph, for both the not-yet-built urgency/capacity/
coordinator agents and the clinician UI. This is the concrete implementation of **ADR-002**: agent
outputs (scores, citations, decisions, rankings, rule checks, overrides) are written to Postgres first;
the corresponding RDF triples are pushed into the graph only if that write succeeds.

## Background

Two of three build phases are merged to `main`: the synthetic dataset (`dataset/`) and the RDF/OWL
graph (`kg/`, 590,814 triples). The third phase — `explainable-agent-based-triage_20260828` (the
agents + clinician UI) — is written but blocked on ADR-002, which was previously unrecorded. It is now
confirmed: **Postgres is the system of record; the graph gets a synchronous, single-writer projection**
on successful Postgres commit (per the proposal in `conductor/retrieval-database-onboarding.md`).

The Postgres side is already provisioned and unblocks this work immediately:

- `dataset/db/migrations/006_outputs.sql` — `agent.agent_scores`, `agent.agent_citations`,
  `agent.decisions`, `agent.decision_rankings`, `agent.decision_citations`, `agent.rule_checks`,
  `agent.overrides`, with CHECK constraints already encoding the valid `agent_name`, `role`, and
  `score` ranges.
- `dataset/db/migrations/007_roles_and_grants.sql` — the `agent_rw` role: `SELECT, INSERT` on schema
  `agent`, `SELECT` on `core`, no access to `eval`.

The graph side must follow `conductor/kg/namespaces.md`'s IRI-minting conventions and named-graph
table: writes land in `…/kg/graph/run/{run_id}` (scores, citations, decisions, placements, rule
checks — "writable by: agents") or `…/kg/graph/overrides` (append-only, "writable by: UI"). `eat:Score`
and `eat:Decision`/`eat:RankedPlacement` are nodes with their own IRIs, never edge properties (this
track builds against the ontology as it actually exists, not the stale edge-property description in
`explainable-agent-based-triage_20260828/spec.md` FR1–FR3 — noted as stale in the onboarding brief).

Since the agents themselves are a separate, still-blocked track, this service's write path is built
and tested against a seeded, reproducible fixture/synthetic decision generator standing in for real
agent output — so the moment the agents exist, they have a working, tested path to write through
rather than being blocked further on this.

## Functional Requirements

### FR1 — Service scaffold

- New `retrieval` service added to docker-compose, network-adjacent to `db` and `oxigraph`, following
  existing container/port conventions (`db:5432` internal, host `5433`; Oxigraph `7878`).
- **Port published to the host** (not internal-network-only), so the service is reachable by
  `host:port` from outside the compose network — e.g. mentors, a demo, or a UI hosted elsewhere. No
  TLS/domain/reverse proxy in scope; this is a host port mapping, not a production deployment.
- Connects to Postgres as the `agent_rw` role (least privilege already provisioned — never broadened)
  and to Oxigraph over its SPARQL Query/Update HTTP endpoints.
- FastAPI app, Pydantic v2 request/response models.

### FR7 — Bearer-token authentication

- Every endpoint (read and write) requires `Authorization: Bearer <token>`, checked against one or
  more static, out-of-band-issued secrets (env-configured, never committed).
- A missing or invalid token returns `401` before any handler logic runs, including before any
  Postgres or Oxigraph access.
- The token is opaque and shared across callers (agents, coordinator, UI) — not per-caller identity.
  Attribution of *who* made a write (which agent, which clinician) continues to come from the
  payload's own fields (`agent_name`, `clinician_id`), not from the token.

### FR2 — Write endpoints (the ADR-002 projector)

One endpoint per `agent.*` output shape, each the single code path for that write — called by agents
and by the clinician UI, never bypassed by a direct Postgres write from a caller:

- `POST /scores` → `agent.agent_scores` + `agent.agent_citations`
- `POST /decisions` → `agent.decisions` + `agent.decision_rankings` + `agent.decision_citations` +
  `agent.rule_checks` (one decision submitted atomically)
- `POST /overrides` → `agent.overrides`

Each handler: validate the payload against the same constraints as the SQL CHECKs (score in
`[0, 1]`, `agent_name` in `{urgency, capacity}`, citation `role` in
`{urgency, capacity, timeframe, multi_list}`, non-blank override reason); insert in a Postgres
transaction and commit; **only on successful commit**, construct the corresponding triples
(`eat:Score`, `eat:Decision`, `eat:RankedPlacement`, `eat:cites` + its four role subproperties) using
`namespaces.md` IRI conventions and push them via SPARQL Update into `…/graph/run/{run_id}` (or
`…/graph/overrides`), in the same request.

If the graph write fails after the Postgres commit succeeds, the Postgres row stands (it's the system
of record) and the endpoint returns a response distinguishing "committed, graph projection failed" from
full success — never a silent 200 that hides a missing triple.

### FR3 — Read endpoints

Shared, single-implementation query helpers — never reimplemented per caller, following the
`kg/queries/wait_counters.rq` pattern:

- Wait counters, wrapping `wait_counters.rq` unmodified.
- Decision/ranked-position lookup that reconstructs full cited evidence by walking `eat:cites` (and
  its role subproperties) backward from the `Decision` node — this is product.md's audit-trail success
  criterion, made queryable over HTTP.
- Evidence-by-role lookups (urgency / capacity / timeframe / multi-list) for the UI's row-expansion.

### FR4 — Fixture decision generator

A seeded, reproducible synthetic generator producing valid `agent.*` payloads (respecting every SQL
CHECK constraint) to exercise FR2's write endpoints end-to-end in tests, standing in for real agent
output until `explainable-agent-based-triage_20260828` is unblocked.

### FR5 — Record ADR-002

Write the confirmed decision into
`conductor/tracks/explainable-agent-based-triage_20260828/decisions.md` (currently empty, named as
that track's blocker), pointing at this track as the implementation.

### FR6 — Named-graph and IRI compliance

All graph writes strictly follow `conductor/kg/namespaces.md`'s IRI-minting conventions and named-graph
table. No ad hoc graph or IRI scheme is invented by this service.

## Non-Functional Requirements

- **NFR1** — Tier 2 (`workflow.md`): tests required, TDD encouraged not enforced, round-trip tests
  count, 60% coverage gate.
- **NFR2** — No score or decision is ever returned by a read endpoint without its cited evidence
  attached (product.md success criterion 6).
- **NFR3** — Postgres access carries exactly `agent_rw`'s privileges, no broader. `agent_rw` itself is
  `NOLOGIN` (a group role — see migration 007), so a new `LOGIN` role granted membership in it was
  required to connect at all (`retrieval_rw`, migration 009); this is a login wrapper, not a privilege
  expansion, and mirrors how `kg_loader` is set up as its own standalone login role.
- **NFR4** — The service is reachable outside the docker-compose network (host port published), so
  every endpoint requires bearer-token auth (FR7) — this is a deliberate narrowing of product.md's
  general "no authentication hardening" non-goal, scoped specifically to this service because it's the
  one component in this build that leaves the trusted network. Still explicitly *not* production-grade
  auth: one shared static token, no per-caller identity, no rotation/expiry.
- **NFR5** — `ruff` and `mypy` clean.
- **NFR6** — Hand-written SPARQL Update strings are subject to the same NULL/`"None"` and
  unescaped-`/`-in-prefixed-name gotchas documented in `conductor/kg/requirements.md` — must not
  silently write `"None"` for a NULL column or emit a broken prefixed IRI.

## Acceptance Criteria

1. `docker compose up` brings up a `retrieval` service container alongside `db`/`oxigraph`, reachable
   on a documented port.
2. `POST /decisions` with a fixture payload produces both the `agent.decisions`/`decision_rankings`/
   `decision_citations`/`rule_checks` rows and the matching `eat:Decision`/`eat:RankedPlacement`/
   `eat:cites` (+ role subproperties) triples in `…/graph/run/{run_id}`, queryable via SPARQL.
3. `POST /scores` produces the matching `agent.agent_scores`/`agent_citations` rows and `eat:Score`
   node with `eat:cites` edges.
4. `POST /overrides` produces the `agent.overrides` row and an append-only entry in
   `…/graph/overrides`.
5. A Postgres commit that succeeds, followed by a simulated graph-write failure, leaves the Postgres
   row intact and the response reports the projection failure rather than a silent success.
6. The wait-counters read endpoint returns values identical to running `wait_counters.rq` directly.
7. The decision read endpoint reconstructs full evidence for a ranked position purely by walking
   `cites` edges.
8. `conductor/tracks/explainable-agent-based-triage_20260828/decisions.md` contains the recorded
   ADR-002 decision.
9. The fixture generator is seeded and reproducible — same seed, same payloads.
10. The `retrieval` service's port is reachable from the host machine (not just from inside the
    compose network), e.g. via `curl http://localhost:<port>/...` from outside any container.
11. Any request without a valid `Authorization: Bearer` token returns `401` on every endpoint,
    including writes; a request with a valid token succeeds.

## Out of Scope

- The urgency/capacity/coordinator agents' actual scoring logic (`explainable-agent-based-triage_20260828`,
  still blocked — this track unblocks it, doesn't implement it).
- The clinician UI's Jinja2/HTMX pages — this track builds the HTTP API the UI will call, not the UI.
- Production-grade auth: per-caller identity/API keys, token rotation/expiry, OAuth2/JWT, TLS/domain
  termination. FR7 is a single shared static bearer token only.
- Queued/async retry infrastructure for graph-projection failures beyond detecting and reporting them
  (no message queue in scope).
- Rationale generation / LLM layer.
- Any change to the existing Morph-KGC batch mapping pipeline — this is a separate, low-latency
  single-row write path per ADR-002, not a reuse of Morph-KGC.
