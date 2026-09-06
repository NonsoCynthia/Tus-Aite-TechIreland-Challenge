"""run.py orchestration tests (NFR2, Tier 2): score_referral/run_for_cohort
against a small in-memory fake of retrieval-service_20260904's contract
(GET context/cohort, POST /scores), via httpx.MockTransport -- exercises the
same client.py wire format as production without needing a live service.
"""

from __future__ import annotations

import json
from datetime import date

import httpx
import pytest

from capacity_agent.calibration import CapacityCalibration
from capacity_agent.client import RetrievalClient
from capacity_agent.run import run_for_cohort, score_referral
from capacity_agent.scoring import InsufficientCapacityEvidenceError


@pytest.fixture
def calibration() -> CapacityCalibration:
    return CapacityCalibration(
        occupancy_weight=0.6,
        escalation_weight=0.4,
        escalation_triggers={
            "surge_capacity_in_use": 0.4,
            "delayed_transfers_of_care": 0.3,
            "awaiting_admission_over_24h": 0.2,
            "outliers": 0.1,
        },
        ward_weight=0.7,
        clinic_weight=0.3,
        method="capacity-ward-clinic-pressure-v1",
        agent_version="capacity-agent-test",
    )


def _context_for(pathway_number: str, occupancy_pct: float) -> dict:
    return {
        "referral": {
            "hospital_hipe": "9001",
            "pathway_number": pathway_number,
            "specialty_hipe": "0100",
        },
        "observations": [],
        "conditions": [],
        "triage_events": [],
        "capacity": {
            "specialty_hipe": "0100",
            "wards": [
                {
                    "ward_id": "W01",
                    "is_primary": True,
                    "nominal_beds": 20,
                    "latest_bed_status": {
                        "snapshot_datetime": "2026-08-16T09:16:00",
                        "occupied": 18,
                        "free": 2,
                        "occupancy_pct": occupancy_pct,
                        "outliers": 0,
                        "surge_capacity_in_use": 0,
                        "delayed_transfers_of_care": 0,
                        "awaiting_admission_over_9h": 0,
                        "awaiting_admission_over_24h": 0,
                        "gar_status": "A",
                    },
                }
            ],
            "clinic_sessions": [],
        },
    }


class _FakeRetrievalService:
    """In-memory stand-in for enough of retrieval-service_20260904 to drive
    run.py's orchestration: GET context per referral, GET cohort, POST
    /scores recording what was written (so tests can assert on it)."""

    def __init__(
        self,
        contexts: dict[str, dict],
        cohort: list[str],
        graph_failures: set[str] | None = None,
    ) -> None:
        self.contexts = contexts
        self.cohort = cohort
        self.graph_failures = graph_failures or set()
        self.written_scores: list[dict] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/context"):
            pathway_number = path.split("/")[-2]
            context = self.contexts.get(pathway_number)
            if context is None:
                return httpx.Response(404, json={"detail": "no such referral"})
            return httpx.Response(200, json=context)
        if "/cohort/" in path:
            return httpx.Response(
                200, json={"referrals": [{"pathway_number": p} for p in self.cohort]}
            )
        if path == "/scores":
            body = json.loads(request.content)
            self.written_scores.append(body)
            if body["pathway_number"] in self.graph_failures:
                return httpx.Response(
                    207,
                    json={
                        "status": "postgres_committed_graph_projection_failed",
                        "detail": "simulated Oxigraph outage",
                    },
                )
            return httpx.Response(200, json={"status": "ok"})
        raise AssertionError(f"unexpected request: {request.method} {path}")


def test_score_referral_gathers_context_scores_and_posts(calibration: CapacityCalibration) -> None:
    fake = _FakeRetrievalService(
        contexts={"PW-9001-000007": _context_for("PW-9001-000007", occupancy_pct=50.0)},
        cohort=[],
    )
    client = RetrievalClient(
        base_url="http://retrieval.test",
        bearer_token="tok",
        transport=httpx.MockTransport(fake.handler),
    )

    result = score_referral(
        client,
        calibration,
        run_id="run-0001",
        hospital_hipe="9001",
        pathway_number="PW-9001-000007",
        as_of_date=date(2026, 8, 30),
    )

    assert result.score == pytest.approx(0.3)
    assert len(fake.written_scores) == 1
    written = fake.written_scores[0]
    assert written["run_id"] == "run-0001"
    assert written["agent_name"] == "capacity"
    assert written["pathway_number"] == "PW-9001-000007"
    assert written["score"] == pytest.approx(0.3)
    assert written["citations"][0]["evidence_type"] == "bed_status"


