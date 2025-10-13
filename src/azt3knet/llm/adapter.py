"""Adaptador para la IA local (Ollama u otro LLM) utilizado por Azt3kNet."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class LLMRequest:
    """Representa un prompt dirigido a la IA local."""

    prompt: str
    seed: int
    field_name: str


class LLMAdapter(Protocol):
    """Contrato de interacción con el modelo local."""

    def generate_field(self, request: LLMRequest) -> str:
        """Devuelve exclusivamente el texto generado por la IA."""


class LocalLLMAdapter:
    """Implementación base pendiente."""

    def __init__(self, *, model: str = "ollama:latest") -> None:
        self.model = model

    def generate_field(self, request: LLMRequest) -> str:  # pragma: no cover - stub
        """TODO: Invocar al LLM local respetando determinismo vía seed."""

        raise NotImplementedError
