"""Deterministic capacity scoring (spec.md FR2): constraint reasoning over a
referral's specialty capacity (ward bed-status pressure + clinic-session
booking pressure), read from GET /referrals/.../context's response --
ADR-002 means this agent never queries SPARQL or Postgres directly.

**Score polarity (a documented design decision -- not specified by
proposal/spec.md, recorded in this track's decisions.md):** `capacity_score`
is a resource-PRESSURE score, the same polarity as the urgency agent's score:
`0.0` = ample capacity, no constraint pressure; `1.0` = severe constraint
pressure. This keeps both scores' polarity aligned for the coordinator, which
combines them (tech-stack.md's Agent Reasoning Model) -- a higher number
always means "more reason to prioritise," never the opposite for one agent
and not the other.

Two independently-weighted pressure signals (capacity_agent/calibration.yml):

- **ward_pressure** -- the specialty's primary ward's latest `BedStatus`:
  a continuous occupancy component plus a boolean escalation component over
  the trolley/surge fields graph-foundation_20260826 found actually carry
  overcrowding (`bs_occupancy_range` caps `occupancy_pct` at 100 by
  construction, so ">100% occupancy" can never be the signal).
- **clinic_pressure** -- the specialty's most recent `ClinicSession`'s
  booked/total ratio (a clinic with zero sessions scheduled is treated as
  maximal pressure, not a 0/0 crash).

The two combine by calibrated weight, renormalised over whichever signal is
actually available (a specialty with no ward, or no clinic sessions, still
scores off the one it has). If neither is available, scoring is refused
(`InsufficientCapacityEvidenceError`) rather than writing an evidence-free
score -- NFR5 forbids a score without cited evidence, and `ScoreIn.citations`
requires at least one anyway.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal
from urllib.parse import quote

from .calibration import CapacityCalibration
from .models import BedStatus, ClinicSession, ReferralContext

EvidenceType = Literal["bed_status", "clinic_session"]


class InsufficientCapacityEvidenceError(RuntimeError):
    """Raised when a referral's specialty has neither a ward bed-status
    snapshot nor a clinic session to cite -- there is nothing to write a
    score against (NFR5, ScoreIn.citations' 1..n minimum)."""


@dataclass(frozen=True)
class Citation:
    evidence_type: EvidenceType
    evidence_key: str


@dataclass(frozen=True)
class CapacityScoreResult:
    score: float
    method: str
    citations: list[Citation] = field(default_factory=list)
    ward_pressure: float | None = None
    clinic_pressure: float | None = None


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def ward_pressure(bed_status: BedStatus | dict, calibration: CapacityCalibration) -> float:
    if isinstance(bed_status, dict):
        bed_status = BedStatus.model_validate(bed_status)
    occupancy_component = _clamp01(bed_status.occupancy_pct / 100)
    # Boolean, not magnitude: a flag either fired or didn't (graph-foundation
    # _20260826's own finding -- one outlier patient and ten both count as
    # "the flag fired," never scaled further).
    escalation_component = _clamp01(
        sum(
            weight
            for flag, weight in calibration.escalation_triggers.items()
            if getattr(bed_status, flag) > 0
        )
    )
    return _clamp01(
        calibration.occupancy_weight * occupancy_component
        + calibration.escalation_weight * escalation_component
    )


def clinic_pressure(session: ClinicSession | dict) -> float:
    if isinstance(session, dict):
        session = ClinicSession.model_validate(session)
    if session.slots_total == 0:
        return 1.0
    return _clamp01(session.slots_booked / session.slots_total)


def _bed_status_evidence_key(hospital_hipe: str, ward_id: str, snapshot_datetime: str) -> str:
    """namespaces.md #4: `bed-status/{hospital_hipe}/{ward_id}/{snapshot_datetime}`.

    `snapshot_datetime` here is the ISO 'T'-separated string the retrieval
    service's JSON response carries; the real graph node was built by
    Morph-KGC directly from Postgres, whose driver stringifies a `timestamp`
    column space-separated ('2026-08-16 09:16:00'), then percent-encodes it
    per retrieval/app/schemas.py's own documented evidence_key convention.
    Using the ISO form unconverted would build an evidence_key pointing at a
    graph node that was never loaded -- silently degrading to `type: null`
    when a reader resolves it (retrieval's `_resolve_iri`), not an error.
    """
    reformatted = datetime.fromisoformat(snapshot_datetime).strftime("%Y-%m-%d %H:%M:%S")
    return f"{hospital_hipe}/{quote(ward_id, safe='')}/{quote(reformatted, safe='')}"


def _clinic_session_evidence_key(hospital_hipe: str, clinic_code: str, session_date: str) -> str:
    """namespaces.md #4: `clinic-session/{hospital_hipe}/{clinic_code}/{session_date}`.
    `session_date` is a bare date ('YYYY-MM-DD') -- already IRI-safe, no
    percent-encoding needed."""
    return f"{hospital_hipe}/{quote(clinic_code, safe='')}/{session_date}"


def score_capacity(
    context: ReferralContext | dict, calibration: CapacityCalibration
) -> CapacityScoreResult:
    if isinstance(context, dict):
        context = ReferralContext.model_validate(context)

    hospital_hipe = context.referral.hospital_hipe
    primary_ward = context.capacity.wards[0] if context.capacity.wards else None
    bed_status = primary_ward.latest_bed_status if primary_ward else None
    session = context.capacity.clinic_sessions[0] if context.capacity.clinic_sessions else None

    if bed_status is None and session is None:
        raise InsufficientCapacityEvidenceError(
            f"no bed-status or clinic-session evidence for specialty "
            f"{context.capacity.specialty_hipe!r} at hospital {hospital_hipe!r} -- "
            "cannot write a score with no citable evidence (NFR5)"
        )

    citations: list[Citation] = []
    weighted_sum = 0.0
    weight_total = 0.0
    ward_p: float | None = None
    clinic_p: float | None = None

    if bed_status is not None:
        assert primary_ward is not None
        ward_p = ward_pressure(bed_status, calibration)
        weighted_sum += calibration.ward_weight * ward_p
        weight_total += calibration.ward_weight
        citations.append(
            Citation(
                "bed_status",
                _bed_status_evidence_key(
                    hospital_hipe, primary_ward.ward_id, bed_status.snapshot_datetime
                ),
            )
        )

    if session is not None:
        clinic_p = clinic_pressure(session)
        weighted_sum += calibration.clinic_weight * clinic_p
        weight_total += calibration.clinic_weight
        citations.append(
            Citation(
                "clinic_session",
                _clinic_session_evidence_key(
                    hospital_hipe, session.clinic_code, session.session_date
                ),
            )
        )

    score = _clamp01(weighted_sum / weight_total)

    return CapacityScoreResult(
        score=score,
        method=calibration.method,
        citations=citations,
        ward_pressure=ward_p,
        clinic_pressure=clinic_p,
    )
