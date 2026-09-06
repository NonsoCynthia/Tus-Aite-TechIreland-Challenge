"""Contract test for the coordinator's citation evidence types.

Tier 1 test, written before implementation, per
`conductor/tracks/coordinating-agent_20260906/plan.md` task 1.2.
"""

from typing import get_args

from coordinator.app.citations import ROLE_EVIDENCE_TYPES
from retrieval.app.schemas import DecisionEvidenceType


def test_role_evidence_types_are_valid_evidence_types() -> None:
    """Every emitted evidence_type must be a member of DecisionEvidenceType.

    Per ADR-009 (`conductor/tracks/coordinating-agent_20260906/
    decisions.md`), this test used to fail on purpose: `EvidenceType` did
    not include `"score"` or `"referral_state"` -- the coordinator's real
    evidence for the `urgency` and `timeframe` citation roles. That change
    request has since landed (PR #7), but not by widening `EvidenceType`
    itself: `ScoreCitationIn` still uses the original five-value
    `EvidenceType` (Postgres' `ac_evidence_type_valid` CHECK on
    `agent.agent_citations` enforces exactly those five, so widening the
    shared `Literal` would let a score citation pass Pydantic only to be
    rejected by Postgres). Placement citations
    (`DecisionCitationIn.evidence_type`) instead got their own, wider
    `DecisionEvidenceType` -- the five original values plus `"score"`,
    `"referral_state"`, and `"rule"` (the last is one more than this
    coordinator emits; `citesTimeframeEvidence`'s ontology range already
    permits a `Rule`, so retrieval left room for it). Per ADR-012, the
    coordinator now uses that room: `timeframe` cites both `referral_state`
    and `rule`, so `ROLE_EVIDENCE_TYPES` maps each role to a *tuple* of
    evidence types rather than one.

    This test therefore now validates every evidence type in every role's
    tuple against `DecisionEvidenceType`, the enum a `RankedPlacement`
    citation is actually checked against, not `EvidenceType`, which only
    governs `ScoreCitationIn` and was never the right enum for this test
    to import.

    This test and `test_decision.py`'s
    `test_assembled_payload_validates_against_the_real_decision_in` are
    the same signal seen from opposite sides, historically: this one used
    to fail and went green when ADR-009 landed; that one used to pass
    (because validation failed) and went red on the same event -- both
    flips were expected and are recorded, not live warnings anymore.
    """
    valid_evidence_types = get_args(DecisionEvidenceType)

    for role, evidence_types in ROLE_EVIDENCE_TYPES.items():
        for evidence_type in evidence_types:
            assert evidence_type in valid_evidence_types, (
                f"evidence_type {evidence_type!r} for role {role!r} is not "
                f"in DecisionEvidenceType {valid_evidence_types!r}"
            )
