"""spec.md FR11: new-referral intake (POST /referrals), user request ("input
new patients"). Same ADR-002 flow as every other write endpoint (Postgres
commit, then graph projection), against the real Postgres and Oxigraph this
container runs alongside -- not mocks, same convention as test_routes.py.

Uses hospital 9001 / specialty 0100 / referral_source 6, which are seeded by
the dataset generator and confirmed present against this environment's own
Postgres (core.hospital_specialty, core.ref_codes) before writing these
tests -- not assumed.
"""

from __future__ import annotations

import uuid
from datetime import date

import httpx
import psycopg
import pytest
from fastapi.testclient import TestClient

from app import graph, iri
from app.config import settings
from app.main import app
from app.schemas import NewPatientIn, ReferralIn

_HOSPITAL = "9001"
_SPECIALTY = "0100"


def _patient_id() -> str:
    return f"intake-test-{uuid.uuid4().hex[:10]}"


def _new_patient_payload(hospital_hipe: str = _HOSPITAL) -> ReferralIn:
    return ReferralIn(
        hospital_hipe=hospital_hipe,
        patient_id=_patient_id(),
        new_patient=NewPatientIn(
            patient_sex="F",
            patient_date_of_birth=date(1990, 5, 14),
            area_of_residence_code="D024",
        ),
        specialty_hipe=_SPECIALTY,
        referral_date=date(2026, 8, 20),
        referral_received_date=date(2026, 8, 22),
        priority_level_gp=1,
        referral_source=6,
        high_clinical_or_social_needs=True,
    )


def _pg_conn() -> psycopg.Connection:
    return psycopg.connect(settings.retrieval_db_url)


_ASK_PREFIXES = "PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>\n"


def _ask(query: str) -> bool:
    response = httpx.post(
        settings.oxigraph_query_url,
        data={"query": _ASK_PREFIXES + query},
        headers={"Accept": "application/sparql-results+json"},
        timeout=10.0,
    )
    response.raise_for_status()
    return bool(response.json()["boolean"])


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def auth_headers() -> dict[str, str]:
    token = next(iter(settings.valid_tokens))
    return {"Authorization": f"Bearer {token}"}


class TestReferralTriples:
    """Pure unit tests -- no Oxigraph needed (graph.py separates building
    triples from pushing them, same as test_graph_triples.py)."""

    def test_new_patient_gets_patient_and_person_triples(self) -> None:
        payload = _new_patient_payload()
        assert payload.new_patient is not None
        payload.new_patient.ihi_number = "IHI-000999"
        payload.new_patient.person_sex = "F"
        payload.new_patient.person_date_of_birth = payload.new_patient.patient_date_of_birth
        payload.new_patient.person_area_of_residence_code = "D024"

        triples = graph.referral_triples(payload, "PW-9001-900001", today=payload.referral_date)

        types = {(s, o) for s, p, o in triples if p == f"<{iri.rdf('type')}>"}
        assert (
            f"<{iri.patient_iri(payload.hospital_hipe, payload.patient_id)}>",
            f"<{iri.eat('Patient')}>",
        ) in types
        assert (
            f"<{iri.person_iri('IHI-000999')}>",
            f"<{iri.eat('Person')}>",
        ) in types

    def test_existing_patient_gets_no_patient_or_person_triples(self) -> None:
        payload = _new_patient_payload()
        payload.new_patient = None

        triples = graph.referral_triples(payload, "PW-9001-900002", today=payload.referral_date)

        types = [o for s, p, o in triples if p == f"<{iri.rdf('type')}>"]
        assert f"<{iri.eat('Patient')}>" not in types
        assert f"<{iri.eat('Person')}>" not in types
        # The Referral itself is always projected, existing patient or not.
        assert f"<{iri.eat('Referral')}>" in types

    def test_gp_priority_omitted_when_absent(self) -> None:
        payload = _new_patient_payload()
        payload.priority_level_gp = None

        triples = graph.referral_triples(payload, "PW-9001-900003", today=payload.referral_date)

        predicates = [p for _, p, _ in triples]
        assert f"<{iri.eat('gpPriority')}>" not in predicates


