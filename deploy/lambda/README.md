# Lambda Orchestrator & API Gateway (Task 11)

Serverless API layer that receives user requests, selects the right SageMaker tier, invokes the endpoint, and returns results with job tracking.

## Architecture

```
User (Web/Mobile)
    |
API Gateway (REST)
    |
Lambda Orchestrator
    |-- Analyzes prompt complexity
    |-- Selects tier (STANDARD / PREMIUM / PERFECT)
    |-- Invokes SageMaker endpoint
    |-- Saves image to S3, metadata to DynamoDB
    |
DynamoDB (photogenius-jobs)   S3 (photogenius-images)
```

## Prerequisites

- **Task 10 done:** SageMaker endpoints deployed (`photogenius-standard-endpoint`, `photogenius-premium-endpoint`, `photogenius-perfect-endpoint`).
- **AWS CLI** and **SAM CLI** installed, credentials configured.
- **Python 3.11** (for local testing).

## Environment Variables (Lambda)

| Variable            | Description                    | Default                         |
| ------------------- | ------------------------------ | ------------------------------- |
| `JOBS_TABLE`        | DynamoDB table name for jobs   | `photogenius-jobs`              |
| `IMAGES_BUCKET`     | S3 bucket for generated images | `photogenius-images`            |
| `STANDARD_ENDPOINT` | SageMaker STANDARD tier        | `photogenius-standard-endpoint` |
| `PREMIUM_ENDPOINT`  | SageMaker PREMIUM tier         | `photogenius-premium-endpoint`  |
| `PERFECT_ENDPOINT`  | SageMaker PERFECT tier         | `photogenius-perfect-endpoint`  |

## API

- **POST /generate**  
  Body: `{ "prompt": "...", "tier": "auto"|"standard"|"premium"|"perfect", "environment": "normal"|"rainy"|"fantasy", "seed": 42 }`  
  Returns: `202` with `job_id`, `status`, `tier`, `estimated_time_seconds`, `check_status_url`.

- **GET /status/{job_id}**  
  Returns: `job_id`, `status`, `tier`, `prompt`, `elapsed_time`, and (if completed) `result_url` / `image_url`, or (if failed) `error`.

- **GET /result/{job_id}**  
  Returns: `image_url` (presigned S3 URL), `metadata`. Add `?include_base64=true` to include `image_base64`.

## Deployment

### Option A: SAM (recommended)

From this directory (`deploy/lambda`):

```bash
sam build
sam deploy --guided
```

On first deploy, `--guided` will prompt for stack name, region, and parameter overrides. After deploy, use the printed **ApiUrl**.

### Option B: CloudFormation (native YAML)

The stack creates S3 bucket (with 30-day lifecycle), DynamoDB jobs table (with TTL), Lambda role, Lambda function, and API Gateway HTTP API.

```bash
cd deploy/lambda

# Deploy with placeholder Lambda code (then update code)
aws cloudformation deploy \
  --template-file cloudformation.yaml \
  --stack-name photogenius-orchestrator \
  --capabilities CAPABILITY_NAMED_IAM

# Upload real orchestrator code and update the function
zip orchestrator.zip orchestrator.py
aws lambda update-function-code \
  --function-name photogenius-orchestrator \
  --zip-file fileb://orchestrator.zip
```

**With Lambda code in S3 (no placeholder step):**

```bash
zip orchestrator.zip orchestrator.py
aws s3 cp orchestrator.zip s3://YOUR_DEPLOY_BUCKET/photogenius-orchestrator.zip
aws cloudformation deploy \
  --template-file cloudformation.yaml \
  --stack-name photogenius-orchestrator \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides CodeS3Bucket=YOUR_DEPLOY_BUCKET CodeS3Key=photogenius-orchestrator.zip
```

**Parameters:** `StandardEndpoint`, `PremiumEndpoint`, `PerfectEndpoint` (defaults match Task 10). Optional: `CodeS3Bucket`, `CodeS3Key` for Lambda zip.

**Outputs:** `ApiEndpoint`, `ImagesBucketName`, `JobsTableName`, `LambdaFunctionName`.

