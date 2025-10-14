"""Command line helpers for generating Azt3kNet populations."""

from __future__ import annotations

import json
from typing import Optional

import typer

from azt3knet.agent_factory.models import PopulationSpec
from azt3knet.llm.adapter import LocalLLMAdapter
from azt3knet.population.builder import generate_population_preview
from azt3knet.storage.agents import (
    AgentPersistenceError,
    AgentRepository,
    AgentUniquenessError,
)
from azt3knet.storage.db import DatabaseConfigurationError, create_engine_from_url

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
    persist: bool = typer.Option(False, help="Persist generated agents to storage"),
    database_url: Optional[str] = typer.Option(
        None,
        help="Override the DATABASE_URL used for persistence",
    ),
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
        persist=persist,
    )
    adapter = LocalLLMAdapter()
    generation = generate_population_preview(
        spec,
        namespace="cli",
        llm=adapter,
        create_mailboxes=create_mailboxes,
    )
    preview_result = generation.preview

    payload: dict[str, object] = {
        "seed": generation.seed,
        "count": len(preview_result.agents),
        "agents": [agent.model_dump(mode="json") for agent in preview_result.agents],
    }
    if preview_result.mailboxes:
        payload["mailboxes"] = [assignment.as_public_dict() for assignment in preview_result.mailboxes]

    if persist:
        try:
            bundle = create_engine_from_url(database_url)
        except DatabaseConfigurationError as exc:
            typer.secho(str(exc), err=True, fg=typer.colors.RED)
            raise typer.Exit(code=1) from exc
        store = AgentRepository.from_engine(bundle)
        try:
            persisted = store.persist_agents(preview_result.agents)
        except AgentUniquenessError as exc:
            typer.secho(f"Username conflict detected: {exc}", err=True, fg=typer.colors.RED)
            raise typer.Exit(code=1) from exc
        except AgentPersistenceError as exc:
            typer.secho(f"Failed to persist agents: {exc}", err=True, fg=typer.colors.RED)
            raise typer.Exit(code=1) from exc
        payload["persisted"] = persisted

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
