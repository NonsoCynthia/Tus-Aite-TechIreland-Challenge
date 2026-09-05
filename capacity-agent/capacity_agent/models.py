"""Typed views over GET /referrals/{hospital_hipe}/{pathway_number}/context's
response (retrieval-service_20260904, spec.md FR9) -- only the `capacity`
section and the identifiers the capacity agent needs; `observations`/
`conditions`/`triage_events` are the urgency agent's concern and are not
modelled here. Extra fields on the real response are ignored (Pydantic v2's
default), so this stays valid if that endpoint grows fields this agent
doesn't use.
"""

from __future__ import annotations

from pydantic import BaseModel


class BedStatus(BaseModel):
    """One ward's latest snapshot (`core.bed_status`, `eat:BedStatus`).
    Overcrowding is carried by the trolley/surge fields below, never by
    `occupancy_pct` alone -- `bs_occupancy_range` caps it at 100 by
    construction, so ">100% occupancy" is unsatisfiable
    (graph-foundation_20260826's own finding)."""

    snapshot_datetime: str
    occupied: int
    free: int
    occupancy_pct: float
    outliers: int
    surge_capacity_in_use: int
    delayed_transfers_of_care: int
    awaiting_admission_over_9h: int
    awaiting_admission_over_24h: int
    gar_status: str


class Ward(BaseModel):
    """One ward serving the referral's specialty. The retrieval service
    orders `capacity.wards` primary-first (`ORDER BY is_primary DESC,
    ward_id`), so index 0 is always the specialty's primary ward when one
    exists."""

    ward_id: str
    is_primary: bool
    nominal_beds: int
    latest_bed_status: BedStatus | None


class ClinicSession(BaseModel):
    """One outpatient clinic session for the referral's specialty. The
    retrieval service orders `capacity.clinic_sessions` most-recent-first
    (`ORDER BY session_date DESC LIMIT 5`), so index 0 is the latest."""

    clinic_code: str
    session_date: str
    clinic_name: str
    slots_total: int
    slots_booked: int
    slots_available: int


class CapacitySection(BaseModel):
    specialty_hipe: str
    wards: list[Ward]
    clinic_sessions: list[ClinicSession]


class ReferralSummary(BaseModel):
    hospital_hipe: str
    pathway_number: str
    specialty_hipe: str


class ReferralContext(BaseModel):
    """The subset of `GET /referrals/{hospital_hipe}/{pathway_number}/context`
    the capacity agent reads."""

    referral: ReferralSummary
    capacity: CapacitySection
