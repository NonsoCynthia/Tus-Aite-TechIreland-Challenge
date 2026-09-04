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

- [x] Task: docker-compose service scaffold
  - [x] Add a `retrieval` service definition (Dockerfile/build context) alongside `db` and `oxigraph`
  - [x] Publish the service's port to the host (FR1 — reachable from outside the compose network)
  - [x] Wire environment config: Postgres DSN using the `agent_rw` role, Oxigraph query/update URLs,
        the bearer-token secret(s) — all env-based, nothing committed
  - [x] Confirm the service starts under `docker compose up` and does not collide with the pinned
        `/triage_db` container name convention from `tech-stack.md`

  Note: `agent_rw` (migration 007) turned out to be `NOLOGIN` — a group role, not something a service
  can connect as directly. Added `dataset/db/migrations/009_retrieval_login_role.sql`, a `LOGIN` role
  `retrieval_rw` granted membership in `agent_rw`, mirroring how `kg_loader` is set up.

  Also consolidated `dataset/docker-compose.yml` (`db`, `pgadmin`, `loader`) into the root
  `docker-compose.yml` alongside `oxigraph` and `retrieval`, at the user's request, so every service
  is one compose project on one default network — no more `triage_net` external-network workaround
  between two separate projects (an earlier version of this task briefly introduced that, then
  removed it again in the same phase). `dataset/db/pgadmin/servers.json` and the loader's build
  context/volume paths were updated to `./dataset/...` accordingly. `dataset/Makefile` and
  `dataset/.env`/`.env.example` are superseded by a new root `Makefile`/`.env.example` — `dataset/Makefile`
  now forwards each target to the root so `cd dataset && make up` still works. `kg/Makefile`'s DB path
  was updated (`dataset/` → repo root) and its unquoted path fixed (broke on this checkout's
  space-containing path; pre-existing bug, not something this track introduced). `tech-stack.md`'s
  Setup/Infrastructure sections still describe the old two-stack layout — left for the track's
  end-of-implementation docs sync, not fixed here (user's call).

- [x] Task: FastAPI app skeleton and bearer-token auth (FR7)
  - [x] Write a smoke test: a request to a health-check route with no `Authorization` header returns
        `401`
  - [x] Write a smoke test: the same route with a valid bearer token returns `200`
  - [x] Implement the FastAPI app skeleton and an auth dependency/middleware applied to every route,
        checked before any handler logic (including before Postgres/Oxigraph access)
  - [x] Implement a `GET /health` route (no DB/graph dependency) proving the app boots and auth is
        enforced

- [x] Task: Phase Verification & Checkpoint (Refer to workflow.md)

  Confirmed by user 2026-09-04: scaffold verified end to end on the consolidated single
  docker-compose (see the note above the FastAPI-skeleton task for what changed after this task was
  first completed).

---

## Phase 2: Fixture decision generator (Tier 2)

- [x] Task: Write tests for the fixture generator
  - [x] Same seed produces identical payloads across two runs (determinism)
  - [x] Generated `agent.agent_scores` / `agent.decisions` / `agent.decision_rankings` /
        `agent.decision_citations` / `agent.rule_checks` / `agent.overrides` payloads satisfy every
        SQL CHECK constraint from `dataset/db/migrations/006_outputs.sql` (score range, valid
        `agent_name`, valid citation `role`, non-blank override reason, positive `cohort_size`,
        positive/unique `position`)

  `agent.rule_checks.rule_id` also carries a hard FK to `core.ref_rules` — queried the live table
  (`RULE-CRT-URGENT`, `RULE-CRT-SEMI`, `RULE-TRIAGE-TURNAROUND`, `RULE-ORDER`, `RULE-TIEBREAK`) rather
  than inventing IDs, so fixture decisions will actually insert once Phase 3 exercises them against
  the real database, not just pass isolated unit tests.

- [x] Task: Implement the fixture generator
  - [x] Seeded, reproducible generator producing one coherent decision (rankings + citations + rule
        checks) plus standalone score/citation and override payloads
  - [x] Generator lives where other tests can import it directly (test fixtures/helpers, not
        production request-handling code) — `retrieval/tests/fixtures.py`

- [x] Task: Verify coverage ≥ 60% on the generator module; `ruff`/`mypy` clean

  100% line coverage on `tests/fixtures.py` (25 seeds × constraint checks + determinism tests, 334
  total tests in the suite); `ruff check .` and `mypy app tests` both clean.

- [x] Task: Phase Verification & Checkpoint (Refer to workflow.md)

  Confirmed by user 2026-09-04.

---

## Phase 3: Write endpoints — the ADR-002 projector (Tier 2)

- [x] Task: IRI construction helpers
  - [x] Write tests asserting generated IRIs match `conductor/kg/namespaces.md`'s minting conventions
        for `eat:Score`, `eat:Decision`, `eat:RankedPlacement`, and citation edges
  - [x] Write a test guarding the known gotcha: no unescaped `/` inside a prefixed name — instance
        IRIs must be full `<...>` form where the identifier contains one
  - [x] Implement the IRI-construction helpers — `app/iri.py`

  Two gaps in `namespaces.md` filled with a documented convention rather than invented silently, per
  its own "stop and ask" instruction:
  - **Citation-evidence target IRIs.** `agent_citations`/`decision_citations` only store a flat
    `(evidence_type, evidence_key)` pair; the four evidence classes each have their own multi-part
    composite-key template. Confirmed with the user: the citing caller supplies `evidence_key` as the
    exact composite-key suffix from that evidence type's own template (e.g. `observation` →
    `"{hospital_hipe}/{pathway_number}/{obs_datetime}/{column}"` to match `obs/...`);
    `iri.evidence_iri` only does the `evidence_type` → path-segment lookup. `tests/fixtures.py`'s
    citation-key generation was updated to match (previously opaque placeholder strings).
  - **Activity/Agent IRIs.** Needed for `prov:wasGeneratedBy`/`prov:wasAssociatedWith`
    (cardinality 1 on `Score`/`Decision`/`RuleCheck`) but not templated anywhere. Convention: one
    Activity per `(run_id, agent_name)` for scores and per `(run_id, hospital_hipe, as_of_date)` for
    decisions/rule-checks (one execution, many nodes generated by it — not one Activity per node);
    one Agent IRI per named identity (`agent/urgency`, `agent/coordinator`, ...), not per run, since
    version is already a separate literal property. Documented in `iri.py`'s docstrings, not just
    picked silently — worth confirming with whoever owns `conductor/kg/` if this needs to become a
    normative addition to `namespaces.md` itself.

