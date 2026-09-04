# Spec: Retrieval Service

**Track:** `retrieval-service_20260904`
**Type:** feature
**Maps to:** implements ADR-002 (agent-output write path) and the read-side retrieval layer named as
"database and retrieval" work in the pre-build briefing docs this track was scoped from (since
removed post-completion as no longer necessary — their content is superseded by this spec and
`retrieval/README.md`).

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
on successful Postgres commit.

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

- New `retrieval` service in the repo-root `docker-compose.yml`, which now defines the whole stack —
  `db`, `pgadmin`, `loader`, `oxigraph` and `retrieval` — as one compose project on one default
  network, addressable by service name (`db`, `oxigraph`, `retrieval`). `dataset/docker-compose.yml`
  is retired; `dataset/Makefile` forwards its targets to a new root `Makefile`.
- **Port published to the host** (not internal-network-only), so the service is reachable by
  `host:port` from outside the compose network — e.g. mentors, a demo, or a UI hosted elsewhere. No
  TLS/domain/reverse proxy in scope; this is a host port mapping, not a production deployment.
- Connects to Postgres as `retrieval_rw`, a login role carrying exactly `agent_rw`'s privileges (see
  NFR3), and to Oxigraph over its SPARQL Query/Update HTTP endpoints.
- FastAPI app, Pydantic v2 request/response models.

### FR7 — Bearer-token authentication

- Every endpoint (read and write) requires `Authorization: Bearer <token>`, checked against one or
  more static, out-of-band-issued secrets (env-configured, never committed) — **except `/health`**,
  deliberately unauthenticated so Docker's own `HEALTHCHECK`, a load balancer, or an uptime monitor
  can use it without holding a credential; it does no DB/graph access either, so there is nothing
  sensitive behind it to protect.
