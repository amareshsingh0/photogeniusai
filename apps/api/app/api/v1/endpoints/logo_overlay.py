"""
Logo Overlay — POST /api/v1/logo-overlay

Composite a brand logo onto an image using PIL.
Supports 9 fixed positions + "auto" (Gemini vision picks best ad-safe spot).

Request:
  image_url   str            — source image URL
  logo_data   str            — base64-encoded logo (PNG/WebP with transparency)
  position    str            — top_left | top_center | top_right |
                               center_left | center | center_right |
                               bottom_left | bottom_center | bottom_right | auto
  size_pct    int (5-40)     — logo width as % of image width (default 20)
  opacity     int (10-100)   — logo opacity % (default 90)
  padding_pct float (1-8)    — edge padding as % of image min-dim (default 3)

Response:
  success     bool
  image_b64   str            — base64 JPEG composite
  position_used str          — actual position chosen
"""
from __future__ import annotations

import base64
import io
import logging
import os

import numpy as np

import httpx
from fastapi import APIRouter, HTTPException
from PIL import Image
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(tags=["logo"])

_GEMINI_KEY = os.getenv("GEMINI_API_KEY", "").strip()

_VALID_POSITIONS = {
    "top_left", "top_center", "top_right",
    "center_left", "center", "center_right",
    "bottom_left", "bottom_center", "bottom_right",
}


class LogoRequest(BaseModel):
    image_url:   str          = Field(..., description="Source image URL")
    logo_data:   str          = Field(..., description="Base64-encoded logo PNG")
    position:    str          = Field(default="auto")
    size_pct:    int          = Field(default=20, ge=5, le=40)
    opacity:     int          = Field(default=90, ge=10, le=100)
    padding_pct: float        = Field(default=3.0, ge=1.0, le=8.0)


class LogoResponse(BaseModel):
    success:       bool
    image_b64:     str = ""
    position_used: str = ""
    error:         str = ""


# ── Gemini: ask where to place logo for best ad placement ────────────────────

def _gemini_pick_position(image_url: str) -> str:
    """
    Ask Gemini 2.5 Flash (vision) where to place a logo in this ad image.
    Returns one of the 9 position strings, falls back to 'bottom_right' on error.
    """
    if not _GEMINI_KEY:
        return "bottom_right"
    try:
        from google import genai
        client = genai.Client(api_key=_GEMINI_KEY)
        prompt = (
            f"Image URL: {image_url}\n\n"
            "This is an advertisement or product image. "
            "Where should I place a small brand logo so it is clearly visible but "
            "does NOT cover the main subject, face, text, or focal point? "
            "Consider ad design best practices: logos typically go in corners. "
            "Reply with EXACTLY ONE of these (no other text): "
            "top_left, top_center, top_right, center_left, center_right, "
            "bottom_left, bottom_center, bottom_right"
        )
        from google.genai import types
        resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=20,
            ),
        )
        raw = (resp.text or "").strip().lower().replace(" ", "_")
        # Extract valid position from response
        for pos in _VALID_POSITIONS:
            if pos in raw:
                return pos
        return "bottom_right"
    except Exception as e:
        logger.warning("[logo] Gemini position failed: %s — using bottom_right", e)
        return "bottom_right"


# ── Heuristic: pick position based on image brightness per quadrant ───────────

