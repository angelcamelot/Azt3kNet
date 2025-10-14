#!/usr/bin/env python
"""Bootstrap helper that ensures MinIO buckets exist for local development."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urlparse

_TRUE_VALUES = {"1", "true", "yes", "on"}


@dataclass
class MinioSettings:
    """Configuration derived from environment variables."""

    endpoint: str
    access_key: str
    secret_key: str
    region: str
    secure: bool
    buckets: tuple[str, ...]

    @classmethod
    def from_env(cls) -> "MinioSettings":
        endpoint = os.getenv("MINIO_ENDPOINT_INTERNAL") or os.getenv(
            "MINIO_ENDPOINT", "http://localhost:9000"
        )
        access_key = os.getenv("MINIO_ACCESS_KEY")
        secret_key = os.getenv("MINIO_SECRET_KEY")
        region = os.getenv("MINIO_REGION", "us-east-1")
        secure_override = os.getenv("MINIO_USE_SSL")

        if not access_key or not secret_key:
            raise RuntimeError(
                "MINIO_ACCESS_KEY and MINIO_SECRET_KEY must be defined in the environment"
            )

        parsed = urlparse(endpoint)
        if parsed.scheme:
            host = parsed.netloc
            default_secure = parsed.scheme == "https"
        else:
            host = parsed.path
            default_secure = False

        if secure_override is None:
            secure = default_secure
        else:
            secure = secure_override.strip().lower() in _TRUE_VALUES

        buckets_env = os.getenv("AZT3KNET_BLOB_BUCKETS")
        if buckets_env:
            buckets = tuple(
                bucket.strip()
                for bucket in buckets_env.split(",")
                if bucket.strip()
            )
        else:
            buckets = (os.getenv("AZT3KNET_BLOB_BUCKET", "azt3knet"),)

        if not buckets:
            raise RuntimeError(
                "At least one bucket must be provided via AZT3KNET_BLOB_BUCKET or AZT3KNET_BLOB_BUCKETS"
            )

        return cls(
            endpoint=host,
            access_key=access_key,
            secret_key=secret_key,
            region=region,
            secure=secure,
            buckets=buckets,
        )


def ensure_buckets(client: "Minio", buckets: Iterable[str]) -> None:
    """Create buckets if they do not exist."""

    for bucket in buckets:
        if client.bucket_exists(bucket):
            print(f"[setup_minio] Bucket '{bucket}' already exists.")
            continue
        client.make_bucket(bucket)
        print(f"[setup_minio] Created bucket '{bucket}'.")


def main() -> int:
    try:
        from minio import Minio
        from minio.error import S3Error
    except ImportError as exc:  # pragma: no cover - optional dependency guard
        print(
            "[setup_minio] Missing dependency 'minio'. Install it with 'poetry add minio' or 'pip install minio'.",
            file=sys.stderr,
        )
        return 1

    try:
        settings = MinioSettings.from_env()
    except RuntimeError as exc:
        print(f"[setup_minio] {exc}", file=sys.stderr)
        return 1

    client = Minio(
        settings.endpoint,
        access_key=settings.access_key,
        secret_key=settings.secret_key,
        secure=settings.secure,
        region=settings.region,
    )

    try:
        ensure_buckets(client, settings.buckets)
    except S3Error as exc:
        print(f"[setup_minio] Failed to create buckets: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
