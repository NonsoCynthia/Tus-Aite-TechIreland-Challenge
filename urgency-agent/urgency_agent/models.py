"""Typed views over `GET /referrals/{hospital_hipe}/{pathway_number}/context`
(retrieval-service_20260904 FR9) -- only the clinical half.

The mirror of `capacity_agent/models.py`, which models the `capacity` section
and says in its own docstring that `observations`/`conditions`/`triage_events`
"are the urgency agent's concern and are not modelled here". This is that
half. Extra fields on the real response are ignored (Pydantic v2's default),
so the model stays valid as that endpoint grows fields this agent doesn't read.
"""

from __future__ import annotations

from pydantic import BaseModel


class Observation(BaseModel):
    """One row of `core.observations` (`eat:Observation`).

    Only the six NEWS2 vitals are required. `dbp` and `pain` are real columns
    that NEWS2 does not score; `news2`, `mts_category` and `icts_category` are
    the generator's own derived values, optional because this agent must not
    depend on them:

    - **`news2`** is the oracle `tests/test_scoring.py` checks recomputation
      against. Reading it instead of recomputing would make the agent a
      passthrough for a value it is supposed to derive, and would leave
      nothing to cite but a number someone else computed.
    - **`mts_category`** is deliberately unused (ADR-004). It is a random draw
      conditioned on the referral's CPC band (generate.py:538), so scoring it
      would double-count the band the coordinator already orders by. It is
      modelled here only so a real response validates.
    - **`icts_category`** carries the colour instead of `mts_category` on
      paediatric referrals, which are refused outright (ADR-007).
    """

    obs_datetime: str
    rr: int
    spo2: int
    sbp: int
    hr: int
    avpu: str
    temp: float

    dbp: int | None = None
    pain: int | None = None
    chiefcomplaint: str | None = None
    news2: int | None = None
    mts_category: str | None = None
    icts_category: str | None = None


class ReferralSummary(BaseModel):
    """`referral` in the context response. `specialty_hipe` is the only
    paediatric signal available -- the endpoint returns no patient
    demographics (retrieval/app/db.py:330-331), so ADR-007's refusal keys on
    the specialty code, not on age."""

    hospital_hipe: str
    pathway_number: str
    specialty_hipe: str


class ReferralContext(BaseModel):
    """The subset of the context response the urgency agent reads.

    `observations` arrives `ORDER BY obs_datetime` ascending
    (retrieval/app/db.py:342-351), so the last element is the most recent --
    the one ADR-005 scores.
    """

    referral: ReferralSummary
    observations: list[Observation]
