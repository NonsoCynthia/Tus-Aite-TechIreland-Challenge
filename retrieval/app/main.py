"""Retrieval service -- FastAPI app skeleton.

Phase 1 of conductor/tracks/retrieval-service_20260904/plan.md: scaffold and
auth only. The write/read endpoints (FR2-FR4) land in later phases.
"""

from fastapi import Depends, FastAPI

from .auth import require_bearer_token

app = FastAPI(title="Retrieval Service", dependencies=[Depends(require_bearer_token)])


@app.get("/health")
async def health() -> dict[str, str]:
    """No DB/graph dependency -- proves the app boots and auth is enforced."""
    return {"status": "ok"}
