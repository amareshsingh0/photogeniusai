"""
Admin Model Registry API - Control which models are active for generation

Allows admins to:
1. View all available models with stats
2. Activate/deactivate models for production
3. Enable/disable models for parallel testing
4. View model performance metrics (avg rating, cost, latency)
"""
import logging
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(tags=["admin"])


# ── Pydantic Models ──────────────────────────────────────────────────────────

class ModelConfigResponse(BaseModel):
    """Model configuration with performance stats."""
    id: str
    modelId: str
    provider: str
    displayName: str
    buckets: List[str]
    isActive: bool
    isTestingEnabled: bool
    totalGenerations: int
    avgRating: Optional[float]
    avgCost: Optional[float]
    avgLatency: Optional[float]
    costPerImage: float
    createdAt: datetime
    updatedAt: datetime


class ModelConfigUpdate(BaseModel):
    """Update model configuration."""
    modelId: str
    isActive: Optional[bool] = None
    isTestingEnabled: Optional[bool] = None
    buckets: Optional[List[str]] = None


class BulkModelUpdate(BaseModel):
    """Update multiple models at once."""
    updates: List[ModelConfigUpdate]


# ── Default Model Registry ───────────────────────────────────────────────────
# These are seeded into database if not exists

DEFAULT_MODELS = [
    {
        "modelId": "flux_2_pro",
        "provider": "wavespeed",
        "displayName": "Flux 2 Pro",
        "buckets": ["typography", "photorealism", "artistic", "humans"],
        "costPerImage": 0.025,
        "isActive": False,  # WaveSpeed integration pending
        "isTestingEnabled": True,
    },
    {
        "modelId": "flux_2_max",
        "provider": "wavespeed",
        "displayName": "Flux 2 Max",
        "buckets": ["photorealism", "artistic", "humans"],
        "costPerImage": 0.055,
        "isActive": False,  # WaveSpeed integration pending
        "isTestingEnabled": True,
    },
    {
        "modelId": "flux_schnell",
        "provider": "fal.ai",
        "displayName": "Flux Schnell",
        "buckets": ["fast", "photorealism"],
        "costPerImage": 0.003,
        "isActive": True,
        "isTestingEnabled": True,
    },
    {
        "modelId": "flux_dev",
        "provider": "fal.ai",
        "displayName": "Flux Dev",
        "buckets": ["photorealism", "artistic"],
        "costPerImage": 0.015,
        "isActive": True,
        "isTestingEnabled": True,
    },
    {
        "modelId": "ideogram_v3",
        "provider": "fal.ai",
        "displayName": "Ideogram v3 Quality",
        "buckets": ["typography"],
        "costPerImage": 0.09,
        "isActive": True,
        "isTestingEnabled": True,
    },
    {
        "modelId": "recraft_v4_svg",
        "provider": "fal.ai",
        "displayName": "Recraft v4 SVG",
        "buckets": ["vector", "typography"],
        "costPerImage": 0.04,
        "isActive": True,
        "isTestingEnabled": True,
    },
    {
        "modelId": "hunyuan_image",
        "provider": "wavespeed",
        "displayName": "Hunyuan Image",
        "buckets": ["anime", "typography"],
        "costPerImage": 0.04,
        "isActive": False,  # WaveSpeed integration pending
        "isTestingEnabled": True,
    },
    {
        "modelId": "seedream_4_5",
        "provider": "fal.ai",
        "displayName": "Seedream 4.5",
        "buckets": ["character_consistency", "photorealism", "typography", "multi_reference", "humans"],
        "costPerImage": 0.06,
        "isActive": True,
        "isTestingEnabled": True,
    },
    {
        "modelId": "grok_2_imagine",
        "provider": "wavespeed",
        "displayName": "Grok 2 Imagine",
        "buckets": ["photorealism", "artistic", "typography", "humans", "multi_person"],
        "costPerImage": 0.05,
        "isActive": False,  # Not integrated yet
        "isTestingEnabled": True,
    },
    {
        "modelId": "imagen_4_ultra",
        "provider": "vertex",
        "displayName": "Imagen 4 Ultra",
        "buckets": ["photorealism", "typography", "humans", "image_to_image"],
        "costPerImage": 0.18,
        "isActive": False,  # Not integrated yet
        "isTestingEnabled": True,
    },
    {
        "modelId": "flux_2_flex",
        "provider": "wavespeed",
        "displayName": "Flux 2 Flex",
        "buckets": ["photorealism", "artistic", "typography"],
        "costPerImage": 0.04,
        "isActive": False,  # WaveSpeed integration pending
        "isTestingEnabled": True,
    },
    {
        "modelId": "wan_2_7",
        "provider": "wavespeed",
        "displayName": "Wan 2.7",
        "buckets": ["photorealism", "artistic", "typography"],
        "costPerImage": 0.05,
        "isActive": False,  # Not integrated yet
        "isTestingEnabled": True,
    },
    {
        "modelId": "imagen_4_standard",
        "provider": "vertex",
        "displayName": "Imagen 4 Standard",
        "buckets": ["photorealism", "typography", "humans"],
        "costPerImage": 0.08,
        "isActive": False,  # Not integrated yet
        "isTestingEnabled": True,
    },
    {
        "modelId": "imagen_3",
        "provider": "vertex",
        "displayName": "Imagen 3",
        "buckets": ["photorealism", "typography"],
        "costPerImage": 0.04,
        "isActive": False,  # Not integrated yet
        "isTestingEnabled": True,
    },
    {
        "modelId": "gemini_flash_image",
        "provider": "vertex",
        "displayName": "Gemini 3.1 Flash Image (Nano Banana 2)",
        "buckets": ["photorealism", "artistic", "typography", "image_to_image"],
        "costPerImage": 0.01,
        "isActive": False,  # Not integrated yet
        "isTestingEnabled": True,
    },
]


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/admin/models/seed")
async def seed_models():
    """
    Seed default models into database (run once on first setup).
    Safe to call multiple times - only creates missing models.
    """
    try:
        from prisma import Prisma
        prisma = Prisma()
        await prisma.connect()

        created_count = 0
        for model_data in DEFAULT_MODELS:
            # Check if model already exists
            existing = await prisma.modelconfig.find_unique(
                where={"modelId": model_data["modelId"]}
            )

            if not existing:
                await prisma.modelconfig.create(data=model_data)
                created_count += 1
                logger.info(f"[seed] Created model: {model_data['modelId']}")

        await prisma.disconnect()

        return {
            "success": True,
            "message": f"Seeded {created_count} new models",
            "total_models": len(DEFAULT_MODELS),
        }

    except Exception as e:
        logger.error(f"[seed] Error seeding models: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to seed models: {str(e)}")


