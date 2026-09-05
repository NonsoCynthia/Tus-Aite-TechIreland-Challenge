"""Capacity scorer tests (spec.md FR2, NFR1 Tier 1 strict TDD): deterministic
constraint reasoning over a referral's specialty capacity (ward bed-status +
clinic-session booking pressure), read from GET /referrals/.../context's
response shape (retrieval-service_20260904, FR9) -- never SPARQL/Postgres
directly (ADR-002: agents only ever talk to the retrieval service).
"""

from __future__ import annotations

import pytest

from capacity_agent.calibration import CapacityCalibration
from capacity_agent.scoring import (
    InsufficientCapacityEvidenceError,
    clinic_pressure,
    score_capacity,
    ward_pressure,
)


@pytest.fixture
def calibration() -> CapacityCalibration:
    return CapacityCalibration(
        occupancy_weight=0.6,
        escalation_weight=0.4,
        escalation_triggers={
            "surge_capacity_in_use": 0.4,
            "delayed_transfers_of_care": 0.3,
            "awaiting_admission_over_24h": 0.2,
            "outliers": 0.1,
        },
        ward_weight=0.7,
        clinic_weight=0.3,
        method="capacity-ward-clinic-pressure-v1",
        agent_version="capacity-agent-test",
    )


def _bed_status(**overrides: object) -> dict:
    base = {
        "snapshot_datetime": "2026-08-16T09:16:00",
        "occupied": 18,
        "free": 2,
        "occupancy_pct": 90.0,
        "outliers": 0,
        "surge_capacity_in_use": 0,
        "delayed_transfers_of_care": 0,
        "awaiting_admission_over_9h": 0,
        "awaiting_admission_over_24h": 0,
        "gar_status": "A",
    }
    base.update(overrides)
    return base


def _clinic_session(**overrides: object) -> dict:
    base = {
        "clinic_code": "CL02",
        "session_date": "2026-08-26",
        "clinic_name": "Orthopaedics OPD",
        "slots_total": 20,
        "slots_booked": 15,
        "slots_available": 5,
    }
    base.update(overrides)
    return base


def _context(
    *, wards: list[dict], clinic_sessions: list[dict], hospital_hipe: str = "9001"
) -> dict:
    return {
        "referral": {
            "hospital_hipe": hospital_hipe,
            "pathway_number": "PW-9001-000007",
            "specialty_hipe": "0100",
        },
        "observations": [],
        "conditions": [],
        "triage_events": [],
        "capacity": {
            "specialty_hipe": "0100",
            "wards": wards,
            "clinic_sessions": clinic_sessions,
        },
    }


class TestWardPressure:
    def test_pure_occupancy_component_when_no_escalation_flags(
        self, calibration: CapacityCalibration
    ) -> None:
        bed_status = _bed_status(occupancy_pct=50.0)
        # 0.6 * 0.5 + 0.4 * 0 = 0.3
        assert ward_pressure(bed_status, calibration) == pytest.approx(0.3)

    def test_full_occupancy_and_every_escalation_flag_saturates_to_one(
        self, calibration: CapacityCalibration
    ) -> None:
        bed_status = _bed_status(
            occupancy_pct=100.0,
            surge_capacity_in_use=2,
            delayed_transfers_of_care=1,
            awaiting_admission_over_24h=3,
            outliers=1,
        )
        assert ward_pressure(bed_status, calibration) == pytest.approx(1.0)

    def test_one_escalation_flag_contributes_only_its_own_weight(
        self, calibration: CapacityCalibration
    ) -> None:
        bed_status = _bed_status(occupancy_pct=0.0, surge_capacity_in_use=5)
        # 0.6 * 0 + 0.4 * 0.4 (surge's own weight) = 0.16
        assert ward_pressure(bed_status, calibration) == pytest.approx(0.16)

    def test_escalation_flags_are_boolean_not_magnitude(
        self, calibration: CapacityCalibration
    ) -> None:
        # graph-foundation_20260826's own finding: pressure is carried by
        # *whether* these fire, not their magnitude -- one outlier patient
        # and ten both count as "the flag fired," never scaled further.
        one = ward_pressure(_bed_status(occupancy_pct=0.0, outliers=1), calibration)
        ten = ward_pressure(_bed_status(occupancy_pct=0.0, outliers=10), calibration)
        assert one == pytest.approx(ten)

    def test_never_exceeds_one_or_drops_below_zero(self, calibration: CapacityCalibration) -> None:
        bed_status = _bed_status(
            occupancy_pct=100.0,
            surge_capacity_in_use=1,
            delayed_transfers_of_care=1,
            awaiting_admission_over_24h=1,
            outliers=1,
        )
        score = ward_pressure(bed_status, calibration)
        assert 0.0 <= score <= 1.0


