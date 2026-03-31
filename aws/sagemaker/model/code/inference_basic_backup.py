"""
SageMaker inference script for SDXL.

Accepts both HuggingFace-style (inputs + parameters) and direct JSON.
Returns: {"image": "<base64>"}.
Optimizations: FP16, DPM++ scheduler, attention/VAE slicing, optional torch.compile.
"""

import json
import io
import base64
import os

# Global model (loaded once at container startup)
model = None


def model_fn(model_dir):
    """
    Load model once at container startup.
    Priority: 1) Local model_dir, 2) S3 bucket, 3) HuggingFace.
    Prefers SDXL Turbo (smaller, faster) unless HF_MODEL_ID is set.
    """
    global model
    import subprocess
    import torch
    from diffusers import (
        StableDiffusionXLPipeline,
        DPMSolverMultistepScheduler,
        AutoPipelineForText2Image,
    )

    # Configuration
    default_model = "stabilityai/sdxl-turbo"
    hf_id = os.environ.get("HF_MODEL_ID", default_model)
    s3_bucket = os.environ.get("MODELS_S3_BUCKET", "photogenius-models-dev")
    s3_prefix = os.environ.get("MODELS_S3_PREFIX", "models/sdxl-turbo")
    use_turbo = "turbo" in hf_id.lower()

    print(f"Loading model: {hf_id} (turbo={use_turbo})")
    print(f"S3 source: s3://{s3_bucket}/{s3_prefix}")

    # Check for local model first
    use_local = os.path.exists(os.path.join(model_dir or "", "model_index.json"))
    local_s3_path = "/opt/ml/model/s3-models"

    try:
        load_kwargs = {
            "torch_dtype": torch.float16,
            "variant": "fp16",
            "use_safetensors": True,
        }

        if use_local and model_dir:
            print(f"Loading from local: {model_dir}")
            pipeline = AutoPipelineForText2Image.from_pretrained(
                model_dir, **load_kwargs
            )
        else:
            # Try to download from S3 first (faster, same region)
            s3_model_path = None
            try:
                print(f"Attempting S3 download: s3://{s3_bucket}/{s3_prefix}")
                os.makedirs(local_s3_path, exist_ok=True)
                subprocess.run(
                    [
                        "aws",
                        "s3",
                        "sync",
                        f"s3://{s3_bucket}/{s3_prefix}",
                        local_s3_path,
                    ],
                    check=True,
                    timeout=300,  # 5 minute timeout
                )
                if os.path.exists(os.path.join(local_s3_path, "model_index.json")):
                    s3_model_path = local_s3_path
                    print(f"S3 download complete: {local_s3_path}")
            except Exception as e:
                print(f"S3 download failed: {e}, falling back to HuggingFace")

            if s3_model_path:
                print(f"Loading from S3 cache: {s3_model_path}")
                pipeline = AutoPipelineForText2Image.from_pretrained(
                    s3_model_path, **load_kwargs
                )
            else:
                print(f"Downloading from HuggingFace: {hf_id}")
                pipeline = AutoPipelineForText2Image.from_pretrained(
                    hf_id, **load_kwargs
                )

        # Use faster scheduler if not Turbo (Turbo has its own optimized scheduler)
        if not use_turbo:
            pipeline.scheduler = DPMSolverMultistepScheduler.from_config(
                pipeline.scheduler.config,
                use_karras_sigmas=True,
            )

        pipeline = pipeline.to("cuda")
        pipeline.enable_attention_slicing()
        pipeline.enable_vae_slicing()

        try:
            if hasattr(torch, "compile"):
                pipeline.unet = torch.compile(
                    pipeline.unet, mode="reduce-overhead", fullgraph=False
                )
                print("Model compiled with torch.compile")
        except Exception as e:
            print(f"torch.compile skipped: {e}")

        model = pipeline
        print("Model loaded and optimized")
        return model

    except Exception as e:
        print(f"ERROR loading model: {e}")
        # Return None; predict_fn will handle gracefully
        model = None
        return None


def input_fn(request_body, request_content_type):
    """Parse input (JSON)."""
    if request_content_type in ("application/json", "application/x-json", None, ""):
        if isinstance(request_body, bytes):
            request_body = request_body.decode("utf-8")
        return json.loads(request_body or "{}")
    raise ValueError(f"Unsupported content type: {request_content_type}")


def _normalize_input(data):
    """Support both HF-style (inputs + parameters) and direct (prompt, negative_prompt, ...)."""
    if "inputs" in data and "parameters" in data:
        params = data["parameters"] or {}
        return {
            "prompt": (
                data["inputs"]
                if isinstance(data["inputs"], str)
                else data["inputs"].get("prompt", "")
            ),
            "negative_prompt": params.get("negative_prompt", ""),
            "num_inference_steps": params.get("num_inference_steps", 50),
            "guidance_scale": params.get("guidance_scale", 8.5),
            "width": params.get("width", 1024),
            "height": params.get("height", 1024),
        }
    return {
        "prompt": data.get("prompt", ""),
        "negative_prompt": data.get("negative_prompt", ""),
        "num_inference_steps": data.get("num_inference_steps", 50),
        "guidance_scale": data.get("guidance_scale", 8.5),
        "width": data.get("width", 1024),
        "height": data.get("height", 1024),
    }


def _generate_mock_image():
    """Generate a simple test image (gradient) for pipeline testing."""
    from PIL import Image
    import numpy as np

    # Create a 256x256 gradient image
    arr = np.zeros((256, 256, 3), dtype=np.uint8)
    for i in range(256):
        arr[i, :, 0] = i  # Red gradient
        arr[:, i, 1] = i  # Green gradient
    arr[:, :, 2] = 128  # Blue constant
    img = Image.fromarray(arr)
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode("utf-8")


def predict_fn(data, model):
    """Generate image; return dict with 'image' base64."""
    import torch

    # Test mode: return mock image without running inference
    if data.get("test_mode") or data.get("test"):
        return {"image": _generate_mock_image(), "test_mode": True}

    opts = _normalize_input(data)
    prompt = opts["prompt"]
    if not prompt:
        return {"image": "", "error": "prompt is required"}

    # Check if model is loaded
    if model is None:
        return {
            "image": "",
            "error": "Model not loaded. Container may still be initializing.",
        }

    with torch.inference_mode():
        out = model(
            prompt=prompt,
            negative_prompt=opts["negative_prompt"],
            num_inference_steps=opts["num_inference_steps"],
            guidance_scale=opts["guidance_scale"],
            width=opts["width"],
            height=opts["height"],
            generator=torch.Generator("cuda").manual_seed(
                int(os.environ.get("SEED", "42"))
            ),
        )

    image = out.images[0]
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
    return {"image": img_str}


def output_fn(prediction, content_type):
    """Return JSON."""
    return json.dumps(prediction)
