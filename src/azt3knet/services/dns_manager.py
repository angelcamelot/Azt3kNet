"""deSEC DNS automation helpers."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Iterable, List, Sequence

import httpx

from azt3knet.core.mail_config import DeSECSettings

logger = logging.getLogger(__name__)


@dataclass
class RRSet:
    """Representation of a DNS RRset for deSEC."""

    subname: str
    type: str
    records: Sequence[str]
    ttl: int

    def as_payload(self) -> dict[str, object]:
        """Return the RRset as a payload suitable for the deSEC API."""

        return {
            "subname": self.subname,
            "type": self.type,
            "records": list(self.records),
            "ttl": self.ttl,
        }


class DeSECDNSManager:
    """Client wrapper around the deSEC DNS API."""

    _PUBLIC_IP_URL = "https://api.ipify.org"

    def __init__(
        self,
        settings: DeSECSettings,
        *,
        client: httpx.Client | None = None,
        dyn_client: httpx.Client | None = None,
    ) -> None:
        self._settings = settings
        base_url = settings.api_base.rstrip("/")
        self._client = client or httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Token {settings.token}"},
            timeout=30.0,
        )
        self._dyn_client = dyn_client or httpx.Client(timeout=10.0)

    def close(self) -> None:
        """Close any managed HTTP clients."""

        self._client.close()
        self._dyn_client.close()

    def __enter__(self) -> "DeSECDNSManager":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        self.close()

    # ------------------------------------------------------------------
    # Core API helpers
    # ------------------------------------------------------------------
    def list_rrsets(self) -> list[dict[str, object]]:
        """Return all RRsets for the configured domain."""

        response = self._client.get(f"domains/{self._settings.domain}/rrsets/")
        response.raise_for_status()
        payload = response.json()
        assert isinstance(payload, list)
        return payload  # type: ignore[return-value]

    def upsert_rrset(self, rrset: RRSet) -> None:
        """Create or update an RRset using PUT semantics."""

        logger.debug("Upserting RRset %s.%s", rrset.subname, rrset.type)
        response = self._client.put(
            f"domains/{self._settings.domain}/rrsets/{rrset.type}/{rrset.subname or '@'}/",
            json=rrset.as_payload(),
        )
        response.raise_for_status()

    def bulk_upsert(self, rrsets: Iterable[RRSet]) -> None:
        """Upsert multiple RRsets in a single request."""

        payload = [rrset.as_payload() for rrset in rrsets]
        logger.debug("Bulk upserting %d RRsets", len(payload))
        response = self._client.patch(
            f"domains/{self._settings.domain}/rrsets/",
            json=payload,
        )
        response.raise_for_status()

    def delete_rrset(self, subname: str, rrtype: str) -> None:
        """Delete an RRset from the domain."""

        logger.debug("Deleting RRset %s %s", subname, rrtype)
        response = self._client.delete(
            f"domains/{self._settings.domain}/rrsets/{rrtype}/{subname or '@'}/"
        )
        response.raise_for_status()

    # ------------------------------------------------------------------
    # Higher level orchestration helpers
    # ------------------------------------------------------------------
    def bootstrap_mail_records(
        self,
        *,
        mx_records: Sequence[str],
        dkim_key: str,
        ttl: int | None = None,
        spf_policy: str | None = None,
        dmarc_policy: str | None = None,
        a_record_host: str | None = None,
        a_record_ip: str | None = None,
    ) -> None:
        """Ensure that all DNS records required for the Mailjet stack exist."""

        if not mx_records:
            raise ValueError("mx_records must contain at least one host")

        ttl = ttl or self._settings.default_ttl
        spf_policy = spf_policy or "v=spf1 mx -all"
        dmarc_policy = dmarc_policy or (
            f"v=DMARC1; p=none; rua=mailto:postmaster@{self._settings.domain}"
        )

        rrsets: List[RRSet] = [
            RRSet(
                subname="@",
                type="MX",
                records=[
                    f"{priority * 10} {host.rstrip('.')}."
                    for priority, host in enumerate(mx_records, start=1)
                ],
                ttl=ttl,
            ),
            RRSet(subname="@", type="TXT", records=[f'"{spf_policy}"'], ttl=ttl),
            RRSet(subname="_dmarc", type="TXT", records=[f'"{dmarc_policy}"'], ttl=ttl),
            RRSet(
                subname="mail._domainkey",
                type="TXT",
                records=[dkim_key if dkim_key.startswith('"') else f'"{dkim_key}"'],
                ttl=ttl,
            ),
        ]
        if a_record_host and a_record_ip:
            rrsets.append(
                RRSet(
                    subname=a_record_host,
                    type="A",
                    records=[a_record_ip],
                    ttl=ttl,
                )
            )
        logger.info("Bootstrapping %d mail-related DNS RRsets", len(rrsets))
        self.bulk_upsert(rrsets)

    def sync_dkim_record(self, dkim_key: str, *, ttl: int | None = None) -> None:
        """Update the DKIM TXT record with the latest key from Mailjet."""

        ttl = ttl or self._settings.default_ttl
        record = dkim_key if dkim_key.startswith('"') else f'"{dkim_key}"'
        rrset = RRSet(
            subname="mail._domainkey",
            type="TXT",
            records=[record],
            ttl=ttl,
        )
        self.upsert_rrset(rrset)

    # ------------------------------------------------------------------
    # DynDNS helpers
    # ------------------------------------------------------------------
    def update_dyndns(self, *, hostname: str | None = None, ip_address: str | None = None) -> str:
        """Trigger a DynDNS update for the managed hostname."""

        hostname = hostname or self._settings.domain
        logger.debug("Updating DynDNS for %s", hostname)
        response = self._dyn_client.get(
            self._settings.dyndns_update_url,
            params={"hostname": hostname, **({"myip": ip_address} if ip_address else {})},
            auth=(self._settings.domain, self._settings.token),
        )
        response.raise_for_status()
        return response.text.strip()

    def lookup_public_ip(self) -> str:
        """Return the detected public IP using a simple external service."""

        response = self._dyn_client.get(self._PUBLIC_IP_URL, params={"format": "json"})
        response.raise_for_status()
        data = response.json()
        ip = data.get("ip") if isinstance(data, dict) else None
        if not ip:
            raise RuntimeError("Unable to determine public IP from deSEC lookup service")
        return str(ip)

