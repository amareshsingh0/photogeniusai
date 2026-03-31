"""
Universal Prompt Classifier for Smart Prompt Engine.

Produces a rich ClassificationResult (category, style, medium, lighting,
people count, flags for fantasy/weather/animals/text/architecture) from
a raw user prompt. Used by SmartPromptEngine to build positive/negative prompts.

Task 4.1 (Text/Math/Diagram Guarantee): Detects text requirements for auto-trigger
text rendering: requires_text, text_type (sign/label/caption/poster/ui),
expected_text (from quoted strings), text_placement (centered/top/bottom/on_object),
and text_confidence. Enables downstream TypographyEngine or overlay pipelines.

Math/Diagram: requires_math, expected_formula (LaTeX extracted from prompt, e.g. E=mc² or $...$);
requires_diagram, diagram_type (line/bar/pie/scatter). Enables MathDiagramRenderer overlay.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


# Text type and placement constants for Auto-Trigger Text Rendering (Task 4.1)
TEXT_TYPES = ("sign", "label", "caption", "poster", "ui")
TEXT_PLACEMENTS = ("centered", "top", "bottom", "on_object")

# Math/Diagram constants (Integrate Math Diagram Renderer)
DIAGRAM_TYPES = ("line", "bar", "pie", "scatter")


@dataclass
class ClassificationResult:
    """Rich classification for image prompts; used by SmartPromptEngine."""

    raw_prompt: str
    style: str
    medium: str
    category: str
    lighting: str
    color_palette: str
    has_people: bool
    person_count: int
    has_fantasy: bool
    has_weather: bool
    has_animals: bool
    has_text: bool
    has_architecture: bool
    # Text/Math/Diagram guarantee (Task 4.1): auto-trigger text rendering
    requires_text: bool = False
    text_type: Optional[str] = None  # "sign" | "label" | "caption" | "poster" | "ui"
    expected_text: Optional[str] = None  # extracted from prompt (e.g. quoted)
    text_placement: Optional[str] = None  # "centered" | "top" | "bottom" | "on_object"
    text_confidence: float = 0.0  # 0.0–1.0 for text detection
    # Math/Diagram (Integrate Math Diagram Renderer): LaTeX, equations, charts
    requires_math: bool = False
    expected_formula: Optional[str] = None  # extracted LaTeX
    requires_diagram: bool = False
    diagram_type: Optional[str] = None  # "line" | "bar" | "pie" | "scatter"

    def to_dict(self) -> dict:
        return {
            "raw_prompt": self.raw_prompt,
            "style": self.style,
            "medium": self.medium,
            "category": self.category,
            "lighting": self.lighting,
            "color_palette": self.color_palette,
            "has_people": self.has_people,
            "person_count": self.person_count,
            "has_fantasy": self.has_fantasy,
            "has_weather": self.has_weather,
            "has_animals": self.has_animals,
            "has_text": self.has_text,
            "has_architecture": self.has_architecture,
            "requires_text": self.requires_text,
            "text_type": self.text_type,
            "expected_text": self.expected_text,
            "text_placement": self.text_placement,
            "text_confidence": self.text_confidence,
            "requires_math": self.requires_math,
            "expected_formula": self.expected_formula,
            "requires_diagram": self.requires_diagram,
            "diagram_type": self.diagram_type,
        }


# Keyword rules: (list of keywords, value_if_match)
STYLE_KEYWORDS: List[Tuple[List[str], str]] = [
    (["photorealistic", "realistic", "photo", "8k", "dslr"], "photorealistic"),
    (["vintage", "film grain", "35mm", "analog", "kodachrome"], "film_grain_vintage"),
    (["watercolor", "aquarelle"], "watercolor"),
    (["oil painting", "oil on canvas", "impasto"], "oil_painting"),
    (["flat design", "minimal", "vector-style"], "minimal_flat"),
    (["cyberpunk", "neon", "holographic"], "cyberpunk_neon"),
    (["low-poly", "low poly", "polygon"], "low_poly"),
    (["cartoon", "cel-shaded"], "cartoon"),
    (["black and white", "b&w", "monochrome", "noir"], "bw_high_contrast"),
    (["surreal", "dreamlike", "dali"], "surreal_dreamlike"),
    (["pencil", "sketch", "graphite"], "pencil_sketch"),
    (["anime", "japanese animation"], "anime"),
    (["impressionist", "monet"], "impressionist"),
    (["cubist", "picasso"], "cubist"),
    (["pop art", "warhol"], "pop_art"),
    (["gothic", "dark atmosphere"], "gothic"),
    (["renaissance", "old master", "chiaroscuro"], "renaissance"),
    (["art deco", "1920s"], "art_deco"),
    (["pixel art", "8-bit", "pixel"], "pixel_art"),
    (["chibi", "kawaii"], "chibi"),
]

CATEGORY_KEYWORDS: List[Tuple[List[str], str]] = [
    (["portrait", "headshot", "face", "selfie", "person close-up"], "portrait"),
    (["landscape", "mountains", "valley", "horizon", "sweeping view"], "landscape"),
    (["nature", "forest", "flower", "tree", "animal", "wildlife", "bird"], "nature"),
    (["action", "running", "jumping", "sports", "dynamic", "motion"], "action"),
    (["product", "product shot", "commercial", "on white background"], "product"),
    (["fine art", "gallery", "museum", "masterpiece"], "fine_art"),
    (["illustration", "illustrated", "digital art"], "illustration"),
    (["technical", "diagram", "blueprint", "schematic"], "technical"),
    (["scientific", "microscope", "cell", "anatomy diagram"], "scientific"),
    (["texture", "seamless", "tile"], "graphics"),
    (["game", "game art", "concept art"], "entertainment"),
    (["book cover", "magazine", "poster"], "publishing"),
    (["historical", "period piece", "medieval"], "historical_film"),
    (["cultural", "traditional", "ceremony"], "cultural"),
    (["wedding", "celebration", "festival"], "ceremonial"),
    (["education", "teaching", "infographic"], "education"),
]

MEDIUM_KEYWORDS: List[Tuple[List[str], str]] = [
    (["photograph", "photo", "camera", "dslr"], "photograph"),
    (["painting", "painted", "canvas"], "painting"),
    (["illustration", "illustrated"], "illustration"),
    (["3d", "3D", "render", "cg", "cgi", "unreal"], "3d_render"),
    (["drawing", "sketch", "drawn"], "drawing"),
    (["vector"], "vector"),
    (["diagram", "chart", "graph"], "diagram"),
    (["microscope", "scientific image"], "scientific_image"),
    (["pixel", "sprite"], "digital_pixel"),
    (["mixed media"], "mixed"),
]

LIGHTING_KEYWORDS: List[Tuple[List[str], str]] = [
    (["golden hour", "sunset", "sunrise", "amber"], "golden_hour"),
    (["studio", "studio light", "key light"], "studio"),
    (["night", "nighttime", "moon", "moonlit"], "night"),
    (["dramatic", "high contrast", "single light"], "dramatic"),
    (["soft", "diffused", "even light"], "soft"),
    (["neon", "neon light", "glow"], "neon"),
]

COLOR_KEYWORDS: List[Tuple[List[str], str]] = [
    (["monochrome", "black and white", "b&w", "grayscale"], "monochrome"),
    (["warm", "amber", "golden", "orange", "brown"], "warm"),
    (["cool", "blue", "teal", "cold"], "cool"),
    (["vibrant", "saturated", "vivid", "punchy"], "vibrant"),
    (["muted", "pastel", "desaturated"], "muted"),
    (["duotone"], "duotone"),
]


# ---- Text detection (Task 4.1: Auto-Trigger Text Rendering) ----
# Patterns: (phrase_regex_or_keywords, text_type, placement_hint)
TEXT_DETECTION_PATTERNS: List[Tuple[List[str], str, Optional[str]]] = [
    # (keywords/phrases, text_type, default_placement)
    (["sign that says", "sign saying", "sign reads", "sign with"], "sign", "on_object"),
    (["text that says", "text reading", "text saying", "text reads"], "label", None),
    (["label that says", "label reading", "labeled", "label saying"], "label", "on_object"),
    (["caption that says", "caption reading", "caption saying", "with caption"], "caption", "bottom"),
    (["poster that says", "poster reading", "poster with text", "poster saying"], "poster", "centered"),
    (["ui", "user interface", "button that says", "menu that says", "interface with"], "ui", "on_object"),
    (["watermark", "watermarked"], "label", "centered"),
    (["heading that says", "header that says", "title that says"], "label", "top"),
    (["subtitle", "subtitle that says"], "caption", "bottom"),
]


def _extract_quoted_text(prompt: str) -> Optional[str]:
    """Extract first quoted string from prompt: '...' or \"...\"."""
    # Single-quoted
    m = re.search(r"'([^']*?)'", prompt)
    if m:
        return m.group(1).strip() or None
    # Double-quoted
    m = re.search(r'"([^"]*?)"', prompt)
    if m:
        return m.group(1).strip() or None
    return None