def test_run_for_cohort_scores_every_referral_on_the_list(calibration: CapacityCalibration) -> None:
    fake = _FakeRetrievalService(
        contexts={
            "PW-9001-000007": _context_for("PW-9001-000007", occupancy_pct=50.0),
            "PW-9001-000008": _context_for("PW-9001-000008", occupancy_pct=90.0),
        },
        cohort=["PW-9001-000007", "PW-9001-000008"],
    )
    client = RetrievalClient(
        base_url="http://retrieval.test",
        bearer_token="tok",
        transport=httpx.MockTransport(fake.handler),
    )

    result = run_for_cohort(
        client, calibration, run_id="run-0001", hospital_hipe="9001", as_of_date=date(2026, 8, 30)
    )

    assert set(result.scored) == {"PW-9001-000007", "PW-9001-000008"}
    assert len(fake.written_scores) == 2
    assert not result.skipped


def test_run_for_cohort_skips_a_referral_with_no_capacity_evidence_and_continues(
    calibration: CapacityCalibration,
) -> None:
    no_evidence_context = {
        "referral": {
            "hospital_hipe": "9001",
            "pathway_number": "PW-9001-000009",
            "specialty_hipe": "0100",
        },
        "observations": [],
        "conditions": [],
        "triage_events": [],
        "capacity": {"specialty_hipe": "0100", "wards": [], "clinic_sessions": []},
    }
    fake = _FakeRetrievalService(
        contexts={
            "PW-9001-000007": _context_for("PW-9001-000007", occupancy_pct=50.0),
            "PW-9001-000009": no_evidence_context,
        },
        cohort=["PW-9001-000007", "PW-9001-000009"],
    )
    client = RetrievalClient(
        base_url="http://retrieval.test",
        bearer_token="tok",
        transport=httpx.MockTransport(fake.handler),
    )

    result = run_for_cohort(
        client, calibration, run_id="run-0001", hospital_hipe="9001", as_of_date=date(2026, 8, 30)
    )

    assert set(result.scored) == {"PW-9001-000007"}
    assert set(result.skipped) == {"PW-9001-000009"}
    # Only the scoreable referral was ever posted -- the skipped one never
    # reached POST /scores at all.
    assert len(fake.written_scores) == 1


def test_run_for_cohort_records_graph_projection_failures_separately_and_continues(
    calibration: CapacityCalibration,
) -> None:
    fake = _FakeRetrievalService(
        contexts={
            "PW-9001-000007": _context_for("PW-9001-000007", occupancy_pct=50.0),
            "PW-9001-000008": _context_for("PW-9001-000008", occupancy_pct=90.0),
        },
        cohort=["PW-9001-000007", "PW-9001-000008"],
        graph_failures={"PW-9001-000007"},
    )
    client = RetrievalClient(
        base_url="http://retrieval.test",
        bearer_token="tok",
        transport=httpx.MockTransport(fake.handler),
    )

    result = run_for_cohort(
        client, calibration, run_id="run-0001", hospital_hipe="9001", as_of_date=date(2026, 8, 30)
    )

    # Both referrals got a POST /scores call (the Postgres row for the first
    # one stands, per ADR-002) -- only the graph projection failed for it.
    assert len(fake.written_scores) == 2
    assert set(result.scored) == {"PW-9001-000008"}
    assert set(result.graph_projection_failed) == {"PW-9001-000007"}
    assert "simulated Oxigraph outage" in result.graph_projection_failed["PW-9001-000007"]
    assert not result.skipped


def test_score_referral_propagates_insufficient_evidence_directly(
    calibration: CapacityCalibration,
) -> None:
    no_evidence_context = {
        "referral": {
            "hospital_hipe": "9001",
            "pathway_number": "PW-9001-000009",
            "specialty_hipe": "0100",
        },
        "observations": [],
        "conditions": [],
        "triage_events": [],
        "capacity": {"specialty_hipe": "0100", "wards": [], "clinic_sessions": []},
    }
    fake = _FakeRetrievalService(contexts={"PW-9001-000009": no_evidence_context}, cohort=[])
    client = RetrievalClient(
        base_url="http://retrieval.test",
        bearer_token="tok",
        transport=httpx.MockTransport(fake.handler),
    )

    with pytest.raises(InsufficientCapacityEvidenceError):
        score_referral(
            client,
            calibration,
            run_id="run-0001",
            hospital_hipe="9001",
            pathway_number="PW-9001-000009",
            as_of_date=date(2026, 8, 30),
        )
    assert fake.written_scores == []
