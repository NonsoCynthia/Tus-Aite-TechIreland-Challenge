"""Bearer-token authentication (spec.md FR7).

Applied per-router (routes.py, reads.py each carry
APIRouter(dependencies=[Depends(require_bearer_token)])) so every route on
them is covered without relying on each handler remembering to add it, and
so a missing/invalid token is rejected before any handler logic runs --
including before any Postgres or Oxigraph access. /health sits outside both
routers and stays unauthenticated (main.py).

Uses fastapi.security.HTTPBearer, not a plain Header dependency: that's what
registers a real OpenAPI security scheme, which is what makes Swagger UI
(/docs) show the padlock icons and an "Authorize" button instead of making
every caller retype the header by hand on every request they try.
`auto_error=False` because HTTPBearer's own default behaviour raises 403 on
a missing header; this project's contract (spec.md FR7, tested in
test_auth.py) is 401 for both missing and invalid tokens, so that path is
handled explicitly below instead.
"""

from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import settings

bearer_scheme = HTTPBearer(auto_error=False)


async def require_bearer_token(
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
) -> None:
    if credentials is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, detail="Missing or malformed Authorization header"
        )
    if credentials.credentials not in settings.valid_tokens:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid bearer token")
