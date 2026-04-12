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

    # Original code with db queries - disabled due to pgbouncer issues
    """
    try:
        # Calculate date ranges
        now = datetime.utcnow()
        today = datetime(now.year, now.month, now.day)
        this_week = now - timedelta(days=7)
        this_month = datetime(now.year, now.month, 1)

        # Total users
        result = await db.execute(text("SELECT COUNT(*) as count FROM users"))
        row = result.fetchone()
        total_users = row[0] if row else 0

        # Total generations
        result = await db.execute(text("SELECT COUNT(*) as count FROM generations WHERE is_deleted = false"))
        row = result.fetchone()
        total_generations = row[0] if row else 0

        # Today's generations
        result = await db.execute(
            text("SELECT COUNT(*) as count FROM generations WHERE created_at >= :today AND is_deleted = false"),
            {"today": today}
        )
        row = result.fetchone()
        today_generations = row[0] if row else 0

        # This week's generations
        result = await db.execute(
            text("SELECT COUNT(*) as count FROM generations WHERE created_at >= :week AND is_deleted = false"),
            {"week": this_week}
        )
        row = result.fetchone()
        week_generations = row[0] if row else 0

        # This month's generations
        result = await db.execute(
            text("SELECT COUNT(*) as count FROM generations WHERE created_at >= :month AND is_deleted = false"),
            {"month": this_month}
        )
        row = result.fetchone()
        month_generations = row[0] if row else 0

        # Active users (generated in last 7 days)
        result = await db.execute(
            text("""
                SELECT COUNT(DISTINCT user_id) as count
                FROM generations
                WHERE created_at >= :week AND is_deleted = false
            """),
            {"week": this_week}
        )
        row = result.fetchone()
        active_users = row[0] if row else 0

        # Total credits used (from generations)
        result = await db.execute(text("SELECT SUM(credits) as total FROM generations WHERE is_deleted = false"))
        row = result.fetchone()
        total_credits_used = int(row[0]) if row and row[0] else 0

        # Generations by tier (quality)
        result = await db.execute(text("""
            SELECT quality as tier, COUNT(*) as count
            FROM generations
            WHERE is_deleted = false AND quality IS NOT NULL
            GROUP BY quality
            ORDER BY count DESC
        """))
        by_tier = [{"tier": row[0], "count": row[1]} for row in result.fetchall()]

        # Generations by bucket
        result = await db.execute(text("""
            SELECT bucket, COUNT(*) as count
            FROM generations
            WHERE is_deleted = false AND bucket IS NOT NULL
            GROUP BY bucket
            ORDER BY count DESC
        """))
        by_bucket = [{"bucket": row[0], "count": row[1]} for row in result.fetchall()]

        # Recent generations (last 10)
        result = await db.execute(text("""
            SELECT
                g.id,
                g.prompt,
                g.quality,
                g.bucket,
                g.created_at,
                u.email as user_email,
                u.name as user_name
            FROM generations g
            LEFT JOIN users u ON g.user_id = u.id
            WHERE g.is_deleted = false
            ORDER BY g.created_at DESC
            LIMIT 10
        """))

        recent = []
        for row in result.fetchall():
            recent.append({
                "id": str(row[0]),
                "prompt": row[1],
                "quality": row[2],
                "bucket": row[3],
                "createdAt": row[4].isoformat() if row[4] else None,
                "user": {
                    "email": row[5],
                    "name": row[6]
                }
            })

        # User growth (last 30 days)
        result = await db.execute(text("""
            SELECT DATE(created_at) as date, COUNT(*) as count
            FROM users
            WHERE created_at >= NOW() - INTERVAL '30 days'
            GROUP BY DATE(created_at)
            ORDER BY date DESC
        """))

        user_growth = []
        for row in result.fetchall():
            user_growth.append({
                "date": row[0].isoformat() if row[0] else None,
                "count": row[1]
            })

        # Calculate averages
        avg_generations_per_user = round(total_generations / total_users, 2) if total_users > 0 else 0
        daily_average = round(week_generations / 7, 2)

        return {
            "overview": {
                "totalUsers": total_users,
                "totalGenerations": total_generations,
                "activeUsers": active_users,
                "totalCreditsUsed": total_credits_used,
                "avgGenerationsPerUser": str(avg_generations_per_user),
                "dailyAverage": str(daily_average)
            },
            "generations": {
                "today": today_generations,
                "week": week_generations,
                "month": month_generations
            },
            "breakdown": {
                "byTier": by_tier,
                "byBucket": by_bucket
            },
            "recent": recent,
            "userGrowth": user_growth
        }

    except Exception as e:
        print(f"[admin/analytics] Error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch analytics: {str(e)}")
    """
