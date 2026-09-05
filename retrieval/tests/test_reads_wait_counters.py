"""spec.md FR3: the wait-counters endpoint must match running
kg/queries/wait_counters.rq directly (workflow.md's Tier 2 round-trip bar).

Builds its own independent GRAPH-wrapped copy of the fragment (not reusing
app.reads._wrap_wait_counters_query) as the comparison ground truth, so a
bug specific to that wrapper would show up as a mismatch rather than
tautologically agreeing with itself.
"""

from __future__ import annotations

import uuid
from datetime import date

import httpx
import pytest
from fastapi.testclient import TestClient

from app import iri
from app.config import settings
from app.main import app
from app.reads import WAIT_COUNTERS_FRAGMENT_PATH


def _referral_iri() -> tuple[str, str, str]:
    hospital_hipe = "9001"
    pathway_number = f"PW-TEST-{uuid.uuid4().hex[:8]}"
    return iri.referral_iri(hospital_hipe, pathway_number), hospital_hipe, pathway_number


async def _insert_test_referral(referral: str, referral_date: date, received_date: date) -> None:
    update = (
        f"PREFIX eat: <{iri.EAT_NS}>\n"
        f"PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>\n"
        f"INSERT DATA {{ GRAPH <{iri.GRAPH_BASE}inputs> {{\n"
        f'  <{referral}> eat:referralDate "{referral_date.isoformat()}"^^xsd:date ;\n'
        f'               eat:referralReceivedDate "{received_date.isoformat()}"^^xsd:date .\n'
        "} }"
    )
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            settings.oxigraph_update_url,
            content=update.encode("utf-8"),
            headers={"Content-Type": "application/sparql-update"},
        )
        response.raise_for_status()


def _run_fragment_directly(referral: str, as_of_date: date) -> dict:
    fragment = WAIT_COUNTERS_FRAGMENT_PATH.read_text(encoding="utf-8")
    fragment = fragment.replace(
        "VALUES (?referral ?asOfDate) { }",
        f'VALUES (?referral ?asOfDate) {{ (<{referral}> "{as_of_date.isoformat()}"^^xsd:date) }}',
        1,
    )
    # Independent wrapping: insert GRAPH right after the opening brace that
    # follows VALUES, close it right before GROUP BY. Different mechanics
    # from app.reads' index-based approach, same net effect.
    inputs_graph = f"{iri.GRAPH_BASE}inputs"
    fragment = fragment.replace("WHERE {", f"WHERE {{ GRAPH <{inputs_graph}> {{", 1)
    fragment = fragment.replace("\nGROUP BY", "} \nGROUP BY", 1)

    response = httpx.post(
        settings.oxigraph_query_url,
        data={"query": fragment},
        headers={"Accept": "application/sparql-results+json"},
        timeout=10.0,
    )
    response.raise_for_status()
    bindings = response.json()["results"]["bindings"]
    assert len(bindings) == 1
    return bindings[0]


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def auth_headers() -> dict[str, str]:
    token = next(iter(settings.valid_tokens))
    return {"Authorization": f"Bearer {token}"}


def test_endpoint_matches_fragment_run_directly(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    import asyncio

    referral, hospital_hipe, pathway_number = _referral_iri()
    referral_date = date(2026, 8, 1)
    received_date = date(2026, 8, 5)
    as_of_date = date(2026, 9, 4)
    asyncio.run(_insert_test_referral(referral, referral_date, received_date))

    direct = _run_fragment_directly(referral, as_of_date)

    response = client.get(
        f"/referrals/{hospital_hipe}/{pathway_number}/wait-counters",
        params={"as_of_date": as_of_date.isoformat()},
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()

    assert body["days_since_referral"] == int(direct["daysSinceReferral"]["value"])
    assert body["days_since_received"] == int(direct["daysSinceReceived"]["value"])
    assert body["adjusted_wait_days"] == int(direct["adjustedWaitDays"]["value"])
    assert ("daysAwaitingTriage" in direct) == (body["days_awaiting_triage"] is not None)
