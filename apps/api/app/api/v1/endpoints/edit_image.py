"""
Edit Image — POST /api/v1/edit

Modes:
  1. Targeted (mask-based):  mask_data provided → Flux Fill inpainting
     mask_data = base64-encoded PNG (white = repaint, black = keep)
  2. Global (instruction):   no mask → Flux Kontext instruction editing
"""
from __future__ import annotations

import base64
import logging
import time
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(tags=["edit"])


class EditRequest(BaseModel):
    image_url: str  = Field(..., description="URL of the image to edit")
    instruction: str = Field(..., min_length=3, max_length=1000)
    quality:   Optional[str] = Field(default="balanced")
    width:     int  = Field(default=1024, ge=256, le=2048)
    height:    int  = Field(default=1024, ge=256, le=2048)
    # Targeted edit — base64-encoded PNG mask (white=edit, black=keep)
    mask_data: Optional[str] = Field(default=None, description="base64 PNG mask for inpainting")


class EditResponse(BaseModel):
    success:      bool  = True
    image_url:    str
    original_url: str
    instruction:  str
    model_used:   str   = ""
    total_time:   float = 0.0
    mode:         str   = "global"   # "global" | "targeted"


@router.post("/edit", response_model=EditResponse)
async def edit_image(request: EditRequest):
    start = time.time()
    from app.services.external.fal_client import fal_client

    # ── Targeted edit: mask provided → Flux Fill inpainting ──────────────────
    if request.mask_data:
        logger.info("[EDIT/targeted] uploading mask for inpainting")
        try:
            # Strip data URI prefix if present
            raw_b64 = request.mask_data
            if "," in raw_b64:
                raw_b64 = raw_b64.split(",", 1)[1]
            mask_bytes = base64.b64decode(raw_b64)

            # Upload mask to fal.ai storage → get URL
            mask_url = await fal_client.upload_bytes(mask_bytes, "image/png", "mask.png")

            # Inpaint with Flux Fill
            result = await fal_client.inpaint(
                image_url=request.image_url,
                mask_url=mask_url,
                prompt=request.instruction,
                image_size="square_hd",
                num_inference_steps=28 if request.quality != "fast" else 12,
                guidance_scale=7.0,
            )
        except Exception as e:
            logger.exception("[EDIT/targeted] upload/inpaint failed: %s", e)
            raise HTTPException(status_code=503, detail=f"Targeted edit failed: {e}")

        if not result["success"]:
            raise HTTPException(
                status_code=503,
                detail=f"Inpainting failed: {result['metadata'].get('error', 'unknown')}",
            )

        return EditResponse(
            success=True,
            image_url=result["image_url"],
            original_url=request.image_url,
            instruction=request.instruction,
            model_used=result["model"],
            total_time=time.time() - start,
            mode="targeted",
        )

    # ── Global edit: no mask → Flux Kontext instruction editing ──────────────
    model = "flux_kontext_max" if request.quality == "quality" else "flux_kontext"
    logger.info("[EDIT/global] instruction=%r model=%s", request.instruction[:60], model)

    try:
        result = await fal_client.generate(
            prompt=request.instruction,
            model=model,
            reference_image_url=request.image_url,
            image_size="square_hd",
            num_images=1,
        )

        if not result["success"]:
            raise HTTPException(
                status_code=503,
                detail=f"Edit failed: {result['metadata'].get('error', 'unknown')}",
            )

        return EditResponse(
            success=True,
            image_url=result["image_url"],
            original_url=request.image_url,
            instruction=request.instruction,
            model_used=result["model"],
            total_time=time.time() - start,
            mode="global",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("[EDIT/global] failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Edit failed: {e}")
