from datetime import date

import pytest

from evaluation.metrics import GroundTruthRanking, RuleSummary, evaluate_rankings


def _row(
    position: int,
    pathway_number: str,
    *,
    hazard: float | None,
    deteriorated: bool = False,
) -> GroundTruthRanking:
    return GroundTruthRanking(
        position=position,
        hospital_hipe="9001",
        pathway_number=pathway_number,
        latent_hazard=hazard,
        deterioration_date=date(2026, 8, 20) if deteriorated else None,
        deterioration_type="emergency_admission" if deteriorated else None,
    )


def test_evaluate_rankings_reports_deadlines_and_top_k_capture() -> None:
    report = evaluate_rankings(
        decision_id="decision-1",
        run_id="run-1",
        hospital_hipe="9001",
        as_of_date="2026-08-30",
        top_k=3,
        high_hazard_threshold=0.7,
        rankings=[
            _row(1, "PW-1", hazard=0.9, deteriorated=True),
            _row(2, "PW-2", hazard=0.2),
            _row(3, "PW-3", hazard=0.8),
            _row(4, "PW-4", hazard=0.4, deteriorated=True),
        ],
        rule_summaries=[
            RuleSummary("RULE-CRT-URGENT", total=2, failed=1),
            RuleSummary("RULE-CRT-SEMI", total=2, failed=1),
            RuleSummary("RULE-TIEBREAK", total=4, failed=0),
            RuleSummary("RULE-TRIAGE-TURNAROUND", total=1, failed=1),
        ],
    )

    assert report.missed_crt_deadlines == 2
    assert report.triage_turnaround_failures == 1
    assert report.total_deteriorations == 2
    assert report.deteriorations_in_top_k == 1
    assert report.deterioration_capture_at_k == 0.5
    assert report.high_hazard_total == 2
    assert report.high_hazard_in_top_k == 2
    assert report.high_hazard_capture_at_k == 1.0
    assert report.mean_latent_hazard_top_k == pytest.approx((0.9 + 0.2 + 0.8) / 3)
    assert report.mean_latent_hazard_rest == 0.4


def test_evaluate_rankings_handles_no_deteriorations_without_dividing_by_zero() -> None:
    report = evaluate_rankings(
        decision_id="decision-1",
        run_id="run-1",
        hospital_hipe="9001",
        as_of_date="2026-08-30",
        top_k=10,
        rankings=[
            _row(1, "PW-1", hazard=0.1),
            _row(2, "PW-2", hazard=0.2),
        ],
        rule_summaries=[],
    )

    assert report.top_k == 2
    assert report.total_deteriorations == 0
    assert report.deterioration_capture_at_k is None
    assert report.mean_rank_of_deteriorations is None
    assert report.median_rank_of_deteriorations is None


def test_evaluate_rankings_counts_missing_ground_truth_rows() -> None:
    report = evaluate_rankings(
        decision_id="decision-1",
        run_id="run-1",
        hospital_hipe="9001",
        as_of_date="2026-08-30",
        top_k=1,
        rankings=[
            _row(1, "PW-1", hazard=0.8),
            _row(2, "PW-2", hazard=None),
        ],
        rule_summaries=[],
    )

    assert report.ranked_count == 2
    assert report.ranked_with_ground_truth == 1


def test_evaluate_rankings_validates_metric_parameters() -> None:
    with pytest.raises(ValueError, match="top_k"):
        evaluate_rankings(
            decision_id="decision-1",
            run_id="run-1",
            hospital_hipe="9001",
            as_of_date="2026-08-30",
            top_k=0,
            rankings=[],
            rule_summaries=[],
        )

    with pytest.raises(ValueError, match="high_hazard_threshold"):
        evaluate_rankings(
            decision_id="decision-1",
            run_id="run-1",
            hospital_hipe="9001",
            as_of_date="2026-08-30",
            high_hazard_threshold=1.2,
            rankings=[],
            rule_summaries=[],
        )
