"""
Claude Prompt Engine — 2-step creative brief + model-specific params.

STAGE A (Sonnet): raw user prompt → structured Creative Brief JSON
STAGE B (Haiku):  Creative Brief → model-specific generation params

Falls back to existing SmartPromptEnhancer (heuristic) if ANTHROPIC_API_KEY
is not set, so nothing breaks in dev without the key.

Cost estimate:
  Sonnet 4.6:  ~800 input tokens → ~₹0.60
  Haiku 4.5:   ~600 input tokens → ~₹0.08
  Total:        ~₹0.68 per image

Feature flag: USE_CLAUDE_ENGINE=true (env) to enable. Default=true when key present.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# ── Feature flag ──────────────────────────────────────────────────────────────
_KEY = os.getenv("ANTHROPIC_API_KEY", "")
USE_CLAUDE_ENGINE: bool = bool(_KEY) and os.getenv("USE_CLAUDE_ENGINE", "true").lower() != "false"

# ── System prompts ─────────────────────────────────────────────────────────────

_BRIEF_SYSTEM = """You are a world-class creative director and award-winning photographer.
Convert the user's raw prompt into a structured Creative Brief as JSON.

Rules:
- Be specific and visual — no vague adjectives, describe exactly what to render.
- camera/lens should feel real (85mm f/1.4, wide-angle 24mm, macro 100mm, etc.)
- lighting must be precise (golden hour from camera-left, rim-lit by neon, etc.)
- color_palette: max 4 hex colors or named tones, separated by comma
- mood: single evocative phrase (e.g., "tense thriller suspense")
- style_refs: 2-3 artist/film/brand names that capture the aesthetic (never copy)
- avoid: list things that would ruin this image

Return ONLY valid JSON, no markdown fences:
{
  "visual_concept": "...",
  "subject": "...",
  "setting": "...",
  "lighting": "...",
  "camera": "...",
  "composition": "...",
  "mood": "...",
  "color_palette": "...",
  "texture_detail": "...",
  "style_refs": ["...", "..."],
  "avoid": ["...", "..."]
}"""

_PARAMS_SYSTEM = """You are an AI image generation specialist.
Convert the Creative Brief into optimized generation parameters for {model_name}.

Model notes:
- Flux Pro: natural descriptive language, no special tokens, very responsive to camera/lens terms
- Ideogram: wrap any on-image text in double quotes, mention font style explicitly
- Generic/default: descriptive comma-separated tags work well

