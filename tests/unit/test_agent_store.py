from __future__ import annotations

import sqlite3
import uuid
from dataclasses import replace

import pytest

from azt3knet.agent_factory.generator import generate_agents
from azt3knet.agent_factory.models import PopulationSpec
from azt3knet.storage.agents import AgentStore, AgentUniquenessError


def test_agent_store_persists_idempotently(tmp_path):
    spec = PopulationSpec(count=4, country="MX", seed="seed-2025")
    agents = generate_agents(spec)
    db_path = tmp_path / "agents.db"
    store = AgentStore(db_path=db_path)

    inserted = store.persist_agents(agents, backoff_base=0)
    assert inserted == len(agents)

    inserted_again = store.persist_agents(agents, backoff_base=0)
    assert inserted_again == 0

    with sqlite3.connect(db_path) as conn:
        total = conn.execute("SELECT COUNT(*) FROM agents").fetchone()[0]
    assert total == len(agents)


def test_agent_store_detects_username_conflicts(tmp_path):
    spec = PopulationSpec(count=1, country="MX", seed="seed-conflict")
    agent = generate_agents(spec)[0]
    conflicting_agent = replace(agent, id=uuid.uuid4(), seed="other-seed")
    db_path = tmp_path / "agents.db"
    store = AgentStore(db_path=db_path)

    store.persist_agents([agent], backoff_base=0)

    with pytest.raises(AgentUniquenessError):
        store.persist_agents([conflicting_agent], backoff_base=0)
