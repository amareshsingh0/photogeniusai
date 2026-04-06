# 🔧 Platform Attribute Fix

**Issue:** `'StreamRequest' object has no attribute 'platform'`
**Date:** April 7, 2026
**Status:** ✅ FIXED

---

## 🐛 Problem

Quality Critic was failing with:
```
[stream][788815c5] Quality Critic failed (non-fatal): 'StreamRequest' object has no attribute 'platform'
```

**Root Cause:** `req.platform` doesn't exist in StreamRequest model

**Affected Lines:**
- Line 504: critique_1 call
- Line 589: critique_2 call

---

## ✅ Solution

**Changed from:**
```python
platform=req.platform or "instagram",
```

**Changed to:**
```python
platform=getattr(req, 'platform', 'instagram'),
```

**Why getattr?**
- Safely checks if attribute exists
- Returns default value ('instagram') if not found
- No AttributeError thrown

---

## 📝 Changes Made

**File:** `apps/api/app/api/v1/endpoints/generate_stream.py`

**Line 504:**
```python
critique_1 = await critic.critique(
    image_url=raw_hero_url,
    creative_bible=creative_bible,
    design_brief=design_brief_for_critic,
    platform=getattr(req, 'platform', 'instagram'),  # ✅ FIXED
    revision_cycle=0,
)
```

**Line 589:**
```python
critique_2 = await critic.critique(
    image_url=image_2_url,
    creative_bible=creative_bible,
    design_brief=design_brief_for_critic,
    platform=getattr(req, 'platform', 'instagram'),  # ✅ FIXED
    revision_cycle=1,
)
```

---

## ✅ Verification

```bash
# Syntax check passed
python -m py_compile generate_stream.py
# No errors ✅

# Both fixes in place
grep "platform=getattr" generate_stream.py
# Line 504 ✅
# Line 589 ✅
```

---

## 🚀 Deployment

### Push to GitHub:
```bash
git add apps/api/app/api/v1/endpoints/generate_stream.py
git commit -m "Fix: Handle missing platform attribute in StreamRequest

- Use getattr() to safely check for req.platform
- Default to 'instagram' if not present
- Fixes Quality Critic AttributeError"
git push origin main
```

### On Ubuntu Server:
```bash
cd /home/ubuntu/PhotoGenius-AI
git pull origin main
pm2 restart photogenius-api
```

---

## 🎯 Expected Behavior After Fix

**Before (Error):**
```
[stream][788815c5] Quality Critic failed (non-fatal): 'StreamRequest' object has no attribute 'platform'
```

**After (Working):**
```
[stream][abc123] Quality review: Image 1/2
[stream][abc123] Image 1: score=8.2, verdict=REVISE, gates=9/10
[stream][abc123] Image 1 REVISE - generating Image 2
[stream][abc123] Image 2: score=8.7, verdict=APPROVED
```

---

**FIXED! Ready to push! 🚀**
