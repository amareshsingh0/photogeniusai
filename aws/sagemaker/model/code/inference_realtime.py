"""
SageMaker inference entrypoint for real-time preview (8–10s).

LCM-LoRA SDXL: 512×512 in 4 steps, optional Lanczos upscale to 1024.
Target: 8–10s preview, GPU <8GB, 6–7 images/min. Instance: ml.g5.xlarge.
"""

import base64
import json
import os
import time
from io import BytesIO

import torch


def model_fn(model_dir):
    """Load LCM-optimized SDXL for 4-step preview."""
    print("Loading realtime (LCM) model from:", model_dir)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    hf_token = os.environ.get("HUGGINGFACE_TOKEN") or os.environ.get("HF_TOKEN")

    from diffusers import StableDiffusionXLPipeline, LCMScheduler

    base_path = os.environ.get("SDXL_BASE_PATH", os.path.join(model_dir, "sdxl-base"))
    if not (os.path.isdir(base_path) and os.path.isfile(os.path.join(base_path, "model_index.json"))):
        base_path = "stabilityai/stable-diffusion-xl-base-1.0"

    kwargs = {"torch_dtype": torch.float16, "variant": "fp16", "use_safetensors": True}
    if hf_token:
        kwargs["token"] = hf_token
    pipe = StableDiffusionXLPipeline.from_pretrained(base_path, **kwargs).to(device)
    pipe.scheduler = LCMScheduler.from_config(pipe.scheduler.config)
    pipe.load_lora_weights("latent-consistency/lcm-lora-sdxl", adapter_name="lcm")

    try:
        pipe.enable_xformers_memory_efficient_attention()
    except Exception:
        pass
    try:
        pipe.enable_vae_slicing()
    except Exception:
        pass
    try:
        import tomesd
        tomesd.apply_patch(pipe, ratio=0.5)
    except Exception:
        pass

    # Warmup
    _ = pipe("warmup", num_inference_steps=4, guidance_scale=1.0, width=512, height=512).images[0]
    if device == "cuda":
        torch.cuda.empty_cache()

    return {"pipe": pipe, "device": device}


def input_fn(request_body, content_type="application/json"):
    """Parse: prompt (required), negative_prompt?, steps?, guidance_scale?, upscale_to?, seed?."""
    if content_type not in ("application/json", "application/x-json", None, ""):
        raise ValueError(f"Unsupported content type: {content_type}")
    if isinstance(request_body, bytes):
        request_body = request_body.decode("utf-8")
    data = json.loads(request_body or "{}")
    prompt = data.get("prompt")
    if not prompt or not str(prompt).strip():
        raise ValueError("'prompt' is required")
    return {
        "prompt": str(prompt).strip(),
        "negative_prompt": data.get("negative_prompt", "blurry, low quality, worst quality"),
        "steps": int(data.get("steps", data.get("num_inference_steps", 4))),
        "guidance_scale": float(data.get("guidance_scale", 1.0)),
        "upscale_to": int(data.get("upscale_to", 0)),
        "seed": data.get("seed"),
    }


def predict_fn(input_data, model):
    """Generate 512×512 preview; optional upscale to 1024."""
    pipe = model["pipe"]
    device = model["device"]
    result = {"preview_image": None, "preview_time": 0.0, "error": None}

    generator = None
    if input_data.get("seed") is not None:
        try:
            generator = torch.Generator(device=device).manual_seed(int(input_data["seed"]))
        except (TypeError, ValueError):
            pass

    start = time.perf_counter()
    try:
        out = pipe(
            prompt=input_data["prompt"],
            negative_prompt=input_data.get("negative_prompt", ""),
            num_inference_steps=input_data["steps"],
            guidance_scale=input_data["guidance_scale"],
            width=512,
            height=512,
            generator=generator,
        )
        image = out.images[0]
        upscale_to = input_data.get("upscale_to") or 0
        if upscale_to and upscale_to > 512:
            from PIL import Image
            image = image.resize((upscale_to, upscale_to), Image.LANCZOS)
        result["preview_image"] = image
    except Exception as e:
        import traceback
        result["error"] = f"{str(e)}\n{traceback.format_exc()}"
    result["preview_time"] = time.perf_counter() - start
    return result


def output_fn(prediction, content_type="application/json"):
    """Return preview_base64, preview_time, error."""
    out = {
        "preview_base64": None,
        "preview_time": prediction.get("preview_time", 0.0),
        "error": prediction.get("error"),
    }
    if prediction.get("preview_image") is not None:
        buf = BytesIO()
        prediction["preview_image"].save(buf, format="PNG")
        out["preview_base64"] = base64.b64encode(buf.getvalue()).decode("utf-8")
    return json.dumps(out)
