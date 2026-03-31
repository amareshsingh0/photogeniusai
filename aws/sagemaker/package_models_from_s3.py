"""
Download models from S3 and create a valid model.tar.gz for SageMaker.
Uses existing sdxl-turbo from S3 (7GB - manageable size).
"""

import boto3
import tarfile
from pathlib import Path
import shutil

S3_BUCKET = "photogenius-models-dev"
REGION = "us-east-1"

print("=" * 80)
print("Creating Valid Model Package from S3")
print("=" * 80)

# Step 1: Create temp directory
print("\n[1/5] Creating temporary directory...")
temp_dir = Path("temp_model_package")
if temp_dir.exists():
    shutil.rmtree(temp_dir)
temp_dir.mkdir()

models_dir = temp_dir / "models"
models_dir.mkdir()

code_dir = temp_dir / "code"
code_dir.mkdir()

print(f"[OK] Created {temp_dir}")

# Step 2: Download SDXL-Turbo from S3
print("\n[2/5] Downloading SDXL-Turbo from S3...")
s3 = boto3.client("s3", region_name=REGION)

turbo_dir = models_dir / "sdxl-turbo"
turbo_dir.mkdir()

# List and download sdxl-turbo files
paginator = s3.get_paginator('list_objects_v2')
file_count = 0

for page in paginator.paginate(Bucket=S3_BUCKET, Prefix='models/sdxl-turbo/'):
    for obj in page.get('Contents', []):
        key = obj['Key']
        if key.endswith('/'):
            continue

        # Extract filename from key
        filename = key.split('/')[-1]
        local_path = turbo_dir / filename

        print(f"  Downloading {filename}...")
        s3.download_file(S3_BUCKET, key, str(local_path))
        file_count += 1

print(f"[OK] Downloaded {file_count} files")

# Step 3: Create inference handler
print("\n[3/5] Creating inference handler...")

inference_code = '''"""
SageMaker inference handler with local SDXL-Turbo model.
"""

import json
import logging
import base64
import io
from pathlib import Path

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

MODELS = {}

def model_fn(model_dir):
    """Load SDXL-Turbo from local directory."""
    logger.info(f"Loading model from {model_dir}")

    try:
        import torch
        from diffusers import DiffusionPipeline

        models_path = Path(model_dir) / "models" / "sdxl-turbo"

        logger.info(f"Loading SDXL-Turbo from {models_path}")

        MODELS['turbo'] = DiffusionPipeline.from_pretrained(
            str(models_path),
            torch_dtype=torch.float16,
            variant="fp16",
            local_files_only=True
        ).to("cuda")

        logger.info("SDXL-Turbo loaded successfully!")
        return MODELS

    except Exception as e:
        logger.error(f"Error loading model: {e}")
        import traceback
        traceback.print_exc()
        raise

def input_fn(request_body, request_content_type):
    """Parse input."""
    if request_content_type == "application/json":
        return json.loads(request_body)
    raise ValueError(f"Unsupported content type: {request_content_type}")

def predict_fn(input_data, models):
    """Generate image with SDXL-Turbo."""
    try:
        import torch

        prompt = input_data.get("inputs", "a beautiful landscape")
        params = input_data.get("parameters", {})

        width = params.get("width", 1024)
        height = params.get("height", 1024)

        logger.info(f"Generating: {prompt}, Size: {width}x{height}")

        with torch.inference_mode():
            result = models['turbo'](
                prompt=prompt,
                num_inference_steps=4,
                guidance_scale=0.0,
                width=width,
                height=height,
            )

        # Convert to base64
        image = result.images[0]
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        image_b64 = base64.b64encode(buffered.getvalue()).decode('utf-8')

        logger.info("Image generated successfully")

        return {
            "image_base64": image_b64,
            "metadata": {
                "tier": "FAST",
                "model": "sdxl-turbo",
                "steps": 4,
                "width": width,
                "height": height,
                "prompt": prompt,
                "backend": "sagemaker_local"
            }
        }

    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return {"error": str(e), "message": "Generation failed"}

def output_fn(prediction, response_content_type):
    """Format output."""
    if response_content_type == "application/json":
        return json.dumps(prediction)
    raise ValueError(f"Unsupported content type: {response_content_type}")
'''

(code_dir / "inference.py").write_text(inference_code)

requirements = """diffusers>=0.24.0
transformers>=4.36.0
accelerate>=0.25.0
safetensors>=0.4.1
torch>=2.1.0
pillow>=10.0.0
"""
(code_dir / "requirements.txt").write_text(requirements)

print("[OK] Created inference.py and requirements.txt")

# Step 4: Create tar.gz
print("\n[4/5] Creating model.tar.gz...")
tar_path = Path("working_model.tar.gz")

with tarfile.open(tar_path, "w:gz") as tar:
    tar.add(models_dir, arcname="models")
    tar.add(code_dir, arcname="code")

size_mb = tar_path.stat().st_size / (1024 * 1024)
print(f"[OK] Created {tar_path} ({size_mb:.1f} MB)")

# Step 5: Upload to S3
print("\n[5/5] Uploading to S3...")
import time
ts = int(time.time())
s3_key = f"sagemaker/models/working-{ts}/model.tar.gz"
s3_uri = f"s3://{S3_BUCKET}/{s3_key}"

print(f"  Uploading to {s3_uri}...")
s3.upload_file(str(tar_path), S3_BUCKET, s3_key)
print(f"[OK] Uploaded!")

print("\n" + "=" * 80)
print("SUCCESS!")
print("=" * 80)
print(f"""
Model Package: {s3_uri}
Size: {size_mb:.1f} MB
Models: sdxl-turbo (FAST tier)

Next: Deploy to SageMaker
  python deploy_working_model.py
""")

# Cleanup
print("\nCleaning up...")
shutil.rmtree(temp_dir)
tar_path.unlink()
print("[OK] Cleaned up local files")
