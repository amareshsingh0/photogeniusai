"""
Deploy SDXL via SageMaker JumpStart (pre-packaged models, no download needed).

Usage:
    python deploy/sagemaker_jumpstart.py --deploy
    python deploy/sagemaker_jumpstart.py --delete
    python deploy/sagemaker_jumpstart.py --test
"""

import argparse
import json
import os
import boto3
from datetime import datetime

# AWS Configuration
REGION = os.environ.get("AWS_REGION", "us-east-1")

# SageMaker JumpStart Model IDs for SDXL
JUMPSTART_MODELS = {
    "sdxl": {
        "model_id": "model-txt2img-stabilityai-stable-diffusion-xl-base-1-0",
        "model_version": "*",  # Latest version
        "instance_type": "ml.g5.2xlarge",
        "endpoint_name": "photogenius-sdxl-jumpstart",
    },
    "sdxl-turbo": {
        # SDXL Turbo via JumpStart (if available) or fallback
        "model_id": "huggingface-txt2img-stabilityai-stable-diffusion-xl-base-1-0-fp16",
        "model_version": "*",
        "instance_type": "ml.g5.xlarge",
        "endpoint_name": "photogenius-turbo-jumpstart",
    },
}


def get_sagemaker_role():
    """Get SageMaker execution role from environment or IAM."""
    role = os.environ.get("SAGEMAKER_ROLE")
    if role:
        return role

    # Try to get from IAM
    try:
        iam = boto3.client("iam", region_name=REGION)
        roles = iam.list_roles()["Roles"]
        for r in roles:
            if "SageMaker" in r["RoleName"]:
                return r["Arn"]
    except Exception:
        pass

    raise ValueError("Set SAGEMAKER_ROLE env var with IAM role ARN for SageMaker")


def deploy_jumpstart_model(model_key: str = "sdxl"):
    """Deploy SDXL using SageMaker JumpStart (pre-packaged, fast deployment)."""
    from sagemaker.jumpstart.model import JumpStartModel

    config = JUMPSTART_MODELS[model_key]
    model_id = config["model_id"]
    instance_type = config["instance_type"]
    endpoint_name = config["endpoint_name"]

    print(f"Deploying JumpStart model: {model_id}")
    print(f"Instance type: {instance_type}")
    print(f"Endpoint name: {endpoint_name}")

    # Check if endpoint already exists
    sm = boto3.client("sagemaker", region_name=REGION)
    try:
        sm.describe_endpoint(EndpointName=endpoint_name)
        print(
            f"Endpoint {endpoint_name} already exists. Delete it first or use a different name."
        )
        return endpoint_name
    except sm.exceptions.ClientError:
        pass  # Endpoint doesn't exist, we can create it

    # Deploy using JumpStart
    model = JumpStartModel(
        model_id=model_id,
        model_version=config["model_version"],
        role=get_sagemaker_role(),
    )

    print("Starting deployment (this may take 10-15 minutes)...")
    predictor = model.deploy(
        initial_instance_count=1,
        instance_type=instance_type,
        endpoint_name=endpoint_name,
    )

    print(f"✅ Endpoint deployed: {endpoint_name}")
    return endpoint_name


def deploy_with_boto3(model_key: str = "sdxl"):
    """Deploy using boto3 directly (fallback if sagemaker SDK unavailable)."""
    config = JUMPSTART_MODELS[model_key]
    endpoint_name = config["endpoint_name"]
    instance_type = config["instance_type"]

    sm = boto3.client("sagemaker", region_name=REGION)

    # Check if endpoint exists
    try:
        sm.describe_endpoint(EndpointName=endpoint_name)
        print(f"Endpoint {endpoint_name} already exists.")
        return endpoint_name
    except sm.exceptions.ClientError:
        pass

    # For boto3 deployment, we need the model package ARN
    # JumpStart models are available via model registry
    model_package_group = f"jumpstart-dft-{config['model_id']}"

    print(f"Deploying model: {model_package_group}")
    print(f"Instance: {instance_type}")
    print(f"Endpoint: {endpoint_name}")

    # Create model
    model_name = f"{endpoint_name}-model-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    # Get the latest model package from JumpStart
    # Note: This requires the model package to be subscribed
    try:
        # Try direct JumpStart inference image
        image_uri = f"763104351884.dkr.ecr.{REGION}.amazonaws.com/huggingface-pytorch-inference:2.0.0-transformers4.28.1-gpu-py310-cu118-ubuntu20.04"

        sm.create_model(
            ModelName=model_name,
            ExecutionRoleArn=get_sagemaker_role(),
            PrimaryContainer={
                "Image": image_uri,
                "Mode": "SingleModel",
                "Environment": {
                    "HF_MODEL_ID": "stabilityai/stable-diffusion-xl-base-1.0",
                    "HF_TASK": "text-to-image",
                },
            },
        )
        print(f"Model created: {model_name}")
    except Exception as e:
        print(f"Model creation failed: {e}")
        print("Try using the SageMaker SDK: pip install sagemaker")
        return None

    # Create endpoint config
    config_name = f"{endpoint_name}-config-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    sm.create_endpoint_config(
        EndpointConfigName=config_name,
        ProductionVariants=[
            {
                "VariantName": "AllTraffic",
                "ModelName": model_name,
                "InstanceType": instance_type,
                "InitialInstanceCount": 1,
            }
        ],
    )
    print(f"Endpoint config created: {config_name}")

    # Create endpoint
    sm.create_endpoint(
        EndpointName=endpoint_name,
        EndpointConfigName=config_name,
    )
    print(f"Endpoint creation started: {endpoint_name}")
    print("Waiting for endpoint to be InService (10-15 minutes)...")

    # Wait for endpoint
    waiter = sm.get_waiter("endpoint_in_service")
    waiter.wait(EndpointName=endpoint_name)

    print(f"✅ Endpoint deployed: {endpoint_name}")
    return endpoint_name


