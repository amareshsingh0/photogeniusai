"""
SmartGenius - Unified Intelligent Image Generation Orchestrator.

This is the brain of PhotoGenius AI. It takes a simple user prompt and:
1. Auto-detects style, mood, lighting, camera, quality tier
2. Builds the perfect enhanced prompt using all detection systems
3. Selects optimal generation parameters
4. Returns a single best-quality image

The user sees NONE of this complexity. They just type and get magic.

Better than Midjourney, DALL-E, Grok, SeedRealm - because we combine:
- Universal Prompt Classification (20+ styles, 16+ categories)
- Advanced Style Analysis (ML-powered visual style, surprise, emotion)
- Cinematic Enhancement (lighting, camera, mood, color grading)
- Smart Prompt Engine (category boosters, negative prompts)
- Quality Tier Auto-Selection
- Aspect Ratio Auto-Detection
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

# Import all detection systems
from services.universal_prompt_classifier import (
    UniversalPromptClassifier,
    ClassificationResult,
    get_default_classifier,
)
from services.advanced_classifier import (
    AdvancedStyleClassifier,
    StyleAnalysis,
    VisualStyle,
    SurpriseLevel,
    LightingStyle,
    EmotionalTone,
    get_default_style_classifier,
)
from services.smart_prompt_engine import SmartPromptEngine
from services.cinematic_prompts import CinematicPromptEngine, get_default_cinematic_engine

try:
    from services.observability import StructuredLogger, trace_function
except ImportError:
    trace_function = lambda n=None: (lambda f: f)  # type: ignore
    StructuredLogger = None  # type: ignore

import logging
logger = logging.getLogger(__name__)


class QualityTier(str, Enum):
    """Auto-detected quality tier."""
    FAST = "fast"           # Quick preview, 20 steps
    BALANCED = "balanced"   # Good quality, 30 steps
    QUALITY = "quality"     # High quality, 50 steps
    ULTRA = "ultra"         # Maximum quality, 75 steps


class AspectRatio(str, Enum):
    """Auto-detected aspect ratio."""
    PORTRAIT = "portrait"       # 3:4 (768x1024)
    LANDSCAPE = "landscape"     # 4:3 (1024x768)
    SQUARE = "square"           # 1:1 (1024x1024)
    WIDE = "wide"               # 16:9 (1024x576)
    ULTRAWIDE = "ultrawide"     # 21:9 (1024x439)
    CINEMATIC = "cinematic"     # 2.39:1 (1024x428)


@dataclass
class GeniusResult:
    """Complete analysis and generation config from SmartGenius."""

    # Original input
    original_prompt: str

    # Enhanced prompts
    enhanced_prompt: str
    negative_prompt: str

    # Auto-detected settings
    detected_style: str
    detected_category: str
    detected_medium: str
    detected_lighting: str
    detected_mood: str
    detected_emotion: str
    detected_color_grade: str
    detected_camera: str

    # Visual analysis
    visual_style: VisualStyle
    surprise_level: SurpriseLevel

    # Generation parameters
    quality_tier: QualityTier
    aspect_ratio: AspectRatio
    cfg_scale: float
    steps: int
    width: int
    height: int

    # Confidence scores
    style_confidence: float
    overall_confidence: float

    # Metadata for debugging
    detection_signals: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "original_prompt": self.original_prompt,
            "enhanced_prompt": self.enhanced_prompt,
            "negative_prompt": self.negative_prompt,
            "detected_style": self.detected_style,
            "detected_category": self.detected_category,
            "visual_style": self.visual_style.value,
            "surprise_level": self.surprise_level.value,
            "quality_tier": self.quality_tier.value,
            "aspect_ratio": self.aspect_ratio.value,
            "cfg_scale": self.cfg_scale,
            "steps": self.steps,
            "width": self.width,
            "height": self.height,
            "style_confidence": self.style_confidence,
            "overall_confidence": self.overall_confidence,
        }


class SmartGenius:
    """
    The unified intelligent orchestrator.

    Usage:
        genius = SmartGenius()
        result = genius.analyze("a woman in a red dress at sunset")
        # result contains everything needed for perfect generation
    """

    # Quality keywords that indicate user wants higher quality
    ULTRA_QUALITY_SIGNALS = [
        "masterpiece", "best quality", "ultra", "8k", "uhd", "4k",
        "professional", "award-winning", "museum quality", "gallery",
        "highest quality", "maximum detail", "perfect", "flawless",
    ]

    # Keywords indicating user wants fast/preview
    FAST_SIGNALS = [
        "quick", "fast", "preview", "draft", "rough", "sketch",
    ]

    # Aspect ratio detection
    PORTRAIT_SIGNALS = [
        "portrait", "person", "face", "headshot", "selfie", "woman", "man",
        "girl", "boy", "character", "bust", "upper body", "half body",
    ]

    LANDSCAPE_SIGNALS = [
        "landscape", "scenery", "panorama", "vista", "horizon",
        "mountains", "ocean", "field", "city skyline", "wide shot",
    ]

    WIDE_SIGNALS = [
        "cinematic", "movie", "film", "widescreen", "epic",
        "16:9", "ultrawide", "banner",
    ]

    # CFG scale based on style
    CFG_SCALE_MAP = {
        VisualStyle.REALISTIC: 7.5,
        VisualStyle.CINEMATIC: 8.0,
        VisualStyle.ARTISTIC: 9.0,
        VisualStyle.COOL_EDGY: 8.5,
        VisualStyle.WHIMSICAL: 7.0,
    }

    # Steps based on quality tier
    STEPS_MAP = {
        QualityTier.FAST: 20,
        QualityTier.BALANCED: 30,
        QualityTier.QUALITY: 50,
        QualityTier.ULTRA: 75,
    }

    # Dimensions based on aspect ratio
    DIMENSIONS_MAP = {
        AspectRatio.PORTRAIT: (768, 1024),
        AspectRatio.LANDSCAPE: (1024, 768),
        AspectRatio.SQUARE: (1024, 1024),
        AspectRatio.WIDE: (1024, 576),
        AspectRatio.ULTRAWIDE: (1280, 512),
        AspectRatio.CINEMATIC: (1024, 428),
    }

    def __init__(self) -> None:
        """Initialize all detection engines."""
        self.universal_classifier = get_default_classifier()
        self.style_classifier = get_default_style_classifier()
        self.smart_engine = SmartPromptEngine()
        self.cinematic_engine = get_default_cinematic_engine()

    @trace_function("genius.analyze")  # type: ignore
    def analyze(self, prompt: str) -> GeniusResult:
        """
        Analyze prompt and return complete generation configuration.

        This is the main entry point. Give it any prompt and get back
        everything needed for the perfect image generation.
        """
        prompt = (prompt or "").strip()
        if not prompt:
            prompt = "beautiful portrait with professional lighting"

        prompt_lower = prompt.lower()

        # 1. Universal classification (style, category, medium, lighting, etc.)
        classification = self.universal_classifier.classify(prompt)

        # 2. Advanced style analysis (visual style, surprise, emotion)
        style_analysis = self.style_classifier.classify(prompt)

        # 3. Cinematic enhancement (lighting, camera, mood, color grade)
        cinematic_result = self.cinematic_engine.enhance_prompt(
            prompt,
            auto_detect=True
        )
        cinematic_settings = cinematic_result["settings"]

        # 4. Build smart prompt using classification
        smart_positive, smart_negative = self.smart_engine.build_prompts(classification)

        # 5. Detect quality tier
        quality_tier = self._detect_quality_tier(prompt_lower)

        # 6. Detect aspect ratio
        aspect_ratio = self._detect_aspect_ratio(prompt_lower, classification)

        # 7. Get optimal CFG scale based on visual style
        cfg_scale = self.CFG_SCALE_MAP.get(style_analysis.visual_style, 7.5)

        # 8. Adjust CFG based on surprise level
        if style_analysis.surprise_level == SurpriseLevel.HIGH:
            cfg_scale = max(6.0, cfg_scale - 1.0)  # Lower CFG for more creativity
        elif style_analysis.surprise_level == SurpriseLevel.SAFE:
            cfg_scale = min(10.0, cfg_scale + 0.5)  # Higher CFG for more adherence

        # 9. Get steps and dimensions
        steps = self.STEPS_MAP[quality_tier]
        width, height = self.DIMENSIONS_MAP[aspect_ratio]

        # 10. Combine prompts intelligently
        enhanced_prompt = self._combine_prompts(
            prompt,
            smart_positive,
            cinematic_result["enhanced_prompt"],
            style_analysis,
            classification,
        )

        # 11. Build comprehensive negative prompt
        negative_prompt = self._build_negative(
            smart_negative,
            cinematic_result["negative_prompt"],
            classification,
        )

        # 12. Calculate overall confidence
        overall_confidence = (
            style_analysis.style_confidence * 0.3 +
            style_analysis.lighting_confidence * 0.2 +
            style_analysis.emotion_confidence * 0.2 +
            0.3  # Base confidence for rule-based systems
        )

        return GeniusResult(
            original_prompt=prompt,
            enhanced_prompt=enhanced_prompt,
            negative_prompt=negative_prompt,
            detected_style=classification.style,
            detected_category=classification.category,
            detected_medium=classification.medium,
            detected_lighting=cinematic_settings["lighting"],
            detected_mood=cinematic_settings["mood"],
            detected_emotion=style_analysis.emotional_tone.value,
            detected_color_grade=cinematic_settings["color_grade"],
            detected_camera=cinematic_settings["camera"],
            visual_style=style_analysis.visual_style,
            surprise_level=style_analysis.surprise_level,
            quality_tier=quality_tier,
            aspect_ratio=aspect_ratio,
            cfg_scale=round(cfg_scale, 1),
            steps=steps,
            width=width,
            height=height,
            style_confidence=style_analysis.style_confidence,
            overall_confidence=round(overall_confidence, 2),
            detection_signals={
                "classification": classification.to_dict(),
                "style_analysis": {
                    "visual_style": style_analysis.visual_style.value,
                    "surprise": style_analysis.surprise_level.value,
                    "lighting": style_analysis.lighting_style.value,
                    "emotion": style_analysis.emotional_tone.value,
                    "signals": style_analysis.detected_signals,
                },
                "cinematic": cinematic_settings,
            },
        )

    def _detect_quality_tier(self, prompt_lower: str) -> QualityTier:
        """Auto-detect quality tier from prompt."""
        # Check for ultra quality signals
        ultra_count = sum(1 for s in self.ULTRA_QUALITY_SIGNALS if s in prompt_lower)
        if ultra_count >= 2:
            return QualityTier.ULTRA
        if ultra_count >= 1:
            return QualityTier.QUALITY

        # Check for fast signals
        if any(s in prompt_lower for s in self.FAST_SIGNALS):
            return QualityTier.FAST

        # Default to balanced for best experience
        return QualityTier.BALANCED

    def _detect_aspect_ratio(
        self,
        prompt_lower: str,
        classification: ClassificationResult
    ) -> AspectRatio:
        """Auto-detect best aspect ratio."""
        # Check for explicit cinematic/wide signals
        if any(s in prompt_lower for s in self.WIDE_SIGNALS):
            if "ultrawide" in prompt_lower or "21:9" in prompt_lower:
                return AspectRatio.ULTRAWIDE
            return AspectRatio.CINEMATIC

        # Check for portrait signals
        if classification.has_people or any(s in prompt_lower for s in self.PORTRAIT_SIGNALS):
            return AspectRatio.PORTRAIT

        # Check for landscape signals
        if any(s in prompt_lower for s in self.LANDSCAPE_SIGNALS):
            return AspectRatio.LANDSCAPE

        # Category-based detection
        if classification.category in ["portrait", "action"]:
            return AspectRatio.PORTRAIT
        if classification.category in ["landscape", "nature"]:
            return AspectRatio.LANDSCAPE
        if classification.category in ["product", "graphics"]:
            return AspectRatio.SQUARE

        # Default to portrait (most versatile for AI portraits)
        return AspectRatio.PORTRAIT

    def _combine_prompts(
        self,
        original: str,
        smart_positive: str,
        cinematic_enhanced: str,
        style_analysis: StyleAnalysis,
        classification: ClassificationResult,
    ) -> str:
        """Intelligently combine all prompt enhancements."""
        parts: List[str] = []

        # Start with cinematic enhancement (has the best structure)
        # But replace the generic "professional cinematic photograph of" if not cinematic style
        if style_analysis.visual_style != VisualStyle.CINEMATIC:
            # Use style-appropriate opener
            openers = {
                VisualStyle.REALISTIC: "photorealistic image of",
                VisualStyle.ARTISTIC: "artistic masterpiece of",
                VisualStyle.COOL_EDGY: "dramatic stylized image of",
                VisualStyle.WHIMSICAL: "whimsical enchanting image of",
            }
            opener = openers.get(style_analysis.visual_style, "stunning image of")
            enhanced = cinematic_enhanced.replace(
                "professional cinematic photograph of",
                opener
            )
            parts.append(enhanced)
        else:
            parts.append(cinematic_enhanced)

        # Add emotion/mood reinforcement
        emotion_boosters = {
            EmotionalTone.SERENE: "peaceful harmonious atmosphere",
            EmotionalTone.INTENSE: "powerful intense energy",
            EmotionalTone.MYSTERIOUS: "enigmatic intriguing mood",
            EmotionalTone.JOYFUL: "vibrant joyful expression",
            EmotionalTone.MELANCHOLIC: "contemplative wistful feeling",
            EmotionalTone.EPIC: "grand heroic scale",
        }
        if style_analysis.emotional_tone in emotion_boosters:
            parts.append(emotion_boosters[style_analysis.emotional_tone])

        # Add surprise boosters if high surprise detected
        if style_analysis.surprise_level == SurpriseLevel.HIGH:
            parts.append("unexpected creative elements, unique artistic interpretation")

        # Universal quality boosters (always add)
        parts.extend([
            "masterpiece quality",
            "highly detailed",
            "perfect composition",
            "professional execution",
        ])

        # Deduplicate while preserving order
        combined = ", ".join(parts)
        seen = set()
        deduped: List[str] = []
        for segment in combined.split(", "):
            segment = segment.strip()
            key = segment.lower()
            if key and key not in seen:
                seen.add(key)
                deduped.append(segment)

        return ", ".join(deduped)

    def _build_negative(
        self,
        smart_negative: str,
        cinematic_negative: str,
        classification: ClassificationResult,
    ) -> str:
        """Build comprehensive negative prompt."""
        # Combine both negative prompts
        all_negatives = set()

        for neg in smart_negative.split(", "):
            all_negatives.add(neg.strip().lower())

        for neg in cinematic_negative.split(", "):
            all_negatives.add(neg.strip().lower())

        # Always add critical negatives
        critical = [
            "worst quality", "low quality", "blurry", "pixelated",
            "deformed", "disfigured", "bad anatomy", "extra limbs",
            "watermark", "text", "logo", "signature",
            "amateur", "unprofessional",
        ]
        for c in critical:
            all_negatives.add(c)

        # Remove empty strings
        all_negatives.discard("")

        return ", ".join(sorted(all_negatives))


# ==================== CONVENIENCE API ====================

_default_genius: Optional[SmartGenius] = None


def get_smart_genius() -> SmartGenius:
    """Get or create default SmartGenius instance."""
    global _default_genius
    if _default_genius is None:
        _default_genius = SmartGenius()
    return _default_genius


def genius_analyze(prompt: str) -> GeniusResult:
    """Quick analysis using default SmartGenius."""
    return get_smart_genius().analyze(prompt)


def genius_generate_config(prompt: str) -> Dict[str, Any]:
    """Get generation config dict for API use."""
    result = genius_analyze(prompt)
    return {
        "prompt": result.enhanced_prompt,
        "negative_prompt": result.negative_prompt,
        "width": result.width,
        "height": result.height,
        "cfg_scale": result.cfg_scale,
        "steps": result.steps,
        "quality_tier": result.quality_tier.value,
        "detected_settings": {
            "style": result.detected_style,
            "category": result.detected_category,
            "visual_style": result.visual_style.value,
            "mood": result.detected_mood,
            "lighting": result.detected_lighting,
        },
    }


__all__ = [
    "SmartGenius",
    "GeniusResult",
    "QualityTier",
    "AspectRatio",
    "get_smart_genius",
    "genius_analyze",
    "genius_generate_config",
]


# ==================== TESTING ====================

if __name__ == "__main__":
    genius = SmartGenius()

    test_prompts = [
        "a woman in a red dress at sunset",
        "cyberpunk city at night with neon lights",
        "cute anime girl with pink hair",
        "professional headshot of a businessman",
        "epic fantasy warrior in dramatic battle",
        "peaceful mountain landscape at dawn",
        "mysterious dark forest with fog",
        "happy child playing in garden",
        "masterpiece 8k ultra detailed portrait",
        "quick sketch of a cat",
    ]

    print("=" * 80)
    print("SmartGenius Test Results")
    print("=" * 80)

    for prompt in test_prompts:
        result = genius.analyze(prompt)
        print(f"\n{'='*60}")
        print(f"PROMPT: {prompt}")
        print(f"{'='*60}")
        print(f"Visual Style: {result.visual_style.value}")
        print(f"Category: {result.detected_category}")
        print(f"Mood: {result.detected_mood}")
        print(f"Lighting: {result.detected_lighting}")
        print(f"Quality Tier: {result.quality_tier.value}")
        print(f"Aspect Ratio: {result.aspect_ratio.value}")
        print(f"Dimensions: {result.width}x{result.height}")
        print(f"CFG Scale: {result.cfg_scale}")
        print(f"Steps: {result.steps}")
        print(f"Confidence: {result.overall_confidence}")
        print(f"\nEnhanced (first 150 chars):")
        print(f"  {result.enhanced_prompt[:150]}...")

    print("\n" + "=" * 80)
    print("All tests completed!")
