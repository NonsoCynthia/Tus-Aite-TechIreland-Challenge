"""Tier 1 tests for the full sort key, ranking, determinism and exclusion.

Covers plan.md Phase 4, tasks 4.1-4.6 (spec.md FR5/FR10, ADR-003, ADR-004,
ADR-005, ADR-010). Per `conductor/workflow.md` strict TDD: these tests are
written and must FAIL before `coordinator.app.ranking` is implemented
(task 4.10).

Expected API of the not-yet-written `coordinator.app.ranking`:

- `CRT_BREACHED_RANK: dict[bool | None, int]`: the documented ordering for
  the three-valued `crt_breached` (`True` > `False` > `None`), since
  `crt_breached desc` in the sort key (spec.md FR5) can't rely on Python's
  native ordering -- `None` does not compare against `bool`.
- `sort_key(referral)`: the pure key function implementing
  `(severity_rank, crt_breached desc, priority desc, referral_date asc,
  pathway_number asc)`, extended so the two tail groups (no severity_rank)
  still sort deterministically after every categorised band and stay
  separated from each other (ADR-006) -- it composes with
  `coordinator.app.bands`'s band ordering.
- `RankedCohort`: a small container with `.rankings` (ranked, positioned
  referrals) and `.excluded` (referrals with no urgency score, each
  carrying `exclusion_reason`).
- `rank_cohort(referrals, *, capacity_direction, alpha_min=..., alpha_max=
  ...)`: the full pipeline -- bands the cohort, excludes referrals with no
  `urgency_score` (ADR-008; a referral missing only `capacity_score` is
  still ranked, spec.md FR2), computes priority for the rest, sorts by
  `sort_key`, and assigns 1-based, contiguous, unique `position`.

Hand-built cohorts are cohort-shaped dicts (as `retrieval.app.db.get_cohort`
returns) plus `urgency_score`/`capacity_score` hand-attached, since the
score-source seam (FR2) is out of scope here.
"""

import json
import random
from pathlib import Path
from typing import Any

from coordinator.app.ranking import CRT_BREACHED_RANK, rank_cohort, sort_key

_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "cohort_9004_2026-08-30.json"


def _referral(pathway_number: str, **overrides: Any) -> dict[str, Any]:
    """Builds a minimal cohort-shaped, score-attached referral dict.

    Args:
        pathway_number: The referral's pathway_number.
        **overrides: Fields to set on top of the defaults.

    Returns:
        A dict with the fields `rank_cohort` needs: `cpc`, `specialty_hipe`,
        `crt_breached`, `referral_date`, `adjusted_wait_days`,
        `urgency_score`, `capacity_score`, `triage_status`.
    """
    referral: dict[str, Any] = {
        "hospital_hipe": "9004",
        "pathway_number": pathway_number,
        "specialty_hipe": "1800",
        "cpc": 1,
        "crt_breached": None,
        "triage_status": "triaged",
        "adjusted_wait_days": 100,
        "days_awaiting_triage": None,
        "referral_date": "2026-01-01",
        "urgency_score": 0.5,
        "capacity_score": 0.5,
    }
    referral.update(overrides)
    return referral


def _load_real_cohort() -> list[dict[str, Any]]:
    """Loads the real 9004/2026-08-30 fixture, unmodified."""
    with _FIXTURE_PATH.open() as f:
        return json.load(f)["referrals"]


