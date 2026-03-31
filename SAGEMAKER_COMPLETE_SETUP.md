# PhotoGenius: Complete SageMaker Setup (Start to End)

**14-Model Enterprise Stack | Ubuntu | Resumable Downloads | No GPU Needed for Setup**

---

## IMPORTANT: You Do NOT Need a GPU for Downloading Models

The old approach used `FluxPipeline.from_pretrained()` which loads 23GB into RAM = crash/swap on 16GB machines.

**New approach:** `huggingface-cli download` — just downloads files to disk. Works with 2GB RAM. Auto-resumes on network failure.

**Use a cheap CPU instance (m5.xlarge ~$0.19/hr) instead of GPU (g5.xlarge ~$1.01/hr).**
CPU instances are ALWAYS available. g5 instances often have capacity issues.

---

## AWS Resources

| Resource | Value |
|----------|-------|
| **S3 Bucket** | `photogenius-models-dev` |
| **SageMaker Endpoint** | `photogenius-production` (ml.g5.2xlarge) |
| **EC2 Instance** | `i-07b66618e018325d5` (currently g5.xlarge) |
| **IAM Role** | `arn:aws:iam::288761732313:role/SageMakerExecutionRole` |

---

## All 14 Models (~67GB Total)

| # | Model | Size | Category | Download Method |
|---|-------|------|----------|-----------------|
| 1 | FLUX.1-schnell | 23 GB | Core | `huggingface-cli download` |
| 2 | PixArt-Sigma | 12 GB | Core | `huggingface-cli download` |
| 3 | InstantID | 2 GB | Core | `huggingface-cli download` |
| 4 | Mixtral-8x7B-Instruct | 15 GB | Intelligence | `huggingface-cli download` |
| 5 | ControlNet-SDXL (canny/depth/openpose) | 5 GB | Control | `huggingface-cli download` |
| 6 | IP-Adapter | 1 GB | Control | `huggingface-cli download` |
| 7 | RealESRGAN-x4 | 64 MB | Enhancement | `wget` |
| 8 | Swin2SR | 3 GB | Enhancement | `huggingface-cli download` |
| 9 | OpenCLIP (ViT-H-14) | 2 GB | Ranking | `huggingface-cli download` |
| 10 | LAION-Aesthetic | 1 GB | Ranking | `huggingface-cli download` |
| 11 | CLIP-ViT-Large | 1.6 GB | Ranking | `huggingface-cli download` |
| 12 | NudeNet | 200 MB | Safety | `huggingface-cli download` |
| 13 | Detoxify | 300 MB | Safety | Python (small) |
| 14 | U2-Net | 200 MB | Utilities | `huggingface-cli download` |

**All licenses: Apache 2.0 / MIT / BSD-3 — 100% commercial free**

---

## HOW TO CHANGE EC2 INSTANCE TYPE

If your current EC2 is g5.xlarge and you want to change it to m5.xlarge (CPU, cheaper, always available):

```bash
# Step 1: Stop the instance first (MUST be stopped to change type)
aws ec2 stop-instances --instance-ids i-07b66618e018325d5
aws ec2 wait instance-stopped --instance-ids i-07b66618e018325d5
echo "Instance stopped"

# Step 2: Change instance type
aws ec2 modify-instance-attribute \
  --instance-id i-07b66618e018325d5 \
  --instance-type m5.xlarge

echo "Changed to m5.xlarge"

# Step 3: Start the instance
aws ec2 start-instances --instance-ids i-07b66618e018325d5
aws ec2 wait instance-running --instance-ids i-07b66618e018325d5

# Step 4: Get new public IP (changes after restart)
aws ec2 describe-instances \
  --instance-ids i-07b66618e018325d5 \
  --query 'Reservations[0].Instances[0].PublicIpAddress' \
  --output text
```

### Which Instance to Use?

| Instance | vCPU | RAM | GPU | Cost/hr | Availability | Use For |
|----------|------|-----|-----|---------|--------------|---------|
| **m5.xlarge** | 4 | 16 GB | None | $0.19 | Always available | Downloading models (RECOMMENDED) |
| **m5.2xlarge** | 8 | 32 GB | None | $0.38 | Always available | If you want faster downloads |
| **c5.xlarge** | 4 | 8 GB | None | $0.17 | Always available | Budget option for downloads |
| g5.xlarge | 4 | 16 GB | A10G 24GB | $1.01 | Often unavailable | NOT needed for downloads |
| g5.2xlarge | 8 | 32 GB | A10G 24GB | $1.52 | Often unavailable | NOT needed for downloads |

**Bottom line: Use m5.xlarge for downloading. GPU is only needed on SageMaker (AWS manages that).**

### SageMaker Instance Alternatives

If `ml.g5.2xlarge` has availability issues on SageMaker:

| Instance | GPU | VRAM | RAM | Cost/hr | Notes |
|----------|-----|------|-----|---------|-------|
| **ml.g5.2xlarge** | A10G | 24 GB | 32 GB | $1.52 | Best choice (RECOMMENDED) |
| **ml.g5.xlarge** | A10G | 24 GB | 16 GB | $1.01 | Works but tight RAM |
| **ml.g6.xlarge** | L4 | 24 GB | 16 GB | $0.98 | Newer GPU, often more available |
| ml.g6.2xlarge | L4 | 24 GB | 32 GB | $1.30 | L4 GPU + more RAM |
| ml.p3.2xlarge | V100 | 16 GB | 61 GB | $3.06 | Lots of RAM but only 16GB VRAM |

