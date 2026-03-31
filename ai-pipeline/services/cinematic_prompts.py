"""
Cinematic Image Prompt Enhancement.

Image-specific enhancement with lighting presets, camera specs, mood descriptors,
color grading, quality keywords, and comprehensive negative prompts. Used for
IMAGE domain prompts after domain classification.
"""

from __future__ import annotations

import random
import logging
from typing import Any, Dict, List, Optional

# Optional observability
try:
    from services.observability import StructuredLogger, trace_function
except ImportError:
    trace_function = lambda n=None: (lambda f: f)  # type: ignore[assignment, misc]
    StructuredLogger = None  # type: ignore[assignment, misc]

logger = logging.getLogger(__name__)


def _log() -> Any:
    logger_cls = StructuredLogger
    if logger_cls is not None:
        return logger_cls(__name__)
    return logger


# ==================== CinematicPromptEngine ====================


class CinematicPromptEngine:
    """Cinematic enhancement for image generation."""

    # ==================== LIGHTING PRESETS ====================

    LIGHTING_PRESETS: Dict[str, Dict[str, Any]] = {
        "golden_hour": {
            "description": "Warm sunset/sunrise lighting",
            "prompt": "golden hour rim lighting, warm backlight, soft sky fill, volumetric god rays",
            "keywords": ["sunset", "sunrise", "golden hour", "dusk", "dawn"],
        },
        "dramatic": {
            "description": "High contrast dramatic lighting",
            "prompt": "dramatic side lighting, high contrast, strong shadows, rim light separation, chiaroscuro",
            "keywords": ["dramatic", "intense", "powerful", "bold"],
        },
        "soft_studio": {
            "description": "Professional studio portrait lighting",
            "prompt": "soft studio lighting, diffused key light, subtle fill, professional portrait setup",
            "keywords": ["studio", "portrait", "professional", "headshot"],
        },
        "natural": {
            "description": "Natural daylight",
            "prompt": "natural window light, soft indirect lighting, gentle shadows, ambient daylight",
            "keywords": ["natural", "daylight", "window", "outdoor"],
        },
        "moody": {
            "description": "Dark moody atmosphere",
            "prompt": "moody atmospheric lighting, low key lighting, selective illumination, mysterious shadows",
            "keywords": ["moody", "dark", "noir", "night", "mysterious"],
        },
        "blue_hour": {
            "description": "Twilight blue hour",
            "prompt": "blue hour ambient light, cool cyan tones, soft diffused twilight",
            "keywords": ["blue hour", "twilight", "evening", "dusk"],
        },
        "cinematic": {
            "description": "Movie-style lighting",
            "prompt": "cinematic three-point lighting, professional film lighting, dramatic contrast, motivated lighting",
            "keywords": ["cinematic", "movie", "film"],
        },
    }

    # ==================== CAMERA SPECS ====================

    CAMERA_PRESETS: Dict[str, Dict[str, Any]] = {
        "portrait": {
            "prompt": "85mm lens, f/1.8 aperture, shallow depth of field, eye-level angle, beautiful bokeh",
            "use_for": ["portrait", "person", "face", "headshot"],
        },
        "wide": {
            "prompt": "24mm wide angle lens, f/8 aperture, deeper depth of field, environmental context",
            "use_for": ["landscape", "environment", "scene", "architecture"],
        },
        "telephoto": {
            "prompt": "135mm telephoto lens, f/2.0 aperture, compressed perspective, creamy bokeh",
            "use_for": ["isolated", "detail", "candid"],
        },
        "cinematic": {
            "prompt": "anamorphic lens, 2.39:1 aspect ratio, cinematic bokeh, subtle lens flares",
            "use_for": ["cinematic", "movie", "epic"],
        },
        "macro": {
            "prompt": "100mm macro lens, f/2.8 aperture, extreme detail focus, minimal depth of field",
            "use_for": ["close-up", "detail", "macro", "texture"],
        },
    }

    # ==================== MOOD PRESETS ====================

    MOOD_PRESETS: Dict[str, str] = {
        "serene": "serene peaceful mood, calm tranquil atmosphere, gentle contemplative feeling",
        "dramatic": "dramatic intense mood, powerful commanding presence, emotional depth",
        "mysterious": "mysterious enigmatic atmosphere, intriguing secretive mood, veiled allure",
        "joyful": "joyful uplifting mood, positive vibrant energy, cheerful radiant atmosphere",
        "melancholic": "melancholic contemplative mood, wistful introspective atmosphere, bittersweet tone",
        "epic": "epic grand scale, heroic majestic mood, powerful cinematic presence",
        "intimate": "intimate personal mood, warm tender atmosphere, emotional closeness",
        "ethereal": "ethereal dreamlike mood, otherworldly mystical atmosphere, transcendent quality",
    }

    # ==================== COLOR GRADING ====================

    COLOR_GRADING: Dict[str, str] = {
        "teal_orange": "teal and orange color grading, warm skin tones, cool shadows, filmic look",
        "warm_film": "warm film color grading, golden amber tones, rich vintage colors, nostalgic warmth",
        "cool_modern": "cool modern color grading, blue-cyan tones, crisp clean look, contemporary style",
        "desaturated": "desaturated muted colors, subtle refined tones, artistic muted palette",
        "vibrant": "vibrant saturated colors, rich deep tones, bold punchy color grading",
        "cinematic": "cinematic color grading, professional film look, balanced sophisticated tones",
    }

    # ==================== QUALITY KEYWORDS ====================

    QUALITY_KEYWORDS: List[str] = [
        "masterpiece",
        "best quality",
        "highly detailed",
        "photorealistic",
        "8k uhd",
        "dslr photography",
        "professional photo",
        "sharp focus",
        "intricate details",
        "realistic skin texture",
        "natural skin pores",
        "detailed eyes with catchlight",
        "fabric texture details",
        "professional composition",
    ]

    # ==================== NEGATIVE PROMPT ====================

    NEGATIVE_BASE: List[str] = [
        # Quality issues
        "simple",
        "plain",
        "flat lighting",
        "boring composition",
        "amateur photo",
        "low detail",
        "low quality",
        "worst quality",
        "blurry",
        "blurry background",
        "no depth",
        "out of focus",
        # Artifacts
        "cartoon",
        "anime",
        "painting",
        "sketch",
        "illustration",
        "drawing",
        "ai artifacts",
        "digital artifacts",
        "glitches",
        "noise",
        "jpeg artifacts",
        "compression artifacts",
        # Exposure/color issues
        "overexposed",
        "underexposed",
        "washed out",
        "too bright",
        "too dark",
        "oversaturated",
        "undersaturated",
        # Skin/face issues
        "plastic skin",
        "doll-like",
        "waxy skin",
        "artificial skin",
        "unnatural skin",
        "bad skin",
        "skin blemishes",
        # Anatomy issues
        "deformed",
        "distorted",
        "mutated",
        "disfigured",
        "bad anatomy",
        "bad proportions",
        "extra limbs",
        "missing limbs",
        "missing arms",
        "missing legs",
        "missing hands",
        "amputated",
        "hand cut off",
        "invisible hand",
        "phantom limb",
        "hand absorbed",
        "duplicate object",
        "extra ball",
        "floating duplicate",
        "cloned object",
        "bad hands",
        "extra fingers",
        "fused fingers",
        # Composition issues
        "cropped",
        "cut off",
        "out of frame",
        "text",
        "watermark",
        "signature",
        "logo",
        "username",
        # Lighting issues
        "unnatural lighting",
        "harsh shadows",
        "flat lighting",
    ]

    # ==================== AUTO-DETECTION ====================

    def auto_detect_lighting(self, prompt: str) -> str:
        """Auto-detect best lighting from prompt."""
        prompt_lower = (prompt or "").strip().lower()
        for preset_name, preset_data in self.LIGHTING_PRESETS.items():
            keywords = preset_data.get("keywords", [])
            if any(kw in prompt_lower for kw in keywords):
                return preset_name
        return "golden_hour"

    def auto_detect_camera(self, prompt: str) -> str:
        """Auto-detect camera type from prompt."""
        prompt_lower = (prompt or "").strip().lower()
        for preset_name, preset_data in self.CAMERA_PRESETS.items():
            use_for = preset_data.get("use_for", [])
            if any(kw in prompt_lower for kw in use_for):
                return preset_name
        return "portrait"

    def auto_detect_mood(self, prompt: str) -> str:
        """Auto-detect mood from prompt."""
        prompt_lower = (prompt or "").strip().lower()
        mood_keywords: Dict[str, List[str]] = {
            "serene": ["peaceful", "calm", "serene", "tranquil"],
            "dramatic": ["dramatic", "intense", "powerful", "bold"],
            "mysterious": ["mysterious", "enigmatic", "dark", "secretive"],
            "joyful": ["happy", "joyful", "cheerful", "smiling"],
            "melancholic": ["sad", "melancholic", "contemplative", "wistful"],
            "epic": ["epic", "heroic", "grand", "majestic"],
            "intimate": ["intimate", "personal", "close", "tender"],
            "ethereal": ["ethereal", "dreamlike", "mystical", "magical"],
        }
        for mood, keywords in mood_keywords.items():
            if any(kw in prompt_lower for kw in keywords):
                return mood
        return "serene"

    def auto_detect_color_grade(self, prompt: str) -> str:
        """Auto-detect color grading from prompt."""
        prompt_lower = (prompt or "").strip().lower()
        if any(w in prompt_lower for w in ["vintage", "retro", "film", "analog"]):
            return "warm_film"
        if any(
            w in prompt_lower for w in ["vibrant", "colorful", "saturated", "bright"]
        ):
            return "vibrant"
        if any(
            w in prompt_lower for w in ["muted", "subtle", "artistic", "desaturated"]
        ):
            return "desaturated"
        if any(w in prompt_lower for w in ["modern", "clean", "minimal"]):
            return "cool_modern"
        return "teal_orange"

    # ==================== MAIN ENHANCEMENT ====================

    @trace_function("cinematic.enhance")  # type: ignore[misc]
    def enhance_prompt(
        self,
        base_prompt: str,
        auto_detect: bool = True,
        lighting: Optional[str] = None,
        camera: Optional[str] = None,
        mood: Optional[str] = None,
        color_grade: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Transform simple prompt into cinematic-style prompt.

        Args:
            base_prompt: Simple user prompt (may already have wow boosters)
            auto_detect: Auto-detect settings from prompt
            lighting: Override lighting (or auto-detect)
            camera: Override camera (or auto-detect)
            mood: Override mood (or auto-detect)
            color_grade: Override color grading (or auto-detect)

        Returns:
            Dict with enhanced_prompt, negative_prompt, and settings metadata
        """
        base_prompt = (base_prompt or "").strip()

        if auto_detect:
            lighting = lighting or self.auto_detect_lighting(base_prompt)
            camera = camera or self.auto_detect_camera(base_prompt)
            mood = mood or self.auto_detect_mood(base_prompt)
            color_grade = color_grade or self.auto_detect_color_grade(base_prompt)

        # Validate preset keys (fallback to defaults if invalid)
        if lighting not in self.LIGHTING_PRESETS:
            lighting = "golden_hour"
        if camera not in self.CAMERA_PRESETS:
            camera = "portrait"
        if mood not in self.MOOD_PRESETS:
            mood = "serene"
        if color_grade not in self.COLOR_GRADING:
            color_grade = "teal_orange"

        parts: List[str] = []
        parts.append("professional cinematic photograph of")
        parts.append(base_prompt)
        parts.append(self.LIGHTING_PRESETS[lighting]["prompt"])
        parts.append(self.CAMERA_PRESETS[camera]["prompt"])
        parts.append(self.MOOD_PRESETS[mood])
        parts.append(self.COLOR_GRADING[color_grade])
        parts.append("highly detailed skin texture")
        parts.append("realistic eyes with natural catchlight")
        parts.append("intricate fabric and material details")

        num_quality = min(8, len(self.QUALITY_KEYWORDS))
        selected_quality = random.sample(self.QUALITY_KEYWORDS, num_quality)
        parts.extend(selected_quality)
        parts.append("subtle film grain")

        enhanced_prompt = ", ".join(parts)

        negative_prompt = ", ".join(self.NEGATIVE_BASE)
        if camera == "portrait":
            negative_prompt += (
                ", multiple people, cropped face, asymmetric eyes, unnatural expression"
            )

        _log().info(
            "Cinematic enhancement applied",
            extra={
                "lighting": lighting,
                "camera": camera,
                "mood": mood,
                "color_grade": color_grade,
                "original_length": len(base_prompt),
                "enhanced_length": len(enhanced_prompt),
            },
        )

        return {
            "enhanced_prompt": enhanced_prompt,
            "negative_prompt": negative_prompt,
            "settings": {
                "lighting": lighting,
                "camera": camera,
                "mood": mood,
                "color_grade": color_grade,
            },
        }


_default_cinematic_engine: Optional[CinematicPromptEngine] = None


def get_default_cinematic_engine() -> CinematicPromptEngine:
    """Return the default CinematicPromptEngine instance (singleton)."""
    global _default_cinematic_engine
    if _default_cinematic_engine is None:
        _default_cinematic_engine = CinematicPromptEngine()
    return _default_cinematic_engine


def enhance_cinematic(
    base_prompt: str,
    auto_detect: bool = True,
    lighting: Optional[str] = None,
    camera: Optional[str] = None,
    mood: Optional[str] = None,
    color_grade: Optional[str] = None,
) -> Dict[str, Any]:
    """Convenience: enhance prompt using default CinematicPromptEngine."""
    return get_default_cinematic_engine().enhance_prompt(
        base_prompt,
        auto_detect=auto_detect,
        lighting=lighting,
        camera=camera,
        mood=mood,
        color_grade=color_grade,
    )


__all__ = [
    "CinematicPromptEngine",
    "get_default_cinematic_engine",
    "enhance_cinematic",
]


# ==================== Testing & Validation ====================

if __name__ == "__main__":
    engine = CinematicPromptEngine()
    simple = "young woman at beach"

    # Auto-detection
    assert engine.auto_detect_lighting("sunset at the beach") == "golden_hour"
    assert engine.auto_detect_camera("portrait of a woman") == "portrait"
    assert engine.auto_detect_mood("dramatic scene") == "dramatic"
    assert engine.auto_detect_color_grade("vintage look") == "warm_film"
    print("Auto-detection OK.")

    # Full enhancement
    result = engine.enhance_prompt(simple, auto_detect=True)
    assert "enhanced_prompt" in result
    assert "negative_prompt" in result
    assert "settings" in result
    assert result["settings"]["lighting"] in engine.LIGHTING_PRESETS
    assert result["settings"]["camera"] in engine.CAMERA_PRESETS
    assert "professional cinematic photograph" in result["enhanced_prompt"]
    assert "golden hour" in result["enhanced_prompt"] or "golden_hour" in str(
        result["settings"]
    )
    assert len(result["negative_prompt"]) > 100
    assert len(result["enhanced_prompt"]) < 2500  # Reasonable length
    print("Full enhancement OK.")
    print("ENHANCED (first 200 chars):", result["enhanced_prompt"][:200] + "...")
    print("NEGATIVE (first 150 chars):", result["negative_prompt"][:150] + "...")

    # Override
    result2 = engine.enhance_prompt(
        simple, auto_detect=False, lighting="moody", camera="wide"
    )
    assert result2["settings"]["lighting"] == "moody"
    assert result2["settings"]["camera"] == "wide"
    print("Override OK.")

    # Convenience API
    result3 = enhance_cinematic("portrait headshot", auto_detect=True)
    assert result3["settings"]["camera"] == "portrait"
    print("enhance_cinematic() OK.")

    print("Cinematic prompt validation passed.")

    # Validation checklist:
    # [x] Auto-detection works for lighting/camera/mood/color_grade
    # [x] All presets produce valid prompts (keys validated)
    # [x] Negative prompt is comprehensive (quality, artifacts, anatomy, etc.)
    # [x] Quality keywords are included (8 random from list)
    # [x] Output length is reasonable (capped by structure; <2500 chars)
