from __future__ import annotations

import json
from collections import Counter
import importlib.util
import pathlib

import httpx

from azt3knet.services import DeSECDNSManager, MailjetProvisioner, ResilientHTTPClient

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


def _make_dns_factory(api_handler, dyn_handler):
    def factory(settings):
        client = httpx.Client(
            base_url=settings.api_base.rstrip("/"),
            headers={"Authorization": f"Token {settings.token}"},
            transport=httpx.MockTransport(api_handler),
        )
        dyn_client = httpx.Client(transport=httpx.MockTransport(dyn_handler))
        return DeSECDNSManager(settings, client=client, dyn_client=dyn_client)

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
    monkeypatch.setenv("DESEC_API", "https://desec.example/api/v1")
    monkeypatch.setenv("DESEC_DOMAIN", "example.com")
    monkeypatch.setenv("DESEC_TOKEN", "token")
    monkeypatch.setenv("DESEC_DYNDNS_UPDATE_URL", "https://update.example")


def test_bootstrap_dns_happy_path(monkeypatch):
    mail_requests = []
    dns_requests = []
    dyn_requests = []

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
        dns_requests.append(
            (
                request.method,
                request.url.path,
                json.loads(request.content.decode()),
            )
        )
        return httpx.Response(200, json={})

    def dyn_handler(request: httpx.Request) -> httpx.Response:
        dyn_requests.append((request.url.host, request.url.path, dict(request.url.params)))
        if request.url.host == "api.ipify.org":
            return httpx.Response(200, json={"ip": "198.51.100.42"})
        if request.url.host == "update.example":
            return httpx.Response(200, text="good 198.51.100.42")
        raise AssertionError(f"Unexpected DynDNS request: {request.url}")

    dns_bootstrap.bootstrap_dns(
        mail_provisioner_factory=_make_mail_factory(mail_handler),
        dns_manager_factory=_make_dns_factory(dns_handler, dyn_handler),
    )

    assert any(method == "GET" and path == "/v3/REST/domain/example.com" for method, path in mail_requests)
    assert any(method == "POST" and path == "/v3/REST/inbound" for method, path in mail_requests)

    assert len(dns_requests) == 1
    method, path, body = dns_requests[0]
    assert method == "PATCH"
    assert path == "/api/v1/domains/example.com/rrsets/"
    assert isinstance(body, list)
    rr_counter = Counter(item["type"] for item in body)
    assert rr_counter["MX"] == 1
    assert rr_counter["TXT"] == 3
    mx_record = next(item for item in body if item["type"] == "MX")
    assert mx_record["records"] == ["10 in.mailjet.com.", "20 in-v3.mailjet.com."]

    assert dyn_requests[0][0] == "api.ipify.org"
    assert dyn_requests[1][0] == "update.example"


def test_main_returns_status_error_code(monkeypatch):
    _set_common_env(monkeypatch)

    def mail_handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/v3/REST/domain/example.com":
            return httpx.Response(200, json={"DKIMPublicKey": "v=DKIM1"})
        if request.method == "POST" and request.url.path == "/v3/REST/inbound":
            return httpx.Response(200, json={})
        raise AssertionError(f"Unexpected Mailjet request: {request.method} {request.url}")

    def dns_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"detail": "oops"})

    def dyn_handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.ipify.org":
            return httpx.Response(200, json={"ip": "198.51.100.42"})
        raise AssertionError("DynDNS update should not be attempted on failure")

    monkeypatch.setattr(dns_bootstrap, "MailjetProvisioner", _make_mail_factory(mail_handler))
    monkeypatch.setattr(dns_bootstrap, "DeSECDNSManager", _make_dns_factory(dns_handler, dyn_handler))

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

    def dyn_handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.ipify.org":
            return httpx.Response(200, json={"ip": "198.51.100.42"})
        raise AssertionError("DynDNS update should not be attempted on failure")

    monkeypatch.setattr(dns_bootstrap, "MailjetProvisioner", _make_mail_factory(mail_handler))
    monkeypatch.setattr(dns_bootstrap, "DeSECDNSManager", _make_dns_factory(dns_handler, dyn_handler))

    assert dns_bootstrap.main() == 3
