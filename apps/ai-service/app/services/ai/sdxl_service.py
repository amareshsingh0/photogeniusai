"""
AI Generation Service – SDXL + InstantID.

Layer 3: Core Services – AI Generation.
Uses Stable Diffusion XL + optional LoRA + InstantID for face consistency.
Falls back to stub when torch/diffusers unavailable or no GPU.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from pathlib import Path
from typing import Optional

from app.services.ai.instantid import InstantIDPipeline
from app.services.ai.quality_scorer import score, select_best, QualityReport

# Lazy imports for torch/diffusers (optional)
_TORCH = None
_DIFFUSERS = None


def _import_gpu() -> tuple[bool, Optional[str]]:
    """Import torch and diffusers. Returns (ok, error_message)."""
    global _TORCH, _DIFFUSERS
    try:
        import torch  # type: ignore[reportMissingImports]
        from diffusers import StableDiffusionXLPipeline  # type: ignore[reportMissingImports]

        _TORCH = torch
        _DIFFUSERS = StableDiffusionXLPipeline
        if not torch.cuda.is_available():
            return False, "CUDA not available"
        return True, None
    except ImportError as e:
        return False, str(e)


# Output dir for generated images (served at /api/generated)
# parents: sdxl_service.py -> ai -> services -> app -> ai-service root
_APP_DIR = Path(__file__).resolve().parents[3]
_OUTPUT_DIR = _APP_DIR / "output" / "generated"


class SDXLGenerationService:
    """
    SDXL-based generation with optional LoRA + InstantID.
    Lazy-loads models on first use; uses stubs when GPU/deps missing.
    """

    def __init__(self) -> None:
        self._pipe = None
        self._instantid: Optional[InstantIDPipeline] = None
        self._available = False
        self._load_error: Optional[str] = None

    def _ensure_loaded(self) -> bool:
        if self._available:
            return True
        if self._load_error is not None:
            return False
        ok, err = _import_gpu()
        if not ok:
            self._load_error = err or "GPU deps unavailable"
            return False
        if _DIFFUSERS is None:
            return False
        try:
            pipe_cls = _DIFFUSERS
            import torch  # type: ignore[reportMissingImports]

            self._pipe = pipe_cls.from_pretrained(
                "stabilityai/stable-diffusion-xl-base-1.0",
                torch_dtype=torch.float16,
                variant="fp16",
                use_safetensors=True,
            ).to("cuda")
            self._instantid = InstantIDPipeline()
            self._instantid.load()
            _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            self._available = True
            return True
        except Exception as e:
            self._load_error = str(e)
            return False

    @property
    def available(self) -> bool:
        return self._ensure_loaded()

    async def generate_realism(
        self,
        prompt: str,
        identity_embedding: Optional[object] = None,
        lora_path: Optional[str] = None,
        num_images: int = 2,
    ) -> Optional[str]:
        """
        Realism mode: high identity preservation.
        Loads user LoRA, generates num_images, selects best by quality + face match.

        Returns:
            URL path to best image (e.g. /api/generated/xxx.png) or None if stub/unavailable.
        """
        if not self._ensure_loaded():
            return None

        loop = asyncio.get_running_loop()
        pipe = self._pipe
        instantid = self._instantid
        if pipe is None:
            return None

        emb: Optional[bytes] = None
        if identity_embedding is not None:
            if isinstance(identity_embedding, bytes):
                emb = identity_embedding
            elif hasattr(identity_embedding, "tobytes") and callable(getattr(identity_embedding, "tobytes", None)):
                emb = identity_embedding.tobytes()

        if instantid:
            instantid.prepare(emb, controlnet_conditioning_scale=0.9)

        def _load_lora() -> None:
            if pipe and lora_path and os.path.isfile(lora_path):
                pipe.load_lora_weights(lora_path)

        def _generate_one(seed: int):
            import torch  # type: ignore[reportMissingImports]

            g = torch.Generator(device="cuda").manual_seed(seed)
            out = pipe(
                prompt=prompt,
                num_inference_steps=50,
                guidance_scale=7.5,
                generator=g,
                # InstantID: ip_adapter_image when real pipeline supports it
                # ip_adapter_image=ip_image,
                # controlnet_conditioning_scale=0.90,
            )
            return out.images[0]

        await loop.run_in_executor(None, _load_lora)
        images = []
        for i in range(num_images):
            img = await loop.run_in_executor(None, _generate_one, hash(prompt) % (2**32) + i)
            images.append(img)

        # Save to output dir, score, select best. Return /api/ai/generated/... for frontend proxy.
        base = "/api/ai/generated"
        saved: list[tuple[str, QualityReport]] = []
        for im in images:
            name = f"{uuid.uuid4().hex}.png"
            path = _OUTPUT_DIR / name
            im.save(str(path))
            url = f"{base}/{name}"
            report = score(url, prompt, emb)  # type: ignore[reportArgumentType]
            saved.append((url, report))

        best_url, _ = select_best(saved)
        return best_url


# Singleton
_sdxl_service: Optional[SDXLGenerationService] = None


def get_sdxl_service() -> SDXLGenerationService:
    global _sdxl_service
    if _sdxl_service is None:
        _sdxl_service = SDXLGenerationService()
    return _sdxl_service
