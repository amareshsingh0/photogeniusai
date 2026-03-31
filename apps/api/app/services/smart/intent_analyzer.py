"""
Intent & Platform Analyzer — STAGE -1 of the Creative OS pipeline.

Classifies every prompt into a structured creative intent BEFORE any generation.
This is what separates professional design tools from raw text-to-image.

Output:
    creative_type   → "photo" | "poster" | "ad" | "social" | "banner" | "product_shot" | "editorial"
    platform        → "instagram" | "facebook" | "youtube" | "print" | "web" | "general"
    aspect_ratios   → list of recommended ratios for the platform
    goal            → "awareness" | "conversion" | "engagement" | "aesthetic" | "informational"
    audience_tone   → "professional" | "casual" | "luxury" | "playful" | "urgent"
    cta_strength    → 0.0-1.0 (how strong the call-to-action should be)

Heuristic-based (keyword scoring). Boolean flag USE_LLM_INTENT for future
LLM-powered upgrade (Llama/Qwen).
"""

from __future__ import annotations

import logging
import re
from typing import Dict, List, TypedDict

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
# Feature Flags
# ══════════════════════════════════════════════════════════════════════════════
USE_LLM_INTENT = False          # Future: Qwen2/Llama intent classification
USE_AUDIENCE_PREDICTOR = False  # Future: predict target audience from prompt


# ══════════════════════════════════════════════════════════════════════════════
# Output Types
# ══════════════════════════════════════════════════════════════════════════════

class PlatformSpec(TypedDict):
    name: str
    aspect_ratios: List[str]         # e.g. ["1:1", "9:16", "4:5"]
    max_text_ratio: float            # max fraction of image for text (0.0-0.5)
    safe_zone_inset: float           # fraction inset from edges for important content


class CreativeIntent(TypedDict):
    creative_type: str               # "photo" | "poster" | "ad" | "social" | ...
    platform: PlatformSpec
    goal: str                        # "awareness" | "conversion" | ...
    audience_tone: str               # "professional" | "casual" | ...
    cta_strength: float              # 0.0-1.0
    is_ad: bool                      # quick flag: is this an ad/poster/marketing?
    text_heavy: bool                 # expect significant text overlay?
    prompt_hints: Dict[str, str]     # extra hints for downstream modules


# ══════════════════════════════════════════════════════════════════════════════
# Platform Definitions
# ══════════════════════════════════════════════════════════════════════════════

PLATFORMS: Dict[str, PlatformSpec] = {
    "instagram": {
        "name": "Instagram",
        "aspect_ratios": ["1:1", "4:5", "9:16"],
        "max_text_ratio": 0.20,      # IG penalizes >20% text
        "safe_zone_inset": 0.05,
    },
    "facebook": {
        "name": "Facebook",
        "aspect_ratios": ["1:1", "16:9", "4:5"],
        "max_text_ratio": 0.20,
        "safe_zone_inset": 0.04,
    },
    "youtube": {
        "name": "YouTube",
        "aspect_ratios": ["16:9"],
        "max_text_ratio": 0.35,
        "safe_zone_inset": 0.05,
    },
    "tiktok": {
        "name": "TikTok",
        "aspect_ratios": ["9:16"],
        "max_text_ratio": 0.25,
        "safe_zone_inset": 0.10,     # large safe zone for UI overlays
    },
    "print": {
        "name": "Print",
        "aspect_ratios": ["3:4", "2:3", "1:1.414"],  # A4-ish
        "max_text_ratio": 0.50,
        "safe_zone_inset": 0.03,     # bleed area
    },
    "web": {
        "name": "Web Banner",
        "aspect_ratios": ["16:9", "3:1", "2:1"],
        "max_text_ratio": 0.40,
        "safe_zone_inset": 0.02,
    },
    "general": {
        "name": "General",
        "aspect_ratios": ["1:1", "3:4", "16:9"],
        "max_text_ratio": 0.35,
        "safe_zone_inset": 0.05,
    },
}


# ══════════════════════════════════════════════════════════════════════════════
# Keyword Rules
# ══════════════════════════════════════════════════════════════════════════════

