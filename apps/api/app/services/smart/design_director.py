"""
Senior Design Director Agent — Visual System Authority

Receives: Creative Director's concept + Creative Bible
Outputs: Visual System Decree (NON-NEGOTIABLE for all downstream)

Role: Issues Visual System Decree — composition law, grid, type scale, color authority
Position: Between Creative Director and downstream agents (Copy Writer, Layout Planner)

Philosophy (from SeniorCreativeDirector.md):
- One idea, executed without compromise
- Emotion first, information second
- Cultural fluency is not optional
- The brief is a starting point (interrogate it)
- "Attention is not earned by beauty. It is earned by truth made visible."
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from typing import Dict, List, Optional

from app.config.loader import config as beast_config

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
# Composition Archetypes (from Creative Director KB)
# ══════════════════════════════════════════════════════════════════════════════

COMPOSITION_ARCHETYPES = {
    "hero_dominant": {
        "description": "One dominant visual element occupies 60-70% of canvas",
        "grid": "12-column asymmetric",
        "hierarchy": ["hero_image", "headline", "cta", "tagline"],
        "whitespace": "breathe",
        "best_for": ["luxury", "fashion", "editorial"]
    },
    "split_60_40": {
        "description": "Image 60% / Copy 40% clear division",
        "grid": "6-6 split or 7-5 split",
        "hierarchy": ["hero_image", "headline", "subheadline", "cta"],
        "whitespace": "structured",
        "best_for": ["product launch", "app promo", "service ad"]
    },
    "typographic_led": {
        "description": "Typography dominates, image supports",
        "grid": "centered or modular",
        "hierarchy": ["headline", "hero_image", "subheadline", "cta"],
        "whitespace": "dense but intentional",
        "best_for": ["sale announcements", "event posters", "typography bucket"]
    },
    "frame_within_frame": {
        "description": "Nested visual frames create depth",
        "grid": "custom nested",
        "hierarchy": ["outer_frame", "inner_hero", "headline", "cta"],
        "whitespace": "structured void",
        "best_for": ["premium brands", "architectural", "editorial"]
    },
    "dynamic_diagonal": {
        "description": "Diagonal energy, high tension",
        "grid": "diagonal grid (rotated 15-30°)",
        "hierarchy": ["diagonal_element", "headline", "cta", "brand"],
        "whitespace": "movement",
        "best_for": ["sports", "fitness", "youth brands", "energy drinks"]
    },
    "asymmetric_grid": {
        "description": "Intentional imbalance creates visual interest",
        "grid": "12-column with rule-of-thirds overlay",
        "hierarchy": ["dominant_left_third", "headline", "cta_bottom_right", "brand_top"],
        "whitespace": "tension",
        "best_for": ["modern brands", "tech", "challenger brands"]
    },
    "full_bleed": {
        "description": "Image bleeds to all edges, minimal copy overlay",
        "grid": "safe zones only (5% margins)",
        "hierarchy": ["full_image", "headline_overlay", "cta_bottom"],
        "whitespace": "minimal",
        "best_for": ["travel", "lifestyle", "aspirational brands"]
    }
}

# ══════════════════════════════════════════════════════════════════════════════
# Type Scales (responsive to canvas size)
# ══════════════════════════════════════════════════════════════════════════════

TYPE_SCALES = {
    "major_third": {
        "ratio": 1.250,
        "description": "Balanced, readable (Bebas Neue, Montserrat)",
        "h1": 0.12,  # 12% of canvas width
        "h2": 0.08,
        "h3": 0.05,
        "body": 0.03,
        "caption": 0.02
    },
    "perfect_fourth": {
        "ratio": 1.333,
        "description": "Strong hierarchy (Anton, Impact)",
        "h1": 0.14,
        "h2": 0.09,
        "h3": 0.06,
        "body": 0.035,
        "caption": 0.022
    },
    "augmented_fourth": {
        "ratio": 1.414,
        "description": "Dramatic contrast (Playfair Display luxury)",
        "h1": 0.16,
        "h2": 0.10,
        "h3": 0.065,
        "body": 0.04,
        "caption": 0.025
    },
    "golden_ratio": {
        "ratio": 1.618,
        "description": "Natural harmony (editorial layouts)",
        "h1": 0.18,
        "h2": 0.11,
        "h3": 0.07,
        "body": 0.043,
        "caption": 0.027
    },
    "minimal": {
        "ratio": 1.125,
        "description": "Subtle, restrained (quiet luxury)",
        "h1": 0.10,
        "h2": 0.07,
        "h3": 0.048,
        "body": 0.032,
        "caption": 0.020
    }
}

# ══════════════════════════════════════════════════════════════════════════════
# Design Director Agent
# ══════════════════════════════════════════════════════════════════════════════

class DesignDirector:
    """
    Senior Design Director — Visual System Authority

    Issues Visual System Decree based on Creative Bible + Brand + Platform.
    Decree is NON-NEGOTIABLE for all downstream agents.
    """

    def __init__(self, gemini_client=None):
        self.client = gemini_client
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-exp")

    async def issue_decree(
        self,
        creative_bible: Dict,
        brand_palette: Dict,
        platform: str,
        aspect_ratio: float,
        triage: Dict,
        industry: str = "general",
    ) -> Dict:
        """
        Issues Visual System Decree.

        Returns:
        {
            "composition_law": "asymmetric_grid",
            "grid_system": {...},
            "type_scale": {...},
            "color_usage_rules": {...},
            "hierarchy_enforcement": [...],
            "forbidden_violations": [...],
            "decree_confidence": 0.92
        }
        """
        # Get composition archetype from Creative Bible
        comp_archetype = creative_bible.get("composition_archetype", "hero_dominant")

        # Load archetype from BeastConfig (with legacy fallback)
        archetype_data = beast_config.get_composition_archetype(comp_archetype)
        if not archetype_data:
            # Fallback to legacy if not in BeastConfig
            archetype_data = COMPOSITION_ARCHETYPES.get(comp_archetype)

        # Deterministic decree for known archetypes
        if archetype_data:
            # Select type scale based on platform + brand personality
            type_scale_key = beast_config.select_scale_by_platform(platform)
            # Override with brand personality if available
            if brand_palette.get("font_personality"):
                type_scale_key = beast_config.select_scale_by_brand_personality(
                    brand_palette.get("font_personality")
                )

            # Load type scale from BeastConfig (with legacy fallback)
            type_scale_data = beast_config.get_type_scale(type_scale_key)
            if not type_scale_data:
                # Fallback to legacy if not in BeastConfig
                type_scale_key_legacy = self._select_type_scale(industry, triage.get("goal", ""))
                type_scale_data = TYPE_SCALES.get(type_scale_key_legacy, TYPE_SCALES["balanced"])

            logger.info(f"[DesignDirector] BeastConfig: archetype={comp_archetype}, type_scale={type_scale_key}")

            # Adapt to BeastConfig structure (composition_archetypes.json) or legacy
            is_beast_config = "composition_rules" in archetype_data

            if is_beast_config:
                # BeastConfig structure
                comp_rules = archetype_data.get("composition_rules", {})
                space_char = archetype_data.get("space_character", {})
                typo_treat = archetype_data.get("typography_treatment", {})

                grid_type = comp_rules.get("grid", "12-column asymmetric")
                description = archetype_data.get("visual_description", "Composition archetype")
                hierarchy = typo_treat.get("acceptable_placements", ["top_center", "bottom_third"])
                whitespace = space_char.get("type", "balanced")
            else:
                # Legacy structure
                grid_type = archetype_data.get("grid", "12-column")
                description = archetype_data.get("description", "Composition archetype")
                hierarchy = archetype_data.get("hierarchy", ["hero_image", "headline", "cta"])
                whitespace = archetype_data.get("whitespace", "balanced")

            # Build type_scale structure (adapt to BeastConfig or legacy)
            is_beast_type_scale = "scale_px" in type_scale_data

            if is_beast_type_scale:
                # BeastConfig type_scales.json structure
                scale_px = type_scale_data.get("scale_px", {})
                display = scale_px.get("display_hero", {})
                h1 = scale_px.get("headline_primary", {})
                h2 = scale_px.get("subheadline", {})
                body = scale_px.get("body", {})
                caption = scale_px.get("caption", {})

                type_scale_decree = {
                    "scale_name": type_scale_key,
                    "hierarchy_ratio": type_scale_data.get("hierarchy_ratio", "8:5.33:2.67:1.67:1"),
                    "display_hero_px": display.get("size_px", 96),
                    "h1_px": h1.get("size_px", 64),
                    "h2_px": h2.get("size_px", 32),
                    "body_px": body.get("size_px", 16),
                    "caption_px": caption.get("size_px", 12),
                    "description": type_scale_data.get("use_case", "Professional type scale")
                }
            else:
                # Legacy structure
                type_scale_decree = {
                    "scale_name": type_scale_key,
                    "ratio": type_scale_data.get("ratio", "1.5"),
                    "h1_canvas_pct": type_scale_data.get("h1", 12),
                    "h2_canvas_pct": type_scale_data.get("h2", 8),
                    "h3_canvas_pct": type_scale_data.get("h3", 5),
                    "body_canvas_pct": type_scale_data.get("body", 3),
                    "caption_canvas_pct": type_scale_data.get("caption", 2),
                    "description": type_scale_data.get("description", "Type scale")
                }

            # Build decree
            decree = {
                "composition_law": comp_archetype,
                "composition_description": description,

                "grid_system": {
                    "type": grid_type,
                    "columns": 12 if "12" in str(grid_type) else 6,
                    "gutter_px": 16,
                    "margins_pct": 5.0,
                    "safe_zones": {
                        "top": 0.07,    # 7% for brand bar
                        "bottom": 0.10, # 10% for CTA
                        "sides": 0.05   # 5% edge breathing
                    }
                },

                "type_scale": type_scale_decree,

                "color_usage_rules": {
                    "dominant_pct": 60,   # Primary color
                    "secondary_pct": 30,  # Secondary color
                    "accent_pct": 10,     # Accent for CTA/highlights
                    "max_colors": 3,      # Max 3 colors + neutrals
                    "rule": "60-30-10 color authority — never exceed 3 colors + neutrals",
                    "dominant_color": brand_palette.get("primary_color", "#000000"),
                    "secondary_color": brand_palette.get("secondary_color", "#FFFFFF"),
                    "accent_color": brand_palette.get("accent_color", "#FF6B00")
                },

                "hierarchy_enforcement": hierarchy,

                "whitespace_philosophy": whitespace,

                "forbidden_violations": [
                    "Centered everything (must use asymmetry unless full_bleed)",
                    "Equal-sized text (must show clear hierarchy)",
                    "Rainbow colors (max 3 + neutrals enforced)",
                    "Text over busy areas (preserve copy space)",
                    "Logo as afterthought (integrate naturally)",
                    "Generic stock aesthetic (must feel intentional)"
                ],

                "platform_constraints": self._get_platform_constraints(platform),

                "decree_confidence": 0.95,  # Deterministic decree
                "decree_source": "beast_config" if is_beast_config else "legacy_library"
            }

            logger.info(f"[DesignDirector] Decree issued: {comp_archetype} + {type_scale_key} scale")
            return decree

        # Fallback: LLM-based decree for unknown archetypes
        else:
            logger.warning(f"[DesignDirector] Unknown archetype '{comp_archetype}', using LLM decree")
            return await self._llm_decree(creative_bible, brand_palette, platform, aspect_ratio, industry)

    def _select_type_scale(self, industry: str, goal: str) -> str:
        """Select type scale based on industry + goal."""
        industry_lower = industry.lower()
        goal_lower = goal.lower()

        # Luxury / Fashion → Golden ratio or Augmented Fourth
        if industry_lower in ["luxury", "fashion", "beauty", "jewelry"]:
            return "augmented_fourth"

        # Fitness / Sports / Youth → Perfect Fourth (strong hierarchy)
        if industry_lower in ["fitness", "sports", "energy", "youth"]:
            return "perfect_fourth"

        # Tech / Modern / Minimal → Minimal scale
        if industry_lower in ["tech", "saas", "minimal", "architecture"]:
            return "minimal"

        # Editorial / Content → Golden ratio
        if "editorial" in goal_lower or "content" in goal_lower:
            return "golden_ratio"

        # Default: Major Third (balanced)
        return "major_third"

    def _get_platform_constraints(self, platform: str) -> Dict:
        """Platform-specific constraints."""
        platform_lower = platform.lower()

        PLATFORM_RULES = {
            "instagram": {
                "text_max_pct": 20,  # Text should not exceed 20% of canvas
                "min_contrast_ratio": 4.5,
                "recommended_formats": ["portrait 4:5", "square 1:1"],
                "attention_window": "1.5s",
                "aesthetic": "editorial quality, color story, curated grids"
            },
            "tiktok": {
                "text_max_pct": 30,  # More text OK for TikTok
                "min_contrast_ratio": 7.0,  # High contrast required
                "recommended_formats": ["vertical 9:16"],
                "attention_window": "0.5s",
                "aesthetic": "text-forward, meme-fluent, raw edges"
            },
            "facebook": {
                "text_max_pct": 15,
                "min_contrast_ratio": 4.5,
                "recommended_formats": ["landscape 1.91:1", "square 1:1"],
                "attention_window": "2s",
                "aesthetic": "clean, family-friendly, readable"
            },
            "linkedin": {
                "text_max_pct": 25,
                "min_contrast_ratio": 4.5,
                "recommended_formats": ["landscape 1.91:1"],
                "attention_window": "3s",
                "aesthetic": "authority signals, restraint, professionalism"
            },
            "billboard": {
                "text_max_pct": 10,  # Minimal text for 80mph viewing
                "min_contrast_ratio": 10.0,  # Maximum contrast
                "recommended_formats": ["wide landscape 3:1"],
                "attention_window": "3s at 80mph",
                "aesthetic": "single idea, readable at distance, bold color"
            }
        }

        return PLATFORM_RULES.get(platform_lower, {
            "text_max_pct": 20,
            "min_contrast_ratio": 4.5,
            "recommended_formats": ["4:5"],
            "attention_window": "2s",
            "aesthetic": "balanced, clear hierarchy"
        })

    async def _llm_decree(
        self,
        creative_bible: Dict,
        brand_palette: Dict,
        platform: str,
        aspect_ratio: float,
        industry: str
    ) -> Dict:
        """Fallback: LLM-generated decree for unknown cases."""

        if not self.client:
            logger.error("[DesignDirector] No Gemini client, returning fallback decree")
            return self._fallback_decree()

        prompt = f"""You are a Senior Design Director issuing a Visual System Decree.

