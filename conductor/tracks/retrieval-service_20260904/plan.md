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

  **Later removed by user request** (2026-09-04, post-completion): `retrieval-database-onboarding.md`
  and `conductor/retrieval-service-references.md` were deleted outright as unnecessary for the final
  repo — they were pre-build briefing/reference-index documents whose purpose ended once the service
  they were briefing toward existed and was documented in `retrieval/README.md` and this track. Links
  to them removed from this track's `index.md`.

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

---

## Post-completion fixes (2026-09-04)

Two corrections raised after the track was marked done, both fixed and re-verified live:

1. **`/health` was behind auth.** The original design (Phase 1) put `/health` behind the same
   app-level auth dependency as every other route, specifically to prove auth was wired correctly.
   User correction: a health check that itself requires a credential can't be used by infra that has
   no reason to hold one (Docker `HEALTHCHECK`, a load balancer, an uptime monitor). Fixed by moving
   the auth dependency from app-level (`main.py`) to per-router (`routes.py`'s and `reads.py`'s own
   `APIRouter(dependencies=[...])`), so `/health` — defined directly on `app`, not through either
   router — is structurally outside the auth boundary rather than special-cased inside the auth check.
   `test_health.py` rewritten for the new behaviour; a new `test_auth.py` proves every other endpoint
   (across both routers) still requires the token, replacing the coverage `/health` used to provide.
   `spec.md` FR7 and AC 11 updated to state the carve-out explicitly.

2. **`retrieval/.env` was a second, un-consolidated env file.** The docker-compose consolidation
   (Phase 1 addendum) established "one root `.env` is authoritative for the whole stack" for
   `db`/`pgadmin`/`loader`, explicitly to avoid a second file drifting out of sync — but the retrieval
   service's own secrets (`RETRIEVAL_BEARER_TOKENS`, `RETRIEVAL_DB_URL`) were left in a separate
   `retrieval/.env`, inconsistent with that stated principle. Fixed: both moved into the root
   `.env`/`.env.example`, passed to the container via explicit `environment:` entries in
   `docker-compose.yml` (same pattern as the `loader` service) instead of `env_file:
   ./retrieval/.env`. `retrieval/.env.example` deleted as superseded (same treatment
   `dataset/.env.example` got earlier). `retrieval/README.md` and `conductor/tech-stack.md`'s
   Environment Variables table updated accordingly; the latter's `HF_TOKEN` row was also still saying
   `dataset/.env` from before the consolidation — fixed in the same pass since it's the same class of
   staleness.

Verified: rebuilt the image, 379 tests pass, `ruff`/`mypy` clean, recreated the running container to
pick up the new env wiring, and confirmed live from the host — `/health` returns `200` with no token
and with a bogus one; `/decisions` still `401`s with no token and resolves correctly (`404`, not an
auth or connection error) with the token now sourced from the consolidated root `.env`.

3. **`/docs` showed no Authorize button.** `auth.py` read `Authorization` as a plain `Header(...)`
   parameter, which works but never registers an OpenAPI security scheme — Swagger UI had no padlock
   icons and no global "Authorize" button, so the header had to be retyped by hand on every "Try it
   out" call. Fixed by switching to `fastapi.security.HTTPBearer` (`auto_error=False`, since its own
   default is `403` on a missing header and this service's contract is `401` for both missing and
   invalid tokens — handled explicitly, so behaviour is unchanged). Confirmed via `/openapi.json`: all
   six protected routes now carry `security: [{"HTTPBearer": []}]`, `/health` correctly carries none.
   379 tests unmodified and still passing, `ruff`/`mypy` clean.

