"""
Real-Time Engine - 8–10 second preview generation for instant feedback.

Ultra-fast preview using:
1. LCM (Latent Consistency Model) – latent-consistency/lcm-lora-sdxl, 4-step inference
2. LCMScheduler – low guidance (1.0), 4–6 steps vs 30–50
3. Token merging (ToMe) – tomesd ratio=0.5 for faster attention
4. Lower resolution preview (512×512 → optional Lanczos upscale to 1024)
5. xformers, VAE slicing, torch.compile (reduce-overhead)

Targets: 8–10s preview (512×512), GPU <8GB, 6–7 images/min.

User flow:
1. User types prompt → generate_preview() → ~8–10s → 512×512 (or upscaled 1024)
2. User likes it → identity_engine.generate_* → ~50s → 2048×2048
3. User wants 4K → ultra_engine.generate_4k() → 2–3 min → 4096×4096

Orchestrator (quality_tier): "fast" → realtime; "balanced" → identity_v2; "ultimate" → identity_v2 + ultra.
"""

import modal  # type: ignore[reportMissingImports]
import time
import io
import base64
from pathlib import Path
from typing import Optional, Dict, List, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from PIL import Image  # type: ignore[reportMissingImports]

app = modal.App("realtime-engine")

MODEL_DIR = "/models"
LORA_DIR = "/loras"

models_volume = modal.Volume.from_name("photogenius-models", create_if_missing=True)
lora_volume = modal.Volume.from_name("photogenius-loras", create_if_missing=True)

gpu_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        [
            "torch==2.4.1",
            "torchvision==0.19.1",
            "diffusers==0.30.3",
            "transformers==4.44.2",
            "accelerate==0.34.2",
            "safetensors==0.4.5",
            "peft==0.12.0",
            "xformers==0.0.28.post1",
            "tomesd>=0.1.3",
            "pillow==10.2.0",
            "numpy==1.26.3",
            "optimum[onnxruntime-gpu]",
            "fastapi[standard]",
        ]
    )
    .run_commands(
        "apt-get update",
        "apt-get install -y libgl1-mesa-glx libglib2.0-0",
    )
)

DEFAULT_NEGATIVE = (
    "blurry, low quality, worst quality, jpeg artifacts, "
    "watermark, text, deformed, bad anatomy, ugly, disfigured, "
    "misaligned parts, disconnected handle, wrong perspective, impossible geometry, "
    "floating parts, broken structure, handle canopy mismatch, inconsistent angles, "
    "structurally impossible, ai generated look, fake looking, disjointed object"
)

# Mode-specific prompt prefixes (light touch for realtime)
MODE_PREFIX = {
    "REALISM": "RAW photo, professional photography, high quality, sharp focus, ",
    "CREATIVE": "trending on artstation, masterpiece, highly detailed, ",
    "ROMANTIC": "romantic atmosphere, warm lighting, dreamy, ",
    "FASHION": "vogue editorial, high fashion, studio lighting, ",
    "CINEMATIC": "cinematic still, film grain, dramatic lighting, ",
}


