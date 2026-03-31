# AWS Scripts (no Modal)

Scripts for AWS-only setup. No Modal dependency.

## SageMaker endpoints

**List endpoints:** See which endpoints exist in your account (so you don't try to delete a name that doesn't exist).

```powershell
.\list-sagemaker-endpoints.ps1
# or: .\list-sagemaker-endpoints.ps1 -Region us-east-1
```

**Delete an endpoint:** Only works if the endpoint exists. Names from `deploy/sagemaker_deployment.py` are typically `photogenius-standard`, `photogenius-two-pass`, `photogenius-perfect`. The dev name `photogenius-generation-dev` may not exist if you never created it.

```powershell
.\delete-sagemaker-endpoint.ps1 -EndpointName "photogenius-standard"
```

If you see _Could not find endpoint "photogenius-generation-dev"_, that endpoint simply doesn't exist—list endpoints above and delete by the name that exists, or ignore if you were just cleaning up.

### One command: delete all / start all

**Delete all PhotoGenius SageMaker endpoints** (only `photogenius-*` names):

```powershell
# Windows (from aws/scripts)
.\delete-all-sagemaker.ps1
.\delete-all-sagemaker.ps1 -Force   # skip confirmation
```

```bash
# Linux/macOS
./delete-all-sagemaker.sh
./delete-all-sagemaker.sh us-east-1
```

**Start (deploy) all tiers** (STANDARD, PREMIUM, PERFECT) in one command:

```powershell
# Windows (from aws/scripts or repo root)
.\start-all-sagemaker.ps1
```

```bash
# Linux/macOS
./start-all-sagemaker.sh
./start-all-sagemaker.sh us-east-1
```

Start script uses `SAGEMAKER_ROLE` from `aws/sagemaker/.env.local` if present. Run from repo root or from `aws/scripts`.

## download_models.py

Downloads all models required for PhotoGenius on AWS (SageMaker, EC2, EFS).  
**Total storage: ~25GB.**  
**Estimated time: 30–60 minutes.**

### Models

| Model                 | Size   | Path under MODEL_DIR                   |
| --------------------- | ------ | -------------------------------------- |
| SDXL Base             | ~6.9GB | stable-diffusion-xl-base-1.0           |
| SDXL Turbo            | ~6.9GB | sdxl-turbo                             |
| SDXL Refiner          | ~6.9GB | stable-diffusion-xl-refiner-1.0        |
| InstantID             | ~500MB | instantid                              |
| InsightFace buffalo_l | ~400MB | insightface                            |
| Sentence Transformer  | ~66MB  | sentence-transformers/all-MiniLM-L6-v2 |

### Setup

```bash
cd aws/scripts
pip install -r requirements.txt
```

Optional: set `HUGGINGFACE_TOKEN` or `HF_TOKEN` for gated/authenticated repos.

### Run

```bash
# Download to ./models (default) or MODEL_DIR
python download_models.py

# Custom directory
python download_models.py --model-dir /data/models

# Or use env
MODEL_DIR=/data/models python download_models.py
```

### Verify

```bash
python download_models.py --verify-only
```

Expected: all lines show ✅ for required paths.

### Sync to S3 (for SageMaker)

After download:

```bash
python download_models.py --model-dir ./models --s3-bucket YOUR_BUCKET --s3-prefix models/
```

Or manually:

```bash
aws s3 sync ./models s3://YOUR_BUCKET/models/
```

### Execution summary

1. Run: `python download_models.py` (or with `--model-dir`)
2. Wait for all downloads (30–60 minutes)
3. Run: `python download_models.py --verify-only`
4. Confirm all ✅
5. Optionally sync to S3 for SageMaker
