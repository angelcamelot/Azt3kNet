from __future__ import annotations

import json

import httpx

from azt3knet.core.mail_config import DeSECSettings
from azt3knet.services.dns_manager import DeSECDNSManager


def test_bootstrap_mail_records_uses_bulk_upsert(monkeypatch) -> None:
    settings = DeSECSettings(
        api_base="https://desec.example/api/v1",
        domain="example.com",
        token="token",
        dyndns_update_url="https://update.example",
        update_interval_hours=24,
        default_ttl=300,
    )

    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["path"] = request.url.path
        captured["json"] = json.loads(request.content.decode())
        return httpx.Response(200, json={})

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url=settings.api_base.rstrip("/"))
    dns = DeSECDNSManager(settings, client=client, dyn_client=httpx.Client(transport=httpx.MockTransport(handler)))

    dns.bootstrap_mail_records(mail_host="mail.example.com", public_ip="1.2.3.4", dkim_key="v=DKIM1", ttl=300)

    assert captured["method"] == "PATCH"
    assert captured["path"] == "/api/v1/domains/example.com/rrsets/"
    payload = captured["json"]
    assert isinstance(payload, list)
    assert len(payload) == 5
    rr_types = {item["type"] for item in payload}
    assert rr_types == {"MX", "A", "TXT"}


def test_update_dyndns_returns_response_text(monkeypatch) -> None:
    settings = DeSECSettings(
        api_base="https://desec.example/api/v1",
        domain="example.com",
        token="token",
        dyndns_update_url="https://update.example",
        update_interval_hours=24,
        default_ttl=300,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if "update" in request.url.host:
            return httpx.Response(200, text="good 1.2.3.4")
        return httpx.Response(200, json=[])

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url=settings.api_base.rstrip("/"))
    dyn_client = httpx.Client(transport=httpx.MockTransport(handler))

    dns = DeSECDNSManager(settings, client=client, dyn_client=dyn_client)
    assert dns.update_dyndns(hostname="example.com", ip_address="1.2.3.4") == "good 1.2.3.4"


def test_lookup_public_ip_parses_json() -> None:
    settings = DeSECSettings(
        api_base="https://desec.example/api/v1",
        domain="example.com",
        token="token",
        dyndns_update_url="https://update.example",
        update_interval_hours=24,
        default_ttl=300,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ip": "203.0.113.10"})

    dns = DeSECDNSManager(
        settings,
        client=httpx.Client(transport=httpx.MockTransport(handler), base_url=settings.api_base.rstrip("/")),
        dyn_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert dns.lookup_public_ip() == "203.0.113.10"
