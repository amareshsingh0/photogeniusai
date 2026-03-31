"""
Variant Generator — Auto-generate 2-3 layout/color variants for poster/ad mode.

Generates PROMPT-LEVEL variants BEFORE GPU generation, so each variant
gets a different composition, color scheme, and text arrangement.

Variant types:
    1. Layout variant   — Different creative graph template
    2. Color variant    — Different theme/palette applied to prompt
    3. Text variant     — Different text position/emphasis

This module does NOT re-generate images. It produces variant configs
that the pipeline can generate in parallel or let the user choose from.

Feature Flag:
    USE_VARIANT_GENERATION = True
"""

from __future__ import annotations

import logging
import random
from typing import Dict, List, Optional, TypedDict

from .config import STYLES, THEMES, DEFAULT_THEME, get_style

logger = logging.getLogger(__name__)

USE_VARIANT_GENERATION = True

# Max variants to generate
MAX_VARIANTS = 3


# ══════════════════════════════════════════════════════════════════════════════
# Types
# ══════════════════════════════════════════════════════════════════════════════

class VariantConfig(TypedDict):
    variant_id: str                  # "v1", "v2", "v3"
    label: str                       # Human-readable label
    variant_type: str                # "layout" | "color" | "text" | "combined"
    template: str                    # Creative graph template name
    style: str                       # Style from config
    color_palette: List[str]         # Suggested colors
    text_position: str               # "top" | "bottom" | "center" | "left" | "right"
    prompt_modifier: str             # Extra prompt keywords for this variant
    negative_modifier: str           # Extra negative keywords


class VariantSet(TypedDict):
    variants: List[VariantConfig]
    primary_variant: str             # variant_id of recommended primary
    generation_strategy: str         # "parallel" | "sequential" | "user_choice"


# ══════════════════════════════════════════════════════════════════════════════
# Template → variant mappings
# ══════════════════════════════════════════════════════════════════════════════

# Layout templates with their characteristics
_LAYOUT_VARIANTS = {
    "poster_standard": {
        "label": "Classic Poster",
        "text_pos": "top",
        "prompt_mod": "clean top space for headline, bold visual hierarchy",
        "neg_mod": "cluttered top area",
    },
    "poster_bold": {
        "label": "Bold Impact",
        "text_pos": "center",
        "prompt_mod": "dramatic centered composition, strong visual impact, bold design",
        "neg_mod": "weak composition, timid design",
    },
    "banner_horizontal": {
        "label": "Wide Banner",
        "text_pos": "left",
        "prompt_mod": "panoramic layout, subject on right, text space on left",
        "neg_mod": "cramped layout, centered subject",
    },
    "social_square": {
        "label": "Social Media",
        "text_pos": "bottom",
        "prompt_mod": "trendy social media aesthetic, eye-catching composition",
        "neg_mod": "boring corporate, stock photo feel",
    },
    "product_centered": {
        "label": "Product Focus",
        "text_pos": "bottom",
        "prompt_mod": "clean studio backdrop, product hero shot, minimal background",
        "neg_mod": "background clutter, busy environment",
    },
    "editorial_split": {
        "label": "Editorial Split",
        "text_pos": "left",
        "prompt_mod": "editorial magazine layout, split composition, sophisticated design",
        "neg_mod": "amateur layout, poor composition",
    },
}

# Color palette variants
_COLOR_VARIANTS = [
    {
        "label": "Vibrant",
        "colors": ["#FF6B35", "#F7C948", "#00D2FF", "#FF2E63"],
        "prompt_mod": "vibrant saturated colors, high energy color palette",
        "neg_mod": "muted colors, desaturated, dull",
    },
    {
        "label": "Elegant Dark",
        "colors": ["#1A1A2E", "#16213E", "#E94560", "#FFD700"],
        "prompt_mod": "elegant dark theme, rich deep tones, luxury feel",
        "neg_mod": "bright flat colors, cheap look",
    },
    {
        "label": "Clean Minimal",
        "colors": ["#FFFFFF", "#F5F5F5", "#333333", "#6366F1"],
        "prompt_mod": "clean minimalist design, white space, refined simplicity",
        "neg_mod": "cluttered, busy, overly colorful",
    },
    {
        "label": "Warm Earthy",
        "colors": ["#D4A574", "#8B6F47", "#2C5F2D", "#F2E8CF"],
        "prompt_mod": "warm earthy tones, natural organic palette, rustic warmth",
        "neg_mod": "cold clinical, artificial colors",
    },
    {
        "label": "Cool Tech",
        "colors": ["#0A0E27", "#00D4FF", "#7B2FFF", "#00FF88"],
        "prompt_mod": "futuristic tech aesthetic, cool neon accents, digital vibes",
        "neg_mod": "organic, rustic, outdated design",
    },
    {
        "label": "Pastel Soft",
        "colors": ["#FFB5E8", "#B5DEFF", "#CAFFBF", "#FDFFB6"],
        "prompt_mod": "soft pastel palette, gentle soothing colors, dreamy aesthetic",
        "neg_mod": "harsh contrast, aggressive colors",
    },
]