Creative Bible (LOCKED decisions from Creative Director):
{json.dumps(creative_bible, indent=2)}

Brand Palette:
{json.dumps(brand_palette, indent=2)}

Platform: {platform}
Industry: {industry}
Aspect Ratio: {aspect_ratio}

YOUR TASK: Issue a Visual System Decree that all downstream agents MUST follow.

Return ONLY valid JSON (no markdown):
{{
    "composition_law": "one of: hero_dominant | split_60_40 | typographic_led | frame_within_frame | dynamic_diagonal | asymmetric_grid | full_bleed",
    "grid_system": {{
        "type": "12-column asymmetric | 6-6 split | centered modular | custom",
        "columns": 12,
        "gutter_px": 16,
        "margins_pct": 5.0,
        "safe_zones": {{"top": 0.07, "bottom": 0.10, "sides": 0.05}}
    }},
    "type_scale": {{
        "scale_name": "major_third | perfect_fourth | golden_ratio | minimal",
        "ratio": 1.250,
        "h1_canvas_pct": 0.12,
        "h2_canvas_pct": 0.08,
        "body_canvas_pct": 0.03
    }},
    "color_usage_rules": {{
        "dominant_pct": 60,
        "secondary_pct": 30,
        "accent_pct": 10,
        "max_colors": 3,
        "rule": "60-30-10 color authority"
    }},
    "hierarchy_enforcement": ["element order by visual priority"],
    "forbidden_violations": ["specific things to avoid"]
}}
"""

        try:
            from google.genai import types

            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.82,
                    max_output_tokens=2500,
                ),
            )
            text = response.text.strip()

            # Extract JSON
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()

            decree = json.loads(text)
            decree["decree_confidence"] = 0.75
            decree["decree_source"] = "llm_generated"

            logger.info(f"[DesignDirector] LLM decree issued: {decree.get('composition_law')}")
            return decree

        except Exception as e:
            logger.error(f"[DesignDirector] LLM decree failed: {e}")
            return self._fallback_decree()

    def _fallback_decree(self) -> Dict:
        """Emergency fallback decree."""
        return {
            "composition_law": "hero_dominant",
            "grid_system": {
                "type": "12-column",
                "columns": 12,
                "gutter_px": 16,
                "margins_pct": 5.0,
                "safe_zones": {"top": 0.07, "bottom": 0.10, "sides": 0.05}
            },
            "type_scale": {
                "scale_name": "major_third",
                "ratio": 1.250,
                "h1_canvas_pct": 0.12,
                "h2_canvas_pct": 0.08,
                "body_canvas_pct": 0.03
            },
            "color_usage_rules": {
                "dominant_pct": 60,
                "secondary_pct": 30,
                "accent_pct": 10,
                "max_colors": 3,
                "rule": "60-30-10 color authority"
            },
            "hierarchy_enforcement": ["hero_image", "headline", "cta", "brand"],
            "forbidden_violations": ["centered_everything", "rainbow_colors", "text_over_busy"],
            "decree_confidence": 0.5,
            "decree_source": "emergency_fallback"
        }


# ══════════════════════════════════════════════════════════════════════════════
# Public API
# ══════════════════════════════════════════════════════════════════════════════

async def design_director_agent(
    creative_bible: Dict,
    brand_palette: Dict,
    platform: str,
    aspect_ratio: float,
    triage: Dict,
    industry: str = "general",
    gemini_client=None
) -> Dict:
    """
    Public API: Issue Visual System Decree.

    This decree is NON-NEGOTIABLE for all downstream agents.
    """
    director = DesignDirector(gemini_client=gemini_client)
    return await director.issue_decree(
        creative_bible=creative_bible,
        brand_palette=brand_palette,
        platform=platform,
        aspect_ratio=aspect_ratio,
        triage=triage,
        industry=industry
    )