def delete_endpoint(endpoint_name: str):
    """Delete a SageMaker endpoint."""
    sm = boto3.client("sagemaker", region_name=REGION)

    try:
        # Get endpoint config and model
        endpoint = sm.describe_endpoint(EndpointName=endpoint_name)
        config_name = endpoint["EndpointConfigName"]

        config = sm.describe_endpoint_config(EndpointConfigName=config_name)
        model_name = config["ProductionVariants"][0]["ModelName"]

        # Delete endpoint
        print(f"Deleting endpoint: {endpoint_name}")
        sm.delete_endpoint(EndpointName=endpoint_name)

        # Wait for deletion
        waiter = sm.get_waiter("endpoint_deleted")
        waiter.wait(EndpointName=endpoint_name)

        # Delete config and model
        print(f"Deleting endpoint config: {config_name}")
        sm.delete_endpoint_config(EndpointConfigName=config_name)

        print(f"Deleting model: {model_name}")
        sm.delete_model(ModelName=model_name)

        print(f"✅ Endpoint deleted: {endpoint_name}")

    except sm.exceptions.ClientError as e:
        print(f"Error: {e}")


def test_endpoint(endpoint_name: str):
    """Test the deployed endpoint."""
    sm_runtime = boto3.client("sagemaker-runtime", region_name=REGION)

    payload = {
        "prompt": "a beautiful sunset over mountains, photorealistic",
        "num_inference_steps": 20,
        "guidance_scale": 7.5,
    }

    print(f"Testing endpoint: {endpoint_name}")
    print(f"Payload: {json.dumps(payload)}")

    try:
        response = sm_runtime.invoke_endpoint(
            EndpointName=endpoint_name,
            ContentType="application/json",
            Body=json.dumps(payload),
        )
        result = json.loads(response["Body"].read())

        if "generated_image" in result or "images" in result:
            print("✅ Test successful! Image generated.")
            # Save image preview info
            if "generated_image" in result:
                img_data = result["generated_image"][:100]
                print(f"Image data (preview): {img_data}...")
        else:
            print(f"Response: {json.dumps(result, indent=2)[:500]}")

    except Exception as e:
        print(f"Test failed: {e}")


def list_endpoints():
    """List all PhotoGenius SageMaker endpoints."""
    sm = boto3.client("sagemaker", region_name=REGION)

    endpoints = sm.list_endpoints(
        NameContains="photogenius",
        StatusEquals="InService",
    )["Endpoints"]

    print("\n=== PhotoGenius Endpoints ===")
    for ep in endpoints:
        print(f"  {ep['EndpointName']}: {ep['EndpointStatus']}")

    if not endpoints:
        print("  No active endpoints found.")


def main():
    parser = argparse.ArgumentParser(description="Deploy SDXL via SageMaker JumpStart")
    parser.add_argument("--deploy", action="store_true", help="Deploy SDXL endpoint")
    parser.add_argument("--delete", type=str, help="Delete endpoint by name")
    parser.add_argument("--test", type=str, help="Test endpoint by name")
    parser.add_argument("--list", action="store_true", help="List all endpoints")
    parser.add_argument(
        "--model", type=str, default="sdxl", choices=["sdxl", "sdxl-turbo"]
    )

    args = parser.parse_args()

    if args.list:
        list_endpoints()
    elif args.deploy:
        try:
            # Try JumpStart SDK first
            deploy_jumpstart_model(args.model)
        except ImportError:
            print("SageMaker JumpStart SDK not available, using boto3...")
            deploy_with_boto3(args.model)
    elif args.delete:
        delete_endpoint(args.delete)
    elif args.test:
        test_endpoint(args.test)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
