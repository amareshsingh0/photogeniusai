"""
Deploy SDXL to SageMaker GPU endpoint.
Run: python deploy_endpoint.py  OR  .\\deploy.ps1
(uses aws/sagemaker/.venv with sagemaker 2.x - auto-switches if run with wrong Python)

Env vars (or in aws/sagemaker/.env):
  SAGEMAKER_ROLE       - IAM role ARN (required if no SageMaker-named role)
  HUGGINGFACE_TOKEN   - HF token for gated models (optional; SDXL public hai)
  HF_MODEL_ID         - Override model (default: stabilityai/stable-diffusion-xl-base-1.0)
"""
import os
import subprocess
import sys
from pathlib import Path

_script_dir = Path(__file__).resolve().parent


def _reexec_with_venv():
    """Re-run this script with .venv Python (has sagemaker 2.x)."""
    if sys.platform == "win32":
        venv_python = _script_dir / ".venv" / "Scripts" / "python.exe"
    else:
        venv_python = _script_dir / ".venv" / "bin" / "python"
    if venv_python.exists():
        print("Using .venv (sagemaker 2.x)...", flush=True)
        os.execv(str(venv_python), [str(venv_python), str(_script_dir / "deploy_endpoint.py")] + sys.argv[1:])
    print("ERROR: sagemaker.huggingface not found. Run: cd aws/sagemaker && .\\deploy.ps1", file=sys.stderr)
    sys.exit(1)


# Load .env from aws/sagemaker if present
try:
    from dotenv import load_dotenv  # type: ignore[reportMissingImports]
    load_dotenv(_script_dir / ".env")
    load_dotenv(_script_dir / ".env.local")
except ImportError:
    pass

# Patch JumpStart region_config.json if missing (sagemaker 2.x package bug)
_src = _script_dir / "region_config.json"
if _src.exists():
    _venv_base = Path(sys.executable).resolve().parent.parent
    if sys.platform == "win32":
        _sp = _venv_base / "Lib" / "site-packages"
    else:
        _sp = _venv_base / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"
    _dst = _sp / "sagemaker" / "jumpstart" / "region_config.json"
    if _dst.parent.exists():
        import shutil
        shutil.copy2(_src, _dst)

try:
    from sagemaker.huggingface import HuggingFaceModel  # type: ignore[reportMissingImports]
except ModuleNotFoundError as e:
    if "sagemaker.huggingface" in str(e):
        _reexec_with_venv()
    raise

import boto3  # type: ignore[reportMissingImports]
from botocore.exceptions import ClientError  # type: ignore[reportMissingImports]

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
ENDPOINT_NAME = os.getenv("SAGEMAKER_ENDPOINT", "photogenius-generation-dev")
INSTANCE_TYPE = os.getenv("SAGEMAKER_INSTANCE", "ml.g5.2xlarge")
SAGEMAKER_ROLE = os.getenv("SAGEMAKER_ROLE", "").strip()
HF_MODEL_ID = os.getenv("HF_MODEL_ID", "stabilityai/stable-diffusion-xl-base-1.0")


def get_execution_role():
    """Get SageMaker execution role ARN."""
    # 1. Explicit env var (best - use your IAM role ARN)
    if SAGEMAKER_ROLE:
        return SAGEMAKER_ROLE
    # 2. sagemaker.get_execution_role() - works on EC2/ECS/Lambda with instance profile
    try:
        import sagemaker  # type: ignore[reportMissingImports]
        return sagemaker.get_execution_role()  # type: ignore[reportAttributeAccessIssue]
    except Exception:
        pass
    # 3. Fallback: find role with SageMaker in name
    client = boto3.client("iam", region_name=AWS_REGION)
    for r in client.list_roles().get("Roles", []):
        name = r.get("RoleName", "")
        if "SageMaker" in name or "sagemaker" in name.lower():
            return r["Arn"]
    raise ValueError(
        "No SageMaker execution role. Set SAGEMAKER_ROLE env var with your IAM role ARN.\n"
        "Example: $env:SAGEMAKER_ROLE=\"arn:aws:iam::YOUR_ACCOUNT:role/YourSageMakerRole\"\n"
        "Create role: IAM Console → Roles → Create role → SageMaker → AmazonSageMakerFullAccess"
    )


def _endpoint_status(sm_client):
    """Get endpoint status if it exists."""
    try:
        r = sm_client.describe_endpoint(EndpointName=ENDPOINT_NAME)
        return r.get("EndpointStatus")
    except ClientError as e:
        if e.response["Error"]["Code"] == "ValidationException":
            return None
        raise


def deploy():
    """Deploy HuggingFace SDXL model to SageMaker."""
    role = get_execution_role()
    sm = boto3.client("sagemaker", region_name=AWS_REGION)
    status = _endpoint_status(sm)
    if status == "InService":
        print(f"Endpoint already deployed: {ENDPOINT_NAME}")
        return ENDPOINT_NAME

    print(f"Using role: {role}")
    print(f"Endpoint: {ENDPOINT_NAME}, Instance: {INSTANCE_TYPE}")

    hf_token = os.getenv("HUGGINGFACE_TOKEN") or os.getenv("HF_TOKEN", "")
    hub = {
        "HF_MODEL_ID": HF_MODEL_ID,
        "HF_TASK": "text-to-image",
    }
    if hf_token:
        hub["HUGGING_FACE_HUB_TOKEN"] = hf_token

    model = HuggingFaceModel(
        env=hub,
        role=role,
        transformers_version="4.37.0",
        pytorch_version="2.1.0",
        py_version="py310",
    )

    try:
        predictor = model.deploy(
            initial_instance_count=1,
            instance_type=INSTANCE_TYPE,
            endpoint_name=ENDPOINT_NAME,
        )
    except ClientError as e:
        err = e.response.get("Error", {})
        if err.get("Code") == "ValidationException" and "already existing endpoint configuration" in str(err.get("Message", "")):
            # Config exists (e.g. from failed previous deploy) - create endpoint using it
            try:
                sm.create_endpoint(
                    EndpointName=ENDPOINT_NAME,
                    EndpointConfigName=ENDPOINT_NAME,
                )
                print("Endpoint created from existing config. Waiting for InService...")
                sm.get_waiter("endpoint_in_service").wait(EndpointName=ENDPOINT_NAME)
                print(f"Deployed: {ENDPOINT_NAME}")
                return ENDPOINT_NAME
            except ClientError as ce:
                if ce.response.get("Error", {}).get("Code") == "ValidationException":
                    msg = ce.response.get("Error", {}).get("Message", "")
                    if "already exists" in msg.lower():
                        print(f"Endpoint already exists: {ENDPOINT_NAME}")
                        return ENDPOINT_NAME
                raise
        raise

    print(f"Deployed: {predictor.endpoint_name}")
    return predictor.endpoint_name


if __name__ == "__main__":
    deploy()
