"""Citation contract for ranked placements.

Per ADR-009 (`conductor/tracks/coordinating-agent_20260906/decisions.md`),
`retrieval.app.schemas.DecisionEvidenceType` -- not the narrower
`EvidenceType`, which only backs `ScoreCitationIn` -- is what a
`RankedPlacement` citation is checked against. It carries the five
clinical/capacity values plus `score`, `referral_state` and `rule`.

Per ADR-012, the `timeframe` role cites **two** evidence types: the
`ReferralState` carrying the wait itself, and the `Rule` (`core.ref_rules`)
the referral is measured against -- so `ROLE_EVIDENCE_TYPES` maps each role
to a tuple of the evidence types it may use, not a single one.
"""

from typing import Any

from retrieval.app.schemas import CitationRole

ROLE_EVIDENCE_TYPES: dict[CitationRole, tuple[str, ...]] = {
    "urgency": ("score",),
    "timeframe": ("referral_state", "rule"),
    "capacity": ("bed_status",),
}
"""Maps each cited `CitationRole` to the `evidence_type`(s) it is built
with. `multi_list` is not mapped: the coordinator does not currently cite
it.

`capacity` maps to `bed_status`, an existing `DecisionEvidenceType` member.
`urgency` maps to `score`, and `timeframe` to `referral_state` **and**
`rule` -- both not members of the original `EvidenceType` (ADR-009), added
to `DecisionEvidenceType` instead (ADR-009's resolution) and used together
(ADR-012). A `referral_state` citation is emitted for every referral;
`rule` is emitted only when a CRT/turnaround rule actually applies (see
`applicable_rule_id`) -- a referral with no applicable rule (Routine,
Excluded, null CPC) cites only the `ReferralState`, never an invented rule.
"""

# Evidence-key templates for the two new evidence types, taken from
# `conductor/kg/namespaces.md`. `iri.evidence_iri` prepends the evidence
# type segment (e.g. `score/...`), so `evidence_key` below is the suffix
# only, not the full IRI path.
SCORE_EVIDENCE_KEY_TEMPLATE = "{run_id}/{hospital_hipe}/{pathway_number}/{agent}"
REFERRAL_STATE_EVIDENCE_KEY_TEMPLATE = "{hospital_hipe}/{pathway_number}/{valid_from}"
# Rule's own template (namespaces.md #4) is `rule/{rule_id}` -- a single
# segment, so the evidence_key for a `rule` citation is just the rule_id
# itself; no template constant is needed beyond that.

_URGENT_CPC = 1
_SEMI_URGENT_CPC = 3


def applicable_rule_id(referral: dict[str, Any]) -> str | None:
    """Which `core.ref_rules` rule a referral's timeframe is measured against.

    Mirrors `coordinator.app.rule_checks`' applicability (which rule
    applies), not its pass/fail evaluation (which additionally needs the
    wait itself) -- this only decides whether a `rule` citation belongs on
    the `timeframe` role at all.

    Args:
        referral: A cohort-shaped referral dict carrying `cpc` and
            `triage_status`.

    Returns:
        `"RULE-CRT-URGENT"` for urgent (cpc=1), `"RULE-CRT-SEMI"` for
        semi-urgent (cpc=3), `"RULE-TRIAGE-TURNAROUND"` for
        `awaiting_triage` referrals, or `None` if no CRT/turnaround rule
        applies (Routine, Excluded, or null-CPC referrals not awaiting
        triage) -- callers must not invent a rule in that case.
    """
    cpc = referral.get("cpc")
    if cpc == _URGENT_CPC:
        return "RULE-CRT-URGENT"
    if cpc == _SEMI_URGENT_CPC:
        return "RULE-CRT-SEMI"
    if referral.get("triage_status") == "awaiting_triage":
        return "RULE-TRIAGE-TURNAROUND"
    return None
