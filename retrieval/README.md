# Retrieval Service

The single read/write path between Postgres (`core`/`agent` schemas) and the Oxigraph knowledge
graph, for the urgency/capacity/coordinator agents and the clinician UI. Implements ADR-002 (see
`conductor/tracks/explainable-agent-based-triage_20260828/decisions.md`): Postgres is the system of
record; the graph gets a synchronous projection on successful commit.

Full spec and plan: [`conductor/tracks/retrieval-service_20260904/`](../conductor/tracks/retrieval-service_20260904/).

## Running

This service is built and run from the **repo root** `docker-compose.yml` -- Postgres, pgAdmin, the
loader, Oxigraph and this service are all one compose project there (see the root `Makefile`).

```bash
# 1. From the repo root: one .env is authoritative for the whole stack,
#    including this service's bearer token and DB password.
cp .env.example .env       # edit HF_TOKEN, RETRIEVAL_BEARER_TOKENS, etc.
make up
make load

# 2. Set the retrieval_rw password to match RETRIEVAL_DB_URL in .env, the
#    same way kg_loader's is set:
docker compose exec db psql -U triage_admin -d triage \
  -c "ALTER ROLE retrieval_rw PASSWORD '<value from .env>';"

# 3. Build and run (already included in `make up`; rebuild after code changes).
make retrieval-build
docker compose up -d retrieval
```

The service is reachable on the host at `http://localhost:${RETRIEVAL_PORT:-8000}` (published, not
internal-only -- see spec.md FR1/NFR4). Every endpoint except `/health` requires `Authorization:
Bearer <token>`, checked against one of the comma-separated values in `RETRIEVAL_BEARER_TOKENS`
(repo-root `.env`).

## Endpoints

All require `Authorization: Bearer <token>` except `/health`, which is deliberately unauthenticated
so Docker/a load balancer/an uptime monitor can use it without holding a credential. Full descriptions
(response shapes, gotchas) are in `/docs` (Swagger UI) -- click **Authorize** there once and every
"Try it out" call picks up the token automatically.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | No auth. Checks Postgres and Oxigraph connectivity (short timeouts); `200` when both reachable, `503` with per-dependency detail otherwise |
| `POST` | `/scores` | Write an agent score + its citations (FR2, the ADR-002 projector) |
| `POST` | `/decisions` | Write a decision: rankings, citations, rule checks, atomically |
| `POST` | `/overrides` | Write a clinician override |
| `POST` | `/referrals` | Called by the clinician/hospital UI, not an agent: intake a brand-new referral (FR11) -- patient (+ demographics if new), specialty, dates. Generates and returns `pathway_number`; does NOT recompute scores or re-rank (that's the agents' job) |
| `GET` | `/referrals/{hospital_hipe}/{pathway_number}/wait-counters?as_of_date=` | The four wait counters, via `kg/queries/wait_counters.rq` unmodified (FR3) |
| `GET` | `/decisions/{hospital_hipe}/{as_of_date}` | Every ranked position for that day, with its cited evidence resolved to real values (FR8) -- reconstructed by walking `eat:cites` |
| `GET` | `/evidence/{hospital_hipe}/{as_of_date}/{pathway_number}?role=` | One placement's cited evidence, resolved (FR8); omit `role` for all four, or narrow to `urgency`/`capacity`/`timeframe`/`multi_list` |
| `GET` | `/referrals/{hospital_hipe}/{pathway_number}/context` | Everything an urgency/capacity agent needs to judge one referral (FR9) -- observations, conditions, triage events, plus capacity data for its specialty (wards + latest bed status, recent clinic sessions). Reads Postgres `core.*` directly, not the graph |
| `GET` | `/hospitals/{hospital_hipe}/cohort/{as_of_date}` | Which referrals the coordinator needs to rank (FR10) -- every referral still on the list that day, oldest-first, with CPC, wait counters, and a computed CRT breach flag (`crt_breached`/`crt_threshold_days`, `null` when no CRT applies to that CPC). Empty list, not 404, if nothing's on the list |
| `GET` | `/runs/{run_id}/hospitals/{hospital_hipe}/scores` | The urgency/capacity scores already written for this run+hospital (FR10), grouped by pathway then agent, citations included. Empty `scores` object, not 404, if nothing's been scored yet |

Every write endpoint follows the same contract: `200 {"status": "ok"}` on full success (`POST
/referrals` also returns the server-generated `pathway_number`); `207
{"status": "postgres_committed_graph_projection_failed", "detail": ...}` if Postgres committed but
the graph push then failed (the Postgres row still stands -- it's the system of record); `400` if
Postgres itself rejects the payload (no graph write is even attempted); `422` if the payload fails
validation before either store is touched.

**Two directions of data flow through this service.** `POST /scores`/`/decisions`/`/overrides` and
`GET /decisions`/`/evidence`/`/wait-counters` are all about agent *output* -- what an agent already
decided, written through and read back with its audit trail. `GET /referrals/.../context`,
`/hospitals/.../cohort/...` and `/runs/.../scores` (FR9/FR10) are the other direction: agent *input* --
the raw clinical/capacity data an agent needs before it can score a referral, which referrals need
ranking, and what the other agents already decided about them. All three read Postgres `core.*`/
`agent.*` directly rather than the graph, since that's where this data actually lives relationally,
and return an empty result (`404` for a single referral that doesn't exist, otherwise an empty
list/object) rather than erroring when there's simply nothing there yet.

`POST /referrals` (FR11) is a third case, different in kind from the other two: a write into `core.*`
itself, not `agent.*`, and called by the **clinician/hospital UI**, not an agent -- it's how a new
patient's referral enters the system in the first place, upstream of anything any agent does. It does
not recompute anything; it only makes the referral exist so the input-side endpoints above (and,
eventually, an agent watching them) can pick it up.

The full picture: the clinician/hospital UI calls `POST /referrals` when a new patient's referral
arrives, putting it on the waiting list. An urgency agent calls `GET /referrals/.../context` to gather
one referral's vitals, then `POST /scores`. A coordinator calls `GET /hospitals/.../cohort/...` to find
its cohort (which now includes that new referral), then `GET /runs/{run_id}/hospitals/.../scores` to
gather every score already written for it, then `POST /decisions` once it's ranked them.

## Rationale Layer Change

For the rationale layer, the cohort endpoint now includes `referral_state_valid_from`. The coordinator
uses that value when it cites `referral_state` evidence, because the KG `ReferralState` IRI is keyed by
`valid_from`, not by `referral_date`.

This keeps decision citations dereferenceable through `GET /evidence/...`: a rationale can resolve the
cited `ReferralState`, `Rule`, `BedStatus`, `ClinicSession`, and `Score` nodes instead of showing an
empty unresolved evidence item.

Every read endpoint's evidence is **resolved inline** (FR8, Phase 6) -- each citation comes back as
`{"role": ..., "iri": ..., "type": ..., "properties": {...}}`, the node's actual data (e.g. a
`ClinicSession`'s `slotsAvailable`), not just an identifier the caller would have to dereference
separately. A citation whose underlying evidence isn't loaded degrades to `type: null` / empty
`properties` rather than erroring. All IRIs in every response are **short** (namespace prefix
stripped, e.g. `clinic-session/9003/CL02/2026-08-26`, never the full
`https://nonsocynthia.github.io/.../kg/id/...` form) -- that full form is only ever used internally,
for the actual SPARQL queries against Oxigraph.

## Tests

```bash
make retrieval-test
make retrieval-lint
make retrieval-typecheck
```
