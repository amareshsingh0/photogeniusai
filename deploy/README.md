# PhotoGenius AI – Deploy (SageMaker multi-tier)

P0: Production deployment with auto-scaling and CloudWatch.

## Full setup (SageMaker + Lambda + optional downloads)

From repo root, with **aws/sagemaker/.env.local** containing `SAGEMAKER_ROLE` and optionally `SAGEMAKER_BUCKET`, `AWS_REGION`:

```powershell
.\scripts\full-setup-aws.ps1
```

Options: `-SkipSageMaker`, `-SkipLambda`, `-SkipDownloads`, `-DryRun`. See **docs/FULL_SETUP_AWS.md** for required .env values and manual steps.

## Files

- **sagemaker_deployment.py** – Deploy multi-tier SageMaker endpoints (STANDARD, PREMIUM, PERFECT), auto-scaling 1–10 instances, CloudWatch latency alarms.
- **endpoint_config.yaml** – Tier config: endpoint names, instance types, min/max capacity, latency targets, CloudWatch thresholds.

## Success metrics

- **&lt;5s latency** for STANDARD tier.
- **&lt;30s latency** for PERFECT tier.

## Dependencies

Install required packages (use the same Python you run the script with):

```bash
pip install -r deploy/requirements.txt
```

Or: `pip install boto3 PyYAML`. If you use a venv, activate it first; if activation fails with "Permission denied", run without the venv or delete `.venv` and recreate it.

## Usage

1. For real deploy, set **SAGEMAKER_ROLE** (IAM role ARN for SageMaker). Dry-run does not need it.
2. Optionally set **MODEL_S3_URI** to use an existing model tarball; otherwise code is packaged from `aws/sagemaker/model/code`.
3. Run:

```bash
# From repo root
python deploy/sagemaker_deployment.py --tier all

# Single tier
python deploy/sagemaker_deployment.py --tier STANDARD

# Dry run (no deploy)
python deploy/sagemaker_deployment.py --tier all --dry-run
```

## Tiers (endpoint_config.yaml)

| Tier     | Endpoint name        | Instance      | Auto-scale | Latency target |
| -------- | -------------------- | ------------- | ---------- | -------------- |
| STANDARD | photogenius-standard | ml.g5.xlarge  | 1–10       | 5s             |
| PREMIUM  | photogenius-two-pass | ml.g5.2xlarge | 1–10       | 20s            |
| PERFECT  | photogenius-perfect  | ml.g5.2xlarge | 1–10       | 30s            |

CloudWatch alarms are created for each tier’s latency threshold.

## SAM (Lambda / API) from project root

The SAM template lives in `aws/template.yaml`. From the repo root use:

- **Windows:** `.\scripts\sam.ps1 build` | `.\scripts\sam.ps1 deploy` | `.\scripts\sam.ps1 list endpoints`
- **Linux/macOS:** `./scripts/sam.sh build` | `./scripts/sam.sh deploy` | `./scripts/sam.sh list endpoints`

Or run `sam` from the `aws/` directory so the template is found.
