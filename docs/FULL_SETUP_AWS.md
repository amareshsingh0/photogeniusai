# PhotoGenius AI – Full AWS Setup

This guide uses values from your **.env.local** files to deploy SageMaker, Lambda, and optionally download models.

## Required values (from .env.local)

### aws/sagemaker/.env.local (SageMaker deploy)

| Variable            | Required    | Description                                                                                                         |
| ------------------- | ----------- | ------------------------------------------------------------------------------------------------------------------- |
| `SAGEMAKER_ROLE`    | **Yes**     | IAM role ARN for SageMaker (e.g. `arn:aws:iam::ACCOUNT:role/SageMakerExecutionRole`)                                |
| `SAGEMAKER_BUCKET`  | Recommended | S3 bucket for model artifact (e.g. `photogenius-models-dev`). If empty, defaults to `photogenius-sagemaker-ACCOUNT` |
| `AWS_REGION`        | Optional    | AWS region (default `us-east-1`)                                                                                    |
| `HUGGINGFACE_TOKEN` | Optional    | For gated HuggingFace models (used by download scripts and some pipelines)                                          |

### apps/api/.env.local (API / Lambda URLs after deploy)

After Lambda deploy, set:

| Variable                      | Description                                                                                        |
| ----------------------------- | -------------------------------------------------------------------------------------------------- |
| `AWS_LAMBDA_GENERATION_URL`   | Full URL to Lambda generate (e.g. `https://xxx.execute-api.us-east-1.amazonaws.com/prod/generate`) |
| `SAGEMAKER_ENDPOINT_TWO_PASS` | SageMaker PREMIUM endpoint name: `photogenius-two-pass`                                            |
| `S3_BUCKET`                   | Images bucket from CloudFormation output: `photogenius-images-ACCOUNT`                             |

### apps/web/.env.local (frontend)

| Variable              | Description                                                                |
| --------------------- | -------------------------------------------------------------------------- |
| `AWS_API_GATEWAY_URL` | Base API URL (e.g. `https://xxx.execute-api.us-east-1.amazonaws.com/prod`) |
| `CLOUD_PROVIDER`      | `aws`                                                                      |

## One-command full setup (Windows PowerShell)

From repo root, with **aws/sagemaker/.env.local** containing at least `SAGEMAKER_ROLE` and optionally `SAGEMAKER_BUCKET`, `AWS_REGION`:

```powershell
.\scripts\full-setup-aws.ps1
```

This will:

1. Load `aws/sagemaker/.env.local` and `apps/api/.env.local` into the environment.
2. Install deploy dependencies (`boto3`, `PyYAML`).
3. **Package** the SageMaker model (`deploy/sagemaker/package_model.py`).
4. **Upload** the package to S3 and **deploy** SageMaker endpoints (STANDARD, PREMIUM, PERFECT) via `deploy/sagemaker/upload_and_deploy.py`.
5. **Deploy Lambda** + API Gateway via `deploy/lambda/deploy.ps1` (endpoint names: `photogenius-standard`, `photogenius-two-pass`, `photogenius-perfect`).
6. **Download** AI models (SDXL, InstantID, etc.) into `ai-pipeline/models/cache` for local/EFS use (optional; SageMaker uses the packaged code).

### Options

```powershell
.\scripts\full-setup-aws.ps1 -SkipSageMaker   # Only Lambda + downloads
.\scripts\full-setup-aws.ps1 -SkipLambda      # Only SageMaker + downloads
.\scripts\full-setup-aws.ps1 -SkipDownloads   # No model downloads (faster)
.\scripts\full-setup-aws.ps1 -DryRun          # Print steps only, no deploy
```

## Manual steps (if you prefer)

### 1. Set environment from .env.local

**Windows (PowerShell):**

```powershell
Get-Content aws\sagemaker\.env.local | ForEach-Object {
  if ($_ -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$' -and $_ -notmatch '^\s*#') {
    $key = $matches[1]; $val = $matches[2].Trim().Trim('"')
    [Environment]::SetEnvironmentVariable($key, $val, "Process")
  }
}
```

**Bash:**

```bash
set -a
source aws/sagemaker/.env.local 2>/dev/null || true
set +a
```

### 2. Deploy SageMaker

```powershell
pip install -r deploy/requirements.txt
python deploy/sagemaker/package_model.py
python deploy/sagemaker/upload_and_deploy.py
```

### 3. Deploy Lambda

**Windows:**

```powershell
.\deploy\lambda\deploy.ps1 -Region us-east-1
```

**Linux/macOS:**

```bash
./deploy/lambda/deploy.sh photogenius-api us-east-1
```

### 4. Download models (optional)

For local or EFS model cache (HUGGINGFACE_TOKEN in env if needed):

