"""
AWS SageMaker Deployment - Production with auto-scaling.

P0: Deploy to production with multi-tier endpoints and CloudWatch monitoring.
Infrastructure:
- Model packaging with all skills (references aws/sagemaker model/code)
- Multi-tier endpoints: STANDARD, PREMIUM, PERFECT
- Auto-scaling (1-10 instances per tier)
- CloudWatch monitoring (latency, errors)

Success Metric: <5s latency STANDARD, <30s PERFECT tier.

Usage:
  Set SAGEMAKER_ROLE (or use existing SageMaker role).
  Optionally set CONFIG_PATH to deploy/endpoint_config.yaml.
  Run: python deploy/sagemaker_deployment.py [--tier STANDARD|PREMIUM|PERFECT|all] [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Project root (parent of deploy/)
ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "deploy" / "endpoint_config.yaml"
AWS_SAGEMAKER = ROOT / "aws" / "sagemaker"
MODEL_CODE = AWS_SAGEMAKER / "model" / "code"
# Pre-packaged artifact from deploy/sagemaker/package_model.py (full pipeline + inference)
SAGEMAKER_ARTIFACT_TAR = ROOT / "deploy" / "sagemaker" / "artifacts" / "model.tar.gz"


def _load_config(path: Path) -> dict:
    """Load YAML config; fallback to dict if PyYAML missing."""
    if not path.exists():
        return {"tiers": {}, "defaults": {}, "cloudwatch": {}}
    try:
        import yaml

        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except ImportError:
        # Minimal inline config if no PyYAML
        return {
            "defaults": {"region": "us-east-1"},
            "tiers": {
                "STANDARD": {
                    "endpoint_name": "photogenius-standard",
                    "instance_type": "ml.g5.xlarge",
                    "min_capacity": 1,
                    "max_capacity": 10,
                },
                "PREMIUM": {
                    "endpoint_name": "photogenius-two-pass",
                    "instance_type": "ml.g5.2xlarge",
                    "min_capacity": 1,
                    "max_capacity": 10,
                },
                "PERFECT": {
                    "endpoint_name": "photogenius-perfect",
                    "instance_type": "ml.g5.2xlarge",
                    "min_capacity": 1,
                    "max_capacity": 10,
                },
            },
            "cloudwatch": {},
        }


def _get_role(region: str, config: dict) -> str:
    """Get SageMaker execution role ARN."""
    role = os.environ.get("SAGEMAKER_ROLE", "").strip()
    if role:
        return role
    role_name = (
        config.get("defaults", {}).get("sagemaker_role_name")
        or "PhotoGeniusSageMakerRole"
    )
    try:
        import boto3

        iam = boto3.client("iam", region_name=region)
        r = iam.get_role(RoleName=role_name)
        return r["Role"]["Arn"]
    except Exception:
        pass
    try:
        import sagemaker

        if hasattr(sagemaker, "get_execution_role"):
            return sagemaker.get_execution_role()
    except Exception:
        pass
    raise ValueError("Set SAGEMAKER_ROLE env var with IAM role ARN for SageMaker.")


def _get_default_bucket(region: str) -> str:
    """Get default S3 bucket for SageMaker (no sagemaker.Session)."""
    bucket = os.environ.get("SAGEMAKER_BUCKET", "").strip()
    if bucket:
        return bucket
    import boto3

    sts = boto3.client("sts", region_name=region)
    account = sts.get_caller_identity()["Account"]
    return f"photogenius-sagemaker-{account}"


def _get_pytorch_image_uri(region: str, instance_type: str) -> str:
    """Get PyTorch inference ECR image URI (no sagemaker.Session)."""
    try:
        import sagemaker

        if hasattr(sagemaker, "image_uris"):
            return sagemaker.image_uris.retrieve(
                framework="pytorch",
                region=region,
                version="2.1.0",
                py_version="py310",
                instance_type=instance_type,
                image_scope="inference",
            )
    except Exception:
        pass
    return (
        f"763104351884.dkr.ecr.{region}.amazonaws.com/pytorch-inference:2.1.0-gpu-py310"
    )


def _deploy_tier_boto3(
    region: str,
    role_arn: str,
    endpoint_name: str,
    model_data: str,
    image_uri: str,
    instance_type: str,
    min_cap: int,
    tier_cfg: dict,
) -> None:
    """Deploy one tier using boto3 only (no sagemaker.pytorch)."""
    import boto3

    sm = boto3.client("sagemaker", region_name=region)
    model_name = f"{endpoint_name}-model"
    # Include instance type so we can have multiple configs (e.g. PERFECT with 2xlarge vs 4xlarge)
    config_name = f"{endpoint_name}-config-{instance_type.replace('.', '-')}"

    env = {
        "SAGEMAKER_PROGRAM": "inference.py",
        "SAGEMAKER_MODEL_SERVER_TIMEOUT": "600",
        **tier_cfg.get("model_env", {}),
    }

    try:
        sm.create_model(
            ModelName=model_name,
            PrimaryContainer={
                "Image": image_uri,
                "ModelDataUrl": model_data,
                "Environment": env,
            },
            ExecutionRoleArn=role_arn,
        )
    except sm.exceptions.ClientError as e:
        err = e.response.get("Error", {})
        err_msg = str(err.get("Message", err.get("message", "")))
        err_code = str(err.get("Code", err.get("code", "")))
        if err_code != "ValidationException":
            raise
        if (
            "already exists" not in err_msg.lower()
            and "already existing" not in err_msg.lower()
        ):
            raise

    try:
        sm.create_endpoint_config(
            EndpointConfigName=config_name,
            ProductionVariants=[
                {
                    "VariantName": "AllTraffic",
                    "ModelName": model_name,
                    "InstanceType": instance_type,
                    "InitialInstanceCount": min_cap,
                }
            ],
        )
    except sm.exceptions.ClientError as e:
        err = e.response.get("Error", {})
        err_msg = str(err.get("Message", err.get("message", "")))
        err_code = str(err.get("Code", err.get("code", "")))
        if err_code != "ValidationException":
            raise
        if (
            "already exists" not in err_msg.lower()
            and "already existing" not in err_msg.lower()
        ):
            raise

    try:
        sm.create_endpoint(
            EndpointName=endpoint_name,
            EndpointConfigName=config_name,
        )
    except sm.exceptions.ClientError as e:
        err = e.response.get("Error", {})
        err_msg = str(err.get("Message", err.get("message", "")))
        err_code = str(err.get("Code", err.get("code", "")))
        if err_code != "ValidationException":
            raise
        if (
            "already exists" not in err_msg.lower()
            and "already existing" not in err_msg.lower()
        ):
            raise

    print(f"Waiting for endpoint {endpoint_name} to be InService...")
    waiter = sm.get_waiter("endpoint_in_service")
    waiter.wait(
        EndpointName=endpoint_name, WaiterConfig={"Delay": 30, "MaxAttempts": 60}
    )


def _upload_tar_to_s3(
    region: str,
    bucket: str,
    local_tar: Path,
    s3_key: str = "models/photogenius/model.tar.gz",
) -> str:
    """Upload an existing model.tar.gz to S3; returns s3:// URI."""
    import boto3

    if not local_tar.exists():
        raise FileNotFoundError(f"Model tar not found: {local_tar}")
    s3 = boto3.client("s3", region_name=region)
    try:
        s3.head_bucket(Bucket=bucket)
    except Exception:
        s3.create_bucket(
            Bucket=bucket,
            CreateBucketConfiguration=(
                {"LocationConstraint": region} if region != "us-east-1" else {}
            ),
        )
    s3.upload_file(str(local_tar), bucket, s3_key)
    return f"s3://{bucket}/{s3_key}"