@app.cls(
    gpu="A10G",
    image=gpu_image,
    volumes={
        MODEL_DIR: models_volume,
        LORA_DIR: lora_volume,
    },
    secrets=[
        modal.Secret.from_name("huggingface"),
    ],
    min_containers=3,
    timeout=120,
)
class RealtimeEngine:
    """
    Real-time generation: 8–10 seconds for 1024×1024.
    Uses LCM-LoRA + LCMScheduler + optimized inference.
    """

    @modal.enter()
    def load_models(self):
        import torch  # type: ignore[reportMissingImports]
        import os
        from diffusers import StableDiffusionXLPipeline, LCMScheduler  # type: ignore[reportMissingImports]

        print("Loading LCM-optimized SDXL...")

        hf_token = os.environ.get("HUGGINGFACE_TOKEN") or os.environ.get("HF_TOKEN")
        model_path = Path(f"{MODEL_DIR}/sdxl-base")
        if model_path.exists() and any(model_path.iterdir()):
            model_repo = str(model_path)
        else:
            model_repo = "stabilityai/stable-diffusion-xl-base-1.0"

        kwargs = {
            "torch_dtype": torch.float16,
            "variant": "fp16",
            "use_safetensors": True,
            "cache_dir": MODEL_DIR,
        }
        if hf_token:
            kwargs["token"] = hf_token

        self.pipe = StableDiffusionXLPipeline.from_pretrained(model_repo, **kwargs).to(
            "cuda"
        )

        # LCMScheduler (required for LCM-LoRA)
        self.pipe.scheduler = LCMScheduler.from_config(self.pipe.scheduler.config)

        # LCM-LoRA for speed (4–8 steps)
        self.pipe.load_lora_weights(
            "latent-consistency/lcm-lora-sdxl", adapter_name="lcm"
        )

        # Optimizations
        try:
            self.pipe.enable_xformers_memory_efficient_attention()
        except Exception:
            pass
        try:
            self.pipe.enable_vae_slicing()
        except Exception:
            pass

        # Token merging (ToMe) – ~50% token reduction for faster attention
        try:
            import tomesd  # type: ignore[reportMissingImports]

            tomesd.apply_patch(self.pipe, ratio=0.5)
            print("[OK] ToMe applied (ratio=0.5)")
        except Exception as e:
            print(f"[WARN] ToMe skipped: {e}")

        # torch.compile for ~20% speedup (spec: fullgraph=True)
        try:
            self.pipe.unet = torch.compile(
                self.pipe.unet,
                mode="reduce-overhead",
                fullgraph=True,
            )
        except Exception as e:
            try:
                self.pipe.unet = torch.compile(
                    self.pipe.unet,
                    mode="reduce-overhead",
                    fullgraph=False,
                )
            except Exception as e2:
                print(f"[WARN] torch.compile skipped: {e2}")

        # Warmup (spec: positional prompt, 4 steps, guidance 1.0)
        _ = self.pipe(
            "warmup",
            num_inference_steps=4,
            guidance_scale=1.0,
        ).images[0]

        self._identity_loaded = False
        self._identity_path: Optional[str] = None
        print("✅ Realtime Engine loaded (optimized)")

    def _ensure_identity_lora(self, identity_lora: Optional[str]) -> None:
        if not identity_lora or not Path(identity_lora).exists():
            if self._identity_loaded:
                try:
                    self.pipe.set_adapters(["lcm"], adapter_weights=[1.0])
                except Exception:
                    pass
                self._identity_loaded = False
                self._identity_path = None
            return
        if self._identity_path == identity_lora:
            return
        try:
            self.pipe.load_lora_weights(identity_lora, adapter_name="identity")
            self.pipe.set_adapters(["lcm", "identity"], adapter_weights=[1.0, 0.75])
            self._identity_loaded = True
            self._identity_path = identity_lora
        except Exception as e:
            print(f"[WARN] Identity LoRA load failed: {e}")
            self._identity_loaded = False
            self._identity_path = None

    def _fast_upscale(self, image: "Image.Image", target_size: int) -> "Image.Image":
        """Use Lanczos for fast upscaling (512→1024 for display)."""
        from PIL import Image  # type: ignore[reportMissingImports]

        return image.resize((target_size, target_size), Image.LANCZOS)

    @modal.method()
    def generate_preview(
        self,
        prompt: str,
        negative_prompt: str = DEFAULT_NEGATIVE,
        steps: int = 4,
        guidance_scale: float = 1.0,
        upscale_to: int = 0,
        seed: Optional[int] = None,
        return_dict: bool = False,
    ) -> Union["Image.Image", Dict]:
        """
        Generate 512×512 preview in 8–10 seconds (LCM 4-step).
        Optional: upscale_to=1024 for display via Lanczos.
        """
        import torch  # type: ignore[reportMissingImports]
        from PIL import Image  # type: ignore[reportMissingImports]

        print("⚡ Generating preview (512×512)...")
        t0 = time.perf_counter()

        gen = torch.Generator(device="cuda")
        if seed is not None:
            gen.manual_seed(seed)
        else:
            gen.manual_seed(torch.randint(0, 2**32, (1,)).item())

        with torch.inference_mode():
            image = self.pipe(
                prompt=prompt or "professional photo, high quality",
                negative_prompt=negative_prompt,
                num_inference_steps=steps,
                guidance_scale=guidance_scale,
                width=512,
                height=512,
                generator=gen,
            ).images[0]

        if upscale_to and upscale_to > 512:
            image = self._fast_upscale(image, upscale_to)

        elapsed = time.perf_counter() - t0
        print(f"✅ Preview generated in {elapsed:.1f}s")

        if return_dict:
            buf = io.BytesIO()
            image.save(buf, format="PNG")
            return {
                "image_base64": base64.b64encode(buf.getvalue()).decode(),
                "width": image.width,
                "height": image.height,
                "elapsed_seconds": round(elapsed, 2),
                "pipeline": "realtime_preview",
            }
        return image

    @modal.method()
    def generate_realtime(
        self,
        prompt: str,
        negative_prompt: str = DEFAULT_NEGATIVE,
        identity_lora: Optional[str] = None,
        mode: str = "REALISM",
        seed: Optional[int] = None,
        width: int = 1024,
        height: int = 1024,
        num_steps: int = 6,
        guidance_scale: float = 1.5,
        return_dict: bool = False,
    ) -> Union["Image.Image", Dict]:
        """
        Generate in 8–10 seconds (1024×1024).

        Trade-off: Slightly less detail vs ~10x faster.
        Use case: Quick iterations, preview → full flow.
        """
        import torch  # type: ignore[reportMissingImports]

        print("⚡ Real-time generation...")
        t0 = time.perf_counter()

        self._ensure_identity_lora(identity_lora)

        prefix = MODE_PREFIX.get(mode.upper(), "")
        full_prompt = (prefix + prompt).strip() or "professional photo, high quality"

        gen = torch.Generator(device="cuda")
        if seed is not None:
            gen.manual_seed(seed)
        else:
            gen.manual_seed(torch.randint(0, 2**32, (1,)).item())

        out = self.pipe(
            prompt=full_prompt,
            negative_prompt=negative_prompt,
            num_inference_steps=num_steps,
            guidance_scale=guidance_scale,
            width=width,
            height=height,
            generator=gen,
        )
        out_img = out.images[0]  # type: ignore[union-attr]

        elapsed = time.perf_counter() - t0
        print(f"✅ Generated in {elapsed:.1f}s")

        if return_dict:
            buf = io.BytesIO()
            out_img.save(buf, format="PNG")
            return {
                "image_base64": base64.b64encode(buf.getvalue()).decode(),
                "width": width,
                "height": height,
                "elapsed_seconds": round(elapsed, 2),
                "pipeline": "realtime",
            }
        return out_img

    @modal.method()
    def generate_realtime_batch(
        self,
        prompt: str,
        negative_prompt: str = DEFAULT_NEGATIVE,
        identity_lora: Optional[str] = None,
        mode: str = "REALISM",
        n_images: int = 4,
        seed: Optional[int] = None,
        width: int = 1024,
        height: int = 1024,
        num_steps: int = 6,
        guidance_scale: float = 1.5,
        return_dict: bool = False,
    ) -> Union[List["Image.Image"], Dict]:
        """
        Generate n images in ~10–15s. Good for quick exploration.
        """
        import torch  # type: ignore[reportMissingImports]

        print(f"⚡ Real-time batch ({n_images} images)...")
        t0 = time.perf_counter()

        self._ensure_identity_lora(identity_lora)

        prefix = MODE_PREFIX.get(mode.upper(), "")
        full_prompt = (prefix + prompt).strip() or "professional photo, high quality"

        gen = torch.Generator(device="cuda")
        if seed is not None:
            gen.manual_seed(seed)
        else:
            gen.manual_seed(torch.randint(0, 2**32, (1,)).item())

        out = self.pipe(
            prompt=full_prompt,
            negative_prompt=negative_prompt,
            num_inference_steps=num_steps,
            guidance_scale=guidance_scale,
            num_images_per_prompt=n_images,
            width=width,
            height=height,
            generator=gen,
        )
        images = out.images  # type: ignore[union-attr]

        elapsed = time.perf_counter() - t0
        print(f"✅ Batch generated in {elapsed:.1f}s")

        if return_dict:
            encoded = []
            for im in images:
                buf = io.BytesIO()
                im.save(buf, format="PNG")
                encoded.append(base64.b64encode(buf.getvalue()).decode())
            return {
                "images_base64": encoded,
                "width": width,
                "height": height,
                "elapsed_seconds": round(elapsed, 2),
                "n_images": n_images,
                "pipeline": "realtime_batch",
            }
        return images

    @modal.method()
    def generate_fast(
        self,
        prompt: str,
        negative_prompt: str = DEFAULT_NEGATIVE,
        identity_lora: Optional[str] = None,
        mode: str = "REALISM",
        num_images: int = 4,
        seed: Optional[int] = None,
        width: int = 1024,
        height: int = 1024,
        num_inference_steps: int = 4,
        guidance_scale: float = 5.0,
        return_dict: bool = True,
    ) -> Union[List["Image.Image"], Dict]:
        """
        Fast preview: 4 steps, guidance 5.0, ~8s for 1024×1024.
        Wraps generate_realtime_batch with FAST-tier defaults.
        """
        return self.generate_realtime_batch(
            prompt=prompt,
            negative_prompt=negative_prompt,
            identity_lora=identity_lora,
            mode=mode,
            n_images=num_images,
            seed=seed,
            width=width,
            height=height,
            num_steps=num_inference_steps,
            guidance_scale=guidance_scale,
            return_dict=return_dict,
        )


