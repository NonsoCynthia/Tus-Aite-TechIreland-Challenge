"""retrieval_client.py tests: request building against
retrieval-service_20260904's documented contract, mocked via
httpx.MockTransport -- no live service needed. tools.py's own tests mock
this client entirely (a fake standing in for the whole class); these tests
instead verify the client itself builds the right requests.
"""

from __future__ import annotations

import httpx
import pytest

from orchestrator_agent.retrieval_client import RetrievalClient, RetrievalClientError


def _client(handler: httpx.MockTransport) -> RetrievalClient:
    return RetrievalClient(
        base_url="http://retrieval.test", bearer_token="tok-123", transport=handler
    )


class TestGetReferralContext:
    def test_builds_the_documented_path_and_sends_the_bearer_token(self) -> None:
        captured: dict[str, httpx.Request] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["request"] = request
            return httpx.Response(200, json={"referral": {}})

        with _client(httpx.MockTransport(handler)) as client:
            body = client.get_referral_context("9001", "PW-9001-000007")

        assert body == {"referral": {}}
        request = captured["request"]
        assert request.url.path == "/referrals/9001/PW-9001-000007/context"
        assert request.headers["Authorization"] == "Bearer tok-123"

    def test_raises_on_an_unexpected_status(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404, text="not found")

        with _client(httpx.MockTransport(handler)) as client:
            with pytest.raises(RetrievalClientError):
                client.get_referral_context("9001", "PW-nope")


class TestGetWaitCounters:
    def test_sends_as_of_date_as_a_query_param(self) -> None:
        captured: dict[str, httpx.Request] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["request"] = request
            return httpx.Response(200, json={"adjusted_wait_days": 12})

        with _client(httpx.MockTransport(handler)) as client:
            client.get_wait_counters("9001", "PW-1", "2026-08-30")

        request = captured["request"]
        assert request.url.path == "/referrals/9001/PW-1/wait-counters"
        assert request.url.params["as_of_date"] == "2026-08-30"


class TestGetCohort:
    def test_builds_the_documented_path(self) -> None:
        captured: dict[str, httpx.Request] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["request"] = request
            return httpx.Response(200, json={"referrals": []})

        with _client(httpx.MockTransport(handler)) as client:
            client.get_cohort("9001", "2026-08-30")

        assert captured["request"].url.path == "/hospitals/9001/cohort/2026-08-30"


class TestGetDecision:
    def test_builds_the_documented_path(self) -> None:
        captured: dict[str, httpx.Request] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["request"] = request
            return httpx.Response(200, json={"decision": "x"})

        with _client(httpx.MockTransport(handler)) as client:
            client.get_decision("9001", "2026-08-30")

        assert captured["request"].url.path == "/decisions/9001/2026-08-30"


class TestGetEvidence:
    def test_omits_role_by_default(self) -> None:
        captured: dict[str, httpx.Request] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["request"] = request
            return httpx.Response(200, json={"evidence": []})

        with _client(httpx.MockTransport(handler)) as client:
            client.get_evidence("9001", "2026-08-30", "PW-1")

        request = captured["request"]
        assert request.url.path == "/evidence/9001/2026-08-30/PW-1"
        assert "role" not in request.url.params

    def test_passes_role_as_a_query_param_when_given(self) -> None:
        captured: dict[str, httpx.Request] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["request"] = request
            return httpx.Response(200, json={"evidence": []})

        with _client(httpx.MockTransport(handler)) as client:
            client.get_evidence("9001", "2026-08-30", "PW-1", role="urgency")

        assert captured["request"].url.params["role"] == "urgency"
