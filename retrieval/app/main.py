"""Retrieval service -- FastAPI app.

The write endpoints (FR2, the ADR-002 projector) live in routes.py. Read
endpoints (FR3) live in reads.py. Auth (FR7) is applied per-router, not at
the app level, so /health can stay unauthenticated -- see auth.py.
"""

from fastapi import FastAPI

from .reads import router as reads_router
from .routes import router as writes_router

app = FastAPI(title="Retrieval Service")
app.include_router(writes_router)
app.include_router(reads_router)


@app.get("/health")
async def health() -> dict[str, str]:
    """Deliberately unauthenticated -- a health check that itself requires a
    credential can't be used by infra (Docker HEALTHCHECK, a load balancer,
    an uptime monitor) that has no reason to hold one. No DB/graph
    dependency either: this only proves the app process is up."""
    return {"status": "ok"}
