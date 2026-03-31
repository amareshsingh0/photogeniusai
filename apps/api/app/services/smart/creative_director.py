"""
Creative Director — Heuristic concept extraction layer.

Converts a raw user prompt into a structured creative concept:
- Theme detection (summer, luxury, tech, food, etc.)
- Object suggestions (decorative elements that frame the scene)
- Color palette selection (mood-appropriate colors)
- Atmosphere keywords (energy, mood, texture)

This is what Midjourney/DALL-E do internally — they don't send raw prompts
to the model. They first extract a "creative brief" and inject controlled
design vocabulary.

Architecture:
    User Prompt → Creative Director → Creative Brief → Layout Planner → Generation

Heuristic-only. Set USE_LLM_DIRECTOR=True for future LLM-powered upgrade.
"""

from __future__ import annotations

import logging
from typing import List, TypedDict

from .config import THEMES, DEFAULT_THEME, ThemeDef

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
# Feature Flag
# ══════════════════════════════════════════════════════════════════════════════
USE_LLM_DIRECTOR = False  # Flip when Llama/Qwen is ready


class CreativeBrief(TypedDict):
    theme: str                     # "summer_beach", "luxury", "tech", etc.
    theme_label: str               # Human-readable: "Summer Beach"
    objects: List[str]             # Decorative/framing objects for the scene
    color_palette: List[str]       # Color keywords: ["orange", "turquoise"]
    color_prompt: str              # "warm orange and turquoise color palette"
    atmosphere: str                # "high-energy, vibrant, tropical warmth"
    decorative_prompt: str         # Objects as prompt fragment
    concept_prompt: str            # Full concept expansion (theme+objects+colors+atmosphere)


class CreativeDirector:
    """
    Extracts a structured creative concept from user prompt.

    Heuristic-based theme/object/color detection. Outputs a CreativeBrief
    that the Layout Planner and prompt assembler use to create design-grade prompts.
    """

    def direct(self, prompt: str) -> CreativeBrief:
        """
        Analyze prompt and produce a creative brief.

        Returns a CreativeBrief with theme, objects, colors, atmosphere,
        and pre-assembled prompt fragments ready for injection.
        """
        prompt_lower = prompt.lower()

        # ── Step 1: Detect theme ──────────────────────────────────────────
        theme_id, theme_def = self._detect_theme(prompt_lower)

        # ── Step 2: Select relevant objects (max 4, skip if already in prompt) ──
        objects = self._select_objects(prompt_lower, theme_def["objects"])

        # ── Step 3: Build color palette prompt ────────────────────────────
        colors = theme_def["colors"]
        color_prompt = self._build_color_prompt(colors)

        # ── Step 4: Build decorative objects prompt ───────────────────────
        decorative_prompt = self._build_decorative_prompt(objects)

        # ── Step 5: Assemble full concept prompt ──────────────────────────
        concept_parts = []
        if decorative_prompt:
            concept_parts.append(decorative_prompt)
        concept_parts.append(color_prompt)
        concept_parts.append(theme_def["atmosphere"])
        concept_prompt = ", ".join(concept_parts)

        brief = CreativeBrief(
            theme=theme_id,
            theme_label=theme_def["label"],
            objects=objects,
            color_palette=colors,
            color_prompt=color_prompt,
            atmosphere=theme_def["atmosphere"],
            decorative_prompt=decorative_prompt,
            concept_prompt=concept_prompt,
        )

        logger.info(
            "[CREATIVE_DIRECTOR] theme=%s objects=%s colors=%d atmosphere=%r",
            theme_id, objects[:3], len(colors), theme_def["atmosphere"][:50],
        )

        return brief

    def _detect_theme(self, prompt_lower: str) -> tuple[str, ThemeDef]:
        """Detect the best matching theme based on keyword density."""
        best_theme = "general"
        best_score = 0
        best_def: ThemeDef = DEFAULT_THEME

        for theme_id, theme_def in THEMES.items():
            score = sum(1 for kw in theme_def["keywords"] if kw in prompt_lower)
            if score > best_score:
                best_score = score
                best_theme = theme_id
                best_def = theme_def

        return best_theme, best_def

    def _select_objects(self, prompt_lower: str, all_objects: List[str]) -> List[str]:
        """Pick up to 4 decorative objects not already mentioned in prompt."""
        selected = []
        for obj in all_objects:
            # Skip if the object (or its core noun) is already in the prompt
            core = obj.split()[-1]  # e.g., "palm leaves" → "leaves"
            if core in prompt_lower:
                continue
            selected.append(obj)
            if len(selected) >= 4:
                break
        return selected

    def _build_color_prompt(self, colors: List[str]) -> str:
        """Build a color palette prompt fragment."""
        if not colors or colors[0] == "harmonious tones":
            return "harmonious balanced color palette"
        # Use top 3 colors
        top = colors[:3]
        return f"{' and '.join(top)} color palette"

    def _build_decorative_prompt(self, objects: List[str]) -> str:
        """Build decorative objects prompt fragment."""
        if not objects:
            return ""
        if len(objects) == 1:
            return f"with {objects[0]} as decorative accent"
        return f"with {', '.join(objects[:-1])} and {objects[-1]} as decorative elements"


# Singleton
creative_director = CreativeDirector()
