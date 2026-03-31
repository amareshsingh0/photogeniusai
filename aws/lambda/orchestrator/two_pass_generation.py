"""
Two-Pass Generation Pipeline for MidJourney-level results.

Designed for AWS (SageMaker / GPU container). No Modal dependency.
- Pass 1: SDXL Turbo (4 steps, ~5s) for fast preview
- Pass 2: SDXL Base (50 steps, 1024x1024) + optional LoRA
- Pass 3: SDXL Refiner img2img (25 steps) for final polish

Environment: Set MODEL_DIR, LORA_DIR (default /models, /loras).
Models: sdxl-turbo, stable-diffusion-xl-base-1.0, stable-diffusion-xl-refiner-1.0
(can be local paths under MODEL_DIR or HuggingFace IDs).
"""

from __future__ import annotations

import io
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Optional PIL for type hints
try:
    from PIL import Image  # type: ignore[reportMissingImports]
except ImportError:
    Image = None  # type: ignore[assignment, misc]

MODEL_DIR = os.environ.get("MODEL_DIR", "/models")
LORA_DIR = os.environ.get("LORA_DIR", "/loras")

# Model path or HuggingFace ID
SDXL_TURBO_PATH = os.environ.get("SDXL_TURBO_PATH", "/models/sdxl-turbo")
SDXL_BASE_PATH = os.environ.get("SDXL_BASE_PATH", "/models/stable-diffusion-xl-base-1.0")
SDXL_REFINER_PATH = os.environ.get("SDXL_REFINER_PATH", "/models/stable-diffusion-xl-refiner-1.0")
HF_TOKEN = os.environ.get("HUGGINGFACE_TOKEN") or os.environ.get("HF_TOKEN")

# Optional InstantID for Pass 2 (90%+ face accuracy when available)
try:
    from .instantid_service import generate_with_instantid, app as instantid_app
except ImportError:
    try:
        from instantid_service import generate_with_instantid, app as instantid_app
    except ImportError:
        generate_with_instantid = None  # type: ignore[assignment, misc]
        instantid_app = None  # type: ignore[assignment]


def get_controlnet_scale(mode: str) -> float:
    """Mode-specific ControlNet conditioning strength for InstantID."""
    scales = {
        "REALISM": 0.92,
        "CREATIVE": 0.68,
        "ROMANTIC": 0.78,
        "FASHION": 0.85,
        "CINEMATIC": 0.72,
    }
    return scales.get(mode.upper() if mode else "", 0.80)


def _resolve_model_path(local_path: str, hf_id: str) -> str:
    """Use local path if it exists and has model files, else HuggingFace ID."""
    p = Path(local_path)
    if p.exists() and (p / "model_index.json").exists():
        return local_path
    return hf_id


def _load_turbo_pipeline():
    """Load SDXL Turbo for Pass 1. guidance_scale=1, 4 steps."""
    import torch
    from diffusers import StableDiffusionXLPipeline

    turbo_hf = "stabilityai/sdxl-turbo"
    model_path = _resolve_model_path(SDXL_TURBO_PATH, turbo_hf)

    kwargs = {"torch_dtype": torch.float16, "use_safetensors": True}
    if HF_TOKEN:
        kwargs["token"] = HF_TOKEN
    try:
        pipe = StableDiffusionXLPipeline.from_pretrained(model_path, variant="fp16", **kwargs)
    except Exception:
        pipe = StableDiffusionXLPipeline.from_pretrained(model_path, **kwargs)
    pipe = pipe.to("cuda")
    pipe.enable_attention_slicing()
    pipe.enable_vae_slicing()
    return pipe


def _load_base_pipeline():
    """Load SDXL Base for Pass 2. Optional LoRA loaded by caller."""
    import torch
    from diffusers import StableDiffusionXLPipeline

    base_hf = "stabilityai/stable-diffusion-xl-base-1.0"
    model_path = _resolve_model_path(SDXL_BASE_PATH, base_hf)

    kwargs = {"torch_dtype": torch.float16, "variant": "fp16", "use_safetensors": True}
    if HF_TOKEN:
        kwargs["token"] = HF_TOKEN

    pipe = StableDiffusionXLPipeline.from_pretrained(model_path, **kwargs)
    pipe = pipe.to("cuda")
    pipe.enable_attention_slicing()
    pipe.enable_vae_slicing()
    return pipe


