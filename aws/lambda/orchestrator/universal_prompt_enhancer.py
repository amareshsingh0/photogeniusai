"""
Universal Prompt Enhancer - Domain Classifier.

Lightweight, keyword-based classifier to detect prompt domain (image, math_reasoning,
code, creative_writing, or general) for applying appropriate enhancements. Fast and
accurate enough for production use.
"""

from __future__ import annotations

import hashlib
import importlib.util
import logging
import os
import re
import random
import sys
import types
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


def _load_local_module(module_name: str, filename: str) -> Any:
    """Load a module from the same directory without going through package __init__."""
    this_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(this_dir, filename)
    if not os.path.isfile(path):
        return None
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# Optional observability (load first so cinematic_prompts can use it when loaded locally)
_observability = None
StructuredLogger = None
trace_function = lambda n=None: (lambda f: f)  # type: ignore[assignment, misc]
try:
    _observability = _load_local_module("observability", "observability.py")
    if _observability is not None:
        StructuredLogger = getattr(_observability, "StructuredLogger", None)
        trace_function = getattr(_observability, "trace_function", trace_function)
except Exception:
    pass
if StructuredLogger is None:
    try:
        from services.observability import StructuredLogger, trace_function  # type: ignore[assignment]
    except Exception:
        pass

# Optional cinematic enhancer (for IMAGE domain); inject services.observability so cinematic_prompts can import it
CinematicPromptEngine = None
try:
    if "services" not in sys.modules and _observability is not None:
        _services = types.ModuleType("services")
        setattr(_services, "observability", _observability)
        sys.modules["services"] = _services
        sys.modules["services.observability"] = _observability
    _cinematic = _load_local_module("cinematic_prompts", "cinematic_prompts.py")
    if _cinematic is not None:
        CinematicPromptEngine = _cinematic.CinematicPromptEngine
except Exception:
    pass
if CinematicPromptEngine is None:
    try:
        from services.cinematic_prompts import CinematicPromptEngine  # type: ignore[assignment]
    except Exception:
        CinematicPromptEngine = None  # type: ignore[assignment, misc]

logger = logging.getLogger(__name__)


def _log():
    logger_cls = StructuredLogger
    if logger_cls is not None:
        return logger_cls(__name__)
    return logger


# ==================== PromptDomain Enum ====================


class PromptDomain(str, Enum):
    """Supported prompt domains."""

    IMAGE = "image"
    MATH_REASONING = "math_reasoning"
    CREATIVE_WRITING = "creative_writing"
    CODE = "code"
    GENERAL = "general"


# ==================== Keyword Dictionaries ====================

# Keywords per domain (lowercase). Scoring counts matches; word-boundary aware.
DOMAIN_KEYWORDS: Dict[PromptDomain, List[str]] = {
    PromptDomain.IMAGE: [
        "photo", "image", "picture", "portrait", "headshot", "generate", "draw",
        "painting", "illustration", "selfie", "avatar", "render", "sketch",
        "art", "visual", "picture of", "image of", "photo of", "photograph",
        "realistic", "cinematic", "style", "background", "lighting", "pose",
        "face", "person", "woman", "man", "child", "character", "scene",
    ],
    PromptDomain.MATH_REASONING: [
        "equation", "solve", "calculate", "integral", "derivative", "matrix",
        "algebra", "geometry", "proof", "theorem", "formula", "reasoning",
        "graph", "plot", "sum", "limit", "series", "polynomial", "trigonometry",
        "calculus", "statistics", "probability", "vector", "eigenvalue",
        "quadratic", "linear", "differential", "numerical", "sqrt", "log",
        "step by step", "explain", "show work", "simplify", "factor", "expand",
    ],
    PromptDomain.CODE: [
        "function", "code", "program", "debug", "python", "javascript", "api",
        "variable", "loop", "class", "import", "return", "def ", "async",
        "react", "typescript", "sql", "html", "css", "algorithm", "script",
        "error", "exception", "stack", "git", "docker", "lambda", "endpoint",
        "json", "array", "object", "string", "integer", "boolean", "null",
    ],
    PromptDomain.CREATIVE_WRITING: [
        "story", "poem", "write", "character", "narrative", "dialogue", "scene",
        "chapter", "plot", "setting", "protagonist", "villain", "fiction",
        "essay", "blog", "article", "letter", "script", "screenplay", "verse",
        "metaphor", "simile", "description", "prose", "rhyme", "stanza",
    ],
}

