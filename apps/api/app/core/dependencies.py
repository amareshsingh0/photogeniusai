"""
FastAPI dependencies: DB session (no-op stub), auth.

The Python API does not run its own Prisma client — the Next.js layer owns the DB.
Endpoints that need DB access should call the Next.js API routes or use the
no-op stub below which silently swallows all calls.
"""
from typing import Annotated, Any, Optional

from fastapi import Depends

from app.core.security import get_current_user_id


# ── No-op Prisma-style DB stub ────────────────────────────────────────────────

class _NoOpQuery:
    """Silently no-ops every Prisma-style method call."""
    async def find_first(self, **_): return None
    async def find_many(self, **_): return []
    async def create(self, **_): return None
    async def update(self, **_): return None
    async def update_many(self, **_): return type("R", (), {"count": 0})()
    async def delete(self, **_): return None
    async def delete_many(self, **_): return None
    async def upsert(self, **_): return None
    async def count(self, **_): return 0
    def __getattr__(self, _): return _NoOpQuery()


class _NoOpDb:
    """No-op Prisma-like db object. All table accessors return _NoOpQuery."""
    def __getattr__(self, _): return _NoOpQuery()


_noop_db = _NoOpDb()


async def _get_db():
    yield _noop_db


DbSession     = Annotated[Any, Depends(_get_db)]
CurrentUserId = Annotated[Optional[str], Depends(get_current_user_id)]
