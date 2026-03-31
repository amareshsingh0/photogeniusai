"""
Memory-Optimized SageMaker inference handler.

Strategy: Load only ONE model at a time to fit in 22GB GPU memory.
- FAST tier: Load Turbo only
- STANDARD tier: Unload Turbo, load Base
- PREMIUM tier: Load Base, generate, unload, load Refiner, refine

This ensures we never exceed GPU memory limits.
"""

import json
import io
import base64
import os
import gc
from typing import Dict, Any, Optional
import subprocess

# Global state
current_model = None
current_model_name = None


def model_fn(model_dir):
    """
    Initial setup - don't load models yet.
    We'll load them on-demand in predict_fn based on tier.
    """
    print("Memory-optimized inference handler initialized")
    print("Models will be loaded on-demand per request")

    # Just return configuration
    return {
        "s3_bucket": os.environ.get("MODELS_S3_BUCKET", "photogenius-models-dev"),
        "device": "cuda",
        "models_loaded": False,
    }


def load_model(model_name: str, config: Dict):
    """Load a specific model on-demand."""
    global current_model, current_model_name

    # If already loaded, return it
    if current_model_name == model_name and current_model is not None:
        print(f"Model '{model_name}' already loaded")
        return current_model

    # Unload previous model to free memory
    if current_model is not None:
        print(f"Unloading previous model: {current_model_name}")
        del current_model
        current_model = None
        current_model_name = None
        gc.collect()

        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()

    # Load new model
    import torch
    from diffusers import AutoPipelineForText2Image, DPMSolverMultistepScheduler

    s3_bucket = config["s3_bucket"]
    device = config["device"]

    print(f"Loading model: {model_name}")

    # Map model names to HF IDs and S3 paths
    model_map = {
        "turbo": {
            "hf_id": "stabilityai/sdxl-turbo",
            "s3_prefix": "models/sdxl-turbo",
        },
        "base": {
            "hf_id": "stabilityai/stable-diffusion-xl-base-1.0",
            "s3_prefix": "models/sdxl-base-1.0",
        },
        "refiner": {
            "hf_id": "stabilityai/stable-diffusion-xl-refiner-1.0",
            "s3_prefix": "models/sdxl-refiner-1.0",
        },
    }

    if model_name not in model_map:
        raise ValueError(f"Unknown model: {model_name}")

    model_info = model_map[model_name]

    # Try S3 first
    local_path = download_from_s3(s3_bucket, model_info["s3_prefix"])

    if local_path:
        print(f"Loading from S3 cache: {local_path}")
        source = local_path
    else:
        print(f"Loading from HuggingFace: {model_info['hf_id']}")
        source = model_info["hf_id"]

    # Load model
    load_kwargs = {
        "torch_dtype": torch.float16,
        "variant": "fp16",
        "use_safetensors": True,
    }

    pipeline = AutoPipelineForText2Image.from_pretrained(source, **load_kwargs)

    # Use better scheduler for non-Turbo models
    if model_name != "turbo":
        pipeline.scheduler = DPMSolverMultistepScheduler.from_config(
            pipeline.scheduler.config,
            use_karras_sigmas=True,
        )

    # Move to GPU
    pipeline = pipeline.to(device)

    # Enable memory optimizations
    pipeline.enable_attention_slicing()
    pipeline.enable_vae_slicing()

    # Try model offloading for even more memory savings
    try:
        pipeline.enable_model_cpu_offload()
    except:
        pass

    current_model = pipeline
    current_model_name = model_name

    print(f"✓ Model loaded: {model_name}")
    return pipeline


def download_from_s3(bucket: str, prefix: str) -> Optional[str]:
    """Download model from S3 to local cache."""
    try:
        local_path = f"/tmp/models/{prefix.split('/')[-1]}"
        os.makedirs(os.path.dirname(local_path), exist_ok=True)

        # Check if already downloaded
        if os.path.exists(os.path.join(local_path, "model_index.json")):
            print(f"Model already cached: {local_path}")
            return local_path

        # Check if exists in S3
        check_cmd = ["aws", "s3", "ls", f"s3://{bucket}/{prefix}/model_index.json"]
        result = subprocess.run(check_cmd, capture_output=True, timeout=10)

        if result.returncode != 0:
            return None

        print(f"Downloading from S3: s3://{bucket}/{prefix}")
        subprocess.run(
            ["aws", "s3", "sync", f"s3://{bucket}/{prefix}", local_path],
            check=True,
            timeout=300,
        )

        if os.path.exists(os.path.join(local_path, "model_index.json")):
            return local_path
        return None

    except Exception as e:
        print(f"S3 download failed: {e}")
        return None


