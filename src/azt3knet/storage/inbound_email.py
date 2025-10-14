"""Persistence helpers for inbound emails received through Mailjet webhooks."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from typing import Any, Mapping, Sequence
import uuid

from azt3knet.services.link_verifier import LinkCheckResult

try:  # pragma: no cover - import guard
    from sqlalchemy import Select, select
    from sqlalchemy.exc import SQLAlchemyError
    from sqlalchemy.orm import Session
    _SQLALCHEMY_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover - environments without SQLAlchemy
    Select = Any  # type: ignore[assignment]
    Session = Any  # type: ignore[assignment]

    class SQLAlchemyError(Exception):
        """Fallback error used when SQLAlchemy isn't installed."""

    def select(*args: Any, **kwargs: Any) -> None:  # type: ignore[override]
        raise RuntimeError("sqlalchemy is required for persistent storage support")

    _SQLALCHEMY_AVAILABLE = False

from .db import EngineBundle, SyncSessionFactory

if _SQLALCHEMY_AVAILABLE:
    from .models.inbound_email import InboundEmailRecord
else:  # pragma: no cover - provide a lightweight stand-in for unit tests

    @dataclass
    class InboundEmailRecord:  # type: ignore[too-many-instance-attributes]
        """In-memory representation when SQLAlchemy is unavailable."""

        id: uuid.UUID
        message_id: str | None
        recipient: str
        sender: str
        subject: str
        text_body: str
        html_body: str
        links: list[str]
        link_results: list[dict[str, Any]]
        attachments: list[dict[str, Any]]
        raw_payload: dict[str, Any]
        attachment_count: int
        created_at: datetime


@dataclass(frozen=True)
class AttachmentMetadata:
    """Summary of an attachment associated with an inbound email."""

    filename: str | None
    content_type: str | None
    size: int | None

    def as_payload(self) -> dict[str, object | None]:
        return {
            "filename": self.filename,
            "content_type": self.content_type,
            "size": self.size,
        }


@dataclass(frozen=True)
class InboundEmail:
    """Representation of an inbound email ready for persistence."""

    recipient: str
    sender: str
    subject: str
    text_body: str
    html_body: str
    message_id: str | None = None
    links: Sequence[str] = field(default_factory=list)
    link_checks: Sequence[LinkCheckResult] = field(default_factory=list)
    attachments: Sequence[AttachmentMetadata] = field(default_factory=list)
    raw_payload: Mapping[str, Any] = field(default_factory=dict)

    @property
    def attachment_count(self) -> int:
        return len(self.attachments)


@dataclass
class StoredInboundEmail:
    """Materialised view of a persisted inbound email."""

    id: uuid.UUID
    recipient: str
    sender: str
    subject: str
    text_body: str
    html_body: str
    message_id: str | None
    links: list[str]
    link_checks: list[LinkCheckResult]
    attachments: list[AttachmentMetadata]
    raw_payload: dict[str, Any]
    attachment_count: int
    created_at: datetime


class InboundEmailPersistenceError(RuntimeError):
    """Raised when the storage layer cannot persist inbound emails."""


if _SQLALCHEMY_AVAILABLE:

    class InboundEmailRepository:
        """Persist and retrieve inbound email records using SQLAlchemy."""

        def __init__(self, session_factory: SyncSessionFactory) -> None:
            self._session_factory = session_factory

        @classmethod
        def from_engine(
            cls,
            bundle: EngineBundle,
        ) -> "InboundEmailRepository":
            if bundle.is_async:
                raise InboundEmailPersistenceError(
                    "InboundEmailRepository requires a synchronous SQLAlchemy engine",
                )
            return cls(bundle.session_factory)

        def persist_email(self, email: InboundEmail) -> StoredInboundEmail:
            session = self._session_factory()
            try:
                record = self._persist(session, email)
                session.commit()
                session.refresh(record)
                return self._to_dataclass(record)
            except SQLAlchemyError as exc:  # pragma: no cover - defensive
                session.rollback()
                raise InboundEmailPersistenceError("Failed to persist inbound email") from exc
            finally:
                session.close()

        def _persist(self, session: Session, email: InboundEmail) -> InboundEmailRecord:
            payload = _json_clone(email.raw_payload)
            link_results = [result.as_payload() for result in email.link_checks]
            attachments = [metadata.as_payload() for metadata in email.attachments]

            if email.message_id:
                existing = session.execute(
                    select(InboundEmailRecord).where(InboundEmailRecord.message_id == email.message_id)
                ).scalar_one_or_none()
            else:
                existing = None

            if existing:
                existing.recipient = email.recipient
                existing.sender = email.sender
                existing.subject = email.subject
                existing.text_body = email.text_body
                existing.html_body = email.html_body
                existing.links = list(email.links)
                existing.link_results = link_results
                existing.attachments = attachments
                existing.raw_payload = payload
                existing.attachment_count = email.attachment_count
                return existing

            record = InboundEmailRecord(
                id=uuid.uuid4(),
                message_id=email.message_id,
                recipient=email.recipient,
                sender=email.sender,
                subject=email.subject,
                text_body=email.text_body,
                html_body=email.html_body,
                links=list(email.links),
                link_results=link_results,
                attachments=attachments,
                raw_payload=payload,
                attachment_count=email.attachment_count,
            )
            session.add(record)
            return record

        def _to_dataclass(self, record: InboundEmailRecord) -> StoredInboundEmail:
            return StoredInboundEmail(
                id=record.id,
                recipient=record.recipient,
                sender=record.sender,
                subject=record.subject,
                text_body=record.text_body,
                html_body=record.html_body,
                message_id=record.message_id,
                links=list(record.links or []),
                link_checks=[_link_from_dict(data) for data in record.link_results or []],
                attachments=[_attachment_from_dict(data) for data in record.attachments or []],
                raw_payload=dict(record.raw_payload or {}),
                attachment_count=record.attachment_count,
                created_at=record.created_at,
            )

