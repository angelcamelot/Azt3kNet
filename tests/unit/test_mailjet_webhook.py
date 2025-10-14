"""Unit tests covering the Mailjet inbound webhook endpoint."""

from __future__ import annotations

import datetime
import uuid

import pytest
from fastapi.testclient import TestClient

from azt3knet.api.main import app
from azt3knet.core.mail_config import get_mailjet_settings
from azt3knet.storage.inbound_email import LinkCheckResult, StoredInboundEmail


client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_mailjet_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure Mailjet settings are reloaded from the environment per test."""

    get_mailjet_settings.cache_clear()  # type: ignore[attr-defined]
    monkeypatch.delenv("MAILJET_INBOUND_SECRET", raising=False)
    monkeypatch.delenv("MAILJET_API_KEY", raising=False)
    monkeypatch.delenv("MAILJET_API_SECRET", raising=False)


@pytest.fixture(autouse=True)
def _stub_link_verifier(monkeypatch: pytest.MonkeyPatch) -> None:
    """Avoid real HTTP requests during link verification."""

    class _Verifier:
        def __enter__(self) -> "_Verifier":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
            return None

        def verify(self, links: list[str]) -> list[LinkCheckResult]:
            return [
                LinkCheckResult(url=link, status_code=200, ok=True, final_url=link)
                for link in links
            ]

    monkeypatch.setattr("azt3knet.api.routes.mailjet_webhook.LinkVerifier", lambda: _Verifier())


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
    assert data["link_checks"] == [
        {
            "url": "https://example.com/verify",
            "status_code": 200,
            "ok": True,
            "final_url": "https://example.com/verify",
            "error": None,
        },
        {
            "url": "http://example.com/policy",
            "status_code": 200,
            "ok": True,
            "final_url": "http://example.com/policy",
            "error": None,
        },
    ]


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


def test_mailjet_inbound_persists_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure inbound payloads are forwarded to the persistence helper."""

    stored_id = uuid.uuid4()
    captured: dict[str, object] = {}

    def _fake_persist(email) -> StoredInboundEmail:  # type: ignore[no-untyped-def]
        captured["email"] = email
        return StoredInboundEmail(
            id=stored_id,
            recipient=email.recipient,
            sender=email.sender,
            subject=email.subject,
            text_body=email.text_body,
            html_body=email.html_body,
            message_id=email.message_id,
            links=list(email.links),
            link_checks=list(email.link_checks),
            attachments=list(email.attachments),
            raw_payload=dict(email.raw_payload),
            attachment_count=email.attachment_count,
            created_at=datetime.datetime.now(datetime.timezone.utc),
        )

    monkeypatch.setattr(
        "azt3knet.api.routes.mailjet_webhook._persist_inbound_email",
        _fake_persist,
    )

    payload = _sample_payload()
    response = client.post("/api/webhooks/mailjet/inbound", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["email_id"] == str(stored_id)
    stored = captured["email"]
    assert stored.links == ["https://example.com/verify", "http://example.com/policy"]
    assert stored.raw_payload["MessageID"] == 12345

