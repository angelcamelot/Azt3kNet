"""Population endpoints for the Azt3kNet API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from azt3knet.agent_factory.models import PopulationSpec
from azt3knet.core.config import resolve_seed
from azt3knet.core.seeds import SeedSequence
from azt3knet.llm.adapter import LocalLLMAdapter
from azt3knet.population.builder import build_population

router = APIRouter(tags=["population"])


@router.post("/populate")
async def populate_endpoint(
    payload: dict[str, Any],
    create_mailboxes: bool = False,
) -> dict[str, object]:
    """Normalize the payload, generate agents, and optionally provision mailboxes."""

    try:
        spec = PopulationSpec.from_dict(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    resolved_seed = resolve_seed(spec.seed)
    numeric_seed = SeedSequence(resolved_seed).derive("api")
    adapter = LocalLLMAdapter()
    preview = build_population(
        spec,
        llm=adapter,
        deterministic_seed=numeric_seed,
        create_mailboxes=create_mailboxes,
    )

    response: dict[str, object] = {
        "seed": resolved_seed,
        "count": len(preview.agents),
        "agents": [agent.model_dump(mode="json") for agent in preview.agents],
    }
    if preview.mailboxes:
        response["mailboxes"] = [mailbox.as_public_dict() for mailbox in preview.mailboxes]
    return response
