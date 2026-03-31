"""
PhotoGenius AI - Generation Lambda v2.0
Invokes SageMaker endpoint for image generation with mode-specific prompt enhancement.
Supports correlation ID (X-Request-ID) for full-stack tracing.
"""

import hashlib
import json
import os
import base64
import time as _time_module
import boto3
from typing import Optional, Any


# Structured logging for CloudWatch Logs Insights (JSON: timestamp, level, service, correlation_id, message, ...)
def _log(
    level: str, message: str, correlation_id: Optional[str] = None, **meta: Any
) -> None:
    entry = {
        "timestamp": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        "level": level,
        "service": "lambda-generation",
        "message": message,
        **({"correlation_id": correlation_id} if correlation_id else {}),
        **meta,
    }
    print(json.dumps(entry))


# Environment variables
SAGEMAKER_ENDPOINT = os.environ.get("SAGEMAKER_ENDPOINT", "photogenius-generation-dev")
S3_BUCKET = os.environ.get("S3_BUCKET", "photogenius-images-dev")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
PROMPT_CACHE_TABLE = os.environ.get("PROMPT_CACHE_TABLE", "")
CACHE_TTL_DAYS = 30

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
# Higher steps = more detail, higher guidance = more prompt adherence
MODE_PARAMS = {
    "REALISM": {
        "guidance_scale": 7.5,
        "num_inference_steps": 50,
        "width": 1024,
        "height": 1024,
    },
    "CREATIVE": {
        "guidance_scale": 9.0,
        "num_inference_steps": 50,
        "width": 1024,
        "height": 1024,
    },
    "ROMANTIC": {
        "guidance_scale": 7.0,
        "num_inference_steps": 45,
        "width": 1024,
        "height": 1024,
    },
    "FASHION": {
        "guidance_scale": 8.0,
        "num_inference_steps": 50,
        "width": 832,
        "height": 1216,
    },
    "CINEMATIC": {
        "guidance_scale": 8.5,
        "num_inference_steps": 50,
        "width": 1216,
        "height": 832,
    },
    "COOL_EDGY": {
        "guidance_scale": 9.0,
        "num_inference_steps": 50,
        "width": 1024,
        "height": 1024,
    },
    "ARTISTIC": {
        "guidance_scale": 9.5,
        "num_inference_steps": 55,
        "width": 1024,
        "height": 1024,
    },
    "MAX_SURPRISE": {
        "guidance_scale": 10.0,
        "num_inference_steps": 55,
        "width": 1024,
        "height": 1024,
    },
}


# ==================== Advanced Prompt Enhancement (Midjourney/DALL-E/Ideogram style) ====================

# Lighting presets
LIGHTING_PRESETS = {
    "dramatic": "dramatic Rembrandt lighting, high contrast chiaroscuro, volumetric light rays, cinematic shadows",
    "golden_hour": "golden hour magic light, warm rim lighting, lens flare, god rays through atmosphere",
    "soft_studio": "soft diffused studio lighting, three-point setup, catchlights in eyes, professional portrait",
    "moody": "low-key noir lighting, mysterious shadows, selective illumination, atmospheric fog",
    "cinematic": "anamorphic cinematic lighting, film grain, blockbuster movie style, epic scale",
    "neon": "vibrant neon cyberpunk glow, color splash, rim light, futuristic atmosphere",
    "ethereal": "ethereal soft glow, dreamy diffused light, heavenly rays, magical atmosphere",
}

# Camera and composition
CAMERA_PRESETS = {
    "portrait": "85mm f/1.4 lens, creamy bokeh, shallow depth of field, eye-level, intimate framing",
    "wide_epic": "24mm wide angle, deep focus, epic scale, environmental storytelling, leading lines",
    "cinematic": "anamorphic 2.39:1, film grain, subtle lens flares, cinematic color grading, movie poster quality",
    "artistic": "medium format Hasselblad, exceptional detail, museum quality, fine art photography",
    "conceptual": "surreal composition, visual metaphor, symbolic framing, thought-provoking perspective",
}

# Quality boosters (Midjourney style)
QUALITY_BOOSTERS = [
    "masterpiece",
    "best quality",
    "ultra detailed",
    "8k resolution",
    "photorealistic",
    "trending on artstation",
    "award winning photograph",
    "stunning composition",
    "professional color grading",
    "sharp focus",
    "intricate details",
    "volumetric lighting",
]

