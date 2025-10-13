"""Compliance guard pipeline ensuring generated content is reviewed."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Iterable, Mapping, Protocol, Sequence

from azt3knet.llm.adapter import LLMAdapter, LLMRequest

from .audit import AuditLog


class Sanitizer(Protocol):
    """Callable that normalizes generated content before review."""

    def __call__(self, value: str) -> str:  # pragma: no cover - protocol signature
        ...


class ComplianceRule(Protocol):
    """Callable that validates sanitized content."""

    def __call__(
        self,
        content: str,
        *,
        field_name: str,
        metadata: Mapping[str, str] | None = None,
    ) -> tuple[bool, Iterable[str], str | None]:  # pragma: no cover - protocol signature
        ...


@dataclass(frozen=True)
class ComplianceDecision:
    """Result returned after the guard evaluates generated content."""

    content: str
    approved: bool
    labels: tuple[str, ...]
    rationale: str | None = None


class ComplianceViolation(RuntimeError):
    """Raised when generated content does not pass compliance checks."""


def _default_sanitizer(value: str) -> str:
    return value.strip()


def _default_rule(
    content: str,
    *,
    field_name: str,
    metadata: Mapping[str, str] | None = None,
) -> tuple[bool, Iterable[str], str | None]:
    """Reject obviously unsafe content for offline contexts."""

    lowered = content.lower()
    if not lowered:
        return False, ("empty_content",), "Generated text was empty after sanitization."
    if "http://" in lowered or "https://" in lowered:
        return False, ("link_detected",), "Hyperlinks are not allowed in offline previews."
    return True, (), None


class ComplianceGuard:
    """Coordinator that sanitizes, validates, and audits generated content."""

    def __init__(
        self,
        *,
        audit_log: AuditLog | None = None,
        sanitizers: Sequence[Sanitizer] | None = None,
        rules: Sequence[ComplianceRule] | None = None,
    ) -> None:
        self._audit_log = audit_log or AuditLog()
        self._sanitizers = sanitizers or (_default_sanitizer,)
        self._rules = rules or (_default_rule,)

    def review(
        self,
        *,
        source: str,
        field_name: str,
        content: str,
        metadata: Mapping[str, str] | None = None,
    ) -> ComplianceDecision:
        """Sanitize and validate the generated content."""

        sanitized = content
        for sanitizer in self._sanitizers:
            sanitized = sanitizer(sanitized)

        approved = True
        labels: list[str] = []
        rationale: str | None = None
        for rule in self._rules:
            decision, rule_labels, rule_rationale = rule(
                sanitized, field_name=field_name, metadata=metadata
            )
            if not decision:
                approved = False
                labels.extend(rule_labels)
                rationale = rule_rationale
                break
            labels.extend(rule_labels)

        self._audit_log.record(
            source=source,
            field_name=field_name,
            content=sanitized,
            approved=approved,
            labels=labels,
            metadata=metadata,
        )

        if not approved:
            raise ComplianceViolation(rationale or "Content rejected by compliance guard.")

        return ComplianceDecision(
            content=sanitized,
            approved=approved,
            labels=tuple(labels),
            rationale=rationale,
        )

    def export_events(self) -> tuple:
        """Expose a tuple copy of the audit log for external storage."""

        return self._audit_log.export()


class GuardedLLMAdapter:
    """Adapter wrapper that routes LLM generations through the compliance guard."""

    def __init__(self, adapter: LLMAdapter, guard: ComplianceGuard, *, context: str) -> None:
        if isinstance(adapter, GuardedLLMAdapter):
            self._adapter = adapter._adapter
            self._guard = adapter._guard
        else:
            self._adapter = adapter
            self._guard = guard
        self._context = context

    def generate_field(self, request: LLMRequest) -> str:
        raw = self._adapter.generate_field(request)
        metadata = {
            "seed": str(request.seed),
            "context": self._context,
            "prompt_sha256": hashlib.sha256(request.prompt.encode("utf-8")).hexdigest(),
        }
        decision = self._guard.review(
            source=self._context,
            field_name=request.field_name,
            content=raw,
            metadata=metadata,
        )
        return decision.content

    @property
    def compliance_guard(self) -> ComplianceGuard:
        return self._guard


_DEFAULT_GUARD = ComplianceGuard()


def get_default_guard() -> ComplianceGuard:
    """Return the process-wide default guard instance."""

    return _DEFAULT_GUARD


def ensure_guarded_llm(
    adapter: LLMAdapter,
    *,
    context: str,
    guard: ComplianceGuard | None = None,
) -> GuardedLLMAdapter:
    """Wrap the adapter with compliance guard enforcement if needed."""

    active_guard = guard or get_default_guard()
    return GuardedLLMAdapter(adapter, active_guard, context=context)


__all__ = [
    "ComplianceDecision",
    "ComplianceGuard",
    "ComplianceViolation",
    "GuardedLLMAdapter",
    "ensure_guarded_llm",
    "get_default_guard",
]

