"""Benchmark checks for agent correctness.

This benchmark is deliberately fixture-driven and database-free. It exercises
the real urgency, capacity and coordinator code paths over controlled cases,
then reports pass/fail checks that are easy to read in a demo or CI log.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from typing import Callable

from capacity_agent.calibration import load_calibration as load_capacity_calibration
from capacity_agent.scoring import (
    InsufficientCapacityEvidenceError,
    score_capacity,
    ward_pressure,
)
from coordinator.app.ranking import rank_cohort
from urgency_agent.calibration import load_calibration as load_urgency_calibration
from urgency_agent.scoring import (
    InsufficientUrgencyEvidenceError,
    PaediatricReferralRefusedError,
    score_urgency,
)

_TOLERANCE = 1e-9


@dataclass(frozen=True)
class BenchmarkCheck:
    agent: str
    name: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class BenchmarkReport:
    checks: tuple[BenchmarkCheck, ...]

    @property
    def passed(self) -> bool:
        return all(check.passed for check in self.checks)

    @property
    def passed_count(self) -> int:
        return sum(check.passed for check in self.checks)

    @property
    def failed_count(self) -> int:
        return len(self.checks) - self.passed_count

    def to_dict(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "checks": [asdict(check) for check in self.checks],
        }

    def render_text(self) -> str:
        lines = [
            "Agent Benchmark",
            f"Result: {'PASS' if self.passed else 'FAIL'} "
            f"({self.passed_count}/{len(self.checks)} checks passed)",
            "",
        ]
        for check in self.checks:
            status = "PASS" if check.passed else "FAIL"
            lines.append(f"[{status}] {check.agent}: {check.name}")
            lines.append(f"  {check.detail}")
        return "\n".join(lines)


def run_benchmark() -> BenchmarkReport:
    checks = [
        *_run_urgency_checks(),
        *_run_capacity_checks(),
        *_run_coordinator_checks(),
    ]
    return BenchmarkReport(tuple(checks))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run deterministic benchmark checks for the urgency, capacity and coordinator agents."
    )
    parser.add_argument("--format", choices=("text", "json"), default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = run_benchmark()
    if args.format == "json":
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        print(report.render_text())
    return 0 if report.passed else 1


def _run_urgency_checks() -> list[BenchmarkCheck]:
    calibration = load_urgency_calibration()
    return [
        _check(
            "urgency",
            "normal adult observation scores zero with full NEWS2 citations",
            lambda: _assert_urgency_normal(calibration),
        ),
        _check(
            "urgency",
            "high NEWS2 observation saturates at maximum urgency",
            lambda: _assert_urgency_high(calibration),
        ),
        _check(
            "urgency",
            "most recent observation is scored",
            lambda: _assert_urgency_most_recent(calibration),
        ),
        _check(
            "urgency",
            "paediatric referrals are refused",
            lambda: _assert_urgency_paediatric_refusal(calibration),
        ),
        _check(
            "urgency",
            "missing observation is refused",
            lambda: _assert_urgency_missing_observation(calibration),
        ),
    ]


def _run_capacity_checks() -> list[BenchmarkCheck]:
    calibration = load_capacity_calibration()
    return [
        _check(
            "capacity",
            "ward and clinic pressure combine with configured weights",
            lambda: _assert_capacity_combined_score(calibration),
        ),
        _check(
            "capacity",
            "escalation flags are boolean, not magnitude-scaled",
            lambda: _assert_capacity_boolean_escalation(calibration),
        ),
        _check(
            "capacity",
            "ward-only evidence is renormalised and cited",
            lambda: _assert_capacity_ward_only(calibration),
        ),
        _check(
            "capacity",
            "full ward and clinic pressure saturates at one",
            lambda: _assert_capacity_saturates(calibration),
        ),
        _check(
            "capacity",
            "missing capacity evidence is refused",
            lambda: _assert_capacity_missing_evidence(calibration),
        ),
    ]


def _run_coordinator_checks() -> list[BenchmarkCheck]:
    return [
        _check(
            "coordinator",
            "CPC band is non-compensatory",
            _assert_coordinator_cpc_band_boundary,
        ),
        _check(
            "coordinator",
            "CRT breach outranks same-band non-breach",
            _assert_coordinator_crt_breach_order,
        ),
        _check(
            "coordinator",
            "missing urgency is excluded, not defaulted",
            _assert_coordinator_missing_urgency_excluded,
        ),
        _check(
            "coordinator",
            "positions are contiguous and deterministic",
            _assert_coordinator_positions_and_determinism,
        ),
    ]


def _check(agent: str, name: str, assertion: Callable[[], str]) -> BenchmarkCheck:
    try:
        detail = assertion()
    except AssertionError as exc:
        return BenchmarkCheck(agent=agent, name=name, passed=False, detail=str(exc))
    except Exception as exc:  # pragma: no cover - defensive, reported in CLI output.
        return BenchmarkCheck(
            agent=agent,
            name=name,
            passed=False,
            detail=f"{type(exc).__name__}: {exc}",
        )
    return BenchmarkCheck(agent=agent, name=name, passed=True, detail=detail)


def _assert_urgency_normal(calibration: object) -> str:
    result = score_urgency(_urgency_context(observations=[_observation()]), calibration)
    _assert_close(result.score, 0.0, "normal observation score")
    assert result.news2 == 0, f"expected NEWS2 0, got {result.news2}"
    assert len(result.citations) == 6, f"expected 6 NEWS2 citations, got {len(result.citations)}"
    return "NEWS2 0 -> score 0.000 with six observation citations"


def _assert_urgency_high(calibration: object) -> str:
    result = score_urgency(
        _urgency_context(
            observations=[
                _observation(rr=25, spo2=91, sbp=90, hr=131, temp=39.1, avpu="V")
            ]
        ),
        calibration,
    )
    assert result.news2 == 17, f"expected NEWS2 17, got {result.news2}"
    _assert_close(result.score, 1.0, "high NEWS2 score")
    return "NEWS2 17 -> score 1.000"


def _assert_urgency_most_recent(calibration: object) -> str:
    result = score_urgency(
        _urgency_context(
            observations=[
                _observation(
                    obs_datetime="2026-08-16T09:16:00",
                    rr=25,
                    spo2=91,
                    sbp=90,
                    hr=131,
                    temp=39.1,
                    avpu="V",
                ),
                _observation(obs_datetime="2026-08-16T09:20:00"),
            ]
        ),
        calibration,
    )
    assert result.news2 == 0, f"expected newest normal observation NEWS2 0, got {result.news2}"
    _assert_close(result.score, 0.0, "newest observation score")
    return "older high NEWS2 ignored in favour of newest normal observation"


def _assert_urgency_paediatric_refusal(calibration: object) -> str:
    try:
        score_urgency(_urgency_context(specialty_hipe="0601"), calibration)
    except PaediatricReferralRefusedError:
        return "specialty 0601 refused"
    raise AssertionError("expected PaediatricReferralRefusedError")


def _assert_urgency_missing_observation(calibration: object) -> str:
    try:
        score_urgency(_urgency_context(observations=[]), calibration)
    except InsufficientUrgencyEvidenceError:
        return "no observation refused"
    raise AssertionError("expected InsufficientUrgencyEvidenceError")


def _assert_capacity_combined_score(calibration: object) -> str:
    result = score_capacity(
        _capacity_context(
            wards=[_ward(latest_bed_status=_bed_status(occupancy_pct=50.0))],
            clinic_sessions=[_clinic_session(slots_total=20, slots_booked=10)],
        ),
        calibration,
    )
    _assert_close(result.ward_pressure, 0.3, "ward pressure")
    _assert_close(result.clinic_pressure, 0.5, "clinic pressure")
    _assert_close(result.score, 0.36, "capacity score")
    citation_types = {citation.evidence_type for citation in result.citations}
    assert citation_types == {"bed_status", "clinic_session"}, citation_types
    return "ward 0.300 and clinic 0.500 -> score 0.360"


def _assert_capacity_boolean_escalation(calibration: object) -> str:
    one = ward_pressure(_bed_status(occupancy_pct=0.0, outliers=1), calibration)
    ten = ward_pressure(_bed_status(occupancy_pct=0.0, outliers=10), calibration)
    _assert_close(one, ten, "outlier escalation pressure")
    return f"outliers=1 and outliers=10 both score ward pressure {one:.3f}"


def _assert_capacity_ward_only(calibration: object) -> str:
    result = score_capacity(
        _capacity_context(
            wards=[_ward(latest_bed_status=_bed_status(occupancy_pct=50.0))],
            clinic_sessions=[],
        ),
        calibration,
    )
    _assert_close(result.score, 0.3, "ward-only capacity score")
    assert len(result.citations) == 1, f"expected 1 citation, got {len(result.citations)}"
    assert result.citations[0].evidence_type == "bed_status", result.citations[0].evidence_type
    return "ward-only evidence renormalises to ward pressure 0.300"


def _assert_capacity_saturates(calibration: object) -> str:
    result = score_capacity(
        _capacity_context(
            wards=[
                _ward(
                    latest_bed_status=_bed_status(
                        occupancy_pct=100.0,
                        surge_capacity_in_use=1,
                        delayed_transfers_of_care=1,
                        awaiting_admission_over_24h=1,
                        outliers=1,
                    )
                )
            ],
            clinic_sessions=[_clinic_session(slots_total=10, slots_booked=10)],
        ),
        calibration,
    )
    _assert_close(result.score, 1.0, "saturated capacity score")
    return "full ward pressure and full clinic pressure -> score 1.000"


def _assert_capacity_missing_evidence(calibration: object) -> str:
    try:
        score_capacity(_capacity_context(wards=[], clinic_sessions=[]), calibration)
    except InsufficientCapacityEvidenceError:
        return "no bed-status or clinic-session evidence refused"
    raise AssertionError("expected InsufficientCapacityEvidenceError")


def _assert_coordinator_cpc_band_boundary() -> str:
    result = rank_cohort(
        [
            _coordinator_referral("P-SEMI-HIGH", cpc=3, urgency_score=1.0, crt_breached=True),
            _coordinator_referral("P-URGENT-LOW", cpc=1, urgency_score=0.0, crt_breached=False),
        ],
        capacity_direction="pressure",
    )
    order = _pathway_order(result.rankings)
    assert order == ["P-URGENT-LOW", "P-SEMI-HIGH"], order
    return "urgent referral ranked above semi-urgent despite lower score"


def _assert_coordinator_crt_breach_order() -> str:
    result = rank_cohort(
        [
            _coordinator_referral("P-NOT-BREACHED", cpc=1, crt_breached=False),
            _coordinator_referral("P-BREACHED", cpc=1, crt_breached=True),
        ],
        capacity_direction="pressure",
    )
    order = _pathway_order(result.rankings)
    assert order == ["P-BREACHED", "P-NOT-BREACHED"], order
    return "same-band breached referral ranked first"


def _assert_coordinator_missing_urgency_excluded() -> str:
    missing_urgency = _coordinator_referral("P-MISSING-URGENCY")
    del missing_urgency["urgency_score"]
    missing_capacity = _coordinator_referral("P-MISSING-CAPACITY", urgency_score=0.3)
    del missing_capacity["capacity_score"]
    result = rank_cohort(
        [_coordinator_referral("P-SCORED"), missing_urgency, missing_capacity],
        capacity_direction="pressure",
    )
    ranked = set(_pathway_order(result.rankings))
    excluded = {referral["pathway_number"] for referral in result.excluded}
    assert "P-MISSING-URGENCY" not in ranked, ranked
    assert excluded == {"P-MISSING-URGENCY"}, excluded
    assert "P-MISSING-CAPACITY" in ranked, ranked
    return "missing urgency excluded; missing capacity alone remains rankable"


def _assert_coordinator_positions_and_determinism() -> str:
    cohort = [
        _coordinator_referral("P-003", referral_date="2026-01-03"),
        _coordinator_referral("P-001", referral_date="2026-01-01"),
        _coordinator_referral("P-002", referral_date="2026-01-02"),
    ]
    first = rank_cohort(cohort, capacity_direction="pressure")
    second = rank_cohort(list(reversed(cohort)), capacity_direction="pressure")
    first_order = [(r["pathway_number"], r["position"]) for r in first.rankings]
    second_order = [(r["pathway_number"], r["position"]) for r in second.rankings]
    assert first_order == second_order, (first_order, second_order)
    positions = [r["position"] for r in first.rankings]
    assert positions == [1, 2, 3], positions
    return "reversed input produced identical ordered positions"


def _observation(obs_datetime: str = "2026-08-16T09:16:00", **overrides: object) -> dict:
    base = {
        "obs_datetime": obs_datetime,
        "rr": 16,
        "spo2": 98,
        "sbp": 120,
        "hr": 70,
        "avpu": "A",
        "temp": 37.0,
    }
    base.update(overrides)
    return base


def _urgency_context(
    *,
    specialty_hipe: str = "1800",
    observations: list[dict] | None = None,
) -> dict:
    return {
        "referral": {
            "hospital_hipe": "9001",
            "pathway_number": "PW-BENCH-001",
            "specialty_hipe": specialty_hipe,
        },
        "observations": [_observation()] if observations is None else observations,
    }


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


def _ward(**overrides: object) -> dict:
    base = {
        "ward_id": "W01",
        "is_primary": True,
        "nominal_beds": 20,
        "latest_bed_status": _bed_status(),
    }
    base.update(overrides)
    return base


def _clinic_session(**overrides: object) -> dict:
    base = {
        "clinic_code": "CL02",
        "session_date": "2026-08-26",
        "clinic_name": "Benchmark Clinic",
        "slots_total": 20,
        "slots_booked": 15,
        "slots_available": 5,
    }
    base.update(overrides)
    return base


def _capacity_context(*, wards: list[dict], clinic_sessions: list[dict]) -> dict:
    return {
        "referral": {
            "hospital_hipe": "9001",
            "pathway_number": "PW-BENCH-001",
            "specialty_hipe": "0100",
        },
        "capacity": {
            "specialty_hipe": "0100",
            "wards": wards,
            "clinic_sessions": clinic_sessions,
        },
    }


def _coordinator_referral(pathway_number: str, **overrides: object) -> dict:
    referral = {
        "hospital_hipe": "9001",
        "pathway_number": pathway_number,
        "specialty_hipe": "0100",
        "cpc": 1,
        "crt_breached": None,
        "triage_status": "triaged",
        "adjusted_wait_days": 30,
        "days_awaiting_triage": None,
        "referral_date": "2026-01-01",
        "urgency_score": 0.5,
        "capacity_score": 0.5,
    }
    referral.update(overrides)
    return referral


def _pathway_order(rankings: list[dict]) -> list[str]:
    return [referral["pathway_number"] for referral in rankings]


def _assert_close(actual: float | None, expected: float, label: str) -> None:
    assert actual is not None, f"{label}: expected {expected}, got None"
    assert abs(actual - expected) <= _TOLERANCE, f"{label}: expected {expected}, got {actual}"


if __name__ == "__main__":
    raise SystemExit(main())
