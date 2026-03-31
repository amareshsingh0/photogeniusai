# 🔧 Orchestrator Fix - FastAPI Required

## Issue

The orchestrator web endpoint requires FastAPI to be installed in the image. Error:
```
ConflictError: Web endpoint Functions require `FastAPI` to be installed in their Image.
```

## Fix Applied ✅

Added `fastapi[standard]` to `orchestrator_image`:

```python
orchestrator_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "anthropic>=0.34.0",
        "pydantic>=2.0.0",
        "httpx>=0.25.0",
        "fastapi[standard]",  # Required for web endpoints
    )
)
```

## Testing

The test function should work now:

```bash
modal run services/orchestrator.py::test_orchestrator
```

**Note**: The web endpoint might still show an error if Modal cached the old image. The test function (which doesn't use the web endpoint) should work fine.

## If Web Endpoint Still Fails

If you need the web endpoint and it still fails:

1. **Clear Modal cache** (if possible) or wait for cache to expire
2. **Deploy explicitly**:
   ```bash
   modal deploy services/orchestrator.py
   ```
3. **Or comment out the web endpoint** temporarily if not needed:
   ```python
   # @modal.fastapi_endpoint(method="POST")
   # def orchestrate_web(item: dict):
   #     ...
   ```

## Status

✅ FastAPI added to orchestrator image
✅ Test function should work
⚠️ Web endpoint may need image rebuild (Modal cache)

The orchestrator can be tested via the test function without the web endpoint.
