# Plan: Retrieval Service

**Track:** `retrieval-service_20260904`
**Spec:** `spec.md`

Tiers per `workflow.md`: this track is entirely **Tier 2** (graph and pipeline: SPARQL read/write
helpers, `cites` edge construction, override write-back) except the bare scaffold/auth wiring, which
is **Tier 3** (smoke test only, no coverage gate). Each phase ends with a manual verification task per
`workflow.md`'s User Manual Verification Protocol.

---

## Phase 1: ADR-002 record + service scaffold (Tier 3)

- [x] Task: Record the ADR-002 decision
  - [x] Write the confirmed decision (Postgres system of record; synchronous, single-writer graph
        projection on successful commit) into
        `conductor/tracks/explainable-agent-based-triage_20260828/decisions.md`
  - [x] Reference this track (`retrieval-service_20260904`) as the implementation
  - [x] Update that track's status in `conductor/tracks.md` to reflect the blocker is resolved

- [ ] Task: docker-compose service scaffold
  - [ ] Add a `retrieval` service definition (Dockerfile/build context) alongside `db` and `oxigraph`
  - [ ] Publish the service's port to the host (FR1 — reachable from outside the compose network)
  - [ ] Wire environment config: Postgres DSN using the `agent_rw` role, Oxigraph query/update URLs,
        the bearer-token secret(s) — all env-based, nothing committed
  - [ ] Confirm the service starts under `docker compose up` and does not collide with the pinned
        `/triage_db` container name convention from `tech-stack.md`

- [ ] Task: FastAPI app skeleton and bearer-token auth (FR7)
  - [ ] Write a smoke test: a request to a health-check route with no `Authorization` header returns
        `401`
  - [ ] Write a smoke test: the same route with a valid bearer token returns `200`
  - [ ] Implement the FastAPI app skeleton and an auth dependency/middleware applied to every route,
        checked before any handler logic (including before Postgres/Oxigraph access)
  - [ ] Implement a `GET /health` route (no DB/graph dependency) proving the app boots and auth is
        enforced

- [ ] Task: Phase Verification & Checkpoint (Refer to workflow.md)

---

## Phase 2: Fixture decision generator (Tier 2)

- [ ] Task: Write tests for the fixture generator
  - [ ] Same seed produces identical payloads across two runs (determinism)
  - [ ] Generated `agent.agent_scores` / `agent.decisions` / `agent.decision_rankings` /
        `agent.decision_citations` / `agent.rule_checks` / `agent.overrides` payloads satisfy every
        SQL CHECK constraint from `dataset/db/migrations/006_outputs.sql` (score range, valid
        `agent_name`, valid citation `role`, non-blank override reason, positive `cohort_size`,
        positive/unique `position`)

- [ ] Task: Implement the fixture generator
  - [ ] Seeded, reproducible generator producing one coherent decision (rankings + citations + rule
        checks) plus standalone score/citation and override payloads
  - [ ] Generator lives where other tests can import it directly (test fixtures/helpers, not
        production request-handling code)

- [ ] Task: Verify coverage ≥ 60% on the generator module; `ruff`/`mypy` clean

- [ ] Task: Phase Verification & Checkpoint (Refer to workflow.md)

---

## Phase 3: Write endpoints — the ADR-002 projector (Tier 2)

- [ ] Task: IRI construction helpers
  - [ ] Write tests asserting generated IRIs match `conductor/kg/namespaces.md`'s minting conventions
        for `eat:Score`, `eat:Decision`, `eat:RankedPlacement`, and citation edges
  - [ ] Write a test guarding the known gotcha: no unescaped `/` inside a prefixed name — instance
        IRIs must be full `<...>` form where the identifier contains one
  - [ ] Implement the IRI-construction helpers

- [ ] Task: Postgres write layer
  - [ ] Write tests (using the Phase 2 fixture generator) that a valid scores/decision/override
        payload inserts the expected rows in a single transaction and commits
  - [ ] Write a test that an invalid payload (e.g. score out of range, bad `agent_name`) is rejected
        before any insert is attempted
  - [ ] Implement the transactional insert logic per payload shape