@router.get("/admin/models")
async def get_all_models():
    """
    Get all models with their current configuration and stats.

    Returns model configs with performance metrics:
    - totalGenerations (calculated from Generation table)
    - avgRating (from user ratings)
    - avgCost
    - avgLatency
    """
    try:
        from prisma import Prisma
        prisma = Prisma()
        await prisma.connect()

        models = await prisma.modelconfig.find_many(
            order={"displayName": "asc"}
        )

        # Calculate stats for each model from Generation table
        models_data = []
        for m in models:
            # Count generations for this model
            total_gens = await prisma.generation.count(
                where={
                    "modelUsed": m.modelId,
                    "isDeleted": False
                }
            )

            # Get average rating from user ratings (Python Prisma doesn't support select)
            rated_gens = await prisma.generation.find_many(
                where={
                    "modelUsed": m.modelId,
                    "userRating": {"not": None},
                    "isDeleted": False
                }
            )

            avg_rating = None
            avg_cost = None
            avg_latency = None

            if rated_gens:
                # Calculate averages (extract fields after fetch)
                ratings = [g.userRating for g in rated_gens if g.userRating is not None]
                costs = [g.creditsUsed for g in rated_gens if g.creditsUsed is not None]
                latencies = [g.generationTimeSeconds for g in rated_gens if g.generationTimeSeconds is not None]

                avg_rating = sum(ratings) / len(ratings) if ratings else None
                avg_cost = sum(costs) / len(costs) if costs else None
                avg_latency = sum(latencies) / len(latencies) if latencies else None

            models_data.append({
                "id": m.id,
                "modelId": m.modelId,
                "provider": m.provider,
                "displayName": m.displayName,
                "buckets": m.buckets,
                "isActive": m.isActive,
                "isTestingEnabled": m.isTestingEnabled,
                "totalGenerations": total_gens,
                "avgRating": round(avg_rating, 2) if avg_rating else None,
                "avgCost": round(avg_cost, 2) if avg_cost else None,
                "avgLatency": round(avg_latency, 2) if avg_latency else None,
                "costPerImage": m.costPerImage,
                "createdAt": m.createdAt.isoformat() if m.createdAt else None,
                "updatedAt": m.updatedAt.isoformat() if m.updatedAt else None,
            })

        await prisma.disconnect()

        return {"models": models_data}

    except Exception as e:
        logger.error(f"[admin_models] Error fetching models: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch models: {str(e)}")


@router.get("/admin/models/active")
async def get_active_models(bucket: Optional[str] = None):
    """
    Get only active models, optionally filtered by bucket.
    Used by generation endpoint to determine which models to use.

    Args:
        bucket: Filter by capability bucket (typography, photorealism, etc.)
    """
    try:
        from prisma import Prisma
        prisma = Prisma()
        await prisma.connect()

        # Find active models
        models = await prisma.modelconfig.find_many(
            where={"isActive": True},
            order={"displayName": "asc"}
        )

        # Filter by bucket if specified
        if bucket:
            models = [m for m in models if bucket in m.buckets]

        await prisma.disconnect()

        return {
            "models": [
                {
                    "modelId": m.modelId,
                    "provider": m.provider,
                    "displayName": m.displayName,
                    "buckets": m.buckets,
                    "costPerImage": m.costPerImage,
                }
                for m in models
            ],
            "count": len(models),
        }

    except Exception as e:
        logger.error(f"[admin_models] Error fetching active models: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/models/testing")
