"""Bearer-token authentication (spec.md FR7).

Applied as an app-level FastAPI dependency (see main.py) so every route is
covered without relying on each handler remembering to add it, and so a
missing/invalid token is rejected before any handler logic runs -- including
before any Postgres or Oxigraph access.
"""

from fastapi import Header, HTTPException, status

from .config import settings


async def require_bearer_token(authorization: str | None = Header(default=None)) -> None:
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, detail="Missing or malformed Authorization header"
        )
    token = authorization.removeprefix("Bearer ").strip()
    if token not in settings.valid_tokens:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid bearer token")
