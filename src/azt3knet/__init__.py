"""Azt3kNet synthetic agent simulator."""

from importlib.metadata import PackageNotFoundError, version

try:  # pragma: no cover - metadata only available in installed environment
    __version__ = version("azt3knet")
except PackageNotFoundError:  # pragma: no cover
    __version__ = "0.0.0"

__all__ = ["__version__"]
