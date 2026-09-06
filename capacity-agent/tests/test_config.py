"""Settings.bearer_token picks the first of a comma-separated
RETRIEVAL_BEARER_TOKENS -- the same env var retrieval-service_20260904
itself reads, so both sides of the connection have one source of truth."""

from __future__ import annotations

from capacity_agent.config import Settings


def test_bearer_token_takes_the_first_of_a_comma_separated_list() -> None:
    settings = Settings(retrieval_bearer_tokens="tok-a, tok-b ,tok-c")
    assert settings.bearer_token == "tok-a"


def test_bearer_token_strips_whitespace_around_a_single_token() -> None:
    settings = Settings(retrieval_bearer_tokens="  tok-only  ")
    assert settings.bearer_token == "tok-only"
