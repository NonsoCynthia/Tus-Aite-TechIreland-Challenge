"""IRI and named-graph construction, per conductor/kg/namespaces.md.

That file is authoritative for the classes it names a template for (Score,
Decision, RankedPlacement, RuleCheck, Override, Referral, Rule) -- those
templates are reproduced here verbatim. It does not give a template for
Activity/Agent nodes (needed for prov:wasGeneratedBy/prov:wasAssociatedWith)
or for citation-evidence targets; both are filled in below with a documented
convention rather than left unimplemented -- see the docstring on each.
"""

from __future__ import annotations

EAT_NS = "https://nonsocynthia.github.io/Tus-Aite-TechIreland-Challenge/kg/ns#"
EATD_NS = "https://nonsocynthia.github.io/Tus-Aite-TechIreland-Challenge/kg/id/"
GRAPH_BASE = "https://nonsocynthia.github.io/Tus-Aite-TechIreland-Challenge/kg/graph/"
PROV_NS = "http://www.w3.org/ns/prov#"
RDF_NS = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"

# evidence_type (agent_citations/decision_citations) -> the IRI path segment
# for that evidence class's own template in namespaces.md #4. 'observation'
# maps to the per-column Observation class ('obs/...'), not ObservationEvent
# -- the CHECK constraint's value is singular and per-measurement.
_EVIDENCE_SEGMENT = {
    "observation": "obs",
    "condition": "condition",
    "triage_event": "triage-event",
    "bed_status": "bed-status",
    "clinic_session": "clinic-session",
}


def eat(term: str) -> str:
    return f"{EAT_NS}{term}"


def eatd(path: str) -> str:
    return f"{EATD_NS}{path}"


def prov(term: str) -> str:
    return f"{PROV_NS}{term}"


def rdf(term: str) -> str:
    return f"{RDF_NS}{term}"


def short(value: str) -> str:
    """Strips the namespace prefix off a full IRI for API *responses* only --
    internal graph operations (SPARQL queries/updates) always use the full
    IRI, per namespaces.md; this is purely a JSON-response convenience so a
    caller sees `clinic-session/9003/CL02/2026-08-26` instead of the full
    `https://.../kg/id/clinic-session/9003/CL02/2026-08-26`. namespaces.md's
    "no unescaped `/` in a prefixed name" rule is about Turtle/N-Quads files
    specifically (a real serialisation constraint); a JSON string field has
    no such restriction, so this drops the prefix outright rather than
    producing an `eatd:`-style compromise. Values outside our namespaces
    (rare, but possible for object values in resolved evidence) pass through
    unchanged rather than being silently mangled.
    """
    for ns in (EATD_NS, EAT_NS, GRAPH_BASE):
        if value.startswith(ns):
            return value[len(ns) :]
    return value


def referral_iri(hospital_hipe: str, pathway_number: str) -> str:
    return eatd(f"referral/{hospital_hipe}/{pathway_number}")


def rule_iri(rule_id: str) -> str:
    return eatd(f"rule/{rule_id}")


def score_iri(run_id: str, hospital_hipe: str, pathway_number: str, agent_name: str) -> str:
    return eatd(f"score/{run_id}/{hospital_hipe}/{pathway_number}/{agent_name}")


def decision_iri(hospital_hipe: str, as_of_date: str) -> str:
    return eatd(f"decision/{hospital_hipe}/{as_of_date}")


def placement_iri(hospital_hipe: str, as_of_date: str, pathway_number: str) -> str:
    return eatd(f"placement/{hospital_hipe}/{as_of_date}/{pathway_number}")


def rule_check_iri(run_id: str, hospital_hipe: str, pathway_number: str, rule_id: str) -> str:
    return eatd(f"rule-check/{run_id}/{hospital_hipe}/{pathway_number}/{rule_id}")


def override_iri(hospital_hipe: str, as_of_date: str, pathway_number: str, override_id: str) -> str:
    return eatd(f"override/{hospital_hipe}/{as_of_date}/{pathway_number}/{override_id}")


def evidence_iri(evidence_type: str, evidence_key: str) -> str:
    """Citation target IRI (agent_citations/decision_citations).

    Not in namespaces.md's template table -- the four evidence classes each
    have their own multi-part composite key, and the citation tables only
    store a flat (evidence_type, evidence_key) pair. Convention, confirmed
    with the track owner rather than invented silently: the citing caller
    supplies `evidence_key` as the exact composite-key suffix from that
    evidence type's own template in namespaces.md #4 (e.g. for
    'observation': "{hospital_hipe}/{pathway_number}/{obs_datetime}/{column}"
    to match `obs/...`). This function only does the evidence_type -> path
    segment lookup and appends evidence_key verbatim.
    """
    try:
        segment = _EVIDENCE_SEGMENT[evidence_type]
    except KeyError as exc:
        raise ValueError(f"unknown evidence_type: {evidence_type!r}") from exc
    return eatd(f"{segment}/{evidence_key}")


def agent_iri(agent_name: str) -> str:
    """Not in namespaces.md -- prov:wasAssociatedWith needs a stable Agent
    IRI and none is templated there. One IRI per named agent identity
    (urgency/capacity/coordinator), not per run: the agent's version is
    already a separate literal property (eat:agentVersion /
    coordinator_version), so it doesn't belong in the identity IRI too.
    """
    return eatd(f"agent/{agent_name}")


def score_activity_iri(run_id: str, agent_name: str) -> str:
    """One activity per (run_id, agent_name): every Score that agent produced
    in that run shares the one execution that produced them, per
    prov:wasGeneratedBy's cardinality-1-per-node (not cardinality-1 overall).
    """
    return eatd(f"activity/{run_id}/{agent_name}")


def decision_activity_iri(run_id: str, hospital_hipe: str, as_of_date: str) -> str:
    """One activity per (run_id, hospital_hipe, as_of_date): the coordinator's
    execution that produced this Decision. RuleChecks for the same decision
    share this same activity -- they're produced by the same coordinator run,
    not a separate rule-checking agent.
    """
    return eatd(f"activity/{run_id}/coordinator/{hospital_hipe}/{as_of_date}")


def run_graph(run_id: str) -> str:
    return f"{GRAPH_BASE}run/{run_id}"


def overrides_graph() -> str:
    return f"{GRAPH_BASE}overrides"