To change SageMaker instance, just change `"InstanceType"` in Phase 5 deploy script.

---

## PHASE 0: COMPLETE CLEANUP

### Step 0.1: Change EC2 to CPU Instance (Save Money + Always Available)

Run these from your **local machine** (Windows/PowerShell):

```bash
# Stop EC2
aws ec2 stop-instances --instance-ids i-07b66618e018325d5
aws ec2 wait instance-stopped --instance-ids i-07b66618e018325d5

# Change to m5.xlarge (CPU, cheaper, always available)
aws ec2 modify-instance-attribute \
  --instance-id i-07b66618e018325d5 \
  --instance-type m5.xlarge

# Start EC2
aws ec2 start-instances --instance-ids i-07b66618e018325d5
aws ec2 wait instance-running --instance-ids i-07b66618e018325d5

# Get new IP
aws ec2 describe-instances \
  --instance-ids i-07b66618e018325d5 \
  --query 'Reservations[0].Instances[0].PublicIpAddress' \
  --output text
```

### Step 0.2: SSH into EC2

```bash
# Use the IP from above
ssh -i your-key.pem ubuntu@<NEW_IP_ADDRESS>
```

### Step 0.3: Clean Everything on EC2

```bash
# Delete ALL old models, packages, test files
rm -rf ~/models 2>/dev/null
rm -rf ~/sagemaker-* 2>/dev/null
rm -rf ~/flux-* 2>/dev/null
rm -f ~/model.tar.gz 2>/dev/null
rm -f ~/test_*.png 2>/dev/null
rm -rf ~/.cache/huggingface 2>/dev/null

# Check disk space (should show ~280GB free on 300GB disk)
df -h /

echo "EC2 cleanup complete!"
```

### Step 0.4: Clean S3

```bash
# See what's in S3
aws s3 ls s3://photogenius-models-dev/ --recursive --human-readable --summarize

# Delete EVERYTHING from S3
aws s3 rm s3://photogenius-models-dev/ --recursive

# Verify empty
aws s3 ls s3://photogenius-models-dev/ --recursive --summarize

echo "S3 cleanup complete!"
```

### Step 0.5: Delete Old SageMaker Endpoint (Optional)

```bash
# If old endpoint exists, delete it
aws sagemaker delete-endpoint --endpoint-name photogenius-production 2>/dev/null
echo "Old endpoint deleted (or didn't exist)"
```

---

## PHASE 1: Environment Setup (Ubuntu)

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install essentials
sudo apt install -y python3-pip python3-venv git wget curl htop

# Create virtual environment
python3 -m venv ~/download-env
source ~/download-env/bin/activate

# Install ONLY what we need for downloading (minimal)
pip install --upgrade pip
pip install huggingface_hub[cli] boto3

# Verify
huggingface-cli --version
aws --version

echo "Environment ready!"
```

### Login to HuggingFace (Required for Some Models)

```bash
# Get FREE token from: https://huggingface.co/settings/tokens
# Click "New token" → Name: "ec2-download" → Type: "Read" → Create
huggingface-cli login
# Paste your token when prompted
```

**Note:** This is a FREE read-only token just for downloading. No API costs. No per-generation charges.

---

## PHASE 2: Download All 14 Models

Save as `download_models.sh` and run with `bash download_models.sh`.
All downloads auto-resume on failure — just run the same command again.

```bash
#!/bin/bash
# PhotoGenius - Download All 14 Models (Using 'hf' command)
# IMPORTANT: --exclude and --include filters prevent downloading duplicate formats

set -e

source ~/download-env/bin/activate

echo "============================================"
echo "DOWNLOADING ALL 14 MODELS"
echo "Total expected: ~75-80GB"
echo "============================================"
echo ""

# Show current disk space
echo "Starting disk space:"
df -h / | grep "/$"
echo ""

mkdir -p ~/models/{core,intelligence,control,enhancement,ranking,safety,utilities}

# ==========================================
# 1/14 - FLUX.1-schnell (~30GB)
# IMPORTANT: Exclude single-file checkpoint (duplicate of diffusers format)
# Without --exclude: downloads 54GB (single-file + diffusers = double)
# With --exclude: downloads ~30GB (diffusers format only)
# ==========================================
echo "=========================================="
echo "1/14 - FLUX.1-schnell (~30GB)"
echo "=========================================="
hf download black-forest-labs/FLUX.1-schnell \
  --local-dir ~/models/core/flux-schnell \
  --exclude "flux1-schnell.safetensors" \
  --exclude "ae.safetensors"
echo "FLUX.1-schnell DONE!"
du -sh ~/models/core/flux-schnell
echo ""

# ==========================================
# 2/14 - PixArt-Sigma (~12GB)
# Exclude .bin files (keep only safetensors format)
# Without --exclude: downloads 21GB (.bin + .safetensors = double)
# ==========================================
echo "=========================================="
echo "2/14 - PixArt-Sigma (~12GB)"
echo "=========================================="
hf download PixArt-alpha/PixArt-Sigma-XL-2-1024-MS \
  --local-dir ~/models/core/pixart-sigma \
  --exclude "*.bin"
