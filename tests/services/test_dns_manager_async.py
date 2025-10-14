"""Tests for the asynchronous deSEC DNS manager."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Iterable

import httpx

from azt3knet.dns.dns_manager import DeSECDNSManager, RRSet


def _mock_transport(handler):
    return httpx.MockTransport(handler)


def test_upsert_rrset_issues_put_request() -> None:
    captured: dict[str, object] = {}

    async def scenario() -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            captured["method"] = request.method
            captured["url"] = str(request.url)
            captured["headers"] = dict(request.headers)
            captured["json"] = json.loads(request.content.decode())
            return httpx.Response(200, json={})

        transport = _mock_transport(handler)
        async with httpx.AsyncClient(
            transport=transport, base_url="https://desec.test/api"
        ) as client:
            manager = DeSECDNSManager(
                api_base="https://desec.test/api",
                token="secret-token",
                domain="example.org",
                client=client,
            )
            await manager.upsert_rrset("@", "TXT", ['"v=spf1 mx -all"'], ttl=600)

    asyncio.run(scenario())

    assert captured["method"] == "PUT"
    assert captured["url"].endswith("/domains/example.org/rrsets/TXT/@/")
    assert captured["json"] == {
        "subname": "@",
        "type": "TXT",
        "ttl": 600,
        "records": ['"v=spf1 mx -all"'],
    }
    assert captured["headers"]["authorization"] == "Token secret-token"


def test_bulk_upsert_sends_patch_request() -> None:
    rrsets: Iterable[RRSet] = [
        RRSet(name="@", rtype="MX", records=["10 mail.example.org."], ttl=900),
        RRSet(name="_dmarc", rtype="TXT", records=["dmarc"], ttl=900),
    ]

    async def scenario() -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            assert request.method == "PATCH"
            payload = json.loads(request.content.decode())
            assert payload[0]["subname"] == "@"
            assert payload[1]["type"] == "TXT"
            return httpx.Response(200, json={})

        transport = _mock_transport(handler)
        async with httpx.AsyncClient(transport=transport, base_url="https://desec.test") as client:
            manager = DeSECDNSManager(
                api_base="https://desec.test",
                token="secret-token",
                domain="example.org",
                client=client,
            )
            await manager.bulk_upsert(rrsets)

    asyncio.run(scenario())


def test_delete_rrset_ignores_missing_records() -> None:
    calls: list[str] = []

    async def scenario() -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            calls.append(str(request.url))
            return httpx.Response(404)

        transport = _mock_transport(handler)
        async with httpx.AsyncClient(transport=transport, base_url="https://desec.test") as client:
            manager = DeSECDNSManager(
                api_base="https://desec.test",
                token="secret-token",
                domain="example.org",
                client=client,
            )
            await manager.delete_rrset("verify", "TXT")

    asyncio.run(scenario())

    assert calls[0].endswith("/domains/example.org/rrsets/TXT/verify/")