def _with_synthetic_scores(referrals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Attaches deterministic, order-independent synthetic scores.

    The real cohort fixture has no `urgency_score`/`capacity_score` at all
    (neither agent exists yet). Scores here are a pure function of each
    referral's own `pathway_number`/`specialty_hipe`, never of its
    position in the input list, so re-ordering the input cannot change
    any referral's assigned score -- required for the determinism test
    (4.4) to be a real test of `rank_cohort`, not of stable input scores.

    Args:
        referrals: Cohort-shaped referral dicts, unmodified.

    Returns:
        A new list with `urgency_score` and `capacity_score` added.
    """
    specialties = sorted({r["specialty_hipe"] for r in referrals})
    capacity_by_specialty = {
        specialty: (i + 1) / (len(specialties) + 1) for i, specialty in enumerate(specialties)
    }
    return [
        {
            **r,
            "urgency_score": (hash(r["pathway_number"]) % 1000) / 1000,
            "capacity_score": capacity_by_specialty[r["specialty_hipe"]],
        }
        for r in referrals
    ]


def test_crt_breached_rank_is_documented_true_false_null() -> None:
    """`CRT_BREACHED_RANK` orders `True` > `False` > `None` -- breached
    first, then not breached, then "no CRT applies to this CPC" last
    (spec.md FR5's `crt_breached desc`)."""
    assert CRT_BREACHED_RANK[True] > CRT_BREACHED_RANK[False]
    assert CRT_BREACHED_RANK[False] > CRT_BREACHED_RANK[None]


def test_mixed_crt_breached_values_sort_without_raising() -> None:
    """A cohort mixing all three `crt_breached` values sorts without
    raising -- Python will not order `None` against `bool` natively, so
    `sort_key` must handle this explicitly -- and in the documented
    True > False > None order."""
    breached = _referral("P-TRUE", crt_breached=True)
    not_breached = _referral("P-FALSE", crt_breached=False)
    not_applicable = _referral("P-NULL", crt_breached=None)

    ordered = sorted([not_applicable, breached, not_breached], key=sort_key)

    assert [r["pathway_number"] for r in ordered] == ["P-TRUE", "P-FALSE", "P-NULL"]


def test_full_sort_key_ordering_band_by_band() -> None:
    """Full sort key ordering, band by band: severity_rank first, then
    crt_breached desc, then priority desc, then referral_date asc, then
    pathway_number asc (spec.md FR5)."""
    result = rank_cohort(
        [
            # Semi-urgent, lower band than urgent -- must rank after it
            # regardless of its own crt_breached/priority/date.
            _referral(
                "P-SEMI",
                cpc=3,
                crt_breached=True,
                urgency_score=1.0,
                adjusted_wait_days=900,
            ),
            # Urgent, not breached, higher priority than the other urgent
            # referral below (higher urgency_score, same band otherwise).
            _referral(
                "P-URGENT-BREACHED",
                cpc=1,
                crt_breached=True,
                urgency_score=0.5,
                adjusted_wait_days=50,
            ),
            _referral(
                "P-URGENT-NOT-BREACHED",
                cpc=1,
                crt_breached=False,
                urgency_score=0.9,
                adjusted_wait_days=50,
            ),
        ],
        capacity_direction="pressure",
    )

    order = [r["pathway_number"] for r in result.rankings]
    # Both urgent referrals rank above the semi-urgent one regardless of
    # its higher urgency_score/crt_breached (ADR-003/ADR-004). Within the
    # urgent band, crt_breached=True outranks crt_breached=False.
    assert order == ["P-URGENT-BREACHED", "P-URGENT-NOT-BREACHED", "P-SEMI"]


def test_urgent_never_ranked_below_semi_urgent_across_full_score_range() -> None:
    """An urgent referral is never ranked below a semi-urgent one, at any
    score values -- swept across urgency and capacity's full 0-1 range
    (spec.md FR5, ADR-004)."""
    score_grid = (0.0, 0.25, 0.5, 0.75, 1.0)
    for urgent_urgency in score_grid:
        for semi_urgency in score_grid:
            for urgent_capacity in score_grid:
                for semi_capacity in score_grid:
                    result = rank_cohort(
                        [
                            _referral(
                                "P-SEMI",
                                cpc=3,
                                urgency_score=semi_urgency,
                                capacity_score=semi_capacity,
                                specialty_hipe="A",
                            ),
                            _referral(
                                "P-URGENT",
                                cpc=1,
                                urgency_score=urgent_urgency,
                                capacity_score=urgent_capacity,
                                specialty_hipe="B",
                            ),
                        ],
                        capacity_direction="pressure",
                    )
                    positions = {r["pathway_number"]: r["position"] for r in result.rankings}
                    assert positions["P-URGENT"] < positions["P-SEMI"], (
                        urgent_urgency,
                        semi_urgency,
                        urgent_capacity,
                        semi_capacity,
                    )


def test_identical_referral_date_resolves_via_pathway_number() -> None:
    """Identical `referral_date` (and everything else that sorts before
    it) resolves deterministically via `pathway_number` ascending --
    the final tiebreak that guarantees a total order (spec.md FR5)."""
    result = rank_cohort(
        [
            _referral("P-002", referral_date="2026-01-01"),
            _referral("P-001", referral_date="2026-01-01"),
            _referral("P-003", referral_date="2026-01-01"),
        ],
        capacity_direction="pressure",
    )

    order = [r["pathway_number"] for r in result.rankings]
    assert order == ["P-001", "P-002", "P-003"]


def test_ranking_same_cohort_twice_and_shuffled_is_identical() -> None:
    """NFR4: ranking the same cohort twice, and a shuffled copy of it,
    produces identical output. Uses the real 9004/2026-08-30 fixture with
    several shuffles under a fixed seed."""
    cohort = _with_synthetic_scores(_load_real_cohort())

    baseline = rank_cohort(cohort, capacity_direction="pressure")
    baseline_order = [(r["pathway_number"], r["position"]) for r in baseline.rankings]

    repeat = rank_cohort(cohort, capacity_direction="pressure")
    repeat_order = [(r["pathway_number"], r["position"]) for r in repeat.rankings]
    assert repeat_order == baseline_order

    rng = random.Random(20260906)
    for _ in range(5):
        shuffled = cohort.copy()
        rng.shuffle(shuffled)
        shuffled_result = rank_cohort(shuffled, capacity_direction="pressure")
        shuffled_order = [(r["pathway_number"], r["position"]) for r in shuffled_result.rankings]
        assert shuffled_order == baseline_order


def test_positions_are_one_based_contiguous_and_unique() -> None:
    """Positions are 1-based, contiguous, and unique across the decision
    (`agent.decision_rankings` `dr_unique_position`)."""
    cohort = _with_synthetic_scores(_load_real_cohort())
    result = rank_cohort(cohort, capacity_direction="pressure")

    positions = [r["position"] for r in result.rankings]
    assert positions == list(range(1, len(positions) + 1))
    assert len(positions) == len(set(positions))


def test_referral_with_no_urgency_score_is_excluded_and_reported() -> None:
    """A referral with no urgency score is excluded from the decision and
    reported, never defaulted to zero (ADR-008). A referral missing only
    its capacity score is still ranked normally (spec.md FR2)."""
    has_urgency = _referral("P-HAS-URGENCY", urgency_score=0.7)
    no_urgency = _referral("P-NO-URGENCY")
    del no_urgency["urgency_score"]
    no_capacity_only = _referral("P-NO-CAPACITY-ONLY", urgency_score=0.3)
    del no_capacity_only["capacity_score"]

    result = rank_cohort([has_urgency, no_urgency, no_capacity_only], capacity_direction="pressure")

    ranked_pathways = {r["pathway_number"] for r in result.rankings}
    excluded_pathways = {r["pathway_number"] for r in result.excluded}

    assert ranked_pathways == {"P-HAS-URGENCY", "P-NO-CAPACITY-ONLY"}
    assert excluded_pathways == {"P-NO-URGENCY"}
    excluded = next(r for r in result.excluded if r["pathway_number"] == "P-NO-URGENCY")
    assert excluded["exclusion_reason"]
    # No referral is defaulted to urgency_score=0 and silently ranked.
    assert not any(r["pathway_number"] == "P-NO-URGENCY" for r in result.rankings)


def test_referral_with_no_urgency_score_key_missing_entirely_is_excluded() -> None:
    """The same exclusion applies when `urgency_score` is `None`, not
    just when the key is entirely absent -- a missing score is missing
    information either way (ADR-008)."""
    referral = _referral("P-NULL-URGENCY", urgency_score=None)

    result = rank_cohort([referral], capacity_direction="pressure")

    assert result.rankings == []
    assert len(result.excluded) == 1
    assert result.excluded[0]["pathway_number"] == "P-NULL-URGENCY"


def test_paediatric_referral_is_excluded_even_if_stale_urgency_score_exists() -> None:
    """ADR-007 is a ranking guardrail too: an old or accidental NEWS2 score
    must not place a paediatric referral in the adult-ranked list."""
    adult = _referral("P-ADULT", specialty_hipe="0600", urgency_score=0.1, capacity_score=0.1)
    paediatric = _referral(
        "P-PAED",
        specialty_hipe="0601",
        urgency_score=1.0,
        capacity_score=1.0,
    )

    result = rank_cohort([paediatric, adult], capacity_direction="pressure")

    assert [r["pathway_number"] for r in result.rankings] == ["P-ADULT"]
    excluded = {r["pathway_number"]: r for r in result.excluded}
    assert excluded["P-PAED"]["exclusion_reason"] == "paediatric_news2_not_applicable"


def test_paediatric_flag_is_excluded_even_without_specialty_code() -> None:
    """If retrieval provides the reference-layer flag, coordinator honors it
    directly instead of relying only on the specialty code literal."""
    paediatric = _referral(
        "P-PAED-FLAG",
        specialty_hipe="9999",
        is_paediatric=True,
        urgency_score=1.0,
    )

    result = rank_cohort([paediatric], capacity_direction="pressure")

    assert result.rankings == []
    assert result.excluded[0]["pathway_number"] == "P-PAED-FLAG"
    assert result.excluded[0]["exclusion_reason"] == "paediatric_news2_not_applicable"


def test_uncategorised_and_excluded_tails_still_separated_after_full_sort() -> None:
    """The full sort key must not accidentally merge the two tail groups
    (ADR-006): both have `severity_rank=None`, so `sort_key` must still
    keep them ordered after every categorised band and separated from
    each other, not interleaved by their own crt_breached/priority/date.
    """
    result = rank_cohort(
        [
            _referral("P-URGENT", cpc=1),
            _referral("P-NULL-CPC", cpc=None, crt_breached=True, urgency_score=1.0),
            _referral("P-EXCLUDED", cpc=4, crt_breached=True, urgency_score=1.0),
        ],
        capacity_direction="pressure",
    )

    order = [r["pathway_number"] for r in result.rankings]
    assert order == ["P-URGENT", "P-NULL-CPC", "P-EXCLUDED"]
