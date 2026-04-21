"""
Admin Model Registry API - Control which models are active for generation

Allows admins to:
1. View all available models with stats
2. Activate/deactivate models for production
3. Enable/disable models for parallel testing
4. View model performance metrics (avg rating, cost, latency)
"""
import logging
from typing import Dict, List, Optional
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

LEGACY_MODEL_ALIASES = {
    "imagen_4_standard": "imagen_4_base",
    "gemini_flash_image": "gemini_3_imagen",
}


DEFAULT_MODELS = [
    {
        "modelId": "flux_2_pro",
        "provider": "kie.ai",
        "displayName": "Flux 2 Pro",
        "buckets": ["typography", "photorealism", "artistic", "humans"],
        "costPerImage": 0.025,
        "isActive": True,
        "isTestingEnabled": True,
    },
    {
        "modelId": "flux_2_max",
        "provider": "api.bfl.ai",
        "displayName": "Flux 2 Max",
        "buckets": ["photorealism", "artistic", "humans"],
        "costPerImage": 0.055,
        "isActive": True,
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
        "modelId": "recraft_v4_pro",
        "provider": "fal.ai",
        "displayName": "Recraft v4 Pro",
        "buckets": ["vector", "typography"],
        "costPerImage": 0.03,
        "isActive": True,
        "isTestingEnabled": True,
    },
    {
        "modelId": "hunyuan_image",
        "provider": "fal.ai",
        "displayName": "Hunyuan Image",
        "buckets": ["anime", "typography"],
        "costPerImage": 0.04,
        "isActive": True,
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
        "provider": "fal.ai",
        "displayName": "Grok 2 Imagine",
        "buckets": ["photorealism", "artistic", "typography", "humans", "multi_person"],
        "costPerImage": 0.05,
        "isActive": True,
        "isTestingEnabled": True,
    },
    {
        "modelId": "imagen_4_ultra",
        "provider": "google.ai",
        "displayName": "Imagen 4 Ultra",
        "buckets": ["photorealism", "typography", "humans", "image_to_image"],
        "costPerImage": 0.18,
        "isActive": True,
        "isTestingEnabled": True,
    },
    {
        "modelId": "flux_2_flex",
        "provider": "fal.ai",
        "displayName": "Flux 2 Flex",
        "buckets": ["photorealism", "artistic", "typography"],
        "costPerImage": 0.04,
        "isActive": True,
        "isTestingEnabled": True,
    },
    {
        "modelId": "wan_2_7",
        "provider": "fal.ai",
        "displayName": "Wan 2.7",
        "buckets": ["photorealism", "artistic", "typography"],
        "costPerImage": 0.05,
        "isActive": True,
        "isTestingEnabled": True,
    },
    {
        "modelId": "imagen_4_base",
        "provider": "google.ai",
        "displayName": "Imagen 4 Base",
        "buckets": ["photorealism", "typography", "humans"],
        "costPerImage": 0.08,
        "isActive": True,
        "isTestingEnabled": True,
    },
    {
        "modelId": "imagen_3",
        "provider": "google.ai",
        "displayName": "Imagen 3",
        "buckets": ["photorealism", "typography"],
        "costPerImage": 0.04,
        "isActive": True,
        "isTestingEnabled": True,
    },
    {
        "modelId": "imagen_4_fast",
        "provider": "google.ai",
        "displayName": "Imagen 4 Fast",
        "buckets": ["photorealism", "typography", "humans", "image_to_image"],
        "costPerImage": 0.06,
        "isActive": True,
        "isTestingEnabled": True,
    },
    {
        "modelId": "gemini_3_imagen",
        "provider": "google.ai",
        "displayName": "Gemini 3 Imagen",
        "buckets": ["photorealism", "artistic", "typography", "image_to_image"],
        "costPerImage": 0.035,
        "isActive": True,
        "isTestingEnabled": True,
    },
    {
        "modelId": "gemini_3_1_imagen",
        "provider": "google.ai",
        "displayName": "Gemini 3.1 Imagen",
        "buckets": ["photorealism", "artistic", "typography", "image_to_image"],
        "costPerImage": 0.07,
        "isActive": True,
        "isTestingEnabled": True,
    },
]

DEFAULT_MODELS_BY_ID = {model["modelId"]: model for model in DEFAULT_MODELS}

_LEGACY_MODEL_IDS_BY_CANONICAL: Dict[str, List[str]] = {}
for legacy_model_id, canonical_model_id in LEGACY_MODEL_ALIASES.items():
    _LEGACY_MODEL_IDS_BY_CANONICAL.setdefault(canonical_model_id, []).append(legacy_model_id)


