"""
Ensemble + Judge Pipeline

Strategy per tier (bucket-aware via BUCKET_MODEL_MAP):
  FAST:     1× model from config → output                           (no ESRGAN)
  STANDARD: 1× model from config → ESRGAN 2x upscale               (+₹0.17)
  PREMIUM:  1× best model from config → ESRGAN 4x upscale          (+₹0.17)
  ULTRA:    N× best model → jury picks best → ESRGAN 4x upscale    (+₹0.17)
            num_images per bucket set in BUCKET_MODEL_MAP ultra rows

Jury is ONLY in ULTRA tier. ESRGAN in STANDARD / PREMIUM / ULTRA.

Prompt cache:
  hash(prompt[:100] + tier + bucket) → TTL 24h in-memory
  Hit → skip Gemini call, reuse enhanced prompt
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import time
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Prompt cache (in-memory, TTL 24h) ─────────────────────────────────────────
_PROMPT_CACHE: Dict[str, Tuple[Dict, float]] = {}
_CACHE_TTL = 86400  # 24 hours


def _cache_key(prompt: str, tier: str, bucket: str) -> str:
    raw = f"{prompt[:100]}|{tier}|{bucket}"
    return hashlib.md5(raw.encode()).hexdigest()


def _cache_get(key: str) -> Optional[Dict]:
    entry = _PROMPT_CACHE.get(key)
    if entry and (time.time() - entry[1]) < _CACHE_TTL:
        return entry[0]
    if entry:
        del _PROMPT_CACHE[key]
    return None


def _cache_set(key: str, value: Dict):
    _PROMPT_CACHE[key] = (value, time.time())
    if len(_PROMPT_CACHE) > 500:
        sorted_keys = sorted(_PROMPT_CACHE, key=lambda k: _PROMPT_CACHE[k][1])
        for k in sorted_keys[:100]:
            del _PROMPT_CACHE[k]


# ── Image quality scorer ───────────────────────────────────────────────────────

def _score_image_url(image_url: str) -> float:
    """
    Fast heuristic score. Returns 0.0–1.0.
    CDN URLs: return neutral 0.7 (no pixel access).
    data URI: run poster_jury if available.
    """
    if not image_url:
        return 0.0
    if image_url.startswith("data:image"):
        try:
            from app.services.smart.poster_jury import poster_jury
            verdict = poster_jury.evaluate(
                image_b64=image_url,
                visual_balance=0.5,
                total_text_area=0.0,
                has_text=False,
                is_ad=False,
                subject_x=0.5,
                subject_y=0.5,
            )
            return verdict["overall_score"]
        except Exception:
            return 0.7
    return 0.7


def _pick_best(results: List[Dict]) -> Dict:
    """Pick highest-scoring result from ensemble list."""
    successful = [r for r in results if r.get("success") and r.get("image_url")]
    if not successful:
        return results[0] if results else {"success": False, "metadata": {"error": "all candidates failed"}}
    if len(successful) == 1:
        return successful[0]

    scored = [((_score_image_url(r["image_url"])), r) for r in successful]
    scored.sort(key=lambda x: x[0], reverse=True)
    best_score, best = scored[0]
    logger.info("[ensemble] jury: best score=%.3f from %d candidates", best_score, len(scored))
    best["jury_score"] = best_score
    best["candidates_count"] = len(successful)
    return best


# ── ESRGAN helper ──────────────────────────────────────────────────────────────

async def _apply_esrgan(result: Dict, scale: int) -> Dict:
    """Apply ESRGAN upscale to a generation result. Returns result (modified in-place)."""
    if not result.get("success") or not result.get("image_url"):
        return result
    try:
        from app.services.external.multi_provider_client import multi_client
        up = await multi_client.upscale(result["image_url"], scale=scale)
        if up.get("success") and up.get("image_url"):
            result["image_url"] = up["image_url"]
            result["upscaled"] = True
            result["upscale_scale"] = scale
            logger.info("[ensemble] ESRGAN %dx OK", scale)
        else:
            logger.warning("[ensemble] ESRGAN %dx failed, using original", scale)
            result["upscaled"] = False
    except Exception as e:
        logger.warning("[ensemble] ESRGAN error: %s", e)
        result["upscaled"] = False
    return result


# ── Main entry point ───────────────────────────────────────────────────────────

async def run_ensemble(
    tier: str,
    bucket: str,
    prompt: str,
    negative_prompt: str,
    image_size: str,
    reference_image_url: Optional[str],
    rendering_speed: str,
) -> Dict:
    """
    Run generation based on tier + bucket.

    FAST     → 1× model, no post-processing
    STANDARD → 1× model + ESRGAN 2x
    PREMIUM  → 1× best model + ESRGAN 4x
    ULTRA    → N× jury + ESRGAN 4x  (N = num_images in config)
    """
    from app.services.smart.config import get_model_config, TIER_ALIASES
    from app.services.external.multi_provider_client import multi_client

    resolved_tier = TIER_ALIASES.get(tier, tier).lower()
    model_cfg = get_model_config(bucket, resolved_tier)
    model_key  = model_cfg.get("model", "flux_2_pro")
    num_images = model_cfg.get("num_images", 1)   # >1 only in ultra rows

    t_start = time.time()
    logger.info("[ensemble] tier=%s bucket=%s model=%s num=%d",
                resolved_tier, bucket, model_key, num_images)

    # ── Common generate kwargs ─────────────────────────────────────────────────
    gen_kwargs = dict(
        model_key=model_key,
        prompt=prompt,
        negative_prompt=negative_prompt,
        image_size=image_size,
        num_images=1,
        num_inference_steps=8 if resolved_tier == "fast" else 28,
        guidance_scale=3.5,
        reference_image_url=reference_image_url,
        rendering_speed=rendering_speed,
    )

    # ── FAST: single, no ESRGAN ────────────────────────────────────────────────
    if resolved_tier == "fast":
        result = await multi_client.generate(**gen_kwargs)
        result["ensemble_strategy"] = f"single_{model_key}"
        result["ensemble_time"]     = round(time.time() - t_start, 2)
        return result

    # ── STANDARD: single + ESRGAN 2x ──────────────────────────────────────────
    if resolved_tier == "standard":
        result = await multi_client.generate(**gen_kwargs)
        result = await _apply_esrgan(result, scale=2)
        result["ensemble_strategy"] = f"single_{model_key}_esrgan2x"
        result["ensemble_time"]     = round(time.time() - t_start, 2)
        return result

    # ── PREMIUM: single best + ESRGAN 4x ──────────────────────────────────────
    if resolved_tier in ("premium", "quality"):
        result = await multi_client.generate(**gen_kwargs)
        result = await _apply_esrgan(result, scale=4)
        result["ensemble_strategy"] = f"single_{model_key}_esrgan4x"
        result["ensemble_time"]     = round(time.time() - t_start, 2)
        return result

    # ── ULTRA: N× jury + ESRGAN 4x ────────────────────────────────────────────
    if resolved_tier == "ultra":
        # ── Cost guardrail: estimate total API cost before firing parallel calls ──
        from app.services.external.multi_provider_client import MODEL_PROVIDER_CHAIN
        model_chain = MODEL_PROVIDER_CHAIN.get(model_key, [])
        per_image_cost = model_chain[0][2] if model_chain else 0.10  # cheapest provider
        estimated_total = per_image_cost * num_images

        _ULTRA_COST_LIMIT_USD = float(os.getenv("ULTRA_COST_LIMIT_USD", "0.50"))
        if estimated_total > _ULTRA_COST_LIMIT_USD:
            # Silent downgrade to premium — log but don't expose to user
            logger.warning(
                "[ensemble] cost guardrail: ultra estimated $%.3f > limit $%.2f "
                "(model=%s ×%d) → downgrading to premium",
                estimated_total, _ULTRA_COST_LIMIT_USD, model_key, num_images,
            )
            result = await multi_client.generate(**gen_kwargs)
            result = await _apply_esrgan(result, scale=4)
            result["ensemble_strategy"] = f"guardrail_downgrade_{model_key}_esrgan4x"
            result["ensemble_time"]     = round(time.time() - t_start, 2)
            result["cost_guardrail_triggered"] = True
            return result

        tasks = [multi_client.generate(**gen_kwargs) for _ in range(num_images)]
        results = await asyncio.gather(*tasks, return_exceptions=False)
        best = _pick_best(list(results))
        best = await _apply_esrgan(best, scale=4)
        best["ensemble_strategy"] = f"jury_{model_key}x{num_images}_esrgan4x"
        best["ensemble_time"]     = round(time.time() - t_start, 2)
        return best

    # ── fallback → standard ────────────────────────────────────────────────────
    result = await multi_client.generate(**gen_kwargs)
    result = await _apply_esrgan(result, scale=2)
    result["ensemble_strategy"] = f"fallback_{model_key}_esrgan2x"
    result["ensemble_time"]     = round(time.time() - t_start, 2)
    return result
