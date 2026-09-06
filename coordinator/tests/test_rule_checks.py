"""Tier 1 tests for CPC/CRT/ordering rule checks.

Covers plan.md Phase 4, tasks 4.7-4.9 (spec.md FR10). Per
`conductor/workflow.md` strict TDD: these tests are written and must FAIL
before `coordinator.app.rule_checks` is implemented (task 4.10).

Expected API of the not-yet-written `coordinator.app.rule_checks`:

- `RULE_CRT_URGENT_DAYS`, `RULE_CRT_SEMI_DAYS`, `RULE_TRIAGE_TURNAROUND_DAYS`:
  module constants, sourced from `core.ref_rules`'s seed data
  (`dataset/docs/BUILD_MANUAL.md` section 7.3 / `ref_rules.csv`:
  `RULE-CRT-URGENT,...,28`; `RULE-CRT-SEMI,...,91`;
  `RULE-TRIAGE-TURNAROUND,...,21`), not invented duplicates of them.
- `evaluate_referral_rules(referral)`: returns a list of `RuleCheckIn`-
  shaped dicts (`rule_id`, `passed`, `detail`) for the rules applicable to
  one referral -- `RULE-CRT-URGENT` for urgent (cpc=1) referrals,
  `RULE-CRT-SEMI` for semi-urgent (cpc=3), `RULE-TRIAGE-TURNAROUND` for
  `triage_status == "awaiting_triage"` referrals. Routine (cpc=2) and
  Excluded (cpc=4) referrals get no CRT rule -- `core.ref_rules` has no
  `threshold_days` for them either.
- `check_order(ranked_referrals)`: the whole-list `RULE-ORDER` check --
  `True` iff no referral is ranked above one of higher clinical priority
  (by `severity_rank`, ADR-003).
- `check_tiebreak(ranked_referrals)`: the whole-list `RULE-TIEBREAK`
  check -- `True` iff, within the same band and status, referrals are
  ordered oldest (`referral_date`) first.

Referral dicts mirror the shape of `retrieval.app.db.get_cohort` rows plus
`severity_rank`/`band` (as `coordinator.app.bands.order_by_band` adds).
"""

import json
from pathlib import Path
from typing import Any

from coordinator.app.citations import applicable_rule_id
from coordinator.app.rule_checks import (
    RULE_CRT_SEMI_DAYS,
    RULE_CRT_URGENT_DAYS,
    RULE_TRIAGE_TURNAROUND_DAYS,
    check_order,
    check_tiebreak,
    evaluate_referral_rules,
)

_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "cohort_9004_2026-08-30.json"


def _referral(pathway_number: str, **overrides: Any) -> dict[str, Any]:
    """Builds a minimal referral dict for one rule-check test case.

    Args:
        pathway_number: The referral's pathway_number.
        **overrides: Fields to set on top of the defaults.

    Returns:
        A dict carrying `cpc`, `severity_rank`, `band`, `triage_status`,
        `adjusted_wait_days`, `days_awaiting_triage`, `referral_date`.
    """
    referral: dict[str, Any] = {
        "pathway_number": pathway_number,
        "cpc": 1,
        "severity_rank": 1,
        "band": 1,
        "triage_status": "triaged",
        "adjusted_wait_days": 10,
        "days_awaiting_triage": None,
        "referral_date": "2026-01-01",
    }
    referral.update(overrides)
    return referral


def _rule_ids(checks: list[dict[str, Any]]) -> set[str]:
    return {c["rule_id"] for c in checks}


def _passed(checks: list[dict[str, Any]], rule_id: str) -> bool:
    return next(c["passed"] for c in checks if c["rule_id"] == rule_id)


def test_thresholds_match_core_ref_rules_seed_data() -> None:
    """Thresholds are the exact `core.ref_rules` values (28/91/21), not
    invented duplicates -- `dataset/docs/BUILD_MANUAL.md` section 7.3."""
    assert RULE_CRT_URGENT_DAYS == 28
    assert RULE_CRT_SEMI_DAYS == 91
    assert RULE_TRIAGE_TURNAROUND_DAYS == 21


def test_rule_crt_urgent_fires_at_the_28_day_threshold() -> None:
    """`RULE-CRT-URGENT` fires (fails) once an urgent referral's wait
    exceeds 28 days, and passes at or under it."""
    breached = _referral("P-BREACHED", cpc=1, severity_rank=1, adjusted_wait_days=41)
    on_time = _referral("P-ON-TIME", cpc=1, severity_rank=1, adjusted_wait_days=9)

    breached_checks = evaluate_referral_rules(breached)
    on_time_checks = evaluate_referral_rules(on_time)

    assert "RULE-CRT-URGENT" in _rule_ids(breached_checks)
    assert _passed(breached_checks, "RULE-CRT-URGENT") is False
    assert _passed(on_time_checks, "RULE-CRT-URGENT") is True


def test_rule_crt_semi_fires_at_the_91_day_threshold() -> None:
    """`RULE-CRT-SEMI` fires (fails) once a semi-urgent referral's wait
    exceeds 91 days, and passes at or under it."""
    breached = _referral("P-BREACHED", cpc=3, severity_rank=2, adjusted_wait_days=100)
    on_time = _referral("P-ON-TIME", cpc=3, severity_rank=2, adjusted_wait_days=50)

    breached_checks = evaluate_referral_rules(breached)
    on_time_checks = evaluate_referral_rules(on_time)

    assert "RULE-CRT-SEMI" in _rule_ids(breached_checks)
    assert _passed(breached_checks, "RULE-CRT-SEMI") is False
    assert _passed(on_time_checks, "RULE-CRT-SEMI") is True