_TYPE_RULES: list[tuple[list[str], str, float]] = [
    # (keywords, creative_type, weight)
    (["poster", "flyer", "billboard", "print ad", "print poster"], "poster", 1.0),
    (["advertisement", "ad ", " ad,", "commercial", "promo", "marketing",
      "campaign", "brand", "branding"], "ad", 1.0),
    (["banner", "web banner", "header", "hero", "landing page"], "banner", 1.0),
    (["instagram", "ig ", "social media", "facebook", "tiktok", "reel",
      "story", "post"], "social", 1.0),
    (["product shot", "packshot", "e-commerce", "catalog", "merchandise",
      "product photo"], "product_shot", 1.0),
    (["editorial", "magazine", "cover", "vogue", "lookbook", "spread"], "editorial", 1.0),
    # Implicit poster signals (weaker)
    (["sale", "discount", "% off", "offer", "deal", "buy now", "shop now",
      "limited time", "clearance", "free shipping"], "ad", 0.7),
    (["headline", "tagline", "slogan", "call to action", "cta"], "poster", 0.5),
]

_PLATFORM_RULES: list[tuple[list[str], str]] = [
    (["instagram", "ig ", "insta"], "instagram"),
    (["facebook", "fb "], "facebook"),
    (["youtube", "yt ", "thumbnail"], "youtube"),
    (["tiktok", "tik tok", "reels"], "tiktok"),
    (["print", "a4", "a3", "poster", "flyer", "billboard"], "print"),
    (["banner", "web", "website", "landing page", "header"], "web"),
]

_GOAL_RULES: list[tuple[list[str], str]] = [
    (["sale", "discount", "buy", "shop", "purchase", "order", "deal",
      "price", "offer", "limited", "checkout"], "conversion"),
    (["brand", "awareness", "launch", "announce", "introducing", "new",
      "coming soon", "reveal"], "awareness"),
    (["like", "share", "comment", "follow", "subscribe", "engage",
      "viral", "trending", "challenge"], "engagement"),
    (["info", "learn", "tutorial", "how to", "guide", "tips",
      "educational", "infographic"], "informational"),
]

_TONE_RULES: list[tuple[list[str], str]] = [
    (["luxury", "premium", "elegant", "exclusive", "high-end", "vip",
      "sophisticated"], "luxury"),
    (["fun", "playful", "cute", "bright", "colorful", "happy",
      "cheerful", "party"], "playful"),
    (["urgent", "hurry", "limited time", "last chance", "don't miss",
      "ending soon", "flash sale", "now"], "urgent"),
    (["corporate", "business", "professional", "office", "enterprise",
      "b2b", "formal"], "professional"),
]


# ══════════════════════════════════════════════════════════════════════════════
# Analyzer Class
# ══════════════════════════════════════════════════════════════════════════════

