import os
from pathlib import Path

import pytest

from rationale import config


def test_load_settings_uses_first_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "_load_dotenv", lambda path: None)
    monkeypatch.setenv("RETRIEVAL_PORT", "8010")
    monkeypatch.setenv("RETRIEVAL_BEARER_TOKENS", "first,second")
    monkeypatch.delenv("RETRIEVAL_BASE_URL", raising=False)

    settings = config.load_settings()

    assert settings.retrieval_base_url == "http://localhost:8010"
    assert settings.bearer_token == "first"


def test_load_settings_reads_openai_key_and_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "_load_dotenv", lambda path: None)
    monkeypatch.setenv("RETRIEVAL_BEARER_TOKENS", "tok")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-real")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4.1")

    settings = config.load_settings()

    assert settings.openai_api_key == "sk-real"
    assert settings.openai_model == "gpt-4.1"


def test_load_settings_openai_key_defaults_to_none_and_model_to_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(config, "_load_dotenv", lambda path: None)
    monkeypatch.setenv("RETRIEVAL_BEARER_TOKENS", "tok")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)

    settings = config.load_settings()

    assert settings.openai_api_key is None
    assert settings.openai_model == config.DEFAULT_OPENAI_MODEL


def test_load_settings_requires_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "_load_dotenv", lambda path: None)
    monkeypatch.delenv("RETRIEVAL_BEARER_TOKENS", raising=False)

    with pytest.raises(RuntimeError, match="RETRIEVAL_BEARER_TOKENS"):
        config.load_settings()


def test_load_dotenv_does_not_override_shell(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("VALUE=from_file\nNEW_VALUE=yes\n", encoding="utf-8")
    monkeypatch.setenv("VALUE", "from_shell")
    monkeypatch.delenv("NEW_VALUE", raising=False)

    config._load_dotenv(env_path)

    assert os.environ["VALUE"] == "from_shell"
    assert os.environ["NEW_VALUE"] == "yes"