def test_rule_triage_turnaround_fires_at_the_21_day_threshold() -> None:
    """`RULE-TRIAGE-TURNAROUND` fires (fails) once an `awaiting_triage`
    referral's wait exceeds 21 days, and passes at or under it."""
    breached = _referral(
        "P-BREACHED",
        cpc=None,
        severity_rank=None,
        band="uncategorised",
        triage_status="awaiting_triage",
        days_awaiting_triage=25,
    )
    on_time = _referral(
        "P-ON-TIME",
        cpc=None,
        severity_rank=None,
        band="uncategorised",
        triage_status="awaiting_triage",
        days_awaiting_triage=10,
    )

    breached_checks = evaluate_referral_rules(breached)
    on_time_checks = evaluate_referral_rules(on_time)

    assert "RULE-TRIAGE-TURNAROUND" in _rule_ids(breached_checks)
    assert _passed(breached_checks, "RULE-TRIAGE-TURNAROUND") is False
    assert _passed(on_time_checks, "RULE-TRIAGE-TURNAROUND") is True


def test_routine_and_excluded_referrals_get_no_crt_rule() -> None:
    """Routine (cpc=2) and Excluded (cpc=4) referrals get no CRT rule --
    `core.ref_rules`/`core.ref_codes` carry no `threshold_days` for
    either (dataset's own null `crt_days`)."""
    routine = _referral("P-ROUTINE", cpc=2, severity_rank=3, triage_status="triaged")
    excluded = _referral(
        "P-EXCLUDED", cpc=4, severity_rank=None, band="excluded", triage_status="triaged"
    )

    assert _rule_ids(evaluate_referral_rules(routine)) == set()
    assert _rule_ids(evaluate_referral_rules(excluded)) == set()


def test_applicable_rule_id_matches_evaluate_referral_rules_on_real_cohort() -> None:
    """THE ADR-012 DRIFT TEST.

    ADR-012 deliberately duplicates rule applicability between
    `coordinator.app.citations.applicable_rule_id` (what a `timeframe`
    citation names) and `coordinator.app.rule_checks.evaluate_referral_
    rules` (what a rule check actually evaluates) -- the trade-off is
    accepted, but nothing else catches the two drifting apart. A
    placement citing one rule while its own rule check evaluates another
    would be silently wrong: the audit trail and the compliance check
    would disagree about which threshold applies.

    Checked against every referral in the real 9004/2026-08-30 fixture,
    not hand-built cases -- the two functions must agree on which rule(s)
    apply for all 500 real referrals, not just the cases each was
    individually tested against.
    """
    with _FIXTURE_PATH.open() as f:
        cohort = json.load(f)["referrals"]

    for referral in cohort:
        evaluated_rule_ids = _rule_ids(evaluate_referral_rules(referral))
        rule_id = applicable_rule_id(referral)
        expected_rule_ids = {rule_id} if rule_id is not None else set()
        assert evaluated_rule_ids == expected_rule_ids, referral["pathway_number"]


def test_rule_order_and_tiebreak_pass_on_a_correctly_ordered_list() -> None:
    """`RULE-ORDER` and `RULE-TIEBREAK` are evaluated over the whole
    ordered list, after the full ordering exists, and pass on correctly
    ordered output (spec.md FR10)."""
    ranked = [
        _referral("P-1", cpc=1, severity_rank=1, band=1, referral_date="2026-01-01"),
        _referral("P-2", cpc=1, severity_rank=1, band=1, referral_date="2026-01-05"),
        _referral("P-3", cpc=3, severity_rank=2, band=3, referral_date="2026-01-02"),
        _referral("P-4", cpc=3, severity_rank=2, band=3, referral_date="2026-01-03"),
    ]

    assert check_order(ranked) is True
    assert check_tiebreak(ranked) is True


def test_rule_order_fails_on_a_deliberately_misordered_list() -> None:
    """THE TEETH TEST for `RULE-ORDER`.

    By construction of the sort key (spec.md FR5), `RULE-ORDER` can never
    fail on real coordinator output -- so it must be shown to fail on a
    hand-built bad list, or the check is vacuous and would pass even if
    someone broke the sort key later.
    """
    misordered = [
        # Semi-urgent (severity_rank 2) ranked above urgent
        # (severity_rank 1) -- this must never happen (ADR-004).
        _referral("P-SEMI", cpc=3, severity_rank=2, referral_date="2026-01-01"),
        _referral("P-URGENT", cpc=1, severity_rank=1, referral_date="2026-01-02"),
    ]

    assert check_order(misordered) is False


def test_rule_tiebreak_fails_on_a_deliberately_misordered_list() -> None:
    """THE TEETH TEST for `RULE-TIEBREAK`: within the same band, a newer
    referral ranked above an older one fails the check."""
    misordered = [
        _referral("P-NEWER", cpc=1, severity_rank=1, referral_date="2026-01-10"),
        _referral("P-OLDER", cpc=1, severity_rank=1, referral_date="2026-01-01"),
    ]

    assert check_tiebreak(misordered) is False
