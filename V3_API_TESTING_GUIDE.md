# 🧪 V3 API Testing Guide - PhotoGenius AI

**Date**: February 6, 2026
**Status**: ✅ Ready for Testing
**API Version**: 3.0.0

---

## 🚀 Quick Start

### 1. Start the Server

```bash
cd apps/api
uvicorn app.main:app --reload --port 8000
```

Server will be available at: `http://localhost:8000`
API Docs: `http://localhost:8000/docs`

---

## 📡 API Endpoints

### Base URL
```
http://localhost:8000/api/v3
```

---

## 1️⃣ Smart Generation

### POST `/api/v3/generate`

Main endpoint for AI-powered smart generation.

**Features:**
- ✅ Auto mode detection (REALISM, CINEMATIC, ANIME, FANTASY, CREATIVE)
- ✅ Auto category detection (portrait, landscape, product, etc.)
- ✅ Auto prompt enhancement
- ✅ Quality tier routing (FAST/STANDARD/PREMIUM)
- ✅ Quality scoring

**Request:**
```json
{
  "prompt": "professional headshot of a businesswoman",
  "quality": "STANDARD",
  "width": 1024,
  "height": 1024,
  "enhancement_level": "standard",
  "use_two_pass": false,
  "use_identity": null,
  "user_id": "user_123"
}
```

**Test with curl:**
```bash
curl -X POST http://localhost:8000/api/v3/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "professional headshot of a businesswoman",
    "quality": "STANDARD",
    "width": 1024,
    "height": 1024,
    "enhancement_level": "standard"
  }'
```

**Response:**
```json
{
  "request_id": "gen_abc123",
  "success": true,
  "image_url": "data:image/png;base64,...",
  "orchestration": {
    "detected_mode": "REALISM",
    "detected_category": "portrait",
    "enhancement_level": "standard",
    "used_two_pass": false,
    "used_identity": false,
    "total_time": 25.5,
    "services_used": [
      "mode_detector",
      "category_detector",
      "prompt_enhancer",
      "generation_service",
      "quality_scorer"
    ]
  },
  "quality_scores": {
    "overall_score": 0.85,
    "aesthetic_score": 0.88,
    "technical_score": 0.82,
    "prompt_adherence": 0.85
  },
  "metadata": {
    "request_time": "2026-02-06T10:30:00Z",
    "total_time": 25.5
  }
}
```

**Enhancement Levels:**
- `simple` - Basic enhancement
- `standard` - Smart enhancement with mode + category
- `advanced` - Universal multi-domain enhancement
- `cinematic` - Movie-quality enhancement

**Test All Quality Tiers:**

```bash
# FAST tier (~3-5s)
curl -X POST http://localhost:8000/api/v3/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "sunset landscape", "quality": "FAST"}'

# STANDARD tier (~25s)
curl -X POST http://localhost:8000/api/v3/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "sunset landscape", "quality": "STANDARD"}'

# PREMIUM tier (~50s)
curl -X POST http://localhost:8000/api/v3/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "sunset landscape", "quality": "PREMIUM"}'
```

**Test Enhancement Levels:**

```bash
# Cinematic enhancement
curl -X POST http://localhost:8000/api/v3/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "warrior in battle",
    "quality": "PREMIUM",
    "enhancement_level": "cinematic"
  }'

# Advanced enhancement
curl -X POST http://localhost:8000/api/v3/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "product showcase",
    "quality": "STANDARD",
    "enhancement_level": "advanced"
  }'
```

---

## 2️⃣ Two-Pass Generation

### POST `/api/v3/generate/two-pass`

Preview + full quality workflow for better UX.

**Workflow:**
1. Generate fast preview (SDXL-Turbo, 3-5s)
2. Show preview to user immediately
3. Generate full quality (SDXL-Base or Base+Refiner, 25-50s)
4. Replace preview with full quality

**Request:**
```json
{
  "prompt": "cinematic shot of city at night",
  "quality": "PREMIUM",
  "width": 1920,
  "height": 1080,
  "skip_preview": false
}
```

**Test with curl:**
```bash
curl -X POST http://localhost:8000/api/v3/generate/two-pass \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "cinematic shot of city at night",
    "quality": "PREMIUM",
    "width": 1920,
    "height": 1080
  }'
```

