"""Pure unit tests for triple construction (spec.md FR2) -- no Oxigraph
needed, since app.graph separates building triples from pushing them.
"""

from app import graph, iri
from app.schemas import ScoreIn
from tests.adapters import to_decision_in, to_override_in, to_score_in
from tests.fixtures import make_decision, make_override, make_score


def _predicates(triples: list[tuple[str, str, str]]) -> list[str]:
    return [p for _, p, _ in triples]


def _score_iri(payload: ScoreIn) -> str:
    return iri.score_iri(
        payload.run_id, payload.hospital_hipe, payload.pathway_number, payload.agent_name
    )


class TestScoreTriples:
    def test_has_rdf_type_score(self) -> None:
        payload = to_score_in(make_score(1))
        triples = graph.score_triples(payload)
        expected = (f"<{_score_iri(payload)}>", f"<{iri.rdf('type')}>", f"<{iri.eat('Score')}>")
        assert expected in [(s, p, o) for s, p, o in triples]

    def test_scored_referral_and_literals(self) -> None:
        payload = to_score_in(make_score(2))
        triples = graph.score_triples(payload)
        score_subject = f"<{_score_iri(payload)}>"
        by_predicate = {p: o for s, p, o in triples if s == score_subject}
        referral = iri.referral_iri(payload.hospital_hipe, payload.pathway_number)

        assert by_predicate[f"<{iri.eat('scored')}>"] == f"<{referral}>"
        assert by_predicate[f"<{iri.eat('scoreValue')}>"] == f'"{payload.score}"^^xsd:decimal'
        assert by_predicate[f"<{iri.eat('method')}>"] == f'"{payload.method}"'
        assert by_predicate[f"<{iri.eat('agentVersion')}>"] == f'"{payload.agent_version}"'

    def test_wasGeneratedBy_and_wasAssociatedWith_present(self) -> None:
        payload = to_score_in(make_score(3))
        triples = graph.score_triples(payload)
        predicates = _predicates(triples)
        assert f"<{iri.prov('wasGeneratedBy')}>" in predicates
        assert f"<{iri.prov('wasAssociatedWith')}>" in predicates

    def test_one_cites_edge_per_citation(self) -> None:
        payload = to_score_in(make_score(4))
        triples = graph.score_triples(payload)
        cites_edges = [t for t in triples if t[1] == f"<{iri.eat('cites')}>"]
        assert len(cites_edges) == len(payload.citations)
        expected_targets = {
            f"<{iri.evidence_iri(c.evidence_type, c.evidence_key)}>" for c in payload.citations
        }
        assert {o for _, _, o in cites_edges} == expected_targets


class TestDecisionTriples:
    def test_decision_has_one_placement_per_ranking(self) -> None:
        payload = to_decision_in(make_decision(5, cohort_size=4))
        triples = graph.decision_triples(payload)
        has_placement = [t for t in triples if t[1] == f"<{iri.eat('hasPlacement')}>"]
        assert len(has_placement) == len(payload.rankings)

    def test_placement_position_and_ranks(self) -> None:
        payload = to_decision_in(make_decision(6, cohort_size=2))
        triples = graph.decision_triples(payload)
        as_of = payload.as_of_date.isoformat()
        for ranking in payload.rankings:
            placement_iri = iri.placement_iri(payload.hospital_hipe, as_of, ranking.pathway_number)
            placement = f"<{placement_iri}>"
            by_predicate = {p: o for s, p, o in triples if s == placement}
            referral = iri.referral_iri(ranking.hospital_hipe, ranking.pathway_number)

            assert by_predicate[f"<{iri.eat('position')}>"] == (
                f'"{ranking.position}"^^xsd:positiveInteger'
            )
            assert by_predicate[f"<{iri.eat('ranks')}>"] == f"<{referral}>"

    def test_citation_uses_role_subproperty_not_base_cites(self) -> None:
        payload = to_decision_in(make_decision(7, cohort_size=1))
        triples = graph.decision_triples(payload)
        ranking = payload.rankings[0]
        for citation in ranking.citations:
            subproperty = graph._ROLE_SUBPROPERTY[citation.role]
            expected_predicate = f"<{iri.eat(subproperty)}>"
            target = iri.evidence_iri(citation.evidence_type, citation.evidence_key)
            expected_target = f"<{target}>"
            assert (expected_predicate, expected_target) in [(p, o) for _, p, o in triples]
        # base eat:cites is never used directly for decision citations -- only
        # the role subproperties (unlike score citations, which have no role).
        assert f"<{iri.eat('cites')}>" not in _predicates(triples)

    def test_rule_check_triples_present_and_correct(self) -> None:
        payload = to_decision_in(make_decision(8, cohort_size=1))
        triples = graph.decision_triples(payload)
        ranking = payload.rankings[0]
        for rule_check in ranking.rule_checks:
            rc_iri = iri.rule_check_iri(
                payload.run_id, ranking.hospital_hipe, ranking.pathway_number, rule_check.rule_id
            )
            subject = f"<{rc_iri}>"
            by_predicate = {p: o for s, p, o in triples if s == subject}
            rule = iri.rule_iri(rule_check.rule_id)
            passed_literal = f'"{"true" if rule_check.passed else "false"}"^^xsd:boolean'

            assert by_predicate[f"<{iri.eat('testedRule')}>"] == f"<{rule}>"
            assert by_predicate[f"<{iri.eat('passed')}>"] == passed_literal

    def test_null_detail_never_serialised_as_none_string(self) -> None:
        # Morph-KGC NULL gotcha guard (conductor/kg/requirements.md), applied
        # to hand-written SPARQL Update too: rule_checks.detail is nullable
        # and every fixture rule check has detail=None -- if the string
        # "None" ever appeared as a literal, this would catch it.
        payload = to_decision_in(make_decision(9, cohort_size=3))
        triples = graph.decision_triples(payload)
        serialised = "\n".join(f"{s} {p} {o}" for s, p, o in triples)
        assert '"None"' not in serialised
        assert "None" not in serialised


class TestOverrideTriples:
    def test_revises_placement_and_reason(self) -> None:
        decision = make_decision(10, cohort_size=2)
        override_payload = to_override_in(make_override(10, decision=decision))
        triples = graph.override_triples(override_payload, decision.as_of_date)
        as_of = decision.as_of_date.isoformat()

        override_iri = iri.override_iri(
            override_payload.hospital_hipe, as_of, override_payload.pathway_number,
            override_payload.override_id,
        )
        placement_iri = iri.placement_iri(
            override_payload.hospital_hipe, as_of, override_payload.pathway_number
        )
        override_subject = f"<{override_iri}>"
        by_predicate = {p: o for s, p, o in triples if s == override_subject}

        assert by_predicate[f"<{iri.eat('reason')}>"] == f'"{override_payload.reason}"'
        assert by_predicate[f"<{iri.eat('revises')}>"] == f"<{placement_iri}>"

    def test_override_has_no_wasGeneratedBy(self) -> None:
        # Override's domain for prov:wasGeneratedBy is unionOf(Score,
        # Decision, RuleCheck) only -- a clinician action, not an agent one.
        decision = make_decision(11, cohort_size=1)
        override_payload = to_override_in(make_override(11, decision=decision))
        triples = graph.override_triples(override_payload, decision.as_of_date)
        assert f"<{iri.prov('wasGeneratedBy')}>" not in _predicates(triples)
