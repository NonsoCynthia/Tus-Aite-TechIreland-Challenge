"""Write endpoints -- the ADR-002 projector (spec.md FR2).

Every endpoint is one code path: validate (FastAPI/Pydantic) -> Postgres
commit -> graph projection, in that order. A Postgres failure means nothing
happened -- no graph write is attempted, and the client gets 400 with the
constraint that failed. A Postgres success followed by a graph failure is
reported as 207, never a silent 200 that hides a missing triple; the
Postgres row stands, since Postgres is the system of record (ADR-002).
"""

from __future__ import annotations

import logging

import psycopg
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from . import db, graph, iri
from .auth import require_bearer_token
from .schemas import DecisionIn, OverrideIn, ScoreIn

logger = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(require_bearer_token)])

_RESPONSE_CONTRACT = (
    "\n\n**Response contract**, the same on every write endpoint: `200` "
    '`{"status": "ok"}` on full success. `207` '
    '`{"status": "postgres_committed_graph_projection_failed", "detail": ...}` '
    "if the Postgres write committed but the graph projection then failed -- "
    "the Postgres row still stands, since Postgres is the system of record "
    "(ADR-002); retry the graph side out of band, don't resubmit the write. "
    "`400` if Postgres itself rejects the payload (a FK/CHECK constraint "
    "violation) -- nothing was written to either store. `422` if the request "
    "body fails validation before either store is touched."
)


def _projection_failed_response(detail: str) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_207_MULTI_STATUS,
        content={"status": "postgres_committed_graph_projection_failed", "detail": detail},
    )


@router.post(
    "/scores",
    response_model=None,
    summary="Write an agent score",
    description=(
        "Called by the urgency/capacity agents (once built) after scoring one referral. Writes "
        "`agent.agent_scores` + `agent.agent_citations`, then projects `eat:Score` + `eat:cites` "
        "triples into the graph. `citations` must be non-empty -- every score must cite at least "
        "one piece of evidence (`eat:cites` is 1..n in the ontology)." + _RESPONSE_CONTRACT
    ),
)
async def create_score(payload: ScoreIn) -> JSONResponse | dict[str, str]:
    try:
        db.insert_score(payload)
    except psycopg.Error as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    triples = graph.score_triples(payload)
    try:
        await graph.push_triples(triples, iri.run_graph(payload.run_id))
    except Exception as exc:
        logger.exception(
            "graph projection failed after Postgres commit: score %s/%s/%s",
            payload.run_id,
            payload.hospital_hipe,
            payload.pathway_number,
        )
        return _projection_failed_response(str(exc))
    return {"status": "ok"}


@router.post(
    "/decisions",
    response_model=None,
    summary="Write a coordinator decision (ranked list)",
    description=(
        "Called by the coordinating agent (once built) after ranking one hospital's referrals for "
        "one day. One call submits the whole decision atomically: `agent.decisions` + every ranked "
        "position (`agent.decision_rankings`), its citations (`agent.decision_citations`), and its "
        "rule checks (`agent.rule_checks`) in a single Postgres transaction, then projects "
        "`eat:Decision`/`eat:RankedPlacement`/`eat:RuleCheck`/`eat:cites` triples into the graph. "
        "Every ranking's `citations` must be non-empty (same 1..n rule as scores), and `position` "
        "must be unique within the decision. Note: the graph node this lands on is keyed only by "
        "`(hospital_hipe, as_of_date)` -- a second decision for the same hospital and day adds to "
        "the same node rather than replacing it." + _RESPONSE_CONTRACT
    ),
)
async def create_decision(payload: DecisionIn) -> JSONResponse | dict[str, str]:
    try:
        db.insert_decision(payload)
    except psycopg.Error as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    triples = graph.decision_triples(payload)
    try:
        await graph.push_triples(triples, iri.run_graph(payload.run_id))
    except Exception as exc:
        logger.exception(
            "graph projection failed after Postgres commit: decision %s", payload.decision_id
        )
        return _projection_failed_response(str(exc))
    return {"status": "ok"}


@router.post(
    "/overrides",
    response_model=None,
    summary="Write a clinician override",
    description=(
        "Called by the clinician UI (once built) when a clinician accepts/reorders/overrides a "
        "ranked position. `decision_id` must already exist (written by a prior `POST "
        "/decisions`) -- this endpoint looks up that decision's `as_of_date` itself to build "
        "the graph IRI, so the caller doesn't need to pass it separately. `reason` must be "
        "non-blank; overrides are treated as first-class clinician judgement, never as "
        "corrections or errors." + _RESPONSE_CONTRACT
    ),
)
async def create_override(payload: OverrideIn) -> JSONResponse | dict[str, str]:
    try:
        db.insert_override(payload)
    except psycopg.Error as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    as_of_date = db.get_decision_as_of_date(payload.decision_id)
    triples = graph.override_triples(payload, as_of_date)
    try:
        await graph.push_triples(triples, iri.overrides_graph())
    except Exception as exc:
        logger.exception(
            "graph projection failed after Postgres commit: override %s", payload.override_id
        )
        return _projection_failed_response(str(exc))
    return {"status": "ok"}
