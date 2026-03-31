# ✅ PhotoGenius AWS GPU – End-to-End Setup

```
Website → API Gateway → Lambda → SageMaker GPU → S3 → Website
```

Agar GPU run nahi ho raha, to inme se koi ek step missing hai.

---

## STEP 0 — Prerequisites (Pehle Ye Install Karo)

### Node.js + pnpm (Website ke liye)

Agar `pnpm` not recognized hai:

1. **Node.js** install karo (18+): https://nodejs.org  
2. **pnpm** install:
```powershell
npm install -g pnpm
```
3. **Naya terminal** kholo (ya PATH refresh), check:
```powershell
pnpm --version
```

**Agar ab bhi "pnpm not recognized":** npm ka folder PATH me nahi hai. Ye run karo (ek baar):
```powershell
[Environment]::SetEnvironmentVariable("Path", $env:Path + ";$env:APPDATA\npm", "User")
```
Phir **terminal band karke naya kholo**.

### Python 3.11+ (SageMaker deploy ke liye)

```powershell
python --version
pip install sagemaker boto3
```

### AWS CLI (SageMaker / Lambda ke liye)

Agar `aws` command not recognized hai:

### Windows (PowerShell – MSI)

1. Download: https://awscli.amazonaws.com/AWSCLIV2.msi  
2. Run MSI, follow wizard  
3. **New PowerShell window** kholo (old me nahi chalega)  
4. Check:
```powershell
aws --version
```

### Windows (winget – agar installed hai)

```powershell
winget install Amazon.AWSCLI
```

### Windows (pip)

```powershell
pip install awscli
aws --version
```

### Configure

```powershell
aws configure
# Access Key ID: (AWS Console → IAM → Users → Security credentials → Create access key)
# Secret Access Key: (same jagah copy karo)
# Region: us-east-1
```

Access key create: AWS Console → IAM → Users → Apna user → Security credentials → Create access key

---

## GPU Requirements (Setup & Pipeline)

### Flow Overview

| Step | Service | GPU? | Role |
|------|---------|------|------|
| 1 | Next.js | No | UI, auth, API routes |
| 2 | API Gateway | No | Route requests |
| 3 | Lambda | No | Orchestrate, invoke SageMaker |
| 4 | **SageMaker** | **Yes** | SDXL inference (image generation) |
| 5 | S3 | No | Store images |

### Image Generation (SageMaker)

| Item | Value |
|------|-------|
| **Model** | stabilityai/stable-diffusion-xl-base-1.0 (SDXL) |
| **Task** | text-to-image |
| **Resolution** | 1024×1024 (default), configurable |
| **Batch** | Up to 4 images per request |
| **Inference steps** | 30 (default), 20–50 supported |
| **VRAM needed** | ~12–16 GB (SDXL at 1024) |
| **Instance (default)** | ml.g5.2xlarge |
| **GPU** | 1× NVIDIA A10G (24 GB VRAM) |
| **vCPU/RAM** | 4 vCPU, 32 GiB |

### Instance (Best Result ke liye)

| Instance | GPU | VRAM | Role |
|----------|-----|------|------|
| **ml.g5.2xlarge** | A10G | 24 GB | Generation, Training, Refinement – **ye use karo** |
| ml.g5.4xlarge | A10G×2 | 48 GB | High load – 2× throughput |
| ml.g4dn.xlarge | T4 | 16 GB | Mat use karo – SDXL 1024 pe OOM ho sakta |

**Best result:** `ml.g5.2xlarge` – SDXL, refinement, LoRA sab ke liye sufficient.

Override via env before deploy:
```powershell
$env:SAGEMAKER_INSTANCE="ml.g5.2xlarge"
python deploy_endpoint.py
```

### LoRA Training (SageMaker Training Job)

| Item | Value |
|------|-------|
| **Instance** | ml.g5.2xlarge |
| **GPU** | 1× A10G (24 GB) |
| **Volume** | 50 GB |
| **Max runtime** | 1 hour |
| **Role** | LoRA fine-tuning on user photos |

### Generation Limits (per code)

| Limit | Value | Config |
|-------|-------|--------|
| Max images/request | 4 | Lambda `num_images` cap |
| Width/Height | 1024 | Lambda payload default |
| Inference steps | 30 | `num_inference_steps` |
| Guidance scale | 6.5–8.5 | Mode-based (REALISM, CREATIVE, etc.) |

