from azt3knet.agent_factory.generator import generate_agents
from azt3knet.agent_factory.models import PopulationSpec


def test_generate_agents_is_deterministic():
    spec = PopulationSpec(count=3, country="MX", seed="seed-123", interests=["cumbia"])
    first = generate_agents(spec)
    second = generate_agents(spec)
    assert [agent.model_dump() for agent in first] == [agent.model_dump() for agent in second]


def test_generate_agents_respects_preview_limit_fields():
    spec = PopulationSpec(count=2, country="MX", seed="seed-123", preview=1)
    agents = generate_agents(spec)
    assert len(agents) == 2
    assert agents[0].username_hint != agents[1].username_hint
