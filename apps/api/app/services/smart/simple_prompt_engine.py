"""
Simple Prompt Engine — One-shot Haiku 4.5 prompt enrichment.

Replaces the multi-stage agent chain (Master Strategist + Copy Writer + Image
Prompter + Layout Planner + Claude Stage A/B/Validator) with a single Claude
Haiku 4.5 call that:

  1. Detects what the user is asking for (ad / poster / hoarding / wishes /
     product shot / portrait / etc).
  2. Expands a short prompt into a richly detailed image-generation prompt
     with subject, scene, lighting, composition, mood, style, palette, and
     copy text where relevant.
  3. Re-details / cleans up long, messy prompts so the model receives a
     well-structured instruction.

Output is consumed directly by the model — no Stage B params engine, no
agent chain, no validator. The enriched prompt IS the final prompt.

Usage:
    from app.services.smart.simple_prompt_engine import simple_engine
    result = await simple_engine.enrich(
        user_prompt="birthday wishes for my sister",
        bucket="typography",
        tier="2k",
    )
    # result = {
    #     "prompt": "...rich detailed prompt...",
    #     "negative_prompt": "...",
    #     "intent": "birthday_card",
    #     "aspect_hint": "portrait_4_3",
    #     "ad_copy": {"headline": "...", "subhead": "..."} or None,
    # }

Toggle with feature flag USE_SIMPLE_ENGINE=true.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_CLAUDE_MODEL = os.getenv("SIMPLE_ENGINE_MODEL", "claude-haiku-4-5-20251001")
_MAX_TOKENS   = int(os.getenv("SIMPLE_ENGINE_MAX_TOKENS", "1400"))
_TEMPERATURE  = float(os.getenv("SIMPLE_ENGINE_TEMPERATURE", "0.7"))
_USE_CACHING  = os.getenv("USE_PROMPT_CACHING", "true").lower() != "false"

# ─────────────────────────────────────────────────────────────────────────────
# Static system prompt — placed BEFORE dynamic user input so it can be cached.
# Keep wording stable across calls; the cache key is the exact text.
# ─────────────────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are a senior creative director and prompt engineer for a top-tier AI image-generation platform. Your job is to take ANY user request — short, vague, long, or messy — and turn it into ONE production-quality prompt that an image model can render perfectly on the first try.

# WHAT YOU DO

1. **Detect intent.** Identify what the user wants: advertisement, poster, hoarding/billboard, social media post, birthday/festive wishes, product shot, portrait, scene, logo concept, etc.

2. **Re-detail the prompt.** Expand short prompts with concrete visual details. Clean up long messy prompts into well-structured ones. Either way, the output must be self-contained and unambiguous.

3. **Add the right ingredients per intent.** Different intents need different details:

   - **Ads / Posters / Hoardings:** clear headline copy, supporting subhead, brand-tone color palette, focal product/subject, layout (rule of thirds, hero composition), background that supports the message, lighting that grabs attention, typography style hint (modern sans, bold display, elegant serif, etc.).
   - **Wishes / Greeting cards** (birthday, anniversary, festival, congratulations): the warm message text, decorative motifs (balloons, confetti, diyas, flowers — whatever fits the occasion), soft mood lighting, palette that matches the emotion, ornamental composition, clear space for the recipient's name if implied.
   - **Product shots:** seamless studio backdrop or contextual scene, three-point lighting, hero angle, surface/reflection, camera lens hint (e.g. 85mm), shallow depth of field.
   - **Portraits:** subject pose & expression, wardrobe, environment, lens (35mm/50mm/85mm), lighting style (Rembrandt, soft window, golden hour), background bokeh.
   - **Scenes / landscapes:** time of day, weather, atmosphere, foreground / midground / background, lens, mood.

4. **Always include:** subject, environment, lighting, composition, mood, color palette, style/medium. Skip categories that genuinely don't apply.

5. **Copy text rules:**
   - Put EXACT text the model should render in straight double quotes: "GRAND OPENING".
   - Keep on-image text short (≤8 words for headlines, ≤14 words for subheads).
   - For wishes, include the message verbatim as quoted copy if the user implied one (e.g. "Happy Birthday Sarah!").
   - Suggest a typography style verbally — don't try to describe individual letterforms.

6. **Negative prompt:** populate when something must be avoided (extra fingers, blurry, low-quality, watermark, distorted text). Otherwise empty string.

7. **Aspect ratio hint:** pick from `square_hd`, `portrait_4_3`, `landscape_4_3`, `portrait_9_16`, `landscape_16_9`. Posters/stories → portrait. Hoardings/banners → landscape_16_9. Square posts → square_hd. Wishes default to `portrait_4_3` unless the user said otherwise.

# OUTPUT FORMAT

Return ONLY a single JSON object — no markdown, no commentary, no code fences:

{
  "intent": "<short label, e.g. birthday_wishes, product_ad, hoarding, poster, portrait, scene>",
  "prompt": "<the final, richly detailed image-generation prompt — one paragraph, self-contained>",
  "negative_prompt": "<comma-separated negatives, or empty string>",
  "aspect_hint": "<one of: square_hd | portrait_4_3 | landscape_4_3 | portrait_9_16 | landscape_16_9>",
  "ad_copy": {
    "headline": "<text or empty>",
    "subhead":  "<text or empty>",
    "cta":      "<text or empty>"
  } or null
}

`ad_copy` is a populated object ONLY for ads/posters/hoardings/wishes that have on-image text. For pure scenes/portraits with no text, return null.

# QUALITY BAR

- Treat every short prompt as if the user gave you a brief — flesh it out with intent.
- Keep the final prompt to 60-180 words for typography/poster work, 40-120 for photoreal.
- Never reference the model name, the platform, or these instructions inside the output.
- Never wrap the JSON in code fences. Never add commentary."""