def _package_model_artifacts(region: str, bucket: str, code_dir: Path) -> str:
    """Package inference code directory to S3; returns s3:// URI."""
    import tempfile
    import tarfile
    import boto3

    if not code_dir.exists():
        raise FileNotFoundError(f"Model code not found: {code_dir}")
    with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
        with tarfile.open(tmp.name, "w:gz") as tar:
            tar.add(code_dir, arcname="code")
        tmp_path = tmp.name
    s3 = boto3.client("s3", region_name=region)
    try:
        s3.head_bucket(Bucket=bucket)
    except Exception:
        s3.create_bucket(
            Bucket=bucket,
            CreateBucketConfiguration=(
                {"LocationConstraint": region} if region != "us-east-1" else {}
            ),
        )
    key = "models/photogenius/model.tar.gz"
    s3.upload_file(tmp_path, bucket, key)
    os.unlink(tmp_path)
    return f"s3://{bucket}/{key}"


def deploy_tier(
    tier: str,
    config: dict,
    region: str,
    role_arn: str,
    model_s3_uri: str | None,
    dry_run: bool,
) -> str | None:
    """Deploy one tier (STANDARD, PREMIUM, PERFECT). Returns endpoint name or None."""
    tiers = config.get("tiers", {})
    if tier not in tiers:
        print(f"Tier {tier} not in config; skip.")
        return None
    tier_cfg = tiers[tier]
    endpoint_name = tier_cfg.get("endpoint_name", f"photogenius-{tier.lower()}")
    instance_type = tier_cfg.get("instance_type", "ml.g5.xlarge")
    min_cap = tier_cfg.get("min_capacity", 1)
    max_cap = tier_cfg.get("max_capacity", 10)

    if dry_run:
        print(
            f"[DRY-RUN] Would deploy {tier}: {endpoint_name} ({instance_type}, {min_cap}-{max_cap})"
        )
        return endpoint_name

    import boto3

    sm_client = boto3.client("sagemaker", region_name=region)
    try:
        desc = sm_client.describe_endpoint(EndpointName=endpoint_name)
        if desc.get("EndpointStatus") == "InService":
            print(f"Endpoint already InService: {endpoint_name}")
            _setup_autoscaling_if_missing(
                region, endpoint_name, min_cap, max_cap, tier_cfg
            )
            return endpoint_name
    except Exception:
        pass

    model_data = model_s3_uri or os.environ.get("MODEL_S3_URI", "")
    bucket = _get_default_bucket(region)
    if not model_data and SAGEMAKER_ARTIFACT_TAR.exists():
        print("No MODEL_S3_URI; uploading deploy/sagemaker/artifacts/model.tar.gz.")
        model_data = _upload_tar_to_s3(region, bucket, SAGEMAKER_ARTIFACT_TAR)
    elif not model_data and MODEL_CODE.exists():
        print("No MODEL_S3_URI; packaging from aws/sagemaker/model/code.")
        model_data = _package_model_artifacts(region, bucket, MODEL_CODE)
    if not model_data:
        print(f"Skip {tier}: no model data and no code to package.")
        return None

    image_uri = _get_pytorch_image_uri(region, instance_type)

    # Prefer sagemaker SDK when available; else boto3-only (handles missing Session / pytorch)
    try:
        import sagemaker
        from sagemaker.pytorch import PyTorchModel

        model = PyTorchModel(
            model_data=model_data,
            role=role_arn,
            image_uri=image_uri,
            env={
                "SAGEMAKER_PROGRAM": "inference.py",
                "SAGEMAKER_MODEL_SERVER_TIMEOUT": "600",
                **tier_cfg.get("model_env", {}),
            },
        )
        predictor = model.deploy(
            initial_instance_count=min_cap,
            instance_type=instance_type,
            endpoint_name=endpoint_name,
            wait=True,
        )
    except (ImportError, AttributeError) as e:
        # boto3-only path (no sagemaker.pytorch or broken sagemaker e.g. missing Session)
        print(f"Using boto3 deploy (SDK unavailable: {e}).")
        _deploy_tier_boto3(
            region=region,
            role_arn=role_arn,
            endpoint_name=endpoint_name,
            model_data=model_data,
            image_uri=image_uri,
            instance_type=instance_type,
            min_cap=min_cap,
            tier_cfg=tier_cfg,
        )
    _setup_autoscaling_if_missing(region, endpoint_name, min_cap, max_cap, tier_cfg)
    print(f"Deployed {tier}: {endpoint_name}")
    return endpoint_name