class TestCreateReferral:
    def test_requires_auth(self, client: TestClient) -> None:
        payload = _new_patient_payload()
        response = client.post("/referrals", json=payload.model_dump(mode="json"))
        assert response.status_code == 401

    def test_new_patient_writes_postgres_and_graph(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        payload = _new_patient_payload()

        response = client.post(
            "/referrals", json=payload.model_dump(mode="json"), headers=auth_headers
        )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        pathway_number = body["pathway_number"]
        assert pathway_number.startswith(f"PW-{payload.hospital_hipe}-")

        with _pg_conn() as conn:
            patient_row = conn.execute(
                "SELECT patient_sex FROM core.patients "
                "WHERE hospital_hipe = %s AND patient_id = %s",
                (payload.hospital_hipe, payload.patient_id),
            ).fetchone()
            referral_row = conn.execute(
                "SELECT specialty_hipe, referral_source FROM core.referrals "
                "WHERE hospital_hipe = %s AND pathway_number = %s",
                (payload.hospital_hipe, pathway_number),
            ).fetchone()
            daily_row = conn.execute(
                "SELECT triage_status, adjusted_wait_days, removal_date FROM core.referral_daily "
                "WHERE hospital_hipe = %s AND pathway_number = %s",
                (payload.hospital_hipe, pathway_number),
            ).fetchone()
        assert patient_row is not None and patient_row[0] == "F"
        assert referral_row == (payload.specialty_hipe, payload.referral_source)
        assert daily_row is not None
        assert daily_row[0] == "awaiting_triage"
        assert daily_row[2] is None  # removal_date -- still on the list

        referral_iri = iri.referral_iri(payload.hospital_hipe, pathway_number)
        assert _ask(
            f"ASK {{ GRAPH <{iri.inputs_graph()}> "
            f"{{ <{referral_iri}> a <{iri.eat('Referral')}> }} }}"
        )
        patient_iri = iri.patient_iri(payload.hospital_hipe, payload.patient_id)
        assert _ask(
            f"ASK {{ GRAPH <{iri.inputs_graph()}> "
            f"{{ <{patient_iri}> a <{iri.eat('Patient')}> }} }}"
        )

    def test_existing_patient_referral_does_not_require_new_patient(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        first = _new_patient_payload()
        r1 = client.post("/referrals", json=first.model_dump(mode="json"), headers=auth_headers)
        assert r1.status_code == 200

        second = ReferralIn(
            hospital_hipe=first.hospital_hipe,
            patient_id=first.patient_id,
            specialty_hipe=_SPECIALTY,
            referral_date=date(2026, 9, 1),
            referral_received_date=date(2026, 9, 1),
            referral_source=6,
        )
        r2 = client.post("/referrals", json=second.model_dump(mode="json"), headers=auth_headers)

        assert r2.status_code == 200
        assert r2.json()["pathway_number"] != r1.json()["pathway_number"]

    def test_unknown_patient_without_new_patient_returns_400(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        payload = ReferralIn(
            hospital_hipe=_HOSPITAL,
            patient_id=_patient_id(),
            specialty_hipe=_SPECIALTY,
            referral_date=date(2026, 8, 20),
            referral_received_date=date(2026, 8, 22),
            referral_source=6,
        )

        response = client.post(
            "/referrals", json=payload.model_dump(mode="json"), headers=auth_headers
        )

        assert response.status_code == 400

    def test_received_before_referral_date_rejected_by_postgres_check(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        payload = ReferralIn(
            hospital_hipe=_HOSPITAL,
            patient_id=_patient_id(),
            new_patient=NewPatientIn(
                patient_sex="F",
                patient_date_of_birth=date(1990, 5, 14),
                area_of_residence_code="D024",
            ),
            specialty_hipe=_SPECIALTY,
            referral_date=date(2026, 8, 22),
            referral_received_date=date(2026, 8, 20),  # before referral_date -- violates the CHECK
            referral_source=6,
        )

        response = client.post(
            "/referrals", json=payload.model_dump(mode="json"), headers=auth_headers
        )

        assert response.status_code == 400

    def test_new_referral_appears_in_the_coordinators_cohort(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        payload = _new_patient_payload()

        response = client.post(
            "/referrals", json=payload.model_dump(mode="json"), headers=auth_headers
        )
        pathway_number = response.json()["pathway_number"]

        cohort = client.get(
            f"/hospitals/{payload.hospital_hipe}/cohort/{date.today().isoformat()}",
            headers=auth_headers,
        )
        assert cohort.status_code == 200
        pathway_numbers = [r["pathway_number"] for r in cohort.json()["referrals"]]
        assert pathway_number in pathway_numbers
