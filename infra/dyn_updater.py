"""DynDNS updater for Azt3kNet using deSEC."""

from __future__ import annotations

import argparse
import logging
import os
from typing import Sequence

import httpx

from azt3knet.core.mail_config import DeSECSettings
from azt3knet.services import DeSECDNSManager

LOGGER = logging.getLogger(__name__)


def _configure_logging() -> None:
    """Initialise basic logging configuration for CLI execution."""

    level_name = os.getenv("AZT3KNET_LOG_LEVEL", "INFO").upper()
    level = logging.getLevelName(level_name)
    if isinstance(level, str):
        level = logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s %(name)s: %(message)s")


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Trigger a deSEC DynDNS refresh")
    parser.add_argument(
        "--hostname",
        help="Hostname to update (defaults to DESEC_DOMAIN)",
    )
    parser.add_argument(
        "--ip",
        dest="ip_address",
        help="Explicit IP address to associate (auto-detect when omitted)",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Execute a single synchronization from the public IP to deSEC DynDNS."""

    _configure_logging()
    args = _parse_args(argv)

    settings = DeSECSettings()
    target_hostname = args.hostname or settings.domain

    try:
        with DeSECDNSManager(settings) as dns_manager:
            resolved_ip = args.ip_address or dns_manager.lookup_public_ip()
            effective_hostname = target_hostname or settings.domain or None
            LOGGER.info(
                "Updating DynDNS for %s with IP %s",
                effective_hostname or "<default>",
                resolved_ip,
            )
            response = dns_manager.update_dyndns(
                hostname=effective_hostname,
                ip_address=resolved_ip,
            )
    except httpx.HTTPStatusError as exc:
        request_url = getattr(exc.request, "url", "<unknown>")
        status = getattr(exc.response, "status_code", "<no-status>")
        LOGGER.error(
            "HTTP status error while updating DynDNS (status=%s, url=%s): %s",
            status,
            request_url,
            exc,
        )
        return 2
    except httpx.HTTPError as exc:
        LOGGER.error("HTTP client error during DynDNS update: %s", exc)
        return 3
    except Exception:  # pragma: no cover
        LOGGER.exception("Unexpected error during DynDNS update")
        return 1

    LOGGER.info(
        "DynDNS update succeeded for %s (ip=%s): %s",
        effective_hostname or "<default>",
        resolved_ip,
        response,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
