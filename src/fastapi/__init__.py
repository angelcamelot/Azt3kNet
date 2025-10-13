"""Lightweight FastAPI substitute used for the kata test suite."""

import inspect
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Iterable, List, Optional, Tuple

RouteHandler = Callable[..., Awaitable[Any] | Any]


class HTTPException(Exception):
    """Exception used to represent HTTP errors."""

    def __init__(self, status_code: int, detail: str | Dict[str, Any] | None = None) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail or ""


@dataclass
class _Route:
    method: str
    path: str
    handler: RouteHandler


class APIRouter:
    """Minimal router collecting handlers before being attached to an app."""

    def __init__(self, *, tags: Optional[Iterable[str]] = None) -> None:
        self.tags = list(tags or [])
        self._routes: List[_Route] = []

    def _register(self, method: str, path: str, handler: RouteHandler) -> RouteHandler:
        self._routes.append(_Route(method, path, handler))
        return handler

    def get(self, path: str, *, tags: Optional[Iterable[str]] = None) -> Callable[[RouteHandler], RouteHandler]:
        def decorator(func: RouteHandler) -> RouteHandler:
            return self._register("GET", path, func)

        return decorator

    def post(self, path: str, *, tags: Optional[Iterable[str]] = None) -> Callable[[RouteHandler], RouteHandler]:
        def decorator(func: RouteHandler) -> RouteHandler:
            return self._register("POST", path, func)

        return decorator

    @property
    def routes(self) -> List[_Route]:
        return list(self._routes)


class FastAPI:
    """Extremely small subset of FastAPI used in the exercises."""

    def __init__(self, *, title: str = "FastAPI", version: str = "0.1.0") -> None:
        self.title = title
        self.version = version
        self._routes: Dict[Tuple[str, str], RouteHandler] = {}
        self._startup_handlers: List[Callable[[], Awaitable[None] | None]] = []

    def _register(self, method: str, path: str, handler: RouteHandler) -> RouteHandler:
        self._routes[(method.upper(), path)] = handler
        return handler

    def get(self, path: str, *, tags: Optional[Iterable[str]] = None) -> Callable[[RouteHandler], RouteHandler]:
        def decorator(func: RouteHandler) -> RouteHandler:
            return self._register("GET", path, func)

        return decorator

    def post(self, path: str, *, tags: Optional[Iterable[str]] = None) -> Callable[[RouteHandler], RouteHandler]:
        def decorator(func: RouteHandler) -> RouteHandler:
            return self._register("POST", path, func)

        return decorator

    def on_event(self, event: str) -> Callable[[Callable[[], Awaitable[None] | None]], Callable[[], Awaitable[None] | None]]:
        if event != "startup":
            raise ValueError("Only the 'startup' event is supported in this stub")

        def decorator(func: Callable[[], Awaitable[None] | None]) -> Callable[[], Awaitable[None] | None]:
            self._startup_handlers.append(func)
            return func

        return decorator

    def include_router(self, router: APIRouter, *, prefix: str = "") -> None:
        for route in router.routes:
            full_path = f"{prefix.rstrip('/')}{route.path}" if prefix else route.path
            self._register(route.method, full_path, route.handler)

    async def _run_startup(self) -> None:
        for handler in self._startup_handlers:
            result = handler()
            if inspect.isawaitable(result):
                await result

    async def _call(self, method: str, path: str, payload: Optional[dict[str, Any]] = None) -> Tuple[int, Any]:
        handler = self._routes.get((method.upper(), path))
        if handler is None:
            return 404, {"detail": "Not Found"}

        try:
            signature = inspect.signature(handler)
            kwargs: Dict[str, Any] = {}
            if payload is not None and signature.parameters:
                parameter = next(iter(signature.parameters.values()))
                annotation = parameter.annotation
                if isinstance(annotation, str):
                    annotation = handler.__globals__.get(annotation, annotation)
                if hasattr(annotation, "from_dict") and callable(getattr(annotation, "from_dict")):
                    argument = annotation.from_dict(payload)  # type: ignore[misc]
                else:
                    argument = payload
                kwargs[parameter.name] = argument
            result = handler(**kwargs)
            if inspect.isawaitable(result):
                result = await result
            return 200, result
        except HTTPException as exc:  # pragma: no cover - exercised via tests
            return exc.status_code, {"detail": exc.detail}


__all__ = ["FastAPI", "APIRouter", "HTTPException"]