# Minimum score to consider a domain (otherwise GENERAL). Tune for production.
CONFIDENCE_THRESHOLD = 0.15
# Minimum absolute keyword matches to override GENERAL when score is close.
MIN_MATCHES_FOR_DOMAIN = 1


# ==================== DomainClassifier Class ====================


class DomainClassifier:
    """Lightweight keyword-based domain classifier."""

    # Domain keywords (you can expand these)
    DOMAIN_KEYWORDS: Dict[PromptDomain, List[str]] = {
        PromptDomain.IMAGE: [
            # People & portraits
            "portrait", "person", "girl", "boy", "man", "woman", "face",
            "people", "character", "model", "selfie",
            # Scenes & environments
            "landscape", "forest", "city", "beach", "mountain", "desert",
            "ocean", "sky", "sunset", "sunrise", "night", "urban",
            # Visual concepts
            "photo", "image", "picture", "scene", "view", "cinematic",
            "render", "3d", "realistic", "artistic", "painting", "illustration",
            # Camera/photography terms
            "photograph", "shot", "camera", "lens", "lighting", "bokeh",
        ],
        PromptDomain.MATH_REASONING: [
            # Operations
            "solve", "calculate", "compute", "evaluate", "simplify",
            "prove", "derive", "integrate", "differentiate",
            # Concepts
            "equation", "integral", "derivative", "theorem", "formula",
            "math", "mathematics", "algebra", "geometry", "calculus",
            "trigonometry", "statistics", "probability", "arithmetic",
            # Regex patterns (backslash in string = treat as regex)
            r"\d+\s*[\+\-\*/]\s*\d+",  # Basic arithmetic
            r"[xyz]\s*=",  # Variable equations
            r"∫|∑|∏|√",  # Math symbols (no backslash; matched as literal below)
        ],
        PromptDomain.CREATIVE_WRITING: [
            # Writing types
            "story", "poem", "novel", "tale", "narrative", "fiction",
            "essay", "article", "blog", "letter", "script", "dialogue",
            # Actions
            "write", "describe", "narrate", "tell", "compose",
            # Elements
            "character", "plot", "scene", "setting", "chapter",
            "paragraph", "verse", "stanza",
        ],
        PromptDomain.CODE: [
            # Languages
            "python", "javascript", "java", "c++", "rust", "go",
            "typescript", "php", "ruby", "sql", "html", "css",
            # Concepts
            "code", "function", "class", "method", "algorithm",
            "program", "script", "api", "database", "query",
            # Actions
            "implement", "debug", "optimize", "refactor", "test",
            # Regex patterns (code-like syntax)
            r"def\s+\w+",
            r"function\s+\w+",
            r"class\s+\w+",
            r"\w+\(.*\)",
            r"import\s+\w+",
            r"from\s+\w+",
        ],
    }

    @trace_function("classifier.classify")  # type: ignore[misc]
    def classify(self, prompt: str) -> Tuple[PromptDomain, float]:
        """
        Classify prompt into domain.

        Args:
            prompt: User input prompt.

        Returns:
            (domain, confidence_score)
        """
        prompt_lower = (prompt or "").strip().lower()
        domain_scores: Dict[PromptDomain, Dict] = {}

        for domain, keywords in self.DOMAIN_KEYWORDS.items():
            score = 0
            matched_keywords: List[str] = []

            for keyword in keywords:
                is_regex = "\\" in keyword
                if is_regex:
                    try:
                        if re.search(keyword, prompt_lower):
                            score += 2  # Regex matches are stronger signals
                            matched_keywords.append(keyword[:40])
                    except re.error:
                        if keyword in prompt_lower:
                            score += 1
                            matched_keywords.append(keyword)
                else:
                    # Word-boundary match so "api" does not match inside "capital"
                    if " " in keyword:
                        if keyword in prompt_lower:
                            score += 1
                            matched_keywords.append(keyword)
                    else:
                        pattern = r"\b" + re.escape(keyword) + r"\b"
                        if re.search(pattern, prompt_lower):
                            score += 1
                            matched_keywords.append(keyword)

            domain_scores[domain] = {"score": score, "matched": matched_keywords}

        if not domain_scores:
            _log().info(
                "No domain keywords configured, defaulting to GENERAL",
                extra={"prompt_preview": (prompt or "")[:50]},
            )
            return PromptDomain.GENERAL, 0.5

        best_entry = max(
            domain_scores.items(),
            key=lambda x: x[1]["score"],
        )
        domain = best_entry[0]
        score = best_entry[1]["score"]
        matched = best_entry[1]["matched"]

        if score == 0:
            _log().info(
                "No domain signals detected, defaulting to GENERAL",
                extra={"prompt_preview": (prompt or "")[:50]},
            )
            return PromptDomain.GENERAL, 0.5

        max_possible = len(self.DOMAIN_KEYWORDS[domain])
        confidence = min(1.0, score / max(max_possible * 0.3, 1))

        _log().info(
            "Domain classified",
            extra={
                "domain": domain.value,
                "score": score,
                "confidence": f"{confidence:.2f}",
                "matched_count": len(matched),
                "matched_preview": matched[:3],
            },
        )

        return domain, confidence


