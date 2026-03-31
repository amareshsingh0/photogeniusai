"""
Deploy SDXL model to SageMaker with optimizations.

Features:
- SDXL (or SDXL Turbo) with 4–50 steps
- PyTorch DLC + custom inference script
- Auto-scaling (1–10 instances)
- Optional: package code only; model loads from HuggingFace at runtime

Usage:
  Set SAGEMAKER_ROLE (or use existing SageMaker role).
  Optionally set MODEL_S3_URI to skip upload and use existing model tarball.
  Run: python deploy_model.py
"""

import json
import os
import tarfile
import tempfile
from pathlib import Path

import boto3

_script_dir = Path(__file__).resolve().parent
_code_dir = _script_dir / "model" / "code"


class SDXLModelDeployer:
    """
    Deploy optimized SDXL model to SageMaker.
    - Custom inference (inference.py) with HF-style and direct JSON
    - Auto-scaling (1–10 instances)
    """

    def __init__(self, region=None, endpoint_name=None, instance_type=None):
        self.region = region or os.environ.get("AWS_REGION", "us-east-1")
        self.endpoint_name = endpoint_name or os.environ.get("SAGEMAKER_ENDPOINT", "photogenius-sdxl")
        self.instance_type = instance_type or os.environ.get("SAGEMAKER_INSTANCE", "ml.g5.xlarge")
        self.sagemaker = boto3.client("sagemaker", region_name=self.region)
        self.role = self._get_execution_role()
        try:
            self.session = __import__("sagemaker").Session(boto_session=boto3.Session(region_name=self.region))
            self.bucket = os.environ.get("SAGEMAKER_BUCKET") or self.session.default_bucket()
        except Exception:
            self.session = None
            self.bucket = os.environ.get("SAGEMAKER_BUCKET") or f"photogenius-sagemaker-{boto3.client('sts', region_name=self.region).get_caller_identity()['Account']}"

    def _get_execution_role(self):
        """Get or create SageMaker execution role."""
        iam = boto3.client("iam", region_name=self.region)
        role_name = os.environ.get("SAGEMAKER_ROLE_NAME", "PhotoGeniusSageMakerRole")

        if os.environ.get("SAGEMAKER_ROLE"):
            return os.environ["SAGEMAKER_ROLE"].strip()

        try:
            role = iam.get_role(RoleName=role_name)
            return role["Role"]["Arn"]
        except iam.exceptions.NoSuchEntityException:
            pass

        trust_policy = {
            "Version": "2012-10-17",
            "Statement": [{"Effect": "Allow", "Principal": {"Service": "sagemaker.amazonaws.com"}, "Action": "sts:AssumeRole"}],
        }
        role = iam.create_role(RoleName=role_name, AssumeRolePolicyDocument=json.dumps(trust_policy))
        iam.attach_role_policy(RoleName=role_name, PolicyArn="arn:aws:iam::aws:policy/AmazonSageMakerFullAccess")
        return role["Role"]["Arn"]

    def prepare_model_artifacts(self):
        """
        Package inference code only (model loads from HuggingFace at runtime).
        Or use MODEL_S3_URI env to skip upload.
        """
        if os.environ.get("MODEL_S3_URI"):
            print("Using existing MODEL_S3_URI")
            return os.environ["MODEL_S3_URI"].strip()

        if not _code_dir.exists():
            raise FileNotFoundError(f"Code dir not found: {_code_dir}")

        print("Preparing model artifacts (code only; SDXL loads from HuggingFace at runtime)...")
        with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
            with tarfile.open(tmp.name, "w:gz") as tar:
                tar.add(_code_dir, arcname="code")
            tmp_path = tmp.name

        s3 = boto3.client("s3", region_name=self.region)
        try:
            s3.head_bucket(Bucket=self.bucket)
        except Exception:
            s3.create_bucket(Bucket=self.bucket, CreateBucketConfiguration={"LocationConstraint": self.region} if self.region != "us-east-1" else {})

        s3_key = "models/sdxl-turbo/model.tar.gz"
        s3.upload_file(tmp_path, self.bucket, s3_key)
        os.unlink(tmp_path)
        model_s3_path = f"s3://{self.bucket}/{s3_key}"
        print(f"Model uploaded: {model_s3_path}")
        return model_s3_path

    def create_model(self, model_s3_path):
        """Create SageMaker model with PyTorch DLC and custom inference."""
        try:
            sagemaker = __import__("sagemaker")
            image_uri = sagemaker.image_uris.retrieve(
                framework="pytorch",
                region=self.region,
                version="2.1.0",
                py_version="py310",
                instance_type=self.instance_type,
                image_scope="inference",
            )
        except Exception as e:
            print(f"image_uris.retrieve failed: {e}; using default PyTorch inference URI")
            image_uri = f"763104351884.dkr.ecr.{self.region}.amazonaws.com/pytorch-inference:2.1.0-gpu-py310"

        PyTorchModel = getattr(__import__("sagemaker.pytorch", fromlist=["PyTorchModel"]), "PyTorchModel")
        model = PyTorchModel(
            model_data=model_s3_path,
            role=self.role,
            image_uri=image_uri,
            sagemaker_session=getattr(self, "session", None),
            env={
                "SAGEMAKER_PROGRAM": "inference.py",
                "SAGEMAKER_SUBMIT_DIRECTORY": "/opt/ml/model/code",
                "MODEL_CACHE_ROOT": "/opt/ml/model",
                "SAGEMAKER_MODEL_SERVER_TIMEOUT": "600",
                "TS_MAX_REQUEST_SIZE": "100000000",
                "TS_MAX_RESPONSE_SIZE": "100000000",
                "TS_DEFAULT_RESPONSE_TIMEOUT": "600",
                "HF_MODEL_ID": os.environ.get("HF_MODEL_ID", "stabilityai/stable-diffusion-xl-base-1.0"),
            },
        )
        print("SageMaker model object created")
        return model

    def deploy_with_autoscaling(self, model, endpoint_name=None):
        """Deploy endpoint and configure auto-scaling (1–10 instances)."""
        endpoint_name = endpoint_name or self.endpoint_name
        print(f"Deploying endpoint: {endpoint_name} (instance: {self.instance_type})...")

        predictor = model.deploy(
            initial_instance_count=1,
            instance_type=self.instance_type,
            endpoint_name=endpoint_name,
            wait=True,
        )
        print(f"Endpoint deployed: {endpoint_name}")
        self._setup_autoscaling(endpoint_name)
        return predictor

    def _setup_autoscaling(self, endpoint_name):
        """Register scalable target and target-tracking scaling policy."""
        client = boto3.client("application-autoscaling", region_name=self.region)
        resource_id = f"endpoint/{endpoint_name}/variant/AllTraffic"
        try:
            client.register_scalable_target(
                ServiceNamespace="sagemaker",
                ResourceId=resource_id,
                ScalableDimension="sagemaker:variant:DesiredInstanceCount",
                MinCapacity=1,
                MaxCapacity=10,
            )
        except client.exceptions.ValidationException as e:
            if "already exists" not in str(e).lower():
                raise
        client.put_scaling_policy(
            PolicyName=f"{endpoint_name}-scaling-policy",
            ServiceNamespace="sagemaker",
            ResourceId=resource_id,
            ScalableDimension="sagemaker:variant:DesiredInstanceCount",
            PolicyType="TargetTrackingScaling",
            TargetTrackingScalingPolicyConfiguration={
                "TargetValue": 10.0,
                "PredefinedMetricSpecification": {"PredefinedMetricType": "SageMakerVariantInvocationsPerInstance"},
                "ScaleInCooldown": 300,
                "ScaleOutCooldown": 60,
            },
        )
        print("Auto-scaling configured (1–10 instances)")

    def deploy_all(self):
        """Full pipeline: prepare → create → deploy → autoscale."""
        print("=" * 60)
        print("SDXL SageMaker deployment")
        print("=" * 60)
        model_path = self.prepare_model_artifacts()
        model = self.create_model(model_path)
        predictor = self.deploy_with_autoscaling(model)
        print("=" * 60)
        print("Deployment complete:", predictor.endpoint_name)
        print("=" * 60)
        return predictor


def main():
    deployer = SDXLModelDeployer()
    deployer.deploy_all()


if __name__ == "__main__":
    main()