def _canonical_model_id(model_id: str) -> str:
    return LEGACY_MODEL_ALIASES.get(model_id, model_id)


def _equivalent_model_ids(model_id: str) -> List[str]:
    canonical_model_id = _canonical_model_id(model_id)
    return [canonical_model_id, *_LEGACY_MODEL_IDS_BY_CANONICAL.get(canonical_model_id, [])]


def _default_model_config(model_id: str) -> Optional[dict]:
    return DEFAULT_MODELS_BY_ID.get(_canonical_model_id(model_id))


def _preferred_model_rows(models) -> Dict[str, object]:
    preferred: Dict[str, object] = {}
    for model in models:
        canonical_model_id = _canonical_model_id(model.modelId)
        current = preferred.get(canonical_model_id)
        if current is None or (current.modelId in LEGACY_MODEL_ALIASES and model.modelId == canonical_model_id):
            preferred[canonical_model_id] = model
    return preferred


def _merged_model_config(model) -> dict:
    defaults = _default_model_config(model.modelId)
    canonical_model_id = _canonical_model_id(model.modelId)
    if defaults:
        provider = defaults["provider"]
        display_name = defaults["displayName"]
        buckets = defaults["buckets"]
        cost_per_image = defaults["costPerImage"]
    else:
        provider = model.provider
        display_name = model.displayName
        buckets = model.buckets
        cost_per_image = model.costPerImage

    return {
        "id": model.id,
        "modelId": canonical_model_id,
        "provider": provider,
        "displayName": display_name,
        "buckets": buckets,
        "isActive": model.isActive,
        "isTestingEnabled": model.isTestingEnabled,
        "costPerImage": cost_per_image,
        "createdAt": model.createdAt.isoformat() if model.createdAt else None,
        "updatedAt": model.updatedAt.isoformat() if model.updatedAt else None,
    }


async def _find_existing_model(prisma, model_id: str):
    for candidate in _equivalent_model_ids(model_id):
        existing = await prisma.modelconfig.find_unique(where={"modelId": candidate})
        if existing:
            return existing
    return None


