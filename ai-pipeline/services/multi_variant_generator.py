"""
Multi-Variant Generator – Generate 5–6 styled variants from a single prompt.

Variants:
1. Realistic/Clean – Literal, photorealistic
2. Cinematic/Epic – Movie-style, dramatic (RECOMMENDED)
3. Cool/Edgy/Dark – Cyberpunk, neon, moody
4. Artistic/Surreal – Painterly, dreamlike
5. Max Surprise – Highest chaos, unconventional
6. Personalized – Based on user history (optional)

Each variant has distinct enhancement, model params (e.g. MJ --chaos, --weird),
scores (detail, cinematic fit, surprise, wow), and remix/escalate options.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, Dict, List, Optional

from services.advanced_classifier import (
    AdvancedStyleClassifier,
    EmotionalTone,
    LightingStyle,
    StyleAnalysis,
    SurpriseLevel,
    VisualStyle,
)
from services.cinematic_prompts import CinematicPromptEngine
from services.observability import StructuredLogger, trace_function
from services.user_preference_analyzer import UserPreferenceAnalyzer

logger = StructuredLogger(__name__)


class VariantType(str, Enum):
    """Variant types."""

    REALISTIC = "realistic"
    CINEMATIC = "cinematic"
    COOL_EDGY = "cool_edgy"
    ARTISTIC = "artistic"
    MAX_SURPRISE = "max_surprise"
    PERSONALIZED = "personalized"


@dataclass
class VariantScore:
    """Scoring for each variant."""

    detail_score: float  # 0-10
    cinematic_fit: float  # 0-10
    surprise_factor: float  # 0-10
    wow_factor: float  # 0-10

    def overall_score(self) -> float:
        """Weighted overall score."""
        return (
            self.detail_score * 0.25
            + self.cinematic_fit * 0.30
            + self.surprise_factor * 0.20
            + self.wow_factor * 0.25
        )


@dataclass
class PromptVariant:
    """Single enhanced variant."""

    variant_type: VariantType
    enhanced_prompt: str
    negative_prompt: str
    model_params: Dict[str, Any]
    scores: VariantScore
    is_recommended: bool = False
    is_personalized: bool = False
    remix_suggestions: List[str] = field(default_factory=list)
    escalate_options: Dict[str, str] = field(default_factory=dict)


@dataclass
class MultiVariantResult:
    """Complete multi-variant generation result."""

    original_prompt: str
    variants: List[PromptVariant]
    recommended_index: int
    personalized_index: Optional[int]
    detected_style: VisualStyle
    detected_surprise: SurpriseLevel
    detected_lighting: LightingStyle
    detected_emotion: EmotionalTone


class MultiVariantGenerator:
    """Generate multiple styled variants from a single prompt."""

    VARIANT_CONFIGS = {
        VariantType.REALISTIC: {
            "description": "Photorealistic, literal interpretation",
            "lighting_override": None,
            "mood_override": None,
            "surprise_intensity": 0.0,
            "quality_keywords": [
                "photorealistic", "realistic", "photograph", "dslr",
                "natural", "authentic", "true to life", "real",
            ],
            "style_suffix": "photorealistic, natural lighting, authentic, realistic photograph",
            "mj_params": {
                "stylize": 300,
                "chaos": 0,
                "weird": 0,
                "style": "raw",
            },
        },
        VariantType.CINEMATIC: {
            "description": "Movie-style, dramatic, professional (RECOMMENDED)",
            "lighting_override": "cinematic",
            "mood_override": "epic",
            "surprise_intensity": 0.4,
            "quality_keywords": [
                "cinematic", "epic", "dramatic", "professional",
                "blockbuster", "theatrical", "film quality",
            ],
            "style_suffix": "cinematic masterpiece, epic composition, professional film quality, volumetric lighting, dramatic atmosphere",
            "mj_params": {
                "stylize": 750,
                "chaos": 40,
                "weird": 200,
            },
        },
        VariantType.COOL_EDGY: {
            "description": "Cyberpunk, neon, dark, mysterious",
            "lighting_override": "neon",
            "mood_override": "mysterious",
            "surprise_intensity": 0.6,
            "quality_keywords": [
                "cyberpunk", "neon", "dark", "edgy", "cool",
                "atmospheric", "moody", "urban",
            ],
            "style_suffix": "neon cyberpunk aesthetic, dark moody atmosphere, rain-slicked streets, holographic elements, futuristic noir",
            "mj_params": {
                "stylize": 650,
                "chaos": 60,
                "weird": 400,
            },
        },
        VariantType.ARTISTIC: {
            "description": "Painterly, dreamlike, creative",
            "lighting_override": "soft",
            "mood_override": "ethereal",
            "surprise_intensity": 0.7,
            "quality_keywords": [
                "artistic", "painterly", "creative", "imaginative",
                "dreamlike", "ethereal", "stylized",
            ],
            "style_suffix": "artistic masterpiece, painterly quality, dreamlike atmosphere, creative interpretation, ethereal beauty",
            "mj_params": {
                "stylize": 900,
                "chaos": 50,
                "weird": 500,
            },
        },
        VariantType.MAX_SURPRISE: {
            "description": "Maximum chaos, weird, unconventional",
            "lighting_override": "moody",
            "mood_override": "mysterious",
            "surprise_intensity": 1.0,
            "quality_keywords": [
                "surreal", "impossible", "mind-bending", "otherworldly",
                "bizarre", "transcendent", "mystical",
            ],
            "style_suffix": "impossible surreal elements, reality-bending physics, mystical otherworldly atmosphere, paradoxical composition, transcendent experience",
            "mj_params": {
                "stylize": 850,
                "chaos": 100,
                "weird": 1000,
            },
        },
    }

    def __init__(
        self,
        preference_analyzer: Optional[UserPreferenceAnalyzer] = None,
    ) -> None:
        self.style_classifier = AdvancedStyleClassifier(use_ml=False)
        self.cinematic_engine = CinematicPromptEngine()
        self.preference_analyzer = preference_analyzer
        logger.info("MultiVariantGenerator initialized")

    @trace_function("variants.generate")  # type: ignore[misc]
    def generate_variants(
        self,
        prompt: str,
        user_id: Optional[str] = None,
        include_personalized: bool = True,
    ) -> MultiVariantResult:
        """Generate all variants (5 or 6 with personalized)."""
        style_analysis = self.style_classifier.classify(prompt)

        logger.info(
            "Generating variants",
            detected_style=style_analysis.visual_style.value,
            detected_surprise=style_analysis.surprise_level.value,
        )

        variants: List[PromptVariant] = []
        variants.append(self._generate_realistic_variant(prompt, style_analysis))

        cinematic_variant = self._generate_cinematic_variant(prompt, style_analysis)
        cinematic_variant.is_recommended = True
        variants.append(cinematic_variant)

        variants.append(self._generate_cool_edgy_variant(prompt, style_analysis))
        variants.append(self._generate_artistic_variant(prompt, style_analysis))
        variants.append(self._generate_max_surprise_variant(prompt, style_analysis))

        personalized_variant: Optional[PromptVariant] = None
        personalized_index: Optional[int] = None

        if include_personalized and user_id and self.preference_analyzer:
            personalized_variant = self._generate_personalized_variant(
                prompt,
                style_analysis,
                user_id,
            )
            if personalized_variant is not None:
                personalized_variant.is_personalized = True
                variants.append(personalized_variant)
                personalized_index = 5

        result = MultiVariantResult(
            original_prompt=prompt,
            variants=variants,
            recommended_index=1,
            personalized_index=personalized_index,
            detected_style=style_analysis.visual_style,
            detected_surprise=style_analysis.surprise_level,
            detected_lighting=style_analysis.lighting_style,
            detected_emotion=style_analysis.emotional_tone,
        )

        logger.info(
            "Variants generated",
            total_variants=len(variants),
            has_personalized=personalized_variant is not None,
        )
        return result

    def _generate_realistic_variant(
        self,
        prompt: str,
        style_analysis: StyleAnalysis,
    ) -> PromptVariant:
        config = self.VARIANT_CONFIGS[VariantType.REALISTIC]
        enhanced_parts = [
            f"photorealistic photograph of {prompt}",
            "natural lighting",
            "authentic realistic details",
            "dslr photography",
            "sharp focus",
            "high quality",
        ]
        enhanced = ", ".join(enhanced_parts)
        negative = self._build_negative_for_variant(VariantType.REALISTIC)
        scores = VariantScore(
            detail_score=7.0,
            cinematic_fit=3.0,
            surprise_factor=1.0,
            wow_factor=5.0,
        )
        remix = [
            "Add cinematic lighting",
            "Increase drama",
            "Add creative elements",
        ]
        escalate = {
            "more_detail": "Add intricate details and textures",
            "more_dramatic": "Switch to cinematic variant",
        }
        return PromptVariant(
            variant_type=VariantType.REALISTIC,
            enhanced_prompt=enhanced,
            negative_prompt=negative,
            model_params=dict(config["mj_params"]),
            scores=scores,
            remix_suggestions=remix,
            escalate_options=escalate,
        )

    def _generate_cinematic_variant(
        self,
        prompt: str,
        style_analysis: StyleAnalysis,
    ) -> PromptVariant:
        config = self.VARIANT_CONFIGS[VariantType.CINEMATIC]
        cinematic_result = self.cinematic_engine.enhance_prompt(
            base_prompt=prompt,
            auto_detect=True,
            lighting=config["lighting_override"],
            mood=config["mood_override"],
        )
        enhanced = cinematic_result["enhanced_prompt"]
        enhanced += f", {config['style_suffix']}"
        surprise = self._generate_surprise_element(
            prompt, intensity=config["surprise_intensity"]
        )
        if surprise:
            enhanced += f", {surprise}"
        negative = cinematic_result["negative_prompt"]
        scores = VariantScore(
            detail_score=9.0,
            cinematic_fit=10.0,
            surprise_factor=6.0,
            wow_factor=9.5,
        )
        remix = [
            "Increase surprise factor",
            "Make it darker/edgier",
            "Add more surreal elements",
        ]
        escalate = {
            "more_dramatic": "Increase lighting contrast and drama",
            "more_surprise": "Switch to max surprise variant",
            "cooler": "Switch to cool/edgy variant",
        }
        return PromptVariant(
            variant_type=VariantType.CINEMATIC,
            enhanced_prompt=enhanced,
            negative_prompt=negative,
            model_params=dict(config["mj_params"]),
            scores=scores,
            remix_suggestions=remix,
            escalate_options=escalate,
        )

    def _generate_cool_edgy_variant(
        self,
        prompt: str,
        style_analysis: StyleAnalysis,
    ) -> PromptVariant:
        config = self.VARIANT_CONFIGS[VariantType.COOL_EDGY]
        enhanced_parts = [
            f"cyberpunk noir photograph of {prompt}",
            "neon lighting with vibrant cyan and magenta accents",
            "rain-slicked dark streets",
            "moody atmospheric fog",
            "holographic UI elements floating in background",
            "dark mysterious shadows",
            "futuristic tech noir aesthetic",
            "high contrast dramatic lighting",
            "cinematic composition",
            config["style_suffix"],
        ]
        surprise = self._generate_surprise_element(prompt, intensity=0.6)
        if surprise:
            surprise = surprise.replace("golden", "neon").replace("warm", "cool")
            enhanced_parts.append(surprise)
        enhanced = ", ".join(enhanced_parts)
        negative = self._build_negative_for_variant(VariantType.COOL_EDGY)
        scores = VariantScore(
            detail_score=8.5,
            cinematic_fit=8.0,
            surprise_factor=7.0,
            wow_factor=8.5,
        )
        remix = [
            "More neon colors",
            "Darker atmosphere",
            "Add rain effects",
        ]
        escalate = {
            "darker": "Increase shadows and darkness",
            "more_neon": "Intensify neon glow effects",
        }
        return PromptVariant(
            variant_type=VariantType.COOL_EDGY,
            enhanced_prompt=enhanced,
            negative_prompt=negative,
            model_params=dict(config["mj_params"]),
            scores=scores,
            remix_suggestions=remix,
            escalate_options=escalate,
        )

    def _generate_artistic_variant(
        self,
        prompt: str,
        style_analysis: StyleAnalysis,
    ) -> PromptVariant:
        config = self.VARIANT_CONFIGS[VariantType.ARTISTIC]
        enhanced_parts = [
            f"artistic dreamlike interpretation of {prompt}",
            "painterly quality with visible brushstrokes",
            "soft ethereal lighting",
            "impressionistic color palette",
            "creative surreal elements blending reality and fantasy",
            "studio ghibli inspired atmosphere",
            "whimsical imaginative details",
            "watercolor-like translucency",
            config["style_suffix"],
        ]
        surprise = self._generate_surprise_element(prompt, intensity=0.7)
        if surprise:
            enhanced_parts.append(surprise)
        enhanced = ", ".join(enhanced_parts)
        negative = self._build_negative_for_variant(VariantType.ARTISTIC)
        scores = VariantScore(
            detail_score=8.0,
            cinematic_fit=6.0,
            surprise_factor=8.0,
            wow_factor=8.0,
        )
        remix = [
            "More painterly style",
            "Increase dreamlike quality",
            "Add fantasy elements",
        ]
        escalate = {
            "more_surreal": "Switch to max surprise variant",
            "more_whimsical": "Increase playful elements",
        }
        return PromptVariant(
            variant_type=VariantType.ARTISTIC,
            enhanced_prompt=enhanced,
            negative_prompt=negative,
            model_params=dict(config["mj_params"]),
            scores=scores,
            remix_suggestions=remix,
            escalate_options=escalate,
        )

    def _generate_max_surprise_variant(
        self,
        prompt: str,
        style_analysis: StyleAnalysis,
    ) -> PromptVariant:
        config = self.VARIANT_CONFIGS[VariantType.MAX_SURPRISE]
        enhanced_parts = [
            f"impossible surreal reimagining of {prompt}",
            "reality-bending physics with floating inverted elements",
            "paradoxical impossible architecture",
            "mystical otherworldly atmosphere",
            "transcendent dreamlike quality",
            "multiple dimensions coexisting",
            "ethereal spirits and energy manifestations",
            "cosmic scale with micro and macro elements merged",
            "M.C. Escher inspired perspective shifts",
            config["style_suffix"],
        ]
        surprises = [
            self._generate_surprise_element(prompt, intensity=1.0),
            self._generate_surprise_element(prompt, intensity=1.0),
        ]
        for s in surprises:
            if s:
                enhanced_parts.append(s)
        enhanced = ", ".join(enhanced_parts)
        negative = self._build_negative_for_variant(VariantType.MAX_SURPRISE)
        scores = VariantScore(
            detail_score=9.5,
            cinematic_fit=7.0,
            surprise_factor=10.0,
            wow_factor=9.0,
        )
        remix = [
            "Tone down chaos slightly",
            "Focus on specific surreal element",
            "Add more grounded elements",
        ]
        escalate = {
            "even_weirder": "Push surrealism to absolute limits",
            "more_abstract": "Reduce recognizable forms",
        }
        return PromptVariant(
            variant_type=VariantType.MAX_SURPRISE,
            enhanced_prompt=enhanced,
            negative_prompt=negative,
            model_params=dict(config["mj_params"]),
            scores=scores,
            remix_suggestions=remix,
            escalate_options=escalate,
        )

    def _generate_personalized_variant(
        self,
        prompt: str,
        style_analysis: StyleAnalysis,
        user_id: str,
    ) -> Optional[PromptVariant]:
        if self.preference_analyzer is None:
            return None
        profile = self.preference_analyzer.get_profile(user_id, min_confidence=0.3)
        if profile is None:
            return None
        defaults = self.preference_analyzer.get_personalized_defaults(user_id)
        preferred_style = defaults["default_style"]
        preferred_surprise = defaults["default_surprise"]

        style_to_variant = {
            VisualStyle.CINEMATIC: VariantType.CINEMATIC,
            VisualStyle.COOL_EDGY: VariantType.COOL_EDGY,
            VisualStyle.ARTISTIC: VariantType.ARTISTIC,
            VisualStyle.REALISTIC: VariantType.REALISTIC,
            VisualStyle.WHIMSICAL: VariantType.ARTISTIC,
        }
        base_variant_type = style_to_variant.get(
            preferred_style, VariantType.CINEMATIC
        )

        if base_variant_type == VariantType.CINEMATIC:
            base_variant = self._generate_cinematic_variant(prompt, style_analysis)
        elif base_variant_type == VariantType.COOL_EDGY:
            base_variant = self._generate_cool_edgy_variant(prompt, style_analysis)
        elif base_variant_type == VariantType.ARTISTIC:
            base_variant = self._generate_artistic_variant(prompt, style_analysis)
        else:
            base_variant = self._generate_realistic_variant(prompt, style_analysis)

        new_scores = replace(
            base_variant.scores,
            wow_factor=min(10.0, base_variant.scores.wow_factor + 0.5),
        )
        personalized_variant = replace(
            base_variant,
            variant_type=VariantType.PERSONALIZED,
            is_personalized=True,
            scores=new_scores,
        )
        logger.info(
            "Personalized variant generated",
            user_id=user_id,
            based_on=base_variant_type.value,
            surprise_level=preferred_surprise.value,
        )
        return personalized_variant

    def _generate_surprise_element(
        self,
        prompt: str,
        intensity: float,
    ) -> Optional[str]:
        if intensity < 0.1:
            return None
        low_surprises = [
            "with subtle ethereal glow emanating from edges",
            "soft bioluminescent accents in shadows",
            "gentle floating particles dancing in air",
            "hint of ancient mystical energy",
        ]
        medium_surprises = [
            "with translucent spirit guardian watching from shadows",
            "ancient floating crystal formations orbiting",
            "mysterious glowing runes appearing on surfaces",
            "ethereal energy ribbons flowing through scene",
            "hidden portal revealing parallel dimension",
        ]
        high_surprises = [
            "impossible floating inverted architecture defying gravity",
            "reality tears revealing cosmic void beyond",
            "multiple timelines coexisting in same space",
            "sentient light beings observing from higher dimension",
            "paradoxical infinite recursion of scene within itself",
            "quantum superposition of multiple states simultaneously",
        ]
        if intensity < 0.4:
            return random.choice(low_surprises)
        if intensity < 0.7:
            return random.choice(medium_surprises)
        surprises = random.sample(high_surprises, min(2, len(high_surprises)))
        return ", ".join(surprises)

    def _build_negative_for_variant(self, variant_type: VariantType) -> str:
        base_negative = [
            "low quality", "worst quality", "blurry", "out of focus",
            "bad anatomy", "deformed", "disfigured",
            "jpeg artifacts", "watermark", "text", "signature",
        ]
        variant_negatives = {
            VariantType.REALISTIC: [
                "artistic", "painterly", "stylized", "cartoon", "anime",
                "fantasy", "surreal", "impossible", "unrealistic",
                "dramatic lighting", "cinematic", "theatrical",
            ],
            VariantType.CINEMATIC: [
                "flat lighting", "amateur", "snapshot", "boring",
                "low production value", "simple", "plain",
            ],
            VariantType.COOL_EDGY: [
                "bright", "cheerful", "warm colors", "soft lighting",
                "cute", "whimsical", "pastel",
            ],
            VariantType.ARTISTIC: [
                "photorealistic", "photograph", "realistic",
                "technical", "literal", "mundane",
            ],
            VariantType.MAX_SURPRISE: [
                "normal", "conventional", "realistic", "typical",
                "boring", "predictable", "straightforward",
            ],
            VariantType.PERSONALIZED: [],
        }
        negatives = base_negative + variant_negatives.get(variant_type, [])
        return ", ".join(negatives)


def format_variant_display(variant: PromptVariant, index: int) -> str:
    """Format variant for display to user."""
    tags = []
    if variant.is_recommended:
        tags.append("⭐ RECOMMENDED")
    if variant.is_personalized:
        tags.append("👤 PERSONALIZED FOR YOU")
    tag_str = " ".join(tags)
    scores_str = (
        f"📊 Scores:\n"
        f"  Detail: {variant.scores.detail_score}/10\n"
        f"  Cinematic: {variant.scores.cinematic_fit}/10\n"
        f"  Surprise: {variant.scores.surprise_factor}/10\n"
        f"  Wow Factor: {variant.scores.wow_factor}/10\n"
        f"  Overall: {variant.scores.overall_score():.1f}/10"
    )
    mj = variant.model_params
    weird = mj.get("weird", 0)
    stylize = mj.get("stylize", 0)
    chaos = mj.get("chaos", 0)
    return f"""
{"=" * 60}
Variant {index + 1}: {variant.variant_type.value.upper()} {tag_str}
{"=" * 60}

{variant.enhanced_prompt}

{scores_str}

🔧 Midjourney Parameters:
  --stylize {stylize}
  --chaos {chaos}
  --weird {weird}

💡 Remix Suggestions:
{chr(10).join("  • " + s for s in variant.remix_suggestions)}
"""
