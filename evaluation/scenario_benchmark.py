"""Seeded scenario and regression benchmark for the deterministic agents."""

from __future__ import annotations

import argparse
import json
import random
from dataclasses import asdict, dataclass
from hashlib import sha256
from typing import Any

from capacity_agent.calibration import load_calibration as load_capacity_calibration
from capacity_agent.scoring import InsufficientCapacityEvidenceError, score_capacity
from coordinator.app.ranking import rank_cohort
from urgency_agent.calibration import load_calibration as load_urgency_calibration
from urgency_agent.scoring import (
    InsufficientUrgencyEvidenceError,
    PaediatricReferralRefusedError,
    score_urgency,
)

SEED = 20260913


@dataclass(frozen=True)
class ScenarioMetric:
    name: str
    value: int | float | str
    expected: int | float | str
    passed: bool


@dataclass(frozen=True)
class ScenarioBenchmarkReport:
    metrics: tuple[ScenarioMetric, ...]

    @property
    def passed(self) -> bool:
        return all(metric.passed for metric in self.metrics)

    @property
    def passed_count(self) -> int:
        return sum(metric.passed for metric in self.metrics)

    @property
    def failed_count(self) -> int:
        return len(self.metrics) - self.passed_count

    def to_dict(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "metrics": [asdict(metric) for metric in self.metrics],
        }

    def render_text(self) -> str:
        lines = [
            "Scenario Benchmark",
            f"Result: {'PASS' if self.passed else 'FAIL'} "
            f"({self.passed_count}/{len(self.metrics)} metrics passed)",
            "",
            "| Metric | Value | Expected | Result |",
            "|---|---:|---:|---|",
        ]
        for metric in self.metrics:
            lines.append(
                f"| {metric.name} | {metric.value} | {metric.expected} | "
                f"{'PASS' if metric.passed else 'FAIL'} |"
            )
        return "\n".join(lines)


