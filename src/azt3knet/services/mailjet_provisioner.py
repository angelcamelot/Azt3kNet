"""Mailjet provisioning helpers."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any, Callable

import httpx

from azt3knet.core.mail_config import MailProvisioningSettings, MailjetSettings
from azt3knet.services.resilient_http_client import (
    ResilientHTTPClient,
    RetryConfiguration,
)

logger = logging.getLogger(__name__)


@dataclass
class MailboxCredentials:
    """Credentials associated with a managed virtual mailbox."""

    address: str
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    inbound_url: str | None = None
    inbound_secret: str | None = None


class MailjetProvisioner:
    """Wrapper around the Mailjet API for agent onboarding."""

    _DOMAIN_ENDPOINT = "/v3/REST/domain"
    _INBOUND_ENDPOINT = "/v3/REST/inbound"

    def __init__(
        self,
        mailjet: MailjetSettings,
        provisioning: MailProvisioningSettings,
        *,
        client: ResilientHTTPClient | httpx.Client | None = None,
        client_factory: Callable[[MailjetSettings], httpx.Client] | None = None,
    ) -> None:
        self._mailjet = mailjet
        self._provisioning = provisioning
        if isinstance(client, ResilientHTTPClient):
            self._client = client
        else:
            http_client = client or (
                client_factory(mailjet)
                if client_factory
                else httpx.Client(
                    base_url=mailjet.base_url,
                    auth=(mailjet.api_key, mailjet.api_secret),
                    timeout=30.0,
                )
            )
            retry_config = RetryConfiguration(max_retries=4, backoff_factor=0.75)
            self._client = ResilientHTTPClient(
                http_client,
                service_name="mailjet",
                retry_config=retry_config,
            )

    # ------------------------------------------------------------------
    # Context manager helpers
    # ------------------------------------------------------------------
    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "MailjetProvisioner":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        self.close()

    # ------------------------------------------------------------------
    # API helpers
    # ------------------------------------------------------------------
    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        request_path = path
        if not httpx.URL(path).is_absolute_url:
            request_path = path.lstrip("/")
        response = self._client.request(method, request_path, **kwargs)
        response.raise_for_status()
        return response

    # ------------------------------------------------------------------
    # Domain management
    # ------------------------------------------------------------------
    def ensure_domain(self) -> None:
        """Ensure the configured domain is registered in Mailjet."""

        domain = self._provisioning.domain
        logger.debug("Ensuring Mailjet domain %s", domain)
        response = self._client.request("GET", f"{self._DOMAIN_ENDPOINT}/{domain}")
        if response.status_code == 404:
            logger.info("Registering Mailjet domain %s", domain)
            payload = {"Name": domain}
            self._request("POST", self._DOMAIN_ENDPOINT, json=payload)
            return
        response.raise_for_status()

    def get_dkim_key(self) -> str:
        """Return the public DKIM key for the configured domain."""

        domain = self._provisioning.domain
        response = self._request("GET", f"{self._DOMAIN_ENDPOINT}/{domain}")
        payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError("Unexpected Mailjet domain response payload")
        key = payload.get("DKIMPublicKey") or payload.get("DKIMKey")
        if not key:
            raise RuntimeError("Mailjet did not return a DKIM key")
        return str(key)

    # ------------------------------------------------------------------
    # Inbound processing helpers
    # ------------------------------------------------------------------
    def ensure_inbound_route(self, address: str) -> None:
        """Ensure an inbound webhook exists for the mailbox address."""

        if not self._mailjet.inbound_webhook_url:
            logger.debug("Inbound webhook disabled; skipping route setup")
            return

        route_payload = {
            "Url": self._mailjet.inbound_webhook_url,
            "Email": address,
            "Version": "2",
            "Status": "enabled",
        }
        if self._mailjet.inbound_webhook_secret:
            route_payload["SecretKey"] = self._mailjet.inbound_webhook_secret

        logger.info("Configuring Mailjet inbound route for %s", address)
        self._request("POST", self._INBOUND_ENDPOINT, json=route_payload)

    # ------------------------------------------------------------------
    # Mailbox provisioning
    # ------------------------------------------------------------------
    def _mailbox_local_part(self, agent_id: str) -> str:
        return f"{self._provisioning.agent_mail_prefix}{agent_id}"

    def create_agent_mailbox(
        self,
        agent_id: str,
        *,
        display_name: str | None = None,
        apply_prefix: bool = True,
    ) -> MailboxCredentials:
        """Create a logical mailbox for an agent and return its credentials."""

        if "@" in agent_id:
            raise ValueError("agent_id must be a local-part identifier without domain")

        local_part = self._mailbox_local_part(agent_id) if apply_prefix else agent_id
        address = f"{local_part}@{self._provisioning.domain}"

        self.ensure_inbound_route(address)

        return MailboxCredentials(
            address=address,
            smtp_host=self._mailjet.smtp_host,
            smtp_port=self._mailjet.smtp_port,
            smtp_username=self._mailjet.smtp_username,
            smtp_password=self._mailjet.smtp_password,
            inbound_url=self._mailjet.inbound_webhook_url,
            inbound_secret=self._mailjet.inbound_webhook_secret,
        )


__all__ = ["MailboxCredentials", "MailjetProvisioner"]
