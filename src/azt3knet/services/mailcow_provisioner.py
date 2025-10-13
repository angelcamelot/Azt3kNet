"""Mailcow provisioning helpers."""

from __future__ import annotations

from dataclasses import dataclass
import logging
import secrets
import string
from typing import Any

import httpx

from azt3knet.core.mail_config import MailProvisioningSettings, MailcowSettings
from azt3knet.services.resilient_http_client import (
    ResilientHTTPClient,
    RetryConfiguration,
)

logger = logging.getLogger(__name__)


@dataclass
class MailboxCredentials:
    """Credentials associated with a managed mailbox."""

    address: str
    password: str
    app_password: str | None
    smtp_host: str
    smtp_port: int
    imap_host: str
    imap_port: int


class MailcowProvisioner:
    """Thin wrapper around the Mailcow API for agent onboarding."""

    def __init__(
        self,
        mailcow: MailcowSettings,
        provisioning: MailProvisioningSettings,
        *,
        client: ResilientHTTPClient | httpx.Client | None = None,
    ) -> None:
        self._mailcow = mailcow
        self._provisioning = provisioning
        self._client: ResilientHTTPClient
        if isinstance(client, ResilientHTTPClient):
            self._client = client
        else:
            http_client = client or httpx.Client(
                base_url=mailcow.base_url,
                headers={"X-API-Key": mailcow.api_key},
                timeout=30.0,
                verify=mailcow.verify_tls,
            )
            retry_config = RetryConfiguration(max_retries=4, backoff_factor=0.75)
            self._client = ResilientHTTPClient(
                http_client,
                service_name="mailcow",
                retry_config=retry_config,
            )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "MailcowProvisioner":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        self.close()

    # ------------------------------------------------------------------
    # API helpers
    # ------------------------------------------------------------------
    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        response = self._client.request(method, path, **kwargs)
        response.raise_for_status()
        return response

    def ensure_domain(self) -> None:
        """Ensure the configured domain exists in Mailcow."""

        domains = self.list_domains()
        if any(domain_info.get("domain") == self._provisioning.domain for domain_info in domains):
            return
        logger.info("Creating Mailcow domain %s", self._provisioning.domain)
        payload = {"domain": self._provisioning.domain, "active": "1"}
        self._request("POST", "/add/domain", json=payload)

    def list_domains(self) -> list[dict[str, Any]]:
        response = self._request("GET", "/get/domain/all")
        payload = response.json()
        assert isinstance(payload, list)
        return payload  # type: ignore[return-value]

    def get_dkim_key(self) -> str:
        """Return the public DKIM key for the configured domain."""

        response = self._request("GET", f"/get/dkim/{self._provisioning.domain}")
        payload = response.json()
        if isinstance(payload, dict):
            for key in ("public", "dkim", "value"):
                if key in payload:
                    return str(payload[key])
        if isinstance(payload, list):
            for item in payload:
                if isinstance(item, dict):
                    for key in ("public", "dkim", "value"):
                        if key in item:
                            return str(item[key])
        raise RuntimeError("Unable to retrieve DKIM key from Mailcow API response")

    def _mailbox_local_part(self, agent_id: str) -> str:
        return f"{self._provisioning.agent_mail_prefix}{agent_id}"

    @staticmethod
    def generate_password(length: int = 24) -> str:
        alphabet = string.ascii_letters + string.digits
        return "".join(secrets.choice(alphabet) for _ in range(length))

    def create_agent_mailbox(
        self,
        agent_id: str,
        *,
        display_name: str | None = None,
        password: str | None = None,
        quota_mb: int | None = None,
    ) -> MailboxCredentials:
        """Create a mailbox for an agent and return its credentials."""

        local_part = self._mailbox_local_part(agent_id)
        if password is None:
            password = self.generate_password()
        if quota_mb is None:
            quota_mb = self._provisioning.mailbox_quota_mb

        payload: dict[str, Any] = {
            "active": "1",
            "domain": self._provisioning.domain,
            "local_part": local_part,
            "name": display_name or agent_id,
            "password": password,
            "quota": quota_mb,
        }
        if self._provisioning.rate_limit_per_hour:
            payload["rl_value"] = self._provisioning.rate_limit_per_hour
            payload["rl_frame"] = 3600
        logger.info("Creating mailbox %s@%s", local_part, self._provisioning.domain)
        self._request("POST", "/add/mailbox", json=payload)

        address = f"{local_part}@{self._provisioning.domain}"
        app_password = self.create_app_password(address)

        return MailboxCredentials(
            address=address,
            password=password,
            app_password=app_password,
            smtp_host=self._mailcow.smtp_host,
            smtp_port=self._mailcow.smtp_port,
            imap_host=self._mailcow.imap_host,
            imap_port=self._mailcow.imap_port,
        )

    def delete_agent_mailbox(self, agent_id: str) -> None:
        """Delete the mailbox associated with an agent."""

        local_part = self._mailbox_local_part(agent_id)
        address = f"{local_part}@{self._provisioning.domain}"
        logger.info("Deleting mailbox %s", address)
        self._request("POST", "/delete/mailbox", json={"mailbox": [address]})

    def create_app_password(self, address: str, *, description: str | None = None) -> str:
        """Generate an application specific password for the mailbox."""

        payload = {
            "username": address,
            "pass_app_name": description or "Azt3kNet agent",
        }
        response = self._request("POST", "/add/app-passwd", json=payload)
        data = response.json()
        if isinstance(data, dict):
            password = data.get("password") or data.get("app_passwd")
            if password:
                return str(password)
        raise RuntimeError("Mailcow did not return an application password")

    def configure_relay(self) -> None:
        """Configure an outbound SMTP relay if credentials are provided."""

        if not self._mailcow.relay_host:
            logger.debug("Relay host not configured; skipping relay setup")
            return
        payload = {
            "relayhost": self._mailcow.relay_host,
            "relayport": self._mailcow.relay_port,
            "relay_user": self._mailcow.relay_user,
            "relay_pass": self._mailcow.relay_password,
            "relay_active": 1,
        }
        logger.info("Configuring Mailcow relay host %s", self._mailcow.relay_host)
        self._request("POST", "/edit/config/relayhost", json=payload)

