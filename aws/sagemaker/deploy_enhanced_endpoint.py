"""
Deploy enhanced SageMaker endpoint with full SDXL pipeline.

Features:
- SDXL Turbo (FAST tier)
- SDXL Base (STANDARD tier)
- SDXL Base + Refiner (PREMIUM tier)
- LoRA support
- Quality scoring
- Best-of-N selection

Usage:
    python deploy_enhanced_endpoint.py --endpoint-name photogenius-generation-dev

Requirements:
    pip install boto3 sagemaker
"""

import argparse
import boto3
import sagemaker
from sagemaker.huggingface import HuggingFaceModel
import time
import os
from pathlib import Path

# Configuration
DEFAULT_ENDPOINT = "photogenius-generation-dev"
DEFAULT_INSTANCE = "ml.g5.2xlarge"  # NVIDIA A10G GPU, 24GB GPU RAM
S3_BUCKET = os.environ.get("MODELS_S3_BUCKET", "photogenius-models-dev")


def create_model_tar(code_dir: Path, output_path: Path):
    """Create model.tar.gz with inference code."""
    import tarfile

    print(f"📦 Creating model.tar.gz...")
    print(f"   Source: {code_dir}")
    print(f"   Output: {output_path}")

    with tarfile.open(output_path, "w:gz") as tar:
        for file in code_dir.glob("*.py"):
            tar.add(file, arcname=f"code/{file.name}")
            print(f"   Added: {file.name}")

    print(f"✅ Created: {output_path}")
    return output_path


def upload_model_to_s3(model_path: Path, bucket: str, key: str):
    """Upload model.tar.gz to S3."""
    s3 = boto3.client("s3")

    print(f"\n📤 Uploading to S3...")
    print(f"   Local: {model_path}")
    print(f"   S3: s3://{bucket}/{key}")

    s3.upload_file(str(model_path), bucket, key)
    s3_uri = f"s3://{bucket}/{key}"

    print(f"✅ Uploaded: {s3_uri}")
    return s3_uri


def deploy_endpoint(
    endpoint_name: str,
    model_data_url: str,
    instance_type: str,
    role_arn: str,
):
    """Deploy SageMaker endpoint."""
    print(f"\n🚀 Deploying SageMaker endpoint...")
    print(f"   Endpoint: {endpoint_name}")
    print(f"   Instance: {instance_type}")
    print(f"   Model: {model_data_url}")

    session = sagemaker.Session()
    region = session.boto_region_name

    # Environment variables for inference container
    env = {
        "MODELS_S3_BUCKET": S3_BUCKET,
        "HF_MODEL_ID": "stabilityai/sdxl-turbo",  # Fallback if S3 fails
        "SAGEMAKER_CONTAINER_LOG_LEVEL": "20",
        "SAGEMAKER_REGION": region,
    }

    # Create HuggingFace Model
    model = HuggingFaceModel(
        model_data=model_data_url,
        role=role_arn,
        transformers_version="4.37.0",
        pytorch_version="2.1.0",
        py_version="py310",
        env=env,
    )

    # Check if endpoint exists
    sm_client = boto3.client("sagemaker", region_name=region)
    try:
        sm_client.describe_endpoint(EndpointName=endpoint_name)
        endpoint_exists = True
        print(f"⚠️ Endpoint '{endpoint_name}' already exists")
    except sm_client.exceptions.ClientError:
        endpoint_exists = False

    # Deploy or update
    if endpoint_exists:
        print(f"🔄 Updating existing endpoint...")
        response = input(f"Update endpoint '{endpoint_name}'? (yes/no): ")
        if response.lower() != "yes":
            print("❌ Deployment cancelled")
            return None

        predictor = model.deploy(
            endpoint_name=endpoint_name,
            instance_type=instance_type,
            initial_instance_count=1,
            update_endpoint=True,
            wait=True,
        )
    else:
        print(f"✨ Creating new endpoint...")
        predictor = model.deploy(
            endpoint_name=endpoint_name,
            instance_type=instance_type,
            initial_instance_count=1,
            wait=True,
        )

    print(f"\n✅ Endpoint deployed: {endpoint_name}")
    print(f"   Region: {region}")
    print(f"   Instance: {instance_type}")
    print(f"\nTest command:")
    print(f"   python test_endpoint.py --endpoint {endpoint_name}")

    return predictor


def get_or_create_role():
    """Get existing SageMaker role or guide user to create one."""
    iam = boto3.client("iam")

    # Try common role names
    role_names = [
        "SageMakerExecutionRole",
        "PhotoGeniusSageMakerRole",
        "photogenius-sagemaker-role",
    ]

    for role_name in role_names:
        try:
            role = iam.get_role(RoleName=role_name)
            role_arn = role["Role"]["Arn"]
            print(f"✅ Found existing role: {role_arn}")
            return role_arn
        except iam.exceptions.NoSuchEntityException:
            continue

    # No role found
    print("\n❌ No SageMaker execution role found")
    print("\nCreate a role with these permissions:")
    print("  - AmazonSageMakerFullAccess")
    print("  - AmazonS3FullAccess")
    print("\nOR run:")
    print("  aws iam create-role --role-name SageMakerExecutionRole \\")
    print("    --assume-role-policy-document '{\"Version\":\"2012-10-17\",\"Statement\":[{\"Effect\":\"Allow\",\"Principal\":{\"Service\":\"sagemaker.amazonaws.com\"},\"Action\":\"sts:AssumeRole\"}]}'")
    print("\n  aws iam attach-role-policy --role-name SageMakerExecutionRole \\")
    print("    --policy-arn arn:aws:iam::aws:policy/AmazonSageMakerFullAccess")
    print("\n  aws iam attach-role-policy --role-name SageMakerExecutionRole \\")
    print("    --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess")

    raise ValueError("SageMaker execution role not found. Create one first.")


def main():
    parser = argparse.ArgumentParser(description="Deploy enhanced SageMaker endpoint")
    parser.add_argument("--endpoint-name", default=DEFAULT_ENDPOINT, help="Endpoint name")
    parser.add_argument("--instance-type", default=DEFAULT_INSTANCE, help="Instance type")
    parser.add_argument("--skip-build", action="store_true", help="Skip model.tar.gz creation")
    args = parser.parse_args()

    print(f"\n{'='*80}")
    print(f"PhotoGenius AI - Enhanced SageMaker Deployment")
    print(f"{'='*80}\n")

    # Get paths
    script_dir = Path(__file__).parent
    code_dir = script_dir / "model" / "code"
    model_tar_path = script_dir / "model.tar.gz"

    # Build model package
    if not args.skip_build:
        create_model_tar(code_dir, model_tar_path)

        # Upload to S3
        model_s3_key = f"sagemaker/models/enhanced-{int(time.time())}/model.tar.gz"
        model_data_url = upload_model_to_s3(model_tar_path, S3_BUCKET, model_s3_key)
    else:
        print("⏭️  Skipping model build (--skip-build)")
        # Use existing model
        model_data_url = f"s3://{S3_BUCKET}/sagemaker/models/enhanced-latest/model.tar.gz"

    # Get IAM role
    try:
        role_arn = get_or_create_role()
    except ValueError as e:
        print(f"\n❌ {e}")
        return 1

    # Deploy endpoint
    try:
        deploy_endpoint(
            endpoint_name=args.endpoint_name,
            model_data_url=model_data_url,
            instance_type=args.instance_type,
            role_arn=role_arn,
        )
        return 0
    except Exception as e:
        print(f"\n❌ Deployment failed: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
