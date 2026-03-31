# FastAPI Development Setup

## Quick Start

```bash
# Install dependencies (uses minimal requirements by default)
pnpm run dev

# Or install full requirements manually
cd apps/api
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
```

## Requirements Files

### `requirements-minimal.txt` (Default for `pnpm run dev`)

**Lightweight setup** - FastAPI core + essential packages only.

**Excludes:**
- `torch`, `diffusers`, `transformers` - Only needed on Modal GPU workers
- `tf-keras`, `deepface` - Heavy TensorFlow dependencies (~2GB)
- `nudenet` - Can be slow to install

**Why:** GPU work happens on Modal, so local API doesn't need these heavy ML packages.

### `requirements.txt` (Full)

**Complete setup** - All packages including ML libraries.

**Use when:**
- Running safety checks locally
- Testing ML features
- Full local development

**Note:** TensorFlow packages can timeout during installation. If this happens:
1. Use `requirements-minimal.txt` for faster setup
2. Install full requirements separately: `pip install -r requirements.txt`
3. Or install specific packages as needed

## DeepFace (Optional)

DeepFace is used for age estimation but pulls in TensorFlow (~2GB download).

**Status:** Made optional - API works without it.

**Behavior:**
- If DeepFace not installed: Age estimation skipped locally
- Safety checks still happen on Modal GPU workers
- API continues to work normally

**Install if needed:**
```bash
pip install deepface tf-keras
```

## Troubleshooting

### PyPI Timeout Errors

**Problem:** `tensorflow-io-gcs-filesystem` times out during installation.

**Solution:**
1. Use minimal requirements: `pnpm run dev` (uses `requirements-minimal.txt` by default)
2. Install full requirements separately when needed
3. Increase timeout: `pip install --default-timeout=200 -r requirements.txt`

### DeepFace Import Errors

**Problem:** `ImportError: cannot import name 'DeepFace'`

**Solution:**
- This is expected if using minimal requirements
- Age estimation is disabled locally (checks happen on Modal)
- API will work normally

### Missing ML Packages

**Problem:** Errors about missing `torch`, `diffusers`, etc.

**Solution:**
- These are only needed on Modal GPU workers
- Local API doesn't need them
- If you need them: `pip install torch diffusers transformers`

## Environment Variables

See `.env.local` for configuration. Key variables:

```env
# Modal (for GPU workers)
MODAL_TOKEN_ID=...
MODAL_TOKEN_SECRET=...
MODAL_USERNAME=...

# Database
DATABASE_URL=...

# Storage
S3_BUCKET_NAME=...
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
```

## Development Workflow

1. **Start services:**
   ```bash
   pnpm run dev  # Starts API + Web + AI Service
   ```

2. **API runs on:** http://127.0.0.1:8000

3. **API docs:** http://127.0.0.1:8000/docs

4. **GPU work:** Happens on Modal (no local GPU needed)

## Notes

- ✅ FastAPI works with minimal requirements
- ✅ GPU generation happens on Modal (not local)
- ✅ Safety checks happen on Modal (not local)
- ✅ DeepFace optional (safety checks on Modal)
- ⚠️ Full requirements can timeout (TensorFlow is huge)
