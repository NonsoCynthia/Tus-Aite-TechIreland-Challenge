"""Pure metric calculations for system-level evaluation.

The evaluator is the only code path that may combine system outputs with
`eval.ground_truth`. Keep this module database-free so the scoring semantics
are easy to test and review.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from statistics import mean, median


CRT_RULE_IDS = frozenset({"RULE-CRT-URGENT", "RULE-CRT-SEMI"})


@dataclass(frozen=True)
class GroundTruthRanking:
    """One ranked referral joined to the held-out answer key."""

    position: int
    hospital_hipe: str
    pathway_number: str
    latent_hazard: float | None
    deterioration_date: date | None
    deterioration_type: str | None

    @property
    def has_ground_truth(self) -> bool:
        return self.latent_hazard is not None

    @property
    def deteriorated(self) -> bool:
        return self.deterioration_date is not None


@dataclass(frozen=True)
class RuleSummary:
    """Aggregate result for one stored rule check."""

    rule_id: str
    total: int
    failed: int

    @property
    def passed(self) -> int:
        return self.total - self.failed


@dataclass(frozen=True)
class EvaluationReport:
    """Decision-level evaluation metrics suitable for JSON or console output."""

    decision_id: str
    run_id: str
    hospital_hipe: str
    as_of_date: str
    top_k: int
    ranked_count: int
    ranked_with_ground_truth: int
    missed_crt_deadlines: int
    triage_turnaround_failures: int
    total_deteriorations: int
    deteriorations_in_top_k: int
    deterioration_capture_at_k: float | None
    mean_rank_of_deteriorations: float | None
    median_rank_of_deteriorations: float | None
    mean_latent_hazard_top_k: float | None
    mean_latent_hazard_rest: float | None
    high_hazard_threshold: float
    high_hazard_total: int
    high_hazard_in_top_k: int
    high_hazard_capture_at_k: float | None
    rule_summaries: tuple[RuleSummary, ...]

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["rule_summaries"] = [asdict(summary) for summary in self.rule_summaries]
        return data

    def render_text(self) -> str:
        capture = _format_rate(self.deterioration_capture_at_k)
        hazard_capture = _format_rate(self.high_hazard_capture_at_k)
        lines = [
            f"Decision {self.decision_id} ({self.hospital_hipe}, {self.as_of_date})",
            f"Run: {self.run_id}",
            "",
            "Compliance",
            f"- Missed CPC/CRT deadlines: {self.missed_crt_deadlines}",
            f"- Triage turnaround failures: {self.triage_turnaround_failures}",
            "",
            "Held-out outcome evaluation",
            f"- Ranked referrals with ground truth: {self.ranked_with_ground_truth}/{self.ranked_count}",
            (
                f"- Deteriorations captured in top {self.top_k}: "
                f"{self.deteriorations_in_top_k}/{self.total_deteriorations} ({capture})"
            ),
            (
                f"- High-hazard referrals captured in top {self.top_k}: "
                f"{self.high_hazard_in_top_k}/{self.high_hazard_total} ({hazard_capture})"
            ),
            f"- Mean latent hazard, top {self.top_k}: {_format_number(self.mean_latent_hazard_top_k)}",
            f"- Mean latent hazard, rest: {_format_number(self.mean_latent_hazard_rest)}",
            "",
            (
                "Note: deterioration metrics use the synthetic, unvalidated "
                "held-out risk model. Lead with CPC/CRT deadline results."
            ),
        ]
        return "\n".join(lines)


def evaluate_rankings(
    *,
    decision_id: str,
    run_id: str,
    hospital_hipe: str,
    as_of_date: str,
    rankings: list[GroundTruthRanking],
    rule_summaries: list[RuleSummary],
    top_k: int = 10,
    high_hazard_threshold: float = 0.7,
) -> EvaluationReport:
    """Evaluate a ranked decision against compliance checks and answer key.

    Args:
        decision_id: The `agent.decisions.decision_id` being evaluated.
        run_id: The run that produced the decision.
        hospital_hipe: Hospital identifier for display/reporting.
        as_of_date: Decision date, already serialised for output.
        rankings: Ranked referrals joined to `eval.ground_truth`.
        rule_summaries: Aggregated `agent.rule_checks` rows.
        top_k: Prefix size to use for capture metrics.
        high_hazard_threshold: Inclusive threshold for hidden hazard capture.

    Returns:
        An immutable `EvaluationReport`.
    """
    if top_k <= 0:
        raise ValueError("top_k must be positive")
    if not 0 <= high_hazard_threshold <= 1:
        raise ValueError("high_hazard_threshold must be between 0 and 1")

    ranked = sorted(rankings, key=lambda row: row.position)
    effective_k = min(top_k, len(ranked))
    top = ranked[:effective_k]
    rest = ranked[effective_k:]

    deteriorated = [row for row in ranked if row.deteriorated]
    deteriorated_top = [row for row in top if row.deteriorated]
    high_hazard = [
        row
        for row in ranked
        if row.latent_hazard is not None and row.latent_hazard >= high_hazard_threshold
    ]
    high_hazard_top = [
        row
        for row in top
        if row.latent_hazard is not None and row.latent_hazard >= high_hazard_threshold
    ]

    missed_crt_deadlines = sum(
        summary.failed for summary in rule_summaries if summary.rule_id in CRT_RULE_IDS
    )
    triage_turnaround_failures = sum(
        summary.failed for summary in rule_summaries if summary.rule_id == "RULE-TRIAGE-TURNAROUND"
    )
    deterioration_positions = [row.position for row in deteriorated]

    return EvaluationReport(
        decision_id=decision_id,
        run_id=run_id,
        hospital_hipe=hospital_hipe,
        as_of_date=as_of_date,
        top_k=effective_k,
        ranked_count=len(ranked),
        ranked_with_ground_truth=sum(row.has_ground_truth for row in ranked),
        missed_crt_deadlines=missed_crt_deadlines,
        triage_turnaround_failures=triage_turnaround_failures,
        total_deteriorations=len(deteriorated),
        deteriorations_in_top_k=len(deteriorated_top),
        deterioration_capture_at_k=_rate(len(deteriorated_top), len(deteriorated)),
        mean_rank_of_deteriorations=_mean(deterioration_positions),
        median_rank_of_deteriorations=_median(deterioration_positions),
        mean_latent_hazard_top_k=_mean_hazard(top),
        mean_latent_hazard_rest=_mean_hazard(rest),
        high_hazard_threshold=high_hazard_threshold,
        high_hazard_total=len(high_hazard),
        high_hazard_in_top_k=len(high_hazard_top),
        high_hazard_capture_at_k=_rate(len(high_hazard_top), len(high_hazard)),
        rule_summaries=tuple(sorted(rule_summaries, key=lambda summary: summary.rule_id)),
    )


def _rate(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator


def _mean(values: list[int] | list[float]) -> float | None:
    if not values:
        return None
    return float(mean(values))


def _median(values: list[int] | list[float]) -> float | None:
    if not values:
        return None
    return float(median(values))


def _mean_hazard(rows: list[GroundTruthRanking]) -> float | None:
    values = [row.latent_hazard for row in rows if row.latent_hazard is not None]
    if not values:
        return None
    return float(mean(values))


def _format_rate(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.1%}"


def _format_number(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.3f}"
