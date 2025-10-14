"""Persistence abstractions for the simulation platform.

The storage layer exposes SQLAlchemy models, repositories, and units of
work that support SQLite and Postgres backends for development and
testing.

Blob/object storage integration relies on the MinIO/S3 configuration
captured by :func:`azt3knet.core.object_storage.get_object_storage_settings`.
Importing the helper here keeps downstream modules from reaching into the
`core` package directly when they need access to bucket names or
credentials.
"""

from azt3knet.core.object_storage import (  # noqa: F401
    ObjectStorageSettings,
    get_object_storage_settings,
)

__all__ = ["ObjectStorageSettings", "get_object_storage_settings"]
