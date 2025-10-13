"""Command line helpers for generating Azt3kNet populations."""

from __future__ import annotations

import json
from typing import Optional

import typer

from azt3knet.agent_factory.models import PopulationSpec
from azt3knet.core.config import resolve_seed
from azt3knet.core.seeds import SeedSequence
from azt3knet.llm.adapter import LocalLLMAdapter
from azt3knet.population.builder import build_population

app = typer.Typer(help="Population utilities for deterministic previews")


@app.command()
def populate(
    count: int = typer.Option(1, help="Number of agents to generate"),
    gender: Optional[str] = typer.Option(None, help="Gender filter"),
    country: Optional[str] = typer.Option(None, help="ISO2 country code"),
    city: Optional[str] = typer.Option(None, help="Preferred city"),
    age_range: Optional[str] = typer.Option(None, help="Age range e.g. 18-30"),
    interests: Optional[str] = typer.Option(None, help="Comma separated interests"),
    seed: Optional[str] = typer.Option(None, help="Deterministic seed"),
    create_mailboxes: bool = typer.Option(False, help="Provision Mailcow mailboxes"),
    preview: Optional[int] = typer.Option(None, help="Limit the preview to N agents"),
) -> None:
    """Generate a synthetic population preview and optional mailboxes."""

    spec = PopulationSpec(
        count=count,
        gender=gender,
        country=(country or "").upper(),
        city=city,
        age_range=_parse_age_range(age_range),
        interests=_parse_interests(interests),
        seed=seed,
        preview=preview,
    )
    resolved_seed = resolve_seed(spec.seed)
    numeric_seed = SeedSequence(resolved_seed).derive("cli")
    adapter = LocalLLMAdapter()
    preview_result = build_population(
        spec,
        llm=adapter,
        deterministic_seed=numeric_seed,
        create_mailboxes=create_mailboxes,
    )

    payload: dict[str, object] = {
        "seed": resolved_seed,
        "count": len(preview_result.agents),
        "agents": [agent.model_dump(mode="json") for agent in preview_result.agents],
    }
    if preview_result.mailboxes:
        payload["mailboxes"] = [assignment.as_public_dict() for assignment in preview_result.mailboxes]

    typer.echo(json.dumps(payload, indent=2))


def _parse_age_range(value: Optional[str]) -> Optional[tuple[int, int]]:
    if not value:
        return None
    start, _, end = value.partition("-")
    return (int(start), int(end))


def _parse_interests(value: Optional[str]) -> Optional[list[str]]:
    if not value:
        return None
    return [item.strip() for item in value.split(",") if item.strip()]


if __name__ == "__main__":
    app()