class VariantGenerator:
    """Generate prompt-level variants for poster/ad content."""

    def generate(
        self,
        creative_type: str = "general",
        is_ad: bool = False,
        template: str = "poster_standard",
        style: str = "poster",
        goal: str = "awareness",
        aspect_ratio: float = 1.0,
        theme_label: str = "",
        num_variants: int = MAX_VARIANTS,
    ) -> VariantSet:
        """
        Generate variant configs for poster/ad content.

        Returns a VariantSet with 2-3 variants that differ in layout,
        color, and text placement. These are prompt-level variants —
        actual image generation happens separately.
        """
        if not USE_VARIANT_GENERATION:
            return VariantSet(
                variants=[],
                primary_variant="",
                generation_strategy="user_choice",
            )

        num_variants = min(num_variants, MAX_VARIANTS)
        variants: List[VariantConfig] = []

        # Determine which layout templates fit
        suitable_templates = self._pick_templates(
            creative_type, aspect_ratio, template, num_variants
        )

        # Determine color variants
        color_picks = self._pick_colors(theme_label, style, num_variants)

        # Build variant configs
        for i in range(num_variants):
            tmpl_name = suitable_templates[i % len(suitable_templates)]
            tmpl = _LAYOUT_VARIANTS.get(tmpl_name, _LAYOUT_VARIANTS["poster_standard"])
            colors = color_picks[i % len(color_picks)]

            # Determine style per variant
            variant_style = style
            if i == 1 and style == "poster":
                variant_style = "marketing"  # slight variation
            elif i == 2 and style in ("poster", "marketing"):
                variant_style = "social"

            variant = VariantConfig(
                variant_id=f"v{i+1}",
                label=f"{tmpl['label']} / {colors['label']}",
                variant_type="combined",
                template=tmpl_name,
                style=variant_style,
                color_palette=colors["colors"],
                text_position=tmpl["text_pos"],
                prompt_modifier=f"{tmpl['prompt_mod']}, {colors['prompt_mod']}",
                negative_modifier=f"{tmpl['neg_mod']}, {colors['neg_mod']}",
            )
            variants.append(variant)

        # Primary = first variant (original intent)
        primary = variants[0]["variant_id"] if variants else ""

        strategy = "user_choice" if is_ad else "user_choice"

        logger.info(
            "[VARIANT] Generated %d variants for type=%s style=%s: %s",
            len(variants), creative_type, style,
            [v["label"] for v in variants],
        )

        return VariantSet(
            variants=variants,
            primary_variant=primary,
            generation_strategy=strategy,
        )

    def _pick_templates(
        self,
        creative_type: str,
        aspect_ratio: float,
        current_template: str,
        count: int,
    ) -> List[str]:
        """Pick suitable layout templates based on content type and aspect ratio."""
        # Start with current template
        candidates = [current_template]

        # Add alternatives based on aspect ratio
        if aspect_ratio > 1.5:
            # Wide → banner templates
            preferred = ["banner_horizontal", "editorial_split", "social_square"]
        elif aspect_ratio < 0.7:
            # Tall → poster templates
            preferred = ["poster_standard", "poster_bold", "product_centered"]
        else:
            # Square-ish → social/product
            preferred = ["social_square", "poster_standard", "product_centered"]

        # Add preferred templates that aren't already selected
        for tmpl in preferred:
            if tmpl not in candidates:
                candidates.append(tmpl)
            if len(candidates) >= count:
                break

        # Fill remaining with any template
        all_templates = list(_LAYOUT_VARIANTS.keys())
        for tmpl in all_templates:
            if tmpl not in candidates:
                candidates.append(tmpl)
            if len(candidates) >= count:
                break

        return candidates[:count]

    def _pick_colors(self, theme_label: str, style: str, count: int) -> List[Dict]:
        """Pick color palettes that complement the theme."""
        # Try to match theme to color variants
        scored: List[tuple] = []
        theme_lower = theme_label.lower() if theme_label else ""

        for cv in _COLOR_VARIANTS:
            score = 0
            label_lower = cv["label"].lower()

            # Boost matching themes
            if "luxury" in theme_lower and "elegant" in label_lower:
                score += 3
            elif "tech" in theme_lower and "tech" in label_lower:
                score += 3
            elif "nature" in theme_lower and "earthy" in label_lower:
                score += 3
            elif "food" in theme_lower and "warm" in label_lower:
                score += 3
            elif "minimalist" in theme_lower and "minimal" in label_lower:
                score += 3
            elif "romantic" in theme_lower and "pastel" in label_lower:
                score += 3

            # Style boost
            if style in ("poster", "marketing", "banner") and "vibrant" in label_lower:
                score += 1
            elif style == "editorial" and "minimal" in label_lower:
                score += 1

            # Add randomness for variety
            score += random.random() * 0.5
            scored.append((score, cv))

        scored.sort(key=lambda x: -x[0])
        return [s[1] for s in scored[:count]]


# Singleton
variant_generator = VariantGenerator()
