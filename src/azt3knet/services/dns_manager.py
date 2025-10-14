"""Cloudflare DNS automation helpers."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Callable, Mapping, Sequence

import httpx

from azt3knet.core.mail_config import CloudflareDNSSettings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DNSRecord:
    """Representation of a DNS record managed through Cloudflare."""

    content: str
    ttl: int
    priority: int | None = None
    proxied: bool | None = None

    def key(self) -> tuple[object | None, ...]:
        return (self.content, self.priority)


class CloudflareAPIError(RuntimeError):
    """Raised when Cloudflare returns an error payload."""


class CloudflareDNSManager:
    """Client wrapper around the Cloudflare DNS API."""

    def __init__(
        self,
        settings: CloudflareDNSSettings,
        *,
        client: httpx.Client | None = None,
    ) -> None:
        if not settings.zone_id:
            raise ValueError("Cloudflare zone identifier is required")
        if not settings.zone_name:
            raise ValueError("Cloudflare zone name is required")
        if not settings.api_token:
            raise ValueError("Cloudflare API token is required")

        self._settings = settings
        base_url = settings.api_base.rstrip("/") or "https://api.cloudflare.com/client/v4"
        headers = {
            "Authorization": f"Bearer {settings.api_token}",
            "Content-Type": "application/json",
        }
        self._client = client or httpx.Client(base_url=base_url, headers=headers, timeout=30.0)
        if client is not None:
            client.headers.update(headers)
        self._owns_client = client is None

    # ------------------------------------------------------------------
    # Context manager helpers
    # ------------------------------------------------------------------
    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "CloudflareDNSManager":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        self.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _request(self, method: str, path: str, **kwargs) -> Mapping[str, object]:
        url = path
        if not httpx.URL(path).is_absolute_url:
            url = f"/zones/{self._settings.zone_id}/{path.lstrip('/')}"
        response = self._client.request(method, url, **kwargs)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, Mapping):
            raise CloudflareAPIError("Unexpected Cloudflare response payload")
        if payload.get("success") is False:
            errors = payload.get("errors")
            raise CloudflareAPIError(f"Cloudflare API error: {errors}")
        return payload

    def _absolute_name(self, name: str) -> str:
        if not name or name == "@":
            return self._settings.zone_name
        if name.endswith(f".{self._settings.zone_name}"):
            return name
        return f"{name}.{self._settings.zone_name}"

    def _list_records(self, name: str, rtype: str) -> list[Mapping[str, object]]:
        params = {
            "name": self._absolute_name(name),
            "type": rtype,
            "per_page": 100,
        }
        payload = self._request("GET", "dns_records", params=params)
        result = payload.get("result", [])
        if not isinstance(result, list):
            raise CloudflareAPIError("Cloudflare DNS list response malformed")
        return [record for record in result if isinstance(record, Mapping)]

    def _record_matches(self, existing: Mapping[str, object], desired: DNSRecord) -> bool:
        if existing.get("content") != desired.content:
            return False
        if int(existing.get("ttl", desired.ttl)) != desired.ttl:
            return False
        if existing.get("priority") != desired.priority:
            return False
        proxied = existing.get("proxied")
        if desired.proxied is not None and proxied != desired.proxied:
            return False
        return True

    def _create_record(self, name: str, rtype: str, record: DNSRecord) -> None:
        payload = {
            "type": rtype,
            "name": self._absolute_name(name),
            "content": record.content,
            "ttl": record.ttl,
        }
        if record.priority is not None:
            payload["priority"] = record.priority
        if record.proxied is not None:
            payload["proxied"] = record.proxied
        logger.info("Creating Cloudflare %s record for %s", rtype, payload["name"])
        self._request("POST", "dns_records", json=payload)

    def _update_record(self, identifier: str, name: str, rtype: str, record: DNSRecord) -> None:
        payload = {
            "type": rtype,
            "name": self._absolute_name(name),
            "content": record.content,
            "ttl": record.ttl,
        }
        if record.priority is not None:
            payload["priority"] = record.priority
        if record.proxied is not None:
            payload["proxied"] = record.proxied
        logger.info("Updating Cloudflare %s record %s", rtype, identifier)
        self._request("PUT", f"dns_records/{identifier}", json=payload)

    def _delete_record(self, identifier: str) -> None:
        logger.info("Deleting Cloudflare DNS record %s", identifier)
        self._request("DELETE", f"dns_records/{identifier}")

    def _prepare_existing_map(
        self,
        existing: Sequence[Mapping[str, object]],
    ) -> dict[tuple[object | None, ...], Mapping[str, object]]:
        prepared: dict[tuple[object | None, ...], Mapping[str, object]] = {}
        for record in existing:
            key = (record.get("content"), record.get("priority"))
            prepared[key] = record
        return prepared

    def replace_records(
        self,
        *,
        name: str,
        rtype: str,
        records: Sequence[DNSRecord],
        match: Callable[[Mapping[str, object]], bool] | None = None,
        purge: bool = True,
    ) -> None:
        """Ensure Cloudflare DNS contains the provided records for name/type."""

        existing = self._list_records(name, rtype)
        if match is not None:
            existing = [record for record in existing if match(record)]

        existing_map = self._prepare_existing_map(existing)
        desired_map = {record.key(): record for record in records}

        for key, record in desired_map.items():
            current = existing_map.pop(key, None)
            if current is None:
                self._create_record(name, rtype, record)
                continue
            identifier = str(current.get("id"))
            if not identifier:
                logger.warning("Skipping Cloudflare record without identifier: %s", current)
                continue
            if not self._record_matches(current, record):
                self._update_record(identifier, name, rtype, record)

        if purge:
            for record in existing_map.values():
                identifier = str(record.get("id"))
                if identifier:
                    self._delete_record(identifier)

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
    ) -> None:
        if not mx_records:
            raise ValueError("mx_records must contain at least one host")

        ttl = ttl or self._settings.default_ttl
        spf_policy = spf_policy or "v=spf1 mx -all"
        dmarc_policy = dmarc_policy or (
            f"v=DMARC1; p=none; rua=mailto:postmaster@{self._settings.zone_name}"
        )

        mx_desired = [
            DNSRecord(content=host.rstrip("."), ttl=ttl, priority=index * 10)
            for index, host in enumerate(mx_records, start=1)
        ]
        self.replace_records(name="@", rtype="MX", records=mx_desired)

        def _spf_match(record: Mapping[str, object]) -> bool:
            content = str(record.get("content", ""))
            return content.startswith("v=spf1")

        self.replace_records(
            name="@",
            rtype="TXT",
            records=[DNSRecord(content=spf_policy, ttl=ttl)],
            match=_spf_match,
            purge=True,
        )

        self.replace_records(
            name="_dmarc",
            rtype="TXT",
            records=[DNSRecord(content=dmarc_policy, ttl=ttl)],
        )

        self.replace_records(
            name="mail._domainkey",
            rtype="TXT",
            records=[DNSRecord(content=dkim_key, ttl=ttl)],
        )

    def sync_dkim_record(self, dkim_key: str, *, ttl: int | None = None) -> None:
        ttl = ttl or self._settings.default_ttl
        self.replace_records(
            name="mail._domainkey",
            rtype="TXT",
            records=[DNSRecord(content=dkim_key, ttl=ttl)],
        )

    def upsert_cname(self, *, subname: str, target: str, ttl: int | None = None, proxied: bool | None = None) -> None:
        if not subname:
            raise ValueError("subname must not be empty")
        if not target:
            raise ValueError("target must not be empty")

        ttl = ttl or self._settings.default_ttl
        record = DNSRecord(content=target.rstrip("."), ttl=ttl, proxied=proxied)
        self.replace_records(name=subname, rtype="CNAME", records=[record])


__all__ = ["CloudflareDNSManager", "CloudflareAPIError", "DNSRecord"]
