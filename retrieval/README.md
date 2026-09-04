# Retrieval Service

The single read/write path between Postgres (`core`/`agent` schemas) and the Oxigraph knowledge
graph, for the urgency/capacity/coordinator agents and the clinician UI. Implements ADR-002 (see
`conductor/tracks/explainable-agent-based-triage_20260828/decisions.md`): Postgres is the system of
record; the graph gets a synchronous projection on successful commit.

Full spec and plan: [`conductor/tracks/retrieval-service_20260904/`](../conductor/tracks/retrieval-service_20260904/).

## Running

This service is built and run from the **repo root** `docker-compose.yml`, not from within this
directory -- it depends on `triage_net`, a network created by `dataset/docker-compose.yml`.

```bash
# 1. Bring up the dataset stack first (creates triage_net); see dataset/README.md.
cd dataset && make up && make load && cd ..

# 2. Apply migration 009 and set the retrieval_rw password, the same way kg_loader's is set:
docker compose -f dataset/docker-compose.yml exec -T db psql -U triage_admin -d triage \
  < dataset/db/migrations/009_retrieval_login_role.sql
docker compose -f dataset/docker-compose.yml exec db psql -U triage_admin -d triage \
  -c "ALTER ROLE retrieval_rw PASSWORD '<value from retrieval/.env>';"

# 3. Configure this service.
cp retrieval/.env.example retrieval/.env   # edit RETRIEVAL_BEARER_TOKENS and the DB password

# 4. Build and run.
docker compose build retrieval
docker compose up -d oxigraph retrieval
```

The service is reachable on the host at `http://localhost:${RETRIEVAL_PORT:-8000}` (published, not
internal-only -- see spec.md FR1/NFR4). Every endpoint requires `Authorization: Bearer <token>`.

## Tests

```bash
docker compose run --rm retrieval pytest tests/ -v
docker compose run --rm retrieval ruff check .
docker compose run --rm retrieval mypy app
```
