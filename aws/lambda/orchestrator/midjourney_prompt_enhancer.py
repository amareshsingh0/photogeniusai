"""
Midjourney-style Advanced Prompt Enhancer.

- 5000+ concept mappings (keyword → visual descriptors)
- Scene understanding: indoor/outdoor, time of day, mood
- Automatic lighting selection (based on scene)
- Camera/lens selection (based on subject)
- Midjourney-style quality boosters
- Negative prompt auto-generation

No LLM required — pure rule-based, fast and deterministic.

CANONICAL SOURCE: this file. Synced for deployment:
- aws/lambda/generation/midjourney_prompt_enhancer.py (Lambda)
- apps/api/app/services/midjourney_prompt_enhancer.py (FastAPI)
"""

from __future__ import annotations

import re
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

try:
    from .midjourney_concepts import (
        CONCEPT_MAP,
        get_negative_list,
        get_concept_count,
        get_all_descriptors_count,
    )
except ImportError:
    from midjourney_concepts import (
        CONCEPT_MAP,
        get_negative_list,
        get_concept_count,
        get_all_descriptors_count,
    )


# ==================== SCENE UNDERSTANDING ====================

INDOOR_KEYWORDS = {
    "indoor",
    "inside",
    "interior",
    "room",
    "studio",
    "bedroom",
    "living room",
    "kitchen",
    "bathroom",
    "office",
    "church",
    "castle",
    "palace",
    "museum",
    "library",
    "cafe",
    "restaurant",
    "bar",
    "warehouse",
    "factory",
    "cave",
    "dungeon",
    "hall",
    "corridor",
    "attic",
    "basement",
    "gym",
    "classroom",
}

OUTDOOR_KEYWORDS = {
    "outdoor",
    "outside",
    "exterior",
    "street",
    "park",
    "garden",
    "beach",
    "mountain",
    "forest",
    "desert",
    "ocean",
    "lake",
    "river",
    "sky",
    "rooftop",
    "bridge",
    "alley",
    "meadow",
    "valley",
    "island",
    "cliff",
    "canyon",
}

TIME_OF_DAY = {
    "sunset": ["sunset", "dusk", "golden hour", "twilight"],
    "sunrise": ["sunrise", "dawn", "morning", "early"],
    "noon": ["noon", "midday", "afternoon", "day"],
    "night": ["night", "midnight", "nocturnal", "starry", "moon"],
    "blue_hour": ["blue hour", "twilight", "dusk"],
}

MOOD_KEYWORDS = {
    "dreamy": ["dreamy", "dream", "ethereal", "soft", "surreal"],
    "dark": ["dark", "noir", "moody", "shadow", "gothic", "horror"],
    "romantic": ["romantic", "love", "intimate", "tender", "warm"],
    "epic": ["epic", "dramatic", "grand", "heroic", "cinematic"],
    "peaceful": ["peaceful", "calm", "serene", "zen", "tranquil"],
    "mysterious": ["mysterious", "enigmatic", "secret", "hidden"],
    "futuristic": ["futuristic", "sci-fi", "cyberpunk", "neon", "tech"],
    "vintage": ["vintage", "retro", "nostalgic", "old", "classic"],
    "luxury": ["luxury", "luxurious", "rich", "elegant", "premium"],
    "minimalist": ["minimal", "minimalist", "simple", "clean", "bare"],
}

SUBJECT_TYPE = {
    "portrait": ["portrait", "face", "person", "woman", "man", "child", "people"],
    "landscape": ["landscape", "nature", "mountain", "beach", "forest", "view"],
    "object": ["object", "product", "still life", "item", "thing"],
    "animal": ["animal", "pet", "wildlife", "bird", "dog", "cat", "lion"],
    "architecture": ["building", "architecture", "structure", "interior", "exterior"],
    "abstract": ["abstract", "concept", "symbolic", "metaphor", "art"],
}


@dataclass
class SceneInfo:
    """Parsed scene understanding from prompt."""

    is_indoor: bool = False
    is_outdoor: bool = False
    time_of_day: Optional[str] = None  # sunset, sunrise, noon, night, blue_hour
    mood: Optional[str] = None
    subject_type: Optional[str] = (
        None  # portrait, landscape, object, animal, architecture, abstract
    )
    raw_keywords: List[str] = field(default_factory=list)


