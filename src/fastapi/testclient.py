"""Simplified TestClient mirroring the interface used in the tests."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Optional

from . import FastAPI


@dataclass
class _Response:
    status_code: int
    _json: Any

    def json(self) -> Any:
        return self._json


class TestClient:
    """Execute requests directly against the in-memory FastAPI stub."""

    def __init__(self, app: FastAPI) -> None:
        self.app = app

    def _perform(self, method: str, path: str, json: Optional[dict[str, Any]] = None) -> _Response:
        coroutine = self.app._call(method, path, payload=json)
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        status_code, payload = loop.run_until_complete(coroutine)
        return _Response(status_code=status_code, _json=payload)

    def get(self, path: str) -> _Response:
        return self._perform("GET", path)

    def post(self, path: str, *, json: Optional[dict[str, Any]] = None) -> _Response:
        return self._perform("POST", path, json=json)
