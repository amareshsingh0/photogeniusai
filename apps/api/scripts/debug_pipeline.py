"""Debug pipeline — runs every stage up to (but NOT including) image generation.

Usage (from apps/api on server, with venv active):
    python scripts/debug_pipeline.py "happy birthday poster for Rahul"
    python scripts/debug_pipeline.py "photorealistic portrait of a chef" --quality 2k

Prints each intermediate JSON so you can see exactly what is fed to the image
model. No provider HTTP call is made, so this is safe / free to run.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

# Make apps/api importable
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


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("prompt", help="User prompt")
    parser.add_argument("--quality", default="1k", choices=["1k", "2k", "4k"])
    parser.add_argument("--width", type=int, default=1024)
    parser.add_argument("--height", type=int, default=1024)
    parser.add_argument("--style", default=None)
    args = parser.parse_args()

    # ── Stage 0 — intent ─────────────────────────────────────────────────
    from app.services.smart.intent_analyzer import intent_analyzer
    intent = await asyncio.to_thread(
        intent_analyzer.analyze, args.prompt, args.width, args.height
    )
    dump("STAGE 0 — INTENT", intent)

    # ── Stage 0.5 — bucket + model routing ───────────────────────────────
    from app.services.smart.config import detect_capability_bucket
    from app.services.smart.model_config import get_model_for_request, normalize_quality_tier

    bucket = detect_capability_bucket(args.prompt)
    quality = normalize_quality_tier(args.quality)
    model_cfg = get_model_for_request(bucket, quality)
    dump("STAGE 0.5 — BUCKET + MODEL ROUTING", {
        "bucket": bucket,
        "quality_tier": quality,
        "model_cfg": model_cfg,
    })

    # ── Stage A — creative brief ─────────────────────────────────────────
    use_claude = os.getenv("USE_CLAUDE_ENGINE", "true").lower() != "false"
    if use_claude:
        from app.services.smart.claude_prompt_engine_v2 import (
            claude_prompt_engine as prompt_engine,
        )
        engine_tag = "claude_prompt_engine_v2"
    else:
        from app.services.smart.gemini_prompt_engine import (
            gemini_prompt_engine as prompt_engine,
        )
        engine_tag = "gemini_prompt_engine"
    print(f"\n[engine] USE_CLAUDE_ENGINE={use_claude} → {engine_tag}")

    brief: dict
    if bucket == "typography":
        try:
            from app.services.smart.design_agent_chain import design_agent_chain
            brief = await design_agent_chain.arun(
                prompt=args.prompt,
                brand_kit=None,
                width=args.width,
                height=args.height,
                prompt_dna=None,
            )
            brief["_source"] = brief.get("_source") or "design_agent_chain"
            if brief.get("_error"):
                raise RuntimeError(brief["_error"])
        except Exception as chain_err:
            print(f"[design_agent_chain] FAILED: {chain_err} — falling back")
            brief = await prompt_engine.create_brief(
                args.prompt,
                creative_type=intent.get("creative_type", "typography"),
                style=args.style or "photo",
                extra_context=(
                    f"creative_type={intent.get('creative_type')}, "
                    f"goal={intent.get('goal')}"
                ),
                bucket=bucket,
                tier=quality,
            )
            brief["_source"] = "fallback_engine"
    else:
        brief = await prompt_engine.create_brief(
            args.prompt,
            creative_type=intent.get("creative_type", "photorealism"),
            style=args.style or "photo",
            extra_context=(
                f"creative_type={intent.get('creative_type')}, "
                f"goal={intent.get('goal')}, "
                f"audience={intent.get('audience_tone')}"
            ),
            bucket=bucket,
            tier=quality,
        )

    dump("STAGE A — CREATIVE BRIEF (full JSON)", brief)

    # ── Stage B — CDI / generation params ────────────────────────────────
    model_label = model_cfg.get("model_key") or model_cfg.get("model") or "unknown"
    params = await prompt_engine.build_params(brief, model_label, bucket)
    dump("STAGE B — PARAMS (full JSON)", params)

    # ── Final assembly — exactly what multi_client.generate() receives ───
    enhanced_prompt = params.get("prompt") or args.prompt
    negative_prompt = params.get("negative_prompt", "")

    final_kwargs = {
        "model_key": model_cfg.get("model_key") or model_cfg.get("model"),
        "prompt": enhanced_prompt,
        "negative_prompt": negative_prompt,
        "num_images": model_cfg.get("num_images", 1),
        "image_size": _pick_size(args.width, args.height),
        "num_inference_steps": params.get("num_inference_steps", 20),
        "guidance_scale": params.get("guidance_scale", 7.5),
        "reference_image_url": None,
        "rendering_speed": model_cfg.get("rendering_speed", "BALANCED"),
    }
    dump("FINAL PAYLOAD → multi_client.generate(**kwargs)", final_kwargs)

    # Integrity checks
    problems = []
    if not final_kwargs["prompt"]:
        problems.append("prompt is empty")
    if not final_kwargs["model_key"]:
        problems.append("model_key missing")
    if len(final_kwargs["prompt"]) > 4000:
        problems.append(f"prompt too long ({len(final_kwargs['prompt'])} chars)")
    if final_kwargs["num_images"] not in (1, 2, 3, 4):
        problems.append(f"num_images invalid: {final_kwargs['num_images']}")

    if problems:
        dump("❌ INTEGRITY CHECK — PROBLEMS FOUND", problems)
        return 1
    else:
        dump("✅ INTEGRITY CHECK", {"status": "all fields present and valid"})
        return 0


def _pick_size(w: int, h: int) -> str:
    if w == h:
        return "square_hd"
    r = w / h
    if r > 1.5:
        return "landscape_16_9"
    if r < 0.67:
        return "portrait_9_16"
    return "landscape_4_3"


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