### Best Result – Full Setup (Sab Deploy Karo)

Sirf 1024 generation se accha result nahi aayega. Best result ke liye ye sab deploy karo:

| Feature | GPU | SageMaker Instance | Kaam |
|---------|-----|--------------------|------|
| **Generation** | A10G 24GB | ml.g5.2xlarge | SDXL 1024×1024 |
| **Refinement** | A10G 24GB | ml.g5.2xlarge | User edits ke baad improve |
| **4K** | A100 40GB | ml.p4d.24xlarge | Large prints, 4096×4096 |
| **Quality scoring** | T4 16GB | ml.g4dn.xlarge | Best image auto-select |
| **Identity (LoRA)** | A10G 24GB | ml.g5.2xlarge | Face-consistent gen |

**Best result ke liye deploy karo:**  
1. Generation endpoint (STEP 1)  
2. Refinement – Lambda + SageMaker endpoint (img2img)  
3. LoRA training (STEP 2 me)  
4. 4K endpoint – A100 (large prints)  
5. Quality scoring endpoint – best image pick

---

## STEP 1 — SageMaker GPU Endpoint (Most Important)

**Check karo endpoint deploy hai ya nahi:**

```powershell
aws sagemaker list-endpoints --region us-east-1
```

Result me hona chahiye:

```
EndpointStatus: InService
EndpointName: photogenius-generation-dev
```

### ❌ Agar endpoint nahi hai

**1. SAGEMAKER_ROLE set karo** (IAM role ARN required):

Agar error aaye "No SageMaker execution role":
- IAM Console → Roles → Create role → SageMaker → AmazonSageMakerFullAccess attach karo
- Role ka ARN copy karo (arn:aws:iam::123456789:role/YourRoleName)
- **Option A** – Deploy se pehle:
```powershell
$env:SAGEMAKER_ROLE="arn:aws:iam::YOUR_ACCOUNT_ID:role/YourSageMakerRole"
```
- **Option B** – `aws/sagemaker/.env.local` banao:
```
SAGEMAKER_ROLE=arn:aws:iam::YOUR_ACCOUNT_ID:role/YourSageMakerRole
```

**2. (Optional) Hugging Face token** – gated models ke liye:
```powershell
$env:HUGGINGFACE_TOKEN="hf_xxxx"
```

**3. Deploy run karo** (alag venv – numpy/facenet conflict avoid):

```powershell
cd aws/sagemaker
.\deploy.ps1
```

Ya manually:
```powershell
cd aws/sagemaker
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python deploy_endpoint.py
```

Wait until status = `InService` (10–15 min).

⚠️ **Jab tak ye green nahi hota, GPU kabhi run nahi karega.**

---

## STEP 2 — Lambda + API Deploy

**Option A — Script (recommended):** Stack ROLLBACK_COMPLETE ho to pehle delete karta hai, phir build + deploy.

```powershell
cd aws
.\deploy.ps1
```

**Option B — Manual:**

```powershell
cd aws
# Agar pehle deploy fail hua tha (ROLLBACK_COMPLETE): pehle stack delete karo
aws cloudformation delete-stack --stack-name photogenius --region us-east-1
# Delete complete hone tak wait, phir:
sam build
sam deploy --guided
```

Output me milega:

```
ApiEndpoint = https://xxxxx.execute-api.us-east-1.amazonaws.com/Prod
```

Is URL ko copy karo.

---

## STEP 3 — Web App Config

File: `apps/web/.env.local`

```env
# AWS Cloud Provider
CLOUD_PROVIDER=aws

# API Gateway URL (from SAM output) - AI calls go here
AWS_API_GATEWAY_URL=https://xxxxx.execute-api.us-east-1.amazonaws.com/Prod

# OR set each service URL explicitly:
# AWS_LAMBDA_GENERATION_URL=https://xxxxx.execute-api.us-east-1.amazonaws.com/Prod/generate
# AWS_LAMBDA_SAFETY_URL=https://xxxxx.execute-api.us-east-1.amazonaws.com/Prod/safety

# App URLs
NEXT_PUBLIC_API_URL=http://localhost:3000
NEXT_PUBLIC_APP_URL=http://localhost:3000
NEXT_PUBLIC_WS_URL=ws://localhost:3000

# Clerk (required)
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_...
CLERK_SECRET_KEY=sk_...
```

