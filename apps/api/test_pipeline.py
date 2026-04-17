"""
Pipeline Debug Script — PhotoGenius AI
Traces: user input → intent → bucket → model routing → brief → params
STOPS before multi_client.generate() — no image is generated.

Usage:
    cd apps/api
    source venv/bin/activate     # Linux/Mac
    venv\\Scripts\\activate        # Windows

    python test_pipeline.py "a beautiful sunset over mountains"
    python test_pipeline.py "make a poster with bold text BUY NOW" --quality 2k
    python test_pipeline.py --batch
    python test_pipeline.py --batch --quality 4k
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from typing import Optional

# ── Path setup so local imports work ─────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# ── Load .env.local ───────────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    _env_path = os.path.join(_HERE, ".env.local")
    if os.path.exists(_env_path):
        load_dotenv(_env_path)
        print(f"[env] Loaded {_env_path}")
    else:
        print(f"[env] WARNING: {_env_path} not found — API keys may be missing")
except ImportError:
    print("[env] python-dotenv not installed — skipping .env load")

# ── ANSI colors ───────────────────────────────────────────────────────────────
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

_RESET  = "\033[0m"
_BOLD   = "\033[1m"
_GREEN  = "\033[32m"
_YELLOW = "\033[33m"
_RED    = "\033[31m"
_CYAN   = "\033[36m"
_DIM    = "\033[2m"

def _header(title: str) -> str:
    line = "=" * 50
    return f"\n{_BOLD}{_CYAN}{line}\n  {title}\n{line}{_RESET}"

def _kv(key: str, val, warn: bool = False) -> str:
    color = _YELLOW if warn else _RESET
    return f"  {_DIM}{key:<22}{_RESET}{color}{val}{_RESET}"

def _ok(msg: str) -> str:
    return f"  {_GREEN}[OK] {msg}{_RESET}"

def _warn(msg: str) -> str:
    return f"  {_YELLOW}[WARN] {msg}{_RESET}"

def _err(msg: str) -> str:
    return f"  {_RED}[ERR] {msg}{_RESET}"

# ── Batch test prompts ────────────────────────────────────────────────────────
BATCH_PROMPTS = [
    ("a beautiful sunset over mountains", "photorealism"),
    ('create a poster for a coffee shop with bold text "BREW MASTERS"', "typography"),
    ("anime girl with glowing blue eyes standing in a neon cyberpunk city at night", "anime"),
    ("minimalist flat logo for a tech startup called NexaAI", "vector"),
    ("portrait of an Indian woman in traditional Rajasthani dress, golden jewelry, warm light", "portrait"),
]

# ── Core pipeline trace ───────────────────────────────────────────────────────
async def trace_pipeline(prompt: str, quality: str = "1k") -> dict:
    results = {
        "prompt": prompt,
        "quality": quality,
        "stages": {},
        "errors": [],
    }

    total_start = time.time()

    # ══════════════════════════════════════════════════════════════════════════
    print(_header("STAGE -1: INTENT ANALYZER"))
    t0 = time.time()
    try:
        from app.services.smart.intent_analyzer import intent_analyzer
        intent = await asyncio.to_thread(intent_analyzer.analyze, prompt, 1024, 1024)
        elapsed = time.time() - t0

        print(_kv("creative_type", intent.get("creative_type", "?")))
        print(_kv("is_ad",         intent.get("is_ad", False)))
        print(_kv("goal",          intent.get("goal", "?")))
        print(_kv("audience_tone", intent.get("audience_tone", "?")))
        print(_kv("cta_strength",  f"{intent.get('cta_strength', 0.0):.2f}"))
        print(_kv("text_heavy",    intent.get("text_heavy", False)))
        print(_kv("elapsed",       f"{elapsed:.2f}s"))
        print(_ok("Intent analysis complete"))

        results["stages"]["intent"] = {"ok": True, "data": intent, "elapsed": elapsed}

    except Exception as e:
        print(_err(f"Intent analysis FAILED: {e}"))
        results["errors"].append(f"intent: {e}")
        intent = {"creative_type": "photorealism", "is_ad": False, "goal": "aesthetic", "audience_tone": "casual"}
        results["stages"]["intent"] = {"ok": False, "error": str(e)}

    # ══════════════════════════════════════════════════════════════════════════
    print(_header("STAGE 0: BUCKET DETECTION"))
    t0 = time.time()
    try:
        from app.services.smart.config import detect_capability_bucket
        bucket = detect_capability_bucket(prompt)
        elapsed = time.time() - t0

        print(_kv("bucket",  bucket))
        print(_kv("elapsed", f"{elapsed:.2f}s"))
        print(_ok("Bucket detected"))

        results["stages"]["bucket"] = {"ok": True, "bucket": bucket, "elapsed": elapsed}

    except Exception as e:
        print(_err(f"Bucket detection FAILED: {e}"))
        results["errors"].append(f"bucket: {e}")
        bucket = "photorealism"
        results["stages"]["bucket"] = {"ok": False, "error": str(e)}

    # ══════════════════════════════════════════════════════════════════════════
    print(_header("STAGE R: MODEL ROUTING"))
    t0 = time.time()
    try:
        from app.services.smart.model_config import get_model_for_request, normalize_quality_tier
        norm_quality = normalize_quality_tier(quality)
        model_cfg = get_model_for_request(bucket, norm_quality)
        elapsed = time.time() - t0

        print(_kv("quality (normalized)", norm_quality))
        print(_kv("model_key",  model_cfg.get("model_key", model_cfg.get("model", "?"))))
        print(_kv("provider",   model_cfg.get("provider", "?")))
        print(_kv("tier_used",  model_cfg.get("tier_used", norm_quality)))
        print(_kv("cost/image", f"${model_cfg.get('cost_per_image', '?')}"))
        print(_kv("max_res",    model_cfg.get("max_resolution", "?")))
        print(_kv("elapsed",    f"{elapsed:.2f}s"))
        print(_ok("Model routed"))

        results["stages"]["routing"] = {"ok": True, "model_cfg": model_cfg, "elapsed": elapsed}
        fal_model_key = model_cfg.get("model_key") or model_cfg.get("model", "flux_2_flex")

    except Exception as e:
        print(_err(f"Model routing FAILED: {e}"))
        results["errors"].append(f"routing: {e}")
        fal_model_key = "flux_2_flex"
        results["stages"]["routing"] = {"ok": False, "error": str(e)}

    # ══════════════════════════════════════════════════════════════════════════
    print(_header("STAGE A: CREATIVE BRIEF"))
    t0 = time.time()
    try:
        use_claude = os.getenv("USE_CLAUDE_ENGINE", "true").lower() != "false"
        has_api_key = bool(os.getenv("ANTHROPIC_API_KEY"))

        if use_claude and has_api_key:
            print(_kv("engine", "Claude Prompt Engine v2"))
        elif use_claude and not has_api_key:
            print(_warn("ANTHROPIC_API_KEY missing — heuristic fallback will be used"))
        else:
            print(_kv("engine", "Gemini (USE_CLAUDE_ENGINE=false)"))

        if use_claude:
            from app.services.smart.claude_prompt_engine_v2 import claude_prompt_engine as prompt_engine
        else:
            from app.services.smart.gemini_prompt_engine import gemini_prompt_engine as prompt_engine

        ctx = (
            f"creative_type={intent.get('creative_type')}, "
            f"goal={intent.get('goal')}, "
            f"audience={intent.get('audience_tone')}"
        )
        brief = await prompt_engine.create_brief(
            prompt,
            creative_type=intent.get("creative_type", "photorealism"),
            style="photo",
            extra_context=ctx,
            bucket=bucket,
            tier=quality,
        )
        elapsed = time.time() - t0

        source = brief.get("_source", "unknown")
        is_fallback = source in ("heuristic", "gemini_fallback")

        print(_kv("source",        source, warn=is_fallback))
        if is_fallback:
            print(_warn(f"FALLBACK USED at Stage A — source: {source}"))

        print(_kv("visual_concept", (brief.get("visual_concept") or "")[:80] + "..."))
        print(_kv("subject",        (brief.get("subject") or "")[:60]))
        print(_kv("lighting",       (brief.get("lighting") or "")[:60]))
        print(_kv("camera",         (brief.get("camera") or "")[:60]))
        print(_kv("mood",           brief.get("mood", "?")))
        print(_kv("color_palette",  (brief.get("color_palette") or "")[:60]))
        print(_kv("style_refs",     brief.get("style_refs", [])))
        print(_kv("ad_copy",        "present" if brief.get("ad_copy") else "None"))
        print(_kv("poster_design",  "present" if brief.get("poster_design") else "None"))
        print(_kv("elapsed",        f"{elapsed:.2f}s"))
        print(_ok("Brief generated"))

        results["stages"]["brief"] = {"ok": True, "source": source, "is_fallback": is_fallback, "elapsed": elapsed}

    except Exception as e:
        print(_err(f"Brief generation FAILED: {e}"))
        import traceback
        traceback.print_exc()
        results["errors"].append(f"brief: {e}")
        brief = {}
        results["stages"]["brief"] = {"ok": False, "error": str(e)}

    # ══════════════════════════════════════════════════════════════════════════
    print(_header("STAGE B: GENERATION PARAMS (CDI)"))
    t0 = time.time()
    try:
        from app.services.smart.model_config import get_model_for_request
        _ml_cfg = get_model_for_request(bucket, quality)
        model_label = _ml_cfg.get("display_name") or fal_model_key

        params = await prompt_engine.build_params(brief, model_label, bucket)
        elapsed = time.time() - t0

        source_b = params.get("_source", "unknown")
        is_fallback_b = source_b in ("heuristic",)

        print(_kv("source",         source_b, warn=is_fallback_b))
        if is_fallback_b:
            print(_warn(f"FALLBACK USED at Stage B — source: {source_b}"))

        # CDI model override
        recommended = params.get("recommended_model", "")
        if recommended and recommended != fal_model_key:
            print(_kv("model override", f"{fal_model_key} → {recommended}", warn=True))
            fal_model_key_final = recommended
        else:
            fal_model_key_final = fal_model_key
            print(_kv("model override", "none (router choice kept)"))

        _cdi_p = params.get("parameters") or {}

        # Quality steps table
        _QUALITY_STEPS = {"1k": 12, "2k": 25, "4k": 50}
        _MODEL_GUIDANCE = {
            "ideogram_v3": 3.0, "recraft_v4_pro": 4.0,
            "hunyuan_image": 4.0, "wan_2_7": 4.0,
        }
        inference_steps = int(_cdi_p.get("steps") or _QUALITY_STEPS.get(quality, 20))
        guidance_scale = float(_cdi_p.get("guidance") or _MODEL_GUIDANCE.get(fal_model_key_final, 3.5))

        print(_kv("inference_steps", inference_steps))
        print(_kv("guidance_scale",  guidance_scale))
        print(_kv("style_notes",     (params.get("style_notes") or "")[:80]))
        print(_kv("recommend_reason",(params.get("recommendation_reason") or "")[:80]))
        print(_kv("elapsed",         f"{elapsed:.2f}s"))

        enhanced_prompt  = params.get("prompt") or prompt
        negative_prompt  = params.get("negative_prompt", "")
        word_count       = len(enhanced_prompt.split())
        neg_word_count   = len(negative_prompt.split())

        print(f"\n  {_BOLD}FINAL PROMPT → [{word_count} words]{_RESET}")
        print(f"  {'─' * 46}")
        # Print in wrapped chunks of ~100 chars
        words = enhanced_prompt.split()
        line = "  "
        for word in words:
            if len(line) + len(word) > 100:
                print(line)
                line = "  " + word + " "
            else:
                line += word + " "
        if line.strip():
            print(line)

        print(f"\n  {_BOLD}NEGATIVE PROMPT → [{neg_word_count} words]{_RESET}")
        print(f"  {'─' * 46}")
        neg_words = negative_prompt.split()
        line = "  "
        for word in neg_words:
            if len(line) + len(word) > 100:
                print(line)
                line = "  " + word + " "
            else:
                line += word + " "
        if line.strip():
            print(line)

        print(_ok("Params built"))

        results["stages"]["params"] = {
            "ok": True,
            "source": source_b,
            "is_fallback": is_fallback_b,
            "model_final": fal_model_key_final,
            "steps": inference_steps,
            "guidance": guidance_scale,
            "prompt_words": word_count,
            "neg_words": neg_word_count,
            "elapsed": elapsed,
        }

    except Exception as e:
        print(_err(f"Params build FAILED: {e}"))
        import traceback
        traceback.print_exc()
        results["errors"].append(f"params: {e}")
        results["stages"]["params"] = {"ok": False, "error": str(e)}
        fal_model_key_final = fal_model_key

    # ══════════════════════════════════════════════════════════════════════════
    total_elapsed = time.time() - total_start

    print(_header("SUMMARY"))
    print(_kv("Total elapsed",   f"{total_elapsed:.2f}s"))
    print(_kv("Bucket",          bucket))
    print(_kv("Final model",     fal_model_key_final + f" ({results['stages'].get('routing', {}).get('model_cfg', {}).get('provider', '?')})"))
    print(_kv("Prompt words",    results["stages"].get("params", {}).get("prompt_words", "?")))
    print(_kv("Negative words",  results["stages"].get("params", {}).get("neg_words", "?")))

    all_ok = all(
        results["stages"].get(s, {}).get("ok", False)
        for s in ["intent", "bucket", "routing", "brief", "params"]
    )
    any_fallback = any(
        results["stages"].get(s, {}).get("is_fallback", False)
        for s in ["brief", "params"]
    )

    if all_ok and not any_fallback:
        print(_ok("ALL STAGES PASSED - READY FOR GENERATION"))
    elif all_ok and any_fallback:
        print(_warn("STAGES PASSED but FALLBACK was used (Claude may be down)"))
    else:
        print(_err("ONE OR MORE STAGES FAILED"))
        for err in results["errors"]:
            print(_err(f"  → {err}"))

    print()
    return results


# ── CLI entry ─────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="PhotoGenius AI pipeline debugger")
    parser.add_argument("prompt", nargs="?", default=None, help="Prompt to test")
    parser.add_argument("--quality", default="1k", choices=["1k", "2k", "4k"],
                        help="Quality tier (default: 1k)")
    parser.add_argument("--batch", action="store_true",
                        help="Run all 5 built-in test prompts")
    args = parser.parse_args()

    if args.batch:
        print(f"\n{_BOLD}{_CYAN}PhotoGenius AI — Batch Pipeline Test ({len(BATCH_PROMPTS)} prompts){_RESET}")
        print(f"{_DIM}Quality: {args.quality} | Image generation: DISABLED{_RESET}\n")

        async def run_batch():
            for i, (p, expected_bucket) in enumerate(BATCH_PROMPTS, 1):
                print(f"\n{'='*60}")
                print(f"{_BOLD}[{i}/{len(BATCH_PROMPTS)}] Expected bucket: {expected_bucket}{_RESET}")
                print(f"Prompt: {p[:80]}{'...' if len(p) > 80 else ''}")
                print('='*60)
                await trace_pipeline(p, args.quality)

        asyncio.run(run_batch())

    elif args.prompt:
        print(f"\n{_BOLD}{_CYAN}PhotoGenius AI — Pipeline Trace{_RESET}")
        print(f"{_DIM}Prompt: {args.prompt[:100]}{_RESET}")
        print(f"{_DIM}Quality: {args.quality} | Image generation: DISABLED{_RESET}")
        asyncio.run(trace_pipeline(args.prompt, args.quality))

    else:
        parser.print_help()
        print(f"\n{_YELLOW}Example:{_RESET}")
        print('  python test_pipeline.py "sunset over mountains"')
        print('  python test_pipeline.py "poster for music festival" --quality 2k')
        print('  python test_pipeline.py --batch')


if __name__ == "__main__":
    main()