realtime = RealtimeEngine()


@app.function(
    image=gpu_image,
    gpu="A10G",
    timeout=120,
    volumes={
        MODEL_DIR: models_volume,
        LORA_DIR: lora_volume,
    },
    secrets=[
        modal.Secret.from_name("huggingface"),
    ],
)
@modal.fastapi_endpoint(method="POST")
def generate_realtime_web(item: dict):
    """HTTP endpoint for real-time generation. Use preview=True for 512×512 in 8–10s."""
    engine = RealtimeEngine()
    if item.get("preview", False):
        result = engine.generate_preview.remote(
            prompt=item.get("prompt", ""),
            negative_prompt=item.get("negative_prompt", DEFAULT_NEGATIVE),
            steps=item.get("num_steps", 4),
            guidance_scale=item.get("guidance_scale", 1.0),
            upscale_to=item.get("upscale_to", 1024),
            seed=item.get("seed"),
            return_dict=True,
        )
        return result
    single = item.get("batch", False) is False
    if single:
        result = engine.generate_realtime(
            prompt=item.get("prompt", ""),
            negative_prompt=item.get("negative_prompt", DEFAULT_NEGATIVE),
            identity_lora=item.get("identity_lora"),
            mode=item.get("mode", "REALISM"),
            seed=item.get("seed"),
            width=item.get("width", 1024),
            height=item.get("height", 1024),
            num_steps=item.get("num_steps", 6),
            guidance_scale=item.get("guidance_scale", 1.5),
            return_dict=True,
        )
    else:
        result = engine.generate_realtime_batch(
            prompt=item.get("prompt", ""),
            negative_prompt=item.get("negative_prompt", DEFAULT_NEGATIVE),
            identity_lora=item.get("identity_lora"),
            mode=item.get("mode", "REALISM"),
            n_images=item.get("n_images", 4),
            seed=item.get("seed"),
            width=item.get("width", 1024),
            height=item.get("height", 1024),
            num_steps=item.get("num_steps", 6),
            guidance_scale=item.get("guidance_scale", 1.5),
            return_dict=True,
        )
    return result


@app.local_entrypoint()
def test_realtime():
    print("\n=== Realtime Engine Test ===\n")
    print("Usage:")
    print("  modal deploy ai-pipeline/services/realtime_engine.py")
    print("  modal run ai-pipeline/services/realtime_engine.py::test_realtime")
    print("\nExample:")
    print("  img = realtime.generate_realtime.remote(")
    print('    prompt="professional portrait, studio lighting",')
    print('    negative_prompt="blurry, low quality",')
    print('    mode="REALISM",')
    print("  )")
    print("  # ~8–10s, 1024×1024")
    print("\nBatch:")
    print("  imgs = realtime.generate_realtime_batch.remote(")
    print('    prompt="portrait, sharp focus", n_images=4)')
    print("  # ~10–15s, 4× 1024×1024")
    print("\nReturn dict (API): return_dict=True")