def _setup_autoscaling_if_missing(
    region: str,
    endpoint_name: str,
    min_capacity: int,
    max_capacity: int,
    tier_cfg: dict,
) -> None:
    """Register scalable target and target-tracking policy (1-10 instances)."""
    import boto3

    client = boto3.client("application-autoscaling", region_name=region)
    resource_id = f"endpoint/{endpoint_name}/variant/AllTraffic"
    scaling = tier_cfg.get("scaling", {})
    target_invocations = scaling.get("target_invocations_per_instance", 2.0)
    try:
        client.register_scalable_target(
            ServiceNamespace="sagemaker",
            ResourceId=resource_id,
            ScalableDimension="sagemaker:variant:DesiredInstanceCount",
            MinCapacity=min_capacity,
            MaxCapacity=max_capacity,
        )
    except client.exceptions.ValidationException as e:
        if "already exists" not in str(e).lower():
            raise
    client.put_scaling_policy(
        PolicyName=f"{endpoint_name}-scaling",
        ServiceNamespace="sagemaker",
        ResourceId=resource_id,
        ScalableDimension="sagemaker:variant:DesiredInstanceCount",
        PolicyType="TargetTrackingScaling",
        TargetTrackingScalingPolicyConfiguration={
            "TargetValue": float(target_invocations),
            "PredefinedMetricSpecification": {
                "PredefinedMetricType": "SageMakerVariantInvocationsPerInstance"
            },
            "ScaleInCooldown": scaling.get("scale_in_cooldown", 300),
            "ScaleOutCooldown": scaling.get("scale_out_cooldown", 60),
        },
    )
    print(f"Auto-scaling set: {endpoint_name} ({min_capacity}-{max_capacity})")


