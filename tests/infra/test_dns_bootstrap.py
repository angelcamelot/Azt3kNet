from __future__ import annotations

import importlib.util
import json
import pathlib
from collections import Counter

import httpx

from azt3knet.services import CloudflareDNSManager, MailjetProvisioner, ResilientHTTPClient

_MODULE_PATH = pathlib.Path(__file__).resolve().parents[1].parent / "infra" / "dns_bootstrap.py"
_SPEC = importlib.util.spec_from_file_location("infra_dns_bootstrap", _MODULE_PATH)
dns_bootstrap = importlib.util.module_from_spec(_SPEC)
assert _SPEC and _SPEC.loader
_SPEC.loader.exec_module(dns_bootstrap)  # type: ignore[call-arg]


def _make_mail_factory(handler):
    def factory(mail_settings, provisioning_settings):
        client = httpx.Client(
            base_url=mail_settings.base_url,
            auth=(mail_settings.api_key, mail_settings.api_secret),
            transport=httpx.MockTransport(handler),
        )
        resilient = ResilientHTTPClient(client, service_name="mailjet")
        return MailjetProvisioner(mail_settings, provisioning_settings, client=resilient)

    return factory


def _make_dns_factory(handler):
    def factory(settings):
        client = httpx.Client(
            base_url=settings.api_base.rstrip("/"),
            transport=httpx.MockTransport(handler),
        )
        return CloudflareDNSManager(settings, client=client)

    return factory


def _set_common_env(monkeypatch):
    monkeypatch.setenv("MAILJET_API", "https://api.mailjet.test")
    monkeypatch.setenv("MAILJET_API_KEY", "public")
    monkeypatch.setenv("MAILJET_API_SECRET", "secret")
    monkeypatch.setenv("MAILJET_SMTP_HOST", "in-v3.mailjet.com")
    monkeypatch.setenv("MAILJET_SMTP_PORT", "587")
    monkeypatch.setenv("MAILJET_MX_HOSTS", "in.mailjet.com,in-v3.mailjet.com")
    monkeypatch.setenv("MAILJET_SPF_INCLUDE", "include:spf.mailjet.com")
    monkeypatch.setenv("AZT3KNET_DOMAIN", "example.com")
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "token")
    monkeypatch.setenv("CLOUDFLARE_ZONE_ID", "zone123")
    monkeypatch.setenv("CLOUDFLARE_ZONE_NAME", "example.com")
    monkeypatch.setenv("CLOUDFLARE_API", "https://api.cloudflare.test/client/v4")
    monkeypatch.delenv("CLOUDFLARE_TUNNEL_CNAME", raising=False)
    monkeypatch.delenv("CLOUDFLARE_TUNNEL_SUBDOMAIN", raising=False)
    monkeypatch.delenv("CLOUDFLARE_TUNNEL_HOSTNAME", raising=False)
    monkeypatch.delenv("CLOUDFLARE_TUNNEL_CNAME_TTL", raising=False)


def test_bootstrap_dns_happy_path(monkeypatch):
    mail_requests: list[tuple[str, str]] = []
    dns_requests: list[tuple[str, str, object | None]] = []

    _set_common_env(monkeypatch)

    def mail_handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        mail_requests.append((request.method, path))
        if request.method == "GET" and path == "/v3/REST/domain/example.com":
            return httpx.Response(200, json={"DKIMPublicKey": "v=DKIM1"})
        if request.method == "POST" and path == "/v3/REST/inbound":
            return httpx.Response(200, json={"status": "ok"})
        raise AssertionError(f"Unexpected Mailjet request: {request.method} {request.url}")

    def dns_handler(request: httpx.Request) -> httpx.Response:
        payload: object | None = None
        if request.content:
            payload = json.loads(request.content.decode())
        dns_requests.append((request.method, request.url.path, payload))
        if request.method == "GET":
            return httpx.Response(200, json={"success": True, "result": []})
        return httpx.Response(200, json={"success": True, "result": {"id": "rec"}})

    dns_bootstrap.bootstrap_dns(
        mail_provisioner_factory=_make_mail_factory(mail_handler),
        dns_manager_factory=_make_dns_factory(dns_handler),
    )

    assert any(method == "GET" and path == "/v3/REST/domain/example.com" for method, path in mail_requests)

    post_payloads = [payload for method, _, payload in dns_requests if method == "POST"]
    assert post_payloads, "Expected Cloudflare POST calls"
    rr_counter = Counter(payload["type"] for payload in post_payloads if isinstance(payload, dict))
    assert rr_counter["MX"] == 2
    assert rr_counter["TXT"] == 3


