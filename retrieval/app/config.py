"""Runtime configuration, read from environment variables.

Field names match the desired environment variable names case-insensitively
(pydantic-settings' default), so `RETRIEVAL_*` and the project-wide
`OXIGRAPH_*` names (conductor/tech-stack.md's Environment Variables table)
can both be read without a blanket prefix.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    retrieval_bearer_tokens: str = "change_me_locally"
    retrieval_db_url: str = "postgresql://retrieval_rw:change_me_locally@db:5432/triage"
    oxigraph_query_url: str = "http://localhost:7878/query"
    oxigraph_update_url: str = "http://localhost:7878/update"

    @property
    def valid_tokens(self) -> set[str]:
        return {t.strip() for t in self.retrieval_bearer_tokens.split(",") if t.strip()}


settings = Settings()
