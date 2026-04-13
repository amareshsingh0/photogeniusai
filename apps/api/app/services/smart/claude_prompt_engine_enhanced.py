"""
Claude Prompt Engine v2 — Enhanced with Gemini-level capabilities
Bucket-aware + Model-specific + Validator + Critic + CDI + Cognitive Aesthetics

Architecture:
  DEFAULT PATH  (all buckets, all tiers):
    Stage A: Sonnet 4.6 bucket-specific → Creative Brief JSON
    Stage B: Haiku 4.5 model-specific  → generation params JSON
    Validator: schema + budget + bucket-rule check

  HARD BUCKET PATH (anime, typography, editing, architecture — premium/ultra only):
    Stage A: bucket-specific brief
    Stage B: model-specific params
    Critic:  specialist review → targeted refinements
    Stage B2: re-generate params with critic notes injected
    Validator: final check

Fallback chain:
  Claude fail → heuristic_brief + heuristic_params (never crash)

Feature flags (env):
  ANTHROPIC_API_KEY   → enables Claude (falls back to heuristic if absent)
  USE_CLAUDE_ENGINE   → set false to force heuristic (default true)
"""

from __future__ import annotations

import colorsys
import json
import logging
import os
import re
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
# Hex → Natural Language Color Translation (APEX model-native syntax)
# Models respond better to descriptive color language than raw hex codes.
# ══════════════════════════════════════════════════════════════════════════════

_HEX_NL_MAP: Dict[str, str] = {
    # Reds / Oranges
    "#FF0000": "pure red", "#CC0000": "deep crimson", "#FF4444": "vivid coral red",
    "#FF6B00": "vivid deep orange", "#FF7700": "bright amber orange",
    "#FF9933": "saffron gold", "#E8593C": "deep burnt orange",
    "#FF5733": "warm vermillion", "#D44000": "rich terracotta",
    # Yellows / Golds
    "#FFD700": "bright gold", "#FFC107": "amber gold", "#C9A84C": "antique gold",
    "#F59E0B": "warm amber", "#FBBF24": "golden yellow",
    # Greens
    "#00FF00": "pure lime green", "#22C55E": "vivid emerald green",
    "#138808": "deep forest green", "#16A34A": "rich green",
    "#059669": "teal green", "#10B981": "fresh mint green",
    # Blues / Cyans
    "#0000FF": "pure blue", "#2563EB": "vivid royal blue",
    "#4FACFE": "bright azure blue", "#00D4FF": "electric cyan",
    "#0EA5E9": "bright sky blue", "#38BDF8": "light cerulean",
    "#0F3460": "deep midnight blue", "#1E40AF": "rich cobalt blue",
    # Purples / Violets
    "#6C63FF": "electric violet", "#7C3AED": "deep purple",
    "#8B5CF6": "soft lavender purple", "#A855F7": "bright amethyst",
    "#6D28D9": "rich indigo violet", "#4C1D95": "deep plum",
    # Pinks / Magentas
    "#FF00FF": "pure magenta", "#EC4899": "vivid hot pink",
    "#F43F5E": "bold rose red", "#FB7185": "soft coral pink",
    # Neutrals / Darks
    "#000000": "pure black", "#0A0A0A": "near-black",
    "#0A0A1A": "near-black midnight navy", "#1A1A2E": "deep midnight navy",
    "#111827": "charcoal black", "#1F2937": "dark slate",
    "#374151": "dark grey", "#6B7280": "medium grey",
    "#9CA3AF": "light grey", "#D1D5DB": "soft silver",
    "#F3F4F6": "near-white", "#FFFFFF": "pure white",
    # Brand-typical
    "#0F172A": "very dark navy", "#1E293B": "dark slate navy",
    "#312E81": "deep indigo", "#4F46E5": "vivid indigo",
}

# Hue→color name mapping for HSV-based fallback
_HUE_NAMES = [
    (15,  "red"), (45, "orange"), (65, "yellow"), (80, "yellow-green"),
    (150, "green"), (185, "teal"), (210, "cyan"), (240, "blue"),
    (265, "indigo"), (285, "violet"), (330, "purple"), (345, "pink"), (360, "red"),
]


def _hex_to_natural(hex_color: str) -> str:
    """
    Convert a hex color to a natural language description that models understand.
    Priority: exact map → HSV-based description.
    """
    if not hex_color:
        return ""
    h = hex_color.upper().strip()
    if not h.startswith("#"):
        h = "#" + h
    # Normalise 3-char shorthand
    if len(h) == 4:
        h = "#" + h[1]*2 + h[2]*2 + h[3]*2
    if len(h) != 7:
        return hex_color  # can't parse — return as-is

    # Exact map lookup
    exact = _HEX_NL_MAP.get(h)
    if exact:
        return exact

    # HSV-based description
    try:
        r = int(h[1:3], 16) / 255.0
        g = int(h[3:5], 16) / 255.0
        b = int(h[5:7], 16) / 255.0
        hue_f, sat, val = colorsys.rgb_to_hsv(r, g, b)
        hue = int(hue_f * 360)

        # Determine lightness adjective
        if val < 0.20:
            lightness = "very dark"
        elif val < 0.45:
            lightness = "dark"
        elif val < 0.65:
            lightness = "medium"
        elif val < 0.85:
            lightness = "bright"
        else:
            lightness = "light"

        # Determine saturation adjective
        if sat < 0.12:
            # Achromatic
            if val < 0.15:
                return "near-black"
            elif val > 0.92:
                return "near-white"
            else:
                return f"{lightness} grey"

        sat_adj = "muted " if sat < 0.40 else ("vivid " if sat > 0.75 else "")

        # Find hue name
        color_name = "colour"
        for threshold, name in _HUE_NAMES:
            if hue <= threshold:
                color_name = name
                break

        return f"{lightness} {sat_adj}{color_name}".strip()
    except Exception:
        return hex_color

# ── Feature flags (read at call time via property, not import time) ────────────
def _is_claude_enabled() -> bool:
    key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    flag = os.getenv("USE_CLAUDE_ENGINE", "true").strip().lower()
    return bool(key) and flag not in ("false", "0", "no", "off")

# Module-level alias kept for legacy imports
USE_CLAUDE_ENGINE: bool = _is_claude_enabled()

# Buckets that get a critic agent on premium/ultra
_HARD_BUCKETS = {"anime", "typography", "editing", "interior_arch", "character_consistency"}

