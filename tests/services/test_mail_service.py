from __future__ import annotations

from email.message import EmailMessage
from typing import List

import pytest

from azt3knet.services.mail_service import AgentMailbox, MailService


class DummySMTP:
    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self.started_tls = False
        self.logged_in: tuple[str, str] | None = None
        self.messages: List[EmailMessage] = []

    def __enter__(self) -> "DummySMTP":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def starttls(self) -> None:
        self.started_tls = True

    def login(self, username: str, password: str) -> None:
        self.logged_in = (username, password)

    def send_message(self, message: EmailMessage) -> None:
        self.messages.append(message)


class DummyIMAP:
    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self.logged_in: tuple[str, str] | None = None
        self.selected_mailbox: str | None = None
        self.store_calls: list[tuple[bytes, str, str]] = []
        self.messages: list[tuple[bytes, bytes]] = []

    def __enter__(self) -> "DummyIMAP":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    # API used by MailService
    def login(self, username: str, password: str) -> tuple[str, list[bytes]]:
        self.logged_in = (username, password)
        return "OK", []

    def select(self, mailbox: str) -> tuple[str, list[bytes]]:
        self.selected_mailbox = mailbox
        return "OK", []

    def search(self, _charset, criteria: str) -> tuple[str, list[bytes]]:
        ids = b" ".join(msg_id for msg_id, _ in self.messages)
        return "OK", [ids]

    def fetch(self, message_id: bytes, _parts: str) -> tuple[str, list[tuple[bytes, bytes]]]:
        for mid, data in self.messages:
            if mid == message_id:
                return "OK", [(b"RFC822", data)]
        return "NO", []

    def store(self, uid: bytes, flags: str, value: str) -> tuple[str, list[bytes]]:
        self.store_calls.append((uid, flags, value))
        return "OK", []


@pytest.fixture()
def mailbox() -> AgentMailbox:
    return AgentMailbox(
        address="agent@example.com",
        password="secret",
        smtp_host="smtp.example.com",
        smtp_port=587,
        imap_host="imap.example.com",
        imap_port=993,
        app_password="app-pass",
    )


def test_send_mail_uses_smtp(monkeypatch, mailbox: AgentMailbox) -> None:
    dummy_smtp = DummySMTP(mailbox.smtp_host, mailbox.smtp_port)
    monkeypatch.setattr("azt3knet.services.mail_service.smtplib.SMTP", lambda host, port: dummy_smtp)

    service = MailService()
    service.send_mail(mailbox, recipients=["dest@example.com"], subject="Hello", body="World")

    assert dummy_smtp.started_tls
    assert dummy_smtp.logged_in == (mailbox.address, mailbox.app_password)
    assert dummy_smtp.messages[0]["Subject"] == "Hello"


def test_fetch_unseen_reads_messages(monkeypatch, mailbox: AgentMailbox) -> None:
    dummy_imap = DummyIMAP(mailbox.imap_host, mailbox.imap_port)
    message = EmailMessage()
    message["From"] = "sender@example.com"
    message["To"] = mailbox.address
    message.set_content("hello")
    dummy_imap.messages.append((b"1", message.as_bytes()))
    monkeypatch.setattr("azt3knet.services.mail_service.imaplib.IMAP4_SSL", lambda host, port: dummy_imap)

    service = MailService()
    messages = service.fetch_unseen(mailbox)

    assert len(messages) == 1
    assert dummy_imap.logged_in == (mailbox.address, mailbox.app_password)
    assert dummy_imap.selected_mailbox == "INBOX"


def test_mark_seen_updates_flags(monkeypatch, mailbox: AgentMailbox) -> None:
    dummy_imap = DummyIMAP(mailbox.imap_host, mailbox.imap_port)
    monkeypatch.setattr("azt3knet.services.mail_service.imaplib.IMAP4_SSL", lambda host, port: dummy_imap)

    service = MailService()
    service.mark_seen(mailbox, [b"1", b"2"])

    assert dummy_imap.store_calls == [(b"1", "+FLAGS", "(\\Seen)"), (b"2", "+FLAGS", "(\\Seen)")]
