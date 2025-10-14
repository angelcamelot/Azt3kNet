"""Mail and DNS related configuration helpers."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Callable


_TRUE_VALUES = {"1", "true", "yes"}


def _env_factory(name: str, default: str = "") -> Callable[[], str]:
    return lambda: os.getenv(name, default)


def _int_env_factory(name: str, default: str) -> Callable[[], int]:
    return lambda: int(os.getenv(name, default))


def _bool_env_factory(name: str, default: str) -> Callable[[], bool]:
    return lambda: os.getenv(name, default).lower() in _TRUE_VALUES


@dataclass
class MailcowSettings:
    """Configuration for interacting with the Mailcow API and services."""

    api_base: str = field(default_factory=_env_factory("MAILCOW_API", ""))
    api_key: str = field(default_factory=_env_factory("MAILCOW_API_KEY", ""))
    smtp_host: str = field(default_factory=_env_factory("MAILCOW_SMTP_HOST", ""))
    smtp_port: int = field(default_factory=_int_env_factory("MAILCOW_SMTP_PORT", "587"))
    imap_host: str = field(default_factory=_env_factory("MAILCOW_IMAP_HOST", ""))
    imap_port: int = field(default_factory=_int_env_factory("MAILCOW_IMAP_PORT", "993"))
    relay_host: str = field(default_factory=_env_factory("MAILCOW_RELAY_HOST", ""))
    relay_port: int = field(default_factory=_int_env_factory("MAILCOW_RELAY_PORT", "587"))
    relay_user: str = field(default_factory=_env_factory("MAILCOW_RELAY_USER", ""))
    relay_password: str = field(default_factory=_env_factory("MAILCOW_RELAY_PASS", ""))
    verify_tls: bool = field(default_factory=_bool_env_factory("MAILCOW_VERIFY_TLS", "true"))

    @property
    def base_url(self) -> str:
        return self.api_base.rstrip("/")


@dataclass
class MailProvisioningSettings:
    """Defaults for agent mailbox provisioning."""

    domain: str = field(default_factory=_env_factory("AZT3KNET_DOMAIN", ""))
    agent_mail_prefix: str = field(default_factory=_env_factory("AZT3KNET_AGENT_MAIL_PREFIX", "agent_"))
    agent_mail_password: str = field(
        default_factory=_env_factory("AZT3KNET_AGENT_MAIL_PASSWORD", "")
    )
    mailbox_quota_mb: int = field(default_factory=_int_env_factory("AZT3KNET_MAIL_QUOTA_MB", "1024"))
    default_ttl: int = field(default_factory=_int_env_factory("AZT3KNET_MAIL_TTL", "300"))
    rate_limit_per_hour: int = field(default_factory=_int_env_factory("AZT3KNET_MAIL_RATE_LIMIT", "100"))


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


@lru_cache(maxsize=1)
def get_mailcow_settings() -> MailcowSettings:
    return MailcowSettings()


@lru_cache(maxsize=1)
def get_mail_provisioning_settings() -> MailProvisioningSettings:
    return MailProvisioningSettings()


@lru_cache(maxsize=1)
def get_desec_settings() -> DeSECSettings:
    return DeSECSettings()

