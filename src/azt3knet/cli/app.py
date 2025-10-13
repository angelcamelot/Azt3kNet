"""Typer CLI entrypoint for Azt3kNet."""

import json
from typing import Optional

import typer

from ..agent_factory.generator import generate_agents
from ..agent_factory.models import PopulationSpec
from ..core.config import get_settings, resolve_seed
from ..core.logging import configure_logging

app = typer.Typer(help="Synthetic agent operations for the Azt3kNet lab.")


def _apply_preview_limit(preview: Optional[int]) -> Optional[int]:
    if preview is None:
        return None
    settings = get_settings()
    return min(preview, settings.preview_limit)


@app.callback()
def main() -> None:  # pragma: no cover - Typer handles invocation
    """Bootstrap logging before running any command."""

    configure_logging()


@app.command()
def populate(
    gender: Optional[str] = typer.Option(None, help="Gender filter for the population."),
    count: int = typer.Option(..., min=1, help="Number of agents to generate."),
    country: str = typer.Option(..., help="ISO country code."),
    city: Optional[str] = typer.Option(None, help="Optional city for context."),
    age: Optional[str] = typer.Option(
        None, help="Inclusive age range formatted as 'min-max' (e.g. 18-35)."
    ),
    interests: Optional[str] = typer.Option(
        None, help="Comma separated list of interests (e.g. 'cumbia,arte urbano')."
    ),
    seed: Optional[str] = typer.Option(None, help="Deterministic seed."),
    preview: Optional[int] = typer.Option(None, help="Preview the first N agents."),
    persist: bool = typer.Option(False, help="Persist the population (stub)."),
) -> None:
    """Generate a synthetic population preview and print JSON to stdout."""

    if age:
        try:
            low, high = [int(part) for part in age.split("-")]
            age_range = (low, high)
        except ValueError as exc:  # pragma: no cover - Typer already validates
            raise typer.BadParameter("age must follow the 'min-max' format") from exc
    else:
        age_range = None

    interests_list = interests.split(",") if interests else None
    spec = PopulationSpec(
        gender=gender,  # type: ignore[arg-type]
        count=count,
        country=country,
        city=city,
        age_range=age_range,
        interests=interests_list,
        seed=resolve_seed(seed),
        preview=_apply_preview_limit(preview),
        persist=persist,
    )

    agents = generate_agents(spec)
    if spec.preview:
        agents = agents[: spec.preview]
    payload = [agent.model_dump(mode="json") for agent in agents]
    typer.echo(json.dumps(payload, indent=2, ensure_ascii=False))

    if persist:
        typer.secho(
            "[stub] Persistence is not yet implemented. Use exports in later sprints.",
            fg=typer.colors.YELLOW,
        )


def run() -> None:  # pragma: no cover - used for entry point
    app()


__all__ = ["app", "run"]
