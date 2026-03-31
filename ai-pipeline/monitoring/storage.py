"""
Monitoring storage backend (AWS/local).
Uses DATA_DIR from env (e.g. /data for EFS, or ./data locally).
No Modal dependency; all connections are file-based for AWS compatibility.
"""

import os
from pathlib import Path
from typing import Any, BinaryIO, Literal, TextIO, cast, overload


def _data_dir() -> Path:
    """Base directory for metrics/logs. Use EFS mount /data on AWS or env DATA_DIR."""
    path = os.environ.get("DATA_DIR", "/data")
    return Path(path)


class LocalVolume:
    """Volume-like interface using local/EFS path (AWS-friendly)."""

    def __init__(self, base: str | Path | None = None):
        self._base = Path(base) if base else _data_dir()

    def _path(self, key: str) -> Path:
        return self._base / key.lstrip("/").replace("/", os.sep)

    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    @overload
    def open(
        self,
        key: str,
        mode: Literal["r", "w", "a", "r+", "w+", "a+", "x", "x+"] = "r",
        **kwargs: Any,
    ) -> TextIO: ...

    @overload
    def open(
        self,
        key: str,
        mode: Literal["rb", "wb", "ab", "r+b", "w+b", "a+b", "xb", "x+b"],
        **kwargs: Any,
    ) -> BinaryIO: ...

    def open(self, key: str, mode: str = "r", **kwargs: Any) -> TextIO | BinaryIO:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        if "b" in mode:
            return cast(BinaryIO, open(p, mode, **kwargs))
        kwargs.setdefault("encoding", "utf-8")
        return cast(TextIO, open(p, mode, **kwargs))


# Singleton for monitoring (same as previous metrics_volume API)
metrics_volume = LocalVolume()
