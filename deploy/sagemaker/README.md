# AWS SageMaker Deployment – PhotoGenius AI

Deploy PhotoGenius AI to AWS SageMaker with **multi-tier endpoints**, **auto-scaling**, and **CloudWatch monitoring**.

## Architecture

```
User Request
    ↓
API Gateway / Lambda (or direct invoke)
    ↓
SageMaker Endpoint (auto-scaling)
    ├── STANDARD (ml.g5.xlarge)  – Fast, ~85% quality
    ├── PREMIUM  (ml.g5.2xlarge) – Balanced, ~90% quality
    └── PERFECT  (ml.g5.4xlarge) – Best, ~99% quality
    ↓
S3 (image storage, optional)
    ↓
Response to User
```

## Prerequisites

- **Tasks 1–9** from the implementation plan (orchestrator, safety, APIs, etc.) done
- **AWS CLI** configured (`aws configure`)
- **Python 3.10+** with `boto3` (and optionally `sagemaker`, `pyyaml`, `Pillow` for saving test images)
- **SageMaker execution role** with access to S3, CloudWatch, and SageMaker

---

## Deployment Steps (What You'll Run)

Run these from the project root or from `deploy/sagemaker`:

```bash
# Step 1: Package the model
cd deploy/sagemaker
python package_model.py

# Step 2: Deploy to SageMaker (requires AWS credentials & IAM role)
python deploy_to_sagemaker.py \
  --model-path artifacts/model.tar.gz \
  --role-arn arn:aws:iam::YOUR_ACCOUNT:role/SageMakerRole \
  --region us-east-1

# Step 3: Test endpoint(s) – defaults to all tiers
python test_endpoint.py
```

Or from repo root:

```bash
python deploy/sagemaker/package_model.py
python deploy/sagemaker/deploy_to_sagemaker.py --model-path deploy/sagemaker/artifacts/model.tar.gz --role-arn arn:aws:iam::YOUR_ACCOUNT:role/SageMakerRole --region us-east-1
python deploy/sagemaker/test_endpoint.py
```

---

## Notes for Deployment

1. **AWS setup required**
   - AWS account with SageMaker access
   - IAM role with SageMaker full access, S3, and CloudWatch Logs
   - S3 bucket (script can create `photogenius-ai-models` or use `SAGEMAKER_BUCKET`)
   - EC2 GPU instance quotas for `ml.g5.xlarge` / `ml.g5.2xlarge` / `ml.g5.4xlarge`

2. **Cost estimate (on-demand, approximate)**
   - STANDARD tier: ~$1/hour
   - PREMIUM tier: ~$1.20/hour
   - PERFECT tier: ~$1.60/hour
   - All three running: ~$3.80/hour

3. **Recommended start**
   - Deploy **STANDARD tier only** first (e.g. deploy one endpoint manually or use a single-tier flow)
   - Test thoroughly with `test_endpoint.py --endpoint photogenius-standard-endpoint`
   - Add PREMIUM/PERFECT after validation

---

## Step 1: Model Packaging (detail)

Bundle services, inference script, and config into `model.tar.gz`:

```bash
# From repo root
python deploy/sagemaker/package_model.py
```

Output: `deploy/sagemaker/artifacts/model.tar.gz` (and `config.json` inside the package).

- Copies `ai-pipeline/services` into the package
- Writes `inference.py` (model_fn, input_fn, predict_fn, output_fn) with tier support
- Adds `requirements.txt` and `config.json` for tiers and scaling

## Step 2: Upload to S3 and Deploy Endpoints

Set the SageMaker role (required) and optional bucket:

```bash
export SAGEMAKER_ROLE="arn:aws:iam::ACCOUNT:role/YourSageMakerRole"
export SAGEMAKER_BUCKET="your-bucket"   # optional; default: photogenius-sagemaker-ACCOUNT
```

**Option A – All-in-one deploy script (recommended for first-time deploy):**

