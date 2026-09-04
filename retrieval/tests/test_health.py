"""/health (Tier 3 smoke test): deliberately unauthenticated, so Docker
HEALTHCHECK / a load balancer / an uptime monitor can use it without holding
a credential -- see main.py. FR7's auth coverage lives in test_auth.py,
against a real protected endpoint instead.
"""

from fastapi.testclient import TestClient


def test_health_returns_ok_without_any_auth_header(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_returns_ok_even_with_a_bogus_token(client: TestClient) -> None:
    # Not just "doesn't require" auth -- confirms it doesn't inspect the
    # header at all, so a stale/wrong token a caller forgot to remove can't
    # accidentally break liveness checks.
    response = client.get("/health", headers={"Authorization": "Bearer wrong-token"})
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
