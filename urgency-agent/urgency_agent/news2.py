"""The NEWS2 rubric itself -- scale 1, breathing air.

Kept as its own module because both `calibration.py` and `scoring.py` depend
on it and neither depends on the other: `UrgencyCalibration` validates its
breakpoints against `NEWS2_MAX`, and `score_urgency` scores against the
component thresholds. Folding this into `scoring.py` would make
scoring -> calibration -> scoring a circular import.

Every threshold below is the published NEWS2 rubric. They are deliberately
*not* imported from `dataset/generator/generate.py`, which carries its own
copy: `tests/test_scoring.py` uses the generator's stored `news2` column as an
independent oracle, and an oracle derived from the same source as the
implementation only proves the two agree with each other.

Two properties of the rubric that the code depends on:

- **Temperature's top band is 2, every other component's is 3.** So the
  reachable maximum is 3+3+3+3+3+2 = 17, not 18 and not the 20 the generator
  caps at (`min(s, 20)`, generate.py:73). That cap can never bind, which is
  why recomputation and the stored column agree exactly.
- **Systolic BP is not a descending ladder.** >= 220 scores 3, the same as
  <= 90. A scorer written as a single downward staircase gets the hypertensive
  tail wrong and no mid-range test notices.

No scale 2, and no +2 for supplemental oxygen: `core.observations` carries no
oxygen-therapy field, so neither is reachable from this data.
"""

from __future__ import annotations

from typing import Any

from .models import Observation

# The six vitals NEWS2 actually scores. `dbp` and `pain` are present in
# core.observations and are NOT NEWS2 inputs -- scoring them would invent a
# seventh component. This tuple is also the citation set: the score is a
# function of all six, so all six are cited, including the ones scoring 0.
NEWS2_VITALS: tuple[str, ...] = ("rr", "spo2", "sbp", "hr", "avpu", "temp")

# The reachable maximum, not the generator's cap. ADR-006's top breakpoint
# anchors here; anchoring at 20 would leave the top of the [0,1] range dead,
# because no real observation could ever reach it.
NEWS2_MAX: int = 17


def _respiratory_rate_score(rr: int) -> int:
    if rr <= 8:
        return 3
    if rr <= 11:
        return 1
    if rr <= 20:
        return 0
    if rr <= 24:
        return 2
    return 3


def _oxygen_saturation_score(spo2: int) -> int:
    if spo2 <= 91:
        return 3
    if spo2 <= 93:
        return 2
    if spo2 <= 95:
        return 1
    return 0


def _systolic_blood_pressure_score(sbp: int) -> int:
    if sbp <= 90:
        return 3
    if sbp <= 100:
        return 2
    if sbp <= 110:
        return 1
    if sbp <= 219:
        return 0
    # Not a ladder: the hypertensive tail returns to 3.
    return 3


def _heart_rate_score(hr: int) -> int:
    if hr <= 40:
        return 3
    if hr <= 50:
        return 1
    if hr <= 90:
        return 0
    if hr <= 110:
        return 1
    if hr <= 130:
        return 2
    return 3


def _consciousness_score(avpu: str) -> int:
    # Binary by construction: alert scores 0, V/P/U all score 3. NEWS2 has no
    # intermediate value here.
    return 0 if avpu == "A" else 3


def _temperature_score(temp: float) -> int:
    if temp <= 35.0:
        return 3
    if temp <= 36.0:
        return 1
    if temp <= 38.0:
        return 0
    if temp <= 39.0:
        return 1
    # Ceiling of 2 -- the one component that never reaches 3.
    return 2


def _as_observation(observation: Observation | dict[str, Any]) -> Observation:
    if isinstance(observation, dict):
        return Observation.model_validate(observation)
    return observation


def news2_components(observation: Observation | dict[str, Any]) -> dict[str, int]:
    """Each vital's own NEWS2 sub-score, keyed by its `core.observations`
    column name. Returned per-component rather than pre-summed so the
    boundary tests can pin one vital at a time, and so a rationale can later
    name which vital drove a score."""
    obs = _as_observation(observation)
    return {
        "rr": _respiratory_rate_score(obs.rr),
        "spo2": _oxygen_saturation_score(obs.spo2),
        "sbp": _systolic_blood_pressure_score(obs.sbp),
        "hr": _heart_rate_score(obs.hr),
        "avpu": _consciousness_score(obs.avpu),
        "temp": _temperature_score(obs.temp),
    }


def news2_total(observation: Observation | dict[str, Any]) -> int:
    """Aggregate NEWS2, 0..NEWS2_MAX.

    Deliberately uncapped: the components cannot sum above 17, so the
    generator's own `min(s, 20)` is unreachable and reproducing it here would
    be dead code hiding the fact that 20 is not a real ceiling.
    """
    return sum(news2_components(observation).values())