- A missing or invalid token returns `401` before any handler logic runs, including before any
  Postgres or Oxigraph access. Applied per-router (write and read routers each carry the auth
  dependency), not at the app level, which is what keeps `/health` outside it structurally rather
  than via a special-cased exemption inside the auth check itself.
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
(`eat:Score`, `eat:Decision`, `eat:RankedPlacement`, `eat:RuleCheck`, `eat:Override`, `eat:cites` +
its four role subproperties — every class the Postgres side above writes has a graph-side
counterpart, per the ontology and `namespaces.md`'s named-graph table) using `namespaces.md` IRI
conventions and push them via SPARQL Update into `…/graph/run/{run_id}` (or `…/graph/overrides`), in
the same request.

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

**Note (added Phase 6):** the above gets the UI *which* evidence node was cited, as an IRI — not what
that node actually says. Rendering `product-guidelines.md`'s required rationale shape (`"NEWS2
aggregate 7"`, `"Ward B occupancy 104%"`) needs a second hop dereferencing that IRI into its own
properties. That's FR8.

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

### FR8 — Evidence resolution, embedded in FR3's read endpoints (added Phase 6, reopened)

Every citation returned by `GET /decisions/{hospital_hipe}/{as_of_date}` and `GET
/evidence/{hospital_hipe}/{as_of_date}/{pathway_number}` is resolved to its actual properties, not
left as a bare IRI. **Not a separate endpoint** — a standalone `GET /evidence/resolve?iri=` was the
original design; the user asked for it folded directly into the existing responses instead, so the UI
never needs a second round-trip per citation. Internally: `_resolve_iri` dereferences one IRI (every
`?p ?o` triple with it as subject, across any named graph) and is called once per citation inside the
existing evidence-lookup helper.

Each citation entry becomes `{"role": ..., "iri": ..., "type": <short class name, from rdf:type>,
"properties": {<short predicate name>: <value>, ...}}`. If the evidence node has no triples loaded
(the normal case in a dev environment without the full dataset), `type` is `null` and `properties` is
empty — the citation still appears, degrading gracefully rather than erroring or being dropped; one
missing citation's detail must not take down an otherwise-complete decision.

Generic by design — one resolver, not five per-evidence-type ones — because the citation itself
already carries `evidence_type` if a caller needs to branch on it; resolution only answers "what does
this specific node say," the same question regardless of type.

**IRI shortening (added alongside FR8, same user request):** every IRI in every read-endpoint JSON
response (`decision`, `placement`, `referral`, evidence `iri`, resolved property values/`type`) has
its namespace prefix stripped (`iri.short`) — e.g. `clinic-session/9003/CL02/2026-08-26`, not
`https://nonsocynthia.github.io/Tus-Aite-TechIreland-Challenge/kg/id/clinic-session/9003/CL02/
2026-08-26`. The full IRI is still used for every actual SPARQL query/update — this is purely a
response-shaping concern, not a change to how the graph itself is addressed or namespaces.md's
conventions. Covers `eat:`/`eatd:`/graph IRIs (stripped bare, no label) and the reused vocabularies
`tech-stack.md` names (PROV-O, SOSA, OWL-Time, SKOS, QUDT — stripped with a short label, e.g.
`sosa:observedProperty`, since those aren't our own dominant vocabulary and a bare strip could
collide) — found to matter, not assumed, when a real `Observation` citation (`sosa:Observation`)
resolved against the real loaded graph and came back with full unshortened `sosa:` URIs.

### FR9 — Referral context (agent judgment input, added Phase 7, reopened again)

FR3/FR8 cover the *output* side: what an agent already decided, with its citations resolved. They
give an agent no way to gather the *input* it needs to decide in the first place. `GET
/referrals/{hospital_hipe}/{pathway_number}/context` closes that gap: the referral's own record
(specialty, clinic, referral/received dates, triage status), every recorded observation (vitals),
condition (ICD-10-AM), and triage event tied to that referral, plus a `capacity` section — every ward
serving the referral's specialty (primary ward first) with its latest bed-status snapshot, and the 5
most recent clinic sessions for that specialty.

Reads Postgres `core.*` directly, not the graph — `retrieval_rw` already has `SELECT` on all of `core`
(migration 007), and the input data is fully relational there; going through SPARQL would mean
reconstructing joins (referral → specialty → ward, referral → specialty → clinic) that Postgres
already expresses as foreign keys. This is also why this endpoint can't be tested by inserting its own
fixture data the way the write-path tests do: `core.*` is genuinely read-only for this service by
design (NFR3's boundary), so its own tests run against whatever real dataset is actually loaded,
skipping cleanly rather than failing when it isn't.

`404` if the referral itself doesn't exist. Unlike FR3/FR8, there's no `eat:cites` walk here and
nothing to resolve — this is raw input, not an audit trail of agent output.

### FR10 — Coordinator input: cohort and already-written scores (added Phase 8, reopened again)

FR9 gives one agent input for one referral. The coordinating agent needs two more things FR9 doesn't
cover: **which** referrals need ranking, and **what the other two agents already decided** for them.

- `GET /hospitals/{hospital_hipe}/cohort/{as_of_date}` — every referral still on the waiting list
  (`core.referral_daily.removal_date IS NULL`) for that hospital and day, with specialty, referral/
  received dates, the same wait counters `wait_counters.rq` computes (denormalised onto the row
  already, no per-referral call needed), CPC (from its triage event, `null` if not yet triaged), and a
  `currently_suspended` flag. That flag is informational only — whether to rank a suspended referral is
  the coordinator's judgement, not decided here. Also includes `crt_threshold_days`/`crt_breached`
  (Clinical Response Time: `core.ref_codes.crt_days` for the referral's CPC, e.g. 28 for Urgent, 91 for
  Semi-Urgent, `null` for Routine/Excluded/untriaged; `crt_breached` is `adjusted_wait_days >
  crt_threshold_days`, `null` when no threshold applies) — user request ("can we also flag that?"),
  reversing this track's own earlier, more conservative design call. Originally omitted citing
  `tech-stack.md` Decision 5's separation of data access from rule logic; on reflection Decision 5 itself
  calls `RULE-CRT-*` "facts about the hospital, not invalid graphs" — unlike `RULE-ORDER`/`RULE-TIEBREAK`,
  it isn't a judgement comparing referrals, just date math against an already-normative threshold, so
  it's computed here rather than left to callers to re-derive. Empty list, not `404`, if the hospital
  exists but nothing is on the list that day.
- `GET /runs/{run_id}/hospitals/{hospital_hipe}/scores` — every urgency/capacity score already written
  via `POST /scores` for that run and hospital, with citations, keyed by `pathway_number` then
  `agent_name`. A referral with only one agent's score written so far still appears, with just that
  key present. Empty `scores` object, not `404`, if nothing has been scored yet.

Both read Postgres directly, same reasoning as FR9. The cohort endpoint hits the same `core.*`
read-only boundary as FR9 (tests skip cleanly without the full dataset loaded); the scores endpoint
reads `agent.agent_scores`/`agent_citations`, which this service's own `POST /scores` writes, so its
tests use the write path directly and need no such skip.

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
11. Any request without a valid `Authorization: Bearer` token returns `401` on every endpoint except
    `/health`, including writes; a request with a valid token succeeds. `/health` itself returns `200`
    regardless of whether a token is present.
12. Citations returned by `GET /decisions/...` and `GET /evidence/...` carry the cited node's actual
    properties (e.g. a `ClinicSession`'s `slotsAvailable`/`slotsTotal`), not just its IRI — resolved
    inline, no second request needed. A citation with nothing loaded for its IRI degrades to
    `type: null` / empty `properties` rather than erroring.
13. No read-endpoint JSON response contains the full `https://nonsocynthia.github.io/...` namespace
    prefix anywhere — every IRI field is shortened to its relative form.
14. Every endpoint (`/health` included) has a `summary` and `description` visible in `/docs`
    (`/openapi.json`), covering what it does and, for writes, the response contract.
15. `GET /referrals/{hospital_hipe}/{pathway_number}/context` on a real, fully-populated referral
    returns its observations, conditions, and triage events, plus capacity data (wards serving its
    specialty with latest bed status, recent clinic sessions for that specialty). `404` on a referral
    that doesn't exist.
16. `GET /hospitals/{hospital_hipe}/cohort/{as_of_date}` on a real hospital/day returns every referral
    still on the list, oldest referral first, each with CPC and wait counters. Empty list, not `404`,
    when nothing is on the list.
17. A score written via `POST /scores` is retrievable via `GET /runs/{run_id}/hospitals/{hospital_hipe}
    /scores`, grouped by `pathway_number` then `agent_name`, with its citations intact. Empty `scores`
    object, not `404`, when nothing has been scored yet for that run/hospital.
18. `GET /hospitals/{hospital_hipe}/cohort/{as_of_date}` computes `crt_breached`/`crt_threshold_days`
    per referral from `core.ref_codes.crt_days`: a real `true`/`false` for CPC 1 (Urgent, 28 days) and
    CPC 3 (Semi-Urgent, 91 days) matching `adjusted_wait_days > crt_threshold_days`, `null` for both
    fields for CPC 2/4 (Routine/Excluded) and untriaged referrals.

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
