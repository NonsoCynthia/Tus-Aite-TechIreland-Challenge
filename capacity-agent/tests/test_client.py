"""RetrievalClient tests (NFR2, Tier 2): request/response handling against
retrieval-service_20260904's documented contract, mocked via
httpx.MockTransport so these run with no live service (spec.md FR9/FR2).
The genuine round-trip against a running retrieval service is
test_run_integration.py, which skips cleanly when that service isn't up.
"""

from __future__ import annotations

import json
from datetime import date

import httpx
import pytest

from capacity_agent.client import (
    GraphProjectionFailedError,
    ReferralNotFoundError,
    RetrievalClient,
    RetrievalServiceError,
)
from capacity_agent.scoring import Citation


def _client(handler: httpx.MockTransport) -> RetrievalClient:
    return RetrievalClient(
        base_url="http://retrieval.test", bearer_token="tok-123", transport=handler
    )


class TestGetReferralContext:
    def test_sends_bearer_token_and_returns_json_on_200(self) -> None:
        captured: dict[str, httpx.Request] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["request"] = request
            return httpx.Response(200, json={"referral": {"hospital_hipe": "9001"}})

        with _client(httpx.MockTransport(handler)) as client:
            body = client.get_referral_context("9001", "PW-9001-000007")

        assert body == {"referral": {"hospital_hipe": "9001"}}
        request = captured["request"]
        assert request.url.path == "/referrals/9001/PW-9001-000007/context"
        assert request.headers["Authorization"] == "Bearer tok-123"

    def test_raises_referral_not_found_on_404(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404, json={"detail": "no such referral"})

        with _client(httpx.MockTransport(handler)) as client:
            with pytest.raises(ReferralNotFoundError):
                client.get_referral_context("9001", "PW-nope")

    def test_raises_retrieval_service_error_on_unexpected_status(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, text="boom")

        with _client(httpx.MockTransport(handler)) as client:
            with pytest.raises(RetrievalServiceError):
                client.get_referral_context("9001", "PW-9001-000007")


class TestGetCohort:
    def test_builds_the_documented_path(self) -> None:
        captured: dict[str, httpx.Request] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["request"] = request
            return httpx.Response(200, json={"referrals": []})

        with _client(httpx.MockTransport(handler)) as client:
            body = client.get_cohort("9001", date(2026, 8, 30))

        assert body == {"referrals": []}
        assert captured["request"].url.path == "/hospitals/9001/cohort/2026-08-30"


class TestGetScoresForRun:
    def test_builds_the_documented_path(self) -> None:
        captured: dict[str, httpx.Request] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["request"] = request
            return httpx.Response(200, json={"scores": {}})

        with _client(httpx.MockTransport(handler)) as client:
            body = client.get_scores_for_run("run-0001", "9001")

        assert body == {"scores": {}}
        assert captured["request"].url.path == "/runs/run-0001/hospitals/9001/scores"


class TestPostScore:
    def test_sends_the_documented_payload_shape(self) -> None:
        captured: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["request"] = request
            captured["json"] = json.loads(request.content)
            return httpx.Response(200, json={"status": "ok"})

        with _client(httpx.MockTransport(handler)) as client:
            client.post_score(
                run_id="run-0001",
                agent_name="capacity",
                hospital_hipe="9001",
                pathway_number="PW-9001-000007",
                as_of_date=date(2026, 8, 30),
                score=0.42,
                method="capacity-ward-clinic-pressure-v1",
                agent_version="capacity-agent-0.1.0",
                citations=[Citation("bed_status", "9001/W01/2026-08-16%2009%3A16%3A00")],
            )

        request = captured["request"]
        assert isinstance(request, httpx.Request)
        assert request.url.path == "/scores"
        assert request.method == "POST"
        body = captured["json"]
        assert isinstance(body, dict)
        assert body["run_id"] == "run-0001"
        assert body["agent_name"] == "capacity"
        assert body["score"] == 0.42
        assert body["as_of_date"] == "2026-08-30"
        assert body["citations"] == [
            {"evidence_type": "bed_status", "evidence_key": "9001/W01/2026-08-16%2009%3A16%3A00"}
        ]

    def test_raises_graph_projection_failed_on_207_but_row_is_written(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                207,
                json={
                    "status": "postgres_committed_graph_projection_failed",
                    "detail": "simulated Oxigraph outage",
                },
            )

        with _client(httpx.MockTransport(handler)) as client:
            with pytest.raises(GraphProjectionFailedError) as exc_info:
                client.post_score(
                    run_id="run-0001",
                    agent_name="capacity",
                    hospital_hipe="9001",
                    pathway_number="PW-9001-000007",
                    as_of_date=date(2026, 8, 30),
                    score=0.42,
                    method="m",
                    agent_version="v",
                    citations=[Citation("bed_status", "9001/W01/2026-08-16%2009%3A16%3A00")],
                )
        assert "simulated Oxigraph outage" in str(exc_info.value)

    def test_raises_retrieval_service_error_on_400(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(400, json={"detail": "constraint violation"})

        with _client(httpx.MockTransport(handler)) as client:
            with pytest.raises(RetrievalServiceError):
                client.post_score(
                    run_id="run-0001",
                    agent_name="capacity",
                    hospital_hipe="9001",
                    pathway_number="PW-9001-000007",
                    as_of_date=date(2026, 8, 30),
                    score=0.42,
                    method="m",
                    agent_version="v",
                    citations=[Citation("bed_status", "9001/W01/2026-08-16%2009%3A16%3A00")],
                )
