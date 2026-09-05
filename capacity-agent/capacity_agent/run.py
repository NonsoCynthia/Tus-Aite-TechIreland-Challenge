"""Orchestrates the capacity agent (spec.md FR2 Phase 2): gather one
referral's capacity evidence via `GET /referrals/.../context`, score it
deterministically, write it via `POST /scores` -- all through
retrieval-service_20260904 (ADR-002), never SPARQL/Postgres directly.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date

from .calibration import CapacityCalibration
from .client import GraphProjectionFailedError, RetrievalClient
from .scoring import CapacityScoreResult, InsufficientCapacityEvidenceError, score_capacity

logger = logging.getLogger(__name__)


@dataclass
class CohortRunResult:
    """One capacity-agent pass over a hospital's cohort. `scored` and
    `skipped`/`graph_projection_failed` are always disjoint: a
    pathway_number appears in exactly one, so a caller checking "did this
    referral get a usable score" never has to check more than one place."""

    scored: dict[str, CapacityScoreResult] = field(default_factory=dict)
    # Postgres commit succeeded but the graph projection then failed
    # (ADR-002's 207) -- the score exists and is readable via
    # GET /runs/.../scores, but the graph audit trail is incomplete.
    graph_projection_failed: dict[str, str] = field(default_factory=dict)
    # Nothing was written at all -- e.g. no capacity evidence to cite.
    skipped: dict[str, str] = field(default_factory=dict)


def score_referral(
    client: RetrievalClient,
    calibration: CapacityCalibration,
    *,
    run_id: str,
    hospital_hipe: str,
    pathway_number: str,
    as_of_date: date,
) -> CapacityScoreResult:
    """Gathers context, scores, and writes one referral's capacity score.
    Raises `InsufficientCapacityEvidenceError` (nothing written) or
    `GraphProjectionFailedError` (Postgres row written, graph projection
    failed) straight through -- callers that need to keep processing a
    batch past either should use `run_for_cohort`, not catch these here
    themselves."""
    context = client.get_referral_context(hospital_hipe, pathway_number)
    result = score_capacity(context, calibration)
    client.post_score(
        run_id=run_id,
        agent_name="capacity",
        hospital_hipe=hospital_hipe,
        pathway_number=pathway_number,
        as_of_date=as_of_date,
        score=result.score,
        method=result.method,
        agent_version=calibration.agent_version,
        citations=result.citations,
    )
    return result


def run_for_cohort(
    client: RetrievalClient,
    calibration: CapacityCalibration,
    *,
    run_id: str,
    hospital_hipe: str,
    as_of_date: date,
) -> CohortRunResult:
    """Scores every referral in the coordinator's cohort for one
    hospital-day (`GET /hospitals/.../cohort/...`, FR10). A single
    referral's failure never aborts the batch -- a compliance reviewer
    checks `CohortRunResult.skipped`/`graph_projection_failed`, the same way
    the retrieval service itself never lets one bad row silently take down
    an otherwise-complete response."""
    cohort = client.get_cohort(hospital_hipe, as_of_date)
    result = CohortRunResult()

    for referral in cohort["referrals"]:
        pathway_number = referral["pathway_number"]
        try:
            result.scored[pathway_number] = score_referral(
                client,
                calibration,
                run_id=run_id,
                hospital_hipe=hospital_hipe,
                pathway_number=pathway_number,
                as_of_date=as_of_date,
            )
        except InsufficientCapacityEvidenceError as exc:
            logger.warning("skipping %s/%s: %s", hospital_hipe, pathway_number, exc)
            result.skipped[pathway_number] = str(exc)
        except GraphProjectionFailedError as exc:
            logger.warning(
                "graph projection failed after Postgres commit for %s/%s: %s",
                hospital_hipe,
                pathway_number,
                exc,
            )
            result.graph_projection_failed[pathway_number] = str(exc)

    return result
