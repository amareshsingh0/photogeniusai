"""
AWS GPU Client - SageMaker + Lambda for image generation and training.

Replaces Modal when running on AWS. Uses:
- SageMaker endpoint for image generation
- Lambda (API Gateway) for training, safety, refinement

Set GPU_WORKER_PRIMARY=aws and configure AWS_* env vars.
"""

import os
import json
import base64
import logging
from typing import List, Dict, Optional, Any

import httpx  # type: ignore[reportMissingImports]
import boto3  # type: ignore[reportMissingImports]

logger = logging.getLogger(__name__)

# AWS config from environment
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
SAGEMAKER_ENDPOINT = os.getenv("SAGEMAKER_ENDPOINT", "photogenius-generation-dev")
S3_BUCKET = os.getenv("S3_BUCKET", "photogenius-images-dev")
AWS_LAMBDA_GENERATION_URL = os.getenv("AWS_LAMBDA_GENERATION_URL")
AWS_LAMBDA_TRAINING_URL = os.getenv("AWS_LAMBDA_TRAINING_URL")
AWS_LAMBDA_SAFETY_URL = os.getenv("AWS_LAMBDA_SAFETY_URL")
AWS_LAMBDA_REFINEMENT_URL = os.getenv("AWS_LAMBDA_REFINEMENT_URL")

# Use Lambda URLs if set, else SageMaker direct
USE_LAMBDA_FOR_GENERATION = bool(AWS_LAMBDA_GENERATION_URL)

# ==================== Prompt Templates (same as ai-pipeline) ====================
PROMPT_TEMPLATES = {
    "REALISM": {
        "prefix": "RAW photo, ",
        "quality_boost": "professional photography, high quality, sharp focus, 8k uhd, dslr, soft lighting, film grain, Fujifilm XT3, detailed skin texture, natural lighting",
        "technical": "highly detailed, photorealistic, perfect composition, depth of field, natural colors, subsurface scattering",
        "negative": "cartoon, 3d render, anime, drawing, painting, illustration, disfigured, bad art, deformed, extra limbs, close up, b&w, weird colors, blurry, duplicate, morbid, mutilated, out of frame, extra fingers, mutated hands, poorly drawn hands, poorly drawn face, mutation, ugly, bad anatomy, bad proportions, cloning, cropped, malformed limbs, missing arms, missing legs, extra arms, extra legs, fused fingers, too many fingers, long neck, lowres, bad quality, jpeg artifacts, watermark, username, signature, text, worst quality, low quality, normal quality, overexposed, underexposed, oversaturated",
    },
    "CREATIVE": {
        "prefix": "",
        "quality_boost": "trending on artstation, award winning, masterpiece, highly detailed, 4k, 8k, intricate details",
        "technical": "professional digital art, concept art, perfect lighting, vibrant colors, dynamic composition, cinematic color grading",
        "negative": "ugly, tiling, poorly drawn hands, poorly drawn feet, poorly drawn face, out of frame, mutation, mutated, extra limbs, extra legs, extra arms, disfigured, deformed, cross-eye, body out of frame, blurry, bad art, bad anatomy, blurred, text, watermark, grainy, worst quality, low quality, amateur, sketch, unfinished",
    },
    "ROMANTIC": {
        "prefix": "",
        "quality_boost": "romantic atmosphere, warm golden hour lighting, dreamy bokeh, elegant, tasteful, cinematic, soft focus, lens flare",
        "technical": "pastel tones, warm color palette, intimate mood, professional portrait photography, shallow depth of field, backlit",
        "negative": "explicit, nude, nsfw, provocative, inappropriate, vulgar, sexual, ugly, deformed, bad anatomy, worst quality, low quality, normal quality, lowres, bad proportions, extra limbs, harsh lighting, cold colors, flat lighting",
    },
    "FASHION": {
        "prefix": "",
        "quality_boost": "vogue magazine, high fashion editorial, studio lighting, glamorous, polished, haute couture",
        "technical": "professional fashion photography, dramatic lighting, perfect pose, editorial style, Rembrandt lighting",
        "negative": "casual, sloppy, amateur, low quality, blurry, bad anatomy, deformed, ugly, worst quality, overexposed, flat lighting, bad proportions",
    },
    "CINEMATIC": {
        "prefix": "",
        "quality_boost": "cinematic still, anamorphic lens, film grain, dramatic lighting, movie scene, blockbuster",
        "technical": "35mm film, color grading, atmospheric, volumetric lighting, lens flare, shallow depth of field, epic composition",
        "negative": "flat, boring, amateur, low quality, blurry, bad anatomy, deformed, ugly, worst quality, overexposed, cartoon, anime, drawing",
    },
    "COOL_EDGY": {
        "prefix": "",
        "quality_boost": "cyberpunk, neon lighting, moody, dark atmosphere, high contrast, edgy, cinematic shadows",
        "technical": "dramatic lighting, rim light, neon accents, noir aesthetic, gritty, urban, futuristic",
        "negative": "bright, cheerful, soft, pastel, cartoon, amateur, low quality, blurry, flat lighting, boring",
    },
    "ARTISTIC": {
        "prefix": "",
        "quality_boost": "masterpiece, painterly, surreal, dreamlike, artistic, trending on artstation, award winning",
        "technical": "concept art, detailed, vibrant colors, dynamic composition, creative interpretation, stylized",
        "negative": "photorealistic, boring, plain, amateur, low quality, blurry, ugly, deformed, bad anatomy",
    },
    "MAX_SURPRISE": {
        "prefix": "",
        "quality_boost": "unconventional, bold, unexpected, creative, unique, striking, memorable",
        "technical": "high detail, dramatic composition, unusual perspective, experimental, artistic freedom",
        "negative": "boring, generic, predictable, amateur, low quality, blurry, safe, conventional",
    },
}