4. **`/health` didn't check its dependencies.** It returned a static `{"status": "ok"}` proving only
   that the process was up, not that it could do its job. User request: check the databases explicitly.
   Added `db.check_connection()` (a `SELECT 1` with a 2s `connect_timeout`) and
   `graph.check_connection()` (an `ASK` query with a 2s `httpx` timeout) — both short-timeout so a
   hung dependency fails the health check fast rather than hanging it. `/health` now returns `200
   {"status": "ok", "postgres": "ok", "oxigraph": "ok"}` when both are reachable, `503 {"status":
   "degraded", ...}` with per-dependency detail otherwise — `503`, not a `200` with a degraded body
   only, so a naive `curl -f` health check (or a Docker `HEALTHCHECK` using one) correctly reports
   unhealthy without parsing the response. Still unauthenticated (unaffected by fix 1 above). Two new
   tests monkeypatch each dependency independently to prove the `503` path; verified again against
   real infrastructure, not just mocks, by actually stopping the `oxigraph` container mid-session —
   `/health` correctly went to `503 {"oxigraph": "unreachable"}` and recovered to `200` once it was
   started again. 381 tests total, `ruff`/`mypy` clean.

---

## Phase 6: Evidence resolution (Tier 2, reopened 2026-09-04)

**Why reopened:** walking `eat:cites` (Phases 3-4) tells the UI *which* evidence node was cited, as an
IRI. It does not tell it *what that node says*. `product-guidelines.md` requires rationale to name
`"NEWS2 aggregate 7"`, `"Ward B occupancy 104%"` — actual values, not opaque identifiers. Rendering
that requires a second hop: dereferencing the evidence IRI into its own properties. FR8 in spec.md.

**Course-corrected mid-phase, twice, both by user direction:**

1. Originally planned as a standalone `GET /evidence/resolve?iri=` endpoint. User: fold resolution
   directly into the existing `GET /decisions` and `GET /evidence` responses instead — no second
   round-trip for the UI to orchestrate. Implemented as an internal `_resolve_iri` helper, called
   once per citation inside `_evidence_for_placement`, so every citation in either endpoint's
   response now carries `type` + `properties` alongside `role`, not just an IRI. The standalone
   endpoint idea was dropped entirely, not kept as an option alongside the embedded version.
2. User: the full `https://nonsocynthia.github.io/.../kg/id/...` form in JSON responses is
   unnecessarily verbose for a caller — why does the API need to expose it. Added `iri.short()`,
   applied to every IRI field in every read-endpoint response (`decision`, `placement`, `referral`,
   evidence `iri`, resolved property values, resolved `type`). The full IRI is still used for every
   actual SPARQL query/update (required, per `namespaces.md`) — only JSON API responses are
   shortened, since that file's "no unescaped `/` in a prefixed name" rule is a Turtle/N-Quads
   serialisation constraint, not something that applies to a JSON string field.

- [x] Task: Evidence resolution, folded into `GET /decisions` and `GET /evidence`
  - [x] Write a test: insert a synthetic `ClinicSession` node (real ontology properties —
        `eat:clinicName`, `eat:slotsTotal`, `eat:slotsBooked`, `eat:slotsAvailable`, `eat:sessionDate`)
        directly into the graph, `POST` a decision citing that exact IRI, `GET` it back, assert the
        citation carries the real property values — not just re-confirming the IRI was cited
  - [x] Write a test that `rdf:type` is pulled out into a `type` field, not left in `properties`
  - [x] Write a test that a citation whose evidence node has no triples loaded degrades to
        `type: null` / `properties: {}` rather than erroring or being dropped — the normal case in
        this dev environment, where the full dataset isn't loaded
  - [x] Write a test proving the two hops (`cites` walk, then resolve) compose end to end against a
        citation this service's own `POST /decisions` wrote, not a hand-inserted fixture alone
  - [x] Implement `_resolve_iri`: `SELECT ?p ?o WHERE { GRAPH ?g { <iri> ?p ?o } }`, `rdf:type` split
        out into `type`, every other predicate shortened via `iri.short`

- [x] Task: Shorten every IRI in every read-endpoint response (`iri.short`, added to `iri.py`)
  - [x] Unit tests: strips the instance/vocabulary/graph namespace correctly; leaves non-namespaced
        literal values (a plain string, a date) unchanged rather than mangling them
  - [x] Integration test asserting no response body contains `"https://"` anywhere

