"""Retrieval service -- FastAPI app.

The write endpoints (FR2, the ADR-002 projector) live in routes.py. Read
endpoints (FR3) live in reads.py. Auth (FR7) is applied per-router, not at
the app level, so /health can stay unauthenticated -- see auth.py.
"""

from fastapi import FastAPI, status
from fastapi.responses import JSONResponse

from . import db, graph
from .reads import router as reads_router
from .routes import router as writes_router

app = FastAPI(
    title="Retrieval Service",
    description=(
        "The single read/write path between Postgres (`core`/`agent` schemas) and the Oxigraph "
        "knowledge graph, for the urgency/capacity/coordinator agents and the clinician UI. "
        "Implements ADR-002: Postgres is the system of record; every write projects matching "
        "RDF triples into the graph only on successful commit. Every endpoint except `/health` "
        "requires `Authorization: Bearer <token>` -- click **Authorize** above to set it once "
        "for every request below.\n\n"
        "See `conductor/tracks/retrieval-service_20260904/spec.md` for the full requirements and "
        "`retrieval/README.md` for a quickstart."
    ),
)
app.include_router(writes_router)
app.include_router(reads_router)


@app.get(
    "/health",
    summary="Health check (no auth)",
)
async def health() -> JSONResponse:
    """Deliberately unauthenticated -- a health check that itself requires a
    credential can't be used by infra (Docker HEALTHCHECK, a load balancer,
    an uptime monitor) that has no reason to hold one.

    Checks Postgres and Oxigraph connectivity explicitly, each with its own
    short timeout (db.check_connection, graph.check_connection) -- a caller
    deciding whether to route traffic here needs to know whether this
    service can actually do its job, not just that uvicorn is listening.
    200 when both are reachable; 503 (not 200-with-a-degraded-body-only) so
    a naive `curl -f` health check, or Docker's own HEALTHCHECK using one,
    correctly treats this as unhealthy without parsing the response body.
    """
    postgres_ok = db.check_connection()
    oxigraph_ok = await graph.check_connection()
    healthy = postgres_ok and oxigraph_ok
    body = {
        "status": "ok" if healthy else "degraded",
        "postgres": "ok" if postgres_ok else "unreachable",
        "oxigraph": "ok" if oxigraph_ok else "unreachable",
    }
    return JSONResponse(
        status_code=status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE,
        content=body,
    )
