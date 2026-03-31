"""
Upload PhotoGenius SageMaker package to S3 and deploy multi-tier endpoints.

Usage:
  1. Package first:  python deploy/sagemaker/package_model.py
  2. Set env:         SAGEMAKER_ROLE (required), SAGEMAKER_BUCKET (optional)
  3. Deploy:          python deploy/sagemaker/upload_and_deploy.py [--tier STANDARD|PREMIUM|PERFECT|all] [--dry-run]

Uses deploy/endpoint_config.yaml for tier settings and auto-scaling.
"""

from __future__ import annotations

import argparse
import os
import sys
import tarfile
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent.parent
ARTIFACTS_DIR = SCRIPT_DIR / "artifacts"
MODEL_TAR = ARTIFACTS_DIR / "model.tar.gz"
CONFIG_PATH = ROOT / "deploy" / "endpoint_config.yaml"


def _load_config(path: Path) -> dict:
    if not path.exists():
        return {
            "defaults": {"region": "us-east-1"},
            "tiers": {
                "STANDARD": {
                    "endpoint_name": "photogenius-standard",
                    "instance_type": "ml.g5.xlarge",
                    "min_capacity": 1,
                    "max_capacity": 10,
                    "model_env": {"PHOTOGENIUS_TIER": "STANDARD"},
                },
                "PREMIUM": {
                    "endpoint_name": "photogenius-two-pass",
                    "instance_type": "ml.g5.2xlarge",
                    "min_capacity": 1,
                    "max_capacity": 10,
                    "model_env": {"PHOTOGENIUS_TIER": "PREMIUM"},
                },
                "PERFECT": {
                    "endpoint_name": "photogenius-perfect",
                    "instance_type": "ml.g5.4xlarge",
                    "min_capacity": 1,
                    "max_capacity": 10,
                    "model_env": {"PHOTOGENIUS_TIER": "PERFECT"},
                },
            },
            "cloudwatch": {},
        }
    try:
        import yaml
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except ImportError:
        return _load_config(Path("/nonexistent"))


def _ensure_photogenius_tier_in_config(config: dict) -> dict:
    """Add PHOTOGENIUS_TIER to each tier's model_env if missing."""
    for tier, cfg in config.get("tiers", {}).items():
        env = cfg.setdefault("model_env", {})
        if "PHOTOGENIUS_TIER" not in env:
            env["PHOTOGENIUS_TIER"] = tier
    return config


def upload_to_s3(region: str, bucket: str, local_tar: Path) -> str:
    """Upload model.tar.gz to S3; return s3:// URI."""
    try:
        import boto3
    except ImportError:
        print("boto3 required: pip install boto3", file=sys.stderr)
        sys.exit(1)
    s3 = boto3.client("s3", region_name=region)
    try:
        s3.head_bucket(Bucket=bucket)
    except Exception:
        s3.create_bucket(
            Bucket=bucket,
            CreateBucketConfiguration=({"LocationConstraint": region} if region != "us-east-1" else {}),
        )
    key = "photogenius/sagemaker/model.tar.gz"
    print(f"Uploading {local_tar} to s3://{bucket}/{key} ...")
    s3.upload_file(str(local_tar), bucket, key)
    uri = f"s3://{bucket}/{key}"
    print(f"   [OK] {uri}")
    return uri


def get_bucket(region: str, config: dict) -> str:
    bucket = os.environ.get("SAGEMAKER_BUCKET", "").strip() or config.get("defaults", {}).get("bucket")
    if bucket:
        return bucket
    import boto3
    sts = boto3.client("sts", region_name=region)
    account = sts.get_caller_identity()["Account"]
    return f"photogenius-sagemaker-{account}"


def get_role(region: str, config: dict) -> str:
    role = os.environ.get("SAGEMAKER_ROLE", "").strip()
    if role:
        return role
    role_name = config.get("defaults", {}).get("sagemaker_role_name") or "PhotoGeniusSageMakerRole"
    try:
        import boto3
        iam = boto3.client("iam", region_name=region)
        return iam.get_role(RoleName=role_name)["Role"]["Arn"]
    except Exception:
        pass
    raise ValueError("Set SAGEMAKER_ROLE to your SageMaker execution role ARN.")


def deploy_with_sagemaker_deployment_script(model_s3_uri: str, tier: str, dry_run: bool) -> None:
    """Invoke the main deploy script with MODEL_S3_URI set."""
    os.environ["MODEL_S3_URI"] = model_s3_uri
    deploy_script = ROOT / "deploy" / "sagemaker_deployment.py"
    if not deploy_script.exists():
        print("deploy/sagemaker_deployment.py not found; deploy manually with MODEL_S3_URI set.", file=sys.stderr)
        return
    # Run as subprocess so env is passed
    import subprocess
    cmd = [sys.executable, str(deploy_script), "--tier", tier]
    if dry_run:
        cmd.append("--dry-run")
    subprocess.run(cmd, cwd=str(ROOT), check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Upload PhotoGenius model to S3 and deploy SageMaker endpoints")
    parser.add_argument("--tier", choices=["STANDARD", "PREMIUM", "PERFECT", "all"], default="all")
    parser.add_argument("--dry-run", action="store_true", help="Print actions only")
    parser.add_argument("--package-only", action="store_true", help="Only run package_model.py, no upload/deploy")
    parser.add_argument("--upload-only", action="store_true", help="Only upload to S3 (no deploy)")
    args = parser.parse_args()

    config = _ensure_photogenius_tier_in_config(_load_config(CONFIG_PATH))
    region = config.get("defaults", {}).get("region", os.environ.get("AWS_REGION", "us-east-1"))

    if not MODEL_TAR.exists() and not args.package_only:
        print("Running package_model.py to create model.tar.gz...")
        import runpy
        runpy.run_path(str(SCRIPT_DIR / "package_model.py"), run_name="__main__")
    if args.package_only:
        return 0

    if not MODEL_TAR.exists():
        print(f"Missing {MODEL_TAR}. Run: python deploy/sagemaker/package_model.py", file=sys.stderr)
        return 1

    if args.upload_only:
        bucket = get_bucket(region, config)
        uri = upload_to_s3(region, bucket, MODEL_TAR)
        print(f"Set MODEL_S3_URI={uri} and run deploy/sagemaker_deployment.py for deployment.")
        return 0

    try:
        role_arn = get_role(region, config)
    except ValueError as e:
        print(e, file=sys.stderr)
        return 1

    bucket = get_bucket(region, config)
    if args.dry_run:
        print(f"[DRY-RUN] Would upload {MODEL_TAR} to s3://{bucket}/... and deploy tier(s) {args.tier}")
        return 0

    model_s3_uri = upload_to_s3(region, bucket, MODEL_TAR)
    deploy_with_sagemaker_deployment_script(model_s3_uri, args.tier, args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