```powershell
$env:MODEL_DIR = ".\ai-pipeline\models\cache"
cd ai-pipeline
python models\download_models.py
python models\download_instantid.py
cd ..
```

## After deploy

1. **Get API Gateway URL**

   ```bash
   aws cloudformation describe-stacks --stack-name photogenius-api --region us-east-1 --query "Stacks[0].Outputs"
   ```

   Use `ApiEndpoint` (e.g. `https://xxx.execute-api.us-east-1.amazonaws.com/prod`).

2. **Update apps/api/.env.local**
   - `AWS_LAMBDA_GENERATION_URL=<ApiEndpoint>/generate`
   - `S3_BUCKET=photogenius-images-<ACCOUNT>` (from CloudFormation output `ImagesBucketName`)

3. **Update apps/web/.env.local**
   - `AWS_API_GATEWAY_URL=<ApiEndpoint>`

4. **Test generation**
   ```bash
   curl -X POST "<ApiEndpoint>/generate" -H "Content-Type: application/json" -d "{\"prompt\": \"Person in sunlight\"}"
   ```

## Endpoint names (must match)

| Tier     | SageMaker endpoint name | Lambda env var      |
| -------- | ----------------------- | ------------------- |
| STANDARD | `photogenius-standard`  | `STANDARD_ENDPOINT` |
| PREMIUM  | `photogenius-two-pass`  | `PREMIUM_ENDPOINT`  |
| PERFECT  | `photogenius-perfect`   | `PERFECT_ENDPOINT`  |

These are set in `deploy/endpoint_config.yaml` and in `deploy/lambda/cloudformation.yaml` (and deploy.ps1 / deploy.sh).

## E2E flow and interconnections

| Step | From                   | To                                                         | What                                                                                                                                                                       |
| ---- | ---------------------- | ---------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1    | **Web** (Next.js)      | **Web API route** `/api/generate` or `/api/generate/smart` | User submits prompt; route uses `AWS_API_GATEWAY_URL` + `/generate` for two-pass.                                                                                          |
| 2    | **Web API route**      | **API Gateway** `POST /generate`                           | Request body: `{ prompt, tier, quality_tier?, environment, seed? }`.                                                                                                       |
| 3    | **API Gateway**        | **Lambda** `orchestrator.lambda_handler`                   | Lambda selects SageMaker tier, creates job in DynamoDB, invokes SageMaker.                                                                                                 |
| 4    | **Lambda**             | **SageMaker** endpoint (e.g. `photogenius-two-pass`)       | `invoke_endpoint` with `{ prompt, environment, seed }`.                                                                                                                    |
| 5    | **SageMaker**          | **ai-pipeline** (packaged)                                 | `inference.py` uses `services.self_improvement_engine` + `iterative_refinement_engine`; returns base64 image + metadata.                                                   |
| 6    | **Lambda**             | **S3** (images bucket)                                     | Stores decoded image; updates DynamoDB job to `completed`.                                                                                                                 |
| 7    | **Lambda**             | **API Gateway** → **Web**                                  | Returns 200 with `{ job_id, image_url, image_base64, metadata, images: [{ url, base64 }] }`.                                                                               |
| 8    | **FastAPI (apps/api)** | **Lambda** (optional)                                      | When `AWS_LAMBDA_GENERATION_URL` is set, `aws_gpu_client._generate_via_lambda()` POSTs to same `/generate`; expects 200 with `body.images` (normalized to `image_base64`). |

- **Database**: Web and API use Prisma + PostgreSQL (Supabase) for users, generations, identities.
- **Redis**: API uses Redis (e.g. Upstash) for rate limiting/cache when configured.

## Step-by-step verification checklist

Use this to confirm nothing is missing:

1. **Env files**
   - [ ] `aws/sagemaker/.env.local` has `SAGEMAKER_ROLE`, optionally `SAGEMAKER_BUCKET`, `AWS_REGION`, `HUGGINGFACE_TOKEN`
   - [ ] `apps/api/.env.local` has `DATABASE_URL`, and after deploy: `AWS_LAMBDA_GENERATION_URL`, `S3_BUCKET`
   - [ ] `apps/web/.env.local` has `DATABASE_URL`, Clerk keys, and after deploy: `AWS_API_GATEWAY_URL`
   - [ ] `packages/database/.env` has `DATABASE_URL` for Prisma

2. **Repo deps**
   - [ ] `pnpm install` (root)
   - [ ] `pnpm run db:generate` (Prisma client)
   - [ ] `pip install -r deploy/requirements.txt` (boto3, PyYAML for deploy)
   - [ ] Optional: `pip install -r ai-pipeline/requirements.txt` (for local AI / downloads)