**Response:**
```json
{
  "preview": {
    "success": true,
    "image_url": "data:image/png;base64,...",
    "generation_time": 3.5,
    "pass": 1
  },
  "full": {
    "success": true,
    "image_url": "data:image/png;base64,...",
    "generation_time": 48.2,
    "pass": 2
  },
  "metadata": {
    "total_time": 51.7,
    "preview_time": 3.5,
    "full_time": 48.2,
    "used_two_pass": true,
    "quality_tier": "PREMIUM"
  }
}
```

---

## 3️⃣ Identity Management

### POST `/api/v3/identity/create`

Create reusable identity from reference photos.

**Requirements:**
- 5-20 high-quality reference photos
- Clear, well-lit face shots
- Consistent person across all photos

**Request:**
```json
{
  "photos": [
    "https://example.com/photo1.jpg",
    "https://example.com/photo2.jpg",
    "data:image/png;base64,...",
    "..."
  ],
  "identity_name": "John Doe",
  "user_id": "user_123"
}
```

**Test with curl:**
```bash
curl -X POST http://localhost:8000/api/v3/identity/create \
  -H "Content-Type: application/json" \
  -d '{
    "photos": [
      "https://example.com/photo1.jpg",
      "https://example.com/photo2.jpg",
      "https://example.com/photo3.jpg",
      "https://example.com/photo4.jpg",
      "https://example.com/photo5.jpg"
    ],
    "identity_name": "John Doe",
    "user_id": "user_123"
  }'
```

**Response:**
```json
{
  "success": true,
  "identity_id": "identity_user_123_john_doe",
  "face_embedding": null,
  "quality_score": 0.92,
  "photos_used": 5,
  "photos_rejected": 0,
  "request_id": "ident_xyz789",
  "timestamp": "2026-02-06T10:30:00Z"
}
```

### POST `/api/v3/identity/generate`

Generate images with consistent face.

**Request:**
```json
{
  "prompt": "professional headshot in office",
  "identity_id": "identity_user_123_john_doe",
  "quality": "STANDARD",
  "width": 1024,
  "height": 1024
}
```

**Test with curl:**
```bash
curl -X POST http://localhost:8000/api/v3/identity/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "professional headshot in office",
    "identity_id": "identity_user_123_john_doe",
    "quality": "STANDARD"
  }'
```

---

## 4️⃣ Group Photo Generation

### POST `/api/v3/group-photo`

Generate photos with multiple identities (2-5 people).

**Request:**
```json
{
  "identities": [
    "identity_user_123_john",
    "identity_user_124_jane",
    "identity_user_125_bob"
  ],
  "prompt": "friends at a party",
  "layout": "auto",
  "quality": "STANDARD"
}
```

**Layouts:**
- `auto` - AI selects best layout
- `line` - People in a line
- `circle` - People in a circle
- `casual` - Natural casual positioning

**Test with curl:**
```bash
curl -X POST http://localhost:8000/api/v3/group-photo \
  -H "Content-Type: application/json" \
  -d '{
    "identities": [
      "identity_user_123_john",
      "identity_user_124_jane"
    ],
    "prompt": "friends at a party",
    "layout": "auto",
    "quality": "STANDARD"
  }'
```

---

## 5️⃣ System Information

### GET `/api/v3/status`

Get AI system status and capabilities.

**Test with curl:**
```bash
curl http://localhost:8000/api/v3/status
```

**Response:**
```json
{
  "status": "ready",
  "services": {
    "smart_ai": {
      "mode_detector": true,
      "category_detector": true,
      "prompt_enhancer": true,
      "generation_router": true
    },
    "generation": {
      "generation_service": true,
      "quality_scorer": true,
      "two_pass_generator": true
    },
    "identity": {
      "instantid": false,
      "identity_engine": false
    },
    "prompts": {
      "universal_enhancer": true,
      "cinematic_engine": true
    }
  },
  "available_modes": [
    "REALISM",
    "CINEMATIC",
    "ANIME",
    "FANTASY",
    "CREATIVE"
  ],
  "available_categories": [
    "portrait",
    "landscape",
    "product",
    "abstract",
    "architecture",
    "nature",
    "animals",
    "fantasy"
  ],
  "quality_tiers": [
    "FAST",
    "STANDARD",
    "PREMIUM"
  ],
  "backends": {
    "huggingface": true,
    "replicate": false,
    "sagemaker": false
  }
}
```

### GET `/api/v3/health`

Simple health check for monitoring.

**Test with curl:**
```bash
curl http://localhost:8000/api/v3/health
```

**Response:**
```json
{
  "status": "healthy",
  "version": "3.0.0",
  "timestamp": "2026-02-06T10:30:00Z",
  "ai_orchestrator": "ready"
}
```

