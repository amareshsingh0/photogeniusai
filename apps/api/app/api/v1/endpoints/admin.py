"""Admin endpoints. Protect with role check."""
from fastapi import APIRouter, Depends, HTTPException  # type: ignore[reportMissingImports]

from app.core.dependencies import CurrentUserId
from app.core.security import require_auth
from app.core.database import get_db

router = APIRouter()


@router.get("/stats")
async def admin_stats(user_id: CurrentUserId, db = Depends(get_db)):
    """Admin dashboard stats with real data from database."""
    require_auth(user_id)

    try:
        # Get total users
        users_count = await db.execute_query_one("SELECT COUNT(*) as count FROM users")
        total_users = users_count['count'] if users_count else 0

        # Get total generations
        gen_count = await db.execute_query_one("SELECT COUNT(*) as count FROM generations WHERE is_deleted = false")
        total_generations = gen_count['count'] if gen_count else 0

        # Get active users (generated in last 30 days)
        active_count = await db.execute_query_one("""
            SELECT COUNT(DISTINCT user_id) as count
            FROM generations
            WHERE created_at > NOW() - INTERVAL '30 days' AND is_deleted = false
        """)
        active_users = active_count['count'] if active_count else 0

        # Get total credits used
        credits_count = await db.execute_query_one("SELECT SUM(total_credits_spent) as total FROM users")
        total_credits_spent = int(credits_count['total']) if credits_count and credits_count['total'] else 0

        return {
            "users": total_users,
            "generations": total_generations,
            "active_users_30d": active_users,
            "total_credits_spent": total_credits_spent
        }
    except Exception as e:
        # Fallback to dummy data if DB query fails
        return {
            "users": 0,
            "generations": 0,
            "active_users_30d": 0,
            "total_credits_spent": 0,
            "error": str(e)
        }
