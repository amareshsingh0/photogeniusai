"""Pytest fixtures. Async client for FastAPI."""

from typing import AsyncGenerator

import pytest_asyncio  # type: ignore[reportMissingImports]
from httpx import ASGITransport, AsyncClient  # type: ignore[reportMissingImports]

from app.main import app


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        yield c
