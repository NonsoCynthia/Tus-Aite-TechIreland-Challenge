"""spec.md FR8: evidence resolution folded into the existing read endpoints
(not a separate endpoint the UI has to round-trip to), and every IRI in an
API response is short (namespace prefix stripped) rather than the full
`https://nonsocynthia.github.io/...` form -- that form is only needed for
the actual SPARQL/RDF operations, never for JSON a caller consumes.
"""

from __future__ import annotations

import random
import uuid
from datetime import date, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

from app import iri
from app.config import settings
from app.main import app
from tests.adapters import to_decision_in
from tests.fixtures import make_decision


def _run_id() -> str:
    return f"run-test-{uuid.uuid4().hex[:8]}"


def _unique_as_of_date() -> date:
    # decision_iri (and therefore placement_iri) is keyed only by
    # (hospital_hipe, as_of_date) -- namespaces.md #4, "one per hospital per
    # day" -- so two decisions landing on the same day accumulate onto the
    # same graph node rather than being independent (see plan.md Phase 4's
    # note on this). fixtures.py's own as_of_date range is a handful of
    # fixed values, which collides across repeated runs of this exact test
    # in one session. Same fix as test_reads_decision.py.
    return date.today() + timedelta(days=random.randint(1000, 999_000))


async def _insert_clinic_session(session_iri: str) -> None:
    """Stands in for what the Morph-KGC loader would have written for a real
    ClinicSession -- this service never writes input-layer data itself, but
    the test needs some to resolve against."""
    update = (
        f"PREFIX eat: <{iri.EAT_NS}>\n"
        f"PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>\n"
        f"INSERT DATA {{ GRAPH <{iri.GRAPH_BASE}inputs> {{\n"
        f"  <{session_iri}> a <{iri.eat('ClinicSession')}> ;\n"
        f'    <{iri.eat("clinicName")}> "Cardiology Outreach" ;\n'
        f'    <{iri.eat("slotsTotal")}> "10"^^xsd:nonNegativeInteger ;\n'
        f'    <{iri.eat("slotsBooked")}> "8"^^xsd:nonNegativeInteger ;\n'
        f'    <{iri.eat("slotsAvailable")}> "2"^^xsd:nonNegativeInteger ;\n'
        f'    <{iri.eat("sessionDate")}> "2026-08-26"^^xsd:date .\n'
        "} }"
    )
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            settings.oxigraph_update_url,
            content=update.encode("utf-8"),
            headers={"Content-Type": "application/sparql-update"},
        )
        response.raise_for_status()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def auth_headers() -> dict[str, str]:
    token = next(iter(settings.valid_tokens))
    return {"Authorization": f"Bearer {token}"}


class TestIriShort:
    def test_strips_instance_namespace(self) -> None:
        full = iri.referral_iri("9001", "PW-9001-000001")
        assert iri.short(full) == "referral/9001/PW-9001-000001"

    def test_strips_vocabulary_namespace(self) -> None:
        assert iri.short(iri.eat("ClinicSession")) == "ClinicSession"

    def test_strips_graph_namespace(self) -> None:
        assert iri.short(iri.run_graph("run-0001")) == "run/run-0001"

    def test_leaves_non_namespaced_values_unchanged(self) -> None:
        assert iri.short("Cardiology Outreach") == "Cardiology Outreach"
        assert iri.short("2026-08-26") == "2026-08-26"

    def test_strips_reused_vocabularies_with_a_short_label(self) -> None:
        # Found via a real citation resolving to unshortened
        # http://www.w3.org/ns/sosa/... URIs (AC13 violation) rather than
        # assumed up front -- every per-column Observation node is
        # sosa:Observation with sosa:observedProperty etc.
        assert iri.short(f"{iri.SOSA_NS}Observation") == "sosa:Observation"
        assert iri.short(f"{iri.SOSA_NS}observedProperty") == "sosa:observedProperty"
        assert iri.short(f"{iri.PROV_NS}wasGeneratedBy") == "prov:wasGeneratedBy"
        assert iri.short(f"{iri.RDF_NS}type") == "rdf:type"


class TestResolvedEvidenceInDecisionEndpoint:
    def test_evidence_carries_real_properties_not_just_an_iri(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        # Build a decision, then overwrite its first ranking's citations
        # with one known clinic_session citation (the generator's own
        # citation types are randomised per seed -- injecting a known one
        # directly is more reliable than hunting for a seed that happens to
        # produce clinic_session), and separately insert real data for that
        # exact IRI (the Morph-KGC loader's job in production) -- proving
        # the two hops (cites walk, then resolve) actually compose against
        # real graph state.
        payload = to_decision_in(make_decision(30, run_id=_run_id(), cohort_size=1))
        payload = payload.model_copy(update={"as_of_date": _unique_as_of_date()})
        evidence_key = f"{payload.hospital_hipe}/CL99/2026-08-26"
        body = payload.model_dump(mode="json")
        body["rankings"][0]["citations"] = [
            {"evidence_type": "clinic_session", "evidence_key": evidence_key, "role": "urgency"}
        ]
        session_iri = iri.evidence_iri("clinic_session", evidence_key)

        import asyncio

        asyncio.run(_insert_clinic_session(session_iri))
        response = client.post("/decisions", json=body, headers=auth_headers)
        assert response.status_code == 200

        body = client.get(
            f"/decisions/{payload.hospital_hipe}/{payload.as_of_date.isoformat()}",
            headers=auth_headers,
        ).json()

        evidence = body["placements"][0]["evidence"]
        clinic_entries = [e for e in evidence if e["type"] == "ClinicSession"]
        assert len(clinic_entries) == 1
        resolved = clinic_entries[0]
        assert resolved["iri"] == iri.short(session_iri)
        assert resolved["properties"]["clinicName"] == "Cardiology Outreach"
        assert resolved["properties"]["slotsTotal"] == "10"
        assert resolved["properties"]["slotsBooked"] == "8"
        assert resolved["properties"]["slotsAvailable"] == "2"
        # not the full IRI form anywhere in the response
        assert "https://" not in str(body)

    def test_unresolved_evidence_degrades_gracefully_not_an_error(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        # No underlying data inserted for any of this decision's citations
        # (the normal case in this dev environment, where the full dataset
        # isn't loaded) -- the endpoint must still succeed and just show
        # empty properties, not fail the whole response over one citation.
        payload = to_decision_in(make_decision(31, run_id=_run_id(), cohort_size=1))
        payload = payload.model_copy(update={"as_of_date": _unique_as_of_date()})
        client.post("/decisions", json=payload.model_dump(mode="json"), headers=auth_headers)

        response = client.get(
            f"/decisions/{payload.hospital_hipe}/{payload.as_of_date.isoformat()}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        for entry in response.json()["placements"][0]["evidence"]:
            assert entry["type"] is None
            assert entry["properties"] == {}

    def test_all_top_level_iris_are_short(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        payload = to_decision_in(make_decision(32, run_id=_run_id(), cohort_size=1))
        payload = payload.model_copy(update={"as_of_date": _unique_as_of_date()})
        client.post("/decisions", json=payload.model_dump(mode="json"), headers=auth_headers)

        body = client.get(
            f"/decisions/{payload.hospital_hipe}/{payload.as_of_date.isoformat()}",
            headers=auth_headers,
        ).json()

        assert not body["decision"].startswith("http")
        placement = body["placements"][0]
        assert not placement["placement"].startswith("http")
        assert not placement["referral"].startswith("http")
        for entry in placement["evidence"]:
            assert not entry["iri"].startswith("http")
