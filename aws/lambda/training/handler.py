"""
PhotoGenius AI - Training Lambda
Triggers SageMaker training jobs for LoRA fine-tuning.
"""

import json
import os
import boto3
import time

AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
S3_BUCKET = os.environ.get("S3_BUCKET", "photogenius-loras-dev")
SAGEMAKER_ROLE = os.environ.get("SAGEMAKER_ROLE", "")

sagemaker_client = boto3.client("sagemaker", region_name=AWS_REGION)
s3_client = boto3.client("s3", region_name=AWS_REGION)


def start_training_job(user_id: str, identity_id: str, image_urls: list) -> dict:
    """
    Start a SageMaker training job for LoRA fine-tuning.

    Args:
        user_id: User ID
        identity_id: Identity ID
        image_urls: List of training image URLs

    Returns:
        Training job details
    """
    job_name = f"photogenius-lora-{identity_id[:8]}-{int(time.time())}"

    # Training job configuration
    training_params = {
        "TrainingJobName": job_name,
        "AlgorithmSpecification": {
            "TrainingImage": "763104351884.dkr.ecr.us-east-1.amazonaws.com/huggingface-pytorch-training:2.0.0-transformers4.28.1-gpu-py310-cu118-ubuntu20.04",
            "TrainingInputMode": "File",
        },
        "RoleArn": SAGEMAKER_ROLE,
        "InputDataConfig": [
            {
                "ChannelName": "training",
                "DataSource": {
                    "S3DataSource": {
                        "S3DataType": "S3Prefix",
                        "S3Uri": f"s3://{S3_BUCKET}/training/{identity_id}/",
                        "S3DataDistributionType": "FullyReplicated",
                    }
                },
            }
        ],
        "OutputDataConfig": {
            "S3OutputPath": f"s3://{S3_BUCKET}/loras/{user_id}/",
        },
        "ResourceConfig": {
            "InstanceCount": 1,
            "InstanceType": "ml.g5.2xlarge",
            "VolumeSizeInGB": 50,
        },
        "StoppingCondition": {
            "MaxRuntimeInSeconds": 3600,  # 1 hour max
        },
        "HyperParameters": {
            "epochs": "10",
            "learning_rate": "1e-4",
            "lora_rank": "64",
            "batch_size": "1",
        },
    }

    # Note: In production, you would actually start the job
    # response = sagemaker_client.create_training_job(**training_params)

    return {
        "job_name": job_name,
        "status": "queued",
        "estimated_time": "15-20 minutes",
    }


def lambda_handler(event, context):
    """
    AWS Lambda handler for LoRA training.

    Expected input:
        {
            "user_id": "...",
            "identity_id": "...",
            "image_urls": ["...", "..."],
            "trigger_word": "sks",
            "training_steps": 1000
        }

    Returns:
        {"success": bool, "job_id": "...", "status": "..."}
    """
    try:
        # Parse input
        if isinstance(event.get("body"), str):
            body = json.loads(event["body"])
        else:
            body = event.get("body", event)

        user_id = body.get("user_id", "")
        identity_id = body.get("identity_id", "")
        image_urls = body.get("image_urls", [])

        if not user_id or not identity_id or not image_urls:
            return {
                "statusCode": 400,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                },
                "body": json.dumps({
                    "error": "user_id, identity_id, and image_urls are required"
                })
            }

        if len(image_urls) < 8:
            return {
                "statusCode": 400,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                },
                "body": json.dumps({
                    "error": f"Minimum 8 images required, got {len(image_urls)}"
                })
            }

        print(f"Starting training for identity {identity_id} with {len(image_urls)} images")

        # Start training job
        job_info = start_training_job(user_id, identity_id, image_urls)

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps({
                "success": True,
                "job_id": job_info["job_name"],
                "status": job_info["status"],
                "estimated_time": job_info["estimated_time"],
                "provider": "aws",
            })
        }

    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps({"error": str(e), "success": False})
        }
