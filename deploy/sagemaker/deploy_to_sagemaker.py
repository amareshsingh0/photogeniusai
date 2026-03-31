"""
Deploy PhotoGenius AI to AWS SageMaker.

Steps:
1. Upload model.tar.gz to S3
2. Create SageMaker Model
3. Create Endpoint Configuration (multi-tier)
4. Deploy Endpoints
5. Configure Auto-Scaling

Usage:
  python deploy/sagemaker/deploy_to_sagemaker.py --model-path deploy/sagemaker/artifacts/model.tar.gz --role-arn arn:aws:iam::ACCOUNT:role/YourRole [--region us-east-1]
  Or set SAGEMAKER_ROLE and SAGEMAKER_BUCKET; --model-path can be omitted if using --s3-url.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime

import boto3


class SageMakerDeployer:
    """Deploy PhotoGenius AI to SageMaker."""

    def __init__(self, region: str = "us-east-1"):
        self.region = region
        self.sagemaker = boto3.client("sagemaker", region_name=region)
        self.s3 = boto3.client("s3", region_name=region)
        self.bucket_name = os.environ.get(
            "SAGEMAKER_BUCKET", "photogenius-ai-models"
        ).strip()
        self.role_arn: str | None = None
        self.image_uri: str | None = None

    def deploy_all_tiers(self, model_data_url: str, role_arn: str) -> dict[str, str]:
        """
        Deploy all three tiers: STANDARD, PREMIUM, PERFECT.

        Args:
            model_data_url: S3 URL to model.tar.gz (s3://bucket/path/model.tar.gz)
            role_arn: IAM role ARN for SageMaker

        Returns:
            Dict mapping tier name to endpoint name.
        """
        self.role_arn = role_arn

        print("Deploying PhotoGenius AI to SageMaker...")
        print(f"   Region: {self.region}")
        print(f"   Model: {model_data_url}")
        print(f"   Role: {role_arn}\n")

        tiers = {
            "STANDARD": "ml.g5.xlarge",
            "PREMIUM": "ml.g5.2xlarge",
            "PERFECT": "ml.g5.4xlarge",
        }

        endpoints: dict[str, str] = {}

        for tier, instance_type in tiers.items():
            print(f"\n{'='*60}")
            print(f"Deploying {tier} Tier")
            print(f"{'='*60}\n")

            endpoint_name = self._deploy_tier(
                tier=tier,
                instance_type=instance_type,
                model_data_url=model_data_url,
            )

            endpoints[tier] = endpoint_name
            print(f"[OK] {tier} tier deployed: {endpoint_name}\n")

        print("\nAll tiers deployed successfully!")
        print("\nEndpoint names:")
        for tier, endpoint in endpoints.items():
            print(f"   {tier}: {endpoint}")

        return endpoints

    def _deploy_tier(
        self,
        tier: str,
        instance_type: str,
        model_data_url: str,
    ) -> str:
        """Deploy single tier endpoint."""
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

        # 1. Create Model
        model_name = f"photogenius-{tier.lower()}-{timestamp}"

        print(f"1. Creating SageMaker Model: {model_name}")

        container = {
            "Image": self._get_inference_image_uri(),
            "ModelDataUrl": model_data_url,
            "Environment": {
                "PHOTOGENIUS_TIER": tier,
                "SAGEMAKER_PROGRAM": "inference.py",
                "SAGEMAKER_MODEL_SERVER_TIMEOUT": "600",
            },
        }

        self.sagemaker.create_model(
            ModelName=model_name,
            PrimaryContainer=container,
            ExecutionRoleArn=self.role_arn,
        )

        print(f"   [OK] Model created: {model_name}")

        # 2. Create Endpoint Config
        config_name = f"photogenius-{tier.lower()}-config-{timestamp}"

        print(f"\n2. Creating Endpoint Configuration: {config_name}")

        self.sagemaker.create_endpoint_config(
            EndpointConfigName=config_name,
            ProductionVariants=[
                {
                    "VariantName": "primary",
                    "ModelName": model_name,
                    "InstanceType": instance_type,
                    "InitialInstanceCount": 1,
                    "InitialVariantWeight": 1.0,
                }
            ],
        )

        print(f"   [OK] Config created: {config_name}")

        # 3. Create Endpoint
        endpoint_name = f"photogenius-{tier.lower()}-endpoint"

        print(f"\n3. Creating Endpoint: {endpoint_name}")
        print("   (This may take 5-10 minutes...)")

        try:
            self.sagemaker.create_endpoint(
                EndpointName=endpoint_name,
                EndpointConfigName=config_name,
            )
        except self.sagemaker.exceptions.ClientError as e:
            if e.response["Error"][
                "Code"
            ] != "ValidationException" or "already exists" not in str(
                e.response.get("Message", "")
            ):
                raise
            print("   Endpoint exists, updating instead...")
            self.sagemaker.update_endpoint(
                EndpointName=endpoint_name,
                EndpointConfigName=config_name,
            )

        self._wait_for_endpoint(endpoint_name)
        print(f"   [OK] Endpoint ready: {endpoint_name}")

        # 4. Configure Auto-Scaling
        print(f"\n4. Configuring Auto-Scaling...")
        self._configure_autoscaling(endpoint_name, tier)
        print("   [OK] Auto-scaling configured")

        return endpoint_name

    def _wait_for_endpoint(self, endpoint_name: str, timeout: int = 600) -> None:
        """Wait for endpoint to be in service."""
        start_time = time.time()

        while True:
            response = self.sagemaker.describe_endpoint(EndpointName=endpoint_name)
            status = response["EndpointStatus"]

            if status == "InService":
                return
            if status == "Failed":
                raise RuntimeError(
                    f"Endpoint creation failed: {response.get('FailureReason', 'Unknown')}"
                )

            elapsed = time.time() - start_time
            if elapsed > timeout:
                raise TimeoutError(f"Endpoint creation timeout after {timeout}s")

            print(f"   Status: {status} (elapsed: {int(elapsed)}s)")
            time.sleep(30)

    def _configure_autoscaling(self, endpoint_name: str, tier: str) -> None:
        """Configure auto-scaling for endpoint."""
        autoscaling = boto3.client("application-autoscaling", region_name=self.region)

        resource_id = f"endpoint/{endpoint_name}/variant/primary"

        autoscaling.register_scalable_target(
            ServiceNamespace="sagemaker",
            ResourceId=resource_id,
            ScalableDimension="sagemaker:variant:DesiredInstanceCount",
            MinCapacity=1,
            MaxCapacity=10 if tier == "STANDARD" else 5,
        )

        autoscaling.put_scaling_policy(
            PolicyName=f"{endpoint_name}-scaling-policy",
            ServiceNamespace="sagemaker",
            ResourceId=resource_id,
            ScalableDimension="sagemaker:variant:DesiredInstanceCount",
            PolicyType="TargetTrackingScaling",
            TargetTrackingScalingPolicyConfiguration={
                "TargetValue": 70.0,
                "PredefinedMetricSpecification": {
                    "PredefinedMetricType": "SageMakerVariantInvocationsPerInstance"
                },
                "ScaleInCooldown": 300,
                "ScaleOutCooldown": 60,
            },
        )

    def _get_inference_image_uri(self) -> str:
        """Get PyTorch inference container image URI."""
        if self.image_uri:
            return self.image_uri
        try:
            import sagemaker

            if hasattr(sagemaker, "image_uris"):
                return sagemaker.image_uris.retrieve(
                    framework="pytorch",
                    region=self.region,
                    version="2.1.0",
                    py_version="py310",
                    instance_type="ml.g5.xlarge",
                    image_scope="inference",
                )
        except Exception:
            pass
        return (
            f"763104351884.dkr.ecr.{self.region}.amazonaws.com/"
            "pytorch-inference:2.1.0-gpu-py310"
        )

    def upload_model_to_s3(self, local_model_path: str) -> str:
        """
        Upload model.tar.gz to S3.

        Returns:
            S3 URL (s3://bucket/key)
        """
        try:
            self.s3.head_bucket(Bucket=self.bucket_name)
        except Exception:
            params = {"Bucket": self.bucket_name}
            if self.region != "us-east-1":
                params["CreateBucketConfiguration"] = {
                    "LocationConstraint": self.region
                }
            self.s3.create_bucket(**params)

        key = f"models/photogenius-ai-{datetime.now().strftime('%Y%m%d')}/model.tar.gz"

        print("Uploading model to S3...")
        print(f"   Bucket: {self.bucket_name}")
        print(f"   Key: {key}")

        self.s3.upload_file(local_model_path, self.bucket_name, key)

        s3_url = f"s3://{self.bucket_name}/{key}"
        print(f"   [OK] Upload complete: {s3_url}\n")

        return s3_url


def main() -> int:
    """Main deployment script."""
    parser = argparse.ArgumentParser(description="Deploy PhotoGenius AI to SageMaker")
    parser.add_argument(
        "--model-path",
        default=None,
        help="Path to model.tar.gz (optional if --s3-url is set)",
    )
    parser.add_argument(
        "--s3-url",
        default=None,
        help="Existing S3 URL of model.tar.gz (skip upload)",
    )
    parser.add_argument(
        "--role-arn",
        default=os.environ.get("SAGEMAKER_ROLE", "").strip(),
        help="SageMaker execution role ARN (or set SAGEMAKER_ROLE)",
    )
    parser.add_argument(
        "--region",
        default=os.environ.get("AWS_REGION", "us-east-1"),
        help="AWS region",
    )
    parser.add_argument(
        "--bucket",
        default=os.environ.get("SAGEMAKER_BUCKET", "").strip(),
        help="S3 bucket for upload (or set SAGEMAKER_BUCKET)",
    )
    parser.add_argument(
        "--no-upload",
        action="store_true",
        help="Do not upload; use --s3-url or existing MODEL_S3_URI",
    )
    args = parser.parse_args()

    if not args.role_arn:
        print("Error: --role-arn or SAGEMAKER_ROLE required.", file=sys.stderr)
        return 1

    deployer = SageMakerDeployer(region=args.region)
    if args.bucket:
        deployer.bucket_name = args.bucket

    model_s3_url = args.s3_url or os.environ.get("MODEL_S3_URI", "").strip()

    if not model_s3_url and not args.no_upload and args.model_path:
        model_s3_url = deployer.upload_model_to_s3(args.model_path)
    elif not model_s3_url and args.no_upload and args.model_path:
        print(
            "Error: with --no-upload provide --s3-url or set MODEL_S3_URI.",
            file=sys.stderr,
        )
        return 1
    elif not model_s3_url:
        default_artifact = os.path.join(
            os.path.dirname(__file__), "artifacts", "model.tar.gz"
        )
        if args.model_path and os.path.isfile(args.model_path):
            model_s3_url = deployer.upload_model_to_s3(args.model_path)
        elif os.path.isfile(default_artifact):
            print(f"Using and uploading default artifact: {default_artifact}")
            model_s3_url = deployer.upload_model_to_s3(default_artifact)
        else:
            print(
                "Error: No model artifact. Run package_model.py or pass --model-path.",
                file=sys.stderr,
            )
            return 1

    deployer.deploy_all_tiers(model_s3_url, args.role_arn)

    print("\nDeployment complete!")
    print("\nNext steps:")
    print("  1. Test endpoints with invoke_endpoint (see deploy/sagemaker/README.md)")
    print("  2. Configure CloudWatch alarms (deploy/sagemaker_deployment.py sets them)")
    print("  3. Set up Lambda/API Gateway integration as needed")

    return 0


if __name__ == "__main__":
    sys.exit(main())
