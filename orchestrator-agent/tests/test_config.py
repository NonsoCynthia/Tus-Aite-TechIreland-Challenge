from __future__ import annotations

import pytest

from orchestrator_agent import config


def test_load_settings_reads_openai_key_and_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "_load_dotenv", lambda path: None)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-real")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4.1")

    settings = config.load_settings()

    assert settings.openai_api_key == "sk-real"
    assert settings.openai_model == "gpt-4.1"


def test_load_settings_defaults_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "_load_dotenv", lambda path: None)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)

    settings = config.load_settings()

    assert settings.openai_api_key is None
    assert settings.openai_model == config.DEFAULT_OPENAI_MODEL


def test_repo_root_is_the_actual_repo_root() -> None:
    root = config.repo_root()

    assert (root / "orchestrator-agent").is_dir()
    assert (root / "rationale").is_dir()
    assert (root / "Makefile").is_file()
