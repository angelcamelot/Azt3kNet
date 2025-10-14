from email.message import EmailMessage

import pytest

from azt3knet.services.mail_service import AgentMailbox, MailService


class DummySMTP:
    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self.started_tls = False
        self.logged_in: tuple[str, str] | None = None
        self.messages: list[EmailMessage] = []

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


@pytest.fixture()
def mailbox() -> AgentMailbox:
    return AgentMailbox(
        address="bot@example.com",
        smtp_host="smtp.mailjet.com",
        smtp_port=587,
        smtp_username="api-key",
        smtp_password="api-secret",
        inbound_url="https://example.com/inbound",
        inbound_secret="shared-token",
    )


def test_send_mail_uses_mailjet_credentials(monkeypatch, mailbox: AgentMailbox) -> None:
    dummy_smtp = DummySMTP(mailbox.smtp_host, mailbox.smtp_port)
    monkeypatch.setattr("azt3knet.services.mail_service.smtplib.SMTP", lambda host, port: dummy_smtp)

    service = MailService()
    service.send_mail(mailbox, recipients=["dest@example.com"], subject="Hello", body="World")

    assert dummy_smtp.started_tls
    assert dummy_smtp.logged_in == (mailbox.smtp_username, mailbox.smtp_password)
    assert dummy_smtp.messages[0]["From"] == mailbox.address


@pytest.mark.parametrize(
    "provided,expected",
    [
        ("shared-token", True),
        ("wrong", False),
        (None, False),
    ],
)
def test_validate_inbound_token(monkeypatch, mailbox: AgentMailbox, provided: str | None, expected: bool) -> None:
    service = MailService()
    assert service.validate_inbound_token(mailbox, provided) is expected


def test_parse_inbound_event_prefers_raw_message() -> None:
    raw = "From: sender@example.com\nTo: bot@example.com\nSubject: Hi\n\nHello"
    service = MailService()
    message = service.parse_inbound_event({"RawMessage": raw})

    assert isinstance(message, EmailMessage)
    assert message["Subject"] == "Hi"


def test_parse_inbound_event_builds_message_from_parts() -> None:
    payload = {
        "Headers": {"From": "sender@example.com", "To": "bot@example.com"},
        "Text-part": "Hola",
    }
    service = MailService()
    message = service.parse_inbound_event(payload)

    assert message["From"] == "sender@example.com"
    assert message.get_content().strip() == "Hola"