def input_fn(request_body, content_type="application/json"):
    """Parse input."""
    if content_type == "application/json":
        return json.loads(request_body)
    raise ValueError(f"Unsupported content type: {content_type}")


def predict_fn(data: Dict[str, Any], config: Dict) -> Dict[str, Any]:
    """
    Memory-optimized prediction with on-demand model loading.
    """
    import torch
    from PIL import Image

    # Extract parameters
    prompt = data.get("inputs") or data.get("prompt", "")
    quality_tier = (data.get("quality_tier") or data.get("tier", "STANDARD")).upper()
    negative_prompt = data.get("parameters", {}).get("negative_prompt") or data.get("negative_prompt", "")
    width = data.get("parameters", {}).get("width") or data.get("width", 1024)
    height = data.get("parameters", {}).get("height") or data.get("height", 1024)
    seed = data.get("parameters", {}).get("seed") or data.get("seed")

    print(f"Generation request: tier={quality_tier}, prompt='{prompt[:50]}...'")

    # Set seed
    if seed:
        torch.manual_seed(seed)

    # Default negative prompt
    if not negative_prompt:
        negative_prompt = (
            "ugly, tiling, poorly drawn hands, poorly drawn feet, poorly drawn face, "
            "out of frame, mutation, mutated, extra limbs, disfigured, deformed, "
            "blurry, bad art, bad anatomy, worst quality, low quality, jpeg artifacts"
        )

    # FAST tier: Turbo only
    if quality_tier == "FAST":
        pipeline = load_model("turbo", config)

        image = pipeline(
            prompt=prompt,
            negative_prompt=negative_prompt,
            num_inference_steps=4,
            guidance_scale=1.0,
            width=width,
            height=height,
        ).images[0]

        return {
            "image_base64": image_to_base64(image),
            "metadata": {
                "tier": "FAST",
                "model": "sdxl-turbo",
                "steps": 4,
            }
        }

    # STANDARD tier: Base only
    elif quality_tier == "STANDARD":
        pipeline = load_model("base", config)

        image = pipeline(
            prompt=prompt,
            negative_prompt=negative_prompt,
            num_inference_steps=30,
            guidance_scale=7.5,
            width=width,
            height=height,
        ).images[0]

        return {
            "image_base64": image_to_base64(image),
            "metadata": {
                "tier": "STANDARD",
                "model": "sdxl-base",
                "steps": 30,
            }
        }

    # PREMIUM tier: Base then Refiner (sequential to save memory)
    elif quality_tier == "PREMIUM":
        # Step 1: Generate with Base
        print("PREMIUM: Step 1 - Base generation")
        base_pipeline = load_model("base", config)

        base_image = base_pipeline(
            prompt=prompt,
            negative_prompt=negative_prompt,
            num_inference_steps=30,
            guidance_scale=7.5,
            width=width,
            height=height,
        ).images[0]

        # Step 2: Refine (unload Base, load Refiner)
        print("PREMIUM: Step 2 - Refiner enhancement")
        refiner_pipeline = load_model("refiner", config)

        refined_image = refiner_pipeline(
            prompt=prompt,
            negative_prompt=negative_prompt,
            image=base_image,
            num_inference_steps=20,
            guidance_scale=7.5,
            strength=0.3,  # Subtle refinement
        ).images[0]

        return {
            "image_base64": image_to_base64(refined_image),
            "metadata": {
                "tier": "PREMIUM",
                "model": "sdxl-base+refiner",
                "steps": 50,
                "two_pass": True,
            }
        }

    else:
        return {"error": f"Invalid quality tier: {quality_tier}"}


def image_to_base64(image: "Image.Image") -> str:
    """Convert PIL Image to base64."""
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode("utf-8")


def output_fn(prediction, content_type="application/json"):
    """Format output."""
    if content_type == "application/json":
        return json.dumps(prediction), content_type
    raise ValueError(f"Unsupported content type: {content_type}")
