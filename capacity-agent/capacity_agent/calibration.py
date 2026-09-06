"""Loads and validates capacity_agent/calibration.yml (spec.md FR2).

product.md's Calibration Configuration principle: weights and thresholds
live in committed, inspectable config, validated by Pydantic before they
can affect a run -- not hidden constants in scoring.py. See calibration.yml
for what each field means and scoring.py for how they combine.
"""

from __future__ import annotations

import math
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, model_validator

DEFAULT_CALIBRATION_PATH = Path(__file__).resolve().parent / "calibration.yml"

# The BedStatus columns escalation_triggers must weight -- fixed by the
# schema (dataset/db/migrations/004_capacity.sql), not open-ended, so a typo
# in calibration.yml (a misspelled flag name) is caught at load time rather
# than silently scoring as if that trigger never fires.
_KNOWN_ESCALATION_FLAGS = frozenset(
    {
        "surge_capacity_in_use",
        "delayed_transfers_of_care",
        "awaiting_admission_over_24h",
        "outliers",
    }
)

_SUM_TOLERANCE = 1e-6


def _assert_sums_to_one(value: float, label: str) -> None:
    if not math.isclose(value, 1.0, abs_tol=_SUM_TOLERANCE):
        raise ValueError(f"{label} must sum to 1.0, got {value}")


class CapacityCalibration(BaseModel):
    """Validated capacity-agent scoring weights (spec.md FR2). Every weight
    is a proportion in [0, 1]; the three weight groups below must each sum
    to 1.0 so a score can never leave [0, 1] by construction."""

    occupancy_weight: float = Field(ge=0, le=1)
    escalation_weight: float = Field(ge=0, le=1)
    escalation_triggers: dict[str, float]
    ward_weight: float = Field(ge=0, le=1)
    clinic_weight: float = Field(ge=0, le=1)
    method: str
    agent_version: str

    @model_validator(mode="after")
    def weights_sum_to_one(self) -> CapacityCalibration:
        _assert_sums_to_one(
            self.occupancy_weight + self.escalation_weight, "occupancy_weight + escalation_weight"
        )
        _assert_sums_to_one(self.ward_weight + self.clinic_weight, "ward_weight + clinic_weight")
        return self

    @model_validator(mode="after")
    def escalation_triggers_are_exactly_the_known_flags_and_sum_to_one(self) -> CapacityCalibration:
        keys = set(self.escalation_triggers)
        if keys != _KNOWN_ESCALATION_FLAGS:
            missing = _KNOWN_ESCALATION_FLAGS - keys
            unknown = keys - _KNOWN_ESCALATION_FLAGS
            raise ValueError(
                f"escalation_triggers must name exactly {sorted(_KNOWN_ESCALATION_FLAGS)} "
                f"(missing={sorted(missing)}, unknown={sorted(unknown)})"
            )
        for weight in self.escalation_triggers.values():
            if not (0 <= weight <= 1):
                raise ValueError(f"escalation_triggers weights must be in [0, 1], got {weight}")
        _assert_sums_to_one(sum(self.escalation_triggers.values()), "escalation_triggers")
        return self


def load_calibration(path: Path = DEFAULT_CALIBRATION_PATH) -> CapacityCalibration:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return CapacityCalibration.model_validate(raw)
