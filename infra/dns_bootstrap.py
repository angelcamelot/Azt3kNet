"""Bootstrap DNS records for Azt3kNet managed domains.

The module orchestrates the initial synchronisation between Mailcow and deSEC.
It is meant to be executed from within the ``azt3knet-dns-bootstrap`` container
once the Mailcow stack is healthy.
"""

from __future__ import annotations

import logging
import os
from typing import Callable

import httpx

from azt3knet.core.mail_config import (
    DeSECSettings,
    MailProvisioningSettings,
    MailcowSettings,
)
from azt3knet.services import DeSECDNSManager, MailcowProvisioner

LOGGER = logging.getLogger(__name__)


def bootstrap_dns(
    *,
    mailcow_settings: MailcowSettings | None = None,
    provisioning_settings: MailProvisioningSettings | None = None,
    desec_settings: DeSECSettings | None = None,
    mail_provisioner_factory: Callable[[MailcowSettings, MailProvisioningSettings], MailcowProvisioner]
    | None = None,
    dns_manager_factory: Callable[[DeSECSettings], DeSECDNSManager] | None = None,
    mail_host: str | None = None,
    public_ip: str | None = None,
) -> None:
    """Synchronise Mailcow and deSEC state for the managed domain."""

    mailcow_settings = mailcow_settings or MailcowSettings()
    provisioning_settings = provisioning_settings or MailProvisioningSettings()
    desec_settings = desec_settings or DeSECSettings()
    mail_provisioner_factory = mail_provisioner_factory or MailcowProvisioner
    dns_manager_factory = dns_manager_factory or DeSECDNSManager

    computed_mail_host = (
        mail_host
        or mailcow_settings.smtp_host
        or (f"mail.{desec_settings.domain}" if desec_settings.domain else "mail")
    )

    LOGGER.info("Bootstrapping DNS records for domain %s", desec_settings.domain)

    with mail_provisioner_factory(mailcow_settings, provisioning_settings) as mailcow:
        mailcow.ensure_domain()
        mailcow.configure_relay()
        dkim_key = mailcow.get_dkim_key()

    with dns_manager_factory(desec_settings) as dns_manager:
        resolved_ip = public_ip or dns_manager.lookup_public_ip()
        dns_manager.bootstrap_mail_records(
            mail_host=computed_mail_host,
            public_ip=resolved_ip,
            dkim_key=dkim_key,
            ttl=provisioning_settings.default_ttl,
        )
        dns_manager.update_dyndns(hostname=desec_settings.domain, ip_address=resolved_ip)

    LOGGER.info("DNS bootstrap complete for domain %s", desec_settings.domain)


def _configure_logging() -> None:
    level_name = os.getenv("AZT3KNET_LOG_LEVEL", "INFO").upper()
    level = logging.getLevelName(level_name)
    if isinstance(level, str):
        level = logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s %(name)s: %(message)s")


def main() -> int:
    """Entry point executed inside the azt3knet-dns-bootstrap container."""

    _configure_logging()

    try:
        bootstrap_dns()
    except httpx.HTTPStatusError as exc:  # pragma: no cover - exercised via tests
        request_url = getattr(exc.request, "url", "<unknown>")
        status = getattr(exc.response, "status_code", "<no-status>")
        LOGGER.error(
            "HTTP status error while bootstrapping DNS (status=%s, url=%s): %s",
            status,
            request_url,
            exc,
        )
        return 2
    except httpx.HTTPError as exc:  # pragma: no cover - exercised via tests
        LOGGER.error("HTTP client error during DNS bootstrap: %s", exc)
        return 3
    except Exception:  # pragma: no cover
        LOGGER.exception("Unexpected error during DNS bootstrap")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