def run_scenario_benchmark() -> ScenarioBenchmarkReport:
    actual = {
        **_urgency_metrics(),
        **_capacity_metrics(),
        **_coordinator_metrics(),
    }
    actual["scenario_regression_digest"] = _digest(actual)

    expected: dict[str, int | float | str] = {
        "urgency_total_cases": 70,
        "urgency_scored": 60,
        "urgency_paediatric_refusals": 5,
        "urgency_missing_evidence_refusals": 5,
        "urgency_total_citations": 360,
        "urgency_score_range_valid": 1,
        "urgency_monotonic_news2_curve": 1,
        "capacity_total_cases": 55,
        "capacity_scored": 50,
        "capacity_missing_evidence_refusals": 5,
        "capacity_total_citations": 90,
        "capacity_score_range_valid": 1,
        "capacity_monotonic_pressure": 1,
        "coordinator_total_cohorts": 25,
        "coordinator_total_referrals": 300,
        "coordinator_ranked_referrals": 250,
        "coordinator_missing_urgency_exclusions": 50,
        "coordinator_order_violations": 0,
        "coordinator_position_violations": 0,
        "coordinator_determinism_violations": 0,
        "scenario_regression_digest": "b287c67dff22",
    }

    metrics = tuple(
        ScenarioMetric(
            name=name,
            value=actual[name],
            expected=expected[name],
            passed=actual[name] == expected[name],
        )
        for name in expected
    )
    return ScenarioBenchmarkReport(metrics)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run seeded scenario and regression checks for the deterministic agents."
    )
    parser.add_argument("--format", choices=("text", "json"), default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = run_scenario_benchmark()
    if args.format == "json":
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        print(report.render_text())
    return 0 if report.passed else 1


def _urgency_metrics() -> dict[str, int]:
    calibration = load_urgency_calibration()
    rng = random.Random(SEED)
    scored = 0
    paediatric = 0
    missing = 0
    citations = 0
    scores: list[float] = []

    for index in range(60):
        context = _urgency_context(
            pathway_number=f"PW-U-{index:03d}",
            observations=[_random_observation(rng, index)],
        )
        result = score_urgency(context, calibration)
        scored += 1
        citations += len(result.citations)
        scores.append(result.score)

    for index in range(5):
        try:
            score_urgency(
                _urgency_context(
                    pathway_number=f"PW-U-PAED-{index}",
                    specialty_hipe="0601",
                    observations=[_random_observation(rng, index)],
                ),
                calibration,
            )
        except PaediatricReferralRefusedError:
            paediatric += 1

    for index in range(5):
        try:
            score_urgency(
                _urgency_context(pathway_number=f"PW-U-MISSING-{index}", observations=[]),
                calibration,
            )
        except InsufficientUrgencyEvidenceError:
            missing += 1

    monotonic = 1
    previous = -1.0
    for rr in (16, 21, 25):
        result = score_urgency(_urgency_context(observations=[_observation(rr=rr)]), calibration)
        if result.score < previous:
            monotonic = 0
        previous = result.score

    return {
        "urgency_total_cases": scored + paediatric + missing,
        "urgency_scored": scored,
        "urgency_paediatric_refusals": paediatric,
        "urgency_missing_evidence_refusals": missing,
        "urgency_total_citations": citations,
        "urgency_score_range_valid": int(all(0.0 <= score <= 1.0 for score in scores)),
        "urgency_monotonic_news2_curve": monotonic,
    }


def _capacity_metrics() -> dict[str, int]:
    calibration = load_capacity_calibration()
    scored = 0
    missing = 0
    citations = 0
    scores: list[float] = []

    for index in range(40):
        result = score_capacity(
            _capacity_context(
                wards=[_ward(latest_bed_status=_bed_status(occupancy_pct=float((index * 7) % 101)))],
                clinic_sessions=[
                    _clinic_session(slots_total=20, slots_booked=(index * 3) % 21)
                ],
            ),
            calibration,
        )
        scored += 1
        citations += len(result.citations)
        scores.append(result.score)

    for index in range(5):
        result = score_capacity(
            _capacity_context(
                wards=[_ward(latest_bed_status=_bed_status(occupancy_pct=float(index * 20)))],
                clinic_sessions=[],
            ),
            calibration,
        )
        scored += 1
        citations += len(result.citations)
        scores.append(result.score)

    for index in range(5):
        result = score_capacity(
            _capacity_context(
                wards=[],
                clinic_sessions=[_clinic_session(slots_total=10, slots_booked=index * 2)],
            ),
            calibration,
        )
        scored += 1
        citations += len(result.citations)
        scores.append(result.score)

    for _ in range(5):
        try:
            score_capacity(_capacity_context(wards=[], clinic_sessions=[]), calibration)
        except InsufficientCapacityEvidenceError:
            missing += 1

    low = score_capacity(
        _capacity_context(
            wards=[_ward(latest_bed_status=_bed_status(occupancy_pct=0.0))],
            clinic_sessions=[_clinic_session(slots_total=10, slots_booked=0)],
        ),
        calibration,
    ).score
    high = score_capacity(
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
    ).score

    return {
        "capacity_total_cases": scored + missing,
        "capacity_scored": scored,
        "capacity_missing_evidence_refusals": missing,
        "capacity_total_citations": citations,
        "capacity_score_range_valid": int(all(0.0 <= score <= 1.0 for score in scores)),
        "capacity_monotonic_pressure": int(high >= low),
    }


def _coordinator_metrics() -> dict[str, int]:
    total_cohorts = 25
    total_referrals = 0
    ranked_referrals = 0
    exclusions = 0
    order_violations = 0
    position_violations = 0
    determinism_violations = 0

    for cohort_index in range(total_cohorts):
        cohort = [_coordinator_referral(cohort_index, referral_index) for referral_index in range(12)]
        total_referrals += len(cohort)
        result = rank_cohort(cohort, capacity_direction="pressure")
        repeat = rank_cohort(list(reversed(cohort)), capacity_direction="pressure")

        ranked_referrals += len(result.rankings)
        exclusions += len(result.excluded)
        order_violations += _clinical_order_violations(result.rankings)

        positions = [referral["position"] for referral in result.rankings]
        if positions != list(range(1, len(positions) + 1)):
            position_violations += 1

        order = [(r["pathway_number"], r["position"]) for r in result.rankings]
        repeat_order = [(r["pathway_number"], r["position"]) for r in repeat.rankings]
        if order != repeat_order:
            determinism_violations += 1

    return {
        "coordinator_total_cohorts": total_cohorts,
        "coordinator_total_referrals": total_referrals,
        "coordinator_ranked_referrals": ranked_referrals,
        "coordinator_missing_urgency_exclusions": exclusions,
        "coordinator_order_violations": order_violations,
        "coordinator_position_violations": position_violations,
        "coordinator_determinism_violations": determinism_violations,
    }


def _digest(values: dict[str, int | float | str]) -> str:
    stable = json.dumps(values, sort_keys=True)
    return sha256(stable.encode("utf-8")).hexdigest()[:12]


def _random_observation(rng: random.Random, index: int) -> dict[str, Any]:
    return _observation(
        obs_datetime=f"2026-08-16T09:{index % 60:02d}:00",
        rr=rng.choice([8, 12, 16, 21, 25]),
        spo2=rng.choice([91, 94, 96, 98]),
        sbp=rng.choice([90, 110, 120, 180, 220]),
        hr=rng.choice([40, 70, 100, 120, 131]),
        temp=rng.choice([35.0, 37.0, 38.5, 39.5]),
        avpu=rng.choice(["A", "A", "A", "V"]),
    )


def _observation(obs_datetime: str = "2026-08-16T09:16:00", **overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
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
    pathway_number: str = "PW-U-000",
    specialty_hipe: str = "1800",
    observations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "referral": {
            "hospital_hipe": "9001",
            "pathway_number": pathway_number,
            "specialty_hipe": specialty_hipe,
        },
        "observations": [_observation()] if observations is None else observations,
    }


def _bed_status(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
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


def _ward(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "ward_id": "W01",
        "is_primary": True,
        "nominal_beds": 20,
        "latest_bed_status": _bed_status(),
    }
    base.update(overrides)
    return base


def _clinic_session(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "clinic_code": "CL02",
        "session_date": "2026-08-26",
        "clinic_name": "Benchmark Clinic",
        "slots_total": 20,
        "slots_booked": 15,
        "slots_available": 5,
    }
    base.update(overrides)
    return base


def _capacity_context(*, wards: list[dict[str, Any]], clinic_sessions: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "referral": {
            "hospital_hipe": "9001",
            "pathway_number": "PW-C-001",
            "specialty_hipe": "0100",
        },
        "capacity": {
            "specialty_hipe": "0100",
            "wards": wards,
            "clinic_sessions": clinic_sessions,
        },
    }


def _coordinator_referral(cohort_index: int, referral_index: int) -> dict[str, Any]:
    cpcs: list[int | None] = [1, 3, 2, 4, None]
    cpc = cpcs[(cohort_index + referral_index) % len(cpcs)]
    referral: dict[str, Any] = {
        "hospital_hipe": "9001",
        "pathway_number": f"PW-R-{cohort_index:02d}-{referral_index:02d}",
        "specialty_hipe": f"{1000 + (referral_index % 4) * 100}",
        "cpc": cpc,
        "crt_breached": [True, False, None][(cohort_index + referral_index) % 3],
        "triage_status": "awaiting_triage" if referral_index % 6 == 0 else "triaged",
        "adjusted_wait_days": 5 + ((cohort_index * 11 + referral_index * 7) % 180),
        "days_awaiting_triage": 25 if referral_index % 6 == 0 else None,
        "referral_date": f"2026-01-{(referral_index % 28) + 1:02d}",
        "urgency_score": ((cohort_index * 13 + referral_index * 17) % 100) / 100,
        "capacity_score": ((referral_index * 19) % 100) / 100,
    }
    if referral_index in {0, 11}:
        del referral["urgency_score"]
    if referral_index == 10:
        del referral["capacity_score"]
    return referral


def _clinical_order_violations(rankings: list[dict[str, Any]]) -> int:
    order_values = [
        referral["severity_rank"] if referral.get("severity_rank") is not None else float("inf")
        for referral in rankings
    ]
    return sum(
        1 for before, after in zip(order_values, order_values[1:], strict=False) if before > after
    )


if __name__ == "__main__":
    raise SystemExit(main())
