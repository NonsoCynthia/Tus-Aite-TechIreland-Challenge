"""Full sort key, ranking, positioning and exclusion.

Per ADR-003/ADR-004, clinical priority (`severity_rank`) is a hard band
boundary; per ADR-005/ADR-010, priority within a band never lets capacity
touch an individual referral, and waiting time is percentile rank, not
min-max. Per ADR-008, a referral with no urgency score is excluded and
reported, never defaulted to zero.

This module composes `coordinator.app.bands` (CPC bands) and
`coordinator.app.priority` (scarcity/alpha/priority) into the full sort key
and the ranked, positioned decision. Citations and decision assembly are
Phase 5.
"""

from dataclasses import dataclass
from typing import Any

from coordinator.app.bands import SEVERITY_RANK, order_by_band
from coordinator.app.priority import (
    ALPHA_MAX,
    ALPHA_MIN,
    CapacityDirection,
    compute_alpha,
    compute_priority,
    compute_scarcity,
    normalise_wait_within_band,
)

CRT_BREACHED_RANK: dict[bool | None, int] = {True: 2, False: 1, None: 0}
"""Explicit ordering for the three-valued `crt_breached` (spec.md FR5's
`crt_breached desc`): breached (`True`) ranks highest, not breached
(`False`) next, "no CRT applies to this CPC" (`None`) last. Python will
not order `None` against `bool` on its own, so `sort_key` looks this value
up rather than comparing `crt_breached` directly.
"""

_UNCATEGORISED_BAND_ORDER = 1
_EXCLUDED_BAND_ORDER = 2
_EXCLUDED_CPC = 4


def _severity_rank_and_band_order(cpc: int | None) -> tuple[int, int]:
    """Resolves the two band-level sort components for one `cpc` value.

    Args:
        cpc: The referral's NTPF `cpc` code, or `None` if uncategorised.

    Returns:
        `(severity_rank, band_order)`. `band_order` is `0` for every
        categorised referral, `1` for uncategorised, `2` for Excluded
        (ADR-006) -- so the two tails sort after every categorised band
        and never interleave with each other. `severity_rank` is `0` for
        both tails (irrelevant there, since `band_order` already separates
        them from categorised referrals and from each other).
    """
    if cpc is None:
        return 0, _UNCATEGORISED_BAND_ORDER
    if cpc == _EXCLUDED_CPC:
        return 0, _EXCLUDED_BAND_ORDER
    return SEVERITY_RANK[cpc], 0


def sort_key(
    referral: dict[str, Any],
) -> tuple[int, int, int, float, str, str]:
    """The full ranking sort key (spec.md FR5).

    `(band_order, severity_rank, -crt_rank, -priority, referral_date,
    pathway_number)`, i.e. severity_rank ascending, crt_breached
    descending, priority descending, referral_date ascending,
    pathway_number ascending -- with `band_order` prepended so the two
    uncategorised tails (ADR-006) sort after every categorised band
    rather than mixing in via a shared placeholder `severity_rank`.

    Works directly on a raw `cpc`-carrying referral dict; it does not
    require `coordinator.app.bands.order_by_band` to have run first.
    `priority` defaults to `0.0` when absent, so this key is also usable
    before priority has been computed (e.g. to test `crt_breached`
    ordering in isolation).

    Args:
        referral: A cohort-shaped referral dict carrying at least `cpc`,
            `crt_breached`, `referral_date`, `pathway_number`, and
            optionally `priority`.

    Returns:
        The sort key tuple, ready for `sorted(..., key=sort_key)`.
    """
    severity_rank, band_order = _severity_rank_and_band_order(referral.get("cpc"))
    crt_rank = CRT_BREACHED_RANK[referral.get("crt_breached")]
    priority = referral.get("priority", 0.0)
    return (
        band_order,
        severity_rank,
        -crt_rank,
        -priority,
        referral["referral_date"],
        referral["pathway_number"],
    )


@dataclass
class RankedCohort:
    """The result of ranking one hospital-day cohort.

    Attributes:
        rankings: Referrals with a score, sorted by `sort_key` and
            carrying a 1-based, contiguous, unique `position`.
        excluded: Referrals with no urgency score, each carrying an
            `exclusion_reason` -- reported, never defaulted (ADR-008).
    """

    rankings: list[dict[str, Any]]
    excluded: list[dict[str, Any]]


def rank_cohort(
    referrals: list[dict[str, Any]],
    *,
    capacity_direction: CapacityDirection | None,
    alpha_min: float = ALPHA_MIN,
    alpha_max: float = ALPHA_MAX,
) -> RankedCohort:
    """Bands, scores, sorts and positions a cohort into one decision.

    Args:
        referrals: Cohort-shaped referral dicts, each carrying `cpc`,
            `specialty_hipe`, `crt_breached`, `referral_date`,
            `adjusted_wait_days`, `pathway_number`, and (where available)
            `urgency_score`/`capacity_score`.
        capacity_direction: The capacity sign convention. Required, with
            no default (ADR-007).
        alpha_min: Alpha at scarcity 0. Defaults to `ALPHA_MIN`.
        alpha_max: Alpha at scarcity 1. Defaults to `ALPHA_MAX`.

    Returns:
        A `RankedCohort`: `rankings` sorted and positioned, `excluded`
        reporting every referral with no urgency score.
    """
    banded = order_by_band(referrals)

    with_urgency = [r for r in banded if r.get("urgency_score") is not None]
    excluded = [
        {**r, "exclusion_reason": "missing_urgency_score"}
        for r in banded
        if r.get("urgency_score") is None
    ]

    # Scarcity is a fact about specialties present in the cohort, not
    # about which referrals have an urgency score yet -- but a referral
    # missing capacity_score entirely contributes nothing to it (FR2: a
    # referral missing only capacity_score is still ranked normally).
    distinct_capacity_by_specialty: dict[str, float] = {
        r["specialty_hipe"]: r["capacity_score"]
        for r in banded
        if r.get("capacity_score") is not None
    }
    scarcity = compute_scarcity(list(distinct_capacity_by_specialty.values()), capacity_direction)
    alpha = compute_alpha(scarcity, alpha_min, alpha_max)

    waited = normalise_wait_within_band(with_urgency)
    prioritised = [
        {
            **r,
            "scarcity": scarcity,
            "alpha": alpha,
            "priority": compute_priority(r["urgency_score"], r["wait_normalised"], alpha),
        }
        for r in waited
    ]

    ranked = sorted(prioritised, key=sort_key)
    for position, referral in enumerate(ranked, start=1):
        referral["position"] = position

    return RankedCohort(rankings=ranked, excluded=excluded)