echo "PixArt-Sigma DONE!"
du -sh ~/models/core/pixart-sigma
echo ""

# ==========================================
# 3/14 - InstantID (~2-4GB)
# ==========================================
echo "=========================================="
echo "3/14 - InstantID (~2-4GB)"
echo "=========================================="
hf download InstantX/InstantID \
  --local-dir ~/models/core/instantid
echo "InstantID DONE!"
du -sh ~/models/core/instantid
echo ""

# ==========================================
# 4/14 - Mixtral-8x7B GPTQ (~23GB)
# Using pre-quantized 4-bit version (saves 120GB vs raw weights)
# ==========================================
echo "=========================================="
echo "4/14 - Mixtral-8x7B GPTQ (~23GB)"
echo "Using 4-bit quantized version"
echo "=========================================="
hf download TheBloke/Mixtral-8x7B-Instruct-v0.1-GPTQ \
  --local-dir ~/models/intelligence/mixtral-8x7b \
  --include "*.safetensors" \
  --include "*.json" \
  --include "tokenizer*"
echo "Mixtral DONE!"
du -sh ~/models/intelligence/mixtral-8x7b
echo ""

# ==========================================
# 5/14 - ControlNet Suite (~2.5GB each, NOT 15GB)
# CRITICAL: Only download fp16 safetensors + config
# Without --include: downloads 15GB per model (fp32 .bin + fp32 .safetensors + fp16)
# With --include: downloads ~2.5GB per model (fp16 safetensors only)
# ==========================================
echo "=========================================="
echo "5a/14 - ControlNet-Canny (~2.5GB)"
echo "=========================================="
hf download diffusers/controlnet-canny-sdxl-1.0 \
  --local-dir ~/models/control/controlnet-canny \
  --include "config.json" \
  --include "diffusion_pytorch_model.fp16.safetensors"
echo "ControlNet-Canny DONE!"
du -sh ~/models/control/controlnet-canny
echo ""

echo "=========================================="
echo "5b/14 - ControlNet-Depth (~2.5GB)"
echo "=========================================="
hf download diffusers/controlnet-depth-sdxl-1.0 \
  --local-dir ~/models/control/controlnet-depth \
  --include "config.json" \
  --include "diffusion_pytorch_model.fp16.safetensors"
echo "ControlNet-Depth DONE!"
du -sh ~/models/control/controlnet-depth
echo ""

echo "=========================================="
echo "5c/14 - ControlNet-OpenPose (~2.5GB)"
echo "=========================================="
hf download thibaud/controlnet-openpose-sdxl-1.0 \
  --local-dir ~/models/control/controlnet-openpose \
  --include "config.json" \
  --include "diffusion_pytorch_model.fp16.safetensors" \
  --include "diffusion_pytorch_model.safetensors"
echo "ControlNet-OpenPose DONE!"
du -sh ~/models/control/controlnet-openpose
echo ""

# ==========================================
# 6/14 - IP-Adapter (~500MB)
# Only download specific safetensor files we need
# ==========================================
echo "=========================================="
echo "6/14 - IP-Adapter (~500MB)"
echo "=========================================="
hf download h94/IP-Adapter \
  --local-dir ~/models/control/ip-adapter \
  --include "models/ip-adapter_sd15.safetensors" \
  --include "models/ip-adapter-plus_sd15.safetensors" \
  --include "models/ip-adapter_sdxl_vit-h.safetensors"
echo "IP-Adapter DONE!"
du -sh ~/models/control/ip-adapter
echo ""

# ==========================================
# 7/14 - RealESRGAN (64MB)
# ==========================================
echo "=========================================="
echo "7/14 - RealESRGAN (64MB)"
echo "=========================================="
mkdir -p ~/models/enhancement/realesrgan
wget -q --show-progress -c -O ~/models/enhancement/realesrgan/RealESRGAN_x4plus.pth \
  "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth"
echo "RealESRGAN DONE!"
du -sh ~/models/enhancement/realesrgan
echo ""

# ==========================================
# 8/14 - Swin2SR (~94MB)
# Note: This model is actually ~94MB, not 3GB. That's correct.
# ==========================================
echo "=========================================="
echo "8/14 - Swin2SR (~94MB)"
echo "=========================================="
hf download caidas/swin2SR-classical-sr-x4-64 \
  --local-dir ~/models/enhancement/swin2sr
echo "Swin2SR DONE!"
du -sh ~/models/enhancement/swin2sr
echo ""

# ==========================================
# 9/14 - OpenCLIP (~3.5GB, NOT 15GB)
# Only download model checkpoint + configs
# Without --include: downloads 15GB (all training artifacts)
# ==========================================
echo "=========================================="
echo "9/14 - OpenCLIP (~3.5GB)"
echo "=========================================="
hf download laion/CLIP-ViT-H-14-laion2B-s32B-b79K \
  --local-dir ~/models/ranking/openclip \
  --include "open_clip_pytorch_model.bin" \
  --include "*.json" \
  --include "*.txt"
echo "OpenCLIP DONE!"
du -sh ~/models/ranking/openclip
echo ""

