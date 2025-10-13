from azt3knet.agent_factory.generator import generate_agents
from azt3knet.agent_factory.models import PopulationSpec
from azt3knet.llm.adapter import LLMAdapter, LLMRequest


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


def test_generate_agents_produces_unique_names():
    spec = PopulationSpec(count=5, country="MX", seed="seed-unique", interests=["arte"])
    agents = generate_agents(spec)
    names = [agent.name for agent in agents]
    assert len(names) == len(set(name.lower() for name in names))


class ConstantNameLLM(LLMAdapter):
    def __init__(self) -> None:
        self.calls: list[LLMRequest] = []

    def generate_field(self, request: LLMRequest) -> str:
        self.calls.append(request)
        return "nombre-prueba"


def test_generate_agents_accepts_custom_llm():
    llm = ConstantNameLLM()
    spec = PopulationSpec(count=1, country="ES", seed="seed-custom")
    agents = generate_agents(spec, llm=llm)
    assert agents[0].name == "Nombre Prueba"
    assert llm.calls  # ensure the custom adapter was invoked
