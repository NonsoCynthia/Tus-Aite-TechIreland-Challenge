"""Retrieval service -- FastAPI app.

The write endpoints (FR2, the ADR-002 projector) live in routes.py. Read
endpoints (FR3) live in reads.py.
"""

from fastapi import Depends, FastAPI

from .auth import require_bearer_token
from .reads import router as reads_router
from .routes import router as writes_router

app = FastAPI(title="Retrieval Service", dependencies=[Depends(require_bearer_token)])
app.include_router(writes_router)
app.include_router(reads_router)


@app.get("/health")
async def health() -> dict[str, str]:
    """No DB/graph dependency -- proves the app boots and auth is enforced."""
    return {"status": "ok"}
