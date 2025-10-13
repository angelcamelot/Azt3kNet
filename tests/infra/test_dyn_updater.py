from __future__ import annotations

import base64
import importlib.util
import pathlib

import httpx
import pytest

from azt3knet.services.dns_manager import DeSECDNSManager

_MODULE_PATH = pathlib.Path(__file__).resolve().parents[1].parent / "infra" / "dyn_updater.py"
_SPEC = importlib.util.spec_from_file_location("infra_dyn_updater", _MODULE_PATH)
dyn_updater = importlib.util.module_from_spec(_SPEC)
assert _SPEC and _SPEC.loader
_SPEC.loader.exec_module(dyn_updater)  # type: ignore[call-arg]


def _set_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DESEC_API", "https://desec.example/api/v1")
    monkeypatch.setenv("DESEC_DOMAIN", "example.com")
    monkeypatch.setenv("DESEC_TOKEN", "token")
    monkeypatch.setenv("DESEC_DYNDNS_UPDATE_URL", "https://update.example")
    monkeypatch.setenv("AZT3KNET_LOG_LEVEL", "INFO")


def _make_dns_factory(handler):
    def factory(settings):
        api_client = httpx.Client(
            base_url=settings.api_base.rstrip("/"),
            headers={"Authorization": f"Token {settings.token}"},
            transport=httpx.MockTransport(lambda request: httpx.Response(200, json={})),
        )
        dyn_client = httpx.Client(transport=httpx.MockTransport(handler))
        return DeSECDNSManager(settings, client=api_client, dyn_client=dyn_client)

    return factory


def test_main_updates_dyndns_with_detected_ip(monkeypatch: pytest.MonkeyPatch, caplog) -> None:
    _set_env(monkeypatch)

    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.ipify.org":
            captured["lookup"] = dict(request.url.params)
            return httpx.Response(200, json={"ip": "198.51.100.42"})
        if request.url.host == "update.example":
            captured["update_request"] = request
            return httpx.Response(200, text="good 198.51.100.42")
        raise AssertionError(f"Unexpected request {request.url}")

    monkeypatch.setattr(dyn_updater, "DeSECDNSManager", _make_dns_factory(handler))
    caplog.set_level("INFO")

    exit_code = dyn_updater.main([])

    assert exit_code == 0
    assert captured["lookup"] == {"format": "json"}

    request = captured["update_request"]
    assert isinstance(request, httpx.Request)
    assert request.url.host == "update.example"
    params = dict(request.url.params)
    assert params["hostname"] == "example.com"
    assert params["myip"] == "198.51.100.42"

    auth_header = request.headers.get("Authorization", "")
    assert auth_header.startswith("Basic ")
    decoded = base64.b64decode(auth_header.split(" ", 1)[1]).decode()
    assert decoded == "example.com:token"

    assert any("DynDNS update succeeded" in record.message for record in caplog.records)


def test_main_uses_provided_ip_without_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_env(monkeypatch)

    calls: list[str] = []
    captured_ip: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.ipify.org":
            calls.append("lookup")
            return httpx.Response(200, json={"ip": "198.51.100.99"})
        if request.url.host == "update.example":
            calls.append("update")
            captured_ip["ip"] = dict(request.url.params)["myip"]
            return httpx.Response(200, text="good 203.0.113.5")
        raise AssertionError(f"Unexpected request {request.url}")

    monkeypatch.setattr(dyn_updater, "DeSECDNSManager", _make_dns_factory(handler))

    exit_code = dyn_updater.main(["--ip", "203.0.113.5"])

    assert exit_code == 0
    assert calls == ["update"]
    assert captured_ip["ip"] == "203.0.113.5"


def test_main_logs_error_on_failed_update(monkeypatch: pytest.MonkeyPatch, caplog) -> None:
    _set_env(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.ipify.org":
            return httpx.Response(200, json={"ip": "198.51.100.55"})
        if request.url.host == "update.example":
            return httpx.Response(500, text="badauth")
        raise AssertionError(f"Unexpected request {request.url}")

    monkeypatch.setattr(dyn_updater, "DeSECDNSManager", _make_dns_factory(handler))
    caplog.set_level("ERROR")

    exit_code = dyn_updater.main([])

    assert exit_code == 2
    assert any("HTTP status error while updating DynDNS" in record.message for record in caplog.records)