def _heuristic_position(img: Image.Image) -> str:
    """
    Analyse 9 zones of the image, pick the darkest/emptiest corner zone
    (lowest std-dev + closest-to-neutral brightness) as the logo spot.
    """
    w, h = img.size
    zones = {
        "top_left":     (0,     0,     w//3,   h//3),
        "top_right":    (2*w//3, 0,    w,      h//3),
        "bottom_left":  (0,     2*h//3, w//3,  h),
        "bottom_right": (2*w//3, 2*h//3, w,    h),
    }
    gray = img.convert("L")
    best_pos = "bottom_right"
    best_score = float("inf")
    arr = np.array(gray, dtype=float)
    for pos, (x1, y1, x2, y2) in zones.items():
        region = arr[y1:y2, x1:x2]
        if region.size == 0:
            continue
        std = float(region.std())
        score = std  # lower std = simpler/emptier region
        if score < best_score:
            best_score = score
            best_pos = pos
    return best_pos


# ── PIL composite ─────────────────────────────────────────────────────────────

def _composite(
    img: Image.Image,
    logo: Image.Image,
    position: str,
    size_pct: int,
    opacity: int,
    padding_pct: float,
) -> Image.Image:
    img_w, img_h = img.size
    pad = int(min(img_w, img_h) * padding_pct / 100)

    # Resize logo: width = size_pct% of image width, maintain aspect ratio
    logo_w = max(1, int(img_w * size_pct / 100))
    ratio = logo_w / logo.width
    logo_h = max(1, int(logo.height * ratio))
    logo = logo.resize((logo_w, logo_h), Image.LANCZOS)

    # Ensure RGBA
    if logo.mode != "RGBA":
        logo = logo.convert("RGBA")

    # Apply opacity
    if opacity < 100:
        r, g, b, a = logo.split()
        a = a.point(lambda x: int(x * opacity / 100))
        logo = Image.merge("RGBA", (r, g, b, a))

    # Calculate paste coordinates
    x, y = _calc_xy(position, img_w, img_h, logo_w, logo_h, pad)

    # Composite
    out = img.convert("RGBA")
    out.paste(logo, (x, y), mask=logo)
    return out.convert("RGB")


def _calc_xy(pos: str, iw: int, ih: int, lw: int, lh: int, pad: int):
    # pos examples: "top_left", "bottom_right", "center", "center_left"
    parts = pos.split("_")
    row_part = parts[0]           # top / center / bottom
    col_part = parts[1] if len(parts) > 1 else "center"  # left / center / right

    if col_part == "left":
        x = pad
    elif col_part == "right":
        x = iw - lw - pad
    else:   # center
        x = (iw - lw) // 2

    if row_part == "top":
        y = pad
    elif row_part == "bottom":
        y = ih - lh - pad
    else:   # center
        y = (ih - lh) // 2

    return x, y


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.post("/logo-overlay", response_model=LogoResponse)
async def logo_overlay(request: LogoRequest):
    try:
        # 1. Download source image
        async with httpx.AsyncClient(timeout=30) as client:
            img_resp = await client.get(request.image_url)
            img_resp.raise_for_status()
        img = Image.open(io.BytesIO(img_resp.content)).convert("RGBA")

        # 2. Decode logo
        raw_b64 = request.logo_data
        if "," in raw_b64:
            raw_b64 = raw_b64.split(",", 1)[1]
        logo_bytes = base64.b64decode(raw_b64)
        logo = Image.open(io.BytesIO(logo_bytes)).convert("RGBA")

        # 3. Resolve position
        position = request.position.lower().strip()
        if position == "auto":
            # Try Gemini first (fast, async-friendly via thread if needed)
            try:
                position = _gemini_pick_position(request.image_url)
                logger.info("[logo] Gemini picked position: %s", position)
            except Exception:
                position = _heuristic_position(img)
                logger.info("[logo] heuristic position: %s", position)
        elif position not in _VALID_POSITIONS:
            position = "bottom_right"

        # 4. Composite
        out = _composite(img, logo, position, request.size_pct, request.opacity, request.padding_pct)

        # 5. Encode as JPEG
        buf = io.BytesIO()
        out.save(buf, format="JPEG", quality=92, optimize=True)
        encoded = base64.b64encode(buf.getvalue()).decode()

        return LogoResponse(
            success=True,
            image_b64=f"data:image/jpeg;base64,{encoded}",
            position_used=position,
        )

    except httpx.HTTPError as e:
        logger.error("[logo] image download failed: %s", e)
        raise HTTPException(status_code=422, detail=f"Could not fetch image: {e}")
    except Exception as e:
        logger.exception("[logo] overlay failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Logo overlay failed: {e}")
