# 📍 GPU Workers - Command Setup Guide

## 🎯 Where to Run Commands

### ✅ Option 1: From `apps/api` Folder (Recommended)

**Navigate to API folder first:**
```powershell
cd "C:\desktop\PhotoGenius AI\apps\api"
```

#### 1. Install Dependencies
```powershell
# Make sure you're in apps/api folder
pip install -r requirements.txt
```

#### 2. Configure Modal.com

```powershell
# Still in apps/api folder
# Install Modal CLI (if not already installed)
pip install modal

# Login to Modal (creates token)
modal token new

# Deploy workers (path is relative to apps/api)
modal deploy app/workers/modal_worker.py
```

#### 3. Run Tests

```powershell
# Still in apps/api folder
pytest app/tests/test_worker_manager.py -v
```

---

### ✅ Option 2: From Project Root

**Navigate to project root:**
```powershell
cd "C:\desktop\PhotoGenius AI"
```

#### 1. Install Dependencies
```powershell
# From project root
cd apps/api
pip install -r requirements.txt
cd ../..
```

#### 2. Configure Modal.com

```powershell
# From project root
cd apps/api
pip install modal
modal token new
modal deploy apps/api/app/workers/modal_worker.py
cd ../..
```

#### 3. Run Tests

```powershell
# From project root
cd apps/api
pytest app/tests/test_worker_manager.py -v
cd ../..
```

---

## 📋 Complete Setup Steps

### Step 1: Install Python Dependencies

```powershell
# Navigate to API folder
cd "C:\desktop\PhotoGenius AI\apps\api"

# Install all dependencies (includes modal)
pip install -r requirements.txt
```

### Step 2: Configure Modal.com

```powershell
# Still in apps/api folder

# Install Modal CLI (if not already installed)
pip install modal

# Create Modal token (interactive - will ask for credentials)
modal token new

# This will:
# 1. Open browser for authentication
# 2. Save token to ~/.modal/token.json
# 3. Set MODAL_TOKEN_ID and MODAL_TOKEN_SECRET
```

**After `modal token new`, add to `apps/api/.env.local`:**
```bash
MODAL_TOKEN_ID=your_token_id_here
MODAL_TOKEN_SECRET=your_token_secret_here
```

### Step 3: Deploy Modal Workers

```powershell
# Still in apps/api folder

# Deploy the worker (path relative to apps/api)
modal deploy app/workers/modal_worker.py

# OR from project root:
# modal deploy apps/api/app/workers/modal_worker.py
```

**Expected Output:**
```
✓ Created objects.
✓ Created function generate_image_gpu
✓ Created function train_lora_gpu
✓ Deployed app photogenius-ai-workers
```

### Step 4: Run Tests

```powershell
# Still in apps/api folder

# Run worker manager tests
pytest app/tests/test_worker_manager.py -v

# Run all worker tests
pytest app/tests/ -k worker -v
```

---

## 🔍 Verify Installation

### Check Modal Installation

```powershell
cd "C:\desktop\PhotoGenius AI\apps\api"

# Check if modal is installed
python -c "import modal; print('✅ Modal installed')"

# Check Modal token
modal token list
```

### Check Deployment

```powershell
# List deployed apps
modal app list

# Check app logs
modal app logs photogenius-ai-workers
```

### Test Worker Manager

```powershell
# Run tests
pytest app/tests/test_worker_manager.py -v

# Expected output:
# test_initialize_manager PASSED
# test_statistics PASSED
# test_health_check PASSED
# ...
```

---

## 🚨 Common Issues

### Issue 1: "modal: command not found"

**Solution:**
```powershell
cd "C:\desktop\PhotoGenius AI\apps\api"
pip install modal
```

### Issue 2: "ModuleNotFoundError: No module named 'app'"

**Solution:**
- Make sure you're in `apps/api` folder
- Or use absolute path: `modal deploy "C:\desktop\PhotoGenius AI\apps\api\app\workers\modal_worker.py"`

### Issue 3: "Modal token not found"

**Solution:**
```powershell
modal token new
# Then add to .env.local:
# MODAL_TOKEN_ID=...
# MODAL_TOKEN_SECRET=...
```

### Issue 4: "pytest: command not found"

**Solution:**
```powershell
cd "C:\desktop\PhotoGenius AI\apps\api"
pip install pytest pytest-asyncio
```

---

## 📝 Quick Reference

### From `apps/api` Folder (Recommended)

```powershell
# 1. Install
cd "C:\desktop\PhotoGenius AI\apps\api"
pip install -r requirements.txt

# 2. Modal setup
pip install modal
modal token new
modal deploy app/workers/modal_worker.py

# 3. Test
pytest app/tests/test_worker_manager.py -v
```

### From Project Root

```powershell
# 1. Install
cd "C:\desktop\PhotoGenius AI"
cd apps/api
pip install -r requirements.txt
cd ../..

# 2. Modal setup
cd apps/api
pip install modal
modal token new
modal deploy apps/api/app/workers/modal_worker.py
cd ../..

# 3. Test
cd apps/api
pytest app/tests/test_worker_manager.py -v
cd ../..
```

---

## ✅ Summary

**Recommended Approach:**
1. Always work from `apps/api` folder
2. All paths are relative to `apps/api`
3. Modal commands work from `apps/api`
4. pytest commands work from `apps/api`

**Commands:**
```powershell
cd "C:\desktop\PhotoGenius AI\apps\api"
pip install -r requirements.txt
modal token new
modal deploy app/workers/modal_worker.py
pytest app/tests/test_worker_manager.py -v
```

---

**Last Updated**: After implementing GPU workers
