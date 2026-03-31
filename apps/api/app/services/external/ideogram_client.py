"""
Ideogram Client — Typography & text-heavy generation specialist.

Use when prompt contains: text, quote, name, logo, poster, banner, headline, etc.
Ideogram 3.0 is the industry leader for readable text in generated images.

Requires:
  IDEOGRAM_API_KEY env var
  pip install httpx

Response contract (same as fal_client):
  {
    "image_url": str,
    "all_urls": List[str],
    "metadata": dict,
    "success": bool,
    "backend": "ideogram",
    "model": str,
    "generation_time": float
  }
"""

from __future__ import annotations

import logging
import os
import time
from typing import Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

IDEOGRAM_BASE = "https://api.ideogram.ai"

# Model versions
IDEOGRAM_MODELS = {
    "v3":      "V_3",
    "v2":      "V_2",
    "v2_turbo": "V_2_TURBO",
}

# Aspect ratios
IDEOGRAM_RATIOS = {
    "1:1":   "ASPECT_1_1",
    "16:9":  "ASPECT_16_9",
    "9:16":  "ASPECT_9_16",
    "4:3":   "ASPECT_4_3",
    "3:4":   "ASPECT_3_4",
    "3:2":   "ASPECT_3_2",
    "2:3":   "ASPECT_2_3",
    "square": "ASPECT_1_1",
    "landscape": "ASPECT_16_9",
    "portrait": "ASPECT_9_16",
}

# Style types
IDEOGRAM_STYLES = {
    "auto":       "AUTO",
    "general":    "GENERAL",
    "realistic":  "REALISTIC",
    "design":     "DESIGN",
    "render_3d":  "RENDER_3D",
    "anime":      "ANIME",
}


class IdeogramClient:
    """
    Async client for Ideogram API (typography specialist).

    Usage:
        client = IdeogramClient()
        result = await client.generate(
            prompt='Bold red text "SALE 50% OFF" on white background',
            aspect_ratio="1:1",
        )
    """

    def __init__(self):
        self.api_key = os.getenv("IDEOGRAM_API_KEY", "")
        self._http: Optional[httpx.AsyncClient] = None

        if not self.api_key:
            logger.warning("IDEOGRAM_API_KEY not set — Ideogram generation will fail")

    @property
    def http(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(
                timeout=httpx.Timeout(connect=10, read=180, write=30, pool=5),
                headers={
                    "Api-Key": self.api_key,
                    "Content-Type": "application/json",
                },
            )
        return self._http

    async def generate(
        self,
        prompt: str,
        model: str = "v3",
        aspect_ratio: str = "1:1",
        style_type: str = "design",
        negative_prompt: str = "",
        num_images: int = 1,
        rendering_speed: str = "DEFAULT",      # DEFAULT | TURBO | QUALITY
        magic_prompt: str = "OFF",             # OFF = no auto-rewrite (we control prompt)
        seed: Optional[int] = None,
    ) -> Dict:
        """
        Generate image via Ideogram. Best for text-heavy prompts.

        rendering_speed: "TURBO" (fast), "DEFAULT" (balanced), "QUALITY" (best)
        magic_prompt:    Keep "OFF" — our Claude prompt engine handles enhancement.
        """
        start = time.time()
        model_id = IDEOGRAM_MODELS.get(model, "V_3")
        ratio = IDEOGRAM_RATIOS.get(aspect_ratio, "ASPECT_1_1")
        style = IDEOGRAM_STYLES.get(style_type, "DESIGN")

        request_body: Dict = {
            "image_request": {
                "prompt": prompt,
                "model": model_id,
                "aspect_ratio": ratio,
                "style_type": style,
                "num_images": num_images,
                "magic_prompt_option": magic_prompt,
                "rendering_speed": rendering_speed,
            }
        }
        if negative_prompt:
            request_body["image_request"]["negative_prompt"] = negative_prompt
        if seed is not None:
            request_body["image_request"]["seed"] = seed

        logger.info("[ideogram] model=%s ratio=%s prompt=%.60s", model_id, ratio, prompt)

        try:
            resp = await self.http.post(
                f"{IDEOGRAM_BASE}/generate",
                json=request_body,
            )
            resp.raise_for_status()
            data = resp.json()

            images: List[Dict] = data.get("data", [])
            if not images:
                raise ValueError(f"No images in Ideogram response: {list(data.keys())}")

            urls = [img["url"] for img in images if img.get("url")]
            if not urls:
                raise ValueError("Could not extract URLs from Ideogram response")

            elapsed = time.time() - start
            logger.info("[ideogram] done images=%d time=%.1fs", len(urls), elapsed)

            return {
                "image_url": urls[0],
                "all_urls": urls,
                "image_b64": None,
                "metadata": {
                    "model": model_id,
                    "style": style,
                    "resolution": images[0].get("resolution", ""),
                    "is_image_safe": images[0].get("is_image_safe", True),
                    "seed": images[0].get("seed"),
                },
                "success": True,
                "backend": "ideogram",
                "model": model_id,
                "generation_time": elapsed,
            }

        except httpx.HTTPStatusError as e:
            logger.error("[ideogram] HTTP %d: %s", e.response.status_code, e.response.text[:300])
            return self._error(model_id, str(e), time.time() - start)
        except Exception as e:
            logger.error("[ideogram] error: %s", e)
            return self._error(model_id, str(e), time.time() - start)

    async def edit(
        self,
        prompt: str,
        image_url: str,
        mask_url: Optional[str] = None,
        model: str = "v2",
        magic_prompt: str = "OFF",
    ) -> Dict:
        """Ideogram inpaint/edit endpoint."""
        start = time.time()
        model_id = IDEOGRAM_MODELS.get(model, "V_2")

        payload = {
            "image_request": {
                "prompt": prompt,
                "model": model_id,
                "image_url": image_url,
                "magic_prompt_option": magic_prompt,
            }
        }
        if mask_url:
            payload["image_request"]["mask_url"] = mask_url

        try:
            resp = await self.http.post(f"{IDEOGRAM_BASE}/edit", json=payload)
            resp.raise_for_status()
            data = resp.json()
            images = data.get("data", [])
            urls = [img["url"] for img in images if img.get("url")]
            return {
                "image_url": urls[0] if urls else None,
                "all_urls": urls,
                "image_b64": None,
                "metadata": data,
                "success": bool(urls),
                "backend": "ideogram",
                "model": model_id,
                "generation_time": time.time() - start,
            }
        except Exception as e:
            logger.error("[ideogram] edit error: %s", e)
            return self._error(model_id, str(e), time.time() - start)

    @staticmethod
    def _error(model: str, msg: str, elapsed: float) -> Dict:
        return {
            "image_url": None,
            "all_urls": [],
            "image_b64": None,
            "metadata": {"error": msg},
            "success": False,
            "backend": "ideogram",
            "model": model,
            "generation_time": elapsed,
        }

    async def close(self):
        if self._http and not self._http.is_closed:
            await self._http.aclose()


# Singleton
ideogram_client = IdeogramClient()
