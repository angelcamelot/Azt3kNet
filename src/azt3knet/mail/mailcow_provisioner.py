"""Proveedor de buzones en Mailcow."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class MailboxRequest:
    """Payload mínimo necesario para crear un buzón en Mailcow."""

    local_part: str
    domain: str
    display_name: str
    password: str
    quota_mb: int = 1024


@dataclass
class MailboxResponse:
    """Respuesta simplificada del API de Mailcow."""

    identifier: str
    success: bool
    raw: dict[str, object]


class MailcowProvisioner(Protocol):
    """Contrato para proveedores de buzones."""

    async def create_mailbox(self, request: MailboxRequest) -> MailboxResponse:
        """Crea un buzón y retorna los datos relevantes."""


class HTTPMailcowProvisioner:
    """Implementación HTTP (pendiente)."""

    def __init__(self, *, api_base: str, api_key: str, default_domain: str) -> None:
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.default_domain = default_domain

    async def create_mailbox(self, request: MailboxRequest) -> MailboxResponse:  # pragma: no cover - stub
        """TODO: Implementar POST /api/v1/add/mailbox con retries."""

        raise NotImplementedError
