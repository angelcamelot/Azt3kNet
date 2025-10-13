"""Tests for the population builder preview logic."""

from __future__ import annotations

import uuid

from azt3knet.agent_factory.models import AgentProfile, PopulationSpec
from azt3knet.compliance_guard import ComplianceViolation
from azt3knet.core.config import resolve_seed
from azt3knet.core.seeds import SeedSequence
from azt3knet.llm.adapter import LLMAdapter, LLMRequest
from azt3knet.population import builder as population_builder
from azt3knet.population.builder import PopulationPreview, build_population
from azt3knet.services.mailcow_provisioner import MailboxCredentials


class StubLLM(LLMAdapter):
    """Return deterministic aliases regardless of the prompt."""

    def generate_field(self, request: LLMRequest) -> str:
        return f"alias-{request.seed}-{request.field_name}"


class StubProvisioner:
    """In-memory Mailcow provisioner used to avoid network calls."""

    def __init__(self) -> None:
        self.created: list[str] = []
        self.closed = False

    def ensure_domain(self) -> None:
        return None

    def create_agent_mailbox(
        self,
        agent_id: str,
        *,
        display_name: str | None = None,
        password: str | None = None,
        quota_mb: int | None = None,
    ) -> MailboxCredentials:
        self.created.append(agent_id)
        resolved_password = "example-password" if password is None else password
        return MailboxCredentials(
            address=f"agent_{agent_id}@example.org",
            password=resolved_password,
            app_password="example-app-pass",
            smtp_host="smtp.example.org",
            smtp_port=587,
            imap_host="imap.example.org",
            imap_port=993,
        )

    def close(self) -> None:
        self.closed = True


def test_build_population_preview_without_mailboxes() -> None:
    """The builder returns the requested number of agents without provisioning."""

    spec = PopulationSpec(count=3, country="US", seed="preview-seed", preview=2)
    preview = build_population(spec, llm=StubLLM(), deterministic_seed=1234, create_mailboxes=False)

    assert isinstance(preview, PopulationPreview)
    assert len(preview.agents) == 2
    assert preview.mailboxes == []


def test_build_population_with_mailboxes(monkeypatch) -> None:
    """Mailboxes are provisioned via the provided Mailcow stub."""

    spec = PopulationSpec(count=2, country="US", seed="mail-seed")
    provisioner = StubProvisioner()
    preview = build_population(
        spec,
        llm=StubLLM(),
        deterministic_seed=9876,
        create_mailboxes=True,
        mail_provisioner=provisioner,
    )

    assert len(preview.agents) == 2
    assert len(preview.mailboxes) == 2
    assert provisioner.created  # ensure the stub was used
    assert all(assignment.address.endswith("@example.org") for assignment in preview.mailboxes)
    assert not provisioner.closed


class MailboxViolatingLLM(LLMAdapter):
    """Stub LLM that raises a compliance violation when generating aliases."""

    def generate_field(self, request: LLMRequest) -> str:
        raise ComplianceViolation("mailbox alias rejected")


def test_build_population_mailbox_alias_fallback(monkeypatch, caplog) -> None:
    """Provisioning falls back to deterministic aliases when the guard rejects output."""

    agent = AgentProfile(
        id=uuid.uuid4(),
        seed="seed:0",
        name="Fallback Agent",
        username_hint="Fallback_User_123",
        country="US",
        city="",
        locale="en_US",
        timezone="America/New_York",
        age=30,
        gender="unspecified",
        interests=["digital culture"],
        bio="Bio",
        posting_cadence="daily",
        tone="informative",
        behavioral_biases=["early_adopter"],
    )

    def fake_generate_agents(spec: PopulationSpec, llm: LLMAdapter):
        return [agent]

    monkeypatch.setattr(population_builder, "generate_agents", fake_generate_agents)

    spec = PopulationSpec(count=1, country="US", seed="guarded-seed")
    provisioner = StubProvisioner()
    deterministic_seed = 2024

    with caplog.at_level("WARNING"):
        preview = build_population(
            spec,
            llm=MailboxViolatingLLM(),
            deterministic_seed=deterministic_seed,
            create_mailboxes=True,
            mail_provisioner=provisioner,
        )

    assert len(preview.mailboxes) == 1
    resolved_seed = resolve_seed(spec.seed)
    numeric_seed = SeedSequence(f"{resolved_seed}:{deterministic_seed}")
    expected_identifier = population_builder._mailbox_identifier(
        agent,
        agent.username_hint,
        numeric_seed,
        0,
    )
    assert provisioner.created == [expected_identifier]
    assert "Compliance guard rejected mailbox alias" in caplog.text


def _make_agent(index: int) -> AgentProfile:
    return AgentProfile(
        id=uuid.UUID(int=index + 1),
        seed=f"seed:{index}",
        name=f"Agent {index}",
        username_hint=f"agent_{index}",
        country="US",
        city="",
        locale="en_US",
        timezone="America/New_York",
        age=30,
        gender="unspecified",
        interests=["digital culture"],
        bio="Bio",
        posting_cadence="daily",
        tone="informative",
        behavioral_biases=["early_adopter"],
    )


def test_mailbox_identifier_generates_high_entropy_suffix() -> None:
    agent = _make_agent(0)
    sequence = SeedSequence("batch-seed")
    identifier = population_builder._mailbox_identifier(agent, "Alias Example", sequence, 0)

    prefix = "aliasexample"
    assert identifier.startswith(prefix)
    suffix = identifier[len(prefix) :]
    assert len(suffix) == 13
    assert suffix.isalnum()
    assert suffix == suffix.lower()


def test_mailbox_identifier_unique_for_large_batch() -> None:
    sequence = SeedSequence("batch-seed")
    identifiers = {
        population_builder._mailbox_identifier(_make_agent(idx), "batch", sequence, idx)
        for idx in range(5000)
    }

    assert len(identifiers) == 5000


def test_mailbox_identifier_preserves_legacy_alias() -> None:
    agent = _make_agent(42)
    sequence = SeedSequence("legacy-seed")
    legacy_alias = "legacyuser0042"

    identifier = population_builder._mailbox_identifier(agent, legacy_alias, sequence, 0)

    assert identifier == legacy_alias
