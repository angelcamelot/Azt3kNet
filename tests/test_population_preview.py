"""Tests for the population builder preview logic."""

from __future__ import annotations

from azt3knet.agent_factory.models import PopulationSpec
from azt3knet.llm.adapter import LLMAdapter, LLMRequest
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
        return MailboxCredentials(
            address=f"agent_{agent_id}@example.org",
            password=password or "example-password",
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