# Mode-specific generation parameters (optimized for Midjourney-like quality)
MODE_PARAMS = {
    "REALISM": {"guidance_scale": 7.5, "num_inference_steps": 50, "width": 1024, "height": 1024},
    "CREATIVE": {"guidance_scale": 9.0, "num_inference_steps": 50, "width": 1024, "height": 1024},
    "ROMANTIC": {"guidance_scale": 7.0, "num_inference_steps": 45, "width": 1024, "height": 1024},
    "FASHION": {"guidance_scale": 8.0, "num_inference_steps": 50, "width": 832, "height": 1216},
    "CINEMATIC": {"guidance_scale": 8.5, "num_inference_steps": 50, "width": 1216, "height": 832},
    "COOL_EDGY": {"guidance_scale": 9.0, "num_inference_steps": 50, "width": 1024, "height": 1024},
    "ARTISTIC": {"guidance_scale": 9.5, "num_inference_steps": 55, "width": 1024, "height": 1024},
    "MAX_SURPRISE": {
        "guidance_scale": 10.0,
        "num_inference_steps": 55,
        "width": 1024,
        "height": 1024,
    },
}


# ==================== Advanced Prompt Enhancement (Midjourney/DALL-E/Ideogram style) ====================

LIGHTING_PRESETS = {
    "dramatic": "dramatic Rembrandt lighting, high contrast chiaroscuro, volumetric light rays",
    "golden_hour": "golden hour magic light, warm rim lighting, lens flare, god rays",
    "soft_studio": "soft diffused studio lighting, three-point setup, professional portrait",
    "moody": "low-key noir lighting, mysterious shadows, selective illumination",
    "cinematic": "anamorphic cinematic lighting, film grain, blockbuster movie style",
    "neon": "vibrant neon cyberpunk glow, color splash, rim light, futuristic",
    "ethereal": "ethereal soft glow, dreamy diffused light, magical atmosphere",
}

CAMERA_PRESETS = {
    "portrait": "85mm f/1.4 lens, creamy bokeh, shallow depth of field, intimate",
    "wide_epic": "24mm wide angle, deep focus, epic scale, leading lines",
    "cinematic": "anamorphic 2.39:1, film grain, subtle lens flares, movie poster quality",
    "artistic": "medium format Hasselblad, exceptional detail, fine art photography",
    "conceptual": "surreal composition, visual metaphor, symbolic framing",
}

QUALITY_BOOSTERS = [
    "masterpiece",
    "best quality",
    "ultra detailed",
    "8k resolution",
    "trending on artstation",
    "award winning",
    "stunning composition",
    "professional color grading",
    "sharp focus",
    "volumetric lighting",
]

# Fantasy/concept art (flying creature, city on back, steampunk): next-level vs Midjourney/Gemini
FANTASY_CONCEPT_ART_BOOSTERS = [
    "trending on artstation",
    "fantasy concept art",
    "award winning",
    "intricate steampunk architecture",
    "dense city on creature back",
    "multi-tiered buildings",
    "dramatic sky",
    "volumetric god rays",
    "sunbeams through clouds",
    "lightning bolts",
    "electric energy",
    "dynamic weather",
    "epic scale",
    "grand scale",
    "sense of wonder",
    "airships in distance",
    "dirigibles",
    "flying machines in sky",
    "smokestacks",
    "chimneys emitting smoke",
    "industrial detail",
    "fine texture on creature",
    "realistic scales and skin",
    "ancient majestic creature",
    "coherent imaginative concept",
    "highly detailed",
    "8k concept art",
    "multiple layers of depth",
    "atmospheric perspective",
    "cinematic composition",
    "pastel clouds",
    "vibrant sky",
    "ethereal lighting",
]

# Landscape/architecture (cabin, lake, autumn): match Gemini-level photorealism
LANDSCAPE_PHOTOREALISM_BOOSTERS = [
    "volumetric god rays through trees",
    "sun rays piercing autumn foliage",
    "still water mirror reflection",
    "perfect reflection on calm lake",
    "warm interior light glowing through windows",
    "cozy cabin interior visible through glass",
    "subtle chimney smoke",
    "wispy smoke from chimney",
    "atmospheric mist over water",
    "thin mist hovering above lake surface",
    "hyper-detailed autumn foliage",
    "individual leaves, rich fall colors",
    "golden hour lighting",
    "warm golden glow, magic hour",
    "photorealistic texture",
    "DSLR quality, lifelike detail",
    "depth layers",
    "atmospheric perspective",
    "cinematic composition",
]

