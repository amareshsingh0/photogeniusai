# 🔧 Deploying Lambda Fix

**Time**: 13:44 UTC  
**Status**: Forcing Lambda code update with --force-upload

---

## The Real Problem:

Old Lambda code has **HARDCODED endpoint names**:

```python
# Line 349 in OLD deployed code
TWO_PASS_ENDPOINT = os.environ.get("SAGEMAKER_TWO_PASS_ENDPOINT", "photogenius-two-pass")
# ❌ Default fallback is "photogenius-two-pass" (doesn't exist!)
```

Even after setting environment variables, the code logic might still use the old function that has these hardcoded defaults.

---

## What We're Doing Now:

```powershell
sam deploy --no-confirm-changeset --force-upload
```

**--force-upload**: Forces CloudFormation to upload and use new Lambda code even if it thinks nothing changed.

This will:

1. Re-upload Lambda zip files
2. Force CloudFormation to update Lambda code
3. Deploy NEW handler.py with correct logic

---

## New Code (will be deployed):

```python
# Line 584
def invoke_sagemaker(prompt, mode, ...):
    SAGEMAKER_ENDPOINT = os.environ.get("SAGEMAKER_ENDPOINT", "photogenius-generation-dev")
    # ✅ Correct default and uses SAGEMAKER_ENDPOINT variable
```

---

## ETA: 5-10 minutes

Deployment includes:

- Uploading 8 Lambda functions
- CloudFormation stack update
- Lambda code refresh

---

## After Deployment:

Test command:

```powershell
curl http://127.0.0.1:3002/api/generate/smart `
  -Method POST `
  -Body '{"prompt":"couple on beach","mode":"ROMANTIC"}' `
  -ContentType "application/json"
```

**Expected Result**: REAL IMAGE (not placeholder!)

---

**Monitoring deployment...**
