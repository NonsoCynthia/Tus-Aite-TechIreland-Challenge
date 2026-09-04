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


def _projection_failed_response(detail: str) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_207_MULTI_STATUS,
        content={"status": "postgres_committed_graph_projection_failed", "detail": detail},
    )


@router.post("/scores", response_model=None)
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


@router.post("/decisions", response_model=None)
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


@router.post("/overrides", response_model=None)
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
