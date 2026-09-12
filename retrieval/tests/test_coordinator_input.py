"""spec.md FR10: the coordinator's input -- which referrals need ranking
(GET /hospitals/.../cohort/...) and the scores already written for them
(GET /runs/.../hospitals/.../scores).

The cohort endpoint reads core.referral_daily, which -- like FR9's
referral-context endpoint -- is genuinely read-only for this service
(NFR3), so its real-data tests skip cleanly when the full dataset isn't
loaded, same pattern as test_referral_context.py. The scores endpoint reads
agent.agent_scores/agent_citations, which THIS service's own POST /scores
writes -- so those tests use the write path directly, no skip needed.
"""

from __future__ import annotations

import uuid
from datetime import date

import psycopg
import pytest
from app.config import settings
from app.main import app
from fastapi.testclient import TestClient

from tests.adapters import to_score_in
from tests.fixtures import make_score


def _run_id() -> str:
    return f"run-test-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def auth_headers() -> dict[str, str]:
    token = next(iter(settings.valid_tokens))
    return {"Authorization": f"Bearer {token}"}


def _find_a_real_hospital_day() -> tuple[str, date] | None:
    """Returns a real (hospital_hipe, as_of_date) with at least one
    non-removed referral, if the full dataset is loaded -- None otherwise."""
    with psycopg.connect(settings.retrieval_db_url) as conn:
        row = conn.execute(
            """
            SELECT hospital_hipe, as_of_date
            FROM core.referral_daily
            WHERE removal_date IS NULL
            LIMIT 1
            """
        ).fetchone()
    return (row[0].strip(), row[1]) if row else None


