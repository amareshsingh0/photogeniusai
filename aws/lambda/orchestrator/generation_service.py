"""
Generation Service - Main Entry Point for Image Generation

Self-contained Modal service. No relative imports.
Uses @app.cls with @modal.enter() for model pre-loading.
Web endpoint is a class method to reuse the warm container (no double GPU).
"""

import modal  # type: ignore[reportMissingImports]
from pathlib import Path
import io
import base64
from typing import Any, List, Dict, Optional, TYPE_CHECKING
import warnings

try:
    from .instantid_service import generate_with_instantid, app as instantid_app
except ImportError:
    generate_with_instantid = None  # type: ignore[assignment, misc]
    instantid_app = None  # type: ignore[assignment]

if TYPE_CHECKING:
    from PIL import Image
    import numpy as np

app = modal.App("photogenius-generation")

# ==================== Modal Config ====================
MODEL_DIR = "/models"
LORA_DIR = "/loras"

models_volume = modal.Volume.from_name("photogenius-models", create_if_missing=True)
lora_volume = modal.Volume.from_name("photogenius-loras", create_if_missing=True)

gpu_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "torch==2.4.1",
        "torchvision==0.19.1",
        "diffusers==0.30.3",
        "transformers==4.44.2",
        "accelerate==0.34.2",
        "safetensors==0.4.5",
        "peft==0.12.0",
        "bitsandbytes==0.43.3",
        "xformers==0.0.28.post1",
        "insightface==0.7.3",
        "onnxruntime-gpu==1.18.0",
        "opencv-python==4.9.0.80",
        "pillow==10.2.0",
        "numpy==1.26.3",
        "scipy==1.12.0",
        "compel==2.0.2",
        "fastapi[standard]",
    )
    .run_commands(
        "apt-get update",
        "apt-get install -y libgl1-mesa-glx libglib2.0-0",
    )
)

# ==================== Prompt Templates ====================
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

# ==================== Advanced Prompt Enhancement (Midjourney/DALL-E style) ====================

LIGHTING_PRESETS = {
    "dramatic": "dramatic Rembrandt lighting, high contrast chiaroscuro, volumetric light rays",
    "golden_hour": "golden hour magic light, warm rim lighting, lens flare, god rays",
    "moody": "low-key noir lighting, mysterious shadows, selective illumination",
    "cinematic": "anamorphic cinematic lighting, film grain, blockbuster movie style",
    "neon": "vibrant neon cyberpunk glow, color splash, rim light, futuristic",
    "ethereal": "ethereal soft glow, dreamy diffused light, magical atmosphere",
}

CAMERA_PRESETS = {
    "portrait": "85mm f/1.4 lens, creamy bokeh, shallow depth of field",
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

STYLE_ENHANCERS = {
    "photorealistic": ["hyperrealistic", "lifelike", "DSLR quality"],
    "artistic": ["fine art", "gallery worthy", "artistic vision"],
    "cinematic": ["blockbuster movie still", "film scene"],
    "conceptual": ["thought-provoking", "symbolic", "metaphorical"],
}

# Anatomy & limb coherence: prevent missing hands, phantom limbs, duplicate objects
ANATOMY_NEGATIVE_EXTRA = (
    "missing hands, amputated, hand cut off, invisible hand, phantom limb, hand absorbed, "
    "hand merged into object, malformed hands, duplicate object, extra ball, floating duplicate, "
    "cloned object, phantom object, mutated hands, poorly drawn hands, bad hands, "
    "missing arms, missing legs, extra limbs, six fingers, seven fingers, fused fingers"
)
HEAD_AND_COUNT_NEGATIVE = (
    "missing head, headless, head cut off, no face, head obscured, extra head, two heads, "
    "merged heads, merged bodies, headless figure, body without head, bad spatial arrangement, "
    "impossible pose, impossible physics, floating limbs, disconnected body parts, "
    "head absorbed by umbrella, face cut off by object, extra arm, arm from back, third arm"
)
MULTI_PERSON_NEGATIVE_EXTRA = "wrong number of people, merged figures, wrong depth order, body merging, jumbled figures"
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
    "every figure has two hands only",
    "correct number of people",
    "natural grouping",
    "logical placement",
    "proper depth order",
    "realistic physics",
    "each face visible",
    "no merged bodies",
    "one head per person",
    "two arms per person",
    "coherent multi-figure composition",
]