def _detect_text_placement(prompt: str, text_type: str) -> Optional[str]:
    """Infer text placement from context."""
    lower = prompt.lower()
    if any(x in lower for x in ["centered", "center", "in the center", "middle of"]):
        return "centered"
    if any(x in lower for x in ["at the top", "top of", "header", "above", "overhead"]):
        return "top"
    if any(x in lower for x in ["at the bottom", "bottom of", "footer", "below", "under", "caption"]):
        return "bottom"
    if any(x in lower for x in ["on the sign", "on the door", "on the wall", "on the label", "on the poster", "on the button"]):
        return "on_object"
    # Default by type
    for _, t, placement in TEXT_DETECTION_PATTERNS:
        if t == text_type and placement:
            return placement
    return "on_object" if text_type in ("sign", "label", "ui") else "centered"


def _detect_text_requirements(prompt: str) -> Tuple[bool, Optional[str], Optional[str], Optional[str], float]:
    """
    Detect text requirements: requires_text, text_type, expected_text, text_placement, confidence.
    Returns (requires_text, text_type, expected_text, text_placement, confidence).
    """
    p = (prompt or "").strip()
    lower = p.lower()
    expected = _extract_quoted_text(p)
    text_type: Optional[str] = None
    placement: Optional[str] = None
    confidence = 0.0

    for keywords, ttype, default_place in TEXT_DETECTION_PATTERNS:
        for kw in keywords:
            if kw in lower:
                text_type = ttype
                placement = placement or _detect_text_placement(p, ttype) or default_place
                # Higher confidence if we also extracted quoted text
                confidence = 0.9 if expected else 0.7
                break
        if text_type is not None:
            break

    # Legacy broad check: "text", "caption", "label", "sign" without specific phrase
    if text_type is None and any(x in lower for x in ["text", "caption", "label", "sign", "watermark"]):
        if "sign" in lower:
            text_type = "sign"
            placement = placement or "on_object"
        elif "caption" in lower:
            text_type = "caption"
            placement = placement or "bottom"
        elif "label" in lower or "labeled" in lower:
            text_type = "label"
            placement = placement or "on_object"
        elif "poster" in lower:
            text_type = "poster"
            placement = placement or "centered"
        else:
            text_type = "label"
            placement = placement or "centered"
        expected = expected or _extract_quoted_text(p)
        confidence = max(confidence, 0.5 if expected else 0.4)

    requires = text_type is not None or bool(expected)
    if requires and not text_type:
        text_type = "label"
        placement = placement or "centered"
        confidence = max(confidence, 0.5)
    return (requires, text_type, expected or None, placement, min(1.0, confidence))


