import pytest
from fastapi.testclient import TestClient

from rationale.app import main
from rationale.config import Settings
from rationale.llm_render import RationaleGuardrailError
from rationale.models import Rationale


class FakeClient:
    def __init__(self, base_url: str, bearer_token: str) -> None:
        self.base_url = base_url
        self.bearer_token = bearer_token

    def __enter__(self) -> "FakeClient":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def get_placement_evidence(
        self,
        hospital_hipe: str,
        as_of_date: str,
        pathway_number: str,
    ) -> dict[str, object]:
        return {
            "placement": f"placement/{hospital_hipe}/{as_of_date}/{pathway_number}",
            "evidence": [
                {
                    "role": "urgency",
                    "iri": f"score/run-1/{hospital_hipe}/{pathway_number}/urgency",
                    "type": "Score",
                    "properties": {
                        "scoreValue": "0.5",
                        "cites": f"obs/{hospital_hipe}/{pathway_number}/2026-08-30/spo2",
                    },
                }
            ],
        }


@pytest.fixture(autouse=True)
def fake_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        main,
        "load_settings",
        lambda: Settings(retrieval_base_url="http://retrieval:8000", bearer_token="token-1"),
    )
    monkeypatch.setattr(main, "RetrievalClient", FakeClient)


def test_health() -> None:
    response = TestClient(main.app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_rationale_endpoint_returns_clinician_style_by_default() -> None:
    response = TestClient(main.app).get("/rationale/9001/2026-08-30/PW-9001-000007")

    assert response.status_code == 200
    body = response.json()
    assert body["hospital_hipe"] == "9001"
    assert body["as_of_date"] == "2026-08-30"
    assert body["pathway_number"] == "PW-9001-000007"
    assert body["style"] == "clinician"
    assert "shown for clinician review" in body["text"]
    assert "Evidence nodes:" not in body["text"]
    assert body["citation_iris"] == ["score/run-1/9001/PW-9001-000007/urgency"]


def test_rationale_endpoint_supports_technical_style() -> None:
    response = TestClient(main.app).get(
        "/rationale/9001/2026-08-30/PW-9001-000007?style=technical"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["style"] == "technical"
    assert "Urgency evidence:" in body["text"]
    assert "score/run-1/9001/PW-9001-000007/urgency" in body["text"]


def test_rationale_endpoint_engine_llm_calls_the_llm_renderer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_render_rationale_llm(pack: object, *, style: str, settings: object) -> Rationale:
        captured["pack"] = pack
        captured["style"] = style
        return Rationale(pathway_number="PW-9001-000007", text="llm text", citation_iris=("x",))

    monkeypatch.setattr(main, "render_rationale_llm", fake_render_rationale_llm)

    response = TestClient(main.app).get(
        "/rationale/9001/2026-08-30/PW-9001-000007?engine=llm"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["engine"] == "llm"
    assert body["text"] == "llm text"
    assert captured["style"] == "clinician"


def test_rationale_endpoint_engine_llm_maps_guardrail_failure_to_503(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_render_rationale_llm(pack: object, *, style: str, settings: object) -> Rationale:
        raise RationaleGuardrailError("citation_iris does not match")

    monkeypatch.setattr(main, "render_rationale_llm", fake_render_rationale_llm)

    response = TestClient(main.app).get(
        "/rationale/9001/2026-08-30/PW-9001-000007?engine=llm"
    )

    assert response.status_code == 503
    assert "citation_iris" in response.json()["detail"]


def test_rationale_endpoint_engine_llm_without_api_key_is_500() -> None:
    response = TestClient(main.app).get(
        "/rationale/9001/2026-08-30/PW-9001-000007?engine=llm"
    )

    # fake_dependencies' Settings carries no openai_api_key -- the real
    # render_rationale_llm (not mocked here) raises RuntimeError for that.
    assert response.status_code == 500
    assert "OPENAI_API_KEY" in response.json()["detail"]
