"""Tests for the fixture decision generator (spec.md FR4, plan.md Phase 2).

Every assertion here mirrors a real constraint in
dataset/db/migrations/006_outputs.sql -- this is what makes the generator
trustworthy as a stand-in for real agent output in Phase 3's write-path
tests, not just internally self-consistent.
"""

import pytest

from tests.fixtures import (
    VALID_AGENT_NAMES,
    VALID_CITATION_ROLES,
    VALID_EVIDENCE_TYPES,
    VALID_RULE_IDS,
    make_decision,
    make_override,
    make_score,
)

SEEDS = range(25)


class TestDeterminism:
    def test_make_score_same_seed_is_identical(self) -> None:
        assert make_score(42) == make_score(42)

    def test_make_decision_same_seed_is_identical(self) -> None:
        assert make_decision(42) == make_decision(42)

    def test_make_override_same_seed_is_identical(self) -> None:
        assert make_override(42) == make_override(42)

    def test_different_seeds_differ(self) -> None:
        assert make_score(1) != make_score(2)
        assert make_decision(1) != make_decision(2)


class TestScoreConstraints:
    @pytest.mark.parametrize("seed", SEEDS)
    def test_score_in_range(self, seed: int) -> None:
        # agent.agent_scores CHECK as_score_range (score BETWEEN 0 AND 1)
        assert 0 <= make_score(seed).score <= 1

    @pytest.mark.parametrize("seed", SEEDS)
    def test_agent_name_valid(self, seed: int) -> None:
        # agent.agent_scores CHECK as_agent_valid
        assert make_score(seed).agent_name in VALID_AGENT_NAMES

    @pytest.mark.parametrize("seed", SEEDS)
    def test_hospital_hipe_is_four_chars(self, seed: int) -> None:
        # agent.agent_scores.hospital_hipe is char(4)
        assert len(make_score(seed).hospital_hipe) == 4

    @pytest.mark.parametrize("seed", SEEDS)
    def test_citation_evidence_types_valid(self, seed: int) -> None:
        # agent.agent_citations CHECK ac_evidence_type_valid
        for evidence_type, _key in make_score(seed).citations:
            assert evidence_type in VALID_EVIDENCE_TYPES

    @pytest.mark.parametrize("seed", SEEDS)
    def test_at_least_one_citation(self, seed: int) -> None:
        assert len(make_score(seed).citations) >= 1


class TestDecisionConstraints:
    @pytest.mark.parametrize("seed", SEEDS)
    def test_cohort_size_positive(self, seed: int) -> None:
        # agent.decisions CHECK d_cohort_positive (cohort_size > 0)
        decision = make_decision(seed)
        assert len(decision.rankings) > 0

    def test_cohort_size_zero_rejected(self) -> None:
        with pytest.raises(ValueError):
            make_decision(1, cohort_size=0)

    @pytest.mark.parametrize("seed", SEEDS)
    def test_positions_positive_and_unique(self, seed: int) -> None:
        # agent.decision_rankings CHECK dr_position_positive, UNIQUE dr_unique_position
        positions = [r.position for r in make_decision(seed).rankings]
        assert all(p > 0 for p in positions)
        assert len(positions) == len(set(positions))

    @pytest.mark.parametrize("seed", SEEDS)
    def test_ranking_scores_in_range(self, seed: int) -> None:
        for ranking in make_decision(seed).rankings:
            assert 0 <= ranking.urgency_score <= 1
            assert 0 <= ranking.capacity_score <= 1

    @pytest.mark.parametrize("seed", SEEDS)
    def test_citation_roles_valid(self, seed: int) -> None:
        # agent.decision_citations CHECK dc_role_valid
        for ranking in make_decision(seed).rankings:
            for evidence_type, _key, role in ranking.citations:
                assert evidence_type in VALID_EVIDENCE_TYPES
                assert role in VALID_CITATION_ROLES

    @pytest.mark.parametrize("seed", SEEDS)
    def test_rule_ids_valid(self, seed: int) -> None:
        # agent.rule_checks.rule_id FK -> core.ref_rules(rule_id)
        for ranking in make_decision(seed).rankings:
            for rule_id, _passed, _detail in ranking.rule_checks:
                assert rule_id in VALID_RULE_IDS

    @pytest.mark.parametrize("seed", SEEDS)
    def test_rationale_summary_non_blank(self, seed: int) -> None:
        # agent.decision_rankings.rationale_summary is NOT NULL
        for ranking in make_decision(seed).rankings:
            assert ranking.rationale_summary.strip()

    def test_cohort_size_respected(self) -> None:
        assert len(make_decision(1, cohort_size=7).rankings) == 7


class TestOverrideConstraints:
    @pytest.mark.parametrize("seed", SEEDS)
    def test_reason_non_blank(self, seed: int) -> None:
        # agent.overrides CHECK o_reason_not_blank
        assert make_override(seed).reason.strip()

    @pytest.mark.parametrize("seed", SEEDS)
    def test_references_a_real_ranking_in_its_decision(self, seed: int) -> None:
        override = make_override(seed)
        # from_position must be a position that actually exists in the
        # decision the override references -- rebuild with the same seed to
        # get the same decision (determinism, tested above).
        decision = make_decision(seed)
        assert override.decision_id == decision.decision_id
        assert override.from_position in {r.position for r in decision.rankings}