### GET `/api/v3/modes`

List all generation modes with descriptions.

**Test with curl:**
```bash
curl http://localhost:8000/api/v3/modes
```

**Response:**
```json
{
  "modes": [
    {
      "id": "REALISM",
      "name": "Realism",
      "description": "Photorealistic images",
      "example_keywords": ["photo", "realistic", "portrait", "professional", "photography"]
    },
    {
      "id": "CINEMATIC",
      "name": "Cinematic",
      "description": "Movie-quality images",
      "example_keywords": ["cinematic", "movie", "epic", "dramatic", "shot"]
    }
  ]
}
```

### GET `/api/v3/categories`

List all image categories.

**Test with curl:**
```bash
curl http://localhost:8000/api/v3/categories
```

---

## 🧪 Complete Test Scenarios

### Scenario 1: Basic Generation Flow

```bash
# 1. Check system status
curl http://localhost:8000/api/v3/status

# 2. List available modes
curl http://localhost:8000/api/v3/modes

# 3. Generate simple image
curl -X POST http://localhost:8000/api/v3/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "sunset over mountains", "quality": "FAST"}'

# 4. Generate with advanced enhancement
curl -X POST http://localhost:8000/api/v3/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "warrior in battle",
    "quality": "PREMIUM",
    "enhancement_level": "cinematic"
  }'
```

### Scenario 2: Two-Pass Workflow

```bash
# 1. Request two-pass generation
curl -X POST http://localhost:8000/api/v3/generate/two-pass \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "futuristic city at night",
    "quality": "PREMIUM",
    "width": 1920,
    "height": 1080
  }'

# Response includes both preview and full quality
```

### Scenario 3: Identity Workflow

```bash
# 1. Create identity from photos
curl -X POST http://localhost:8000/api/v3/identity/create \
  -H "Content-Type: application/json" \
  -d '{
    "photos": ["url1", "url2", "url3", "url4", "url5"],
    "identity_name": "John Doe",
    "user_id": "user_123"
  }'

# Save the identity_id from response

# 2. Generate with identity
curl -X POST http://localhost:8000/api/v3/identity/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "businessman in office",
    "identity_id": "identity_user_123_john_doe",
    "quality": "STANDARD"
  }'
```

---

## 📊 Performance Benchmarks

### Expected Generation Times

| Quality Tier | Model | Steps | Expected Time |
|--------------|-------|-------|---------------|
| FAST | SDXL-Turbo | 4 | 3-5 seconds |
| STANDARD | SDXL-Base | 30 | 20-30 seconds |
| PREMIUM | SDXL-Base+Refiner | 50 | 45-60 seconds |

### Backend Performance

| Backend | Setup Time | Cost | Speed |
|---------|------------|------|-------|
| HuggingFace | ✅ Ready | FREE* | Medium |
| Replicate | 5 min | $0.005/gen | Fast |
| SageMaker | 2-3 hours | $1.50/hr | Fastest |

*HuggingFace FREE tier: 1000 generations/day

---

## 🐛 Troubleshooting

### Issue: "Enhancement service unavailable"

**Solution:** Make sure ai-pipeline is on PYTHONPATH
```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)/../../ai-pipeline"
```

### Issue: "Generation backend not configured"

**Solution:** Set GENERATION_BACKEND in .env
```bash
echo "GENERATION_BACKEND=huggingface" >> .env
echo "HUGGINGFACE_API_TOKEN=your_token" >> .env
```

### Issue: "InstantID not available"

**Solution:** Download InstantID model
```bash
python scripts/download_models.py --model instantid
```

### Issue: Slow generation times

**Solution:**
1. Use FAST tier for quick results
2. Enable two-pass generation for better UX
3. Consider using Replicate or SageMaker for production

---

## 🎯 Next Steps

After testing the API:

1. **Download Models** (if not using HuggingFace API)
   ```bash
   python scripts/download_models.py --model all
   ```

2. **Build Frontend UI**
   - SmartGenerateForm component
   - QualitySelector component
   - PreviewDisplay component
   - ProgressIndicator component

3. **Create API Client Library**
   - TypeScript client for frontend
   - Error handling
   - Retry logic
   - Progress tracking

4. **Production Deployment**
   - Add authentication
   - Rate limiting
   - Caching
   - Monitoring

---

**Last Updated**: February 6, 2026
**Status**: ✅ API Ready for Testing
**Documentation**: Complete