else:

    class InboundEmailRepository:
        """In-memory repository used when SQLAlchemy is unavailable."""

        def __init__(self, session_factory: SyncSessionFactory | None = None) -> None:
            if session_factory is not None:
                raise InboundEmailPersistenceError(
                    "Persistent storage requires SQLAlchemy; use InboundEmailRepository() without a session factory",
                )
            self._records: dict[uuid.UUID, StoredInboundEmail] = {}
            self._message_index: dict[str, uuid.UUID] = {}

        @classmethod
        def from_engine(
            cls,
            bundle: EngineBundle,
        ) -> "InboundEmailRepository":
            raise InboundEmailPersistenceError(
                "sqlalchemy is not installed; persistent storage is unavailable in this environment",
            )

        def persist_email(self, email: InboundEmail) -> StoredInboundEmail:
            if email.message_id and email.message_id in self._message_index:
                record_id = self._message_index[email.message_id]
                stored = self._records[record_id]
                updated = self._create_record(email, record_id, stored.created_at)
                self._records[record_id] = updated
                return updated

            record_id = uuid.uuid4()
            created_at = datetime.now(timezone.utc)
            stored = self._create_record(email, record_id, created_at)
            self._records[record_id] = stored
            if email.message_id:
                self._message_index[email.message_id] = record_id
            return stored

        def _create_record(
            self,
            email: InboundEmail,
            record_id: uuid.UUID,
            created_at: datetime,
        ) -> StoredInboundEmail:
            return StoredInboundEmail(
                id=record_id,
                recipient=email.recipient,
                sender=email.sender,
                subject=email.subject,
                text_body=email.text_body,
                html_body=email.html_body,
                message_id=email.message_id,
                links=list(email.links),
                link_checks=[LinkCheckResult(**result.as_payload()) for result in email.link_checks],
                attachments=[
                    AttachmentMetadata(**metadata.as_payload()) for metadata in email.attachments
                ],
                raw_payload=_json_clone(email.raw_payload),
                attachment_count=email.attachment_count,
                created_at=created_at,
            )


def _json_clone(value: Mapping[str, Any] | Sequence[Any] | object) -> Any:
    """Ensure complex structures are converted to JSON primitives."""

    try:
        return json.loads(json.dumps(value))  # type: ignore[arg-type]
    except TypeError:
        if isinstance(value, Mapping):
            return {str(key): _json_clone(item) for key, item in value.items()}
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            return [_json_clone(item) for item in value]
        return str(value)


def _link_from_dict(data: Mapping[str, Any]) -> LinkCheckResult:
    return LinkCheckResult(
        url=str(data.get("url", "")),
        status_code=data.get("status_code"),
        ok=bool(data.get("ok", False)),
        final_url=data.get("final_url"),
        error=data.get("error"),
    )


def _attachment_from_dict(data: Mapping[str, Any]) -> AttachmentMetadata:
    return AttachmentMetadata(
        filename=data.get("filename"),
        content_type=data.get("content_type"),
        size=data.get("size"),
    )


__all__ = [
    "AttachmentMetadata",
    "InboundEmail",
    "InboundEmailPersistenceError",
    "InboundEmailRepository",
    "LinkCheckResult",
    "StoredInboundEmail",
]

