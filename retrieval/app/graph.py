"""SPARQL Update triple construction and dispatch (spec.md FR2/FR6).

Pure triple-construction functions (score_triples/decision_triples/
override_triples) are separated from dispatch (push_triples) so they're
testable without a running Oxigraph -- see tests/test_graph_triples.py.

A None/optional field is simply omitted from the triple list -- never
serialised as the literal string "None" (the Morph-KGC NULL gotcha this
guards against by construction; conductor/kg/requirements.md).
"""

from __future__ import annotations

from datetime import date

import httpx

from . import iri
from .config import settings
from .schemas import DecisionIn, OverrideIn, RankingIn, RuleCheckIn, ScoreIn

Triple = tuple[str, str, str]


def _iri(value: str) -> str:
    return f"<{value}>"


def _string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{escaped}"'


def _decimal(value: float) -> str:
    return f'"{value}"^^xsd:decimal'


def _date(value: date) -> str:
    return f'"{value.isoformat()}"^^xsd:date'


def _bool(value: bool) -> str:
    return f'"{"true" if value else "false"}"^^xsd:boolean'


def _positive_int(value: int) -> str:
    return f'"{value}"^^xsd:positiveInteger'


def _type_triple(subject_iri: str, class_term: str) -> Triple:
    return (_iri(subject_iri), _iri(iri.rdf("type")), _iri(iri.eat(class_term)))


_ROLE_SUBPROPERTY = {
    "urgency": "citesUrgencyEvidence",
    "capacity": "citesCapacityEvidence",
    "timeframe": "citesTimeframeEvidence",
    "multi_list": "citesMultiListEvidence",
}


def score_triples(payload: ScoreIn) -> list[Triple]:
    score = iri.score_iri(
        payload.run_id, payload.hospital_hipe, payload.pathway_number, payload.agent_name
    )
    referral = iri.referral_iri(payload.hospital_hipe, payload.pathway_number)
    activity = iri.score_activity_iri(payload.run_id, payload.agent_name)
    agent = iri.agent_iri(payload.agent_name)

    triples = [
        _type_triple(score, "Score"),
        (_iri(score), _iri(iri.eat("scored")), _iri(referral)),
        (_iri(score), _iri(iri.eat("scoreValue")), _decimal(payload.score)),
        (_iri(score), _iri(iri.eat("method")), _string(payload.method)),
        (_iri(score), _iri(iri.eat("agentVersion")), _string(payload.agent_version)),
        (_iri(score), _iri(iri.prov("wasGeneratedBy")), _iri(activity)),
        (_iri(activity), _iri(iri.prov("wasAssociatedWith")), _iri(agent)),
    ]
    # eat:cites is 1..n on Score, enforced at the ScoreIn schema level
    # (min_length=1) -- every score here has at least one.
    for citation in payload.citations:
        target = iri.evidence_iri(citation.evidence_type, citation.evidence_key)
        # agent_citations carries no `role` column (unlike decision_citations),
        # so these use the base eat:cites, not a role subproperty.
        triples.append((_iri(score), _iri(iri.eat("cites")), _iri(target)))
    return triples


def _ranking_triples(
    ranking: RankingIn, decision_iri_: str, hospital_hipe: str, as_of_date: date
) -> list[Triple]:
    placement = iri.placement_iri(hospital_hipe, as_of_date.isoformat(), ranking.pathway_number)
    referral = iri.referral_iri(ranking.hospital_hipe, ranking.pathway_number)

    triples = [
        _type_triple(placement, "RankedPlacement"),
        (_iri(decision_iri_), _iri(iri.eat("hasPlacement")), _iri(placement)),
        (_iri(placement), _iri(iri.eat("position")), _positive_int(ranking.position)),
        (_iri(placement), _iri(iri.eat("ranks")), _iri(referral)),
    ]
    for citation in ranking.citations:
        target = iri.evidence_iri(citation.evidence_type, citation.evidence_key)
        predicate = iri.eat(_ROLE_SUBPROPERTY[citation.role])
        triples.append((_iri(placement), _iri(predicate), _iri(target)))
    return triples


