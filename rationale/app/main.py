"""FastAPI wrapper for graph-backed rationale generation."""

from __future__ import annotations

from dataclasses import asdict
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query, status

from rationale.client import RetrievalClient, RetrievalServiceError
from rationale.config import load_settings
from rationale.models import EvidencePack
from rationale.render import RenderStyle, render_rationale

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
) -> dict[str, object]:
    """Return rationale text for one ranked placement.

    Args:
        hospital_hipe: Four-character hospital HIPE code.
        as_of_date: Decision date, YYYY-MM-DD.
        pathway_number: Referral pathway number.
        style: `clinician` for prose or `technical` for audit output.

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
    rationale = render_rationale(pack, style=style)
    return {
        "hospital_hipe": hospital_hipe,
        "as_of_date": as_of_date,
        "pathway_number": pathway_number,
        "style": style,
        **asdict(rationale),
    }