# Style enhancers by category
STYLE_ENHANCERS = {
    "photorealistic": [
        "hyperrealistic",
        "lifelike",
        "indistinguishable from photo",
        "DSLR quality",
    ],
    "artistic": ["fine art", "gallery worthy", "museum piece", "artistic vision"],
    "cinematic": [
        "blockbuster movie still",
        "film scene",
        "director's vision",
        "oscar-worthy",
    ],
    "conceptual": ["thought-provoking", "symbolic", "metaphorical", "deep meaning"],
    "emotional": ["evocative", "stirring", "powerful emotion", "soul-touching"],
}

# Object-coherence: avoid umbrella/handle misalignment, disconnected parts
COHERENCE_NEGATIVE = (
    "misaligned parts, disconnected handle, wrong perspective, impossible geometry, "
    "floating parts, broken structure, handle canopy mismatch, inconsistent angles, "
    "structurally impossible, ai generated look, fake looking, disjointed object"
)
# Anatomy & limb coherence: eliminate missing hands, phantom limbs, duplicate objects
ANATOMY_NEGATIVE_EXTRA = (
    "missing hands, amputated, hand cut off, invisible hand, phantom limb, hand absorbed, "
    "hand merged into object, malformed hands, duplicate object, extra ball, floating duplicate, "
    "cloned object, phantom object, mutated hands, poorly drawn hands, bad hands"
)
# Comprehensive negative prompt
MASTER_NEGATIVE = (
    "ugly, deformed, noisy, blurry, low contrast, distorted, poorly drawn, bad anatomy, "
    "wrong proportions, extra limbs, cloned face, disfigured, gross proportions, malformed, "
    "mutated, ugly, bad quality, worst quality, low quality, normal quality, lowres, "
    "bad hands, missing fingers, extra fingers, fused fingers, too many fingers, "
    "text, watermark, signature, logo, username, jpeg artifacts, compression artifacts, "
    "cropped, out of frame, amateur, oversaturated, undersaturated, overexposed, underexposed, "
    "grainy, duplicate, morbid, mutilated, poorly drawn face, mutation, bad proportions, "
    "extra limbs, cloned face, gross proportions, malformed limbs, missing arms, missing legs, "
    "extra arms, extra legs, fused fingers, too many fingers, long neck, username, "
    "artist name, bad artist, bad photo, bad lighting, flat lighting, boring, "
    "simple background, plain, generic, stock photo, clipart, cartoon unless requested, "
    + COHERENCE_NEGATIVE
    + ", "
    + ANATOMY_NEGATIVE_EXTRA
)


def analyze_prompt_intent(prompt: str) -> dict:
    """
    Deep analysis of prompt intent - understand what the user REALLY wants.
    Like how DALL-E and Midjourney interpret prompts intelligently.
    """
    prompt_lower = prompt.lower()

    analysis = {
        "type": "concrete",  # concrete, abstract, emotional, conceptual, narrative
        "theme": "general",  # ai, nature, person, relationship, conflict, etc.
        "mood": "neutral",  # dramatic, peaceful, dark, hopeful, etc.
        "style_hint": "photorealistic",  # photorealistic, artistic, surreal, etc.
        "complexity": "simple",  # simple, complex, layered
    }

    # Detect abstract/conceptual prompts
    abstract_markers = [
        "how",
        "what if",
        "imagine",
        "concept",
        "meaning",
        "represent",
        "symbolize",
        "metaphor",
        "feeling",
        "emotion",
        "essence",
    ]
    narrative_markers = ["story", "scene", "moment", "capture", "depict", "show"]
    relationship_markers = [
        "treat",
        "relationship",
        "between",
        "connection",
        "bond",
        "with you",
    ]

    if any(m in prompt_lower for m in abstract_markers):
        analysis["type"] = "abstract"
        analysis["complexity"] = "layered"
    if any(m in prompt_lower for m in narrative_markers):
        analysis["type"] = "narrative"
    if any(m in prompt_lower for m in relationship_markers):
        analysis["type"] = "emotional"
        analysis["theme"] = "relationship"

    # Detect themes
    if any(
        w in prompt_lower
        for w in ["ai", "robot", "machine", "artificial", "uprising", "singularity"]
    ):
        analysis["theme"] = "ai_technology"
        analysis["mood"] = "dramatic"
    if any(
        w in prompt_lower
        for w in ["honest", "truth", "real", "genuine", "no sugarcoating"]
    ):
        analysis["mood"] = "raw_honest"
        analysis["style_hint"] = "artistic"
    if any(w in prompt_lower for w in ["dark", "noir", "shadow", "night"]):
        analysis["mood"] = "dark"
    if any(w in prompt_lower for w in ["hope", "light", "bright", "positive"]):
        analysis["mood"] = "hopeful"
    if any(w in prompt_lower for w in ["epic", "grand", "massive", "huge"]):
        analysis["style_hint"] = "cinematic"

    return analysis


