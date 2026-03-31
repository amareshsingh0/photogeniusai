"""
Download AI Models to S3

Models needed:
1. SDXL-Base (already in S3) ✅
2. SDXL-Refiner (already in S3) ✅
3. SDXL-Turbo (FAST tier) - NEED TO DOWNLOAD
4. InstantID (face consistency) - NEED TO DOWNLOAD

Usage:
    python scripts/download_models.py --model all
    python scripts/download_models.py --model sdxl-turbo
    python scripts/download_models.py --model instantid
"""

import os
import sys
import boto3
import argparse
from pathlib import Path
from huggingface_hub import snapshot_download

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# S3 Configuration
S3_BUCKET = os.getenv('S3_BUCKET', 'photogenius-models-dev')
S3_PREFIX = 'models/'

# Model configurations
MODELS = {
    'sdxl-turbo': {
        'hf_repo': 'stabilityai/sdxl-turbo',
        's3_path': 'models/sdxl-turbo/',
        'description': 'SDXL-Turbo for FAST tier (4 steps, ~3s)',
        'size': '~7GB',
        'required': True
    },
    'sdxl-base': {
        'hf_repo': 'stabilityai/stable-diffusion-xl-base-1.0',
        's3_path': 'models/sdxl-base-1.0/',
        'description': 'SDXL-Base for STANDARD tier (30 steps, ~25s)',
        'size': '~7GB',
        'required': True,
        'status': '✅ Already in S3'
    },
    'sdxl-refiner': {
        'hf_repo': 'stabilityai/stable-diffusion-xl-refiner-1.0',
        's3_path': 'models/sdxl-refiner-1.0/',
        'description': 'SDXL-Refiner for PREMIUM tier (50 steps, ~50s)',
        'size': '~6GB',
        'required': True,
        'status': '✅ Already in S3'
    },
    'instantid': {
        'hf_repo': 'InstantX/InstantID',
        's3_path': 'models/instantid/',
        'description': 'InstantID for face consistency',
        'size': '~2GB',
        'required': False
    }
}


def check_s3_model(s3_client, bucket, s3_path):
    """Check if model exists in S3"""
    try:
        response = s3_client.list_objects_v2(
            Bucket=bucket,
            Prefix=s3_path,
            MaxKeys=1
        )
        return response.get('KeyCount', 0) > 0
    except Exception as e:
        print(f"Error checking S3: {e}")
        return False


def download_model_from_hf(repo_id, local_dir):
    """Download model from HuggingFace"""
    print(f"\n📥 Downloading {repo_id} from HuggingFace...")
    print(f"   → Destination: {local_dir}")

    try:
        snapshot_download(
            repo_id=repo_id,
            local_dir=local_dir,
            local_dir_use_symlinks=False,
            resume_download=True
        )
        print(f"✅ Downloaded successfully!")
        return True
    except Exception as e:
        print(f"❌ Download failed: {e}")
        return False


def upload_to_s3(s3_client, bucket, local_dir, s3_prefix):
    """Upload model directory to S3"""
    print(f"\n📤 Uploading to S3: s3://{bucket}/{s3_prefix}")

    local_path = Path(local_dir)
    uploaded_files = 0

    for file_path in local_path.rglob('*'):
        if file_path.is_file():
            relative_path = file_path.relative_to(local_path)
            s3_key = f"{s3_prefix}{relative_path}"

            try:
                s3_client.upload_file(
                    str(file_path),
                    bucket,
                    s3_key
                )
                uploaded_files += 1
                if uploaded_files % 10 == 0:
                    print(f"   Uploaded {uploaded_files} files...")
            except Exception as e:
                print(f"   ❌ Failed to upload {relative_path}: {e}")

    print(f"✅ Uploaded {uploaded_files} files to S3")
    return uploaded_files > 0


def download_and_upload_model(model_name, config, s3_client, bucket, local_base_dir):
    """Download model from HF and upload to S3"""

    # Check if already in S3
    if check_s3_model(s3_client, bucket, config['s3_path']):
        print(f"\n✅ {model_name} already in S3: s3://{bucket}/{config['s3_path']}")
        return True

    print(f"\n{'='*60}")
    print(f"📦 Processing: {model_name}")
    print(f"   Description: {config['description']}")
    print(f"   Size: {config['size']}")
    print(f"{'='*60}")

    # Create local directory
    local_dir = local_base_dir / model_name
    local_dir.mkdir(parents=True, exist_ok=True)

    # Download from HuggingFace
    if not download_model_from_hf(config['hf_repo'], str(local_dir)):
        return False

    # Upload to S3
    if not upload_to_s3(s3_client, bucket, str(local_dir), config['s3_path']):
        return False

    print(f"\n✅ {model_name} setup complete!")
    return True


def main():
    parser = argparse.ArgumentParser(description='Download AI models to S3')
    parser.add_argument(
        '--model',
        choices=['all', 'sdxl-turbo', 'sdxl-base', 'sdxl-refiner', 'instantid'],
        default='all',
        help='Which model to download'
    )
    parser.add_argument(
        '--local-dir',
        default='./models_temp',
        help='Local directory for temporary storage'
    )
    parser.add_argument(
        '--skip-upload',
        action='store_true',
        help='Download only, skip S3 upload'
    )

    args = parser.parse_args()

    # Setup
    local_base_dir = Path(args.local_dir)
    local_base_dir.mkdir(exist_ok=True)

    s3_client = boto3.client('s3')

    print("\n" + "="*60)
    print("🚀 PhotoGenius AI - Model Download Script")
    print("="*60)

    # Check which models need download
    models_to_download = []

    if args.model == 'all':
        # Check all models
        for model_name, config in MODELS.items():
            if check_s3_model(s3_client, S3_BUCKET, config['s3_path']):
                print(f"✅ {model_name}: Already in S3")
                config['status'] = '✅ Already in S3'
            else:
                print(f"⏳ {model_name}: Needs download")
                models_to_download.append(model_name)
    else:
        models_to_download = [args.model]

    if not models_to_download:
        print("\n✅ All required models are already in S3!")
        print("\nModels in S3:")
        for model_name, config in MODELS.items():
            status = config.get('status', '❓ Unknown')
            print(f"  - {model_name}: {status}")
        return

    print(f"\n📥 Models to download: {', '.join(models_to_download)}")
    print("\nStarting downloads...\n")

    # Download each model
    success_count = 0
    for model_name in models_to_download:
        if model_name in MODELS:
            config = MODELS[model_name]
            if download_and_upload_model(model_name, config, s3_client, S3_BUCKET, local_base_dir):
                success_count += 1
        else:
            print(f"❌ Unknown model: {model_name}")

    # Summary
    print("\n" + "="*60)
    print("📊 SUMMARY")
    print("="*60)
    print(f"✅ Successfully processed: {success_count}/{len(models_to_download)} models")
    print(f"📦 S3 Bucket: s3://{S3_BUCKET}/models/")
    print("\nModels status:")
    for model_name, config in MODELS.items():
        if check_s3_model(s3_client, S3_BUCKET, config['s3_path']):
            print(f"  ✅ {model_name}: Ready in S3")
        else:
            print(f"  ⏳ {model_name}: Not yet uploaded")

    print("\n" + "="*60)
    print("✅ Model download complete!")
    print("="*60)


if __name__ == '__main__':
    main()
