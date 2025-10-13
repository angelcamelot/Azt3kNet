"""Population endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ...agent_factory.generator import generate_agents
from ...agent_factory.models import PopulationSpec
from ...core.config import get_settings, resolve_seed

router = APIRouter(tags=["population"])


@router.post("/populate")
async def populate_population(payload: dict[str, object]) -> dict[str, object]:
    """Generate a deterministic population.

    For the first sprint the endpoint returns the generated agents directly.
    Subsequent iterations will enqueue background jobs and persist results.
    """

    try:
        spec = PopulationSpec.from_dict(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    settings = get_settings()
    preview = spec.preview
    if preview and preview > settings.preview_limit:
        raise HTTPException(status_code=400, detail="preview exceeds configured limit")

    spec.seed = resolve_seed(spec.seed)
    agents = generate_agents(spec)
    if preview:
        agents = agents[:preview]
    return {
        "seed": spec.seed,
        "count": len(agents),
        "agents": [agent.model_dump(mode="json") for agent in agents],
        "persisted": False,
        "message": "Persistence will be delivered in a future sprint.",
    }