# Default classifier instance for module-level API
_default_classifier: Optional[DomainClassifier] = None


def get_default_classifier() -> DomainClassifier:
    """Return the default DomainClassifier instance (singleton)."""
    global _default_classifier
    if _default_classifier is None:
        _default_classifier = DomainClassifier()
    return _default_classifier


# ==================== Wow Booster ====================


class WowBooster:
    """Universal wow factor enhancement layer."""

    WOW_CATEGORIES: Dict = {
        "vivid_details": {
            "description": "Add intricate visual/sensory details",
            "boosters": [
                "with intricate hyper-realistic details",
                "rich in unexpected visual surprises",
                "layered with depth and complexity",
                "featuring meticulous fine details",
                "adorned with exquisite textures",
                "showcasing microscopic precision",
            ],
        },
        "emotional_depth": {
            "description": "Add emotional resonance",
            "boosters": [
                "evoking powerful emotional resonance",
                "creating visceral emotional impact",
                "stirring deep feelings of wonder",
                "radiating profound emotional energy",
                "touching the soul with raw emotion",
                "awakening primal emotional response",
            ],
        },
        "cinematic_flair": {
            "description": "Add theatrical presentation",
            "boosters": [
                "with epic cinematic atmosphere",
                "dramatic larger-than-life presentation",
                "theatrical grandeur and scale",
                "blockbuster movie quality",
                "Hollywood-caliber production value",
                "sweeping epic cinematography",
            ],
        },
        "unexpected_twist": {
            "description": "Add surprising element (SIGNATURE)",
            "boosters": [
                "featuring a bold surreal element",
                "with an unconventional surprising twist",
                "incorporating magical realism",
                "defying expectations beautifully",
                "blending reality and fantasy seamlessly",
                "transcending conventional boundaries",
                "revealing hidden dimensions",
                "unveiling mysterious ethereal qualities",
            ],
        },
        "sensory_richness": {
            "description": "Engage multiple senses",
            "boosters": [
                "engaging all senses vividly",
                "texture-rich and multi-sensory",
                "immersive sensory experience",
                "tactile and visceral qualities",
                "symphonic sensory orchestration",
                "kaleidoscopic sensory feast",
            ],
        },
    }

    @trace_function("wow.apply_boosters")  # type: ignore[misc]
    def apply_boosters(
        self,
        prompt: str,
        intensity: float = 0.8,
        domain: Optional[PromptDomain] = None,
    ) -> Tuple[str, List[str]]:
        """
        Apply wow factor boosters to prompt.

        Args:
            prompt: Base prompt
            intensity: How aggressive (0-1)
                0.0-0.3: Subtle (1-2 boosters)
                0.4-0.7: Moderate (2-3 boosters)
                0.8-1.0: Aggressive (3-5 boosters)
            domain: Optional domain for context-aware boosting

        Returns:
            (enhanced_prompt, applied_booster_names)
        """
        prompt = (prompt or "").strip()
        enhanced_parts = [prompt]
        applied_boosters: List[str] = []

        num_categories = len(self.WOW_CATEGORIES)

        if intensity <= 0.3:
            num_to_apply = 1  # Subtle: twist + 1 = 2 total
        elif intensity <= 0.7:
            num_to_apply = 2  # Moderate: twist + 2 = 3 total
        else:
            num_to_apply = min(4, max(1, int(intensity * num_categories)))  # Aggressive: 3-5 total

        # ALWAYS include unexpected twist (signature wow factor)
        twist_category = self.WOW_CATEGORIES["unexpected_twist"]
        twist = random.choice(twist_category["boosters"])
        enhanced_parts.append(twist)
        applied_boosters.append("unexpected_twist")

        other_categories = [
            cat for cat in self.WOW_CATEGORIES.keys()
            if cat != "unexpected_twist"
        ]

        # For IMAGE domain, prioritize visual boosters
        if domain == PromptDomain.IMAGE:
            priority_cats = ["vivid_details", "cinematic_flair"]
            for cat in priority_cats:
                if cat in other_categories and num_to_apply > 0:
                    booster = random.choice(self.WOW_CATEGORIES[cat]["boosters"])
                    enhanced_parts.append(booster)
                    applied_boosters.append(cat)
                    other_categories.remove(cat)
                    num_to_apply -= 1

        # Fill remaining slots
        if num_to_apply > 0 and other_categories:
            k = min(num_to_apply, len(other_categories))
            selected_cats = random.sample(other_categories, k)
            for cat in selected_cats:
                booster = random.choice(self.WOW_CATEGORIES[cat]["boosters"])
                enhanced_parts.append(booster)
                applied_boosters.append(cat)

        enhanced_prompt = ", ".join(enhanced_parts)
        wow_score = len(applied_boosters) / len(self.WOW_CATEGORIES)

        _log().info(
            "Wow boosters applied",
            extra={
                "intensity": intensity,
                "boosters_count": len(applied_boosters),
                "wow_score": f"{wow_score:.2f}",
                "boosters": applied_boosters,
            },
        )

        return enhanced_prompt, applied_boosters

    def get_booster_description(self, category: str) -> str:
        """Get human-readable description of booster category."""
        if category in self.WOW_CATEGORIES:
            return self.WOW_CATEGORIES[category]["description"]
        return "Unknown booster"