```bash
# Upload artifacts/model.tar.gz to S3 and deploy all tiers (STANDARD, PREMIUM, PERFECT)
python deploy/sagemaker/deploy_to_sagemaker.py --model-path deploy/sagemaker/artifacts/model.tar.gz --role-arn $SAGEMAKER_ROLE

# Or use default artifact path and env role
python deploy/sagemaker/deploy_to_sagemaker.py

# Use existing S3 URL (skip upload)
python deploy/sagemaker/deploy_to_sagemaker.py --s3-url s3://bucket/key/model.tar.gz --role-arn $SAGEMAKER_ROLE
```

**Option B – Upload then turbo deploy (uses endpoint_config.yaml):**

```bash
# Package + upload + deploy all tiers (STANDARD, PREMIUM, PERFECT)
python deploy/sagemaker/upload_and_deploy.py

# Or only one tier
python deploy/sagemaker/upload_and_deploy.py --tier STANDARD

# Dry-run (no upload/deploy)
python deploy/sagemaker/upload_and_deploy.py --dry-run

# Only create/upload package
python deploy/sagemaker/upload_and_deploy.py --package-only

# Only upload to S3 (deploy later with deploy/sagemaker_deployment.py)
python deploy/sagemaker/upload_and_deploy.py --upload-only
```

**Option C – Main deployment script (prefer existing artifact):**

```bash
python deploy/sagemaker/package_model.py
# Then either set MODEL_S3_URI after uploading manually, or let the script upload the artifact:
python deploy/sagemaker_deployment.py --tier all
```

If `deploy/sagemaker/artifacts/model.tar.gz` exists, `sagemaker_deployment.py` will upload it to S3 and use it for all tiers.

## Step 3: Multi-Tier Endpoints

| Tier     | Endpoint Name        | Instance      | Target Latency | Use Case     |
| -------- | -------------------- | ------------- | -------------- | ------------ |
| STANDARD | photogenius-standard | ml.g5.xlarge  | &lt;5s         | Fast preview |
| PREMIUM  | photogenius-two-pass | ml.g5.2xlarge | &lt;20s        | Balanced     |
| PERFECT  | photogenius-perfect  | ml.g5.4xlarge | &lt;30s        | Best quality |

Config: `deploy/endpoint_config.yaml`. Each tier has `model_env.PHOTOGENIUS_TIER` so the inference script can tune iterations and quality.

## Step 4: Auto-Scaling

Handled by `deploy/sagemaker_deployment.py` after each endpoint is created:

- **Min instances:** 1 per tier (configurable in `endpoint_config.yaml`)
- **Max instances:** 10 per tier
- **Metric:** `SageMakerVariantInvocationsPerInstance` (target 1–2 invocations per instance depending on tier)
- **Cooldowns:** scale-out 60–120s, scale-in 300–400s

You can change `scaling.target_invocations_per_instance`, `scale_in_cooldown`, and `scale_out_cooldown` in `deploy/endpoint_config.yaml`.

## Step 5: Monitoring (CloudWatch)

Alarms are created by `deploy/sagemaker_deployment.py` when `deploy/endpoint_config.yaml` has a `cloudwatch` section:

- **Namespace:** `AWS/SageMaker`
- **Metric:** `ModelLatency` per endpoint/variant
- **Thresholds:** e.g. STANDARD &lt;8s, PREMIUM &lt;25s, PERFECT &lt;35s (configurable)
- **Error rate:** optional `error_rate_threshold`

Example config in `endpoint_config.yaml`:

```yaml
cloudwatch:
  alarm_namespace: PhotoGenius/SageMaker
  latency_alarm_threshold_seconds:
    STANDARD: 8
    PREMIUM: 25
    PERFECT: 35
  error_rate_threshold: 0.05
```

## Step 6: Cost Optimization

