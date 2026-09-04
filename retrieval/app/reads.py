"""Read endpoints (spec.md FR3): shared, single-implementation query
helpers, following the kg/queries/wait_counters.rq pattern -- one place
computes a derived value or walks the audit trail, every caller includes it
rather than reimplementing it.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Query, status

from . import iri
from .config import settings
from .schemas import CitationRole

router = APIRouter()

# Two directories up from app/reads.py (/app/app/reads.py -> /app), where the
# Dockerfile COPYs the real file (see retrieval/Dockerfile and
# docker-compose.yml's build context) -- wrapped unmodified, per FR3, not
# reimplemented.
WAIT_COUNTERS_FRAGMENT_PATH = (
    Path(__file__).resolve().parent.parent / "kg" / "queries" / "wait_counters.rq"
)

_ROLE_SUBPROPERTY = {
    "urgency": "citesUrgencyEvidence",
    "capacity": "citesCapacityEvidence",
    "timeframe": "citesTimeframeEvidence",
    "multi_list": "citesMultiListEvidence",
}


async def _sparql_select(query: str) -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            settings.oxigraph_query_url,
            data={"query": query},
            headers={"Accept": "application/sparql-results+json"},
        )
        response.raise_for_status()
    result: list[dict[str, Any]] = response.json()["results"]["bindings"]
    return result


def _pathway_number_from_iri(value: str) -> str:
    return value.rstrip("/").rsplit("/", 1)[-1]


def _wrap_wait_counters_query(referral_iri: str, as_of_date: date) -> str:
    """Substitutes the fragment's one documented substitution point (the
    empty VALUES line) and adds the GRAPH wrapper its header says is the
    includer's job -- the fragment's own body (everything else) is untouched.
    """
    fragment = WAIT_COUNTERS_FRAGMENT_PATH.read_text(encoding="utf-8")

    values_placeholder = "VALUES (?referral ?asOfDate) { }"
    date_literal = f'"{as_of_date.isoformat()}"^^xsd:date'
    values_line = f"VALUES (?referral ?asOfDate) {{ (<{referral_iri}> {date_literal}) }}"
    if values_placeholder not in fragment:
        raise RuntimeError(
            "wait_counters.rq's substitution point has changed shape -- "
            "this wrapper needs updating to match, not silently skipped"
        )
    fragment = fragment.replace(values_placeholder, values_line, 1)

    where_open = "WHERE {"
    group_by_marker = "\nGROUP BY"
    start = fragment.index(where_open) + len(where_open)
    end = fragment.index(group_by_marker)
    body = fragment[start:end]
    inputs_graph = f"{iri.GRAPH_BASE}inputs"
    return fragment[:start] + f"\n  GRAPH <{inputs_graph}> {{{body}}}\n" + fragment[end:]


@router.get("/referrals/{hospital_hipe}/{pathway_number}/wait-counters")
async def wait_counters(
    hospital_hipe: str, pathway_number: str, as_of_date: date = Query(...)
) -> dict[str, Any]:
    referral = iri.referral_iri(hospital_hipe, pathway_number)
    query = _wrap_wait_counters_query(referral, as_of_date)
    bindings = await _sparql_select(query)
    if not bindings:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="no referral data for that date")
    row = bindings[0]
    return {
        "referral": referral,
        "as_of_date": as_of_date.isoformat(),
        "days_since_referral": int(row["daysSinceReferral"]["value"]),
        "days_since_received": int(row["daysSinceReceived"]["value"]),
        "days_awaiting_triage": (
            int(row["daysAwaitingTriage"]["value"]) if "daysAwaitingTriage" in row else None
        ),
        "adjusted_wait_days": int(row["adjustedWaitDays"]["value"]),
    }


def _evidence_query(placement_iri: str, role: CitationRole | None) -> str:
    """The one shared, role-parameterised evidence query (spec.md FR3) --
    every branch is the same shape, built from _ROLE_SUBPROPERTY, not four
    hand-written near-duplicate queries. `role=None` returns all four (the
    UI's full expander); a specific role narrows to one section.
    """
    roles = [role] if role is not None else list(_ROLE_SUBPROPERTY)
    branches = [
        f'{{ <{placement_iri}> eat:{_ROLE_SUBPROPERTY[r]} ?evidence . BIND("{r}" AS ?role) }}'
        for r in roles
    ]
    body = " UNION ".join(branches)
    return (
        f"PREFIX eat: <{iri.EAT_NS}>\n"
        f"SELECT ?role ?evidence WHERE {{\n  GRAPH ?g {{ {body} }}\n}}"
    )


async def _evidence_for_placement(
    placement_iri: str, role: CitationRole | None = None
) -> list[dict[str, str]]:
    bindings = await _sparql_select(_evidence_query(placement_iri, role))
    return [{"role": b["role"]["value"], "evidence": b["evidence"]["value"]} for b in bindings]


@router.get("/evidence/{hospital_hipe}/{as_of_date}/{pathway_number}")
async def evidence_for_placement(
    hospital_hipe: str,
    as_of_date: date,
    pathway_number: str,
    role: CitationRole | None = None,
) -> dict[str, Any]:
    placement = iri.placement_iri(hospital_hipe, as_of_date.isoformat(), pathway_number)
    return {"placement": placement, "evidence": await _evidence_for_placement(placement, role)}


@router.get("/decisions/{hospital_hipe}/{as_of_date}")
async def get_decision(hospital_hipe: str, as_of_date: date) -> dict[str, Any]:
    """Reconstructs the full decision -- every ranked position with its
    cited evidence -- purely by walking eat:hasPlacement then eat:cites (via
    its role subproperties) from the Decision node. No score or placement is
    ever returned without its evidence (spec.md NFR2): every placement here
    has at least one citation, guaranteed by RankingIn's own validation
    (schemas.py) at write time, not by filtering here.
    """
    decision = iri.decision_iri(hospital_hipe, as_of_date.isoformat())
    query = (
        f"PREFIX eat: <{iri.EAT_NS}>\n"
        "SELECT ?placement ?position ?referral WHERE {\n"
        f"  GRAPH ?g {{\n"
        f"    <{decision}> eat:hasPlacement ?placement .\n"
        "    ?placement eat:position ?position ;\n"
        "               eat:ranks ?referral .\n"
        "  }\n"
        "}\nORDER BY ?position"
    )
    bindings = await _sparql_select(query)
    if not bindings:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="no decision for that hospital/date")

    placements = []
    for row in bindings:
        placement_iri = row["placement"]["value"]
        placements.append(
            {
                "placement": placement_iri,
                "position": int(row["position"]["value"]),
                "referral": row["referral"]["value"],
                "pathway_number": _pathway_number_from_iri(row["referral"]["value"]),
                "evidence": await _evidence_for_placement(placement_iri),
            }
        )
    return {"decision": decision, "placements": placements}