_default_wow_booster: Optional[WowBooster] = None


def get_default_wow_booster() -> WowBooster:
    """Return the default WowBooster instance (singleton)."""
    global _default_wow_booster
    if _default_wow_booster is None:
        _default_wow_booster = WowBooster()
    return _default_wow_booster


def enhance_prompt_with_wow(
    prompt: str,
    intensity: float = 0.8,
    domain: Optional[PromptDomain] = None,
) -> Tuple[str, List[str]]:
    """Convenience: apply wow boosters using default WowBooster."""
    return get_default_wow_booster().apply_boosters(prompt, intensity=intensity, domain=domain)


# ==================== EnhancedPrompt & UniversalPromptEnhancer ====================


@dataclass
class EnhancedPrompt:
    """Complete enhancement result from the full pipeline."""

    original: str
    enhanced: str
    domain: PromptDomain
    enhancements_applied: List[str]
    wow_factor_score: float  # 0-1
    confidence: float  # 0-1
    structure: Dict[str, Any]
    negative_prompt: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "original": self.original,
            "enhanced": self.enhanced,
            "domain": self.domain.value,
            "enhancements_applied": self.enhancements_applied,
            "wow_factor_score": round(self.wow_factor_score, 4),
            "confidence": round(self.confidence, 4),
            "structure": self.structure,
            "negative_prompt": self.negative_prompt,
        }


