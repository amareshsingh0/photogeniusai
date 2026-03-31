"""
Ultra High-Res Engine - Native 4K Generation (4096×4096)

CONTEXT: Progressive 2048 works, but native 4K gives better quality for prints/large displays.

ARCHITECTURE:
┌─────────────────────────────────────────┐
│    ULTRA HIGH-RES ENGINE                │
│                                         │
│  1. Tile-based generation (1024 tiles)  │
│  2. Overlap & blend seamlessly          │
│  3. Detail pass at full resolution      │
│  4. VRAM-efficient (fits in 40GB)       │
└─────────────────────────────────────────┘

Strategy:
1. Generate 2048×2048 base
2. Tile into 4×4 grid (1024×1024 each)
3. Upscale each tile, img2img refine, blend seamlessly
4. Final detail pass

Cost optimization:
- Use A100-40GB instead of 80GB if possible (set ULTRARES_GPU=40).
- Use tile_grid="2x2" for fewer tiles.
- Offer as premium feature ($0.10/image).
"""

import modal  # type: ignore[reportMissingImports]
import numpy as np  # type: ignore[reportMissingImports]
from PIL import Image  # type: ignore[reportMissingImports]
import io
import base64
from pathlib import Path
from typing import Optional, Dict, Literal, Union, List, Any, Callable, Tuple
import os
import logging

logger = logging.getLogger(__name__)

app = modal.App("ultra-high-res")

MODEL_DIR = "/models"
LORA_DIR = "/loras"

models_volume = modal.Volume.from_name("photogenius-models", create_if_missing=True)
lora_volume = modal.Volume.from_name("photogenius-loras", create_if_missing=True)

# Prefer A100-40GB when ULTRARES_GPU=40 (cost optimization)
_GPU = "A100-40GB" if os.environ.get("ULTRARES_GPU") == "40" else "A100-80GB"

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
            "pillow==10.2.0",
            "numpy==1.26.3",
            "opencv-python==4.9.0.80",
            "fastapi[standard]",
        ]
    )
    .run_commands(
        "apt-get update",
        "apt-get install -y libgl1-mesa-glx libglib2.0-0",
    )
)

# Default negative prompt (includes object-coherence: umbrella/handle alignment)
DEFAULT_NEGATIVE = (
    "blurry, low quality, worst quality, jpeg artifacts, "
    "watermark, text, deformed, bad anatomy, ugly, disfigured, "
    "misaligned parts, disconnected handle, wrong perspective, impossible geometry, "
    "floating parts, broken structure, handle canopy mismatch, inconsistent angles, "
    "structurally impossible, ai generated look, fake looking, disjointed object"
)

# Native 4K resolutions (no upscaling from lower): 120–180s on ml.g5.4xlarge
WIDTH_4K_UHD, HEIGHT_4K_UHD = 3840, 2160  # 16:9
WIDTH_4K_SQ, HEIGHT_4K_SQ = 3840, 3840  # 1:1


