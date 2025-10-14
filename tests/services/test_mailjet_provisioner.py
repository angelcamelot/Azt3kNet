import json
from typing import Any

import httpx
import pytest

from azt3knet.core.mail_config import MailProvisioningSettings, MailjetSettings
from azt3knet.services.mailjet_provisioner import MailboxCredentials, MailjetProvisioner


@pytest.fixture()
def mailjet_settings() -> MailjetSettings:
    return MailjetSettings(
        api_base="https://api.mailjet.com",
        api_key="public",
        api_secret="private",
        smtp_host="in-v3.mailjet.com",
        smtp_port=587,
        smtp_user="smtp-user",
        smtp_pass="smtp-pass",
        inbound_webhook_url="https://example.com/inbound",
        inbound_webhook_secret="token",
        mx_hosts=("in.mailjet.com", "in-v3.mailjet.com"),
    )


@pytest.fixture()
def provisioning_settings() -> MailProvisioningSettings:
    return MailProvisioningSettings(domain="example.com", agent_mail_prefix="bot_")


def _make_provisioner(
    settings: MailjetSettings,
    provisioning: MailProvisioningSettings,
    handler: Any,
) -> MailjetProvisioner:
    client = httpx.Client(transport=httpx.MockTransport(handler), base_url=settings.base_url)
    return MailjetProvisioner(settings, provisioning, client=client)


def test_ensure_domain_creates_missing_domain(
    mailjet_settings: MailjetSettings, provisioning_settings: MailProvisioningSettings
) -> None:
    calls: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        if request.method == "GET":
            return httpx.Response(404)
        if request.method == "POST":
            payload = json.loads(request.content.decode())
            assert payload == {"Name": provisioning_settings.domain}
            return httpx.Response(201)
        raise AssertionError("Unexpected request")

    provisioner = _make_provisioner(mailjet_settings, provisioning_settings, handler)
    provisioner.ensure_domain()

    assert calls == [("GET", "/v3/REST/domain/example.com"), ("POST", "/v3/REST/domain")]


def test_get_dkim_key_returns_value(
    mailjet_settings: MailjetSettings, provisioning_settings: MailProvisioningSettings
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        return httpx.Response(200, json={"DKIMPublicKey": "v=DKIM1; p=abc"})

    provisioner = _make_provisioner(mailjet_settings, provisioning_settings, handler)
    assert provisioner.get_dkim_key() == "v=DKIM1; p=abc"


def test_create_agent_mailbox_registers_inbound_route(
    mailjet_settings: MailjetSettings, provisioning_settings: MailProvisioningSettings
) -> None:
    requests: list[tuple[str, str, dict[str, Any]]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode()) if request.content else {}
        requests.append((request.method, request.url.path, payload))
        return httpx.Response(200, json={})

    provisioner = _make_provisioner(mailjet_settings, provisioning_settings, handler)
    credentials = provisioner.create_agent_mailbox("alpha")

    assert isinstance(credentials, MailboxCredentials)
    assert credentials.address == "bot_alpha@example.com"
    assert credentials.smtp_username == "smtp-user"
    assert credentials.inbound_secret == "token"

    assert requests == [
        (
            "POST",
            "/v3/REST/inbound",
            {
                "Url": mailjet_settings.inbound_webhook_url,
                "Email": "bot_alpha@example.com",
                "Version": "2",
                "Status": "enabled",
                "SecretKey": "token",
            },
        )
    ]


def test_create_agent_mailbox_skips_inbound_when_disabled(
    provisioning_settings: MailProvisioningSettings,
) -> None:
    settings = MailjetSettings(api_base="https://api.mailjet.com", api_key="k", api_secret="s")

    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("Should not hit inbound endpoint when webhook disabled")

    provisioner = _make_provisioner(settings, provisioning_settings, handler)
    credentials = provisioner.create_agent_mailbox("alpha")

    assert credentials.address.endswith("@example.com")
