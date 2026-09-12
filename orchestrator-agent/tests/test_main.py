"""Smoke test for the CLI's argument parsing, subcommand dispatch, and the
missing-key guard -- run_pipeline/ask_question's own wiring is already
exercised by test_run.py."""

from __future__ import annotations

import pytest

from orchestrator_agent.__main__ import _parse_args, _run_chat_loop, main
from orchestrator_agent.config import Settings


def _settings(*, openai_api_key: str | None = "sk-test") -> Settings:
    return Settings(
        openai_api_key=openai_api_key,
        openai_model="gpt-4.1-mini",
        retrieval_base_url="http://retrieval.test",
        bearer_token="tok",
    )


class TestParseArgs:
    def test_parses_run_subcommand(self) -> None:
        args = _parse_args(
            ["run", "--hospital", "9001", "--as-of-date", "2026-08-30", "--run-id", "run-1"]
        )

        assert args.command == "run"
        assert args.hospital == "9001"
        assert args.as_of_date == "2026-08-30"
        assert args.run_id == "run-1"

    def test_parses_ask_subcommand(self) -> None:
        args = _parse_args(["ask", "why is PW-1 ranked here?"])

        assert args.command == "ask"
        assert args.question == "why is PW-1 ranked here?"

    def test_parses_chat_subcommand(self) -> None:
        args = _parse_args(["chat"])

        assert args.command == "chat"

    def test_requires_a_subcommand(self) -> None:
        with pytest.raises(SystemExit):
            _parse_args([])


class TestMain:
    def test_reports_and_exits_1_without_an_api_key(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        import orchestrator_agent.__main__ as entrypoint

        monkeypatch.setattr(entrypoint, "load_settings", lambda: _settings(openai_api_key=None))

        exit_code = main(
            ["run", "--hospital", "9001", "--as-of-date", "2026-08-30", "--run-id", "run-1"]
        )

        assert exit_code == 1
        assert "OPENAI_API_KEY" in capsys.readouterr().err

    def test_run_subcommand_calls_run_pipeline(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        import orchestrator_agent.__main__ as entrypoint

        monkeypatch.setattr(entrypoint, "load_settings", _settings)

        def fake_run_pipeline(
            hospital: str, as_of_date: str, run_id: str, *, settings: object
        ) -> str:
            return f"ran {hospital}/{as_of_date}/{run_id}"

        monkeypatch.setattr(entrypoint, "run_pipeline", fake_run_pipeline)

        exit_code = main(
            ["run", "--hospital", "9001", "--as-of-date", "2026-08-30", "--run-id", "run-1"]
        )

        assert exit_code == 0
        assert "ran 9001/2026-08-30/run-1" in capsys.readouterr().out

    def test_ask_subcommand_calls_ask_question(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        import orchestrator_agent.__main__ as entrypoint

        monkeypatch.setattr(entrypoint, "load_settings", _settings)
        monkeypatch.setattr(
            entrypoint,
            "ask_question",
            lambda question, *, settings, history=None: (f"answer to: {question}", []),
        )

        exit_code = main(["ask", "why is PW-1 ranked here?"])

        assert exit_code == 0
        assert "answer to: why is PW-1 ranked here?" in capsys.readouterr().out


class TestChatLoop:
    def test_prints_the_answer_and_exits_cleanly_on_eof(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        import orchestrator_agent.__main__ as entrypoint

        responses = iter(["why is PW-1 ranked here?"])

        def fake_input(prompt: str = "") -> str:
            try:
                return next(responses)
            except StopIteration:
                raise EOFError from None

        monkeypatch.setattr("builtins.input", fake_input)
        monkeypatch.setattr(
            entrypoint,
            "ask_question",
            lambda question, *, settings, history=None: (f"answer to: {question}", ["turn-1"]),
        )

        exit_code = _run_chat_loop(_settings())

        assert exit_code == 0
        assert "answer to: why is PW-1 ranked here?" in capsys.readouterr().out

    def test_exit_keyword_stops_the_loop_without_calling_ask_question(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import orchestrator_agent.__main__ as entrypoint

        monkeypatch.setattr("builtins.input", lambda prompt="": "exit")
        called = False

        def fake_ask(question: str, *, settings: object, history: object = None) -> tuple:
            nonlocal called
            called = True
            return "should not be called", []

        monkeypatch.setattr(entrypoint, "ask_question", fake_ask)

        exit_code = _run_chat_loop(_settings())

        assert exit_code == 0
        assert called is False

    def test_carries_history_across_turns(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        import orchestrator_agent.__main__ as entrypoint

        responses = iter(["first question", "second question"])

        def fake_input(prompt: str = "") -> str:
            try:
                return next(responses)
            except StopIteration:
                raise EOFError from None

        monkeypatch.setattr("builtins.input", fake_input)
        seen_histories: list[object] = []

        def fake_ask(question: str, *, settings: object, history: object = None) -> tuple:
            seen_histories.append(history)
            return f"answer to {question}", ["accumulated-history"]

        monkeypatch.setattr(entrypoint, "ask_question", fake_ask)

        _run_chat_loop(_settings())

        assert seen_histories == [None, ["accumulated-history"]]
