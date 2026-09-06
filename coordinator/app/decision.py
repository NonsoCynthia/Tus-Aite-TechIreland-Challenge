"""Citation construction, decision assembly and write-back response handling.

Per ADR-009 (`conductor/tracks/coordinating-agent_20260906/decisions.md`),
the coordinator's real evidence for the `urgency`/`timeframe` citation
roles (a `Score` node and a `ReferralState`) is not yet an accepted
`EvidenceType` in `retrieval.app.schemas` -- a change request is open. This
module builds against the intended enum by default, and offers a
`legacy_citations` fallback that validates against today's `EvidenceType`.

Per spec.md FR8, `rationale_summary` is the coordinator's own short,
deterministic note -- never LLM output -- following `conductor/product-
guidelines.md`'s verb rules (the system ranks and explains; it never
admits, schedules, or acts).

Per spec.md FR9, `coordinator_version` and the `POST /decisions` response
handling make every decision traceable to the assumptions it was written
under, and make a `207` (partial success) impossible to mistake for a `200`.
"""

from enum import Enum
from typing import Any, Final

from coordinator.app.citations import ROLE_EVIDENCE_TYPES
from coordinator.app.priority import CapacityDirection

CPC_BAND_LABELS: Final[dict[int | None, str]] = {
    1: "Urgent",
    3: "Semi-Urgent",
    2: "Routine/Non-Urgent",
    4: "Excluded",
    None: "uncategorised",
}
"""`core.ref_codes`' own descriptions for the NTPF `cpc` codes, keyed by
the raw code (ADR-003). `rationale_summary` must never print a raw `cpc`
value -- 3 (Semi-Urgent) sitting next to 2 (Routine) would read as *less*
urgent to a clinician, exactly the confusion `severity_rank` (not `cpc`)
exists to prevent.
"""


def build_citations(
    referral: dict[str, Any], *, legacy_citations: bool = False
) -> list[dict[str, Any]]:
    """Builds the `DecisionCitationIn`-shaped citations for one referral.

    Default mode emits `urgency` (evidence_type `"score"`) and
    `timeframe` (evidence_type `"referral_state"`) per ADR-009, plus
    `capacity` (a pass-through of the capacity agent's own citations,
    already valid `bed_status`/`clinic_session` evidence). Every
    `evidence_type` is read from `ROLE_EVIDENCE_TYPES`, never hardcoded
    here.

    `legacy_citations=True` instead copies the urgency agent's own
    citations onto the `urgency` role and omits `timeframe` entirely
    (ADR-009's fallback) -- safe because `RankingIn.citations` only
    requires `min_length=1`, not one per role.

    Args:
        referral: A ranked referral dict carrying `run_id`,
            `hospital_hipe`, `pathway_number`, `referral_date`,
            `urgency_citations` and `capacity_citations`.
        legacy_citations: Whether to use the fallback citation set.

    Returns:
        A list of `DecisionCitationIn`-shaped dicts (`evidence_type`,
        `evidence_key`, `role`).
    """
    capacity_citations = [
        {
            "evidence_type": citation["evidence_type"],
            "evidence_key": citation["evidence_key"],
            "role": "capacity",
        }
        for citation in referral["capacity_citations"]
    ]

    if legacy_citations:
        urgency_citations = [
            {
                "evidence_type": citation["evidence_type"],
                "evidence_key": citation["evidence_key"],
                "role": "urgency",
            }
            for citation in referral["urgency_citations"]
        ]
        return [*urgency_citations, *capacity_citations]

    score_evidence_key = (
        f"{referral['run_id']}/{referral['hospital_hipe']}/{referral['pathway_number']}/urgency"
    )
    referral_state_evidence_key = (
        f"{referral['hospital_hipe']}/{referral['pathway_number']}/{referral['referral_date']}"
    )
    urgency_citation = {
        "evidence_type": ROLE_EVIDENCE_TYPES["urgency"],
        "evidence_key": score_evidence_key,
        "role": "urgency",
    }
    timeframe_citation = {
        "evidence_type": ROLE_EVIDENCE_TYPES["timeframe"],
        "evidence_key": referral_state_evidence_key,
        "role": "timeframe",
    }
    return [urgency_citation, timeframe_citation, *capacity_citations]


def build_rationale_summary(referral: dict[str, Any]) -> str:
    """Builds the coordinator's own short, deterministic rationale.

    States only band, breach status, the two scores and the weight in
    force -- nothing beyond what `build_citations` cites for this
    referral. Follows `conductor/product-guidelines.md`'s verb rules: the
    system ranks and explains, it never admits, schedules or acts.

    Args:
        referral: A ranked referral dict carrying `cpc`, `crt_breached`,
            `urgency_score`, `capacity_score` and `alpha`.

    Returns:
        A single deterministic sentence.
    """
    band_label = CPC_BAND_LABELS[referral.get("cpc")]

    crt_breached = referral.get("crt_breached")
    if crt_breached is True:
        breach_clause = "outside the applicable CRT window"
    elif crt_breached is False:
        breach_clause = "within the applicable CRT window"
    else:
        breach_clause = "no CRT window applies to this category"

    return (
        f"Ranked. {band_label} category, {breach_clause}. "
        f"Urgency score {referral['urgency_score']}, capacity score "
        f"{referral['capacity_score']}, urgency weighted at {referral['alpha']} "
        f"for this decision."
    )


