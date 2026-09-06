"""Tier 2 tests for citations, decision assembly and write-back handling.

Covers plan.md Phase 5, tasks 5.1-5.6 (spec.md FR7/FR8/FR9, ADR-008,
ADR-009). Per `conductor/workflow.md`: tests are written before
`coordinator.app.decision` is implemented (task 5.7).

Expected API of the not-yet-written `coordinator.app.decision`:

- `build_citations(referral, *, legacy_citations=False)`: returns
  `DecisionCitationIn`-shaped dicts (`evidence_type`, `evidence_key`,
  `role`) for one ranked referral. Default mode emits `urgency` (evidence_
  type `"score"`) and `timeframe` (evidence_type `"referral_state"`) per
  ADR-009, plus `capacity` (pass-through of the capacity agent's own
  citations, already valid `bed_status`/`clinic_session` evidence). Every
  `evidence_type` comes from `coordinator.app.citations.ROLE_EVIDENCE_
  TYPES`, never duplicated inline. `legacy_citations=True` instead copies
  the urgency agent's own citations onto the `urgency` role and omits
  `timeframe` entirely (ADR-009's fallback, since `RankingIn.citations`
  only requires `min_length=1`, not one per role).
- `build_rationale_summary(referral)`: the coordinator's own short,
  deterministic sentence -- band, breach status, the two scores, alpha --
  making no claim beyond what's cited, following `conductor/product-
  guidelines.md`'s verb rules (ranks/explains, never admits/schedules/acts).
- `build_coordinator_version(*, semantic_version, capacity_direction,
  alpha_min, alpha_max, score_source)`: one string encoding all five, so
  two decisions made under different assumptions are distinguishable
  (spec.md FR9).
- `build_ranking(referral, *, legacy_citations=False)`: one `RankingIn`-
  shaped dict, assembling citations, rule_checks and rationale_summary.
- `build_decision(*, decision_id, run_id, hospital_hipe, as_of_date,
  coordinator_version, rankings)`: one `DecisionIn`-shaped dict.
- `DecisionPostOutcome`: an enum, `OK` / `PARTIAL` / `REJECTED` / `INVALID`.
- `interpret_decision_response(status_code)`: maps 200/207/400/422 to the
  above, `is_ok` true only for `OK` -- `PARTIAL` (207) is never reported as
  success (spec.md FR9).

No network I/O anywhere in this file (NFR5): the retrieval service is
never called; `interpret_decision_response` is tested against bare status
codes, not a live response.
"""

import re
from datetime import date
from typing import Any

import pytest
from pydantic import ValidationError
from retrieval.app.schemas import DecisionIn

from coordinator.app.citations import ROLE_EVIDENCE_TYPES
from coordinator.app.decision import (
    DecisionPostOutcome,
    build_citations,
    build_coordinator_version,
    build_decision,
    build_ranking,
    build_rationale_summary,
    interpret_decision_response,
)

# Verbs product-guidelines.md's Verbs table names as implying system action
# on the patient, or a diagnostic/corrective claim -- rationale_summary
# must never use these.
_FORBIDDEN_VERBS = (
    "admitted",
    "scheduled",
    "assigned",
    "approved",
    "triaged",
    "decided",
    "diagnoses",
    "indicates",
    "corrected",
    "fixed",
    "resolved",
)


