"""Seeded, reproducible fixture payloads for agent.* outputs (spec.md FR4).

Stands in for real urgency/capacity/coordinator agent output until
explainable-agent-based-triage_20260828 is unblocked, so the write-projector
(Phase 3) has something valid to exercise now. Every payload satisfies the
SQL CHECK/FK constraints in dataset/db/migrations/006_outputs.sql -- verified
against those exact constraints in test_fixtures.py, not just asserted here.

Lives under tests/, not app/: this is a test helper, not something the
running service imports (see plan.md Phase 2).
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, timedelta

VALID_AGENT_NAMES = ("urgency", "capacity")
VALID_EVIDENCE_TYPES = ("observation", "condition", "triage_event", "bed_status", "clinic_session")
VALID_CITATION_ROLES = ("urgency", "capacity", "timeframe", "multi_list")

# Must exist in core.ref_rules -- agent.rule_checks.rule_id is a hard FK to it
# (dataset/db/migrations/006_outputs.sql). Read from the live table, not
# invented: `SELECT rule_id FROM core.ref_rules`.
VALID_RULE_IDS = (
    "RULE-CRT-URGENT",
    "RULE-CRT-SEMI",
    "RULE-TRIAGE-TURNAROUND",
    "RULE-ORDER",
    "RULE-TIEBREAK",
)

_BASE_DATE = date(2026, 9, 4)


def _hospital_hipe(rng: random.Random) -> str:
    # Real values in core.referral_daily are 9001-9004 -- the reserved,
    # non-real HIPE range this project's synthetic data uses throughout.
    return f"900{rng.randint(1, 4)}"


def _pathway_number(rng: random.Random, hospital_hipe: str) -> str:
    return f"PW-{hospital_hipe}-{rng.randint(1, 999999):06d}"


@dataclass(frozen=True)
class ScorePayload:
    run_id: str
    agent_name: str
    hospital_hipe: str
    pathway_number: str
    as_of_date: date
    score: float
    method: str
    agent_version: str
    citations: tuple[tuple[str, str], ...]  # (evidence_type, evidence_key)


@dataclass(frozen=True)
class RankingPayload:
    hospital_hipe: str
    pathway_number: str
    position: int
    triage_category: int | None
    urgency_score: float
    capacity_score: float
    rationale_summary: str
    citations: tuple[tuple[str, str, str], ...]  # (evidence_type, evidence_key, role)
    rule_checks: tuple[tuple[str, bool, str | None], ...]  # (rule_id, passed, detail)


@dataclass(frozen=True)
class DecisionPayload:
    decision_id: str
    run_id: str
    hospital_hipe: str
    as_of_date: date
    coordinator_version: str
    rankings: tuple[RankingPayload, ...]


@dataclass(frozen=True)
class OverridePayload:
    override_id: str
    decision_id: str
    hospital_hipe: str
    pathway_number: str
    clinician_id: str
    from_position: int | None
    to_position: int | None
    reason: str
    rule_warning_accepted: bool


def make_score(
    seed: int, *, run_id: str = "run-0001", agent_name: str | None = None
) -> ScorePayload:
    rng = random.Random(seed)
    hospital_hipe = _hospital_hipe(rng)
    pathway_number = _pathway_number(rng, hospital_hipe)
    chosen_agent = agent_name or rng.choice(VALID_AGENT_NAMES)
    evidence_types = rng.sample(VALID_EVIDENCE_TYPES, rng.randint(1, 3))
    return ScorePayload(
        run_id=run_id,
        agent_name=chosen_agent,
        hospital_hipe=hospital_hipe,
        pathway_number=pathway_number,
        as_of_date=_BASE_DATE - timedelta(days=rng.randint(0, 30)),
        score=round(rng.uniform(0, 1), 3),
        method=f"{chosen_agent}-fixture-v1",
        agent_version="fixture-0.1.0",
        citations=tuple((et, f"{et}-{seed}-{i}") for i, et in enumerate(evidence_types)),
    )


def make_decision(
    seed: int, *, run_id: str = "run-0001", cohort_size: int = 3
) -> DecisionPayload:
    if cohort_size < 1:
        raise ValueError("cohort_size must be positive (agent.decisions.d_cohort_positive)")

    rng = random.Random(seed)
    hospital_hipe = _hospital_hipe(rng)
    rankings = []
    for position in range(1, cohort_size + 1):
        pathway_number = _pathway_number(rng, hospital_hipe)
        n_citations = rng.randint(1, 2)
        citations = tuple(
            (
                rng.choice(VALID_EVIDENCE_TYPES),
                f"ev-{seed}-{position}-{i}",
                rng.choice(VALID_CITATION_ROLES),
            )
            for i in range(n_citations)
        )
        rule_checks = tuple(
            (rule_id, rng.random() > 0.1, None) for rule_id in rng.sample(VALID_RULE_IDS, 2)
        )
        rankings.append(
            RankingPayload(
                hospital_hipe=hospital_hipe,
                pathway_number=pathway_number,
                position=position,
                triage_category=rng.randint(1, 5),
                urgency_score=round(rng.uniform(0, 1), 3),
                capacity_score=round(rng.uniform(0, 1), 3),
                rationale_summary=f"Fixture rationale for position {position}",
                citations=citations,
                rule_checks=rule_checks,
            )
        )
    return DecisionPayload(
        decision_id=f"dec-{seed:06d}",
        run_id=run_id,
        hospital_hipe=hospital_hipe,
        as_of_date=_BASE_DATE - timedelta(days=rng.randint(0, 5)),
        coordinator_version="fixture-0.1.0",
        rankings=tuple(rankings),
    )


def make_override(seed: int, *, decision: DecisionPayload | None = None) -> OverridePayload:
    rng = random.Random(seed)
    if decision is None:
        decision = make_decision(seed)
    ranking = decision.rankings[rng.randrange(len(decision.rankings))]
    return OverridePayload(
        override_id=f"ovr-{seed:06d}",
        decision_id=decision.decision_id,
        hospital_hipe=ranking.hospital_hipe,
        pathway_number=ranking.pathway_number,
        clinician_id=f"clin-{rng.randint(1, 20):03d}",
        from_position=ranking.position,
        to_position=rng.randint(1, len(decision.rankings)),
        reason="Fixture override reason for testing.",
        rule_warning_accepted=rng.random() > 0.5,
    )
