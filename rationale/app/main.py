"""FastAPI wrapper for graph-backed rationale generation."""

from __future__ import annotations

from dataclasses import asdict
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException, Query, status

from rationale.client import RetrievalClient, RetrievalServiceError
from rationale.config import load_settings
from rationale.llm_render import (
    AgentRunError,
    RationaleGuardrailError,
    render_rationale_llm,
)
from rationale.models import EvidencePack
from rationale.render import RenderStyle, render_rationale

RenderEngine = Literal["deterministic", "llm"]

app = FastAPI(
    title="Rationale Service",
    description=(
        "HTTP API for rendering technical or clinician-facing rationale text from retrieval "
        "service evidence. It does not score, rank, or query Postgres/Oxigraph directly."
    ),
)


@app.get("/health")
def health() -> dict[str, str]:
    """Lightweight process health check."""
    return {"status": "ok"}


@app.get("/rationale/{hospital_hipe}/{as_of_date}/{pathway_number}")
def rationale_for_placement(
    hospital_hipe: str,
    as_of_date: str,
    pathway_number: str,
    style: Annotated[RenderStyle, Query()] = "clinician",
    engine: Annotated[RenderEngine, Query()] = "deterministic",
) -> dict[str, object]:
    """Return rationale text for one ranked placement.

    Args:
        hospital_hipe: Four-character hospital HIPE code.
        as_of_date: Decision date, YYYY-MM-DD.
        pathway_number: Referral pathway number.
        style: `clinician` for prose or `technical` for audit output.
        engine: `deterministic` (default, no external calls) or `llm`
            (OpenAI Agents SDK rewrites the same evidence as prose).

    Returns:
        JSON rationale response for frontend/API callers.
    """
    settings = load_settings()
    try:
        with RetrievalClient(settings.retrieval_base_url, settings.bearer_token) as client:
            evidence = client.get_placement_evidence(hospital_hipe, as_of_date, pathway_number)
    except RetrievalServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    pack = EvidencePack.from_evidence_response(
        decision=f"decision/{hospital_hipe}/{as_of_date}",
        pathway_number=pathway_number,
        response=evidence,
    )
    if engine == "llm":
        try:
            rationale = render_rationale_llm(pack, style=style, settings=settings)
        except RuntimeError as exc:
            # RuntimeError (no API key), RationaleGuardrailError and
            # AgentRunError are all this endpoint's fault to report, not the
            # caller's -- none of them mean the request itself was invalid.
            status_code = (
                status.HTTP_503_SERVICE_UNAVAILABLE
                if isinstance(exc, RationaleGuardrailError | AgentRunError)
                else status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    else:
        rationale = render_rationale(pack, style=style)
    return {
        "hospital_hipe": hospital_hipe,
        "as_of_date": as_of_date,
        "pathway_number": pathway_number,
        "style": style,
        "engine": engine,
        **asdict(rationale),
    }
