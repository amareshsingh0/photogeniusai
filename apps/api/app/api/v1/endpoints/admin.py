"""Admin endpoints. Protect with role check."""
from fastapi import APIRouter, Depends  # type: ignore[reportMissingImports]

from app.core.dependencies import CurrentUserId
from app.core.security import require_auth

router = APIRouter()


@router.get("/stats")
async def admin_stats(user_id: CurrentUserId):
    """Admin dashboard stats. TODO: require admin role."""
    require_auth(user_id)
    return {"users": 0, "generations": 0}