def _load_refiner_pipeline():
    """Load SDXL Refiner img2img for Pass 3."""
    import torch
    from diffusers import StableDiffusionXLImg2ImgPipeline

    refiner_hf = "stabilityai/stable-diffusion-xl-refiner-1.0"
    model_path = _resolve_model_path(SDXL_REFINER_PATH, refiner_hf)

    kwargs = {"torch_dtype": torch.float16, "variant": "fp16", "use_safetensors": True}
    if HF_TOKEN:
        kwargs["token"] = HF_TOKEN

    pipe = StableDiffusionXLImg2ImgPipeline.from_pretrained(model_path, **kwargs)
    pipe = pipe.to("cuda")
    pipe.enable_attention_slicing()
    pipe.enable_vae_slicing()
    return pipe


def generate_fast(
    prompt: str,
    negative_prompt: str = "",
    seed: Optional[int] = None,
) -> Dict[str, Any]:
    """
    FAST tier: SDXL Turbo only (4 steps, ~5s). Returns preview as final.
    """
    import torch

    if not prompt or not prompt.strip():
        return {
            "preview": None,
            "final": None,
            "preview_time": 0.0,
            "final_time": 0.0,
            "error": "prompt is required",
        }

    generator = torch.Generator("cuda").manual_seed(seed) if seed is not None else None
    turbo_pipe = None
    try:
        t0 = time.perf_counter()
        turbo_pipe = _load_turbo_pipeline()
        preview = turbo_pipe(
            prompt=prompt,
            num_inference_steps=4,
            guidance_scale=1.0,
            width=512,
            height=512,
            generator=generator,
        ).images[0]
        preview_time = time.perf_counter() - t0
        print(f"✅ FAST (Turbo) generated in {preview_time:.2f}s")
    except Exception as e:
        print(f"⚠️ generate_fast failed: {e}")
        return {
            "preview": None,
            "final": None,
            "preview_time": 0.0,
            "final_time": 0.0,
            "error": str(e),
        }
    finally:
        if turbo_pipe is not None:
            del turbo_pipe
        torch.cuda.empty_cache()

    buf = io.BytesIO()
    preview.save(buf, format="PNG", quality=95)
    import base64
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    return {
        "preview": preview,
        "final": preview,
        "preview_time": preview_time,
        "final_time": 0.0,
        "preview_base64": b64,
        "final_base64": b64,
    }


