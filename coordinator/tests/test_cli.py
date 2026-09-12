"""Tier 3 smoke test for the coordinator CLI (spec.md FR11, NFR3).

One smoke test proving the CLI runs end to end against the fixture score
source without raising -- per `conductor/workflow.md`, Tier 3 requires
exactly this, not an exhaustive suite.

No network I/O (NFR5): `fetch_cohort` and `_load_config` are faked at the
seam via monkeypatch, `--score-source fixture` avoids any live scores call,
and `--dry-run` avoids `post_decision` entirely.
"""

from typing import Any

import pytest

from coordinator.app import cli


def _fixture_cohort() -> list[dict[str, Any]]:
    """A tiny, hand-built cohort -- just enough to exercise the pipeline."""
    return [
        {
            "hospital_hipe": "9004",
            "pathway_number": "PW-9004-000001",
            "specialty_hipe": "1800",
            "cpc": 1,
            "crt_breached": True,
            "referral_date": "2026-01-01",
            "adjusted_wait_days": 41,
            "crt_threshold_days": 28,
            "triage_status": "triaged",
            "days_awaiting_triage": None,
            "referral_state_valid_from": "2026-01-01",
        },
        {
            "hospital_hipe": "9004",
            "pathway_number": "PW-9004-000002",
            "specialty_hipe": "1800",
            "cpc": 2,
            "crt_breached": None,
            "referral_date": "2026-01-02",
            "adjusted_wait_days": 10,
            "crt_threshold_days": None,
            "triage_status": "triaged",
            "days_awaiting_triage": None,
            "referral_state_valid_from": "2026-01-02",
        },
    ]


def test_cli_runs_end_to_end_against_fixture_score_source_without_raising(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The CLI runs end to end -- cohort fetch (faked), fixture scoring,
    ranking, decision assembly, dry-run print -- without raising."""
    monkeypatch.setattr(cli, "fetch_cohort", lambda *args, **kwargs: _fixture_cohort())
    monkeypatch.setattr(cli, "_load_config", lambda: ("http://unused.invalid", "unused-token"))

    exit_code = cli.main(
        [
            "--hospital",
            "9004",
            "--as-of",
            "2026-01-01",
            "--run-id",
            "run-test",
            "--capacity-direction",
            "pressure",
            "--score-source",
            "fixture",
            "--dry-run",
        ]
    )

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "PW-9004-000001" in captured.out


def test_cli_exits_nonzero_naming_both_values_when_capacity_direction_omitted(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`--capacity-direction` is required with no default (ADR-007):
    omitting it exits non-zero with a message naming both accepted
    values and explaining why there is no default -- not a bare
    "required argument" message."""
    with pytest.raises(SystemExit) as exc_info:
        cli.main(
            [
                "--hospital",
                "9004",
                "--as-of",
                "2026-01-01",
                "--run-id",
                "run-test",
                "--score-source",
                "fixture",
                "--dry-run",
            ]
        )

    assert exc_info.value.code != 0

    stderr = capsys.readouterr().err
    assert "availability" in stderr
    assert "pressure" in stderr
    assert "ADR-007" in stderr
