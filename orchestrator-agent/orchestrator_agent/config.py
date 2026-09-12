"""Runtime configuration for the orchestrator agent.

Reuses the same root `.env` every other package in this repo reads from
(rationale/config.py, capacity_agent/config.py, ...) -- one source of truth
for `OPENAI_API_KEY`/`OPENAI_MODEL` and the retrieval service's bearer
token. This package's *trigger* tools (tools.py's
run_urgency_agent/run_capacity_agent/run_coordinator) don't need
`retrieval_base_url`/`bearer_token` -- they shell out to the root
Makefile's `*-run` targets, which read `.env` themselves. The *read* tools
(get_referral_context, get_cohort, get_decision, get_evidence,
get_wait_counters -- retrieval_client.py) do, for the clinician Q&A mode.
`generate_rationale` reuses `rationale.config.load_settings()` directly
(see tools.py) rather than a third copy of this logic.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"


def repo_root() -> Path:
    """orchestrator-agent/orchestrator_agent/config.py -> repo root."""
    return Path(__file__).resolve().parent.parent.parent


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


@dataclass(frozen=True)
class Settings:
    openai_api_key: str | None
    openai_model: str
    retrieval_base_url: str
    bearer_token: str


def load_settings() -> Settings:
    """Read OpenAI credentials and retrieval connection details from the
    shell or repo-root `.env`.

    Returns:
        Settings for the orchestrator agent. `openai_api_key` may be `None`
        -- callers that need it (run.run_pipeline/run.ask_question) check
        and report that clearly rather than letting the SDK fail with an
        opaque auth error. `bearer_token` may be empty -- only the read
        tools (Q&A mode) need it; the pipeline-only path never calls them.
    """
    _load_dotenv(repo_root() / ".env")
    openai_api_key = os.environ.get("OPENAI_API_KEY", "").strip() or None
    openai_model = os.environ.get("OPENAI_MODEL", "").strip() or DEFAULT_OPENAI_MODEL

    base_url = os.environ.get("RETRIEVAL_BASE_URL", "").strip()
    if not base_url:
        port = os.environ.get("RETRIEVAL_PORT", "8000").strip()
        base_url = f"http://localhost:{port}"
    bearer_token = os.environ.get("RETRIEVAL_BEARER_TOKENS", "").split(",")[0].strip()

    return Settings(
        openai_api_key=openai_api_key,
        openai_model=openai_model,
        retrieval_base_url=base_url,
        bearer_token=bearer_token,
    )
