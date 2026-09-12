"""Runtime configuration for the orchestrator agent.

Reuses the same root `.env` every other package in this repo reads from
(rationale/config.py, capacity_agent/config.py, ...) -- one source of truth
for `OPENAI_API_KEY`/`OPENAI_MODEL`. This package's *trigger* tools
(tools.py's run_urgency_agent/run_capacity_agent/run_coordinator) don't need
their own copy of the retrieval bearer token -- they shell out to the root
Makefile's `*-run` targets, which read `.env` themselves. `generate_rationale`
reuses `rationale.config.load_settings()` directly (see tools.py) rather than
duplicating that logic here.
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


def load_settings() -> Settings:
    """Read OpenAI credentials from the shell or repo-root `.env`.

    Returns:
        Settings for the orchestrator agent. `openai_api_key` may be `None`
        -- callers that need it (run.run_pipeline) check and report that
        clearly rather than letting the SDK fail with an opaque auth error.
    """
    _load_dotenv(repo_root() / ".env")
    openai_api_key = os.environ.get("OPENAI_API_KEY", "").strip() or None
    openai_model = os.environ.get("OPENAI_MODEL", "").strip() or DEFAULT_OPENAI_MODEL
    return Settings(openai_api_key=openai_api_key, openai_model=openai_model)
