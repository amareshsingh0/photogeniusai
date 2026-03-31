# 🔐 Modal Secrets Setup Guide

## Required Secrets

### 1. HuggingFace Token (CRITICAL) ⚠️

**Why Required:**
- Bypasses rate limits for model downloads
- Required for gated models
- Essential for CI/CD and production deployments
- Without it: Downloads may fail silently, CI/CD will break

**Get Token:**
1. Go to https://huggingface.co/settings/tokens
2. Create new token with "Read" access
3. Copy token (starts with `hf_`)

**Create Secret:**

**Option 1: Using PowerShell Script (Recommended)**
```powershell
# From project root
.\scripts\setup-modal-secrets.ps1
```
This script automatically reads `HUGGINGFACE_TOKEN` from `apps/api/.env.local` and creates the Modal secret.

**Option 2: Manual Command**
```bash
modal secret create huggingface HUGGINGFACE_TOKEN=hf_your_token_here
```

**Note:** The token in `.env.local` is for local development. Modal secrets are separate and must be created in Modal's cloud.

**Verify:**
```bash
modal secret list
# Should show: huggingface
```

**Test Token:**
```bash
curl -H "Authorization: Bearer hf_your_token_here" https://huggingface.co/api/whoami
```

---

### 2. AWS Credentials (Optional)

**When Needed:**
- S3 access for training images
- Uploading generated images to S3

**Create Secret:**
```bash
modal secret create aws-credentials \
  AWS_ACCESS_KEY_ID=your_access_key \
  AWS_SECRET_ACCESS_KEY=your_secret_key
```

---

## Secret Usage in Code

Secrets are automatically injected as environment variables:

```python
import os

# HuggingFace token
hf_token = os.environ.get("HUGGINGFACE_TOKEN") or os.environ.get("HF_TOKEN")

# AWS credentials
aws_key = os.environ.get("AWS_ACCESS_KEY_ID")
aws_secret = os.environ.get("AWS_SECRET_ACCESS_KEY")
```

---

## Troubleshooting

### Secret Not Found

**Error:**
```
[ERROR] HUGGINGFACE_TOKEN not found
```

**Solution:**
1. Verify secret exists: `modal secret list`
2. Check secret name matches: `huggingface` (lowercase)
3. Recreate if needed: `modal secret create huggingface HUGGINGFACE_TOKEN=hf_xxx`

### Token Invalid

**Error:**
```
[ERROR] 401 Unauthorized from HuggingFace
```

**Solution:**
1. Verify token at https://huggingface.co/settings/tokens
2. Check token has "Read" access
3. Regenerate token if expired
4. Update secret: `modal secret create huggingface HUGGINGFACE_TOKEN=hf_new_token`

---

## CI/CD Setup

### GitHub Actions

```yaml
- name: Create Modal Secret
  run: |
    modal secret create huggingface HUGGINGFACE_TOKEN=${{ secrets.HUGGINGFACE_TOKEN }}
  env:
    MODAL_TOKEN_ID: ${{ secrets.MODAL_TOKEN_ID }}
    MODAL_TOKEN_SECRET: ${{ secrets.MODAL_TOKEN_SECRET }}
```

### GitLab CI

```yaml
create_secret:
  script:
    - modal secret create huggingface HUGGINGFACE_TOKEN=$HUGGINGFACE_TOKEN
  variables:
    MODAL_TOKEN_ID: $MODAL_TOKEN_ID
    MODAL_TOKEN_SECRET: $MODAL_TOKEN_SECRET
```

---

## Best Practices

1. ✅ **Never commit tokens** to git
2. ✅ **Use Modal secrets** for all sensitive data
3. ✅ **Rotate tokens** regularly (every 90 days)
4. ✅ **Use read-only tokens** when possible
5. ✅ **Test secrets** before deploying

---

**Last Updated:** 2026-01-27