- [x] Task: Postgres write layer
  - [x] Write tests (using the Phase 2 fixture generator) that a valid scores/decision/override
        payload inserts the expected rows in a single transaction and commits
  - [x] Write a test that an invalid payload (e.g. score out of range, bad `agent_name`) is rejected
        before any insert is attempted
  - [x] Implement the transactional insert logic per payload shape — `app/db.py`, connects as
        `retrieval_rw` (migration 009)

- [x] Task: SPARQL Update projection layer
  - [x] Write tests that a committed decision/score/override produces exactly the expected triples
        (`eat:Score`, `eat:Decision`, `eat:RankedPlacement`, `eat:cites` + its four role
        subproperties) in the correct named graph (`run/{run_id}` or `overrides`)
  - [x] Write a test guarding the Morph-KGC-adjacent NULL gotcha: a NULL/optional column never
        materialises as the literal string `"None"`
  - [x] Implement the SPARQL Update construction and dispatch — `app/graph.py` (pure triple
        construction separated from `httpx` dispatch, so it's unit-testable without Oxigraph)

  `eat:RuleCheck` and `eat:Override` triples are also produced, even though spec.md FR2's
  parenthetical triple list didn't name them — they were always implied by the surrounding sentence
  (Postgres side explicitly includes `agent.rule_checks`) and by the ontology/named-graph docs; spec.md
  updated to say so explicitly rather than leaving the omission standing.

- [x] Task: Wire `POST /scores`
  - [x] Write a round-trip test: fixture payload in → `agent.agent_scores`/`agent_citations` rows +
        matching `eat:Score`/`eat:cites` triples out, both queryable after the call
  - [x] Implement the endpoint: validate → Postgres commit → graph projection, one code path

- [x] Task: Wire `POST /decisions`
  - [x] Write a round-trip test covering the full decision shape (rankings + citations + rule checks)
        landing correctly in both stores
  - [x] Implement the endpoint

- [x] Task: Wire `POST /overrides`
  - [x] Write a round-trip test: override payload in → `agent.overrides` row + append-only entry in
        `…/graph/overrides`
  - [x] Implement the endpoint

  All three verified against the real running Postgres and Oxigraph (`docker compose run --rm
  retrieval pytest`), not mocks — actual rows queried back via `psycopg`, actual triples confirmed via
  SPARQL `ASK` against the live store.

- [x] Task: Partial-failure handling
  - [x] Write a test that simulates the Postgres commit succeeding and the subsequent graph write
        failing (e.g. inject a fault into the Oxigraph client) — assert the Postgres row still exists
        and the response is distinguishable from full success (not a silent `200`)
  - [x] Implement the response contract and error surfacing for this case across all three write
        endpoints

  Response contract: `200 {"status": "ok"}` on full success; `207 {"status":
  "postgres_committed_graph_projection_failed", "detail": ...}` when Postgres committed but the graph
  push then failed (row stands); `400` when Postgres itself rejects the payload (FK/CHECK violation —
  no graph write is even attempted, verified with a spy). Tested for all three endpoints, not just
  `/scores`.

- [x] Task: Verify coverage ≥ 60% on the write path; `ruff`/`mypy` clean

  366 tests total, 97% coverage across `app/` (lowest single file 92%), `ruff check .` and
  `mypy app tests` both clean.

- [x] Task: Phase Verification & Checkpoint (Refer to workflow.md)

  Confirmed by user 2026-09-04.

---

## Phase 4: Read endpoints (Tier 2)

- [x] Task: Wait-counters endpoint
  - [x] Write a test asserting the endpoint's output matches running `kg/queries/wait_counters.rq`
        directly against the same graph state
  - [x] Implement the endpoint, including the `GRAPH` clause the fragment's header notes must be
        added by the includer

  The test builds its own independent `GRAPH`-wrapped copy of the fragment (different code path from
  `app/reads.py`'s wrapper) as ground truth, so a wrapper-specific bug would surface as a mismatch
  rather than the test tautologically agreeing with itself. To wrap the actual file unmodified rather
  than re-typing its contents, the retrieval image's build context moved from `./retrieval` to the
  repo root (`docker-compose.yml` + `retrieval/Dockerfile` updated) so it can `COPY
  kg/queries/wait_counters.rq` verbatim.

- [x] Task: Decision / ranked-position lookup
  - [x] Write a test that the endpoint reconstructs the full cited-evidence set for a ranked position
        purely by walking `eat:cites` (and role subproperties) backward from the `Decision` node —
        against data written by Phase 3's endpoints, not hand-inserted fixtures
  - [x] Implement the endpoint

  **Finding, not a bug:** `decision_iri` is keyed only by `(hospital_hipe, as_of_date)` —
  `namespaces.md` #4 says "one per hospital per day" deliberately. Two different `POST /decisions`
  calls (different `run_id`, different Postgres `decision_id`) that land on the same hospital+day
  accumulate their placements onto the *same* graph node rather than creating independent ones — this
  read endpoint therefore returns the union of every run's placements for that day, not just the
  latest run's. That's almost certainly the right behaviour for a real re-run of the coordinator
  (this day's decision *is* one entity), but it's worth the coordinator-agent developer knowing before
  they're surprised by it. Caught because repeated test runs in this session, reusing the fixture
  generator's small deterministic `(hospital_hipe, as_of_date)` space, briefly accumulated placements
  from earlier unrelated test runs onto one node — fixed in the tests with a wide random `as_of_date`
  offset per test, not in the endpoint (the accumulation is correct behaviour).

- [x] Task: Evidence-by-role lookups
  - [x] Write tests for urgency / capacity / timeframe / multi-list evidence retrieval, one shared
        query parameterised by role rather than four separate implementations
  - [x] Implement the endpoint(s)

  One query-builder function (`_evidence_query`) generates either the single-role pattern or a
  `UNION` of all four, built from the same `_ROLE_SUBPROPERTY` mapping the write side uses — not four
  hand-written near-duplicates. Reused by both the standalone evidence endpoint and the decision
  endpoint's per-placement evidence lookup.

- [x] Task: Evidence-completeness guard (NFR2)
  - [x] Write a test proving no read endpoint can return a score or decision without its cited
        evidence attached
  - [x] Implement the guard if the above tests surface a gap

  Gap found and fixed: `RankingIn.citations` (Phase 3) defaulted to an empty list, even though
  `eat:cites` is 1..n on `eat:RankedPlacement` in the ontology (same cardinality as `Score`, which
  *was* already enforced). Added `Field(min_length=1)`, matching `ScoreIn`. The read-side guarantee is
  a consequence of this write-time validation, not separate filtering logic in `reads.py` — proven by
  a test showing the write is rejected before the state could ever exist to filter.

- [x] Task: Verify coverage ≥ 60% on the read path; `ruff`/`mypy` clean

  372 tests total, 97% coverage across `app/` (lowest single file 92%), `ruff check .` and
  `mypy app tests` both clean.

- [x] Task: Phase Verification & Checkpoint (Refer to workflow.md)

  Confirmed by user 2026-09-04.

---

## Phase 5: Integration and acceptance pass (Tier 3)

- [x] Task: End-to-end demo path
  - [x] `docker compose up`, then from the host (outside any container): call `POST /decisions` with
        a generated fixture, then read it back via the Phase 4 endpoints, using a valid bearer token
  - [x] Confirm an unauthenticated call is rejected the same way, from the host

  Ran a fixture decision through `POST /decisions` from inside a throwaway container talking to the
  running `retrieval:8000` (simulating what an agent will do), then `GET /decisions/{hospital_hipe}/
  {as_of_date}` from the same process — every ranked position came back with its cited evidence.
  Separately confirmed from a bare `curl` on the host, outside any container: unauthenticated write
  and read both `401`; authenticated `/health` `200`.

- [x] Task: Documentation
  - [x] Document how to run the service, set the bearer-token env var, and the published port, in the
        service's own README (or `conductor/kg/requirements.md`-style doc, whichever the codebase
        convention points to)
  - [x] Note the service in `retrieval-database-onboarding.md` / `retrieval-service-references.md` as
        built, not just proposed

  `retrieval/README.md` gained an Endpoints table (all 7 routes, the write-response contract) and a
  corrected Running section. Both root-level docs updated: their "ADR-002 still open" framing replaced
  with "resolved and built," pointing at this track and `retrieval/README.md`.

- [x] Task: Full acceptance-criteria pass
  - [x] Walk `spec.md`'s Acceptance Criteria 1–11 one by one against the running system and record the
        result

  | # | Criterion | Result |
  |---|---|---|
  | 1 | `retrieval` container up, port reachable | ✅ `docker compose ps` — `Up`, `0.0.0.0:8000->8000` |
  | 2 | `POST /decisions` → Postgres rows + `eat:Decision`/`RankedPlacement`/`cites` triples | ✅ `test_routes.py::TestCreateDecision`, live demo |
  | 3 | `POST /scores` → Postgres rows + `eat:Score`/`cites` | ✅ `test_routes.py::TestCreateScore` |
  | 4 | `POST /overrides` → Postgres row + `overrides` graph entry | ✅ `test_routes.py::TestCreateOverride` |
  | 5 | Postgres commits, graph fails → row stands, failure reported | ✅ `test_partial_failure.py` (all 3 endpoints) |
  | 6 | Wait-counters endpoint matches `wait_counters.rq` directly | ✅ `test_reads_wait_counters.py`, independent comparison |
  | 7 | Decision endpoint reconstructs evidence via `cites` walk | ✅ `test_reads_decision.py` |
  | 8 | ADR-002 recorded in the blocked track's `decisions.md` | ✅ Phase 1, verified present |
  | 9 | Fixture generator seeded and reproducible | ✅ `test_fixtures.py::TestDeterminism` |
  | 10 | Port reachable from the host, outside any container | ✅ `curl http://localhost:8000/...` from host, this session |
  | 11 | No/invalid token → `401` on every endpoint; valid token succeeds | ✅ `test_health.py` + live `curl`, writes and reads both |

  11/11 met.

- [x] Task: Phase Verification & Checkpoint (Refer to workflow.md)

  Confirmed by user 2026-09-04. Track complete.