---

## STEP 4 — Lambda Environment (SAM)

SAM template already passes:

- `SAGEMAKER_ENDPOINT=photogenius-generation-dev`
- `S3_BUCKET=photogenius-images-dev`
- `AWS_REGION` — Lambda automatically set karta hai (template mein **mat** add karo; reserved key hai).

Agar custom endpoint hai, deploy time pe override karo:

```powershell
sam deploy --parameter-overrides SageMakerEndpoint=your-endpoint-name
```

---

## STEP 5 — Website Run

```powershell
cd apps/web
pnpm install
pnpm dev
```

Browser: `http://localhost:3000`

Image generate try karo.

---

## STEP 6 — GPU Hit Ho Raha Hai Ya Nahi

```powershell
aws sagemaker describe-endpoint --endpoint-name photogenius-generation-dev --region us-east-1
```

CloudWatch logs:

```powershell
aws logs tail /aws/lambda/photogenius-generation-dev --follow
```

---

## Common Problems

| Problem              | Result              | Fix                    |
|----------------------|---------------------|------------------------|
| Endpoint deploy nahi | GPU never runs      | STEP 1 run karo        |
| Wrong endpoint name  | Calls fail silently | Name must match exactly|
| Lambda not deployed  | Website calls fail  | STEP 2 run karo        |
| API URL missing      | Frontend broken     | STEP 3 check karo      |
| Region mismatch      | Endpoint not found  | sab jagah us-east-1    |
| S3 bucket missing    | Upload fail         | SAM creates it         |

---

## Debug Commands (Ek Baar Run Karo)

```powershell
# S3 buckets
aws s3 ls | findstr photogenius

# SageMaker endpoints
aws sagemaker list-endpoints --region us-east-1

# SAM stack
sam list stacks
```

---

## Golden Rule

GPU **tab hi chalega** jab:

```
Website → Next.js /api/generate → AIService → API Gateway /generate → Lambda → SageMaker InService
```

Ek bhi step missing → generation fail.

---

## S3 Bucket Names

| Bucket                 | Use            |
|------------------------|----------------|
| photogenius-images-dev | Generated pics |
| photogenius-models-dev | AI models      |
| photogenius-loras-dev  | LoRA weights   |

SAM deploy inhe create karta hai.

---

## Cost (Approx)

| Service   | Config              | Monthly  |
|-----------|---------------------|----------|
| SageMaker | ml.g5.2xlarge       | ~$100–150|
| Lambda    | 1M requests         | ~$0.20   |
| S3        | 50GB                | ~$1.15   |
| API Gateway | 1M requests       | ~$3.50   |

---

## Dependency Conflicts (numpy / sagemaker)

**Problem:** `pip install sagemaker` do tarah se break karta hai:
- **sagemaker 2.x** → numpy 2.x pull karta hai → facenet, scipy break
- **sagemaker 3.x** → HuggingFaceModel hata diya, deploy script fail

**Fix:** Main project me sagemaker **mat** install karo. Deploy ke liye `deploy.ps1` use karo – wo apna venv bana ke sagemaker 2.x use karta hai:

```powershell
cd aws\sagemaker
.\deploy.ps1
```

Main env me agar sagemaker 3.x hai to uninstall karo:
```powershell
pip uninstall sagemaker sagemaker-core sagemaker-mlops sagemaker-serve sagemaker-train -y
```

Agar `~umpy` invalid distribution warning aaye:
```powershell
Remove-Item "$env:LOCALAPPDATA\Programs\Python\Python311\Lib\site-packages\~*" -Recurse -Force -ErrorAction SilentlyContinue
```

---

## SAM Deploy Errors

**"Reserved keys used in this request: AWS_REGION"**  
Template me `AWS_REGION` env var mat set karo — Lambda khud set karta hai. Ab template me hata diya gaya hai; bas `sam build` + `sam deploy` dobara chalao.

**"Stack is in ROLLBACK_COMPLETE state and can not be updated"**  
Pehle stack delete karo, phir fresh deploy:
```powershell
aws cloudformation delete-stack --stack-name photogenius --region us-east-1
# 1–2 min wait, phir:
.\deploy.ps1
```

---

## Agar Abhi Bhi GPU Start Nahi Hota

Ye output bhejo:

```powershell
aws sagemaker list-endpoints --region us-east-1
```

Us se turant issue clear ho jayega.
