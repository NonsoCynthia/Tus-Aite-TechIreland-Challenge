"""run.py tests: prompt composition and the API-key guard, exercised through
an injected fake `PipelineRunner` -- no `agents` package, no network, no key
needed. The real SDK call (`_default_pipeline_runner`) is exercised manually
against a live key; see README.md.
"""

from __future__ import annotations

import pytest

from orchestrator_agent.config import Settings
from orchestrator_agent.run import ask_question, run_pipeline


def _settings(*, openai_api_key: str | None = "sk-test") -> Settings:
    return Settings(
        openai_api_key=openai_api_key,
        openai_model="gpt-4.1-mini",
        retrieval_base_url="http://retrieval.test",
        bearer_token="tok",
    )


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
        settings=Settings(
            openai_api_key="sk-abc",
            openai_model="gpt-4.1",
            retrieval_base_url="http://retrieval.test",
            bearer_token="tok",
        ),
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


class _FakeAskRunner:
    def __init__(self, answer: str = "here's why") -> None:
        self.answer = answer
        self.calls: list[dict[str, object]] = []

    def __call__(
        self, *, history: list | None, question: str, model: str, api_key: str
    ) -> tuple[str, list]:
        self.calls.append(
            {"history": history, "question": question, "model": model, "api_key": api_key}
        )
        return self.answer, [*(history or []), {"role": "assistant", "content": self.answer}]


class TestAskQuestion:
    def test_starts_a_fresh_conversation_when_no_history_given(self) -> None:
        runner = _FakeAskRunner()

        answer, history = ask_question(
            "why is PW-1 ranked here?", settings=_settings(), runner=runner
        )

        assert answer == "here's why"
        assert runner.calls[0]["history"] is None
        assert runner.calls[0]["question"] == "why is PW-1 ranked here?"

    def test_continues_a_prior_conversation_when_history_given(self) -> None:
        runner = _FakeAskRunner()
        prior_history = [{"role": "user", "content": "first question"}]

        ask_question("a follow-up", settings=_settings(), history=prior_history, runner=runner)

        assert runner.calls[0]["history"] == prior_history

    def test_returns_updated_history_for_the_next_call(self) -> None:
        runner = _FakeAskRunner(answer="42")

        _, history = ask_question("how many?", settings=_settings(), runner=runner)

        assert {"role": "assistant", "content": "42"} in history

    def test_raises_runtime_error_when_no_api_key_configured(self) -> None:
        runner = _FakeAskRunner()

        with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
            ask_question("why?", settings=_settings(openai_api_key=None), runner=runner)
        assert runner.calls == []
