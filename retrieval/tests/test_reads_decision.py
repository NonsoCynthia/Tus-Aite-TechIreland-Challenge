"""spec.md FR3 (decision/evidence lookup) and NFR2 (no score/decision
without cited evidence) -- exercised against data written by Phase 3's own
write endpoints, not hand-inserted fixtures, so this tests the whole
write-then-read loop, not just the read side in isolation.
"""

from __future__ import annotations

import random
import uuid
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.schemas import DecisionIn
from tests.adapters import to_decision_in
from tests.fixtures import make_decision


def _run_id() -> str:
    return f"run-test-{uuid.uuid4().hex[:8]}"


def _unique_as_of_date() -> date:
    # decision_iri is keyed only by (hospital_hipe, as_of_date) -- namespaces.md
    # #4: "one per hospital per day" -- so two different test-written decisions
    # that land on the same day accumulate onto the SAME graph node rather than
    # being independent. fixtures.py's own as_of_date range is a handful of
    # fixed values, which collides across repeated test runs in one session
    # (the graph, unlike Postgres rows, isn't cleared between runs). A wide
    # random offset from today keeps each test run's decision graph-isolated.
    return date.today() + timedelta(days=random.randint(1000, 999_000))


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def auth_headers() -> dict[str, str]:
    token = next(iter(settings.valid_tokens))
    return {"Authorization": f"Bearer {token}"}


def _write_decision(
    client: TestClient, auth_headers: dict[str, str], seed: int, cohort_size: int
) -> DecisionIn:
    payload = to_decision_in(make_decision(seed, run_id=_run_id(), cohort_size=cohort_size))
    payload = payload.model_copy(update={"as_of_date": _unique_as_of_date()})
    response = client.post(
        "/decisions", json=payload.model_dump(mode="json"), headers=auth_headers
    )
    assert response.status_code == 200
    return payload


class TestGetDecision:
    def test_reconstructs_every_placement_with_evidence(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        payload = _write_decision(client, auth_headers, seed=20, cohort_size=3)

        response = client.get(
            f"/decisions/{payload.hospital_hipe}/{payload.as_of_date.isoformat()}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        body = response.json()
        assert len(body["placements"]) == len(payload.rankings)

        by_pathway = {p["pathway_number"]: p for p in body["placements"]}
        for ranking in payload.rankings:
            placement = by_pathway[ranking.pathway_number]
            assert placement["position"] == ranking.position
            # NFR2: never a placement with no evidence.
            assert len(placement["evidence"]) > 0
            assert len(placement["evidence"]) == len(ranking.citations)
            got_roles = sorted(e["role"] for e in placement["evidence"])
            expected_roles = sorted(c.role for c in ranking.citations)
            assert got_roles == expected_roles

    def test_unknown_decision_returns_404(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        response = client.get("/decisions/9099/2020-01-01", headers=auth_headers)
        assert response.status_code == 404


class TestEvidenceForPlacement:
    def test_filters_to_one_role(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        payload = _write_decision(client, auth_headers, seed=21, cohort_size=1)
        ranking = payload.rankings[0]
        # pick a role that's actually present on this ranking's citations
        role = ranking.citations[0].role

        response = client.get(
            f"/evidence/{ranking.hospital_hipe}/{payload.as_of_date.isoformat()}/"
            f"{ranking.pathway_number}",
            params={"role": role},
            headers=auth_headers,
        )

        assert response.status_code == 200
        body = response.json()
        assert all(e["role"] == role for e in body["evidence"])
        expected_count = sum(1 for c in ranking.citations if c.role == role)
        assert len(body["evidence"]) == expected_count

class TestNFR2EvidenceCompletenessGuard:
    """spec.md NFR2: no score or decision is ever returned without its cited
    evidence. Enforced at write time (schemas.py's citations min_length=1 on
    both ScoreIn and RankingIn, backing eat:cites' 1..n cardinality) --
    proven here by showing the write-time rejection, which is what makes the
    read-side guarantee actually hold rather than just being hoped for.
    """

    def test_ranking_with_no_citations_is_rejected(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        payload = to_decision_in(make_decision(23, run_id=_run_id(), cohort_size=1))
        body = payload.model_dump(mode="json")
        body["rankings"][0]["citations"] = []

        response = client.post("/decisions", json=body, headers=auth_headers)

        assert response.status_code == 422

    def test_no_role_returns_all_citations(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        payload = _write_decision(client, auth_headers, seed=22, cohort_size=1)
        ranking = payload.rankings[0]

        response = client.get(
            f"/evidence/{ranking.hospital_hipe}/{payload.as_of_date.isoformat()}/"
            f"{ranking.pathway_number}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        assert len(response.json()["evidence"]) == len(ranking.citations)