def _tokenize_prompt(prompt: str) -> List[str]:
    """Lowercase, split on non-alphanumeric, keep words 2+ chars."""
    prompt_lower = prompt.lower()
    tokens = re.findall(r"[a-z0-9]+(?:\s+[a-z0-9]+)?", prompt_lower)
    # Also single words
    words = set(re.findall(r"\b[a-z]{2,}\b", prompt_lower))
    out = list(words)
    for t in tokens:
        if len(t) > 2:
            out.append(t)
    return list(set(out))


def analyze_scene(prompt: str) -> SceneInfo:
    """Scene understanding: indoor/outdoor, time of day, mood, subject."""
    info = SceneInfo()
    tokens = _tokenize_prompt(prompt)
    info.raw_keywords = tokens

    for t in tokens:
        if t in INDOOR_KEYWORDS:
            info.is_indoor = True
        if t in OUTDOOR_KEYWORDS:
            info.is_outdoor = True
        for time_key, time_words in TIME_OF_DAY.items():
            if t in time_words or time_key.replace("_", " ") in t:
                info.time_of_day = time_key
                break
        for mood_key, mood_words in MOOD_KEYWORDS.items():
            if t in mood_words:
                info.mood = mood_key
                break
        for subj_key, subj_words in SUBJECT_TYPE.items():
            if t in subj_words:
                info.subject_type = subj_key
                break

    if not info.is_indoor and not info.is_outdoor:
        if any(
            w in prompt.lower()
            for w in [
                "sky",
                "cloud",
                "sun",
                "mountain",
                "beach",
                "forest",
                "street",
                "park",
            ]
        ):
            info.is_outdoor = True
        elif any(
            w in prompt.lower()
            for w in ["room", "wall", "inside", "studio", "interior"]
        ):
            info.is_indoor = True

    if not info.time_of_day:
        if any(w in prompt.lower() for w in ["night", "moon", "star", "dark"]):
            info.time_of_day = "night"
        elif any(w in prompt.lower() for w in ["sunset", "golden", "dusk"]):
            info.time_of_day = "sunset"
        elif any(w in prompt.lower() for w in ["sunrise", "dawn", "morning"]):
            info.time_of_day = "sunrise"

    if not info.subject_type:
        info.subject_type = (
            "landscape"
            if (info.is_outdoor and "person" not in prompt.lower())
            else "portrait"
        )

    return info


# ==================== LIGHTING SELECTION (based on scene) ====================

LIGHTING_BY_SCENE: Dict[str, str] = {
    "sunset": "golden hour magic light, warm rim lighting, long shadows, volumetric god rays, honey-toned atmosphere",
    "sunrise": "soft morning light, dewy atmosphere, cool blue and warm orange gradient, ethereal dawn glow",
    "noon": "overhead sun, high contrast, strong highlights, clear visibility, bright midday",
    "night": "starry sky, moonlight, deep blues, ambient artificial light, mysterious shadows, noir atmosphere",
    "blue_hour": "twilight blue, cool atmospheric, moody blue tones, urban glow, transitional light",
    "indoor": "controlled interior lighting, warm ambient, soft diffusion, window light or artificial key light",
    "outdoor": "natural light, sky as fill, directional sun or overcast, environmental reflection",
    "studio": "soft diffused studio lighting, three-point setup, catchlights in eyes, professional portrait",
    "default": "cinematic lighting, volumetric light rays, professional color grading, depth and dimension",
}

LIGHTING_BY_MOOD: Dict[str, str] = {
    "dreamy": "ethereal soft glow, dreamy diffused light, heavenly rays, magical atmosphere, soft focus",
    "dark": "low-key noir lighting, mysterious shadows, selective illumination, chiaroscuro, dramatic contrast",
    "romantic": "warm golden hour, soft rim light, candlelight quality, intimate, lens flare",
    "epic": "dramatic Rembrandt lighting, high contrast chiaroscuro, volumetric rays, blockbuster scale",
    "peaceful": "soft even light, gentle shadows, serene atmosphere, natural diffusion",
    "mysterious": "single source, deep shadows, rim light, enigmatic, film noir",
    "futuristic": "vibrant neon glow, color splash, rim light, cyberpunk atmosphere, LED accents",
    "vintage": "warm film grain, soft contrast, nostalgic tone, aged photograph feel",
    "luxury": "warm key light, soft fill, premium feel, golden accents, elegant shadows",
    "minimalist": "clean even light, minimal shadow, soft gradient, negative space",
}


