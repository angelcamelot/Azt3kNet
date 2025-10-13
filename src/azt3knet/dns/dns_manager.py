"""Cliente de deSEC para operaciones DNS.

La implementación final gestionará:
- Creación/actualización de RRsets (TXT, MX, A, SPF, DMARC, DKIM).
- Gestión de errores/reintentos con backoff.
- Coordinación con configuración de Mailcow (DKIM).

Este stub define las interfaces esperadas para ser utilizadas por los módulos de
bootstrap y provisión de buzones.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol


@dataclass
class RRSet:
    """Representación mínima de un RRset de deSEC."""

    name: str
    rtype: str
    records: list[str]
    ttl: int = 3600


class DNSManager(Protocol):
    """Contrato para gestores DNS."""

    async def upsert_rrset(self, name: str, rtype: str, records: Iterable[str], *, ttl: int = 3600) -> None:
        """Crea o actualiza un RRset en deSEC."""

    async def delete_rrset(self, name: str, rtype: str) -> None:
        """Elimina un RRset si existe."""


class DeSECDNSManager:
    """Implementación concreta (pendiente)."""

    def __init__(self, *, api_base: str, token: str, domain: str) -> None:
        self.api_base = api_base.rstrip("/")
        self.token = token
        self.domain = domain

    async def upsert_rrset(self, name: str, rtype: str, records: Iterable[str], *, ttl: int = 3600) -> None:  # pragma: no cover - stub
        """TODO: Implementar llamado HTTP PATCH a deSEC."""

        raise NotImplementedError

    async def delete_rrset(self, name: str, rtype: str) -> None:  # pragma: no cover - stub
        """TODO: Implementar borrado de RRset."""

        raise NotImplementedError
