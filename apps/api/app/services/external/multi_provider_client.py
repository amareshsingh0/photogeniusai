"""
Multi-Provider Client — Automatic cheapest provider routing with failover.

Strategy:
  Same model → always use cheapest available provider.
  If primary fails → auto-failover to next provider.
  User never sees provider errors.

Provider priority (cheapest first per model):
  Flux Schnell:   Fireworks ($0.0014) → fal.ai ($0.003) → Replicate ($0.003)
  Flux 2 Dev:     fal.ai ($0.012) → Together AI ($0.015) → Replicate ($0.025)
  Flux 2 Pro:     fal.ai ($0.03) → Together AI ($0.03) → Replicate ($0.04)
  Flux Kontext:   fal.ai ($0.04) → Together AI ($0.04) → BFL Direct ($0.04)
  Ideogram v3:    fal.ai ($0.03-0.09) → Replicate ($0.03-0.09)
  Recraft v4:     fal.ai ($0.04-0.08) → Replicate ($0.04-0.08)

Requires (in .env.local):
  FAL_KEY              — fal.ai (primary for most models)
  FIREWORKS_API_KEY    — cheapest Schnell ($0.0014)
  TOGETHER_API_KEY     — Flux 2 Pro/Dev fallback
  REPLICATE_API_TOKEN  — last resort fallback

Cost per model (approx, 1024×1024):
  flux_schnell   → $0.0014 = ₹0.12  (Fireworks primary)
  flux_2_dev     → $0.012  = ₹1.01  (fal.ai primary)
  flux_2_pro     → $0.030  = ₹2.52  (fal.ai primary)
  flux_2_max     → $0.070  = ₹5.88  (fal.ai only)
  flux_kontext   → $0.040  = ₹3.36  (fal.ai primary)
  ideogram_turbo → $0.030  = ₹2.52  (fal.ai primary)
  ideogram_qual  → $0.090  = ₹7.56  (fal.ai primary)
  recraft_svg    → $0.080  = ₹6.72  (fal.ai primary)
  real_esrgan    → $0.002  = ₹0.17  (fal.ai only)
"""

from __future__ import annotations

import logging
import os
import time
from typing import Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# ── Provider API configs ───────────────────────────────────────────────────────

_FAL_BASE       = "https://fal.run"
_FIREWORKS_BASE = "https://api.fireworks.ai/inference/v1"
_TOGETHER_BASE  = "https://api.together.xyz/v1"
_REPLICATE_BASE = "https://api.replicate.com/v1"
_BFL_BASE       = "https://api.bfl.ai/v1"                  # Black Forest Labs official
_KIE_BASE       = "https://api.kie.ai/api/v1/jobs"         # kie.ai — Flux 2 Pro $0.025
_PIXAZO_BASE    = "https://gateway.pixazo.ai"              # Pixazo — Schnell $0.0012, 100 free/day

# Provider → env var
_PROVIDER_KEYS = {
    "fal":       "FAL_KEY",
    "fireworks": "FIREWORKS_API_KEY",
    "together":  "TOGETHER_API_KEY",
    "replicate": "REPLICATE_API_TOKEN",
    "bfl":       "BFL_API_KEY",          # api.bfl.ai — flux-2-max official
    "kie":       "KIE_API_KEY",          # kie.ai — Flux 2 Pro cheapest ($0.025)
    "pixazo":    "PIXAZO_API_KEY",       # pixazo.ai — Flux Schnell cheapest ($0.0012)
}

# ── Model routing table — ordered by cheapest provider ────────────────────────
# Format: model_key → list of (provider, provider_model_id, cost_usd)
# First entry = cheapest / primary. Rest = ordered fallbacks.

