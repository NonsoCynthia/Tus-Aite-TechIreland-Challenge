"""Smoke test for the CLI's argument parsing and the missing-key guard --
main()'s wiring itself is already exercised by test_run.py (run_pipeline)."""

from __future__ import annotations

import pytest

from orchestrator_agent.__main__ import _parse_args, main
from orchestrator_agent.config import Settings


def test_parses_required_arguments() -> None:
    args = _parse_args(["--hospital", "9001", "--as-of-date", "2026-08-30", "--run-id", "run-1"])

    assert args.hospital == "9001"
    assert args.as_of_date == "2026-08-30"
    assert args.run_id == "run-1"


def test_main_reports_and_exits_1_without_an_api_key(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import orchestrator_agent.__main__ as entrypoint

    monkeypatch.setattr(
        entrypoint,
        "load_settings",
        lambda: Settings(openai_api_key=None, openai_model="gpt-4.1-mini"),
    )

    exit_code = main(["--hospital", "9001", "--as-of-date", "2026-08-30", "--run-id", "run-1"])

    assert exit_code == 1
    assert "OPENAI_API_KEY" in capsys.readouterr().err
