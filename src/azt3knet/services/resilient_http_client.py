"""Resilient HTTP client with retries, circuit breaking and metrics."""

from __future__ import annotations

from dataclasses import dataclass, field
import random
import threading
import time
from typing import Callable, Iterable, Sequence

import httpx


class CircuitBreakerOpenError(RuntimeError):
    """Raised when a request is attempted while the breaker is open."""


@dataclass
class ClientMetrics:
    """Simple in-memory metrics for observing client behaviour."""

    service_name: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_retries: int = 0
    rate_limited_responses: int = 0
    circuit_breaker_tripped: int = 0
    circuit_breaker_rejections: int = 0

    def as_dict(self) -> dict[str, int | str]:
        """Return a serialisable view of the collected metrics."""

        return {
            "service_name": self.service_name,
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "total_retries": self.total_retries,
            "rate_limited_responses": self.rate_limited_responses,
            "circuit_breaker_tripped": self.circuit_breaker_tripped,
            "circuit_breaker_rejections": self.circuit_breaker_rejections,
        }


class CircuitBreaker:
    """Small synchronous circuit breaker implementation."""

    def __init__(
        self,
        *,
        failure_threshold: int = 5,
        recovery_time: float = 30.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if failure_threshold <= 0:
            raise ValueError("failure_threshold must be positive")
        if recovery_time <= 0:
            raise ValueError("recovery_time must be positive")
        self._failure_threshold = failure_threshold
        self._recovery_time = recovery_time
        self._clock = clock
        self._lock = threading.Lock()
        self._state = "closed"
        self._failure_count = 0
        self._opened_at = 0.0

    @property
    def state(self) -> str:
        with self._lock:
            return self._state

    def allow_request(self) -> bool:
        with self._lock:
            if self._state == "open":
                if self._clock() - self._opened_at >= self._recovery_time:
                    self._state = "half-open"
                    return True
                return False
            return True

    def record_success(self) -> None:
        with self._lock:
            self._failure_count = 0
            self._state = "closed"
            self._opened_at = 0.0

    def record_failure(self) -> bool:
        """Register a failure and return True when the breaker opens."""

        with self._lock:
            if self._state == "half-open":
                self._state = "open"
                self._opened_at = self._clock()
                self._failure_count = self._failure_threshold
                return True

            self._failure_count += 1
            if self._failure_count >= self._failure_threshold:
                self._state = "open"
                self._opened_at = self._clock()
                return True
            return False


@dataclass
class RetryConfiguration:
    """Configuration for the retry/backoff strategy."""

    max_retries: int = 3
    backoff_factor: float = 0.5
    max_backoff: float = 10.0
    jitter_ratio: float = 0.1
    retry_statuses: Sequence[int] = field(
        default_factory=lambda: (408, 425, 429, 500, 502, 503, 504)
    )
    _retry_status_set: frozenset[int] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        statuses = tuple(dict.fromkeys(self.retry_statuses))
        if not statuses:
            raise ValueError("retry_statuses must contain at least one status code")
        object.__setattr__(self, "retry_statuses", statuses)
        object.__setattr__(self, "_retry_status_set", frozenset(statuses))

    def should_retry(self, status_code: int) -> bool:
        """Return True when the response status should trigger a retry."""

        return status_code in self._retry_status_set


class ResilientHTTPClient:
    """Wrap an ``httpx.Client`` with retries, circuit breaking and metrics."""

    def __init__(
        self,
        client: httpx.Client,
        *,
        service_name: str,
        retry_config: RetryConfiguration | None = None,
        circuit_breaker: CircuitBreaker | None = None,
        metrics: ClientMetrics | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._client = client
        self._retry_config = retry_config or RetryConfiguration()
        self._breaker = circuit_breaker or CircuitBreaker()
        self.metrics = metrics or ClientMetrics(service_name=service_name)
        self._sleep = sleep
        self._retry_statuses = frozenset(self._retry_config.retry_statuses)

    def close(self) -> None:
        self._client.close()

    def _compute_backoff(self, attempt: int) -> float:
        delay = self._retry_config.backoff_factor * (2 ** (attempt - 1))
        delay = min(delay, self._retry_config.max_backoff)
        jitter = delay * self._retry_config.jitter_ratio
        if jitter:
            delay += random.uniform(-jitter, jitter)
            delay = max(delay, 0.0)
        return delay

    def _should_retry_response(self, response: httpx.Response) -> bool:
        return response.status_code in self._retry_statuses

    def request(self, method: str, url: str, **kwargs) -> httpx.Response:
        """Issue a resilient HTTP request."""

        if not self._breaker.allow_request():
            self.metrics.circuit_breaker_rejections += 1
            raise CircuitBreakerOpenError("circuit breaker is open")

        attempt = 0
        max_attempts = self._retry_config.max_retries + 1
        last_exc: httpx.RequestError | None = None
        response: httpx.Response | None = None

        while attempt < max_attempts:
            attempt += 1
            self.metrics.total_requests += 1
            try:
                response = self._client.request(method, url, **kwargs)
            except httpx.RequestError as exc:  # pragma: no cover - network error
                last_exc = exc
                self.metrics.failed_requests += 1
                opened = self._breaker.record_failure()
                if opened:
                    self.metrics.circuit_breaker_tripped += 1
                if attempt >= max_attempts:
                    raise
            else:
                if self._should_retry_response(response):
                    self.metrics.failed_requests += 1
                    if response.status_code == 429:
                        self.metrics.rate_limited_responses += 1
                    opened = self._breaker.record_failure()
                    if opened:
                        self.metrics.circuit_breaker_tripped += 1
                    if attempt >= max_attempts:
                        return response
                    response.close()
                else:
                    self.metrics.successful_requests += 1
                    self._breaker.record_success()
                    return response

            if attempt < max_attempts:
                self.metrics.total_retries += 1
                delay = self._compute_backoff(attempt)
                self._sleep(delay)

        if last_exc is not None:
            raise last_exc
        assert response is not None  # for mypy, we either returned or have a response
        return response


__all__ = [
    "CircuitBreaker",
    "CircuitBreakerOpenError",
    "ClientMetrics",
    "ResilientHTTPClient",
    "RetryConfiguration",
]

