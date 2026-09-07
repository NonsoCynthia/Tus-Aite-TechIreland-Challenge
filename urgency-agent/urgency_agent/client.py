"""HTTP client for retrieval-service_20260904 -- per ADR-002, this is the
urgency agent's *only* interface to Postgres/the graph. It never issues
SPARQL or Postgres queries directly, and there is deliberately no code path
here that could.
"""

from __future__ import annotations

from datetime import date
from types import TracebackType
from typing import Any

import httpx

from .scoring import Citation


class RetrievalServiceError(RuntimeError):
    """A non-2xx (and non-207) response, or a request-level failure, from
    the retrieval service."""


class GraphProjectionFailedError(RuntimeError):
    """retrieval/app/routes.py's 207: Postgres committed but the graph
    projection then failed. The score row IS written and stands (ADR-002,
    Postgres is the system of record) -- this is raised, not swallowed, so
    the caller can log/retry the graph side out of band rather than assume
    the audit trail is complete."""


class ReferralNotFoundError(RuntimeError):
    """404 from GET /referrals/.../context: the referral doesn't exist."""


def _raise_for_unexpected_status(response: httpx.Response, *, expected: int) -> None:
    if response.status_code != expected:
        raise RetrievalServiceError(
            f"retrieval service returned {response.status_code} for "
            f"{response.request.method} {response.request.url}: {response.text}"
        )


class RetrievalClient:
    """Thin wrapper over retrieval-service_20260904's documented contract
    (retrieval/README.md). One bearer token, one base URL -- the same shared
    token every other caller of that service uses (retrieval spec.md NFR4:
    the token carries no per-caller identity)."""

    def __init__(
        self,
        base_url: str,
        bearer_token: str,
        *,
        timeout: float = 15.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._client = httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {bearer_token}"},
            timeout=timeout,
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> RetrievalClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def get_referral_context(self, hospital_hipe: str, pathway_number: str) -> dict[str, Any]:
        """FR9: everything the urgency agent needs to judge one referral.

        Note what this does NOT currently return: `priority_level_gp`,
        `referral_source` and `high_clinical_or_social_needs`, which the
        dataset's own documentation says an urgency agent must read. See
        ADR-008 -- that is a change request against this service, not
        something to work around here.
        """
        response = self._client.get(f"/referrals/{hospital_hipe}/{pathway_number}/context")
        if response.status_code == 404:
            raise ReferralNotFoundError(f"no such referral: {hospital_hipe}/{pathway_number}")
        _raise_for_unexpected_status(response, expected=200)
        result: dict[str, Any] = response.json()
        return result

    def get_cohort(self, hospital_hipe: str, as_of_date: date) -> dict[str, Any]:
        """FR10: every referral still on the waiting list that day -- used to
        find which referrals need an urgency score, not to compute one."""
        response = self._client.get(f"/hospitals/{hospital_hipe}/cohort/{as_of_date.isoformat()}")
        _raise_for_unexpected_status(response, expected=200)
        result: dict[str, Any] = response.json()
        return result

    def get_scores_for_run(self, run_id: str, hospital_hipe: str) -> dict[str, Any]:
        """FR10: every urgency/capacity score already written for this
        run+hospital, grouped by pathway then agent -- used here only to
        verify POST /scores' round trip (test_run_integration.py); the
        urgency agent itself never reads its own scores back."""
        response = self._client.get(f"/runs/{run_id}/hospitals/{hospital_hipe}/scores")
        _raise_for_unexpected_status(response, expected=200)
        result: dict[str, Any] = response.json()
        return result

    def post_score(
        self,
        *,
        run_id: str,
        hospital_hipe: str,
        pathway_number: str,
        as_of_date: date,
        score: float,
        method: str,
        agent_version: str,
        citations: list[Citation],
    ) -> None:
        """FR2: writes `agent.agent_scores` + `agent_citations`, then
        projects `eat:Score`/`eat:cites` into the graph -- one call, per
        ADR-002.

        `agent_name` is hard-coded to `"urgency"` rather than taken as a
        parameter (capacity's equivalent accepts it). `AgentName` is
        `Literal["urgency", "capacity"]`, and a score written under the wrong
        name would be read by the coordinator as the *other* agent's
        judgement -- in range, plausible, and wrong. This client can only
        ever write as the agent it belongs to.

        Raises `GraphProjectionFailedError` on the service's 207 (row
        written, graph projection failed) and `RetrievalServiceError` on any
        other non-2xx (400 means nothing was written at all).
        """
        payload = {
            "run_id": run_id,
            "agent_name": "urgency",
            "hospital_hipe": hospital_hipe,
            "pathway_number": pathway_number,
            "as_of_date": as_of_date.isoformat(),
            "score": score,
            "method": method,
            "agent_version": agent_version,
            "citations": [
                {"evidence_type": c.evidence_type, "evidence_key": c.evidence_key}
                for c in citations
            ],
        }
        response = self._client.post("/scores", json=payload)
        if response.status_code == 207:
            detail = response.json().get("detail", response.text)
            raise GraphProjectionFailedError(detail)
        _raise_for_unexpected_status(response, expected=200)
