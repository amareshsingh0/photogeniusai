# 🚀 Quick Start - Modal Deployment

## Prerequisites

1. **Modal CLI installed and authenticated:**
   ```bash
   pip install modal
   modal token new
   ```

2. **HuggingFace Token in `.env.local`:**
   - File: `apps/api/.env.local`
   - Add: `HUGGINGFACE_TOKEN=hf_your_token_here`

## Step 1: Create Modal Secrets

**Run the setup script:**
```powershell
# From project root
.\scripts\setup-modal-secrets.ps1
```

This will:
- Read `HUGGINGFACE_TOKEN` from `apps/api/.env.local`
- Create Modal secret `huggingface` in Modal cloud
- Verify the secret was created

**Or manually:**
```bash
modal secret create huggingface HUGGINGFACE_TOKEN=hf_your_token_here
```

## Step 2: Deploy Services

```bash
cd ai-pipeline

# Deploy all services
modal deploy services/generation_service.py
modal deploy services/lora_trainer.py
modal deploy services/safety_service.py
```

## Step 3: Verify Deployment

```bash
# List all apps
modal app list

# Check logs
modal app logs photogenius-generation
```

## Troubleshooting

### Secret Not Found Error

**Error:**
```
Secret 'huggingface' not found in environment 'main'
```

**Solution:**
1. Run `.\scripts\setup-modal-secrets.ps1` to create the secret
2. Or manually: `modal secret create huggingface HUGGINGFACE_TOKEN=hf_xxx`
3. Verify: `modal secret list`

### Token Invalid

**Error:**
```
401 Unauthorized from HuggingFace
```

**Solution:**
1. Verify token at https://huggingface.co/settings/tokens
2. Update secret: `modal secret create huggingface HUGGINGFACE_TOKEN=hf_new_token`

---

**Next:** See `DEPLOYMENT.md` for detailed deployment guide.
