"""Genuine round trip against a *running* retrieval-service_20260904
(plan.md Phase 1: "score, POST /scores, read back via
GET /runs/.../hospitals/.../scores, compare").

Unlike test_run.py's mocked transport, this hits real Postgres/Oxigraph
through the real service -- so it skips cleanly rather than failing when
that service isn't reachable at config.settings.retrieval_base_url, the same
way retrieval's own real-data tests skip when the dataset isn't loaded.
Otherwise every `pytest` run of this package would need docker up.

Run with the stack up:

    docker compose up -d db oxigraph retrieval    # from the repo root
    pytest tests/test_run_integration.py          # from here
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import httpx
import pytest

from urgency_agent.calibration import DEFAULT_CALIBRATION_PATH, load_calibration
from urgency_agent.client import RetrievalClient
from urgency_agent.config import settings
from urgency_agent.run import score_referral
from urgency_agent.scoring import InsufficientUrgencyEvidenceError

# Any seeded hospital works -- this is only where we look for a real cohort
# to pick a referral from, not a fact these tests assert on.
_HOSPITAL_HIPE = "9004"


def _service_reachable() -> bool:
    try:
        response = httpx.get(f"{settings.retrieval_base_url}/health", timeout=2.0)
        return response.status_code == 200
    except httpx.HTTPError:
        return False


pytestmark = pytest.mark.skipif(
    not _service_reachable(),
    reason=(
        "retrieval-service_20260904 not reachable at "
        f"{settings.retrieval_base_url} -- start it (`docker compose up -d db oxigraph "
        "retrieval` from the repo root) to run this test"
    ),
)


def _find_cohort(client: RetrievalClient) -> tuple[date, list[dict[str, Any]]]:
    """Look back for a hospital-day that actually has referrals on the list.
    Real seeded data, not a fixture this test writes."""
    for offset in range(30):
        as_of_date = date.today() - timedelta(days=offset)
        cohort = client.get_cohort(_HOSPITAL_HIPE, as_of_date)
        if cohort["referrals"]:
            return as_of_date, cohort["referrals"]
    pytest.skip(f"no cohort data for hospital {_HOSPITAL_HIPE} in the last 30 days")


def test_score_written_via_post_scores_reads_back_via_get_scores_for_run() -> None:
    calibration = load_calibration(DEFAULT_CALIBRATION_PATH)
    client = RetrievalClient(settings.retrieval_base_url, settings.bearer_token)
    as_of_date, referrals = _find_cohort(client)
    run_id = f"run-urgency-agent-integration-test-{date.today().isoformat()}"

    # Refusals are legitimate outcomes on real data (ADR-004/ADR-007), so
    # walk the cohort until one referral is actually scorable rather than
    # failing on whichever happens to sit at index 0.
    for referral in referrals:
        pathway_number = referral["pathway_number"]
        try:
            result = score_referral(
                client,
                calibration,
                run_id=run_id,
                hospital_hipe=_HOSPITAL_HIPE,
                pathway_number=pathway_number,
                as_of_date=as_of_date,
            )
            break
        except InsufficientUrgencyEvidenceError:
            continue
    else:
        pytest.skip("no scorable referral found in this cohort")

    scores = client.get_scores_for_run(run_id, _HOSPITAL_HIPE)
    written = scores["scores"][pathway_number]["urgency"]

    assert written["score"] == pytest.approx(result.score)
    assert written["method"] == result.method
    assert {c["evidence_type"] for c in written["citations"]} == {"observation"}
    assert len(written["citations"]) == len(result.citations)


def test_citations_resolve_to_real_graph_nodes() -> None:
    """The silent-failure guard. An evidence_key built with the wrong
    timestamp format points at a node that was never loaded and degrades to
    `type: null` when resolved -- it never raises. Only a live round trip
    against the real graph catches it, which is why this test cannot live in
    test_run.py.
    """
    calibration = load_calibration(DEFAULT_CALIBRATION_PATH)
    client = RetrievalClient(settings.retrieval_base_url, settings.bearer_token)
    as_of_date, referrals = _find_cohort(client)
    run_id = f"run-urgency-agent-citation-test-{date.today().isoformat()}"

    for referral in referrals:
        pathway_number = referral["pathway_number"]
        try:
            score_referral(
                client,
                calibration,
                run_id=run_id,
                hospital_hipe=_HOSPITAL_HIPE,
                pathway_number=pathway_number,
                as_of_date=as_of_date,
            )
            break
        except InsufficientUrgencyEvidenceError:
            continue
    else:
        pytest.skip("no scorable referral found in this cohort")

    scores = client.get_scores_for_run(run_id, _HOSPITAL_HIPE)
    citations = scores["scores"][pathway_number]["urgency"]["citations"]
    unresolved = [c for c in citations if c.get("type") is None]
    assert not unresolved, (
        f"{len(unresolved)} of {len(citations)} citations did not resolve to a graph "
        f"node -- check the obs_datetime format in the evidence_key: {unresolved[:2]}"
    )
