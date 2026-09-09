"""Smoke test for the CLI's argument parsing (Tier 3). main()'s wiring is
already exercised by test_run.py (run_for_cohort) and
test_run_integration.py (the real round trip)."""

from __future__ import annotations

from datetime import date

from urgency_agent.__main__ import _parse_args
from urgency_agent.calibration import DEFAULT_CALIBRATION_PATH


def test_parses_required_arguments() -> None:
    args = _parse_args(["--hospital", "9004", "--as-of-date", "2026-08-30", "--run-id", "run-0001"])
    assert args.hospital == "9004"
    assert args.as_of_date == date(2026, 8, 30)
    assert args.run_id == "run-0001"
    assert args.calibration == DEFAULT_CALIBRATION_PATH
