import random

from azt3knet.agent_factory.generator import generate_agents
from azt3knet.agent_factory.models import PopulationSpec
from azt3knet.compliance_guard import ComplianceViolation
from azt3knet.core.config import resolve_seed
from azt3knet.core.seeds import SeedSequence, cycle_choices
from azt3knet.llm.adapter import LLMAdapter, LLMRequest


def test_generate_agents_is_deterministic():
    spec = PopulationSpec(count=3, country="MX", seed="seed-123", interests=["street art"])
    first = generate_agents(spec)
    second = generate_agents(spec)
    assert [agent.model_dump() for agent in first] == [agent.model_dump() for agent in second]


def test_generate_agents_respects_preview_limit_fields():
    spec = PopulationSpec(count=2, country="MX", seed="seed-123", preview=1)
    agents = generate_agents(spec)
    assert len(agents) == 2
    assert agents[0].username_hint != agents[1].username_hint


def test_generate_agents_produces_unique_names():
    spec = PopulationSpec(count=5, country="MX", seed="seed-unique", interests=["digital art"])
    agents = generate_agents(spec)
    names = [agent.name for agent in agents]
    assert len(names) == len(set(name.lower() for name in names))


class ConstantNameLLM(LLMAdapter):
    def __init__(self) -> None:
        self.calls: list[LLMRequest] = []

    def generate_field(self, request: LLMRequest) -> str:
        self.calls.append(request)
        return "test-name"


class ViolatingLLM(LLMAdapter):
    def generate_field(self, request: LLMRequest) -> str:
        raise ComplianceViolation("name rejected")


def test_generate_agents_accepts_custom_llm():
    llm = ConstantNameLLM()
    spec = PopulationSpec(count=1, country="ES", seed="seed-custom")
    agents = generate_agents(spec, llm=llm)
    assert agents[0].name == "Test Name"
    assert llm.calls  # ensure the custom adapter was invoked


def test_generate_agents_falls_back_when_compliance_rejects_all_attempts():
    spec = PopulationSpec(count=1, country="US", seed="seed-compliance")
    llm = ViolatingLLM()

    agents = generate_agents(spec, llm=llm)

    resolved_seed = resolve_seed(spec.seed)
    sequence = SeedSequence(resolved_seed)
    expected_number = sequence.derive("fallback-name", "0", "0") % 10_000
    expected_name = f"Agent {expected_number:04d}"

    assert agents[0].name == expected_name


def test_generate_agents_produces_unique_username_hints():
    spec = PopulationSpec(count=25, country="MX", seed="seed-unique-usernames")
    agents = generate_agents(spec)
    hints = [agent.username_hint for agent in agents]
    assert len(hints) == len(set(hints))


def test_generate_agents_returns_distinct_interest_lists():
    spec = PopulationSpec(
        count=2,
        country="US",
        seed="seed-independent-interests",
        interests=["digital art", "community events"],
    )

    agents = generate_agents(spec)

    agents[0].interests.append("gardening")

    assert "gardening" not in agents[1].interests


def test_cycle_choices_walks_sequentially_from_offset():
    options = ["alpha", "beta", "gamma", "delta"]
    rng = random.Random(2024)

    result = cycle_choices(options, count=6, rng=rng)

    assert result == ["delta", "alpha", "beta", "gamma", "delta", "alpha"]
