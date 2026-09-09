"""In-memory run and decision store.

Deliberately not read back from GET /decisions: a second POST for the same
(hospital, as_of_date) APPENDS rather than replaces, and GET /runs/{unknown}/...
returns 200 with an empty object, so a stale run_id is indistinguishable from a
run that has just started. The orchestrator holds what it built and serves the
UI from that.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Literal

RunStatus = Literal["queued", "scoring_urgency", "scoring_capacity", "ranking", "done", "failed"]

# Two agents over the cohort. The denominator the progress bar counts towards.
AGENTS_PER_REFERRAL = 2


@dataclass
class Run:
    run_id: str
    hospital_hipe: str
    as_of_date: str
    status: RunStatus = "queued"
    cohort_size: int = 0
    scored: int = 0
    urgency_scored: int = 0
    capacity_scored: int = 0
    refused_paediatric: int = 0
    skipped: int = 0
    ranked: int = 0
    excluded: int = 0
    alpha: float | None = None
    scarcity: float | None = None
    decision_id: str | None = None
    error: str | None = None
    started_at: str | None = None
    finished_at: str | None = None

    @property
    def total(self) -> int:
        """616 for a 308-referral cohort: every referral is scored twice."""
        return self.cohort_size * AGENTS_PER_REFERRAL

    def as_dict(self) -> dict[str, Any]:
        d = {k: v for k, v in self.__dict__.items()}
        d["total"] = self.total
        return d


class Store:
    """Thread-safe. A run executes on a worker thread while polls read from it."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._runs: dict[str, Run] = {}
        # keyed on (hospital_hipe, as_of_date) -- as_of_date is part of the key,
        # never hospital alone, or the date filters nothing.
        self._decisions: dict[tuple[str, str], dict[str, Any]] = {}
        self._latest_run: dict[tuple[str, str], str] = {}

    def create_run(self, run: Run) -> None:
        with self._lock:
            self._runs[run.run_id] = run
            self._latest_run[(run.hospital_hipe, run.as_of_date)] = run.run_id

    def update(self, run_id: str, **fields: Any) -> None:
        with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                return
            for k, v in fields.items():
                setattr(run, k, v)

    def get_run(self, run_id: str) -> Run | None:
        with self._lock:
            return self._runs.get(run_id)

    def put_decision(self, hospital_hipe: str, as_of_date: str, decision: dict[str, Any]) -> None:
        with self._lock:
            self._decisions[(hospital_hipe, as_of_date)] = decision

    def get_decision(self, hospital_hipe: str, as_of_date: str) -> dict[str, Any] | None:
        with self._lock:
            return self._decisions.get((hospital_hipe, as_of_date))

    def latest_run_id(self, hospital_hipe: str, as_of_date: str) -> str | None:
        with self._lock:
            return self._latest_run.get((hospital_hipe, as_of_date))


store = Store()
