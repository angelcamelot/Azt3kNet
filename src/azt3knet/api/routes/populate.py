"""Endpoints de población para la API de Azt3kNet."""

from __future__ import annotations

from fastapi import APIRouter

from azt3knet.models.agent import PopulationSpec

router = APIRouter(prefix="/api", tags=["population"])


@router.post("/populate")
async def populate_endpoint(spec: PopulationSpec, create_mailboxes: bool = False) -> dict[str, str]:  # pragma: no cover - stub
    """Endpoint placeholder que retornará un resumen cuando se implemente."""

    return {"status": "pending", "create_mailboxes": str(create_mailboxes)}
