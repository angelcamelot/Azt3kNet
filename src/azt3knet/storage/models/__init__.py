"""Declarative models used by the storage layer."""

from __future__ import annotations

try:  # pragma: no cover - import guard
    from sqlalchemy.orm import DeclarativeBase
except ModuleNotFoundError:  # pragma: no cover - minimal environments

    class Base:  # type: ignore[too-few-public-methods]
        """Fallback placeholder used when SQLAlchemy is unavailable."""

        pass

else:

    class Base(DeclarativeBase):
        """Base declarative class for SQLAlchemy ORM mappings."""


__all__ = ["Base"]

