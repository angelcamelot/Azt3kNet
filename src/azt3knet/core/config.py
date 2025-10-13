"""Application configuration utilities without external dependencies."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Callable

from .seeds import SeedSequence


_TRUE_VALUES = {"1", "true", "yes"}


def _env_factory(name: str, default: str) -> Callable[[], str]:
    """Return a default factory that reads a string environment variable."""

    return lambda: os.getenv(name, default)


def _int_env_factory(name: str, default: str) -> Callable[[], int]:
    """Return a default factory that reads an integer environment variable."""

    return lambda: int(os.getenv(name, default))


def _bool_env_factory(name: str, default: str) -> Callable[[], bool]:
    """Return a default factory that reads a boolean environment variable."""

    return lambda: os.getenv(name, default).lower() in _TRUE_VALUES


@dataclass
class Settings:
    """Central application settings."""

    environment: str = field(
        default_factory=_env_factory("AZT3KNET_ENVIRONMENT", "development")
    )
    default_seed: str = field(
        default_factory=_env_factory("AZT3KNET_DEFAULT_SEED", "azt3knet")
    )
    preview_limit: int = field(
        default_factory=_int_env_factory("AZT3KNET_PREVIEW_LIMIT", "25")
    )
    compliance_enabled: bool = field(
        default_factory=_bool_env_factory("AZT3KNET_COMPLIANCE_ENABLED", "true")
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


def derive_seed_components(seed: str | None, *, namespace: str) -> tuple[str, int]:
    """Return the resolved seed and a numeric derivation for a namespace."""

    resolved_seed = resolve_seed(seed)
    numeric_seed = SeedSequence(resolved_seed).derive(namespace)
    return resolved_seed, numeric_seed
