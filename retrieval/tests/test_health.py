"""/health: deliberately unauthenticated (so Docker HEALTHCHECK / a load
balancer / an uptime monitor can use it without holding a credential -- see
main.py), but explicitly checks Postgres and Oxigraph connectivity rather
than just proving the process is up. FR7's auth coverage for every other
endpoint lives in test_auth.py.
"""

import pytest
from fastapi.testclient import TestClient

from app import db, graph


def test_health_returns_ok_without_any_auth_header(client: TestClient) -> None:
    # Real Postgres and Oxigraph are up in this test environment (Tier 2
    # round-trip tests elsewhere depend on it), so this exercises the real
    # connectivity checks, not mocks.
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body == {"status": "ok", "postgres": "ok", "oxigraph": "ok"}


def test_health_returns_ok_even_with_a_bogus_token(client: TestClient) -> None:
    # Not just "doesn't require" auth -- confirms it doesn't inspect the
    # header at all, so a stale/wrong token a caller forgot to remove can't
    # accidentally break liveness checks.
    response = client.get("/health", headers={"Authorization": "Bearer wrong-token"})
    assert response.status_code == 200


def test_health_reports_503_when_postgres_unreachable(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(db, "check_connection", lambda: False)

    response = client.get("/health")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["postgres"] == "unreachable"
    assert body["oxigraph"] == "ok"


def test_health_reports_503_when_oxigraph_unreachable(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _unreachable() -> bool:
        return False

    monkeypatch.setattr(graph, "check_connection", _unreachable)

    response = client.get("/health")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["postgres"] == "ok"
    assert body["oxigraph"] == "unreachable"
