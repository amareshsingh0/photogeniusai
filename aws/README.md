# PhotoGenius AWS – SAM & Orchestrator

**SAM and Orchestrator infra live here** (`aws/`). The template is `template.yaml` (not in repo root).

## Flow

```
Client (curl / website)
   → API Gateway
   → Lambda (Orchestrator v1 @ /orchestrate, Orchestrator v2 @ /orchestrate/v2)
   → SageMaker Endpoint (photogenius-standard, photogenius-two-pass)
   → S3 image URL / base64
```

## Build & Deploy (from repo root or from aws/)

**From repo root (recommended):**

- Windows: `.\scripts\sam.ps1 build` then `.\scripts\sam.ps1 deploy --guided`
- Linux/macOS: `./scripts/sam.sh build` then `./scripts/sam.sh deploy --guided`

**From aws/ folder:**

```bash
cd aws
sam build
sam deploy --guided
```

**After changing Lambda code** (e.g. fixing `handler.py`), redeploy so AWS runs the new code:

```powershell
cd aws
sam build
sam deploy
```

**Guided deploy answers:**

- Stack Name: `photogenius` (or `photogenius-orchestrator` if you prefer)
- Region: `us-east-1`
- Confirm changes: Y
- Allow SAM to create IAM roles: Y
- Save config: Y

## Stack & Outputs

- **Stack name:** `photogenius` (from `samconfig.toml`: `stack_name = "photogenius"`)
- **Orchestrator v1:** `POST .../Prod/orchestrate` (quality_tier: FAST | STANDARD | PREMIUM)
- **Orchestrator v2:** `POST .../Prod/orchestrate/v2` (smart routing, tier detection, direct SageMaker fallback)

After deploy, get the API URL:

```bash
# From repo root
.\scripts\sam.ps1 list endpoints --stack-name photogenius

# Or from aws/
sam list endpoints --stack-name photogenius
```

Outputs in CloudFormation (or `sam list endpoints`) include:

- **OrchestrateUrl** – `/orchestrate`
- **OrchestrateV2Url** – `/orchestrate/v2`

## First real image (GPU)

**PowerShell:** Use a single line or a variable so the JSON is not split (line continuation with backticks can break the `-d` string).

```powershell
# Single line (recommended)
$body = '{"prompt":"cinematic portrait, ultra realistic, studio lighting","steps":30}'
curl.exe -X POST "https://YOUR_API_URL/Prod/orchestrate/v2" -H "Content-Type: application/json" -d $body
```

Or one line without variable:

```powershell
curl.exe -X POST "https://YOUR_API_URL/Prod/orchestrate/v2" -H "Content-Type: application/json" -d "{\"prompt\":\"cinematic portrait, studio lighting\",\"steps\":30}"
```

**Bash / Linux:**

```bash
curl -X POST "https://YOUR_API_URL/Prod/orchestrate/v2" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"cinematic portrait, studio lighting","steps":30}'
```

Response: `images.preview`, `images.final` (base64), `metadata.quality_tier`, etc.

## Orchestrator v2 behavior

1. **In-package v1:** If v1 handler is in the same package, use it.
2. **Invoke v1 Lambda:** Else invoke `photogenius-orchestrator-${Environment}` by name.
3. **Direct SageMaker:** If v1 is unavailable or fails, v2 calls SageMaker directly:
   - **STANDARD** → `photogenius-standard` (single-pass)
   - **PREMIUM/FAST** → `photogenius-two-pass` (preview + final)

So **v2 works even when v1 is not deployed** (minimal production-ready setup).

## SageMaker endpoints

Deploy SageMaker separately (see repo root `deploy/`):

- `photogenius-standard` – single-pass (ml.g5.xlarge)
- `photogenius-two-pass` – two-pass (ml.g5.2xlarge)

Parameter overrides in `samconfig.toml`:

- `SageMakerEndpoint`: `photogenius-generation-dev` (or `photogenius-standard` after deploy)
- `SageMakerTwoPassEndpoint`: `photogenius-two-pass-dev` (or `photogenius-two-pass`)