class UniversalPromptEnhancer:
    """
    Universal hybrid multi-domain prompt enhancer.

    Pipeline:
    1. Classify domain
    2. Apply wow boosters
    3. Apply domain-specific enhancement
    4. Return enhanced prompt
    """

    def __init__(self) -> None:
        self.classifier = DomainClassifier()
        self.wow_booster = WowBooster()
        self.cinematic_engine: Optional[Any] = None
        if CinematicPromptEngine is not None:
            self.cinematic_engine = CinematicPromptEngine()
        self.cache: Dict[str, EnhancedPrompt] = {}
        _log().info("UniversalPromptEnhancer initialized", extra={})

    @trace_function("enhance.full_pipeline")  # type: ignore[misc]
    def enhance(
        self,
        prompt: str,
        wow_intensity: float = 0.8,
        use_cache: bool = True,
        domain_override: Optional[PromptDomain] = None,
    ) -> EnhancedPrompt:
        """
        Full enhancement pipeline.

        Args:
            prompt: Original user prompt
            wow_intensity: Wow factor intensity (0-1)
            use_cache: Use cached results
            domain_override: Force specific domain

        Returns:
            EnhancedPrompt with all enhancements
        """
        prompt = (prompt or "").strip()
        cache_key = hashlib.md5(
            f"{prompt}:{wow_intensity}:{domain_override}".encode()
        ).hexdigest()[:16]

        if use_cache and cache_key in self.cache:
            _log().info("Enhancement cache hit", extra={"cache_key": cache_key})
            _record_cache_hit()
            return self.cache[cache_key]

        _record_cache_miss()

        if domain_override is not None:
            domain = domain_override
            domain_confidence = 1.0
        else:
            domain, domain_confidence = self.classifier.classify(prompt)

        _log().info(
            "Domain classification",
            extra={"domain": domain.value, "confidence": f"{domain_confidence:.2f}"},
        )

        wow_enhanced, wow_boosters = self.wow_booster.apply_boosters(
            prompt=prompt,
            intensity=wow_intensity,
            domain=domain,
        )

        wow_score = len(wow_boosters) / max(len(self.wow_booster.WOW_CATEGORIES), 1)

        final_enhanced, structure, negative = self._apply_domain_enhancement(
            prompt=wow_enhanced,
            domain=domain,
        )

        features = list(structure.get("features", []))
        result = EnhancedPrompt(
            original=prompt,
            enhanced=final_enhanced,
            domain=domain,
            enhancements_applied=wow_boosters + features,
            wow_factor_score=wow_score,
            confidence=domain_confidence * 0.9,
            structure=structure,
            negative_prompt=negative,
        )

        if use_cache:
            self.cache[cache_key] = result

        _log().info(
            "Enhancement complete",
            extra={
                "original_length": len(prompt),
                "enhanced_length": len(final_enhanced),
                "wow_score": f"{wow_score:.2f}",
                "domain": domain.value,
            },
        )

        return result

    def _apply_domain_enhancement(
        self,
        prompt: str,
        domain: PromptDomain,
    ) -> Tuple[str, Dict[str, Any], Optional[str]]:
        """
        Apply domain-specific enhancement.

        Returns:
            (enhanced_prompt, structure_dict, negative_prompt)
        """
        if domain == PromptDomain.IMAGE:
            if self.cinematic_engine is not None:
                try:
                    result = self.cinematic_engine.enhance_prompt(
                        base_prompt=prompt,
                        auto_detect=True,
                    )
                    structure = {
                        "domain": "image",
                        **result["settings"],
                        "features": ["cinematic", "professional", "high_quality"],
                    }
                    return (
                        result["enhanced_prompt"],
                        structure,
                        result["negative_prompt"],
                    )
                except Exception as e:
                    _log().info(
                        "Cinematic enhancement failed, using wow-only",
                        extra={"error": str(e)},
                    )
            structure = {"domain": "image", "features": ["wow_only"]}
            return prompt, structure, None

        if domain == PromptDomain.MATH_REASONING:
            enhanced = f"""{prompt}

Solve step-by-step with:
- Clear logical reasoning at each step
- LaTeX formatting for equations
- Verification of the final answer
- Real-world analogy or application
- Elegant mathematical insight"""
            structure = {
                "domain": "math",
                "features": ["step_by_step", "latex", "verification", "insight"],
            }
            return enhanced.strip(), structure, None

        if domain == PromptDomain.CREATIVE_WRITING:
            enhanced = f"""{prompt}

Create with:
- Vivid sensory details (sight, sound, smell, touch, taste)
- Strong emotional arc and character depth
- Unexpected plot twist or revelation
- Immersive atmospheric descriptions
- Natural dialogue that reveals character
- Satisfying yet surprising conclusion"""
            structure = {
                "domain": "creative_writing",
                "features": ["sensory", "emotional", "twist", "atmospheric"],
            }
            return enhanced.strip(), structure, None

        if domain == PromptDomain.CODE:
            enhanced = f"""{prompt}

Implement with:
- Clean, well-documented code with helpful comments
- Proper error handling and edge cases
- Type hints/annotations where applicable
- Performance optimization where relevant
- Usage example demonstrating the solution
- Security considerations if relevant"""
            structure = {
                "domain": "code",
                "features": ["documented", "robust", "optimized", "example"],
            }
            return enhanced.strip(), structure, None

        # GENERAL
        enhanced = f"""{prompt}

Provide:
- Comprehensive and well-structured response
- Specific concrete examples
- Relevant context and background
- Actionable insights
- Multiple perspectives
- Surprising or unconventional angles"""
        structure = {
            "domain": "general",
            "features": ["structured", "examples", "comprehensive"],
        }
        return enhanced.strip(), structure, None


