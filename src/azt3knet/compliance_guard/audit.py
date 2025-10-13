"""Immutable audit log structures for compliance review."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Mapping, Tuple


def _freeze_metadata(metadata: Mapping[str, str] | None) -> tuple[tuple[str, str], ...]:
    """Return an immutable, sorted representation of the metadata."""

    if not metadata:
        return ()
    items = [(str(key), str(value)) for key, value in metadata.items()]
    items.sort()
    return tuple(items)


@dataclass(frozen=True)
class AuditEvent:
    """Snapshot describing a compliance decision for generated content."""

    timestamp: datetime
    source: str
    field_name: str
    content: str
    approved: bool
    labels: tuple[str, ...]
    metadata: tuple[tuple[str, str], ...]


class AuditLog:
    """In-memory immutable audit trail for compliance guard decisions."""

    def __init__(self) -> None:
        self._events: list[AuditEvent] = []

    def record(
        self,
        *,
        source: str,
        field_name: str,
        content: str,
        approved: bool,
        labels: Iterable[str],
        metadata: Mapping[str, str] | None = None,
    ) -> AuditEvent:
        """Append an immutable event to the audit log."""

        event = AuditEvent(
            timestamp=datetime.now(timezone.utc),
            source=source,
            field_name=field_name,
            content=content,
            approved=approved,
            labels=tuple(labels),
            metadata=_freeze_metadata(metadata),
        )
        self._events.append(event)
        return event

    def export(self) -> tuple[AuditEvent, ...]:
        """Return a tuple copy of the recorded events for external storage."""

        return tuple(self._events)


__all__ = ["AuditEvent", "AuditLog", "_freeze_metadata"]

