"""
fal.ai Client — Primary generation backend (fast-move phase).

Models (updated March 2026 — Gen 2):
  fal-ai/flux-2-pro           → Photorealism, portrait, product (STANDARD/PREMIUM) [$0.03]
  fal-ai/flux-2               → Artistic, dev-quality generation [$0.012]
  fal-ai/flux-2/turbo         → Fast high-quality drafts [$0.008]
  fal-ai/flux-2-max           → Best artistic/cinematic quality [$0.07]
  fal-ai/flux/schnell         → Ultra-fast drafts (FAST tier) [$0.003]
  fal-ai/flux-pro/kontext     → Character consistency + instruction editing [$0.04]
  fal-ai/flux-pro/kontext/max → Multi-ref (up to 5 images) character consistency [$0.08]
  fal-ai/flux-pro/fill        → Mask-based inpainting [$0.05]
  fal-ai/ideogram/v3          → Typography / text-in-image (TURBO $0.03, QUALITY $0.09)
  fal-ai/recraft/v4/text-to-image       → Design / flat / brand raster [$0.04]
  fal-ai/recraft/v4/text-to-vector      → True SVG vector output [$0.08]
  fal-ai/hunyuan/image                  → Anime / Asian art styles [$0.03]
  fal-ai/real-esrgan          → 4x upscaling [$0.002]

Requires:
  FAL_KEY env var
  pip install fal-client httpx

Response contract (matches existing GenerationRouter format):
  {
    "image_url": str,          # CDN URL or data URI
    "image_b64": str | None,
    "all_urls": list[str],
    "metadata": dict,
    "success": bool,
    "backend": "fal.ai",
    "model": str,
    "generation_time": float
  }
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# ── Model IDs (fal.ai) ────────────────────────────────────────────────────────
FAL_MODELS = {
    # ── Flux Gen 2 (current generation) ───────────────────────────────────────
    "flux_2_pro":       "fal-ai/flux-2-pro",          # $0.03 — best photorealism
    "flux_2_dev":       "fal-ai/flux-2",               # $0.012 — gen2 dev quality
    "flux_2_turbo":     "fal-ai/flux-2/turbo",         # $0.008 — fast gen2
    "flux_2_max":       "fal-ai/flux-2-max",           # $0.07 — best artistic/cinematic
    # ── Flux Gen 1 (kept for compat / cheapest schnell) ───────────────────────
    "flux_schnell":     "fal-ai/flux/schnell",         # $0.003 — ultra-fast drafts
    "flux_pro":         "fal-ai/flux-pro",             # $0.05 — legacy, use flux_2_pro
    "flux_dev":         "fal-ai/flux/dev",             # $0.025 — legacy, use flux_2_dev
    # ── Flux Kontext (editing + character consistency) ─────────────────────────
    "flux_kontext":     "fal-ai/flux-pro/kontext",     # $0.04 — instruction editing
    "flux_kontext_max": "fal-ai/flux-pro/kontext/max", # $0.08 — multi-ref consistency
    "flux_fill":        "fal-ai/flux-pro/fill",        # $0.05 — mask inpainting
    # ── Specialist models ──────────────────────────────────────────────────────
    "ideogram_v3":      "fal-ai/ideogram/v3",          # $0.03-0.09 — best typography
    "recraft_v4":       "fal-ai/recraft/v4/text-to-image",  # $0.04 — design/brand
    "recraft_v4_svg":   "fal-ai/recraft/v4/text-to-vector", # $0.08 — true SVG output
    "hunyuan_image":    "fal-ai/hunyuan/image",        # $0.03 — best anime/Asian art
    # ── Post-processing ────────────────────────────────────────────────────────
    "real_esrgan":      "fal-ai/real-esrgan",          # $0.002 — 4x upscale
}

# Models that need specific payload handling
_SCHNELL_MODELS = {"fal-ai/flux/schnell"}               # max 12 steps, no guidance_scale
_IDEOGRAM_MODELS = {"fal-ai/ideogram/v3"}               # uses rendering_speed param
_RECRAFT_MODELS  = {"fal-ai/recraft/v4/text-to-image",
                    "fal-ai/recraft/v4/text-to-vector"} # uses style param
_KONTEXT_MODELS  = {"fal-ai/flux-pro/kontext",
                    "fal-ai/flux-pro/kontext/max"}       # uses image_url for reference

# Aspect ratio → fal.ai image_size string
FAL_SIZES = {
    "square":      "square_hd",       # 1024×1024
    "landscape":   "landscape_16_9",  # 1024×576
    "portrait":    "portrait_9_16",   # 576×1024
    "1:1":         "square_hd",
    "16:9":        "landscape_16_9",
    "9:16":        "portrait_9_16",
    "4:3":         "landscape_4_3",
    "3:4":         "portrait_4_3",
}


class FalClient:
    """
    Async client for fal.ai image generation.

    Usage:
        result = await fal_client.generate(model="flux_2_pro", prompt="...")
        result = await fal_client.upscale(image_url="https://...")
    """

    def __init__(self):
        self.api_key = os.getenv("FAL_KEY", "")
        self._http: Optional[httpx.AsyncClient] = None
        if not self.api_key:
            logger.warning("[fal] FAL_KEY not set — generation will fail")

    @property
    def http(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(
                timeout=httpx.Timeout(connect=10, read=300, write=30, pool=5),
                headers={
                    "Authorization": f"Key {self.api_key}",
                    "Content-Type": "application/json",
                },
            )
        return self._http

    # ── Core generate ──────────────────────────────────────────────────────────

    async def generate(
        self,
        prompt: str,
        model: str = "flux_2_pro",
        negative_prompt: str = "",
        num_images: int = 1,
        image_size: str = "square_hd",
        num_inference_steps: int = 28,
        guidance_scale: float = 3.5,
        seed: Optional[int] = None,
        reference_image_url: Optional[str] = None,
        # Ideogram-specific
        rendering_speed: str = "BALANCED",      # TURBO / BALANCED / QUALITY
        ideogram_style_type: str = "REALISTIC", # REALISTIC / GENERAL / DESIGN / RENDER_3D / ANIME
        # Recraft-specific
        style: Optional[str] = None,            # "realistic_image", "digital_illustration"
    ) -> Dict:
        """
        Generate image(s) via fal.ai. Handles model-specific payload differences.
        Returns the standard contract dict (see module docstring).
        """
        start = time.time()
        model_id = FAL_MODELS.get(model, model)   # accept raw fal model ID too
        resolved_size = FAL_SIZES.get(image_size, image_size)

        # ── Build model-specific payload ───────────────────────────────────────
        if model_id in _IDEOGRAM_MODELS:
            payload = self._ideogram_payload(
                prompt, resolved_size, num_images, rendering_speed,
                negative_prompt, ideogram_style_type
            )
        elif model_id in _RECRAFT_MODELS:
            payload = self._recraft_payload(
                prompt, resolved_size, num_images, style
            )
        elif model_id in _KONTEXT_MODELS:
            payload = self._kontext_payload(
                prompt, resolved_size, reference_image_url, num_images
            )
        else:
            payload = self._flux_payload(
                prompt, resolved_size, num_images, num_inference_steps,
                guidance_scale, seed, negative_prompt, model_id, reference_image_url
            )

        logger.info("[fal] model=%s prompt=%.60s num=%d", model_id, prompt, num_images)

        try:
            resp = await self.http.post(f"https://fal.run/{model_id}", json=payload)
            resp.raise_for_status()
            data = resp.json()
            image_urls = self._extract_urls(data)

            if not image_urls:
                raise ValueError(f"No images in fal.ai response: {list(data.keys())}")

            elapsed = time.time() - start
            logger.info("[fal] OK model=%s images=%d time=%.1fs", model_id, len(image_urls), elapsed)

            return {
                "image_url":       image_urls[0],
                "all_urls":        image_urls,
                "image_b64":       None,
                "metadata": {
                    "seed":        data.get("seed"),
                    "has_nsfw":    data.get("has_nsfw_concepts", [False])[0]
                                   if data.get("has_nsfw_concepts") else False,
                    "steps":       num_inference_steps,
                    "guidance":    guidance_scale,
                },
                "success":         True,
                "backend":         "fal.ai",
                "model":           model_id,
                "generation_time": elapsed,
            }

        except httpx.HTTPStatusError as e:
            logger.error("[fal] HTTP %d: %s", e.response.status_code, e.response.text[:300])
            return self._error(model_id, f"HTTP {e.response.status_code}: {e.response.text[:200]}", time.time() - start)
        except Exception as e:
            logger.error("[fal] error: %s", e)
            return self._error(model_id, str(e), time.time() - start)

    # ── Upscale ────────────────────────────────────────────────────────────────

    async def upscale(self, image_url: str, scale: int = 4) -> Dict:
        """4x upscale using Real-ESRGAN on fal.ai ($0.002/image)."""
        start = time.time()
        try:
            resp = await self.http.post(
                f"https://fal.run/{FAL_MODELS['real_esrgan']}",
                json={"image_url": image_url, "scale": scale, "face_enhance": True},
            )
            resp.raise_for_status()
            data = resp.json()
            out_url = (data.get("image") or {}).get("url") or data.get("output_url")
            return {
                "image_url":       out_url,
                "all_urls":        [out_url] if out_url else [],
                "success":         bool(out_url),
                "backend":         "fal.ai",
                "model":           FAL_MODELS["real_esrgan"],
                "generation_time": time.time() - start,
            }
        except Exception as e:
            logger.error("[fal] upscale error: %s", e)
            return self._error(FAL_MODELS["real_esrgan"], str(e), time.time() - start)

    # ── Queue-based (async) for long jobs ─────────────────────────────────────

    async def generate_queued(self, prompt: str, model: str = "flux_2_pro", **kwargs) -> Dict:
        """Submit to fal.ai queue and poll for result (for models without real-time endpoint)."""
        start = time.time()
        model_id = FAL_MODELS.get(model, model)
        payload = {"prompt": prompt, **kwargs}

        try:
            sub = await self.http.post(f"https://queue.fal.run/{model_id}", json=payload)
            sub.raise_for_status()
            request_id = sub.json()["request_id"]

            status_url = f"https://queue.fal.run/{model_id}/requests/{request_id}/status"
            result_url = f"https://queue.fal.run/{model_id}/requests/{request_id}"

            waited = 0
            while waited < 180:
                await asyncio.sleep(3)
                waited += 3
                st = await self.http.get(status_url)
                st.raise_for_status()
                status = st.json().get("status", "")
                if status == "COMPLETED":
                    res = await self.http.get(result_url)
                    res.raise_for_status()
                    data = res.json()
                    urls = self._extract_urls(data)
                    return {
                        "image_url": urls[0] if urls else None,
                        "all_urls": urls, "image_b64": None,
                        "metadata": data, "success": bool(urls),
                        "backend": "fal.ai (queue)", "model": model_id,
                        "generation_time": time.time() - start,
                    }
                elif status in ("FAILED", "CANCELLED"):
                    raise RuntimeError(f"fal.ai queue job {status}: {request_id}")

            raise TimeoutError(f"fal.ai queue timed out after 180s")

        except Exception as e:
            logger.error("[fal] queue error: %s", e)
            return self._error(model_id, str(e), time.time() - start)

    # ── Payload builders ───────────────────────────────────────────────────────

    def _flux_payload(self, prompt, image_size, num_images, steps, guidance,
                      seed, negative_prompt, model_id, reference_image_url) -> Dict:
        # Schnell: max 12 steps, no guidance_scale
        if model_id in _SCHNELL_MODELS:
            steps = min(steps, 12)

        p: Dict = {
            "prompt": prompt,
            "image_size": image_size,
            "num_inference_steps": steps,
            "num_images": num_images,
            "enable_safety_checker": False,
            "output_format": "jpeg",
        }
        if model_id not in _SCHNELL_MODELS:
            p["guidance_scale"] = guidance
        if negative_prompt:
            p["negative_prompt"] = negative_prompt
        if seed is not None:
            p["seed"] = seed
        if reference_image_url:
            p["image_url"] = reference_image_url
        return p

    def _ideogram_payload(self, prompt, image_size, num_images,
                          rendering_speed, negative_prompt,
                          style_type: str = "REALISTIC") -> Dict:
        p: Dict = {
            "prompt": prompt,
            "image_size": image_size,
            "num_images": num_images,
            "rendering_speed": rendering_speed,
            "style_type": style_type,  # REALISTIC prevents text generation in background
        }
        if negative_prompt:
            p["negative_prompt"] = negative_prompt
        return p

    def _recraft_payload(self, prompt, image_size, num_images, style) -> Dict:
        p: Dict = {
            "prompt": prompt,
            "image_size": image_size,
            "n": num_images,
        }
        if style:
            p["style"] = style
        return p

    def _kontext_payload(self, prompt, image_size, reference_image_url,
                         num_images) -> Dict:
        p: Dict = {
            "prompt": prompt,
            "image_size": image_size,
            "num_images": num_images,
        }
        if reference_image_url:
            p["image_url"] = reference_image_url
        return p

    # ── URL extraction (handles different fal.ai response shapes) ─────────────

    @staticmethod
    def _extract_urls(data: Dict) -> List[str]:
        images = data.get("images") or data.get("output") or []
        if isinstance(images, list):
            urls = []
            for img in images:
                if isinstance(img, dict):
                    url = img.get("url") or img.get("content_url")
                elif isinstance(img, str):
                    url = img
                else:
                    continue
                if url:
                    urls.append(url)
            return urls
        # Some models return single image object
        single = data.get("image")
        if isinstance(single, dict):
            url = single.get("url")
            return [url] if url else []
        return []

    # ── Helpers ────────────────────────────────────────────────────────────────

    @staticmethod
    def _error(model: str, msg: str, elapsed: float) -> Dict:
        return {
            "image_url": None, "all_urls": [], "image_b64": None,
            "metadata": {"error": msg}, "success": False,
            "backend": "fal.ai", "model": model, "generation_time": elapsed,
        }

    # ── File upload (for mask images) ─────────────────────────────────────────

    async def upload_bytes(self, data: bytes, content_type: str = "image/png",
                           filename: str = "mask.png") -> str:
        """
        Upload raw bytes to fal.ai storage.
        Returns a public URL usable as mask_url / image_url in API calls.
        Flow: POST /storage/upload/initiate → PUT to presigned URL → return file_url
        """
        if not self.api_key:
            raise RuntimeError("FAL_KEY not set — cannot upload")
        try:
            # Step 1: Get presigned upload URL
            initiate = await self.http.post(
                "https://rest.alpha.fal.ai/storage/upload/initiate",
                json={"content_type": content_type, "file_name": filename},
            )
            initiate.raise_for_status()
            init_data = initiate.json()
            upload_url: str = init_data["upload_url"]
            file_url: str = init_data["file_url"]

            # Step 2: PUT the binary data
            upload_client = httpx.AsyncClient(timeout=httpx.Timeout(60))
            async with upload_client as uc:
                put_resp = await uc.put(
                    upload_url,
                    content=data,
                    headers={"Content-Type": content_type},
                )
                put_resp.raise_for_status()

            logger.info("[fal] uploaded %d bytes → %s", len(data), file_url)
            return file_url
        except Exception as e:
            logger.error("[fal] upload error: %s", e)
            raise

    # ── Mask-based inpainting ─────────────────────────────────────────────────

    async def inpaint(
        self,
        image_url: str,
        mask_url: str,
        prompt: str,
        image_size: str = "square_hd",
        num_inference_steps: int = 28,
        guidance_scale: float = 7.0,
        strength: float = 0.99,
    ) -> Dict:
        """
        Mask-based inpainting via fal-ai/flux-pro/fill.
        mask_url: white = repaint, black = keep.
        """
        start = time.time()
        model_id = FAL_MODELS["flux_fill"]
        payload = {
            "image_url":            image_url,
            "mask_url":             mask_url,
            "prompt":               prompt,
            "image_size":           FAL_SIZES.get(image_size, image_size),
            "num_inference_steps":  num_inference_steps,
            "guidance_scale":       guidance_scale,
            "strength":             strength,
            "num_images":           1,
            "enable_safety_checker": False,
            "output_format":        "jpeg",
        }
        logger.info("[fal/fill] prompt=%.60s", prompt)
        try:
            resp = await self.http.post(f"https://fal.run/{model_id}", json=payload)
            resp.raise_for_status()
            data = resp.json()
            image_urls = self._extract_urls(data)
            if not image_urls:
                raise ValueError(f"No images in flux-fill response: {list(data.keys())}")
            elapsed = time.time() - start
            return {
                "image_url":       image_urls[0],
                "all_urls":        image_urls,
                "image_b64":       None,
                "metadata":        {},
                "success":         True,
                "backend":         "fal.ai",
                "model":           model_id,
                "generation_time": elapsed,
            }
        except httpx.HTTPStatusError as e:
            logger.error("[fal/fill] HTTP %d: %s", e.response.status_code, e.response.text[:300])
            return self._error(model_id, f"HTTP {e.response.status_code}: {e.response.text[:200]}", time.time() - start)
        except Exception as e:
            logger.error("[fal/fill] error: %s", e)
            return self._error(model_id, str(e), time.time() - start)

    async def close(self):
        if self._http and not self._http.is_closed:
            await self._http.aclose()


# Singleton
fal_client = FalClient()
