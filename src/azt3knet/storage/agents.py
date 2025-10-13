"""SQLite-backed persistence helpers for agent profiles."""

from __future__ import annotations

import json
import os
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from azt3knet.agent_factory.models import AgentProfile

DEFAULT_DB_PATH = os.getenv("AZT3KNET_DB_PATH", "azt3knet.db")


class AgentPersistenceError(RuntimeError):
    """Base exception for agent persistence failures."""


class AgentUniquenessError(AgentPersistenceError):
    """Raised when attempting to insert a conflicting agent record."""


@dataclass
class AgentStore:
    """Persist ``AgentProfile`` entries into a SQLite database."""

    db_path: str | os.PathLike[str] = DEFAULT_DB_PATH

    def __post_init__(self) -> None:
        path = self.db_path
        if isinstance(path, Path):
            self._db_path = str(path)
        else:
            self._db_path = str(path)
        if self._db_path != ":memory:":
            Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS agents (
                    id TEXT PRIMARY KEY,
                    seed TEXT NOT NULL,
                    username_hint TEXT NOT NULL UNIQUE,
                    payload TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.commit()

    def persist_agents(
        self,
        agents: Iterable[AgentProfile],
        *,
        max_retries: int = 3,
        backoff_base: float = 0.05,
    ) -> int:
        """Persist agents ensuring uniqueness and idempotency."""

        inserted = 0
        with self._connect() as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            for agent in agents:
                payload_dict = agent.model_dump(mode="json")
                payload = json.dumps(payload_dict, sort_keys=True)
                attempt = 0
                while True:
                    try:
                        conn.execute(
                            """
                            INSERT INTO agents (id, seed, username_hint, payload)
                            VALUES (?, ?, ?, ?)
                            """,
                            (str(agent.id), agent.seed, agent.username_hint, payload),
                        )
                        inserted += 1
                        break
                    except sqlite3.IntegrityError as exc:
                        conn.rollback()
                        try:
                            if self._is_same_record(conn, agent, payload_dict):
                                break
                        except AgentUniquenessError as unique_exc:  # pragma: no cover - defensive
                            raise unique_exc from exc
                        if attempt >= max_retries:
                            raise AgentPersistenceError(
                                "Exceeded retries while persisting agent"
                            ) from exc
                        if backoff_base:
                            time.sleep(backoff_base * (2**attempt))
                        attempt += 1
            conn.commit()
        return inserted

    def _is_same_record(
        self, conn: sqlite3.Connection, agent: AgentProfile, payload_dict: dict[str, object]
    ) -> bool:
        existing = conn.execute(
            "SELECT payload FROM agents WHERE id = ?",
            (str(agent.id),),
        ).fetchone()
        if existing:
            stored_payload = json.loads(existing[0])
            if stored_payload == payload_dict:
                return True
            raise AgentUniquenessError(
                f"Agent {agent.id} already exists with different data"
            )

        existing = conn.execute(
            "SELECT id, payload FROM agents WHERE username_hint = ?",
            (agent.username_hint,),
        ).fetchone()
        if existing:
            existing_id, payload = existing
            stored_payload = json.loads(payload)
            if existing_id == str(agent.id) and stored_payload == payload_dict:
                return True
            raise AgentUniquenessError(
                f"username_hint {agent.username_hint!r} is already assigned to agent {existing_id}"
            )

        return False


__all__ = [
    "AgentStore",
    "AgentPersistenceError",
    "AgentUniquenessError",
]