def _referral(pathway_number: str, **overrides: Any) -> dict[str, Any]:
    """Builds a minimal ranked-referral dict for one decision-assembly test.

    Args:
        pathway_number: The referral's pathway_number.
        **overrides: Fields to set on top of the defaults.

    Returns:
        A dict carrying every field `build_ranking`/`build_citations`/
        `build_rationale_summary` need.
    """
    referral: dict[str, Any] = {
        "run_id": "run-2026-09-06-001",
        "hospital_hipe": "9004",
        "pathway_number": pathway_number,
        "position": 1,
        "cpc": 1,
        "band": 1,
        "crt_breached": True,
        "adjusted_wait_days": 41,
        "crt_threshold_days": 28,
        "referral_date": "2026-08-01",
        "urgency_score": 0.8,
        "capacity_score": 0.4,
        "alpha": 0.7,
        "urgency_citations": [
            {
                "evidence_type": "observation",
                "evidence_key": "9004/PW-1/2026-08-16%2009%3A00%3A00/hr",
            }
        ],
        "capacity_citations": [
            {"evidence_type": "bed_status", "evidence_key": "9004/W1/2026-08-30%2008%3A00%3A00"}
        ],
    }
    referral.update(overrides)
    return referral


def test_every_ranking_carries_at_least_one_citation() -> None:
    """Every ranking carries at least one citation (`RankingIn.citations`
    is `min_length=1` -- an uncited placement is unwritable by contract,
    spec.md FR7)."""
    ranking = build_ranking(_referral("PW-1"))
    assert len(ranking["citations"]) >= 1

    legacy_ranking = build_ranking(_referral("PW-1"), legacy_citations=True)
    assert len(legacy_ranking["citations"]) >= 1


def test_citation_roles_map_to_evidence_types_from_the_shared_constant() -> None:
    """Citation roles map correctly to the four subproperties, and each
    role's evidence_type comes from `ROLE_EVIDENCE_TYPES`
    (`coordinator/app/citations.py`) -- never duplicated inline (spec.md
    FR7, ADR-009)."""
    citations = build_citations(_referral("PW-1"))

    roles_seen = {c["role"] for c in citations}
    assert roles_seen == {"urgency", "capacity", "timeframe"}

    for citation in citations:
        assert citation["evidence_type"] == ROLE_EVIDENCE_TYPES[citation["role"]]


def test_legacy_citations_fallback_uses_urgency_agent_citations_and_omits_timeframe() -> None:
    """The `--legacy-citations` fallback (ADR-009) copies the urgency
    agent's own citations onto the `urgency` role and omits `timeframe`
    entirely -- safe because `RankingIn.citations` requires
    `min_length=1`, not one per role."""
    referral = _referral("PW-1")
    citations = build_citations(referral, legacy_citations=True)

    roles_seen = {c["role"] for c in citations}
    assert "timeframe" not in roles_seen
    assert "urgency" in roles_seen

    urgency_citations = [c for c in citations if c["role"] == "urgency"]
    assert len(urgency_citations) == len(referral["urgency_citations"])
    for citation, original in zip(urgency_citations, referral["urgency_citations"], strict=True):
        assert citation["evidence_type"] == original["evidence_type"]
        assert citation["evidence_key"] == original["evidence_key"]


def test_coordinator_version_encodes_all_four_decision_shaping_assumptions() -> None:
    """`coordinator_version` encodes the semantic version, capacity
    direction, alpha bounds and score source, so two decisions made under
    different assumptions are distinguishable after the fact (spec.md
    FR9)."""
    semantic_version = "1.0.0"
    alpha_min, alpha_max = 0.5, 0.9

    fixture_version = build_coordinator_version(
        semantic_version=semantic_version,
        capacity_direction="pressure",
        alpha_min=alpha_min,
        alpha_max=alpha_max,
        score_source="fixture",
    )
    live_version = build_coordinator_version(
        semantic_version=semantic_version,
        capacity_direction="pressure",
        alpha_min=alpha_min,
        alpha_max=alpha_max,
        score_source="live",
    )
    assert fixture_version != live_version

    availability_version = build_coordinator_version(
        semantic_version=semantic_version,
        capacity_direction="availability",
        alpha_min=alpha_min,
        alpha_max=alpha_max,
        score_source="live",
    )
    assert availability_version != live_version

    different_alpha_version = build_coordinator_version(
        semantic_version="1.0.0",
        capacity_direction="pressure",
        alpha_min=0.4,
        alpha_max=0.9,
        score_source="live",
    )
    assert different_alpha_version != live_version

    assert "1.0.0" in live_version


