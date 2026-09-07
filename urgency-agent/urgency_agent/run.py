"""Orchestrates the urgency agent (spec.md FR1, plan.md Phase 1): gather one
referral's clinical context via `GET /referrals/.../context`, score it
deterministically, write it via `POST /scores` -- all through
retrieval-service_20260904 (ADR-002), never SPARQL/Postgres directly.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date

from .calibration import UrgencyCalibration
from .client import GraphProjectionFailedError, RetrievalClient
from .scoring import (
    InsufficientUrgencyEvidenceError,
    PaediatricReferralRefusedError,
    UrgencyScoreResult,
    score_urgency,
)

logger = logging.getLogger(__name__)


@dataclass
class CohortRunResult:
    """One urgency-agent pass over a hospital's cohort.

    The four buckets are always **disjoint**: a pathway_number appears in
    exactly one, so a caller asking "did this referral get a usable score"
    never has to check more than one place.

    `refused_paediatric` is deliberately separate from `skipped`, which is
    the one place this differs from the capacity agent's equivalent. A whole
    specialty leaving the ranked list (ADR-007) is a *coverage statement*
    about what this system does not cover; a missing observation is a *data
    quality* incident on one referral. Reported together, "we do not cover
    paediatrics" would be indistinguishable from "some rows are broken" --
    and ADR-007 requires that exclusion to stay visible rather than silent.
    """

    scored: dict[str, UrgencyScoreResult] = field(default_factory=dict)
    # ADR-007: specialty 0601. Expected and systematic, not a failure.
    refused_paediatric: dict[str, str] = field(default_factory=dict)
    # Nothing was written at all -- e.g. no observation to score or cite.
    skipped: dict[str, str] = field(default_factory=dict)
    # Postgres commit succeeded but the graph projection then failed
    # (ADR-002's 207) -- the score exists and is readable via
    # GET /runs/.../scores, but the graph audit trail is incomplete.
    graph_projection_failed: dict[str, str] = field(default_factory=dict)


def score_referral(
    client: RetrievalClient,
    calibration: UrgencyCalibration,
    *,
    run_id: str,
    hospital_hipe: str,
    pathway_number: str,
    as_of_date: date,
) -> UrgencyScoreResult:
    """Gather context, score, and write one referral's urgency score.

    Raises `PaediatricReferralRefusedError` / `InsufficientUrgencyEvidenceError`
    (nothing written) or `GraphProjectionFailedError` (Postgres row written,
    graph projection failed) straight through -- callers that need to keep
    processing a batch past any of these should use `run_for_cohort` rather
    than catching them here themselves.

    Note the ordering: scoring happens *before* the POST, so a refusal never
    reaches `POST /scores`. Writing a score and then reporting it as skipped
    would leave the coordinator reading a number this agent does not stand
    behind.
    """
    context = client.get_referral_context(hospital_hipe, pathway_number)
    result = score_urgency(context, calibration)
    client.post_score(
        run_id=run_id,
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
    calibration: UrgencyCalibration,
    *,
    run_id: str,
    hospital_hipe: str,
    as_of_date: date,
) -> CohortRunResult:
    """Score every referral in the coordinator's cohort for one hospital-day
    (`GET /hospitals/.../cohort/...`, FR10).

    A single referral's failure never aborts the batch -- a compliance
    reviewer checks the result buckets, the same way the retrieval service
    itself never lets one bad row silently take down an otherwise-complete
    response.
    """
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
        # Caught before its parent class -- PaediatricReferralRefusedError is
        # a subclass of InsufficientUrgencyEvidenceError, so the order of
        # these two blocks is what keeps the buckets meaningful.
        except PaediatricReferralRefusedError as exc:
            logger.info("refusing paediatric %s/%s: %s", hospital_hipe, pathway_number, exc)
            result.refused_paediatric[pathway_number] = str(exc)
        except InsufficientUrgencyEvidenceError as exc:
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
