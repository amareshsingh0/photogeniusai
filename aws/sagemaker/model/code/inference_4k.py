"""
SageMaker inference entrypoint for native 4K generation (3840×2160 or 3840×3840).

AWS only. Deploy on ml.g5.4xlarge (24GB) or ml.g5.8xlarge (48GB).
- method=latent: MultiDiffusion (1024 latent → upscale latents → tiled VAE decode)
- method=iterative: 1024 → 2048 img2img → 4K img2img

Input: prompt (required), negative_prompt?, width? (3840), height? (2160|3840), steps?, guidance_scale?, seed?, method? (latent|iterative)
Output: image_base64, width, height, inference_time, error?
Target: 120–180s, 20–24GB GPU, no visible tiling artifacts.
"""

import base64
import json
import os
import time
import traceback
from io import BytesIO

import torch


def model_fn(model_dir):
    """Load SDXL Base + img2img; enable vae_tiling, vae_slicing, attention_slicing."""
    print("Loading 4K models from:", model_dir)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    hf_token = os.environ.get("HUGGINGFACE_TOKEN") or os.environ.get("HF_TOKEN") or ""

    def _resolve(env_key, default_local, hf_id):
        p = os.environ.get(env_key, default_local)
        if os.path.isdir(p) and os.path.isfile(os.path.join(p, "model_index.json")):
            return p
        return hf_id

    base_path = _resolve("SDXL_BASE_PATH", f"{model_dir}/stable-diffusion-xl-base-1.0", "stabilityai/stable-diffusion-xl-base-1.0")
    kwargs = {"torch_dtype": torch.float16, "variant": "fp16", "use_safetensors": True}
    if hf_token:
        kwargs["token"] = hf_token

    from diffusers import StableDiffusionXLPipeline, StableDiffusionXLImg2ImgPipeline

    pipe = StableDiffusionXLPipeline.from_pretrained(base_path, **kwargs).to(device)
    pipe_img2img = StableDiffusionXLImg2ImgPipeline.from_pretrained(base_path, **kwargs).to(device)
    for p in (pipe, pipe_img2img):
        p.enable_attention_slicing()
        p.enable_vae_slicing()
        p.enable_vae_tiling()
    print("✅ 4K models loaded")
    return {"pipe": pipe, "pipe_img2img": pipe_img2img, "device": device}


def input_fn(request_body, content_type="application/json"):
    if content_type not in ("application/json", "application/x-json", None, ""):
        raise ValueError(f"Unsupported content type: {content_type}")
    if isinstance(request_body, bytes):
        request_body = request_body.decode("utf-8")
    data = json.loads(request_body or "{}")
    prompt = (data.get("prompt") or "").strip()
    if not prompt:
        raise ValueError("'prompt' is required")
    width = int(data.get("width", 3840))
    height = int(data.get("height", 2160))
    if width <= 0 or height <= 0:
        width, height = 3840, 2160
    return {
        "prompt": prompt,
        "negative_prompt": data.get("negative_prompt", ""),
        "width": width,
        "height": height,
        "steps": int(data.get("steps", 40)),
        "guidance_scale": float(data.get("guidance_scale", 7.5)),
        "seed": data.get("seed"),
        "method": (data.get("method") or "latent").lower() if data.get("method") else "latent",
    }


def _upscale_latents(latents, target_width, target_height, dtype, device):
    lh, lw = target_height // 8, target_width // 8
    up = torch.nn.functional.interpolate(
        latents.float(),
        size=(lh, lw),
        mode="bicubic",
        align_corners=False,
    )
    return up.to(dtype).to(device)


def predict_fn(input_data, models):
    pipe = models["pipe"]
    pipe_img2img = models["pipe_img2img"]
    device = models["device"]
    result = {"image": None, "inference_time": 0.0, "error": None}
    generator = None
    if input_data.get("seed") is not None:
        try:
            seed = int(input_data["seed"])
            generator = torch.Generator(device=device).manual_seed(seed)
        except (TypeError, ValueError):
            pass
    if generator is None:
        generator = torch.Generator(device=device).manual_seed(torch.randint(0, 2**32, (1,)).item())

    t0 = time.time()
    try:
        prompt = input_data["prompt"]
        negative_prompt = input_data.get("negative_prompt") or ""
        width = input_data["width"]
        height = input_data["height"]
        steps = input_data.get("steps", 40)
        guidance_scale = input_data.get("guidance_scale", 7.5)
        method = input_data.get("method", "latent")

        if method == "iterative":
            # 1024 base → 2048 img2img → 4K img2img
            out = pipe(
                prompt=prompt,
                negative_prompt=negative_prompt,
                num_inference_steps=40,
                guidance_scale=7.5,
                width=1024,
                height=1024,
                generator=generator,
            )
            base = out.images[0]
            mid_w, mid_h = min(2048, width), min(2048, height)
            if width * height > 2048 * 2048:
                mid_w, mid_h = 2048, 2048
            base_2k = base.resize((mid_w, mid_h))
            refined_2k = pipe_img2img(
                prompt=prompt,
                negative_prompt=negative_prompt,
                image=base_2k,
                strength=0.3,
                num_inference_steps=20,
                guidance_scale=7.0,
                generator=generator,
            ).images[0]
            refined_2k_4k = refined_2k.resize((width, height))
            refined_4k = pipe_img2img(
                prompt=prompt,
                negative_prompt=negative_prompt,
                image=refined_2k_4k,
                strength=0.2,
                num_inference_steps=15,
                guidance_scale=6.5,
                generator=generator,
            ).images[0]
            result["image"] = refined_4k
        else:
            # latent: 1024 latent → upscale latents → tiled VAE decode
            out = pipe(
                prompt=prompt,
                negative_prompt=negative_prompt,
                num_inference_steps=steps,
                guidance_scale=guidance_scale,
                width=1024,
                height=1024,
                output_type="latent",
                generator=generator,
            )
            latents = out.images
            latents_up = _upscale_latents(latents, width, height, latents.dtype, device)
            with torch.no_grad():
                decoded = pipe.vae.decode(latents_up / pipe.vae.config.scaling_factor, return_dict=False)[0]
            decoded = (decoded / 2 + 0.5).clamp(0, 1).cpu()
            import numpy as np
            from PIL import Image
            image_np = (decoded[0].permute(1, 2, 0).numpy() * 255).round().astype("uint8")
            result["image"] = Image.fromarray(image_np)

        result["inference_time"] = time.time() - t0
        print(f"✅ 4K generated in {result['inference_time']:.1f}s ({method})")
    except Exception as e:
        result["error"] = f"{str(e)}\n{traceback.format_exc()}"
        print(f"❌ 4K generation failed: {e}")
    return result


def output_fn(prediction, content_type="application/json"):
    resp = {
        "image_base64": None,
        "width": 0,
        "height": 0,
        "inference_time": prediction.get("inference_time", 0.0),
        "error": prediction.get("error"),
    }
    if prediction.get("image") is not None:
        buf = BytesIO()
        prediction["image"].save(buf, format="PNG")
        resp["image_base64"] = base64.b64encode(buf.getvalue()).decode("utf-8")
        resp["width"] = prediction["image"].width
        resp["height"] = prediction["image"].height
    return json.dumps(resp)
