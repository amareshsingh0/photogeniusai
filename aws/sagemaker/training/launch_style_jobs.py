"""
Launch SageMaker Training Jobs for style LoRAs.
Runs up to 4 styles in parallel (4 jobs). Total ~2-3 days for all 20 styles.

Usage:
  python launch_style_jobs.py --role Arn --bucket photogenius-models-dev --prefix loras/styles
  python launch_style_jobs.py --role Arn --bucket bucket --parallel 4 --styles cinematic anime photorealistic oil_painting

Requires: boto3, sagemaker (pip install sagemaker).
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

# 20 style names - must match train_lora.STYLE_DATASETS
STYLE_NAMES = [
    "cinematic", "anime", "photorealistic", "oil_painting", "watercolor",
    "digital_art", "concept_art", "pixel_art", "three_d_render", "sketch_pencil",
    "comic_book", "ukiyo_e", "art_nouveau", "cyberpunk", "fantasy_art",
    "minimalist", "surrealism", "vintage_photo", "gothic", "pop_art",
]


def main():
    ap = argparse.ArgumentParser(description="Launch SageMaker style LoRA training jobs")
    ap.add_argument("--role", required=True, help="SageMaker execution role ARN")
    ap.add_argument("--bucket", required=True, help="S3 bucket for output (e.g. photogenius-models-dev)")
    ap.add_argument("--prefix", default="loras/styles", help="S3 prefix for LoRA outputs")
    ap.add_argument("--image", default=None, help="Training container image URI (default: PyTorch 2.0 GPU)")
    ap.add_argument("--instance", default="ml.g5.2xlarge", help="Instance type")
    ap.add_argument("--instance-count", type=int, default=1)
    ap.add_argument("--steps", type=int, default=2500)
    ap.add_argument("--parallel", type=int, default=4, help="Max concurrent jobs")
    ap.add_argument("--styles", nargs="*", default=None, help="Style names; default all 20")
    ap.add_argument("--job-prefix", default="style-lora", help="Training job name prefix")
    args = ap.parse_args()

    try:
        import boto3
        from sagemaker.pytorch import PyTorch
        from sagemaker.inputs import TrainingInput
    except ImportError:
        print("Install: pip install boto3 sagemaker")
        raise

    region = boto3.Session().region_name or "us-east-1"
    account = boto3.client("sts").get_caller_identity()["Account"]
    default_image = f"{account}.dkr.ecr.{region}.amazonaws.com/pytorch-training:2.0-gpu-py310"
    image_uri = args.image or default_image

    # Resolve training script path (same dir as this script)
    training_dir = Path(__file__).resolve().parent
    train_script = training_dir / "train_lora.py"
    if not train_script.exists():
        print(f"Training script not found: {train_script}")
        return

    styles = args.styles or STYLE_NAMES
    output_s3 = f"s3://{args.bucket}/{args.prefix}"

    # Optional: upload training code to S3 so SageMaker can run it
    # For simplicity we use source_dir so SageMaker packages train_lora.py
    timestamp = int(time.time())
    jobs = []
    for i, style_name in enumerate(styles):
        if style_name not in STYLE_NAMES:
            print(f"Unknown style: {style_name}, skip")
            continue
        job_name = f"{args.job_prefix}-{style_name}-{timestamp}"
        hyperparameters = {
            "style_name": style_name,
            "steps": args.steps,
            "batch_size": 4,
            "learning_rate": 0.0001,
            "output_s3": output_s3,
        }
        estimator = PyTorch(
            entry_point="train_lora.py",
            source_dir=str(training_dir),
            role=args.role,
            instance_count=args.instance_count,
            instance_type=args.instance,
            framework_version="2.0",
            py_version="py310",
            hyperparameters=hyperparameters,
            output_path=output_s3,
            base_job_name=args.job_prefix,
        )
        estimator.fit(inputs={}, wait=False)
        jobs.append(estimator.latest_training_job.name)
        print(f"Started job: {estimator.latest_training_job.name} (style={style_name})")
        if len(jobs) >= args.parallel:
            print(f"Reached parallel limit {args.parallel}. Run again for more styles.")
            break

    print(f"Launched {len(jobs)} jobs. Upload trained LoRAs to: {output_s3}")
    print("Upload trained LoRAs to S3:", output_s3)


if __name__ == "__main__":
    main()
