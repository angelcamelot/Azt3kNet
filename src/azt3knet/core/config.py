"""Application configuration utilities."""

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Central application settings.

    The first sprint focuses on deterministic agent generation, so only a
    handful of toggles are required. Future sprints can extend this model with
    database, queue, and telemetry configuration while keeping a single source
    of truth for both CLI and API layers.
    """

    environment: str = Field(
        "development",
        description="Deployment environment label used for logging and metrics.",
    )
    default_seed: str = Field(
        "azt3knet",
        description=(
            "Fallback seed that guarantees deterministic behaviour whenever a "
            "command does not provide one explicitly."
        ),
    )
    preview_limit: int = Field(
        25,
        ge=1,
        description=(
            "Upper bound for preview responses to avoid overwhelming the CLI or "
            "API clients during the exploratory phase."
        ),
    )
    compliance_enabled: bool = Field(
        True,
        description="Global switch that allows turning moderation logic on/off for tests.",
    )

    model_config = {
        "env_prefix": "AZT3KNET_",
        "extra": "ignore",
    }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the memoized settings instance.

    Settings are cached so every component (CLI, API, background jobs) can
    access a consistent configuration view without repeatedly reading
    environment variables. The helper is intentionally tiny to keep the first
    sprint lightweight.
    """

    return Settings()


def resolve_seed(seed: Optional[str]) -> str:
    """Return the provided seed or fall back to the configured default."""

    if seed:
        return seed
    return get_settings().default_seed
