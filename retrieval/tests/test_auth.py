"""FR7: every endpoint except /health (test_health.py) requires
Authorization: Bearer. Auth is applied per-router now (routes.py, reads.py),
not at the app level, so this proves the dependency is actually wired on
both routers rather than assuming it from one endpoint's behaviour.
"""

import pytest
from fastapi.testclient import TestClient


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/scores"),
        ("POST", "/decisions"),
        ("POST", "/overrides"),
        ("GET", "/referrals/9001/PW-9001-000001/wait-counters?as_of_date=2026-09-04"),
        ("GET", "/decisions/9001/2026-09-04"),
        ("GET", "/evidence/9001/2026-09-04/PW-9001-000001"),
    ],
)
def test_endpoint_requires_auth(client: TestClient, method: str, path: str) -> None:
    response = client.request(method, path, json={} if method == "POST" else None)
    assert response.status_code == 401


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/scores"),
        ("GET", "/decisions/9001/2026-09-04"),
    ],
)
def test_endpoint_rejects_invalid_token(client: TestClient, method: str, path: str) -> None:
    response = client.request(
        method, path, json={} if method == "POST" else None,
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert response.status_code == 401
