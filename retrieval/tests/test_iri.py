"""IRI construction tests (spec.md FR6): every template mirrored exactly
from conductor/kg/namespaces.md #4, plus a guard against the known
unescaped-'/'-in-prefixed-name gotcha (conductor/kg/requirements.md) --
enforced here by construction, since these functions only ever build full
<...> IRI strings, never a `prefix:relative` form.
"""

from app import iri

BASE = "https://nonsocynthia.github.io/Tus-Aite-TechIreland-Challenge/kg/id/"
GRAPH_BASE = "https://nonsocynthia.github.io/Tus-Aite-TechIreland-Challenge/kg/graph/"


def test_referral_iri_matches_namespaces_md_template() -> None:
    assert iri.referral_iri("9001", "PW-9001-000007") == f"{BASE}referral/9001/PW-9001-000007"


def test_rule_iri() -> None:
    assert iri.rule_iri("RULE-ORDER") == f"{BASE}rule/RULE-ORDER"


def test_score_iri() -> None:
    assert (
        iri.score_iri("run-0001", "9001", "PW-9001-000007", "urgency")
        == f"{BASE}score/run-0001/9001/PW-9001-000007/urgency"
    )


def test_decision_iri() -> None:
    assert iri.decision_iri("9001", "2026-09-04") == f"{BASE}decision/9001/2026-09-04"


def test_placement_iri() -> None:
    assert (
        iri.placement_iri("9001", "2026-09-04", "PW-9001-000007")
        == f"{BASE}placement/9001/2026-09-04/PW-9001-000007"
    )


def test_rule_check_iri() -> None:
    assert (
        iri.rule_check_iri("run-0001", "9001", "PW-9001-000007", "RULE-ORDER")
        == f"{BASE}rule-check/run-0001/9001/PW-9001-000007/RULE-ORDER"
    )


def test_override_iri() -> None:
    assert (
        iri.override_iri("9001", "2026-09-04", "PW-9001-000007", "ovr-000001")
        == f"{BASE}override/9001/2026-09-04/PW-9001-000007/ovr-000001"
    )


def test_evidence_iri_maps_type_to_segment() -> None:
    assert iri.evidence_iri("observation", "9001/PW-9001-000007/2026-09-04/news2") == (
        f"{BASE}obs/9001/PW-9001-000007/2026-09-04/news2"
    )
    assert iri.evidence_iri("triage_event", "TE-000123") == f"{BASE}triage-event/TE-000123"
    assert iri.evidence_iri("condition", "9001/PW-9001-000007/I219") == (
        f"{BASE}condition/9001/PW-9001-000007/I219"
    )
    assert iri.evidence_iri("bed_status", "9001/W01/2026-09-04T08:00:00") == (
        f"{BASE}bed-status/9001/W01/2026-09-04T08:00:00"
    )
    assert iri.evidence_iri("clinic_session", "9001/CL01/2026-09-04") == (
        f"{BASE}clinic-session/9001/CL01/2026-09-04"
    )


def test_evidence_iri_decision_only_types_match_their_own_builders() -> None:
    # ADR-009: 'score'/'referral_state'/'rule' are citable evidence_types for
    # DecisionCitationIn only. evidence_iri() does a segment lookup and
    # appends evidence_key verbatim -- it never calls score_iri/
    # referral_state_iri/rule_iri, so this guards against the two drifting
    # apart (e.g. a segment rename in one place but not the other).
    assert iri.evidence_iri("score", "run-0001/9001/PW-9001-000007/urgency") == iri.score_iri(
        "run-0001", "9001", "PW-9001-000007", "urgency"
    )
    assert iri.evidence_iri(
        "referral_state", "9001/PW-9001-000007/2026-09-04"
    ) == iri.referral_state_iri("9001", "PW-9001-000007", "2026-09-04")
    assert iri.evidence_iri("rule", "RULE-CRT-URGENT") == iri.rule_iri("RULE-CRT-URGENT")


def test_evidence_iri_rejects_unknown_type() -> None:
    import pytest

    with pytest.raises(ValueError):
        iri.evidence_iri("not_a_real_type", "whatever")


def test_run_graph() -> None:
    assert iri.run_graph("run-0001") == f"{GRAPH_BASE}run/run-0001"


def test_overrides_graph() -> None:
    assert iri.overrides_graph() == f"{GRAPH_BASE}overrides"


def test_no_iri_contains_an_unescaped_prefixed_form() -> None:
    # Every function here returns a full IRI string, so none of them can
    # produce the "eatd:referral/9001/..." form namespaces.md #3 forbids in
    # committed files -- checked directly rather than assumed.
    values = [
        iri.referral_iri("9001", "PW-9001-000007"),
        iri.rule_iri("RULE-ORDER"),
        iri.score_iri("run-0001", "9001", "PW-9001-000007", "urgency"),
        iri.decision_iri("9001", "2026-09-04"),
        iri.evidence_iri("triage_event", "TE-000123"),
    ]
    for value in values:
        assert value.startswith("https://")
        assert not value.startswith("eatd:")
