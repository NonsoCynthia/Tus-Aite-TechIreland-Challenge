# Decisions — Retrieval Service

## 1. ADR-009: `DecisionCitationIn.evidence_type` widened, `ScoreCitationIn.evidence_type` left alone

**Decided**, raised by `coordinating-agent_20260906` at their Phase 1 (before writing any code),
against this track's `EvidenceType`/`iri.evidence_iri`.

**The problem, as raised.** `EvidenceType` (`observation`/`condition`/`triage_event`/`bed_status`/
`clinic_session`) covers what a `Score` cites — raw clinical/capacity input. It doesn't cover what a
`RankedPlacement` cites: the coordinator doesn't reason over raw clinical data, so for the `urgency`/
`capacity` roles the honest evidence is the scoring agent's own `Score` node, and for `timeframe` (CRT
breach, which drives ordering after the CPC band) there's no observation-shaped fact at all — `triage_event`
is the wrong thing (records *when* triage happened, not wait-time-against-CRT). The requester's stopgap:
copy the urgency agent's own citations onto the placement, and omit `timeframe` entirely rather than cite
something inaccurate. Sound as a stopgap, but it loses a hop of provenance (the audit trail reads "because
of these vitals" instead of "because of this score, which cited these vitals") and drops timeframe
evidence from CRT-breach-driven positions entirely.

**Checked against the ontology, not just this service's own schema/DB layer** (the requester's write-up
only checked `schemas.py`/`namespaces.md`/`iri.py`) — `kg/ontology/eat.ttl`:

- `eat:citesUrgencyEvidence`/`eat:citesCapacityEvidence` carry no `rdfs:range` at all — deliberately open
  (`eat:cites`'s own comment: "range is whichever evidence node was cited"). Citing a `Score` node there
  was never disallowed, just unreachable — `EvidenceType` had no way to name one.
- `eat:citesTimeframeEvidence` has an *explicit* `rdfs:range`: `owl:unionOf (eat:ReferralState eat:Rule)`.
  The ontology already anticipated citing a `ReferralState` for timeframe — this isn't new scope, it's
  closing a gap between what the ontology permits and what this service's Literal/CHECK allowed. It also
  already sanctions `eat:Rule` — which the original ask didn't request, but which is arguably the more
  direct timeframe citation for a CRT-breach-driven position: the `RULE-CRT-URGENT`/`RULE-CRT-SEMI` node
  *is* the normative threshold being applied, where a `ReferralState` only carries the date facts.

**Also checked the SQL layer** (`dataset/db/migrations/006_outputs.sql`): `agent_citations` has
`CHECK ac_evidence_type_valid` restricting `evidence_type` to the five clinical values; `decision_citations`
carries **no such CHECK at all** (only `dc_role_valid`, on `role`). The two citation tables were never
actually constrained to the same set at the DB layer — only the shared Pydantic `Literal` made them look
that way.

**Resolution:** rather than widening the shared `EvidenceType` (which would let `ScoreCitationIn` accept
`score`/`referral_state`/`rule` at the Pydantic layer only to have Postgres reject them — a 422 becoming an
avoidable 400), added a separate `DecisionEvidenceType` Literal, used only by `DecisionCitationIn.evidence_type`:
the original five plus `score`, `referral_state`, and `rule`. `ScoreCitationIn.evidence_type` (`EvidenceType`)
is unchanged. `iri._EVIDENCE_SEGMENT` gained the three matching segments (`score`, `referral-state`, `rule`),
verified to produce the exact same IRI `score_iri`/`referral_state_iri`/`rule_iri` would (new regression test,
`test_iri.py::test_evidence_iri_decision_only_types_match_their_own_builders`). No DB migration needed —
`decision_citations.evidence_type` was never CHECK-constrained. No read-side change needed — `_resolve_iri`
in `reads.py` is generic over any IRI.

**What the coordinator should do differently from its Phase-5 workaround, given this:** cite the urgency/
capacity `Score` node directly (`evidence_type="score"`, `evidence_key="{run_id}/{hospital_hipe}/
{pathway_number}/{agent_name}"`) instead of copying the agent's own citations onto the placement — this
keeps the provenance hop the original write-up wanted to preserve. For `timeframe` on a CRT-breach-driven
position, cite the applicable `RULE-CRT-*` node (`evidence_type="rule"`, `evidence_key=rule_id`) and/or the
referral's current `ReferralState` (`evidence_type="referral_state"`,
`evidence_key="{hospital_hipe}/{pathway_number}/{valid_from}"`) instead of omitting the role.