def _syncable_model_fields(existing, canonical_model_data: dict) -> dict:
    update_data = {}
    for field in ("provider", "displayName", "buckets", "costPerImage"):
        if getattr(existing, field) != canonical_model_data[field]:
            update_data[field] = canonical_model_data[field]
    return update_data


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/admin/models/seed")
async def seed_models():
    """
    Seed and sync default models into database.
    Safe to call multiple times - creates missing rows and repairs stale metadata.
    """
    try:
        from prisma import Prisma
        prisma = Prisma()
        await prisma.connect()

        created_count = 0
        updated_count = 0
        migrated_count = 0

        for legacy_model_id, canonical_model_id in LEGACY_MODEL_ALIASES.items():
            legacy = await prisma.modelconfig.find_unique(where={"modelId": legacy_model_id})
            canonical = await prisma.modelconfig.find_unique(where={"modelId": canonical_model_id})
            canonical_model_data = DEFAULT_MODELS_BY_ID.get(canonical_model_id)

            if legacy and not canonical and canonical_model_data:
                await prisma.modelconfig.update(
                    where={"modelId": legacy_model_id},
                    data={
                        "modelId": canonical_model_id,
                        "provider": canonical_model_data["provider"],
                        "displayName": canonical_model_data["displayName"],
                        "buckets": canonical_model_data["buckets"],
                        "costPerImage": canonical_model_data["costPerImage"],
                    },
                )
                migrated_count += 1
                logger.info("[seed] Migrated legacy model: %s -> %s", legacy_model_id, canonical_model_id)

        for model_data in DEFAULT_MODELS:
            # Check if model already exists
            existing = await prisma.modelconfig.find_unique(
                where={"modelId": model_data["modelId"]}
            )

            if not existing:
                await prisma.modelconfig.create(data=model_data)
                created_count += 1
                logger.info(f"[seed] Created model: {model_data['modelId']}")
                continue

            update_data = _syncable_model_fields(existing, model_data)
            if update_data:
                await prisma.modelconfig.update(
                    where={"modelId": model_data["modelId"]},
                    data=update_data,
                )
                updated_count += 1
                logger.info("[seed] Synced model metadata: %s", model_data["modelId"])

        await prisma.disconnect()

        return {
            "success": True,
            "message": (
                f"Seeded {created_count} new models, "
                f"updated {updated_count} existing models, "
                f"migrated {migrated_count} legacy ids"
            ),
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

        display_models = sorted(
            (_merged_model_config(model) for model in _preferred_model_rows(models).values()),
            key=lambda model: model["displayName"].lower(),
        )

        # Calculate stats for each model from Generation table
        models_data = []
        for model in display_models:
            model_ids = _equivalent_model_ids(model["modelId"])
            # Count generations for this model
            total_gens = await prisma.generation.count(
                where={
                    "modelUsed": {"in": model_ids},
                    "isDeleted": False
                }
            )

            # Get average rating from user ratings (Python Prisma doesn't support select)
            # Wrapped in try-except to handle schema mismatches (userReason column may not exist yet)
            avg_rating = None
            avg_cost = None
            avg_latency = None

            try:
                rated_gens = await prisma.generation.find_many(
                    where={
                        "modelUsed": {"in": model_ids},
                        "userRating": {"not": None},
                        "isDeleted": False
                    }
                )

                if rated_gens:
                    # Calculate averages (extract fields after fetch)
                    ratings = [g.userRating for g in rated_gens if g.userRating is not None]
                    costs = [g.creditsUsed for g in rated_gens if g.creditsUsed is not None]
                    latencies = [g.generationTimeSeconds for g in rated_gens if g.generationTimeSeconds is not None]

                    avg_rating = sum(ratings) / len(ratings) if ratings else None
                    avg_cost = sum(costs) / len(costs) if costs else None
                    avg_latency = sum(latencies) / len(latencies) if latencies else None
            except Exception as e:
                # Schema mismatch (userReason column doesn't exist) - skip averages for now
                logger.warning(f"[admin_models] Could not calculate averages for {model['modelId']}: {e}")

            models_data.append({
                "id": model["id"],
                "modelId": model["modelId"],
                "provider": model["provider"],
                "displayName": model["displayName"],
                "buckets": model["buckets"],
                "isActive": model["isActive"],
                "isTestingEnabled": model["isTestingEnabled"],
                "totalGenerations": total_gens,
                "avgRating": round(avg_rating, 2) if avg_rating else None,
                "avgCost": round(avg_cost, 2) if avg_cost else None,
                "avgLatency": round(avg_latency, 2) if avg_latency else None,
                "costPerImage": model["costPerImage"],
                "createdAt": model["createdAt"],
                "updatedAt": model["updatedAt"],
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

        display_models = sorted(
            (_merged_model_config(model) for model in _preferred_model_rows(models).values()),
            key=lambda model: model["displayName"].lower(),
        )

        # Filter by bucket if specified
        if bucket:
            display_models = [model for model in display_models if bucket in model["buckets"]]

        await prisma.disconnect()

        return {
            "models": [
                {
                    "modelId": model["modelId"],
                    "provider": model["provider"],
                    "displayName": model["displayName"],
                    "buckets": model["buckets"],
                    "costPerImage": model["costPerImage"],
                }
                for model in display_models
            ],
            "count": len(display_models),
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

        display_models = sorted(
            (_merged_model_config(model) for model in _preferred_model_rows(models).values()),
            key=lambda model: model["displayName"].lower(),
        )

        # Filter by bucket if specified
        if bucket:
            display_models = [model for model in display_models if bucket in model["buckets"]]

        await prisma.disconnect()

        return {
            "models": [model["modelId"] for model in display_models],
            "count": len(display_models),
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

        existing = await _find_existing_model(prisma, update.modelId)
        if not existing:
            await prisma.disconnect()
            raise HTTPException(status_code=404, detail=f"Model not found: {update.modelId}")

        # Update model
        model = await prisma.modelconfig.update(
            where={"modelId": existing.modelId},
            data=update_data
        )

        await prisma.disconnect()

        logger.info(f"[admin_models] Updated model {update.modelId}: {update_data}")

        return {
            "success": True,
            "message": f"Updated {_canonical_model_id(update.modelId)}",
            "model": {
                "modelId": _canonical_model_id(model.modelId),
                "isActive": model.isActive,
                "isTestingEnabled": model.isTestingEnabled,
                "buckets": model.buckets,
            },
        }

    except HTTPException:
        raise
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
                    existing = await _find_existing_model(prisma, update.modelId)
                    if not existing:
                        raise ValueError(f"Model not found: {update.modelId}")

                    await prisma.modelconfig.update(
                        where={"modelId": existing.modelId},
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
                "modelUsed": {"in": _equivalent_model_ids(model_id)},
                "userRating": {"not": None}
            },
            order={"createdAt": "desc"},
            take=100  # Latest 100 ratings
        )

        await prisma.disconnect()

        return {
            "model_id": _canonical_model_id(model_id),
            "total_ratings": len(generations),
            "ratings": [
                {
                    "id": g.id,
                    "rating": g.userRating,
                    "reason": getattr(g, 'userReason', None),  # Safe access (column may not exist yet)
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
