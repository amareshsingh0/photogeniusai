# 🐛 Bug Fix: IndexError in Generation Service

## Issue

**Error:**
```
IndexError: list index out of range
File "/root/generation_service.py", line 269, in generate_images
    print(f"   2nd:  Total score = {best_candidates[1]['scores']['total']:.1f}")
```

**Root Cause:**
- Code always tries to access `best_candidates[1]` (2nd best image)
- But if only 1 candidate is generated, `best_candidates` only has 1 element
- This happens when `num_candidates=1` is requested

**Example:**
- User requests: `num_candidates: 1`
- Code generates: 1 candidate ✅
- Code tries to select: "top 2 images" ❌
- Code tries to print: `best_candidates[1]` ❌ (IndexError)

---

## Fix Applied ✅

**File:** `ai-pipeline/services/generation_service.py`

**Changes:**
1. Dynamic selection: `min(2, len(scored_candidates))` instead of hardcoded `[:2]`
2. Conditional printing: Only print 2nd best if it exists
3. Dynamic message: "Selected top N image(s)" based on actual count

**Before:**
```python
best_candidates = scored_candidates[:2]
print(f"[OK] Selected top 2 images")
print(f"   Best: Total score = {best_candidates[0]['scores']['total']:.1f}")
print(f"   2nd:  Total score = {best_candidates[1]['scores']['total']:.1f}")  # ❌ Crashes if only 1
```

**After:**
```python
num_to_return = min(2, len(scored_candidates))
best_candidates = scored_candidates[:num_to_return]
print(f"[OK] Selected top {num_to_return} image{'s' if num_to_return > 1 else ''}")
if len(best_candidates) > 0:
    print(f"   Best: Total score = {best_candidates[0]['scores']['total']:.1f}")
if len(best_candidates) > 1:  # ✅ Safe check
    print(f"   2nd:  Total score = {best_candidates[1]['scores']['total']:.1f}")
```

---

## Testing

**Test Case 1: Single Candidate**
- Input: `num_candidates: 1`
- Expected: Returns 1 image, no crash ✅

**Test Case 2: Multiple Candidates**
- Input: `num_candidates: 4`
- Expected: Returns top 2 images ✅

**Test Case 3: Edge Case**
- Input: `num_candidates: 0` (shouldn't happen, but handled)
- Expected: Returns empty list ✅

---

## Deployment

**Redeploy the service:**
```bash
cd ai-pipeline
modal deploy services/generation_service.py
```

**Verify:**
- Test with `num_candidates: 1` - should work ✅
- Test with `num_candidates: 4` - should return top 2 ✅

---

**Status:** ✅ Fixed and ready to deploy
