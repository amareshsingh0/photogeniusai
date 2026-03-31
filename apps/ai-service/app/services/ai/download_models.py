"""
Model download & caching for Modal GPU environment.

Pre-downloads all required models into a Modal Volume so they're
available instantly when GPU functions cold-start.

Usage (local):
    python -m app.services.ai.download_models

Usage (Modal):
    modal run modal_app.py::download_models
"""

import os
from pathlib import Path

# Default cache directory (overridden by Modal volume mount)
MODEL_CACHE_DIR = os.getenv("MODEL_CACHE_DIR", "/root/.cache/huggingface")

# ---------------------------------------------------------------------------
# Model registry – every model the pipeline needs
# ---------------------------------------------------------------------------

MODELS = {
    "sdxl_base": {
        "repo_id": "stabilityai/stable-diffusion-xl-base-1.0",
        "variant": "fp16",
        "type": "diffusers",
    },
    "sdxl_turbo": {
        "repo_id": "stabilityai/sdxl-turbo",
        "variant": "fp16",
        "type": "diffusers",
    },
    "safety_checker": {
        "repo_id": "CompVis/stable-diffusion-safety-checker",
        "type": "transformers",
    },
    "clip_vit": {
        "repo_id": "openai/clip-vit-large-patch14",
        "type": "transformers",
    },
    "insightface_buffalo": {
        "repo_id": "deepinsight/insightface",
        "subfolder": "models/buffalo_l",
        "type": "manual",
    },
}


def download_diffusers_model(repo_id: str, variant: str | None = None) -> Path:
    """Download a diffusers pipeline model."""
    from diffusers import DiffusionPipeline  # type: ignore[reportMissingImports]

    kwargs: dict = {
        "cache_dir": MODEL_CACHE_DIR,
        "torch_dtype": "auto",
    }
    if variant:
        kwargs["variant"] = variant
        kwargs["use_safetensors"] = True

    print(f"  Downloading {repo_id} (variant={variant})...")
    path = DiffusionPipeline.download(repo_id, **kwargs)
    print(f"  -> cached at {path}")
    return Path(str(path))


def download_transformers_model(repo_id: str) -> Path:
    """Download a transformers model."""
    from huggingface_hub import snapshot_download  # type: ignore[reportMissingImports]

    print(f"  Downloading {repo_id}...")
    path = snapshot_download(repo_id, cache_dir=MODEL_CACHE_DIR)
    print(f"  -> cached at {path}")
    return Path(path)


def download_all() -> dict[str, str]:
    """Download all models. Returns mapping of name -> local path."""
    os.makedirs(MODEL_CACHE_DIR, exist_ok=True)
    results: dict[str, str] = {}

    for name, info in MODELS.items():
        repo_id = info["repo_id"]
        model_type = info["type"]

        try:
            if model_type == "diffusers":
                p = download_diffusers_model(repo_id, variant=info.get("variant"))
            elif model_type == "transformers":
                p = download_transformers_model(repo_id)
            elif model_type == "manual":
                from huggingface_hub import snapshot_download  # type: ignore[reportMissingImports]

                subfolder = info.get("subfolder")
                print(f"  Downloading {repo_id} (subfolder={subfolder})...")
                p = Path(snapshot_download(repo_id, cache_dir=MODEL_CACHE_DIR))
                print(f"  -> cached at {p}")
            else:
                print(f"  Skipping unknown type: {model_type}")
                continue
            results[name] = str(p)
        except Exception as e:
            print(f"  ERROR downloading {name}: {e}")
            results[name] = f"ERROR: {e}"

    return results


if __name__ == "__main__":
    print("Downloading all models for PhotoGenius AI pipeline...")
    results = download_all()
    print("\nResults:")
    for name, path in results.items():
        print(f"  {name}: {path}")
