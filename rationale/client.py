"""HTTP client for the retrieval service.

The rationale layer deliberately has no Postgres or SPARQL client. It consumes
the retrieval service's resolved evidence endpoints, keeping ADR-002's single
mediator boundary intact.
"""

from __future__ import annotations

from types import TracebackType
from typing import Any

import httpx


class RetrievalServiceError(RuntimeError):
    """Raised when the retrieval service rejects or fails a request."""


def _raise_for_unexpected_status(response: httpx.Response, *, expected: int) -> None:
    if response.status_code != expected:
        raise RetrievalServiceError(
            f"retrieval service returned {response.status_code} for "
            f"{response.request.method} {response.request.url}: {response.text}"
        )


class RetrievalClient:
    """Thin client for retrieval-service_20260904 rationale inputs."""

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

    def get_decision(self, hospital_hipe: str, as_of_date: str) -> dict[str, Any]:
        """Return one hospital-day decision with resolved placement evidence."""
        response = self._client.get(f"/decisions/{hospital_hipe}/{as_of_date}")
        _raise_for_unexpected_status(response, expected=200)
        result: dict[str, Any] = response.json()
        return result

    def get_placement_evidence(
        self,
        hospital_hipe: str,
        as_of_date: str,
        pathway_number: str,
        *,
        role: str | None = None,
    ) -> dict[str, Any]:
        """Return resolved evidence for one ranked placement."""
        params = {"role": role} if role else None
        response = self._client.get(
            f"/evidence/{hospital_hipe}/{as_of_date}/{pathway_number}",
            params=params,
        )
        _raise_for_unexpected_status(response, expected=200)
        result: dict[str, Any] = response.json()
        return result
