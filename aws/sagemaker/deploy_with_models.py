"""
Deploy SageMaker endpoint with models pre-packaged in model.tar.gz.
Downloads models from S3 and creates a complete model.tar.gz.
"""

import boto3
import tarfile
import time
import os
import shutil
from pathlib import Path

# Configuration
ENDPOINT_NAME = "photogenius-generation-dev"
S3_BUCKET = "photogenius-models-dev"
REGION = "us-east-1"
INSTANCE_TYPE = "ml.g5.2xlarge"

# Boto3 clients
s3 = boto3.client("s3", region_name=REGION)
sm = boto3.client("sagemaker", region_name=REGION)
iam = boto3.client("iam")


def download_model_from_s3(model_name, target_dir):
    """Download model from S3 to local directory."""
    print(f"\nDownloading {model_name} from S3...")
    s3_prefix = f"models/{model_name}/"
    model_dir = Path(target_dir) / model_name
    model_dir.mkdir(parents=True, exist_ok=True)

    # List all files
    paginator = s3.get_paginator("list_objects_v2")
    pages = paginator.paginate(Bucket=S3_BUCKET, Prefix=s3_prefix)

    file_count = 0
    total_size = 0

    for page in pages:
        if "Contents" not in page:
            continue
        for obj in page["Contents"]:
            s3_key = obj["Key"]
            rel_path = s3_key[len(s3_prefix):]
            if not rel_path:
                continue

            local_path = model_dir / rel_path
            local_path.parent.mkdir(parents=True, exist_ok=True)

            # Download
            s3.download_file(S3_BUCKET, s3_key, str(local_path))
            file_size = obj["Size"] / (1024 * 1024)  # MB
            total_size += file_size
            file_count += 1

            if file_count % 10 == 0:
                print(f"  Downloaded {file_count} files ({total_size:.1f} MB)...")

    print(f"  ✓ Downloaded {file_count} files ({total_size:.1f} MB)")
    return model_dir


def create_model_tar_with_models():
    """Create model.tar.gz with models and inference code."""
    print("\n" + "="*80)
    print("Creating model.tar.gz with pre-loaded models")
    print("="*80)

    # Create temp directory
    temp_dir = Path("temp_model_package")
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir()

    try:
        # Download models from S3
        print("\nStep 1: Downloading models from S3...")
        print("This will take 10-15 minutes (downloading ~20GB)")
        print()

        models_dir = temp_dir / "models"
        models_dir.mkdir()

        # Download Turbo and Base (skip Refiner to save space/time)
        download_model_from_s3("sdxl-turbo", models_dir)
        download_model_from_s3("sdxl-base-1.0", models_dir)

        # Copy inference code
        print("\nStep 2: Adding inference code...")
        code_dir = temp_dir / "code"
        code_dir.mkdir()
        shutil.copy("model/code/inference_preloaded.py", code_dir / "inference.py")
        print("  ✓ Added inference.py")

        # Create tar.gz
        print("\nStep 3: Creating model.tar.gz...")
        print("This will take 5-10 minutes (compressing ~20GB)...")
        tar_path = Path("model.tar.gz")

        with tarfile.open(tar_path, "w:gz") as tar:
            tar.add(temp_dir / "models", arcname="models")
            tar.add(temp_dir / "code" / "inference.py", arcname="code/inference.py")

        tar_size = tar_path.stat().st_size / (1024 * 1024 * 1024)  # GB
        print(f"  ✓ Created {tar_path} ({tar_size:.2f} GB)")

        return tar_path

    finally:
        # Cleanup
        print("\nCleaning up temp files...")
        if temp_dir.exists():
            shutil.rmtree(temp_dir)


def upload_to_s3(file_path):
    """Upload model.tar.gz to S3."""
    key = f"sagemaker/models/preloaded-{int(time.time())}/model.tar.gz"
    print(f"\nUploading to s3://{S3_BUCKET}/{key}...")
    print("This will take 5-10 minutes (uploading multi-GB file)...")

    s3.upload_file(str(file_path), S3_BUCKET, key)
    s3_uri = f"s3://{S3_BUCKET}/{key}"

    print(f"✓ Uploaded: {s3_uri}")
    return s3_uri


def get_execution_role():
    """Get SageMaker execution role."""
    role_name = "SageMakerExecutionRole"
    try:
        role = iam.get_role(RoleName=role_name)
        return role["Role"]["Arn"]
    except:
        print(f"ERROR: Role '{role_name}' not found")
        exit(1)


