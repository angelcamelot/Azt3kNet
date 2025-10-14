"""Unit tests covering the Mailjet inbound webhook endpoint."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from azt3knet.api.main import app
from azt3knet.core.mail_config import get_mailjet_settings


client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_mailjet_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure Mailjet settings are reloaded from the environment per test."""

    get_mailjet_settings.cache_clear()  # type: ignore[attr-defined]
    monkeypatch.delenv("MAILJET_INBOUND_SECRET", raising=False)
    monkeypatch.delenv("MAILJET_API_KEY", raising=False)
    monkeypatch.delenv("MAILJET_API_SECRET", raising=False)


def _sample_payload() -> dict[str, object]:
    return {
        "Headers": {
            "Subject": "Action required",
            "From": "Support <support@example.com>",
            "To": "agent@azt3knet.test",
        },
        "Text-part": "Visit https://example.com/verify to continue.",
        "Html-part": "<p>Verify your account <a href='https://example.com/verify'>here</a> or read our <a href='http://example.com/policy'>policy</a>.</p>",
        "MessageID": 12345,
    }


def test_mailjet_inbound_accepts_valid_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAILJET_INBOUND_SECRET", "shared-token")
    payload = _sample_payload()
    payload["token"] = "shared-token"

    response = client.post(
        "/api/webhooks/mailjet/inbound",
        json=payload,
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "accepted"
    assert data["subject"] == "Action required"
    assert data["from"].startswith("Support")
    assert data["to"] == "agent@azt3knet.test"
    assert "https://example.com/verify" in data["links"]
    assert "http://example.com/policy" in data["links"]
    assert data["attachment_count"] == 0
    assert data["message_id"] == "12345"


def test_mailjet_inbound_rejects_invalid_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAILJET_INBOUND_SECRET", "expected")

    payload = _sample_payload()
    payload["token"] = "wrong"

    response = client.post("/api/webhooks/mailjet/inbound", json=payload)

    assert response.status_code == 401
    assert response.json()["detail"] == "invalid or missing webhook token"


def test_mailjet_inbound_allows_when_secret_disabled() -> None:
    payload = _sample_payload()
    # The fixture cleared the secret, therefore authentication should be bypassed.
    response = client.post("/api/webhooks/mailjet/inbound", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["links"] == ["https://example.com/verify", "http://example.com/policy"]

