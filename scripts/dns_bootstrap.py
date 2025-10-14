"""Bootstrap deSEC DNS records based on the current Mailjet state."""

from __future__ import annotations

import argparse
import logging
from typing import Optional

from azt3knet.core.mail_config import (
    get_cloudflare_tunnel_settings,
    get_desec_settings,
    get_mail_provisioning_settings,
    get_mailjet_settings,
)
from azt3knet.services import DeSECDNSManager, MailjetProvisioner


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mx-host",
        dest="mx_hosts",
        action="append",
        help="Override the MX host(s) used for Mailjet",
    )
    parser.add_argument(
        "--public-ip",
        dest="public_ip",
        help="Provide an explicit public IP instead of discovery",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Python logging level",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(level=args.log_level.upper(), format="%(levelname)s %(name)s: %(message)s")

    mailjet_settings = get_mailjet_settings()
    provisioning_settings = get_mail_provisioning_settings()
    desec_settings = get_desec_settings()
    cloudflare_settings = get_cloudflare_tunnel_settings()

    mx_hosts = tuple(args.mx_hosts) if args.mx_hosts else mailjet_settings.mx_hosts

    with MailjetProvisioner(mailjet_settings, provisioning_settings) as mailjet:
        mailjet.ensure_domain()
        dkim_key = mailjet.get_dkim_key()

    with DeSECDNSManager(desec_settings) as dns_manager:
        public_ip = args.public_ip or dns_manager.lookup_public_ip()
        dns_manager.bootstrap_mail_records(
            mx_records=mx_hosts,
            dkim_key=dkim_key,
            ttl=provisioning_settings.default_ttl,
            spf_policy=f"v=spf1 {mailjet_settings.spf_include} -all",
            a_record_host="mail" if public_ip else None,
            a_record_ip=public_ip if public_ip else None,
        )
        dns_manager.update_dyndns(hostname=desec_settings.domain, ip_address=public_ip)

        cname_target = cloudflare_settings.normalised_cname_target()
        if cname_target:
            subname = cloudflare_settings.cname_subdomain
            if not subname:
                hostname = cloudflare_settings.hostname
                suffix = f".{desec_settings.domain}"
                if hostname and hostname.endswith(suffix):
                    subname = hostname[: -len(suffix)].rstrip(".") or "@"
                elif hostname and hostname == desec_settings.domain:
                    subname = "@"
            subname = subname or "@"
            dns_manager.upsert_cname(
                subname=subname,
                target=cname_target,
                ttl=cloudflare_settings.cname_ttl or provisioning_settings.default_ttl,
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