def get_lighting_for_scene(scene: SceneInfo, mode: str) -> str:
    """Automatic lighting selection from scene + mood + mode."""
    parts = []

    if scene.time_of_day and scene.time_of_day in LIGHTING_BY_SCENE:
        parts.append(LIGHTING_BY_SCENE[scene.time_of_day])
    elif scene.is_indoor:
        parts.append(LIGHTING_BY_SCENE.get("indoor", LIGHTING_BY_SCENE["default"]))
    elif scene.is_outdoor:
        parts.append(LIGHTING_BY_SCENE.get("outdoor", LIGHTING_BY_SCENE["default"]))

    if scene.mood and scene.mood in LIGHTING_BY_MOOD:
        parts.append(LIGHTING_BY_MOOD[scene.mood])

    if not parts:
        parts.append(LIGHTING_BY_SCENE["default"])
    return parts[0] if len(parts) == 1 else ", ".join(parts[:2])


# ==================== CAMERA / LENS SELECTION (based on subject) ====================

CAMERA_BY_SUBJECT: Dict[str, str] = {
    "portrait": "85mm f/1.4 lens, creamy bokeh, shallow depth of field, eye-level, intimate framing, flattering compression",
    "landscape": "24mm wide angle, deep focus, environmental storytelling, leading lines, epic scale, sharp foreground to background",
    "object": "100mm macro or 50mm f/2, sharp detail, controlled dof, product-style composition, clean background",
    "animal": "200mm telephoto or 85mm, shallow dof, sharp eyes, natural moment, wildlife composition",
    "architecture": "tilt-shift or 24mm, straight lines, perspective control, dramatic angles, environmental context",
    "abstract": "creative focal length, surreal composition, symbolic framing, thought-provoking perspective",
}

CAMERA_BY_MODE: Dict[str, str] = {
    "REALISM": "DSLR quality, natural perspective, professional composition",
    "CREATIVE": "artistic angle, dynamic composition, creative framing",
    "CINEMATIC": "anamorphic 2.39:1, film grain, subtle lens flares, movie poster quality",
    "FASHION": "editorial 85mm, Rembrandt lighting, high fashion composition",
    "ROMANTIC": "soft focus, dreamy bokeh, intimate framing",
    "COOL_EDGY": "dutch angle, high contrast, urban composition",
    "ARTISTIC": "medium format Hasselblad feel, fine art composition, museum quality",
    "MAX_SURPRISE": "unusual perspective, experimental composition, bold framing",
}


def get_camera_for_scene(scene: SceneInfo, mode: str) -> str:
    """Camera and lens selection from subject + mode."""
    subject = scene.subject_type or "portrait"
    cam_subject = CAMERA_BY_SUBJECT.get(subject, CAMERA_BY_SUBJECT["portrait"])
    cam_mode = CAMERA_BY_MODE.get(mode, "")
    if cam_mode:
        return f"{cam_subject}, {cam_mode}"
    return cam_subject


# ==================== MIDJOURNEY-STYLE QUALITY BOOSTERS ====================

QUALITY_BOOSTERS_BY_MODE: Dict[str, List[str]] = {
    "REALISM": [
        "masterpiece",
        "best quality",
        "ultra detailed",
        "8k resolution",
        "photorealistic",
        "DSLR",
        "professional photography",
        "sharp focus",
        "natural lighting",
        "trending on artstation",
        "award winning",
        "stunning composition",
    ],
    "CREATIVE": [
        "masterpiece",
        "best quality",
        "ultra detailed",
        "trending on artstation",
        "award winning digital art",
        "concept art",
        "vibrant colors",
        "dynamic composition",
    ],
    "CINEMATIC": [
        "cinematic still",
        "blockbuster",
        "film grain",
        "anamorphic",
        "movie quality",
        "dramatic lighting",
        "epic scale",
        "oscar-worthy",
        "director's vision",
    ],
    "FASHION": [
        "vogue editorial",
        "high fashion",
        "haute couture",
        "glamorous",
        "polished",
        "professional fashion photography",
        "dramatic lighting",
        "perfect pose",
    ],
    "ROMANTIC": [
        "romantic atmosphere",
        "dreamy",
        "soft focus",
        "warm tones",
        "intimate",
        "golden hour",
        "lens flare",
        "pastel tones",
        "elegant",
    ],
    "COOL_EDGY": [
        "cyberpunk",
        "neon",
        "moody",
        "high contrast",
        "noir",
        "edgy",
        "dramatic shadows",
        "urban",
        "futuristic",
    ],
    "ARTISTIC": [
        "masterpiece",
        "fine art",
        "gallery worthy",
        "museum quality",
        "painterly",
        "trending on artstation",
        "award winning",
        "artistic vision",
        "stylized",
    ],
    "MAX_SURPRISE": [
        "unconventional",
        "bold",
        "unique",
        "striking",
        "memorable",
        "experimental",
        "high detail",
        "dramatic composition",
        "artistic freedom",
    ],
}


