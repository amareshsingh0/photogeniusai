"""
Simple SageMaker endpoint deployment using boto3 directly.
No sagemaker SDK needed - just boto3.
"""

import boto3
import tarfile
import time
from pathlib import Path
import json

# Configuration
ENDPOINT_NAME = "photogenius-generation-dev"
S3_BUCKET = "photogenius-models-dev"
REGION = "us-east-1"
INSTANCE_TYPE = "ml.g5.2xlarge"

# Boto3 clients
s3 = boto3.client("s3", region_name=REGION)
sm = boto3.client("sagemaker", region_name=REGION)
iam = boto3.client("iam")


def create_model_tar():
    """Create model.tar.gz with enhanced inference code."""
    print("Creating model.tar.gz...")
    code_dir = Path("model/code")
    tar_path = Path("model.tar.gz")

    with tarfile.open(tar_path, "w:gz") as tar:
        tar.add(code_dir / "inference.py", arcname="code/inference.py")
        print(f"Added: inference.py")

    print(f"Created: {tar_path}")
    return tar_path


def upload_to_s3(file_path):
    """Upload model.tar.gz to S3."""
    key = f"sagemaker/models/enhanced-{int(time.time())}/model.tar.gz"
    print(f"Uploading to s3://{S3_BUCKET}/{key}...")

    s3.upload_file(str(file_path), S3_BUCKET, key)
    s3_uri = f"s3://{S3_BUCKET}/{key}"

    print(f"Uploaded: {s3_uri}")
    return s3_uri


def get_execution_role():
    """Get or create SageMaker execution role."""
    role_name = "SageMakerExecutionRole"

    try:
        role = iam.get_role(RoleName=role_name)
        role_arn = role["Role"]["Arn"]
        print(f"Found role: {role_arn}")
        return role_arn
    except:
        print(f"ERROR: Role '{role_name}' not found. Please create it first.")
        print("\nCreate with:")
        print(f"  aws iam create-role --role-name {role_name} --assume-role-policy-document file://trust-policy.json")
        exit(1)


def create_or_update_model(model_name, model_data_url, role_arn):
    """Create or update SageMaker model."""
    # HuggingFace Deep Learning Container image
    image_uri = "763104351884.dkr.ecr.us-east-1.amazonaws.com/huggingface-pytorch-inference:2.1.0-transformers4.37.0-gpu-py310-cu118-ubuntu20.04"

    model_config = {
        "ModelName": model_name,
        "PrimaryContainer": {
            "Image": image_uri,
            "ModelDataUrl": model_data_url,
            "Environment": {
                "MODELS_S3_BUCKET": S3_BUCKET,
                "HF_MODEL_ID": "stabilityai/sdxl-turbo",
                "SAGEMAKER_CONTAINER_LOG_LEVEL": "20",
                "SAGEMAKER_REGION": REGION,
            }
        },
        "ExecutionRoleArn": role_arn,
    }

    try:
        sm.describe_model(ModelName=model_name)
        print(f"Model '{model_name}' already exists, deleting...")
        sm.delete_model(ModelName=model_name)
        time.sleep(2)
    except:
        pass

    print(f"Creating model: {model_name}")
    sm.create_model(**model_config)
    print(f"Model created: {model_name}")


def create_endpoint_config(config_name, model_name):
    """Create endpoint configuration."""
    try:
        sm.describe_endpoint_config(EndpointConfigName=config_name)
        print(f"Endpoint config '{config_name}' already exists, deleting...")
        sm.delete_endpoint_config(EndpointConfigName=config_name)
        time.sleep(2)
    except:
        pass

    print(f"Creating endpoint config: {config_name}")
    sm.create_endpoint_config(
        EndpointConfigName=config_name,
        ProductionVariants=[{
            "VariantName": "AllTraffic",
            "ModelName": model_name,
            "InitialInstanceCount": 1,
            "InstanceType": INSTANCE_TYPE,
        }]
    )
    print(f"Endpoint config created: {config_name}")


def create_or_update_endpoint(endpoint_name, config_name):
    """Create or update endpoint."""
    try:
        response = sm.describe_endpoint(EndpointName=endpoint_name)
        status = response["EndpointStatus"]
        print(f"Endpoint '{endpoint_name}' exists (status: {status})")

        if status == "InService":
            print("Updating endpoint...")
            sm.update_endpoint(
                EndpointName=endpoint_name,
                EndpointConfigName=config_name,
            )
            print("Update initiated. Waiting for update to complete...")
        else:
            print(f"Endpoint in status '{status}', waiting...")

        # Wait for endpoint to be in service
        waiter = sm.get_waiter("endpoint_in_service")
        waiter.wait(EndpointName=endpoint_name)

    except sm.exceptions.ClientError as e:
        if "Could not find endpoint" in str(e):
            print(f"Creating new endpoint: {endpoint_name}")
            sm.create_endpoint(
                EndpointName=endpoint_name,
                EndpointConfigName=config_name,
            )
            print("Creation initiated. Waiting for endpoint to be in service...")

            # Wait for endpoint
            waiter = sm.get_waiter("endpoint_in_service")
            waiter.wait(EndpointName=endpoint_name)
        else:
            raise

    print(f"\n✓ Endpoint ready: {endpoint_name}")


def main():
    print(f"\n{'='*80}")
    print(f"SageMaker Endpoint Deployment (Simple)")
    print(f"{'='*80}\n")
    print(f"Endpoint: {ENDPOINT_NAME}")
    print(f"Region: {REGION}")
    print(f"Instance: {INSTANCE_TYPE}")
    print(f"S3 Bucket: {S3_BUCKET}\n")

    # Step 1: Create model package
    tar_path = create_model_tar()

    # Step 2: Upload to S3
    model_data_url = upload_to_s3(tar_path)

    # Step 3: Get execution role
    role_arn = get_execution_role()

    # Step 4: Create model
    model_name = f"{ENDPOINT_NAME}-model-{int(time.time())}"
    create_or_update_model(model_name, model_data_url, role_arn)

    # Step 5: Create endpoint config
    config_name = f"{ENDPOINT_NAME}-config-{int(time.time())}"
    create_endpoint_config(config_name, model_name)

    # Step 6: Create/update endpoint
    create_or_update_endpoint(ENDPOINT_NAME, config_name)

    print(f"\n{'='*80}")
    print(f"DEPLOYMENT COMPLETE!")
    print(f"{'='*80}")
    print(f"Endpoint: {ENDPOINT_NAME}")
    print(f"Status: InService")
    print(f"\nTest with:")
    print(f"  python test_endpoint.py")


if __name__ == "__main__":
    main()
