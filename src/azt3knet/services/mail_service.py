"""SMTP/IMAP helpers for agent mailboxes."""

from __future__ import annotations

from dataclasses import dataclass
from email import message_from_string, policy
from email.message import EmailMessage
import logging
import smtplib
from typing import Mapping, Sequence, cast

from azt3knet.services.mailjet_provisioner import MailboxCredentials

logger = logging.getLogger(__name__)


@dataclass
class AgentMailbox:
    """Runtime representation of a Mailjet-backed agent mailbox."""

    address: str
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    inbound_url: str | None = None
    inbound_secret: str | None = None

    @classmethod
    def from_credentials(cls, credentials: MailboxCredentials) -> "AgentMailbox":
        return cls(
            address=credentials.address,
            smtp_host=credentials.smtp_host,
            smtp_port=credentials.smtp_port,
            smtp_username=credentials.smtp_username,
            smtp_password=credentials.smtp_password,
            inbound_url=credentials.inbound_url,
            inbound_secret=credentials.inbound_secret,
        )


class MailService:
    """Simple synchronous SMTP/IMAP wrapper."""

    def send_mail(
        self,
        mailbox: AgentMailbox,
        *,
        recipients: Sequence[str],
        subject: str,
        body: str,
        subtype: str = "plain",
        headers: dict[str, str] | None = None,
    ) -> None:
        """Send an email using the agent mailbox."""

        message = EmailMessage()
        message["From"] = mailbox.address
        message["To"] = ", ".join(recipients)
        message["Subject"] = subject
        if headers:
            for key, value in headers.items():
                message[key] = value
        message.set_content(body, subtype=subtype)

        logger.debug("Sending email from %s to %s", mailbox.address, recipients)
        with smtplib.SMTP(mailbox.smtp_host, mailbox.smtp_port) as client:
            client.starttls()
            client.login(mailbox.smtp_username, mailbox.smtp_password)
            client.send_message(message)

    def validate_inbound_token(self, mailbox: AgentMailbox, token: str | None) -> bool:
        """Return True when the provided webhook token matches the mailbox secret."""

        if not mailbox.inbound_secret:
            return True
        return token == mailbox.inbound_secret

    def parse_inbound_event(self, payload: Mapping[str, object]) -> EmailMessage:
        """Convert a Mailjet inbound webhook payload into an ``EmailMessage``."""

        raw_message = payload.get("RawMessage")
        if isinstance(raw_message, str) and raw_message.strip():
            return cast(EmailMessage, message_from_string(raw_message, policy=policy.default))

        headers = payload.get("Headers")
        text_part = payload.get("Text-part")
        html_part = payload.get("Html-part")

        message = EmailMessage(policy=policy.default)
        if isinstance(headers, Mapping):
            for key, value in headers.items():
                if isinstance(key, str) and isinstance(value, str):
                    message[key] = value
        if isinstance(text_part, str) and text_part.strip():
            message.set_content(text_part)
        elif isinstance(html_part, str) and html_part.strip():
            message.set_content(html_part, subtype="html")
        else:
            message.set_content("")
        return message

