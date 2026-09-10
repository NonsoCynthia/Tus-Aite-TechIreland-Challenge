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
