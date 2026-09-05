"""Converts tests/fixtures.py dataclasses into the app.schemas Pydantic
models the write endpoints actually accept -- keeps the fixture generator
(Phase 2) independent of the request-schema shape (Phase 3), and gives every
Phase 3 test a one-line way to get a valid, real request body.
"""

from __future__ import annotations

from typing import cast

from app.schemas import (
    AgentName,
    CitationRole,
    DecisionCitationIn,
    DecisionIn,
    EvidenceType,
    OverrideIn,
    RankingIn,
    RuleCheckIn,
    ScoreCitationIn,
    ScoreIn,
)
from tests.fixtures import DecisionPayload, OverridePayload, ScorePayload

# fixtures.py deliberately doesn't import app.schemas (Phase 2 is
# schema-agnostic), so its dataclasses type these fields as plain `str`.
# fixtures.py's own VALID_* constants and test_fixtures.py's constraint tests
# already guarantee the values are one of the Literal options; these casts
# just tell mypy what test_fixtures.py already checks at runtime.


def to_score_in(payload: ScorePayload) -> ScoreIn:
    return ScoreIn(
        run_id=payload.run_id,
        agent_name=cast(AgentName, payload.agent_name),
        hospital_hipe=payload.hospital_hipe,
        pathway_number=payload.pathway_number,
        as_of_date=payload.as_of_date,
        score=payload.score,
        method=payload.method,
        agent_version=payload.agent_version,
        citations=[
            ScoreCitationIn(evidence_type=cast(EvidenceType, et), evidence_key=key)
            for et, key in payload.citations
        ],
    )


def to_decision_in(payload: DecisionPayload) -> DecisionIn:
    return DecisionIn(
        decision_id=payload.decision_id,
        run_id=payload.run_id,
        hospital_hipe=payload.hospital_hipe,
        as_of_date=payload.as_of_date,
        coordinator_version=payload.coordinator_version,
        rankings=[
            RankingIn(
                hospital_hipe=ranking.hospital_hipe,
                pathway_number=ranking.pathway_number,
                position=ranking.position,
                triage_category=ranking.triage_category,
                urgency_score=ranking.urgency_score,
                capacity_score=ranking.capacity_score,
                rationale_summary=ranking.rationale_summary,
                citations=[
                    DecisionCitationIn(
                        evidence_type=cast(EvidenceType, et),
                        evidence_key=key,
                        role=cast(CitationRole, role),
                    )
                    for et, key, role in ranking.citations
                ],
                rule_checks=[
                    RuleCheckIn(rule_id=rule_id, passed=passed, detail=detail)
                    for rule_id, passed, detail in ranking.rule_checks
                ],
            )
            for ranking in payload.rankings
        ],
    )


def to_override_in(payload: OverridePayload) -> OverrideIn:
    return OverrideIn(
        override_id=payload.override_id,
        decision_id=payload.decision_id,
        hospital_hipe=payload.hospital_hipe,
        pathway_number=payload.pathway_number,
        clinician_id=payload.clinician_id,
        from_position=payload.from_position,
        to_position=payload.to_position,
        reason=payload.reason,
        rule_warning_accepted=payload.rule_warning_accepted,
    )
