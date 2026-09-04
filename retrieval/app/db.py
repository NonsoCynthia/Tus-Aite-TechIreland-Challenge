"""Postgres write layer (spec.md FR2) and the referral-context read (FR9).

Each write function is one transaction: `with psycopg.connect(...) as conn:`
commits on clean exit, rolls back on any exception -- so a decision's
rankings, citations and rule checks either all land or none do. Connects as
retrieval_rw (migration 009), which carries exactly agent_rw's SELECT/INSERT
grants -- see spec.md NFR3. The same role's SELECT on all of `core`
(migration 007) is what get_referral_context reads from directly.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import psycopg
from psycopg.rows import dict_row

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


def get_referral_context(hospital_hipe: str, pathway_number: str) -> dict[str, Any] | None:
    """Everything an urgency/capacity agent needs to judge one referral --
    spec.md FR9. Reads core.* directly (retrieval_rw has SELECT on all of
    it, migration 007) rather than via SPARQL: the input data is fully
    relational here, and going through Postgres is simpler and more
    reliable than composing the equivalent graph traversal.

    Returns None if the referral doesn't exist at all (no core.referral_daily
    row) -- the caller (reads.py) turns that into a 404, not an empty body.
    """
    with psycopg.connect(settings.retrieval_db_url, row_factory=dict_row) as conn:
        referral = conn.execute(
            """
            SELECT hospital_hipe, pathway_number, specialty_hipe, clinic_code,
                   referral_date, referral_received_date, triage_status, as_of_date
            FROM core.referral_daily
            WHERE hospital_hipe = %s AND pathway_number = %s
            ORDER BY as_of_date DESC
            LIMIT 1
            """,
            (hospital_hipe, pathway_number),
        ).fetchone()
        if referral is None:
            return None

        observations = conn.execute(
            """
            SELECT obs_datetime, hr, sbp, dbp, rr, temp, spo2, pain, avpu,
                   chiefcomplaint, news2, mts_category, icts_category
            FROM core.observations
            WHERE hospital_hipe = %s AND pathway_number = %s
            ORDER BY obs_datetime
            """,
            (hospital_hipe, pathway_number),
        ).fetchall()

        conditions = conn.execute(
            """
            SELECT icd10am_code, condition_label, is_primary, snomed_ct_id
            FROM core.conditions
            WHERE hospital_hipe = %s AND pathway_number = %s
            """,
            (hospital_hipe, pathway_number),
        ).fetchall()

        triage_events = conn.execute(
            """
            SELECT triage_event_id, sent_for_triage_date, triage_date,
                   date_returned_from_triage, triage_outcome, triage_category,
                   turnaround_days
            FROM core.triage_events
            WHERE hospital_hipe = %s AND pathway_number = %s
            """,
            (hospital_hipe, pathway_number),
        ).fetchall()

        specialty_hipe = referral["specialty_hipe"]

        wards = conn.execute(
            """
            SELECT ward_id, is_primary, nominal_beds
            FROM core.ward_specialty
            WHERE hospital_hipe = %s AND specialty_hipe = %s
            ORDER BY is_primary DESC, ward_id
            """,
            (hospital_hipe, specialty_hipe),
        ).fetchall()

        for ward in wards:
            ward["latest_bed_status"] = conn.execute(
                """
                SELECT snapshot_datetime, occupied, free, occupancy_pct, outliers,
                       surge_capacity_in_use, delayed_transfers_of_care,
                       awaiting_admission_over_9h, awaiting_admission_over_24h, gar_status
                FROM core.bed_status
                WHERE hospital_hipe = %s AND ward_id = %s
                ORDER BY snapshot_datetime DESC
                LIMIT 1
                """,
                (hospital_hipe, ward["ward_id"]),
            ).fetchone()

        clinic_sessions = conn.execute(
            """
            SELECT clinic_code, session_date, clinic_name, slots_total,
                   slots_booked, slots_available
            FROM core.clinic_sessions
            WHERE hospital_hipe = %s AND specialty_hipe = %s
            ORDER BY session_date DESC
            LIMIT 5
            """,
            (hospital_hipe, specialty_hipe),
        ).fetchall()

    return {
        "referral": referral,
        "observations": observations,
        "conditions": conditions,
        "triage_events": triage_events,
        "capacity": {
            "specialty_hipe": specialty_hipe,
            "wards": wards,
            "clinic_sessions": clinic_sessions,
        },
    }
