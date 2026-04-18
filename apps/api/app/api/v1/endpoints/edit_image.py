"""
Edit Image — POST /api/v1/edit

Operations (auto-routed to the best capable model — model name is NOT exposed
to clients):

  instruction_edit   — "make sky purple", "add a hat"        → Flux Kontext
  inpaint_mask       — mask + prompt → repaint masked region → Flux Fill
  style_remix        — restyle reference with new prompt     → Ideogram remix
  compose            — combine multiple reference images     → Seedream edit
  object_add         — add an object to the scene            → Flux Kontext
  object_remove      — remove an object cleanly              → Flux Kontext
  background_swap    — change background, keep subject       → Flux Kontext
  text_replace       — change text inside the image          → Ideogram remix

Legacy clients without `edit_mode` default to `instruction_edit` (or
`inpaint_mask` when `mask_data` is supplied).
"""
from __future__ import annotations

import base64
import logging
import time
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.services.smart.model_config import (
    EDIT_MODES,
    QualityTier,
    get_default_model_for_edit_mode,
    normalize_quality_tier,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["edit"])


class EditRequest(BaseModel):
    image_url: str = Field(..., description="URL of the image to edit")
    instruction: str = Field(..., min_length=3, max_length=1000)
    quality: Optional[str] = Field(default=QualityTier.RES_1K.value)
    width: int = Field(default=1024, ge=256, le=4096)
    height: int = Field(default=1024, ge=256, le=4096)
    # Targeted edit — base64 PNG mask (white=edit, black=keep)
    mask_data: Optional[str] = Field(default=None)
    # New: explicit operation type. If absent, inferred from mask_data presence.
    edit_mode: Optional[str] = Field(default=None)
    # Compose mode: extra reference image URLs (Seedream edit accepts multiple)
    extra_image_urls: Optional[List[str]] = Field(default=None)

    @field_validator("quality")
    @classmethod
    def validate_quality(cls, v: Optional[str]) -> str:
        return normalize_quality_tier(v)

    @field_validator("edit_mode")
    @classmethod
    def validate_edit_mode(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        if v not in EDIT_MODES:
            raise ValueError(f"edit_mode must be one of {EDIT_MODES}")
        return v


class EditResponse(BaseModel):
    success: bool = True
    image_url: str
    original_url: str
    instruction: str
    edit_mode: str = "instruction_edit"
    total_time: float = 0.0
    # Note: `model_used` deliberately omitted — internal routing detail.


class UploadDataUrlRequest(BaseModel):
    data_url: str = Field(..., description="data:image/...;base64,... URL")


class UploadDataUrlResponse(BaseModel):
    url: str
    content_type: str


@router.post("/storage/upload-data-url", response_model=UploadDataUrlResponse)
async def upload_data_url(request: UploadDataUrlRequest):
    """Upload a base64 data URL to fal.ai storage → returns an HTTPS URL."""
    from app.services.external.fal_client import fal_client
    try:
        header, b64 = request.data_url.split(",", 1)
        content_type = header.split(":")[1].split(";")[0] if ":" in header else "image/png"
        import base64 as _b64
        img_bytes = _b64.b64decode(b64)
        ext = "jpg" if "jpeg" in content_type else "png"
        url = await fal_client.upload_bytes(img_bytes, content_type, f"image.{ext}")
        return UploadDataUrlResponse(url=url, content_type=content_type)
    except Exception as e:
        logger.exception("[upload-data-url] failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Upload failed: {e}")


def _resolve_edit_mode(request: EditRequest) -> str:
    """Infer mode if caller didn't pass one explicitly."""
    if request.edit_mode:
        return request.edit_mode
    if request.mask_data:
        return "inpaint_mask"
    if request.extra_image_urls:
        return "compose"
    return "instruction_edit"


def _instruction_for_mode(edit_mode: str, instruction: str) -> str:
    """Prepend a verb hint so the model interprets the instruction correctly.

    Kontext / Seedream respond well to imperative phrasing. We add a short
    prefix so "a hat" becomes "Add a hat to the subject", etc.
    """
    raw = instruction.strip()
    raw_low = raw.lower()
    prefixes = {
        "object_add":      "Add to the scene: ",
        "object_remove":   "Remove from the scene cleanly: ",
        "background_swap": "Replace the background with: ",
        "text_replace":    "Replace the visible text with: ",
        "style_remix":     "Restyle in the style of: ",
        "compose":         "Combine the reference images so that: ",
    }
    pref = prefixes.get(edit_mode)
    if not pref:
        return raw
    # Don't double-prefix if the user already wrote it that way
    if raw_low.startswith(pref.strip().lower()[:6]):
        return raw
    return f"{pref}{raw}"


@router.post("/edit", response_model=EditResponse)
async def edit_image(request: EditRequest):
    start = time.time()
    edit_mode = _resolve_edit_mode(request)
    instruction = _instruction_for_mode(edit_mode, request.instruction)
    logger.info(
        "[EDIT] mode=%s quality=%s instr=%r extra_imgs=%d mask=%s",
        edit_mode, request.quality, instruction[:60],
        len(request.extra_image_urls or []),
        bool(request.mask_data),
    )

    # ── Inpaint (mask) — Flux Fill ────────────────────────────────────────
    if edit_mode == "inpaint_mask":
        if not request.mask_data:
            raise HTTPException(status_code=400, detail="inpaint_mask requires mask_data")
        from app.services.external.fal_client import fal_client
        try:
            raw_b64 = request.mask_data
            if "," in raw_b64:
                raw_b64 = raw_b64.split(",", 1)[1]
            mask_bytes = base64.b64decode(raw_b64)
            mask_url = await fal_client.upload_bytes(mask_bytes, "image/png", "mask.png")
            steps = (
                50 if request.quality == QualityTier.RES_4K.value
                else 28 if request.quality == QualityTier.RES_2K.value
                else 12
            )
            result = await fal_client.inpaint(
                image_url=request.image_url,
                mask_url=mask_url,
                prompt=instruction,
                image_size="square_hd",
                num_inference_steps=steps,
                guidance_scale=7.0,
            )
        except Exception as e:
            logger.exception("[EDIT/inpaint] failed: %s", e)
            raise HTTPException(status_code=503, detail=f"Inpaint failed: {e}")

        if not result.get("success"):
            raise HTTPException(
                status_code=503,
                detail=f"Inpaint failed: {result.get('metadata', {}).get('error', 'unknown')}",
            )
        return EditResponse(
            success=True,
            image_url=result["image_url"],
            original_url=request.image_url,
            instruction=request.instruction,
            edit_mode=edit_mode,
            total_time=time.time() - start,
        )

    # ── All other modes — route to the capable model via multi_client ─────
    from app.services.external.multi_provider_client import multi_client
    model_key = get_default_model_for_edit_mode(edit_mode, request.quality)
    logger.info("[EDIT] mode=%s → model=%s (hidden from client)", edit_mode, model_key)

    try:
        # Compose mode: Seedream Edit + Kontext Max accept image_urls arrays.
        # For single-ref modes, only reference_image_url is used; extras are a no-op.
        result = await multi_client.generate(
            model_key=model_key,
            prompt=instruction,
            reference_image_url=request.image_url,
            extra_image_urls=request.extra_image_urls or None,
            num_images=1,
            image_size="square_hd",
        )
    except Exception as e:
        logger.exception("[EDIT/%s] generate failed: %s", edit_mode, e)
        raise HTTPException(status_code=503, detail=f"Edit failed: {e}")

    if not result.get("success") or not result.get("image_url"):
        err = result.get("metadata", {}).get("error", "unknown")
        raise HTTPException(status_code=503, detail=f"Edit failed: {err}")

    return EditResponse(
        success=True,
        image_url=result["image_url"],
        original_url=request.image_url,
        instruction=request.instruction,
        edit_mode=edit_mode,
        total_time=time.time() - start,
    )


# ── Capability discovery — used by frontend to show only supported ops ──────
class EditCapabilitiesResponse(BaseModel):
    modes: List[str]


@router.get("/edit/capabilities", response_model=EditCapabilitiesResponse)
async def edit_capabilities():
    """Return the list of edit modes supported by the backend."""
    return EditCapabilitiesResponse(modes=list(EDIT_MODES))
