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
from datetime import date

import psycopg
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from . import db, graph, iri
from .auth import require_bearer_token
from .schemas import DecisionIn, OverrideIn, ReferralIn, ScoreIn

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


def _projection_failed_response(detail: str, **extra: str) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_207_MULTI_STATUS,
        content={
            "status": "postgres_committed_graph_projection_failed",
            "detail": detail,
            **extra,
        },
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

    try:
        as_of_date = db.get_decision_as_of_date(payload.decision_id)
    except (psycopg.Error, ValueError) as exc:
        # decision_id is FK-enforced against agent.decisions (migration 006), so
        # insert_override succeeding already guarantees the row exists -- a
        # failure here is a fresh connection/transient error, not a missing
        # decision. The override row already committed, so this is the same
        # partial-failure shape as a graph-push failure, not a fresh 400/500.
        logger.exception(
            "could not resolve decision as_of_date after Postgres commit: override %s",
            payload.override_id,
        )
        return _projection_failed_response(str(exc))
    triples = graph.override_triples(payload, as_of_date)
    try:
        await graph.push_triples(triples, iri.overrides_graph())
    except Exception as exc:
        logger.exception(
            "graph projection failed after Postgres commit: override %s", payload.override_id
        )
        return _projection_failed_response(str(exc))
    return {"status": "ok"}


@router.post(
    "/referrals",
    response_model=None,
    summary="Intake a new referral (clinician/hospital UI input)",
    description=(
        "A new referral arriving at a hospital -- spec.md FR11, user request (\"input new "
        "patients\"). Called by the clinician/hospital UI (once built) when staff enter a new "
        "patient's referral directly, NOT by an agent -- this is how a referral enters the system "
        "in the first place, upstream of everything the urgency/capacity/coordinator agents do. "
        "Writes `core.patients`/`core.persons` (only if `new_patient` is given), `core.referrals`, "
        "and today's initial `core.referral_daily` row (`triage_status='awaiting_triage'`), then "
        "projects `eat:Referral` (+ `eat:Patient`/`eat:Person` if new, + an initial "
        "`eat:ReferralState`) into the graph's `inputs` named graph -- the same one the batch "
        "pipeline uses, so this referral reads back identically to a batch-loaded one everywhere "
        "else in this API. `pathway_number` is generated server-side (never supplied by the "
        "caller) and returned in the response so the caller can address this referral afterwards."
        "\n\nThis endpoint does NOT recompute any score or re-run the coordinator's ranking -- "
        "that is the urgency/capacity/coordinator agents' job (a separate track), not a judgement "
        "this data-access service makes for itself. Once this referral is stored, it shows up in "
        "`GET /hospitals/.../cohort/...` like any other, which is how an agent or orchestrator "
        "watching that endpoint would notice it and trigger whatever re-scoring it wants to do."
        + _RESPONSE_CONTRACT
    ),
)
async def create_referral(payload: ReferralIn) -> JSONResponse | dict[str, str]:
    today = date.today()
    try:
        pathway_number = db.insert_referral(payload, today)
    except db.UnknownPatientError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except psycopg.Error as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    triples = graph.referral_triples(payload, pathway_number, today)
    try:
        await graph.push_triples(triples, iri.inputs_graph())
    except Exception as exc:
        logger.exception(
            "graph projection failed after Postgres commit: referral %s/%s",
            payload.hospital_hipe,
            pathway_number,
        )
        return _projection_failed_response(str(exc), pathway_number=pathway_number)
    return {"status": "ok", "pathway_number": pathway_number}
