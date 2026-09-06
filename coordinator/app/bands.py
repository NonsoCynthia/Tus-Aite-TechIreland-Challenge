"""CPC band resolution and tail assignment.

Per ADR-003 and ADR-004 (`conductor/tracks/coordinating-agent_20260906/
decisions.md`), clinical prioritisation category is a hard,
non-compensatory band boundary: no score may move a referral across a
band, and ordering is by `severity_rank`, never the raw `cpc` code value.

Per ADR-006, referrals with no `severity_rank` -- `cpc: null` and Excluded
(`cpc: "4"`) -- are ranked after every categorised referral, as two
distinguishable groups, never merged.

This module resolves bands only. Within-band ordering by priority (urgency,
wait, breach status) is Phase 3/4's job (spec.md FR5) and is not done here.
"""

from typing import Any, Final

SEVERITY_RANK: Final[dict[str, int]] = {
    "1": 1,  # Urgent
    "3": 2,  # Semi-Urgent
    "2": 3,  # Routine
    # "4" (Excluded) intentionally omitted: it has no severity_rank.
}
"""Maps the NTPF `cpc` code (`core.ref_codes`) to its clinical severity
rank, lower is more urgent. This is the only place these values live
(ADR-003); `cpc` itself is never used as a sort key.
"""

_NULL_CPC_BAND: Final[str] = "uncategorised"
_EXCLUDED_BAND: Final[str] = "excluded"
_EXCLUDED_CPC: Final[str] = "4"


def _resolve_band(cpc: str | None) -> tuple[int | None, str]:
    """Resolves one referral's severity_rank and band label.

    Args:
        cpc: The referral's NTPF `cpc` code, or `None` if uncategorised.

    Returns:
        A tuple of `(severity_rank, band)`. `severity_rank` is `None` for
        both tail groups. `band` is the `cpc` code itself for a
        categorised referral, or one of the two distinguishable tail
        labels (`"uncategorised"`, `"excluded"`) for the tails -- so the
        two tails are never merged (ADR-006).
    """
    if cpc is None:
        return None, _NULL_CPC_BAND
    if cpc == _EXCLUDED_CPC:
        return None, _EXCLUDED_BAND
    return SEVERITY_RANK[cpc], cpc


def order_by_band(referrals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Groups and orders a cohort by CPC band, tails last.

    Every categorised referral is ordered by `severity_rank` ascending
    (most urgent first). The two uncategorised groups follow, in the
    fixed order uncategorised-then-excluded (ADR-006), each internally
    stable in input order -- within-band ordering by priority is not this
    function's job (spec.md FR5, Phase 3/4).

    Args:
        referrals: Cohort-shaped referral dicts (as returned by
            `retrieval.app.db.get_cohort`), each carrying a `cpc` key.

    Returns:
        A new list of referral dicts, each with `severity_rank` and
        `band` added, ordered by band per the rules above. No referral is
        dropped or duplicated.
    """
    annotated = []
    for referral in referrals:
        severity_rank, band = _resolve_band(referral.get("cpc"))
        annotated.append(
            {**referral, "severity_rank": severity_rank, "band": band}
        )

    # Tails sort after every categorised band: categorised referrals get
    # rank 0 in this key (their real severity_rank breaks ties among
    # them), uncategorised gets 1, excluded gets 2. This key only orders
    # bands relative to each other -- it is a stable placeholder, not the
    # final within-band sort key (spec.md FR5's composite priority).
    def _band_sort_key(item: dict[str, Any]) -> tuple[int, int]:
        if item["band"] == _NULL_CPC_BAND:
            return (1, 0)
        if item["band"] == _EXCLUDED_BAND:
            return (2, 0)
        return (0, item["severity_rank"])

    return sorted(annotated, key=_band_sort_key)
