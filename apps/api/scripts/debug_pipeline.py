"""Debug pipeline — runs every stage up to (but NOT including) image generation.

Mirrors the EXACT flow of generate_stream.py — honours USE_SIMPLE_ENGINE,
applies the sanitizer + word-cap + single-image anchor + anti-collage negatives,
and finally builds the per-provider JSON payload that would go to fal/google/
wavespeed.

Usage (from apps/api with venv active):
    python scripts/debug_pipeline.py "happy birthday poster for Rahul"
    python scripts/debug_pipeline.py "sunscreen ad" --quality 1k
    python scripts/debug_pipeline.py "chef portrait" --quality 2k --style photo

No HTTP call to any provider is made — safe and free to run.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

# Make apps/api importable when run as `python scripts/debug_pipeline.py`
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def dump(label: str, data) -> None:
    bar = "=" * 78
    print(f"\n{bar}\n{label}\n{bar}")
    if isinstance(data, (dict, list)):
        try:
            print(json.dumps(data, indent=2, ensure_ascii=False, default=str))
            return
        except Exception:
            pass
    print(data)


def _pick_size(w: int, h: int) -> str:
    if w == h:
        return "square_hd"
    r = w / h
    if r > 1.5:
        return "landscape_16_9"
    if r < 0.67:
        return "portrait_9_16"
    return "landscape_4_3"


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("prompt", help="User prompt")
    parser.add_argument("--quality", default="1k", choices=["1k", "2k", "4k"])
    parser.add_argument("--width", type=int, default=1024)
    parser.add_argument("--height", type=int, default=1024)
    parser.add_argument("--style", default=None)
    parser.add_argument("--bucket", default=None,
                        help="Force a bucket (skip auto-detection)")
    args = parser.parse_args()

    dump("INPUT", {
        "prompt": args.prompt,
        "quality": args.quality,
        "width":   args.width,
        "height":  args.height,
        "style":   args.style,
        "bucket_override": args.bucket,
    })

    # ── Stage 0 — intent ─────────────────────────────────────────────────
    from app.services.smart.intent_analyzer import intent_analyzer
    intent = await asyncio.to_thread(
        intent_analyzer.analyze, args.prompt, args.width, args.height
    )
    dump("STAGE 0 — INTENT", intent)

    # ── Stage 0.5 — bucket + model routing ───────────────────────────────
    from app.services.smart.config import detect_capability_bucket
    from app.services.smart.model_config import (
        get_model_for_request, normalize_quality_tier,
    )

    bucket = args.bucket or detect_capability_bucket(args.prompt)
    quality = normalize_quality_tier(args.quality)
    model_cfg = get_model_for_request(bucket, quality)
    fal_model_key = model_cfg.get("model_key") or model_cfg.get("model") or "unknown"
    dump("STAGE 0.5 — BUCKET + MODEL ROUTING", {
        "bucket":       bucket,
        "quality_tier": quality,
        "model_cfg":    model_cfg,
        "fal_model_key": fal_model_key,
    })

    # ── Stage 1 — engine selection (mirrors generate_stream.py:432-450) ──
    _simple_env = os.getenv("USE_SIMPLE_ENGINE", "").strip().lower()
    use_simple = _simple_env not in ("false", "0", "off", "no")
    print(f"\n[engine-flag] USE_SIMPLE_ENGINE env={_simple_env!r} → use_simple={use_simple}")

    params: dict
    brief: dict | None = None
    _simple_payload: dict | None = None

    if use_simple:
        from app.services.smart.simple_prompt_engine import simple_engine
        _simple_payload = await simple_engine.enrich(
            user_prompt=args.prompt,
            bucket=bucket,
            tier=quality,
            width=args.width,
            height=args.height,
            style=args.style,
            brand_kit=None,
        )
        dump("STAGE 1 — SIMPLE_ENGINE OUTPUT (raw from Haiku)", _simple_payload)
        params = {
            "prompt":           _simple_payload.get("prompt", args.prompt),
            "negative_prompt":  _simple_payload.get("negative_prompt", ""),
            "parameters":       {},
            "style_notes":      _simple_payload.get("intent", "")[:80],
            "_source":          _simple_payload.get("_source", "simple_engine"),
        }
    else:
        # Brief → params (4-agent for typography, claude_v2 otherwise)
        use_claude = os.getenv("USE_CLAUDE_ENGINE", "true").lower() != "false"
        if use_claude:
            from app.services.smart.claude_prompt_engine_v2 import (
                claude_prompt_engine as prompt_engine,
            )
        else:
            from app.services.smart.gemini_prompt_engine import (
                gemini_prompt_engine as prompt_engine,
            )
        if bucket == "typography":
            try:
                from app.services.smart.design_agent_chain import design_agent_chain
                brief = await design_agent_chain.arun(
                    prompt=args.prompt, brand_kit=None,
                    width=args.width, height=args.height, prompt_dna=None,
                )
                brief["_source"] = brief.get("_source") or "design_agent_chain"
            except Exception as e:
                print(f"[design_agent_chain] FAILED: {e} — falling back to claude")
                brief = await prompt_engine.create_brief(
                    args.prompt,
                    creative_type=intent.get("creative_type", "typography"),
                    style=args.style or "photo",
                    bucket=bucket, tier=quality,
                )
        else:
            brief = await prompt_engine.create_brief(
                args.prompt,
                creative_type=intent.get("creative_type", "photorealism"),
                style=args.style or "photo",
                bucket=bucket, tier=quality,
            )
        dump("STAGE 1A — CREATIVE BRIEF", brief)
        params = await prompt_engine.build_params(brief, fal_model_key, bucket)
        dump("STAGE 1B — PARAMS (from prompt_engine)", params)

    # ── Stage 2 — universal sanitizer + cap + anchor (generate_stream.py:572-615)
    from app.services.smart.simple_prompt_engine import (
        _sanitize_prompt, _ANTI_COLLAGE_NEGATIVES,
    )
    enhanced_prompt = params.get("prompt") or args.prompt
    negative_prompt = params.get("negative_prompt", "")

    pre_sanitize = enhanced_prompt
    enhanced_prompt = _sanitize_prompt(enhanced_prompt)
    sanitized_diff = len(pre_sanitize) - len(enhanced_prompt)

    pre_cap_words = enhanced_prompt.split()
    engine_source = (params.get("_source") or "").lower()
    if engine_source != "simple_engine" and len(pre_cap_words) > 220:
        truncated = " ".join(pre_cap_words[:220])
        last_term = max(truncated.rfind("."), truncated.rfind("!"), truncated.rfind("?"))
        if last_term > 200:
            truncated = truncated[: last_term + 1]
        enhanced_prompt = truncated

    _single_image_anchor = "ONE single unified image, one cohesive composition. "
    enhanced_prompt = _single_image_anchor + enhanced_prompt

    if not negative_prompt:
        negative_prompt = _ANTI_COLLAGE_NEGATIVES
    elif "design sheet, pitch deck" not in negative_prompt:
        negative_prompt = f"{negative_prompt}, {_ANTI_COLLAGE_NEGATIVES}"

    dump("STAGE 2 — UNIVERSAL DEFENSE (sanitize + cap + anchor + neg)", {
        "sanitizer_dropped_chars": sanitized_diff,
        "engine_source":           engine_source,
        "word_count_before_cap":   len(pre_cap_words),
        "word_count_after_cap":    len(enhanced_prompt.split()) - len(_single_image_anchor.split()),
        "cap_applied":             engine_source != "simple_engine" and len(pre_cap_words) > 220,
        "anchor_prepended":        True,
        "final_prompt":            enhanced_prompt,
        "final_negative_prompt":   negative_prompt,
    })

    # ── Stage 3 — pick provider + build the EXACT payload that gets POSTed ──
    # Source of truth for the actual provider URL is MODEL_PROVIDER_CHAIN in
    # multi_provider_client.py (NOT the `endpoint` alias on MODEL_REGISTRY).
    # Each chain entry = (provider, provider_model_id, cost). First = primary.
    from app.services.external.multi_provider_client import MODEL_PROVIDER_CHAIN
    chain = MODEL_PROVIDER_CHAIN.get(fal_model_key, [])
    if not chain:
        dump("STAGE 3 — ROUTING FAILED", {"reason": f"{fal_model_key!r} not in MODEL_PROVIDER_CHAIN"})
        return 1
    provider, provider_model_id, _cost = chain[0]

    image_size = _pick_size(args.width, args.height)
    num_images = model_cfg.get("num_images", 1)
    steps = params.get("num_inference_steps", 20)
    guidance = params.get("guidance_scale", 7.5)
    rendering_speed = model_cfg.get("rendering_speed", "BALANCED")

    dump("STAGE 3 — PROVIDER ROUTING", {
        "model_key":         fal_model_key,
        "provider":          provider,
        "provider_model_id": provider_model_id,
        "image_size":        image_size,
        "num_images":        num_images,
        "steps":             steps,
        "guidance":          guidance,
    })

    # Build the EXACT JSON that would be POSTed
    if provider == "fal":
        from app.services.external.multi_provider_client import (
            MultiProviderClient, _safe_json,
        )
        payload = MultiProviderClient._build_fal_payload(
            model_id=provider_model_id,
            prompt=enhanced_prompt,
            negative_prompt=negative_prompt,
            num_images=num_images,
            image_size=image_size,
            steps=steps,
            guidance=guidance,
            seed=None,
            reference_image_url=None,
            rendering_speed=rendering_speed,
            style=None,
        )
        dump(f"STAGE 4 — FINAL JSON → POST https://fal.run/{provider_model_id}", payload)
        print(f"\n[compact] {_safe_json(payload)}")

    elif provider == "google":
        # Mirror _call_google body construction
        full_prompt = enhanced_prompt
        if negative_prompt:
            full_prompt = f"{enhanced_prompt}. Avoid: {negative_prompt}"
        aspect_map = {
            "square_hd": "1:1", "landscape_16_9": "16:9",
            "portrait_9_16": "9:16", "landscape_4_3": "4:3",
        }
        payload = {
            "instances": [{"prompt": full_prompt}],
            "parameters": {
                "sampleCount":       min(num_images, 4),
                "aspectRatio":       aspect_map.get(image_size, "1:1"),
                "safetyFilterLevel": "BLOCK_ONLY_HIGH",
                "personGeneration":  "ALLOW_ADULT",
            },
        }
        endpoint = spec.get("endpoint") or provider_model_id
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{endpoint}:predict"
        dump(f"STAGE 4 — FINAL JSON → POST {url}", payload)

    elif provider == "wavespeed":
        from app.services.external.multi_provider_client import _WAVESPEED_MODEL_PATHS
        size_map = {
            "square_hd": "1024*1024", "landscape_16_9": "1344*768",
            "portrait_9_16": "768*1344", "landscape_4_3": "1152*896",
        }
        aspect_map = {
            "square_hd": "1:1", "landscape_16_9": "16:9",
            "portrait_9_16": "9:16", "landscape_4_3": "4:3",
        }
        # Mirror the anti-collage fold-in for wavespeed
        ws_prompt = enhanced_prompt
        if negative_prompt:
            _neg_lower = negative_prompt.lower()
            if any(k in _neg_lower for k in ("collage", "panel", "grid", "option")):
                ws_prompt = (
                    "ONE single unified image, one cohesive composition. "
                    "Not a collage, not a grid, not multi-panel, not a design sheet. "
                    + ws_prompt
                )
        if provider_model_id == "grok_2_imagine":
            payload = {
                "prompt":        ws_prompt,
                "aspect_ratio":  aspect_map.get(image_size, "1:1"),
                "num_images":    max(1, min(num_images, 4)),
                "output_format": "jpeg",
            }
        else:
            payload = {"prompt": ws_prompt, "size": size_map.get(image_size, "1024*1024"), "seed": -1}
        path = _WAVESPEED_MODEL_PATHS.get(provider_model_id, provider_model_id)
        dump(f"STAGE 4 — FINAL JSON → POST https://api.wavespeed.ai/api/v3/{path}", payload)

    else:
        dump("STAGE 4 — UNKNOWN PROVIDER (no payload built)", {"provider": provider})

    # Integrity checks
    problems = []
    if not enhanced_prompt:           problems.append("prompt is empty")
    if not fal_model_key:             problems.append("model_key missing")
    if len(enhanced_prompt) > 4000:   problems.append(f"prompt too long ({len(enhanced_prompt)} chars)")
    if num_images not in (1, 2, 3, 4): problems.append(f"num_images invalid: {num_images}")

    if problems:
        dump("INTEGRITY CHECK — PROBLEMS FOUND", problems)
        return 1
    dump("INTEGRITY CHECK — OK", {"status": "all fields present"})
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