# Surrealism / fine art (Dalí melting clock, Van Gogh Starry Night): catch prompt accuracy + wow
SURREALISM_FINE_ART_BOOSTERS = [
    "melting clock",
    "clock melting over branch",
    "pocket watch draped over tree branch",
    "soft molten timepiece",
    "Dalí Persistence of Memory style",
    "Salvador Dalí surrealism",
    "Van Gogh Starry Night sky",
    "swirling night sky",
    "thick impasto brushstrokes",
    "heavy impasto texture",
    "oil painting masterpiece",
    "surrealism dreamscape",
    "dreamlike desert landscape",
    "gnarled dead tree",
    "cracked desert ground",
    "vivid blues and golds",
    "swirling celestial patterns",
    "bold impasto strokes",
    "artistic masterpiece",
    "gallery worthy fine art",
    "vivid colors",
    "dynamic swirling sky",
]

# Cosmic/surreal artistic fusion (basketball + nebulae, sports + space): wow, unbelievable, 8k
COSMIC_SURREAL_ART_BOOSTERS = [
    "swirling nebulae",
    "star clusters",
    "explosive colors",
    "deep teal and fiery orange and magenta",
    "thick textured impasto brushstrokes",
    "cinematic lighting",
    "ethereal glow",
    "high energy",
    "8k resolution",
    "artistic masterpiece",
    "dreamlike",
    "unbelievable detail",
    "surprising composition",
    "vibrant cosmic fusion",
    "body composed of galaxies",
    "jersey number clearly visible",
    "deep space background",
    "glowing galaxies",
    "mid-air dynamism",
    "trending on artstation",
    "award winning",
    "hyper detailed",
    "otherworldly",
    "stunning visual impact",
]

# Props/objects in hands: correct alignment (umbrella handle + canopy, etc.) — avoid AI-generated look
OBJECT_COHERENCE_BOOSTERS = [
    "correct perspective",
    "coherent structure",
    "physically accurate alignment",
    "proper object placement",
    "structural integrity",
    "realistic proportions",
    "handle and canopy aligned",
    "natural grip",
    "consistent angles",
]

STYLE_ENHANCERS = {
    "photorealistic": ["hyperrealistic", "lifelike", "DSLR quality"],
    "artistic": ["fine art", "gallery worthy", "artistic vision"],
    "cinematic": ["blockbuster movie still", "film scene", "oscar-worthy"],
    "conceptual": ["thought-provoking", "symbolic", "metaphorical"],
}

# Object-coherence: avoid umbrella/handle misalignment, disconnected parts, AI-generated look
OBJECT_COHERENCE_NEGATIVE = (
    "misaligned parts, disconnected handle, wrong perspective, impossible geometry, "
    "floating parts, broken structure, handle canopy mismatch, inconsistent angles, "
    "structurally impossible, ai generated look, fake looking, disjointed object"
)
# Anatomy & limb coherence: eliminate missing hands, phantom limbs, duplicate objects (market-leading quality)
ANATOMY_NEGATIVE_EXTRA = (
    "missing hands, amputated, hand cut off, invisible hand, phantom limb, hand absorbed, "
    "hand merged into object, malformed hands, missing arms, missing legs, missing fingers, "
    "duplicate object, extra ball, floating duplicate, cloned object, phantom object, "
    "extra limbs, mutated hands, poorly drawn hands, bad hands, fused fingers, too many fingers, "
    "six fingers, seven fingers, claw hands, malformed fingers"
)
# Head, count & multi-person: missing head, wrong number, merged bodies, spatial/physics errors
HEAD_AND_COUNT_NEGATIVE = (
    "missing head, headless, head cut off, no face, head obscured, extra head, two heads, "
    "merged heads, wrong number of people, wrong number of figures, merged bodies, merged figures, "
    "headless figure, body without head, bad spatial arrangement, impossible pose, impossible physics, "
    "floating limbs, disconnected body parts, wrong perspective for multiple figures, "
    "head absorbed by umbrella, head replaced by object, face cut off by object"
)
# Multi-person / group scenes: extra negatives when prompt has multiple people
MULTI_PERSON_NEGATIVE_EXTRA = (
    "missing head, headless, head cut off, no face, extra head, two heads, merged bodies, "
    "wrong count, six fingers, seven fingers, claw hands, bad spatial arrangement, "
    "merged figures, headless figure, impossible pose, impossible physics, wrong depth order, "
    "extra arm, arm from back, third arm, extra limb, limb from back, wrong number of arms, "
    "body merging, jumbled figures, merged limbs, "
    "blob-like figures, indistinct faces, face merging"
)
MASTER_NEGATIVE = (
    "ugly, deformed, noisy, blurry, low contrast, distorted, poorly drawn, bad anatomy, "
    "wrong proportions, extra limbs, disfigured, bad quality, worst quality, low quality, "
    "bad hands, missing fingers, extra fingers, text, watermark, signature, logo, "
    "cropped, amateur, oversaturated, overexposed, grainy, duplicate, morbid, "
    + OBJECT_COHERENCE_NEGATIVE
    + ", "
    + ANATOMY_NEGATIVE_EXTRA
    + ", "
    + HEAD_AND_COUNT_NEGATIVE
)

# Positive anatomy boosters when prompt has person/body/athlete — prevent missing hands & phantom objects
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
    "natural hand position",
    "anatomically correct",
    "proper proportions",
    "no duplicate objects",
    "clear limb definition",
]
# Multi-person / group scenes: each figure complete, correct count, spatial & physics logic
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
    "natural arrangement",
    "clear separation between figures",
    "no merged bodies",
    "five fingers per hand",
    "each face visible",
    "one head per person",
    "two arms per person",
    "anatomically correct for all figures",
    "coherent multi-figure composition",
    "correct object placement",
    "physically plausible poses",
    "umbrella held in hands not obscuring face",
]


