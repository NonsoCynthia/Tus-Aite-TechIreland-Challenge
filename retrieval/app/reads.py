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
from fastapi import APIRouter, Depends, HTTPException, Query, status

from . import db, iri
from .auth import require_bearer_token
from .config import settings
from .schemas import CitationRole

router = APIRouter(dependencies=[Depends(require_bearer_token)])

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


@router.get(
    "/referrals/{hospital_hipe}/{pathway_number}/wait-counters",
    summary="Get the four wait-time counters for one referral",
    description=(
        "Wraps `kg/queries/wait_counters.rq` unmodified -- the one shared fragment every agent and "
        "the rule checker use, so they can never disagree about a wait. Returns "
        "`days_since_referral`, `days_since_received`, `days_awaiting_triage` (`null` if the "
        "referral isn't currently awaiting triage), and `adjusted_wait_days` (suspensions "
        "subtracted). `404` if the referral has no data as of that date in the graph's `inputs` "
        "layer -- this needs the real dataset loaded via the Morph-KGC pipeline, not just fixture "
        "data from the write endpoints."
    ),
)
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
        "referral": iri.short(referral),
        "as_of_date": as_of_date.isoformat(),
        "days_since_referral": int(row["daysSinceReferral"]["value"]),
        "days_since_received": int(row["daysSinceReceived"]["value"]),
        "days_awaiting_triage": (
            int(row["daysAwaitingTriage"]["value"]) if "daysAwaitingTriage" in row else None
        ),
        "adjusted_wait_days": int(row["adjustedWaitDays"]["value"]),
    }


@router.get(
    "/referrals/{hospital_hipe}/{pathway_number}/context",
    summary="Get everything needed to judge one referral (agent input)",
    description=(
        "Built for the urgency/capacity agents (spec.md FR9, added by user request after "
        "GET /decisions and GET /evidence turned out to only cover the *output* side -- an "
        "agent still had no single call to gather the *input* data it needs to compute a "
        "score in the first place). Returns: the referral's own record (specialty, clinic, "
        "referral/received dates, triage status); every recorded `observation` (vitals -- hr, "
        "sbp, dbp, rr, temp, spo2, pain, avpu, chief complaint, news2, mts/icts category); "
        "every `condition` (ICD-10-AM code, label, whether primary); every `triage_event`; "
        "and a `capacity` section -- every ward serving this referral's specialty (primary "
        "ward first) with its latest bed-status snapshot, plus the 5 most recent clinic "
        "sessions for that specialty. Reads straight from Postgres `core.*` (retrieval_rw's "
        "existing SELECT grant), not the graph -- this is raw input data, not an audit trail "
        "of agent output, so there's nothing to resolve via `eat:cites`. `404` if the "
        "referral itself doesn't exist."
    ),
)
async def referral_context(hospital_hipe: str, pathway_number: str) -> dict[str, Any]:
    context = db.get_referral_context(hospital_hipe, pathway_number)
    if context is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="no such referral")
    return context


@router.get(
    "/hospitals/{hospital_hipe}/cohort/{as_of_date}",
    summary="Get the coordinator's cohort for one hospital-day (agent input)",
    description=(
        "Built for the coordinating agent (spec.md FR10, added by user request): which "
        "referrals need ranking at this hospital, on this day. Every referral still on the "
        "waiting list (`removal_date IS NULL`) as of that date, with its specialty, referral/"
        "received dates, wait counters (`days_since_referral`, `adjusted_wait_days`, etc. -- "
        "the same numbers `wait-counters` computes, denormalised onto this row already so "
        "there's no need to call that endpoint per referral), CPC (`cpc`, from its triage "
        "event, `null` if not yet triaged), and a `currently_suspended` flag. That flag is "
        "informational only -- whether to rank a suspended referral is the coordinator's "
        "judgement, not decided here. Also includes `crt_threshold_days` (the Clinical "
        "Response Time limit for this referral's CPC, e.g. 28 for Urgent, 91 for Semi-Urgent, "
        "`null` for Routine/Excluded/untriaged) and `crt_breached` (`adjusted_wait_days > "
        "crt_threshold_days`, `null` when no threshold applies) -- unlike `currently_suspended`, "
        "this IS computed here: it's a single-referral fact against a documented, already-"
        "normative threshold (tech-stack.md Decision 5 calls RULE-CRT-* 'facts about the "
        "hospital, not invalid graphs'), not a ranking judgement between referrals. Empty list "
        "(not 404) if the hospital exists but nothing is on the list that day."
    ),
)
async def cohort(hospital_hipe: str, as_of_date: date) -> dict[str, Any]:
    return {
        "hospital_hipe": hospital_hipe,
        "as_of_date": as_of_date.isoformat(),
        "referrals": db.get_cohort(hospital_hipe, as_of_date),
    }


