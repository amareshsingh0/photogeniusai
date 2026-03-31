"""
SDXL-Turbo preview + full-quality pipeline.
Connect to GPU (RunPod/Modal) and HuggingFace models.

Production:
- SDXL-Turbo for preview (4 steps, ~3s)
- SDXL 1.0 for full quality (25-50 steps, ~25s)
- LoRA for identity consistency
- Best-of-N selection with quality scoring
"""

import asyncio
import uuid
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

from app.core.config import settings  # type: ignore[reportAttributeAccessIssue]
from app.services.ai.sdxl_service import get_sdxl_service


@dataclass
class GenerationConfig:
    """Configuration for image generation."""
    num_inference_steps: int = 4  # Turbo: 4, Full: 25-50
    guidance_scale: float = 1.0   # Turbo: 1.0, Full: 7.5
    width: int = 1024
    height: int = 1024
    seed: Optional[int] = None


# Preview config (fast, ~3s)
PREVIEW_CONFIG = GenerationConfig(num_inference_steps=4, guidance_scale=1.0)

# Full quality config (~25s)
FULL_CONFIG = GenerationConfig(num_inference_steps=30, guidance_scale=7.5)

# Output directory for generated images
_APP_DIR = Path(__file__).resolve().parents[3]
_OUTPUT_DIR = _APP_DIR / "output" / "generated"
_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def _create_placeholder(prompt: str, label: str = "Preview") -> str:
    """Create a placeholder image with PIL and return a servable URL path."""
    try:
        from PIL import Image, ImageDraw, ImageFont  # type: ignore[reportMissingImports]
    except ImportError:
        # PIL not available - return inline data
        return "/api/generated/placeholder.png"

    img = Image.new("RGB", (1024, 1024), color=(24, 24, 32))
    draw = ImageDraw.Draw(img)

    # Draw gradient-like background
    for y in range(1024):
        r = int(24 + (y / 1024) * 20)
        g = int(24 + (y / 1024) * 10)
        b = int(32 + (y / 1024) * 40)
        draw.line([(0, y), (1023, y)], fill=(r, g, b))

    # Draw text
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
        small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 22)
    except (OSError, IOError):
        font = ImageFont.load_default()
        small_font = font

    draw.text((512, 420), "PhotoGenius AI", fill=(0, 212, 255), font=font, anchor="mm")
    draw.text((512, 480), label, fill=(180, 180, 200), font=small_font, anchor="mm")

    short_prompt = prompt[:80] + "..." if len(prompt) > 80 else prompt
    draw.text((512, 540), f'"{short_prompt}"', fill=(120, 120, 140), font=small_font, anchor="mm")

    draw.rectangle([(20, 20), (1003, 1003)], outline=(0, 212, 255), width=2)

    name = f"{uuid.uuid4().hex}.png"
    path = _OUTPUT_DIR / name
    img.save(str(path))
    return f"/api/generated/{name}"


async def generate_preview(
    prompt: str,
    identity_embedding: Optional[bytes] = None,
    config: GenerationConfig = PREVIEW_CONFIG,
) -> str:
    """
    Generate a quick preview using SDXL-Turbo.
    Falls back to a placeholder image when GPU is unavailable.
    """
    svc = get_sdxl_service()
    if svc.available:
        url = await svc.generate_realism(
            prompt=prompt,
            identity_embedding=identity_embedding,
            lora_path=None,
            num_images=1,
        )
        if url:
            return url

    # Fallback: generate a placeholder image
    await asyncio.sleep(1.0)
    return _create_placeholder(prompt, label="Preview")


async def generate_full(
    prompt: str,
    identity_embedding: Optional[bytes] = None,
    num_outputs: int = 2,
    config: GenerationConfig = FULL_CONFIG,
) -> str:
    """
    Generate full-quality image with Best-of-N selection.
    Uses SDXLGenerationService when GPU/deps available, else placeholder.
    """
    svc = get_sdxl_service()
    if svc.available:
        url = await svc.generate_realism(
            prompt=prompt,
            identity_embedding=identity_embedding,
            lora_path=None,
            num_images=num_outputs,
        )
        if url:
            return url

    await asyncio.sleep(2.0)
    return _create_placeholder(prompt, label="Full Quality")


async def apply_identity_lora(
    base_prompt: str,
    identity_id: str,
    strength: float = 0.8,
) -> str:
    """
    Apply user-specific LoRA for face consistency.

    TODO: Load user LoRA weights from storage
    """
    return f"{base_prompt} in the style of <identity:{identity_id}>"


# -----------------------------------------------------------------------------
# generate_with_mode for /api/v1/generate
# -----------------------------------------------------------------------------

async def generate_with_mode(
    prompt: str,
    mode: str,
    identity: Optional[object] = None,
    num_outputs: int = 2,
) -> list[str]:
    """
    Generate images for given mode and optional identity.
    Uses SDXLGenerationService for realism when GPU available.
    """
    embedding = getattr(identity, "embedding", None) if identity else None
    identity_id = getattr(identity, "identity_id", None) if identity else None
    lora_path = getattr(identity, "lora_path", None) if identity else None
    use_prompt = prompt
    if identity_id:
        use_prompt = await apply_identity_lora(prompt, identity_id)

    svc = get_sdxl_service()
    if mode == "realism" and svc.available:
        best = await svc.generate_realism(
            prompt=use_prompt,
            identity_embedding=embedding,
            lora_path=lora_path,
            num_images=num_outputs,
        )
        if best:
            return [best]

    # Fallback: generate placeholder images
    await asyncio.sleep(2.0)
    urls = []
    for i in range(num_outputs):
        url = _create_placeholder(use_prompt, label=f"{mode.title()} #{i+1}")
        urls.append(url)
    return urls