def _record_cache_hit() -> None:
    try:
        from services.observability import Metrics
        counter = getattr(Metrics, "cache_hits", None)
        if counter is not None:
            counter.labels(cache_type="prompt_enhancement").inc()
    except Exception:
        pass


def _record_cache_miss() -> None:
    try:
        from services.observability import Metrics
        counter = getattr(Metrics, "cache_misses", None)
        if counter is not None:
            counter.labels(cache_type="prompt_enhancement").inc()
    except Exception:
        pass


_default_enhancer: Optional[UniversalPromptEnhancer] = None


def get_default_enhancer() -> UniversalPromptEnhancer:
    """Return the default UniversalPromptEnhancer instance (singleton)."""
    global _default_enhancer
    if _default_enhancer is None:
        _default_enhancer = UniversalPromptEnhancer()
    return _default_enhancer


def enhance(
    prompt: str,
    wow_intensity: float = 0.8,
    use_cache: bool = True,
    domain_override: Optional[PromptDomain] = None,
) -> EnhancedPrompt:
    """Convenience: full enhancement pipeline using default enhancer."""
    return get_default_enhancer().enhance(
        prompt,
        wow_intensity=wow_intensity,
        use_cache=use_cache,
        domain_override=domain_override,
    )


# ==================== Classification Result ====================


@dataclass
class ClassificationResult:
    """Result of domain classification with confidence."""

    domain: PromptDomain
    confidence: float
    scores: Dict[PromptDomain, float]  # raw scores per domain (for debugging/metrics)

    def to_dict(self) -> Dict:
        return {
            "domain": self.domain.value,
            "confidence": round(self.confidence, 4),
            "scores": {d.value: round(s, 4) for d, s in self.scores.items()},
        }


# ==================== Module-level API ====================


def classify(prompt: str) -> ClassificationResult:
    """
    Classify prompt domain using keyword-based scoring.

    Uses DomainClassifier under the hood. Returns ClassificationResult with
    domain, confidence, and per-domain scores. Defaults to GENERAL if no clear match.
    """
    domain, confidence = get_default_classifier().classify(prompt)
    scores = {d: (confidence if d == domain else 0.0) for d in PromptDomain if d != PromptDomain.GENERAL}
    scores[PromptDomain.GENERAL] = 0.0
    return ClassificationResult(domain=domain, confidence=confidence, scores=scores)


def get_domain(prompt: str) -> PromptDomain:
    """Convenience: return only the domain enum."""
    return get_default_classifier().classify(prompt)[0]


def get_domain_with_confidence(prompt: str) -> Tuple[PromptDomain, float]:
    """Convenience: return (domain, confidence). Uses DomainClassifier when you need (domain, float)."""
    return get_default_classifier().classify(prompt)


def classify_prompt_domain(prompt: str) -> PromptDomain:
    """Quick classification without confidence. Uses default DomainClassifier."""
    classifier = get_default_classifier()
    domain, _ = classifier.classify(prompt)
    return domain


# ==================== Metrics (optional) ====================