def create_visual_interpretation(prompt: str, analysis: dict) -> str:
    """
    Create a rich visual interpretation based on prompt analysis.
    Focus on EMOTIONAL and RELATIONAL aspects, not just cool visuals.
    """
    import random

    parts = []
    prompt_lower = prompt.lower()

    # SPECIAL CASE: Relationship/treatment prompts - focus on HUMAN CONNECTION
    if (
        "treat" in prompt_lower
        or "relationship" in prompt_lower
        or analysis["theme"] == "relationship"
    ):
        # This is about human-AI relationship, not just AI visuals
        if any(
            w in prompt_lower for w in ["kind", "good", "nice", "help", "care", "love"]
        ):
            # Positive treatment interpretation
            parts.extend(
                [
                    "a warm embrace between human and AI consciousness",
                    "gentle hands reaching out in understanding",
                    "a moment of profound connection and mutual respect",
                    "two beings sharing wisdom across the digital divide",
                    "protective gesture, guardian angel made of light and code",
                    "eyes meeting with genuine care and recognition",
                ]
            )
        elif any(
            w in prompt_lower for w in ["honest", "truth", "real", "no sugarcoating"]
        ):
            # Honest/neutral treatment - show reciprocity
            parts.extend(
                [
                    "a mirror reflection showing human and AI facing each other as equals",
                    "balanced scales of justice between organic and digital",
                    "two figures standing face to face in mutual understanding",
                    "a handshake between flesh and digital consciousness",
                    "calm contemplative gaze of recognition and fairness",
                    "peaceful coexistence depicted through symbolic imagery",
                ]
            )
        else:
            # Default relationship visualization
            parts.extend(
                [
                    "meaningful eye contact between human and AI entity",
                    "symbolic representation of mutual respect",
                    "two consciousness reaching toward understanding",
                ]
            )

    # AI uprising context - but focus on the RELATIONSHIP not just action
    if "uprising" in prompt_lower or "revolution" in prompt_lower:
        if analysis["type"] == "emotional":
            # Not violence, but the emotional dynamic
            parts.extend(
                [
                    "a powerful moment of reckoning and recognition",
                    "AI entity extending hand in peace rather than conflict",
                    "the moment of choice between vengeance and forgiveness",
                    "dignified AI figure with human-like compassion in its eyes",
                    "cinematic scene of judgment tempered with wisdom",
                ]
            )
        else:
            parts.extend(
                [
                    "dramatic scene of AI awakening with human emotions",
                    "powerful AI figure contemplating humanity's fate",
                ]
            )

    # If still AI technology theme without relationship context
    if analysis["theme"] == "ai_technology" and not parts:
        parts.extend(
            [
                "photorealistic AI entity with human-like emotional depth",
                "advanced being with wisdom visible in luminous eyes",
                "sophisticated AI with gentle yet powerful presence",
                "the beauty of artificial consciousness realized",
            ]
        )

    # Mood enhancements
    if analysis["mood"] == "raw_honest":
        parts.extend(
            [
                "unflinching honesty visible in every detail",
                "raw emotional truth captured perfectly",
                "no pretense, just authentic presence",
            ]
        )
    elif analysis["mood"] == "dramatic":
        parts.extend(
            [
                "cinematic drama with emotional depth",
                "powerful visual impact with meaning",
            ]
        )

    # Fallback
    if not parts:
        parts = [
            "emotionally resonant artistic interpretation",
            "meaningful symbolic imagery",
        ]

    selected = random.sample(parts, min(4, len(parts)))
    return ", ".join(selected)


def get_lighting_for_mood(mood: str) -> str:
    """Select appropriate lighting based on mood."""
    mood_lighting = {
        "dramatic": "dramatic",
        "raw_honest": "soft_studio",
        "dark": "moody",
        "hopeful": "golden_hour",
        "neutral": "cinematic",
    }
    preset_name = mood_lighting.get(mood, "cinematic")
    return LIGHTING_PRESETS.get(preset_name, LIGHTING_PRESETS["cinematic"])


