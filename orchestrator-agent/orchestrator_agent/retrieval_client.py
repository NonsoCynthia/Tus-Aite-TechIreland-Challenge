"""HTTP client for retrieval-service_20260904's read endpoints -- backs the
clinician Q&A mode's tools (tools.py). Read-only by construction: every
method here is a GET, matching the "read or trigger, never compute" bound
every tool in this package holds to (see tools.py's own module docstring).

A separate, smaller client from `rationale.client.RetrievalClient` (used
only by generate_rationale for GET /decisions) -- this one covers the wider
read surface (cohort, referral context, wait counters, evidence) the Q&A
mode needs, mirroring the same pattern already established in
capacity_agent/client.py and urgency_agent/client.py.
"""

from __future__ import annotations

from types import TracebackType
from typing import Any

import httpx


class RetrievalClientError(RuntimeError):
    """A non-2xx response, or a request-level failure, from the retrieval
    service."""


class RetrievalClient:
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

    def _get(self, path: str, *, params: dict[str, str] | None = None) -> dict[str, Any]:
        response = self._client.get(path, params=params)
        if response.status_code >= 400:
            raise RetrievalClientError(
                f"retrieval service returned {response.status_code} for GET {path}: "
                f"{response.text}"
            )
        result: dict[str, Any] = response.json()
        return result

    def get_referral_context(self, hospital_hipe: str, pathway_number: str) -> dict[str, Any]:
        """FR9: observations, conditions, triage events, and capacity data
        for one referral."""
        return self._get(f"/referrals/{hospital_hipe}/{pathway_number}/context")

    def get_wait_counters(
        self, hospital_hipe: str, pathway_number: str, as_of_date: str
    ) -> dict[str, Any]:
        """FR3: the four wait-time counters, via kg/queries/wait_counters.rq."""
        return self._get(
            f"/referrals/{hospital_hipe}/{pathway_number}/wait-counters",
            params={"as_of_date": as_of_date},
        )

    def get_cohort(self, hospital_hipe: str, as_of_date: str) -> dict[str, Any]:
        """FR10: every referral still on the waiting list that day, with CPC
        and computed CRT breach."""
        return self._get(f"/hospitals/{hospital_hipe}/cohort/{as_of_date}")

    def get_decision(self, hospital_hipe: str, as_of_date: str) -> dict[str, Any]:
        """FR8: the full ranked list for that hospital-day, with resolved
        evidence per placement."""
        return self._get(f"/decisions/{hospital_hipe}/{as_of_date}")

    def get_evidence(
        self,
        hospital_hipe: str,
        as_of_date: str,
        pathway_number: str,
        *,
        role: str | None = None,
    ) -> dict[str, Any]:
        """FR8: one ranked placement's cited evidence, resolved. `role`
        narrows to one of urgency/capacity/timeframe/multi_list; omit for
        all four."""
        params = {"role": role} if role else None
        return self._get(
            f"/evidence/{hospital_hipe}/{as_of_date}/{pathway_number}", params=params
        )
