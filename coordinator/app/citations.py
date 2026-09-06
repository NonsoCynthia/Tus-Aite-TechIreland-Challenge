"""Citation contract for ranked placements.

Per ADR-009 (`conductor/tracks/coordinating-agent_20260906/decisions.md`),
`retrieval.app.schemas.EvidenceType` is a closed `Literal` of five
primary-input types and does not yet include the two evidence types the
coordinator actually cites: the urgency `Score` node and the
`ReferralState` carrying the wait against the CRT. A change request against
the retrieval service is open to widen that `Literal`.

This module holds the single mapping from `CitationRole` to the
`evidence_type` string the coordinator emits for it, so no other module
duplicates these strings. `multi_list` is not mapped: the coordinator does
not currently cite it.
"""

from retrieval.app.schemas import CitationRole

ROLE_EVIDENCE_TYPES: dict[CitationRole, str] = {
    "urgency": "score",
    "timeframe": "referral_state",
    "capacity": "bed_status",
}
"""Maps each cited `CitationRole` to the `evidence_type` it is built with.

`capacity` maps to `bed_status`, an existing `EvidenceType` member. `urgency`
and `timeframe` map to `score` and `referral_state`, which are not yet
members of `EvidenceType` (ADR-009) and will be rejected with a `422` by
`POST /decisions` until the retrieval service is updated. That rejection is
intentional and tracked by `test_citation_contract.py`.
"""

# Evidence-key templates for the two new evidence types, taken from
# `conductor/kg/namespaces.md`. `iri.evidence_iri` prepends the evidence
# type segment (e.g. `score/...`), so `evidence_key` below is the suffix
# only, not the full IRI path.
SCORE_EVIDENCE_KEY_TEMPLATE = "{run_id}/{hospital_hipe}/{pathway_number}/{agent}"
REFERRAL_STATE_EVIDENCE_KEY_TEMPLATE = (
    "{hospital_hipe}/{pathway_number}/{valid_from}"
)
