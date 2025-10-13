"""Bootstrap deSEC DNS records based on the current Mailcow state."""

from __future__ import annotations

import argparse
import logging
from typing import Optional

from azt3knet.core.mail_config import (
    get_desec_settings,
    get_mail_provisioning_settings,
    get_mailcow_settings,
)
from azt3knet.services import DeSECDNSManager, MailcowProvisioner


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mail-host",
        dest="mail_host",
        help="Override the mail host used for MX records",
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

    mailcow_settings = get_mailcow_settings()
    provisioning_settings = get_mail_provisioning_settings()
    desec_settings = get_desec_settings()

    mail_host = args.mail_host or mailcow_settings.smtp_host or f"mail.{desec_settings.domain}"

    with MailcowProvisioner(mailcow_settings, provisioning_settings) as mailcow:
        mailcow.ensure_domain()
        mailcow.configure_relay()
        dkim_key = mailcow.get_dkim_key()

    with DeSECDNSManager(desec_settings) as dns_manager:
        public_ip = args.public_ip or dns_manager.lookup_public_ip()
        dns_manager.bootstrap_mail_records(
            mail_host=mail_host,
            public_ip=public_ip,
            dkim_key=dkim_key,
            ttl=provisioning_settings.default_ttl,
        )
        dns_manager.update_dyndns(hostname=desec_settings.domain, ip_address=public_ip)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

