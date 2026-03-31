"""
Modal.com deployment for PhotoGenius AI Service

Deploy:   modal deploy modal_app.py
Test:     modal run modal_app.py::generate_image --prompt "a portrait"
Logs:     modal app logs photogenius-ai
Download: modal run modal_app.py::download_models

Functions:
- fastapi_app:       Full FastAPI ASGI (API routes)
- generate_image:    GPU image generation (SDXL/Turbo + LoRA)
- train_lora:        GPU LoRA training for identity consistency
- run_safety_check:  Safety classification (NSFW + age)
- download_models:   Pre-download all models to volume
"""

import modal  # type: ignore[reportMissingImports]
from pathlib import Path

_THIS_DIR = Path(__file__).parent

# ---------------------------------------------------------------------------
# Modal App & Volumes
# ---------------------------------------------------------------------------

modal_app = modal.App("photogenius-ai")
app = modal_app  # Alias for `modal deploy modal_app.py`

# Persistent volumes for model weights and LoRA checkpoints
model_volume = modal.Volume.from_name("photogenius-models", create_if_missing=True)
lora_volume = modal.Volume.from_name("photogenius-loras", create_if_missing=True)

VOLUME_MOUNTS = {
    "/root/.cache/huggingface": model_volume,
    "/root/loras": lora_volume,
}

# ---------------------------------------------------------------------------
# Container image
# ---------------------------------------------------------------------------

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("git", "build-essential", "libpq-dev", "libgl1-mesa-glx", "libglib2.0-0")
    .pip_install(
        # Web framework
        "fastapi==0.104.1",
        "uvicorn[standard]==0.24.0",
        "pydantic==2.5.0",
        "pydantic-settings>=2.0.0",
        "python-multipart==0.0.6",
        # ML / GPU
        "torch==2.1.1",
        "torchvision==0.16.1",
        "diffusers==0.24.0",
        "transformers==4.37.0",
        "accelerate==0.25.0",
        "safetensors>=0.4.0",
        "peft>=0.7.0",
        # Vision & face
        "pillow==10.1.0",
        "numpy==1.24.3",
        "opencv-python-headless==4.8.1.78",
        "insightface==0.7.3",
        "onnxruntime-gpu==1.16.3",
        # Storage & networking
        "boto3==1.29.7",
        "httpx==0.25.0",
        # Database
        "asyncpg==0.29.0",
        "redis==5.0.1",
        "sqlalchemy[asyncio]>=2.0.0",
    )
    .env({
        "HF_HOME": "/root/.cache/huggingface",
        "MODEL_CACHE_DIR": "/root/.cache/huggingface",
        "LORA_STORAGE_DIR": "/root/loras",
    })
    .add_local_dir(_THIS_DIR / "app", remote_path="/root/app")
)

# Secrets (create in Modal dashboard)
# modal secret create photogenius-secrets HUGGINGFACE_TOKEN=xxx S3_BUCKET_NAME=xxx ...
secrets = []

# ---------------------------------------------------------------------------
# 1. FastAPI ASGI App (serves all REST API routes)
# ---------------------------------------------------------------------------

@modal_app.function(
    image=image,
    gpu="A10G",
    timeout=600,
    secrets=secrets,
    memory=16384,
    scaledown_window=300,
    volumes=VOLUME_MOUNTS,
)
@modal.asgi_app(label="fastapi-app")
def fastapi_app():
    """Mount the full FastAPI application with all routes."""
    from app.main import app as fastapi_application
    return fastapi_application


# ---------------------------------------------------------------------------
# 2. Image Generation (GPU)
# ---------------------------------------------------------------------------

@modal_app.function(
    image=image,
    gpu="A10G",
    timeout=300,
    secrets=secrets,
    memory=16384,
    scaledown_window=120,
    volumes=VOLUME_MOUNTS,
)
def generate_image(
    prompt: str,
    mode: str = "realism",
    identity_id: str | None = None,
    lora_path: str | None = None,
    num_outputs: int = 2,
    width: int = 1024,
    height: int = 1024,
    seed: int | None = None,
) -> dict:
    """
    Generate images on GPU.

    Returns dict with image_urls, best_url, scores, generation_time_seconds.
    """
    from app.services.ai.generation_service import (  # type: ignore[reportAttributeAccessIssue]
        GenerationRequest,
        get_generation_service,
    )

    svc = get_generation_service()
    if hasattr(svc, "load_models"):
        svc.load_models()

    # Resolve LoRA path from volume if identity_id provided
    resolved_lora = lora_path
    if not resolved_lora and identity_id:
        candidate = Path(f"/root/loras/{identity_id}/{identity_id}.safetensors")
        if candidate.exists():
            resolved_lora = str(candidate)

    request = GenerationRequest(
        prompt=prompt,
        mode=mode,
        identity_id=identity_id,
        lora_path=resolved_lora,
        num_outputs=num_outputs,
        width=width,
        height=height,
        seed=seed,
    )

    result = svc.generate(request)
    return {
        "image_urls": result.image_urls,
        "best_url": result.best_url,
        "scores": result.scores,
        "generation_time_seconds": result.generation_time_seconds,
        "mode": result.mode,
        "seed": result.seed,
    }