- [x] Task: Per-endpoint `summary`/`description` for `/docs` (user request, mid-phase)
  - [x] All 7 routes (`/health` + 3 writes + 3 reads) get a `summary` and a full `description`
        covering what the endpoint does, its response contract (writes: 200/207/400/422), and any
        gotcha a caller needs (decision-node accumulation, evidence-degradation behaviour, etc.)
  - [x] App-level `description` on the `FastAPI(...)` constructor, shown at the top of `/docs`,
        pointing at `spec.md` and `README.md`

- [x] Task: Verify coverage stays ≥ 60% on the read path; `ruff`/`mypy` clean

  388 tests total (up from 381), 97% coverage on `app/`, `ruff`/`mypy` clean. Confirmed stable across
  three consecutive full-suite runs (the accumulation gotcha documented above was actually caught and
  fixed here — the first attempt at the new evidence-resolution tests failed intermittently across
  runs until they adopted the same wide-random-`as_of_date` isolation pattern `test_reads_decision.py`
  already used).

- [x] Task: Phase Verification & Checkpoint (Refer to workflow.md)
  - [x] Rebuilt, ran the full suite three times consecutively (388 passed each time), confirmed live
        against the running container: `POST /decisions` with a citation pointing at a synthetically
        inserted `ClinicSession`, then `GET /decisions/...` — response showed
        `"clinicName": "Cardiology Outreach"`, `"slotsAvailable": "2"` etc. directly, IRIs in short
        form throughout, zero occurrences of the full namespace URL. `/openapi.json` confirmed every
        route carries the expected `summary`.

### Post-Phase-6 fix: `iri.short()` missed reused vocabularies

Found by loading the **real** knowledge graph (see below) and citing genuine evidence: a real
`Observation` node's `type`/`properties` came back as full `http://www.w3.org/ns/sosa/...` URIs,
unshortened — `short()` only knew about `eat:`/`eatd:`/`graph/`, not the reused vocabularies
(`tech-stack.md`: "PROV-O, SOSA, OWL-Time, SKOS and QUDT") real loaded data actually uses. Every
per-column `Observation` is `sosa:Observation`, so this wasn't an edge case — it was the first real
`Observation` citation resolved against real data. Fixed: `short()` now also strips
`SOSA_NS`/`TIME_NS`/`SKOS_NS`/`QUDT_NS`/`UNIT_NS`/`PROV_NS`/`RDF_NS`, prefixed with a short label
(`sosa:`, `prov:`, etc.) rather than bare — our own `eat:`/`eatd:`/graph namespaces stay bare, since
they're the dominant vocabulary in every response and unambiguous. New test
(`test_strips_reused_vocabularies_with_a_short_label`); 389 tests, `ruff`/`mypy` clean; reconfirmed
live against the same real citation.

## Real-data verification (2026-09-04, post-completion)

User asked to test against real data rather than fixtures. Checked first rather than assuming:
Postgres already had the full dataset loaded (`core.referral_daily`: 70,022 rows), but Oxigraph did
not — only this session's own test-run graphs existed, no `…/kg/graph/inputs`. Loaded the real graph:

- Found pre-existing, correctly-materialized `kg/out/*.nq` files (timestamped hours before this
  session touched anything) — no need to regenerate via Morph-KGC. A throwaway `python -m morph_kgc`
  run in a container on the compose network (to resolve the mappings' hardcoded `db` hostname,
  which only resolves inside Docker, not from the host — the `.ini` files were not modified) produced
  fragmented per-group chunk files instead of cleanly consolidating; those were discarded rather than
  trusted, and the pre-existing clean files were used instead.
- Loaded all 5 files into Oxigraph (`…/kg/graph/inputs`: 590,683 triples; `clinical.nq` had 381,026
  lines vs. `kg/README.md`'s documented 357,285 — flagged to the user as unexplained, not chased
  further, since RDF stores deduplicate on insert so loading it either way was safe).
- Verified end-to-end against real data: `GET /referrals/9001/PW-9001-000007/wait-counters` returned
  genuine computed counters; a `POST /decisions` citing a real `Condition` (`core.conditions`,
  ICD-10-AM `M16.1`) resolved correctly on read-back — which is what surfaced the SOSA gap above,
  fixed in the same session.

Not committed to the repo (no code/mapping changes) — this loaded data into the local Oxigraph
container's runtime state only, for interactive testing.
