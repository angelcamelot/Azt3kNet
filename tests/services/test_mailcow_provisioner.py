from __future__ import annotations

import json

import httpx
import pytest

from azt3knet.core.mail_config import MailProvisioningSettings, MailcowSettings
from azt3knet.services.mailcow_provisioner import MailcowProvisioner


@pytest.fixture()
def mailcow_settings() -> MailcowSettings:
    return MailcowSettings(
        api_base="https://mail.example/api/v1",
        api_key="secret",
        smtp_host="mail.example",
        smtp_port=587,
        imap_host="mail.example",
        imap_port=993,
    )


@pytest.fixture()
def provisioning_settings() -> MailProvisioningSettings:
    return MailProvisioningSettings(
        domain="example.com",
        agent_mail_prefix="agent_",
        mailbox_quota_mb=1024,
        default_ttl=300,
        rate_limit_per_hour=100,
    )


def test_create_agent_mailbox_issues_expected_requests(
    mailcow_settings: MailcowSettings, provisioning_settings: MailProvisioningSettings
) -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        json_payload = json.loads(request.content.decode()) if request.content else {}
        calls.append((request.url.path, json_payload))
        if request.url.path.endswith("/add/mailbox"):
            assert request.url.path == "/api/v1/add/mailbox"
            assert json_payload["local_part"] == "agent_alpha"
            assert json_payload["rl_value"] == 100
            assert json_payload["password2"] == "s3cret"
            return httpx.Response(200, json={"status": "success"})
        if request.url.path.endswith("/add/app-passwd"):
            assert request.url.path == "/api/v1/add/app-passwd"
            return httpx.Response(200, json={"password": "app-secret"})
        raise AssertionError(f"Unexpected request to {request.url}")

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url=mailcow_settings.base_url,
    )

    provisioner = MailcowProvisioner(mailcow_settings, provisioning_settings, client=client)
    credentials = provisioner.create_agent_mailbox("alpha", display_name="Agent Alpha", password="s3cret")

    assert credentials.address == "agent_alpha@example.com"
    assert credentials.app_password == "app-secret"
    assert calls[0][0] == "/api/v1/add/mailbox"
    assert calls[1][0] == "/api/v1/add/app-passwd"


def test_create_agent_mailbox_preserves_falsy_values(
    mailcow_settings: MailcowSettings, provisioning_settings: MailProvisioningSettings
) -> None:
    calls: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        json_payload = json.loads(request.content.decode()) if request.content else {}
        if request.url.path.endswith("/add/mailbox"):
            assert request.url.path == "/api/v1/add/mailbox"
            calls.append(json_payload)
            return httpx.Response(200, json={"status": "success"})
        if request.url.path.endswith("/add/app-passwd"):
            assert request.url.path == "/api/v1/add/app-passwd"
            return httpx.Response(200, json={"password": "app-secret"})
        raise AssertionError(f"Unexpected request to {request.url}")

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url=mailcow_settings.base_url,
    )

    provisioner = MailcowProvisioner(mailcow_settings, provisioning_settings, client=client)
    credentials = provisioner.create_agent_mailbox(
        "empty", password="", quota_mb=0, display_name=""
    )

    assert calls, "Expected at least one mailbox creation call"
    payload = calls[0]
    assert payload["password"] == ""
    assert payload["password2"] == ""
    assert payload["force_pw_update"] == "0"
    assert payload["quota"] == 0
    assert credentials.password == ""


def test_create_agent_mailbox_respects_shared_password_and_prefix(
    mailcow_settings: MailcowSettings, provisioning_settings: MailProvisioningSettings
) -> None:
    provisioning_settings.agent_mail_password = "SharedSecret1"

    def handler(request: httpx.Request) -> httpx.Response:
        json_payload = json.loads(request.content.decode()) if request.content else {}
        if request.url.path.endswith("/add/mailbox"):
            assert json_payload["local_part"] == "jane.doe.123.20240101010101"
            assert json_payload["password"] == "SharedSecret1"
            assert json_payload["password2"] == "SharedSecret1"
            return httpx.Response(200, json={"status": "success"})
        if request.url.path.endswith("/add/app-passwd"):
            return httpx.Response(200, json={"password": "app-secret"})
        raise AssertionError(f"Unexpected request to {request.url}")

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url=mailcow_settings.base_url,
    )

    provisioner = MailcowProvisioner(mailcow_settings, provisioning_settings, client=client)
    credentials = provisioner.create_agent_mailbox(
        "jane.doe.123.20240101010101",
        display_name="Agent Jane",
        apply_prefix=False,
    )

    assert credentials.address == "jane.doe.123.20240101010101@example.com"
    assert credentials.password == "SharedSecret1"


def test_get_dkim_key_handles_list_response(
    mailcow_settings: MailcowSettings, provisioning_settings: MailProvisioningSettings
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/get/dkim/example.com"
        return httpx.Response(200, json=[{"public": "v=DKIM1; p=abc"}])

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url=mailcow_settings.base_url)
    provisioner = MailcowProvisioner(mailcow_settings, provisioning_settings, client=client)

    assert provisioner.get_dkim_key() == "v=DKIM1; p=abc"


def test_create_app_password_raises_when_missing(
    mailcow_settings: MailcowSettings, provisioning_settings: MailProvisioningSettings
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/add/app-passwd"):
            assert request.url.path == "/api/v1/add/app-passwd"
            return httpx.Response(200, json={})
        return httpx.Response(200, json={})

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url=mailcow_settings.base_url)
    provisioner = MailcowProvisioner(mailcow_settings, provisioning_settings, client=client)

    with pytest.raises(RuntimeError):
        provisioner.create_app_password("agent@example.com")