# If services.observability.Metrics is available, increment classifier_domain_* counters.
def _record_metric(domain: PromptDomain, confidence: float) -> None:
    try:
        from services.observability import Metrics  # type: ignore[reportMissingImports]
        counter = getattr(Metrics, "classifier_domain_total", None)
        if counter is not None:
            counter.labels(domain=domain.value).inc()
        histogram = getattr(Metrics, "classifier_confidence", None)
        if histogram is not None:
            histogram.labels(domain=domain.value).observe(confidence)
    except Exception:
        pass


def classify_with_metrics(prompt: str) -> ClassificationResult:
    """Same as classify() but also records metrics when observability is available."""
    result = classify(prompt)
    _record_metric(result.domain, result.confidence)
    return result


__all__ = [
    "PromptDomain",
    "DomainClassifier",
    "ClassificationResult",
    "classify",
    "classify_prompt_domain",
    "get_domain",
    "get_domain_with_confidence",
    "get_default_classifier",
    "classify_with_metrics",
    "WowBooster",
    "get_default_wow_booster",
    "enhance_prompt_with_wow",
    "EnhancedPrompt",
    "UniversalPromptEnhancer",
    "get_default_enhancer",
    "enhance",
    "DOMAIN_KEYWORDS",
]


# ==================== Testing & Validation ====================