@router.get(
    "/runs/{run_id}/hospitals/{hospital_hipe}/scores",
    summary="Get already-written agent scores for one run (agent input)",
    description=(
        "Built for the coordinating agent (spec.md FR10, added by user request): the urgency "
        "and capacity scores the other two agents already wrote via POST /scores for this run "
        "and hospital, with their citations -- so the coordinator can gather its whole "
        "cohort's scores in one call instead of guessing at agent.agent_scores directly. "
        "Response is keyed by pathway_number, then by agent_name ('urgency'/'capacity') -- a "
        "referral only appears if at least one agent has scored it; a referral with only one "
        "of the two agents' scores written so far still appears, with just that one key. "
        "Empty `scores` object (not 404) if nothing has been scored yet for this run/hospital."
    ),
)
async def scores_for_run(run_id: str, hospital_hipe: str) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "hospital_hipe": hospital_hipe,
        "scores": db.get_scores_for_run(run_id, hospital_hipe),
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


async def _resolve_iri(target_iri: str) -> dict[str, Any]:
    """Dereferences one graph node into its own properties (spec.md FR8) --
    walking eat:cites (_evidence_query above) only tells you *which* node was
    cited, as an IRI; this is the second hop that says *what it says* (e.g. a
    BedStatus's actual occupancy numbers). Folded directly into the read
    endpoints below rather than a separate endpoint the UI would have to
    round-trip to -- callers get fully-resolved evidence in one request.

    Every predicate/class name is shortened (iri.short) for the response --
    a caller has no use for the full
    `https://nonsocynthia.github.io/.../kg/ns#slotsAvailable` when
    `slotsAvailable` identifies the same thing unambiguously within this
    API's own responses. If the IRI has no triples at all (nothing loaded
    for it yet), this degrades to an empty `properties` dict rather than
    failing the whole enclosing response -- one missing citation's detail
    shouldn't take down an otherwise-complete decision.
    """
    query = f"SELECT ?p ?o WHERE {{\n  GRAPH ?g {{ <{target_iri}> ?p ?o }}\n}}"
    bindings = await _sparql_select(query)
    rdf_type = iri.rdf("type")
    entity_type: str | None = None
    properties: dict[str, str] = {}
    for row in bindings:
        predicate = row["p"]["value"]
        obj = row["o"]["value"]
        if predicate == rdf_type:
            entity_type = iri.short(obj)
            continue
        properties[iri.short(predicate)] = iri.short(obj)
    return {"iri": iri.short(target_iri), "type": entity_type, "properties": properties}


async def _evidence_for_placement(
    placement_iri: str, role: CitationRole | None = None
) -> list[dict[str, Any]]:
    bindings = await _sparql_select(_evidence_query(placement_iri, role))
    results = []
    for b in bindings:
        resolved = await _resolve_iri(b["evidence"]["value"])
        results.append({"role": b["role"]["value"], **resolved})
    return results


@router.get(
    "/evidence/{hospital_hipe}/{as_of_date}/{pathway_number}",
    summary="Get one ranked position's cited evidence, resolved",
    description=(
        "Every citation the coordinator recorded for this placement (via `POST /decisions`), "
        "each already resolved (spec.md FR8) into its actual properties -- not just the IRI of "
        "the node that was cited. Omit `role` for all four citation roles "
        "(`urgency`/`capacity`/`timeframe`/`multi_list`) at once, the full row-expansion view; "
        "pass one to narrow to just that section. A citation whose underlying evidence node has "
        "no data loaded (common in a dev environment without the full dataset) still appears, "
        "with `type: null` and empty `properties`, rather than being dropped or erroring."
    ),
)
async def evidence_for_placement(
    hospital_hipe: str,
    as_of_date: date,
    pathway_number: str,
    role: CitationRole | None = None,
) -> dict[str, Any]:
    placement = iri.placement_iri(hospital_hipe, as_of_date.isoformat(), pathway_number)
    return {
        "placement": iri.short(placement),
        "evidence": await _evidence_for_placement(placement, role),
    }


@router.get(
    "/decisions/{hospital_hipe}/{as_of_date}",
    summary="Get one hospital-day's ranked list, with resolved evidence",
    description=(
        "The audit trail, made queryable: reconstructs the full decision -- every ranked "
        "position, in order, with its cited evidence already resolved to actual properties "
        "(FR8), not just IRIs -- purely by walking `eat:hasPlacement` then `eat:cites` from the "
        "`Decision` node. No placement is ever returned without evidence (spec.md NFR2): every "
        "one has at least one citation, guaranteed by write-time validation, not by filtering "
        "here. `404` if nothing has been written for that hospital/date yet. Note: a second "
        "`POST /decisions` for the same hospital and day adds its placements to this same "
        "result rather than replacing it -- the graph node is keyed only by "
        "`(hospital_hipe, as_of_date)`."
    ),
)
async def get_decision(hospital_hipe: str, as_of_date: date) -> dict[str, Any]:
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
        referral_iri = row["referral"]["value"]
        placements.append(
            {
                "placement": iri.short(placement_iri),
                "position": int(row["position"]["value"]),
                "referral": iri.short(referral_iri),
                "pathway_number": _pathway_number_from_iri(referral_iri),
                "evidence": await _evidence_for_placement(placement_iri),
            }
        )
    return {"decision": iri.short(decision), "placements": placements}
