"""spec.md FR2's partial-failure contract: a Postgres commit that succeeds,
followed by a graph write that fails, must leave the Postgres row intact and
report the failure distinctly -- never a silent 200 that hides a missing
triple. Simulated by monkeypatching graph.push_triples to raise, since
actually taking Oxigraph down mid-test would make this test's outcome depend
on container orchestration timing rather than the code path being tested.
"""

from __future__ import annotations

import uuid

import psycopg
import pytest
from fastapi.testclient import TestClient

from app import graph
from app.config import settings
from app.main import app
from tests.adapters import to_decision_in, to_override_in, to_score_in
from tests.fixtures import make_decision, make_override, make_score


def _run_id() -> str:
    return f"run-test-{uuid.uuid4().hex[:8]}"


def _pg_conn() -> psycopg.Connection:
    return psycopg.connect(settings.retrieval_db_url)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def auth_headers() -> dict[str, str]:
    token = next(iter(settings.valid_tokens))
    return {"Authorization": f"Bearer {token}"}


def test_score_row_persists_when_graph_projection_fails(
    client: TestClient, auth_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _boom(triples: list, graph_iri: str) -> None:
        raise RuntimeError("simulated Oxigraph outage")

    monkeypatch.setattr(graph, "push_triples", _boom)

    payload = to_score_in(make_score(1, run_id=_run_id()))
    response = client.post("/scores", json=payload.model_dump(mode="json"), headers=auth_headers)

    # Not a silent 200, and not a plain 5xx that reads as "nothing happened"
    # either -- 207 reports exactly what did and didn't succeed.
    assert response.status_code == 207
    body = response.json()
    assert body["status"] == "postgres_committed_graph_projection_failed"
    assert "simulated Oxigraph outage" in body["detail"]

    # Postgres is the system of record (ADR-002) -- the row must still be there.
    with _pg_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM agent.agent_scores WHERE run_id = %s AND agent_name = %s "
            "AND hospital_hipe = %s AND pathway_number = %s",
            (payload.run_id, payload.agent_name, payload.hospital_hipe, payload.pathway_number),
        ).fetchone()
    assert row is not None


def test_decision_rows_persist_when_graph_projection_fails(
    client: TestClient, auth_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _boom(triples: list, graph_iri: str) -> None:
        raise RuntimeError("simulated Oxigraph outage")

    monkeypatch.setattr(graph, "push_triples", _boom)

    payload = to_decision_in(make_decision(2, run_id=_run_id(), cohort_size=2))
    response = client.post(
        "/decisions", json=payload.model_dump(mode="json"), headers=auth_headers
    )

    assert response.status_code == 207
    assert response.json()["status"] == "postgres_committed_graph_projection_failed"
    with _pg_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM agent.decisions WHERE decision_id = %s", (payload.decision_id,)
        ).fetchone()
    assert row is not None


def test_override_row_persists_when_graph_projection_fails(
    client: TestClient, auth_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id = _run_id()
    decision = make_decision(3, run_id=run_id, cohort_size=1)
    decision_payload = to_decision_in(decision)
    client.post("/decisions", json=decision_payload.model_dump(mode="json"), headers=auth_headers)

    async def _boom(triples: list, graph_iri: str) -> None:
        raise RuntimeError("simulated Oxigraph outage")

    monkeypatch.setattr(graph, "push_triples", _boom)

    override_payload = to_override_in(make_override(3, decision=decision))
    response = client.post(
        "/overrides", json=override_payload.model_dump(mode="json"), headers=auth_headers
    )

    assert response.status_code == 207
    assert response.json()["status"] == "postgres_committed_graph_projection_failed"
    with _pg_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM agent.overrides WHERE override_id = %s",
            (override_payload.override_id,),
        ).fetchone()
    assert row is not None


class TestPostgresFailureNeverAttemptsGraphWrite:
    def test_decision_fk_violation_returns_400_before_graph_write(
        self, client: TestClient, auth_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        called = False

        async def _spy(triples: list, graph_iri: str) -> None:
            nonlocal called
            called = True

        monkeypatch.setattr(graph, "push_triples", _spy)

        payload = to_decision_in(make_decision(4, run_id=_run_id(), cohort_size=1))
        body = payload.model_dump(mode="json")
        # rule_id that doesn't exist in core.ref_rules -- violates the FK
        # rule_checks_rule_id_fkey, a real Postgres constraint no Pydantic
        # validator can catch.
        body["rankings"][0]["rule_checks"] = [
            {"rule_id": "RULE-DOES-NOT-EXIST", "passed": True, "detail": None}
        ]

        response = client.post("/decisions", json=body, headers=auth_headers)

        assert response.status_code == 400
        assert called is False
