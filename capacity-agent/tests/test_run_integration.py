"""Genuine round-trip against a *running* retrieval-service_20260904
(spec.md FR2 Phase 2: "score, POST /scores, read back via GET /runs/.../
hospitals/.../scores, compare"). Unlike test_run.py's mocked-transport
tests, this hits real Postgres/Oxigraph through the real service -- so it
skips cleanly (not fails) when that service isn't reachable at
CAPACITY_AGENT_TEST_RETRIEVAL_URL / config.settings.retrieval_base_url,
the same way retrieval's own `TestReferralContextRealData` skips when the
real dataset isn't loaded, rather than needing docker up for every
`pytest` run of this package.

Run with the stack up: `docker compose up -d db oxigraph retrieval` from
the repo root, then `pytest tests/test_run_integration.py` from here.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import httpx
import pytest

from capacity_agent.calibration import DEFAULT_CALIBRATION_PATH, load_calibration
from capacity_agent.client import RetrievalClient
from capacity_agent.config import settings
from capacity_agent.run import score_referral

# Any hospital in the seeded dataset works -- this is just where we look for
# a real cohort to pick a referral from, not a fact this test asserts on.
_HOSPITAL_HIPE = "9001"


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


def test_score_written_via_post_scores_reads_back_via_get_scores_for_run() -> None:
    calibration = load_calibration(DEFAULT_CALIBRATION_PATH)
    client = RetrievalClient(settings.retrieval_base_url, settings.bearer_token)

    # Look back a few days for a hospital-day with at least one referral
    # still on the list -- real seeded data, not a fixture this test writes.
    cohort: dict[str, Any] = {"referrals": []}
    as_of_date = date.today()
    for offset in range(30):
        as_of_date = date.today() - timedelta(days=offset)
        cohort = client.get_cohort(_HOSPITAL_HIPE, as_of_date)
        if cohort["referrals"]:
            break
    if not cohort["referrals"]:
        pytest.skip(f"no cohort data found for hospital {_HOSPITAL_HIPE} in the last 30 days")

    pathway_number = cohort["referrals"][0]["pathway_number"]
    run_id = f"run-capacity-agent-integration-test-{date.today().isoformat()}"

    result = score_referral(
        client,
        calibration,
        run_id=run_id,
        hospital_hipe=_HOSPITAL_HIPE,
        pathway_number=pathway_number,
        as_of_date=as_of_date,
    )

    scores = client.get_scores_for_run(run_id, _HOSPITAL_HIPE)
    written = scores["scores"][pathway_number]["capacity"]
    assert written["score"] == pytest.approx(result.score)
    assert written["method"] == result.method
    assert {c["evidence_type"] for c in written["citations"]} == {
        c.evidence_type for c in result.citations
    }
