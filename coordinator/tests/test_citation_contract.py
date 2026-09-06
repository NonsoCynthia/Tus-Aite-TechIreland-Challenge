"""Contract test for the coordinator's citation evidence types.

Tier 1 test, written before implementation, per
`conductor/tracks/coordinating-agent_20260906/plan.md` task 1.2.
"""

from typing import get_args

from coordinator.app.citations import ROLE_EVIDENCE_TYPES
from retrieval.app.schemas import EvidenceType


def test_role_evidence_types_are_valid_evidence_types() -> None:
    """Every emitted evidence_type must be a member of EvidenceType.

    This test is EXPECTED TO FAIL today, deliberately. Per ADR-009
    (`conductor/tracks/coordinating-agent_20260906/decisions.md`),
    `EvidenceType` does not yet include `"score"` or `"referral_state"` —
    the coordinator's real evidence for the `urgency` and `timeframe`
    citation roles. A change request is open against the retrieval
    service to widen that `Literal`.

    The failure is the tracking mechanism for that change request: it
    turns green only once `retrieval.app.schemas.EvidenceType` is widened
    to include `"score"` and `"referral_state"`. Do NOT make this test
    pass by weakening the assertion, removing entries from
    `ROLE_EVIDENCE_TYPES`, or asserting against anything other than the
    real `EvidenceType` Literal imported from source. If this test is
    green, either the retrieval service enum was widened (good — update
    ADR-009's status) or the test was weakened (not good — revert it).
    """
    valid_evidence_types = get_args(EvidenceType)

    for role, evidence_type in ROLE_EVIDENCE_TYPES.items():
        assert evidence_type in valid_evidence_types, (
            f"evidence_type {evidence_type!r} for role {role!r} is not "
            f"in EvidenceType {valid_evidence_types!r}"
        )
