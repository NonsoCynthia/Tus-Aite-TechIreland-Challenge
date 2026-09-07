"""Tier 1: calibration loading and validation.

`urgency_agent/calibration.yml` is committed, inspectable config rather than
constants in code (product.md's Calibration Configuration principle) -- a
clinician or compliance reviewer retunes the NEWS2 -> [0,1] mapping by editing
YAML without reading Python. That only holds if a bad edit is rejected loudly
at load time instead of silently producing wrong scores, which is what these
tests pin.

ADR-006 (conductor/tracks/explainable-agent-based-triage_20260828/decisions.md)
is the decision under test.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import ValidationError

from urgency_agent.calibration import (
    DEFAULT_CALIBRATION_PATH,
    UrgencyCalibration,
    load_calibration,
)
from urgency_agent.scoring import NEWS2_MAX

VALID: dict[str, Any] = {
    "breakpoints": [
        {"news2": 0, "score": 0.0},
        {"news2": 4, "score": 0.30},
        {"news2": 6, "score": 0.60},
        {"news2": 17, "score": 1.0},
    ],
    "method": "urgency-news2-v1",
    "agent_version": "urgency-agent-0.1.0",
}


def with_breakpoints(*pairs: tuple[int, float]) -> dict[str, Any]:
    return {**VALID, "breakpoints": [{"news2": n, "score": s} for n, s in pairs]}


# --------------------------------------------------------------------------- #
# The committed file
# --------------------------------------------------------------------------- #


def test_committed_calibration_loads() -> None:
    calibration = load_calibration()
    assert isinstance(calibration, UrgencyCalibration)


def test_default_calibration_path_exists() -> None:
    assert DEFAULT_CALIBRATION_PATH.exists()
    assert DEFAULT_CALIBRATION_PATH.name == "calibration.yml"


def test_committed_calibration_is_valid_yaml_mapping() -> None:
    loaded = yaml.safe_load(DEFAULT_CALIBRATION_PATH.read_text())
    assert isinstance(loaded, dict)


def test_committed_method_names_news2_and_a_version() -> None:
    """ADR-004: the method string names the single scored component, so a
    score written now is never mistaken for one from a later
    multi-component calibration. Bump it when the breakpoints change --
    otherwise a historical score is no longer reproducible against the
    calibration that actually produced it."""
    calibration = load_calibration()
    assert "news2" in calibration.method
    assert calibration.agent_version.startswith("urgency-agent-")


def test_load_calibration_accepts_an_explicit_path(tmp_path: Path) -> None:
    """`--calibration` on the CLI has to be able to point somewhere else, or
    retuning means editing a committed file in place."""
    path = tmp_path / "custom.yml"
    path.write_text(yaml.safe_dump(VALID))
    assert load_calibration(path).method == "urgency-news2-v1"


# --------------------------------------------------------------------------- #
# ADR-006's structural invariants
# --------------------------------------------------------------------------- #


def test_breakpoints_must_start_at_zero() -> None:
    """A NEWS2 of 0 is a fully normal observation and must score 0.0. Without
    this anchor, interpolation below the first breakpoint is undefined."""
    with pytest.raises(ValidationError):
        UrgencyCalibration.model_validate(with_breakpoints((2, 0.1), (17, 1.0)))


def test_breakpoints_must_reach_news2_max() -> None:
    """Anchoring the top at 20 (the generator's cap) rather than 17 (the
    reachable maximum on scale 1) would mean no real observation could ever
    score 1.0 -- the top of the range would be dead."""
    with pytest.raises(ValidationError):
        UrgencyCalibration.model_validate(with_breakpoints((0, 0.0), (12, 1.0)))


def test_breakpoints_must_be_strictly_ascending_in_news2() -> None:
    """Interpolation reads them in order; a duplicate or out-of-order NEWS2
    value would divide by zero or silently pick the wrong segment."""
    with pytest.raises(ValidationError):
        UrgencyCalibration.model_validate(with_breakpoints((0, 0.0), (6, 0.6), (4, 0.3), (17, 1.0)))


def test_duplicate_breakpoints_are_rejected() -> None:
    with pytest.raises(ValidationError):
        UrgencyCalibration.model_validate(with_breakpoints((0, 0.0), (4, 0.3), (4, 0.5), (17, 1.0)))


def test_scores_must_be_non_decreasing() -> None:
    """The one clinical invariant: a higher NEWS2 can never map to a lower
    urgency score. A reviewer retuning weights in YAML must not be able to
    invert the scale by accident -- that is exactly the silent sign error
    ADR-003 and coordinating-agent_20260906's ADR-007 were written about."""
    with pytest.raises(ValidationError):
        UrgencyCalibration.model_validate(with_breakpoints((0, 0.0), (4, 0.7), (6, 0.3), (17, 1.0)))


def test_scores_must_stay_within_zero_and_one() -> None:
    """ScoreIn.score is `ge=0, le=1`; an out-of-range breakpoint would be a
    422 from the retrieval service at write time, far from its cause."""
    with pytest.raises(ValidationError):
        UrgencyCalibration.model_validate(with_breakpoints((0, 0.0), (17, 1.4)))


def test_negative_scores_are_rejected() -> None:
    with pytest.raises(ValidationError):
        UrgencyCalibration.model_validate(with_breakpoints((0, -0.1), (17, 1.0)))


def test_at_least_two_breakpoints_are_required() -> None:
    """One point defines no curve -- there is nothing to interpolate between."""
    with pytest.raises(ValidationError):
        UrgencyCalibration.model_validate(with_breakpoints((0, 0.0)))


def test_news2_beyond_max_is_rejected() -> None:
    """17 is the reachable ceiling; a breakpoint above it is unreachable
    config, which is a mistake worth surfacing rather than ignoring."""
    with pytest.raises(ValidationError):
        UrgencyCalibration.model_validate(with_breakpoints((0, 0.0), (NEWS2_MAX + 1, 1.0)))


def test_valid_calibration_validates() -> None:
    """The positive control. If this fails, the rejection tests above prove
    nothing -- they could be failing for an unrelated reason."""
    calibration = UrgencyCalibration.model_validate(VALID)
    assert len(calibration.breakpoints) == 4


# --------------------------------------------------------------------------- #
# Loading failures
# --------------------------------------------------------------------------- #


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_calibration(tmp_path / "nope.yml")


def test_missing_required_field_raises(tmp_path: Path) -> None:
    """No defaults for `method`/`agent_version`: a score whose provenance is
    a silently-defaulted version string cannot be reproduced later."""
    path = tmp_path / "partial.yml"
    path.write_text(yaml.safe_dump({"breakpoints": VALID["breakpoints"]}))
    with pytest.raises(ValidationError):
        load_calibration(path)