def generate_two_pass(
    prompt: str,
    identity_id: Optional[str] = None,
    user_id: str = "",
    negative_prompt: str = "",
    return_preview: bool = True,
    seed: Optional[int] = None,
    use_instantid: bool = False,
    mode: str = "REALISM",
    style_lora: Optional[str] = None,
    lora_names: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Run two-pass pipeline: fast preview (Turbo) then full quality (Base + Refiner).

    Parameters
    ----------
    prompt : str
        Enhanced text prompt.
    identity_id : str, optional
        If set, load LoRA from /loras/{user_id}/{identity_id}.safetensors for Pass 2.
    user_id : str
        Used for LoRA path resolution.
    style_lora : str, optional
        If set, load style LoRA from LORA_DIR/styles/{style_lora}/ for Pass 2 (e.g. cinematic, anime).
    lora_names : list of str, optional
        Auto-LoRA names from SmartPromptEngine.recommend_loras(); only LoRAs that exist under
        LORA_DIR/styles/{name}/ or LORA_DIR/{name}/ are loaded (max 3).
    negative_prompt : str
        Negative prompt for Pass 2 (and refiner).
    return_preview : bool
        If True, run Pass 1 and include preview in result. If False, only run Pass 2+3.
    seed : int, optional
        Random seed for reproducibility.

    Returns
    -------
    dict
        - preview: PIL Image (512x512) or None if skipped/failed
        - final: PIL Image (1024x1024), refined
        - preview_time: float seconds (0 if skipped)
        - final_time: float seconds
        - preview_base64: str (optional, if return_preview and preview exists)
        - final_base64: str (optional, for JSON APIs)
    """
    import torch

    if not prompt or not prompt.strip():
        return {
            "preview": None,
            "final": None,
            "preview_time": 0.0,
            "final_time": 0.0,
            "error": "prompt is required",
        }

    generator = None
    if seed is not None:
        generator = torch.Generator("cuda").manual_seed(seed)

    preview: Optional[Any] = None
    preview_time = 0.0
    final_time = 0.0

    # ----- Pass 1: Fast preview (SDXL Turbo, 4 steps, ~5s) -----
    turbo_pipe = None
    if return_preview:
        try:
            t0 = time.perf_counter()
            turbo_pipe = _load_turbo_pipeline()
            preview = turbo_pipe(
                prompt=prompt,
                num_inference_steps=4,
                guidance_scale=1.0,
                width=512,
                height=512,
                generator=generator,
            ).images[0]
            preview_time = time.perf_counter() - t0
            print(f"✅ Preview generated in {preview_time:.2f}s")
        except Exception as e:
            print(f"⚠️ Preview skipped (SDXL Turbo): {e}")
            preview = None
        finally:
            if turbo_pipe is not None:
                del turbo_pipe
            torch.cuda.empty_cache()

    # ----- Pass 2: Full quality (InstantID if identity_id+use_instantid, else SDXL Base + optional LoRA) -----
    full_pipe = None
    full_image = None
    t1 = time.perf_counter()
    try:
        if identity_id and user_id and use_instantid and generate_with_instantid is not None and instantid_app is not None:
            try:
                face_image_path = f"{LORA_DIR}/{user_id}/{identity_id}/reference_face.jpg"
                lora_path = f"{LORA_DIR}/{user_id}/{identity_id}.safetensors"
                controlnet_scale = get_controlnet_scale(mode)
                full_image = generate_with_instantid(
                    prompt=prompt,
                    face_image_path=face_image_path,
                    lora_path=lora_path if Path(lora_path).exists() else None,
                    negative_prompt=negative_prompt or "",
                    controlnet_conditioning_scale=controlnet_scale,
                    stub=instantid_app.InstantIDService,
                )
                if hasattr(full_image, "convert"):
                    full_image = full_image.convert("RGB")
                print("[OK] Pass 2: InstantID")
            except Exception as e:
                print(f"⚠️ InstantID failed, falling back to LoRA: {e}")
                full_image = None
        if full_image is None:
            full_pipe = _load_base_pipeline()
            lora_loaded_identity = False
            lora_loaded_style = False
            if identity_id and user_id:
                lora_path = f"{LORA_DIR}/{user_id}/{identity_id}.safetensors"
                lora_dir = f"{LORA_DIR}/{user_id}/{identity_id}"
                if Path(lora_path).exists():
                    try:
                        full_pipe.load_lora_weights(lora_path)
                        lora_loaded_identity = True
                        print(f"[OK] LoRA loaded: {lora_path}")
                    except Exception as e:
                        print(f"[WARN] LoRA load failed: {e}")
                elif Path(lora_dir).exists():
                    try:
                        full_pipe.load_lora_weights(lora_dir)
                        lora_loaded_identity = True
                        print(f"[OK] LoRA loaded: {lora_dir}")
                    except Exception as e:
                        print(f"[WARN] LoRA load failed: {e}")
            # Auto-LoRA from recommend_loras (only load those that exist; max 3)
            if lora_names:
                for name in lora_names[:3]:
                    style_dir = f"{LORA_DIR}/styles/{name}"
                    alt_dir = f"{LORA_DIR}/{name}"
                    style_file = Path(style_dir) / "lora.safetensors"
                    alt_file = Path(alt_dir) / "lora.safetensors"
                    loaded = False
                    if style_file.exists():
                        try:
                            full_pipe.load_lora_weights(str(style_file))
                            lora_loaded_style = True
                            loaded = True
                            print(f"[OK] Auto-LoRA loaded: {style_file}")
                        except Exception as e:
                            print(f"[WARN] Auto-LoRA load failed for {name}: {e}")
                    elif Path(style_dir).exists():
                        try:
                            full_pipe.load_lora_weights(style_dir)
                            lora_loaded_style = True
                            loaded = True
                            print(f"[OK] Auto-LoRA loaded: {style_dir}")
                        except Exception as e:
                            print(f"[WARN] Auto-LoRA load failed for {name}: {e}")
                    elif alt_file.exists():
                        try:
                            full_pipe.load_lora_weights(str(alt_file))
                            lora_loaded_style = True
                            loaded = True
                            print(f"[OK] Auto-LoRA loaded: {alt_file}")
                        except Exception as e:
                            print(f"[WARN] Auto-LoRA load failed for {name}: {e}")
                    elif Path(alt_dir).exists():
                        try:
                            full_pipe.load_lora_weights(alt_dir)
                            lora_loaded_style = True
                            loaded = True
                            print(f"[OK] Auto-LoRA loaded: {alt_dir}")
                        except Exception as e:
                            print(f"[WARN] Auto-LoRA load failed for {name}: {e}")
                    if not loaded:
                        print(f"[INFO] Auto-LoRA not found (skipped): {name}")
            elif style_lora:
                style_dir = f"{LORA_DIR}/styles/{style_lora}"
                style_file = Path(style_dir) / "lora.safetensors"
                if style_file.exists():
                    try:
                        full_pipe.load_lora_weights(str(style_file))
                        lora_loaded_style = True
                        print(f"[OK] Style LoRA loaded: {style_file}")
                    except Exception as e:
                        print(f"[WARN] Style LoRA load failed: {e}")
                elif Path(style_dir).exists():
                    try:
                        full_pipe.load_lora_weights(style_dir)
                        lora_loaded_style = True
                        print(f"[OK] Style LoRA loaded: {style_dir}")
                    except Exception as e:
                        print(f"[WARN] Style LoRA load failed: {e}")

            full_image = full_pipe(
                prompt=prompt,
                negative_prompt=negative_prompt or "",
                num_inference_steps=50,
                guidance_scale=8.5,
                width=1024,
                height=1024,
                generator=generator,
            ).images[0]

            if identity_id or style_lora or lora_loaded_style:
                try:
                    full_pipe.unload_lora_weights()
                except Exception:
                    pass
    except Exception as e:
        if full_pipe is not None:
            try:
                del full_pipe
            except Exception:
                pass
        torch.cuda.empty_cache()
        return {
            "preview": preview,
            "final": None,
            "preview_time": preview_time,
            "final_time": 0.0,
            "error": str(e),
        }
    finally:
        if full_pipe is not None:
            del full_pipe
        torch.cuda.empty_cache()

    # ----- Pass 3: Img2Img refinement (25 steps, strength 0.3) -----
    refiner = None
    try:
        refiner = _load_refiner_pipeline()
        refined = refiner(
            prompt=prompt,
            image=full_image,
            num_inference_steps=25,
            strength=0.3,
            generator=generator,
        ).images[0]
        final_image = refined
    except Exception as e:
        print(f"⚠️ Refiner skipped, using full image: {e}")
        final_image = full_image
    finally:
        if refiner is not None:
            del refiner
        torch.cuda.empty_cache()

    final_time = time.perf_counter() - t1
    print(f"✅ Final generated in {final_time:.2f}s")

    # Optional base64 for JSON APIs
    def _pil_to_base64(im: Any) -> str:
        buf = io.BytesIO()
        im.save(buf, format="PNG", quality=95)
        import base64
        return base64.b64encode(buf.getvalue()).decode("utf-8")

    result = {
        "preview": preview,
        "final": final_image,
        "preview_time": preview_time,
        "final_time": final_time,
    }
    if preview is not None:
        result["preview_base64"] = _pil_to_base64(preview)
    result["final_base64"] = _pil_to_base64(final_image)
    return result
