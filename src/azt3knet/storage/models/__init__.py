"""Declarative models used by the storage layer."""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base declarative class for SQLAlchemy ORM mappings."""


__all__ = ["Base"]

