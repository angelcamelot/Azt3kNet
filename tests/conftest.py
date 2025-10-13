"""Fixtures compartidos para pruebas de Azt3kNet (pendientes)."""

from __future__ import annotations

import pytest


@pytest.fixture
def sample_seed() -> int:
    """Seed determinista para reutilizar en pruebas."""

    return 42