class IntentAnalyzer:
    """
    Classifies user prompt into structured creative intent.

    This runs BEFORE everything else — creative director, layout planner,
    even text overlay detection. It gives every downstream module context
    about what the user is actually trying to create.
    """

    def analyze(self, prompt: str, width: int = 1024, height: int = 1024) -> CreativeIntent:
        """
        Analyze prompt and return structured creative intent.

        Args:
            prompt: Raw user prompt
            width/height: Requested dimensions (can hint at platform)

        Returns:
            CreativeIntent with all classification fields
        """
        p = prompt.lower()

        # ── Detect creative type ────────────────────────────────────────
        creative_type = self._detect_type(p)

        # ── Detect platform ─────────────────────────────────────────────
        platform_name = self._detect_platform(p, width, height)
        platform = PLATFORMS[platform_name]

        # ── Detect goal ─────────────────────────────────────────────────
        goal = self._detect_goal(p, creative_type)

        # ── Detect audience tone ────────────────────────────────────────
        tone = self._detect_tone(p)

        # ── Calculate CTA strength ──────────────────────────────────────
        cta_strength = self._calc_cta_strength(p, creative_type, goal)

        # ── Derived flags ───────────────────────────────────────────────
        is_ad = creative_type in ("ad", "poster", "banner", "social")
        text_heavy = is_ad or creative_type == "editorial" or cta_strength > 0.5

        # ── Prompt hints for downstream modules ─────────────────────────
        prompt_hints = self._build_hints(creative_type, platform_name, goal, tone)

        intent = CreativeIntent(
            creative_type=creative_type,
            platform=platform,
            goal=goal,
            audience_tone=tone,
            cta_strength=cta_strength,
            is_ad=is_ad,
            text_heavy=text_heavy,
            prompt_hints=prompt_hints,
        )

        logger.info(
            "[INTENT] type=%s platform=%s goal=%s tone=%s cta=%.2f ad=%s",
            creative_type, platform_name, goal, tone, cta_strength, is_ad,
        )

        return intent

    # ── Detection methods ──────────────────────────────────────────────────

    def _detect_type(self, prompt_lower: str) -> str:
        scores: Dict[str, float] = {}
        for keywords, ctype, weight in _TYPE_RULES:
            for kw in keywords:
                if kw in prompt_lower:
                    scores[ctype] = scores.get(ctype, 0) + weight
        if not scores:
            return "photo"
        return max(scores, key=scores.get)

    def _detect_platform(self, prompt_lower: str, w: int, h: int) -> str:
        # Explicit keyword match
        for keywords, platform in _PLATFORM_RULES:
            if any(kw in prompt_lower for kw in keywords):
                return platform

        # Infer from aspect ratio
        ratio = w / h if h > 0 else 1.0
        if ratio > 2.5:
            return "web"        # very wide = banner
        if ratio > 1.5:
            return "youtube"    # 16:9-ish
        if ratio < 0.6:
            return "tiktok"     # very tall = story/reel

        return "general"

    def _detect_goal(self, prompt_lower: str, creative_type: str) -> str:
        for keywords, goal in _GOAL_RULES:
            if any(kw in prompt_lower for kw in keywords):
                return goal
        # Default based on creative type
        if creative_type in ("ad", "banner"):
            return "conversion"
        if creative_type in ("poster", "social"):
            return "awareness"
        return "aesthetic"

    def _detect_tone(self, prompt_lower: str) -> str:
        for keywords, tone in _TONE_RULES:
            if any(kw in prompt_lower for kw in keywords):
                return tone
        return "casual"

    def _calc_cta_strength(self, prompt_lower: str, ctype: str, goal: str) -> float:
        """0.0 = no CTA needed, 1.0 = strong CTA urgency."""
        score = 0.0

        # Creative type contribution
        type_scores = {"ad": 0.4, "poster": 0.3, "banner": 0.35, "social": 0.2}
        score += type_scores.get(ctype, 0.0)

        # Goal contribution
        goal_scores = {"conversion": 0.4, "engagement": 0.2, "awareness": 0.1}
        score += goal_scores.get(goal, 0.0)

        # Urgency keywords boost
        urgency = ["buy now", "shop now", "limited", "hurry", "don't miss",
                    "last chance", "order now", "get yours", "act now"]
        hits = sum(1 for u in urgency if u in prompt_lower)
        score += min(hits * 0.1, 0.3)

        return min(score, 1.0)

    def _build_hints(
        self, ctype: str, platform: str, goal: str, tone: str
    ) -> Dict[str, str]:
        """Build prompt hints that downstream modules can inject."""
        hints: Dict[str, str] = {}

        # Composition hint based on creative type
        if ctype in ("poster", "ad", "banner"):
            hints["composition"] = "clean negative space for text placement, uncluttered background areas"
        if ctype == "product_shot":
            hints["composition"] = "clean studio background, product centered, soft reflective surface"

        # Tone → lighting hint
        tone_lighting = {
            "luxury": "premium studio lighting, rich deep shadows",
            "playful": "bright cheerful lighting, soft shadows",
            "urgent": "high contrast dramatic lighting, attention-grabbing",
            "professional": "clean even lighting, balanced exposure",
        }
        if tone in tone_lighting:
            hints["lighting"] = tone_lighting[tone]

        # Platform-specific hints
        if platform == "instagram":
            hints["framing"] = "mobile-friendly composition, bold visual impact"
        elif platform == "youtube":
            hints["framing"] = "wide cinematic framing, space for title text"
        elif platform == "print":
            hints["framing"] = "high-resolution detail, print-quality sharpness"

        return hints


# Singleton
intent_analyzer = IntentAnalyzer()
