"""Deterministic urgency scoring (spec.md FR1): NEWS2 over one referral's most
recent observation, read from `GET /referrals/.../context` -- ADR-002 means
this agent never queries SPARQL or Postgres directly.

**Score polarity:** `urgency_score` is a clinical-urgency score -- `0.0` = no
physiological derangement, `1.0` = maximum. The same polarity as the capacity
agent's pressure score (ADR-003), so a higher number always means more reason
to prioritise, for either agent.

The rubric itself lives in `news2.py`; this module is the decisions built on
top of it:

- **ADR-004** -- NEWS2 is the only scored component in v1. `mts_category` is
  read into the model but never scored: it is a random draw conditioned on the
  referral's CPC band (generate.py:538), so scoring it would double-count the
  band the coordinator already orders by.
- **ADR-005** -- the most recent observation is scored, not the worst in
  window. Worst-in-window is not reproducible: a newer, better observation
  would leave the score unchanged, making it depend on history rather than on
  state, and reproducibility is a compliance property here.
- **ADR-006** -- NEWS2 maps to [0,1] by linear interpolation between the
  calibrated escalation breakpoints, never by a flat divide.
- **ADR-007** -- paediatric referrals (specialty 0601) are refused, never
  scored. NEWS2 is validated for adults; an adult-scaled score for a
  2-14-year-old is in range, ordinally plausible, and clinically meaningless.

Both refusals raise rather than returning a low score. That distinction is
load-bearing downstream: `coordinating-agent_20260906`'s ADR-008 excludes a
referral with no urgency score and reports it, explicitly refusing to default
it to zero, because a missing score is missing information, not low urgency.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal
from urllib.parse import quote

from .calibration import UrgencyCalibration
from .models import Observation, ReferralContext
from .news2 import NEWS2_MAX, NEWS2_VITALS, news2_components, news2_total

__all__ = [
    "NEWS2_MAX",
    "NEWS2_VITALS",
    "Citation",
    "EvidenceType",
    "InsufficientUrgencyEvidenceError",
    "UrgencyScoreResult",
    "news2_components",
    "news2_total",
    "normalise_news2",
    "score_urgency",
]

# The urgency agent cites clinical evidence only. `bed_status`/`clinic_session`
# belong to the capacity agent; `score`/`referral_state`/`rule` are
# decision_citations-only and are rejected outright by agent_citations' own
# CHECK constraint (retrieval/app/iri.py:37-39).
EvidenceType = Literal["observation"]

# ADR-007. Specialty 0601 is paediatric (generate.py:50); its patients are
# generated at ages 2-14 (generate.py:405). Matched by equality, never by
# prefix -- 0600 differs by one character and is NOT paediatric.
PAEDIATRIC_SPECIALTY = "0601"


class InsufficientUrgencyEvidenceError(RuntimeError):
    """Raised when no urgency score can honestly be written for a referral --
    either there is no observation to cite (NFR5, `ScoreIn.citations`'
    1..n minimum) or the referral is paediatric and NEWS2 does not apply
    (ADR-007). Nothing is written in either case."""


@dataclass(frozen=True)
class Citation:
    evidence_type: EvidenceType
    evidence_key: str


@dataclass(frozen=True)
class UrgencyScoreResult:
    score: float
    method: str
    citations: list[Citation] = field(default_factory=list)
    news2: int = 0


def normalise_news2(total: int, calibration: UrgencyCalibration) -> float:
    """Map a raw NEWS2 onto [0,1] by linear interpolation between the
    calibrated breakpoints (ADR-006).

    The endpoints return their breakpoint's score exactly rather than by
    interpolation, so `normalise_news2(0)` is exactly 0.0 and
    `normalise_news2(NEWS2_MAX)` is exactly 1.0 with no floating-point drift
    at the anchors -- `ScoreIn.score` is `ge=0, le=1`, and a 1.0000000000000002
    is a 422 from the retrieval service, not a rounding curiosity.
    """
    points = calibration.breakpoints

    if total <= points[0].news2:
        return points[0].score
    if total >= points[-1].news2:
        return points[-1].score

    for lower, upper in zip(points, points[1:], strict=False):
        if total <= upper.news2:
            fraction = (total - lower.news2) / (upper.news2 - lower.news2)
            return lower.score + fraction * (upper.score - lower.score)

    # Unreachable: the guards above cover everything outside the breakpoint
    # range, and the loop covers everything inside it.
    return points[-1].score


def _observation_evidence_key(
    hospital_hipe: str, pathway_number: str, obs_datetime: str, column: str
) -> str:
    """namespaces.md #4: `obs/{hospital_hipe}/{pathway_number}/{obs_datetime}/{column}`.

    Note the timestamp conversion, which is the trap the capacity agent
    documented in its own `_bed_status_evidence_key`. The retrieval service's
    JSON carries an ISO 'T'-separated datetime; the graph node Morph-KGC built
    was created from Postgres, whose driver stringifies a `timestamp` column
    space-separated ('2026-08-16 09:16:00'). An evidence_key built from the
    unconverted ISO form points at a node that was never loaded and fails
    SILENTLY -- degrading to `type: null` when a reader resolves it
    (retrieval's `_resolve_iri`), never raising.

    Keys are per-column, not per-row, so one observation yields one citation
    per vital scored.
    """
    reformatted = datetime.fromisoformat(obs_datetime).strftime("%Y-%m-%d %H:%M:%S")
    return (
        f"{hospital_hipe}/{quote(pathway_number, safe='')}/{quote(reformatted, safe='')}/{column}"
    )


def _citations_for(
    hospital_hipe: str, pathway_number: str, observation: Observation
) -> list[Citation]:
    """One citation per NEWS2 vital, including vitals that scored 0.

    The score is a function of all six, so citing only the abnormal ones would
    leave a reader unable to reconstruct it -- and a normal vital is evidence
    of normality, not an absence of evidence.
    """
    return [
        Citation(
            evidence_type="observation",
            evidence_key=_observation_evidence_key(
                hospital_hipe, pathway_number, observation.obs_datetime, column
            ),
        )
        for column in NEWS2_VITALS
    ]


def score_urgency(
    context: ReferralContext | dict[str, Any], calibration: UrgencyCalibration
) -> UrgencyScoreResult:
    """Score one referral's clinical urgency from its most recent observation."""
    if isinstance(context, dict):
        context = ReferralContext.model_validate(context)

    referral = context.referral

    # Checked before the observation, and before any scoring: the refusal is a
    # property of the specialty, not of the data. A paediatric referral with
    # perfectly scorable vitals must still be refused, or the refusal would
    # silently depend on data quality rather than on ADR-007.
    if referral.specialty_hipe == PAEDIATRIC_SPECIALTY:
        raise InsufficientUrgencyEvidenceError(
            f"referral {referral.hospital_hipe}/{referral.pathway_number} is paediatric "
            f"(specialty {PAEDIATRIC_SPECIALTY}); NEWS2 is validated for adults only, so "
            "no urgency score is written (ADR-007)"
        )

    if not context.observations:
        raise InsufficientUrgencyEvidenceError(
            f"referral {referral.hospital_hipe}/{referral.pathway_number} has no "
            "observation to score or cite -- refusing to write a score with no "
            "citable evidence (NFR5)"
        )

    # ADR-005: the endpoint orders observations ascending by obs_datetime, so
    # the last element is the most recent.
    observation = context.observations[-1]
    total = news2_total(observation)

    return UrgencyScoreResult(
        score=normalise_news2(total, calibration),
        method=calibration.method,
        citations=_citations_for(referral.hospital_hipe, referral.pathway_number, observation),
        news2=total,
    )
