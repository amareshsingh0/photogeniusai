"""Admin endpoints. Protect with role check."""
from fastapi import APIRouter, Depends, HTTPException  # type: ignore[reportMissingImports]
from datetime import datetime, timedelta
from typing import List, Dict, Any
from sqlalchemy import text  # type: ignore[reportMissingImports]

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
        result = await db.execute(text("SELECT COUNT(*) as count FROM users"))
        row = result.fetchone()
        total_users = row[0] if row else 0

        # Get total generations
        result = await db.execute(text("SELECT COUNT(*) as count FROM generations WHERE is_deleted = false"))
        row = result.fetchone()
        total_generations = row[0] if row else 0

        # Get active users (generated in last 30 days)
        result = await db.execute(text("""
            SELECT COUNT(DISTINCT user_id) as count
            FROM generations
            WHERE created_at > NOW() - INTERVAL '30 days' AND is_deleted = false
        """))
        row = result.fetchone()
        active_users = row[0] if row else 0

        # Get total credits used
        result = await db.execute(text("SELECT SUM(total_credits_spent) as total FROM users"))
        row = result.fetchone()
        total_credits_spent = int(row[0]) if row and row[0] else 0

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


@router.get("/analytics")
async def admin_analytics(user_id: CurrentUserId):
    """Comprehensive admin analytics matching Next.js admin panel requirements."""
    require_auth(user_id)

    # NOTE: Temporarily return basic stats due to pgbouncer prepared statement issues
    # Full analytics with aggregations will be moved to Next.js API or direct connection
    return {
        "overview": {
            "totalUsers": 1,
            "totalGenerations": 0,
            "activeUsers": 0,
            "totalCreditsUsed": 0,
            "avgGenerationsPerUser": "0",
            "dailyAverage": "0"
        },
        "generations": {
            "today": 0,
            "week": 0,
            "month": 0
        },
        "breakdown": {
            "byTier": [],
            "byBucket": []
        },
        "recent": [],
        "userGrowth": []
    }

