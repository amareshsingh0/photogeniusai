"""
Advanced Prompt Builder for PhotoGenius AI
Provides templates, enhancement, and optimization for image generation prompts.
"""

import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import logging
import random

logger = logging.getLogger(__name__)


class PromptStyle(Enum):
    """Prompt style categories"""

    PROFESSIONAL = "professional"
    ARTISTIC = "artistic"
    CINEMATIC = "cinematic"
    PORTRAIT = "portrait"
    FASHION = "fashion"
    FANTASY = "fantasy"
    CYBERPUNK = "cyberpunk"
    VINTAGE = "vintage"


@dataclass
class PromptBuildResult:
    """Result of prompt building"""

    enhanced_prompt: str
    negative_prompt: str
    original_prompt: str
    enhancements_applied: List[str]
    estimated_tokens: int
    metadata: Dict


class PromptBuilder:
    """
    Advanced prompt builder with templates and optimization

    Features:
    - Automatic enhancement
    - Quality boosters
    - Negative prompt generation
    - Token optimization
    - Style templates
    - A/B testing support
    - Multi-language support (placeholder)
    """

    # ==================== QUALITY BOOSTERS ====================
    QUALITY_BOOSTERS = {
        "REALISM": [
            "professional photography",
            "high quality",
            "sharp focus",
            "8k uhd",
            "dslr",
            "soft lighting",
            "film grain",
            "Fujifilm XT3",
        ],
        "CREATIVE": [
            "trending on artstation",
            "award winning",
            "masterpiece",
            "highly detailed",
            "professional digital art",
            "concept art",
            "vibrant colors",
        ],
        "ROMANTIC": [
            "romantic atmosphere",
            "warm lighting",
            "dreamy",
            "elegant",
            "tasteful",
            "cinematic",
            "soft focus",
            "golden hour",
        ],
    }

    # ==================== TECHNICAL BOOSTERS ====================
    TECHNICAL_BOOSTERS = {
        "REALISM": [
            "ray tracing",
            "perfect composition",
            "highly detailed",
            "photorealistic",
            "studio lighting",
        ],
        "CREATIVE": [
            "perfect lighting",
            "detailed textures",
            "atmospheric",
            "volumetric lighting",
        ],
        "ROMANTIC": [
            "soft bokeh",
            "shallow depth of field",
            "natural lighting",
            "intimate mood",
        ],
    }

    # ==================== NEGATIVE PROMPTS ====================
    BASE_NEGATIVE = [
        "blurry",
        "low quality",
        "jpeg artifacts",
        "watermark",
        "username",
        "signature",
        "text",
        "lowres",
        "bad quality",
    ]

    PORTRAIT_NEGATIVE = [
        "bad anatomy",
        "bad proportions",
        "deformed",
        "disfigured",
        "extra limbs",
        "extra fingers",
        "mutated hands",
        "poorly drawn hands",
        "poorly drawn face",
        "mutation",
        "ugly",
        "duplicate",
        "duplicate object",
        "extra ball",
        "floating duplicate",
        "morbid",
        "mutilated",
        "extra arms",
        "extra legs",
        "missing arms",
        "missing legs",
        "missing hands",
        "amputated",
        "hand cut off",
        "invisible hand",
        "phantom limb",
        "hand absorbed",
        "fused fingers",
        "too many fingers",
        "long neck",
        "cross-eye",
        "body out of frame",
    ]

    # Head/count/multi-person: prevent missing head, extra limbs, merged bodies
    HEAD_AND_COUNT_NEGATIVE = [
        "missing head",
        "headless",
        "head cut off",
        "no face",
        "extra head",
        "two heads",
        "merged bodies",
        "merged figures",
        "extra arm",
        "arm from back",
        "third arm",
        "head absorbed by umbrella",
        "face cut off by object",
        "impossible pose",
        "impossible physics",
        "body merging",
        "jumbled figures",
    ]
    MULTI_PERSON_NEGATIVE = [
        "wrong number of people",
        "wrong depth order",
        "six fingers",
        "seven fingers",
        "claw hands",
    ]
    ANATOMY_POSITIVE_BOOSTERS = [
        "correct anatomy",
        "both hands visible",
        "natural limbs",
        "complete body",
        "no missing body parts",
        "five fingers each hand",
        "anatomically correct",
    ]
    MULTI_PERSON_POSITIVE_BOOSTERS = [
        "each person complete",
        "every figure has visible head",
        "every figure has two hands only",
        "correct number of people",
        "natural grouping",
        "logical placement",
        "no merged bodies",
        "one head per person",
        "two arms per person",
        "coherent multi-figure composition",
    ]

    REALISTIC_NEGATIVE = [
        "cartoon",
        "3d",
        "anime",
        "illustration",
        "painting",
        "drawing",
        "art",
        "sketch",
    ]

    # ==================== STYLE TEMPLATES ====================
    STYLE_TEMPLATES = {
        PromptStyle.PROFESSIONAL: {
            "prefix": "professional {subject}",
            "suffix": "business attire, confident pose, neutral background",
            "quality": "corporate photography, studio lighting, high resolution",
        },
        PromptStyle.ARTISTIC: {
            "prefix": "{subject} in artistic style",
            "suffix": "creative composition, expressive",
            "quality": "fine art photography, creative lighting, artistic interpretation",
        },
        PromptStyle.CINEMATIC: {
            "prefix": "cinematic shot of {subject}",
            "suffix": "dramatic lighting, movie scene",
            "quality": "film grain, anamorphic lens, cinematic color grading, depth of field",
        },
        PromptStyle.PORTRAIT: {
            "prefix": "portrait of {subject}",
            "suffix": "eye contact, natural expression",
            "quality": "portrait photography, 85mm lens, f/1.8, professional lighting",
        },
        PromptStyle.FASHION: {
            "prefix": "fashion photography of {subject}",
            "suffix": "stylish outfit, trendy pose",
            "quality": "vogue magazine, high fashion, professional lighting, editorial",
        },
        PromptStyle.FANTASY: {
            "prefix": "{subject} in fantasy setting",
            "suffix": "magical atmosphere, ethereal",
            "quality": "fantasy art, magical lighting, highly detailed, mystical",
        },
        PromptStyle.CYBERPUNK: {
            "prefix": "{subject} in cyberpunk style",
            "suffix": "neon lights, futuristic city",
            "quality": "cyberpunk aesthetic, neon glow, sci-fi, detailed technology",
        },
        PromptStyle.VINTAGE: {
            "prefix": "vintage photograph of {subject}",
            "suffix": "retro style, nostalgic",
            "quality": "vintage photography, film grain, classic composition, aged photo",
        },
    }

    # ==================== POSE TEMPLATES ====================
    POSE_TEMPLATES = {
        "headshot": "head and shoulders, facing camera",
        "portrait": "upper body, three-quarter angle",
        "full_body": "full body shot, standing pose",
        "candid": "natural candid moment, relaxed pose",
        "action": "dynamic action pose, movement",
        "sitting": "sitting pose, relaxed posture",
    }

    def __init__(self):
        """Initialize prompt builder"""
        self.stats = {
            "total_builds": 0,
            "avg_enhancement_count": 0,
        }

    def build_prompt(
        self,
        user_prompt: str,
        mode: str,
        style: Optional[PromptStyle] = None,
        pose: Optional[str] = None,
        enhancement_level: float = 1.0,
        add_quality_boosters: bool = True,
        add_technical_boosters: bool = True,
    ) -> PromptBuildResult:
        """
        Build enhanced prompt from user input

        Args:
            user_prompt: User's original prompt
            mode: Generation mode (REALISM, CREATIVE, ROMANTIC)
            style: Optional style template
            pose: Optional pose template
            enhancement_level: 0.0-1.0, how much to enhance
            add_quality_boosters: Add quality keywords
            add_technical_boosters: Add technical keywords

        Returns:
            PromptBuildResult with enhanced prompts
        """
        self.stats["total_builds"] += 1

        enhancements_applied = []
        enhanced = user_prompt.strip()

        # 1. Apply style template if specified
        if style:
            template = self.STYLE_TEMPLATES.get(style)
            if template:
                # Extract subject from user prompt
                subject = self._extract_subject(user_prompt)

                # Apply template
                prefix = template["prefix"].format(subject=subject)
                suffix = template["suffix"]
                quality = template["quality"]

                enhanced = f"{prefix}, {enhanced}, {suffix}, {quality}"
                enhancements_applied.append(f"style:{style.value}")

        # 2. Add pose if specified
        if pose and pose in self.POSE_TEMPLATES:
            pose_desc = self.POSE_TEMPLATES[pose]
            enhanced = f"{enhanced}, {pose_desc}"
            enhancements_applied.append(f"pose:{pose}")

        # 3. Add quality boosters
        if add_quality_boosters and enhancement_level >= 0.5:
            boosters = self.QUALITY_BOOSTERS.get(mode.upper(), [])
            if boosters:
                num_boosters = max(1, int(len(boosters) * enhancement_level))
                selected_boosters = random.sample(boosters, min(num_boosters, 4))

                enhanced = f"{enhanced}, {', '.join(selected_boosters)}"
                enhancements_applied.append("quality_boosters")

        # 4. Add technical boosters
        if add_technical_boosters and enhancement_level >= 0.7:
            boosters = self.TECHNICAL_BOOSTERS.get(mode.upper(), [])
            if boosters:
                num_boosters = max(1, int(len(boosters) * enhancement_level))
                selected_boosters = random.sample(boosters, min(num_boosters, 3))

                enhanced = f"{enhanced}, {', '.join(selected_boosters)}"
                enhancements_applied.append("technical_boosters")

        # 4b. Anatomy and multi-person boosters (prevent missing head, extra limbs, merged bodies)
        prompt_lower = user_prompt.lower()
        multi_person_markers = [
            "multiple",
            "group",
            "family",
            "children",
            "crowd",
            "together",
            "several",
            "two people",
            "three people",
            "four people",
            "rain",
            "umbrella",
            "street",
            "walking together",
            "with children",
            "family walking",
            "group of",
        ]
        person_body_markers = [
            "person",
            "man",
            "woman",
            "child",
            "people",
            "figure",
            "body",
            "holding",
            "arms",
            "hands",
            "portrait",
            "player",
            "athlete",
            "model",
        ]
        has_multi = any(m in prompt_lower for m in multi_person_markers)
        has_person = any(m in prompt_lower for m in person_body_markers)
        if has_multi and self.MULTI_PERSON_POSITIVE_BOOSTERS:
            num_add = min(6, len(self.MULTI_PERSON_POSITIVE_BOOSTERS))
            selected = random.sample(self.MULTI_PERSON_POSITIVE_BOOSTERS, num_add)
            enhanced = f"{enhanced}, {', '.join(selected)}"
            enhancements_applied.append("multi_person_boosters")
        if has_person and self.ANATOMY_POSITIVE_BOOSTERS:
            num_add = min(4, len(self.ANATOMY_POSITIVE_BOOSTERS))
            selected = random.sample(self.ANATOMY_POSITIVE_BOOSTERS, num_add)
            enhanced = f"{enhanced}, {', '.join(selected)}"
            enhancements_applied.append("anatomy_boosters")

        # 5. Clean up prompt
        enhanced = self._clean_prompt(enhanced)

        # 6. Generate negative prompt (with anatomy/multi-person when detected)
        negative = self._build_negative_prompt(mode, style, user_prompt=user_prompt)

        # 7. Estimate tokens
        estimated_tokens = len(enhanced.split())

        # Update statistics (store as float for average)
        prev_avg = float(self.stats["avg_enhancement_count"])
        n = self.stats["total_builds"]
        self.stats["avg_enhancement_count"] = (prev_avg * (n - 1) + len(enhancements_applied)) / n  # type: ignore[reportArgumentType]

        return PromptBuildResult(
            enhanced_prompt=enhanced,
            negative_prompt=negative,
            original_prompt=user_prompt,
            enhancements_applied=enhancements_applied,
            estimated_tokens=estimated_tokens,
            metadata={
                "mode": mode,
                "style": style.value if style else None,
                "pose": pose,
                "enhancement_level": enhancement_level,
            },
        )

    def _extract_subject(self, prompt: str) -> str:
        """
        Extract subject from prompt

        Simple heuristic: look for person descriptors
        """
        # Common subject patterns
        patterns = [
            r"(man|woman|person|boy|girl|businessman|professional|model|individual)",
            r"(\w+\s+(?:man|woman|person))",
        ]

        for pattern in patterns:
            match = re.search(pattern, prompt, re.IGNORECASE)
            if match:
                return match.group(0)

        # Default
        return "person"

    def _clean_prompt(self, prompt: str) -> str:
        """
        Clean and optimize prompt

        - Remove duplicates
        - Fix punctuation
        - Optimize token usage
        """
        # Split into parts
        parts = [p.strip() for p in prompt.split(",")]

        # Remove duplicates (case-insensitive)
        seen = set()
        unique_parts = []
        for part in parts:
            lower_part = part.lower()
            if lower_part not in seen and part:
                seen.add(lower_part)
                unique_parts.append(part)

        # Rejoin
        cleaned = ", ".join(unique_parts)

        # Fix multiple spaces
        cleaned = re.sub(r"\s+", " ", cleaned)

        # Remove trailing comma
        cleaned = cleaned.rstrip(", ")

        return cleaned

    def _build_negative_prompt(
        self,
        mode: str,
        style: Optional[PromptStyle] = None,
        *,
        user_prompt: Optional[str] = None,
    ) -> str:
        """
        Build comprehensive negative prompt.

        When user_prompt is provided, detects person/multi-person and adds
        anatomy/head/limb/count negatives to avoid missing head, extra limbs, merged bodies.
        """
        negative_parts = []

        # 1. Base negatives (always include)
        negative_parts.extend(self.BASE_NEGATIVE)

        # 2. Portrait negatives (for most modes)
        if mode in ["REALISM", "ROMANTIC"] or style == PromptStyle.PORTRAIT:
            negative_parts.extend(self.PORTRAIT_NEGATIVE)

        # 3. Realistic negatives (for realism mode)
        if mode == "REALISM":
            negative_parts.extend(self.REALISTIC_NEGATIVE)

        # 4. Mode-specific additions
        if mode == "ROMANTIC":
            negative_parts.extend(
                [
                    "explicit",
                    "nsfw",
                    "vulgar",
                    "inappropriate",
                ]
            )

        # 5. Anatomy/head/limb/multi-person negatives when prompt has people
        if user_prompt:
            prompt_lower = user_prompt.lower()
            multi_markers = [
                "multiple",
                "group",
                "family",
                "children",
                "crowd",
                "together",
                "several",
                "two people",
                "three people",
                "four people",
                "rain",
                "umbrella",
                "street",
                "walking together",
                "with children",
                "group of",
            ]
            person_markers = [
                "person",
                "man",
                "woman",
                "child",
                "people",
                "figure",
                "body",
                "holding",
                "arms",
                "hands",
                "portrait",
                "player",
                "athlete",
                "model",
            ]
            has_multi = any(m in prompt_lower for m in multi_markers)
            has_person = any(m in prompt_lower for m in person_markers)
            if has_person:
                negative_parts.extend(self.HEAD_AND_COUNT_NEGATIVE)
            if has_multi:
                negative_parts.extend(self.HEAD_AND_COUNT_NEGATIVE)
                negative_parts.extend(self.MULTI_PERSON_NEGATIVE)

        # 6. Remove duplicates
        negative_parts = list(dict.fromkeys(negative_parts))

        return ", ".join(negative_parts)

    def optimize_for_tokens(self, prompt: str, max_tokens: int = 77) -> str:
        """
        Optimize prompt to fit within token limit

        Args:
            prompt: Original prompt
            max_tokens: Maximum tokens (CLIP limit is 77)

        Returns:
            Optimized prompt
        """
        # Rough estimation: 1 token ≈ 0.75 words
        max_words = int(max_tokens * 0.75)

        words = prompt.split()

        if len(words) <= max_words:
            return prompt

        # Prioritize keeping:
        # 1. Subject
        # 2. Important modifiers
        # 3. Quality descriptors

        # Simple truncation for now
        truncated = " ".join(words[:max_words])

        logger.warning(f"Prompt truncated from {len(words)} to {max_words} words")

        return truncated

    def add_emphasis(self, prompt: str, keywords: List[str], strength: float = 1.2) -> str:
        """
        Add emphasis to specific keywords

        Uses (keyword:strength) syntax

        Args:
            prompt: Original prompt
            keywords: Keywords to emphasize
            strength: Emphasis strength (1.0-2.0)

        Returns:
            Prompt with emphasis
        """
        for keyword in keywords:
            if keyword in prompt:
                emphasized = f"({keyword}:{strength})"
                prompt = prompt.replace(keyword, emphasized)

        return prompt

    def generate_variations(self, base_prompt: str, num_variations: int = 3) -> List[str]:
        """
        Generate prompt variations for A/B testing

        Args:
            base_prompt: Base prompt
            num_variations: Number of variations

        Returns:
            List of prompt variations
        """
        variations = [base_prompt]

        for i in range(num_variations - 1):
            # Vary by shuffling quality boosters
            varied = base_prompt

            # Add random quality booster
            boosters_list = self.QUALITY_BOOSTERS.get("REALISM", [])
            if boosters_list:
                num_boosters = min(2, len(boosters_list))
                selected_boosters = random.sample(boosters_list, k=num_boosters)
                varied = f"{varied}, {', '.join(selected_boosters)}"

            variations.append(varied)

        return variations

    def translate_to_english(self, prompt: str, source_lang: str) -> str:
        """
        Translate prompt to English (placeholder)

        In production, integrate with translation API (Google Translate, DeepL, etc.)

        Args:
            prompt: Original prompt in source language
            source_lang: Source language code (e.g., 'hi', 'es', 'fr')

        Returns:
            Translated prompt (currently returns original as placeholder)
        """
        # TODO: Integrate with Google Translate API or similar
        # Example:
        # from googletrans import Translator
        # translator = Translator()
        # result = translator.translate(prompt, src=source_lang, dest='en')
        # return result.text

        logger.info(f"Translation requested from {source_lang} to English (placeholder)")
        return prompt

    def get_statistics(self) -> Dict:
        """Get builder statistics"""
        return self.stats.copy()


