"""Helpers for reading object storage configuration from the environment."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Tuple

_TRUE_VALUES = {"1", "true", "yes", "on"}


def _endpoint() -> str:
    internal = os.getenv("MINIO_ENDPOINT_INTERNAL")
    if internal:
        return internal
    return os.getenv("MINIO_ENDPOINT", "http://localhost:9000")


def _env(name: str, default: str) -> str:
    return os.getenv(name, default)


def _bool_env(name: str, default: str) -> bool:
    return os.getenv(name, default).strip().lower() in _TRUE_VALUES


def _bucket_list_factory() -> Tuple[str, ...]:
    buckets_env = os.getenv("AZT3KNET_BLOB_BUCKETS")
    if buckets_env:
        buckets = tuple(
            bucket.strip()
            for bucket in buckets_env.split(",")
            if bucket.strip()
        )
        if buckets:
            return buckets
    return (os.getenv("AZT3KNET_BLOB_BUCKET", "azt3knet"),)


@dataclass
class ObjectStorageSettings:
    """Strongly typed access to S3/MinIO configuration."""

    endpoint: str = field(default_factory=_endpoint)
    access_key: str = field(default_factory=lambda: _env("MINIO_ACCESS_KEY", "azt3knet"))
    secret_key: str = field(default_factory=lambda: _env("MINIO_SECRET_KEY", "azt3knet123"))
    region: str = field(default_factory=lambda: _env("MINIO_REGION", "us-east-1"))
    secure: bool = field(default_factory=lambda: _bool_env("MINIO_USE_SSL", "false"))
    buckets: Tuple[str, ...] = field(default_factory=_bucket_list_factory)

    @property
    def primary_bucket(self) -> str:
        """Return the first configured bucket."""

        return self.buckets[0]


@lru_cache(maxsize=1)
def get_object_storage_settings() -> ObjectStorageSettings:
    """Return the cached object storage settings instance."""

    return ObjectStorageSettings()


__all__ = ["ObjectStorageSettings", "get_object_storage_settings"]