# ---------------------------------------------------------------------------
# 3. LoRA Training (GPU, long-running)
# ---------------------------------------------------------------------------

@modal_app.function(
    image=image,
    gpu="A10G",
    timeout=1800,  # 30 min max for training
    secrets=secrets,
    memory=24576,  # 24GB RAM for training
    scaledown_window=60,
    volumes=VOLUME_MOUNTS,
)
def train_lora(
    identity_id: str,
    image_urls: list[str],
    num_train_steps: int = 1000,
    learning_rate: float = 1e-4,
    rank: int = 32,
) -> dict:
    """
    Train a LoRA for identity consistency on GPU.

    Returns dict with identity_id, lora_path, training_time_seconds, etc.
    """
    from app.services.ai.lora_trainer import (  # type: ignore[reportAttributeAccessIssue]
        train_lora_sync,
        TrainingConfig,
        _download_images,
        _preprocess_images,
    )
    from pathlib import Path
    import tempfile

    config = TrainingConfig(
        num_train_steps=num_train_steps,
        learning_rate=learning_rate,
        rank=rank,
        alpha=rank,
        resolution=1024,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        download_dir = tmp / "raw"
        processed_dir = tmp / "processed"
        download_dir.mkdir()
        processed_dir.mkdir()

        raw_paths = _download_images(image_urls, download_dir)
        if not raw_paths:
            return {"success": False, "error": "No images could be downloaded"}

        processed = _preprocess_images(raw_paths, config.resolution, processed_dir)
        if not processed:
            return {"success": False, "error": "No images could be preprocessed"}

        result = train_lora_sync(identity_id, processed, config)

    # Copy LoRA to persistent volume
    import shutil
    lora_src = Path(result.lora_path)
    lora_dest = Path(f"/root/loras/{identity_id}")
    lora_dest.mkdir(parents=True, exist_ok=True)
    if lora_src.exists():
        dest_file = lora_dest / f"{identity_id}.safetensors"
        shutil.copy2(str(lora_src), str(dest_file))
        result.lora_path = str(dest_file)
        lora_volume.commit()

    return {
        "success": True,
        "identity_id": result.identity_id,
        "lora_path": result.lora_path,
        "training_time_seconds": result.training_time_seconds,
        "num_images_used": result.num_images_used,
        "quality_score": result.quality_score,
        "final_loss": result.final_loss,
    }


# ---------------------------------------------------------------------------
# 4. Safety Check (GPU-accelerated)
# ---------------------------------------------------------------------------

@modal_app.function(
    image=image,
    gpu="T4",  # Smaller GPU sufficient for classification
    timeout=60,
    secrets=secrets,
    memory=8192,
    scaledown_window=300,
    volumes=VOLUME_MOUNTS,
)
def run_safety_check(
    prompt: str,
    image_path: str | None = None,
) -> dict:
    """
    Run safety checks on prompt and/or generated image.

    Returns dict with allowed, blocked_reason, nsfw_score, etc.
    """
    from app.services.safety.safety_service import get_safety_service

    svc = get_safety_service()
    svc.load_models()

    result = svc.full_check(prompt, image_path)
    return {
        "allowed": result.allowed,
        "blocked_reason": result.blocked_reason,
        "nsfw_score": result.nsfw_score,
        "age_estimate": result.age_estimate,
        "prompt_violations": result.prompt_violations,
    }


# ---------------------------------------------------------------------------
# 5. Model Download (run once to populate volume)
# ---------------------------------------------------------------------------

@modal_app.function(
    image=image,
    timeout=1800,
    secrets=secrets,
    memory=16384,
    volumes=VOLUME_MOUNTS,
)
def download_models() -> dict:
    """Pre-download all models to persistent volume."""
    from app.services.ai.download_models import download_all

    results = download_all()
    model_volume.commit()
    return results