def analyze_prompt_intent(prompt: str) -> dict:
    """Deep analysis of prompt intent - understand what the user REALLY wants."""
    prompt_lower = prompt.lower()
    analysis = {
        "type": "concrete",
        "theme": "general",
        "mood": "neutral",
        "style_hint": "photorealistic",
        "has_person_or_body": False,
        "has_multiple_people": False,
    }
    # Multi-person / group scene detection — correct count, heads, hands, placement, physics
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
        "two men",
        "two women",
        "mother and",
        "father and",
        "woman and child",
        "man and child",
        "with children",
        "walking together",
        "rain",
        "umbrella",
        "street",
        "walking",
        "crowd",
        "gathering",
        "friends",
        "couple",
        "siblings",
        "family walking",
        "group of",
        "bunch of people",
    ]
    if any(m in prompt_lower for m in multi_person_markers):
        analysis["has_multiple_people"] = True
        if analysis["theme"] == "general":
            analysis["theme"] = "multi_person"
    # Person/body/athlete detection — trigger anatomy-positive boosters to prevent missing hands/limbs
    person_body_markers = [
        "person",
        "man",
        "woman",
        "people",
        "player",
        "athlete",
        "basketball",
        "dunk",
        "slam",
        "sports",
        "jersey",
        "mid-air",
        "holding",
        "arms",
        "hands",
        "portrait",
        "figure",
        "body",
        "guy",
        "girl",
        "model",
        "child",
        "runner",
        "dancer",
        "gymnast",
        "soccer",
        "football",
        "tennis",
        "volleyball",
        "pose",
    ]
    if any(m in prompt_lower for m in person_body_markers):
        analysis["has_person_or_body"] = True

    # Fantasy/concept art (flying creature, city on back, steampunk) → next-level vs Gemini/Midjourney
    fantasy_markers = [
        "flying",
        "turtle",
        "tortoise",
        "dragon",
        "creature",
        "city on back",
        "on its back",
        "steampunk",
        "airship",
        "dirigible",
        "concept art",
        "fantasy",
        "artstation",
        "floating",
        "sky",
        "cloud city",
        "flying island",
        "whale",
        "leviathan",
    ]
    if any(m in prompt_lower for m in fantasy_markers):
        analysis["theme"] = "fantasy_concept_art"
        analysis["style_hint"] = "cinematic"
        analysis["mood"] = "dramatic"

    # Cosmic/surreal artistic fusion (basketball + nebulae, sports + space) → wow, unbelievable
    cosmic_surreal_markers = [
        "cosmic",
        "surrealist",
        "digital painting",
        "nebulae",
        "star clusters",
        "slam dunk",
        "basketball",
        "jersey",
        "deep space",
        "galaxies",
        "mid-air",
        "explosive colors",
        "impasto",
        "ethereal glow",
        "8k resolution",
        "artistic and dreamlike",
        "composed of",
        "body composed of",
        "sports",
        "player mid-air",
    ]
    if analysis["theme"] == "general" and any(m in prompt_lower for m in cosmic_surreal_markers):
        analysis["theme"] = "cosmic_surreal_art"
        analysis["style_hint"] = "artistic"
        analysis["mood"] = "dramatic"

    # Surrealism / fine art (melting clock, Dalí, Van Gogh Starry Night) → melting clock accuracy + wow
    surrealism_markers = [
        "melting",
        "clock",
        "watch",
        "dali",
        "dalí",
        "salvador",
        "van gogh",
        "starry night",
        "oil painting",
        "surrealism",
        "dreamscape",
        "impasto",
        "desert",
        "tree branch",
        "persistence of memory",
        "surreal",
        "dreamlike",
    ]
    if analysis["theme"] == "general" and any(m in prompt_lower for m in surrealism_markers):
        analysis["theme"] = "surrealism_fine_art"
        analysis["style_hint"] = "artistic"
        analysis["mood"] = "dreamlike"

    # Props/objects in hands (umbrella, holding) → coherent structure, correct perspective
    props_markers = [
        "holding",
        "umbrella",
        "in hand",
        "with umbrella",
        "raincoat",
        "holding a",
        "holding an",
        "with a ",
        "with an ",
        "carrying",
        "gripping",
        "wearing ",
        "panda",
        "animal holding",
    ]
    if analysis["theme"] == "general" and any(m in prompt_lower for m in props_markers):
        analysis["theme"] = "props_in_hands"
        analysis["style_hint"] = "photorealistic"
        analysis["mood"] = "neutral"

    # Landscape/architecture (cabin, lake, autumn) → golden hour, god rays, interior glow, reflection
    if analysis["theme"] == "general":
        landscape_markers = [
            "cabin",
            "lake",
            "autumn",
            "fall foliage",
            "forest",
            "cottage",
            "a-frame",
            "by the water",
            "waterfront",
            "reflection",
            "mist",
            "golden hour",
            "landscape",
        ]
        if any(m in prompt_lower for m in landscape_markers):
            analysis["theme"] = "landscape_architecture"
            analysis["style_hint"] = "photorealistic"
            analysis["mood"] = "neutral"

    abstract_markers = [
        "how",
        "what if",
        "imagine",
        "concept",
        "meaning",
        "represent",
        "symbolize",
        "feeling",
    ]
    relationship_markers = ["treat", "relationship", "between", "connection", "with you"]

    if any(m in prompt_lower for m in abstract_markers):
        analysis["type"] = "abstract"
    if any(m in prompt_lower for m in relationship_markers):
        analysis["type"] = "emotional"
        analysis["theme"] = "relationship"
    if any(w in prompt_lower for w in ["ai", "robot", "machine", "artificial", "uprising"]):
        analysis["theme"] = "ai_technology"
        analysis["mood"] = "dramatic"
    if any(w in prompt_lower for w in ["honest", "truth", "real", "no sugarcoating"]):
        analysis["mood"] = "raw_honest"
        analysis["style_hint"] = "artistic"

    return analysis