- [ ] Task: SPARQL Update projection layer
  - [ ] Write tests that a committed decision/score/override produces exactly the expected triples
        (`eat:Score`, `eat:Decision`, `eat:RankedPlacement`, `eat:cites` + its four role
        subproperties) in the correct named graph (`run/{run_id}` or `overrides`)
  - [ ] Write a test guarding the Morph-KGC-adjacent NULL gotcha: a NULL/optional column never
        materialises as the literal string `"None"`
  - [ ] Implement the SPARQL Update construction and dispatch

- [ ] Task: Wire `POST /scores`
  - [ ] Write a round-trip test: fixture payload in → `agent.agent_scores`/`agent_citations` rows +
        matching `eat:Score`/`eat:cites` triples out, both queryable after the call
  - [ ] Implement the endpoint: validate → Postgres commit → graph projection, one code path

- [ ] Task: Wire `POST /decisions`
  - [ ] Write a round-trip test covering the full decision shape (rankings + citations + rule checks)
        landing correctly in both stores
  - [ ] Implement the endpoint

- [ ] Task: Wire `POST /overrides`
  - [ ] Write a round-trip test: override payload in → `agent.overrides` row + append-only entry in
        `…/graph/overrides`
  - [ ] Implement the endpoint

- [ ] Task: Partial-failure handling
  - [ ] Write a test that simulates the Postgres commit succeeding and the subsequent graph write
        failing (e.g. inject a fault into the Oxigraph client) — assert the Postgres row still exists
        and the response is distinguishable from full success (not a silent `200`)
  - [ ] Implement the response contract and error surfacing for this case across all three write
        endpoints

- [ ] Task: Verify coverage ≥ 60% on the write path; `ruff`/`mypy` clean

- [ ] Task: Phase Verification & Checkpoint (Refer to workflow.md)

---

## Phase 4: Read endpoints (Tier 2)

- [ ] Task: Wait-counters endpoint
  - [ ] Write a test asserting the endpoint's output matches running `kg/queries/wait_counters.rq`
        directly against the same graph state
  - [ ] Implement the endpoint, including the `GRAPH` clause the fragment's header notes must be
        added by the includer

- [ ] Task: Decision / ranked-position lookup
  - [ ] Write a test that the endpoint reconstructs the full cited-evidence set for a ranked position
        purely by walking `eat:cites` (and role subproperties) backward from the `Decision` node —
        against data written by Phase 3's endpoints, not hand-inserted fixtures
  - [ ] Implement the endpoint

- [ ] Task: Evidence-by-role lookups
  - [ ] Write tests for urgency / capacity / timeframe / multi-list evidence retrieval, one shared
        query parameterised by role rather than four separate implementations
  - [ ] Implement the endpoint(s)

- [ ] Task: Evidence-completeness guard (NFR2)
  - [ ] Write a test proving no read endpoint can return a score or decision without its cited
        evidence attached
  - [ ] Implement the guard if the above tests surface a gap

- [ ] Task: Verify coverage ≥ 60% on the read path; `ruff`/`mypy` clean

- [ ] Task: Phase Verification & Checkpoint (Refer to workflow.md)

---

## Phase 5: Integration and acceptance pass (Tier 3)

- [ ] Task: End-to-end demo path
  - [ ] `docker compose up`, then from the host (outside any container): call `POST /decisions` with
        a generated fixture, then read it back via the Phase 4 endpoints, using a valid bearer token
  - [ ] Confirm an unauthenticated call is rejected the same way, from the host

- [ ] Task: Documentation
  - [ ] Document how to run the service, set the bearer-token env var, and the published port, in the
        service's own README (or `conductor/kg/requirements.md`-style doc, whichever the codebase
        convention points to)
  - [ ] Note the service in `retrieval-database-onboarding.md` / `retrieval-service-references.md` as
        built, not just proposed

- [ ] Task: Full acceptance-criteria pass
  - [ ] Walk `spec.md`'s Acceptance Criteria 1–11 one by one against the running system and record the
        result

- [ ] Task: Phase Verification & Checkpoint (Refer to workflow.md)
