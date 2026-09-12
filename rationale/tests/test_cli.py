import pytest

from rationale import cli
from rationale.config import Settings


class FakeClient:
    calls: list[str] = []

    def __init__(self, base_url: str, bearer_token: str) -> None:
        self.base_url = base_url
        self.bearer_token = bearer_token

    def __enter__(self) -> "FakeClient":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def get_decision(self, hospital_hipe: str, as_of_date: str) -> dict[str, object]:
        self.calls.append("decision")
        return {
            "decision": f"decision/{hospital_hipe}/{as_of_date}",
            "placements": [
                {
                    "placement": f"placement/{hospital_hipe}/{as_of_date}/PW-1",
                    "position": 1,
                    "referral": f"referral/{hospital_hipe}/PW-1",
                    "pathway_number": "PW-1",
                    "evidence": [
                        {
                            "role": "urgency",
                            "iri": "score/run-1/9004/PW-1/urgency",
                            "type": "Score",
                            "properties": {"scoreValue": "0.500"},
                        }
                    ],
                }
            ],
        }

    def get_placement_evidence(
        self,
        hospital_hipe: str,
        as_of_date: str,
        pathway_number: str,
    ) -> dict[str, object]:
        self.calls.append("evidence")
        return {
            "placement": f"placement/{hospital_hipe}/{as_of_date}/{pathway_number}",
            "evidence": [
                {
                    "role": "capacity",
                    "iri": "bed-status/9004/W1/2026-08-30%2008%3A00%3A00",
                    "type": "BedStatus",
                    "properties": {"freeBeds": "12"},
                }
            ],
        }


def test_cli_prints_text(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    FakeClient.calls = []
    monkeypatch.setattr(
        cli,
        "load_settings",
        lambda: Settings(retrieval_base_url="http://testserver", bearer_token="token-1"),
    )
    monkeypatch.setattr(cli, "RetrievalClient", FakeClient)

    assert cli.main(["--hospital", "9004", "--as-of", "2026-08-30"]) == 0

    captured = capsys.readouterr()
    assert "Ranked #1" in captured.out
    assert "score/run-1/9004/PW-1/urgency" in captured.out
    assert FakeClient.calls == ["decision"]


def test_cli_pathway_uses_single_placement_evidence_endpoint(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    FakeClient.calls = []
    monkeypatch.setattr(
        cli,
        "load_settings",
        lambda: Settings(retrieval_base_url="http://testserver", bearer_token="token-1"),
    )
    monkeypatch.setattr(cli, "RetrievalClient", FakeClient)

    assert (
        cli.main(
            [
                "--hospital",
                "9004",
                "--as-of",
                "2026-08-30",
                "--pathway",
                "PW-9004-000123",
            ]
        )
        == 0
    )

    captured = capsys.readouterr()
    assert "Ranked placement" in captured.out
    assert "bed-status/9004/W1/2026-08-30%2008%3A00%3A00" in captured.out
    assert FakeClient.calls == ["evidence"]


def test_cli_supports_clinician_style(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    FakeClient.calls = []
    monkeypatch.setattr(
        cli,
        "load_settings",
        lambda: Settings(retrieval_base_url="http://testserver", bearer_token="token-1"),
    )
    monkeypatch.setattr(cli, "RetrievalClient", FakeClient)

    assert (
        cli.main(
            [
                "--hospital",
                "9004",
                "--as-of",
                "2026-08-30",
                "--pathway",
                "PW-9004-000123",
                "--style",
                "clinician",
            ]
        )
        == 0
    )

    captured = capsys.readouterr()
    assert "shown for clinician review" in captured.out
    assert "beds free" in captured.out
    assert "Evidence nodes:" not in captured.out
