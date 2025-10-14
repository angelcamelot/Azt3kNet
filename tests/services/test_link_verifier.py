"""Tests for the LinkVerifier helper used to follow hyperlinks."""

from __future__ import annotations

import httpx

from azt3knet.services.link_verifier import LinkVerifier


def test_link_verifier_uses_head_requests() -> None:
    """HEAD requests should be attempted first for efficiency."""

    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.method)
        return httpx.Response(200, request=request)

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport, follow_redirects=True) as client:
        verifier = LinkVerifier(client=client)
        results = verifier.verify(["https://example.org"])

    assert calls == ["HEAD"]
    assert results[0].status_code == 200
    assert results[0].ok is True
    assert (results[0].final_url or "").rstrip("/") == "https://example.org"


def test_link_verifier_falls_back_to_get_when_head_not_allowed() -> None:
    """The verifier should retry with GET when HEAD is unsupported."""

    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.method)
        if request.method == "HEAD":
            return httpx.Response(405, request=request)
        return httpx.Response(200, request=request)

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport, follow_redirects=True) as client:
        verifier = LinkVerifier(client=client)
        results = verifier.verify(["https://example.org"])

    assert calls == ["HEAD", "GET"]
    assert results[0].status_code == 200
    assert results[0].ok is True


def test_link_verifier_handles_network_errors() -> None:
    """Network failures should return a descriptive result instead of raising."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TransportError("connection lost")

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport, follow_redirects=True) as client:
        verifier = LinkVerifier(client=client)
        results = verifier.verify(["https://example.org"])

    assert results[0].status_code is None
    assert results[0].ok is False
    assert results[0].error is not None