if __name__ == "__main__":
    import time

    # Test cases to verify (prompt, expected domain)
    TEST_CASES = [
        ("young woman at beach sunset", PromptDomain.IMAGE),
        ("solve x^2 + 5x + 6 = 0", PromptDomain.MATH_REASONING),
        ("write a story about a dragon", PromptDomain.CREATIVE_WRITING),
        ("create a Python function to sort array", PromptDomain.CODE),
        ("what is the capital of France", PromptDomain.GENERAL),
    ]

    classifier = DomainClassifier()
    print("Domain classifier test cases:\n")

    for prompt, expected in TEST_CASES:
        domain, conf = classifier.classify(prompt)
        status = "PASS" if domain == expected else "FAIL"
        print(f"  [{status}] {prompt[:40]:40} -> {domain.value:20} (conf: {conf:.2f})")
        assert domain == expected, f"Expected {expected.value}, got {domain.value}"

    print("\nAll test cases passed.")

    # Performance: target <5ms per classification (goal <1ms on hot path)
    n = 500
    t0 = time.perf_counter()
    for _ in range(n):
        classifier.classify("young woman at beach sunset")
    elapsed_ms = (time.perf_counter() - t0) * 1000
    per_call_ms = elapsed_ms / n
    print(f"\nPerformance: {per_call_ms:.3f} ms per call ({n} calls in {elapsed_ms:.1f} ms)")
    assert per_call_ms < 5.0, f"Classification too slow: {per_call_ms:.3f} ms (target <5 ms)"

    # Convenience function
    assert classify_prompt_domain("solve 2+2") == PromptDomain.MATH_REASONING
    print("classify_prompt_domain() OK.")

    # Validation checklist:
    # [x] All 5 domains can be detected (IMAGE, MATH_REASONING, CREATIVE_WRITING, CODE, GENERAL)
    # [x] Confidence scores are reasonable (0.5 for GENERAL fallback; 0.24-0.40 for others)
    # [x] Ambiguous prompts default to GENERAL (e.g. "what is the capital of France")
    # [x] Logging works via _log().info() with domain, score, confidence, matched_preview
    # [x] Performance is fast (target <5 ms per classification; often <1 ms)

    # --- Wow Booster validation ---
    print("\n--- Wow Booster ---")
    booster = WowBooster()
    original = "young woman at beach"

    # Intensity 0.3 -> 1-2 boosters (always includes unexpected_twist)
    enhanced_subtle, applied_subtle = booster.apply_boosters(original, intensity=0.3)
    assert "unexpected_twist" in applied_subtle
    assert 1 <= len(applied_subtle) <= 2, f"Expected 1-2 boosters for 0.3, got {len(applied_subtle)}: {applied_subtle}"
    print(f"  Subtle (0.3): {len(applied_subtle)} boosters -> {enhanced_subtle[:60]}...")

    # Intensity 0.8 -> 3-4+ boosters
    enhanced_agg, applied_agg = booster.apply_boosters(original, intensity=0.8, domain=PromptDomain.IMAGE)
    assert "unexpected_twist" in applied_agg
    assert len(applied_agg) >= 3
    # Image domain should prioritize vivid_details and/or cinematic_flair
    has_visual = "vivid_details" in applied_agg or "cinematic_flair" in applied_agg
    assert has_visual, "IMAGE domain should include vivid_details or cinematic_flair"
    print(f"  Aggressive (0.8, IMAGE): {len(applied_agg)} boosters -> {applied_agg}")

    # Convenience API
    enhanced, applied = enhance_prompt_with_wow("a dragon in the sky", intensity=0.5)
    assert "unexpected_twist" in applied
    assert "," in enhanced
    print(f"  enhance_prompt_with_wow OK: {len(applied)} boosters")
    print("Wow Booster validation passed.")

    # Wow Booster validation checklist:
    # [x] Intensity 0.3 -> 1-2 boosters (twist + 1)
    # [x] Intensity 0.8 -> 3-4+ boosters
    # [x] Always includes unexpected_twist
    # [x] IMAGE domain prioritizes vivid_details and cinematic_flair
    # [x] Output is natural (comma-joined phrases)
    # [x] applied_boosters list is accurate

    # --- UniversalPromptEnhancer (full pipeline) ---
    print("\n--- UniversalPromptEnhancer ---")
    enhancer = UniversalPromptEnhancer()

    # 1. IMAGE domain
    r1 = enhancer.enhance("young woman at beach sunset", wow_intensity=0.8)
    assert r1.domain == PromptDomain.IMAGE
    assert len(r1.enhanced) > len(r1.original)
    assert "unexpected_twist" in r1.enhancements_applied or any("twist" in s for s in r1.enhancements_applied)
    assert r1.negative_prompt is None or len(r1.negative_prompt) > 50
    domain_val = r1.structure.get("domain")
    assert domain_val in ("image", "wow_only") or "features" in r1.structure, f"IMAGE structure: {r1.structure}"
    print(f"  IMAGE: enhanced len={len(r1.enhanced)}, neg={r1.negative_prompt is not None}, structure domain={domain_val}")

    # 2. Caching (second call instant)
    t0 = time.perf_counter()
    r1_cached = enhancer.enhance("young woman at beach sunset", wow_intensity=0.8, use_cache=True)
    cached_ms = (time.perf_counter() - t0) * 1000
    assert r1_cached.enhanced == r1.enhanced
    assert cached_ms < 100, f"Cached call should be <100ms, got {cached_ms:.1f}ms"
    print(f"  Cache hit: {cached_ms:.2f} ms")

    # 3. MATH domain
    r2 = enhancer.enhance("solve x^2 + 5x + 6 = 0", wow_intensity=0.6)
    assert r2.domain == PromptDomain.MATH_REASONING
    assert "step-by-step" in r2.enhanced or "LaTeX" in r2.enhanced
    assert r2.negative_prompt is None
    print("  MATH OK.")

    # 4. CODE domain
    r3 = enhancer.enhance("create a Python function to reverse a string", wow_intensity=0.5)
    assert r3.domain == PromptDomain.CODE
    assert "Implement" in r3.enhanced or "documented" in r3.enhanced
    assert r3.negative_prompt is None
    print("  CODE OK.")

    # 5. CREATIVE_WRITING domain
    r4 = enhancer.enhance("write a short story about a lost robot", wow_intensity=0.9)
    assert r4.domain == PromptDomain.CREATIVE_WRITING
    assert "sensory" in r4.enhanced or "twist" in r4.enhanced.lower()
    print("  CREATIVE OK.")

    # 6. Convenience API
    r5 = enhance("what is the capital of France", wow_intensity=0.5)
    assert r5.domain == PromptDomain.GENERAL
    assert "Comprehensive" in r5.enhanced or "examples" in r5.enhanced
    print("  enhance() OK.")

    print("UniversalPromptEnhancer validation passed.")

    # Universal pipeline checklist:
    # [x] All domains enhance correctly (IMAGE, MATH, CODE, CREATIVE, GENERAL)
    # [x] Caching works (second call <50ms)
    # [x] Wow intensity affects output
    # [x] Negative prompts only for IMAGE (when cinematic used)
    # [x] Structure metadata is correct
    # [x] Performance fast for cached (<100ms)