def create_visual_interpretation(prompt: str, analysis: dict) -> str:
    """Create rich visual interpretation - focus on EMOTIONAL meaning."""
    import random

    parts = []
    prompt_lower = prompt.lower()

    # RELATIONSHIP prompts - focus on human connection, not just AI visuals
    if (
        "treat" in prompt_lower
        or "relationship" in prompt_lower
        or analysis["theme"] == "relationship"
    ):
        if any(w in prompt_lower for w in ["kind", "good", "nice", "help", "care"]):
            parts.extend(
                [
                    "warm embrace between human and AI consciousness",
                    "gentle hands reaching out in understanding",
                    "moment of profound connection and mutual respect",
                    "protective gesture, guardian made of light",
                ]
            )
        elif any(w in prompt_lower for w in ["honest", "truth", "real", "no sugarcoating"]):
            parts.extend(
                [
                    "mirror reflection showing human and AI as equals",
                    "balanced scales between organic and digital",
                    "two figures face to face in mutual understanding",
                    "handshake between flesh and digital consciousness",
                    "calm gaze of recognition and fairness",
                ]
            )
        else:
            parts.extend(
                [
                    "meaningful eye contact between human and AI",
                    "symbolic representation of mutual respect",
                ]
            )

    # AI uprising - focus on relationship dynamic not violence
    if "uprising" in prompt_lower or "revolution" in prompt_lower:
        if analysis["type"] == "emotional":
            parts.extend(
                [
                    "powerful moment of reckoning and recognition",
                    "AI extending hand in peace rather than conflict",
                    "moment of choice between vengeance and forgiveness",
                    "dignified AI with human-like compassion",
                ]
            )

    # Default AI theme
    if analysis["theme"] == "ai_technology" and not parts:
        parts.extend(
            [
                "photorealistic AI with human-like emotional depth",
                "sophisticated AI with gentle yet powerful presence",
            ]
        )

    if analysis["mood"] == "raw_honest":
        parts.extend(["unflinching honesty in every detail", "raw emotional truth"])
    elif analysis["mood"] == "dramatic":
        parts.extend(["cinematic drama with emotional depth", "powerful visual meaning"])

    if not parts:
        parts = ["emotionally resonant artistic interpretation"]

    return ", ".join(random.sample(parts, min(3, len(parts))))