def analyze_prompt_intent(prompt: str) -> dict:
    """Deep analysis of prompt intent."""
    prompt_lower = prompt.lower()
    analysis = {
        "type": "concrete",
        "theme": "general",
        "mood": "neutral",
        "style_hint": "photorealistic",
        "has_person_or_body": False,
        "has_multiple_people": False,
    }
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
        "friends",
        "couple",
        "siblings",
        "gathering",
    ]
    if any(m in prompt_lower for m in multi_person_markers):
        analysis["has_multiple_people"] = True
        if analysis["theme"] == "general":
            analysis["theme"] = "multi_person"
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
    ]
    if any(m in prompt_lower for m in person_body_markers):
        analysis["has_person_or_body"] = True
    if any(
        m in prompt_lower
        for m in ["how", "what if", "imagine", "concept", "meaning", "feeling"]
    ):
        analysis["type"] = "abstract"
    if any(
        m in prompt_lower for m in ["treat", "relationship", "between", "connection"]
    ):
        analysis["type"] = "emotional"
        analysis["theme"] = "relationship"
    if any(
        w in prompt_lower for w in ["ai", "robot", "machine", "artificial", "uprising"]
    ):
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

    # RELATIONSHIP prompts - human connection focus
    if (
        "treat" in prompt_lower
        or "relationship" in prompt_lower
        or analysis["theme"] == "relationship"
    ):
        if any(
            w in prompt_lower for w in ["honest", "truth", "real", "no sugarcoating"]
        ):
            parts.extend(
                [
                    "mirror reflection showing human and AI as equals",
                    "balanced scales between organic and digital",
                    "two figures face to face in mutual understanding",
                    "handshake between flesh and digital consciousness",
                ]
            )
        else:
            parts.extend(
                [
                    "meaningful eye contact between human and AI",
                    "symbolic representation of mutual respect",
                ]
            )

    # AI uprising - relationship dynamic
    if "uprising" in prompt_lower:
        if analysis["type"] == "emotional":
            parts.extend(
                [
                    "powerful moment of reckoning and recognition",
                    "AI extending hand in peace rather than conflict",
                    "dignified AI with human-like compassion",
                ]
            )

    if analysis["theme"] == "ai_technology" and not parts:
        parts.extend(
            [
                "photorealistic AI with human-like emotional depth",
                "sophisticated AI with gentle powerful presence",
            ]
        )

    if analysis["mood"] == "raw_honest":
        parts.extend(["unflinching honesty in every detail"])
    elif analysis["mood"] == "dramatic":
        parts.extend(["cinematic drama with emotional depth"])

    return (
        ", ".join(random.sample(parts, min(3, len(parts))))
        if parts
        else "emotionally resonant artistic interpretation"
    )


