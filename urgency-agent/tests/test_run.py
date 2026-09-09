"""run.py orchestration tests (NFR2, Tier 2): score_referral/run_for_cohort
against a small in-memory fake of retrieval-service_20260904's contract
(GET context/cohort, POST /scores), via httpx.MockTransport -- exercising the
same client.py wire format as production without a live service.

The urgency-specific concern here is **how a cohort run reports what it did
not score**. Two very different things get excluded (ADR-004/ADR-007), and a
compliance reviewer must be able to tell them apart:

  - `refused_paediatric` -- an entire specialty deliberately out of scope,
    expected and systematic.
  - `skipped` -- a data gap on an individual referral.

Collapsing both into one bucket would make "we do not cover paediatrics" look
identical to "some rows are missing observations", which is exactly the
distinction ADR-007 says must stay visible.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

import httpx
import pytest

from urgency_agent.calibration import UrgencyCalibration
from urgency_agent.client import RetrievalClient
from urgency_agent.run import run_for_cohort, score_referral
from urgency_agent.scoring import InsufficientUrgencyEvidenceError


@pytest.fixture
def calibration() -> UrgencyCalibration:
    return UrgencyCalibration.model_validate(
        {
            "breakpoints": [
                {"news2": 0, "score": 0.0},
                {"news2": 4, "score": 0.30},
                {"news2": 6, "score": 0.60},
                {"news2": 17, "score": 1.0},
            ],
            "method": "urgency-news2-v1",
            "agent_version": "urgency-agent-test",
        }
    )


def _context_for(
    pathway_number: str,
    *,
    rr: int = 16,
    specialty_hipe: str = "1800",
    observations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    default = [
        {
            "obs_datetime": "2026-08-16T09:16:00",
            "hr": 70,
            "sbp": 120,
            "dbp": 80,
            "rr": rr,
            "temp": 37.0,
            "spo2": 98,
            "pain": 0,
            "avpu": "A",
        }
    ]
    return {
        "referral": {
            "hospital_hipe": "9004",
            "pathway_number": pathway_number,
            "specialty_hipe": specialty_hipe,
        },
        "observations": default if observations is None else observations,
        "conditions": [],
        "triage_events": [],
    }


class _FakeRetrievalService:
    """In-memory stand-in for enough of retrieval-service_20260904 to drive
    run.py: GET context per referral, GET cohort, POST /scores recording
    what was written so tests can assert on it."""

    def __init__(
        self,
        contexts: dict[str, dict[str, Any]],
        cohort: list[str],
        graph_failures: set[str] | None = None,
    ) -> None:
        self.contexts = contexts
        self.cohort = cohort
        self.graph_failures = graph_failures or set()
        self.written_scores: list[dict[str, Any]] = []

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


def _client_for(fake: _FakeRetrievalService) -> RetrievalClient:
    return RetrievalClient(
        base_url="http://retrieval.test",
        bearer_token="tok",
        transport=httpx.MockTransport(fake.handler),
    )


def test_score_referral_gathers_context_scores_and_posts(
    calibration: UrgencyCalibration,
) -> None:
    fake = _FakeRetrievalService(
        contexts={"PW-9004-000286": _context_for("PW-9004-000286", rr=22)},
        cohort=[],
    )
    result = score_referral(
        _client_for(fake),
        calibration,
        run_id="run-0001",
        hospital_hipe="9004",
        pathway_number="PW-9004-000286",
        as_of_date=date(2026, 8, 30),
    )

    assert result.news2 == 2
    assert len(fake.written_scores) == 1
    written = fake.written_scores[0]
    assert written["run_id"] == "run-0001"
    assert written["agent_name"] == "urgency"
    assert written["pathway_number"] == "PW-9004-000286"
    assert written["score"] == pytest.approx(result.score)
    assert written["method"] == "urgency-news2-v1"
    assert written["agent_version"] == "urgency-agent-test"


def test_score_referral_writes_one_citation_per_news2_vital(
    calibration: UrgencyCalibration,
) -> None:
    """NFR5 end to end: the citations built by the scorer are the citations
    that reach the wire, all six of them, all of type `observation`."""
    fake = _FakeRetrievalService(
        contexts={"PW-9004-000286": _context_for("PW-9004-000286")}, cohort=[]
    )
    score_referral(
        _client_for(fake),
        calibration,
        run_id="run-0001",
        hospital_hipe="9004",
        pathway_number="PW-9004-000286",
        as_of_date=date(2026, 8, 30),
    )

    citations = fake.written_scores[0]["citations"]
    assert len(citations) == 6
    assert {c["evidence_type"] for c in citations} == {"observation"}


def test_score_referral_raises_and_writes_nothing_when_refused(
    calibration: UrgencyCalibration,
) -> None:
    """A refusal must not reach POST /scores at all. Writing a score and
    then reporting it as skipped would leave the coordinator reading a
    number this agent does not stand behind."""
    fake = _FakeRetrievalService(
        contexts={"PW-9004-000999": _context_for("PW-9004-000999", specialty_hipe="0601")},
        cohort=[],
    )
    with pytest.raises(InsufficientUrgencyEvidenceError):
        score_referral(
            _client_for(fake),
            calibration,
            run_id="run-0001",
            hospital_hipe="9004",
            pathway_number="PW-9004-000999",
            as_of_date=date(2026, 8, 30),
        )
    assert fake.written_scores == []


def test_run_for_cohort_scores_every_referral_on_the_list(
    calibration: UrgencyCalibration,
) -> None:
    fake = _FakeRetrievalService(
        contexts={
            "PW-9004-000286": _context_for("PW-9004-000286", rr=16),
            "PW-9004-000287": _context_for("PW-9004-000287", rr=22),
        },
        cohort=["PW-9004-000286", "PW-9004-000287"],
    )
    result = run_for_cohort(
        _client_for(fake),
        calibration,
        run_id="run-0001",
        hospital_hipe="9004",
        as_of_date=date(2026, 8, 30),
    )

    assert set(result.scored) == {"PW-9004-000286", "PW-9004-000287"}
    assert len(fake.written_scores) == 2
    assert not result.skipped
    assert not result.refused_paediatric


def test_run_for_cohort_reports_paediatric_refusals_separately(
    calibration: UrgencyCalibration,
) -> None:
    """ADR-007's visibility requirement. A whole specialty falling out of
    the ranked list is a coverage statement, not a data-quality incident,
    and the clinician UI has to be able to say which it is."""
    fake = _FakeRetrievalService(
        contexts={
            "PW-9004-000286": _context_for("PW-9004-000286"),
            "PW-9004-000999": _context_for("PW-9004-000999", specialty_hipe="0601"),
        },
        cohort=["PW-9004-000286", "PW-9004-000999"],
    )
    result = run_for_cohort(
        _client_for(fake),
        calibration,
        run_id="run-0001",
        hospital_hipe="9004",
        as_of_date=date(2026, 8, 30),
    )

    assert set(result.scored) == {"PW-9004-000286"}
    assert set(result.refused_paediatric) == {"PW-9004-000999"}
    assert not result.skipped
    assert len(fake.written_scores) == 1


def test_run_for_cohort_skips_a_referral_with_no_observation_and_continues(
    calibration: UrgencyCalibration,
) -> None:
    """One referral's failure never aborts the batch -- a compliance
    reviewer checks the result buckets, the same way the retrieval service
    never lets one bad row take down an otherwise-complete response."""
    fake = _FakeRetrievalService(
        contexts={
            "PW-9004-000286": _context_for("PW-9004-000286"),
            "PW-9004-000288": _context_for("PW-9004-000288", observations=[]),
            "PW-9004-000287": _context_for("PW-9004-000287"),
        },
        cohort=["PW-9004-000286", "PW-9004-000288", "PW-9004-000287"],
    )
    result = run_for_cohort(
        _client_for(fake),
        calibration,
        run_id="run-0001",
        hospital_hipe="9004",
        as_of_date=date(2026, 8, 30),
    )

    assert set(result.scored) == {"PW-9004-000286", "PW-9004-000287"}
    assert set(result.skipped) == {"PW-9004-000288"}
    assert "observation" in result.skipped["PW-9004-000288"]


def test_run_for_cohort_records_graph_projection_failures_separately(
    calibration: UrgencyCalibration,
) -> None:
    """The 207 case: the score row exists and is readable via
    GET /runs/.../scores, but the graph audit trail is incomplete. Not the
    same as 'not scored', and must not be reported as such."""
    fake = _FakeRetrievalService(
        contexts={
            "PW-9004-000286": _context_for("PW-9004-000286"),
            "PW-9004-000287": _context_for("PW-9004-000287"),
        },
        cohort=["PW-9004-000286", "PW-9004-000287"],
        graph_failures={"PW-9004-000287"},
    )
    result = run_for_cohort(
        _client_for(fake),
        calibration,
        run_id="run-0001",
        hospital_hipe="9004",
        as_of_date=date(2026, 8, 30),
    )

    assert set(result.scored) == {"PW-9004-000286"}
    assert set(result.graph_projection_failed) == {"PW-9004-000287"}
    assert len(fake.written_scores) == 2


def test_result_buckets_are_disjoint(calibration: UrgencyCalibration) -> None:
    """A pathway_number appears in exactly one bucket, so a caller asking
    'did this referral get a usable score' never has to check more than one
    place."""
    fake = _FakeRetrievalService(
        contexts={
            "PW-9004-000286": _context_for("PW-9004-000286"),
            "PW-9004-000287": _context_for("PW-9004-000287"),
            "PW-9004-000288": _context_for("PW-9004-000288", observations=[]),
            "PW-9004-000999": _context_for("PW-9004-000999", specialty_hipe="0601"),
        },
        cohort=[
            "PW-9004-000286",
            "PW-9004-000287",
            "PW-9004-000288",
            "PW-9004-000999",
        ],
        graph_failures={"PW-9004-000287"},
    )
    result = run_for_cohort(
        _client_for(fake),
        calibration,
        run_id="run-0001",
        hospital_hipe="9004",
        as_of_date=date(2026, 8, 30),
    )

    buckets = [
        set(result.scored),
        set(result.skipped),
        set(result.refused_paediatric),
        set(result.graph_projection_failed),
    ]
    everything = [pathway for bucket in buckets for pathway in bucket]
    assert len(everything) == len(set(everything)) == 4