async def get_testing_models(bucket: Optional[str] = None):
    """
    Get models enabled for parallel testing mode.
    Used when admin enables "Testing Mode" to broadcast to multiple models.
    """
    try:
        from prisma import Prisma
        prisma = Prisma()
        await prisma.connect()

        models = await prisma.modelconfig.find_many(
            where={
                "isActive": True,
                "isTestingEnabled": True,
            },
            order={"displayName": "asc"}
        )

        # Filter by bucket if specified
        if bucket:
            models = [m for m in models if bucket in m.buckets]

        await prisma.disconnect()

        return {
            "models": [m.modelId for m in models],
            "count": len(models),
        }

    except Exception as e:
        logger.error(f"[admin_models] Error fetching testing models: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/admin/models/update")
async def update_model_config(update: ModelConfigUpdate):
    """
    Update a single model's configuration.

    Can update:
    - isActive: Enable/disable for production
    - isTestingEnabled: Include in parallel testing
    - buckets: Which capability buckets this model supports
    """
    try:
        from prisma import Prisma
        prisma = Prisma()
        await prisma.connect()

        # Build update data (only include non-None fields)
        update_data = {}
        if update.isActive is not None:
            update_data["isActive"] = update.isActive
        if update.isTestingEnabled is not None:
            update_data["isTestingEnabled"] = update.isTestingEnabled
        if update.buckets is not None:
            update_data["buckets"] = update.buckets

        if not update_data:
            await prisma.disconnect()
            raise HTTPException(status_code=400, detail="No fields to update")

        # Update model
        model = await prisma.modelconfig.update(
            where={"modelId": update.modelId},
            data=update_data
        )

        await prisma.disconnect()

        logger.info(f"[admin_models] Updated model {update.modelId}: {update_data}")

        return {
            "success": True,
            "message": f"Updated {update.modelId}",
            "model": {
                "modelId": model.modelId,
                "isActive": model.isActive,
                "isTestingEnabled": model.isTestingEnabled,
                "buckets": model.buckets,
            },
        }

    except Exception as e:
        logger.error(f"[admin_models] Error updating model: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/admin/models/bulk-update")
async def bulk_update_models(request: BulkModelUpdate):
    """
    Update multiple models at once.
    Used for batch operations like "Enable all for testing".
    """
    try:
        from prisma import Prisma
        prisma = Prisma()
        await prisma.connect()

        updated_count = 0
        errors = []

        for update in request.updates:
            try:
                update_data = {}
                if update.isActive is not None:
                    update_data["isActive"] = update.isActive
                if update.isTestingEnabled is not None:
                    update_data["isTestingEnabled"] = update.isTestingEnabled
                if update.buckets is not None:
                    update_data["buckets"] = update.buckets

                if update_data:
                    await prisma.modelconfig.update(
                        where={"modelId": update.modelId},
                        data=update_data
                    )
                    updated_count += 1

            except Exception as e:
                errors.append({"modelId": update.modelId, "error": str(e)})

        await prisma.disconnect()

        return {
            "success": True,
            "updated": updated_count,
            "total": len(request.updates),
            "errors": errors if errors else None,
        }

    except Exception as e:
        logger.error(f"[admin_models] Error in bulk update: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/models/{model_id}/ratings")
async def get_model_ratings(model_id: str):
    """
    Get all user ratings and feedback for a specific model.
    Shows rating, reason, prompt, and timestamp for admin analytics.
    """
    try:
        from prisma import Prisma
        prisma = Prisma()
        await prisma.connect()

        # Get all generations with ratings for this model (Python Prisma doesn't support select)
        generations = await prisma.generation.find_many(
            where={
                "modelUsed": model_id,
                "userRating": {"not": None}
            },
            order={"createdAt": "desc"},
            take=100  # Latest 100 ratings
        )

        await prisma.disconnect()

        return {
            "model_id": model_id,
            "total_ratings": len(generations),
            "ratings": [
                {
                    "id": g.id,
                    "rating": g.userRating,
                    "reason": g.userReason,
                    "prompt": g.originalPrompt[:100] + "..." if len(g.originalPrompt) > 100 else g.originalPrompt,
                    "bucket": g.bucket,
                    "generation_time_seconds": g.generationTimeSeconds,
                    "image_url": g.outputUrls[0] if isinstance(g.outputUrls, list) and len(g.outputUrls) > 0 else None,
                    "created_at": g.createdAt.isoformat() if g.createdAt else None,
                }
                for g in generations
            ],
        }

    except Exception as e:
        logger.error(f"[admin_models] Error fetching ratings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
