"""Tier 1 tests for scarcity, alpha and within-band priority.

Covers plan.md Phase 3, tasks 3.1-3.6 (spec.md FR5/FR6, ADR-005, ADR-007).
Per `conductor/workflow.md` strict TDD: these tests are written and must
FAIL before `coordinator.app.priority` is implemented (task 3.7).

Expected API of the not-yet-written `coordinator.app.priority`:

- `ALPHA_MIN`, `ALPHA_MAX`: module constants, defaults 0.5 and 0.9.
- `compute_scarcity(capacity_scores, direction)`: scarcity from the
  distinct specialty capacity scores present in the cohort. `direction`
  is `"availability"` or `"pressure"`, with no default (ADR-007);
  `None` is rejected explicitly rather than silently accepted.
- `compute_alpha(scarcity, alpha_min=ALPHA_MIN, alpha_max=ALPHA_MAX)`.
- `normalise_wait_within_band(referrals)`: adds `wait_normalised` to each
  referral dict, min-max normalised against only the other referrals
  sharing its `band` (as annotated by `coordinator.app.bands`).
- `compute_priority(urgency_score, wait_normalised, alpha)`: the
  composite priority, `alpha * urgency + (1 - alpha) * wait_normalised`.
- `annotate_priority(referrals, *, capacity_direction, alpha_min=...,
  alpha_max=...)`: the full pipeline -- computes scarcity and alpha once
  for the whole decision, normalises waits within band, and adds
  `scarcity`, `alpha`, `wait_normalised` and `priority` to every referral.
  Crucially, `priority` never reads a referral's own `capacity_score`
  (ADR-005) -- only cohort-level `scarcity`/`alpha` are capacity-derived.

Referral dicts mirror the shape produced by
`coordinator.app.bands.order_by_band` (which adds `band`) plus
`urgency_score`/`capacity_score`, since the score-source seam (FR2) is out
of scope for this phase -- scores are hand-attached directly here.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from coordinator.app.bands import order_by_band
from coordinator.app.priority import (
    ALPHA_MAX,
    ALPHA_MIN,
    annotate_priority,
    compute_alpha,
    compute_priority,
    compute_scarcity,
    normalise_wait_within_band,
)

_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "cohort_9004_2026-08-30.json"


def _referral(pathway_number: str, **overrides: Any) -> dict[str, Any]:
    """Builds a minimal band-and-score-annotated referral dict.

    Args:
        pathway_number: The referral's pathway_number.
        **overrides: Fields to set on top of the defaults.

    Returns:
        A dict carrying the fields `priority.py`'s functions need: `band`,
        `specialty_hipe`, `urgency_score`, `capacity_score`,
        `adjusted_wait_days`.
    """
    referral: dict[str, Any] = {
        "pathway_number": pathway_number,
        "band": 1,
        "specialty_hipe": "1800",
        "urgency_score": 0.5,
        "capacity_score": 0.5,
        "adjusted_wait_days": 100,
    }
    referral.update(overrides)
    return referral


def _load_real_cohort() -> list[dict[str, Any]]:
    """Loads the real 9004/2026-08-30 fixture, banded via order_by_band."""
    with _FIXTURE_PATH.open() as f:
        cohort = json.load(f)["referrals"]
    return order_by_band(cohort)


def test_scarcity_computed_once_from_distinct_specialty_scores() -> None:
    """Scarcity is computed once per decision, at hospital level, from the
    *distinct* specialty capacity scores in the cohort -- not re-derived
    per referral and not weighted by how many referrals share a specialty
    (spec.md FR5).
    """
    # Specialty A (0.2) has two referrals, specialty B (0.8) has one. A
    # naive mean over referrals would give (0.2+0.2+0.8)/3 = 0.4; the
    # correct mean over the two *distinct* specialty scores is 0.5.
    referrals = [
        _referral("P-1", specialty_hipe="A", capacity_score=0.2),
        _referral("P-2", specialty_hipe="A", capacity_score=0.2),
        _referral("P-3", specialty_hipe="B", capacity_score=0.8),
    ]

    result = annotate_priority(referrals, capacity_direction="pressure")

    scarcities = {r["scarcity"] for r in result}
    assert scarcities == {0.5}, "scarcity must be identical for every referral"


def test_scarcity_identical_for_every_referral_in_the_decision() -> None:
    """Even with three distinct bands and specialties, every referral in
    the decision carries the same `scarcity` value (spec.md FR5)."""
    referrals = [
        _referral("P-1", band=1, specialty_hipe="A", capacity_score=0.1),
        _referral("P-2", band=2, specialty_hipe="B", capacity_score=0.9),
        _referral("P-3", band=3, specialty_hipe="C", capacity_score=0.5),
    ]

    result = annotate_priority(referrals, capacity_direction="availability")

    assert len({r["scarcity"] for r in result}) == 1
    assert len({r["alpha"] for r in result}) == 1


def test_availability_and_pressure_produce_inverse_scarcity() -> None:
    """`availability` gives scarcity = 1 - capacity; `pressure` gives
    scarcity = capacity -- inverse conventions on the same input
    (ADR-007)."""
    availability_scarcity = compute_scarcity([0.3], "availability")
    pressure_scarcity = compute_scarcity([0.3], "pressure")

    assert availability_scarcity == pytest.approx(0.7)
    assert pressure_scarcity == pytest.approx(0.3)
    assert availability_scarcity == pytest.approx(1 - pressure_scarcity)


def test_scarcity_refuses_unset_capacity_direction() -> None:
    """The agent refuses to compute scarcity when the capacity direction
    is unset -- no default, per ADR-007."""
    with pytest.raises(ValueError):
        compute_scarcity([0.5], None)


def test_alpha_stays_within_bounds_across_full_scarcity_range() -> None:
    """Alpha stays within [alpha_min, alpha_max] across the full scarcity
    range 0.0-1.0, and hits the bounds exactly at the extremes
    (spec.md FR5; defaults alpha_min=0.5, alpha_max=0.9)."""
    assert ALPHA_MIN == pytest.approx(0.5)
    assert ALPHA_MAX == pytest.approx(0.9)

    for scarcity in (0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0):
        alpha = compute_alpha(scarcity)
        assert ALPHA_MIN <= alpha <= ALPHA_MAX

    assert compute_alpha(0.0) == pytest.approx(ALPHA_MIN)
    assert compute_alpha(1.0) == pytest.approx(ALPHA_MAX)


def test_wait_normalised_within_band_degenerate_case() -> None:
    """When every wait in a band is equal, `wait_normalised` is defined
    explicitly as the neutral midpoint 0.5, rather than dividing by zero
    (spec.md FR5). Under percentile rank this falls out of the same rule
    that gives ties a shared percentile (ADR-010): with only one distinct
    wait value, every referral shares the 50th percentile.
    """
    referrals = [
        _referral("P-1", band=1, adjusted_wait_days=50),
        _referral("P-2", band=1, adjusted_wait_days=50),
        _referral("P-3", band=1, adjusted_wait_days=50),
    ]

    result = normalise_wait_within_band(referrals)

    assert all(r["wait_normalised"] == pytest.approx(0.5) for r in result)


def _expected_percentile_rank(wait: int, all_waits_in_band: list[int]) -> float:
    """Computes the expected percentile rank for one wait value.

    Per ADR-010: `wait_normalised` is percentile rank within band, with
    ties sharing a percentile -- the fraction of the band strictly below
    `wait`, plus half the fraction equal to it. This is the reference
    implementation the tests check `normalise_wait_within_band` against.

    Args:
        wait: The wait value to rank.
        all_waits_in_band: Every wait in the same band, including `wait`.

    Returns:
        The expected percentile rank, in [0, 1].
    """
    n = len(all_waits_in_band)
    count_less = sum(1 for w in all_waits_in_band if w < wait)
    count_equal = sum(1 for w in all_waits_in_band if w == wait)
    return (count_less + count_equal / 2) / n


def test_wait_normalised_is_percentile_rank_median_lands_near_half() -> None:
    """`wait_normalised` is the referral's percentile rank among the waits
    in its own band (ADR-010), verified against the real 9004/2026-08-30
    fixture. This is the property ADR-010 exists to secure: under the
    superseded min-max normalisation, the median referral in every band
    landed near 0.18 (waits 0-870ish, median ~150-180) because a handful
    of 800+ day outliers stretched the range. Under percentile rank the
    median referral in each band must land near 0.5.
    """
    banded = _load_real_cohort()
    result = normalise_wait_within_band(banded)

    by_band: dict[Any, list[dict[str, Any]]] = {}
    for referral in result:
        by_band.setdefault(referral["band"], []).append(referral)

    for band, band_referrals in by_band.items():
        waits = [r["adjusted_wait_days"] for r in band_referrals]
        for referral in band_referrals:
            expected = _expected_percentile_rank(referral["adjusted_wait_days"], waits)
            assert referral["wait_normalised"] == pytest.approx(expected, abs=1e-9), band

        # The property ADR-010 exists to secure: the median referral's
        # wait_normalised is near 0.5, not compressed toward ~0.18 by a
        # handful of 800+ day outliers, in every categorised band.
        if band in ("uncategorised", "excluded"):
            continue
        sorted_waits = sorted(waits)
        median_wait = sorted_waits[len(sorted_waits) // 2]
        median_referral = next(r for r in band_referrals if r["adjusted_wait_days"] == median_wait)
        assert median_referral["wait_normalised"] == pytest.approx(0.5, abs=0.1), band


def test_wait_normalised_ties_share_a_percentile_and_are_order_independent() -> None:
    """Referrals sharing an `adjusted_wait_days` value receive an
    identical `wait_normalised`, and shuffling the input cohort does not
    change any referral's value -- the determinism precondition for
    NFR4. A rank that depended on input order (e.g. breaking ties by
    position) would make ranking the same cohort twice, or a shuffled
    copy of it, produce different output.
    """
    referrals = [
        _referral("P-1", band=1, adjusted_wait_days=30),
        _referral("P-2", band=1, adjusted_wait_days=90),
        _referral("P-3", band=1, adjusted_wait_days=90),
        _referral("P-4", band=1, adjusted_wait_days=90),
        _referral("P-5", band=1, adjusted_wait_days=150),
    ]

    result = normalise_wait_within_band(referrals)
    by_pathway = {r["pathway_number"]: r["wait_normalised"] for r in result}

    # The three tied referrals (wait=90) share one percentile.
    assert by_pathway["P-2"] == pytest.approx(by_pathway["P-3"])
    assert by_pathway["P-3"] == pytest.approx(by_pathway["P-4"])

    shuffled = [referrals[3], referrals[0], referrals[4], referrals[2], referrals[1]]
    shuffled_result = normalise_wait_within_band(shuffled)
    shuffled_by_pathway = {r["pathway_number"]: r["wait_normalised"] for r in shuffled_result}

    assert shuffled_by_pathway == by_pathway


def test_capacity_cannot_reorder_referrals_within_a_band() -> None:
    """THE ADR-005 TEST.

    Two referrals in the same band, identical in urgency and wait,
    differ only in their specialty's capacity score. Their computed
    priority -- and therefore their relative order -- must be unchanged.
    This is what stops the system ranking patients by which department
    referred them (ADR-005): capacity may only modulate the cohort-level
    weight (`alpha`), shared by every referral, never enter an individual
    referral's own priority calculation.
    """
    referral_low_capacity_specialty = _referral(
        "P-LOW-CAP",
        band=1,
        specialty_hipe="CONGESTED",
        capacity_score=0.05,
        urgency_score=0.6,
        adjusted_wait_days=100,
    )
    referral_high_capacity_specialty = _referral(
        "P-HIGH-CAP",
        band=1,
        specialty_hipe="UNCONGESTED",
        capacity_score=0.95,
        urgency_score=0.6,
        adjusted_wait_days=100,
    )

    result = annotate_priority(
        [referral_low_capacity_specialty, referral_high_capacity_specialty],
        capacity_direction="pressure",
    )

    priorities = {r["pathway_number"]: r["priority"] for r in result}
    assert priorities["P-LOW-CAP"] == pytest.approx(priorities["P-HIGH-CAP"])


def test_raising_scarcity_increases_urgency_influence_over_wait() -> None:
    """Raising scarcity increases urgency's influence relative to waiting
    time (spec.md FR5, ADR-005): two referrals where urgency and wait
    rank them oppositely swap their priority order between low and high
    scarcity.
    """
    # A: high urgency, low (normalised) wait. B: low urgency, high wait.
    urgency_a, wait_normalised_a = 0.9, 0.0
    urgency_b, wait_normalised_b = 0.1, 1.0

    low_scarcity_alpha = compute_alpha(0.0)
    high_scarcity_alpha = compute_alpha(1.0)

    priority_a_low = compute_priority(urgency_a, wait_normalised_a, low_scarcity_alpha)
    priority_b_low = compute_priority(urgency_b, wait_normalised_b, low_scarcity_alpha)
    assert priority_b_low > priority_a_low, "low scarcity should order by wait"

    priority_a_high = compute_priority(urgency_a, wait_normalised_a, high_scarcity_alpha)
    priority_b_high = compute_priority(urgency_b, wait_normalised_b, high_scarcity_alpha)
    assert priority_a_high > priority_b_high, "high scarcity should order by urgency"
