"""Tests for the compliance guard pipeline."""

from __future__ import annotations

import pytest

from azt3knet.compliance_guard import ComplianceGuard, ComplianceViolation, ensure_guarded_llm
from azt3knet.llm.adapter import LLMRequest


class _EchoAdapter:
    def generate_field(self, request: LLMRequest) -> str:
        return "  synthetic-output  "


class _EmptyAdapter:
    def generate_field(self, request: LLMRequest) -> str:
        return "   "


def test_guard_strips_and_audits_content() -> None:
    guard = ComplianceGuard()
    adapter = ensure_guarded_llm(_EchoAdapter(), context="tests.guard", guard=guard)

    result = adapter.generate_field(
        LLMRequest(prompt="prompt", seed=1, field_name="field"),
    )

    assert result == "synthetic-output"

    events = guard.export_events()
    assert len(events) == 1
    event = events[0]
    assert event.source == "tests.guard"
    assert event.field_name == "field"
    assert event.content == "synthetic-output"
    assert event.approved is True


def test_guard_rejects_empty_content() -> None:
    guard = ComplianceGuard()
    adapter = ensure_guarded_llm(_EmptyAdapter(), context="tests.guard", guard=guard)

    with pytest.raises(ComplianceViolation):
        adapter.generate_field(
            LLMRequest(prompt="prompt", seed=2, field_name="field"),
        )

    events = guard.export_events()
    assert len(events) == 1
    event = events[0]
    assert event.approved is False
    assert event.labels == ("empty_content",)

