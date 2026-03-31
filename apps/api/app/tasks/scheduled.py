"""
Scheduled Tasks - Background jobs for PhotoGenius AI

Features:
- Daily cleanup of old generations (3 AM)
- Auto-delete generations older than 15 days
- Preserve favorites
- S3 image cleanup
"""

import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.database import get_db
from app.services.gallery import GalleryCleanupService

logger = logging.getLogger(__name__)

# Initialize cleanup service
cleanup_service = GalleryCleanupService(delete_after_days=15)

# Initialize scheduler
scheduler = AsyncIOScheduler()


async def run_daily_cleanup():
    """
    Daily cleanup job - runs at 3 AM

    Process:
    1. Delete generations older than 15 days
    2. Preserve favorites
    3. Delete images from S3
    4. Log statistics
    """
    logger.info("Starting daily cleanup job...")

    try:
        # Get database session
        async for db in get_db():
            # Run cleanup
            result = await cleanup_service.cleanup_old_generations(db)

            # Log results
            logger.info(f"Daily cleanup completed:")
            logger.info(f"  - Deleted: {result.get('deleted_count', 0)} generations")
            logger.info(f"  - Freed: {result.get('freed_storage_mb', 0):.2f} MB")
            logger.info(f"  - Protected favorites: {result.get('protected_count', 0)}")
            logger.info(f"  - Cutoff date: {result.get('cutoff_date', 'N/A')}")

            break  # Only need one iteration

    except Exception as e:
        logger.error(f"Daily cleanup failed: {e}")
        raise


async def run_weekly_stats():
    """
    Weekly statistics job - runs every Sunday at 2 AM

    Logs storage statistics for monitoring
    """
    logger.info("Generating weekly storage statistics...")

    try:
        async for db in get_db():
            stats = await cleanup_service.get_storage_stats(db)

            logger.info(f"Weekly stats:")
            logger.info(f"  - Total generations: {stats.get('total_generations', 0)}")
            logger.info(f"  - Eligible for deletion: {stats.get('eligible_for_deletion', 0)}")
            logger.info(f"  - Protected favorites: {stats.get('protected_favorites', 0)}")
            logger.info(f"  - Total size: {stats.get('total_size_mb', 0):.2f} MB")

            break

    except Exception as e:
        logger.error(f"Weekly stats generation failed: {e}")


def start_scheduler():
    """
    Start the scheduled task system

    Jobs:
    - Daily cleanup at 3 AM (delete old generations)
    - Weekly stats at 2 AM on Sundays
    """

    # Daily cleanup at 3 AM
    scheduler.add_job(
        run_daily_cleanup,
        CronTrigger(hour=3, minute=0),  # 3:00 AM daily
        id='daily_cleanup',
        name='Daily Gallery Cleanup',
        replace_existing=True
    )
    logger.info("Scheduled: Daily cleanup at 3:00 AM")

    # Weekly stats on Sundays at 2 AM
    scheduler.add_job(
        run_weekly_stats,
        CronTrigger(day_of_week='sun', hour=2, minute=0),  # Sunday 2:00 AM
        id='weekly_stats',
        name='Weekly Storage Stats',
        replace_existing=True
    )
    logger.info("Scheduled: Weekly stats on Sundays at 2:00 AM")

    # Start scheduler
    scheduler.start()
    logger.info("Scheduler started successfully")


def stop_scheduler():
    """Stop the scheduled task system"""
    scheduler.shutdown()
    logger.info("Scheduler stopped")


# Manual trigger for testing
async def trigger_cleanup_now():
    """
    Manually trigger cleanup (for testing or admin use)

    Returns:
        dict: Cleanup results
    """
    logger.info("Manual cleanup triggered")

    async for db in get_db():
        result = await cleanup_service.cleanup_old_generations(db)
        return result