# ---- Math/Diagram detection (Integrate Math Diagram Renderer) ----
MATH_KEYWORDS = [
    "equation", "formula", "latex", "math", "mathematical",
    "e=mc", "e=mc²", "e=mc^2", "quadratic", "integral", "sum",
    "theorem", "proof", "derivation",
]
DIAGRAM_KEYWORDS: List[Tuple[List[str], str]] = [
    (["bar chart", "bar graph", "bar plot"], "bar"),
    (["line chart", "line graph", "line plot", "trend line"], "line"),
    (["pie chart", "pie graph", "donut chart"], "pie"),
    (["scatter plot", "scatter chart", "scatter graph"], "scatter"),
    (["chart showing", "graph showing", "diagram showing", "chart comparing", "chart with"], "bar"),
]


def _extract_latex_from_prompt(prompt: str) -> Optional[str]:
    """Extract LaTeX or equation from prompt: \\( \\), \\[ \\], $...$, or E=mc^2 style."""
    p = (prompt or "").strip()
    m = re.search(r"\\\((.+?)\\\)", p)
    if m:
        return m.group(1).strip()
    m = re.search(r"\\\[(.+?)\\\]", p, re.DOTALL)
    if m:
        return m.group(1).strip()
    m = re.search(r"\$\$?(.+?)\$\$?", p)
    if m:
        return m.group(1).strip()
    if re.search(r"e\s*=\s*mc\s*[²2]\s*", p, re.IGNORECASE):
        return r"E=mc^2"
    if re.search(r"e\s*=\s*mc\s*\^?\s*2", p, re.IGNORECASE):
        return r"E=mc^2"
    if "a²+b²=c²" in p or "a^2+b^2=c^2" in p.lower():
        return r"a^2+b^2=c^2"
    m = re.search(r"(?:equation|formula)\s+([^\s,\.]+)", p, re.IGNORECASE)
    if m:
        cand = m.group(1).strip()
        if re.match(r"^[\w\^²\s\+\-\*=]+$", cand):
            return cand.replace("²", "^2")
    return None


def _detect_math_requirements(prompt: str) -> Tuple[bool, Optional[str]]:
    """Detect math/formula requirements; return (requires_math, expected_formula)."""
    lower = (prompt or "").lower()
    if not any(k in lower for k in ["equation", "formula", "latex", "math", "e=mc", "quadratic", "integral"]):
        formula = _extract_latex_from_prompt(prompt or "")
        if formula:
            return True, formula
        return False, None
    formula = _extract_latex_from_prompt(prompt or "")
    if formula:
        return True, formula
    if "equation" in lower or "formula" in lower or "latex" in lower:
        return True, None
    return False, None