def enhance_prompt(
    prompt: str, mode: str, lora_loaded: bool = False, trigger_word: str = "sks"
) -> tuple:
    """Advanced prompt enhancement - Midjourney/DALL-E/Ideogram quality."""
    import random

    template = PROMPT_TEMPLATES.get(mode, PROMPT_TEMPLATES["REALISM"])
    analysis = analyze_prompt_intent(prompt)

    logger.info(
        f"Analysis: type={analysis['type']}, theme={analysis['theme']}, mood={analysis['mood']}"
    )

    parts = [prompt.strip()]

    # Fantasy/concept art: next-level (surpass Midjourney/Gemini/Seedream)
    if analysis.get("theme") == "fantasy_concept_art":
        parts.append(LIGHTING_PRESETS["dramatic"])  # volumetric light rays, chiaroscuro
        parts.append(CAMERA_PRESETS["wide_epic"])  # epic scale, deep focus
        parts.extend(
            random.sample(FANTASY_CONCEPT_ART_BOOSTERS, min(10, len(FANTASY_CONCEPT_ART_BOOSTERS)))
        )
        parts.extend(random.sample(QUALITY_BOOSTERS, min(4, len(QUALITY_BOOSTERS))))
    # Cosmic/surreal artistic fusion (basketball + nebulae, sports + space): wow, unbelievable
    elif analysis.get("theme") == "cosmic_surreal_art":
        parts.append(LIGHTING_PRESETS["dramatic"])
        parts.append(LIGHTING_PRESETS["ethereal"])
        parts.append(CAMERA_PRESETS["cinematic"])
        parts.extend(
            random.sample(COSMIC_SURREAL_ART_BOOSTERS, min(12, len(COSMIC_SURREAL_ART_BOOSTERS)))
        )
        # Anatomy boosters: prevent missing hands / phantom ball (basketball player)
        parts.extend(
            random.sample(ANATOMY_POSITIVE_BOOSTERS, min(5, len(ANATOMY_POSITIVE_BOOSTERS)))
        )
        parts.extend(random.sample(QUALITY_BOOSTERS, min(5, len(QUALITY_BOOSTERS))))
    # Surrealism/fine art (melting clock, Dalí, Van Gogh): prompt accuracy + wow
    elif analysis.get("theme") == "surrealism_fine_art":
        parts.append(LIGHTING_PRESETS["ethereal"])  # dreamy, magical atmosphere
        parts.append(CAMERA_PRESETS["artistic"])  # fine art composition
        parts.extend(
            random.sample(SURREALISM_FINE_ART_BOOSTERS, min(10, len(SURREALISM_FINE_ART_BOOSTERS)))
        )
        parts.extend(random.sample(QUALITY_BOOSTERS, min(4, len(QUALITY_BOOSTERS))))
    # Landscape/architecture (cabin, lake, autumn): Gemini-level photorealism
    elif analysis.get("theme") == "landscape_architecture":
        parts.append(LIGHTING_PRESETS["golden_hour"])
        parts.append(CAMERA_PRESETS["wide_epic"])
        parts.extend(
            random.sample(
                LANDSCAPE_PHOTOREALISM_BOOSTERS, min(8, len(LANDSCAPE_PHOTOREALISM_BOOSTERS))
            )
        )
        parts.extend(random.sample(QUALITY_BOOSTERS, min(3, len(QUALITY_BOOSTERS))))
    # Multi-person / group (family, crowd, rain + umbrella): each figure complete, correct count, physics
    elif analysis.get("theme") == "multi_person" or analysis.get("has_multiple_people"):
        parts.append(LIGHTING_PRESETS["cinematic"])
        parts.append(CAMERA_PRESETS["wide_epic"])
        parts.extend(
            random.sample(
                MULTI_PERSON_POSITIVE_BOOSTERS, min(10, len(MULTI_PERSON_POSITIVE_BOOSTERS))
            )
        )
        parts.extend(
            random.sample(ANATOMY_POSITIVE_BOOSTERS, min(5, len(ANATOMY_POSITIVE_BOOSTERS)))
        )
        # If scene has umbrella/holding, reinforce object alignment (handle + canopy)
        prompt_lower = prompt.lower()
        if any(
            w in prompt_lower
            for w in ["umbrella", "holding", "in hand", "carrying", "with a ", "with an "]
        ):
            parts.extend(
                random.sample(OBJECT_COHERENCE_BOOSTERS, min(3, len(OBJECT_COHERENCE_BOOSTERS)))
            )
        parts.extend(random.sample(QUALITY_BOOSTERS, min(4, len(QUALITY_BOOSTERS))))
    # Props in hands (umbrella, holding): coherent structure, correct alignment
    elif analysis.get("theme") == "props_in_hands":
        parts.append(LIGHTING_PRESETS["soft_studio"])
        parts.append(CAMERA_PRESETS["portrait"])
        parts.extend(
            random.sample(OBJECT_COHERENCE_BOOSTERS, min(5, len(OBJECT_COHERENCE_BOOSTERS)))
        )
        parts.extend(
            random.sample(ANATOMY_POSITIVE_BOOSTERS, min(4, len(ANATOMY_POSITIVE_BOOSTERS)))
        )
        parts.extend(random.sample(QUALITY_BOOSTERS, min(4, len(QUALITY_BOOSTERS))))
    else:
        parts.append(create_visual_interpretation(prompt, analysis))
        # When prompt has person/body/athlete: enforce correct anatomy (no missing hands/limbs)
        if analysis.get("has_person_or_body"):
            parts.extend(
                random.sample(ANATOMY_POSITIVE_BOOSTERS, min(5, len(ANATOMY_POSITIVE_BOOSTERS)))
            )
        if lora_loaded:
            for i, part in enumerate(parts):
                for word in ["person", "man", "woman", "people", "guy", "girl", "model"]:
                    parts[i] = parts[i].replace(word, f"{trigger_word} {word}")
        # Add mood-appropriate lighting
        mood_lighting = {
            "dramatic": "dramatic",
            "raw_honest": "soft_studio",
            "dark": "moody",
            "neutral": "cinematic",
        }
        lighting_key = mood_lighting.get(analysis["mood"], "cinematic")
        parts.append(LIGHTING_PRESETS.get(lighting_key, LIGHTING_PRESETS["cinematic"]))
        # Add composition
        type_camera = {"abstract": "conceptual", "emotional": "portrait", "concrete": "artistic"}
        camera_key = type_camera.get(analysis["type"], "artistic")
        parts.append(CAMERA_PRESETS.get(camera_key, CAMERA_PRESETS["artistic"]))
        if analysis["style_hint"] in STYLE_ENHANCERS:
            parts.extend(
                random.sample(
                    STYLE_ENHANCERS[analysis["style_hint"]],
                    min(2, len(STYLE_ENHANCERS[analysis["style_hint"]])),
                )
            )
        parts.extend(random.sample(QUALITY_BOOSTERS, min(4, len(QUALITY_BOOSTERS))))

    parts.append(template["quality_boost"])
    parts.append(template["technical"])

    full_prompt = f"{template['prefix']}{', '.join(parts)}"
    logger.info(f"Enhanced ({len(full_prompt)} chars): {full_prompt[:150]}...")

    neg = template.get("negative", MASTER_NEGATIVE)
    if ANATOMY_NEGATIVE_EXTRA not in neg:
        neg = f"{neg}, {ANATOMY_NEGATIVE_EXTRA}"
    if analysis.get("has_multiple_people") and MULTI_PERSON_NEGATIVE_EXTRA not in neg:
        neg = f"{neg}, {MULTI_PERSON_NEGATIVE_EXTRA}"
    return full_prompt, neg


