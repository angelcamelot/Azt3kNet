"""Integration tests for the SQLAlchemy-backed agent repository."""

from __future__ import annotations

import shutil
import socket
import subprocess
import uuid
from typing import Iterable

import pytest

from azt3knet.agent_factory.models import AgentProfile
from azt3knet.storage.agents import AgentRepository, AgentUniquenessError
from azt3knet.storage.db import create_engine_from_url


def _find_free_port() -> int:
    sock = socket.socket()
    try:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]
    finally:
        sock.close()


def _run(cmd: Iterable[str], *, env: dict[str, str] | None = None) -> None:
    subprocess.run(
        list(cmd),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )


@pytest.fixture(scope="session")
def postgres_url(tmp_path_factory: pytest.TempPathFactory) -> str:
    initdb = shutil.which("initdb")
    pg_ctl = shutil.which("pg_ctl")
    createdb = shutil.which("createdb")
    if not (initdb and pg_ctl and createdb):
        pytest.skip("Postgres utilities are required for storage integration tests")

    data_dir = tmp_path_factory.mktemp("pgdata")
    _run([initdb, "-D", str(data_dir)])

    port = _find_free_port()
    env = {"PGPORT": str(port), "PGUSER": "root"}
    _run([pg_ctl, "-D", str(data_dir), "-o", f"-p {port}", "-w", "start"], env=env)

    db_name = "azt3knet_test"
    _run([createdb, "-h", "127.0.0.1", "-p", str(port), db_name, "root"], env=env)

    url = f"postgresql+psycopg://root@127.0.0.1:{port}/{db_name}"

    yield url

    _run([pg_ctl, "-D", str(data_dir), "-m", "immediate", "-w", "stop"], env=env)


@pytest.fixture()
def agent_repo(postgres_url: str) -> AgentRepository:
    bundle = create_engine_from_url(postgres_url)
    with bundle.engine.begin() as conn:
        conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector;")
        conn.exec_driver_sql("DROP TABLE IF EXISTS agents CASCADE;")
        conn.exec_driver_sql(
            """
            CREATE TABLE agents (
                id UUID NOT NULL,
                seed TEXT NOT NULL,
                username_hint TEXT NOT NULL,
                payload JSONB NOT NULL,
                embedding VECTOR,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            ) PARTITION BY RANGE (created_at);
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE agents_default
            PARTITION OF agents
            DEFAULT;
            """
        )
        conn.exec_driver_sql("CREATE UNIQUE INDEX ux_agents_default_id ON agents_default (id);")
        conn.exec_driver_sql(
            "CREATE UNIQUE INDEX ux_agents_default_username ON agents_default (username_hint);",
        )
        conn.exec_driver_sql(
            "CREATE INDEX ix_agents_default_created_at ON agents_default (created_at);",
        )
        conn.exec_driver_sql(
            """
            CREATE INDEX ix_agents_default_embedding
            ON agents_default
            USING ivfflat (embedding vector_l2_ops)
            WITH (lists = 100);
            """
        )

    repository = AgentRepository.from_engine(bundle, vector_search_enabled=True)
    try:
        yield repository
    finally:
        bundle.engine.dispose()


def _make_profile(seed: str, username: str) -> AgentProfile:
    identifier = uuid.uuid5(uuid.NAMESPACE_DNS, f"{seed}:{username}")
    return AgentProfile(
        id=identifier,
        seed=seed,
        name=f"Agent {username}",
        username_hint=username,
        country="US",
        city="New York",
        locale="en_US",
        timezone="UTC",
        age=30,
        gender="unspecified",
        interests=["technology"],
        bio="Synthetic agent",
        posting_cadence="daily",
        tone="casual",
        behavioral_biases=["curious"],
    )


def test_persist_agents_stores_records(agent_repo: AgentRepository) -> None:
    repo = agent_repo
    profile = _make_profile("seed-1", "user_one")

    inserted = repo.persist_agents([profile])
    assert inserted == 1

    stored = repo.fetch_by_id(profile.id)
    assert stored is not None
    assert stored.username_hint == "user_one"

    inserted = repo.persist_agents(
        [profile],
        embeddings={profile.id: [0.1, 0.2, 0.3]},
    )
    assert inserted == 0

    updated = repo.fetch_by_id(profile.id)
    assert updated is not None
    assert updated.embedding == [0.1, 0.2, 0.3]


def test_persist_agents_detects_username_conflicts(agent_repo: AgentRepository) -> None:
    repo = agent_repo
    first = _make_profile("seed-1", "conflict")
    second = _make_profile("seed-2", "conflict")

    repo.persist_agents([first])

    with pytest.raises(AgentUniquenessError):
        repo.persist_agents([second])


def test_vector_search_returns_nearest_neighbors(agent_repo: AgentRepository) -> None:
    repo = agent_repo
    base = _make_profile("seed-0", "vector-base")
    near = _make_profile("seed-1", "vector-near")
    far = _make_profile("seed-2", "vector-far")

    repo.persist_agents(
        [base, near, far],
        embeddings={
            base.id: [0.0, 0.0, 0.0],
            near.id: [0.1, 0.1, 0.1],
            far.id: [0.9, 0.9, 0.9],
        },
    )

    matches = repo.similar_to_embedding([0.0, 0.0, 0.0], limit=2)
    assert [match.agent.username_hint for match in matches] == ["vector-base", "vector-near"]