def build_coordinator_version(
    *,
    semantic_version: str,
    capacity_direction: CapacityDirection,
    alpha_min: float,
    alpha_max: float,
    score_source: str,
) -> str:
    """Encodes the coordinator's version and every decision-shaping choice.

    Per spec.md FR9, two decisions produced under different assumptions
    must be distinguishable after the fact -- capacity direction, alpha
    bounds and score source all change the ranking, so all four are
    encoded alongside the semantic version.

    Args:
        semantic_version: The coordinator's own semantic version.
        capacity_direction: The capacity sign convention in force
            (ADR-007).
        alpha_min: The alpha lower bound in force.
        alpha_max: The alpha upper bound in force.
        score_source: Which score source produced this decision's scores
            (e.g. `"live"` or `"fixture"`, ADR-008) -- so a decision
            written from stub scores can never be mistaken for a real one.

    Returns:
        One string encoding all five values.
    """
    return (
        f"{semantic_version}+capacity={capacity_direction}"
        f",alpha=[{alpha_min},{alpha_max}]"
        f",scores={score_source}"
    )


def build_ranking(referral: dict[str, Any], *, legacy_citations: bool = False) -> dict[str, Any]:
    """Assembles one `RankingIn`-shaped dict for a ranked referral.

    Args:
        referral: A ranked referral dict, as produced by
            `coordinator.app.ranking.rank_cohort`, plus
            `urgency_citations`/`capacity_citations`.
        legacy_citations: Whether to use the ADR-009 fallback citation set.

    Returns:
        A dict shaped like `retrieval.app.schemas.RankingIn`.
    """
    return {
        "hospital_hipe": referral["hospital_hipe"],
        "pathway_number": referral["pathway_number"],
        "position": referral["position"],
        "triage_category": referral.get("cpc"),
        "urgency_score": referral["urgency_score"],
        "capacity_score": referral["capacity_score"],
        "rationale_summary": build_rationale_summary(referral),
        "citations": build_citations(referral, legacy_citations=legacy_citations),
        "rule_checks": referral.get("rule_checks", []),
    }


def build_decision(
    *,
    decision_id: str,
    run_id: str,
    hospital_hipe: str,
    as_of_date: str,
    coordinator_version: str,
    rankings: list[dict[str, Any]],
) -> dict[str, Any]:
    """Assembles one `DecisionIn`-shaped payload.

    Args:
        decision_id: Caller-assigned unique ID for this decision.
        run_id: The run_id the scores in `rankings` came from.
        hospital_hipe: 4-character HIPE hospital code.
        as_of_date: The day this ranking is for (ISO date string).
        coordinator_version: As built by `build_coordinator_version`.
        rankings: `RankingIn`-shaped dicts, as built by `build_ranking`.

    Returns:
        A dict shaped like `retrieval.app.schemas.DecisionIn`.
    """
    return {
        "decision_id": decision_id,
        "run_id": run_id,
        "hospital_hipe": hospital_hipe,
        "as_of_date": as_of_date,
        "coordinator_version": coordinator_version,
        "rankings": rankings,
    }


class DecisionPostOutcome(Enum):
    """The four documented `POST /decisions` responses (spec.md FR9)."""

    OK = "ok"
    PARTIAL = "partial"
    REJECTED = "rejected"
    INVALID = "invalid"

    @property
    def is_ok(self) -> bool:
        """Whether this outcome is unambiguous success.

        `PARTIAL` (a `207`) is deliberately not `is_ok` -- Postgres
        committed but the graph projection failed, so it must never be
        reported as success (spec.md FR9).
        """
        return self is DecisionPostOutcome.OK


_STATUS_CODE_TO_OUTCOME: dict[int, DecisionPostOutcome] = {
    200: DecisionPostOutcome.OK,
    207: DecisionPostOutcome.PARTIAL,
    400: DecisionPostOutcome.REJECTED,
    422: DecisionPostOutcome.INVALID,
}


def interpret_decision_response(status_code: int) -> DecisionPostOutcome:
    """Maps a `POST /decisions` status code to its documented outcome.

    Args:
        status_code: The HTTP status code `POST /decisions` returned.

    Returns:
        The corresponding `DecisionPostOutcome`.

    Raises:
        ValueError: If `status_code` is not one of the four documented
            responses (200/207/400/422) -- an undocumented response is
            refused rather than silently treated as one of the four.
    """
    try:
        return _STATUS_CODE_TO_OUTCOME[status_code]
    except KeyError:
        raise ValueError(
            f"undocumented POST /decisions status code: {status_code!r}; "
            "expected one of 200, 207, 400, 422"
        ) from None
