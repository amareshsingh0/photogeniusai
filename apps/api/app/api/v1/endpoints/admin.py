"""Admin endpoints. Protect with role check."""
from fastapi import APIRouter, Depends, HTTPException  # type: ignore[reportMissingImports]
from datetime import datetime, timedelta
from typing import List, Dict, Any

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


@router.get("/analytics")
async def admin_analytics(user_id: CurrentUserId, db = Depends(get_db)):
    """Comprehensive admin analytics matching Next.js admin panel requirements."""
    require_auth(user_id)

    try:
        # Calculate date ranges
        now = datetime.utcnow()
        today = datetime(now.year, now.month, now.day)
        this_week = now - timedelta(days=7)
        this_month = datetime(now.year, now.month, 1)

        # Total users
        total_users_result = await db.execute_query_one("SELECT COUNT(*) as count FROM users")
        total_users = total_users_result['count'] if total_users_result else 0

        # Total generations
        total_gen_result = await db.execute_query_one(
            "SELECT COUNT(*) as count FROM generations WHERE is_deleted = false"
        )
        total_generations = total_gen_result['count'] if total_gen_result else 0

        # Today's generations
        today_gen_result = await db.execute_query_one(
            "SELECT COUNT(*) as count FROM generations WHERE created_at >= $1 AND is_deleted = false",
            today
        )
        today_generations = today_gen_result['count'] if today_gen_result else 0

        # This week's generations
        week_gen_result = await db.execute_query_one(
            "SELECT COUNT(*) as count FROM generations WHERE created_at >= $1 AND is_deleted = false",
            this_week
        )
        week_generations = week_gen_result['count'] if week_gen_result else 0

        # This month's generations
        month_gen_result = await db.execute_query_one(
            "SELECT COUNT(*) as count FROM generations WHERE created_at >= $1 AND is_deleted = false",
            this_month
        )
        month_generations = month_gen_result['count'] if month_gen_result else 0

        # Active users (generated in last 7 days)
        active_users_result = await db.execute_query_one("""
            SELECT COUNT(DISTINCT user_id) as count
            FROM generations
            WHERE created_at >= $1 AND is_deleted = false
        """, this_week)
        active_users = active_users_result['count'] if active_users_result else 0

        # Total credits used (from generations)
        credits_result = await db.execute_query_one(
            "SELECT SUM(credits) as total FROM generations WHERE is_deleted = false"
        )
        total_credits_used = int(credits_result['total']) if credits_result and credits_result['total'] else 0

        # Generations by tier (quality)
        by_tier_results = await db.execute_query_all("""
            SELECT quality as tier, COUNT(*) as count
            FROM generations
            WHERE is_deleted = false AND quality IS NOT NULL
            GROUP BY quality
            ORDER BY count DESC
        """)
        by_tier = [{"tier": row['tier'], "count": row['count']} for row in by_tier_results] if by_tier_results else []

        # Generations by bucket
        by_bucket_results = await db.execute_query_all("""
            SELECT bucket, COUNT(*) as count
            FROM generations
            WHERE is_deleted = false AND bucket IS NOT NULL
            GROUP BY bucket
            ORDER BY count DESC
        """)
        by_bucket = [{"bucket": row['bucket'], "count": row['count']} for row in by_bucket_results] if by_bucket_results else []

        # Recent generations (last 10)
        recent_results = await db.execute_query_all("""
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
        """)

        recent = []
        if recent_results:
            for row in recent_results:
                recent.append({
                    "id": str(row['id']),
                    "prompt": row['prompt'],
                    "quality": row['quality'],
                    "bucket": row['bucket'],
                    "createdAt": row['created_at'].isoformat() if row['created_at'] else None,
                    "user": {
                        "email": row['user_email'],
                        "name": row['user_name']
                    }
                })

        # User growth (last 30 days)
        growth_results = await db.execute_query_all("""
            SELECT DATE(created_at) as date, COUNT(*) as count
            FROM users
            WHERE created_at >= NOW() - INTERVAL '30 days'
            GROUP BY DATE(created_at)
            ORDER BY date DESC
        """)

        user_growth = []
        if growth_results:
            for row in growth_results:
                user_growth.append({
                    "date": row['date'].isoformat() if row['date'] else None,
                    "count": row['count']
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
