"""
Publish Scheduler — APScheduler cron every 60s

Queries BatchTask WHERE scheduledFor <= now() AND status='ready' AND platform IS NOT NULL
For each: calls Instagram or LinkedIn publisher using tokens from User.preferences.integrations

Lifecycle:
  start_scheduler() → called once at app startup (lifespan event)
  stop_scheduler()  → called at app shutdown
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_scheduler = None


async def _publish_due_tasks() -> None:
    """Find and publish all tasks that are due."""
    try:
        from app.core.db import get_db
        from app.services.publishers.instagram_publisher import InstagramPublisher
        from app.services.publishers.linkedin_publisher import LinkedInPublisher
    except ImportError as e:
        logger.warning("[scheduler] import error: %s", e)
        return

    now = datetime.now(timezone.utc)

    try:
        async with get_db() as db:
            due_tasks = await db.batchtask.find_many(
                where={
                    "status":       "ready",
                    "scheduledFor": {"lte": now},
                    "platform":     {"not": None},
                    "publishedAt":  None,
                },
                include={"batchJob": {"include": {"user": True}}},
                take=20,  # max 20 per tick
            )
    except Exception as e:
        logger.error("[scheduler] DB query failed: %s", e)
        return

    if not due_tasks:
        return

    logger.info("[scheduler] %d tasks due for publishing", len(due_tasks))

    for task in due_tasks:
        await _publish_one(task)


async def _publish_one(task) -> None:
    """Attempt to publish a single BatchTask."""
    try:
        from app.core.db import get_db
    except ImportError:
        return

    if not task.imageUrl:
        logger.warning("[scheduler] task %s has no imageUrl, skipping", task.id)
        return

    # Get user integrations from preferences
    try:
        from app.core.db import get_db
        async with get_db() as db:
            user = await db.user.find_first(where={"id": task.batchJob.userId})
            if not user:
                return
            prefs       = user.preferences or {}
            integrations = prefs.get("integrations", {})
    except Exception as e:
        logger.error("[scheduler] failed to load user prefs for task %s: %s", task.id, e)
        return

    platform = (task.platform or "").lower()
    caption  = task.prompt[:2200] if task.prompt else ""

    result: dict = {"success": False, "error": "Unknown platform"}

    try:
        if platform == "instagram":
            ig_creds = integrations.get("instagram", {})
            if not ig_creds.get("access_token"):
                result = {"success": False, "error": "Instagram not connected"}
            else:
                pub = InstagramPublisher(ig_creds["access_token"], ig_creds.get("user_id", ""))
                from app.services.publishers.instagram_publisher import InstagramPublisher
                result = await pub.post_image(task.imageUrl, caption)

        elif platform == "linkedin":
            li_creds = integrations.get("linkedin", {})
            if not li_creds.get("access_token"):
                result = {"success": False, "error": "LinkedIn not connected"}
            else:
                from app.services.publishers.linkedin_publisher import LinkedInPublisher
                pub = LinkedInPublisher(li_creds["access_token"], li_creds.get("person_urn", ""))
                result = await pub.post_image(task.imageUrl, caption)

    except Exception as e:
        logger.error("[scheduler] publish error task %s platform %s: %s", task.id, platform, e)
        result = {"success": False, "error": str(e)}

    # Update task status in DB
    try:
        from app.core.db import get_db
        async with get_db() as db:
            if result.get("success"):
                await db.batchtask.update(
                    where={"id": task.id},
                    data={
                        "status":      "published",
                        "publishedAt": datetime.now(timezone.utc),
                    },
                )
                logger.info("[scheduler] task %s published on %s", task.id, platform)
            else:
                await db.batchtask.update(
                    where={"id": task.id},
                    data={"error": result.get("error", "Unknown error")},
                )
                logger.warning("[scheduler] task %s publish failed: %s", task.id, result.get("error"))
    except Exception as e:
        logger.error("[scheduler] DB update failed for task %s: %s", task.id, e)


def start_scheduler() -> None:
    """Start APScheduler background job. Call once at app startup."""
    global _scheduler
    if _scheduler is not None:
        return

    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
    except ImportError:
        logger.warning(
            "[scheduler] apscheduler not installed — auto-publishing disabled. "
            "Run: pip install apscheduler"
        )
        return

    _scheduler = AsyncIOScheduler(timezone="UTC")
    _scheduler.add_job(
        _publish_due_tasks,
        trigger="interval",
        seconds=60,
        id="publish_due_tasks",
        replace_existing=True,
        max_instances=1,  # never overlap
    )
    _scheduler.start()
    logger.info("[scheduler] started — polling every 60s for due publish tasks")


def stop_scheduler() -> None:
    """Shutdown APScheduler. Call at app shutdown."""
    global _scheduler
    if _scheduler is not None:
        try:
            _scheduler.shutdown(wait=False)
        except Exception:
            pass
        _scheduler = None
        logger.info("[scheduler] stopped")