def _rule_check_triples(
    rule_check_id: str,
    rule_check: RuleCheckIn,
    run_id: str,
    hospital_hipe: str,
    pathway_number: str,
    activity: str,
) -> list[Triple]:
    rule = iri.rule_iri(rule_check.rule_id)
    triples = [
        _type_triple(rule_check_id, "RuleCheck"),
        (_iri(rule_check_id), _iri(iri.eat("testedRule")), _iri(rule)),
        (_iri(rule_check_id), _iri(iri.eat("passed")), _bool(rule_check.passed)),
        (_iri(rule_check_id), _iri(iri.prov("wasGeneratedBy")), _iri(activity)),
    ]
    # detail is nullable in agent.rule_checks -- omitted entirely when None,
    # never serialised as the string "None".
    return triples


def decision_triples(payload: DecisionIn) -> list[Triple]:
    as_of_date = payload.as_of_date.isoformat()
    decision = iri.decision_iri(payload.hospital_hipe, as_of_date)
    activity = iri.decision_activity_iri(payload.run_id, payload.hospital_hipe, as_of_date)
    coordinator = iri.agent_iri("coordinator")

    triples = [
        _type_triple(decision, "Decision"),
        (_iri(decision), _iri(iri.prov("wasGeneratedBy")), _iri(activity)),
        (_iri(activity), _iri(iri.prov("wasAssociatedWith")), _iri(coordinator)),
    ]
    for ranking in payload.rankings:
        triples.extend(
            _ranking_triples(ranking, decision, payload.hospital_hipe, payload.as_of_date)
        )
        for rule_check in ranking.rule_checks:
            rc_iri = iri.rule_check_iri(
                payload.run_id, ranking.hospital_hipe, ranking.pathway_number, rule_check.rule_id
            )
            triples.extend(
                _rule_check_triples(
                    rc_iri,
                    rule_check,
                    payload.run_id,
                    ranking.hospital_hipe,
                    ranking.pathway_number,
                    activity,
                )
            )
    return triples


def override_triples(payload: OverrideIn, as_of_date: date) -> list[Triple]:
    # namespaces.md's Override template is override/{hospital_hipe}/{as_of_date}/
    # {pathway_number}/{override_id} -- as_of_date isn't a column on
    # agent.overrides itself (only decision_id is), so the caller (routes)
    # looks it up from the parent agent.decisions row and passes it in.
    as_of_date_str = as_of_date.isoformat()
    override = iri.override_iri(
        payload.hospital_hipe, as_of_date_str, payload.pathway_number, payload.override_id
    )
    placement = iri.placement_iri(payload.hospital_hipe, as_of_date_str, payload.pathway_number)

    triples = [
        _type_triple(override, "Override"),
        (_iri(override), _iri(iri.eat("revises")), _iri(placement)),
        (_iri(override), _iri(iri.eat("reason")), _string(payload.reason)),
    ]
    # Override carries no prov:wasGeneratedBy (its domain is unionOf(Score,
    # Decision, RuleCheck) only) -- a clinician action, not an agent one.
    return triples


SPARQL_PREFIXES = (
    f"PREFIX eat: <{iri.EAT_NS}>\n"
    f"PREFIX eatd: <{iri.EATD_NS}>\n"
    f"PREFIX prov: <{iri.PROV_NS}>\n"
    "PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>\n"
)


def build_update(triples: list[Triple], graph_iri: str) -> str:
    body = "\n".join(f"{s} {p} {o} ." for s, p, o in triples)
    return f"{SPARQL_PREFIXES}INSERT DATA {{ GRAPH <{graph_iri}> {{\n{body}\n}} }}"


async def push_triples(triples: list[Triple], graph_iri: str) -> None:
    """Raises on any non-2xx response or connection failure -- the caller
    (routes) is responsible for distinguishing this from the Postgres commit
    that already succeeded (spec.md FR2's partial-failure contract)."""
    update = build_update(triples, graph_iri)
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            settings.oxigraph_update_url,
            content=update.encode("utf-8"),
            headers={"Content-Type": "application/sparql-update"},
        )
        response.raise_for_status()
