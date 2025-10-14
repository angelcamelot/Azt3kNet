"""SQLAlchemy-backed repository for agent persistence and retrieval."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence
import uuid

try:  # pragma: no cover - import guard
    from sqlalchemy import Select, select
    from sqlalchemy.exc import SQLAlchemyError
    from sqlalchemy.orm import Session
    _SQLALCHEMY_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover - minimal environments
    Select = Any  # type: ignore[assignment]
    Session = Any  # type: ignore[assignment]

    class SQLAlchemyError(Exception):
        """Fallback error used when SQLAlchemy isn't installed."""

    def select(*args: Any, **kwargs: Any) -> None:  # type: ignore[override]
        raise RuntimeError("sqlalchemy is required for persistent storage support")

    _SQLALCHEMY_AVAILABLE = False

from azt3knet.agent_factory.models import AgentProfile

from .db import EngineBundle, SyncSessionFactory

if _SQLALCHEMY_AVAILABLE:
    from .models.agent import AgentRecord
else:  # pragma: no cover - fallback representation for tests without SQLAlchemy
    @dataclass
    class AgentRecord:
        """Lightweight representation used when SQLAlchemy is unavailable."""

        id: uuid.UUID
        seed: str
        username_hint: str
        payload: dict[str, Any]
        embedding: list[float] | None = None


class AgentPersistenceError(RuntimeError):
    """Base exception for agent persistence failures."""


class AgentUniquenessError(AgentPersistenceError):
    """Raised when attempting to insert a conflicting agent record."""


@dataclass(frozen=True)
class VectorMatch:
    """Represents an agent matched via a vector search."""

    agent: AgentRecord
    distance: float


if _SQLALCHEMY_AVAILABLE:

    class AgentRepository:
        """Repository that manages the ``AgentRecord`` lifecycle."""

        def __init__(
            self,
            session_factory: SyncSessionFactory,
            *,
            vector_search_enabled: bool = False,
        ) -> None:
            self._session_factory = session_factory
            self._vector_search_enabled = vector_search_enabled

        @classmethod
        def from_engine(
            cls,
            bundle: EngineBundle,
            *,
            vector_search_enabled: bool = False,
        ) -> "AgentRepository":
            if bundle.is_async:
                raise AgentPersistenceError(
                    "AgentRepository currently supports synchronous engines only",
                )
            return cls(bundle.session_factory, vector_search_enabled=vector_search_enabled)

        def persist_agents(
            self,
            agents: Iterable[AgentProfile],
            *,
            embeddings: Mapping[uuid.UUID, Sequence[float]] | None = None,
        ) -> int:
            """Persist ``AgentProfile`` instances ensuring uniqueness."""

            if embeddings is None:
                embeddings = {}

            inserted = 0
            session = self._session_factory()
            try:
                for agent in agents:
                    payload = agent.model_dump(mode="json")
                    vector = embeddings.get(agent.id)
                    inserted += self._persist_single(session, agent, payload, vector)
                session.commit()
            except AgentPersistenceError:
                session.rollback()
                raise
            except SQLAlchemyError as exc:  # pragma: no cover - defensive
                session.rollback()
                raise AgentPersistenceError("Failed to persist agents") from exc
            finally:
                session.close()
            return inserted

        def _persist_single(
            self,
            session: Session,
            agent: AgentProfile,
            payload: dict[str, Any],
            embedding: Sequence[float] | None,
        ) -> int:
            existing = session.get(AgentRecord, agent.id)
            if existing:
                return self._handle_existing(existing, payload, embedding)

            username_match = session.execute(
                select(AgentRecord).where(AgentRecord.username_hint == agent.username_hint),
            ).scalar_one_or_none()
            if username_match:
                if username_match.id == agent.id and username_match.payload == payload:
                    return self._handle_existing(username_match, payload, embedding)
                raise AgentUniquenessError(
                    f"username_hint {agent.username_hint!r} already assigned to agent {username_match.id}",
                )

            record = AgentRecord(
                id=agent.id,
                seed=agent.seed,
                username_hint=agent.username_hint,
                payload=payload,
                embedding=list(embedding) if embedding is not None else None,
            )
            session.add(record)
            return 1

        def _handle_existing(
            self,
            existing: AgentRecord,
            payload: dict[str, Any],
            embedding: Sequence[float] | None,
        ) -> int:
            if existing.payload != payload:
                raise AgentUniquenessError(
                    f"Agent {existing.id} already exists with different data",
                )
            if embedding is not None:
                new_vector = list(embedding)
                if existing.embedding != new_vector:
                    existing.embedding = new_vector
            return 0

        def fetch_by_id(self, agent_id: uuid.UUID) -> AgentRecord | None:
            """Return a persisted agent by identifier."""

            session = self._session_factory()
            try:
                return session.get(AgentRecord, agent_id)
            finally:
                session.close()

        def similar_to_embedding(
            self,
            embedding: Sequence[float],
            *,
            limit: int = 10,
        ) -> list[VectorMatch]:
            """Perform a vector similarity search using ``pgvector`` operations."""

            if not self._vector_search_enabled:
                raise AgentPersistenceError("Vector search is not enabled for this repository")

            session = self._session_factory()
            try:
                distance_expression = AgentRecord.embedding.l2_distance(list(embedding))
                stmt: Select[tuple[AgentRecord, float]] = (
                    select(AgentRecord, distance_expression.label("distance"))
                    .where(AgentRecord.embedding.is_not(None))
                    .order_by(distance_expression)
                    .limit(limit)
                )
                results = session.execute(stmt).all()
                return [VectorMatch(agent=row[0], distance=float(row[1])) for row in results]
            finally:
                session.close()

