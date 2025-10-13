"""FastAPI application exposing the first sprint endpoints."""

from __future__ import annotations

from fastapi import FastAPI

from ..core.logging import configure_logging
from .routes.populate import router as populate_router

configure_logging()
app = FastAPI(title="Azt3kNet API", version="0.1.0")


@app.on_event("startup")
async def _startup() -> None:
    configure_logging()


@app.get("/healthz", tags=["system"])
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(populate_router, prefix="/api")
