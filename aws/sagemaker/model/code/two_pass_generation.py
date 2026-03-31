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
from typing import Any, Dict, Optional

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


def generate_two_pass(
    prompt: str,
    identity_id: Optional[str] = None,
    user_id: str = "",
    negative_prompt: str = "",
    return_preview: bool = True,
    seed: Optional[int] = None,
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

    # ----- Pass 2: Full quality (SDXL Base 50 steps, 1024x1024 + optional LoRA) -----
    full_pipe = None
    full_image = None
    t1 = time.perf_counter()
    try:
        full_pipe = _load_base_pipeline()
        if identity_id and user_id:
            lora_path = f"{LORA_DIR}/{user_id}/{identity_id}.safetensors"
            lora_dir = f"{LORA_DIR}/{user_id}/{identity_id}"
            if Path(lora_path).exists():
                try:
                    full_pipe.load_lora_weights(lora_path)
                    print(f"[OK] LoRA loaded: {lora_path}")
                except Exception as e:
                    print(f"[WARN] LoRA load failed: {e}")
            elif Path(lora_dir).exists():
                try:
                    full_pipe.load_lora_weights(lora_dir)
                    print(f"[OK] LoRA loaded: {lora_dir}")
                except Exception as e:
                    print(f"[WARN] LoRA load failed: {e}")

        full_image = full_pipe(
            prompt=prompt,
            negative_prompt=negative_prompt or "",
            num_inference_steps=50,
            guidance_scale=8.5,
            width=1024,
            height=1024,
            generator=generator,
        ).images[0]

        if identity_id:
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
