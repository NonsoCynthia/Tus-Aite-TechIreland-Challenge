"""Request models for the write endpoints (spec.md FR2).

Validation mirrors the SQL CHECK constraints in
dataset/db/migrations/006_outputs.sql exactly, plus a constraint the SQL
doesn't carry but the ontology does: eat:cites is "1..n" on both eat:Score
and eat:RankedPlacement (every score and every ranked placement must cite at
least one evidence node) -- enforced here since Postgres has no way to. This
is also what backs spec.md NFR2 on the read side: a read endpoint can only
ever return evidence-free placements/scores if one somehow got written
without going through this validation.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator

EvidenceType = Literal["observation", "condition", "triage_event", "bed_status", "clinic_session"]
CitationRole = Literal["urgency", "capacity", "timeframe", "multi_list"]
AgentName = Literal["urgency", "capacity"]


class ScoreCitationIn(BaseModel):
    evidence_type: EvidenceType
    evidence_key: str


class ScoreIn(BaseModel):
    run_id: str
    agent_name: AgentName
    hospital_hipe: str = Field(min_length=4, max_length=4)
    pathway_number: str
    as_of_date: date
    score: float = Field(ge=0, le=1)
    method: str
    agent_version: str
    # eat:cites is 1..n on eat:Score (kg/ontology/eat.ttl) -- not a SQL CHECK,
    # but a real graph-side cardinality constraint, enforced here instead.
    citations: list[ScoreCitationIn] = Field(min_length=1)


class DecisionCitationIn(BaseModel):
    evidence_type: EvidenceType
    evidence_key: str
    role: CitationRole


class RuleCheckIn(BaseModel):
    rule_id: str
    passed: bool
    detail: str | None = None


class RankingIn(BaseModel):
    hospital_hipe: str = Field(min_length=4, max_length=4)
    pathway_number: str
    position: int = Field(gt=0)
    triage_category: int | None = None
    urgency_score: float = Field(ge=0, le=1)
    capacity_score: float = Field(ge=0, le=1)
    rationale_summary: str
    # eat:cites is 1..n on eat:RankedPlacement too (same cardinality as
    # eat:Score) -- not a SQL CHECK, enforced here (spec.md NFR2).
    citations: list[DecisionCitationIn] = Field(min_length=1)
    rule_checks: list[RuleCheckIn] = Field(default_factory=list)


class DecisionIn(BaseModel):
    decision_id: str
    run_id: str
    hospital_hipe: str = Field(min_length=4, max_length=4)
    as_of_date: date
    coordinator_version: str
    rankings: list[RankingIn] = Field(min_length=1)

    @field_validator("rankings")
    @classmethod
    def positions_unique(cls, rankings: list[RankingIn]) -> list[RankingIn]:
        # agent.decision_rankings UNIQUE dr_unique_position
        positions = [r.position for r in rankings]
        if len(positions) != len(set(positions)):
            raise ValueError("ranking positions must be unique within a decision")
        return rankings


class OverrideIn(BaseModel):
    override_id: str
    decision_id: str
    hospital_hipe: str = Field(min_length=4, max_length=4)
    pathway_number: str
    clinician_id: str
    from_position: int | None = None
    to_position: int | None = None
    reason: str = Field(min_length=1)
    rule_warning_accepted: bool = False

    @field_validator("reason")
    @classmethod
    def reason_not_blank(cls, reason: str) -> str:
        # agent.overrides CHECK o_reason_not_blank (length(trim(reason)) > 0)
        if not reason.strip():
            raise ValueError("reason must not be blank")
        return reason