MODEL_PROVIDER_CHAIN: Dict[str, List[tuple]] = {
    # ── Flux Schnell — pixazo cheapest ($0.0012) + 100 free/day, Fireworks fallback
    "flux_schnell": [
        ("pixazo",   "flux-schnell",                              0.0012),
        ("fireworks","accounts/fireworks/models/flux-1-schnell-fp8", 0.0014),
        ("fal",      "fal-ai/flux/schnell",                       0.003),
        ("replicate","black-forest-labs/flux-schnell",            0.003),
    ],
    # ── Flux 2 Dev — Together AI primary ($0.010)
    "flux_2_dev": [
        ("together", "black-forest-labs/FLUX.1-dev",  0.010),
        ("fal",      "fal-ai/flux-2",                 0.012),
        ("replicate","black-forest-labs/flux-dev",    0.025),
    ],
    # ── Flux 2 Turbo — fal.ai only
    "flux_2_turbo": [
        ("fal",      "fal-ai/flux-2/turbo",  0.008),
        ("fal",      "fal-ai/flux-2",        0.012),   # fallback to dev if turbo fails
    ],
    # ── Flux 2 Pro — kie.ai cheapest ($0.025), fal.ai fallback ($0.030)
    "flux_2_pro": [
        ("kie",      "flux-2/pro-text-to-image",       0.025),
        ("fal",      "fal-ai/flux-2-pro",              0.030),
        ("together", "black-forest-labs/FLUX.1.1-pro", 0.040),
        ("replicate","black-forest-labs/flux-1.1-pro", 0.040),
    ],
    # ── Flux 2 Max — BFL official primary ($0.060), fal.ai fallback ($0.070)
    "flux_2_max": [
        ("bfl",      "flux-1.1-ultra",    0.060),   # api.bfl.ai official
        ("fal",      "fal-ai/flux-2-max", 0.070),
    ],
    # ── Flux Kontext Pro — fal.ai primary
    "flux_kontext": [
        ("fal",      "fal-ai/flux-pro/kontext",              0.040),
        ("together", "black-forest-labs/FLUX.1-kontext-pro", 0.040),
    ],
    "flux_kontext_max": [
        ("fal",      "fal-ai/flux-pro/kontext/max",    0.080),
        ("bfl",      "flux-kontext-max",               0.080),
    ],
    # ── Flux Fill (inpainting) — fal.ai
    "flux_fill": [
        ("fal",      "fal-ai/flux-pro/fill",           0.050),
    ],
    # ── Ideogram v3 — fal.ai
    "ideogram_turbo": [
        ("fal",      "fal-ai/ideogram/v3",             0.030),
    ],
    "ideogram_quality": [
        ("fal",      "fal-ai/ideogram/v3",             0.090),
    ],
    # ── Recraft v4 — fal.ai
    "recraft_v4": [
        ("fal",      "fal-ai/recraft/v4/text-to-image",     0.040),
    ],
    "recraft_v4_svg": [
        ("fal",      "fal-ai/recraft/v4/text-to-vector",    0.080),
    ],
    # ── Hunyuan Image — anime/Asian styles — fal.ai
    "hunyuan_image": [
        ("fal",      "fal-ai/hunyuan/image",           0.030),
    ],
    # ── Real-ESRGAN upscale — fal.ai
    "real_esrgan": [
        ("fal",      "fal-ai/real-esrgan",             0.002),
        ("replicate","nightmareai/real-esrgan",        0.001),
    ],
}

# Models that need special payload handling
_SCHNELL_IDS  = {"fal-ai/flux/schnell", "accounts/fireworks/models/flux-1-schnell-fp8"}
_IDEOGRAM_IDS = {"fal-ai/ideogram/v3"}
_RECRAFT_IDS  = {"fal-ai/recraft/v4/text-to-image", "fal-ai/recraft/v4/text-to-vector"}
_KONTEXT_IDS  = {"fal-ai/flux-pro/kontext", "fal-ai/flux-pro/kontext/max"}


