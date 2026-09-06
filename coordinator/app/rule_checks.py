"""CPC/CRT/ordering rule checks (spec.md FR10).

`RULE-CRT-URGENT`, `RULE-CRT-SEMI` and `RULE-TRIAGE-TURNAROUND` are
per-referral facts (a date comparison against a documented threshold).
`RULE-ORDER` and `RULE-TIEBREAK` are properties of the whole ordered list,
evaluated after the full ordering exists -- by construction of
`coordinator.app.ranking.sort_key` they cannot fail on real output, but the
checks are kept anyway (spec.md FR10) so a future change to the sort key
would be caught.

Citation construction and `RuleCheckIn` assembly for `POST /decisions` are
Phase 5; this module returns plain dicts shaped like `RuleCheckIn`
(`rule_id`, `passed`, `detail`).
"""

from typing import Any

# Thresholds are core.ref_rules' own seed values -- not invented here.
# Source: dataset/docs/BUILD_MANUAL.md section 7.3 (ref_rules.csv):
#   RULE-CRT-URGENT,...,28
#   RULE-CRT-SEMI,...,91
#   RULE-TRIAGE-TURNAROUND,...,21
RULE_CRT_URGENT_DAYS = 28
RULE_CRT_SEMI_DAYS = 91
RULE_TRIAGE_TURNAROUND_DAYS = 21

_URGENT_CPC = 1
_SEMI_URGENT_CPC = 3


def evaluate_referral_rules(referral: dict[str, Any]) -> list[dict[str, Any]]:
    """Evaluates the per-referral CRT/turnaround rules for one referral.

    Args:
        referral: A cohort-shaped referral dict carrying `cpc`,
            `adjusted_wait_days`, `triage_status` and
            `days_awaiting_triage`.

    Returns:
        A list of `RuleCheckIn`-shaped dicts (`rule_id`, `passed`,
        `detail`) -- `RULE-CRT-URGENT` for urgent (cpc=1) referrals,
        `RULE-CRT-SEMI` for semi-urgent (cpc=3), `RULE-TRIAGE-TURNAROUND`
        for `awaiting_triage` referrals with a recorded
        `days_awaiting_triage`. Routine (cpc=2) and Excluded (cpc=4)
        referrals get no CRT rule -- `core.ref_rules` has no
        `threshold_days` for either.
    """
    checks: list[dict[str, Any]] = []

    cpc = referral.get("cpc")
    wait: int = referral["adjusted_wait_days"]
    if cpc == _URGENT_CPC:
        breached = wait > RULE_CRT_URGENT_DAYS
        checks.append(
            {
                "rule_id": "RULE-CRT-URGENT",
                "passed": not breached,
                "detail": f"urgent, day {wait} of {RULE_CRT_URGENT_DAYS}"
                + (f", over by {wait - RULE_CRT_URGENT_DAYS}" if breached else ""),
            }
        )
    elif cpc == _SEMI_URGENT_CPC:
        breached = wait > RULE_CRT_SEMI_DAYS
        checks.append(
            {
                "rule_id": "RULE-CRT-SEMI",
                "passed": not breached,
                "detail": f"semi-urgent, day {wait} of {RULE_CRT_SEMI_DAYS}"
                + (f", over by {wait - RULE_CRT_SEMI_DAYS}" if breached else ""),
            }
        )

    days_awaiting_triage: int | None = referral.get("days_awaiting_triage")
    if referral.get("triage_status") == "awaiting_triage" and days_awaiting_triage is not None:
        breached = days_awaiting_triage > RULE_TRIAGE_TURNAROUND_DAYS
        checks.append(
            {
                "rule_id": "RULE-TRIAGE-TURNAROUND",
                "passed": not breached,
                "detail": f"awaiting triage, day {days_awaiting_triage} of "
                f"{RULE_TRIAGE_TURNAROUND_DAYS}"
                + (
                    f", over by {days_awaiting_triage - RULE_TRIAGE_TURNAROUND_DAYS}"
                    if breached
                    else ""
                ),
            }
        )

    return checks


def check_order(ranked_referrals: list[dict[str, Any]]) -> bool:
    """`RULE-ORDER`: no referral ranked above one of higher clinical priority.

    Evaluated over the whole ordered list, not per referral -- true iff
    `severity_rank` is non-decreasing from the first ranked position to
    the last, treating the two tail groups (`severity_rank=None`,
    ADR-006) as ranking after every real severity_rank.

    Args:
        ranked_referrals: The decision's referrals, in ranked order, each
            carrying `severity_rank` (as `coordinator.app.bands` adds).

    Returns:
        `True` if clinical priority is never violated across the list.
    """
    order_values = [
        r["severity_rank"] if r.get("severity_rank") is not None else float("inf")
        for r in ranked_referrals
    ]
    return all(order_values[i] <= order_values[i + 1] for i in range(len(order_values) - 1))


def check_tiebreak(ranked_referrals: list[dict[str, Any]]) -> bool:
    """`RULE-TIEBREAK`: same category and status ordered oldest-first.

    Evaluated over the whole ordered list, not per referral -- true iff,
    within each run of referrals sharing the same `severity_rank` and
    `triage_status`, `referral_date` is non-decreasing.

    Args:
        ranked_referrals: The decision's referrals, in ranked order, each
            carrying `severity_rank`, `triage_status` and `referral_date`.

    Returns:
        `True` if no same-category, same-status referral is ranked ahead
        of an older one.
    """
    for current, following in zip(ranked_referrals, ranked_referrals[1:], strict=False):
        same_severity = current.get("severity_rank") == following.get("severity_rank")
        same_status = current.get("triage_status") == following.get("triage_status")
        if same_severity and same_status and current["referral_date"] > following["referral_date"]:
            return False
    return True
