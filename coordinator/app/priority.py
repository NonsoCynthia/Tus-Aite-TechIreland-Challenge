"""Scarcity, alpha and within-band priority.

Per ADR-005 (`conductor/tracks/coordinating-agent_20260906/decisions.md`),
capacity modulates the weight given to urgency versus waiting time --
never an individual referral's own score. Per ADR-007, the capacity sign
convention is required configuration with no default. Per ADR-010,
`wait_normalised` is percentile rank within band, not min-max, so one
long-waiting outlier cannot flatten the rest of the band.

This module computes scarcity, alpha and priority only. CPC band
resolution is `coordinator.app.bands`; the full sort key, rule checks and
citations are Phase 4/5.
"""

from typing import Any, Final, Literal

CapacityDirection = Literal["availability", "pressure"]
"""The two accepted capacity-score sign conventions (ADR-007).

`availability`: 1.0 means most capacity free, so `scarcity = 1 - capacity`.
`pressure`: 1.0 means maximum pressure, so `scarcity = capacity`.
"""

ALPHA_MIN: Final[float] = 0.5
ALPHA_MAX: Final[float] = 0.9
"""Default bounds on alpha (ADR-005): urgency never counts for less than
waiting time (`ALPHA_MIN`), and waiting time never drops out of the
ordering entirely (`ALPHA_MAX`). Deliberate, documented choices, not
fitted quantities.
"""


def compute_scarcity(capacity_scores: list[float], direction: CapacityDirection | None) -> float:
    """Computes cohort-level scarcity from distinct specialty capacity scores.

    Scarcity is one property of the whole hospital-day (ADR-005), so it is
    the mean of the *distinct* specialty capacity scores passed in -- the
    caller (`annotate_priority`) is responsible for de-duplicating by
    specialty before calling this.

    Args:
        capacity_scores: The distinct specialty capacity scores present in
            the cohort.
        direction: The capacity sign convention. Required, with no
            default (ADR-007) -- passing `None` is refused rather than
            silently assumed.

    Returns:
        A single scarcity value in [0, 1].

    Raises:
        ValueError: If `direction` is `None`.
    """
    if direction is None:
        raise ValueError(
            "capacity direction is required configuration with no default "
            "(ADR-007); refusing to guess whether capacity_score means "
            "availability or pressure"
        )

    mean_capacity = sum(capacity_scores) / len(capacity_scores)
    if direction == "availability":
        return 1 - mean_capacity
    return mean_capacity


def compute_alpha(
    scarcity: float, alpha_min: float = ALPHA_MIN, alpha_max: float = ALPHA_MAX
) -> float:
    """Maps scarcity to alpha, the urgency/wait weight (ADR-005).

    Args:
        scarcity: Cohort-level scarcity, in [0, 1].
        alpha_min: Alpha at scarcity 0. Defaults to `ALPHA_MIN`.
        alpha_max: Alpha at scarcity 1. Defaults to `ALPHA_MAX`.

    Returns:
        Alpha, linearly interpolated between `alpha_min` and `alpha_max`.
    """
    return alpha_min + (alpha_max - alpha_min) * scarcity


def _percentile_rank(wait: int, waits_in_band: list[int]) -> float:
    """Computes one wait's percentile rank within its band (ADR-010).

    Ties share a percentile: the rank is the fraction of the band
    strictly below `wait`, plus half the fraction equal to it. This keeps
    the result independent of input order, which determinism (NFR4)
    requires -- a rank that depended on position would let a shuffled
    cohort produce a different ranking.

    Args:
        wait: The wait value to rank.
        waits_in_band: Every wait in the same band, including `wait`.

    Returns:
        The percentile rank, in [0, 1]. A band with one distinct value
        (including the degenerate all-equal case) yields 0.5 for every
        referral, rather than dividing by zero.
    """
    n = len(waits_in_band)
    count_less = sum(1 for w in waits_in_band if w < wait)
    count_equal = sum(1 for w in waits_in_band if w == wait)
    return (count_less + count_equal / 2) / n


def normalise_wait_within_band(referrals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Adds `wait_normalised` to each referral, percentile rank within band.

    Args:
        referrals: Cohort-shaped referral dicts, each carrying `band`
            (as annotated by `coordinator.app.bands.order_by_band`) and
            `adjusted_wait_days`.

    Returns:
        A new list, same order as the input, each referral with
        `wait_normalised` added.
    """
    waits_by_band: dict[Any, list[int]] = {}
    for referral in referrals:
        waits_by_band.setdefault(referral["band"], []).append(referral["adjusted_wait_days"])

    return [
        {
            **referral,
            "wait_normalised": _percentile_rank(
                referral["adjusted_wait_days"], waits_by_band[referral["band"]]
            ),
        }
        for referral in referrals
    ]


def compute_priority(urgency_score: float, wait_normalised: float, alpha: float) -> float:
    """Computes the composite within-band priority (ADR-005).

    Args:
        urgency_score: The referral's urgency score, in [0, 1].
        wait_normalised: The referral's percentile rank within its band
            (ADR-010), in [0, 1].
        alpha: The urgency/wait weight for this decision (`compute_alpha`).

    Returns:
        `alpha * urgency_score + (1 - alpha) * wait_normalised`.
    """
    return alpha * urgency_score + (1 - alpha) * wait_normalised


def annotate_priority(
    referrals: list[dict[str, Any]],
    *,
    capacity_direction: CapacityDirection | None,
    alpha_min: float = ALPHA_MIN,
    alpha_max: float = ALPHA_MAX,
) -> list[dict[str, Any]]:
    """Computes scarcity, alpha, wait_normalised and priority for a cohort.

    Scarcity and alpha are computed once for the whole decision and are
    identical for every referral (ADR-005). `priority` never reads a
    referral's own `capacity_score` -- only the shared, cohort-level
    `scarcity`/`alpha` are capacity-derived, so capacity cannot reorder
    two referrals within a band.

    Args:
        referrals: Cohort-shaped referral dicts, each carrying `band`,
            `specialty_hipe`, `urgency_score`, `capacity_score` and
            `adjusted_wait_days`.
        capacity_direction: The capacity sign convention. Required, with
            no default (ADR-007).
        alpha_min: Alpha at scarcity 0. Defaults to `ALPHA_MIN`.
        alpha_max: Alpha at scarcity 1. Defaults to `ALPHA_MAX`.

    Returns:
        A new list, same order as the input, each referral with
        `scarcity`, `alpha`, `wait_normalised` and `priority` added.
    """
    distinct_capacity_by_specialty: dict[str, float] = {
        referral["specialty_hipe"]: referral["capacity_score"] for referral in referrals
    }
    scarcity = compute_scarcity(list(distinct_capacity_by_specialty.values()), capacity_direction)
    alpha = compute_alpha(scarcity, alpha_min, alpha_max)

    waited = normalise_wait_within_band(referrals)
    return [
        {
            **referral,
            "scarcity": scarcity,
            "alpha": alpha,
            "priority": compute_priority(
                referral["urgency_score"], referral["wait_normalised"], alpha
            ),
        }
        for referral in waited
    ]
