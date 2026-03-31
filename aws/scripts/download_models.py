"""
AWS Model Download Script – populate local/EFS/S3 with all required models.

No Modal. For AWS: run on EC2 or locally, then sync to S3/EFS for SageMaker.
Downloads: SDXL Base, SDXL Turbo, SDXL Refiner, InstantID, InsightFace, Sentence Transformer.
Total storage: ~25GB.

Usage:
  MODEL_DIR=/data/models python download_models.py
  python download_models.py --model-dir ./models
  python download_models.py --verify-only
  python download_models.py --s3-bucket my-bucket [--s3-prefix models/]
"""

from __future__ import annotations

import argparse
import os
import sys
import zipfile
from pathlib import Path

# Default: ./models or /models on Linux
MODEL_DIR = os.environ.get("MODEL_DIR", str(Path(__file__).resolve().parent.parent / "models"))
HF_TOKEN = os.environ.get("HUGGINGFACE_TOKEN") or os.environ.get("HF_TOKEN")


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def download_sdxl_base(models_root: Path) -> None:
    """SDXL Base (~6.9GB)."""
    from huggingface_hub import snapshot_download

    dest = models_root / "stable-diffusion-xl-base-1.0"
    if (dest / "model_index.json").exists():
        print("  [skip] SDXL Base already present")
        return
    print("  📥 Downloading SDXL Base (~6.9GB)...")
    kwargs = {
        "repo_id": "stabilityai/stable-diffusion-xl-base-1.0",
        "local_dir": str(dest),
        "local_dir_use_symlinks": False,
        "resume_download": True,
    }
    if HF_TOKEN:
        kwargs["token"] = HF_TOKEN
    snapshot_download(**kwargs)
    print("  ✅ SDXL Base downloaded")


def download_sdxl_turbo(models_root: Path) -> None:
    """SDXL Turbo (~6.9GB)."""
    from huggingface_hub import snapshot_download

    dest = models_root / "sdxl-turbo"
    if (dest / "model_index.json").exists():
        print("  [skip] SDXL Turbo already present")
        return
    print("  📥 Downloading SDXL Turbo (~6.9GB)...")
    kwargs = {
        "repo_id": "stabilityai/sdxl-turbo",
        "local_dir": str(dest),
        "local_dir_use_symlinks": False,
        "resume_download": True,
    }
    if HF_TOKEN:
        kwargs["token"] = HF_TOKEN
    snapshot_download(**kwargs)
    print("  ✅ SDXL Turbo downloaded")


def download_sdxl_refiner(models_root: Path) -> None:
    """SDXL Refiner (~6.9GB)."""
    from huggingface_hub import snapshot_download

    dest = models_root / "stable-diffusion-xl-refiner-1.0"
    if (dest / "model_index.json").exists():
        print("  [skip] SDXL Refiner already present")
        return
    print("  📥 Downloading SDXL Refiner (~6.9GB)...")
    kwargs = {
        "repo_id": "stabilityai/stable-diffusion-xl-refiner-1.0",
        "local_dir": str(dest),
        "local_dir_use_symlinks": False,
        "resume_download": True,
    }
    if HF_TOKEN:
        kwargs["token"] = HF_TOKEN
    snapshot_download(**kwargs)
    print("  ✅ SDXL Refiner downloaded")


def download_instantid(models_root: Path) -> None:
    """InstantID (~500MB)."""
    from huggingface_hub import snapshot_download

    dest = models_root / "instantid"
    if (dest / "ip-adapter.bin").exists() and (dest / "ControlNetModel").exists():
        print("  [skip] InstantID already present")
        return
    print("  📥 Downloading InstantID (~500MB)...")
    kwargs = {
        "repo_id": "InstantX/InstantID",
        "local_dir": str(dest),
        "local_dir_use_symlinks": False,
        "resume_download": True,
    }
    if HF_TOKEN:
        kwargs["token"] = HF_TOKEN
    snapshot_download(**kwargs)
    # Optional: CLIP image encoder for InstantID (if not in repo)
    clip_dir = dest / "image_encoder"
    if not (clip_dir / "config.json").exists():
        try:
            from huggingface_hub import hf_hub_download
            clip_repo = "laion/CLIP-ViT-H-14-laion2B-s32B-b79K"
            clip_dir.mkdir(parents=True, exist_ok=True)
            for fn in ["config.json", "pytorch_model.bin"]:
                hf_hub_download(
                    repo_id=clip_repo,
                    filename=fn,
                    local_dir=str(clip_dir),
                    resume_download=True,
                    token=HF_TOKEN,
                )
        except Exception as e:
            print("  ⚠️ CLIP encoder optional:", e)
    print("  ✅ InstantID downloaded")