- **Reserved capacity:** For steady load, use SageMaker **inference component** or **reserved capacity** to reduce cost vs on-demand.
- **Spot instances:** Not used by default; you can switch to spot for non-critical tiers by changing the endpoint config (e.g. production variant to use spot).
- **Right-sizing:** Start with one instance per tier; scale out only if latency or throughput requires it.
- **Shut down when idle:** Set `min_capacity: 0` for optional tiers (e.g. PERFECT) in `endpoint_config.yaml` and scale to zero when not needed (via auto-scaling or scheduled actions).

Approximate on-demand cost per hour (us-east-1):

| Tier     | Instance      | $/hr (approx) |
| -------- | ------------- | ------------- |
| STANDARD | ml.g5.xlarge  | ~1.006        |
| PREMIUM  | ml.g5.2xlarge | ~1.212        |
| PERFECT  | ml.g5.4xlarge | ~1.624        |

## Invoking and Testing Endpoints

**Quick test with the test script:**

```bash
# Test one endpoint (default prompt: "Person standing in sunlight")
python deploy/sagemaker/test_endpoint.py --endpoint photogenius-standard-endpoint

# Test all tiers with a custom prompt
python deploy/sagemaker/test_endpoint.py --all-tiers --prompt "Mother with 3 children under umbrella in rain"

# Custom region and environment; do not save images
python deploy/sagemaker/test_endpoint.py --endpoint photogenius-premium-endpoint --region us-west-2 --environment rainy --no-save
```

Requires `boto3`; `Pillow` is optional (needed to decode and save images). Output images are saved as `test_output_<endpoint_name>.png` unless `--no-save` is used.

**Programmatic invoke:**

```python
import boto3
import json

runtime = boto3.client("sagemaker-runtime")
response = runtime.invoke_endpoint(
    EndpointName="photogenius-standard-endpoint",
    ContentType="application/json",
    Body=json.dumps({
        "prompt": "Mother with 3 children under umbrella in rain",
        "environment": "rainy",
        "seed": 42,
    }),
)
result = json.loads(response["Body"].read())
# result["image"] = base64 PNG, result["metadata"] = { final_score, total_iterations, success, prompt }
```

## File Layout

- `deploy/sagemaker/package_model.py` – Builds `model.tar.gz` (services + inference + config)
- `deploy/sagemaker/deploy_to_sagemaker.py` – **All-in-one:** upload model to S3, create model, endpoint config, endpoints, and auto-scaling (per-tier with `primary` variant)
- `deploy/sagemaker/upload_and_deploy.py` – Upload to S3 and run multi-tier deploy via `sagemaker_deployment.py`
- `deploy/sagemaker/artifacts/model.tar.gz` – Produced by `package_model.py`
- `deploy/endpoint_config.yaml` – Tier definitions, scaling, CloudWatch (used by `sagemaker_deployment.py`)
- `deploy/sagemaker_deployment.py` – Creates endpoints (AllTraffic variant), auto-scaling, and CloudWatch alarms
- `deploy/sagemaker/test_endpoint.py` – Test one or all tiers (invoke endpoint, optional save image)

## Troubleshooting

- **"Can't find inference.py"** – Ensure the tarball root contains `inference.py` (created by `package_model.py`).
- **"ModuleNotFoundError: services"** – Package was built without `ai-pipeline/services` or path is wrong; run `package_model.py` from repo root.
- **Endpoint InService but 500** – Check CloudWatch Logs for the endpoint; inference may fall back to placeholder if heavy deps (e.g. CLIP, diffusion) are missing in the container.
- **SAGEMAKER_ROLE** – IAM role must have `AmazonSageMakerFullAccess`, S3 read/write, and CloudWatch Logs.

---

## When You're Done with Task 10

Reply with your completion status:

```
TASK 10 COMPLETE
- Model packaged: [Y/N]
- Uploaded to S3: [Y/N]
- Endpoint deployed: [Y/N] (which tier?)
- Test successful: [Y/N]
- Issues encountered: [any problems?]
```