class MultiProviderClient:
    """
    Auto-routing image generation client.

    Picks the cheapest provider for each model.
    Falls back to next provider on failure.
    Unified response contract regardless of provider.

    Usage:
        result = await multi_client.generate("flux_schnell", prompt="...")
        result = await multi_client.upscale(image_url="...")
    """

    def __init__(self):
        self._clients: Dict[str, httpx.AsyncClient] = {}
        self._keys = {p: os.getenv(env, "") for p, env in _PROVIDER_KEYS.items()}
        self._log_missing_keys()

    def _log_missing_keys(self):
        for provider, key in self._keys.items():
            if not key:
                logger.debug("[multi] %s key not set — that provider will be skipped", provider)

    def _provider_enabled(self, provider: str) -> bool:
        """Check feature flag for provider. Missing flag = enabled by default."""
        flag_map = {
            "together":  "USE_TOGETHER",
            "bfl":       "USE_BFL",
            "kie":       "USE_KIE",
            "pixazo":    "USE_PIXAZO",
            "fireworks": "USE_FIREWORKS",
        }
        env_var = flag_map.get(provider)
        if env_var is None:
            return True   # fal, replicate — always on
        return os.getenv(env_var, "true").lower() not in ("false", "0", "off")

    def _get_client(self, provider: str) -> httpx.AsyncClient:
        if provider not in self._clients or self._clients[provider].is_closed:
            key = self._keys.get(provider, "")
            auth_header = (
                f"Key {key}"       if provider == "fal"       else
                f"Bearer {key}"    if provider in ("fireworks", "together") else
                f"Token {key}"     if provider == "replicate"  else
                ""
            )
            self._clients[provider] = httpx.AsyncClient(
                timeout=httpx.Timeout(connect=10, read=300, write=30, pool=5),
                headers={"Authorization": auth_header, "Content-Type": "application/json"},
            )
        return self._clients[provider]

    # ── Main generate with auto-failover ──────────────────────────────────────

    async def generate(
        self,
        model_key: str,
        prompt: str,
        negative_prompt: str = "",
        num_images: int = 1,
        image_size: str = "square_hd",
        num_inference_steps: int = 28,
        guidance_scale: float = 3.5,
        seed: Optional[int] = None,
        reference_image_url: Optional[str] = None,
        rendering_speed: str = "BALANCED",
        style: Optional[str] = None,
    ) -> Dict:
        """
        Generate image with automatic cheapest provider + failover.
        model_key = key from MODEL_PROVIDER_CHAIN (e.g. "flux_schnell", "flux_2_pro")
        """
        chain = MODEL_PROVIDER_CHAIN.get(model_key)
        if not chain:
            return self._error(model_key, f"Unknown model_key: {model_key}", 0.0)

        last_error = "No providers available"
        for provider, model_id, cost_usd in chain:
            if not self._provider_enabled(provider):
                logger.debug("[multi] skip %s — disabled via flag", provider)
                continue
            key = self._keys.get(provider, "")
            if not key:
                logger.debug("[multi] skip %s — no API key", provider)
                continue

            logger.info("[multi] trying %s / %s (cost=$%.4f)", provider, model_id, cost_usd)
            result = await self._call_provider(
                provider=provider,
                model_id=model_id,
                prompt=prompt,
                negative_prompt=negative_prompt,
                num_images=num_images,
                image_size=image_size,
                num_inference_steps=num_inference_steps,
                guidance_scale=guidance_scale,
                seed=seed,
                reference_image_url=reference_image_url,
                rendering_speed=rendering_speed,
                style=style,
            )
            if result["success"]:
                result["provider"] = provider
                result["cost_usd"] = cost_usd
                result["cost_inr"] = round(cost_usd * 84, 2)
                logger.info("[multi] OK provider=%s model=%s cost=$%.4f",
                            provider, model_id, cost_usd)
                return result

            last_error = result.get("metadata", {}).get("error", "unknown")
            logger.warning("[multi] %s failed (%s), trying next provider", provider, last_error)

        return self._error(model_key, f"All providers failed. Last: {last_error}", 0.0)

    # ── Upscale (ESRGAN) ──────────────────────────────────────────────────────

    async def upscale(self, image_url: str, scale: int = 4) -> Dict:
        """4x upscale — fal.ai ESRGAN primary, Replicate fallback."""
        chain = MODEL_PROVIDER_CHAIN.get("real_esrgan", [])
        last_error = "No providers"
        for provider, model_id, cost_usd in chain:
            key = self._keys.get(provider, "")
            if not key:
                continue
            result = await self._upscale_fal(image_url, scale) if provider == "fal" \
                else await self._upscale_replicate(image_url, scale)
            if result["success"]:
                result["provider"] = provider
                result["cost_usd"] = cost_usd
                return result
            last_error = result.get("metadata", {}).get("error", "unknown")
        return self._error("real_esrgan", f"Upscale failed: {last_error}", 0.0)

    # ── Provider-specific callers ─────────────────────────────────────────────

    async def _call_provider(self, provider: str, model_id: str, **kwargs) -> Dict:
        if provider == "fal":
            return await self._call_fal(model_id, **kwargs)
        elif provider == "fireworks":
            return await self._call_fireworks(model_id, **kwargs)
        elif provider == "together":
            return await self._call_together(model_id, **kwargs)
        elif provider == "replicate":
            return await self._call_replicate(model_id, **kwargs)
        elif provider == "bfl":
            return await self._call_bfl(model_id, **kwargs)
        elif provider == "kie":
            return await self._call_kie(model_id, **kwargs)
        elif provider == "pixazo":
            return await self._call_pixazo(model_id, **kwargs)
        return self._error(model_id, f"Unknown provider: {provider}", 0.0)

    async def _call_fal(self, model_id: str, prompt: str, negative_prompt: str,
                        num_images: int, image_size: str, num_inference_steps: int,
                        guidance_scale: float, seed, reference_image_url,
                        rendering_speed: str, style) -> Dict:
        start = time.time()
        client = self._get_client("fal")
        payload = self._build_fal_payload(
            model_id, prompt, negative_prompt, num_images, image_size,
            num_inference_steps, guidance_scale, seed, reference_image_url,
            rendering_speed, style
        )
        try:
            resp = await client.post(f"https://fal.run/{model_id}", json=payload)
            resp.raise_for_status()
            data = resp.json()
            urls = self._extract_fal_urls(data)
            if not urls:
                raise ValueError(f"No images returned: {list(data.keys())}")
            return self._ok(urls, model_id, "fal.ai", time.time() - start)
        except Exception as e:
            return self._error(model_id, str(e), time.time() - start)

    async def _call_fireworks(self, model_id: str, prompt: str, negative_prompt: str,
                              num_images: int, image_size: str, num_inference_steps: int,
                              guidance_scale: float, seed, **kwargs) -> Dict:
        """Fireworks AI — OpenAI-compatible images API."""
        start = time.time()
        client = self._get_client("fireworks")
        # Fireworks uses OpenAI-compatible /images/generations
        size_map = {
            "square_hd": "1024x1024", "landscape_16_9": "1280x720",
            "portrait_9_16": "720x1280", "landscape_4_3": "1024x768",
        }
        payload = {
            "model": model_id,
            "prompt": prompt,
            "n": num_images,
            "size": size_map.get(image_size, "1024x1024"),
            "steps": min(num_inference_steps, 12),   # schnell max 12
        }
        if negative_prompt:
            payload["negative_prompt"] = negative_prompt
        if seed is not None:
            payload["seed"] = seed
        try:
            resp = await client.post(f"{_FIREWORKS_BASE}/images/generations", json=payload)
            resp.raise_for_status()
            data = resp.json()
            urls = [item.get("url") for item in data.get("data", []) if item.get("url")]
            if not urls:
                raise ValueError(f"No images from Fireworks: {data}")
            return self._ok(urls, model_id, "fireworks.ai", time.time() - start)
        except Exception as e:
            return self._error(model_id, str(e), time.time() - start)

    async def _call_together(self, model_id: str, prompt: str, negative_prompt: str,
                             num_images: int, image_size: str, num_inference_steps: int,
                             guidance_scale: float, seed, **kwargs) -> Dict:
        """Together AI — OpenAI-compatible images API."""
        start = time.time()
        client = self._get_client("together")
        size_map = {
            "square_hd": "1024x1024", "landscape_16_9": "1280x720",
            "portrait_9_16": "720x1280",
        }
        payload = {
            "model": model_id,
            "prompt": prompt,
            "n": num_images,
            "size": size_map.get(image_size, "1024x1024"),
            "steps": num_inference_steps,
            "guidance_scale": guidance_scale,
        }
        if negative_prompt:
            payload["negative_prompt"] = negative_prompt
        if seed is not None:
            payload["seed"] = seed
        try:
            resp = await client.post(f"{_TOGETHER_BASE}/images/generations", json=payload)
            resp.raise_for_status()
            data = resp.json()
            urls = [item.get("url") or item.get("b64_json")
                    for item in data.get("data", []) if item]
            urls = [u for u in urls if u]
            if not urls:
                raise ValueError(f"No images from Together: {data}")
            return self._ok(urls, model_id, "together.ai", time.time() - start)
        except Exception as e:
            return self._error(model_id, str(e), time.time() - start)

    async def _call_replicate(self, model_id: str, prompt: str, negative_prompt: str,
                              num_images: int, image_size: str, num_inference_steps: int,
                              guidance_scale: float, seed, **kwargs) -> Dict:
        """Replicate — submit prediction + poll."""
        import asyncio
        start = time.time()
        client = self._get_client("replicate")
        size_map = {"square_hd": (1024, 1024), "landscape_16_9": (1280, 720),
                    "portrait_9_16": (720, 1280)}
        w, h = size_map.get(image_size, (1024, 1024))
        input_data: Dict = {
            "prompt": prompt,
            "num_outputs": num_images,
            "width": w, "height": h,
            "num_inference_steps": num_inference_steps,
            "guidance_scale": guidance_scale,
        }
        if negative_prompt:
            input_data["negative_prompt"] = negative_prompt
        if seed is not None:
            input_data["seed"] = seed
        try:
            sub = await client.post(
                f"{_REPLICATE_BASE}/models/{model_id}/predictions",
                json={"input": input_data},
            )
            sub.raise_for_status()
            prediction_id = sub.json()["id"]
            poll_url = f"{_REPLICATE_BASE}/predictions/{prediction_id}"

            waited = 0
            while waited < 120:
                await asyncio.sleep(3)
                waited += 3
                res = await client.get(poll_url)
                res.raise_for_status()
                pred = res.json()
                status = pred.get("status", "")
                if status == "succeeded":
                    output = pred.get("output", [])
                    urls = output if isinstance(output, list) else [output]
                    urls = [u for u in urls if u]
                    if not urls:
                        raise ValueError("No output URLs from Replicate")
                    return self._ok(urls, model_id, "replicate.com", time.time() - start)
                elif status == "failed":
                    raise RuntimeError(pred.get("error", "Replicate prediction failed"))

            raise TimeoutError("Replicate timed out after 120s")
        except Exception as e:
            return self._error(model_id, str(e), time.time() - start)

    async def _call_kie(self, model_id: str, prompt: str, negative_prompt: str,
                        num_images: int, image_size: str, num_inference_steps: int,
                        guidance_scale: float, seed, **kwargs) -> Dict:
        """kie.ai — Flux 2 Pro cheapest ($0.025). Bearer token auth."""
        import asyncio
        start = time.time()
        client = self._get_client("kie")
        size_map = {
            "square_hd": "1024*1024", "landscape_16_9": "1344*768",
            "portrait_9_16": "768*1344", "landscape_4_3": "1152*896",
        }
        payload: Dict = {
            "model": model_id,
            "taskType": "txt2img",
            "input": {
                "prompt": prompt,
                "imageSize": size_map.get(image_size, "1024*1024"),
                "numInferenceSteps": num_inference_steps,
                "guidanceScale": guidance_scale,
                "outputFormat": "jpeg",
            }
        }
        if negative_prompt:
            payload["input"]["negativePrompt"] = negative_prompt
        if seed is not None:
            payload["input"]["seed"] = seed
        try:
            sub = await client.post(f"{_KIE_BASE}/createTask", json=payload)
            sub.raise_for_status()
            resp_data = sub.json()
            task_id = (resp_data.get("data") or {}).get("taskId")
            if not task_id:
                raise ValueError(f"No taskId from kie.ai: {resp_data}")

            waited = 0
            while waited < 120:
                await asyncio.sleep(3)
                waited += 3
                res = await client.get(f"{_KIE_BASE}/getTask", params={"taskId": task_id})
                res.raise_for_status()
                data = res.json().get("data", {})
                status = data.get("status", "")
                if status in ("SUCCESS", "COMPLETED", "success"):
                    outputs = data.get("output") or data.get("outputs") or []
                    if isinstance(outputs, list):
                        urls = [o.get("url") or o if isinstance(o, str) else None for o in outputs]
                    else:
                        urls = [outputs] if outputs else []
                    urls = [u for u in urls if u]
                    if not urls:
                        raise ValueError(f"No output URLs from kie.ai: {data}")
                    return self._ok(urls, model_id, "kie.ai", time.time() - start)
                elif status in ("FAILED", "ERROR", "failed"):
                    raise RuntimeError(f"kie.ai task failed: {data}")

            raise TimeoutError("kie.ai timed out after 120s")
        except Exception as e:
            logger.error("[kie] error: %s", e)
            return self._error(model_id, str(e), time.time() - start)

    async def _call_pixazo(self, model_id: str, prompt: str, negative_prompt: str,
                           num_images: int, image_size: str, num_inference_steps: int,
                           guidance_scale: float, seed, **kwargs) -> Dict:
        """pixazo.ai — Flux Schnell cheapest ($0.0012), 100 free/day. Subscription-key auth."""
        start = time.time()
        key = self._keys.get("pixazo", "")
        # Pixazo uses Ocp-Apim-Subscription-Key header (not standard Bearer)
        client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10, read=120, write=30, pool=5),
            headers={"Ocp-Apim-Subscription-Key": key, "Content-Type": "application/json"},
        )
        size_map = {
            "square_hd": {"width": 1024, "height": 1024},
            "landscape_16_9": {"width": 1344, "height": 768},
            "portrait_9_16": {"width": 768, "height": 1344},
        }
        dims = size_map.get(image_size, {"width": 1024, "height": 1024})
        payload: Dict = {
            "prompt": prompt,
            "num_inference_steps": min(num_inference_steps, 12),  # schnell max 12
            "num_images": num_images,
            **dims,
        }
        if negative_prompt:
            payload["negative_prompt"] = negative_prompt
        if seed is not None:
            payload["seed"] = seed
        try:
            resp = await client.post(f"{_PIXAZO_BASE}/generateT2I", json=payload)
            resp.raise_for_status()
            data = resp.json()
            # Pixazo returns images array with url or base64
            images = data.get("images") or data.get("data") or []
            urls = []
            for img in images:
                if isinstance(img, dict):
                    url = img.get("url") or img.get("image_url")
                    if url:
                        urls.append(url)
                elif isinstance(img, str) and img.startswith("http"):
                    urls.append(img)
            if not urls:
                raise ValueError(f"No images from pixazo: {list(data.keys())}")
            return self._ok(urls, model_id, "pixazo.ai", time.time() - start)
        except Exception as e:
            logger.error("[pixazo] error: %s", e)
            return self._error(model_id, str(e), time.time() - start)
        finally:
            await client.aclose()

    async def _call_bfl(self, model_id: str, prompt: str, negative_prompt: str,
                        num_images: int, image_size: str, num_inference_steps: int,
                        guidance_scale: float, seed, **kwargs) -> Dict:
        """Black Forest Labs official API — api.bfl.ai (flux-2-max, flux-kontext-max)."""
        import asyncio
        start = time.time()
        client = self._get_client("bfl")
        size_map = {
            "square_hd": {"width": 1024, "height": 1024},
            "landscape_16_9": {"width": 1344, "height": 768},
            "portrait_9_16": {"width": 768, "height": 1344},
            "landscape_4_3": {"width": 1152, "height": 896},
        }
        dims = size_map.get(image_size, {"width": 1024, "height": 1024})
        payload: Dict = {
            "prompt": prompt,
            "width": dims["width"],
            "height": dims["height"],
            "steps": num_inference_steps,
            "guidance": guidance_scale,
            "output_format": "jpeg",
        }
        if negative_prompt:
            payload["negative_prompt"] = negative_prompt
        if seed is not None:
            payload["seed"] = seed
        try:
            # BFL uses async polling: POST → get id → poll /get_result
            sub = await client.post(f"{_BFL_BASE}/{model_id}", json=payload)
            sub.raise_for_status()
            task_id = sub.json().get("id")
            if not task_id:
                raise ValueError(f"No task id from BFL: {sub.json()}")

            waited = 0
            while waited < 120:
                await asyncio.sleep(3)
                waited += 3
                res = await client.get(f"{_BFL_BASE}/get_result", params={"id": task_id})
                res.raise_for_status()
                data = res.json()
                status = data.get("status", "")
                if status == "Ready":
                    url = (data.get("result") or {}).get("sample")
                    if not url:
                        raise ValueError(f"No sample URL in BFL result: {data}")
                    return self._ok([url], model_id, "api.bfl.ai", time.time() - start)
                elif status in ("Error", "Failed", "Content Moderated"):
                    raise RuntimeError(f"BFL task {status}: {data}")

            raise TimeoutError("BFL API timed out after 120s")
        except Exception as e:
            logger.error("[bfl] error: %s", e)
            return self._error(model_id, str(e), time.time() - start)

    async def _upscale_fal(self, image_url: str, scale: int) -> Dict:
        start = time.time()
        client = self._get_client("fal")
        try:
            resp = await client.post(
                "https://fal.run/fal-ai/real-esrgan",
                json={"image_url": image_url, "scale": scale, "face_enhance": True},
            )
            resp.raise_for_status()
            data = resp.json()
            url = (data.get("image") or {}).get("url") or data.get("output_url")
            return self._ok([url] if url else [], "fal-ai/real-esrgan", "fal.ai", time.time() - start)
        except Exception as e:
            return self._error("fal-ai/real-esrgan", str(e), time.time() - start)

    async def _upscale_replicate(self, image_url: str, scale: int) -> Dict:
        start = time.time()
        client = self._get_client("replicate")
        try:
            import asyncio
            sub = await client.post(
                f"{_REPLICATE_BASE}/models/nightmareai/real-esrgan/predictions",
                json={"input": {"image": image_url, "scale": scale, "face_enhance": False}},
            )
            sub.raise_for_status()
            pid = sub.json()["id"]
            waited = 0
            while waited < 60:
                await asyncio.sleep(3)
                waited += 3
                res = await client.get(f"{_REPLICATE_BASE}/predictions/{pid}")
                pred = res.json()
                if pred.get("status") == "succeeded":
                    url = pred.get("output")
                    return self._ok([url] if url else [], "nightmareai/real-esrgan",
                                    "replicate.com", time.time() - start)
                if pred.get("status") == "failed":
                    break
            raise RuntimeError("Replicate upscale failed/timed out")
        except Exception as e:
            return self._error("real-esrgan", str(e), time.time() - start)

    # ── Payload builder (fal.ai specific) ─────────────────────────────────────

    @staticmethod
    def _build_fal_payload(model_id, prompt, negative_prompt, num_images, image_size,
                           steps, guidance, seed, reference_image_url,
                           rendering_speed, style) -> Dict:
        if model_id in _IDEOGRAM_IDS:
            p: Dict = {
                "prompt": prompt, "image_size": image_size,
                "num_images": num_images, "rendering_speed": rendering_speed,
            }
            if negative_prompt:
                p["negative_prompt"] = negative_prompt
            return p

        if model_id in _RECRAFT_IDS:
            p = {"prompt": prompt, "image_size": image_size, "n": num_images}
            if style:
                p["style"] = style
            return p

        if model_id in _KONTEXT_IDS:
            p = {"prompt": prompt, "image_size": image_size, "num_images": num_images}
            if reference_image_url:
                p["image_url"] = reference_image_url
            return p

        # Standard Flux payload
        if model_id in _SCHNELL_IDS:
            steps = min(steps, 12)
        p = {
            "prompt": prompt, "image_size": image_size,
            "num_inference_steps": steps, "num_images": num_images,
            "enable_safety_checker": False, "output_format": "jpeg",
        }
        if model_id not in _SCHNELL_IDS:
            p["guidance_scale"] = guidance
        if negative_prompt:
            p["negative_prompt"] = negative_prompt
        if seed is not None:
            p["seed"] = seed
        if reference_image_url:
            p["image_url"] = reference_image_url
        return p

    # ── Response helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _extract_fal_urls(data: Dict) -> List[str]:
        images = data.get("images") or data.get("output") or []
        if isinstance(images, list):
            urls = []
            for img in images:
                url = img.get("url") if isinstance(img, dict) else img
                if url:
                    urls.append(url)
            return urls
        single = data.get("image")
        if isinstance(single, dict):
            url = single.get("url")
            return [url] if url else []
        return []

    @staticmethod
    def _ok(urls: List[str], model: str, backend: str, elapsed: float) -> Dict:
        return {
            "image_url": urls[0] if urls else None,
            "all_urls": urls, "image_b64": None,
            "metadata": {}, "success": bool(urls),
            "backend": backend, "model": model,
            "generation_time": elapsed,
        }

    @staticmethod
    def _error(model: str, msg: str, elapsed: float) -> Dict:
        return {
            "image_url": None, "all_urls": [], "image_b64": None,
            "metadata": {"error": msg}, "success": False,
            "backend": "multi_provider", "model": model,
            "generation_time": elapsed,
        }

    async def close(self):
        for client in self._clients.values():
            if not client.is_closed:
                await client.aclose()

    def get_cheapest_cost(self, model_key: str) -> Optional[float]:
        """Returns cheapest available cost in USD for a model_key (based on available keys)."""
        chain = MODEL_PROVIDER_CHAIN.get(model_key, [])
        for provider, _, cost in chain:
            if self._keys.get(provider):
                return cost
        return None


# Singleton
multi_client = MultiProviderClient()
