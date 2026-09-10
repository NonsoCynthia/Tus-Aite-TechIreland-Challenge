import httpx
import pytest

from rationale.client import RetrievalClient, RetrievalServiceError


def test_get_decision_sends_bearer_token() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer token-1"
        assert request.url.path == "/decisions/9004/2026-08-30"
        return httpx.Response(200, json={"decision": "decision/9004/2026-08-30"})

    client = RetrievalClient(
        "http://testserver",
        "token-1",
        transport=httpx.MockTransport(handler),
    )

    assert client.get_decision("9004", "2026-08-30")["decision"] == ("decision/9004/2026-08-30")


def test_get_placement_evidence_passes_role_filter() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/evidence/9004/2026-08-30/PW-1"
        assert request.url.params["role"] == "urgency"
        return httpx.Response(200, json={"placement": "placement/9004/2026-08-30/PW-1"})

    client = RetrievalClient(
        "http://testserver",
        "token-1",
        transport=httpx.MockTransport(handler),
    )

    response = client.get_placement_evidence("9004", "2026-08-30", "PW-1", role="urgency")

    assert response["placement"] == "placement/9004/2026-08-30/PW-1"


def test_unexpected_status_raises() -> None:
    client = RetrievalClient(
        "http://testserver",
        "token-1",
        transport=httpx.MockTransport(lambda request: httpx.Response(404, text="missing")),
    )

    with pytest.raises(RetrievalServiceError, match="404"):
        client.get_decision("9004", "2026-08-30")
