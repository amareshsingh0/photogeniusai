# Fixes Applied

## Issue 1: NameError - logger not defined ✅ FIXED

**Problem:**
```python
# Logger was used before being defined
try:
    from deepface import DeepFace
except ImportError:
    logger.warning(...)  # ❌ logger not defined yet
logger = logging.getLogger(__name__)  # Defined after use
```

**Fix:**
- Moved `logger = logging.getLogger(__name__)` before the try/except block
- Now logger is available when handling import errors

## Issue 2: TensorFlow/Protobuf Dependency Conflict ✅ FIXED

**Problem:**
- TensorFlow 2.20.0 requires `protobuf>=5.28.0`
- Modal 0.64.0 requires `protobuf<5.0`
- Conflict causes import errors even when TensorFlow is optional

**Fix:**
- Updated exception handling to catch `Exception` (not just `ImportError`)
- Catches protobuf/TensorFlow errors during import
- Gracefully disables DeepFace if dependencies conflict
- Updated Modal version: `modal>=0.65.0` (0.64.0 was yanked)

## Issue 3: Python-dotenv Version Conflict ✅ FIXED

**Problem:**
- `deepface` requires `python-dotenv>=1.0.1`
- Requirements had `python-dotenv==1.0.0`

**Fix:**
- Updated to `python-dotenv>=1.0.1` in both `requirements.txt` and `requirements-minimal.txt`

## Issue 4: Missing Dependencies in Minimal Requirements ✅ FIXED

**Problem:**
- `age_estimator.py` uses `numpy` and `PIL` but they weren't in minimal requirements

**Fix:**
- Added `numpy>=1.26.0` and `pillow>=10.0.0` to `requirements-minimal.txt`
- Made imports optional with graceful fallback

## Issue 5: TensorFlow oneDNN Warnings ✅ FIXED

**Problem:**
- TensorFlow installed globally prints oneDNN warnings even when not used
- Warning: "oneDNN custom operations are on. You may see slightly different numerical results..."

**Fix:**
- Added `TF_CPP_MIN_LOG_LEVEL=3` and `TF_ENABLE_ONEDNN_OPTS=0` environment variables
- Set in `app/main.py` and `app/services/safety/age_estimator.py` before any imports
- Suppresses TensorFlow logging and oneDNN warnings

## Issue 6: Misleading Warning Messages ✅ FIXED

**Problem:**
- Warning said "DeepFace/numpy not available" even when numpy WAS available
- Only DeepFace was missing (expected with minimal requirements)

**Fix:**
- Updated warning logic to only warn about numpy if it's actually missing
- Changed DeepFace unavailable message to `logger.debug()` (expected behavior)
- Only shows warning if numpy is also missing

## Summary

All issues fixed:
1. ✅ Logger order corrected
2. ✅ TensorFlow import errors handled gracefully
3. ✅ Dependency conflicts resolved
4. ✅ Modal version updated
5. ✅ Minimal requirements updated
6. ✅ TensorFlow warnings suppressed
7. ✅ Warning messages clarified

The API should now start cleanly without unnecessary warnings, even if TensorFlow/DeepFace have dependency conflicts.
