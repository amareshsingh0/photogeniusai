# PhotoGenius SageMaker Setup

## Current Status

| Component              | Status       | Notes                                                         |
| ---------------------- | ------------ | ------------------------------------------------------------- |
| API Gateway            | ✅ Working   | `https://xa89zghkq7.execute-api.us-east-1.amazonaws.com/Prod` |
| Lambda Orchestrator v2 | ✅ Working   | Supports test_mode and real inference                         |
| SageMaker Endpoints    | ⚠️ InService | Models timeout on loading                                     |

## The Issue

SageMaker endpoints exist but their inference containers **timeout when loading SDXL models** (7GB+) from HuggingFace on first invocation. This is because:

1. Container startup timeout: ~60 seconds
2. SDXL model download: 7GB takes longer
3. Result: Timeout before model loads

## Solutions

### Option 1: Use EC2 to Pre-stage Models (Recommended)

Launch an EC2 instance with good network to download models and upload to S3:

```bash
# On EC2 (e.g., t3.medium in us-east-1)
pip install huggingface_hub boto3

# Download SDXL Turbo (faster, smaller)
python -c "
from huggingface_hub import snapshot_download
snapshot_download(
    repo_id='stabilityai/sdxl-turbo',
    local_dir='/tmp/sdxl-turbo',
    ignore_patterns=['*.md', '*.txt', 'samples/*']
)
"

# Upload to S3
aws s3 sync /tmp/sdxl-turbo s3://photogenius-models-dev/models/sdxl-turbo --region us-east-1
```

Then update SageMaker inference code to load from S3.

### Option 2: Use SageMaker JumpStart

AWS provides pre-packaged SDXL models via JumpStart:

```python
from sagemaker.jumpstart.model import JumpStartModel

model = JumpStartModel(
    model_id="model-txt2img-stabilityai-stable-diffusion-xl-base-1-0",
    role="arn:aws:iam::288761732313:role/SageMakerExecutionRole"
)

predictor = model.deploy(
    initial_instance_count=1,
    instance_type="ml.g5.2xlarge",
    endpoint_name="photogenius-jumpstart"
)
```

### Option 3: Use Modal.com (Simplest)

Modal handles model caching automatically:

```python
# modal_app.py
import modal

stub = modal.Stub("photogenius")

@stub.cls(gpu="A10G", image=modal.Image.debian_slim().pip_install("diffusers", "torch"))
class SDXLGenerator:
    @modal.enter()
    def load_model(self):
        from diffusers import AutoPipelineForText2Image
        import torch
        self.pipe = AutoPipelineForText2Image.from_pretrained(
            "stabilityai/sdxl-turbo",
            torch_dtype=torch.float16
        ).to("cuda")

    @modal.method()
    def generate(self, prompt: str):
        return self.pipe(prompt, num_inference_steps=4).images[0]
```

Deploy: `modal deploy modal_app.py`

## Testing Current Setup

The pipeline works with `test_mode`:

```powershell
# Test API (returns mock image instantly)
$body = @{ prompt = "beautiful sunset"; test_mode = $true } | ConvertTo-Json
Invoke-RestMethod -Uri "https://xa89zghkq7.execute-api.us-east-1.amazonaws.com/Prod/orchestrate/v2" `
  -Method Post -ContentType "application/json" -Body $body
```

## Files Reference

- `deploy/sagemaker_deployment.py` - Multi-tier endpoint deployment
- `deploy/sagemaker_jumpstart.py` - JumpStart deployment (simpler)
- `aws/lambda/orchestrator_v2/handler.py` - Lambda with test_mode
- `aws/sagemaker/model/code/inference.py` - SageMaker inference code

## Recommended Next Steps

1. **For Testing**: Use `test_mode=true` to verify full pipeline
2. **For Production**:
   - Option A: Launch EC2, download models, upload to S3, redeploy
   - Option B: Use SageMaker JumpStart (if available in your region)
   - Option C: Use Modal.com (simplest, pay-per-use)

## Cost Estimates

| Service                 | Cost                    | Notes             |
| ----------------------- | ----------------------- | ----------------- |
| SageMaker ml.g5.xlarge  | ~$1.20/hr               | STANDARD tier     |
| SageMaker ml.g5.2xlarge | ~$2.40/hr               | PREMIUM tier      |
| Modal A10G              | ~$0.0011/sec            | Pay-per-inference |
| API Gateway             | ~$3.50/million requests |                   |
| Lambda                  | ~$0.20/million requests |                   |
