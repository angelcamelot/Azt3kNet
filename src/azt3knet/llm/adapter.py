"""Adapter for the local LLM (Ollama or similar) used by Azt3kNet."""

from __future__ import annotations

import hashlib

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class LLMRequest:
    """Container describing a prompt sent to the local language model."""

    prompt: str
    seed: int
    field_name: str


class LLMAdapter(Protocol):
    """Interface implemented by language model adapters."""

    def generate_field(self, request: LLMRequest) -> str:
        """Return the generated text for the requested field."""


class LocalLLMAdapter:
    """Deterministic offline adapter used for testing and previews."""

    _VOCABULARY = (
        "aurora",
        "lumen",
        "nexus",
        "signal",
        "glyph",
        "vector",
        "orbit",
        "stride",
    )

    def __init__(self, *, model: str = "deepseek-r1:1.5b") -> None:
        """Initialize the adapter with the lightweight DeepSeek model name.

        The real implementation running against Ollama should align with this
        default so local previews mimic the production configuration.
        """

        self.model = model

    def generate_field(self, request: LLMRequest) -> str:
        """Return a short deterministic phrase for the requested field."""

        payload = f"{self.model}:{request.seed}:{request.field_name}:{request.prompt}"
        digest = hashlib.sha256(payload.encode("utf-8")).digest()
        tokens = []
        for index in range(3):
            tokens.append(self._VOCABULARY[digest[index] % len(self._VOCABULARY)])
        return "-".join(tokens)
