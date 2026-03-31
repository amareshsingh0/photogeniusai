"""
Inference handler for pre-loaded models.
Models are packaged in model.tar.gz and available at MODEL_DIR/models/.
"""

import json
import io
import base64
import os
import gc
from typing import Dict, Any
from pathlib import Path

# Global models
models = {}
MODEL_DIR = None


def model_fn(model_dir):
    """Initialize - models will be lazy loaded on first use."""
    global MODEL_DIR
    MODEL_DIR = model_dir

    print(f"Model directory: {model_dir}")

    # Check if models are available
    models_path = Path(model_dir) / "models"
    if models_path.exists():
        print(f"Models path: {models_path}")
        for model in models_path.iterdir():
            if model.is_dir():
                print(f"  Found: {model.name}")
    else:
        print(f"WARNING: Models path not found: {models_path}")

    print("Inference handler initialized")
    return {"initialized": True}


def load_single_model(model_name: str):
    """Load a specific model from local directory."""
    global models

    if model_name in models:
        print(f"Model '{model_name}' already loaded")
        return models[model_name]

    import torch
    from diffusers import AutoPipelineForText2Image, DPMSolverMultistepScheduler

    print(f"Loading {model_name}...")

    # Model paths (models are in MODEL_DIR/models/)
    model_map = {
        "turbo": "sdxl-turbo",
        "base": "sdxl-base-1.0",
    }

    model_path = Path(MODEL_DIR) / "models" / model_map[model_name]
    print(f"Loading from: {model_path}")

    if not model_path.exists():
        raise FileNotFoundError(f"Model not found: {model_path}")

    load_kwargs = {
        "torch_dtype": torch.float16,
        "variant": "fp16",
        "use_safetensors": True,
        "local_files_only": True,
    }

    pipeline = AutoPipelineForText2Image.from_pretrained(
        str(model_path), **load_kwargs
    )

    if model_name == "base":
        pipeline.scheduler = DPMSolverMultistepScheduler.from_config(
            pipeline.scheduler.config, use_karras_sigmas=True
        )

    pipeline = pipeline.to("cuda")
    pipeline.enable_attention_slicing()
    pipeline.enable_vae_slicing()

    models[model_name] = pipeline
    print(f"✓ {model_name} loaded into GPU")

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
    # Return just the JSON string (HuggingFace toolkit adds content-type)
    return json.dumps(prediction)
