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
# 1. From the repo root: dataset up + loaded, migrations included (009 creates retrieval_rw).
cp .env.example .env       # repo root -- edit HF_TOKEN etc.
make up
make load

# 2. Set the retrieval_rw password, the same way kg_loader's is set:
docker compose exec db psql -U triage_admin -d triage \
  -c "ALTER ROLE retrieval_rw PASSWORD '<value from retrieval/.env>';"

# 3. Configure this service.
cp retrieval/.env.example retrieval/.env   # edit RETRIEVAL_BEARER_TOKENS and the DB password

# 4. Build and run (already included in `make up` once retrieval/.env exists).
make retrieval-build
docker compose up -d retrieval
```

The service is reachable on the host at `http://localhost:${RETRIEVAL_PORT:-8000}` (published, not
internal-only -- see spec.md FR1/NFR4). Every endpoint requires `Authorization: Bearer <token>`.

## Tests

```bash
make retrieval-test
make retrieval-lint
make retrieval-typecheck
```
