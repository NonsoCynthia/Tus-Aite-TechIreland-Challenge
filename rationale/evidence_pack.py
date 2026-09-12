"""Build evidence packs from retrieval-service responses."""

from __future__ import annotations

from typing import Any

from .models import EvidencePack


def packs_from_decision_response(response: dict[str, Any]) -> list[EvidencePack]:
    """Build one evidence pack per ranked placement.

    Args:
        response: JSON returned by `GET /decisions/{hospital}/{date}`.

    Returns:
        Evidence packs in ranking order.

    Raises:
        ValueError: If a placement has no evidence.
    """
    decision = str(response["decision"])
    packs = [
        EvidencePack.from_decision_placement(decision, placement)
        for placement in response.get("placements", [])
    ]
    for pack in packs:
        if not pack.evidence:
            raise ValueError(f"{pack.pathway_number} has no cited evidence")
    return packs


def select_pack(packs: list[EvidencePack], pathway_number: str) -> EvidencePack:
    """Return the pack for one pathway number."""
    for pack in packs:
        if pack.pathway_number == pathway_number:
            return pack
    raise ValueError(f"no ranked placement for pathway_number={pathway_number!r}")
