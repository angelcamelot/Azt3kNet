"""Herramientas para construir poblaciones sintéticas."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List

from azt3knet.llm.adapter import LLMAdapter, LLMRequest
from azt3knet.models.agent import Agent, AgentIdentity, AgentTraits, PopulationSpec


@dataclass
class PopulationPreview:
    """Contenedor con el resultado de un modo preview."""

    agents: List[Agent]


def build_population(
    spec: PopulationSpec,
    *,
    llm: LLMAdapter,
    deterministic_seed: int,
    create_mailboxes: bool = False,
) -> Iterable[Agent]:  # pragma: no cover - stub
    """Construye una secuencia de agentes.

    TODO: Implementar generación determinista y orquestación Mailcow.
    """

    raise NotImplementedError
