"""Pydantic-validated scoring config, loaded from `calibration.yml`.

ADR-006: NEWS2 maps to [0,1] through calibrated escalation breakpoints, and
the mapping lives in committed YAML rather than in `scoring.py`
(product.md's Calibration Configuration principle) so a clinician or
compliance reviewer can retune it without reading Python.

That only holds if a bad edit fails loudly at load time rather than silently
producing wrong scores, so the invariants below are enforced here rather than
trusted. The one that matters clinically is **non-decreasing scores**: a
higher NEWS2 must never map to a lower urgency. A reviewer must not be able to
invert the scale by accident -- that is the silent sign error ADR-003 and
`coordinating-agent_20260906`'s ADR-007 were both written about, and no
downstream test catches it once the numbers are still in range.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, model_validator

from .news2 import NEWS2_MAX

DEFAULT_CALIBRATION_PATH = Path(__file__).parent / "calibration.yml"


class Breakpoint(BaseModel):
    """One anchor on the NEWS2 -> score curve. `normalise_news2` interpolates
    linearly between consecutive breakpoints."""

    news2: int = Field(ge=0, le=NEWS2_MAX)
    score: float = Field(ge=0.0, le=1.0)


class UrgencyCalibration(BaseModel):
    breakpoints: list[Breakpoint] = Field(min_length=2)

    # No defaults. A score whose provenance is a silently-defaulted version
    # string cannot be reproduced later against the calibration that actually
    # produced it -- bump these whenever the breakpoints change.
    method: str
    agent_version: str

    @model_validator(mode="after")
    def _check_curve(self) -> UrgencyCalibration:
        points = self.breakpoints

        if points[0].news2 != 0 or points[0].score != 0.0:
            raise ValueError(
                "the first breakpoint must be news2=0, score=0.0 -- a fully normal "
                "observation scores zero, and interpolation below the first "
                f"breakpoint is otherwise undefined (got news2={points[0].news2}, "
                f"score={points[0].score})"
            )

        if points[-1].score != 1.0:
            raise ValueError(
                "the last breakpoint must score 1.0, or the top of the [0,1] range is "
                f"unreachable by any observation (got {points[-1].score}). NEWS2 values "
                "above the last breakpoint saturate at its score, so where that anchor "
                "sits is a clinical choice; that it scores 1.0 is not"
            )

        for lower, upper in zip(points, points[1:], strict=False):
            if upper.news2 <= lower.news2:
                raise ValueError(
                    "breakpoints must be strictly ascending in news2 -- interpolation "
                    "reads them in order, so a duplicate or out-of-order value would "
                    f"divide by zero or pick the wrong segment (got {lower.news2} "
                    f"then {upper.news2})"
                )
            if upper.score < lower.score:
                raise ValueError(
                    "breakpoint scores must be non-decreasing: a higher NEWS2 can never "
                    f"map to a lower urgency score (news2 {lower.news2} -> {lower.score} "
                    f"then news2 {upper.news2} -> {upper.score})"
                )

        return self


def load_calibration(path: Path | None = None) -> UrgencyCalibration:
    """Load and validate a calibration file, defaulting to the committed one."""
    resolved = DEFAULT_CALIBRATION_PATH if path is None else path
    if not resolved.exists():
        raise FileNotFoundError(f"no calibration file at {resolved}")
    data: Any = yaml.safe_load(resolved.read_text())
    return UrgencyCalibration.model_validate(data)
