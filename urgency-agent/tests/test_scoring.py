"""Tier 1, strict TDD: the deterministic urgency scorer.

Every NEWS2 boundary below is pinned to the published rubric (scale 1,
breathing air) -- not to our implementation, and not to the dataset
generator's copy of it. The generator's `news2()`
(`dataset/generator/generate.py:63`) is used as an *oracle* in
`test_real_fixture_*` at the bottom of this file, never as the source of the
expected values here; deriving both from the same place would only prove the
two agree, which is the exact trap
`BUILDING_AN_AGENT_WITH_CONDUCTOR.md` Step 7 documents.

ADRs enforced (conductor/tracks/explainable-agent-based-triage_20260828/decisions.md):
  ADR-004  NEWS2 is the only scored component in v1; no MTS anywhere.
  ADR-005  The most recent observation is the one scored.
  ADR-006  NEWS2 maps to [0,1] through calibrated escalation breakpoints.
  ADR-007  Specialty 0601 (paediatric) is refused, never scored.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from urgency_agent.calibration import load_calibration
from urgency_agent.scoring import (
    NEWS2_MAX,
    NEWS2_VITALS,
    Citation,
    InsufficientUrgencyEvidenceError,
    news2_components,
    news2_total,
    normalise_news2,
    score_urgency,
)

FIXTURES = Path(__file__).parent / "fixtures"

# Every NEWS2 component scores 0 on this observation, so a test can vary one
# vital and read the total as that vital's component.
NORMAL_VITALS: dict[str, Any] = {
    "hr": 70,
    "sbp": 120,
    "dbp": 80,
    "rr": 16,
    "temp": 37.0,
    "spo2": 98,
    "pain": 0,
    "avpu": "A",
}


def make_observation(obs_datetime: str = "2026-08-16T09:16:00", **overrides: Any) -> dict[str, Any]:
    return {"obs_datetime": obs_datetime, **NORMAL_VITALS, **overrides}


def make_context(
    *,
    specialty_hipe: str = "1800",
    hospital_hipe: str = "9004",
    pathway_number: str = "PW-9004-000286",
    observations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "referral": {
            "hospital_hipe": hospital_hipe,
            "pathway_number": pathway_number,
            "specialty_hipe": specialty_hipe,
        },
        "observations": [make_observation()] if observations is None else observations,
    }


@pytest.fixture
def calibration():  # type: ignore[no-untyped-def]
    return load_calibration()


# --------------------------------------------------------------------------- #
# NEWS2 component boundaries -- straight from the rubric, scale 1, air
# --------------------------------------------------------------------------- #


# Each case sits exactly ON a boundary or one step past it. Off-by-one errors
# in a threshold are the whole failure mode this table exists to catch, so
# midpoints are deliberately absent.
@pytest.mark.parametrize(
    ("rr", "expected"),
    [(8, 3), (9, 1), (11, 1), (12, 0), (20, 0), (21, 2), (24, 2), (25, 3)],
)
def test_respiratory_rate_boundaries(rr: int, expected: int) -> None:
    assert news2_components(make_observation(rr=rr))["rr"] == expected


@pytest.mark.parametrize(
    ("spo2", "expected"), [(91, 3), (92, 2), (93, 2), (94, 1), (95, 1), (96, 0), (100, 0)]
)
def test_oxygen_saturation_boundaries(spo2: int, expected: int) -> None:
    """Scale 1. The data carries no supplemental-oxygen field, so scale 2 and
    the +2 for oxygen therapy are unreachable here and are not implemented."""
    assert news2_components(make_observation(spo2=spo2))["spo2"] == expected


@pytest.mark.parametrize(
    ("sbp", "expected"),
    [(90, 3), (91, 2), (100, 2), (101, 1), (110, 1), (111, 0), (219, 0), (220, 3)],
)
def test_systolic_blood_pressure_boundaries(sbp: int, expected: int) -> None:
    """Note the non-monotonic tail: SBP >= 220 scores 3, the same as
    SBP <= 90. A scorer written as a simple descending ladder gets this
    wrong and no mid-range test would notice."""
    assert news2_components(make_observation(sbp=sbp))["sbp"] == expected


@pytest.mark.parametrize(
    ("hr", "expected"),
    [(40, 3), (41, 1), (50, 1), (51, 0), (90, 0), (91, 1), (110, 1), (111, 2), (130, 2), (131, 3)],
)
def test_heart_rate_boundaries(hr: int, expected: int) -> None:
    assert news2_components(make_observation(hr=hr))["hr"] == expected


@pytest.mark.parametrize(
    ("temp", "expected"),
    [(35.0, 3), (35.1, 1), (36.0, 1), (36.1, 0), (38.0, 0), (38.1, 1), (39.0, 1), (39.1, 2)],
)
def test_temperature_boundaries(temp: float, expected: int) -> None:
    """Temperature is the one component that never reaches 3 -- its top band
    is 2. That asymmetry is why NEWS2_MAX is 17, not 18."""
    assert news2_components(make_observation(temp=temp))["temp"] == expected


@pytest.mark.parametrize(("avpu", "expected"), [("A", 0), ("V", 3), ("P", 3), ("U", 3)])
def test_consciousness_boundaries(avpu: str, expected: int) -> None:
    """Binary by construction: alert scores 0, anything else scores 3. There
    is no intermediate value in NEWS2."""
    assert news2_components(make_observation(avpu=avpu))["avpu"] == expected


# --------------------------------------------------------------------------- #
# NEWS2 total
# --------------------------------------------------------------------------- #


def test_normal_observation_scores_zero() -> None:
    assert news2_total(make_observation()) == 0


def test_total_is_the_sum_of_its_components() -> None:
    obs = make_observation(rr=22, spo2=93, hr=115, temp=39.5)
    assert news2_total(obs) == sum(news2_components(obs).values())


def test_total_of_worst_case_is_news2_max() -> None:
    """3 (rr) + 3 (spo2) + 3 (sbp) + 3 (hr) + 3 (avpu) + 2 (temp) = 17.

    The generator caps its own score at 20 (`min(s, 20)`), but 20 is
    unreachable on scale 1 -- temperature's ceiling is 2. NEWS2_MAX must be
    the reachable maximum, because ADR-006's top breakpoint anchors to it: an
    18 or 20 there would mean no real observation could ever score 1.0.
    """
    worst = make_observation(rr=4, spo2=85, sbp=70, hr=180, temp=41.0, avpu="U")
    assert news2_total(worst) == 17
    assert NEWS2_MAX == 17


def test_components_cover_exactly_the_six_news2_vitals() -> None:
    """dbp and pain are present in core.observations and are NOT NEWS2
    inputs. Scoring them would silently invent a seventh component."""
    assert set(news2_components(make_observation())) == set(NEWS2_VITALS)
    assert set(NEWS2_VITALS) == {"rr", "spo2", "sbp", "hr", "avpu", "temp"}


# --------------------------------------------------------------------------- #
# ADR-006: normalisation to [0, 1] through escalation breakpoints
# --------------------------------------------------------------------------- #


def test_normalisation_anchors_at_zero_and_one(calibration) -> None:  # type: ignore[no-untyped-def]
    assert normalise_news2(0, calibration) == 0.0
    assert normalise_news2(NEWS2_MAX, calibration) == 1.0


def test_normalisation_is_monotonic_non_decreasing(calibration) -> None:  # type: ignore[no-untyped-def]
    """The one property that must hold whatever the breakpoints are tuned to:
    a sicker patient can never score lower. Everything else about the curve is
    a calibration choice; this is not."""
    scores = [normalise_news2(n, calibration) for n in range(NEWS2_MAX + 1)]
    assert scores == sorted(scores)


def test_normalisation_stays_in_range(calibration) -> None:  # type: ignore[no-untyped-def]
    """ScoreIn.score is `ge=0, le=1` -- out of range is a 422 from the
    retrieval service, not a bad score."""
    for n in range(NEWS2_MAX + 1):
        assert 0.0 <= normalise_news2(n, calibration) <= 1.0


def test_normalisation_separates_the_escalation_bands(calibration) -> None:  # type: ignore[no-untyped-def]
    """ADR-006's whole point. A referral in the high-response band (>=7) must
    score strictly above one at the top of the low band (<=4), by a visible
    margin rather than the 3/20 = 0.15 a linear map would give.
    """
    assert normalise_news2(7, calibration) - normalise_news2(4, calibration) > 0.2


def test_normalisation_is_not_linear_in_news2(calibration) -> None:  # type: ignore[no-untyped-def]
    """EXPECTED TO PASS, and to keep passing. If someone 'simplifies'
    normalisation to news2/NEWS2_MAX this goes red -- which is the point.
    ADR-006 exists because a linear map compresses the whole population into
    the bottom of the range, exactly as min-max did on the coordinator."""
    linear = [n / NEWS2_MAX for n in range(NEWS2_MAX + 1)]
    actual = [normalise_news2(n, calibration) for n in range(NEWS2_MAX + 1)]
    assert actual != pytest.approx(linear)


def test_normalisation_preserves_ordering_within_a_band(calibration) -> None:  # type: ignore[no-untyped-def]
    """A pure step function would give every referral in a band the same
    score, producing hundreds of ties for the coordinator to break on wait
    time alone. Interpolation inside a band is required, not optional.

    REVISED 2026-09-08: previously compared news2 8 and 12. Both now sit above
    the top anchor (7) and saturate at 1.0, so that pair no longer tests
    interpolation -- it tests saturation, which
    `test_scores_saturate_above_the_top_anchor` covers deliberately.
    """
    assert normalise_news2(1, calibration) < normalise_news2(3, calibration)
    assert normalise_news2(5, calibration) < normalise_news2(6, calibration)


def test_scores_saturate_above_the_top_anchor(calibration) -> None:  # type: ignore[no-untyped-def]
    """ADR-006 as revised: the top anchor is NEWS2 7, the emergency-response
    threshold, not the rubric maximum of 17. Anything above it scores 1.0.

    This is clinically deliberate, not a clamp of convenience -- NEWS2 >= 7 is
    a single escalation category, and a 9 does not trigger a different
    response than a 7. It also means a future cohort containing scores this
    dataset never produced still ranks sensibly rather than exceeding 1.0.
    """
    assert normalise_news2(7, calibration) == 1.0
    assert normalise_news2(8, calibration) == 1.0
    assert normalise_news2(NEWS2_MAX, calibration) == 1.0


def test_the_highest_score_is_reachable_by_real_data(calibration) -> None:  # type: ignore[no-untyped-def]
    """The defect this ADR-006 revision fixes, pinned so it cannot return.

    The previous calibration anchored 1.0 at NEWS2 17. Measured across all 609
    observations in data v1.1, NEWS2 never exceeds 7 -- so the best any real
    referral could score was 0.636 and the top 36% of the range was dead.
    A score range no observation can reach is not a calibration choice, it is
    a bug.
    """
    highest_observed_in_data_v1_1 = 7
    assert normalise_news2(highest_observed_in_data_v1_1, calibration) == 1.0


# --------------------------------------------------------------------------- #
# ADR-005: which observation gets scored
# --------------------------------------------------------------------------- #


def test_scores_the_most_recent_observation(calibration) -> None:  # type: ignore[no-untyped-def]
    """The endpoint returns observations ORDER BY obs_datetime ASC
    (retrieval/app/db.py:342-351), so the last element is the newest."""
    context = make_context(
        observations=[
            make_observation("2026-08-14T09:00:00", rr=30, spo2=88, avpu="V"),  # very sick
            make_observation("2026-08-16T09:16:00"),  # recovered, all normal
        ]
    )
    result = score_urgency(context, calibration)
    assert result.news2 == 0
    assert result.score == 0.0


def test_does_not_take_the_worst_observation(calibration) -> None:  # type: ignore[no-untyped-def]
    """Mirror of the above, stated as the rejected alternative so the
    intent survives someone 'fixing' it to max(). Worst-in-window is not
    reproducible: a newer, better observation would leave the score
    unchanged, so the score would depend on history rather than state."""
    worst_first = score_urgency(
        make_context(
            observations=[
                make_observation("2026-08-14T09:00:00", rr=30),
                make_observation("2026-08-16T09:16:00"),
            ]
        ),
        calibration,
    )
    assert worst_first.news2 != news2_total(make_observation(rr=30))


def test_single_observation_is_the_most_recent_observation(calibration) -> None:  # type: ignore[no-untyped-def]
    """The ordinary case in this dataset: the generator writes exactly one
    observation per referral (generate.py:460)."""
    result = score_urgency(make_context(observations=[make_observation(rr=22)]), calibration)
    assert result.news2 == 2


# --------------------------------------------------------------------------- #
# ADR-007: paediatric refusal
# --------------------------------------------------------------------------- #


def test_paediatric_specialty_is_refused(calibration) -> None:  # type: ignore[no-untyped-def]
    """NEWS2 is validated for adults only; specialty 0601's patients are
    aged 2-14 (generate.py:405). An adult-scaled score for a child is in
    range, ordinally plausible, and clinically meaningless -- so nothing is
    written at all."""
    with pytest.raises(InsufficientUrgencyEvidenceError, match="paediatric"):
        score_urgency(make_context(specialty_hipe="0601"), calibration)


def test_paediatric_refusal_happens_before_scoring(calibration) -> None:  # type: ignore[no-untyped-def]
    """Refusal is on specialty, not on the observation. A paediatric referral
    with perfectly scorable vitals must still be refused -- otherwise the
    refusal silently depends on data quality rather than on ADR-007."""
    with pytest.raises(InsufficientUrgencyEvidenceError, match="paediatric"):
        score_urgency(
            make_context(specialty_hipe="0601", observations=[make_observation(rr=22)]),
            calibration,
        )


@pytest.mark.parametrize("specialty", ["2600", "0100", "0300", "1800", "0700", "0600"])
def test_non_paediatric_specialties_are_scored(specialty: str, calibration) -> None:  # type: ignore[no-untyped-def]
    """0600 and 0601 differ by one character and 0600 is NOT paediatric.
    A prefix match instead of an equality check would wrongly refuse it."""
    result = score_urgency(make_context(specialty_hipe=specialty), calibration)
    assert result.score == 0.0


# --------------------------------------------------------------------------- #
# Refusal when there is nothing to cite (NFR5)
# --------------------------------------------------------------------------- #


def test_no_observations_is_refused(calibration) -> None:  # type: ignore[no-untyped-def]
    """NFR5: no score without cited evidence. ScoreIn.citations requires at
    least one entry anyway, so writing here would 422."""
    with pytest.raises(InsufficientUrgencyEvidenceError, match="observation"):
        score_urgency(make_context(observations=[]), calibration)


def test_refusal_is_not_a_zero_score(calibration) -> None:  # type: ignore[no-untyped-def]
    """The distinction the coordinator depends on: ADR-008 of
    coordinating-agent_20260906 excludes and reports a referral with no
    urgency score, explicitly refusing to default it to zero, because a
    missing score is missing information, not low urgency. That only works
    if we raise instead of returning 0.0."""
    with pytest.raises(InsufficientUrgencyEvidenceError):
        score_urgency(make_context(observations=[]), calibration)


# --------------------------------------------------------------------------- #
# Citations
# --------------------------------------------------------------------------- #


def test_cites_every_vital_the_score_used(calibration) -> None:  # type: ignore[no-untyped-def]
    """All six, including the ones that scored 0. The score is a function of
    all six, so citing only the non-zero ones would leave a reader unable to
    reconstruct it -- and a normal vital is evidence of normality, not an
    absence of evidence."""
    result = score_urgency(make_context(), calibration)
    cited_columns = {c.evidence_key.rsplit("/", 1)[-1] for c in result.citations}
    assert cited_columns == set(NEWS2_VITALS)


def test_citations_are_all_observation_type(calibration) -> None:  # type: ignore[no-untyped-def]
    """`bed_status`/`clinic_session` belong to the capacity agent;
    `score`/`referral_state`/`rule` are decision_citations-only and are
    rejected outright by agent_citations' CHECK constraint
    (retrieval/app/iri.py:37-39)."""
    result = score_urgency(make_context(), calibration)
    assert {c.evidence_type for c in result.citations} == {"observation"}


def test_evidence_key_uses_space_separated_percent_encoded_timestamp(calibration) -> None:  # type: ignore[no-untyped-def]
    """The trap the capacity agent documented in `_bed_status_evidence_key`.
    The JSON carries ISO 'T' form; the graph node Morph-KGC built from
    Postgres is space-separated, then percent-encoded. An evidence_key built
    from the unconverted ISO form points at a node that was never loaded and
    fails SILENTLY -- degrading to `type: null` when a reader resolves it,
    never raising.
    """
    result = score_urgency(
        make_context(observations=[make_observation("2026-08-16T09:16:00")]), calibration
    )
    hr_citation = next(c for c in result.citations if c.evidence_key.endswith("/hr"))
    assert hr_citation == Citation(
        evidence_type="observation",
        evidence_key="9004/PW-9004-000286/2026-08-16%2009%3A16%3A00/hr",
    )
    assert "T09" not in hr_citation.evidence_key


def test_citations_reference_the_scored_observation_not_an_earlier_one(calibration) -> None:  # type: ignore[no-untyped-def]
    """ADR-005 chose the newest observation; the citations must point at that
    same one. Citing the wrong timestamp would produce an audit trail that
    reconstructs to a different number than the one written."""
    result = score_urgency(
        make_context(
            observations=[
                make_observation("2026-08-14T09:00:00", rr=30),
                make_observation("2026-08-16T09:16:00"),
            ]
        ),
        calibration,
    )
    assert all("2026-08-16" in c.evidence_key for c in result.citations)


def test_result_carries_the_calibrated_method(calibration) -> None:  # type: ignore[no-untyped-def]
    """ADR-004: `method` names the single scored component, so a v1 score can
    never be mistaken for one written under a later multi-component
    calibration."""
    result = score_urgency(make_context(), calibration)
    assert result.method == calibration.method
    assert "news2" in result.method


# --------------------------------------------------------------------------- #
# Determinism
# --------------------------------------------------------------------------- #


def test_scoring_is_deterministic(calibration) -> None:  # type: ignore[no-untyped-def]
    """Reproducibility is a compliance property here, not a convenience
    (tech-stack.md's Agent Reasoning Model). Same input, same output, every
    time -- no clock, no RNG, no dict-ordering dependence."""
    context = make_context(observations=[make_observation(rr=22, spo2=93, hr=115)])
    first = score_urgency(context, calibration)
    second = score_urgency(context, calibration)
    assert first == second


def test_no_mts_anywhere_in_the_result(calibration) -> None:  # type: ignore[no-untyped-def]
    """ADR-004: MTS is deferred. `mts_category` is a random draw conditioned
    on CPC (generate.py:538), so scoring it would double-count the band the
    coordinator already orders by. Present in the input, absent from the
    output."""
    context = make_context(
        observations=[make_observation(**{"mts_category": "red", "icts_category": ""})]
    )
    result = score_urgency(context, calibration)
    assert result.score == 0.0
    assert "mts" not in result.method.lower()


# --------------------------------------------------------------------------- #
# Real captured data -- Step 7. Skips until the fixture exists.
# --------------------------------------------------------------------------- #


def _load_fixture(name: str) -> Any:
    path = FIXTURES / name
    if not path.exists():
        pytest.skip(f"{name} not captured yet -- see tests/fixtures/README.md")
    return json.loads(path.read_text())


def test_real_fixture_news2_matches_the_generators_own_value() -> None:
    """THE ORACLE. `core.observations.news2` was computed by the dataset
    generator from these same vitals (generate.py:63). Recomputing must
    reproduce it exactly, on every observation in a real captured response.

    This is the test that would have caught the coordinator's str/int defect
    class: its hand-built fixtures made the same wrong assumption as its
    implementation, so they agreed with each other and not with reality.
    A test written from the same assumption as the code verifies internal
    consistency, not truth.
    """
    context = _load_fixture("context_adult.json")
    observations = context["observations"]
    assert observations, "fixture has no observations -- recapture against a referral that has some"
    for obs in observations:
        assert news2_total(obs) == obs["news2"], (
            f"recomputed NEWS2 disagrees with the stored value at {obs['obs_datetime']}: "
            f"{news2_total(obs)} != {obs['news2']}"
        )


def test_real_fixture_scores_end_to_end(calibration) -> None:  # type: ignore[no-untyped-def]
    """A real response, through the whole scorer, with real citations."""
    context = _load_fixture("context_adult.json")
    result = score_urgency(context, calibration)
    assert 0.0 <= result.score <= 1.0
    assert len(result.citations) == len(NEWS2_VITALS)


def test_real_paediatric_fixture_is_refused(calibration) -> None:  # type: ignore[no-untyped-def]
    """ADR-007 against a real 0601 referral rather than a hand-built one."""
    context = _load_fixture("context_paediatric.json")
    assert context["referral"]["specialty_hipe"] == "0601"
    with pytest.raises(InsufficientUrgencyEvidenceError, match="paediatric"):
        score_urgency(context, calibration)
