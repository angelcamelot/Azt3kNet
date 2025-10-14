"""SQLAlchemy-backed repository for agent persistence and retrieval."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence
import uuid

from sqlalchemy import Select, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from azt3knet.agent_factory.models import AgentProfile

from .db import EngineBundle, SyncSessionFactory
from .models.agent import AgentRecord


class AgentPersistenceError(RuntimeError):
    """Base exception for agent persistence failures."""


class AgentUniquenessError(AgentPersistenceError):
    """Raised when attempting to insert a conflicting agent record."""


@dataclass(frozen=True)
class VectorMatch:
    """Represents an agent matched via a vector search."""

    agent: AgentRecord
    distance: float


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


__all__ = [
    "AgentPersistenceError",
    "AgentRepository",
    "AgentUniquenessError",
    "VectorMatch",
]

