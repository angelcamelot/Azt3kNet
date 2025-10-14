"""Database configuration helpers for SQLAlchemy engines and sessions."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Protocol

try:  # pragma: no cover - import guard
    from sqlalchemy import create_engine
    from sqlalchemy.engine import Engine
    from sqlalchemy.ext.asyncio import (
        AsyncEngine,
        AsyncSession,
        async_sessionmaker,
        create_async_engine,
    )
    from sqlalchemy.orm import Session, sessionmaker
    _SQLALCHEMY_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover - gracefully degrade in minimal envs
    Engine = AsyncEngine = Session = AsyncSession = object  # type: ignore[assignment]
    _SQLALCHEMY_AVAILABLE = False

    def create_engine(*args: Any, **kwargs: Any) -> Engine:  # type: ignore[override]
        raise ModuleNotFoundError("sqlalchemy is required for persistent storage support")

    def create_async_engine(*args: Any, **kwargs: Any) -> AsyncEngine:  # type: ignore[override]
        raise ModuleNotFoundError("sqlalchemy is required for persistent storage support")

    def sessionmaker(*args: Any, **kwargs: Any) -> Any:  # type: ignore[override]
        raise ModuleNotFoundError("sqlalchemy is required for persistent storage support")

    def async_sessionmaker(*args: Any, **kwargs: Any) -> Any:  # type: ignore[override]
        raise ModuleNotFoundError("sqlalchemy is required for persistent storage support")


class DatabaseConfigurationError(RuntimeError):
    """Raised when the storage layer cannot be configured."""


class SyncSessionFactory(Protocol):
    """Typing protocol for factories that create ``Session`` instances."""

    def __call__(self) -> Session:  # pragma: no cover - typing helper
        """Return a new synchronous SQLAlchemy ``Session``."""


class AsyncSessionFactory(Protocol):
    """Typing protocol for factories that create ``AsyncSession`` instances."""

    def __call__(self) -> AsyncSession:  # pragma: no cover - typing helper
        """Return a new asynchronous SQLAlchemy ``AsyncSession``."""


@dataclass(frozen=True)
class EngineBundle:
    """Container bundling an engine together with its session factory."""

    engine: Engine | AsyncEngine
    session_factory: SyncSessionFactory | AsyncSessionFactory

    @property
    def is_async(self) -> bool:
        """Return whether the wrapped engine is asynchronous."""

        return isinstance(self.engine, AsyncEngine)


def _require_database_url(database_url: str | None) -> str:
    if not database_url:
        raise DatabaseConfigurationError(
            "DATABASE_URL environment variable is required to configure storage",
        )
    return database_url


def create_engine_from_url(
    database_url: str | None = None,
    *,
    async_io: bool | None = None,
    engine_kwargs: dict[str, Any] | None = None,
) -> EngineBundle:
    """Create an SQLAlchemy engine from a URL.

    Parameters
    ----------
    database_url:
        Optional database URL. When omitted the ``DATABASE_URL`` environment
        variable will be consulted.
    async_io:
        Force asynchronous engine creation. When ``None`` the driver component
        of the URL is inspected to infer whether the engine should be async.
    engine_kwargs:
        Additional keyword arguments passed directly to the SQLAlchemy engine
        constructor.
    """

    if not _SQLALCHEMY_AVAILABLE:
        raise DatabaseConfigurationError(
            "sqlalchemy is not installed; persistent storage is unavailable in this environment",
        )

    url = _require_database_url(database_url or os.getenv("DATABASE_URL"))
    driver = url.split("+", 1)[-1] if "+" in url else url
    inferred_async = driver.startswith("asyncpg") or "aiosqlite" in driver
    use_async = async_io if async_io is not None else inferred_async

    kwargs = {"pool_pre_ping": True, "future": True}
    if engine_kwargs:
        kwargs.update(engine_kwargs)

    if use_async:
        engine = create_async_engine(url, **kwargs)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        return EngineBundle(engine=engine, session_factory=session_factory)

    engine = create_engine(url, **kwargs)
    session_factory = sessionmaker(engine, expire_on_commit=False)
    return EngineBundle(engine=engine, session_factory=session_factory)


__all__ = [
    "AsyncSessionFactory",
    "DatabaseConfigurationError",
    "EngineBundle",
    "SyncSessionFactory",
    "create_engine_from_url",
]

