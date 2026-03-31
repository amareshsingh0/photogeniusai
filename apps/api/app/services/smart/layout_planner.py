"""
Layout Planner — Converts prompt into structured design plan.

This is the "secret" that Canva, Midjourney, and Leonardo use internally.
Instead of sending raw prompt to the model, we first create a structured
design specification that drives the entire generation pipeline.

Architecture:
    User Prompt → Intent Analyzer → Creative Graph → Layout Planner → Generation

The design plan includes:
- Layout zones (headline, subject, CTA, copy_space) from Creative Graph
- Style classification (poster, editorial, product, social, photo)
- Camera/lighting directives from scene_compiler
- Prompt augmentation with composition + lighting keywords
- Rule-of-thirds / golden-ratio math for subject placement
- Visual balance scoring
- Negative prompt assembly

Heuristic-only (no LLM). Boolean flag `USE_LLM_PLANNER` for future
LLM-powered upgrade (Llama/Qwen).
"""

from __future__ import annotations

import logging
import math
import re
from typing import Any, Dict, List, Optional, Tuple, TypedDict

from .config import (
    BG_PROMPT_HINTS,
    COPY_SPACE_HINTS,
    QUALITY_POLISH,
    STYLES,
    TEXT_FRAMING,
    get_style,
)
from .scene_compiler import scene_compiler, CAMERA_PRESETS, LIGHTING_PRESETS

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# Feature Flags — flip to True when LLM models are ready
# ══════════════════════════════════════════════════════════════════════════════
USE_LLM_PLANNER = False        # Use Llama/Qwen for layout planning
USE_LLM_PROMPT_BRAIN = False   # Use LLM for prompt enhancement
USE_LLM_STYLE_ENGINE = False   # Use LLM for style token generation


# ══════════════════════════════════════════════════════════════════════════════
# Layout Zone Types
# ══════════════════════════════════════════════════════════════════════════════

class LayoutZone(TypedDict):
    name: str           # "headline", "subject", "cta", "copy_space", "product"
    position: str       # "top_center", "center", "bottom_center", etc.
    size: str           # "large", "medium", "small"
    priority: int       # 1=highest attention, 3=lowest


class DesignPlan(TypedDict):
    style: str                    # "poster", "editorial", "product", "social", "photo", "banner"
    layout_zones: List[LayoutZone]
    subject_placement: str        # "center", "left_third", "right_third", "top_half"
    copy_space: str               # "top", "bottom", "center", "left", "right", "none"
    background_style: str         # "gradient", "solid", "photo", "minimal", "complex"
    camera_prompt: str            # Camera directive string
    lighting_prompt: str          # Lighting directive string
    composition_prompt: str       # Composition directive string
    enhanced_prompt: str          # Final prompt with all augmentations
    negative_prompt: str          # Assembled negative prompt
    has_text_overlay: bool        # Whether text overlay was detected
    design_intent: str            # "marketing", "cinematic", "artistic", "informational", "personal"
    # ── Creative OS additions ───────────────────────────────────────────────
    subject_x: float              # Rule-of-thirds X (0.0-1.0 fraction of width)
    subject_y: float              # Rule-of-thirds Y (0.0-1.0 fraction of height)
    visual_balance: float         # 0.0-1.0 predicted balance score
    safe_zone: Dict[str, float]   # {"left", "top", "right", "bottom"} inset fractions


# ══════════════════════════════════════════════════════════════════════════════
# Style Detection Rules
# ══════════════════════════════════════════════════════════════════════════════

_STYLE_RULES: list[tuple[list[str], str]] = [
    # Poster/advertising
    (["poster", "banner", "flyer", "billboard", "advertisement", "ad ", "promo",
      "marketing", "sale", "discount", "offer"], "poster"),
    # Editorial/magazine
    (["editorial", "magazine", "cover", "vogue", "fashion shoot", "lookbook"], "editorial"),
    # Product photography
    (["product", "packshot", "e-commerce", "catalog", "item", "merchandise"], "product"),
    # Social media
    (["instagram", "social media", "story", "thumbnail", "youtube", "tiktok",
      "reel", "profile", "avatar"], "social"),
    # Banner/web
    (["banner", "header", "hero image", "website", "web banner", "landing page"], "banner"),
    # Cinematic
    (["movie", "film", "cinematic", "trailer", "scene", "dramatic"], "cinematic"),
]

