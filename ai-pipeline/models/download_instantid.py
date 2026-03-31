"""
Download InstantID Models for PhotoGenius AI

InstantID is a state-of-the-art face identity preservation model.
This script downloads all required InstantID models from HuggingFace to local/EFS.
No Modal; uses MODEL_DIR from env. AWS-compatible.

Usage:
    python -m ai_pipeline.models.download_instantid
    # or: MODEL_DIR=/path python download_instantid.py

Models will be available in MODEL_DIR/instantid/ (default /models/instantid).
"""

import os
from pathlib import Path

MODEL_DIR = os.environ.get("MODEL_DIR", "/models")


def download_instantid() -> dict:
    """
    Download InstantID models from HuggingFace to MODEL_DIR.
    Returns dict with status and location of downloaded models.
    """
    from huggingface_hub import hf_hub_download  # type: ignore[reportMissingImports]

    hf_token = os.environ.get("HUGGINGFACE_TOKEN") or os.environ.get("HF_TOKEN")
    repo_id = "InstantX/InstantID"
    base = Path(MODEL_DIR)
    instantid_dir = base / "instantid"
    instantid_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("📥 Downloading InstantID Models")
    print("=" * 60)
    print(f"Repository: {repo_id}")
    print(f"Destination: {instantid_dir}")
    print()

    files_to_download = [
        "ip-adapter.bin",
        "ControlNetModel/config.json",
        "ControlNetModel/diffusion_pytorch_model.safetensors",
    ]

    downloaded_files = []

    print("📦 Downloading InstantID core models...")
    for file_path in files_to_download:
        print(f"\n  📥 Downloading {file_path}...")
        kw = {
            "repo_id": repo_id,
            "filename": file_path,
            "local_dir": str(instantid_dir),
            "resume_download": True,
        }
        if hf_token:
            kw["token"] = hf_token
        local_path = hf_hub_download(**kw)
        file_size = os.path.getsize(local_path) / (1024 * 1024)
        print(f"  ✅ Saved to {local_path} ({file_size:.1f} MB)")
        downloaded_files.append(local_path)

    print("\n📦 Downloading CLIP image encoder...")
    clip_encoder_dir = instantid_dir / "image_encoder"
    clip_encoder_dir.mkdir(parents=True, exist_ok=True)
    clip_repo_id = "laion/CLIP-ViT-H-14-laion2B-s32B-b79K"
    clip_files = ["config.json", "pytorch_model.bin"]

    for fn in clip_files:
        print(f"\n  📥 Downloading {fn}...")
        kw = {
            "repo_id": clip_repo_id,
            "filename": fn,
            "local_dir": str(clip_encoder_dir),
            "resume_download": True,
        }
        if hf_token:
            kw["token"] = hf_token
        local_path = hf_hub_download(**kw)
        file_size = os.path.getsize(local_path) / (1024 * 1024)
        print(f"  [OK] Saved to {local_path} ({file_size:.1f} MB)")
        downloaded_files.append(local_path)

    required_files = [
        instantid_dir / "ip-adapter.bin",
        instantid_dir / "ControlNetModel" / "config.json",
        instantid_dir / "ControlNetModel" / "diffusion_pytorch_model.safetensors",
        instantid_dir / "image_encoder" / "config.json",
        instantid_dir / "image_encoder" / "pytorch_model.bin",
    ]

    all_present = all(f.exists() for f in required_files)
    if not all_present:
        raise RuntimeError("Some required files are missing after download")

    total_size = sum(f.stat().st_size for f in required_files if f.exists()) / (
        1024 * 1024 * 1024
    )

    print("\n" + "=" * 60)
    print("✅ InstantID Models Download Complete!")
    print("=" * 60)
    print(f"Total size: {total_size:.2f} GB")
    print(f"Location: {instantid_dir}/")

    return {
        "status": "success",
        "location": str(instantid_dir),
        "files": [str(f.relative_to(base)) for f in required_files if f.exists()],
        "total_size_gb": round(total_size, 2),
    }


def main() -> None:
    """Entrypoint."""
    print("\n🚀 Starting InstantID model download...")
    print("This may take 10-20 minutes depending on your connection.\n")

    try:
        result = download_instantid()
        print("\n🎉 Download Complete!")
        print(f"Status: {result['status']}")
        print(f"Location: {result['location']}")
        print(f"Total Size: {result['total_size_gb']} GB")
    except Exception as e:
        print(f"\n❌ Download failed: {e}")
        raise


if __name__ == "__main__":
    main()
