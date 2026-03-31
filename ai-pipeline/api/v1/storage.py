"""
API storage backend (AWS/local). Uses DATA_DIR from env. No Modal.
"""

import os
from pathlib import Path


def _data_dir() -> Path:
    path = os.environ.get("DATA_DIR", "/data")
    return Path(path)


class LocalVolume:
    """Volume-like interface using local/EFS path."""

    def __init__(self, base: str | Path | None = None):
        self._base = Path(base) if base else _data_dir()

    def _path(self, key: str) -> Path:
        return self._base / key.lstrip("/").replace("/", os.sep)

    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def open(self, key: str, mode: str = "r", **kwargs):
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        return open(p, mode, **kwargs)


api_data_volume = LocalVolume()
