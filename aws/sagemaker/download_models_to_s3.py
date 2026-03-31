"""
Download all required models and upload to S3 for SageMaker.

This script:
1. Downloads SDXL models from HuggingFace
2. Uploads them to S3 for fast SageMaker loading
3. Downloads LoRAs and InstantID models

Usage:
    python download_models_to_s3.py

Requirements:
    pip install diffusers transformers accelerate safetensors boto3 huggingface_hub
"""

import os
import subprocess
from pathlib import Path
from typing import List
import argparse

# Configuration
S3_BUCKET = os.environ.get("MODELS_S3_BUCKET", "photogenius-models-dev")
CACHE_DIR = Path("/tmp/photogenius-models")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Models to download
MODELS = {
    "sdxl-turbo": {
        "hf_id": "stabilityai/sdxl-turbo",
        "s3_prefix": "models/sdxl-turbo",
        "size": "7GB",
    },
    "sdxl-base": {
        "hf_id": "stabilityai/stable-diffusion-xl-base-1.0",
        "s3_prefix": "models/sdxl-base-1.0",
        "size": "14GB",
    },
    "sdxl-refiner": {
        "hf_id": "stabilityai/stable-diffusion-xl-refiner-1.0",
        "s3_prefix": "models/sdxl-refiner-1.0",
        "size": "14GB",
    },
    "clip": {
        "hf_id": "openai/clip-vit-large-patch14",
        "s3_prefix": "models/clip-vit-large",
        "size": "1GB",
    },
}


def download_model_from_hf(hf_id: str, local_dir: Path):
    """Download model from HuggingFace to local directory."""
    print(f"\n{'='*80}")
    print(f"📥 Downloading: {hf_id}")
    print(f"📂 Target: {local_dir}")
    print(f"{'='*80}\n")

    try:
        from huggingface_hub import snapshot_download

        snapshot_download(
            repo_id=hf_id,
            local_dir=str(local_dir),
            local_dir_use_symlinks=False,
            resume_download=True,
            ignore_patterns=["*.msgpack", "*.h5", "*.ot"],  # Skip unnecessary files
        )

        print(f"✅ Downloaded: {hf_id}")
        return True

    except Exception as e:
        print(f"❌ Failed to download {hf_id}: {e}")
        return False


def upload_to_s3(local_dir: Path, s3_prefix: str, bucket: str):
    """Upload local directory to S3."""
    print(f"\n📤 Uploading to S3...")
    print(f"   Local: {local_dir}")
    print(f"   S3: s3://{bucket}/{s3_prefix}")

    try:
        cmd = [
            "aws", "s3", "sync",
            str(local_dir),
            f"s3://{bucket}/{s3_prefix}",
            "--delete",  # Remove files not in local
        ]

        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(f"✅ Uploaded to s3://{bucket}/{s3_prefix}")
        return True

    except subprocess.CalledProcessError as e:
        print(f"❌ S3 upload failed: {e.stderr}")
        return False


def check_s3_exists(bucket: str, prefix: str) -> bool:
    """Check if model exists in S3."""
    try:
        cmd = ["aws", "s3", "ls", f"s3://{bucket}/{prefix}/model_index.json"]
        result = subprocess.run(cmd, capture_output=True, timeout=10)
        return result.returncode == 0
    except:
        return False


def get_dir_size(path: Path) -> str:
    """Get directory size in human-readable format."""
    try:
        total_size = sum(f.stat().st_size for f in path.rglob('*') if f.is_file())
        for unit in ['B', 'KB', 'MB', 'GB']:
            if total_size < 1024.0:
                return f"{total_size:.1f}{unit}"
            total_size /= 1024.0
        return f"{total_size:.1f}TB"
    except:
        return "Unknown"


def main():
    parser = argparse.ArgumentParser(description="Download models and upload to S3")
    parser.add_argument("--skip-existing", action="store_true", help="Skip models that already exist in S3")
    parser.add_argument("--models", nargs="+", choices=list(MODELS.keys()) + ["all"], default=["all"], help="Models to download")
    args = parser.parse_args()

    # Select models to process
    if "all" in args.models:
        models_to_process = MODELS
    else:
        models_to_process = {k: MODELS[k] for k in args.models if k in MODELS}

    print(f"\n{'='*80}")
    print(f"PhotoGenius AI - Model Download & S3 Upload")
    print(f"{'='*80}")
    print(f"S3 Bucket: {S3_BUCKET}")
    print(f"Cache Dir: {CACHE_DIR}")
    print(f"Models: {', '.join(models_to_process.keys())}")
    print(f"{'='*80}\n")

    success_count = 0
    skip_count = 0
    fail_count = 0

    for name, config in models_to_process.items():
        hf_id = config["hf_id"]
        s3_prefix = config["s3_prefix"]
        estimated_size = config["size"]

        print(f"\n{'='*80}")
        print(f"Processing: {name}")
        print(f"HuggingFace ID: {hf_id}")
        print(f"S3 Prefix: {s3_prefix}")
        print(f"Estimated Size: {estimated_size}")
        print(f"{'='*80}\n")

        # Check if already in S3
        if args.skip_existing and check_s3_exists(S3_BUCKET, s3_prefix):
            print(f"✅ Already in S3: s3://{S3_BUCKET}/{s3_prefix}")
            print(f"   Skipping download (use --no-skip-existing to force)")
            skip_count += 1
            continue

        # Create local directory
        local_dir = CACHE_DIR / name
        local_dir.mkdir(parents=True, exist_ok=True)

        # Download from HuggingFace
        if not download_model_from_hf(hf_id, local_dir):
            fail_count += 1
            continue

        # Show downloaded size
        actual_size = get_dir_size(local_dir)
        print(f"📊 Downloaded size: {actual_size}")

        # Upload to S3
        if upload_to_s3(local_dir, s3_prefix, S3_BUCKET):
            success_count += 1

            # Clean up local files to save space
            print(f"🧹 Cleaning up local cache: {local_dir}")
            subprocess.run(["rm", "-rf", str(local_dir)], check=False)
        else:
            fail_count += 1

    # Summary
    print(f"\n{'='*80}")
    print(f"📊 SUMMARY")
    print(f"{'='*80}")
    print(f"✅ Success: {success_count}")
    print(f"⏭️  Skipped: {skip_count}")
    print(f"❌ Failed: {fail_count}")
    print(f"{'='*80}\n")

    if success_count > 0:
        print(f"✅ Models uploaded to s3://{S3_BUCKET}/models/")
        print(f"\nNext steps:")
        print(f"1. Deploy SageMaker endpoint:")
        print(f"   python deploy_enhanced_endpoint.py")
        print(f"\n2. Verify models in S3:")
        print(f"   aws s3 ls s3://{S3_BUCKET}/models/ --recursive --human-readable")
        print(f"\n3. Test endpoint:")
        print(f"   python test_endpoint.py")

    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    exit(main())
