"""
SageMaker inference entrypoint for two-pass generation (preview + final).

AWS only (no Modal). Loads Turbo, Base, Refiner at startup for low latency.
- Pass 1: SDXL Turbo (4 steps, ~5s) fast preview
- Pass 2: SDXL Base + optional LoRA (full resolution)
- Pass 3: SDXL Refiner img2img (optional)

Input JSON: prompt (required), identity_id?, user_id?, negative_prompt?, width?, height?,
  num_inference_steps?, guidance_scale?, seed?, return_preview?, controlnet_conditioning_scale?, denoising_strength?
Output JSON: preview_base64?, final_base64, preview_time, final_time, error?
"""

import base64
import json
import os
import time
import traceback
from io import BytesIO

import torch


# ==================== Model Loading (model_fn) ====================

def model_fn(model_dir):
    """
    Load all three models: Turbo, Base, Refiner.
    Memory optimized with fp16 and attention slicing.
    Missing Turbo or Refiner degrades gracefully.
    """
    print("Loading models from:", model_dir)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    hf_token = os.environ.get("HUGGINGFACE_TOKEN") or os.environ.get("HF_TOKEN") or ""

    def _resolve_path(env_key: str, default_local: str, hf_id: str) -> str:
        p = os.environ.get(env_key, default_local)
        if os.path.isdir(p) and os.path.isfile(os.path.join(p, "model_index.json")):
            return p
        return hf_id

    turbo_path = _resolve_path("SDXL_TURBO_PATH", f"{model_dir}/sdxl-turbo", "stabilityai/sdxl-turbo")
    base_path = _resolve_path("SDXL_BASE_PATH", f"{model_dir}/stable-diffusion-xl-base-1.0", "stabilityai/stable-diffusion-xl-base-1.0")
    refiner_path = _resolve_path("SDXL_REFINER_PATH", f"{model_dir}/stable-diffusion-xl-refiner-1.0", "stabilityai/stable-diffusion-xl-refiner-1.0")

    models = {}

    # 1. SDXL Turbo (preview - optional)
    try:
        print("Loading SDXL Turbo...")
        from diffusers import StableDiffusionXLPipeline

        kwargs = {"torch_dtype": torch.float16, "variant": "fp16", "use_safetensors": True}
        if hf_token:
            kwargs["token"] = hf_token
        turbo_pipe = StableDiffusionXLPipeline.from_pretrained(turbo_path, **kwargs)
        turbo_pipe = turbo_pipe.to(device)
        turbo_pipe.enable_attention_slicing()
        turbo_pipe.enable_vae_slicing()
        models["turbo"] = turbo_pipe
        print("✅ SDXL Turbo loaded")
    except Exception as e:
        print(f"⚠️ SDXL Turbo not available: {e}")
        models["turbo"] = None

    # 2. SDXL Base (required)
    print("Loading SDXL Base...")
    try:
        from diffusers import StableDiffusionXLPipeline

        kwargs = {"torch_dtype": torch.float16, "variant": "fp16", "use_safetensors": True}
        if hf_token:
            kwargs["token"] = hf_token
        base_pipe = StableDiffusionXLPipeline.from_pretrained(base_path, **kwargs)
        base_pipe = base_pipe.to(device)
        base_pipe.enable_attention_slicing()
        base_pipe.enable_vae_slicing()
        models["base"] = base_pipe
        print("✅ SDXL Base loaded")
    except Exception as e:
        print(f"❌ SDXL Base required but failed: {e}")
        raise

    # 3. SDXL Refiner (optional)
    try:
        print("Loading SDXL Refiner...")
        from diffusers import StableDiffusionXLImg2ImgPipeline

        kwargs = {"torch_dtype": torch.float16, "variant": "fp16", "use_safetensors": True}
        if hf_token:
            kwargs["token"] = hf_token
        refiner_pipe = StableDiffusionXLImg2ImgPipeline.from_pretrained(refiner_path, **kwargs)
        refiner_pipe = refiner_pipe.to(device)
        refiner_pipe.enable_attention_slicing()
        refiner_pipe.enable_vae_slicing()
        models["refiner"] = refiner_pipe
        print("✅ SDXL Refiner loaded")
    except Exception as e:
        print(f"⚠️ SDXL Refiner not available: {e}")
        models["refiner"] = None

    models["lora_dir"] = os.environ.get("LORA_DIR", f"{model_dir}/loras")
    models["device"] = device
    return models


# ==================== Input Processing (input_fn) ====================

def input_fn(request_body, content_type="application/json"):
    """
    Parse and validate input request.
    """
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
        "identity_id": data.get("identity_id"),
        "user_id": data.get("user_id"),
        "style_lora": (data.get("style_lora") or "").strip() or None,
        "negative_prompt": data.get("negative_prompt", ""),
        "width": int(data.get("width", 1024)),
        "height": int(data.get("height", 1024)),
        "num_inference_steps": int(data.get("num_inference_steps", 50)),
        "guidance_scale": float(data.get("guidance_scale", 8.5)),
        "seed": data.get("seed"),
        "return_preview": bool(data.get("return_preview", True)),
        "controlnet_conditioning_scale": float(data.get("controlnet_conditioning_scale", 0.80)),
        "denoising_strength": float(data.get("denoising_strength", 0.3)),
    }


# ==================== Prediction (predict_fn) ====================