# ==========================================
# 10/14 - LAION-Aesthetic (symlink to OpenCLIP)
# Uses same CLIP model for aesthetic scoring - no separate download
# ==========================================
echo "=========================================="
echo "10/14 - LAION-Aesthetic (symlink)"
echo "=========================================="
ln -sf ~/models/ranking/openclip ~/models/ranking/laion-aesthetic
echo "LAION-Aesthetic DONE! (symlink to OpenCLIP)"
echo ""

# ==========================================
# 11/14 - CLIP-ViT-Large (~1.7GB, NOT 6.4GB)
# Exclude TensorFlow, Flax, and other non-PyTorch formats
# ==========================================
echo "=========================================="
echo "11/14 - CLIP-ViT-Large (~1.7GB)"
echo "=========================================="
hf download openai/clip-vit-large-patch14 \
  --local-dir ~/models/ranking/clip-vit-large \
  --exclude "tf_*" \
  --exclude "flax_*" \
  --exclude "*.msgpack" \
  --exclude "*.h5"
echo "CLIP-ViT-Large DONE!"
du -sh ~/models/ranking/clip-vit-large
echo ""

# ==========================================
# 12/14 - NudeNet (~200MB)
# ==========================================
echo "=========================================="
echo "12/14 - NudeNet (~200MB)"
echo "=========================================="
hf download notAI-tech/NudeNet \
  --local-dir ~/models/safety/nudenet
echo "NudeNet DONE!"
du -sh ~/models/safety/nudenet
echo ""

# ==========================================
# 13/14 - Detoxify (~300MB)
# ==========================================
echo "=========================================="
echo "13/14 - Detoxify (~300MB)"
echo "=========================================="
pip install -q detoxify 2>/dev/null
python3 << 'PYEOF'
from detoxify import Detoxify
import torch, os
os.makedirs("/home/ubuntu/models/safety/detoxify", exist_ok=True)
model = Detoxify('original')
torch.save(model.model.state_dict(), "/home/ubuntu/models/safety/detoxify/model.pt")
model.tokenizer.save_pretrained("/home/ubuntu/models/safety/detoxify")
print("Detoxify saved!")
del model
PYEOF
echo "Detoxify DONE!"
du -sh ~/models/safety/detoxify
echo ""

# ==========================================
# 14/14 - U2-Net (~200MB)
# ==========================================
echo "=========================================="
echo "14/14 - U2-Net (~200MB)"
echo "=========================================="
mkdir -p ~/models/utilities/u2net
wget -q --show-progress -c -O ~/models/utilities/u2net/u2net.pth \
  "https://huggingface.co/skytnt/u2net/resolve/main/u2net.pth"
echo "U2-Net DONE!"
du -sh ~/models/utilities/u2net
echo ""

# ==========================================
# CLEANUP: Remove HuggingFace cache
# ==========================================
echo "=========================================="
echo "CLEANUP: Removing HuggingFace cache"
echo "=========================================="
CACHE_SIZE=$(du -sh ~/.cache/huggingface 2>/dev/null | cut -f1 || echo "0")
echo "Cache size: $CACHE_SIZE"
rm -rf ~/.cache/huggingface 2>/dev/null || true
echo "Cache cleared!"
echo ""

# ==========================================
# FINAL VERIFICATION
# ==========================================
echo ""
echo "============================================"
echo "ALL 14 MODELS DOWNLOADED!"
echo "============================================"
echo ""

