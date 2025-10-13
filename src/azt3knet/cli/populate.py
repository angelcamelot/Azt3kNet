"""CLI para generación de poblaciones Azt3kNet."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Optional

import typer

from azt3knet.agent_factory.models import PopulationSpec

app = typer.Typer(help="Herramientas de población Azt3kNet")


@app.command()
def populate(
    count: int = typer.Option(1, help="Número de agentes a generar"),
    gender: Optional[str] = typer.Option(None, help="Filtro de género"),
    country: Optional[str] = typer.Option(None, help="Código ISO2 del país"),
    city: Optional[str] = typer.Option(None, help="Ciudad preferida"),
    age_range: Optional[str] = typer.Option(None, help="Rango de edad ej. 18-30"),
    interests: Optional[str] = typer.Option(None, help="Lista separada por comas"),
    seed: Optional[str] = typer.Option(None, help="Seed determinista"),
    create_mailboxes: bool = typer.Option(False, help="Crear buzones en Mailcow"),
    preview: bool = typer.Option(False, help="Solo mostrar resultado sin persistir"),
) -> None:  # pragma: no cover - stub
    """Comando placeholder, implementado en fases posteriores."""

    spec = PopulationSpec(
        count=count,
        gender=gender,
        country=country or "",
        city=city,
        age_range=_parse_age_range(age_range),
        interests=_parse_interests(interests),
        seed=seed,
    )
    typer.echo(json.dumps(asdict(spec), indent=2, default=str))
    if preview:
        typer.echo("Modo preview no persistente (TODO)")
    if create_mailboxes:
        typer.echo("Creación de buzones pendiente")


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
