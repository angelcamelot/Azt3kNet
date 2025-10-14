"""Helpers that orchestrate agent generation and optional mailbox provisioning."""

from __future__ import annotations

import logging
import re
import uuid
from contextlib import ExitStack
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import List, Set

from azt3knet.agent_factory.generator import generate_agents
from azt3knet.agent_factory.models import AgentProfile, PopulationSpec
from azt3knet.compliance_guard import ensure_guarded_llm
from azt3knet.core.config import derive_seed_components, resolve_seed
from azt3knet.core.mail_config import (
    MailProvisioningSettings,
    MailjetSettings,
    get_mail_provisioning_settings,
    get_mailjet_settings,
)
from azt3knet.core.seeds import SeedSequence
from azt3knet.llm.adapter import LLMAdapter
from azt3knet.services.mailjet_provisioner import MailboxCredentials, MailjetProvisioner

logger = logging.getLogger(__name__)


@dataclass
class MailboxAssignment:
    """Mapping between an agent and the credentials created for it."""

    agent_id: uuid.UUID
    address: str
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    inbound_url: str | None = None
    inbound_secret: str | None = None

    @classmethod
    def from_credentials(
        cls, agent_id: uuid.UUID, credentials: MailboxCredentials
    ) -> "MailboxAssignment":
        return cls(
            agent_id=agent_id,
            address=credentials.address,
            smtp_host=credentials.smtp_host,
            smtp_port=credentials.smtp_port,
            smtp_username=credentials.smtp_username,
            smtp_password=credentials.smtp_password,
            inbound_url=credentials.inbound_url,
            inbound_secret=credentials.inbound_secret,
        )

    def as_public_dict(self) -> dict[str, object]:
        """Return a serializable representation suitable for JSON output."""

        return {
            "agent_id": str(self.agent_id),
            "address": self.address,
            "smtp_host": self.smtp_host,
            "smtp_port": self.smtp_port,
            "smtp_username": self.smtp_username,
            "smtp_password": self.smtp_password,
            "inbound_url": self.inbound_url,
            "inbound_secret": self.inbound_secret,
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
    *, mailjet: MailjetSettings | None = None,
    provisioning: MailProvisioningSettings | None = None,
) -> MailjetProvisioner:
    mailjet_settings = mailjet or get_mailjet_settings()
    provisioning_settings = provisioning or get_mail_provisioning_settings()
    if not mailjet_settings.api_key:
        raise RuntimeError("MAILJET_API_KEY is not configured; cannot provision mailboxes")
    if not mailjet_settings.api_secret:
        raise RuntimeError("MAILJET_API_SECRET is not configured; cannot provision mailboxes")
    if not provisioning_settings.domain:
        raise RuntimeError("AZT3KNET_DOMAIN is not configured; cannot provision mailboxes")
    return MailjetProvisioner(mailjet_settings, provisioning_settings)


def _sanitize_name_component(value: str, fallback: str = "agent") -> str:
    filtered = "".join(ch for ch in value.lower() if ch.isalnum())
    if not filtered:
        filtered = "".join(ch for ch in fallback.lower() if ch.isalnum())
    return (filtered or fallback or "agent")[:16]


def _split_name_components(name: str) -> list[str]:
    return [part for part in re.split(r"[^A-Za-z0-9]+", name) if part]


def _current_date_digits() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")


def _mailbox_local_part_for_agent(
    agent: AgentProfile,
    sequence: SeedSequence,
    index: int,
    *,
    attempt: int = 0,
    timestamp_digits: str | None = None,
) -> str:
    components = _split_name_components(agent.name)
    if components:
        first_component = components[0]
        last_component = components[-1] if len(components) > 1 else components[0]
    else:
        first_component = agent.username_hint
        last_component = agent.username_hint

    first = _sanitize_name_component(first_component, fallback="agent")
    last = _sanitize_name_component(last_component, fallback=first)
    digits_source = sequence.derive("mailbox", agent.seed, str(index), "digits", str(attempt))
    random_digits = f"{digits_source % 1000:03d}"
    suffix = timestamp_digits or _current_date_digits()
    return f"{first}.{last}.{random_digits}.{suffix}"


def build_population(
    spec: PopulationSpec,
    *,
    llm: LLMAdapter,
    deterministic_seed: int,
    create_mailboxes: bool = False,
    mail_provisioner: MailjetProvisioner | None = None,
) -> PopulationPreview:
    """Generate a deterministic population and optionally create mailboxes."""

    resolved_seed = resolve_seed(spec.seed)
    numeric_seed = SeedSequence(f"{resolved_seed}:{deterministic_seed}")

    guarded_llm = ensure_guarded_llm(llm, context="population.build_population")

    agents = generate_agents(spec, llm=guarded_llm)
    if spec.preview:
        agents = agents[: spec.preview]

    mailboxes: List[MailboxAssignment] = []
    used_local_parts: Set[str] = set()
    timestamp_digits = _current_date_digits()
    if create_mailboxes:
        with ExitStack() as stack:
            provisioner = mail_provisioner
            if provisioner is None:
                provisioner = stack.enter_context(_provisioner_from_settings())
            provisioner.ensure_domain()
            for index, agent in enumerate(agents):
                identifier: str | None = None
                for attempt in range(1000):
                    candidate = _mailbox_local_part_for_agent(
                        agent,
                        numeric_seed,
                        index,
                        attempt=attempt,
                        timestamp_digits=timestamp_digits,
                    )
                    if candidate not in used_local_parts:
                        identifier = candidate
                        used_local_parts.add(candidate)
                        break
                if identifier is None:
                    raise RuntimeError(
                        "Unable to generate a unique mailbox identifier after 1000 attempts"
                    )
                credentials = provisioner.create_agent_mailbox(
                    identifier,
                    display_name=agent.name,
                    apply_prefix=False,
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
    mail_provisioner: MailjetProvisioner | None = None,
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
