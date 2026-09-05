"""Integration tests for the write endpoints (spec.md FR2), against the real
Postgres and Oxigraph this container runs alongside -- not mocks. Round-trip
tests count as the bar for Tier 2 (workflow.md), and "the row exists in
Postgres and the triples exist in the graph" is the actual claim FR2 makes.

Each test uses a fresh, uuid-suffixed run_id so re-running the suite never
collides with a previous run's rows (agent_scores/agent_citations key on
run_id; decision_id folds run_id in too -- see fixtures.py).
"""

from __future__ import annotations

import uuid

import httpx
import psycopg
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from tests.adapters import to_decision_in, to_override_in, to_score_in
from tests.fixtures import make_decision, make_override, make_score


def _run_id() -> str:
    return f"run-test-{uuid.uuid4().hex[:8]}"


def _pg_conn() -> psycopg.Connection:
    return psycopg.connect(settings.retrieval_db_url)


_ASK_PREFIXES = "PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>\n"


def _ask(query: str) -> bool:
    response = httpx.post(
        settings.oxigraph_query_url,
        data={"query": _ASK_PREFIXES + query},
        headers={"Accept": "application/sparql-results+json"},
        timeout=10.0,
    )
    response.raise_for_status()
    return bool(response.json()["boolean"])


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def auth_headers() -> dict[str, str]:
    token = next(iter(settings.valid_tokens))
    return {"Authorization": f"Bearer {token}"}


class TestCreateScore:
    def test_writes_postgres_row(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        payload = to_score_in(make_score(1, run_id=_run_id()))
        body = payload.model_dump(mode="json")

        response = client.post("/scores", json=body, headers=auth_headers)

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        with _pg_conn() as conn:
            row = conn.execute(
                "SELECT score, method, agent_version FROM agent.agent_scores "
                "WHERE run_id = %s AND agent_name = %s AND hospital_hipe = %s "
                "AND pathway_number = %s",
                (payload.run_id, payload.agent_name, payload.hospital_hipe, payload.pathway_number),
            ).fetchone()
        assert row is not None
        assert float(row[0]) == payload.score
        assert row[1] == payload.method

    def test_writes_graph_triples(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        from app import iri

        payload = to_score_in(make_score(2, run_id=_run_id()))
        client.post("/scores", json=payload.model_dump(mode="json"), headers=auth_headers)

        score_iri = iri.score_iri(
            payload.run_id, payload.hospital_hipe, payload.pathway_number, payload.agent_name
        )
        graph_iri = iri.run_graph(payload.run_id)
        assert _ask(f"ASK {{ GRAPH <{graph_iri}> {{ <{score_iri}> a <{iri.eat('Score')}> }} }}")
        score_value_predicate = iri.eat("scoreValue")
        assert _ask(
            f"ASK {{ GRAPH <{graph_iri}> {{ <{score_iri}> <{score_value_predicate}> "
            f'"{payload.score}"^^xsd:decimal }} }}'
        )
        # every citation actually landed as a cites edge
        for citation in payload.citations:
            target = iri.evidence_iri(citation.evidence_type, citation.evidence_key)
            assert _ask(
                f"ASK {{ GRAPH <{graph_iri}> {{ <{score_iri}> <{iri.eat('cites')}> <{target}> }} }}"
            )


class TestCreateDecision:
    def test_writes_postgres_rows_and_graph_triples(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        from app import iri

        payload = to_decision_in(make_decision(3, run_id=_run_id(), cohort_size=2))

        response = client.post(
            "/decisions", json=payload.model_dump(mode="json"), headers=auth_headers
        )

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

        with _pg_conn() as conn:
            decision_row = conn.execute(
                "SELECT cohort_size FROM agent.decisions WHERE decision_id = %s",
                (payload.decision_id,),
            ).fetchone()
            ranking_rows = conn.execute(
                "SELECT position FROM agent.decision_rankings "
                "WHERE decision_id = %s ORDER BY position",
                (payload.decision_id,),
            ).fetchall()
            rule_check_rows = conn.execute(
                "SELECT rule_id FROM agent.rule_checks WHERE decision_id = %s",
                (payload.decision_id,),
            ).fetchall()
        assert decision_row is not None
        assert decision_row[0] == len(payload.rankings)
        assert [r[0] for r in ranking_rows] == [r.position for r in payload.rankings]
        expected_rule_checks = sum(len(r.rule_checks) for r in payload.rankings)
        assert len(rule_check_rows) == expected_rule_checks

        as_of = payload.as_of_date.isoformat()
        decision_iri = iri.decision_iri(payload.hospital_hipe, as_of)
        graph_iri = iri.run_graph(payload.run_id)
        decision_type = iri.eat("Decision")
        assert _ask(f"ASK {{ GRAPH <{graph_iri}> {{ <{decision_iri}> a <{decision_type}> }} }}")
        has_placement = iri.eat("hasPlacement")
        for ranking in payload.rankings:
            placement = iri.placement_iri(payload.hospital_hipe, as_of, ranking.pathway_number)
            assert _ask(
                f"ASK {{ GRAPH <{graph_iri}> {{ "
                f"<{decision_iri}> <{has_placement}> <{placement}> }} }}"
            )


class TestCreateOverride:
    def test_writes_postgres_row_and_graph_triple(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        from app import iri

        run_id = _run_id()
        decision_payload = to_decision_in(make_decision(4, run_id=run_id, cohort_size=2))
        decision_body = decision_payload.model_dump(mode="json")
        client.post("/decisions", json=decision_body, headers=auth_headers)

        decision = make_decision(4, run_id=run_id, cohort_size=2)
        override_payload = to_override_in(make_override(4, decision=decision))
        # decision_id must match what was actually inserted -- make_decision
        # with the same seed/run_id is deterministic (Phase 2), so it does.
        assert override_payload.decision_id == decision_payload.decision_id

        response = client.post(
            "/overrides", json=override_payload.model_dump(mode="json"), headers=auth_headers
        )

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        with _pg_conn() as conn:
            row = conn.execute(
                "SELECT reason FROM agent.overrides WHERE override_id = %s",
                (override_payload.override_id,),
            ).fetchone()
        assert row is not None
        assert row[0] == override_payload.reason

        override_iri = iri.override_iri(
            override_payload.hospital_hipe,
            decision_payload.as_of_date.isoformat(),
            override_payload.pathway_number,
            override_payload.override_id,
        )
        overrides_graph = iri.overrides_graph()
        override_type = iri.eat("Override")
        assert _ask(
            f"ASK {{ GRAPH <{overrides_graph}> {{ <{override_iri}> a <{override_type}> }} }}"
        )


class TestValidationRejectedBeforeAnyWrite:
    def test_score_out_of_range_returns_400_and_writes_nothing(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        run_id = _run_id()
        payload = to_score_in(make_score(5, run_id=run_id)).model_dump(mode="json")
        payload["score"] = 1.5  # violates as_score_range CHECK

        response = client.post("/scores", json=payload, headers=auth_headers)

        assert response.status_code == 422  # Pydantic rejects before the handler runs
        with _pg_conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM agent.agent_scores WHERE run_id = %s", (run_id,)
            ).fetchone()
        assert row is None
