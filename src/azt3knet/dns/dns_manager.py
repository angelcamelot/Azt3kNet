"""Helpers for managing DNS records via the deSEC API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol


@dataclass
class RRSet:
    """Minimal representation of a deSEC RRset."""

    name: str
    rtype: str
    records: list[str]
    ttl: int = 3600


class DNSManager(Protocol):
    """Contract that DNS manager implementations must follow."""

    async def upsert_rrset(
        self, name: str, rtype: str, records: Iterable[str], *, ttl: int = 3600
    ) -> None:
        """Create or update an RRset in deSEC."""

    async def delete_rrset(self, name: str, rtype: str) -> None:
        """Delete an RRset if it exists."""


class DeSECDNSManager:
    """Concrete implementation placeholder."""

    def __init__(self, *, api_base: str, token: str, domain: str) -> None:
        self.api_base = api_base.rstrip("/")
        self.token = token
        self.domain = domain

    async def upsert_rrset(
        self, name: str, rtype: str, records: Iterable[str], *, ttl: int = 3600
    ) -> None:  # pragma: no cover - stub
        """TODO: Implement HTTP PATCH call to deSEC."""

        raise NotImplementedError

    async def delete_rrset(self, name: str, rtype: str) -> None:  # pragma: no cover - stub
        """TODO: Implement RRset deletion."""

        raise NotImplementedError


__all__ = ["RRSet", "DNSManager", "DeSECDNSManager"]
