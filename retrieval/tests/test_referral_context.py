"""spec.md FR9: GET /referrals/{hospital_hipe}/{pathway_number}/context --
the input-gathering endpoint agents use to judge one referral, as opposed to
FR3's endpoints which cover already-decided *output*.

Unlike the write-path tests, this can't insert its own fixture data: `core.*`
is genuinely read-only for this service (retrieval_rw has SELECT only,
migration 007, deliberately -- NFR3), and rightly so, since it's the
Morph-KGC/dataset loader's job to populate it, not this service's. The
real-data tests below skip cleanly (not fail) if the full dataset hasn't
been loaded into this environment's Postgres, rather than depending on it.
"""

from __future__ import annotations

import psycopg
import pytest
from fastapi.testclient import TestClient

from app.config import settings


@pytest.fixture
def client() -> TestClient:
    from app.main import app

    return TestClient(app)


@pytest.fixture
def auth_headers() -> dict[str, str]:
    token = next(iter(settings.valid_tokens))
    return {"Authorization": f"Bearer {token}"}


def _find_a_real_referral() -> tuple[str, str] | None:
    """Returns a real (hospital_hipe, pathway_number) with at least one
    observation, condition and triage event, if the full dataset is loaded
    in this environment -- None otherwise."""
    with psycopg.connect(settings.retrieval_db_url) as conn:
        row = conn.execute(
            """
            SELECT o.hospital_hipe, o.pathway_number
            FROM core.observations o
            JOIN core.conditions c
              ON c.hospital_hipe = o.hospital_hipe AND c.pathway_number = o.pathway_number
            JOIN core.triage_events t
              ON t.hospital_hipe = o.hospital_hipe AND t.pathway_number = o.pathway_number
            LIMIT 1
            """
        ).fetchone()
    return (row[0].strip(), row[1]) if row else None


class TestReferralContextNotFound:
    def test_unknown_referral_returns_404(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        response = client.get(
            "/referrals/9099/PW-DOES-NOT-EXIST/context", headers=auth_headers
        )
        assert response.status_code == 404

    def test_requires_auth(self, client: TestClient) -> None:
        response = client.get("/referrals/9099/PW-DOES-NOT-EXIST/context")
        assert response.status_code == 401


class TestReferralContextRealData:
    def test_returns_clinical_and_capacity_data_for_a_real_referral(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        real = _find_a_real_referral()
        if real is None:
            pytest.skip("full dataset not loaded in this environment")
        hospital_hipe, pathway_number = real

        response = client.get(
            f"/referrals/{hospital_hipe}/{pathway_number}/context", headers=auth_headers
        )

        assert response.status_code == 200
        body = response.json()

        assert body["referral"]["hospital_hipe"] == hospital_hipe
        assert body["referral"]["pathway_number"] == pathway_number
        assert body["referral"]["specialty_hipe"]

        assert len(body["observations"]) >= 1
        obs = body["observations"][0]
        assert "obs_datetime" in obs
        # at least one vital sign column present, whatever its value
        assert any(k in obs for k in ("hr", "sbp", "dbp", "rr", "temp", "spo2"))

        assert len(body["conditions"]) >= 1
        assert "icd10am_code" in body["conditions"][0]

        assert len(body["triage_events"]) >= 1
        assert "triage_event_id" in body["triage_events"][0]

        capacity = body["capacity"]
        assert capacity["specialty_hipe"] == body["referral"]["specialty_hipe"]
        # every ward returned actually serves this specialty
        for ward in capacity["wards"]:
            assert "ward_id" in ward
        # at most one ward is marked primary
        assert sum(1 for w in capacity["wards"] if w["is_primary"]) <= 1

    def test_no_full_https_iris_leak_into_a_postgres_backed_response(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        # This endpoint doesn't touch the graph at all, but the same
        # response-hygiene bar applies (AC13's spirit) -- nothing here
        # should ever be a raw https:// IRI.
        real = _find_a_real_referral()
        if real is None:
            pytest.skip("full dataset not loaded in this environment")
        hospital_hipe, pathway_number = real

        response = client.get(
            f"/referrals/{hospital_hipe}/{pathway_number}/context", headers=auth_headers
        )
        assert "https://" not in response.text
