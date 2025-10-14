"""Bootstrap DNS records for Azt3kNet managed domains using Mailjet and Cloudflare."""

from __future__ import annotations

import logging
import os
from typing import Callable, Sequence

import httpx

from azt3knet.core.mail_config import (
    CloudflareDNSSettings,
    CloudflareTunnelSettings,
    MailProvisioningSettings,
    MailjetSettings,
)
from azt3knet.services import CloudflareDNSManager, MailjetProvisioner

LOGGER = logging.getLogger(__name__)


def bootstrap_dns(
    *,
    mailjet_settings: MailjetSettings | None = None,
    provisioning_settings: MailProvisioningSettings | None = None,
    cloudflare_dns: CloudflareDNSSettings | None = None,
    cloudflare_settings: CloudflareTunnelSettings | None = None,
    mail_provisioner_factory: Callable[[MailjetSettings, MailProvisioningSettings], MailjetProvisioner]
        | None = None,
    dns_manager_factory: Callable[[CloudflareDNSSettings], CloudflareDNSManager] | None = None,
    mx_records: Sequence[str] | None = None,
) -> None:
    """Synchronise Mailjet and Cloudflare DNS state for the managed domain."""

    mailjet_settings = mailjet_settings or MailjetSettings()
    provisioning_settings = provisioning_settings or MailProvisioningSettings()
    cloudflare_dns = cloudflare_dns or CloudflareDNSSettings()
    cloudflare_settings = cloudflare_settings or CloudflareTunnelSettings()
    mail_provisioner_factory = mail_provisioner_factory or MailjetProvisioner
    dns_manager_factory = dns_manager_factory or CloudflareDNSManager

    computed_mx_records: Sequence[str] = (
        mx_records if mx_records else (mailjet_settings.mx_hosts or ("in.mailjet.com",))
    )

    LOGGER.info("Bootstrapping DNS records for domain %s", cloudflare_dns.zone_name)

    with mail_provisioner_factory(mailjet_settings, provisioning_settings) as mailjet:
        mailjet.ensure_domain()
        dkim_key = mailjet.get_dkim_key()

    with dns_manager_factory(cloudflare_dns) as dns_manager:
        dns_manager.bootstrap_mail_records(
            mx_records=computed_mx_records,
            dkim_key=dkim_key,
            ttl=provisioning_settings.default_ttl,
            spf_policy=f"v=spf1 {mailjet_settings.spf_include} -all",
        )

        cname_target = cloudflare_settings.normalised_cname_target()
        if cname_target:
            subname = cloudflare_settings.cname_subdomain
            if not subname:
                hostname = cloudflare_settings.hostname
                suffix = f".{cloudflare_dns.zone_name}"
                if hostname and hostname.endswith(suffix):
                    subname = hostname[: -len(suffix)].rstrip(".") or "@"
                elif hostname and hostname == cloudflare_dns.zone_name:
                    subname = "@"
            subname = subname or "@"
            dns_manager.upsert_cname(
                subname=subname,
                target=cname_target,
                ttl=cloudflare_settings.cname_ttl or provisioning_settings.default_ttl,
            )

    LOGGER.info("DNS bootstrap complete for domain %s", cloudflare_dns.zone_name)


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