def predict_fn(input_data, models):
    """
    Execute two-pass generation with comprehensive error handling.
    Pass 1: Turbo preview (optional). Pass 2: Base + optional LoRA. Pass 3: Refiner (optional).
    """
    turbo_pipe = models.get("turbo")
    base_pipe = models["base"]
    refiner_pipe = models.get("refiner")
    lora_dir = models.get("lora_dir", "")
    device = models.get("device", "cuda")

    result = {
        "preview_image": None,
        "final_image": None,
        "preview_time": 0.0,
        "final_time": 0.0,
        "error": None,
    }

    generator = None
    if input_data.get("seed") is not None:
        try:
            seed = int(input_data["seed"])
            generator = torch.Generator(device=device).manual_seed(seed)
        except (TypeError, ValueError):
            pass

    try:
        # ----- PASS 1: Fast Preview (SDXL Turbo) -----
        if turbo_pipe and input_data.get("return_preview"):
            print("🚀 Pass 1: Generating preview...")
            preview_start = time.time()
            try:
                preview_output = turbo_pipe(
                    prompt=input_data["prompt"],
                    negative_prompt=input_data.get("negative_prompt") or "",
                    num_inference_steps=4,
                    guidance_scale=1.0,
                    width=512,
                    height=512,
                    generator=generator,
                )
                result["preview_image"] = preview_output.images[0]
                result["preview_time"] = time.time() - preview_start
                print(f"✅ Preview generated in {result['preview_time']:.2f}s")
            except Exception as e:
                print(f"⚠️ Preview failed: {e}")
                result["preview_time"] = time.time() - preview_start

            if device == "cuda":
                torch.cuda.empty_cache()

        # ----- PASS 2: Full Quality (SDXL Base + optional LoRA) -----
        print("🎨 Pass 2: Generating full quality...")
        final_start = time.time()
        lora_loaded = False

        if input_data.get("identity_id") and input_data.get("user_id") and lora_dir:
            lora_path = os.path.join(
                lora_dir,
                str(input_data["user_id"]),
                f"{input_data['identity_id']}.safetensors",
            )
            if os.path.isfile(lora_path):
                try:
                    print(f"Loading LoRA: {lora_path}")
                    base_pipe.load_lora_weights(lora_path)
                    base_pipe.fuse_lora()
                    lora_loaded = True
                    print("✅ LoRA loaded and fused")
                except Exception as e:
                    print(f"⚠️ LoRA load failed: {e}")

        style_lora = input_data.get("style_lora")
        if style_lora and lora_dir:
            style_path = os.path.join(lora_dir, "styles", style_lora, "lora.safetensors")
            style_dir_path = os.path.join(lora_dir, "styles", style_lora)
            if os.path.isfile(style_path):
                try:
                    print(f"Loading style LoRA: {style_path}")
                    base_pipe.load_lora_weights(style_path)
                    base_pipe.fuse_lora()
                    lora_loaded = True
                    print("✅ Style LoRA loaded and fused")
                except Exception as e:
                    print(f"⚠️ Style LoRA load failed: {e}")
            elif os.path.isdir(style_dir_path):
                try:
                    print(f"Loading style LoRA: {style_dir_path}")
                    base_pipe.load_lora_weights(style_dir_path)
                    base_pipe.fuse_lora()
                    lora_loaded = True
                    print("✅ Style LoRA loaded and fused")
                except Exception as e:
                    print(f"⚠️ Style LoRA load failed: {e}")

        try:
            base_output = base_pipe(
                prompt=input_data["prompt"],
                negative_prompt=input_data.get("negative_prompt") or "",
                num_inference_steps=input_data["num_inference_steps"],
                guidance_scale=input_data["guidance_scale"],
                width=input_data["width"],
                height=input_data["height"],
                generator=generator,
            )
            full_image = base_output.images[0]
        finally:
            if lora_loaded:
                try:
                    base_pipe.unfuse_lora()
                except Exception:
                    pass

        print(f"✅ Full image generated in {time.time() - final_start:.2f}s")
        if device == "cuda":
            torch.cuda.empty_cache()

        # ----- PASS 3: Refinement (SDXL Refiner img2img) -----
        if refiner_pipe:
            print("✨ Pass 3: Refining...")
            refine_start = time.time()
            try:
                strength = input_data.get("denoising_strength", 0.3)
                refiner_output = refiner_pipe(
                    prompt=input_data["prompt"],
                    negative_prompt=input_data.get("negative_prompt") or "",
                    image=full_image,
                    num_inference_steps=25,
                    strength=strength,
                    generator=generator,
                )
                result["final_image"] = refiner_output.images[0]
                print(f"✅ Refinement complete in {time.time() - refine_start:.2f}s")
            except Exception as e:
                print(f"⚠️ Refiner failed, using base output: {e}")
                result["final_image"] = full_image
        else:
            result["final_image"] = full_image
            print("ℹ️ Skipping refinement (refiner not available)")

        result["final_time"] = time.time() - final_start
        print(f"✅ Total generation: {result['preview_time'] + result['final_time']:.2f}s")

    except Exception as e:
        error_msg = f"Generation failed: {str(e)}\n{traceback.format_exc()}"
        print(f"❌ {error_msg}")
        result["error"] = error_msg

    return result


# ==================== Output Formatting (output_fn) ====================

def output_fn(prediction, content_type="application/json"):
    """
    Convert images to base64 and format response.
    """
    response = {
        "preview_base64": None,
        "final_base64": None,
        "preview_time": prediction.get("preview_time", 0.0),
        "final_time": prediction.get("final_time", 0.0),
        "error": prediction.get("error"),
    }

    if prediction.get("preview_image") is not None:
        buf = BytesIO()
        prediction["preview_image"].save(buf, format="PNG")
        response["preview_base64"] = base64.b64encode(buf.getvalue()).decode("utf-8")

    if prediction.get("final_image") is not None:
        buf = BytesIO()
        prediction["final_image"].save(buf, format="PNG")
        response["final_base64"] = base64.b64encode(buf.getvalue()).decode("utf-8")

    return json.dumps(response)
