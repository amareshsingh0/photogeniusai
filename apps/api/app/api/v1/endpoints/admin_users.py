"""
Admin users management endpoint
GET /api/admin/users - List all users with pagination
PATCH /api/admin/users - Update user
DELETE /api/admin/users - Delete user
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List, Dict, Any
import logging

# Lazy prisma import — missing prisma client should not crash API startup.
# Routes that need it will raise 500 with a clear message instead.
try:
    from prisma import Prisma  # type: ignore
    _PRISMA_AVAILABLE = True
except ImportError:
    Prisma = None  # type: ignore
    _PRISMA_AVAILABLE = False

router = APIRouter()
logger = logging.getLogger(__name__)


def _require_prisma() -> None:
    if not _PRISMA_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Prisma Python client not installed. Run: pip install prisma && prisma generate",
        )

# Models
class UserResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    email: str
    name: str
    role: str
    credits: int
    createdAt: str
    count: Dict[str, Any] = Field(serialization_alias="_count")

class PaginationResponse(BaseModel):
    page: int
    limit: int
    total: int
    totalPages: int

class UsersListResponse(BaseModel):
    users: List[UserResponse]
    pagination: PaginationResponse

class UpdateUserRequest(BaseModel):
    userId: str
    updates: dict

@router.get("/admin/users", response_model=UsersListResponse)
async def get_users(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    search: Optional[str] = Query(None)
):
    """Get all users with pagination and search"""
    _require_prisma()
    try:
        prisma = Prisma()
        await prisma.connect()

        skip = (page - 1) * limit

        # Build where clause for search
        where = {}
        if search:
            where = {
                "OR": [
                    {"email": {"contains": search, "mode": "insensitive"}},
                    {"name": {"contains": search, "mode": "insensitive"}},
                ]
            }

        # Fetch users and total count
        users = await prisma.user.find_many(
            where=where,
            skip=skip,
            take=limit,
            order={"createdAt": "desc"}
        )

        total = await prisma.user.count(where=where)

        # Get generation counts for each user
        users_data = []
        for user in users:
            # Count generations for this user
            gen_count = await prisma.generation.count(where={"userId": user.id})

            users_data.append({
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "role": user.role,
                "credits": user.creditsBalance,
                "createdAt": user.createdAt.isoformat(),
                "count": {"generations": gen_count}
            })

        await prisma.disconnect()

        return {
            "users": users_data,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "totalPages": (total + limit - 1) // limit
            }
        }

    except Exception as e:
        logger.error(f"[admin/users] GET error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/admin/users")
async def update_user(body: UpdateUserRequest):
    """Update user"""
    _require_prisma()
    try:
        prisma = Prisma()
        await prisma.connect()

        # Allowed update fields
        allowed_fields = ["name", "email", "role", "creditsBalance"]
        update_data = {k: v for k, v in body.updates.items() if k in allowed_fields}

        if not update_data:
            raise HTTPException(status_code=400, detail="No valid update fields provided")

        # Update user
        user = await prisma.user.update(
            where={"id": body.userId},
            data=update_data
        )

        await prisma.disconnect()

        return {
            "user": {
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "role": user.role,
                "credits": user.creditsBalance,
                "updatedAt": user.updatedAt.isoformat()
            }
        }

    except Exception as e:
        logger.error(f"[admin/users] PATCH error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/admin/users")
async def delete_user(userId: str = Query(...)):
    """Delete user"""
    _require_prisma()
    try:
        prisma = Prisma()
        await prisma.connect()

        # Delete user
        await prisma.user.delete(where={"id": userId})

        await prisma.disconnect()

        return {"success": True}

    except Exception as e:
        logger.error(f"[admin/users] DELETE error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
