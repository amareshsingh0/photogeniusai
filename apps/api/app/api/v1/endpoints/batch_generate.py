"""
Batch Generation API

POST /api/v1/batch/start   — create a BatchJob with N tasks, queue them
GET  /api/v1/batch/{job_id} — poll job status + per-task progress
DELETE /api/v1/batch/{job_id} — cancel a running job
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from app.core.dependencies import CurrentUserId, DbSession
from app.core.security import require_auth

logger = logging.getLogger(__name__)
router = APIRouter()

# ── In-memory job registry (replaces DB for active jobs — DB is ground truth) ──
_active_jobs: Dict[str, asyncio.Task] = {}
_job_semaphore = asyncio.Semaphore(3)  # max 3 concurrent generations


# ── Request / Response models ──────────────────────────────────────────────────

class BatchTask(BaseModel):
    prompt:        str
    quality:       str           = Field(default="balanced", pattern="^(fast|balanced|quality|ultra)$")
    platform:      str           = Field(default="instagram")
    width:         int           = Field(default=1024, ge=512, le=2048)
    height:        int           = Field(default=1024, ge=512, le=2048)
    scheduled_for: Optional[str] = Field(default=None, description="ISO datetime for scheduled publish")
    caption:       Optional[str] = None
    metadata:      Optional[Dict[str, Any]] = None


class BatchStartRequest(BaseModel):
    name:  str             = Field(default="Batch Job", max_length=120)
    tasks: List[BatchTask] = Field(..., min_length=1, max_length=50)


class BatchTaskStatus(BaseModel):
    id:         str
    prompt:     str
    status:     str   # pending | running | done | failed
    image_url:  Optional[str] = None
    error:      Optional[str] = None
    platform:   str   = "instagram"
    caption:    Optional[str] = None


class BatchJobStatus(BaseModel):
    job_id:      str
    name:        str
    status:      str   # pending | running | done | cancelled | failed
    total:       int
    done:        int
    failed:      int
    pending:     int
    tasks:       List[BatchTaskStatus] = []
    created_at:  str
    updated_at:  str


class BatchStartResponse(BaseModel):
    success: bool = True
    job_id:  str
    total:   int


# ── Worker ─────────────────────────────────────────────────────────────────────

async def _run_single_task(task_id: str, prompt: str, quality: str, db) -> str:
    """Run one generation task and return the image URL. Raises on failure."""
    from app.services.smart.generation_router import SmartGenerationRouter
    router_svc = SmartGenerationRouter()
    result = await router_svc.generate(
        prompt=prompt,
        quality=quality,
        user_id="batch",
    )
    if not result.get("success"):
        raise RuntimeError(result.get("error", "Generation failed"))
    return result.get("image_url") or result.get("preview_url") or ""


async def _batch_worker(job_id: str, task_ids: List[str], tasks_data: List[dict], db_factory):
    """Background worker — processes tasks with semaphore-limited concurrency."""
    async def process_one(task_id: str, task_data: dict):
        async with _job_semaphore:
            try:
                async with db_factory() as db:
                    await db.batchtask.update(
                        where={"id": task_id},
                        data={"status": "running"},
                    )
                image_url = await _run_single_task(
                    task_id, task_data["prompt"], task_data["quality"], None
                )
                async with db_factory() as db:
                    await db.batchtask.update(
                        where={"id": task_id},
                        data={"status": "done", "imageUrl": image_url},
                    )
                    await db.batchjob.update(
                        where={"id": job_id},
                        data={"doneTasks": {"increment": 1}},
                    )
            except Exception as exc:
                logger.warning("batch task %s failed: %s", task_id, exc)
                async with db_factory() as db:
                    await db.batchtask.update(
                        where={"id": task_id},
                        data={"status": "failed", "error": str(exc)[:500]},
                    )
                    await db.batchjob.update(
                        where={"id": job_id},
                        data={"failedTasks": {"increment": 1}},
                    )

    await asyncio.gather(*[process_one(tid, td) for tid, td in zip(task_ids, tasks_data)])

    # Mark job done
    async with db_factory() as db:
        await db.batchjob.update(
            where={"id": job_id},
            data={"status": "done"},
        )
    _active_jobs.pop(job_id, None)
    logger.info("BatchJob %s completed", job_id)


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post(
    "/start",
    response_model=BatchStartResponse,
    summary="Start a batch generation job",
)
async def start_batch(
    req: BatchStartRequest,
    background_tasks: BackgroundTasks,
    user_id: CurrentUserId,
    db: DbSession,
) -> BatchStartResponse:
    require_auth(user_id)

    job_id = str(uuid.uuid4())
    now    = datetime.now(timezone.utc).isoformat()

    # Create BatchJob in DB
    try:
        await db.batchjob.create(data={
            "id":          job_id,
            "userId":      user_id,
            "name":        req.name,
            "status":      "running",
            "totalTasks":  len(req.tasks),
            "doneTasks":   0,
            "failedTasks": 0,
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create job: {e}")

    # Create BatchTask records
    task_ids: List[str] = []
    tasks_data: List[dict] = []
    for t in req.tasks:
        tid = str(uuid.uuid4())
        task_ids.append(tid)
        tasks_data.append(t.model_dump())
        try:
            await db.batchtask.create(data={
                "id":           tid,
                "batchJobId":   job_id,
                "prompt":       t.prompt,
                "quality":      t.quality,
                "width":        t.width,
                "height":       t.height,
                "platform":     t.platform,
                "caption":      t.caption or "",
                "status":       "pending",
                "scheduledFor": t.scheduled_for,
                "metadata":     t.metadata or {},
            })
        except Exception as e:
            logger.warning("Failed to create batch task: %s", e)

    # Launch background worker
    from app.core.database import get_db_context
    bg_task = asyncio.create_task(
        _batch_worker(job_id, task_ids, tasks_data, get_db_context)
    )
    _active_jobs[job_id] = bg_task

    return BatchStartResponse(success=True, job_id=job_id, total=len(req.tasks))


@router.get(
    "/{job_id}",
    response_model=BatchJobStatus,
    summary="Poll batch job status",
)
async def get_batch_status(
    job_id: str,
    user_id: CurrentUserId,
    db: DbSession,
) -> BatchJobStatus:
    require_auth(user_id)

    job = await db.batchjob.find_first(
        where={"id": job_id, "userId": user_id},
        include={"tasks": True},
    )
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    tasks_out = [
        BatchTaskStatus(
            id=t.id,
            prompt=t.prompt,
            status=t.status,
            image_url=getattr(t, "imageUrl", None),
            error=t.error,
            platform=t.platform,
            caption=t.caption,
        )
        for t in (job.tasks or [])
    ]

    pending_count = sum(1 for t in tasks_out if t.status == "pending")

    return BatchJobStatus(
        job_id=job.id,
        name=job.name,
        status=job.status,
        total=job.totalTasks,
        done=job.doneTasks,
        failed=job.failedTasks,
        pending=pending_count,
        tasks=tasks_out,
        created_at=job.createdAt.isoformat() if hasattr(job, "createdAt") else "",
        updated_at=job.updatedAt.isoformat() if hasattr(job, "updatedAt") else "",
    )


@router.delete(
    "/{job_id}",
    summary="Cancel a running batch job",
)
async def cancel_batch(
    job_id: str,
    user_id: CurrentUserId,
    db: DbSession,
):
    require_auth(user_id)

    job = await db.batchjob.find_first(where={"id": job_id, "userId": user_id})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Cancel asyncio task if running
    task = _active_jobs.pop(job_id, None)
    if task and not task.done():
        task.cancel()

    await db.batchjob.update(where={"id": job_id}, data={"status": "cancelled"})
    return {"success": True, "job_id": job_id, "status": "cancelled"}
