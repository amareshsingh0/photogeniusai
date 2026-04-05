"""
Auth helpers — Dev Mode (Clerk removed Apr 1 2026).

All endpoints that use CurrentUserId / require_auth get a hardcoded dev user ID.
Production auth will be added as a custom system later.
"""
from typing import Optional

from fastapi import HTTPException, status

# Fixed dev user — matches the DEV_USER in apps/web/lib/auth.ts
_DEV_USER_ID = "dev_user_123"


async def get_current_user_id() -> Optional[str]:
    """Always returns the dev user ID. Replace with real auth when ready."""
    return _DEV_USER_ID


async def get_optional_user() -> Optional[str]:
    """Optional auth — returns dev user ID in dev mode."""
    return _DEV_USER_ID


async def get_current_user() -> str:
    """Require auth — returns dev user ID in dev mode."""
    return _DEV_USER_ID


def require_auth(user_id: Optional[str]) -> str:
    """
    Require authentication — raises 401 if user_id is None.
    In dev mode this never raises since get_current_user_id always returns a value.
    """
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return user_id


# Dependency alias
RequireAuth = get_current_user