def test_rationale_summary_states_only_what_ranking_used() -> None:
    """`rationale_summary` states only band, breach status, the two
    scores and the weight in force -- and nothing beyond its cited
    evidence (spec.md FR8)."""
    referral = _referral(
        "PW-1", cpc=1, crt_breached=True, urgency_score=0.8, capacity_score=0.4, alpha=0.7
    )
    summary = build_rationale_summary(referral)

    assert "0.8" in summary
    assert "0.4" in summary
    assert "1" in summary or "urgent" in summary.lower()


def test_rationale_summary_uses_no_forbidden_system_as_actor_verbs() -> None:
    """`rationale_summary` follows `conductor/product-guidelines.md`'s
    verb rules: the system ranks and explains, it never admits, schedules
    or acts (spec.md FR8)."""
    summary = build_rationale_summary(_referral("PW-1"))
    lowered = summary.lower()
    for verb in _FORBIDDEN_VERBS:
        assert verb not in lowered, f"forbidden verb {verb!r} found in: {summary!r}"


def test_rationale_summary_is_deterministic_not_llm_output() -> None:
    """`rationale_summary` is the coordinator's own deterministic note,
    not LLM output (spec.md FR8): calling it twice on the same referral
    produces byte-identical text."""
    referral = _referral("PW-1")
    assert build_rationale_summary(referral) == build_rationale_summary(referral)


def test_rationale_summary_never_contains_a_raw_cpc_code() -> None:
    """`rationale_summary` never prints a raw `cpc` value (ADR-003): "CPC
    3" (Semi-Urgent) sitting next to "CPC 2" (Routine) would read as
    *less* urgent to a clinician than Routine, since the NTPF codes don't
    sort in clinical order. Only `core.ref_codes`' own band descriptions
    appear."""
    for cpc in (1, 3, 2, 4, None):
        summary = build_rationale_summary(_referral("PW-1", cpc=cpc))
        for raw_code in ("1", "2", "3", "4"):
            # "1" legitimately appears inside score values like "0.1" or
            # weight "0.7" is fine, but a bare/standalone digit token
            # naming the cpc code itself must never appear.
            assert f"CPC {raw_code}" not in summary


def test_rationale_summary_rounds_displayed_floats_to_three_decimal_places() -> None:
    """Displayed scores are rounded to 3 decimal places for readability --
    floating-point noise like `0.6333333333333333` or `0.7000000000000001`
    must never reach a clinical screen. Rounding is display-only: it must
    not touch the values that enter the sort key or `RankingIn` fields
    (checked separately by `build_ranking`'s own tests, which assert the
    unrounded scores)."""
    referral = _referral(
        "PW-1",
        urgency_score=0.6333333333333333,
        capacity_score=0.7000000000000001,
        alpha=0.6666666666666667,
    )
    summary = build_rationale_summary(referral)

    for match in re.findall(r"\d+\.\d+", summary):
        decimal_places = len(match.split(".")[1])
        assert decimal_places <= 3, f"{match!r} in rationale has more than 3 decimal places"


def test_rationale_summary_never_names_the_bare_alpha_value() -> None:
    """`rationale_summary` describes alpha in plain language a clinician
    can act on, never the internal numeric parameter -- the number stays
    in `coordinator_version` for audit (spec.md FR8, FR9)."""
    distinctive_alpha = 0.734
    referral = _referral("PW-1", alpha=distinctive_alpha)
    summary = build_rationale_summary(referral)

    assert str(distinctive_alpha) not in summary
    assert "weighted" in summary.lower()