def create_or_update_model(model_name, model_data_url, role_arn):
    """Create or update SageMaker model."""
    image_uri = "763104351884.dkr.ecr.us-east-1.amazonaws.com/huggingface-pytorch-inference:2.1.0-transformers4.37.0-gpu-py310-cu118-ubuntu20.04"

    model_config = {
        "ModelName": model_name,
        "PrimaryContainer": {
            "Image": image_uri,
            "ModelDataUrl": model_data_url,
            "Environment": {
                "SAGEMAKER_CONTAINER_LOG_LEVEL": "20",
                "SAGEMAKER_REGION": REGION,
            }
        },
        "ExecutionRoleArn": role_arn,
    }

    try:
        sm.describe_model(ModelName=model_name)
        print(f"\nDeleting existing model: {model_name}")
        sm.delete_model(ModelName=model_name)
        time.sleep(2)
    except:
        pass

    print(f"Creating model: {model_name}")
    sm.create_model(**model_config)
    print(f"✓ Model created")


def create_endpoint_config(config_name, model_name):
    """Create endpoint configuration."""
    try:
        sm.describe_endpoint_config(EndpointConfigName=config_name)
        return False  # Already exists
    except:
        pass

    print(f"\nCreating endpoint config: {config_name}")
    sm.create_endpoint_config(
        EndpointConfigName=config_name,
        ProductionVariants=[
            {
                "VariantName": "AllTraffic",
                "ModelName": model_name,
                "InitialInstanceCount": 1,
                "InstanceType": INSTANCE_TYPE,
            }
        ],
    )
    print(f"✓ Config created")
    return True


def create_or_update_endpoint(endpoint_name, config_name):
    """Create or update endpoint."""
    try:
        sm.describe_endpoint(EndpointName=endpoint_name)
        print(f"\nUpdating endpoint: {endpoint_name}")
        sm.update_endpoint(
            EndpointName=endpoint_name,
            EndpointConfigName=config_name,
        )
        print(f"✓ Update initiated")
    except:
        print(f"\nCreating endpoint: {endpoint_name}")
        sm.create_endpoint(
            EndpointName=endpoint_name,
            EndpointConfigName=config_name,
        )
        print(f"✓ Creation initiated")


def main():
    print("\n" + "="*80)
    print("PhotoGenius AI - Deploy with Pre-loaded Models")
    print("="*80)
    print(f"\nEndpoint: {ENDPOINT_NAME}")
    print(f"Instance: {INSTANCE_TYPE}")
    print(f"Region: {REGION}")
    print("\nWARNING: This will take 30-45 minutes:")
    print("  - 10-15 min: Download models from S3")
    print("  - 5-10 min: Create model.tar.gz")
    print("  - 5-10 min: Upload to S3")
    print("  - 10-15 min: SageMaker deployment")
    print("="*80)
    print("\nStarting deployment...")

    # response = input("\nContinue? (yes/no): ")
    # if response.lower() != "yes":
    #     print("Deployment cancelled")
    #     return

    # Step 1: Create model.tar.gz with models
    tar_path = create_model_tar_with_models()

    # Step 2: Upload to S3
    model_data_url = upload_to_s3(tar_path)

    # Step 3: Get IAM role
    role_arn = get_execution_role()

    # Step 4: Create model
    timestamp = int(time.time())
    model_name = f"{ENDPOINT_NAME}-model-{timestamp}"
    create_or_update_model(model_name, model_data_url, role_arn)

    # Step 5: Create endpoint config
    config_name = f"{ENDPOINT_NAME}-config-{timestamp}"
    create_endpoint_config(config_name, model_name)

    # Step 6: Deploy endpoint
    create_or_update_endpoint(ENDPOINT_NAME, config_name)

    print("\n" + "="*80)
    print("Deployment Complete!")
    print("="*80)
    print(f"\nEndpoint '{ENDPOINT_NAME}' is being deployed")
    print("This will take 10-15 minutes to become 'InService'")
    print("\nMonitor status:")
    print(f"  aws sagemaker describe-endpoint --endpoint-name {ENDPOINT_NAME} --query 'EndpointStatus'")
    print("\nCleanup:")
    print(f"  rm model.tar.gz  # Delete local tar file ({tar_path.stat().st_size / (1024**3):.2f} GB)")


if __name__ == "__main__":
    main()