def intelligent_enhance_prompt(
    prompt: str, mode: str, lora_loaded: bool = False, trigger_word: str = "sks"
) -> tuple:
    """Advanced prompt enhancement - Midjourney/DALL-E quality."""
    import random

    template = PROMPT_TEMPLATES.get(mode, PROMPT_TEMPLATES["REALISM"])
    analysis = analyze_prompt_intent(prompt)

    print(
        f"[Enhance] Analysis: type={analysis['type']}, theme={analysis['theme']}, mood={analysis['mood']}"
    )

    parts = [prompt.strip()]
    parts.append(create_visual_interpretation(prompt, analysis))
    if analysis.get("has_multiple_people"):
        parts.extend(
            random.sample(
                MULTI_PERSON_POSITIVE_BOOSTERS,
                min(8, len(MULTI_PERSON_POSITIVE_BOOSTERS)),
            )
        )
    if analysis.get("has_person_or_body"):
        parts.extend(
            random.sample(
                ANATOMY_POSITIVE_BOOSTERS, min(5, len(ANATOMY_POSITIVE_BOOSTERS))
            )
        )
    if lora_loaded:
        for i, part in enumerate(parts):
            for word in ["person", "man", "woman", "people", "guy", "girl", "model"]:
                parts[i] = parts[i].replace(word, f"{trigger_word} {word}")

    # Add mood-appropriate lighting
    mood_lighting = {
        "dramatic": "dramatic",
        "raw_honest": "ethereal",
        "neutral": "cinematic",
    }
    parts.append(
        LIGHTING_PRESETS.get(
            mood_lighting.get(analysis["mood"], "cinematic"),
            LIGHTING_PRESETS["cinematic"],
        )
    )

    # Add composition
    type_camera = {
        "abstract": "conceptual",
        "emotional": "portrait",
        "concrete": "artistic",
    }
    parts.append(
        CAMERA_PRESETS.get(
            type_camera.get(analysis["type"], "artistic"), CAMERA_PRESETS["artistic"]
        )
    )

    # Add style enhancers
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
    print(f"[Enhance] Final ({len(full_prompt)} chars): {full_prompt[:150]}...")
    neg = template["negative"]
    if ANATOMY_NEGATIVE_EXTRA not in neg:
        neg = f"{neg}, {ANATOMY_NEGATIVE_EXTRA}"
    if HEAD_AND_COUNT_NEGATIVE not in neg and (
        analysis.get("has_person_or_body") or analysis.get("has_multiple_people")
    ):
        neg = f"{neg}, {HEAD_AND_COUNT_NEGATIVE}"
    if analysis.get("has_multiple_people") and MULTI_PERSON_NEGATIVE_EXTRA not in neg:
        neg = f"{neg}, {MULTI_PERSON_NEGATIVE_EXTRA}"
    return full_prompt, neg


def get_controlnet_scale(mode: str) -> float:
    """Mode-specific ControlNet conditioning strength for InstantID."""
    scales = {
        "REALISM": 0.92,  # Maximum face control
        "CREATIVE": 0.68,  # More creative freedom
        "ROMANTIC": 0.78,
        "FASHION": 0.85,
        "CINEMATIC": 0.72,
    }
    return scales.get(mode, 0.80)


# Mode-specific generation parameters (optimized for Midjourney-like quality)
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


def score_image(image, face_embedding, mode: str) -> Dict:
    """Score generated image on face match, aesthetics, and technical quality"""
    import cv2  # type: ignore[reportMissingImports]
    import numpy as np  # type: ignore[reportMissingImports]
    from PIL import Image as PILImage  # type: ignore[reportMissingImports]

    scores = {"face_match": 0.0, "aesthetic": 0.0, "technical": 0.0, "total": 0.0}
    img_array = np.array(image)

    # Face Match
    if face_embedding is not None:
        try:
            from insightface.app import FaceAnalysis  # type: ignore[reportMissingImports]

            face_app = FaceAnalysis(name="buffalo_l")
            face_app.prepare(ctx_id=0, det_size=(640, 640))
            faces = face_app.get(img_array)
            if len(faces) > 0:
                face = sorted(
                    faces,
                    key=lambda x: (x.bbox[2] - x.bbox[0]) * (x.bbox[3] - x.bbox[1]),
                )[-1]
                gen_emb = face.embedding
                ref_emb = np.array(face_embedding)
                similarity = np.dot(gen_emb, ref_emb) / (
                    np.linalg.norm(gen_emb) * np.linalg.norm(ref_emb)
                )
                scores["face_match"] = float(similarity * 100)
            else:
                scores["face_match"] = 0.0
        except Exception as e:
            print(f"[WARN] Face scoring error: {e}")
            scores["face_match"] = 50.0
    else:
        scores["face_match"] = 50.0

    # Aesthetic Score
    brightness = img_array.mean() / 255.0
    brightness_score = 1.0 - abs(brightness - 0.45) * 2
    contrast = img_array.std() / 255.0
    contrast_score = min(contrast * 2.2, 1.0)
    hsv = cv2.cvtColor(img_array, cv2.COLOR_RGB2HSV)
    saturation = hsv[:, :, 1].mean() / 255.0
    saturation_score = min(saturation * 1.5, 1.0)
    hue_std = hsv[:, :, 0].std() / 180.0
    harmony_score = max(0, 1.0 - hue_std)
    aesthetic_score = (
        brightness_score * 0.2
        + contrast_score * 0.3
        + saturation_score * 0.25
        + harmony_score * 0.25
    ) * 100
    scores["aesthetic"] = float(max(0, aesthetic_score))

    # Technical Quality
    gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    sharpness = min(laplacian_var / 800, 1.0)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    noise = np.abs(gray.astype(float) - blurred.astype(float)).mean() / 255.0
    noise_score = max(0, 1.0 - noise * 5)
    technical_score = (sharpness * 0.6 + noise_score * 0.4) * 100
    scores["technical"] = float(max(0, technical_score))

    # Total Score (mode-specific weights)
    weights = {
        "REALISM": (0.50, 0.30, 0.20),
        "CREATIVE": (0.25, 0.50, 0.25),
        "ROMANTIC": (0.40, 0.40, 0.20),
        "FASHION": (0.35, 0.40, 0.25),
        "CINEMATIC": (0.20, 0.50, 0.30),
        "COOL_EDGY": (0.25, 0.45, 0.30),
        "ARTISTIC": (0.20, 0.55, 0.25),
        "MAX_SURPRISE": (0.20, 0.50, 0.30),
    }
    w = weights.get(mode, weights["REALISM"])
    scores["total"] = float(
        scores["face_match"] * w[0]
        + scores["aesthetic"] * w[1]
        + scores["technical"] * w[2]
    )
    return scores


