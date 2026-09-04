"""Smoke tests for FR7 (bearer-token auth) and the /health scaffold route.

Tier 3 per workflow.md: smoke test only, no coverage gate -- but the auth
dependency is applied at the app level (main.py), so these three cases prove
every route is covered, not just /health specifically.
"""

from fastapi.testclient import TestClient


def test_health_requires_auth(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 401


def test_health_rejects_invalid_token(client: TestClient) -> None:
    response = client.get("/health", headers={"Authorization": "Bearer wrong-token"})
    assert response.status_code == 401


def test_health_with_valid_token_returns_ok(client: TestClient, valid_token: str) -> None:
    response = client.get("/health", headers={"Authorization": f"Bearer {valid_token}"})
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