def test_rationale_summary_names_days_over_threshold_for_a_breach() -> None:
    """A breached referral's summary names its days over threshold,
    sourced from `adjusted_wait_days` against `crt_threshold_days` --
    "outside the CRT window" alone doesn't distinguish a referral 1 day
    over from one 800 days over."""
    referral = _referral("PW-1", crt_breached=True, adjusted_wait_days=41, crt_threshold_days=28)
    summary = build_rationale_summary(referral)

    assert "13" in summary
    assert "days" in summary.lower()


@pytest.mark.parametrize(
    ("cpc", "expected_band_label"),
    [
        (1, "Urgent"),
        (3, "Semi-Urgent"),
        (2, "Routine/Non-Urgent"),
        (4, "Excluded"),
        (None, "uncategorised"),
    ],
)
@pytest.mark.parametrize(
    ("crt_breached", "expected_breach_fragment"),
    [
        (True, "outside"),
        (False, "within"),
        (None, "no CRT window applies"),
    ],
)
def test_rationale_summary_across_every_band_and_breach_combination(
    cpc: int | None,
    expected_band_label: str,
    crt_breached: bool | None,
    expected_breach_fragment: str,
) -> None:
    """`build_rationale_summary` is exercised across every `cpc` (1, 3, 2,
    4, None) crossed with every `crt_breached` (`True`, `False`, `None`)
    combination -- the existing single-case test only covered the urgent/
    breached path. Each combination must produce the right band label,
    the right breach clause, and stay free of every forbidden verb."""
    referral = _referral("PW-1", cpc=cpc, crt_breached=crt_breached)
    summary = build_rationale_summary(referral)

    assert expected_band_label in summary
    assert expected_breach_fragment in summary

    lowered = summary.lower()
    for verb in _FORBIDDEN_VERBS:
        assert verb not in lowered, f"forbidden verb {verb!r} found in: {summary!r}"


def test_assembled_payload_fails_real_decision_in_validation_today() -> None:
    """THE ADR-009 TEST.

    A decision assembled with the coordinator's default (non-legacy)
    citations -- evidence_type `"score"`/`"referral_state"` -- is
    expected to FAIL validation against the real `DecisionIn` model
    imported from `retrieval.app.schemas`, TODAY, because that service's
    `EvidenceType` Literal does not yet include those two values
    (ADR-009). This is not a bug in the coordinator: it is the tracked
    consequence of an open change request against the retrieval service.

    Do NOT make this test pass by weakening the assertion or mocking
    `DecisionIn` -- it must import and use the real model.

    NOTE THE POLARITY: this test passes *because* validation fails. When
    `retrieval.app.schemas.EvidenceType` is widened, the payload will
    validate, no ValidationError will be raised, and this test will FAIL.
    That failure is the signal that the change request landed. The fix at
    that point is to invert this test into an assertion that the payload
    validates, drop the legacy-citations companion test if it is no longer
    needed, and close ADR-009 -- not to investigate a regression.

    This test and `test_citation_contract.py`'s
    `test_role_evidence_types_are_valid_evidence_types` are the same
    signal seen from opposite sides: that one fails today and goes green
    when the change lands; this one passes today and goes red. Seeing one
    newly green and the other newly red at the same time is the change
    landing, not a second problem.
    """
    ranking = build_ranking(_referral("PW-1"))
    payload = build_decision(
        decision_id="dec-1",
        run_id="run-2026-09-06-001",
        hospital_hipe="9004",
        as_of_date="2026-08-30",
        coordinator_version=build_coordinator_version(
            semantic_version="1.0.0",
            capacity_direction="pressure",
            alpha_min=0.5,
            alpha_max=0.9,
            score_source="fixture",
        ),
        rankings=[ranking],
    )

    with pytest.raises(ValidationError):
        DecisionIn(**payload)


