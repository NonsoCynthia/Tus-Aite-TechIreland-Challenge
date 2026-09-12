"""run.py tests: prompt composition and the API-key guard, exercised through
an injected fake `PipelineRunner` -- no `agents` package, no network, no key
needed. The real SDK call (`_default_pipeline_runner`) is exercised manually
against a live key; see README.md.
"""

from __future__ import annotations

import pytest

from orchestrator_agent.config import Settings
from orchestrator_agent.run import run_pipeline


def _settings(*, openai_api_key: str | None = "sk-test") -> Settings:
    return Settings(openai_api_key=openai_api_key, openai_model="gpt-4.1-mini")


class _FakeRunner:
    def __init__(self, output: str = "done") -> None:
        self.output = output
        self.calls: list[dict[str, str]] = []

    def __call__(self, *, prompt: str, model: str, api_key: str) -> str:
        self.calls.append({"prompt": prompt, "model": model, "api_key": api_key})
        return self.output


def test_prompt_names_every_pipeline_parameter() -> None:
    runner = _FakeRunner()

    run_pipeline("9001", "2026-08-30", "run-1", settings=_settings(), runner=runner)

    prompt = runner.calls[0]["prompt"]
    assert "9001" in prompt
    assert "2026-08-30" in prompt
    assert "run-1" in prompt


def test_returns_the_runners_output() -> None:
    runner = _FakeRunner(output="pipeline complete, 12 referrals ranked")

    result = run_pipeline("9001", "2026-08-30", "run-1", settings=_settings(), runner=runner)

    assert result == "pipeline complete, 12 referrals ranked"


def test_passes_model_and_api_key_through() -> None:
    runner = _FakeRunner()

    run_pipeline(
        "9001",
        "2026-08-30",
        "run-1",
        settings=Settings(openai_api_key="sk-abc", openai_model="gpt-4.1"),
        runner=runner,
    )

    assert runner.calls[0]["api_key"] == "sk-abc"
    assert runner.calls[0]["model"] == "gpt-4.1"


def test_raises_runtime_error_when_no_api_key_configured() -> None:
    runner = _FakeRunner()

    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        run_pipeline(
            "9001", "2026-08-30", "run-1", settings=_settings(openai_api_key=None), runner=runner
        )
    assert runner.calls == []