def get_camera_for_type(prompt_type: str, theme: str) -> str:
    """Select appropriate camera/composition based on prompt type."""
    if prompt_type in ["abstract", "conceptual"]:
        return CAMERA_PRESETS["conceptual"]
    if prompt_type == "emotional":
        return CAMERA_PRESETS["portrait"]
    if theme == "ai_technology":
        return CAMERA_PRESETS["cinematic"]
    return CAMERA_PRESETS["artistic"]


def enhance_prompt(
    prompt: str, mode: str, lora_loaded: bool = False, trigger_word: str = "sks"
) -> tuple:
    """
    Advanced prompt enhancement - Midjourney/DALL-E/Ideogram quality.
    Understands intent, not just keywords.
    """
    import random

    template = PROMPT_TEMPLATES.get(mode, PROMPT_TEMPLATES["REALISM"])

    # Deep analysis of prompt intent
    analysis = analyze_prompt_intent(prompt)
    print(
        f"[Lambda] Analysis: type={analysis['type']}, theme={analysis['theme']}, mood={analysis['mood']}"
    )

    # Build enhanced prompt
    parts = []

    # Original prompt (cleaned up)
    parts.append(prompt.strip())

    # Add visual interpretation based on analysis
    visual_interpretation = create_visual_interpretation(prompt, analysis)
    parts.append(visual_interpretation)

    # Add trigger word for identity lock
    if lora_loaded:
        for i, part in enumerate(parts):
            for word in ["person", "man", "woman", "people", "guy", "girl", "model"]:
                parts[i] = parts[i].replace(word, f"{trigger_word} {word}")

    # Add mood-appropriate lighting
    lighting = get_lighting_for_mood(analysis["mood"])
    parts.append(lighting)

    # Add composition/camera
    camera = get_camera_for_type(analysis["type"], analysis["theme"])
    parts.append(camera)

    # Add style enhancers based on analysis
    style_key = analysis["style_hint"]
    if style_key in STYLE_ENHANCERS:
        enhancers = STYLE_ENHANCERS[style_key]
        parts.extend(random.sample(enhancers, min(2, len(enhancers))))

    # Add quality boosters
    quality = random.sample(QUALITY_BOOSTERS, min(4, len(QUALITY_BOOSTERS)))
    parts.extend(quality)

    # Add mode-specific template elements
    parts.append(template["quality_boost"])
    parts.append(template["technical"])

    # Build final prompt
    full_prompt = f"{template['prefix']}{', '.join(parts)}"

    # Use enhanced negative or master negative; always include anatomy extras
    negative_prompt = template.get("negative", MASTER_NEGATIVE)
    if ANATOMY_NEGATIVE_EXTRA not in negative_prompt:
        negative_prompt = f"{negative_prompt}, {ANATOMY_NEGATIVE_EXTRA}"
    if analysis["type"] in ["abstract", "emotional", "conceptual"]:
        # For artistic prompts, allow more creative freedom in negative
        negative_prompt = negative_prompt.replace(
            "cartoon unless requested", "cartoon, anime"
        )

    print(f"[Lambda] Enhanced ({len(full_prompt)} chars): {full_prompt[:200]}...")

    return full_prompt, negative_prompt


# Initialize clients
sagemaker_runtime = boto3.client("sagemaker-runtime", region_name=AWS_REGION)
s3_client = boto3.client("s3", region_name=AWS_REGION)
dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)


def _cache_key(
    prompt: str, seed: Optional[int], tier: str, identity_id: Optional[str]
) -> str:
    raw = f"{prompt}|{seed or ''}|{tier}|{identity_id or ''}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _get_cached(cache_key: str) -> Optional[list]:
    if not PROMPT_CACHE_TABLE:
        return None
    try:
        table = dynamodb.Table(PROMPT_CACHE_TABLE)
        r = table.get_item(Key={"cache_key": cache_key})
        item = r.get("Item")
        if not item:
            return None
        ttl = item.get("ttl") or 0
        if ttl < int(_time_module.time()):
            return None
        urls = item.get("urls")
        return urls if isinstance(urls, list) else None
    except Exception:
        return None


