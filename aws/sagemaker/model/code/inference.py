"""
Simplified working inference handler.
Uses only SDXL-Turbo and Base (no Refiner to avoid compatibility issues).
Downloads models from S3 on first use.
"""

import json
import io
import base64
import os
import gc
import subprocess
from typing import Dict, Any, Optional
from pathlib import Path

# Global models
models = {}
MODEL_DIR = None
S3_BUCKET = None
MODELS_CACHE = "/tmp/models"  # Cache models in /tmp


def model_fn(model_dir):
    """Load models on startup."""
    global MODEL_DIR, S3_BUCKET
    MODEL_DIR = model_dir
    S3_BUCKET = os.environ.get("MODELS_S3_BUCKET", "photogenius-models-dev")

    print(f"Model directory: {model_dir}")
    print(f"S3 bucket: {S3_BUCKET}")
    print(f"Models cache: {MODELS_CACHE}")

    # Create cache directory
    Path(MODELS_CACHE).mkdir(parents=True, exist_ok=True)

    print("Inference handler initialized")
    return {"initialized": True}


def download_model_from_s3(model_name: str) -> str:
    """Download model from S3 if not cached."""
    import boto3

    cache_path = os.path.join(MODELS_CACHE, model_name)

    # Check if already cached
    if os.path.exists(cache_path) and os.path.exists(os.path.join(cache_path, "model_index.json")):
        print(f"Model '{model_name}' found in cache: {cache_path}")
        return cache_path

    # Download from S3
    print(f"Downloading model '{model_name}' from S3...")
    s3 = boto3.client("s3")
    s3_prefix = f"models/{model_name}/"

    # List all files in the model directory
    paginator = s3.get_paginator("list_objects_v2")
    pages = paginator.paginate(Bucket=S3_BUCKET, Prefix=s3_prefix)

    file_count = 0
    for page in pages:
        if "Contents" not in page:
            continue
        for obj in page["Contents"]:
            s3_key = obj["Key"]
            # Get relative path within model directory
            rel_path = s3_key[len(s3_prefix):]
            if not rel_path:  # Skip directory itself
                continue

            local_path = os.path.join(cache_path, rel_path)
            os.makedirs(os.path.dirname(local_path), exist_ok=True)

            # Download file
            s3.download_file(S3_BUCKET, s3_key, local_path)
            file_count += 1

            if file_count % 10 == 0:
                print(f"Downloaded {file_count} files...")

    print(f"Downloaded {file_count} files for '{model_name}'")
    return cache_path


def load_single_model(model_name: str):
    """Load a specific model."""
    global models

    if model_name in models:
        print(f"Model '{model_name}' already loaded")
        return models[model_name]

    import torch
    from diffusers import AutoPipelineForText2Image, DPMSolverMultistepScheduler

    print(f"Loading {model_name}...")

    # Model name mapping
    model_map = {
        "turbo": "sdxl-turbo",
        "base": "sdxl-base-1.0",
    }

    s3_model_name = model_map[model_name]

    # Download model from S3 (or use cached)
    model_path = download_model_from_s3(s3_model_name)
    print(f"Loading from: {model_path}")

    load_kwargs = {
        "torch_dtype": torch.float16,
        "variant": "fp16",
        "use_safetensors": True,
        "local_files_only": True,
    }

    pipeline = AutoPipelineForText2Image.from_pretrained(
        model_path, **load_kwargs
    )

    if model_name == "base":
        pipeline.scheduler = DPMSolverMultistepScheduler.from_config(
            pipeline.scheduler.config, use_karras_sigmas=True
        )

    pipeline = pipeline.to("cuda")
    pipeline.enable_attention_slicing()
    pipeline.enable_vae_slicing()

    models[model_name] = pipeline
    print(f"✓ {model_name} loaded")

    return pipeline


def clear_gpu_memory():
    """Free GPU memory."""
    import torch
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.synchronize()


def input_fn(request_body, content_type="application/json"):
    """Parse input."""
    return json.loads(request_body) if content_type == "application/json" else {}


def predict_fn(data: Dict[str, Any], config: Dict) -> Dict[str, Any]:
    """Generate image based on tier."""
    import torch
    from PIL import Image

    prompt = data.get("inputs") or data.get("prompt", "")
    tier = (data.get("quality_tier") or "STANDARD").upper()
    negative = data.get("parameters", {}).get("negative_prompt") or data.get("negative_prompt", "")
    width = data.get("parameters", {}).get("width") or data.get("width", 1024)
    height = data.get("parameters", {}).get("height") or data.get("height", 1024)
    seed = data.get("parameters", {}).get("seed") or data.get("seed")

    if seed:
        torch.manual_seed(seed)

    if not negative:
        negative = (
            "ugly, blurry, low quality, distorted, deformed, bad anatomy, "
            "poorly drawn hands, poorly drawn face, worst quality, jpeg artifacts"
        )

    print(f"Request: tier={tier}, prompt='{prompt[:50]}...'")

    try:
        if tier == "FAST":
            # Turbo: 4 steps
            pipeline = load_single_model("turbo")
            image = pipeline(
                prompt=prompt,
                negative_prompt=negative,
                num_inference_steps=4,
                guidance_scale=1.0,
                width=width,
                height=height,
            ).images[0]

            return {
                "image_base64": image_to_base64(image),
                "metadata": {"tier": "FAST", "model": "sdxl-turbo", "steps": 4}
            }

        elif tier == "STANDARD":
            # Base: 30 steps
            # Clear turbo if loaded
            if "turbo" in models:
                del models["turbo"]
                clear_gpu_memory()

            pipeline = load_single_model("base")
            image = pipeline(
                prompt=prompt,
                negative_prompt=negative,
                num_inference_steps=30,
                guidance_scale=7.5,
                width=width,
                height=height,
            ).images[0]

            return {
                "image_base64": image_to_base64(image),
                "metadata": {"tier": "STANDARD", "model": "sdxl-base", "steps": 30}
            }

        elif tier == "PREMIUM":
            # Base: 50 steps (high quality, no refiner)
            # Clear turbo if loaded
            if "turbo" in models:
                del models["turbo"]
                clear_gpu_memory()

            pipeline = load_single_model("base")
            image = pipeline(
                prompt=prompt,
                negative_prompt=negative,
                num_inference_steps=50,  # More steps for premium
                guidance_scale=8.0,       # Stronger guidance
                width=width,
                height=height,
            ).images[0]

            return {
                "image_base64": image_to_base64(image),
                "metadata": {
                    "tier": "PREMIUM",
                    "model": "sdxl-base",
                    "steps": 50,
                    "note": "High-quality generation without refiner"
                }
            }

        else:
            return {"error": f"Invalid tier: {tier}"}

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return {"error": str(e)}


def image_to_base64(image: "Image.Image") -> str:
    """Convert PIL Image to base64."""
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode("utf-8")


def output_fn(prediction, content_type="application/json"):
    """Format output."""
    return (json.dumps(prediction), content_type) if content_type == "application/json" else ("", "")
