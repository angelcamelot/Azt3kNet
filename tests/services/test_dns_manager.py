from __future__ import annotations

import json

import httpx

from azt3knet.core.mail_config import CloudflareDNSSettings
from azt3knet.services.dns_manager import CloudflareDNSManager, DNSRecord


def _make_settings() -> CloudflareDNSSettings:
    return CloudflareDNSSettings(
        api_base="https://api.cloudflare.test/client/v4",
        api_token="token",
        zone_id="zone-123",
        zone_name="example.com",
        default_ttl=600,
    )


def test_bootstrap_mail_records_creates_cloudflare_requests() -> None:
    requests: list[tuple[str, str, object | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload: object | None = None
        if request.content:
            payload = json.loads(request.content.decode())
        requests.append((request.method, request.url.path, payload))
        if request.method == "GET":
            return httpx.Response(200, json={"success": True, "result": []})
        return httpx.Response(200, json={"success": True, "result": {"id": "rec"}})

    settings = _make_settings()
    client = httpx.Client(transport=httpx.MockTransport(handler), base_url=settings.api_base)
    manager = CloudflareDNSManager(settings, client=client)

    manager.bootstrap_mail_records(
        mx_records=("in.mailjet.com", "in-v3.mailjet.com"),
        dkim_key="v=DKIM1; p=abc",
        ttl=900,
        spf_policy="v=spf1 include:spf.mailjet.com -all",
        dmarc_policy="v=DMARC1; p=quarantine",
    )

    post_payloads = [payload for method, _, payload in requests if method == "POST"]
    assert any(payload["type"] == "MX" and payload["priority"] == 10 for payload in post_payloads)
    assert any(payload["type"] == "MX" and payload["priority"] == 20 for payload in post_payloads)
    assert any(
        payload["type"] == "TXT" and str(payload.get("name", "")).endswith("_dmarc.example.com")
        for payload in post_payloads
    )
    assert any(payload["type"] == "TXT" and payload["content"].startswith("v=spf1") for payload in post_payloads)
    assert any(payload["type"] == "TXT" and payload["name"].endswith("mail._domainkey.example.com") for payload in post_payloads)


def test_upsert_cname_updates_existing_record() -> None:
    requests: list[tuple[str, str, object | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload: object | None = None
        if request.content:
            payload = json.loads(request.content.decode())
        requests.append((request.method, request.url.path, payload))
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "result": [
                        {
                            "id": "rec-1",
                            "type": "CNAME",
                            "name": "api.example.com",
                            "content": "old.target",
                            "ttl": 300,
                            "proxied": False,
                        }
                    ],
                },
            )
        return httpx.Response(200, json={"success": True, "result": {"id": "rec-1"}})

    settings = _make_settings()
    client = httpx.Client(transport=httpx.MockTransport(handler), base_url=settings.api_base)
    manager = CloudflareDNSManager(settings, client=client)

    manager.upsert_cname(subname="api", target="new.target")

    methods = [method for method, _, _ in requests]
    assert "POST" in methods
    assert "DELETE" in methods


def test_replace_records_removes_outdated_records() -> None:
    delete_calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "result": [
                        {
                            "id": "rec-1",
                            "type": "MX",
                            "name": "example.com",
                            "content": "old.mailjet.com",
                            "ttl": 300,
                            "priority": 10,
                        }
                    ],
                },
            )
        if request.method == "DELETE":
            delete_calls.append(str(request.url))
            return httpx.Response(200, json={"success": True, "result": None})
        return httpx.Response(200, json={"success": True, "result": {"id": "rec-2"}})

    settings = _make_settings()
    client = httpx.Client(transport=httpx.MockTransport(handler), base_url=settings.api_base)
    manager = CloudflareDNSManager(settings, client=client)

    manager.replace_records(
        name="@",
        rtype="MX",
        records=[DNSRecord(content="in.mailjet.com", ttl=600, priority=10)],
    )

    assert delete_calls, "Expected outdated record to be deleted"
