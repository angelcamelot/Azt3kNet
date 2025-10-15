from __future__ import annotations
from typing import Any

__doc__ = """SQLAlchemy model describing inbound email records."""

import uuid
from datetime import datetime

from sqlalchemy import Index, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class InboundEmailRecord(Base):
    """ORM mapping for inbound emails received by the system."""

    __tablename__ = "inbound_emails"
    __table_args__ = (
        Index(
            "ux_inbound_emails_message_id",
            "message_id",
            unique=True,
            postgresql_where=text("message_id IS NOT NULL"),
        ),
        Index("ix_inbound_emails_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id: Mapped[str | None] = mapped_column(nullable=True)
    recipient: Mapped[str] = mapped_column(nullable=False)
    sender: Mapped[str] = mapped_column(nullable=False)
    subject: Mapped[str] = mapped_column(nullable=False, default="")
    text_body: Mapped[str] = mapped_column(nullable=False, default="")
    html_body: Mapped[str] = mapped_column(nullable=False, default="")
    links: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    link_results: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    attachments: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    attachment_count: Mapped[int] = mapped_column(nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())


__all__ = ["InboundEmailRecord"]

