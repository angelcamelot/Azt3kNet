"""Application configuration utilities without external dependencies."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass
class Settings:
    """Central application settings."""

    environment: str = os.getenv("AZT3KNET_ENVIRONMENT", "development")
    default_seed: str = os.getenv("AZT3KNET_DEFAULT_SEED", "azt3knet")
    preview_limit: int = int(os.getenv("AZT3KNET_PREVIEW_LIMIT", "25"))
    compliance_enabled: bool = os.getenv("AZT3KNET_COMPLIANCE_ENABLED", "true").lower() in (
        "1",
        "true",
        "yes",
    )

    def __post_init__(self) -> None:
        if self.preview_limit < 1:
            raise ValueError("preview_limit must be at least 1")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the memoized settings instance."""

    return Settings()


def resolve_seed(seed: str | None) -> str:
    """Return the provided seed or fall back to the configured default."""

    if seed:
        return seed
    return get_settings().default_seed