**One-command deploy (bash):**

```bash
chmod +x deploy.sh
./deploy.sh                    # stack name: photogenius-api, region: us-east-1
./deploy.sh my-stack us-west-2 # custom stack name and region
```

The script packages `orchestrator.py`, deploys the CloudFormation stack, updates the Lambda code, prints the API endpoint, and removes the zip.

## Manual Deployment (Lambda + API Gateway)

1. **Create DynamoDB table**  
   Name: `photogenius-jobs`, partition key: `job_id` (String), billing: on-demand.

2. **Create S3 bucket**  
   e.g. `photogenius-images-<env>` (or reuse existing).

3. **Create Lambda function**
   - Runtime: Python 3.11
   - Handler: `orchestrator.lambda_handler`
   - Code: zip contents of `deploy/lambda/` (at least `orchestrator.py`).
   - Env: set `JOBS_TABLE`, `IMAGES_BUCKET`, `STANDARD_ENDPOINT`, `PREMIUM_ENDPOINT`, `PERFECT_ENDPOINT`.
   - IAM: allow DynamoDB (GetItem, PutItem, UpdateItem), S3 (PutObject, GetObject), SageMaker (InvokeEndpoint).

4. **Create API Gateway**
   - REST API, CORS enabled.
   - POST `/generate` -> Lambda.
   - GET `/status/{job_id}` -> Lambda (path parameter `job_id`).
   - GET `/result/{job_id}` -> Lambda.
   - OPTIONS for each path for CORS.

## Testing

**Option 1: Test client (Python)**

```bash
# Replace with your API endpoint from deploy output
python test_api.py https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com/prod
python test_api.py https://YOUR_API_ID.../prod "Person in rain"
```

Requires `requests`; optional `Pillow` for saving as PNG. The client creates a job, polls until complete, then saves `api_test_output.png`.

**Option 2: curl**

```bash
# Create job (replace API_BASE with your ApiUrl)
curl -X POST "$API_BASE/generate" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Person in sunlight", "tier": "auto"}'

# Response: {"job_id": "abc123...", "status": "processing", "tier": "STANDARD", ...}

# Check status
curl "$API_BASE/status/abc123..."

# Get result (after status is completed)
curl "$API_BASE/result/abc123..."
```

## Tier Selection (auto)

- **STANDARD:** Simple prompts (e.g. one person, no weather).
- **PREMIUM:** Medium (2–3 people, weather, or some complexity).
- **PERFECT:** Complex (4+ people, fantasy, detailed scenes).

Override with `"tier": "standard"|"premium"|"perfect"` in the request body.

---

## Task 11 completion checklist

- [ ] orchestrator.py – Lambda function code
- [ ] cloudformation.yaml – Infrastructure as Code
- [ ] deploy.sh – Deployment script
- [ ] test_api.py – API test client
- [ ] DynamoDB table created (photogenius-jobs)
- [ ] S3 bucket created (photogenius-images-\*)
- [ ] API Gateway deployed (HTTP API)
- [ ] Lambda function deployed (photogenius-orchestrator)
- [ ] Endpoints tested successfully

**When you're done with Task 11**, reply with:

```
TASK 11 COMPLETE
- Lambda deployed: Y/N
- API Gateway working: Y/N
- DynamoDB created: Y/N
- S3 bucket created: Y/N
- Test successful: Y/N
- API endpoint: [URL]
```

## Files

- `orchestrator.py` – Lambda handler (routing, tier selection, SageMaker invoke, DynamoDB, S3).
- `template.yaml` – SAM template (Lambda, API Gateway, DynamoDB table, S3 bucket, IAM).
- `cloudformation.yaml` – CloudFormation template (same resources; S3 lifecycle 30-day, DynamoDB TTL, HTTP API routes including OPTIONS).
- `deploy.sh` – One-command deploy: package Lambda, deploy stack, update function code, print API endpoint (bash; run `chmod +x deploy.sh` first on Unix).
- `test_api.py` – Test client: `PhotoGeniusClient(api_endpoint).generate(prompt)`; CLI `python test_api.py <API_ENDPOINT> [prompt]`.
