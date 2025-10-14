"""HTTP utilities that validate hyperlinks found in inbound emails."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import List, Sequence

import httpx

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LinkCheckResult:
    """Represents the outcome of verifying a hyperlink."""

    url: str
    status_code: int | None
    ok: bool
    final_url: str | None = None
    error: str | None = None

    def as_payload(self) -> dict[str, object | None]:
        """Return a JSON-serialisable representation of the result."""

        return {
            "url": self.url,
            "status_code": self.status_code,
            "ok": self.ok,
            "final_url": self.final_url,
            "error": self.error,
        }


class LinkVerifier:
    """Follow hyperlinks and capture basic metadata about their availability."""

    def __init__(
        self,
        *,
        client: httpx.Client | None = None,
        timeout: float = 10.0,
        user_agent: str = "Azt3kNet-LinkVerifier/0.1",
    ) -> None:
        self._owns_client = client is None
        if client is None:
            self._client = httpx.Client(
                timeout=timeout,
                headers={"User-Agent": user_agent},
                follow_redirects=True,
            )
        else:
            self._client = client

    def close(self) -> None:
        """Release resources held by the underlying HTTP client."""

        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "LinkVerifier":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        self.close()

    def verify(self, links: Sequence[str]) -> list[LinkCheckResult]:
        """Validate each hyperlink returning metadata suitable for persistence."""

        results: List[LinkCheckResult] = []
        for url in links:
            if not url:
                continue
            results.append(self._verify_single(url))
        return results

    def _verify_single(self, url: str) -> LinkCheckResult:
        """Verify an individual hyperlink using HEAD/GET fallbacks."""

        try:
            response = self._client.request("HEAD", url, follow_redirects=True)
            if response.status_code in {405, 501}:
                response = self._client.request("GET", url, follow_redirects=True)
            status_code = response.status_code
            ok = 200 <= status_code < 400
            final_url = str(response.url)
            return LinkCheckResult(url=url, status_code=status_code, ok=ok, final_url=final_url)
        except httpx.RequestError as exc:
            logger.debug("Link verification failed for %s: %s", url, exc)
            return LinkCheckResult(url=url, status_code=None, ok=False, final_url=None, error=str(exc))


__all__ = ["LinkCheckResult", "LinkVerifier"]

