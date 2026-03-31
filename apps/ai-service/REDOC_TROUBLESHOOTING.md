# ReDoc Troubleshooting Guide

If ReDoc page is not opening or not displaying properly, try these solutions:

## Quick Fixes

### 1. Clear Browser Cache
- Press `Ctrl + Shift + Delete` (Windows) or `Cmd + Shift + Delete` (Mac)
- Clear cached images and files
- Reload the page: `http://localhost:8001/redoc`

### 2. Check Browser Console
- Open browser DevTools (`F12`)
- Go to Console tab
- Look for JavaScript errors
- Common issues:
  - CORS errors
  - CDN loading failures
  - Network errors

### 3. Try Different Browser
- Test in Chrome, Firefox, or Edge
- Some browsers block CDN resources

### 4. Check if Server is Running
```bash
curl http://localhost:8001/health
```

### 5. Verify OpenAPI JSON
```bash
curl http://localhost:8001/openapi.json
```
Should return valid JSON.

## Common Issues

### Issue: ReDoc Shows Blank Page

**Solution 1: Check Browser Console**
- Open DevTools (F12)
- Check Console for errors
- Check Network tab for failed requests

**Solution 2: Disable Browser Extensions**
- Ad blockers might block CDN resources
- Try incognito/private mode

**Solution 3: Check CDN Access**
- ReDoc uses: `https://cdn.jsdelivr.net/npm/redoc@next/bundles/redoc.standalone.js`
- If blocked, you may need to:
  - Allow the CDN in your firewall
  - Use a VPN
  - Host ReDoc locally

### Issue: "ReDoc requires Javascript" Message

**Solution:**
- Enable JavaScript in your browser
- Check if any extensions are blocking JavaScript

### Issue: CORS Errors

**Solution:**
- The CORS middleware is already configured
- If you see CORS errors, check the `_CORS_ORIGINS` list in `app/main.py`
- Add your origin if needed

## Alternative: Use Swagger UI

If ReDoc doesn't work, use Swagger UI instead:
```
http://localhost:8001/docs
```

## Manual Test

Test ReDoc HTML directly:
```bash
# Get ReDoc HTML
curl http://localhost:8001/redoc

# Get OpenAPI JSON
curl http://localhost:8001/openapi.json > openapi.json

# Validate JSON
python -m json.tool openapi.json
```

## Verify Configuration

Check `apps/ai-service/app/main.py`:
```python
app = FastAPI(
    title="PhotoGenius AI Service",
    version="0.1.0",
    docs_url="/docs",      # Swagger UI
    redoc_url="/redoc",    # ReDoc
    openapi_url="/openapi.json",
)
```

## Still Not Working?

1. **Restart the server:**
   ```bash
   # Stop current server (Ctrl+C)
   # Then restart:
   pnpm --filter @photogenius/ai-service dev
   ```

2. **Check server logs** for errors

3. **Try accessing via IP instead of localhost:**
   ```
   http://127.0.0.1:8001/redoc
   ```

4. **Check firewall/antivirus** - might be blocking CDN

5. **Test with curl:**
   ```bash
   curl -v http://localhost:8001/redoc
   ```

## Expected Behavior

When ReDoc works correctly, you should see:
- Clean, readable API documentation
- All endpoints listed
- Request/response schemas
- Try it out functionality (if enabled)

If you see a blank page or errors, check the browser console for specific error messages.