def test_legacy_citations_payload_validates_against_the_real_decision_in() -> None:
    """The `--legacy-citations` fallback payload validates against the
    real `DecisionIn` model TODAY, since it only uses evidence types
    already accepted by `EvidenceType` (ADR-009's working path while the
    change request is pending)."""
    ranking = build_ranking(_referral("PW-1"), legacy_citations=True)
    payload = build_decision(
        decision_id="dec-1",
        run_id="run-2026-09-06-001",
        hospital_hipe="9004",
        as_of_date="2026-08-30",
        coordinator_version=build_coordinator_version(
            semantic_version="1.0.0",
            capacity_direction="pressure",
            alpha_min=0.5,
            alpha_max=0.9,
            score_source="fixture",
        ),
        rankings=[ranking],
    )

    validated = DecisionIn(**payload)
    assert validated.decision_id == "dec-1"
    assert len(validated.rankings) == 1


def test_real_decision_in_positions_unique_validator_is_enforced() -> None:
    """The real `DecisionIn.positions_unique` validator rejects two
    rankings sharing a `position` (`agent.decision_rankings`
    `dr_unique_position`) -- exercised via the real model, not
    reimplemented."""
    ranking_a = build_ranking(_referral("PW-1", position=1), legacy_citations=True)
    ranking_b = build_ranking(_referral("PW-2", position=1), legacy_citations=True)
    payload = build_decision(
        decision_id="dec-1",
        run_id="run-2026-09-06-001",
        hospital_hipe="9004",
        as_of_date="2026-08-30",
        coordinator_version=build_coordinator_version(
            semantic_version="1.0.0",
            capacity_direction="pressure",
            alpha_min=0.5,
            alpha_max=0.9,
            score_source="fixture",
        ),
        rankings=[ranking_a, ranking_b],
    )

    with pytest.raises(ValidationError):
        DecisionIn(**payload)


def test_real_decision_in_min_length_constraints_are_enforced() -> None:
    """The real `DecisionIn.rankings` `min_length=1` and
    `RankingIn.citations` `min_length=1` constraints reject an empty
    decision and an uncited ranking, respectively -- exercised via the
    real model."""
    with pytest.raises(ValidationError):
        DecisionIn(
            decision_id="dec-1",
            run_id="run-2026-09-06-001",
            hospital_hipe="9004",
            as_of_date=date(2026, 8, 30),
            coordinator_version="1.0.0",
            rankings=[],
        )

    uncited_ranking = build_ranking(_referral("PW-1"), legacy_citations=True)
    uncited_ranking["citations"] = []
    payload = build_decision(
        decision_id="dec-1",
        run_id="run-2026-09-06-001",
        hospital_hipe="9004",
        as_of_date="2026-08-30",
        coordinator_version="1.0.0",
        rankings=[uncited_ranking],
    )
    with pytest.raises(ValidationError):
        DecisionIn(**payload)


@pytest.mark.parametrize(
    ("status_code", "expected_outcome"),
    [
        (200, DecisionPostOutcome.OK),
        (207, DecisionPostOutcome.PARTIAL),
        (400, DecisionPostOutcome.REJECTED),
        (422, DecisionPostOutcome.INVALID),
    ],
)
def test_all_four_documented_responses_are_handled(
    status_code: int, expected_outcome: DecisionPostOutcome
) -> None:
    """All four documented `POST /decisions` responses are handled:
    `200` ok, `207` Postgres committed but graph projection failed, `400`
    Postgres rejected, `422` validation failed before either store was
    touched (spec.md FR9)."""
    assert interpret_decision_response(status_code) == expected_outcome


def test_207_is_surfaced_distinctly_from_success_and_never_reported_ok() -> None:
    """A `207` is surfaced as a distinct, non-zero exit condition and is
    never reported as success (spec.md FR9)."""
    partial = interpret_decision_response(207)
    ok = interpret_decision_response(200)

    assert partial != ok
    assert partial.is_ok is False
    assert ok.is_ok is True


def test_unknown_status_code_is_rejected_rather_than_silently_accepted() -> None:
    """An undocumented status code is refused rather than silently
    treated as one of the four known outcomes."""
    with pytest.raises(ValueError):
        interpret_decision_response(500)
