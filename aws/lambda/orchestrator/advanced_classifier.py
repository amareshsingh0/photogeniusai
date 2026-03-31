"""
Advanced Style Classifier – ML-powered style classification for personalization.

Detects:
- Visual style (cinematic, cool_edgy, artistic, realistic, whimsical)
- Surprise level (safe, moderate, high)
- Lighting style (dramatic, soft, natural, moody, golden, neon)
- Emotional tone (serene, intense, mysterious, joyful, melancholic, epic)

Used by variant generation and prompt enhancement. Complements DomainClassifier
in universal_prompt_enhancer (domain: image/math/writing/code).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple

from services.observability import StructuredLogger, trace_function

logger = StructuredLogger(__name__)

# Optional ML dependencies (rule-based works without them)
try:
    import numpy as np  # type: ignore[reportMissingImports]
except ImportError:
    np = None  # type: ignore[assignment]

try:
    from sklearn.feature_extraction.text import TfidfVectorizer  # type: ignore[reportMissingImports]

    _SKLEARN_AVAILABLE = True
except ImportError:
    TfidfVectorizer = None  # type: ignore[assignment, misc]
    _SKLEARN_AVAILABLE = False


class VisualStyle(str, Enum):
    """Visual style preferences."""

    CINEMATIC = "cinematic"
    COOL_EDGY = "cool_edgy"
    ARTISTIC = "artistic"
    REALISTIC = "realistic"
    WHIMSICAL = "whimsical"


class SurpriseLevel(str, Enum):
    """How much surprise/wow user wants."""

    SAFE = "safe"  # 0-0.3: Minimal surprise
    MODERATE = "moderate"  # 0.4-0.7: Balanced
    HIGH = "high"  # 0.8-1.0: Maximum chaos


class LightingStyle(str, Enum):
    """Lighting preference."""

    DRAMATIC = "dramatic"
    SOFT = "soft"
    NATURAL = "natural"
    MOODY = "moody"
    GOLDEN = "golden"
    NEON = "neon"


class EmotionalTone(str, Enum):
    """Emotional tone."""

    SERENE = "serene"
    INTENSE = "intense"
    MYSTERIOUS = "mysterious"
    JOYFUL = "joyful"
    MELANCHOLIC = "melancholic"
    EPIC = "epic"


@dataclass
class StyleAnalysis:
    """Complete style analysis result."""

    visual_style: VisualStyle
    surprise_level: SurpriseLevel
    lighting_style: LightingStyle
    emotional_tone: EmotionalTone

    style_confidence: float
    surprise_confidence: float
    lighting_confidence: float
    emotion_confidence: float

    detected_signals: Dict[str, List[str]]


class AdvancedStyleClassifier:
    """ML-powered style classifier for personalization."""

    STYLE_KEYWORDS = {
        VisualStyle.CINEMATIC: {
            "strong": [
                "cinematic",
                "epic",
                "dramatic",
                "movie",
                "film",
                "volumetric",
                "god rays",
                "rim light",
                "anamorphic",
                "blockbuster",
                "theatrical",
                "larger than life",
            ],
            "moderate": [
                "professional",
                "high quality",
                "stunning",
                "breathtaking",
                "majestic",
                "grand",
                "powerful",
                "intense",
            ],
            "negative": ["simple", "basic", "minimal", "clean", "everyday"],
        },
        VisualStyle.COOL_EDGY: {
            "strong": [
                "cyberpunk",
                "neon",
                "dark",
                "edgy",
                "gritty",
                "noir",
                "urban",
                "street",
                "underground",
                "dystopian",
                "tech",
                "futuristic",
                "blade runner",
                "rain",
                "night",
            ],
            "moderate": [
                "cool",
                "modern",
                "sleek",
                "mysterious",
                "shadows",
                "contrast",
                "moody",
                "atmospheric",
            ],
            "negative": ["bright", "cheerful", "warm", "cozy", "soft"],
        },
        VisualStyle.ARTISTIC: {
            "strong": [
                "artistic",
                "painterly",
                "impressionist",
                "surreal",
                "abstract",
                "expressive",
                "stylized",
                "illustrative",
                "studio ghibli",
                "anime",
                "art nouveau",
                "watercolor",
            ],
            "moderate": [
                "creative",
                "imaginative",
                "dreamlike",
                "whimsical",
                "fantastical",
                "ethereal",
                "magical",
            ],
            "negative": ["realistic", "photorealistic", "photo", "photograph"],
        },
        VisualStyle.REALISTIC: {
            "strong": [
                "photorealistic",
                "realistic",
                "photograph",
                "photo",
                "dslr",
                "camera",
                "lens",
                "natural",
                "authentic",
                "lifelike",
                "true to life",
                "documentary",
            ],
            "moderate": [
                "real",
                "actual",
                "genuine",
                "everyday",
                "normal",
                "candid",
                "unposed",
            ],
            "negative": ["fantasy", "surreal", "impossible", "magical", "artistic"],
        },
        VisualStyle.WHIMSICAL: {
            "strong": [
                "whimsical",
                "playful",
                "cute",
                "kawaii",
                "colorful",
                "bright",
                "cheerful",
                "fantastical",
                "storybook",
                "fairytale",
            ],
            "moderate": [
                "imaginative",
                "creative",
                "fun",
                "lighthearted",
                "charming",
                "delightful",
            ],
            "negative": ["dark", "serious", "gritty", "realistic", "somber"],
        },
    }

    SURPRISE_KEYWORDS = {
        SurpriseLevel.HIGH: [
            "impossible",
            "surreal",
            "bizarre",
            "weird",
            "chaotic",
            "unexpected",
            "twist",
            "surprising",
            "mind-bending",
            "otherworldly",
            "alien",
            "mystical",
            "supernatural",
            "hidden dimensions",
            "secret",
            "mysterious element",
            "paradox",
            "defying",
            "transcendent",
        ],
        SurpriseLevel.MODERATE: [
            "interesting",
            "unique",
            "unusual",
            "special",
            "magical",
            "fantasy",
            "enchanted",
            "mystical",
            "subtle twist",
            "hint of mystery",
        ],
        SurpriseLevel.SAFE: [
            "normal",
            "everyday",
            "realistic",
            "typical",
            "standard",
            "conventional",
            "traditional",
            "straightforward",
            "literal",
            "simple",
        ],
    }

    LIGHTING_KEYWORDS = {
        LightingStyle.DRAMATIC: [
            "dramatic",
            "high contrast",
            "chiaroscuro",
            "strong shadows",
            "rim light",
            "side light",
            "intense",
            "bold",
        ],
        LightingStyle.SOFT: [
            "soft",
            "diffused",
            "gentle",
            "subtle",
            "delicate",
            "studio",
            "portrait",
            "even lighting",
        ],
        LightingStyle.NATURAL: [
            "natural",
            "window light",
            "daylight",
            "ambient",
            "outdoor",
            "sun",
            "overcast",
        ],
        LightingStyle.MOODY: [
            "moody",
            "dark",
            "low key",
            "atmospheric",
            "noir",
            "shadows",
            "mysterious lighting",
        ],
        LightingStyle.GOLDEN: [
            "golden hour",
            "sunset",
            "sunrise",
            "warm",
            "golden",
            "amber",
            "orange glow",
        ],
        LightingStyle.NEON: [
            "neon",
            "fluorescent",
            "led",
            "glow",
            "luminous",
            "electric",
            "cyberpunk lighting",
        ],
    }

    EMOTION_KEYWORDS = {
        EmotionalTone.SERENE: [
            "serene",
            "peaceful",
            "calm",
            "tranquil",
            "quiet",
            "gentle",
            "relaxed",
            "zen",
        ],
        EmotionalTone.INTENSE: [
            "intense",
            "powerful",
            "dramatic",
            "forceful",
            "passionate",
            "fierce",
            "strong",
        ],
        EmotionalTone.MYSTERIOUS: [
            "mysterious",
            "enigmatic",
            "secretive",
            "cryptic",
            "hidden",
            "veiled",
            "unknown",
        ],
        EmotionalTone.JOYFUL: [
            "joyful",
            "happy",
            "cheerful",
            "delightful",
            "bright",
            "uplifting",
            "positive",
        ],
        EmotionalTone.MELANCHOLIC: [
            "melancholic",
            "sad",
            "wistful",
            "nostalgic",
            "contemplative",
            "introspective",
            "bittersweet",
        ],
        EmotionalTone.EPIC: [
            "epic",
            "heroic",
            "grand",
            "majestic",
            "legendary",
            "monumental",
            "awe-inspiring",
        ],
    }

    def __init__(self, use_ml: bool = True) -> None:
        """
        Initialize advanced classifier.

        Args:
            use_ml: Use ML-based semantic similarity (requires sklearn; slower but extensible).
        """
        self.use_ml = use_ml and _SKLEARN_AVAILABLE
        self.vectorizer = None

        if self.use_ml and TfidfVectorizer is not None:
            all_keywords: List[str] = []
            for style_dict in (
                self.STYLE_KEYWORDS,
                self.SURPRISE_KEYWORDS,
                self.LIGHTING_KEYWORDS,
                self.EMOTION_KEYWORDS,
            ):
                for category_dict in style_dict.values():
                    if isinstance(category_dict, dict):
                        for keyword_list in category_dict.values():
                            all_keywords.extend(keyword_list)
                    else:
                        all_keywords.extend(category_dict)

            if all_keywords:
                try:
                    self.vectorizer = TfidfVectorizer(
                        max_features=500,
                        ngram_range=(1, 2),
                        strip_accents="unicode",
                    )
                    self.vectorizer.fit(all_keywords)
                    logger.info("AdvancedStyleClassifier: ML (TF-IDF) initialized")
                except Exception as e:
                    logger.warning("AdvancedStyleClassifier: ML init failed, using rules only: %s", e)  # type: ignore[reportCallIssue]
                    self.use_ml = False
            else:
                self.use_ml = False
        if not self.use_ml:
            logger.info("AdvancedStyleClassifier: rule-based only")

    @trace_function("advanced.classify_style")  # type: ignore[misc]
    def classify(self, prompt: str) -> StyleAnalysis:
        """
        Perform complete style analysis.

        Args:
            prompt: User prompt.

        Returns:
            StyleAnalysis with all detected preferences.
        """
        prompt_lower = (prompt or "").strip().lower()
        detected_signals: Dict[str, List[str]] = {}

        visual_style, style_conf, style_signals = self._classify_visual_style(
            prompt_lower
        )
        detected_signals["visual_style"] = style_signals

        surprise_level, surprise_conf, surprise_signals = self._classify_surprise(
            prompt_lower
        )
        detected_signals["surprise"] = surprise_signals

        lighting, lighting_conf, lighting_signals = self._classify_lighting(
            prompt_lower
        )
        detected_signals["lighting"] = lighting_signals

        emotion, emotion_conf, emotion_signals = self._classify_emotion(prompt_lower)
        detected_signals["emotion"] = emotion_signals

        result = StyleAnalysis(
            visual_style=visual_style,
            surprise_level=surprise_level,
            lighting_style=lighting,
            emotional_tone=emotion,
            style_confidence=style_conf,
            surprise_confidence=surprise_conf,
            lighting_confidence=lighting_conf,
            emotion_confidence=emotion_conf,
            detected_signals=detected_signals,
        )

        avg_conf = (style_conf + surprise_conf + lighting_conf + emotion_conf) / 4.0
        logger.info(
            "Style analysis complete",
            visual_style=visual_style.value,
            surprise=surprise_level.value,
            lighting=lighting.value,
            emotion=emotion.value,
            avg_confidence=round(avg_conf, 2),
        )
        return result

    def _classify_visual_style(
        self, prompt: str
    ) -> Tuple[VisualStyle, float, List[str]]:
        """Classify visual style preference."""
        scores: Dict[VisualStyle, float] = {}
        all_matches: Dict[VisualStyle, List[str]] = {}

        for style, keyword_dict in self.STYLE_KEYWORDS.items():
            score = 0.0
            matches: List[str] = []

            for kw in keyword_dict["strong"]:
                if kw in prompt:
                    score += 3
                    matches.append(f"strong:{kw}")

            for kw in keyword_dict["moderate"]:
                if kw in prompt:
                    score += 1
                    matches.append(f"moderate:{kw}")

            for kw in keyword_dict["negative"]:
                if kw in prompt:
                    score -= 2
                    matches.append(f"negative:{kw}")

            scores[style] = score
            all_matches[style] = matches

        if scores:
            best_style = max(scores.items(), key=lambda x: x[1])
            style = best_style[0]
            score_val = best_style[1]

            if score_val <= 0:
                style = VisualStyle.CINEMATIC
                confidence = 0.5
            else:
                max_possible = 10.0
                confidence = min(1.0, score_val / max_possible)

            return style, confidence, all_matches[style]

        return VisualStyle.CINEMATIC, 0.5, []

    def _classify_surprise(self, prompt: str) -> Tuple[SurpriseLevel, float, List[str]]:
        """Classify surprise level preference."""
        scores = {level: 0 for level in SurpriseLevel}
        matches: Dict[SurpriseLevel, List[str]] = {level: [] for level in SurpriseLevel}

        for level, keywords in self.SURPRISE_KEYWORDS.items():
            for kw in keywords:
                if kw in prompt:
                    scores[level] += 1
                    matches[level].append(kw)

        if any(scores.values()):
            best_level = max(scores.items(), key=lambda x: x[1])
            level = best_level[0]
            score_val = best_level[1]
            confidence = min(1.0, score_val / 3.0)
            return level, confidence, matches[level]

        return SurpriseLevel.MODERATE, 0.6, []

    def _classify_lighting(self, prompt: str) -> Tuple[LightingStyle, float, List[str]]:
        """Classify lighting preference."""
        scores: Dict[LightingStyle, int] = {}
        match_lists: Dict[LightingStyle, List[str]] = {}

        for lighting, keywords in self.LIGHTING_KEYWORDS.items():
            matched = [kw for kw in keywords if kw in prompt]
            scores[lighting] = len(matched)
            match_lists[lighting] = matched

        if any(scores.values()):
            best = max(scores.items(), key=lambda x: x[1])
            lighting = best[0]
            score_val = best[1]
            confidence = min(1.0, score_val / 2.0)
            return lighting, confidence, match_lists[lighting]

        return LightingStyle.GOLDEN, 0.5, []

    def _classify_emotion(self, prompt: str) -> Tuple[EmotionalTone, float, List[str]]:
        """Classify emotional tone."""
        scores: Dict[EmotionalTone, int] = {}
        match_lists: Dict[EmotionalTone, List[str]] = {}

        for emotion, keywords in self.EMOTION_KEYWORDS.items():
            matched = [kw for kw in keywords if kw in prompt]
            scores[emotion] = len(matched)
            match_lists[emotion] = matched

        if any(scores.values()):
            best = max(scores.items(), key=lambda x: x[1])
            emotion = best[0]
            score_val = best[1]
            confidence = min(1.0, score_val / 2.0)
            return emotion, confidence, match_lists[emotion]

        return EmotionalTone.SERENE, 0.5, []


# ==================== CONVENIENCE ====================

_default_classifier: Optional[AdvancedStyleClassifier] = None


def get_default_style_classifier() -> AdvancedStyleClassifier:
    """Get or create default AdvancedStyleClassifier (rule-based)."""
    global _default_classifier
    if _default_classifier is None:
        _default_classifier = AdvancedStyleClassifier(use_ml=False)
    return _default_classifier


def quick_style_analysis(prompt: str) -> StyleAnalysis:
    """Quick style analysis using rule-based classifier."""
    classifier = AdvancedStyleClassifier(use_ml=False)
    return classifier.classify(prompt)


# ==================== TESTS ====================

if __name__ == "__main__":
    test_prompts = [
        (
            "cinematic epic warrior with dramatic lighting",
            "CINEMATIC + DRAMATIC + INTENSE",
        ),
        ("cute girl in soft pastel forest", "WHIMSICAL + SOFT + SERENE"),
        ("neon cyberpunk street at night with rain", "COOL_EDGY + NEON + MYSTERIOUS"),
        (
            "photorealistic portrait with natural lighting",
            "REALISTIC + NATURAL + SERENE",
        ),
        (
            "surreal impossible floating castle with mystical elements",
            "ARTISTIC + HIGH_SURPRISE + MYSTERIOUS",
        ),
    ]

    classifier = AdvancedStyleClassifier(use_ml=False)

    for prompt, expected in test_prompts:
        result = classifier.classify(prompt)
        print("\n" + "=" * 60)
        print("PROMPT:", prompt)
        print("EXPECTED:", expected)
        print("\nRESULT:")
        print(
            "  Visual Style:",
            result.visual_style.value,
            "(conf: %.2f)" % result.style_confidence,
        )
        print(
            "  Surprise:",
            result.surprise_level.value,
            "(conf: %.2f)" % result.surprise_confidence,
        )
        print(
            "  Lighting:",
            result.lighting_style.value,
            "(conf: %.2f)" % result.lighting_confidence,
        )
        print(
            "  Emotion:",
            result.emotional_tone.value,
            "(conf: %.2f)" % result.emotion_confidence,
        )
        print("\nDetected Signals:")
        for category, signals in result.detected_signals.items():
            if signals:
                print("  %s: %s" % (category, signals[:3]))
