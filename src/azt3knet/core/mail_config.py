"""Mail and DNS related configuration helpers."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Callable


def _env_factory(name: str, default: str = "") -> Callable[[], str]:
    return lambda: os.getenv(name, default)


def _int_env_factory(name: str, default: str) -> Callable[[], int]:
    return lambda: int(os.getenv(name, default))


def _tuple_env_factory(name: str, default: str) -> Callable[[], tuple[str, ...]]:
    def factory() -> tuple[str, ...]:
        raw = os.getenv(name, default)
        if not raw:
            return ()
        return tuple(part.strip() for part in raw.split(",") if part.strip())

    return factory


@dataclass
class MailjetSettings:
    """Configuration for interacting with the Mailjet API and services."""

    api_base: str = field(default_factory=_env_factory("MAILJET_API", "https://api.mailjet.com"))
    api_key: str = field(default_factory=_env_factory("MAILJET_API_KEY", ""))
    api_secret: str = field(default_factory=_env_factory("MAILJET_API_SECRET", ""))
    smtp_host: str = field(default_factory=_env_factory("MAILJET_SMTP_HOST", "in-v3.mailjet.com"))
    smtp_port: int = field(default_factory=_int_env_factory("MAILJET_SMTP_PORT", "587"))
    smtp_user: str = field(default_factory=_env_factory("MAILJET_SMTP_USER", ""))
    smtp_pass: str = field(default_factory=_env_factory("MAILJET_SMTP_PASS", ""))
    inbound_webhook_url: str = field(default_factory=_env_factory("MAILJET_INBOUND_URL", ""))
    inbound_webhook_secret: str = field(default_factory=_env_factory("MAILJET_INBOUND_SECRET", ""))
    mx_hosts: tuple[str, ...] = field(
        default_factory=_tuple_env_factory("MAILJET_MX_HOSTS", "in.mailjet.com")
    )
    spf_include: str = field(
        default_factory=_env_factory("MAILJET_SPF_INCLUDE", "include:spf.mailjet.com")
    )

    def __post_init__(self) -> None:
        if not self.smtp_user:
            object.__setattr__(self, "smtp_user", self.api_key)
        if not self.smtp_pass:
            object.__setattr__(self, "smtp_pass", self.api_secret)
        if not self.mx_hosts:
            object.__setattr__(self, "mx_hosts", ("in.mailjet.com",))

    @property
    def base_url(self) -> str:
        return self.api_base.rstrip("/")

    @property
    def smtp_username(self) -> str:
        return self.smtp_user

    @property
    def smtp_password(self) -> str:
        return self.smtp_pass


@dataclass
class MailProvisioningSettings:
    """Defaults for agent mailbox provisioning."""

    domain: str = field(default_factory=_env_factory("AZT3KNET_DOMAIN", ""))
    agent_mail_prefix: str = field(default_factory=_env_factory("AZT3KNET_AGENT_MAIL_PREFIX", "agent_"))
    default_ttl: int = field(default_factory=_int_env_factory("AZT3KNET_MAIL_TTL", "300"))


@dataclass
class DeSECSettings:
    """Configuration for deSEC dynamic DNS management."""

    api_base: str = field(default_factory=_env_factory("DESEC_API", "https://desec.io/api/v1"))
    domain: str = field(default_factory=_env_factory("DESEC_DOMAIN", ""))
    token: str = field(default_factory=_env_factory("DESEC_TOKEN", ""))
    dyndns_update_url: str = field(
        default_factory=_env_factory("DESEC_DYNDNS_UPDATE_URL", "https://update.dedyn.io")
    )
    update_interval_hours: int = field(default_factory=_int_env_factory("DESEC_UPDATE_INTERVAL_HOURS", "24"))
    default_ttl: int = field(default_factory=_int_env_factory("AZT3KNET_MAIL_TTL", "300"))


@dataclass
class CloudflareTunnelSettings:
    """Settings required to operate a Cloudflare Tunnel for the API surface."""

    token: str = field(default_factory=_env_factory("CLOUDFLARE_TUNNEL_TOKEN", ""))
    hostname: str = field(default_factory=_env_factory("CLOUDFLARE_TUNNEL_HOSTNAME", ""))
    service_url: str = field(default_factory=_env_factory("CLOUDFLARE_TUNNEL_SERVICE", "http://api:8000"))
    cname_target: str = field(default_factory=_env_factory("CLOUDFLARE_TUNNEL_CNAME", ""))
    cname_subdomain: str = field(default_factory=_env_factory("CLOUDFLARE_TUNNEL_SUBDOMAIN", ""))
    cname_ttl: int = field(default_factory=_int_env_factory("CLOUDFLARE_TUNNEL_CNAME_TTL", "300"))

    def normalised_cname_target(self) -> str:
        """Return the CNAME target with a trailing dot when applicable."""

        target = self.cname_target.strip()
        if target and not target.endswith("."):
            target = f"{target}."
        return target


@lru_cache(maxsize=1)
def get_mailjet_settings() -> MailjetSettings:
    return MailjetSettings()


@lru_cache(maxsize=1)
def get_mail_provisioning_settings() -> MailProvisioningSettings:
    return MailProvisioningSettings()


@lru_cache(maxsize=1)
def get_desec_settings() -> DeSECSettings:
    return DeSECSettings()


@lru_cache(maxsize=1)
def get_cloudflare_tunnel_settings() -> CloudflareTunnelSettings:
    return CloudflareTunnelSettings()