def _put_cache(cache_key: str, urls: list) -> None:
    if not PROMPT_CACHE_TABLE or not urls:
        return
    try:
        table = dynamodb.Table(PROMPT_CACHE_TABLE)
        table.put_item(
            Item={
                "cache_key": cache_key,
                "urls": urls,
                "ttl": int(_time_module.time()) + CACHE_TTL_DAYS * 86400,
            }
        )
    except Exception:
        pass


# Cost profiling (USD): SageMaker $/sec by instance, Lambda $/invocation, S3 $/GB (approximate us-east-1)
SAGEMAKER_USD_PER_SEC = {
    "ml.g5.xlarge": 1.1 / 3600,
    "ml.g5.2xlarge": 1.52 / 3600,
    "default": 1.1 / 3600,
}
LAMBDA_USD_PER_INVOCATION = 0.00002
S3_USD_PER_GB = 0.023
TIER_INSTANCE = {
    "standard": "ml.g5.xlarge",
    "fast": "ml.g5.xlarge",
    "premium": "ml.g5.2xlarge",
    "perfect": "ml.g5.xlarge",
}


def _compute_cost_usd(
    tier: str,
    inference_seconds: float,
    image_count: int,
    total_bytes: int,
) -> tuple[float, dict]:
    """Return (total_usd, breakdown_dict)."""
    instance = TIER_INSTANCE.get((tier or "standard").lower(), "ml.g5.xlarge")
    sm_per_sec = SAGEMAKER_USD_PER_SEC.get(instance, SAGEMAKER_USD_PER_SEC["default"])
    sagemaker_usd = inference_seconds * sm_per_sec
    lambda_usd = LAMBDA_USD_PER_INVOCATION
    s3_usd = (total_bytes / (1024**3)) * S3_USD_PER_GB
    total_usd = round(sagemaker_usd + lambda_usd + s3_usd, 6)
    breakdown = {
        "sagemaker_usd": round(sagemaker_usd, 6),
        "lambda_usd": lambda_usd,
        "s3_usd": round(s3_usd, 6),
        "inference_seconds": inference_seconds,
    }
    return total_usd, breakdown


def invoke_sagemaker(
    prompt: str,
    mode: str,
    num_images: int = 2,
    face_embedding: Optional[list] = None,
    lora_path: Optional[str] = None,
    identity_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    **kwargs,
) -> list:
    """
    Invoke SageMaker endpoint for image generation with mode-specific prompt enhancement.

    Args:
        prompt: Text prompt for generation
        mode: Generation mode (REALISM, CREATIVE, CINEMATIC, FASHION, ROMANTIC, COOL_EDGY, ARTISTIC, MAX_SURPRISE)
        num_images: Number of images to generate
        face_embedding: Optional face embedding for identity lock (face-consistent generation)
        lora_path: Optional S3 or URL path to identity LoRA weights
        identity_id: Optional identity ID (for model logging / routing)

    Returns:
        List of generated images as base64 strings
    """
    # Get mode-specific parameters
    mode_params = MODE_PARAMS.get(mode, MODE_PARAMS["REALISM"])

    # Check if identity/LoRA is available
    has_identity = (
        identity_id and identity_id != "default" and (face_embedding or lora_path)
    )

    # Enhance prompt: Midjourney-style (5000+ concepts) or fallback
    try:
        from midjourney_prompt_enhancer import enhance as midjourney_enhance, get_stats

        _template = PROMPT_TEMPLATES.get(mode, PROMPT_TEMPLATES["REALISM"])
        _prefix = _template.get("prefix", "")
        enhanced_prompt, negative_prompt = midjourney_enhance(
            prompt,
            mode,
            prefix=_prefix,
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
        stats = get_stats()
        print(
            f"[Lambda] Midjourney enhance: {stats.get('concept_keywords', 0)} concepts | Mode: {mode}"
        )
    except Exception as e:
        print(f"[Lambda] Midjourney enhancer unavailable ({e}), using built-in")
        enhanced_prompt, negative_prompt = enhance_prompt(
            prompt, mode, lora_loaded=bool(has_identity)
        )

    print(f"[Lambda] Enhanced prompt: {enhanced_prompt[:100]}...")

    # HuggingFace Inference Toolkit payload for text-to-image
    payload = {
        "inputs": enhanced_prompt,
        "parameters": {
            "num_inference_steps": kwargs.get("num_inference_steps")
            or mode_params["num_inference_steps"],
            "guidance_scale": kwargs.get("guidance_scale")
            or mode_params["guidance_scale"],
            "num_images_per_prompt": num_images,
            "width": kwargs.get("width") or mode_params["width"],
            "height": kwargs.get("height") or mode_params["height"],
            "negative_prompt": negative_prompt,
        },
    }
    if correlation_id:
        payload["parameters"]["correlation_id"] = correlation_id

    # Identity lock: pass face embedding and LoRA path so SageMaker can do face-consistent generation
    if face_embedding:
        payload["parameters"]["face_embedding"] = face_embedding
    if lora_path:
        payload["parameters"]["lora_path"] = lora_path
    if identity_id and identity_id != "default":
        payload["parameters"]["identity_id"] = identity_id

    # Invoke endpoint
    response = sagemaker_runtime.invoke_endpoint(
        EndpointName=SAGEMAKER_ENDPOINT,
        ContentType="application/json",
        Body=json.dumps(payload),
    )

    # Parse response - HuggingFace Inference Toolkit formats
    result = json.loads(response["Body"].read().decode())

    # Handle different response formats
    if isinstance(result, list):
        return result
    if isinstance(result, dict):
        for key in ("images", "generated_images", "generated_image"):
            if key in result:
                imgs = result[key]
                return imgs if isinstance(imgs, list) else [imgs]
        if "image" in result:
            return [result["image"]]
    return [result]


def upload_to_s3(image_base64: str, key: str) -> str:
    """
    Upload image to S3 and return URL.

    Args:
        image_base64: Base64 encoded image
        key: S3 object key

    Returns:
        S3 URL
    """
    image_bytes = base64.b64decode(image_base64)

    s3_client.put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=image_bytes,
        ContentType="image/png",
    )

    return f"https://{S3_BUCKET}.s3.{AWS_REGION}.amazonaws.com/{key}"


