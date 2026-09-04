"""Retrieval service -- FastAPI app.

The write endpoints (FR2, the ADR-002 projector) live in routes.py. Read
endpoints (FR3) land in Phase 4.
"""

from fastapi import Depends, FastAPI

from .auth import require_bearer_token
from .routes import router

app = FastAPI(title="Retrieval Service", dependencies=[Depends(require_bearer_token)])
app.include_router(router)


@app.get("/health")
async def health() -> dict[str, str]:
    """No DB/graph dependency -- proves the app boots and auth is enforced."""
    return {"status": "ok"}
