"""SQLAlchemy model describing persisted agent metadata."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import Index, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class AgentRecord(Base):
    """ORM mapping describing persisted agent profiles."""

    __tablename__ = "agents"
    __table_args__ = (
        Index("ix_agents_username_hint", "username_hint", unique=True),
        Index("ix_agents_created_at", "created_at"),
        {
            "postgresql_partition_by": "RANGE (created_at)",
        },
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
    )
    seed: Mapped[str] = mapped_column(nullable=False)
    username_hint: Mapped[str] = mapped_column(nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
    )


__all__ = ["AgentRecord"]

