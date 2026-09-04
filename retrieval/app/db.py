"""Postgres write layer (spec.md FR2).

Each function is one transaction: `with psycopg.connect(...) as conn:` commits
on clean exit, rolls back on any exception -- so a decision's rankings,
citations and rule checks either all land or none do. Connects as
retrieval_rw (migration 009), which carries exactly agent_rw's SELECT/INSERT
grants -- see spec.md NFR3.
"""

from __future__ import annotations

from datetime import date

import psycopg

from .config import settings
from .schemas import DecisionIn, OverrideIn, ScoreIn


def check_connection() -> bool:
    """Used by /health (main.py). A short, fixed connect_timeout -- not the
    default (which can hang for a long time against a dead host) -- so a
    health check fails fast rather than stalling the caller."""
    try:
        with psycopg.connect(settings.retrieval_db_url, connect_timeout=2) as conn:
            conn.execute("SELECT 1")
        return True
    except psycopg.Error:
        return False


def _connect() -> psycopg.Connection:
    return psycopg.connect(settings.retrieval_db_url)


def insert_score(payload: ScoreIn) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO agent.agent_scores
                (run_id, agent_name, hospital_hipe, pathway_number, as_of_date, score,
                 method, agent_version)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                payload.run_id,
                payload.agent_name,
                payload.hospital_hipe,
                payload.pathway_number,
                payload.as_of_date,
                payload.score,
                payload.method,
                payload.agent_version,
            ),
        )
        for citation in payload.citations:
            conn.execute(
                """
                INSERT INTO agent.agent_citations
                    (run_id, agent_name, hospital_hipe, pathway_number, evidence_type, evidence_key)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    payload.run_id,
                    payload.agent_name,
                    payload.hospital_hipe,
                    payload.pathway_number,
                    citation.evidence_type,
                    citation.evidence_key,
                ),
            )


def insert_decision(payload: DecisionIn) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO agent.decisions
                (decision_id, run_id, hospital_hipe, as_of_date, cohort_size, coordinator_version)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                payload.decision_id,
                payload.run_id,
                payload.hospital_hipe,
                payload.as_of_date,
                len(payload.rankings),
                payload.coordinator_version,
            ),
        )
        for ranking in payload.rankings:
            conn.execute(
                """
                INSERT INTO agent.decision_rankings
                    (decision_id, hospital_hipe, pathway_number, position, triage_category,
                     urgency_score, capacity_score, rationale_summary)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    payload.decision_id,
                    ranking.hospital_hipe,
                    ranking.pathway_number,
                    ranking.position,
                    ranking.triage_category,
                    ranking.urgency_score,
                    ranking.capacity_score,
                    ranking.rationale_summary,
                ),
            )
            for citation in ranking.citations:
                conn.execute(
                    """
                    INSERT INTO agent.decision_citations
                        (decision_id, hospital_hipe, pathway_number, evidence_type,
                         evidence_key, role)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        payload.decision_id,
                        ranking.hospital_hipe,
                        ranking.pathway_number,
                        citation.evidence_type,
                        citation.evidence_key,
                        citation.role,
                    ),
                )
            for rule_check in ranking.rule_checks:
                conn.execute(
                    """
                    INSERT INTO agent.rule_checks
                        (decision_id, rule_id, hospital_hipe, pathway_number, passed, detail)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        payload.decision_id,
                        rule_check.rule_id,
                        ranking.hospital_hipe,
                        ranking.pathway_number,
                        rule_check.passed,
                        rule_check.detail,
                    ),
                )


def get_decision_as_of_date(decision_id: str) -> date:
    """Overrides don't carry as_of_date themselves; the Override IRI template
    (namespaces.md) needs it, so it's looked up from the parent decision."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT as_of_date FROM agent.decisions WHERE decision_id = %s", (decision_id,)
        ).fetchone()
    if row is None:
        raise ValueError(f"no agent.decisions row for decision_id={decision_id!r}")
    return row[0]


def insert_override(payload: OverrideIn) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO agent.overrides
                (override_id, decision_id, hospital_hipe, pathway_number, clinician_id,
                 from_position, to_position, reason, rule_warning_accepted)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                payload.override_id,
                payload.decision_id,
                payload.hospital_hipe,
                payload.pathway_number,
                payload.clinician_id,
                payload.from_position,
                payload.to_position,
                payload.reason,
                payload.rule_warning_accepted,
            ),
        )
