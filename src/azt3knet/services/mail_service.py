"""SMTP/IMAP helpers for agent mailboxes."""

from __future__ import annotations

from dataclasses import dataclass
from email import message_from_bytes, policy
from email.message import EmailMessage
import imaplib
import logging
import smtplib
from typing import Iterable, List, Sequence, cast

from azt3knet.services.mailcow_provisioner import MailboxCredentials

logger = logging.getLogger(__name__)


@dataclass
class AgentMailbox:
    """Runtime representation of an agent mailbox."""

    address: str
    password: str
    smtp_host: str
    smtp_port: int
    imap_host: str
    imap_port: int
    app_password: str | None = None

    @classmethod
    def from_credentials(cls, credentials: MailboxCredentials) -> "AgentMailbox":
        return cls(
            address=credentials.address,
            password=credentials.password,
            smtp_host=credentials.smtp_host,
            smtp_port=credentials.smtp_port,
            imap_host=credentials.imap_host,
            imap_port=credentials.imap_port,
            app_password=credentials.app_password,
        )

    def auth_secret(self) -> str:
        return self.app_password or self.password


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
            client.login(mailbox.address, mailbox.auth_secret())
            client.send_message(message)

    def fetch_unseen(self, mailbox: AgentMailbox, *, folder: str = "INBOX") -> list[EmailMessage]:
        """Fetch unseen messages from the mailbox."""

        logger.debug("Fetching unseen messages for %s", mailbox.address)
        with imaplib.IMAP4_SSL(mailbox.imap_host, mailbox.imap_port) as client:
            client.login(mailbox.address, mailbox.auth_secret())
            client.select(folder)
            status, data = client.search(None, "UNSEEN")
            if status != "OK":
                raise RuntimeError(f"IMAP search failed for {mailbox.address}: {status}")

            message_ids = data[0].split()
            messages: List[EmailMessage] = []
            for message_id in message_ids:
                fetch_status, message_data = client.fetch(message_id, "(RFC822)")
                if fetch_status != "OK" or not message_data:
                    continue
                raw = message_data[0][1]
                if raw:
                    messages.append(
                        cast(EmailMessage, message_from_bytes(raw, policy=policy.default))
                    )
            return messages

    def mark_seen(self, mailbox: AgentMailbox, uids: Iterable[bytes], *, folder: str = "INBOX") -> None:
        """Mark the provided message UIDs as seen."""

        with imaplib.IMAP4_SSL(mailbox.imap_host, mailbox.imap_port) as client:
            client.login(mailbox.address, mailbox.auth_secret())
            client.select(folder)
            for uid in uids:
                client.store(uid, "+FLAGS", "(\\Seen)")