_INTENT_RULES: list[tuple[list[str], str]] = [
    (["sale", "discount", "offer", "buy", "shop", "promo", "deal", "price",
      "marketing", "advertising", "brand"], "marketing"),
    (["movie", "film", "cinematic", "scene", "dramatic", "epic", "trailer"], "cinematic"),
    (["art", "creative", "abstract", "painting", "illustration", "fantasy",
      "surreal", "concept"], "artistic"),
    (["infographic", "diagram", "data", "chart", "educational", "scientific",
      "tutorial", "how-to"], "informational"),
]

# ══════════════════════════════════════════════════════════════════════════════
# Camera/Lighting → Prompt String Converters
# ══════════════════════════════════════════════════════════════════════════════

def _camera_to_prompt(camera: Dict) -> str:
    """Convert camera preset to prompt-friendly string."""
    parts = []
    focal = camera.get("focal_mm", 50)
    aperture = camera.get("aperture", "f/4")
    angle = camera.get("angle", "eye_level")

    if focal <= 24:
        parts.append("wide-angle shot")
    elif focal >= 85:
        parts.append(f"shot on {focal}mm lens")
    else:
        parts.append(f"{focal}mm focal length")

    parts.append(f"{aperture} aperture")

    angle_map = {
        "low": "low angle shot",
        "high_angle": "high angle shot",
        "top_down": "overhead shot, bird's eye view",
        "dutch": "dutch angle, tilted frame",
        "eye_level": "",
        "slightly_above": "slightly elevated angle",
    }
    angle_str = angle_map.get(angle, "")
    if angle_str:
        parts.append(angle_str)

    return ", ".join(p for p in parts if p)


def _lighting_to_prompt(lighting: Dict) -> str:
    """Convert lighting preset to prompt-friendly string."""
    parts = []
    style = lighting.get("style", "balanced")
    mood = lighting.get("mood", "neutral")
    color_temp = lighting.get("color_temp", "neutral")

    style_map = {
        "studio": "professional studio lighting",
        "rembrandt": "Rembrandt lighting, dramatic shadows",
        "golden_hour": "golden hour sunlight, warm tones",
        "overcast": "soft overcast lighting, even illumination",
        "midday_sun": "harsh midday sunlight, strong shadows",
        "noir": "film noir lighting, high contrast shadows",
        "cinematic": "cinematic lighting, warm tones",
        "cyberpunk": "neon lighting, colorful reflections",
        "backlit": "backlit, rim lighting, silhouette edges",
        "product": "clean product lighting, even illumination",
        "chiaroscuro": "chiaroscuro lighting, dramatic contrast",
        "fantasy": "ethereal magical lighting, soft glow",
        "underwater": "underwater caustic light patterns",
        "space": "starlight ambient illumination",
        "vintage": "warm vintage lighting, nostalgic tones",
        "food": "appetizing food photography lighting, soft side light",
        "balanced": "natural balanced lighting",
    }
    light_str = style_map.get(style, f"{style} lighting")
    parts.append(light_str)

    if color_temp == "warm":
        parts.append("warm color temperature")
    elif color_temp == "cool":
        parts.append("cool color temperature")

    return ", ".join(parts)


def _composition_to_prompt(composition: Dict) -> str:
    """Convert composition preset to prompt-friendly string."""
    rule = composition.get("rule", "rule_of_thirds")

    rule_map = {
        "rule_of_thirds": "rule of thirds composition",
        "centered": "centered symmetric composition",
        "golden_ratio": "golden ratio composition",
        "leading_lines": "leading lines composition, depth",
        "symmetry": "perfect symmetry, mirror composition",
        "diagonal": "dynamic diagonal composition",
        "frame_within_frame": "framing composition, natural frame",
        "negative_space": "minimalist composition, ample negative space",
        "fill": "fill the frame, tight crop",
        "panoramic": "panoramic wide composition",
    }
    return rule_map.get(rule, f"{rule} composition")


# ══════════════════════════════════════════════════════════════════════════════
# Layout Planner Class
# ══════════════════════════════════════════════════════════════════════════════

