"""Database access for the held-out system evaluator."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from typing import Any

import psycopg
from psycopg.rows import dict_row

from .metrics import GroundTruthRanking, RuleSummary


@dataclass(frozen=True)
class DecisionBundle:
    """Database rows needed to evaluate one decision."""

    decision_id: str
    run_id: str
    hospital_hipe: str
    as_of_date: str
    rankings: list[GroundTruthRanking]
    rule_summaries: list[RuleSummary]


def default_db_url() -> str:
    """Build a local admin URL that can `SET ROLE evaluator`."""
    explicit = os.getenv("EVALUATOR_DB_URL")
    if explicit:
        return explicit

    user = os.getenv("POSTGRES_USER", "triage_admin")
    password = os.getenv("POSTGRES_PASSWORD", "change_me_locally")
    database = os.getenv("POSTGRES_DB", "triage")
    port = os.getenv("POSTGRES_PORT", "5433")
    return f"postgresql://{user}:{password}@localhost:{port}/{database}"


def load_decision_bundle(decision_id: str, db_url: str | None = None) -> DecisionBundle:
    """Load one decision and its held-out answer-key join.

    The connection must be able to `SET ROLE evaluator`; normal agent and
    retrieval roles should fail here by design.
    """
    with psycopg.connect(db_url or default_db_url(), row_factory=dict_row) as conn:
        conn.execute("SET ROLE evaluator")
        decision = conn.execute(
            """
            SELECT decision_id, run_id, hospital_hipe, as_of_date
            FROM agent.decisions
            WHERE decision_id = %s
            """,
            (decision_id,),
        ).fetchone()
        if decision is None:
            raise ValueError(f"no decision found for decision_id={decision_id!r}")

        rankings = conn.execute(
            """
            SELECT
                dr.position,
                dr.hospital_hipe,
                dr.pathway_number,
                gt.latent_hazard::float8 AS latent_hazard,
                gt.deterioration_date,
                gt.deterioration_type
            FROM agent.decision_rankings dr
            LEFT JOIN eval.ground_truth gt
              ON gt.hospital_hipe = dr.hospital_hipe
             AND gt.pathway_number = dr.pathway_number
            WHERE dr.decision_id = %s
            ORDER BY dr.position
            """,
            (decision_id,),
        ).fetchall()

        rule_rows = conn.execute(
            """
            SELECT
                rule_id,
                count(*)::int AS total,
                count(*) FILTER (WHERE NOT passed)::int AS failed
            FROM agent.rule_checks
            WHERE decision_id = %s
            GROUP BY rule_id
            ORDER BY rule_id
            """,
            (decision_id,),
        ).fetchall()

    return DecisionBundle(
        decision_id=decision["decision_id"],
        run_id=decision["run_id"],
        hospital_hipe=decision["hospital_hipe"],
        as_of_date=_serialise_date(decision["as_of_date"]),
        rankings=[_ranking_from_row(row) for row in rankings],
        rule_summaries=[
            RuleSummary(rule_id=row["rule_id"], total=row["total"], failed=row["failed"])
            for row in rule_rows
        ],
    )


def _ranking_from_row(row: dict[str, Any]) -> GroundTruthRanking:
    return GroundTruthRanking(
        position=row["position"],
        hospital_hipe=row["hospital_hipe"],
        pathway_number=row["pathway_number"],
        latent_hazard=row["latent_hazard"],
        deterioration_date=row["deterioration_date"],
        deterioration_type=row["deterioration_type"],
    )


def _serialise_date(value: date | str) -> str:
    if isinstance(value, date):
        return value.isoformat()
    return str(value)