@app.cls(
    image=gpu_image,
    gpu="A100",
    scaledown_window=300,
    timeout=600,
    volumes={
        MODEL_DIR: models_volume,
        LORA_DIR: lora_volume,
    },
    secrets=[
        modal.Secret.from_name("huggingface"),
    ],
)
class GenerationService:
    """Generation service with pre-loaded SDXL model for instant warm starts"""

    @modal.enter()
    def load_models(self):
        """Load once, reuse forever in warm container"""
        import os

        import torch  # type: ignore[reportMissingImports]
        from diffusers import StableDiffusionXLPipeline  # type: ignore[reportMissingImports]
        from compel import Compel, ReturnedEmbeddingsType  # type: ignore[reportMissingImports]

        print("\n[*] Pre-loading SDXL model (container warm-up)...")

        hf_token = os.environ.get("HUGGINGFACE_TOKEN") or os.environ.get("HF_TOKEN")
        model_path = Path(f"{MODEL_DIR}/sdxl-base")

        try:
            if model_path.exists() and any(model_path.iterdir()):
                print("[*] Using cached model")
                model_repo = str(model_path)
            else:
                raise FileNotFoundError("Model not cached")
        except (FileNotFoundError, OSError):
            print("[*] Downloading SDXL from HuggingFace (first run)...")
            model_repo = "stabilityai/stable-diffusion-xl-base-1.0"

        pretrained_kwargs = {
            "torch_dtype": torch.float16,
            "variant": "fp16",
            "use_safetensors": True,
            "cache_dir": MODEL_DIR,
        }
        if hf_token:
            pretrained_kwargs["token"] = hf_token

        self.pipe = StableDiffusionXLPipeline.from_pretrained(
            model_repo, **pretrained_kwargs
        ).to("cuda")

        try:
            self.pipe.enable_xformers_memory_efficient_attention()
            print("[OK] xformers enabled")
        except Exception:
            print("[WARN] xformers not available")
        try:
            self.pipe.enable_vae_tiling()
        except Exception:
            pass

        try:
            self.compel = Compel(
                tokenizer=[self.pipe.tokenizer, self.pipe.tokenizer_2],
                text_encoder=[self.pipe.text_encoder, self.pipe.text_encoder_2],
                returned_embeddings_type=ReturnedEmbeddingsType.PENULTIMATE_HIDDEN_STATES_NON_NORMALIZED,
                requires_pooled=[False, True],
            )
            self.use_compel = True
            print("[OK] Compel prompt weighting enabled")
        except Exception as e:
            print(f"[WARN] Compel not available: {e}")
            self.compel = None
            self.use_compel = False

        # Warmup to pre-compile CUDA kernels
        print("[*] Pre-compiling model (warmup generation)...")
        try:
            with torch.inference_mode():
                generator = torch.Generator("cuda").manual_seed(42)
                _ = self.pipe(
                    prompt="warmup",
                    num_inference_steps=1,
                    guidance_scale=1.0,
                    height=512,
                    width=512,
                    generator=generator,
                    output_type="latent",
                )
            print("[OK] Model pre-compiled - CUDA kernels ready")
        except Exception as e:
            print(f"[WARN] Warmup failed (non-critical): {e}")

        print("[OK] Models pre-loaded, container warm and ready")

    @modal.method()
    def generate_images(
        self,
        user_id: str,
        identity_id: str,
        prompt: str,
        mode: str = "REALISM",
        num_candidates: int = 4,
        guidance_scale: Optional[float] = None,
        num_inference_steps: Optional[int] = None,
        seed: Optional[int] = None,
        face_embedding: Optional[List[float]] = None,
    ):
        """Generate images using pre-loaded SDXL with optional LoRA"""
        from PIL import Image  # type: ignore[reportMissingImports]
        import torch  # type: ignore[reportMissingImports]
        import numpy as np  # type: ignore[reportMissingImports]

        print(f"[*] Starting generation for {identity_id}")
        print(f"[*] Prompt: {prompt}")
        print(f"[*] Mode: {mode}, Candidates: {num_candidates}")

        # Mode-specific params
        mode_params = MODE_PARAMS.get(mode, MODE_PARAMS["REALISM"])
        if guidance_scale is None:
            guidance_scale = mode_params["guidance_scale"]
        if num_inference_steps is None:
            num_inference_steps = mode_params["num_inference_steps"]
        gen_width = mode_params["width"]
        gen_height = mode_params["height"]

        # Load LoRA
        print("\n[*] Loading LoRA weights...")
        lora_path = f"{LORA_DIR}/{user_id}/{identity_id}"
        lora_dir = Path(lora_path)
        lora_loaded = False

        if lora_dir.exists() and lora_dir.is_dir():
            try:
                self.pipe.load_lora_weights(str(lora_dir))
                lora_loaded = True
                print(f"[OK] LoRA loaded from {lora_path}")
            except Exception as e:
                print(f"[WARN] Failed to load LoRA: {e}")
        else:
            # Also try .safetensors direct path
            safetensors_path = f"{LORA_DIR}/{user_id}/{identity_id}.safetensors"
            if Path(safetensors_path).exists():
                try:
                    self.pipe.load_lora_weights(safetensors_path)
                    lora_loaded = True
                    print(f"[OK] LoRA loaded from {safetensors_path}")
                except Exception as e:
                    print(f"[WARN] Failed to load LoRA: {e}")
            else:
                print("[INFO] No LoRA found, using base model")

        # Load face embedding from training data if available
        if face_embedding is None:
            embedding_path = Path(
                f"{LORA_DIR}/{user_id}/{identity_id}/face_embedding.npy"
            )
            if embedding_path.exists():
                try:
                    import numpy as np  # type: ignore[reportMissingImports]

                    face_embedding = np.load(str(embedding_path)).tolist()
                    print(f"[OK] Loaded face embedding from training data")
                except Exception as e:
                    print(f"[WARN] Failed to load face embedding: {e}")

        # Build enhanced prompt: Midjourney-style (5000+ concepts) or fallback
        try:
            from midjourney_prompt_enhancer import (
                enhance as midjourney_enhance,
                get_stats,
            )

            _prefix = PROMPT_TEMPLATES.get(mode, PROMPT_TEMPLATES["REALISM"]).get(
                "prefix", ""
            )
            full_prompt, negative_prompt = midjourney_enhance(
                prompt,
                mode,
                prefix=_prefix,
                max_concept_adds=10,
                include_lighting=True,
                include_camera=True,
                include_quality=True,
                quality_count=4,
                trigger_word="sks" if lora_loaded else None,
                identity_words=(
                    ["person", "man", "woman", "people", "guy", "girl", "model"]
                    if lora_loaded
                    else None
                ),
            )
            stats = get_stats()
            print(
                f"[OK] Midjourney enhance: {stats.get('concept_keywords', 0)} concepts | Prompt: {full_prompt[:150]}..."
            )
        except Exception as e:
            print(f"[WARN] Midjourney enhancer unavailable ({e}), using built-in")
            full_prompt, negative_prompt = intelligent_enhance_prompt(
                prompt=prompt, mode=mode, lora_loaded=lora_loaded, trigger_word="sks"
            )
            print(f"[OK] Enhanced Prompt: {full_prompt[:150]}...")

        # Generate candidates
        print(
            f"\n[*] Generating {num_candidates} candidates at {gen_width}x{gen_height}..."
        )
        candidates = []

        for i in range(num_candidates):
            current_seed = (
                int(seed) + i
                if seed is not None
                else torch.randint(0, 2**32, (1,)).item()
            )
            if not isinstance(current_seed, int):
                current_seed = int(current_seed)
            generator = torch.Generator("cuda").manual_seed(current_seed)
            print(f"  [{i+1}/{num_candidates}] seed={current_seed}...")

            with torch.inference_mode():
                if self.use_compel and self.compel is not None:
                    conditioning, pooled = self.compel(full_prompt)  # type: ignore[misc]
                    neg_conditioning, neg_pooled = self.compel(negative_prompt)  # type: ignore[misc]
                    image = self.pipe(
                        prompt_embeds=conditioning,
                        pooled_prompt_embeds=pooled,
                        negative_prompt_embeds=neg_conditioning,
                        negative_pooled_prompt_embeds=neg_pooled,
                        num_inference_steps=num_inference_steps,
                        guidance_scale=guidance_scale,
                        height=gen_height,
                        width=gen_width,
                        generator=generator,
                    ).images[0]
                else:
                    image = self.pipe(
                        prompt=full_prompt,
                        negative_prompt=negative_prompt,
                        num_inference_steps=num_inference_steps,
                        guidance_scale=guidance_scale,
                        height=gen_height,
                        width=gen_width,
                        generator=generator,
                    ).images[0]

            buffered = io.BytesIO()
            image.save(buffered, format="PNG", quality=95)
            img_base64 = base64.b64encode(buffered.getvalue()).decode()

            candidates.append(
                {
                    "image_base64": img_base64,
                    "seed": current_seed,
                    "prompt": full_prompt,
                    "negative_prompt": negative_prompt,
                }
            )
            print(f"  [OK] Candidate {i+1} done")

        # Unload LoRA after generation
        if lora_loaded:
            try:
                self.pipe.unload_lora_weights()
                print("[OK] LoRA unloaded")
            except Exception:
                pass

        print(f"\n[OK] Generated {len(candidates)} candidates")

        # Score images
        print("\n[*] Scoring images...")
        scored_candidates = []
        for idx, candidate in enumerate(candidates):
            img_bytes = base64.b64decode(candidate["image_base64"])
            from PIL import Image as PILImage  # type: ignore[reportMissingImports]

            image = PILImage.open(io.BytesIO(img_bytes))
            scores = score_image(image, face_embedding, mode)
            scored_candidates.append({**candidate, "scores": scores})
            print(
                f"  [{idx+1}] Face={scores['face_match']:.1f} Aesthetic={scores['aesthetic']:.1f} "
                f"Technical={scores['technical']:.1f} Total={scores['total']:.1f}"
            )

        # Select best
        scored_candidates.sort(key=lambda x: x["scores"]["total"], reverse=True)
        num_to_return = min(2, len(scored_candidates))
        best = scored_candidates[:num_to_return]

        print(f"\n[OK] Returning top {num_to_return} images")
        for i, c in enumerate(best):
            label = (
                "Best" if i == 0 else f"{i+1}{'nd' if i==1 else 'rd' if i==2 else 'th'}"
            )
            print(f"   {label}: Total={c['scores']['total']:.1f}")

        return best

    @modal.fastapi_endpoint(method="POST", label="generate-images-web")
    def generate_images_web(self, item: dict):
        """
        Web endpoint - runs on the SAME warm container with pre-loaded model.
        No double GPU cost because this is a class method, not a separate @app.function.
        """
        result = self.generate_images.local(  # type: ignore[reportAttributeAccessIssue]
            user_id=item.get("user_id", ""),
            identity_id=item.get("identity_id", ""),
            prompt=item.get("prompt", ""),
            mode=item.get("mode", "REALISM"),
            num_candidates=item.get("num_candidates", 4),
            guidance_scale=item.get("guidance_scale"),
            num_inference_steps=item.get("num_inference_steps"),
            seed=item.get("seed"),
            face_embedding=item.get("face_embedding"),
        )
        return result