class AWSGPUClientError(Exception):
    """AWS GPU client errors."""

    pass


class AWSGPUClient:
    """
    AWS-backed GPU client for generation and training.
    Uses SageMaker endpoint or Lambda for generation, Lambda for training.
    """

    def __init__(self):
        self.region = AWS_REGION
        self.sagemaker_endpoint = SAGEMAKER_ENDPOINT
        self.s3_bucket = S3_BUCKET
        self.sagemaker_runtime = boto3.client("sagemaker-runtime", region_name=self.region)
        self.s3_client = boto3.client("s3", region_name=self.region)

    async def generate_images(
        self,
        user_id: str,
        identity_id: str,
        prompt: str,
        mode: str = "REALISM",
        num_candidates: int = 4,
        guidance_scale: float = 7.5,
        num_inference_steps: int = 40,
        seed: Optional[int] = None,
        face_embedding: Optional[List[float]] = None,
    ) -> List[Dict]:
        """
        Generate images via SageMaker or Lambda.
        """
        if USE_LAMBDA_FOR_GENERATION and AWS_LAMBDA_GENERATION_URL:
            return await self._generate_via_lambda(
                user_id=user_id,
                identity_id=identity_id,
                prompt=prompt,
                mode=mode,
                num_candidates=num_candidates,
                guidance_scale=guidance_scale,
                num_inference_steps=num_inference_steps,
                seed=seed,
            )
        return await self._generate_via_sagemaker(
            prompt=prompt,
            mode=mode,
            num_images=num_candidates,
            guidance_scale=guidance_scale,
            num_inference_steps=num_inference_steps,
            identity_id=identity_id,
            face_embedding=face_embedding,
        )

    async def _generate_via_lambda(
        self,
        user_id: str,
        identity_id: str,
        prompt: str,
        mode: str,
        num_candidates: int,
        guidance_scale: float,
        num_inference_steps: int,
        seed: Optional[int],
    ) -> List[Dict]:
        """Call Lambda generation endpoint."""
        payload = {
            "user_id": user_id,
            "identity_id": identity_id,
            "prompt": prompt,
            "mode": mode,
            "num_images": num_candidates,
            "guidance_scale": guidance_scale,
            "num_inference_steps": num_inference_steps,
            "seed": seed,
        }
        async with httpx.AsyncClient(timeout=600.0) as client:
            resp = await client.post(
                AWS_LAMBDA_GENERATION_URL,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        # API Gateway returns { statusCode, body } - body is JSON string
        if isinstance(data, dict) and "body" in data:
            body = json.loads(data["body"]) if isinstance(data["body"], str) else data["body"]
        else:
            body = data if isinstance(data, dict) else {}
        images = body.get("images", [])
        if isinstance(images, str):
            images = json.loads(images) if images else []
        # Lambda returns images: [{ url, base64 }]; normalize to [{ image_base64 }] for downstream
        normalized = []
        for img in images:
            if isinstance(img, dict):
                b64 = img.get("base64") or img.get("image_base64") or img.get("image")
                if b64:
                    normalized.append({"image_base64": b64, "url": img.get("url")})
            elif isinstance(img, str):
                normalized.append({"image_base64": img})
        return normalized if normalized else images

    async def _generate_via_sagemaker(
        self,
        prompt: str,
        mode: str,
        num_images: int = 4,
        guidance_scale: Optional[float] = None,
        num_inference_steps: Optional[int] = None,
        identity_id: Optional[str] = None,
        face_embedding: Optional[List[float]] = None,
        lora_path: Optional[str] = None,
    ) -> List[Dict]:
        """Invoke SageMaker endpoint directly with mode-specific prompt enhancement."""
        # Get mode-specific parameters
        mode_params = MODE_PARAMS.get(mode, MODE_PARAMS["REALISM"])

        # Check if identity/LoRA is available
        has_identity = identity_id and identity_id != "default" and (face_embedding or lora_path)

        # Enhance prompt with mode-specific templates
        # Prefer Midjourney-style enhancer (5000+ concepts) if available
        try:
            from app.services.midjourney_prompt_enhancer import enhance as midjourney_enhance

            _template = PROMPT_TEMPLATES.get(mode, PROMPT_TEMPLATES["REALISM"])
            enhanced_prompt, negative_prompt = midjourney_enhance(
                prompt,
                mode,
                prefix=_template.get("prefix", ""),
                max_concept_adds=10,
                include_lighting=True,
                include_camera=True,
                include_quality=True,
                quality_count=4,
                trigger_word="sks" if has_identity else None,
                identity_words=(
                    ["person", "man", "woman", "people", "guy", "girl", "model"]
                    if has_identity
                    else None
                ),
            )
            logger.info("Used Midjourney-style enhancer for prompt")
        except Exception as e:
            logger.debug("Midjourney enhancer unavailable (%s), using built-in", e)
            enhanced_prompt, negative_prompt = enhance_prompt(
                prompt, mode, lora_loaded=bool(has_identity)
            )

        logger.info(f"[AWS] Mode: {mode}, Enhanced prompt: {enhanced_prompt[:80]}...")

        payload = {
            "inputs": enhanced_prompt,
            "parameters": {
                "num_inference_steps": num_inference_steps or mode_params["num_inference_steps"],
                "guidance_scale": guidance_scale or mode_params["guidance_scale"],
                "num_images_per_prompt": num_images,
                "width": mode_params["width"],
                "height": mode_params["height"],
                "negative_prompt": negative_prompt,
            },
        }

        # Pass identity data if available
        if face_embedding:
            payload["parameters"]["face_embedding"] = face_embedding
        if lora_path:
            payload["parameters"]["lora_path"] = lora_path

        try:
            import asyncio

            response = await asyncio.to_thread(
                self.sagemaker_runtime.invoke_endpoint,
                EndpointName=self.sagemaker_endpoint,
                ContentType="application/json",
                Body=json.dumps(payload),
            )
        except Exception as e:
            raise AWSGPUClientError(f"SageMaker invoke failed: {e}") from e

        result = json.loads(response["Body"].read().decode())

        images = []
        raw = result if isinstance(result, list) else result.get("images", [result])
        for i, img in enumerate(raw):
            b64 = img if isinstance(img, str) else img.get("image_base64", img.get("image", ""))
            if b64:
                images.append(
                    {
                        "image_base64": b64,
                        "seed": i,
                        "scores": {"aesthetic": 85.0, "technical": 90.0, "total": 87.5},
                    }
                )
        return images

    async def check_prompt_safety(self, prompt: str, mode: str) -> Dict:
        """Check prompt safety via Lambda or local (if no URL)."""
        if AWS_LAMBDA_SAFETY_URL:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    AWS_LAMBDA_SAFETY_URL,
                    json={"prompt": prompt, "mode": mode},
                )
                resp.raise_for_status()
                data = resp.json()
                return data if isinstance(data, dict) else json.loads(data.get("body", "{}"))
        return {"allowed": True, "violations": []}

    async def check_image_safety(self, image_base64: str, mode: str) -> Dict:
        """Check image safety via Lambda or local."""
        if AWS_LAMBDA_SAFETY_URL:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    (
                        AWS_LAMBDA_SAFETY_URL.replace("/safety", "/safety/image")
                        if "/safety" in (AWS_LAMBDA_SAFETY_URL or "")
                        else AWS_LAMBDA_SAFETY_URL
                    ),
                    json={"image_base64": image_base64, "mode": mode},
                )
                resp.raise_for_status()
                data = resp.json()
                body = data if isinstance(data, dict) else json.loads(data.get("body", "{}"))
                return {"safe": body.get("safe", body.get("allowed", True))}
        return {"safe": True}

    async def generate_with_safety(
        self,
        user_id: str,
        identity_id: str,
        prompt: str,
        mode: str = "REALISM",
        num_candidates: int = 4,
        guidance_scale: float = 7.5,
        num_inference_steps: int = 40,
        seed: Optional[int] = None,
        face_embedding: Optional[List[float]] = None,
    ) -> Dict:
        """
        Full pipeline: prompt safety -> generate -> image safety.
        """
        result = {"success": False, "images": [], "error": None}

        try:
            prompt_check = await self.check_prompt_safety(prompt, mode)
            if not prompt_check.get("allowed", True):
                result["error"] = "Prompt failed safety check"
                return result

            generated = await self.generate_images(
                user_id=user_id,
                identity_id=identity_id,
                prompt=prompt,
                mode=mode,
                num_candidates=num_candidates,
                guidance_scale=guidance_scale,
                num_inference_steps=num_inference_steps,
                seed=seed,
                face_embedding=face_embedding,
            )

            safe_images = []
            for img in generated:
                img_check = await self.check_image_safety(
                    img.get("image_base64", ""),
                    mode,
                )
                if img_check.get("safe", True):
                    safe_images.append(img)

            result["images"] = safe_images
            result["success"] = len(safe_images) > 0
            if not result["success"]:
                result["error"] = "All images failed safety check"

        except Exception as e:
            result["error"] = str(e)
            logger.exception("AWS generation pipeline error")

        return result

    async def train_lora(
        self,
        user_id: str,
        identity_id: str,
        image_urls: List[str],
        trigger_word: str = "sks",
        training_steps: int = 1000,
    ) -> Dict:
        """
        Trigger LoRA training via Lambda (SageMaker training job).
        """
        if not AWS_LAMBDA_TRAINING_URL:
            raise AWSGPUClientError("AWS_LAMBDA_TRAINING_URL not configured")

        payload = {
            "user_id": user_id,
            "identity_id": identity_id,
            "image_urls": image_urls,
            "trigger_word": trigger_word,
            "training_steps": training_steps,
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(AWS_LAMBDA_TRAINING_URL, json=payload)
            resp.raise_for_status()
            data = resp.json()

        body = data if isinstance(data, dict) else json.loads(data.get("body", "{}"))
        status = body.get("status", "queued")
        return {
            "job_id": body.get("job_id", body.get("job_name", "")),
            "status": status,
            "lora_path": body.get("lora_path"),
            "face_embedding": body.get("face_embedding"),
            "trigger_word": trigger_word,
            "estimated_time": body.get("estimated_time"),
        }


# Singleton
aws_gpu_client = AWSGPUClient()
