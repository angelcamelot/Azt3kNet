from __future__ import annotations

import itertools

import httpx
import pytest

from azt3knet.services.resilient_http_client import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    ResilientHTTPClient,
    RetryConfiguration,
)


class DummyClock:
    def __init__(self) -> None:
        self._time = 0.0

    def advance(self, delta: float) -> None:
        self._time += delta

    def __call__(self) -> float:
        return self._time


def test_retries_apply_exponential_backoff() -> None:
    attempts = itertools.count(1)

    def handler(_: httpx.Request) -> httpx.Response:
        attempt = next(attempts)
        if attempt < 3:
            return httpx.Response(429, json={"error": "too many"})
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport, base_url="https://service.local")
    retry_config = RetryConfiguration(max_retries=4, backoff_factor=0.1, jitter_ratio=0.0)
    delays: list[float] = []
    resilient = ResilientHTTPClient(
        client,
        service_name="test-service",
        retry_config=retry_config,
        sleep=delays.append,
    )

    response = resilient.request("GET", "/resource")

    assert response.status_code == 200
    assert delays == [0.1, 0.2]
    metrics = resilient.metrics.as_dict()
    assert metrics["total_requests"] == 3
    assert metrics["total_retries"] == 2
    assert metrics["rate_limited_responses"] == 2


def test_custom_retry_statuses_are_honoured() -> None:
    attempts = itertools.count(1)

    def handler(_: httpx.Request) -> httpx.Response:
        if next(attempts) == 1:
            return httpx.Response(418)
        return httpx.Response(200)

    client = httpx.Client(
        transport=httpx.MockTransport(handler), base_url="https://service.local"
    )
    retry_config = RetryConfiguration(max_retries=1, retry_statuses=(418,))
    resilient = ResilientHTTPClient(
        client,
        service_name="test-service",
        retry_config=retry_config,
        sleep=lambda _: None,
    )

    response = resilient.request("GET", "/resource")

    assert response.status_code == 200
    metrics = resilient.metrics.as_dict()
    assert metrics["total_requests"] == 2
    assert metrics["total_retries"] == 1


def test_circuit_breaker_blocks_requests_until_recovered() -> None:
    clock = DummyClock()

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport, base_url="https://service.local")
    breaker = CircuitBreaker(failure_threshold=2, recovery_time=5.0, clock=clock)
    retry_config = RetryConfiguration(max_retries=0)
    resilient = ResilientHTTPClient(
        client,
        service_name="test-service",
        retry_config=retry_config,
        circuit_breaker=breaker,
        sleep=lambda _: None,
    )

    first = resilient.request("GET", "/fail")
    assert first.status_code == 500

    second = resilient.request("GET", "/fail")
    assert second.status_code == 500
    assert breaker.state == "open"
    assert resilient.metrics.circuit_breaker_tripped == 1

    with pytest.raises(CircuitBreakerOpenError):
        resilient.request("GET", "/fail")

    clock.advance(5.5)

    def success_handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True})

    client = httpx.Client(transport=httpx.MockTransport(success_handler), base_url="https://service.local")
    resilient = ResilientHTTPClient(
        client,
        service_name="test-service",
        retry_config=retry_config,
        circuit_breaker=breaker,
        sleep=lambda _: None,
    )

    recovered = resilient.request("GET", "/recover")
    assert recovered.status_code == 200
    assert breaker.state == "closed"