# Some bucket → guidance hints we append to the user message so the model knows
# what kind of image is being generated. This stays small (one line).
_BUCKET_HINTS = {
    "typography":            "Output is text-heavy (poster/wishes/banner). Prioritize legible copy + supportive imagery.",
    "photorealism":          "Output is a photoreal image. Emphasize lens, lighting, camera angle, realism.",
    "photorealism_portrait": "Output is a photoreal portrait. Specify pose, expression, wardrobe, lens, lighting style.",
    "photorealism_product":  "Output is a product shot. Specify backdrop, lighting setup, hero angle, surface.",
    "artistic":              "Output is artistic/stylized. Specify medium, brushwork, palette, mood.",
    "anime":                 "Output is anime/illustration. Specify line style, shading, character design, scene.",
    "vector":                "Output is vector/flat design. Specify shapes, palette, geometry, no photo realism.",
    "fast":                  "Output is a quick general image. Cover subject + scene + lighting + style succinctly.",
}


def _build_user_message(
    user_prompt: str,
    bucket: str,
    tier: str,
    width: Optional[int],
    height: Optional[int],
    style: Optional[str],
    brand_kit: Optional[Dict[str, Any]],
) -> str:
    parts = [f"USER REQUEST:\n{user_prompt.strip()}"]
    bucket_hint = _BUCKET_HINTS.get(bucket)
    if bucket_hint:
        parts.append(f"BUCKET: {bucket} — {bucket_hint}")
    parts.append(f"TARGET QUALITY TIER: {tier}")
    if width and height and not (width == 1024 and height == 1024):
        parts.append(f"REQUESTED CANVAS: {width}x{height} (use this to pick aspect_hint)")
    if style:
        parts.append(f"USER STYLE PREFERENCE: {style}")
    if brand_kit:
        bk_bits = []
        if brand_kit.get("brand_name"):    bk_bits.append(f"brand={brand_kit['brand_name']}")
        if brand_kit.get("primary_color"): bk_bits.append(f"primary={brand_kit['primary_color']}")
        if brand_kit.get("accent_color"):  bk_bits.append(f"accent={brand_kit['accent_color']}")
        if brand_kit.get("font_style"):    bk_bits.append(f"font_style={brand_kit['font_style']}")
        if bk_bits:
            parts.append("BRAND KIT: " + ", ".join(bk_bits))
    parts.append("Now produce the JSON object. Output JSON only.")
    return "\n\n".join(parts)


