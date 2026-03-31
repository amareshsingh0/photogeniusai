#!/usr/bin/env python3
"""
Deploy SageMaker endpoint that loads SDXL from S3.
This creates a new endpoint configuration with S3 model loading.
"""
import boto3
import json
import os
import tarfile
import tempfile
import shutil
from datetime import datetime

# Configuration
REGION = "us-east-1"
S3_BUCKET = "photogenius-models-dev"
ENDPOINT_NAME = "photogenius-standard"
MODEL_NAME = f"photogenius-sdxl-turbo-{datetime.now().strftime('%Y%m%d%H%M')}"
INSTANCE_TYPE = "ml.g5.xlarge"


# Get SageMaker execution role
def get_execution_role():
    """Get or create SageMaker execution role."""
    iam = boto3.client("iam", region_name=REGION)

    role_name = "PhotoGenius-SageMaker-Role"

    # Check if role exists
    try:
        role = iam.get_role(RoleName=role_name)
        return role["Role"]["Arn"]
    except iam.exceptions.NoSuchEntityException:
        pass

    # Create role
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "sagemaker.amazonaws.com"},
                "Action": "sts:AssumeRole",
            }
        ],
    }

    role = iam.create_role(
        RoleName=role_name,
        AssumeRolePolicyDocument=json.dumps(trust_policy),
        Description="SageMaker execution role for PhotoGenius",
    )

    # Attach policies
    iam.attach_role_policy(
        RoleName=role_name,
        PolicyArn="arn:aws:iam::aws:policy/AmazonSageMakerFullAccess",
    )
    iam.attach_role_policy(
        RoleName=role_name, PolicyArn="arn:aws:iam::aws:policy/AmazonS3FullAccess"
    )

    print(f"Created role: {role['Role']['Arn']}")
    return role["Role"]["Arn"]


def create_model_package():
    """Create model.tar.gz with inference code."""
    # Create temp directory
    temp_dir = tempfile.mkdtemp()
    code_dir = os.path.join(temp_dir, "code")
    os.makedirs(code_dir)

    # Copy inference code
    inference_src = r"c:\desktop\PhotoGenius AI\aws\sagemaker\model\code\inference.py"
    shutil.copy(inference_src, os.path.join(code_dir, "inference.py"))

    # Create requirements.txt with compatible versions
    requirements = """
diffusers==0.24.0
transformers==4.37.0
accelerate==0.25.0
safetensors==0.4.0
Pillow>=9.0.0
peft==0.7.0
"""
    with open(os.path.join(code_dir, "requirements.txt"), "w") as f:
        f.write(requirements.strip())

    # Create model.tar.gz
    tar_path = os.path.join(temp_dir, "model.tar.gz")
    with tarfile.open(tar_path, "w:gz") as tar:
        tar.add(code_dir, arcname="code")

    print(f"Created model package: {tar_path}")
    return tar_path


def upload_model_to_s3(tar_path):
    """Upload model package to S3."""
    s3 = boto3.client("s3", region_name=REGION)
    key = f"sagemaker-models/{MODEL_NAME}/model.tar.gz"

    print(f"Uploading to s3://{S3_BUCKET}/{key}...")
    s3.upload_file(tar_path, S3_BUCKET, key)

    return f"s3://{S3_BUCKET}/{key}"


def create_sagemaker_model(model_data_url, role_arn):
    """Create SageMaker model."""
    sm = boto3.client("sagemaker", region_name=REGION)

    # Use base PyTorch DLC for more control over dependencies
    # PyTorch 2.1.0 with CUDA 12.1 - stable base
    image_uri = f"763104351884.dkr.ecr.{REGION}.amazonaws.com/pytorch-inference:2.1.0-gpu-py310-cu121-ubuntu20.04-sagemaker"

    # Environment variables for S3 model loading
    env = {
        "MODELS_S3_BUCKET": S3_BUCKET,
        "MODELS_S3_PREFIX": "models/sdxl-turbo",
        "HF_MODEL_ID": "stabilityai/sdxl-turbo",  # Fallback
        "SAGEMAKER_PROGRAM": "inference.py",
        "SAGEMAKER_SUBMIT_DIRECTORY": model_data_url,
        # Fix numpy compatibility
        "TRANSFORMERS_OFFLINE": "0",
    }

    print(f"Creating SageMaker model: {MODEL_NAME}")
    sm.create_model(
        ModelName=MODEL_NAME,
        PrimaryContainer={
            "Image": image_uri,
            "ModelDataUrl": model_data_url,
            "Environment": env,
        },
        ExecutionRoleArn=role_arn,
    )

    return MODEL_NAME


def create_endpoint_config(model_name):
    """Create endpoint configuration."""
    sm = boto3.client("sagemaker", region_name=REGION)
    config_name = f"{ENDPOINT_NAME}-config-{datetime.now().strftime('%Y%m%d%H%M')}"

    print(f"Creating endpoint config: {config_name}")
    sm.create_endpoint_config(
        EndpointConfigName=config_name,
        ProductionVariants=[
            {
                "VariantName": "AllTraffic",
                "ModelName": model_name,
                "InstanceType": INSTANCE_TYPE,
                "InitialInstanceCount": 1,
                "ContainerStartupHealthCheckTimeoutInSeconds": 600,  # 10 min for model loading
            }
        ],
    )

    return config_name


def create_or_update_endpoint(config_name):
    """Create or update endpoint."""
    sm = boto3.client("sagemaker", region_name=REGION)

    # Check if endpoint exists
    try:
        sm.describe_endpoint(EndpointName=ENDPOINT_NAME)
        print(f"Updating endpoint: {ENDPOINT_NAME}")
        sm.update_endpoint(
            EndpointName=ENDPOINT_NAME,
            EndpointConfigName=config_name,
        )
    except sm.exceptions.ClientError:
        print(f"Creating endpoint: {ENDPOINT_NAME}")
        sm.create_endpoint(
            EndpointName=ENDPOINT_NAME,
            EndpointConfigName=config_name,
        )

    print("Endpoint creation/update initiated. This takes 5-10 minutes.")
    return ENDPOINT_NAME


def main():
    print("=" * 60)
    print("PhotoGenius SageMaker Deployment (S3 Models)")
    print("=" * 60)

    # Step 1: Get execution role
    print("\n1. Getting execution role...")
    role_arn = get_execution_role()
    print(f"   Role: {role_arn}")

    # Step 2: Create model package
    print("\n2. Creating model package...")
    tar_path = create_model_package()

    # Step 3: Upload to S3
    print("\n3. Uploading to S3...")
    model_data_url = upload_model_to_s3(tar_path)
    print(f"   Model data: {model_data_url}")

    # Step 4: Create SageMaker model
    print("\n4. Creating SageMaker model...")
    model_name = create_sagemaker_model(model_data_url, role_arn)

    # Step 5: Create endpoint config
    print("\n5. Creating endpoint configuration...")
    config_name = create_endpoint_config(model_name)

    # Step 6: Create endpoint
    print("\n6. Creating endpoint...")
    endpoint_name = create_or_update_endpoint(config_name)

    print("\n" + "=" * 60)
    print("Deployment initiated successfully!")
    print(f"Endpoint: {endpoint_name}")
    print(
        f"Check status: aws sagemaker describe-endpoint --endpoint-name {endpoint_name}"
    )
    print("=" * 60)


if __name__ == "__main__":
    main()
