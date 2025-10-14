"""Mailjet webhook endpoints for inbound email processing."""

from __future__ import annotations

import logging
import re
from email.message import EmailMessage
from typing import Iterable

from fastapi import APIRouter, HTTPException

from azt3knet.core.mail_config import get_mailjet_settings
from azt3knet.services.link_verifier import LinkVerifier
from azt3knet.services.mail_service import AgentMailbox, MailService
from azt3knet.storage.db import DatabaseConfigurationError, create_engine_from_url
from azt3knet.storage.inbound_email import (
    AttachmentMetadata,
    InboundEmail,
    InboundEmailPersistenceError,
    InboundEmailRepository,
    StoredInboundEmail,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["mail"])


def _extract_recipient(payload: dict[str, object]) -> str:
    """Best-effort extraction of the primary recipient from the webhook payload."""

    for key in ("Recipient", "recipient", "To", "Email", "email"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _body_content(message: EmailMessage) -> tuple[str, str]:
    """Return plain text and HTML bodies from the parsed email message."""

    text_body = ""
    html_body = ""

    if message.is_multipart():
        text_part = message.get_body(preferencelist=("plain",))
        html_part = message.get_body(preferencelist=("html",))
        if text_part is not None:
            try:
                text_body = text_part.get_content()
            except Exception:  # pragma: no cover - defensive against malformed payloads
                logger.exception("Failed to read text body from inbound email")
        if html_part is not None:
            try:
                html_body = html_part.get_content()
            except Exception:  # pragma: no cover - defensive against malformed payloads
                logger.exception("Failed to read HTML body from inbound email")
    else:
        try:
            content = message.get_content()
        except Exception:  # pragma: no cover - defensive
            logger.exception("Failed to read payload from non-multipart email")
        else:
            subtype = message.get_content_subtype()
            if subtype == "html":
                html_body = content
            else:
                text_body = content

    return text_body or "", html_body or ""


_LINK_PATTERN = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)


def _extract_links(*parts: Iterable[str]) -> list[str]:
    """Return a de-duplicated list of hyperlinks discovered in the provided text segments."""

    seen: set[str] = set()
    ordered_links: list[str] = []

    for part in parts:
        if not part:
            continue
        # ``part`` may be a sequence of strings or a single string. Normalise accordingly.
        if isinstance(part, str):
            texts = [part]
        else:
            texts = [segment for segment in part if isinstance(segment, str)]
        for text in texts:
            for match in _LINK_PATTERN.findall(text):
                cleaned = match.rstrip(").,;\'\"")
                if cleaned and cleaned not in seen:
                    seen.add(cleaned)
                    ordered_links.append(cleaned)

    return ordered_links


def _attachment_metadata(message: EmailMessage) -> list[AttachmentMetadata]:
    """Collect metadata for each attachment in the email message."""

    attachments: list[AttachmentMetadata] = []
    for part in message.iter_attachments():
        filename = part.get_filename()
        content_type = part.get_content_type()
        size: int | None = None
        try:
            payload = part.get_payload(decode=True)
        except Exception:  # pragma: no cover - defensive
            logger.exception("Failed to decode attachment payload")
            payload = None
        if isinstance(payload, (bytes, bytearray)):
            size = len(payload)
        attachments.append(
            AttachmentMetadata(
                filename=filename or None,
                content_type=content_type or None,
                size=size,
            )
        )
    return attachments


def _sanitise_payload(value: object) -> object:
    """Convert the webhook payload into JSON-serialisable primitives."""

    if isinstance(value, dict):
        return {str(key): _sanitise_payload(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitise_payload(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _persist_inbound_email(email: InboundEmail) -> StoredInboundEmail | None:
    """Persist the inbound email using the configured repository if available."""

    try:
        bundle = create_engine_from_url()
    except DatabaseConfigurationError:
        logger.debug("DATABASE_URL not configured; skipping inbound email persistence")
        return None

    repository = InboundEmailRepository.from_engine(bundle)
    try:
        return repository.persist_email(email)
    except InboundEmailPersistenceError:
        logger.exception("Failed to persist inbound email destined for %s", email.recipient)
        return None


@router.post("/webhooks/mailjet/inbound")
def mailjet_inbound_webhook(payload: dict[str, object]) -> dict[str, object]:
    """Validate and parse a Mailjet inbound webhook payload.

    The endpoint is intentionally lightweight so it can operate within the local
    environment exposed through Cloudflare Tunnel. Messages are parsed into a
    structured representation that down-stream services can use for verification
    flows or simulations.
    """

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="payload must be an object")

    settings = get_mailjet_settings()
    provided_token = None
    for key in ("token", "Token", "x-mailjet-token", "X-Mailjet-Token"):
        token_value = payload.get(key)
        if isinstance(token_value, str) and token_value.strip():
            provided_token = token_value.strip()
            break

    mailbox = AgentMailbox(
        address=_extract_recipient(payload),
        smtp_host=settings.smtp_host,
        smtp_port=settings.smtp_port,
        smtp_username=settings.smtp_username,
        smtp_password=settings.smtp_password,
        inbound_url=settings.inbound_webhook_url or None,
        inbound_secret=settings.inbound_webhook_secret or None,
    )

    mail_service = MailService()
    if mailbox.inbound_secret:
        if not mail_service.validate_inbound_token(mailbox, provided_token):
            logger.warning("Rejected Mailjet inbound webhook due to invalid token")
            raise HTTPException(
                status_code=401,
                detail="invalid or missing webhook token",
            )

    email_message = mail_service.parse_inbound_event(payload)
    text_body, html_body = _body_content(email_message)
    links = _extract_links(text_body, html_body)
    attachments = _attachment_metadata(email_message)

    subject = email_message.get("Subject", "") or payload.get("Subject") or ""
    sender = email_message.get("From", "") or payload.get("Sender") or ""
    recipient = email_message.get("To", "") or mailbox.address
    message_id = email_message.get("Message-ID", "") or payload.get("MessageID")

    with LinkVerifier() as verifier:
        link_checks = verifier.verify(links)

    inbound_email = InboundEmail(
        recipient=str(recipient) if recipient is not None else mailbox.address,
        sender=str(sender) if sender is not None else "",
        subject=str(subject) if subject is not None else "",
        text_body=text_body,
        html_body=html_body,
        message_id=str(message_id) if message_id else None,
        links=links,
        link_checks=link_checks,
        attachments=attachments,
        raw_payload=_sanitise_payload(payload),
    )

    stored_email = _persist_inbound_email(inbound_email)

    response: dict[str, object] = {
        "status": "accepted",
        "subject": str(subject) if subject is not None else "",
        "from": str(sender) if sender is not None else "",
        "to": str(recipient) if recipient is not None else "",
        "text_body": text_body,
        "html_body": html_body,
        "links": links,
        "attachment_count": len(attachments),
        "attachments": [item.as_payload() for item in attachments],
        "link_checks": [check.as_payload() for check in link_checks],
    }

    if message_id:
        response["message_id"] = str(message_id)

    if stored_email is not None:
        response["email_id"] = str(stored_email.id)

    return response


__all__ = ["mailjet_inbound_webhook", "router"]

