# ⚡ Lightning.ai Setup Guide

PhotoGenius AI ko Lightning.ai pe setup karne ka complete guide.
Local laptop pe code chalega, GPU Lightning.ai pe hoga (Modal jaisa hi).

---

## 📋 Table of Contents

1. [Prerequisites](#prerequisites)
2. [Lightning Account Setup](#lightning-account-setup)
3. [Local Development Setup](#local-development-setup)
4. [Deploy AI Services](#deploy-ai-services)
5. [Connect Frontend to Lightning](#connect-frontend-to-lightning)
6. [Testing](#testing)
7. [Troubleshooting](#troubleshooting)

---

## 🔑 Prerequisites

### 1. Lightning.ai Account
- Sign up at https://lightning.ai
- Free tier: 22 GPU hours/month
- Pro tier: More GPU hours + priority

### 2. Python Environment
```bash
# Python 3.10+ required
python --version

# Create virtual environment
python -m venv venv
.\venv\Scripts\activate  # Windows
source venv/bin/activate  # Mac/Linux
```

### 3. Install Lightning SDK
```bash
pip install lightning
pip install lightning-cloud
```

---

## ⚡ Lightning Account Setup

### Step 1: Login to Lightning

```bash
lightning login
```
Browser khulega → Login karo → Token automatically save ho jayega

### Step 2: Verify Authentication

```bash
lightning whoami
```
Output:
```
Username: your-username
Team: your-team-id
```

### Step 3: Get API Key (Optional - for programmatic access)

1. Go to https://lightning.ai/settings/keys
2. Click "Create API Key"
3. Copy and save the key

```bash
# Set in environment
export LIGHTNING_API_KEY=your_api_key_here
```

---

## 💻 Local Development Setup

### Step 1: Update Environment Variables

Edit `apps/web/.env.local`:

```bash
# Cloud Provider
CLOUD_PROVIDER=lightning

# Lightning Configuration
LIGHTNING_API_KEY=your_api_key_here
LIGHTNING_TEAM_ID=your_team_id
LIGHTNING_APP_ID=photogenius

# Service URLs (will be set after deployment)
LIGHTNING_SAFETY_URL=
LIGHTNING_GENERATION_URL=
LIGHTNING_REFINEMENT_URL=
LIGHTNING_TRAINING_URL=
```

### Step 2: Create Lightning App Structure

Create `ai-pipeline/lightning_app/` folder:

```
ai-pipeline/
└── lightning_app/
    ├── app.py              # Main Lightning App
    ├── components/
    │   ├── __init__.py
    │   ├── safety.py       # Safety check component
    │   ├── generation.py   # Image generation component
    │   ├── refinement.py   # Refinement component
    │   └── training.py     # LoRA training component
    └── requirements.txt
```

---

## 🚀 Deploy AI Services

### Step 1: Create Main Lightning App

Create `ai-pipeline/lightning_app/app.py`:

```python
import lightning as L
from lightning.app.components import LightningWork
from lightning.app.storage import Drive

# ==================== Safety Component ====================
class SafetyWork(LightningWork):
    """CPU-based safety checks"""

    def __init__(self):
        super().__init__(
            cloud_compute=L.CloudCompute("cpu-small"),
            parallel=True,
        )

    def run(self, prompt: str, mode: str = "REALISM"):
        from services.safety_service import check_prompt_safety
        return check_prompt_safety(prompt, mode)


# ==================== Generation Component ====================
class GenerationWork(LightningWork):
    """GPU-accelerated image generation"""

    def __init__(self):
        super().__init__(
            cloud_compute=L.CloudCompute(
                "gpu-rtx",  # RTX 3090/4090
                # "gpu-a100"  # For production
                disk_size=50,
                preemptible=True,  # Cheaper, can be interrupted
            ),
            parallel=True,
        )
        self.model_drive = Drive("lit://photogenius-models")

    def setup(self):
        """Load models on GPU startup"""
        import torch
        from diffusers import StableDiffusionXLPipeline

        # Download models to persistent drive
        self.pipe = StableDiffusionXLPipeline.from_pretrained(
            "stabilityai/stable-diffusion-xl-base-1.0",
            torch_dtype=torch.float16,
            cache_dir=self.model_drive.root,
        ).to("cuda")

    def run(self, prompt: str, mode: str, num_images: int = 2, **kwargs):
        """Generate images"""
        images = self.pipe(
            prompt=prompt,
            num_images_per_prompt=num_images,
            num_inference_steps=30,
            guidance_scale=7.5,
        ).images

        # Convert to base64
        import base64
        from io import BytesIO

        results = []
        for img in images:
            buffer = BytesIO()
            img.save(buffer, format="PNG")
            b64 = base64.b64encode(buffer.getvalue()).decode()
            results.append({"image_base64": b64})

        return results


# ==================== Refinement Component ====================
class RefinementWork(LightningWork):
    """GPU-accelerated image refinement"""

    def __init__(self):
        super().__init__(
            cloud_compute=L.CloudCompute("gpu-rtx", preemptible=True),
            parallel=True,
        )

    def run(self, image_base64: str, refinement_request: str, **kwargs):
        from services.refinement_engine import refine_image
        return refine_image(image_base64, refinement_request)


# ==================== Training Component ====================
class TrainingWork(LightningWork):
    """GPU-accelerated LoRA training"""

    def __init__(self):
        super().__init__(
            cloud_compute=L.CloudCompute(
                "gpu-a100",  # A100 for training
                disk_size=100,
            ),
            parallel=True,
        )
        self.lora_drive = Drive("lit://photogenius-loras")

    def run(self, user_id: str, identity_id: str, image_urls: list, **kwargs):
        from services.lora_trainer import train_lora
        result = train_lora(
            user_id=user_id,
            identity_id=identity_id,
            image_urls=image_urls,
            output_dir=self.lora_drive.root,
        )
        return result


# ==================== Main App ====================
class PhotoGeniusApp(L.LightningFlow):
    """Main PhotoGenius Lightning App"""

    def __init__(self):
        super().__init__()
        self.safety = SafetyWork()
        self.generation = GenerationWork()
        self.refinement = RefinementWork()
        self.training = TrainingWork()

    def run(self):
        """Main flow - components auto-scale"""
        pass

    def check_safety(self, prompt: str, mode: str = "REALISM"):
        """API endpoint for safety check"""
        return self.safety.run(prompt, mode)

    def generate(self, prompt: str, mode: str, **kwargs):
        """API endpoint for generation"""
        # First check safety
        safety_result = self.safety.run(prompt, mode)
        if not safety_result.get("allowed", True):
            return {"error": "Content blocked", "violations": safety_result.get("violations", [])}

        # Generate images
        return self.generation.run(prompt, mode, **kwargs)

    def refine(self, image_base64: str, refinement_request: str, **kwargs):
        """API endpoint for refinement"""
        return self.refinement.run(image_base64, refinement_request, **kwargs)

    def train(self, user_id: str, identity_id: str, image_urls: list, **kwargs):
        """API endpoint for training"""
        return self.training.run(user_id, identity_id, image_urls, **kwargs)

    def configure_api(self):
        """Expose REST API endpoints"""
        return [
            {
                "endpoint": "/api/safety",
                "method": "POST",
                "handler": self.check_safety,
            },
            {
                "endpoint": "/api/generate",
                "method": "POST",
                "handler": self.generate,
            },
            {
                "endpoint": "/api/refine",
                "method": "POST",
                "handler": self.refine,
            },
            {
                "endpoint": "/api/train",
                "method": "POST",
                "handler": self.train,
            },
        ]


# Create app instance
app = L.LightningApp(PhotoGeniusApp())
```

### Step 2: Create Requirements

Create `ai-pipeline/lightning_app/requirements.txt`:

```
torch>=2.0.0
diffusers>=0.25.0
transformers>=4.36.0
accelerate>=0.25.0
safetensors>=0.4.0
peft>=0.7.0
insightface>=0.7.3
opencv-python>=4.9.0
pillow>=10.0.0
numpy>=1.24.0
anthropic>=0.8.0
```

### Step 3: Deploy to Lightning Cloud

```bash
cd ai-pipeline/lightning_app

# Run locally first (for testing)
lightning run app app.py

# Deploy to cloud
lightning run app app.py --cloud
```

### Step 4: Get Service URLs

After deployment, you'll see URLs like:
```
🚀 App running at: https://your-team.lightning.ai/apps/photogenius

API Endpoints:
  - POST https://your-team.lightning.ai/apps/photogenius/api/safety
  - POST https://your-team.lightning.ai/apps/photogenius/api/generate
  - POST https://your-team.lightning.ai/apps/photogenius/api/refine
  - POST https://your-team.lightning.ai/apps/photogenius/api/train
```

### Step 5: Update Environment Variables

```bash
# apps/web/.env.local
LIGHTNING_SAFETY_URL=https://your-team.lightning.ai/apps/photogenius/api/safety
LIGHTNING_GENERATION_URL=https://your-team.lightning.ai/apps/photogenius/api/generate
LIGHTNING_REFINEMENT_URL=https://your-team.lightning.ai/apps/photogenius/api/refine
LIGHTNING_TRAINING_URL=https://your-team.lightning.ai/apps/photogenius/api/train
```

---

## 🔗 Connect Frontend to Lightning

### Option 1: Using Cloud Config (Automatic)

Already configured in `apps/web/lib/cloud-config.ts`:

```typescript
// Auto-detects Lightning when LIGHTNING_API_KEY is set
const provider = detectProvider(); // Returns "lightning"
const url = getServiceUrl("generation"); // Returns Lightning URL
```

### Option 2: Direct URL Override

```bash
# apps/web/.env.local
AI_GENERATION_URL=https://your-team.lightning.ai/apps/photogenius/api/generate
AI_SAFETY_URL=https://your-team.lightning.ai/apps/photogenius/api/safety
```

---

## 🧪 Testing

### Test Locally First

```bash
# Terminal 1: Run Lightning app locally
cd ai-pipeline/lightning_app
lightning run app app.py

# Terminal 2: Run frontend
cd apps/web
pnpm dev
```

### Test Cloud Deployment

```bash
# Test safety endpoint
curl -X POST https://your-team.lightning.ai/apps/photogenius/api/safety \
  -H "Content-Type: application/json" \
  -d '{"prompt": "professional headshot", "mode": "REALISM"}'

# Test generation endpoint
curl -X POST https://your-team.lightning.ai/apps/photogenius/api/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "professional headshot", "mode": "REALISM", "num_images": 2}'
```

---

## 💰 Lightning.ai Pricing

| Compute | Price | Use Case |
|---------|-------|----------|
| cpu-small | $0.01/hr | Safety checks |
| gpu-rtx | $0.50/hr | Generation, Refinement |
| gpu-a100 | $2.00/hr | Training |

**Free Tier:** 22 GPU hours/month

---

## 🔧 Troubleshooting

### Error: "GPU not available"
```bash
# Check available GPUs
lightning show resources

# Use different GPU type
cloud_compute=L.CloudCompute("gpu-t4")  # Cheaper alternative
```

### Error: "Model download failed"
```bash
# Pre-download models
lightning run app download_models.py --cloud
```

### Error: "App not responding"
```bash
# Check app status
lightning list apps

# View logs
lightning logs photogenius

# Restart app
lightning stop photogenius
lightning run app app.py --cloud
```

### Error: "Authentication failed"
```bash
# Re-login
lightning logout
lightning login
```

---

## 📁 Project Structure After Setup

```
PhotoGenius AI/
├── apps/
│   └── web/
│       └── .env.local          # CLOUD_PROVIDER=lightning
├── ai-pipeline/
│   ├── lightning_app/          # NEW
│   │   ├── app.py
│   │   ├── components/
│   │   └── requirements.txt
│   └── services/               # Existing services (reused)
└── docs/
    └── LIGHTNING_SETUP.md
```

---

## ✅ Checklist

- [ ] Lightning.ai account created
- [ ] `lightning login` done
- [ ] LIGHTNING_API_KEY set in .env.local
- [ ] Lightning app created (app.py)
- [ ] App deployed: `lightning run app app.py --cloud`
- [ ] Service URLs updated in .env.local
- [ ] Frontend tested with Lightning backend
