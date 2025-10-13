"""Minimal structured logging bootstrap."""

import logging
from typing import Optional

from .config import get_settings


def configure_logging(level: Optional[str] = None) -> None:
    """Configure the standard logging stack.

    A structured logger (e.g. structlog) will arrive in a future sprint. For
    now, the basic configuration keeps timestamps and levels consistent across
    the CLI and API.
    """

    settings = get_settings()
    resolved_level = level or ("DEBUG" if settings.environment == "development" else "INFO")
    logging.basicConfig(
        level=resolved_level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


__all__ = ["configure_logging"]