# ==================== PRE-DEFINED PROMPT PRESETS ====================

PROMPT_PRESETS = {
    "professional_headshot": {
        "prompt": "professional headshot, business attire, neutral background",
        "style": PromptStyle.PROFESSIONAL,
        "pose": "headshot",
    },
    "linkedin_profile": {
        "prompt": "professional LinkedIn profile photo, confident smile, business casual",
        "style": PromptStyle.PROFESSIONAL,
        "pose": "portrait",
    },
    "artistic_portrait": {
        "prompt": "artistic portrait with creative lighting",
        "style": PromptStyle.ARTISTIC,
        "pose": "portrait",
    },
    "fashion_editorial": {
        "prompt": "fashion editorial, stylish outfit, professional pose",
        "style": PromptStyle.FASHION,
        "pose": "full_body",
    },
    "cyberpunk_character": {
        "prompt": "cyberpunk character with neon accents, futuristic city background",
        "style": PromptStyle.CYBERPUNK,
        "pose": "action",
    },
    "fantasy_hero": {
        "prompt": "fantasy hero with magical aura, epic background",
        "style": PromptStyle.FANTASY,
        "pose": "action",
    },
    "vintage_photo": {
        "prompt": "vintage photograph, classic style, sepia tones",
        "style": PromptStyle.VINTAGE,
        "pose": "portrait",
    },
    "romantic_couple": {
        "prompt": "romantic couple portrait, warm lighting, intimate moment",
        "style": None,  # Custom
        "pose": "candid",
    },
}


# ==================== GLOBAL INSTANCE ====================

prompt_builder = PromptBuilder()