class LayoutPlanner:
    """
    Converts user prompt into a structured design plan.

    This is the intelligence layer between user input and image generation.
    Instead of raw prompt → model, we do:
        prompt → design plan → augmented prompt → model

    Heuristic-based. Set USE_LLM_PLANNER=True for LLM-powered planning.
    """

    def plan(
        self,
        prompt: str,
        quality: str = "STANDARD",
        width: int = 1024,
        height: int = 1024,
        has_text_overlay: bool = False,
        text_positions: Optional[List[str]] = None,
    ) -> DesignPlan:
        """
        Create a structured design plan from user prompt.

        Args:
            prompt: Raw user prompt (after text extraction if applicable)
            quality: Quality tier
            width/height: Target dimensions
            has_text_overlay: Whether text overlay system detected text
            text_positions: Positions of detected text overlays

        Returns:
            Complete DesignPlan driving the generation pipeline
        """
        prompt_lower = prompt.lower()

        # ── Step 1: Compile scene (camera, lighting, composition) ─────────
        scene = scene_compiler.compile(prompt, quality, width, height)

        # ── Step 2: Detect design style ───────────────────────────────────
        style = self._detect_style(prompt_lower)

        # ── Step 3: Detect design intent ──────────────────────────────────
        intent = self._detect_intent(prompt_lower)

        # ── Step 4: Plan layout zones ─────────────────────────────────────
        zones = self._plan_zones(style, intent, has_text_overlay, text_positions)

        # ── Step 5: Determine copy space and subject placement ────────────
        copy_space = self._plan_copy_space(style, has_text_overlay, text_positions)
        subject_placement = self._plan_subject_placement(style, copy_space, scene)

        # ── Step 6: Determine background style ────────────────────────────
        bg_style = self._plan_background(style, scene, has_text_overlay)

        # ── Step 7: Convert scene data to prompt strings ──────────────────
        camera_prompt = _camera_to_prompt(scene["camera"])
        lighting_prompt = _lighting_to_prompt(scene["lighting"])
        composition_prompt = _composition_to_prompt(scene["composition"])

        # ── Step 8: Assemble enhanced prompt ──────────────────────────────
        enhanced = self._assemble_prompt(
            original=prompt,
            scene=scene,
            camera=camera_prompt,
            lighting=lighting_prompt,
            composition=composition_prompt,
            bg_style=bg_style,
            copy_space=copy_space,
            has_text=has_text_overlay,
            style=style,
        )

        # ── Step 9: Assemble negative prompt ──────────────────────────────
        negative = self._assemble_negative(scene, style, has_text_overlay)

        # ── Step 10: Rule-of-thirds subject coordinates ────────────────
        subj_x, subj_y = self._calc_subject_position(
            subject_placement, copy_space, width, height
        )

        # ── Step 11: Predict visual balance ──────────────────────────────
        vis_balance = self._predict_balance(zones, copy_space)

        # ── Step 12: Safe zone (platform inset) ─────────────────────────
        safe_zone = {"left": 0.05, "top": 0.05, "right": 0.05, "bottom": 0.05}
        if has_text_overlay:
            # Leave more room when text is present
            safe_zone = {"left": 0.08, "top": 0.08, "right": 0.08, "bottom": 0.08}

        plan = DesignPlan(
            style=style,
            layout_zones=zones,
            subject_placement=subject_placement,
            copy_space=copy_space,
            background_style=bg_style,
            camera_prompt=camera_prompt,
            lighting_prompt=lighting_prompt,
            composition_prompt=composition_prompt,
            enhanced_prompt=enhanced,
            negative_prompt=negative,
            has_text_overlay=has_text_overlay,
            design_intent=intent,
            subject_x=subj_x,
            subject_y=subj_y,
            visual_balance=vis_balance,
            safe_zone=safe_zone,
        )

        logger.info(
            "[LAYOUT] style=%s intent=%s copy=%s subject=%s(%.2f,%.2f) bal=%.2f bg=%s text=%s",
            style, intent, copy_space, subject_placement, subj_x, subj_y,
            vis_balance, bg_style, has_text_overlay,
        )

        return plan

    # ── Detection helpers ─────────────────────────────────────────────────

    def _detect_style(self, prompt_lower: str) -> str:
        for keywords, style in _STYLE_RULES:
            if any(kw in prompt_lower for kw in keywords):
                return style
        return "photo"  # default: standard photography

    def _detect_intent(self, prompt_lower: str) -> str:
        for keywords, intent in _INTENT_RULES:
            if any(kw in prompt_lower for kw in keywords):
                return intent
        return "personal"

    # ── Layout zone planning ──────────────────────────────────────────────

    def _plan_zones(
        self,
        style: str,
        intent: str,
        has_text: bool,
        text_positions: Optional[List[str]],
    ) -> List[LayoutZone]:
        """Plan layout zones based on style and intent."""

        # Style-specific zone templates (like Canva's internal representation)
        zone_templates = {
            "poster": [
                LayoutZone(name="headline", position="top_center", size="large", priority=1),
                LayoutZone(name="subject", position="center", size="large", priority=2),
                LayoutZone(name="cta", position="bottom_center", size="medium", priority=3),
            ],
            "editorial": [
                LayoutZone(name="subject", position="center", size="large", priority=1),
                LayoutZone(name="headline", position="bottom_left", size="medium", priority=2),
                LayoutZone(name="copy_space", position="right_third", size="small", priority=3),
            ],
            "product": [
                LayoutZone(name="product", position="center", size="large", priority=1),
                LayoutZone(name="copy_space", position="bottom_center", size="small", priority=2),
            ],
            "social": [
                LayoutZone(name="subject", position="center", size="large", priority=1),
                LayoutZone(name="headline", position="top_center", size="medium", priority=2),
            ],
            "banner": [
                LayoutZone(name="headline", position="left_center", size="large", priority=1),
                LayoutZone(name="subject", position="right_center", size="medium", priority=2),
            ],
            "cinematic": [
                LayoutZone(name="subject", position="center", size="large", priority=1),
                LayoutZone(name="headline", position="bottom_center", size="medium", priority=2),
            ],
            "photo": [
                LayoutZone(name="subject", position="center", size="large", priority=1),
            ],
        }

        zones = zone_templates.get(style, zone_templates["photo"])

        # If text overlay is active but no headline zone, add one
        if has_text and not any(z["name"] == "headline" for z in zones):
            pos = "bottom_center"
            if text_positions:
                pos_map = {"top": "top_center", "center": "center", "bottom": "bottom_center"}
                pos = pos_map.get(text_positions[0], "bottom_center")
            zones.append(LayoutZone(name="headline", position=pos, size="medium", priority=2))

        return zones

    def _plan_copy_space(
        self,
        style: str,
        has_text: bool,
        text_positions: Optional[List[str]],
    ) -> str:
        """Where should empty space be reserved for text/branding."""
        if has_text and text_positions:
            return text_positions[0]  # "top", "center", "bottom"

        return get_style(style).get("copy_space_default", "none")

    def _plan_subject_placement(
        self, style: str, copy_space: str, scene: Dict
    ) -> str:
        """Where should the main subject be placed."""
        # If copy space is at top → push subject to bottom half and vice versa
        if copy_space == "top":
            return "bottom_half"
        if copy_space == "bottom":
            return "top_half"
        if copy_space == "left":
            return "right_third"
        if copy_space == "right":
            return "left_third"

        # Default: use scene composition
        comp = scene.get("composition", {}).get("rule", "rule_of_thirds")
        if comp == "centered":
            return "center"
        return "center"

    def _plan_background(self, style: str, scene: Dict, has_text: bool) -> str:
        """Determine background complexity."""
        bg_type = scene.get("background", {}).get("type", "studio_white")

        if has_text:
            # Text needs clean backgrounds
            if "studio" in bg_type or "gradient" in bg_type:
                return "gradient"
            return "minimal"

        return get_style(style).get("bg_default", "photo")

    # ── Rule-of-thirds math ──────────────────────────────────────────────

    # The 4 power points on a rule-of-thirds grid (fraction of image)
    _ROT_POINTS = [
        (1/3, 1/3),   # top-left power point
        (2/3, 1/3),   # top-right power point
        (1/3, 2/3),   # bottom-left power point
        (2/3, 2/3),   # bottom-right power point
    ]

    # Golden ratio power points (phi ≈ 0.618)
    _PHI = 1.0 / 1.618
    _GOLDEN_POINTS = [
        (_PHI, _PHI),             # top-left
        (1 - _PHI, _PHI),         # top-right
        (_PHI, 1 - _PHI),         # bottom-left
        (1 - _PHI, 1 - _PHI),     # bottom-right
    ]

    def _calc_subject_position(
        self, placement: str, copy_space: str, width: int, height: int
    ) -> tuple[float, float]:
        """
        Calculate optimal subject position using rule-of-thirds math.

        Returns (x, y) as fractions of image dimensions (0.0-1.0).
        The subject's visual center should be placed at this point
        for maximum aesthetic impact.
        """
        # Map placement to preferred power point quadrant
        placement_map = {
            "center":       (0.50, 0.50),
            "left_third":   (1/3, 0.50),
            "right_third":  (2/3, 0.50),
            "top_half":     (0.50, 1/3),
            "bottom_half":  (0.50, 2/3),
        }

        if placement in placement_map:
            base_x, base_y = placement_map[placement]
        else:
            base_x, base_y = 0.50, 0.50

        # Adjust for copy space: push subject away from text zone
        nudge = 0.08  # shift amount
        if copy_space == "top":
            base_y = max(base_y, 2/3 - nudge)  # push toward bottom third
        elif copy_space == "bottom":
            base_y = min(base_y, 1/3 + nudge)  # push toward top third
        elif copy_space == "left":
            base_x = max(base_x, 2/3 - nudge)
        elif copy_space == "right":
            base_x = min(base_x, 1/3 + nudge)

        # Snap to nearest rule-of-thirds power point (if close)
        snap_threshold = 0.12
        best_dist = float("inf")
        best_point = (base_x, base_y)
        for px, py in self._ROT_POINTS:
            dist = math.sqrt((base_x - px)**2 + (base_y - py)**2)
            if dist < best_dist and dist < snap_threshold:
                best_dist = dist
                best_point = (px, py)

        return (round(best_point[0], 3), round(best_point[1], 3))

    def _predict_balance(self, zones: List[LayoutZone], copy_space: str) -> float:
        """
        Predict visual balance from layout zones.

        Uses quadrant weight distribution (same algorithm as creative_graph).
        Perfect balance = equal weight in all 4 quadrants.
        """
        # Priority → visual weight mapping
        weight_map = {1: 0.4, 2: 0.3, 3: 0.2, 4: 0.1, 5: 0.05}

        # Position → center coordinate mapping
        pos_map = {
            "top_center":    (0.50, 0.15),
            "center":        (0.50, 0.50),
            "bottom_center": (0.50, 0.85),
            "bottom_left":   (0.25, 0.85),
            "right_third":   (0.75, 0.50),
            "left_third":    (0.25, 0.50),
            "left_center":   (0.25, 0.50),
            "right_center":  (0.75, 0.50),
            "top_left":      (0.25, 0.15),
            "top_right":     (0.75, 0.15),
        }

        qw = {"tl": 0.0, "tr": 0.0, "bl": 0.0, "br": 0.0}
        for zone in zones:
            cx, cy = pos_map.get(zone["position"], (0.5, 0.5))
            w = weight_map.get(zone["priority"], 0.1)
            qw["tl"] += w * (1.0 - cx) * (1.0 - cy)
            qw["tr"] += w * cx * (1.0 - cy)
            qw["bl"] += w * (1.0 - cx) * cy
            qw["br"] += w * cx * cy

        total = sum(qw.values())
        if total == 0:
            return 1.0
        values = [v / total for v in qw.values()]
        deviation = sum(abs(v - 0.25) for v in values) / 4
        return round(max(0.0, 1.0 - deviation / 0.375), 3)

    # ── Prompt assembly ───────────────────────────────────────────────────

    def _assemble_prompt(
        self,
        original: str,
        scene: Dict,
        camera: str,
        lighting: str,
        composition: str,
        bg_style: str,
        copy_space: str,
        has_text: bool,
        style: str = "photo",
    ) -> str:
        """Assemble the final enhanced prompt with all directives."""
        parts = [original]

        # Add camera directive
        if camera:
            parts.append(camera)

        # Add lighting
        if lighting:
            parts.append(lighting)

        # Add composition
        if composition:
            parts.append(composition)

        # Add quality boost from scene template
        quality_boost = scene.get("prompt_strategy", {}).get("quality_boost", "")
        if quality_boost:
            parts.append(quality_boost)

        # ── Design element keywords from central config ────────────────────
        style_cfg = get_style(style)
        design_el = style_cfg.get("design_elements", "")
        if design_el:
            parts.append(design_el)

        # Background style hint from config
        bg_hint = BG_PROMPT_HINTS.get(bg_style, "")
        if bg_hint:
            parts.append(bg_hint)

        # Copy space directive (for text overlay images)
        if has_text and copy_space != "none":
            hint = COPY_SPACE_HINTS.get(copy_space, "")
            if hint:
                parts.append(hint)
            parts.append(TEXT_FRAMING)

        # Aspect ratio hint
        aspect_hint = scene.get("aspect", {}).get("hint", "")
        if aspect_hint:
            parts.append(aspect_hint)

        # Universal quality polish
        parts.append(QUALITY_POLISH)

        return ", ".join(p for p in parts if p)

    def _assemble_negative(
        self, scene: Dict, style: str, has_text: bool
    ) -> str:
        """Assemble the complete negative prompt."""
        parts = []

        # Base negative from scene template
        template_neg = scene.get("prompt_strategy", {}).get("negative_prompt", "")
        if template_neg:
            parts.append(template_neg)

        # Universal quality negatives
        parts.append("low quality, blurry, distorted, deformed, ugly, bad anatomy")

        # Text artifact negatives (when text overlay is active)
        if has_text:
            parts.append(
                "text, typography, letters, words, watermark, signature, "
                "writing, font, caption, busy background, cluttered, "
                "distracting elements, messy, complex patterns"
            )

        # Style-specific negatives from config
        style_cfg = get_style(style)
        style_neg = style_cfg.get("negative_prompt", "")
        if style_neg:
            parts.append(style_neg)

        return ", ".join(parts)


# Singleton
layout_planner = LayoutPlanner()
