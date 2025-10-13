"""Herramientas para construir poblaciones sintéticas."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List

from azt3knet.agent_factory.models import AgentProfile, PopulationSpec
from azt3knet.llm.adapter import LLMAdapter, LLMRequest


@dataclass
class PopulationPreview:
    """Contenedor con el resultado de un modo preview."""

    agents: List[AgentProfile]


def build_population(
    spec: PopulationSpec,
    *,
    llm: LLMAdapter,
    deterministic_seed: int,
    create_mailboxes: bool = False,
) -> Iterable[AgentProfile]:  # pragma: no cover - stub
    """Construye una secuencia de agentes.

    TODO: Implementar generación determinista y orquestación Mailcow.
    """

    raise NotImplementedError
