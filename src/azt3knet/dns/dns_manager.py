"""Asynchronous helpers for managing DNS records via the deSEC API."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Iterable, Protocol, Sequence

import httpx

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RRSet:
    """Representation of a DNS resource record set."""

    name: str
    rtype: str
    records: Sequence[str]
    ttl: int = 3600

    def as_payload(self) -> dict[str, object]:
        """Return the payload expected by the deSEC API."""

        return {
            "subname": self.name or "@",
            "type": self.rtype,
            "ttl": self.ttl,
            "records": list(self.records),
        }


class DNSManager(Protocol):
    """Contract implemented by DNS manager clients."""

    async def upsert_rrset(
        self,
        name: str,
        rtype: str,
        records: Iterable[str],
        *,
        ttl: int = 3600,
    ) -> None:
        """Create or update an RRset."""

    async def delete_rrset(self, name: str, rtype: str) -> None:
        """Delete an RRset if it exists."""


class DeSECDNSManager:
    """Asynchronous client wrapper around the deSEC DNS REST API."""

    def __init__(
        self,
        *,
        api_base: str,
        token: str,
        domain: str,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._domain = domain
        self._base_url = api_base.rstrip("/")
        self._owns_client = client is None
        if client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                headers={"Authorization": f"Token {token}"},
                timeout=30.0,
            )
        else:
            client.headers.setdefault("Authorization", f"Token {token}")
            self._client = client

    async def close(self) -> None:
        """Release the underlying HTTP client if owned by this instance."""

        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> "DeSECDNSManager":  # pragma: no cover - convenience
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # pragma: no cover - convenience
        await self.close()

    # ------------------------------------------------------------------
    # Core helpers
    # ------------------------------------------------------------------
    def _rrset_path(self, name: str, rtype: str) -> str:
        identifier = name or "@"
        return f"domains/{self._domain}/rrsets/{rtype}/{identifier}/"

    def _url(self, path: str) -> str:
        if path.startswith("http://") or path.startswith("https://"):
            return path
        base = self._base_url.rstrip("/")
        return f"{base}/{path.lstrip('/')}"

    async def upsert_rrset(
        self,
        name: str,
        rtype: str,
        records: Iterable[str],
        *,
        ttl: int = 3600,
    ) -> None:
        """Create or update an RRset using PUT semantics."""

        payload = RRSet(name=name, rtype=rtype, records=list(records), ttl=ttl).as_payload()
        logger.debug("Upserting RRset %s %s -> %s", name or "@", rtype, payload["records"])
        response = await self._client.put(self._url(self._rrset_path(name, rtype)), json=payload)
        response.raise_for_status()

    async def bulk_upsert(self, rrsets: Iterable[RRSet]) -> None:
        """Upsert multiple RRsets in a single PATCH request."""

        payload = [rrset.as_payload() for rrset in rrsets]
        if not payload:
            return
        logger.debug("Bulk upserting %d RRsets", len(payload))
        response = await self._client.patch(
            self._url(f"domains/{self._domain}/rrsets/"),
            json=payload,
        )
        response.raise_for_status()

    async def delete_rrset(self, name: str, rtype: str) -> None:
        """Delete an RRset, treating missing records as a success."""

        logger.debug("Deleting RRset %s %s", name or "@", rtype)
        response = await self._client.delete(self._url(self._rrset_path(name, rtype)))
        if response.status_code == 404:
            logger.debug("RRset %s %s already absent", name or "@", rtype)
            return
        response.raise_for_status()


__all__ = ["DNSManager", "DeSECDNSManager", "RRSet"]