def test_bootstrap_dns_with_cloudflare_cname(monkeypatch):
    dns_requests: list[tuple[str, str, object | None]] = []

    _set_common_env(monkeypatch)
    monkeypatch.setenv("CLOUDFLARE_TUNNEL_CNAME", "abcd1234.cfargotunnel.com")
    monkeypatch.setenv("CLOUDFLARE_TUNNEL_SUBDOMAIN", "api")
    monkeypatch.setenv("CLOUDFLARE_TUNNEL_CNAME_TTL", "600")

    def mail_handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/v3/REST/domain/example.com":
            return httpx.Response(200, json={"DKIMPublicKey": "v=DKIM1"})
        if request.method == "POST" and request.url.path == "/v3/REST/inbound":
            return httpx.Response(200, json={"status": "ok"})
        raise AssertionError(f"Unexpected Mailjet request: {request.method} {request.url}")

    def dns_handler(request: httpx.Request) -> httpx.Response:
        payload: object | None = None
        if request.content:
            payload = json.loads(request.content.decode())
        dns_requests.append((request.method, request.url.path, payload))
        if request.method == "GET":
            return httpx.Response(200, json={"success": True, "result": []})
        return httpx.Response(200, json={"success": True, "result": {"id": "rec"}})

    dns_bootstrap.bootstrap_dns(
        mail_provisioner_factory=_make_mail_factory(mail_handler),
        dns_manager_factory=_make_dns_factory(dns_handler),
    )

    assert any(method == "POST" and path.endswith("/dns_records") for method, path, _ in dns_requests)
    assert any(
        method == "POST"
        and isinstance(payload, dict)
        and payload.get("type") == "CNAME"
        and payload.get("name") == "api.example.com"
        for method, _, payload in dns_requests
    )


def test_main_returns_status_error_code(monkeypatch):
    _set_common_env(monkeypatch)

    def mail_handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/v3/REST/domain/example.com":
            return httpx.Response(200, json={"DKIMPublicKey": "v=DKIM1"})
        if request.method == "POST" and request.url.path == "/v3/REST/inbound":
            return httpx.Response(200, json={})
        raise AssertionError(f"Unexpected Mailjet request: {request.method} {request.url}")

    def dns_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"success": False, "errors": ["oops"]})

    monkeypatch.setattr(dns_bootstrap, "MailjetProvisioner", _make_mail_factory(mail_handler))
    monkeypatch.setattr(dns_bootstrap, "CloudflareDNSManager", _make_dns_factory(dns_handler))

    assert dns_bootstrap.main() == 2


def test_main_returns_transport_error_code(monkeypatch):
    _set_common_env(monkeypatch)

    def mail_handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/v3/REST/domain/example.com":
            return httpx.Response(200, json={"DKIMPublicKey": "v=DKIM1"})
        if request.method == "POST" and request.url.path == "/v3/REST/inbound":
            return httpx.Response(200, json={})
        raise AssertionError(f"Unexpected Mailjet request: {request.method} {request.url}")

    def dns_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    monkeypatch.setattr(dns_bootstrap, "MailjetProvisioner", _make_mail_factory(mail_handler))
    monkeypatch.setattr(dns_bootstrap, "CloudflareDNSManager", _make_dns_factory(dns_handler))

    assert dns_bootstrap.main() == 3