echo "CORE MODELS:"
du -sh ~/models/core/* 2>/dev/null || echo "None"
echo ""

echo "INTELLIGENCE:"
du -sh ~/models/intelligence/* 2>/dev/null || echo "None"
echo ""

echo "CONTROL:"
du -sh ~/models/control/* 2>/dev/null || echo "None"
echo ""

echo "ENHANCEMENT:"
du -sh ~/models/enhancement/* 2>/dev/null || echo "None"
echo ""

echo "RANKING:"
du -sh ~/models/ranking/* 2>/dev/null || echo "None"
echo ""

echo "SAFETY:"
du -sh ~/models/safety/* 2>/dev/null || echo "None"
echo ""

echo "UTILITIES:"
du -sh ~/models/utilities/* 2>/dev/null || echo "None"
echo ""

echo "============================================"
echo "TOTAL SIZE:"
du -sh ~/models
echo ""
echo "DISK USAGE:"
df -h / | grep "/$"
echo "============================================"
echo ""
echo "Expected total: 75-80GB"
echo ""
echo "Next step: Upload to S3"
echo "Run: bash upload_to_s3.sh"
echo "============================================"
```

### Expected Sizes After Download

| Model | Expected Size | Notes |
|-------|---------------|-------|
| FLUX.1-schnell | ~30GB | Diffusers format only (not 54GB) |
| PixArt-Sigma | ~12GB | Safetensors only (not 21GB) |
| InstantID | ~2-4GB | Full repo |
| Mixtral GPTQ | ~23GB | Pre-quantized 4-bit |
| ControlNet (x3) | ~2.5GB each | fp16 only (not 15GB each) |
| IP-Adapter | ~500MB | Selected files only |
| RealESRGAN | 64MB | Single .pth file |
| Swin2SR | ~94MB | This IS the correct size |
| OpenCLIP | ~3.5GB | Model checkpoint only (not 15GB) |
| LAION-Aesthetic | 0 (symlink) | Points to OpenCLIP |
| CLIP-ViT-Large | ~1.7GB | PyTorch only (not 6.4GB) |
| NudeNet | ~200MB-1.4GB | ONNX model |
| Detoxify | ~300-420MB | Saved via Python |
| U2-Net | ~200MB | Single .pth file |
| **TOTAL** | **~75-80GB** | |

---

## PHASE 3: Upload All Models to S3

### Upload Script (Resumable with aws s3 sync)

`aws s3 sync` only uploads NEW or CHANGED files. If it disconnects, just run again.

```bash
source ~/download-env/bin/activate
BUCKET="photogenius-models-dev"

echo "============================================================"
echo "UPLOADING 14 MODELS TO S3"
echo "============================================================"
echo "All uploads are RESUMABLE - if it stops, just run again"
echo ""

# CORE (37GB)
echo "1/14 - Uploading FLUX.1-schnell (23GB)..."
aws s3 sync ~/models/core/flux-schnell s3://$BUCKET/models/core/flux-schnell/
echo "FLUX.1-schnell uploaded!"

echo "2/14 - Uploading PixArt-Sigma (12GB)..."
aws s3 sync ~/models/core/pixart-sigma s3://$BUCKET/models/core/pixart-sigma/
echo "PixArt-Sigma uploaded!"

echo "3/14 - Uploading InstantID (2GB)..."
aws s3 sync ~/models/core/instantid s3://$BUCKET/models/core/instantid/
echo "InstantID uploaded!"

# INTELLIGENCE (26GB)
echo "4/14 - Uploading Mixtral-8x7B (26GB)..."
aws s3 sync ~/models/intelligence/mixtral-8x7b s3://$BUCKET/models/intelligence/mixtral-8x7b/
echo "Mixtral uploaded!"

# CONTROL (6GB)
echo "5/14 - Uploading ControlNet Suite (5GB)..."
aws s3 sync ~/models/control/controlnet-canny s3://$BUCKET/models/control/controlnet-canny/
aws s3 sync ~/models/control/controlnet-depth s3://$BUCKET/models/control/controlnet-depth/
aws s3 sync ~/models/control/controlnet-openpose s3://$BUCKET/models/control/controlnet-openpose/
echo "ControlNet uploaded!"

echo "6/14 - Uploading IP-Adapter (1GB)..."
aws s3 sync ~/models/control/ip-adapter s3://$BUCKET/models/control/ip-adapter/
echo "IP-Adapter uploaded!"

# ENHANCEMENT (3GB)
echo "7/14 - Uploading RealESRGAN (64MB)..."
aws s3 sync ~/models/enhancement/realesrgan s3://$BUCKET/models/enhancement/realesrgan/
echo "RealESRGAN uploaded!"

echo "8/14 - Uploading Swin2SR (3GB)..."
aws s3 sync ~/models/enhancement/swin2sr s3://$BUCKET/models/enhancement/swin2sr/
echo "Swin2SR uploaded!"

# RANKING (4.6GB)
echo "9/14 - Uploading OpenCLIP (2GB)..."
aws s3 sync ~/models/ranking/openclip s3://$BUCKET/models/ranking/openclip/
echo "OpenCLIP uploaded!"

echo "10/14 - Uploading LAION-Aesthetic (1GB)..."
aws s3 sync ~/models/ranking/laion-aesthetic s3://$BUCKET/models/ranking/laion-aesthetic/
echo "LAION-Aesthetic uploaded!"

echo "11/14 - Uploading CLIP-ViT-Large (1.6GB)..."
aws s3 sync ~/models/ranking/clip-vit-large s3://$BUCKET/models/ranking/clip-vit-large/
echo "CLIP-ViT-Large uploaded!"

# SAFETY (500MB)
echo "12/14 - Uploading NudeNet (200MB)..."
aws s3 sync ~/models/safety/nudenet s3://$BUCKET/models/safety/nudenet/
echo "NudeNet uploaded!"

echo "13/14 - Uploading Detoxify (300MB)..."
aws s3 sync ~/models/safety/detoxify s3://$BUCKET/models/safety/detoxify/
echo "Detoxify uploaded!"

# UTILITIES (200MB)
echo "14/14 - Uploading U2-Net (200MB)..."
aws s3 sync ~/models/utilities/u2net s3://$BUCKET/models/utilities/u2net/
echo "U2-Net uploaded!"

echo ""
echo "============================================================"
echo "ALL 14 MODELS UPLOADED TO S3!"
echo "============================================================"

# Verify
echo ""
echo "S3 Summary:"
aws s3 ls s3://$BUCKET/models/ --recursive --summarize --human-readable | tail -3
```

---

## PHASE 4: Create SageMaker Deployment Package

### Create the package

```bash
mkdir -p ~/sagemaker-deploy/code
```

### Create requirements.txt

```bash
cat > ~/sagemaker-deploy/code/requirements.txt << 'EOF'
diffusers>=0.30.0
transformers>=4.44.0
accelerate>=0.33.0
safetensors>=0.4.1
sentencepiece>=0.2.0
protobuf>=4.25.0
Pillow>=10.0.0
opencv-python>=4.8.0
controlnet-aux>=0.0.7
insightface>=0.7.3
onnxruntime-gpu>=1.16.0
realesrgan>=0.3.0
nudenet>=3.0.0
detoxify>=0.5.0
open-clip-torch>=2.24.0
bitsandbytes>=0.41.0
scipy>=1.11.0
numpy>=1.24.3,<2
boto3
EOF
```

### Create inference.py

Copy from your local repo or create directly:

```bash
# OPTION A: Copy from local machine (run on YOUR machine, not EC2)
scp -i your-key.pem \
    "c:/desktop/PhotoGenius AI/aws/sagemaker/model/code/inference.py" \
    ubuntu@<EC2_IP>:~/sagemaker-deploy/code/inference.py

# OPTION B: If already on EC2, the inference.py is in the repo
# (see aws/sagemaker/model/code/inference.py in the repo)
```

### Package and Upload

```bash
cd ~/sagemaker-deploy

# Create tarball (code only ~5KB - models load from S3 at runtime)
tar -czf model.tar.gz code/

# Verify
echo "Package contents:"
tar -tzf model.tar.gz
echo ""
echo "Package size:"
ls -lh model.tar.gz

# Upload
aws s3 cp model.tar.gz s3://photogenius-models-dev/deployment/enterprise-model.tar.gz

# Verify
aws s3 ls s3://photogenius-models-dev/deployment/

echo "Deployment package ready!"
```

---

## PHASE 5: Deploy SageMaker Endpoint

```bash
source ~/download-env/bin/activate

python3 << 'PYEOF'
import boto3
import time

sm = boto3.client("sagemaker", region_name="us-east-1")

ROLE = "arn:aws:iam::288761732313:role/SageMakerExecutionRole"
BUCKET = "photogenius-models-dev"
CONTAINER = "763104351884.dkr.ecr.us-east-1.amazonaws.com/pytorch-inference:2.1.0-gpu-py310"
TIMESTAMP = str(int(time.time()))

MODEL_NAME = f"photogenius-enterprise-{TIMESTAMP}"
CONFIG_NAME = f"photogenius-enterprise-config-{TIMESTAMP}"
ENDPOINT_NAME = "photogenius-production"

# ============================================================
# CHANGE INSTANCE TYPE HERE IF NEEDED
# Options: ml.g5.2xlarge (recommended), ml.g5.xlarge, ml.g6.xlarge
# ============================================================
INSTANCE_TYPE = "ml.g5.2xlarge"

print("=" * 60)
print("DEPLOYING PHOTOGENIUS ENTERPRISE PIPELINE")
print(f"Instance: {INSTANCE_TYPE}")
print("=" * 60)

# Step 1: Create Model
print(f"\nCreating model: {MODEL_NAME}")
sm.create_model(
    ModelName=MODEL_NAME,
    PrimaryContainer={
        "Image": CONTAINER,
        "ModelDataUrl": f"s3://{BUCKET}/deployment/enterprise-model.tar.gz",
        "Environment": {
            "MODELS_S3_BUCKET": BUCKET,
            "SAGEMAKER_PROGRAM": "inference.py",
            "SAGEMAKER_SUBMIT_DIRECTORY": f"s3://{BUCKET}/deployment/enterprise-model.tar.gz",
        },
    },
    ExecutionRoleArn=ROLE,
)
print("Model created!")

# Step 2: Create Endpoint Config
print(f"\nCreating endpoint config: {CONFIG_NAME}")
sm.create_endpoint_config(
    EndpointConfigName=CONFIG_NAME,
    ProductionVariants=[{
        "VariantName": "AllTraffic",
        "ModelName": MODEL_NAME,
        "InstanceType": INSTANCE_TYPE,
        "InitialInstanceCount": 1,
        "ContainerStartupHealthCheckTimeoutInSeconds": 900,
        "ModelDataDownloadTimeoutInSeconds": 900,
    }],
)
print("Endpoint config created!")

# Step 3: Update or Create Endpoint
try:
    sm.update_endpoint(
        EndpointName=ENDPOINT_NAME,
        EndpointConfigName=CONFIG_NAME,
    )
    action = "Updating"
except sm.exceptions.ClientError:
    sm.create_endpoint(
        EndpointName=ENDPOINT_NAME,
        EndpointConfigName=CONFIG_NAME,
    )
    action = "Creating"

print(f"\n{action} endpoint '{ENDPOINT_NAME}' (takes 10-15 minutes)...")

while True:
    resp = sm.describe_endpoint(EndpointName=ENDPOINT_NAME)
    status = resp["EndpointStatus"]

    if status == "InService":
        print(f"\n{'=' * 60}")
        print(f"ENDPOINT READY!")
        print(f"Name: {ENDPOINT_NAME}")
        print(f"Instance: {INSTANCE_TYPE}")
        print(f"{'=' * 60}")
        break
    elif status in ("Failed", "RollbackFailed"):
        reason = resp.get("FailureReason", "Unknown")
        print(f"\nDeployment FAILED: {reason}")
        break
    else:
        print(f"  [{time.strftime('%H:%M:%S')}] {status}")
        time.sleep(30)

PYEOF
```

---

## PHASE 6: Test All Tiers

```bash
source ~/download-env/bin/activate

python3 << 'PYEOF'
import boto3
import json
import base64
import time

runtime = boto3.client("sagemaker-runtime", region_name="us-east-1")
ENDPOINT = "photogenius-production"

print("=" * 60)
print("TESTING PHOTOGENIUS ENTERPRISE PIPELINE")
print("=" * 60)

def test_generation(tier, prompt, description):
    print(f"\n{'=' * 60}")
    print(f"Test: {description}")
    print(f"Tier: {tier}")
    print(f"{'=' * 60}")

    payload = {
        "prompt": prompt,
        "quality_tier": tier,
        "width": 1024,
        "height": 1024,
    }

    start = time.time()

    try:
        response = runtime.invoke_endpoint(
            EndpointName=ENDPOINT,
            ContentType="application/json",
            Body=json.dumps(payload),
        )

        elapsed = time.time() - start
        result = json.loads(response["Body"].read())

        if result.get("status") == "success":
            img_data = base64.b64decode(result["image"])
            filename = f"/home/ubuntu/test_{tier.lower()}.png"
            with open(filename, "wb") as f:
                f.write(img_data)

            print(f"SUCCESS!")
            print(f"  Total time: {elapsed:.1f}s")
            print(f"  Model: {result.get('model')}")
            print(f"  Steps: {result.get('steps')}")
            print(f"  Gen time: {result.get('generation_time')}s")
            print(f"  Saved: {filename}")
        else:
            print(f"FAILED: {result.get('error')}")

    except Exception as e:
        print(f"ERROR: {str(e)}")

# Test 1: FAST (FLUX.1-schnell, ~5s)
# NOTE: First request takes 2-5 min (model loads from S3). Be patient!
print("\nNOTE: First request downloads model from S3 (~23GB). Takes 2-5 minutes.")
print("Subsequent requests are fast (model stays cached in memory).\n")

test_generation(
    "FAST",
    "A majestic lion in golden savanna at sunset, photorealistic, 8k quality",
    "FAST - FLUX.1-schnell (4 steps)"
)

# Test 2: STANDARD (PixArt-Sigma, 20 steps)
test_generation(
    "STANDARD",
    "A professional business card with text 'JOHN SMITH - CEO' in elegant font",
    "STANDARD - PixArt-Sigma (20 steps, text rendering)"
)

# Test 3: PREMIUM (PixArt-Sigma, 50 steps)
test_generation(
    "PREMIUM",
    "A cyberpunk cityscape at night with neon signs reading 'PHOTOGENIUS', rain reflections, ultra detailed",
    "PREMIUM - PixArt-Sigma (50 steps, highest quality)"
)

print("\n" + "=" * 60)
print("ALL TESTS COMPLETE!")
print("=" * 60)
print("\nDownload images to your machine:")
print("  scp -i your-key.pem ubuntu@<IP>:~/test_*.png .")

PYEOF
```

---

## PHASE 7: Stop EC2 (Save Money)

```bash
# Exit EC2
exit

# Stop EC2 from your local machine
aws ec2 stop-instances --instance-ids i-07b66618e018325d5

echo "EC2 stopped! No more charges."
echo ""
echo "Costs while running:"
echo "  SageMaker endpoint: ~\$1.52/hr"
echo "  S3 storage (67GB):  ~\$1.55/month"
echo ""
echo "To save money when not using:"
echo "  aws sagemaker delete-endpoint --endpoint-name photogenius-production"
echo "  Re-deploy takes 10-15 min when needed again"
```

---

## IF INTERNET IS SLOW: Tips

### 1. Use `screen` or `tmux` (Keeps Running if SSH Disconnects)

```bash
# Start a screen session BEFORE downloading
screen -S download

# ... run all download commands inside screen ...

# If SSH disconnects, reconnect and resume:
ssh -i your-key.pem ubuntu@<IP>
screen -r download
```

### 2. Download One Model at a Time

If internet is very slow, download models individually. `huggingface-cli download` auto-resumes:

```bash
# If this gets interrupted:
huggingface-cli download black-forest-labs/FLUX.1-schnell \
  --local-dir ~/models/core/flux-schnell \
  --local-dir-use-symlinks False

# Just run the EXACT same command again - it skips already-downloaded files
```

### 3. Check Download Progress

```bash
# In another terminal/screen window:
watch -n 5 'du -sh ~/models/core/flux-schnell'
```

### 4. If a Single File Is Stuck

```bash
# HuggingFace uses hf_transfer for faster downloads (2-3x faster)
pip install hf_transfer
export HF_HUB_ENABLE_HF_TRANSFER=1

# Now re-run the download command - much faster!
huggingface-cli download black-forest-labs/FLUX.1-schnell \
  --local-dir ~/models/core/flux-schnell \
  --local-dir-use-symlinks False
```

### 5. S3 Upload Stuck

```bash
# aws s3 sync auto-retries. Just run again if it stops:
aws s3 sync ~/models/core/flux-schnell s3://photogenius-models-dev/models/core/flux-schnell/

# For very slow uploads, increase multipart chunk size:
aws configure set default.s3.multipart_chunksize 64MB
```

---

## S3 Directory Structure (Final)

```
s3://photogenius-models-dev/
├── models/
│   ├── core/
│   │   ├── flux-schnell/          (23 GB)
│   │   ├── pixart-sigma/          (12 GB)
│   │   └── instantid/             (2 GB)
│   ├── intelligence/
│   │   └── mixtral-8x7b/          (26 GB)
│   ├── control/
│   │   ├── controlnet-canny/      (1.7 GB)
│   │   ├── controlnet-depth/      (1.7 GB)
│   │   ├── controlnet-openpose/   (1.7 GB)
│   │   └── ip-adapter/            (1 GB)
│   ├── enhancement/
│   │   ├── realesrgan/            (64 MB)
│   │   └── swin2sr/               (3 GB)
│   ├── ranking/
│   │   ├── openclip/              (2 GB)
│   │   ├── laion-aesthetic/        (1 GB)
│   │   └── clip-vit-large/        (1.6 GB)
│   ├── safety/
│   │   ├── nudenet/               (200 MB)
│   │   └── detoxify/              (300 MB)
│   └── utilities/
│       └── u2net/                 (200 MB)
└── deployment/
    └── enterprise-model.tar.gz    (~5 KB)
```

---

## Cost Summary

| Resource | Cost | When |
|----------|------|------|
| **EC2 m5.xlarge (setup only)** | ~$0.19/hr | Only during download/upload |
| **SageMaker ml.g5.2xlarge** | ~$1.52/hr | While endpoint is InService |
| **S3 Storage (~75GB)** | ~$1.75/month | Always |
| **Data Transfer** | ~$0.001/image | Per request |

**Save money:**
- Stop EC2 after uploading (~$0 when stopped)
- Delete SageMaker endpoint when not using: `aws sagemaker delete-endpoint --endpoint-name photogenius-production`
- Re-deploy takes 10-15 min when needed

---

## Backend Connection

In `apps/api/.env.local`:
```
GENERATION_BACKEND=sagemaker
SAGEMAKER_ENDPOINT=photogenius-production
AWS_REGION=us-east-1
S3_BUCKET=photogenius-models-dev
```

Test from local:
```bash
cd apps/api
uvicorn app.main:app --reload --port 8000
curl http://localhost:8000/api/v3/status
```

---

## Quick Reference: Changing SageMaker GPU Instance

If `ml.g5.2xlarge` is unavailable or you want different performance:

```bash
python3 << 'PYEOF'
import boto3, time

sm = boto3.client("sagemaker", region_name="us-east-1")
ROLE = "arn:aws:iam::288761732313:role/SageMakerExecutionRole"
BUCKET = "photogenius-models-dev"
CONTAINER = "763104351884.dkr.ecr.us-east-1.amazonaws.com/pytorch-inference:2.1.0-gpu-py310"
TS = str(int(time.time()))

# ====== CHANGE THIS LINE ======
NEW_INSTANCE = "ml.g6.xlarge"  # or ml.g5.xlarge, ml.g5.4xlarge, etc.
# ===============================

# Create new model
MODEL = f"photogenius-{TS}"
sm.create_model(
    ModelName=MODEL,
    PrimaryContainer={
        "Image": CONTAINER,
        "ModelDataUrl": f"s3://{BUCKET}/deployment/enterprise-model.tar.gz",
        "Environment": {"MODELS_S3_BUCKET": BUCKET, "SAGEMAKER_PROGRAM": "inference.py",
            "SAGEMAKER_SUBMIT_DIRECTORY": f"s3://{BUCKET}/deployment/enterprise-model.tar.gz"},
    },
    ExecutionRoleArn=ROLE,
)

# Create new config with different instance
CONFIG = f"photogenius-config-{TS}"
sm.create_endpoint_config(
    EndpointConfigName=CONFIG,
    ProductionVariants=[{
        "VariantName": "AllTraffic", "ModelName": MODEL,
        "InstanceType": NEW_INSTANCE, "InitialInstanceCount": 1,
        "ContainerStartupHealthCheckTimeoutInSeconds": 900,
        "ModelDataDownloadTimeoutInSeconds": 900,
    }],
)

# Update endpoint (rolling update, no downtime)
sm.update_endpoint(EndpointName="photogenius-production", EndpointConfigName=CONFIG)
print(f"Updating to {NEW_INSTANCE}... (10-15 min)")

while True:
    status = sm.describe_endpoint(EndpointName="photogenius-production")["EndpointStatus"]
    if status == "InService":
        print(f"DONE! Running on {NEW_INSTANCE}")
        break
    elif "Failed" in status:
        print(f"FAILED: {sm.describe_endpoint(EndpointName='photogenius-production').get('FailureReason')}")
        break
    print(f"  [{time.strftime('%H:%M:%S')}] {status}")
    time.sleep(30)

PYEOF
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| EC2 instance type not available | Use m5.xlarge (CPU, always available). No GPU needed for downloading. |
| Download stuck/frozen | Run same command again. `huggingface-cli` auto-resumes. |
| SSH disconnects during download | Use `screen -S download` before starting. Reconnect with `screen -r download`. |
| S3 upload slow | Normal for 67GB. Takes 1-3 hours. Use `aws s3 sync` (resumable). |
| First SageMaker request slow | Expected! First request loads model from S3 (2-5 min). Cached after that. |
| GPU Out of Memory | Reduce image to 768x768. Handler auto-clamps to 1MP max. |
| SageMaker endpoint failed | Check logs: `aws logs tail /aws/sagemaker/Endpoints/photogenius-production --follow` |
| HuggingFace rate limited | Wait 1 hour, then retry. Or install `hf_transfer` for faster downloads. |
| Disk full on EC2 | `df -h /` to check. Need ~80GB free. Delete old files: `rm -rf ~/.cache/huggingface` |