else:

    class AgentRepository:
        """Fallback in-memory repository used when SQLAlchemy isn't installed."""

        def __init__(
            self,
            session_factory: SyncSessionFactory | None = None,
            *,
            vector_search_enabled: bool = False,
        ) -> None:
            if session_factory is not None:
                raise AgentPersistenceError(
                    "Persistent storage requires SQLAlchemy; use AgentRepository() without a session factory",
                )
            self._records: dict[uuid.UUID, AgentRecord] = {}
            self._vector_search_enabled = vector_search_enabled

        @classmethod
        def from_engine(
            cls,
            bundle: EngineBundle,
            *,
            vector_search_enabled: bool = False,
        ) -> "AgentRepository":
            raise AgentPersistenceError(
                "sqlalchemy is not installed; persistent storage is unavailable in this environment",
            )

        def persist_agents(
            self,
            agents: Iterable[AgentProfile],
            *,
            embeddings: Mapping[uuid.UUID, Sequence[float]] | None = None,
        ) -> int:
            if embeddings is None:
                embeddings = {}

            inserted = 0
            for agent in agents:
                payload = agent.model_dump(mode="json")
                vector = embeddings.get(agent.id)
                inserted += self._persist_single(agent, payload, vector)
            return inserted

        def _persist_single(
            self,
            agent: AgentProfile,
            payload: dict[str, Any],
            embedding: Sequence[float] | None,
        ) -> int:
            existing = self._records.get(agent.id)
            if existing is not None:
                return self._handle_existing(existing, payload, embedding)

            for record in self._records.values():
                if record.username_hint != agent.username_hint:
                    continue
                if record.id == agent.id and record.payload == payload:
                    return self._handle_existing(record, payload, embedding)
                raise AgentUniquenessError(
                    f"username_hint {agent.username_hint!r} already assigned to agent {record.id}",
                )

            record = AgentRecord(
                id=agent.id,
                seed=agent.seed,
                username_hint=agent.username_hint,
                payload=payload,
                embedding=list(embedding) if embedding is not None else None,
            )
            self._records[agent.id] = record
            return 1

        def _handle_existing(
            self,
            existing: AgentRecord,
            payload: dict[str, Any],
            embedding: Sequence[float] | None,
        ) -> int:
            if existing.payload != payload:
                raise AgentUniquenessError(
                    f"Agent {existing.id} already exists with different data",
                )
            if embedding is not None:
                new_vector = list(embedding)
                if existing.embedding != new_vector:
                    existing.embedding = new_vector
            return 0

        def fetch_by_id(self, agent_id: uuid.UUID) -> AgentRecord | None:
            return self._records.get(agent_id)

        def similar_to_embedding(
            self,
            embedding: Sequence[float],
            *,
            limit: int = 10,
        ) -> list[VectorMatch]:
            if not self._vector_search_enabled:
                raise AgentPersistenceError("Vector search is not enabled for this repository")

            target = list(embedding)
            results: list[VectorMatch] = []
            for record in self._records.values():
                if record.embedding is None:
                    continue
                if len(record.embedding) != len(target):
                    raise AgentPersistenceError("Embedding dimension mismatch during similarity search")
                distance = math.sqrt(
                    sum((float(a) - float(b)) ** 2 for a, b in zip(record.embedding, target))
                )
                results.append(VectorMatch(agent=record, distance=distance))

            results.sort(key=lambda item: item.distance)
            return results[:limit]


__all__ = [
    "AgentPersistenceError",
    "AgentRepository",
    "AgentUniquenessError",
    "VectorMatch",
]

