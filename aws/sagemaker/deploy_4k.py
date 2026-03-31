"""
Deploy native 4K SageMaker endpoint (3840×2160 or 3840×3840).

Deploy on ml.g5.4xlarge (24GB) or ml.g5.8xlarge (48GB). ~120–180s per image.

Usage:
  Set SAGEMAKER_ROLE (or SAGEMAKER_ROLE_NAME). Optionally SAGEMAKER_BUCKET, AWS_REGION.
  Package: tar -czf model_4k.tar.gz -C aws/sagemaker/model/code inference_4k.py (and deps if any)
  Upload: aws s3 cp model_4k.tar.gz s3://YOUR_BUCKET/models/4k/model.tar.gz
  Then: python aws/sagemaker/deploy_4k.py

  Or set MODEL_S3_URI=s3://bucket/models/4k/model.tar.gz to use existing package.
"""

import json
import os
import tarfile
import tempfile
from pathlib import Path

import boto3

_script_dir = Path(__file__).resolve().parent
_code_dir = _script_dir / "model" / "code"


def _get_execution_role(region: str):
    if os.environ.get("SAGEMAKER_ROLE"):
        return os.environ["SAGEMAKER_ROLE"].strip()
    iam = boto3.client("iam", region_name=region)
    role_name = os.environ.get("SAGEMAKER_ROLE_NAME", "PhotoGeniusSageMakerRole")
    try:
        role = iam.get_role(RoleName=role_name)
        return role["Role"]["Arn"]
    except iam.exceptions.NoSuchEntityException:
        trust = {"Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Principal": {"Service": "sagemaker.amazonaws.com"}, "Action": "sts:AssumeRole"}]}
        role = iam.create_role(RoleName=role_name, AssumeRolePolicyDocument=json.dumps(trust))
        iam.attach_role_policy(RoleName=role_name, PolicyArn="arn:aws:iam::aws:policy/AmazonSageMakerFullAccess")
        return role["Role"]["Arn"]


def _prepare_model_artifacts(region: str, bucket: str) -> str:
    model_s3_uri = os.environ.get("MODEL_S3_URI", "").strip()
    if model_s3_uri:
        print("Using existing MODEL_S3_URI:", model_s3_uri)
        return model_s3_uri

    if not _code_dir.exists():
        raise FileNotFoundError(f"Code dir not found: {_code_dir}")

    s3 = boto3.client("s3", region_name=region)
    try:
        s3.head_bucket(Bucket=bucket)
    except Exception:
        s3.create_bucket(
            Bucket=bucket,
            CreateBucketConfiguration={"LocationConstraint": region} if region != "us-east-1" else {},
        )

    print("Packaging 4K model code...")
    with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
        with tarfile.open(tmp.name, "w:gz") as tar:
            tar.add(_code_dir, arcname="code")
        tmp_path = tmp.name

    s3_key = "models/4k/model.tar.gz"
    s3.upload_file(tmp_path, bucket, s3_key)
    os.unlink(tmp_path)
    uri = f"s3://{bucket}/{s3_key}"
    print("Uploaded:", uri)
    return uri


def deploy_4k_endpoint():
    """Deploy native 4K endpoint to SageMaker (ml.g5.4xlarge or ml.g5.8xlarge)."""
    region = os.environ.get("AWS_REGION", "us-east-1")
    bucket = os.environ.get("SAGEMAKER_BUCKET") or None
    if not bucket:
        try:
            session = __import__("sagemaker").Session(boto_session=boto3.Session(region_name=region))
            bucket = session.default_bucket()
        except Exception:
            bucket = f"photogenius-sagemaker-{boto3.client('sts', region_name=region).get_caller_identity()['Account']}"

    role = _get_execution_role(region)
    model_data = _prepare_model_artifacts(region, bucket)

    instance_type = os.environ.get("SAGEMAKER_INSTANCE_4K", "ml.g5.4xlarge")
    try:
        sagemaker = __import__("sagemaker")
        image_uri = sagemaker.image_uris.retrieve(
            framework="pytorch",
            region=region,
            version="2.1.0",
            py_version="py310",
            instance_type=instance_type,
            image_scope="inference",
        )
    except Exception as e:
        print("image_uris.retrieve failed:", e)
        image_uri = f"763104351884.dkr.ecr.{region}.amazonaws.com/pytorch-inference:2.1.0-gpu-py310"

    PyTorchModel = getattr(__import__("sagemaker.pytorch", fromlist=["PyTorchModel"]), "PyTorchModel")
    endpoint_name = os.environ.get("SAGEMAKER_ENDPOINT_4K", "photogenius-4k-dev")

    env = {
        "SAGEMAKER_PROGRAM": "inference_4k.py",
        "SAGEMAKER_SUBMIT_DIRECTORY": "/opt/ml/model/code",
        "SAGEMAKER_MODEL_SERVER_TIMEOUT": "600",
        "TS_MAX_REQUEST_SIZE": "100000000",
        "TS_MAX_RESPONSE_SIZE": "100000000",
        "TS_DEFAULT_RESPONSE_TIMEOUT": "600",
    }
    if os.environ.get("HUGGINGFACE_TOKEN"):
        env["HUGGINGFACE_TOKEN"] = os.environ["HUGGINGFACE_TOKEN"]
    if os.environ.get("HF_TOKEN"):
        env["HF_TOKEN"] = os.environ["HF_TOKEN"]

    try:
        from sagemaker import Session
        session = Session(boto_session=boto3.Session(region_name=region))
    except ImportError:
        session = None

    model = PyTorchModel(
        model_data=model_data,
        role=role,
        image_uri=image_uri,
        sagemaker_session=session,
        env=env,
    )

    print(f"Deploying 4K endpoint: {endpoint_name} (instance: {instance_type})...")
    predictor = model.deploy(
        initial_instance_count=1,
        instance_type=instance_type,
        endpoint_name=endpoint_name,
        wait=True,
    )
    print("✅ 4K endpoint deployed:", predictor.endpoint_name)
    return predictor


if __name__ == "__main__":
    deploy_4k_endpoint()