def get_quality_boosters(mode: str, count: int = 4) -> List[str]:
    """Midjourney-style quality boosters for the given mode."""
    boosters = QUALITY_BOOSTERS_BY_MODE.get(mode, QUALITY_BOOSTERS_BY_MODE["REALISM"])
    return random.sample(boosters, min(count, len(boosters)))


# ==================== CONCEPT EXPANSION (5000+ concepts) ====================


def expand_concepts(prompt: str, max_add: int = 12) -> List[str]:
    """Match prompt tokens to CONCEPT_MAP and return added descriptors."""
    added = []
    seen = set()
    tokens = _tokenize_prompt(prompt)
    # Prefer longer phrases first
    sorted_tokens = sorted(tokens, key=len, reverse=True)
    for t in sorted_tokens:
        if len(added) >= max_add:
            break
        if t in seen:
            continue
        if t in CONCEPT_MAP:
            choices = CONCEPT_MAP[t]
            pick = random.choice(choices)
            if pick not in seen:
                added.append(pick)
                seen.add(pick)
            # Optionally add one more from same concept
            if len(added) < max_add and len(choices) > 1:
                pick2 = random.choice([c for c in choices if c != pick])
                if pick2 not in seen:
                    added.append(pick2)
                    seen.add(pick2)
    return added


# ==================== ANATOMY POSITIVE (prevent missing hands / phantom objects) ====================
ANATOMY_POSITIVE_BOOSTERS = [
    "correct anatomy",
    "both hands visible",
    "natural limbs",
    "complete body",
    "well-defined hands",
    "five fingers each hand",
    "no missing body parts",
    "coherent figure",
    "single subject",
    "anatomically correct",
    "no duplicate objects",
]
MULTI_PERSON_POSITIVE_BOOSTERS = [
    "each person complete",
    "every figure has visible head",
    "head visible even when holding umbrella",
    "every figure has exactly two arms",
    "every figure has two hands only",
    "correct number of people",
    "natural grouping",
    "logical placement",
    "proper depth order",
    "realistic physics",
    "five fingers per hand",
    "each face visible",
    "one head per person",
    "two arms per person",
    "no merged bodies",
    "coherent multi-figure composition",
    "umbrella held in hands not obscuring face",
]
ANATOMY_HEAD_COUNT_NEGATIVE = [
    "missing head",
    "headless",
    "head cut off",
    "no face",
    "head obscured",
    "extra head",
    "two heads",
    "merged heads",
    "extra limbs",
    "extra arm",
    "arm from back",
    "third arm",
    "missing hands",
    "missing arms",
    "phantom limb",
    "merged bodies",
    "merged figures",
    "wrong number of people",
    "six fingers",
    "seven fingers",
    "claw hands",
    "bad anatomy",
    "impossible pose",
    "impossible physics",
]
OBJECT_COHERENCE_NEGATIVE = [
    "misaligned parts",
    "disconnected handle",
    "handle canopy mismatch",
    "structurally impossible",
]

# ==================== NEGATIVE PROMPT AUTO-GENERATION ====================

BASE_NEGATIVE = get_negative_list()

NEGATIVE_BY_MODE: Dict[str, List[str]] = {
    "REALISM": [
        "cartoon",
        "anime",
        "drawing",
        "painting",
        "illustration",
        "3d render",
        "cgi",
    ],
    "CREATIVE": ["ugly", "deformed", "bad anatomy", "blurry", "low quality", "amateur"],
    "CINEMATIC": ["flat", "boring", "amateur", "overexposed", "cartoon", "anime"],
    "FASHION": ["casual", "sloppy", "amateur", "flat lighting", "bad proportions"],
    "ROMANTIC": ["explicit", "nsfw", "harsh", "cold", "flat", "ugly"],
    "COOL_EDGY": ["bright", "cheerful", "pastel", "soft", "boring"],
    "ARTISTIC": ["photorealistic", "boring", "plain", "generic"],
    "MAX_SURPRISE": ["boring", "generic", "predictable", "safe", "conventional"],
}