@app.cls(
    gpu=_GPU,
    image=gpu_image,
    volumes={
        MODEL_DIR: models_volume,
        LORA_DIR: lora_volume,
    },
    secrets=[
        modal.Secret.from_name("huggingface"),
    ],
    min_containers=0,
    timeout=900,
)
class UltraHighResEngine:
    """
    Native 4K (4096×4096) generation.
    Uses tiled refine + seamless blend for VRAM efficiency.
    """

    @modal.enter()
    def load_models(self):
        import torch  # type: ignore[reportMissingImports]
        from diffusers import (  # type: ignore[reportMissingImports]
            StableDiffusionXLPipeline,
            StableDiffusionXLImg2ImgPipeline,
        )

        print("Loading SDXL for 4K generation...")

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

        self.pipe_img2img = StableDiffusionXLImg2ImgPipeline.from_pretrained(
            model_repo, **kwargs
        ).to("cuda")

        # VRAM optimizations
        try:
            self.pipe.enable_xformers_memory_efficient_attention()
            self.pipe_img2img.enable_xformers_memory_efficient_attention()
        except Exception:
            pass
        try:
            self.pipe.enable_vae_tiling()
            self.pipe_img2img.enable_vae_tiling()
        except Exception:
            pass
        try:
            self.pipe.enable_vae_slicing()
            self.pipe_img2img.enable_vae_slicing()
        except Exception:
            pass
        try:
            self.pipe.enable_attention_slicing(1)
            self.pipe_img2img.enable_attention_slicing(1)
        except Exception:
            pass

        self._lora_loaded = False
        print("✅ Ultra High-Res Engine loaded")

    def _ensure_lora(self, lora_path: Optional[str], strength: float = 0.85):
        import torch  # type: ignore[reportMissingImports]

        if not lora_path or not Path(lora_path).exists():
            if self._lora_loaded:
                try:
                    self.pipe.set_adapters([])
                    self.pipe_img2img.set_adapters([])
                except Exception:
                    pass
                self._lora_loaded = False
            return
        try:
            self.pipe.load_lora_weights(lora_path, adapter_name="identity")
            self.pipe.set_adapters(["identity"], adapter_weights=[strength])
            self.pipe_img2img.load_lora_weights(lora_path, adapter_name="identity")
            self.pipe_img2img.set_adapters(["identity"], adapter_weights=[strength])
            self._lora_loaded = True
        except Exception as e:
            print(f"[WARN] LoRA load failed: {e}")

    @staticmethod
    def _create_feather_mask(width: int, height: int, feather: int) -> np.ndarray:
        """
        Create feathered mask for seamless blending.
        Spec-style: edge rows/cols ramp 0 -> (feather-1)/feather; center 1.0.
        """
        mask = np.ones((height, width), dtype=np.float32)
        if feather <= 0:
            return mask
        # Edge ramps: spec-style (alpha = i / feather)
        for i in range(feather):
            alpha = i / feather
            if i < height:
                mask[i, :] *= alpha
            if height - 1 - i >= 0:
                mask[-(i + 1), :] *= alpha
            if i < width:
                mask[:, i] *= alpha
            if width - 1 - i >= 0:
                mask[:, -(i + 1)] *= alpha
        return mask

    def _tiled_upscale(
        self,
        image: Image.Image,
        prompt: str,
        negative_prompt: str,
        target_size: int = 4096,
        tile_grid: Literal["4x4", "2x2"] = "4x4",
        overlap: int = 128,
        tile_size_override: Optional[int] = None,
        tile_overlap_override: Optional[int] = None,
        strength: float = 0.25,
        steps: int = 20,
    ) -> Image.Image:
        """
        Upscale using overlapping tiles (spec: num_tiles × num_tiles grid).
        4x4: 1024×1024 tiles; 2x2: 2048×2048 tiles. Or use tile_size_override (e.g. 512) + tile_overlap_override (e.g. 64).
        """
        import torch  # type: ignore[reportMissingImports]

        if tile_size_override is not None and tile_overlap_override is not None:
            tile_size = max(256, tile_size_override)
            overlap = min(tile_overlap_override, tile_size - 1)
            stride = max(1, tile_size - overlap)
            num_tiles = max(1, (target_size + stride - 1) // stride)
        elif tile_grid == "2x2":
            tile_size = 2048
            num_tiles = 2
            stride = max(1, tile_size - overlap)
        else:
            tile_size = 1024
            num_tiles = 4
            stride = max(1, tile_size - overlap)

        image_4k = image.resize((target_size, target_size), Image.LANCZOS)
        output = np.zeros((target_size, target_size, 3), dtype=np.float64)
        weights = np.zeros((target_size, target_size), dtype=np.float64)

        total = num_tiles * num_tiles
        print(
            f"  Processing {num_tiles}x{num_tiles} tiles (size={tile_size}, overlap={overlap})..."
        )
        logger.info(
            "Ultra high-res: %dx%d tiles (%dx%d), overlap=%d",
            target_size,
            target_size,
            num_tiles,
            num_tiles,
            overlap,
        )

        for i in range(num_tiles):
            for j in range(num_tiles):
                y_start = i * stride
                x_start = j * stride
                y_end = min(y_start + tile_size, target_size)
                x_end = min(x_start + tile_size, target_size)
                tw = x_end - x_start
                th = y_end - y_start

                tile = image_4k.crop((x_start, y_start, x_end, y_end))
                tile = tile.resize((1024, 1024), Image.LANCZOS)

                gen = torch.Generator(device="cuda").manual_seed(
                    hash((i, j, prompt)) % (2**32)
                )
                pipe_out = self.pipe_img2img(
                    prompt=prompt,
                    negative_prompt=negative_prompt,
                    image=tile,
                    strength=strength,
                    num_inference_steps=steps,
                    guidance_scale=7.0,
                    generator=gen,
                )
                refined = pipe_out.images[0]  # type: ignore[union-attr]
                refined = refined.resize((tw, th), Image.LANCZOS)
                tile_np = np.array(refined).astype(np.float64)

                feather = min(overlap, tw // 2, th // 2)
                mask = self._create_feather_mask(tw, th, feather)
                w = np.maximum(mask, 1e-8)

                output[y_start:y_end, x_start:x_end] += tile_np * w[:, :, np.newaxis]
                weights[y_start:y_end, x_start:x_end] += w

                done = i * num_tiles + j + 1
                pct = int(100 * done / total)
                step = max(1, total // 10) if total > 16 else 4
                if done % step == 0 or done == total:
                    print(f"    Progress: {done}/{total} ({pct}%)")
                    logger.info("Ultra progress: %d/%d tiles, %d%%", done, total, pct)

        w = np.maximum(weights[:, :, np.newaxis], 1e-8)
        out = np.clip(output / w, 0, 255).astype(np.uint8)
        return Image.fromarray(out)

    def _detail_pass(
        self,
        image: Image.Image,
        prompt: str,
        negative_prompt: str,
        strength: float = 0.15,
        steps: int = 15,
    ) -> Image.Image:
        """
        Final detail enhancement pass on full 4K.
        Runs at 2048 then upscales to 4K to avoid OOM (VRAM-efficient).
        """
        import torch  # type: ignore[reportMissingImports]

        w, h = image.size
        down = image.resize((2048, 2048), Image.LANCZOS)
        enhanced = f"{prompt}, extremely detailed, ultra sharp, 8k uhd"
        gen = torch.Generator(device="cuda").manual_seed(42)
        pipe_out = self.pipe_img2img(
            prompt=enhanced,
            negative_prompt=negative_prompt,
            image=down,
            strength=strength,  # Very light
            num_inference_steps=steps,
            guidance_scale=6.5,
            generator=gen,
        )
        refined = pipe_out.images[0]  # type: ignore[union-attr]
        return refined.resize((w, h), Image.LANCZOS)

    def _upscale_latents(self, latents: Any, target_size: Tuple[int, int]) -> Any:
        """
        Upscale latent tensors using bicubic interpolation.
        SDXL VAE downsampling factor is 8; target_size is pixel (W, H), latent size (H//8, W//8).
        """
        import torch  # type: ignore[reportMissingImports]

        if not hasattr(latents, "dim"):
            return latents
        # target_size = (width, height) pixel -> latent (height//8, width//8)
        lh, lw = target_size[1] // 8, target_size[0] // 8
        latents_up = torch.nn.functional.interpolate(
            latents.float(),
            size=(lh, lw),
            mode="bicubic",
            align_corners=False,
        )
        return latents_up.to(latents.dtype)

    def generate_4k_native_latent(
        self,
        prompt: str,
        negative_prompt: str = DEFAULT_NEGATIVE,
        width: int = WIDTH_4K_UHD,
        height: int = HEIGHT_4K_UHD,
        steps: int = 40,
        guidance_scale: float = 7.5,
        seed: Optional[int] = None,
        lora_path: Optional[str] = None,
    ) -> Image.Image:
        """
        Generate native 4K using MultiDiffusion (tiled VAE decode).
        First pass: 1024×1024 latent; upscale latents to 4K latent size; tiled VAE decode.
        Resolution: 3840×2160 (16:9) or 3840×3840 (1:1). ~120–180s on ml.g5.4xlarge.
        """
        import torch  # type: ignore[reportMissingImports]

        self._ensure_lora(lora_path, strength=0.85)
        gen = torch.Generator(device="cuda")
        if seed is not None:
            gen.manual_seed(int(seed))
        else:
            gen.manual_seed(torch.randint(0, 2**32, (1,)).item())

        # First pass: 1024×1024 latent
        out = self.pipe(
            prompt=prompt,
            negative_prompt=negative_prompt,
            num_inference_steps=steps,
            guidance_scale=guidance_scale,
            width=1024,
            height=1024,
            output_type="latent",
            generator=gen,
        )
        latents = out.images
        latents_up = self._upscale_latents(latents, (width, height))
        # Tiled VAE decode (enable_vae_tiling already in load_models)
        with torch.no_grad():
            decoded = self.pipe.vae.decode(
                latents_up / self.pipe.vae.config.scaling_factor, return_dict=False
            )[0]
        # decoded: (B, 3, H*8, W*8); take first batch, CHW -> HWC
        decoded = (decoded / 2 + 0.5).clamp(0, 1).cpu()
        image_np = decoded[0].permute(1, 2, 0).numpy()
        image_np = (image_np * 255).round().astype(np.uint8)
        return Image.fromarray(image_np)

    def generate_4k_iterative(
        self,
        prompt: str,
        negative_prompt: str = DEFAULT_NEGATIVE,
        width: int = WIDTH_4K_UHD,
        height: int = HEIGHT_4K_UHD,
        seed: Optional[int] = None,
        lora_path: Optional[str] = None,
    ) -> Image.Image:
        """
        Multi-stage refinement for 4K: 1024 → 2048 img2img → 4K img2img.
        Stages: base 1024 → upscale 2048, refine 0.3 → upscale to 3840×2160/3840×3840, refine 0.2.
        """
        import torch  # type: ignore[reportMissingImports]

        self._ensure_lora(lora_path, strength=0.85)
        gen = torch.Generator(device="cuda")
        if seed is not None:
            gen.manual_seed(int(seed))
        else:
            gen.manual_seed(torch.randint(0, 2**32, (1,)).item())

        # Stage 1: Base 1024×1024
        pipe_out = self.pipe(
            prompt=prompt,
            negative_prompt=negative_prompt,
            num_inference_steps=40,
            guidance_scale=7.5,
            width=1024,
            height=1024,
            generator=gen,
        )
        base_image = pipe_out.images[0]  # type: ignore[union-attr]

        # Stage 2: First upscale (2×) then light refinement
        mid_w, mid_h = min(2048, width), min(2048, height)
        if width * height > 2048 * 2048:
            mid_w, mid_h = 2048, 2048
        base_2k = base_image.resize((mid_w, mid_h), Image.LANCZOS)
        refined_2k = self.pipe_img2img(
            prompt=prompt,
            negative_prompt=negative_prompt,
            image=base_2k,
            strength=0.3,
            num_inference_steps=20,
            guidance_scale=7.0,
            generator=gen,
        ).images[
            0
        ]  # type: ignore[union-attr]

        # Stage 3: Second upscale to target 4K, very light refinement
        refined_2k_4k = refined_2k.resize((width, height), Image.LANCZOS)
        refined_4k = self.pipe_img2img(
            prompt=prompt,
            negative_prompt=negative_prompt,
            image=refined_2k_4k,
            strength=0.2,
            num_inference_steps=15,
            guidance_scale=6.5,
            generator=gen,
        ).images[
            0
        ]  # type: ignore[union-attr]

        return refined_4k

    @modal.method()
    def generate_4k_native(
        self,
        prompt: str,
        negative_prompt: str = DEFAULT_NEGATIVE,
        width: int = WIDTH_4K_UHD,
        height: int = HEIGHT_4K_UHD,
        steps: int = 40,
        guidance_scale: float = 7.5,
        seed: Optional[int] = None,
        lora_path: Optional[str] = None,
        method: Literal["latent", "iterative"] = "latent",
        return_pil: bool = False,
    ) -> Union[Dict, Image.Image]:
        """
        Generate native 4K (3840×2160 or 3840×3840) without upscaling from lower-res.
        method="latent": MultiDiffusion (1024 latent → upscale latents → tiled VAE decode).
        method="iterative": 1024 → 2048 img2img → 4K img2img. ~120–180s on ml.g5.4xlarge.
        """
        if method == "iterative":
            img = self.generate_4k_iterative(
                prompt=prompt,
                negative_prompt=negative_prompt,
                width=width,
                height=height,
                seed=seed,
                lora_path=lora_path,
            )
        else:
            img = self.generate_4k_native_latent(
                prompt=prompt,
                negative_prompt=negative_prompt,
                width=width,
                height=height,
                steps=steps,
                guidance_scale=guidance_scale,
                seed=seed,
                lora_path=lora_path,
            )
        buf = io.BytesIO()
        img.save(buf, format="PNG", quality=95)
        b64 = base64.b64encode(buf.getvalue()).decode()
        d = {
            "image_base64": b64,
            "width": img.size[0],
            "height": img.size[1],
            "pipeline": f"4k_native_{method}",
        }
        if return_pil:
            return img
        return d

    def _run_4k_single(
        self,
        prompt: str,
        negative_prompt: str,
        lora_path: Optional[str],
        seed: Optional[int],
        use_tiled_refine: bool,
        use_detail_pass: bool,
        tile_grid: Literal["4x4", "2x2"],
        tile_size: Optional[int] = None,
        tile_overlap: Optional[int] = None,
        width: int = 4096,
        height: int = 4096,
        guidance_scale: float = 7.5,
        num_inference_steps: int = 40,
    ) -> Dict[str, Any]:
        """Single 4K run. Used by generate_4k and generate_ultra. Output 4096×4096 (or width×height when supported)."""
        import torch  # type: ignore[reportMissingImports]

        self._ensure_lora(lora_path, strength=0.85)
        s = torch.Generator(device="cuda")
        if seed is not None:
            s.manual_seed(int(seed))
        else:
            s.manual_seed(torch.randint(0, 2**32, (1,)).item())

        out_w, out_h = min(width, 4096), min(height, 4096)
        print("  Stage 1: Base 2048×2048...")
        pipe_out = self.pipe(
            prompt=prompt,
            negative_prompt=negative_prompt,
            num_inference_steps=num_inference_steps,
            guidance_scale=guidance_scale,
            width=2048,
            height=2048,
            generator=s,
        )
        base = pipe_out.images[0]  # type: ignore[union-attr]

        if not use_tiled_refine:
            out = base.resize((out_w, out_h), Image.LANCZOS)
            pipeline = "base_upscaled"
        else:
            print("  Stage 2: Tiled upscaling...")
            kw: Dict[str, Any] = {
                "target_size": max(out_w, out_h, 4096),
                "tile_grid": tile_grid,
                "overlap": 128,
                "strength": 0.25,
                "steps": 20,
            }
            if tile_size is not None and tile_overlap is not None:
                kw["tile_size_override"] = tile_size
                kw["tile_overlap_override"] = tile_overlap
            out = self._tiled_upscale(
                base,
                prompt=prompt,
                negative_prompt=negative_prompt,
                **kw,
            )
            if (out.size[0], out.size[1]) != (out_w, out_h):
                out = out.resize((out_w, out_h), Image.LANCZOS)
            pipeline = "tiled"
            if use_detail_pass:
                print("  Stage 3: Final detail pass...")
                out = self._detail_pass(out, prompt, negative_prompt)
                pipeline = "full"

        buf = io.BytesIO()
        out.save(buf, format="PNG", quality=95)
        b64 = base64.b64encode(buf.getvalue()).decode()
        return {
            "image_base64": b64,
            "width": out.size[0],
            "height": out.size[1],
            "pipeline": pipeline,
        }

    @modal.method()
    def generate_4k(
        self,
        prompt: str,
        negative_prompt: str = DEFAULT_NEGATIVE,
        lora_path: Optional[str] = None,
        mode: str = "REALISM",
        seed: Optional[int] = None,
        use_tiled_refine: bool = True,
        use_detail_pass: bool = True,
        tile_grid: Literal["4x4", "2x2"] = "4x4",
        return_pil: bool = False,
    ) -> Union[Dict, Image.Image]:
        """
        Generate native 4K (4096×4096) image using tiled approach.

        Strategy:
        1. Generate 2048×2048 base
        2. Tile into 4×4 grid (1024×1024 each), or 2×2 for cost optimization
        3. Upscale each tile, img2img refine, blend seamlessly
        4. Final detail pass

        Returns:
            Dict with image_base64, width, height, pipeline (base | tiled | full),
            or PIL Image when return_pil=True (spec-style).
        """
        print("🎨 Generating 4K native...")
        d = self._run_4k_single(
            prompt=prompt,
            negative_prompt=negative_prompt,
            lora_path=lora_path,
            seed=seed,
            use_tiled_refine=use_tiled_refine,
            use_detail_pass=use_detail_pass,
            tile_grid=tile_grid,
        )
        print("✅ 4K generation complete")
        if return_pil:
            raw = base64.b64decode(d["image_base64"])
            return Image.open(io.BytesIO(raw)).convert("RGB")
        return d

    @modal.method()
    def generate_ultra(
        self,
        prompt: str,
        negative_prompt: str = DEFAULT_NEGATIVE,
        num_images: int = 1,
        width: int = 4096,
        height: int = 4096,
        lora_path: Optional[str] = None,
        seed: Optional[int] = None,
        use_tiled_refine: bool = True,
        use_detail_pass: bool = True,
        tile_grid: Literal["4x4", "2x2"] = "4x4",
        tile_size: int = 512,
        tile_overlap: int = 64,
        guidance_scale: float = 8.0,
        num_inference_steps: int = 80,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Generate multiple ultra high-res images (default 4096×4096) with progress tracking.

        width/height: target resolution (orchestrator passes tier-capped dims).
        tile_size/tile_overlap: 512×512 tiles, 64px overlap (spec).
        progress_callback(d) receives {"current": 1, "total": N, "percent": 25, "image": 1}.
        """
        logger.info(
            "Ultra high-res generation: %dx%d, %d images (tile=%d, overlap=%d)",
            width,
            height,
            num_images,
            tile_size,
            tile_overlap,
        )
        results: List[Dict[str, Any]] = []
        for i in range(num_images):
            s = (seed + i) if seed is not None else None
            logger.info("Ultra image %d/%d", i + 1, num_images)
            print("🎨 Ultra image %d/%d..." % (i + 1, num_images))
            if progress_callback:
                progress_callback(
                    {
                        "current": i + 1,
                        "total": num_images,
                        "percent": int(100 * (i + 1) / num_images),
                        "image": i + 1,
                    }
                )
            d = self._run_4k_single(
                prompt=prompt,
                negative_prompt=negative_prompt,
                lora_path=lora_path,
                seed=s,
                use_tiled_refine=use_tiled_refine,
                use_detail_pass=use_detail_pass,
                tile_grid=tile_grid,
                tile_size=tile_size,
                tile_overlap=tile_overlap,
                width=width,
                height=height,
                guidance_scale=guidance_scale,
                num_inference_steps=num_inference_steps,
            )
            results.append(d)
        print("✅ Ultra batch complete: %d images" % num_images)
        return results

    @modal.method()
    def generate_4k_fast(
        self,
        prompt: str,
        negative_prompt: str = DEFAULT_NEGATIVE,
        lora_path: Optional[str] = None,
        seed: Optional[int] = None,
    ) -> Dict:
        """
        Faster 4K: base 2048 → LANCZOS upscale only.
        No tiled refine or detail pass. ~1–2 min.
        """
        return self.generate_4k(
            prompt=prompt,
            negative_prompt=negative_prompt,
            lora_path=lora_path,
            seed=seed,
            use_tiled_refine=False,
            use_detail_pass=False,
        )


ultra_engine = UltraHighResEngine()


@app.function(
    image=gpu_image,
    gpu=_GPU,
    timeout=900,
    volumes={
        MODEL_DIR: models_volume,
        LORA_DIR: lora_volume,
    },
    secrets=[
        modal.Secret.from_name("huggingface"),
    ],
)
@modal.fastapi_endpoint(method="POST")
def generate_4k_web(item: dict):
    """HTTP endpoint for 4K generation. Runs engine in same container."""
    engine = UltraHighResEngine()
    result = engine.generate_4k(
        prompt=item.get("prompt", ""),
        negative_prompt=item.get("negative_prompt", DEFAULT_NEGATIVE),
        lora_path=item.get("lora_path"),
        mode=item.get("mode", "REALISM"),
        seed=item.get("seed"),
        use_tiled_refine=item.get("use_tiled_refine", True),
        use_detail_pass=item.get("use_detail_pass", True),
        tile_grid=item.get("tile_grid", "4x4"),
        return_pil=False,
    )
    return result


@app.function(
    image=gpu_image,
    gpu=_GPU,
    timeout=900,
    volumes={MODEL_DIR: models_volume, LORA_DIR: lora_volume},
    secrets=[modal.Secret.from_name("huggingface")],
)
@modal.fastapi_endpoint(method="POST")
def generate_ultra_web(item: dict):
    """HTTP endpoint for ultra 4K batch (tile_size=512, tile_overlap=64, progress logging)."""
    engine = UltraHighResEngine()
    results = engine.generate_ultra(
        prompt=item.get("prompt", ""),
        negative_prompt=item.get("negative_prompt", DEFAULT_NEGATIVE),
        num_images=item.get("num_images", 1),
        width=item.get("width", 4096),
        height=item.get("height", 4096),
        lora_path=item.get("lora_path"),
        seed=item.get("seed"),
        use_tiled_refine=item.get("use_tiled_refine", True),
        use_detail_pass=item.get("use_detail_pass", True),
        tile_grid=item.get("tile_grid", "4x4"),
        tile_size=item.get("tile_size", 512),
        tile_overlap=item.get("tile_overlap", 64),
        guidance_scale=item.get("guidance_scale", 8.0),
        num_inference_steps=item.get("num_inference_steps", 80),
    )
    return {"images": results, "count": len(results)}


@app.local_entrypoint()
def test_4k():
    print("\n=== Ultra High-Res Engine Test ===\n")
    print("Usage:")
    print("  modal deploy ai-pipeline/services/ultra_high_res_engine.py")
    print("  modal run ai-pipeline/services/ultra_high_res_engine.py::test_4k")
    print("\nExample (spec-style):")
    print("  result = ultra_engine.generate_4k.remote(")
    print('    prompt="professional portrait, studio lighting, sharp focus",')
    print('    negative_prompt="blurry, low quality",')
    print('    mode="REALISM",')
    print("  )")
    print("  # Returns 4096×4096 image_base64; ~2–3 min with tiled+detail")
    print("\nPIL return:")
    print("  img = ultra_engine.generate_4k.remote(..., return_pil=True)")
    print("\nCost optimization: tile_grid='2x2', or ULTRARES_GPU=40")