class TestClinicPressure:
    def test_booked_ratio_when_slots_exist(self) -> None:
        session = _clinic_session(slots_total=20, slots_booked=15, slots_available=5)
        assert clinic_pressure(session) == pytest.approx(0.75)

    def test_empty_clinic_is_zero_pressure(self) -> None:
        session = _clinic_session(slots_total=10, slots_booked=0, slots_available=10)
        assert clinic_pressure(session) == pytest.approx(0.0)

    def test_fully_booked_clinic_is_full_pressure(self) -> None:
        session = _clinic_session(slots_total=10, slots_booked=10, slots_available=0)
        assert clinic_pressure(session) == pytest.approx(1.0)

    def test_no_sessions_scheduled_at_all_is_maximal_pressure(self) -> None:
        # slots_total == 0 means no clinic capacity exists at all for this
        # specialty right now -- the maximal constraint, not a 0/0 crash.
        session = _clinic_session(slots_total=0, slots_booked=0, slots_available=0)
        assert clinic_pressure(session) == pytest.approx(1.0)


class TestScoreCapacity:
    def test_combines_ward_and_clinic_pressure_by_configured_weights(
        self, calibration: CapacityCalibration
    ) -> None:
        context = _context(
            wards=[
                {
                    "ward_id": "W01",
                    "is_primary": True,
                    "nominal_beds": 20,
                    "latest_bed_status": _bed_status(occupancy_pct=50.0),
                }
            ],
            clinic_sessions=[_clinic_session(slots_total=20, slots_booked=10)],
        )
        result = score_capacity(context, calibration)
        # ward_pressure = 0.6*0.5 = 0.3, clinic_pressure = 0.5
        # score = 0.7*0.3 + 0.3*0.5 = 0.21 + 0.15 = 0.36
        assert result.score == pytest.approx(0.36)
        assert result.method == calibration.method

    def test_cites_both_bed_status_and_clinic_session_when_both_present(
        self, calibration: CapacityCalibration
    ) -> None:
        context = _context(
            wards=[
                {
                    "ward_id": "W01",
                    "is_primary": True,
                    "nominal_beds": 20,
                    "latest_bed_status": _bed_status(),
                }
            ],
            clinic_sessions=[_clinic_session()],
        )
        result = score_capacity(context, calibration)
        types = {c.evidence_type for c in result.citations}
        assert types == {"bed_status", "clinic_session"}
        assert len(result.citations) == 2

    def test_uses_the_primary_ward_first_in_list(self, calibration: CapacityCalibration) -> None:
        context = _context(
            wards=[
                {
                    "ward_id": "W01",
                    "is_primary": True,
                    "nominal_beds": 20,
                    "latest_bed_status": _bed_status(occupancy_pct=90.0),
                },
                {
                    "ward_id": "W02",
                    "is_primary": False,
                    "nominal_beds": 10,
                    "latest_bed_status": _bed_status(occupancy_pct=10.0),
                },
            ],
            clinic_sessions=[],
        )
        result = score_capacity(context, calibration)
        bed_status_citation = next(c for c in result.citations if c.evidence_type == "bed_status")
        assert "/W01/" in bed_status_citation.evidence_key

    def test_bed_status_evidence_key_matches_namespaces_md_template(
        self, calibration: CapacityCalibration
    ) -> None:
        # namespaces.md #4: bed-status/{hospital_hipe}/{ward_id}/{snapshot_datetime},
        # with the timestamp in Morph-KGC's own (space-separated, then
        # percent-encoded) form -- not the ISO 'T'-separated string the
        # retrieval service's JSON response actually carries, which would
        # point at a graph node that was never loaded.
        context = _context(
            wards=[
                {
                    "ward_id": "W01",
                    "is_primary": True,
                    "nominal_beds": 20,
                    "latest_bed_status": _bed_status(snapshot_datetime="2026-08-16T09:16:00"),
                }
            ],
            clinic_sessions=[],
        )
        result = score_capacity(context, calibration)
        citation = result.citations[0]
        assert citation.evidence_type == "bed_status"
        assert citation.evidence_key == "9001/W01/2026-08-16%2009%3A16%3A00"

    def test_clinic_session_evidence_key_matches_namespaces_md_template(
        self, calibration: CapacityCalibration
    ) -> None:
        context = _context(
            wards=[],
            clinic_sessions=[_clinic_session(clinic_code="CL02", session_date="2026-08-26")],
        )
        result = score_capacity(context, calibration)
        citation = result.citations[0]
        assert citation.evidence_type == "clinic_session"
        assert citation.evidence_key == "9001/CL02/2026-08-26"

    def test_falls_back_to_ward_only_when_no_clinic_sessions(
        self, calibration: CapacityCalibration
    ) -> None:
        context = _context(
            wards=[
                {
                    "ward_id": "W01",
                    "is_primary": True,
                    "nominal_beds": 20,
                    "latest_bed_status": _bed_status(occupancy_pct=50.0),
                }
            ],
            clinic_sessions=[],
        )
        result = score_capacity(context, calibration)
        # Renormalised over the one available signal: score == ward_pressure alone.
        assert result.score == pytest.approx(0.3)
        assert len(result.citations) == 1
        assert result.citations[0].evidence_type == "bed_status"

    def test_falls_back_to_clinic_only_when_no_ward_bed_status(
        self, calibration: CapacityCalibration
    ) -> None:
        context = _context(
            wards=[
                {
                    "ward_id": "W01",
                    "is_primary": True,
                    "nominal_beds": 20,
                    "latest_bed_status": None,
                }
            ],
            clinic_sessions=[_clinic_session(slots_total=10, slots_booked=5)],
        )
        result = score_capacity(context, calibration)
        assert result.score == pytest.approx(0.5)
        assert len(result.citations) == 1
        assert result.citations[0].evidence_type == "clinic_session"

    def test_raises_when_there_is_no_capacity_evidence_at_all(
        self, calibration: CapacityCalibration
    ) -> None:
        # NFR5: no score is ever rendered without its cited evidence attached
        # -- with nothing to cite, the right behaviour is to refuse to score,
        # not to write an uncited (and therefore un-writable, per ScoreIn's
        # min_length=1 citations) row.
        context = _context(wards=[], clinic_sessions=[])
        with pytest.raises(InsufficientCapacityEvidenceError):
            score_capacity(context, calibration)

    def test_score_is_deterministic_for_identical_input(
        self, calibration: CapacityCalibration
    ) -> None:
        context = _context(
            wards=[
                {
                    "ward_id": "W01",
                    "is_primary": True,
                    "nominal_beds": 20,
                    "latest_bed_status": _bed_status(occupancy_pct=73.0, outliers=2),
                }
            ],
            clinic_sessions=[_clinic_session(slots_total=8, slots_booked=8)],
        )
        first = score_capacity(context, calibration)
        second = score_capacity(context, calibration)
        assert first.score == second.score
        assert first.citations == second.citations