Return ONLY valid JSON, no markdown fences:
{
  "prompt": "...",
  "negative_prompt": "...",
  "style_notes": "..."
}"""


def _extract_json(text: str) -> Dict:
    """Extract first JSON object from LLM response, even if wrapped in markdown."""
    # Strip markdown fences if present
    text = re.sub(r"```(?:json)?\s*", "", text).strip()
    # Find first { ... }
    start = text.find("{")
    end = text.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError("No JSON object found in LLM response")
    return json.loads(text[start:end])


class ClaudePromptEngine:
    """
    2-step prompt engine using Claude API.

    Step A: Sonnet creates a Creative Brief (structured JSON).
    Step B: Haiku converts that brief into model-specific generation params.

    If ANTHROPIC_API_KEY is missing, falls back to heuristic enhancer.
    """

    def __init__(self):
        self._client = None
        self.enabled = USE_CLAUDE_ENGINE

    @property
    def client(self):
        if self._client is None:
            import anthropic  # lazy import — only needed when key is set
            self._client = anthropic.Anthropic(api_key=_KEY)
        return self._client

    # ── Public API ─────────────────────────────────────────────────────────────

    def create_brief(
        self,
        raw_prompt: str,
        creative_type: str = "photo",
        style: str = "photo",
        extra_context: Optional[str] = None,
    ) -> Dict:
        """
        Stage A: Convert raw prompt → Creative Brief JSON.

        Args:
            raw_prompt:     What the user typed.
            creative_type:  From intent_analyzer ("photo", "poster", "ad", etc.)
            style:          From request ("Realistic", "Cinematic", etc.)
            extra_context:  Optional extra hints (platform, audience, etc.)

        Returns:
            dict with keys: visual_concept, subject, setting, lighting, camera,
                            composition, mood, color_palette, texture_detail,
                            style_refs, avoid
        """
        if not self.enabled:
            return self._heuristic_brief(raw_prompt)

        user_msg = f"Raw prompt: {raw_prompt}"
        if creative_type != "photo":
            user_msg += f"\nCreative type: {creative_type}"
        if style and style not in ("Auto", "photo", ""):
            user_msg += f"\nDesired style: {style}"
        if extra_context:
            user_msg += f"\nExtra context: {extra_context}"

        try:
            resp = self.client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1024,
                system=_BRIEF_SYSTEM,
                messages=[{"role": "user", "content": user_msg}],
            )
            brief = _extract_json(resp.content[0].text)
            brief["_source"] = "claude-sonnet-4-6"
            logger.info("[prompt-engine] brief created via Claude Sonnet")
            return brief

        except Exception as e:
            logger.warning("[prompt-engine] Sonnet brief failed (%s), using heuristic", e)
            return self._heuristic_brief(raw_prompt)

    def build_params(
        self,
        brief: Dict,
        model_name: str = "Flux Pro",
        capability_bucket: str = "photorealism",
    ) -> Dict:
        """
        Stage B: Convert Creative Brief → model-specific generation params.

        Args:
            brief:              Output from create_brief().
            model_name:         Human-readable model name for the system prompt.
            capability_bucket:  e.g. "typography", "photorealism", "artistic"

        Returns:
            dict with keys: prompt, negative_prompt, style_notes
        """
        if not self.enabled or brief.get("_source") == "heuristic":
            return self._heuristic_params(brief, capability_bucket)

        brief_str = json.dumps({k: v for k, v in brief.items() if not k.startswith("_")}, indent=2)

        try:
            resp = self.client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=512,
                system=_PARAMS_SYSTEM.format(model_name=model_name),
                messages=[
                    {
                        "role": "user",
                        "content": f"Creative Brief:\n{brief_str}\n\nTarget model: {model_name}",
                    }
                ],
            )
            params = _extract_json(resp.content[0].text)
            params["_source"] = "claude-haiku-4-5"
            logger.info("[prompt-engine] params built via Claude Haiku for %s", model_name)
            return params

        except Exception as e:
            logger.warning("[prompt-engine] Haiku params failed (%s), using heuristic", e)
            return self._heuristic_params(brief, capability_bucket)

    def enhance(
        self,
        raw_prompt: str,
        model_name: str = "Flux Pro",
        capability_bucket: str = "photorealism",
        creative_type: str = "photo",
        style: str = "photo",
        extra_context: Optional[str] = None,
    ) -> Dict:
        """
        Full 2-step pipeline: raw prompt → brief → params.

        Returns:
            {
              "brief": dict,         # Creative Brief
              "prompt": str,         # Final generation prompt
              "negative_prompt": str,
              "style_notes": str,
              "original_prompt": str,
              "engine": "claude" | "heuristic"
            }
        """
        brief = self.create_brief(raw_prompt, creative_type, style, extra_context)
        params = self.build_params(brief, model_name, capability_bucket)

        engine = "claude" if self.enabled else "heuristic"
        return {
            "brief": brief,
            "prompt": params.get("prompt", raw_prompt),
            "negative_prompt": params.get("negative_prompt", _DEFAULT_NEGATIVE),
            "style_notes": params.get("style_notes", ""),
            "original_prompt": raw_prompt,
            "engine": engine,
        }

    # ── Heuristic fallbacks (no API key needed) ────────────────────────────────

    @staticmethod
    def _heuristic_brief(raw_prompt: str) -> Dict:
        """Simple brief from prompt when Claude is unavailable."""
        return {
            "visual_concept": raw_prompt,
            "subject": raw_prompt,
            "setting": "",
            "lighting": "natural soft lighting",
            "camera": "85mm f/1.8",
            "composition": "rule of thirds",
            "mood": "professional quality",
            "color_palette": "harmonious tones",
            "texture_detail": "sharp details",
            "style_refs": [],
            "avoid": ["blurry", "low quality", "deformed"],
            "_source": "heuristic",
        }

    @staticmethod
    def _heuristic_params(brief: Dict, capability_bucket: str) -> Dict:
        """Build prompt from brief dict without Claude."""
        parts = [brief.get("visual_concept") or brief.get("subject", "")]

        for field in ("lighting", "camera", "composition", "mood", "color_palette", "texture_detail"):
            val = brief.get(field, "")
            if val:
                parts.append(val)

        # Add bucket-specific quality suffix
        suffix_map = {
            "photorealism": "photorealistic, 8K, sharp focus, professional photography",
            "typography": "crisp text rendering, graphic design, high contrast",
            "artistic": "artistic masterpiece, painterly, expressive, vibrant",
            "character_consistency": "consistent character, detailed face, sharp focus",
            "vector": "clean vector art, flat design, scalable",
            "fast": "good quality",
        }
        parts.append(suffix_map.get(capability_bucket, "masterful quality, professional finish"))

        avoid = brief.get("avoid", [])
        neg = _DEFAULT_NEGATIVE
        if avoid:
            neg = ", ".join(avoid) + ", " + neg

        return {
            "prompt": ", ".join(p for p in parts if p),
            "negative_prompt": neg,
            "style_notes": f"bucket={capability_bucket}",
            "_source": "heuristic",
        }


_DEFAULT_NEGATIVE = (
    "blurry, low quality, deformed, bad anatomy, watermark, signature, "
    "text artifacts, overexposed, underexposed, grainy, noisy, ugly"
)


# Singleton
claude_prompt_engine = ClaudePromptEngine()
