"""
Image Modification Engine
=========================
When a user says "make it brighter" or "change the background to forest"
we MODIFY the existing image, not regenerate from scratch.

Only when the user explicitly asks for "a new image" or "something completely
different" do we regenerate.

Architecture:
    1. Intent Parser         → detects MODIFY vs NEW
    2. Modification Planner  → extracts what regions / attributes change
    3. Inpaint Executor      → applies the change via img2img / inpainting (optional)
    4. Attribute Editor      → handles global adjustments (brightness, color, etc.)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

try:
    from PIL import Image, ImageEnhance, ImageFilter  # type: ignore[reportMissingImports]

    HAS_PIL = True
except Exception:
    Image = None  # type: ignore[assignment]
    ImageEnhance = None  # type: ignore[assignment]
    ImageFilter = None  # type: ignore[assignment]
    HAS_PIL = False


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


class ModificationType(str, Enum):
    MODIFY_GLOBAL = "modify_global"  # brightness, contrast, color shift
    MODIFY_REGION = "modify_region"  # inpaint a specific area
    MODIFY_STYLE = "modify_style"  # change artistic style (img2img)
    MODIFY_ATTRIBUTE = "modify_attribute"  # change an attribute of a subject
    NEW_IMAGE = "new_image"  # full regeneration requested


@dataclass
class ModificationPlan:
    """What to do to the image."""

    mod_type: ModificationType
    description: str  # human-readable summary
    # brightness, contrast, saturation, sharpness  (each -1.0 .. +1.0)
    global_adjustments: Dict[str, float] = field(default_factory=dict)
    style_target: Optional[str] = None  # target style for img2img
    inpaint_instruction: Optional[str] = None  # text prompt for inpainted region
    inpaint_mask_hint: Optional[str] = (
        None  # "background", "sky", "person", "left half"
    )
    img2img_strength: float = 0.5  # 0.0 = no change, 1.0 = full regen
    preserve_subject: bool = True  # keep main subject intact
    new_prompt: Optional[str] = None  # only set when mod_type == NEW_IMAGE


# ---------------------------------------------------------------------------
# Intent keyword maps
# ---------------------------------------------------------------------------

# Phrases that mean "keep this image, just tweak it"
MODIFY_SIGNALS = [
    "make it",
    "change the",
    "change its",
    "adjust",
    "turn it",
    "convert to",
    "add a",
    "remove the",
    "remove all",
    "darken",
    "lighten",
    "brighten",
    "saturate",
    "desaturate",
    "blur",
    "sharpen",
    "zoom in",
    "zoom out",
    "crop",
    "flip",
    "mirror",
    "rotate",
    "tint",
    "colorize",
    "add more",
    "more vibrant",
    "more colorful",
    "edit",
    "modify",
    "update",
    "tweak",
    "alter",
    "shift",
    "swap",
    "replace",
    "switch",
    "transform into",
    "turn into",
    "in a different style",
    "but as a",
    "same but",
    "keep the same",
    "keep it but",
    "keep the person but",
    "enhance",
    "improve",
    "fix",
]

# Phrases that mean "generate a brand new image"
NEW_SIGNALS = [
    "new image",
    "new picture",
    "new photo",
    "different image",
    "completely different",
    "something else",
    "start over",
    "generate another",
    "create a new",
    "make a new",
    "totally new",
    "brand new",
    "fresh image",
    "another one",
    "from scratch",
    "generate fresh",
]


# ---------------------------------------------------------------------------
# Global adjustment keyword maps
# ---------------------------------------------------------------------------


BRIGHTNESS_KEYWORDS: Dict[str, float] = {
    # Increase brightness
    "brighter": 0.3,
    "more bright": 0.3,
    "lighten": 0.3,
    "lighter": 0.3,
    "increase brightness": 0.4,
    "make it light": 0.3,
    "overexpose": 0.5,
    "sunny": 0.2,
    "more light": 0.25,
    # Decrease brightness
    "darker": -0.3,
    "more dark": -0.3,
    "darken": -0.35,
    "dim": -0.3,
    "decrease brightness": -0.4,
    "make it dark": -0.35,
    "underexpose": -0.5,
    "moody": -0.2,
    "less light": -0.25,
}

CONTRAST_KEYWORDS: Dict[str, float] = {
    "more contrast": 0.3,
    "increase contrast": 0.35,
    "high contrast": 0.4,
    "punchy": 0.3,
    "vivid": 0.2,
    "bold": 0.2,
    "less contrast": -0.3,
    "decrease contrast": -0.35,
    "low contrast": -0.3,
    "flat": -0.25,
    "washed out": -0.3,
}

SATURATION_KEYWORDS: Dict[str, float] = {
    "more saturated": 0.3,
    "saturate": 0.3,
    "vibrant": 0.35,
    "vivid colors": 0.3,
    "colorful": 0.25,
    "punchy colors": 0.35,
    "increase saturation": 0.4,
    "pop the colors": 0.3,
    # Decrease
    "desaturate": -0.35,
    "less saturated": -0.3,
    "muted": -0.3,
    "pastel": -0.25,
    "washed": -0.3,
    "decrease saturation": -0.4,
    "dull": -0.3,
    "grey": -0.4,
    "gray": -0.4,
}

SHARPNESS_KEYWORDS: Dict[str, float] = {
    "sharper": 0.3,
    "sharpen": 0.35,
    "more sharp": 0.3,
    "crisp": 0.25,
    "increase sharpness": 0.4,
    "ultra sharp": 0.5,
    # Decrease
    "blur": -0.35,
    "blurry": -0.3,
    "soft": -0.25,
    "soften": -0.3,
    "decrease sharpness": -0.4,
    "dreamy blur": -0.4,
    "bokeh": -0.3,
    "shallow dof": -0.25,
}


# Style-swap keywords  (triggers img2img style transfer)
STYLE_SWAP_KEYWORDS: Dict[str, str] = {
    "watercolor": "watercolor painting style",
    "oil painting": "oil painting style on canvas",
    "sketch": "pencil sketch drawing style",
    "cartoon": "cartoon cel-shaded style",
    "anime": "anime illustration style",
    "pixel art": "pixel art retro game style",
    "vintage": "vintage film photography style with grain",
    "noir": "black and white noir style high contrast",
    "impressionist": "impressionist painting style with brushstrokes",
    "cubist": "cubist geometric abstract style",
    "pop art": "pop art bold colors Andy Warhol style",
    "gothic": "dark gothic moody style",
    "minimalist": "minimalist clean flat design style",
    "surreal": "surrealist dreamlike impossible style",
    "cyberpunk": "cyberpunk neon futuristic style",
    "art deco": "art deco geometric golden style",
}

# Region-hint keywords (used to locate what part of the image to modify)
REGION_KEYWORDS: Dict[str, List[str]] = {
    "background": ["background", "bg", "behind", "backdrop"],
    "sky": ["sky", "above", "clouds", "upper part"],
    "foreground": ["foreground", "front", "in front"],
    "left": ["left side", "left half", "left part"],
    "right": ["right side", "right half", "right part"],
    "top": ["top", "upper", "top half"],
    "bottom": ["bottom", "lower", "bottom half"],
    "center": ["center", "middle", "central"],
    "person": [
        "person",
        "people",
        "man",
        "woman",
        "character",
        "subject",
        "figure",
        "him",
        "her",
        "they",
    ],
    "face": ["face", "facial", "expression"],
    "hair": ["hair"],
    "clothes": ["clothes", "clothing", "outfit", "shirt", "dress", "jacket"],
    "animal": ["animal", "dog", "cat", "bird", "creature"],
}


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


# ---------------------------------------------------------------------------
# Intent parser
# ---------------------------------------------------------------------------


class IntentParser:
    """Decide: is the user asking to MODIFY the existing image or generate NEW?"""

    @staticmethod
    def parse(instruction: str) -> ModificationType:
        instr_lower = (instruction or "").lower().strip()

        # NEW signals take priority only if they appear clearly
        for sig in NEW_SIGNALS:
            if sig in instr_lower:
                return ModificationType.NEW_IMAGE

        # Direct style / global / region cues should count as MODIFY even if the user
        # didn't include a generic "make it / change it" prefix (e.g. "increase contrast").
        for style_kw in STYLE_SWAP_KEYWORDS:
            if style_kw in instr_lower:
                return ModificationType.MODIFY_STYLE

        all_global = {
            **BRIGHTNESS_KEYWORDS,
            **CONTRAST_KEYWORDS,
            **SATURATION_KEYWORDS,
            **SHARPNESS_KEYWORDS,
        }
        for kw in all_global:
            if kw in instr_lower:
                return ModificationType.MODIFY_GLOBAL

        for region, triggers in REGION_KEYWORDS.items():
            for t in triggers:
                if t in instr_lower:
                    return ModificationType.MODIFY_REGION

        # MODIFY signals
        for sig in MODIFY_SIGNALS:
            if sig in instr_lower:
                # Distinguish sub-types
                # (Style keywords handled above, but keep for completeness)
                for style_kw in STYLE_SWAP_KEYWORDS:
                    if style_kw in instr_lower:
                        return ModificationType.MODIFY_STYLE

                # Check for global adjustments
                # (Global keywords handled above, but keep for completeness)
                for kw in all_global:
                    if kw in instr_lower:
                        return ModificationType.MODIFY_GLOBAL

                # Check for region-based edit
                # (Region keywords handled above, but keep for completeness)
                for region, triggers in REGION_KEYWORDS.items():
                    for t in triggers:
                        if t in instr_lower:
                            return ModificationType.MODIFY_REGION

                # Fallback: attribute modification
                return ModificationType.MODIFY_ATTRIBUTE

        # If nothing matched clearly, treat as new
        return ModificationType.NEW_IMAGE


# ---------------------------------------------------------------------------
# Modification planner
# ---------------------------------------------------------------------------


class ModificationPlanner:
    """From user instruction + detected intent type, build a ModificationPlan."""

    def plan(self, instruction: str, current_prompt: str) -> ModificationPlan:
        instr_lower = (instruction or "").lower().strip()
        mod_type = IntentParser.parse(instruction)

        if mod_type == ModificationType.NEW_IMAGE:
            return ModificationPlan(
                mod_type=ModificationType.NEW_IMAGE,
                description="Generate a completely new image",
                new_prompt=instruction,
            )

        if mod_type == ModificationType.MODIFY_GLOBAL:
            return self._plan_global(instr_lower)

        if mod_type == ModificationType.MODIFY_STYLE:
            return self._plan_style(instr_lower, current_prompt)

        if mod_type == ModificationType.MODIFY_REGION:
            return self._plan_region(instr_lower, current_prompt)

        # MODIFY_ATTRIBUTE — combine original prompt context with the change
        return self._plan_attribute(instr_lower, current_prompt)

    def _plan_global(self, instr: str) -> ModificationPlan:
        adjustments: Dict[str, float] = {}

        for kw, val in BRIGHTNESS_KEYWORDS.items():
            if kw in instr:
                adjustments["brightness"] = val
                break
        for kw, val in CONTRAST_KEYWORDS.items():
            if kw in instr:
                adjustments["contrast"] = val
                break
        for kw, val in SATURATION_KEYWORDS.items():
            if kw in instr:
                adjustments["saturation"] = val
                break
        for kw, val in SHARPNESS_KEYWORDS.items():
            if kw in instr:
                adjustments["sharpness"] = val
                break

        desc = "Global adjustment: " + ", ".join(
            f"{k} {('+' if v > 0 else '')}{v:.1f}" for k, v in adjustments.items()
        )

        return ModificationPlan(
            mod_type=ModificationType.MODIFY_GLOBAL,
            description=desc,
            global_adjustments=adjustments,
        )

    def _plan_style(self, instr: str, current_prompt: str) -> ModificationPlan:
        target_style = None
        for kw, style_prompt in STYLE_SWAP_KEYWORDS.items():
            if kw in instr:
                target_style = style_prompt
                break

        # Strength: "subtle" → 0.35, "completely" / "full" → 0.75, default 0.55
        strength = 0.55
        if any(w in instr for w in ["subtle", "slight", "little bit", "slightly"]):
            strength = 0.35
        elif any(w in instr for w in ["completely", "fully", "total", "extreme"]):
            strength = 0.75

        return ModificationPlan(
            mod_type=ModificationType.MODIFY_STYLE,
            description=f"Style transfer → {target_style}",
            style_target=target_style,
            img2img_strength=strength,
            preserve_subject=True,
        )

    def _plan_region(self, instr: str, current_prompt: str) -> ModificationPlan:
        # Detect which region
        detected_region = "background"  # default
        for region, triggers in REGION_KEYWORDS.items():
            for t in triggers:
                if t in instr:
                    detected_region = region
                    break

        # The inpaint prompt = original prompt with the modification baked in
        inpaint_prompt = f"{current_prompt}, modified: {instr}".strip(", ")

        return ModificationPlan(
            mod_type=ModificationType.MODIFY_REGION,
            description=f"Region edit: {detected_region} → {instr[:80]}",
            inpaint_instruction=inpaint_prompt,
            inpaint_mask_hint=detected_region,
            img2img_strength=0.6,
            preserve_subject=(detected_region != "person"),
        )

    def _plan_attribute(self, instr: str, current_prompt: str) -> ModificationPlan:
        combined = f"{current_prompt}, {instr}".strip(", ")
        return ModificationPlan(
            mod_type=ModificationType.MODIFY_ATTRIBUTE,
            description=f"Attribute change: {instr[:80]}",
            inpaint_instruction=combined,
            img2img_strength=0.45,
            preserve_subject=True,
        )


# ---------------------------------------------------------------------------
# Inpaint / attribute executor  (applies plan to actual PIL image)
# ---------------------------------------------------------------------------


class ImageModificationExecutor:
    """
    Applies a ModificationPlan to a PIL Image.

    For MODIFY_GLOBAL: pure PIL transforms (instant, no model needed).
    For MODIFY_STYLE / MODIFY_REGION / MODIFY_ATTRIBUTE:
        Tries an optional diffusion pipeline hook (generate_img2img).
        If unavailable or fails, applies a best-effort PIL fallback.
    """

    def execute(
        self,
        image: Any,
        plan: ModificationPlan,
        diffusion_pipeline: Any = None,  # optional: pass GuidedDiffusionPipeline or similar
    ) -> Tuple[Any, ModificationPlan]:
        """
        Returns (modified_image, plan_used).

        If plan is NEW_IMAGE, returns the original image untouched;
        caller must trigger full regeneration separately.
        """
        if plan.mod_type == ModificationType.NEW_IMAGE:
            return image, plan

        if plan.mod_type == ModificationType.MODIFY_GLOBAL:
            return self._apply_global(image, plan), plan

        # For style / region / attribute: try pipeline hook, else fallback
        if diffusion_pipeline is not None:
            try:
                return self._apply_with_pipeline(image, plan, diffusion_pipeline), plan
            except Exception:
                # fall back to PIL transforms
                pass

        return self._apply_fallback(image, plan), plan

    def _apply_global(self, image: Any, plan: ModificationPlan) -> Any:
        """Apply brightness / contrast / saturation / sharpness via PIL."""
        if not HAS_PIL or ImageEnhance is None or not hasattr(image, "copy"):
            return image
        img = image.copy()
        adj = plan.global_adjustments or {}

        if "brightness" in adj:
            factor = _clamp(1.0 + float(adj["brightness"]), 0.1, 2.5)
            img = ImageEnhance.Brightness(img).enhance(factor)

        if "contrast" in adj:
            factor = _clamp(1.0 + float(adj["contrast"]), 0.1, 2.5)
            img = ImageEnhance.Contrast(img).enhance(factor)

        if "saturation" in adj:
            factor = _clamp(1.0 + float(adj["saturation"]), 0.0, 3.0)
            img = ImageEnhance.Color(img).enhance(factor)

        if "sharpness" in adj:
            factor = _clamp(1.0 + float(adj["sharpness"]), 0.0, 3.0)
            img = ImageEnhance.Sharpness(img).enhance(factor)

        return img

    def _apply_with_pipeline(
        self, image: Any, plan: ModificationPlan, pipeline: Any
    ) -> Any:
        """
        Use img2img / inpainting from the diffusion pipeline.

        Expected hook:
            pipeline.generate_img2img(prompt, init_image, strength, mask_hint=None) -> {"image": ...}
        """
        if not hasattr(pipeline, "generate_img2img"):
            raise AttributeError("pipeline has no generate_img2img")

        prompt = plan.inpaint_instruction or plan.style_target or ""
        strength = float(plan.img2img_strength)
        result = pipeline.generate_img2img(
            prompt=prompt,
            init_image=image,
            strength=strength,
            mask_hint=plan.inpaint_mask_hint,
        )
        if (
            isinstance(result, dict)
            and "image" in result
            and result["image"] is not None
        ):
            return result["image"]
        return image

    def _apply_fallback(self, image: Any, plan: ModificationPlan) -> Any:
        """
        Best-effort PIL fallback when no diffusion pipeline is available.
        Applies simple transforms based on the style target or instruction.
        """
        if not HAS_PIL or ImageFilter is None or not hasattr(image, "copy"):
            return image
        img = image.copy()
        style = (plan.style_target or plan.inpaint_instruction or "").lower()

        if any(k in style for k in ["black and white", "noir", "monochrome"]):
            img = img.convert("L").convert("RGB")
        elif any(k in style for k in ["vintage", "sepia"]):
            img = img.convert("L").convert("RGB")
            r, g, b = img.split()
            r = r.point(lambda x: min(x + 40, 255))
            g = g.point(lambda x: min(x + 20, 255))
            b = b.point(lambda x: max(x - 20, 0))
            img = Image.merge("RGB", (r, g, b))  # type: ignore[reportOptionalMemberAccess]
        elif any(k in style for k in ["blur", "soft"]):
            img = img.filter(ImageFilter.GaussianBlur(radius=2))
        elif any(k in style for k in ["sharp", "crisp"]):
            img = img.filter(ImageFilter.SHARPEN).filter(ImageFilter.SHARPEN)

        return img


# ---------------------------------------------------------------------------
# High-level facade  (used by orchestrator / frontend)
# ---------------------------------------------------------------------------


class ImageModificationEngine:
    """
    Single entry point. Feed it a user instruction + the current image.
    It figures out everything and returns the result.
    """

    def __init__(self, diffusion_pipeline: Any = None) -> None:
        self.planner = ModificationPlanner()
        self.executor = ImageModificationExecutor()
        self.pipeline = diffusion_pipeline

    def modify(
        self,
        current_image: Any,
        instruction: str,
        current_prompt: str = "",
    ) -> Tuple[Any, ModificationPlan]:
        """
        Main API.
        Returns (result_image, plan).
        If plan.mod_type == NEW_IMAGE, caller must regenerate using plan.new_prompt.
        """
        plan = self.planner.plan(instruction, current_prompt)
        result_image, _ = self.executor.execute(
            current_image, plan, diffusion_pipeline=self.pipeline
        )
        return result_image, plan


__all__ = [
    "ModificationType",
    "ModificationPlan",
    "IntentParser",
    "ModificationPlanner",
    "ImageModificationExecutor",
    "ImageModificationEngine",
]
