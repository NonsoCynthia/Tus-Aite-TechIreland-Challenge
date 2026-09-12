"""Typed rationale-layer data structures."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class EvidenceItem:
    """One graph evidence node cited by a ranked placement."""

    role: str
    iri: str
    type: str | None
    properties: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_json(cls, value: dict[str, Any]) -> EvidenceItem:
        properties = value.get("properties") or {}
        return cls(
            role=str(value["role"]),
            iri=str(value["iri"]),
            type=str(value["type"]) if value.get("type") is not None else None,
            properties={str(k): str(v) for k, v in properties.items()},
        )


@dataclass(frozen=True)
class EvidencePack:
    """All graph-backed evidence needed to explain one ranked placement."""

    decision: str
    placement: str
    position: int | None
    referral: str | None
    pathway_number: str
    evidence: tuple[EvidenceItem, ...]

    @classmethod
    def from_decision_placement(cls, decision: str, placement: dict[str, Any]) -> EvidencePack:
        evidence = tuple(EvidenceItem.from_json(item) for item in placement.get("evidence", []))
        return cls(
            decision=decision,
            placement=str(placement["placement"]),
            position=int(placement["position"]),
            referral=str(placement.get("referral") or ""),
            pathway_number=str(placement["pathway_number"]),
            evidence=evidence,
        )

    @classmethod
    def from_evidence_response(
        cls,
        *,
        decision: str,
        pathway_number: str,
        response: dict[str, Any],
    ) -> EvidencePack:
        evidence = tuple(EvidenceItem.from_json(item) for item in response.get("evidence", []))
        return cls(
            decision=decision,
            placement=str(response["placement"]),
            position=None,
            referral=None,
            pathway_number=pathway_number,
            evidence=evidence,
        )


@dataclass(frozen=True)
class Rationale:
    """Rendered rationale text and the graph nodes it cites."""

    pathway_number: str
    text: str
    citation_iris: tuple[str, ...]