class TestCohort:
    def test_unknown_hospital_day_returns_empty_list_not_404(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        response = client.get("/hospitals/9099/cohort/2020-01-01", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["referrals"] == []

    def test_requires_auth(self, client: TestClient) -> None:
        response = client.get("/hospitals/9099/cohort/2020-01-01")
        assert response.status_code == 401

    def test_real_cohort_has_expected_shape_and_is_oldest_first(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        real = _find_a_real_hospital_day()
        if real is None:
            pytest.skip("full dataset not loaded in this environment")
        hospital_hipe, as_of_date = real

        response = client.get(
            f"/hospitals/{hospital_hipe}/cohort/{as_of_date.isoformat()}", headers=auth_headers
        )

        assert response.status_code == 200
        body = response.json()
        assert body["hospital_hipe"] == hospital_hipe
        referrals = body["referrals"]
        assert len(referrals) >= 1

        first = referrals[0]
        assert first["hospital_hipe"] == hospital_hipe
        for key in (
            "pathway_number",
            "specialty_hipe",
            "referral_date",
            "referral_state_valid_from",
            "adjusted_wait_days",
            "cpc",
            "currently_suspended",
            "crt_threshold_days",
            "crt_breached",
        ):
            assert key in first

        # oldest-referral-first (namespaces.md / tech-stack.md tie-break rule)
        dates = [r["referral_date"] for r in referrals]
        assert dates == sorted(dates)

    def test_crt_breach_is_computed_only_when_a_threshold_applies(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        """CPC 1 (Urgent, crt_days=28) and CPC 3 (Semi-Urgent, crt_days=91) get a
        real true/false; CPC 2/4 (Routine/Excluded) and untriaged referrals get
        `null` for both fields -- core.ref_codes has no crt_days for them."""
        real = _find_a_real_hospital_day()
        if real is None:
            pytest.skip("full dataset not loaded in this environment")
        hospital_hipe, as_of_date = real

        response = client.get(
            f"/hospitals/{hospital_hipe}/cohort/{as_of_date.isoformat()}", headers=auth_headers
        )
        referrals = response.json()["referrals"]

        for r in referrals:
            if r["cpc"] in (1, 3):
                assert r["crt_threshold_days"] in (28, 91)
                assert isinstance(r["crt_breached"], bool)
                assert r["crt_breached"] == (r["adjusted_wait_days"] > r["crt_threshold_days"])
            else:
                assert r["crt_threshold_days"] is None
                assert r["crt_breached"] is None

    def test_no_full_https_iris_leak_into_a_postgres_backed_response(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        real = _find_a_real_hospital_day()
        if real is None:
            pytest.skip("full dataset not loaded in this environment")
        hospital_hipe, as_of_date = real

        response = client.get(
            f"/hospitals/{hospital_hipe}/cohort/{as_of_date.isoformat()}", headers=auth_headers
        )
        assert "https://" not in response.text


class TestScoresForRun:
    def test_no_scores_written_yet_returns_empty_dict_not_404(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        response = client.get(
            f"/runs/{_run_id()}/hospitals/9001/scores", headers=auth_headers
        )
        assert response.status_code == 200
        assert response.json()["scores"] == {}

    def test_requires_auth(self, client: TestClient) -> None:
        response = client.get("/runs/some-run/hospitals/9001/scores")
        assert response.status_code == 401

    def test_written_scores_come_back_grouped_by_pathway_then_agent(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        run_id = _run_id()
        # Same seed -> identical hospital_hipe/pathway_number regardless of
        # agent_name (fixed before the agent branch runs, see fixtures.py) --
        # so these two calls describe the same referral, scored by both agents.
        urgency = to_score_in(make_score(40, run_id=run_id, agent_name="urgency"))
        capacity = to_score_in(make_score(40, run_id=run_id, agent_name="capacity"))
        assert urgency.pathway_number == capacity.pathway_number

        for payload in (urgency, capacity):
            response = client.post(
                "/scores", json=payload.model_dump(mode="json"), headers=auth_headers
            )
            assert response.status_code == 200

        response = client.get(
            f"/runs/{run_id}/hospitals/{urgency.hospital_hipe}/scores", headers=auth_headers
        )

        assert response.status_code == 200
        scores = response.json()["scores"]
        entry = scores[urgency.pathway_number]
        assert float(entry["urgency"]["score"]) == pytest.approx(urgency.score)
        assert float(entry["capacity"]["score"]) == pytest.approx(capacity.score)
        assert entry["urgency"]["citations"]
        assert entry["capacity"]["citations"]

    def test_score_is_returned_as_a_json_number_not_a_string(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        # agent_scores.score is a Postgres `numeric`; psycopg returns a
        # Decimal, which serialises to a JSON *string* if this route lets
        # FastAPI infer a response_model from its `-> dict[str, Any]`
        # annotation (Pydantic's own Decimal-under-Any encoding) instead of
        # going through `jsonable_encoder` directly (`response_model=None`).
        # A consumer doing arithmetic on this field -- the coordinator's
        # `priority.py` multiplies it -- gets a `TypeError`, not a wrong
        # number, so this must fail loudly rather than coerce and pass.
        run_id = _run_id()
        payload = to_score_in(make_score(42, run_id=run_id, agent_name="urgency"))
        client.post("/scores", json=payload.model_dump(mode="json"), headers=auth_headers)

        response = client.get(
            f"/runs/{run_id}/hospitals/{payload.hospital_hipe}/scores", headers=auth_headers
        )

        score = response.json()["scores"][payload.pathway_number]["urgency"]["score"]
        assert isinstance(score, float), (
            f"score must be a JSON number, got {type(score)}: {score!r}"
        )

    def test_only_written_agent_appears_when_the_other_hasnt_scored_yet(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        run_id = _run_id()
        urgency = to_score_in(make_score(41, run_id=run_id, agent_name="urgency"))
        client.post("/scores", json=urgency.model_dump(mode="json"), headers=auth_headers)

        response = client.get(
            f"/runs/{run_id}/hospitals/{urgency.hospital_hipe}/scores", headers=auth_headers
        )

        entry = response.json()["scores"][urgency.pathway_number]
        assert "urgency" in entry
        assert "capacity" not in entry