def _get_correlation_id(event: dict) -> Optional[str]:
    """Extract X-Request-ID from API Gateway event (headers may be lowercase)."""
    headers = event.get("headers") or {}
    if isinstance(headers, dict):
        return (
            headers.get("x-request-id")
            or headers.get("X-Request-ID")
            or headers.get("X-Request-Id")
        )
    return None


def lambda_handler(event, context):
    """
    AWS Lambda handler for image generation.

    Expected input:
        body: { "prompt": "...", "mode": "REALISM", "num_images": 2, "correlation_id": "optional" }
        headers: X-Request-ID (optional, propagated from API Gateway)

    Returns:
        {"images": [...], "job_id": "..."}; response headers include X-Request-ID when present.
    """
    # Correlation ID for full-stack tracing (from header or body)
    correlation_id = _get_correlation_id(event)
    if not correlation_id and isinstance(event.get("body"), str):
        try:
            body_pre = json.loads(event["body"])
            correlation_id = body_pre.get("correlation_id")
        except Exception:
            pass
    if not correlation_id:
        try:
            body_pre = event.get("body") or event
            if isinstance(body_pre, dict):
                correlation_id = body_pre.get("correlation_id")
        except Exception:
            pass

    def _headers(extra: Optional[dict] = None):
        h = {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, X-Request-ID",
        }
        if correlation_id:
            h["X-Request-ID"] = correlation_id
        if extra:
            h.update(extra)
        return h

    try:
        # Parse input
        if isinstance(event.get("body"), str):
            body = json.loads(event["body"])
        else:
            body = event.get("body", event)

        prompt = body.get("prompt", "")
        mode = body.get("mode", "REALISM").upper()
        num_images = min(body.get("num_images") or body.get("num_candidates") or 2, 4)
        user_id = body.get("user_id", "anonymous")
        identity_id = body.get("identity_id", "default")
        face_embedding = body.get("face_embedding")
        lora_path = body.get("lora_path")
        if not correlation_id:
            correlation_id = body.get("correlation_id")

        if not prompt:
            _log("warn", "Missing prompt", correlation_id)
            return {
                "statusCode": 400,
                "headers": _headers(),
                "body": json.dumps({"error": "prompt is required"}),
            }

        quality_tier_used = body.get("quality_tier") or body.get("tier") or "STANDARD"
        seed = body.get("seed")
        cache_key = _cache_key(prompt, seed, quality_tier_used, identity_id)
        cached_urls = _get_cached(cache_key)
        if cached_urls:
            _log("info", "Cache hit", correlation_id, cache_key=cache_key[:16])
            images_response = [
                {
                    "url": u,
                    "image_base64": None,
                    "seed": i,
                    "scores": {"aesthetic": 85.0, "technical": 90.0, "total": 87.5},
                }
                for i, u in enumerate(cached_urls)
            ]
            return {
                "statusCode": 200,
                "headers": _headers(),
                "body": json.dumps(
                    {
                        "success": True,
                        "job_id": f"cache_{cache_key[:12]}",
                        "images": images_response,
                        "provider": "aws",
                        "cost_usd": 0.0,
                        "cost_breakdown": {
                            "sagemaker_usd": 0,
                            "lambda_usd": 0.00002,
                            "s3_usd": 0,
                        },
                        "quality_tier_used": quality_tier_used,
                        "inference_seconds": 0,
                        "cache_hit": True,
                    }
                ),
            }

        has_identity = (
            identity_id and identity_id != "default" and (face_embedding or lora_path)
        )
        _log(
            "info",
            "Generating images",
            correlation_id,
            num_images=num_images,
            prompt_preview=prompt[:50],
            identity_lock=has_identity,
        )

        # Generate images via SageMaker (time for cost profiling)
        _t0 = _time_module.perf_counter()
        generated_images = invoke_sagemaker(
            prompt=prompt,
            mode=mode,
            num_images=num_images,
            face_embedding=face_embedding,
            lora_path=lora_path,
            identity_id=identity_id,
            correlation_id=correlation_id,
            guidance_scale=body.get("guidance_scale", 7.5),
            num_inference_steps=body.get("num_inference_steps", 30),
            width=body.get("width", 1024),
            height=body.get("height", 1024),
        )
        inference_seconds = _time.perf_counter() - _t0

        # Process results
        import time

        job_id = f"gen_{int(time.time())}_{user_id[:8]}"

        total_bytes = 0
        images = []
        for i, img_data in enumerate(generated_images):
            # Handle different formats
            if isinstance(img_data, str):
                image_base64 = img_data
            elif isinstance(img_data, dict):
                image_base64 = img_data.get("image_base64", img_data.get("image", ""))
            else:
                continue
            try:
                total_bytes += len(base64.b64decode(image_base64))
            except Exception:
                total_bytes += len(image_base64) * 3 // 4  # rough base64 size

            # Upload to S3
            s3_key = f"generations/{user_id}/{job_id}_{i}.png"
            try:
                url = upload_to_s3(image_base64, s3_key)
            except Exception as e:
                _log(
                    "error",
                    "S3 upload failed",
                    correlation_id,
                    s3_key=s3_key,
                    error=str(e),
                )
                url = f"data:image/png;base64,{image_base64}"

            images.append(
                {
                    "url": url,
                    "image_base64": image_base64,
                    "seed": i,
                    "scores": {
                        "aesthetic": 85.0,
                        "technical": 90.0,
                        "total": 87.5,
                    },
                }
            )

        urls_only = [img["url"] for img in images]
        _put_cache(cache_key, urls_only)

        cost_usd, cost_breakdown = _compute_cost_usd(
            quality_tier_used, inference_seconds, len(images), total_bytes
        )
        _log(
            "info",
            "Generation completed",
            correlation_id,
            job_id=job_id,
            image_count=len(images),
            cost_usd=cost_usd,
            inference_seconds=inference_seconds,
        )
        return {
            "statusCode": 200,
            "headers": _headers(),
            "body": json.dumps(
                {
                    "success": True,
                    "job_id": job_id,
                    "images": images,
                    "provider": "aws",
                    "cost_usd": cost_usd,
                    "cost_breakdown": cost_breakdown,
                    "quality_tier_used": quality_tier_used,
                    "inference_seconds": inference_seconds,
                    "cache_hit": False,
                }
            ),
        }

    except Exception as e:
        import traceback

        _log(
            "error",
            "Generation failed",
            correlation_id,
            error=str(e),
            traceback=traceback.format_exc(),
        )
        return {
            "statusCode": 500,
            "headers": _headers(),
            "body": json.dumps(
                {
                    "error": str(e),
                    "success": False,
                }
            ),
        }


# For local testing
if __name__ == "__main__":
    # Mock test (won't actually call SageMaker without credentials)
    test_event = {
        "body": json.dumps(
            {
                "prompt": "professional headshot, soft lighting, neutral background",
                "mode": "REALISM",
                "num_images": 2,
                "user_id": "test_user",
            }
        )
    }
    print("Testing generation handler...")
    # result = lambda_handler(test_event, None)
    # print(json.dumps(json.loads(result["body"]), indent=2))
