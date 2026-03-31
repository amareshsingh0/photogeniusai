"""
Pytest configuration for ai-pipeline tests.

Enables pytest-asyncio for async tests when available.
Add to pytest.ini or pyproject.toml: asyncio_mode = auto
"""

import sys
from pathlib import Path

# Ensure ai-pipeline root is on path
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

try:
    import pytest_asyncio  # type: ignore[reportMissingImports]
    pytest_plugins = ("pytest_asyncio",)
except ImportError:
    pytest_asyncio = None
    pytest_plugins = ()