def build_negative_prompt(
    mode: str,
    scene: Optional[SceneInfo] = None,
    *,
    has_person: bool = False,
    has_multiple_people: bool = False,
) -> str:
    """Auto-generated negative prompt from base + mode + anatomy/multi-person when needed."""
    parts = list(BASE_NEGATIVE)
    mode_neg = NEGATIVE_BY_MODE.get(mode, [])
    parts.extend(mode_neg)
    if has_person or (scene and scene.subject_type == "portrait"):
        parts.extend(ANATOMY_HEAD_COUNT_NEGATIVE)
        parts.extend(OBJECT_COHERENCE_NEGATIVE)
    if has_multiple_people:
        parts.extend(ANATOMY_HEAD_COUNT_NEGATIVE)
        parts.extend(
            [
                "wrong depth order",
                "body merging",
                "jumbled figures",
                "head absorbed by umbrella",
                "face cut off by object",
            ]
        )
    seen = set()
    out = []
    for p in parts:
        p_lower = p.lower()
        if p_lower not in seen:
            seen.add(p_lower)
            out.append(p)
    return ", ".join(out[:100])


# ==================== MAIN ENHANCER API ====================


def enhance(
    prompt: str,
    mode: str = "REALISM",
    *,
    prefix: str = "",
    max_concept_adds: int = 10,
    include_lighting: bool = True,
    include_camera: bool = True,
    include_quality: bool = True,
    quality_count: int = 4,
    trigger_word: Optional[str] = None,
    identity_words: Optional[List[str]] = None,
) -> Tuple[str, str]:
    """
    Full Midjourney-style enhancement.

    Returns:
        (enhanced_prompt, negative_prompt)
    """
    prompt_clean = prompt.strip()
    if not prompt_clean:
        return prompt_clean, build_negative_prompt(mode)

    # 1) Scene understanding
    scene = analyze_scene(prompt_clean)
    parts = [prompt_clean]

    # 2) Concept expansion (5000+ concepts)
    concept_adds = expand_concepts(prompt_clean, max_add=max_concept_adds)
    if concept_adds:
        parts.extend(concept_adds)

    # 2b) Anatomy and multi-person boosters — prevent missing head/hands, extra limbs, merged bodies
    person_body_markers = [
        "person",
        "man",
        "woman",
        "child",
        "player",
        "athlete",
        "basketball",
        "sports",
        "dunk",
        "portrait",
        "figure",
        "body",
        "holding",
        "arms",
        "hands",
    ]
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
    prompt_lower = prompt_clean.lower()
    has_multi = any(m in prompt_lower for m in multi_person_markers)
    has_person = scene.subject_type == "portrait" or any(
        m in prompt_lower for m in person_body_markers
    )
    if has_multi:
        multi_adds = random.sample(
            MULTI_PERSON_POSITIVE_BOOSTERS, min(8, len(MULTI_PERSON_POSITIVE_BOOSTERS))
        )
        parts.extend(multi_adds)
    if has_person:
        anatomy_adds = random.sample(
            ANATOMY_POSITIVE_BOOSTERS, min(5, len(ANATOMY_POSITIVE_BOOSTERS))
        )
        parts.extend(anatomy_adds)

    # 3) Trigger word for identity (e.g. "sks person")
    if trigger_word and identity_words:
        for w in identity_words:
            parts = [p.replace(w, f"{trigger_word} {w}") for p in parts]

    # 4) Lighting
    if include_lighting:
        lighting = get_lighting_for_scene(scene, mode)
        parts.append(lighting)

    # 5) Camera / lens
    if include_camera:
        camera = get_camera_for_scene(scene, mode)
        parts.append(camera)

    # 6) Quality boosters
    if include_quality:
        boosters = get_quality_boosters(mode, count=quality_count)
        parts.extend(boosters)

    # Build final prompt
    if prefix:
        parts.insert(0, prefix)
    full_prompt = ", ".join(parts)
    negative = build_negative_prompt(
        mode, scene, has_person=has_person, has_multiple_people=has_multi
    )
    return full_prompt, negative


def get_stats() -> Dict[str, int]:
    """Return concept counts for logging."""
    return {
        "concept_keywords": get_concept_count(),
        "concept_descriptors": get_all_descriptors_count(),
    }