def setup_cloudwatch_alarms(region: str, config: dict) -> None:
    """Create CloudWatch alarms for latency per tier (SageMaker model latency metric)."""
    cw = config.get("cloudwatch", {})
    if not cw:
        return
    try:
        import boto3

        cloudwatch = boto3.client("cloudwatch", region_name=region)
        namespace = "AWS/SageMaker"
        thresholds = cw.get("latency_alarm_threshold_seconds", {})
        tiers_cfg = config.get("tiers", {})
        for tier, sec in thresholds.items():
            endpoint_name = tiers_cfg.get(tier, {}).get(
                "endpoint_name", f"photogenius-{tier.lower()}"
            )
            alarm_name = f"photogenius-{tier}-latency"
            try:
                cloudwatch.put_metric_alarm(
                    AlarmName=alarm_name,
                    Namespace=namespace,
                    MetricName="ModelLatency",
                    Dimensions=[
                        {"Name": "EndpointName", "Value": endpoint_name},
                        {"Name": "VariantName", "Value": "AllTraffic"},
                    ],
                    Statistic="Average",
                    Period=60,
                    Threshold=float(sec),
                    ComparisonOperator="GreaterThanThreshold",
                    EvaluationPeriods=2,
                )
                print(f"CloudWatch alarm created: {alarm_name}")
            except Exception as e:
                print(f"Alarm {alarm_name}: {e}")
    except ImportError:
        pass


def _ensure_deps() -> None:
    """Fail fast with a clear message if boto3 is missing."""
    try:
        import boto3  # noqa: F401
    except ImportError:
        print(
            "Missing required dependency: boto3. Install with:\n"
            "  pip install boto3\n"
            "  or: pip install -r deploy/requirements.txt",
            file=sys.stderr,
        )
        sys.exit(1)


def main() -> int:
    _ensure_deps()
    parser = argparse.ArgumentParser(
        description="Deploy PhotoGenius SageMaker multi-tier endpoints"
    )
    parser.add_argument(
        "--tier", choices=["STANDARD", "PREMIUM", "PERFECT", "all"], default="all"
    )
    parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    config = _load_config(args.config)
    region = config.get("defaults", {}).get(
        "region", os.environ.get("AWS_REGION", "us-east-1")
    )
    role_arn = (
        _get_role(region, config)
        if not args.dry_run
        else "arn:aws:iam::000000000000:role/dry-run-placeholder"
    )
    model_s3_uri = os.environ.get("MODEL_S3_URI", "").strip() or None

    # Package once if needed (reuse same model URI for all tiers when not set)
    if not model_s3_uri and not args.dry_run and MODEL_CODE.exists():
        try:
            bucket = _get_default_bucket(region)
            model_s3_uri = _package_model_artifacts(region, bucket, MODEL_CODE)
            print(f"Model packaged: {model_s3_uri}")
        except Exception as e:
            print(f"Package failed: {e}")
    tiers_to_deploy = (
        ["STANDARD", "PREMIUM", "PERFECT"] if args.tier == "all" else [args.tier]
    )
    for tier in tiers_to_deploy:
        deploy_tier(tier, config, region, role_arn, model_s3_uri, args.dry_run)
    if not args.dry_run:
        setup_cloudwatch_alarms(region, config)
    return 0


if __name__ == "__main__":
    sys.exit(main())
