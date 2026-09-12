"""Deterministic rationale rendering from graph evidence.

The renderer only verbalises fields already present in the resolved evidence
pack. Every evidence sentence ends with the evidence node's IRI, so the prose
can always be walked back to the graph node that supports it.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Literal

from .models import EvidenceItem, EvidencePack, Rationale

RenderStyle = Literal["technical", "clinician"]

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


def _first(items: list[EvidenceItem], entity_type: str) -> EvidenceItem | None:
    for item in items:
        if item.type == entity_type:
            return item
    return None


def _format_score(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        return f"{float(value):.3f}"
    except ValueError:
        return value


def _score_phrase(value: str | None) -> str | None:
    score = _format_score(value)
    if score is None:
        return None
    try:
        numeric = float(score)
    except ValueError:
        return f"The recorded urgency score is {score}"

    if numeric < 0.33:
        band = "lower"
    elif numeric < 0.67:
        band = "moderate"
    else:
        band = "higher"
    return f"The recorded urgency score is {score} on a 0 to 1 scale, which is in the {band} range"


def _observation_label(value: str | None) -> str:
    if not value:
        return "the cited observation"
    observed = value.rstrip("/").rsplit("/", 1)[-1]
    labels = {
        "spo2": "the cited oxygen saturation observation",
        "hr": "the cited heart-rate observation",
        "sbp": "the cited systolic blood-pressure observation",
        "dbp": "the cited diastolic blood-pressure observation",
        "rr": "the cited respiratory-rate observation",
        "temp": "the cited temperature observation",
        "pain": "the cited pain-score observation",
        "news2": "the cited NEWS2 observation",
    }
    return labels.get(observed, "the cited observation")


def _render_technical(pack: EvidencePack) -> str:
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
    return "\n".join(lines)


def _render_clinician(pack: EvidencePack) -> str:
    by_role: dict[str, list[EvidenceItem]] = defaultdict(list)
    for item in pack.evidence:
        by_role[item.role].append(item)

    heading = (
        f"Referral {pack.pathway_number} is ranked #{pack.position} for clinician review."
        if pack.position is not None
        else f"Referral {pack.pathway_number} is shown for clinician review."
    )
    lines = [f"{heading} This is decision support; clinician sign-off is required."]

    urgency_score = _first(by_role.get("urgency", []), "Score")
    if urgency_score:
        score = _score_phrase(urgency_score.properties.get("scoreValue"))
        cited_observation = _observation_label(urgency_score.properties.get("cites"))
        if score:
            lines.append(f"{score}. It is supported by {cited_observation}.")

    capacity_items = by_role.get("capacity", [])
    bed_status = _first(capacity_items, "BedStatus")
    clinic_session = _first(capacity_items, "ClinicSession")
    capacity_parts = []
    if bed_status:
        occupancy = bed_status.properties.get("occupancyPct")
        free_beds = bed_status.properties.get("freeBeds")
        if occupancy and free_beds:
            capacity_parts.append(
                f"the relevant ward was {occupancy} percent occupied, with {free_beds} beds free"
            )
        elif occupancy:
            capacity_parts.append(f"the relevant ward was {occupancy} percent occupied")
        elif free_beds:
            capacity_parts.append(f"the relevant ward had {free_beds} beds free")
    if clinic_session:
        clinic = clinic_session.properties.get("clinicName", "the cited clinic session")
        slots = clinic_session.properties.get("slotsAvailable")
        total = clinic_session.properties.get("slotsTotal")
        session_date = clinic_session.properties.get("sessionDate")
        if slots and total and session_date:
            capacity_parts.append(
                f"{clinic} on {session_date} had {slots} of {total} slots available"
            )
        elif slots:
            capacity_parts.append(f"{clinic} had {slots} slots available")
    if capacity_parts:
        lines.append(f"Capacity evidence reports {'; and '.join(capacity_parts)}.")

    timeframe_items = by_role.get("timeframe", [])
    referral_state = _first(timeframe_items, "ReferralState")
    rule = _first(timeframe_items, "Rule")
    timeframe_parts = []
    if referral_state:
        triage_status = referral_state.properties.get("triageStatus")
        valid_from = referral_state.properties.get("validFrom")
        needs = referral_state.properties.get("hasHighClinicalOrSocialNeeds")
        state_text = "the cited referral state"
        if triage_status and valid_from:
            state_text = f"the referral state was {triage_status} from {valid_from}"
        elif triage_status:
            state_text = f"the referral state was {triage_status}"
        if needs == "true":
            state_text += " and recorded high clinical or social needs"
        elif needs == "false":
            state_text += " and did not record high clinical or social needs"
        timeframe_parts.append(state_text)
    if rule:
        statement = rule.properties.get("statement")
        threshold = rule.properties.get("thresholdDays")
        if statement:
            timeframe_parts.append(f"the applicable timeframe rule states: {statement}")
        elif threshold:
            timeframe_parts.append(f"the applicable timeframe threshold is {threshold} days")
    if timeframe_parts:
        lines.append(f"CPC/CRT evidence records {'; and '.join(timeframe_parts)}.")

    if any(item.type is None or not item.properties for item in pack.evidence):
        lines.append("Some cited evidence could not be resolved in the current graph.")

    return "\n".join(lines)


def render_rationale(pack: EvidencePack, *, style: RenderStyle = "technical") -> Rationale:
    """Render one rationale from a graph evidence pack.

    Args:
        pack: A placement's already-resolved graph evidence.
        style: `technical` for audit detail, or `clinician` for prose.

    Returns:
        Rationale text plus the cited IRI list.

    Raises:
        ValueError: If the placement has no evidence.
    """
    if not pack.evidence:
        raise ValueError(f"{pack.pathway_number} has no cited evidence")

    text = _render_clinician(pack) if style == "clinician" else _render_technical(pack)
    citation_iris = tuple(item.iri for item in pack.evidence)
    return Rationale(
        pathway_number=pack.pathway_number,
        text=text,
        citation_iris=citation_iris,
    )


def render_many(packs: list[EvidencePack], *, style: RenderStyle = "technical") -> list[Rationale]:
    """Render rationale text for every pack."""
    return [render_rationale(pack, style=style) for pack in packs]
