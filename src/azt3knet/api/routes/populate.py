"""Endpoints de población para la API de Azt3kNet."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from azt3knet.agent_factory.generator import generate_agents
from azt3knet.agent_factory.models import PopulationSpec

router = APIRouter(tags=["population"])


@router.post("/populate")
async def populate_endpoint(
    payload: dict[str, Any],
    create_mailboxes: bool = False,
) -> dict[str, str]:  # pragma: no cover - stub
    """Endpoint placeholder que normaliza el payload con ``PopulationSpec``."""

    try:
        spec = PopulationSpec.from_dict(payload)
    except ValueError as exc:  # pragma: no cover - exercised via tests
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    agents = generate_agents(spec)
    if spec.preview:
        agents = agents[: spec.preview]

    return {
        "seed": spec.seed,
        "count": len(agents),
        "agents": [agent.model_dump(mode="json") for agent in agents],
        "create_mailboxes": create_mailboxes,
    }
