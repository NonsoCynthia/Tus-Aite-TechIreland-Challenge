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

import os
import uuid
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
# to pick a referral from, not a fact these tests assert on. 9001 because the
# default `sample` profile (dataset/versions.yml) carries only 9001 and 9002;
# 9004 exists in `full` but not in what `make load` pulls by default, and a
# hospital that isn't there skips the test rather than failing it, which is
# an easy way to think these tests ran when they never did.
_HOSPITAL_HIPE = "9001"
_OXIGRAPH_URL = "http://localhost:7878"
_EATD_NS = "https://nonsocynthia.github.io/Tus-Aite-TechIreland-Challenge/kg/id/"


# agent_scores' primary key is (run_id, agent_name, hospital_hipe,
# pathway_number), so a run_id that is stable within a day makes these tests
# pass exactly once and then 400 on every re-run that day -- self-poisoning,
# and it looks like a service fault rather than a test defect. One fresh id
# per invocation.
def _fresh_run_id(label: str) -> str:
    return f"run-urgency-{label}-{date.today().isoformat()}-{uuid.uuid4().hex[:8]}"


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


def _graph_is_populated() -> bool:
    """The RDF projection (Morph-KGC) is a manual host-side step, not part of
    `make up`/`make load` -- see kg/docs/GETTING_THE_GRAPH.md. Against an empty
    Oxigraph every citation resolves to `type: null`, which is precisely the
    symptom `test_citations_resolve_to_real_graph_nodes` looks for. Without
    this guard that test reports a scary "citations did not resolve" failure
    whose actual cause is "the graph was never built"."""
    url = os.environ.get("OXIGRAPH_URL", "http://localhost:7878")
    try:
        response = httpx.post(
            f"{url}/query",
            # NOTE THE `GRAPH ?g`. Everything in this store is quad-tagged into
            # named graphs, so `ASK { ?s ?p ?o }` inspects only the empty
            # default graph and returns false against a fully loaded store --
            # the exact trap kg/docs/GETTING_THE_GRAPH.md section 6 warns
            # about, which this guard originally fell into: it reported "graph
            # not built" and skipped after the graph had been built correctly.
            data={"query": "ASK { GRAPH ?g { ?s ?p ?o } }"},
            headers={"Accept": "application/sparql-results+json"},
            timeout=5.0,
        )
        return bool(response.status_code == 200 and response.json().get("boolean"))
    except (httpx.HTTPError, ValueError):
        return False


def _obs_iri(evidence_key: str) -> str:
    """retrieval/app/iri.py's own convention: EATD_NS + the evidence type's
    segment + the caller-supplied composite key."""
    return f"{_EATD_NS}obs/{evidence_key}"


def _graph_has(iri: str) -> bool:
    url = os.environ.get("OXIGRAPH_URL", _OXIGRAPH_URL)
    response = httpx.post(
        url + "/query",
        data={"query": f"ASK {{ GRAPH ?g {{ <{iri}> ?p ?o }} }}"},
        headers={"Accept": "application/sparql-results+json"},
        timeout=10.0,
    )
    response.raise_for_status()
    return bool(response.json().get("boolean"))


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
    run_id = _fresh_run_id("roundtrip")

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

    # NOTE THE float(). `GET /runs/.../scores` returns `score` as a **string**
    # ("0.075"), not a number: agent_scores.score is a Postgres `numeric`, and
    # the driver hands back a Decimal that serialises as a JSON string. The
    # value round-trips exactly; only the type changes. Recorded as ADR-009,
    # because the coordinator reads this same field and does arithmetic on it
    # (`compute_priority`), which raises TypeError on a string -- its tests pass
    # only because its stub score source produces real floats.
    # abs=5e-4, not pytest.approx's default relative tolerance: `agent_scores.score`
    # is `numeric(4,3)`, so the service silently rounds every score to THREE
    # DECIMALS on write. The committed calibration happens to produce exact
    # 3dp values (0.075, 0.225, 0.6, 1.0), so a stricter tolerance passes today
    # by luck rather than design -- retune a breakpoint to something like 1/3
    # and this test would fail on storage precision while nothing was actually
    # wrong. Half of one ulp of the stored scale is the honest bound.
    assert float(written["score"]) == pytest.approx(result.score, abs=5e-4)
    assert isinstance(written["score"], str), (
        "score came back as a number -- if the retrieval service now returns a "
        "float, ADR-009 has been fixed upstream and this assertion should be "
        "inverted, not deleted"
    )
    assert written["method"] == result.method
    assert {c["evidence_type"] for c in written["citations"]} == {"observation"}
    assert len(written["citations"]) == len(result.citations)


def test_citations_point_at_real_graph_nodes() -> None:
    """The silent-failure guard, and the only test that can catch it.

    An `evidence_key` built with the wrong `obs_datetime` format names a graph
    node that was never loaded. Nothing raises: the retrieval service's
    `_resolve_iri` simply returns `type: null` when a reader eventually asks
    for that evidence, far from the agent that wrote it. Only a live check
    against the real graph catches it, which is why this cannot live in
    test_run.py.

    **Checked against the graph directly, by SPARQL ASK, not through the
    service.** `GET /runs/.../scores` returns citations as raw
    `{evidence_type, evidence_key}` pairs and deliberately does NOT resolve
    them -- it is an agent-input endpoint. Resolution happens on the
    decision-placement evidence endpoint (`reads.py:_evidence_for_placement`),
    which needs a `Decision` to exist, which needs the coordinator, which is
    blocked on ADR-009. An earlier version of this test read the scores
    endpoint and asserted `type` was not null; every citation "failed" because
    that key never exists there. That was a false alarm about the agent and a
    real defect in the test.

    The IRI template is retrieval's own (`app/iri.py`: `EATD_NS` +
    `obs/{evidence_key}`), reproduced here rather than imported because this
    package does not depend on the retrieval service's source.
    """
    if not _graph_is_populated():
        pytest.skip(
            "Oxigraph holds no triples -- the RDF projection has not been built "
            "(kg/docs/GETTING_THE_GRAPH.md). Every citation would appear unresolvable "
            "for that reason rather than because of a malformed evidence_key."
        )
    calibration = load_calibration(DEFAULT_CALIBRATION_PATH)
    client = RetrievalClient(settings.retrieval_base_url, settings.bearer_token)
    as_of_date, referrals = _find_cohort(client)
    run_id = _fresh_run_id("citations")

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

    missing = [c.evidence_key for c in result.citations if not _graph_has(_obs_iri(c.evidence_key))]
    assert not missing, (
        f"{len(missing)} of {len(result.citations)} citations name a graph node that does "
        f"not exist -- check the obs_datetime format in the evidence_key "
        f"(space-separated and percent-encoded, not ISO 'T'): {missing[:2]}"
    )