def download_insightface(models_root: Path) -> None:
    """InsightFace buffalo_l (~400MB)."""
    dest = models_root / "insightface"
    _ensure_dir(dest)
    zip_path = dest / "buffalo_l.zip"
    buffalo_dir = dest / "buffalo_l"
    if buffalo_dir.exists() and any(buffalo_dir.iterdir()):
        print("  [skip] InsightFace buffalo_l already present")
        return
    print("  📥 Downloading InsightFace buffalo_l (~400MB)...")
    try:
        from huggingface_hub import hf_hub_download
        hf_hub_download(
            repo_id="public-data/insightface",
            filename="models/buffalo_l.zip",
            local_dir=str(dest),
            resume_download=True,
            token=HF_TOKEN,
        )
        # Move from models/buffalo_l.zip to buffalo_l.zip if needed
        alt_zip = dest / "models" / "buffalo_l.zip"
        if alt_zip.exists():
            import shutil
            shutil.move(str(alt_zip), str(zip_path))
    except Exception:
        # Fallback: GitHub release
        import urllib.request
        url = "https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_l.zip"
        urllib.request.urlretrieve(url, zip_path)
    if zip_path.exists():
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(dest)
        zip_path.unlink(missing_ok=True)
    if not buffalo_dir.exists():
        buffalo_dir.mkdir(parents=True, exist_ok=True)
    print("  ✅ InsightFace downloaded")


def download_sentence_transformer(models_root: Path) -> None:
    """Sentence Transformer all-MiniLM-L6-v2 (~66MB)."""
    dest = models_root / "sentence-transformers" / "all-MiniLM-L6-v2"
    if (dest / "config.json").exists():
        print("  [skip] Sentence Transformer already present")
        return
    print("  📥 Downloading Sentence Transformer (~66MB)...")
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        _ensure_dir(dest)
        model.save(str(dest))
    except ImportError:
        # Fallback: clone via huggingface_hub
        from huggingface_hub import snapshot_download
        snapshot_download(
            repo_id="sentence-transformers/all-MiniLM-L6-v2",
            local_dir=str(dest),
            local_dir_use_symlinks=False,
            resume_download=True,
            token=HF_TOKEN,
        )
    print("  ✅ Sentence Transformer downloaded")


def download_all_models(model_dir: str | Path) -> None:
    """Run all download steps with progress and error handling."""
    root = Path(model_dir)
    root.mkdir(parents=True, exist_ok=True)
    steps = [
        ("SDXL Base", lambda: download_sdxl_base(root)),
        ("SDXL Turbo", lambda: download_sdxl_turbo(root)),
        ("SDXL Refiner", lambda: download_sdxl_refiner(root)),
        ("InstantID", lambda: download_instantid(root)),
        ("InsightFace", lambda: download_insightface(root)),
        ("Sentence Transformer", lambda: download_sentence_transformer(root)),
    ]
    for name, fn in steps:
        print(f"\n📦 {name}...")
        try:
            fn()
        except Exception as e:
            print(f"❌ {name} failed: {e}")
            raise
    print("\n✅ All models downloaded to %s" % root)


def verify_models(model_dir: str | Path) -> bool:
    """Check that required paths exist. Returns True if all present."""
    root = Path(model_dir)
    required = [
        root / "stable-diffusion-xl-base-1.0" / "model_index.json",
        root / "sdxl-turbo" / "model_index.json",
        root / "stable-diffusion-xl-refiner-1.0" / "model_index.json",
        root / "instantid" / "ip-adapter.bin",
        root / "insightface",  # dir
        root / "sentence-transformers" / "all-MiniLM-L6-v2",  # dir
    ]
    all_ok = True
    for p in required:
        exists = p.exists()
        if not exists and p.name == "insightface":
            exists = (root / "insightface" / "buffalo_l").exists() or (root / "insightface").exists()
        if not exists and "sentence-transformers" in str(p):
            exists = (root / "sentence-transformers").exists()
        label = "✅" if exists else "❌"
        print(f"  {label} {p}")
        if not exists:
            all_ok = False
    return all_ok


def upload_to_s3(model_dir: str | Path, bucket: str, prefix: str = "models/") -> None:
    """Upload model dir to S3 (for SageMaker). Uses AWS CLI."""
    import subprocess
    root = Path(model_dir)
    if not root.exists():
        raise FileNotFoundError(str(root))
    s3_uri = "s3://%s/%s/" % (bucket.rstrip("/"), (prefix or "models").strip("/").rstrip("/"))
    cmd = ["aws", "s3", "sync", str(root), s3_uri, "--only-show-errors"]
    print("  Running: %s" % " ".join(cmd))
    subprocess.run(cmd, check=True)
    print("  ✅ Synced to %s" % s3_uri)


def main() -> int:
    parser = argparse.ArgumentParser(description="AWS model download (no Modal)")
    parser.add_argument("--model-dir", default=MODEL_DIR, help="Base directory for models (default: MODEL_DIR env or ./models)")
    parser.add_argument("--verify-only", action="store_true", help="Only verify existing downloads")
    parser.add_argument("--s3-bucket", default="", help="After download, sync to this S3 bucket")
    parser.add_argument("--s3-prefix", default="models/", help="S3 key prefix (default: models/)")
    args = parser.parse_args()
    model_dir = Path(args.model_dir)

    if args.verify_only:
        print("Verifying models under %s\n" % model_dir)
        ok = verify_models(model_dir)
        sys.exit(0 if ok else 1)

    print("=" * 60)
    print("AWS Model Download (no Modal)")
    print("=" * 60)
    print("Model directory: %s" % model_dir)
    print("Estimated time: 30–60 minutes; total ~25GB")
    if HF_TOKEN:
        print("Using HuggingFace token for gated/authenticated repos")
    print()

    try:
        download_all_models(model_dir)
        if args.s3_bucket:
            upload_to_s3(model_dir, args.s3_bucket, args.s3_prefix)
        print("\nVerification:")
        verify_models(model_dir)
        return 0
    except Exception as e:
        print("\n❌ Download failed: %s" % e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