3. **SageMaker**
   - [ ] `python deploy/sagemaker/package_model.py` (creates `deploy/sagemaker/artifacts/model.tar.gz`)
   - [ ] `python deploy/sagemaker/upload_and_deploy.py` (upload S3 + create/update endpoints; requires AWS CLI + role)

4. **Lambda**
   - [ ] `.\deploy\lambda\deploy.ps1` (Windows) or `./deploy/lambda/deploy.sh` (Linux/macOS)
   - [ ] CloudFormation stack `photogenius-api` created; Lambda env has `STANDARD_ENDPOINT`, `PREMIUM_ENDPOINT`, `PERFECT_ENDPOINT` matching SageMaker endpoint names

5. **Post-deploy**
   - [ ] Set `AWS_LAMBDA_GENERATION_URL` and `S3_BUCKET` in `apps/api/.env.local`
   - [ ] Set `AWS_API_GATEWAY_URL` in `apps/web/.env.local`
   - [ ] Test: `curl -X POST "<ApiEndpoint>/generate" -H "Content-Type: application/json" -d "{\"prompt\": \"Person in sunlight\"}"`

6. **Optional: model downloads (local/EFS)**
   - [ ] `$env:MODEL_DIR = ".\ai-pipeline\models\cache"; cd ai-pipeline; python models\download_models.py; python models\download_instantid.py`

7. **Full verification script**
   - [ ] `.\scripts\verify-setup.ps1` (Node, pnpm, Python, deps, Prisma, .env)

## SageMaker endpoints – already running

Your SageMaker endpoints are **always on** once deployed; there is no separate "start" step. To confirm they are up:

```bash
aws sagemaker list-endpoints --region us-east-1 --query "Endpoints[*].{Name:EndpointName,Status:EndpointStatus}" --output table
```

You should see **InService** for `photogenius-standard` and `photogenius-two-pass`. Image generation on the website uses these via Lambda.

## Generate images on your website

1. **Ensure env is set** (already in `apps/web/.env.local`):
   - `CLOUD_PROVIDER=aws`
   - `AWS_API_GATEWAY_URL=https://adwvprgwzi.execute-api.us-east-1.amazonaws.com/prod`

2. **Start the web app** (from repo root):

   ```bash
   pnpm run dev
   ```

   Or run only the web app: `pnpm --filter web dev`.

3. **Open** [http://localhost:3000](http://localhost:3000), sign in (Clerk), go to **Generate**, enter a prompt and choose a quality tier (e.g. STANDARD or PREMIUM). The app calls Lambda → SageMaker and shows the generated image.

4. **If generation fails**: Check the browser console and Network tab; ensure you're signed in and that `AWS_API_GATEWAY_URL` is set (no trailing slash). Test the API directly:
   ```bash
   curl -X POST "https://adwvprgwzi.execute-api.us-east-1.amazonaws.com/prod/generate" -H "Content-Type: application/json" -d "{\"prompt\": \"Person in sunlight\"}"
   ```

## Deployed state (after running setup)

- **SageMaker**: `photogenius-standard` (ml.g5.xlarge), `photogenius-two-pass` (ml.g5.2xlarge) are deployed. `photogenius-perfect` requires a quota increase for additional instances (see Troubleshooting).
- **Lambda**: Stack `photogenius-api`; API base `https://adwvprgwzi.execute-api.us-east-1.amazonaws.com/prod` (or your region’s URL from deploy output).
- **apps/api/.env.local**: `AWS_LAMBDA_GENERATION_URL`, `S3_BUCKET` set from deploy.
- **apps/web/.env.local**: `AWS_API_GATEWAY_URL` set from deploy.

## Troubleshooting

- **SAGEMAKER_ROLE**: Create in IAM a role for SageMaker with access to S3 and ECR (and any VPC if needed). Use its ARN in `aws/sagemaker/.env.local`.
- **Lambda "ResourceNotFoundException" for SageMaker**: Deploy SageMaker first so endpoints exist; then deploy or update Lambda.
- **SageMaker ResourceLimitExceeded**: Request a quota increase in AWS Service Quotas for the instance type (e.g. ml.g5.xlarge, ml.g5.2xlarge). With default quotas (e.g. 1 per type), only STANDARD and PREMIUM may deploy; PERFECT can be added after increasing quota or by reusing an existing instance type in `deploy/endpoint_config.yaml`.
- **Model downloads fail**: Set `HUGGINGFACE_TOKEN` in `aws/sagemaker/.env.local` (or export before running). Some models require an accepted Hugging Face license.
- **Web two-pass returns 502**: Ensure `AWS_API_GATEWAY_URL` is the base URL (e.g. `https://xxx.execute-api.us-east-1.amazonaws.com/prod`); the app appends `/generate`.
