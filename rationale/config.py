"""Runtime configuration for the rationale CLI.

The rationale layer is a caller of retrieval-service_20260904, so it reuses
the same root `.env` values as the urgency agent, capacity agent and
coordinator. A tiny `.env` reader is used here rather than adding a dependency
just to support local CLI runs from Codex.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    """Load simple KEY=VALUE entries without overriding the shell."""
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"


@dataclass(frozen=True)
class Settings:
    """Configuration needed to call the retrieval service, plus the `llm`
    render engine's OpenAI credentials (unused, and not required, by the
    default `deterministic` engine -- see llm_render.py)."""

    retrieval_base_url: str
    bearer_token: str
    openai_api_key: str | None = None
    openai_model: str = DEFAULT_OPENAI_MODEL


def load_settings() -> Settings:
    """Read retrieval URL and token from the shell or repo-root `.env`.

    Returns:
        Settings for the rationale client.

    Raises:
        RuntimeError: If no bearer token is configured.
    """
    _load_dotenv(_repo_root() / ".env")
    base_url = os.environ.get("RETRIEVAL_BASE_URL")
    if not base_url:
        port = os.environ.get("RETRIEVAL_PORT", "8000")
        base_url = f"http://localhost:{port}"

    token = os.environ.get("RETRIEVAL_BEARER_TOKENS", "").split(",")[0].strip()
    if not token:
        raise RuntimeError("RETRIEVAL_BEARER_TOKENS is not set in the environment or root .env")

    openai_api_key = os.environ.get("OPENAI_API_KEY", "").strip() or None
    openai_model = os.environ.get("OPENAI_MODEL", "").strip() or DEFAULT_OPENAI_MODEL

    return Settings(
        retrieval_base_url=base_url,
        bearer_token=token,
        openai_api_key=openai_api_key,
        openai_model=openai_model,
    )
