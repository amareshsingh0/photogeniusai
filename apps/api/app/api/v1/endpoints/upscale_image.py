"""
Upscale Image — POST /api/v1/upscale
Uses Real-ESRGAN 4x for high-quality upscaling.
"""
from __future__ import annotations

import logging
import time

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(tags=["upscale"])


class UpscaleRequest(BaseModel):
    image_url: str = Field(..., description="URL of the image to upscale")
    scale: int = Field(default=4, ge=2, le=4, description="Upscale factor: 2x or 4x")


class UpscaleResponse(BaseModel):
    success: bool = True
    image_url: str
    original_url: str
    scale: int
    model_used: str = "real-esrgan"
    total_time: float = 0.0


@router.post("/upscale", response_model=UpscaleResponse, summary="Upscale image 2x or 4x")
async def upscale_image(request: UpscaleRequest):
    start = time.time()

    logger.info("[UPSCALE] scale=%dx url=%s", request.scale, request.image_url[:60])

    try:
        from app.services.external.fal_client import fal_client

        result = await fal_client.upscale(
            image_url=request.image_url,
            scale=request.scale,
        )

        if not result["success"]:
            raise HTTPException(
                status_code=503,
                detail="Upscale service unavailable",
            )

        return UpscaleResponse(
            success=True,
            image_url=result["image_url"],
            original_url=request.image_url,
            scale=request.scale,
            model_used=result["model"],
            total_time=time.time() - start,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("[UPSCALE] failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Upscale failed: {e}")