def _detect_diagram_requirements(prompt: str) -> Tuple[bool, Optional[str]]:
    """Detect chart/diagram requirements; return (requires_diagram, diagram_type)."""
    lower = (prompt or "").lower()
    for keywords, dtype in DIAGRAM_KEYWORDS:
        for kw in keywords:
            if kw in lower:
                return True, dtype
    if any(x in lower for x in ["chart", "graph", "diagram", "infographic", "comparing sales", "comparing data"]):
        return True, "bar"
    return False, None


def _match_keywords(text: str, rules: List[Tuple[List[str], str]]) -> str:
    """Return first matching value for keyword rules; else default (first rule's value style)."""
    lower = text.lower()
    for keywords, value in rules:
        for kw in keywords:
            if kw in lower:
                return value
    return rules[0][1] if rules else ""


def _infer_style(prompt: str) -> str:
    for keywords, value in STYLE_KEYWORDS:
        for kw in keywords:
            if kw in prompt.lower():
                return value
    return "photorealistic"


def _infer_category(prompt: str) -> str:
    for keywords, value in CATEGORY_KEYWORDS:
        for kw in keywords:
            if kw in prompt.lower():
                return value
    return "specialty"


def _infer_medium(prompt: str) -> str:
    for keywords, value in MEDIUM_KEYWORDS:
        for kw in keywords:
            if kw in prompt.lower():
                return value
    return "photograph"


def _infer_lighting(prompt: str) -> str:
    for keywords, value in LIGHTING_KEYWORDS:
        for kw in keywords:
            if kw in prompt.lower():
                return value
    return "natural"


def _infer_color_palette(prompt: str) -> str:
    for keywords, value in COLOR_KEYWORDS:
        for kw in keywords:
            if kw in prompt.lower():
                return value
    return "natural"


def _count_people(prompt: str) -> Tuple[bool, int]:
    """Heuristic: detect 'one/two/three people' or 'person' / 'people'."""
    lower = prompt.lower()
    if "two people" in lower or "2 people" in lower or "couple" in lower:
        return True, 2
    if "three people" in lower or "3 people" in lower:
        return True, 3
    if "group of" in lower or "crowd" in lower or "people" in lower:
        return True, 3  # multi
    if "person" in lower or "man" in lower or "woman" in lower or "child" in lower or "portrait" in lower:
        return True, 1
    return False, 0


class UniversalPromptClassifier:
    """Classify raw user prompt into rich ClassificationResult for SmartPromptEngine."""

    def classify(self, prompt: str) -> ClassificationResult:
        """Return ClassificationResult with style, category, medium, lighting, people, flags, and text fields."""
        p = (prompt or "").strip()
        has_people, person_count = _count_people(p)
        lower = p.lower()
        has_text_legacy = any(x in lower for x in ["text", "caption", "label", "sign", "watermark"])
        requires_text, text_type, expected_text, text_placement, text_confidence = _detect_text_requirements(p)
        requires_math, expected_formula = _detect_math_requirements(p)
        requires_diagram, diagram_type = _detect_diagram_requirements(p)
        return ClassificationResult(
            raw_prompt=p,
            style=_infer_style(p),
            medium=_infer_medium(p),
            category=_infer_category(p),
            lighting=_infer_lighting(p),
            color_palette=_infer_color_palette(p),
            has_people=has_people,
            person_count=person_count,
            has_fantasy=any(x in lower for x in ["dragon", "magic", "fantasy", "wizard", "elf", "unicorn"]),
            has_weather=any(x in lower for x in ["rain", "snow", "storm", "cloud", "fog", "sunny"]),
            has_animals=any(x in lower for x in ["cat", "dog", "animal", "bird", "horse", "lion"]),
            has_text=has_text_legacy or requires_text,
            has_architecture=any(x in lower for x in ["building", "house", "tower", "bridge", "architecture"]),
            requires_text=requires_text,
            text_type=text_type,
            expected_text=expected_text,
            text_placement=text_placement,
            text_confidence=text_confidence,
            requires_math=requires_math,
            expected_formula=expected_formula,
            requires_diagram=requires_diagram,
            diagram_type=diagram_type,
        )


_default_classifier: Optional[UniversalPromptClassifier] = None


def get_default_classifier() -> UniversalPromptClassifier:
    """Return shared classifier instance."""
    global _default_classifier
    if _default_classifier is None:
        _default_classifier = UniversalPromptClassifier()
    return _default_classifier


__all__ = ["ClassificationResult", "UniversalPromptClassifier", "get_default_classifier"]
