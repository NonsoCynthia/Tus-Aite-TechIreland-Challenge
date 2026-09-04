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
so Docker/a load balancer/an uptime monitor can use it without holding a credential.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | No auth, no DB/graph dependency -- proves the app process is up |
| `POST` | `/scores` | Write an agent score + its citations (FR2, the ADR-002 projector) |
| `POST` | `/decisions` | Write a decision: rankings, citations, rule checks, atomically |
| `POST` | `/overrides` | Write a clinician override |
| `GET` | `/referrals/{hospital_hipe}/{pathway_number}/wait-counters?as_of_date=` | The four wait counters, via `kg/queries/wait_counters.rq` unmodified (FR3) |
| `GET` | `/decisions/{hospital_hipe}/{as_of_date}` | Every ranked position for that day, with its cited evidence, reconstructed by walking `eat:cites` |
| `GET` | `/evidence/{hospital_hipe}/{as_of_date}/{pathway_number}?role=` | One placement's cited evidence; omit `role` for all four, or narrow to `urgency`/`capacity`/`timeframe`/`multi_list` |

Every write endpoint follows the same contract: `200 {"status": "ok"}` on full success; `207
{"status": "postgres_committed_graph_projection_failed", "detail": ...}` if Postgres committed but
the graph push then failed (the Postgres row still stands -- it's the system of record); `400` if
Postgres itself rejects the payload (no graph write is even attempted); `422` if the payload fails
validation before either store is touched.

## Tests

```bash
make retrieval-test
make retrieval-lint
make retrieval-typecheck
```
