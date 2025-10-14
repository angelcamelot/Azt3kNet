"""Tests for the population builder preview logic."""

from __future__ import annotations

import uuid

from azt3knet.agent_factory.models import AgentProfile, PopulationSpec
from azt3knet.core.seeds import SeedSequence
from azt3knet.llm.adapter import LLMAdapter, LLMRequest
from azt3knet.population import builder as population_builder
from azt3knet.population.builder import (
    PopulationPreview,
    _mailbox_local_part_for_agent,
    build_population,
)
from azt3knet.services.mailjet_provisioner import MailboxCredentials


class StubLLM(LLMAdapter):
    """Return deterministic aliases regardless of the prompt."""

    def generate_field(self, request: LLMRequest) -> str:
        return f"alias-{request.seed}-{request.field_name}"


class StubProvisioner:
    """In-memory Mailjet provisioner used to avoid network calls."""

    def __init__(self) -> None:
        self.created: list[dict[str, object]] = []
        self.closed = False

    def ensure_domain(self) -> None:
        return None

    def create_agent_mailbox(
        self,
        agent_id: str,
        *,
        display_name: str | None = None,
        apply_prefix: bool = True,
    ) -> MailboxCredentials:
        self.created.append({
            "agent_id": agent_id,
            "apply_prefix": apply_prefix,
        })
        local_part = f"agent_{agent_id}" if apply_prefix else agent_id
        return MailboxCredentials(
            address=f"{local_part}@example.org",
            smtp_host="smtp.example.org",
            smtp_port=587,
            smtp_username="api-key",
            smtp_password="api-secret",
            inbound_url="https://example.org/inbound",
            inbound_secret="token",
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
    """Mailboxes are provisioned via the provided Mailjet stub."""

    spec = PopulationSpec(count=2, country="US", seed="mail-seed")
    provisioner = StubProvisioner()
    monkeypatch.setattr(population_builder, "_current_date_digits", lambda: "20241005123045")
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
    assert all(
        isinstance(entry.get("apply_prefix"), bool) and entry.get("apply_prefix") is False
        for entry in provisioner.created
    )
    assert all(assignment.address.endswith("@example.org") for assignment in preview.mailboxes)
    for assignment in preview.mailboxes:
        local_part = assignment.address.split("@", 1)[0]
        assert local_part.count(".") == 3
        _, _, digits, timestamp = local_part.split(".")
        assert len(digits) == 3 and digits.isdigit()
        assert timestamp == "20241005123045"
    assert not provisioner.closed


def test_mailbox_local_part_handles_missing_last_name(monkeypatch) -> None:
    agent = AgentProfile(
        id=uuid.uuid4(),
        seed="seed:0",
        name="Madonna",
        username_hint="Performer42",
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
    sequence = SeedSequence("mail-sequence")
    monkeypatch.setattr(population_builder, "_current_date_digits", lambda: "20231201000000")

    local_part = _mailbox_local_part_for_agent(agent, sequence, 0)

    first, last, digits, timestamp = local_part.split(".")
    assert first == "madonna"
    assert last == "madonna"
    assert len(digits) == 3 and digits.isdigit()
    assert timestamp == "20231201000000"


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


def test_mailbox_local_part_is_deterministic(monkeypatch) -> None:
    agent = _make_agent(7)
    sequence = SeedSequence("batch-seed")
    monkeypatch.setattr(population_builder, "_current_date_digits", lambda: "20240102030405")

    first = _mailbox_local_part_for_agent(agent, sequence, 2)
    second = _mailbox_local_part_for_agent(agent, sequence, 2)

    assert first == second
