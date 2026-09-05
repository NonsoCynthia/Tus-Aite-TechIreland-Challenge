"""calibration.py loads and validates capacity_agent/calibration.yml
(spec.md FR2, product.md's "committed, inspectable config rather than
hidden constants" principle) -- malformed or non-normalised weights must
be rejected before they can affect a scoring run.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from capacity_agent.calibration import (
    DEFAULT_CALIBRATION_PATH,
    CapacityCalibration,
    load_calibration,
)


def test_default_calibration_file_loads_and_validates() -> None:
    calibration = load_calibration(DEFAULT_CALIBRATION_PATH)
    assert calibration.occupancy_weight + calibration.escalation_weight == pytest.approx(1.0)
    assert calibration.ward_weight + calibration.clinic_weight == pytest.approx(1.0)
    assert sum(calibration.escalation_triggers.values()) == pytest.approx(1.0)
    assert calibration.method
    assert calibration.agent_version


def test_rejects_occupancy_and_escalation_weights_not_summing_to_one() -> None:
    with pytest.raises(ValidationError):
        CapacityCalibration(
            occupancy_weight=0.5,
            escalation_weight=0.6,
            escalation_triggers={
                "surge_capacity_in_use": 0.4,
                "delayed_transfers_of_care": 0.3,
                "awaiting_admission_over_24h": 0.2,
                "outliers": 0.1,
            },
            ward_weight=0.7,
            clinic_weight=0.3,
            method="m",
            agent_version="v",
        )


def test_rejects_ward_and_clinic_weights_not_summing_to_one() -> None:
    with pytest.raises(ValidationError):
        CapacityCalibration(
            occupancy_weight=0.6,
            escalation_weight=0.4,
            escalation_triggers={
                "surge_capacity_in_use": 0.4,
                "delayed_transfers_of_care": 0.3,
                "awaiting_admission_over_24h": 0.2,
                "outliers": 0.1,
            },
            ward_weight=0.7,
            clinic_weight=0.4,
            method="m",
            agent_version="v",
        )


def test_rejects_escalation_triggers_not_summing_to_one() -> None:
    with pytest.raises(ValidationError):
        CapacityCalibration(
            occupancy_weight=0.6,
            escalation_weight=0.4,
            escalation_triggers={
                "surge_capacity_in_use": 0.4,
                "delayed_transfers_of_care": 0.3,
                "awaiting_admission_over_24h": 0.2,
                "outliers": 0.05,
            },
            ward_weight=0.7,
            clinic_weight=0.3,
            method="m",
            agent_version="v",
        )


def test_rejects_a_negative_weight() -> None:
    with pytest.raises(ValidationError):
        CapacityCalibration(
            occupancy_weight=-0.1,
            escalation_weight=1.1,
            escalation_triggers={
                "surge_capacity_in_use": 0.4,
                "delayed_transfers_of_care": 0.3,
                "awaiting_admission_over_24h": 0.2,
                "outliers": 0.1,
            },
            ward_weight=0.7,
            clinic_weight=0.3,
            method="m",
            agent_version="v",
        )


def test_rejects_escalation_triggers_missing_a_known_flag() -> None:
    with pytest.raises(ValidationError):
        CapacityCalibration(
            occupancy_weight=0.6,
            escalation_weight=0.4,
            escalation_triggers={
                "surge_capacity_in_use": 0.5,
                "delayed_transfers_of_care": 0.3,
                "awaiting_admission_over_24h": 0.2,
                # outliers missing
            },
            ward_weight=0.7,
            clinic_weight=0.3,
            method="m",
            agent_version="v",
        )
