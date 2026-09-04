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
# Reused vocabularies (tech-stack.md: "PROV-O, SOSA, OWL-Time, SKOS and QUDT") --
# real loaded data uses these directly (e.g. sosa:Observation for every
# per-column observation node), so `short()` needs to know them too, not
# just eat:/eatd:/prov:/rdf:. Found via a real citation resolving to
# unshortened `http://www.w3.org/ns/sosa/...` URIs (AC13 violation) rather
# than assumed up front.
SOSA_NS = "http://www.w3.org/ns/sosa/"
TIME_NS = "http://www.w3.org/2006/time#"
SKOS_NS = "http://www.w3.org/2004/02/skos/core#"
QUDT_NS = "http://qudt.org/schema/qudt/"
UNIT_NS = "http://qudt.org/vocab/unit/"

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


# (namespace, label) pairs `short()` strips, checked in order. Our own
# namespaces (eatd:/eat:/graph) reduce to the bare local name -- unambiguous,
# since they're the dominant vocabulary in every response. Reused vocabularies
# (SOSA in particular: every per-column Observation node is `sosa:Observation`
# with `sosa:observedProperty`/`sosa:hasSimpleResult`/etc. -- confirmed
# against real loaded data, not assumed) keep a short label so a property
# from a different vocabulary doesn't silently collide with one of ours.
_STRIPPABLE_NAMESPACES: list[tuple[str, str]] = [
    (EATD_NS, ""),
    (EAT_NS, ""),
    (GRAPH_BASE, ""),
    (PROV_NS, "prov:"),
    (RDF_NS, "rdf:"),
    (SOSA_NS, "sosa:"),
    (TIME_NS, "time:"),
    (SKOS_NS, "skos:"),
    (QUDT_NS, "qudt:"),
    (UNIT_NS, "unit:"),
]


def short(value: str) -> str:
    """Strips the namespace prefix off a full IRI for API *responses* only --
    internal graph operations (SPARQL queries/updates) always use the full
    IRI, per namespaces.md; this is purely a JSON-response convenience so a
    caller sees `clinic-session/9003/CL02/2026-08-26` instead of the full
    `https://.../kg/id/clinic-session/9003/CL02/2026-08-26`. namespaces.md's
    "no unescaped `/` in a prefixed name" rule is about Turtle/N-Quads files
    specifically (a real serialisation constraint); a JSON string field has
    no such restriction, so this drops the prefix outright (for our own
    namespaces) rather than producing an `eatd:`-style compromise. Values
    outside every known namespace pass through unchanged rather than being
    silently mangled.
    """
    for ns, label in _STRIPPABLE_NAMESPACES:
        if value.startswith(ns):
            return f"{label}{value[len(ns):]}"
    return value


def referral_iri(hospital_hipe: str, pathway_number: str) -> str:
    return eatd(f"referral/{hospital_hipe}/{pathway_number}")


def referral_state_iri(hospital_hipe: str, pathway_number: str, valid_from: str) -> str:
    return eatd(f"referral-state/{hospital_hipe}/{pathway_number}/{valid_from}")


def patient_iri(hospital_hipe: str, patient_id: str) -> str:
    return eatd(f"patient/{hospital_hipe}/{patient_id}")


def person_iri(ihi_number: str) -> str:
    return eatd(f"person/{ihi_number}")


def hospital_iri(hospital_hipe: str) -> str:
    return eatd(f"hospital/{hospital_hipe}")


def service_iri(hospital_hipe: str, specialty_hipe: str) -> str:
    return eatd(f"service/{hospital_hipe}/{specialty_hipe}")


def concept_iri(code_table: str, code_value: int) -> str:
    """A `ref_codes` concept reference (namespaces.md #4's 'Other code
    concepts' row, `{code_table}/{code_value}`) -- used for e.g. `eat:
    gpPriority`/`eat:referralSource`, which are `skos:Concept` references,
    never literals. Referenced only, never re-minted with its own type/
    label triples here -- the batch mapping (reference_layer.rml.ttl)
    already projects the full ConceptScheme for every code_table."""
    return eatd(f"{code_table}/{code_value}")


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


def inputs_graph() -> str:
    """Same named graph the batch Morph-KGC pipeline projects referrals/
    patients/persons into -- a referral written through POST /referrals
    (spec.md FR11) lands here too, so it's indistinguishable from a
    batch-loaded one to every read endpoint."""
    return f"{GRAPH_BASE}inputs"