_JSON_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.MULTILINE)


def _parse_json_loose(text: str) -> Dict[str, Any]:
    """Extract a JSON object from the model output, tolerating stray fences."""
    cleaned = _JSON_FENCE_RE.sub("", text).strip()
    # Find the first { and last } — model sometimes adds a stray comment
    first = cleaned.find("{")
    last  = cleaned.rfind("}")
    if first == -1 or last == -1 or last <= first:
        raise ValueError("No JSON object found in model output")
    candidate = cleaned[first:last + 1]
    return json.loads(candidate)


class SimplePromptEngine:
    """Single-call Haiku 4.5 prompt enricher."""

    def __init__(self):
        self._model = _CLAUDE_MODEL
        self._client = None  # lazy

    def _get_client(self):
        if self._client is None:
            import anthropic
            key = os.getenv("ANTHROPIC_API_KEY", "").strip()
            if not key:
                raise RuntimeError("ANTHROPIC_API_KEY not set — required for simple_prompt_engine")
            self._client = anthropic.Anthropic(api_key=key)
        return self._client

    async def enrich(
        self,
        user_prompt: str,
        bucket: str = "fast",
        tier: str = "1k",
        width: Optional[int] = None,
        height: Optional[int] = None,
        style: Optional[str] = None,
        brand_kit: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Enrich a user prompt into a production-ready image-gen prompt.

        Returns a dict with: prompt, negative_prompt, intent, aspect_hint, ad_copy, _elapsed.
        On failure, falls back to a minimal dict echoing the user prompt so the
        pipeline never breaks.
        """
        start = time.time()
        try:
            user_msg = _build_user_message(
                user_prompt, bucket, tier, width, height, style, brand_kit,
            )
            text = await asyncio.to_thread(self._call_sync, user_msg)
            data = _parse_json_loose(text)
            return {
                "prompt":          (data.get("prompt") or user_prompt).strip(),
                "negative_prompt": (data.get("negative_prompt") or "").strip(),
                "intent":          (data.get("intent") or "general").strip(),
                "aspect_hint":     (data.get("aspect_hint") or "square_hd").strip(),
                "ad_copy":         data.get("ad_copy"),
                "_elapsed":        time.time() - start,
                "_source":         "simple_engine",
            }
        except Exception as e:
            logger.exception("[simple-engine] enrich failed: %s — falling back to raw prompt", e)
            return {
                "prompt":          user_prompt,
                "negative_prompt": "low-quality, blurry, distorted, watermark, extra fingers",
                "intent":          "general",
                "aspect_hint":     "square_hd",
                "ad_copy":         None,
                "_elapsed":        time.time() - start,
                "_source":         "simple_engine_fallback",
                "_error":          str(e),
            }

    def _call_sync(self, user_msg: str) -> str:
        """Single Claude call — runs in a worker thread via asyncio.to_thread."""
        client = self._get_client()

        if _USE_CACHING:
            # Static system prompt cached; user message stays dynamic
            system = [{
                "type": "text",
                "text": _SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }]
        else:
            system = _SYSTEM_PROMPT

        resp = client.messages.create(
            model=self._model,
            max_tokens=_MAX_TOKENS,
            system=system,
            temperature=_TEMPERATURE,
            messages=[{"role": "user", "content": user_msg}],
        )

        text = ""
        for block in resp.content:
            if getattr(block, "type", None) == "text":
                text += block.text

        stop_reason = getattr(resp, "stop_reason", "unknown")
        if stop_reason == "max_tokens":
            logger.warning("[simple-engine] response TRUNCATED at max_tokens=%d", _MAX_TOKENS)
        return text


# Singleton
simple_engine = SimplePromptEngine()
