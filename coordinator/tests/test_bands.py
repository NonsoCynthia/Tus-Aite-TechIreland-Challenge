"""Tier 1 tests for CPC band resolution and tail assignment.

Covers plan.md Phase 2, tasks 2.1-2.5 (spec.md FR3/FR4, ADR-003, ADR-006).
Per `conductor/workflow.md` strict TDD: these tests are written and must
FAIL before `coordinator.app.bands` is implemented (task 2.6).

Referral dicts here mirror the shape `retrieval.app.db.get_cohort` returns
(see its docstring/query): `pathway_number`, `cpc` (the NTPF
`triage_category` code, as a string, or `None`), `crt_breached`,
`triage_status`, `adjusted_wait_days`, `referral_date`, etc. Only the fields
each test needs are populated; the rest are irrelevant to band resolution.
"""

from datetime import date
from typing import Any

from coordinator.app.bands import SEVERITY_RANK, order_by_band


def _referral(pathway_number: str, **overrides: Any) -> dict[str, Any]:
    """Builds a minimal cohort-shaped referral dict for a test case.

    Args:
        pathway_number: The referral's pathway_number.
        **overrides: Fields to set on top of the defaults.

    Returns:
        A dict with the fields `order_by_band` and `SEVERITY_RANK` need,
        shaped like one row from `retrieval.app.db.get_cohort`.
    """
    referral: dict[str, Any] = {
        "hospital_hipe": "9004",
        "pathway_number": pathway_number,
        "cpc": None,
        "crt_breached": None,
        "triage_status": "triaged",
        "adjusted_wait_days": 0,
        "referral_date": date(2026, 1, 1),
    }
    referral.update(overrides)
    return referral


def test_severity_rank_matches_core_ref_codes() -> None:
    """SEVERITY_RANK matches core.ref_codes exactly (ADR-003).

    Urgent (cpc 1) -> rank 1, Semi-Urgent (cpc 3) -> rank 2,
    Routine (cpc 2) -> rank 3, Excluded (cpc 4) -> no rank at all.
    """
    assert SEVERITY_RANK["1"] == 1  # Urgent
    assert SEVERITY_RANK["3"] == 2  # Semi-Urgent
    assert SEVERITY_RANK["2"] == 3  # Routine
    assert "4" not in SEVERITY_RANK  # Excluded has no severity_rank


def test_semi_urgent_outranks_routine_ntpf_code_trap() -> None:
    """Regression test for the NTPF code trap (ADR-003).

    `core.ref_codes` gives Urgent=1, Semi-Urgent=3, Routine=2 --
    `dataset/docs/GETTING_THE_DATA.md` section 4 names sorting on the raw
    `cpc` value as the trap it is: ascending `cpc` places every Routine
    (cpc=2) referral above every Semi-Urgent one (cpc=3). Ordering on
    `severity_rank` must produce the opposite, clinically correct order.
    """
    semi_urgent = _referral("P-SEMI", cpc="3")
    routine = _referral("P-ROUTINE", cpc="2")

    raw_cpc_order = sorted(
        [semi_urgent, routine], key=lambda r: r["cpc"]
    )
    assert [r["pathway_number"] for r in raw_cpc_order] == [
        "P-ROUTINE",
        "P-SEMI",
    ], "fixture assumption broken: raw cpc order should be the wrong order"

    banded_order = order_by_band([routine, semi_urgent])
    assert [r["pathway_number"] for r in banded_order] == [
        "P-SEMI",
        "P-ROUTINE",
    ]


def test_null_and_excluded_cpc_rank_after_every_banded_referral() -> None:
    """Referrals with cpc null and cpc 4 both rank after every referral
    that has a severity_rank (spec.md FR4, ADR-006)."""
    urgent = _referral("P-URGENT", cpc="1")
    routine = _referral("P-ROUTINE", cpc="2")
    null_cpc = _referral("P-NULL", cpc=None)
    excluded = _referral("P-EXCLUDED", cpc="4")

    result = order_by_band([excluded, null_cpc, routine, urgent])
    order = [r["pathway_number"] for r in result]

    banded_positions = [order.index("P-URGENT"), order.index("P-ROUTINE")]
    tail_positions = [order.index("P-NULL"), order.index("P-EXCLUDED")]
    assert max(banded_positions) < min(tail_positions)


def test_tail_groups_stay_distinguishable_null_before_excluded() -> None:
    """The two tail groups are never merged: null-CPC referrals all rank
    above Excluded referrals, and the boundary is identifiable in the
    output (spec.md FR4, ADR-006)."""
    null_a = _referral("P-NULL-A", cpc=None)
    null_b = _referral("P-NULL-B", cpc=None)
    excluded_a = _referral("P-EXCL-A", cpc="4")
    excluded_b = _referral("P-EXCL-B", cpc="4")

    result = order_by_band([excluded_b, null_a, excluded_a, null_b])
    order = [r["pathway_number"] for r in result]

    null_positions = [order.index("P-NULL-A"), order.index("P-NULL-B")]
    excluded_positions = [
        order.index("P-EXCL-A"),
        order.index("P-EXCL-B"),
    ]
    assert max(null_positions) < min(excluded_positions)

    # The boundary is identifiable: every result carries a band label that
    # tells the two tails apart, not just their relative order.
    bands_by_pathway = {r["pathway_number"]: r["band"] for r in result}
    assert bands_by_pathway["P-NULL-A"] == bands_by_pathway["P-NULL-B"]
    assert (
        bands_by_pathway["P-EXCL-A"] == bands_by_pathway["P-EXCL-B"]
    )
    assert (
        bands_by_pathway["P-NULL-A"] != bands_by_pathway["P-EXCL-A"]
    )


def test_no_referral_is_dropped() -> None:
    """Every pathway_number in the input cohort appears exactly once in
    the output, including both tail groups (spec.md FR4, ADR-006)."""
    cohort = [
        _referral("P-1", cpc="1"),
        _referral("P-2", cpc="3"),
        _referral("P-3", cpc="2"),
        _referral("P-4", cpc=None),
        _referral("P-5", cpc="4"),
        _referral("P-6", cpc=None),
        _referral("P-7", cpc="4"),
    ]

    result = order_by_band(cohort)

    input_pathways = [r["pathway_number"] for r in cohort]
    output_pathways = [r["pathway_number"] for r in result]
    assert sorted(output_pathways) == sorted(input_pathways)
    assert len(output_pathways) == len(set(output_pathways))
