"""In-memory run and decision store, with a snapshot behind it.

Deliberately not read back from GET /decisions: a second POST for the same
(hospital, as_of_date) APPENDS rather than replaces, and GET /runs/{unknown}/...
returns 200 with an empty object, so a stale run_id is indistinguishable from a
run that has just started. The orchestrator holds what it built and serves the
UI from that.

The cost of that choice used to be that a container restart silently emptied the
ranked list until someone re-ran -- and took the actual alpha with it, because
`agent.decision_rankings` stores no alpha, scarcity, priority or band, so the
number that produced a stored decision is not recoverable from Postgres or the
graph. Every put_decision now also writes a snapshot, and the store reloads it on
import. The snapshot is a cache of what this process built, never a substitute
for a run.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

logger = logging.getLogger(__name__)

SNAPSHOT = os.environ.get("DECISION_SNAPSHOT", "")

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
        self._restore()

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
            snap = dict(self._decisions)
        self._persist(snap)

    # ------------------------------------------------------------ snapshot

    def _persist(self, decisions: dict[tuple[str, str], dict[str, Any]]) -> None:
        """Write outside the lock, atomically. A half-written snapshot that a
        restart then loads would be worse than no snapshot at all, so it goes to
        a temp file in the same directory and is renamed over the target."""
        if not SNAPSHOT:
            return
        path = Path(SNAPSHOT)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            payload = [{"hospital_hipe": h, "as_of_date": d, "decision": v}
                       for (h, d), v in decisions.items()]
            fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
            with os.fdopen(fd, "w") as fh:
                json.dump(payload, fh)
            os.replace(tmp, path)
        except Exception:                                        # noqa: BLE001
            logger.exception("could not write the decision snapshot")

    def _restore(self) -> None:
        """Best effort, and silent when there is nothing to restore. A corrupt
        or absent snapshot leaves the store empty, which is exactly the state
        the UI already handles: /api/decision 404s and the screens say no agent
        has scored this hospital-day."""
        if not SNAPSHOT or not Path(SNAPSHOT).is_file():
            return
        try:
            for row in json.loads(Path(SNAPSHOT).read_text()):
                d = row["decision"]
                d["_source"] = "snapshot"
                self._decisions[(row["hospital_hipe"], row["as_of_date"])] = d
            logger.info("restored %d decision(s) from %s", len(self._decisions), SNAPSHOT)
        except Exception:                                        # noqa: BLE001
            logger.exception("could not read the decision snapshot; starting empty")

    def get_decision(self, hospital_hipe: str, as_of_date: str) -> dict[str, Any] | None:
        with self._lock:
            return self._decisions.get((hospital_hipe, as_of_date))

    def decisions_held(self) -> list[dict[str, str]]:
        """Which hospital-days currently have a decision, and how it got here --
        a run this process performed, or a snapshot restored on boot."""
        with self._lock:
            return [{"hospital_hipe": h, "as_of_date": d,
                     "run_id": v.get("run_id", ""), "built_at": v.get("built_at", ""),
                     "source": v.get("_source", "run")}
                    for (h, d), v in sorted(self._decisions.items())]

    def latest_run_id(self, hospital_hipe: str, as_of_date: str) -> str | None:
        with self._lock:
            return self._latest_run.get((hospital_hipe, as_of_date))


store = Store()
