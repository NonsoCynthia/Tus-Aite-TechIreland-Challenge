"""RetrievalClient tests (NFR2, Tier 2): request/response handling against
retrieval-service_20260904's documented contract, mocked via
httpx.MockTransport so these run with no live service. The genuine round
trip is test_run_integration.py, which skips cleanly when the service isn't
up.

Per ADR-002 this client is the urgency agent's *only* interface to
Postgres/the graph -- there is deliberately no SPARQL or psycopg path to
test, because there is deliberately none to write.
"""

from __future__ import annotations

import json
from datetime import date

import httpx
import pytest

from urgency_agent.client import (
    GraphProjectionFailedError,
    ReferralNotFoundError,
    RetrievalClient,
    RetrievalServiceError,
)
from urgency_agent.scoring import Citation

_KEY = "9004/PW-9004-000286/2026-08-16%2009%3A16%3A00/hr"


def _client(handler: httpx.MockTransport) -> RetrievalClient:
    return RetrievalClient(
        base_url="http://retrieval.test", bearer_token="tok-123", transport=handler
    )


class TestGetReferralContext:
    def test_sends_bearer_token_and_returns_json_on_200(self) -> None:
        captured: dict[str, httpx.Request] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["request"] = request
            return httpx.Response(200, json={"referral": {"hospital_hipe": "9004"}})

        with _client(httpx.MockTransport(handler)) as client:
            body = client.get_referral_context("9004", "PW-9004-000286")

        assert body == {"referral": {"hospital_hipe": "9004"}}
        request = captured["request"]
        assert request.url.path == "/referrals/9004/PW-9004-000286/context"
        assert request.headers["Authorization"] == "Bearer tok-123"

    def test_raises_referral_not_found_on_404(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404, json={"detail": "no such referral"})

        with _client(httpx.MockTransport(handler)) as client:
            with pytest.raises(ReferralNotFoundError):
                client.get_referral_context("9004", "PW-nope")

    def test_raises_retrieval_service_error_on_unexpected_status(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, text="boom")

        with _client(httpx.MockTransport(handler)) as client:
            with pytest.raises(RetrievalServiceError):
                client.get_referral_context("9004", "PW-9004-000286")


class TestGetCohort:
    def test_builds_the_documented_path(self) -> None:
        captured: dict[str, httpx.Request] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["request"] = request
            return httpx.Response(200, json={"referrals": []})

        with _client(httpx.MockTransport(handler)) as client:
            body = client.get_cohort("9004", date(2026, 8, 30))

        assert body == {"referrals": []}
        assert captured["request"].url.path == "/hospitals/9004/cohort/2026-08-30"


class TestGetScoresForRun:
    def test_builds_the_documented_path(self) -> None:
        captured: dict[str, httpx.Request] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["request"] = request
            return httpx.Response(200, json={"scores": {}})

        with _client(httpx.MockTransport(handler)) as client:
            body = client.get_scores_for_run("run-0001", "9004")

        assert body == {"scores": {}}
        assert captured["request"].url.path == "/runs/run-0001/hospitals/9004/scores"


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
                hospital_hipe="9004",
                pathway_number="PW-9004-000286",
                as_of_date=date(2026, 8, 30),
                score=0.3,
                method="urgency-news2-v1",
                agent_version="urgency-agent-0.1.0",
                citations=[Citation("observation", _KEY)],
            )

        request = captured["request"]
        assert isinstance(request, httpx.Request)
        assert request.url.path == "/scores"
        assert request.method == "POST"
        body = captured["json"]
        assert isinstance(body, dict)
        assert body["run_id"] == "run-0001"
        assert body["score"] == 0.3
        assert body["as_of_date"] == "2026-08-30"
        assert body["citations"] == [{"evidence_type": "observation", "evidence_key": _KEY}]

    def test_always_writes_as_the_urgency_agent(self) -> None:
        """`agent_name` is not a caller's choice. `AgentName` is
        Literal["urgency", "capacity"] and a score written under the wrong
        name would be silently picked up by the coordinator as the other
        agent's judgement -- so this client hard-codes it rather than
        accepting it as a parameter, unlike capacity's, which took it."""
        captured: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["json"] = json.loads(request.content)
            return httpx.Response(200, json={"status": "ok"})

        with _client(httpx.MockTransport(handler)) as client:
            client.post_score(
                run_id="run-0001",
                hospital_hipe="9004",
                pathway_number="PW-9004-000286",
                as_of_date=date(2026, 8, 30),
                score=0.3,
                method="urgency-news2-v1",
                agent_version="urgency-agent-0.1.0",
                citations=[Citation("observation", _KEY)],
            )

        body = captured["json"]
        assert isinstance(body, dict)
        assert body["agent_name"] == "urgency"

    def test_raises_graph_projection_failed_on_207_but_row_is_written(self) -> None:
        """ADR-002's 207: Postgres committed, the graph projection then
        failed. The score row IS written and stands -- Postgres is the
        system of record -- so this is raised rather than swallowed, letting
        the caller log or retry the graph side out of band instead of
        assuming the audit trail is complete."""

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
                    hospital_hipe="9004",
                    pathway_number="PW-9004-000286",
                    as_of_date=date(2026, 8, 30),
                    score=0.3,
                    method="m",
                    agent_version="v",
                    citations=[Citation("observation", _KEY)],
                )
        assert "simulated Oxigraph outage" in str(exc_info.value)

    def test_raises_retrieval_service_error_on_400(self) -> None:
        """400 means nothing was written at all -- a different situation
        from the 207 above, and the caller must be able to tell them
        apart."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(400, json={"detail": "constraint violation"})

        with _client(httpx.MockTransport(handler)) as client:
            with pytest.raises(RetrievalServiceError):
                client.post_score(
                    run_id="run-0001",
                    hospital_hipe="9004",
                    pathway_number="PW-9004-000286",
                    as_of_date=date(2026, 8, 30),
                    score=0.3,
                    method="m",
                    agent_version="v",
                    citations=[Citation("observation", _KEY)],
                )
