"""Deterministic rationale rendering from graph evidence.

The renderer only verbalises fields already present in the resolved evidence
pack. Every evidence sentence ends with the evidence node's IRI, so the prose
can always be walked back to the graph node that supports it.
"""

from __future__ import annotations

from collections import defaultdict

from .models import EvidenceItem, EvidencePack, Rationale

ROLE_LABELS = {
    "urgency": "Urgency evidence",
    "capacity": "Capacity evidence",
    "timeframe": "CPC/CRT evidence",
    "multi_list": "Multi-list evidence",
}

PROPERTY_PRIORITY = (
    "scoreValue",
    "method",
    "agentVersion",
    "triageStatus",
    "daysSinceReferral",
    "daysSinceReceived",
    "adjustedWaitDays",
    "daysAwaitingTriage",
    "hasHighClinicalOrSocialNeeds",
    "occupancyPct",
    "occupied",
    "free",
    "surgeCapacityInUse",
    "delayedTransfersOfCare",
    "awaitingAdmissionOver24h",
    "slotsTotal",
    "slotsBooked",
    "slotsAvailable",
    "passed",
)


def _format_properties(item: EvidenceItem) -> str:
    if not item.properties:
        return "properties were not resolved"

    ordered_keys = [key for key in PROPERTY_PRIORITY if key in item.properties] + sorted(
        key for key in item.properties if key not in PROPERTY_PRIORITY
    )
    pairs = [f"{key}={item.properties[key]}" for key in ordered_keys[:6]]
    return ", ".join(pairs)


def _sentence(item: EvidenceItem) -> str:
    entity_type = item.type or "unresolved evidence"
    return f"{entity_type} {item.iri}: {_format_properties(item)}."


def render_rationale(pack: EvidencePack) -> Rationale:
    """Render one clinician-facing rationale from a graph evidence pack.

    Args:
        pack: A placement's already-resolved graph evidence.

    Returns:
        Rationale text plus the cited IRI list.

    Raises:
        ValueError: If the placement has no evidence.
    """
    if not pack.evidence:
        raise ValueError(f"{pack.pathway_number} has no cited evidence")

    heading = f"Ranked #{pack.position}. " if pack.position is not None else "Ranked placement. "
    lines = [
        (
            f"{heading}Referral {pack.pathway_number}. "
            "This is decision support; clinician sign-off is required."
        )
    ]

    by_role: dict[str, list[EvidenceItem]] = defaultdict(list)
    for item in pack.evidence:
        by_role[item.role].append(item)

    for role in ("urgency", "capacity", "timeframe", "multi_list"):
        items = by_role.get(role, [])
        if not items:
            continue
        label = ROLE_LABELS.get(role, f"{role} evidence")
        rendered = " ".join(_sentence(item) for item in items)
        lines.append(f"{label}: {rendered}")

    unknown_roles = sorted(set(by_role) - set(ROLE_LABELS))
    for role in unknown_roles:
        rendered = " ".join(_sentence(item) for item in by_role[role])
        lines.append(f"{role} evidence: {rendered}")

    citation_iris = tuple(item.iri for item in pack.evidence)
    return Rationale(
        pathway_number=pack.pathway_number,
        text="\n".join(lines),
        citation_iris=citation_iris,
    )


def render_many(packs: list[EvidencePack]) -> list[Rationale]:
    """Render rationale text for every pack."""
    return [render_rationale(pack) for pack in packs]
