"""Runtime configuration, read from environment variables.

Reuses `RETRIEVAL_BEARER_TOKENS` and `RETRIEVAL_PORT` -- the same root
`.env` retrieval-service_20260904 itself reads (conductor/tech-stack.md's
Environment Variables table) -- rather than inventing a second token/port
pair, so a local dev setup has one source of truth for the credential every
caller of that service presents.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    retrieval_base_url: str = "http://localhost:8000"
    retrieval_bearer_tokens: str = "change_me_locally"

    @property
    def bearer_token(self) -> str:
        # The service accepts any one of a comma-separated set (spec.md
        # NFR4); a caller only ever needs to present one.
        return self.retrieval_bearer_tokens.split(",")[0].strip()


settings = Settings()
