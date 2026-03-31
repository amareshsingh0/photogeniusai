# 📥 InstantID Model Download Guide

## Overview

InstantID is a state-of-the-art face identity preservation model that boosts face consistency from **60-70% → 90%+**. This script downloads all required InstantID models from HuggingFace to Modal volumes.

## What Gets Downloaded

### Core InstantID Models (~2-3 GB total)
1. **IP-Adapter weights** (`ip-adapter.bin`) - ~1.5 GB
   - Used for face identity conditioning
   
2. **ControlNet Model** (`ControlNetModel/`)
   - `config.json` - Model configuration
   - `diffusion_pytorch_model.safetensors` - Model weights
   - Used for pose/face structure control

3. **CLIP Image Encoder** (`image_encoder/`)
   - `config.json` - Encoder configuration
   - `pytorch_model.bin` - Encoder weights
   - Used for generating face embeddings

## Usage

### One-Time Setup

```bash
# From ai-pipeline directory
modal run models/download_instantid.py
```

### What Happens

1. **Downloads** all InstantID models from HuggingFace
2. **Saves** to `/models/instantid/` in Modal volume
3. **Commits** volume changes (persists across runs)
4. **Verifies** all files are present

### Expected Output

```
🚀 Starting InstantID model download...
This may take 10-20 minutes depending on your connection.

============================================================
📥 Downloading InstantID Models
============================================================
Repository: InstantX/InstantID
Destination: /models/instantid

📦 Downloading InstantID core models...

  📥 Downloading ip-adapter.bin...
  ✅ Saved to /models/instantid/ip-adapter.bin (1500.0 MB)

  📥 Downloading ControlNetModel/config.json...
  ✅ Saved to /models/instantid/ControlNetModel/config.json (0.1 MB)

  📥 Downloading ControlNetModel/diffusion_pytorch_model.safetensors...
  ✅ Saved to /models/instantid/ControlNetModel/diffusion_pytorch_model.safetensors (800.0 MB)

📦 Downloading CLIP image encoder...

  📥 Downloading image_encoder/config.json...
  ✅ Saved to /models/instantid/image_encoder/config.json (0.1 MB)

  📥 Downloading image_encoder/pytorch_model.bin...
  ✅ Saved to /models/instantid/image_encoder/pytorch_model.bin (600.0 MB)

💾 Committing changes to volume...
✅ Volume committed successfully

🔍 Verifying downloaded files...
  ✅ instantid/ip-adapter.bin (1500.0 MB)
  ✅ instantid/ControlNetModel/config.json (0.1 MB)
  ✅ instantid/ControlNetModel/diffusion_pytorch_model.safetensors (800.0 MB)
  ✅ instantid/image_encoder/config.json (0.1 MB)
  ✅ instantid/image_encoder/pytorch_model.bin (600.0 MB)

============================================================
✅ InstantID Models Download Complete!
============================================================
Total size: 2.90 GB
Location: /models/instantid/

🎉 Download Complete!
Status: success
Location: /models/instantid
Total Size: 2.90 GB
Files: 5 files downloaded
```

## File Structure

After download, your Modal volume will have:

```
/models/
└── instantid/
    ├── ip-adapter.bin                          (~1.5 GB)
    ├── ControlNetModel/
    │   ├── config.json
    │   └── diffusion_pytorch_model.safetensors (~800 MB)
    └── image_encoder/
        ├── config.json
        └── pytorch_model.bin                   (~600 MB)
```

## Integration with Identity Engine

Once downloaded, these models can be used in `identity_engine.py`:

```python
# In identity_engine.py load_models() method:
from diffusers import ControlNetModel
from transformers import CLIPImageProcessor, CLIPVisionModelWithProjection

# Load InstantID ControlNet
controlnet_path = "/models/instantid/ControlNetModel"
controlnet = ControlNetModel.from_pretrained(
    controlnet_path,
    torch_dtype=torch.float16
)

# Load CLIP image encoder
clip_path = "/models/instantid/image_encoder"
clip_image_processor = CLIPImageProcessor.from_pretrained(clip_path)
clip_image_encoder = CLIPVisionModelWithProjection.from_pretrained(
    clip_path,
    torch_dtype=torch.float16
)

# Load IP-Adapter
ip_adapter_path = "/models/instantid/ip-adapter.bin"
# Use with diffusers IP-Adapter pipeline
```

## Troubleshooting

### Download Fails

1. **Check internet connection**
   ```bash
   # Test HuggingFace access
   curl https://huggingface.co
   ```

2. **Verify Modal volume exists**
   ```bash
   modal volume list
   ```

3. **Resume download** (automatic)
   - The script uses `resume_download=True`
   - If interrupted, just run again

### Files Missing After Download

1. **Check volume commit**
   - Script automatically commits volume
   - Verify with: `modal volume list`

2. **Re-run download**
   - Script checks for existing files
   - Safe to run multiple times

### Out of Space

- InstantID models require ~3 GB
- Check Modal volume size: `modal volume list`
- Free up space if needed

## Next Steps

After downloading InstantID models:

1. **Integrate into Identity Engine**
   - Update `identity_engine.py` to load InstantID models
   - Add IP-Adapter to generation pipeline

2. **Test face consistency**
   - Generate images with InstantID enabled
   - Verify 90%+ face similarity

3. **Save face embeddings**
   - Extract embeddings during training
   - Reuse for faster generation

## Status

✅ **Download script created**
✅ **Ready to run**
⚠️ **One-time setup required**

Run `modal run models/download_instantid.py` to download models!
