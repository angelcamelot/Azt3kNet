"""Helpers that orchestrate agent generation and optional mailbox provisioning."""

from __future__ import annotations

import logging
import uuid
from contextlib import ExitStack
from dataclasses import dataclass, field, replace
from typing import List

from azt3knet.agent_factory.generator import generate_agents
from azt3knet.agent_factory.models import AgentProfile, PopulationSpec
from azt3knet.compliance_guard import ComplianceViolation, ensure_guarded_llm
from azt3knet.core.config import derive_seed_components, resolve_seed
from azt3knet.core.mail_config import (
    MailcowSettings,
    MailProvisioningSettings,
    get_mailcow_settings,
    get_mail_provisioning_settings,
)
from azt3knet.core.seeds import SeedSequence
from azt3knet.llm.adapter import LLMAdapter, LLMRequest
from azt3knet.services.mailcow_provisioner import MailboxCredentials, MailcowProvisioner

logger = logging.getLogger(__name__)


@dataclass
class MailboxAssignment:
    """Mapping between an agent and the credentials created for it."""

    agent_id: uuid.UUID
    address: str
    password: str
    smtp_host: str
    smtp_port: int
    imap_host: str
    imap_port: int
    app_password: str | None = None

    @classmethod
    def from_credentials(
        cls, agent_id: uuid.UUID, credentials: MailboxCredentials
    ) -> "MailboxAssignment":
        return cls(
            agent_id=agent_id,
            address=credentials.address,
            password=credentials.password,
            smtp_host=credentials.smtp_host,
            smtp_port=credentials.smtp_port,
            imap_host=credentials.imap_host,
            imap_port=credentials.imap_port,
            app_password=credentials.app_password,
        )

    def as_public_dict(self) -> dict[str, object]:
        """Return a serializable representation suitable for JSON output."""

        return {
            "agent_id": str(self.agent_id),
            "address": self.address,
            "password": self.password,
            "app_password": self.app_password,
            "smtp_host": self.smtp_host,
            "smtp_port": self.smtp_port,
            "imap_host": self.imap_host,
            "imap_port": self.imap_port,
        }


@dataclass
class PopulationPreview:
    """Container with the generated agents and optional mailboxes."""

    agents: List[AgentProfile]
    mailboxes: List[MailboxAssignment] = field(default_factory=list)


@dataclass(frozen=True)
class PopulationGenerationResult:
    """Return value bundling the preview with the resolved seed context."""

    seed: str
    deterministic_seed: int
    preview: PopulationPreview


def _sanitize_local_part(value: str, fallback: str, *, max_length: int = 32) -> str:
    filtered = "".join(ch for ch in value.lower() if ch.isalnum())
    if not filtered:
        filtered = "".join(ch for ch in fallback.lower() if ch.isalnum())
    if not filtered:
        filtered = "agent"
    return filtered[:max_length]


def _provisioner_from_settings(
    *, mailcow: MailcowSettings | None = None,
    provisioning: MailProvisioningSettings | None = None,
) -> MailcowProvisioner:
    mailcow_settings = mailcow or get_mailcow_settings()
    provisioning_settings = provisioning or get_mail_provisioning_settings()
    if not mailcow_settings.api_base:
        raise RuntimeError("MAILCOW_API is not configured; cannot provision mailboxes")
    if not mailcow_settings.api_key:
        raise RuntimeError("MAILCOW_API_KEY is not configured; cannot provision mailboxes")
    if not provisioning_settings.domain:
        raise RuntimeError("AZT3KNET_DOMAIN is not configured; cannot provision mailboxes")
    return MailcowProvisioner(mailcow_settings, provisioning_settings)


def _mailbox_identifier(
    agent: AgentProfile, alias_source: str, sequence: SeedSequence, index: int
) -> str:
    alias = _sanitize_local_part(alias_source, agent.username_hint)
    suffix = sequence.derive("mailbox", agent.seed, str(index)) % 10_000
    return f"{alias}{suffix:04d}"


def build_population(
    spec: PopulationSpec,
    *,
    llm: LLMAdapter,
    deterministic_seed: int,
    create_mailboxes: bool = False,
    mail_provisioner: MailcowProvisioner | None = None,
) -> PopulationPreview:
    """Generate a deterministic population and optionally create mailboxes."""

    resolved_seed = resolve_seed(spec.seed)
    numeric_seed = SeedSequence(f"{resolved_seed}:{deterministic_seed}")

    guarded_llm = ensure_guarded_llm(llm, context="population.build_population")

    agents = generate_agents(spec, llm=guarded_llm)
    if spec.preview:
        agents = agents[: spec.preview]

    mailboxes: List[MailboxAssignment] = []
    if create_mailboxes:
        with ExitStack() as stack:
            provisioner = mail_provisioner
            if provisioner is None:
                provisioner = stack.enter_context(_provisioner_from_settings())
            provisioner.ensure_domain()
            for index, agent in enumerate(agents):
                prompt = (
                    f"Generate a lowercase alias (no spaces) for the mailbox of agent {agent.name} "
                    f"located in {agent.country}."
                )
                try:
                    alias_text = guarded_llm.generate_field(
                        LLMRequest(
                            prompt=prompt,
                            seed=deterministic_seed + index,
                            field_name="mailbox_alias",
                        )
                    )
                except ComplianceViolation as exc:
                    logger.warning(
                        "Compliance guard rejected mailbox alias for agent %s: %s. "
                        "Falling back to deterministic alias.",
                        agent.id,
                        exc,
                    )
                    alias_text = agent.username_hint
                identifier = _mailbox_identifier(agent, alias_text, numeric_seed, index)
                credentials = provisioner.create_agent_mailbox(
                    identifier,
                    display_name=agent.name,
                )
                logger.debug("Provisioned mailbox %s for agent %s", credentials.address, agent.id)
                mailboxes.append(MailboxAssignment.from_credentials(agent.id, credentials))

    return PopulationPreview(agents=agents, mailboxes=mailboxes)


def generate_population_preview(
    spec: PopulationSpec,
    *,
    namespace: str,
    llm: LLMAdapter,
    create_mailboxes: bool = False,
    mail_provisioner: MailcowProvisioner | None = None,
) -> PopulationGenerationResult:
    """Normalize seeds and build a population preview for a given namespace."""

    resolved_seed, deterministic_seed = derive_seed_components(spec.seed, namespace=namespace)
    normalized_spec = replace(spec, seed=resolved_seed)
    preview = build_population(
        normalized_spec,
        llm=llm,
        deterministic_seed=deterministic_seed,
        create_mailboxes=create_mailboxes,
        mail_provisioner=mail_provisioner,
    )
    return PopulationGenerationResult(
        seed=resolved_seed,
        deterministic_seed=deterministic_seed,
        preview=preview,
    )


__all__ = [
    "PopulationPreview",
    "MailboxAssignment",
    "PopulationGenerationResult",
    "build_population",
    "generate_population_preview",
]