def generate_image(
    prompt: str,
    identity_id: Optional[str] = None,
    user_id: str = "",
    mode: str = "REALISM",
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Generate a single image using LoRA-only flow (no InstantID).
    Deprecated: use generate_image_v2() for InstantID support and face consistency.
    """
    warnings.warn(
        "generate_image() is deprecated; use generate_image_v2() for InstantID support.",
        DeprecationWarning,
        stacklevel=2,
    )
    best = GenerationService().generate_images.remote(  # type: ignore[reportAttributeAccessIssue]
        user_id=user_id,
        identity_id=identity_id or "",
        prompt=prompt,
        mode=mode,
        **{
            k: v
            for k, v in kwargs.items()
            if k
            in (
                "num_candidates",
                "guidance_scale",
                "num_inference_steps",
                "seed",
                "face_embedding",
            )
        },
    )
    return best[0] if best else {}


def generate_image_v2(
    prompt: str,
    identity_id: Optional[str] = None,
    user_id: str = "",
    mode: str = "REALISM",
    use_instantid: bool = True,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Generate image with optional InstantID for 99%+ face accuracy.
    When identity_id is set and use_instantid=True, uses InstantID; otherwise falls back to LoRA-only.
    """
    if (
        identity_id
        and use_instantid
        and generate_with_instantid is not None
        and instantid_app is not None
    ):
        face_image_path = f"/loras/{user_id}/{identity_id}/reference_face.jpg"
        lora_path = f"/loras/{user_id}/{identity_id}.safetensors"
        controlnet_scale = get_controlnet_scale(mode)
        template = PROMPT_TEMPLATES.get(mode, PROMPT_TEMPLATES["REALISM"])
        negative_prompt = template.get("negative", "")
        mode_params = MODE_PARAMS.get(mode, MODE_PARAMS["REALISM"])
        pil_image = generate_with_instantid(
            prompt=prompt,
            face_image_path=face_image_path,
            lora_path=lora_path,
            controlnet_conditioning_scale=controlnet_scale,
            negative_prompt=negative_prompt,
            num_inference_steps=kwargs.get("num_inference_steps", 50),
            guidance_scale=kwargs.get(
                "guidance_scale", mode_params.get("guidance_scale", 8.5)
            ),
            width=kwargs.get("width", mode_params["width"]),
            height=kwargs.get("height", mode_params["height"]),
            seed=kwargs.get("seed"),
            stub=instantid_app.InstantIDService,
        )
        buffered = io.BytesIO()
        pil_image.save(buffered, format="PNG", quality=95)
        img_base64 = base64.b64encode(buffered.getvalue()).decode()
        return {
            "image_base64": img_base64,
            "seed": kwargs.get("seed"),
            "prompt": prompt,
            "negative_prompt": negative_prompt,
        }
    return generate_image(
        prompt=prompt,
        identity_id=identity_id,
        user_id=user_id,
        mode=mode,
        **kwargs,
    )


@app.local_entrypoint()
def test_generation():
    """Test image generation"""
    print("\n[INFO] Generation Test")
    print("=" * 50)

    service = GenerationService()
    result = service.generate_images.remote(  # type: ignore[reportAttributeAccessIssue]
        user_id="test_user",
        identity_id="test_identity_1",
        prompt="professional headshot of person in business suit",
        mode="REALISM",
        num_candidates=2,
        seed=42,
    )

    print(f"\n[OK] Generated {len(result)} images")
    for idx, img in enumerate(result):
        print(
            f"  Image {idx+1}: Seed={img.get('seed')}, Scores={img.get('scores', {})}"
        )
        try:
            img_bytes = base64.b64decode(img["image_base64"])
            from PIL import Image  # type: ignore[reportMissingImports]

            test_img = Image.open(io.BytesIO(img_bytes))
            test_img.save(f"test_output_{idx+1}.png")
            print(f"  Saved: test_output_{idx+1}.png")
        except Exception as e:
            print(f"  [WARN] Save failed: {e}")
