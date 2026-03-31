# 📊 PhotoGenius AI - Current System Status

**Date**: February 5, 2026
**Analysis**: Complete infrastructure audit

---

## ✅ What's Already Working

### 1. Database Schema (Excellent!)

**Generation Model** - Fully featured:
```prisma
- ✅ User relationship
- ✅ Identity/LoRA support
- ✅ Multiple generation modes
- ✅ Quality scores (face, aesthetic, technical)
- ✅ Safety checks (pre/post generation)
- ✅ Quarantine system
- ✅ Credits tracking
- ✅ Public gallery support
- ✅ Soft delete (isDeleted, deletedAt)
- ✅ Timestamps (createdAt, updatedAt)
```

### 2. Lambda Functions (Updated!)

```
✅ photogenius-orchestrator-dev
✅ photogenius-prompt-enhancer-dev
✅ photogenius-generation-dev
✅ photogenius-post-processor-dev
✅ photogenius-safety-dev
```

**Status**: Code updated, Function URLs created

### 3. Frontend Structure

```
✅ Next.js 14 + React 18 + TypeScript
✅ Tailwind CSS + shadcn/ui
✅ Clerk Authentication
✅ Supabase Database
✅ Environment variables configured
```

---

## ⚠️ What Needs Fixing

### 1. SageMaker Endpoints

**Current**: No endpoints deployed
**Need**: Deploy generation endpoints

```yaml
Required Endpoints:
  - FAST: SDXL-Turbo (4 steps, ~3s)
  - STANDARD: SDXL-Base (30 steps, ~25s)
  - PREMIUM: SDXL-Refiner (50 steps, ~50s)
```

### 2. Gallery System

**Current**: Minimal implementation
**Need**: Complete gallery + auto-delete

```python
# Current (incomplete)
@router.get("")
async def list_generations():
    return []  # TODO

# Need to implement:
- List user generations
- Public gallery
- Auto-delete after 10-20 days
- Cleanup job
```

### 3. AI Services

**Current**: Basic services in Lambda
**Need**: Smart AI detection

```
Required:
- Mode auto-detection
- Prompt enhancement
- Quality routing
- Dimension detection
```

---

## 🎯 Implementation Plan

### Phase 1: Gallery System (Priority 1) ✅

**Auto-Delete Feature**:
```python
# Delete generations older than 15 days (configurable)
DELETE_AFTER_DAYS = 15

# Cleanup job runs daily
- Check createdAt < (now - 15 days)
- Soft delete (set isDeleted = true)
- Delete from S3
- Free up credits (optional)
```

**Gallery Endpoints**:
```python
GET  /api/v1/gallery        # List user's generations
GET  /api/v1/gallery/public # Public gallery
POST /api/v1/gallery/:id/delete  # Manual delete
GET  /api/v1/gallery/:id    # Get single generation
```

### Phase 2: Use Existing Advanced System (Priority 2) ✅

**Current codebase has**:
- `apps/ai-service/` - Advanced AI services
- `ai-pipeline/services/` - 75+ AI services
- Modal app with full pipeline

**Strategy**: Use Lambda + existing services instead of rebuilding

### Phase 3: SageMaker or Lambda Decision

**Option A: SageMaker (Better for scale)**
- Pro: Dedicated GPU, consistent performance
- Con: $1.50-3/hour per endpoint
- Best for: Production, high volume

**Option B: Lambda + Modal/Replicate (Easier)**
- Pro: Easier deployment, pay per use
- Con: Cold starts, less control
- Best for: MVP, lower volume

---

## 🚀 Immediate Action Items

### 1. Gallery Auto-Delete (Today)

```python
# Create cleanup service
apps/api/app/services/gallery/
├── gallery_service.py      # List, get, delete
├── cleanup_service.py      # Auto-delete old generations
└── scheduler.py            # Daily cleanup job
```

### 2. Complete Gallery API (Today)

```python
# Implement full CRUD
- List generations (with filters)
- Get single generation
- Delete generation (manual)
- Public gallery (pagination)
```

### 3. Deploy Generation Endpoint (Tomorrow)

**Quick Start**: Use existing Modal deployment
```bash
cd apps/ai-service
modal deploy modal_app.py
```

**OR**: Deploy to Lambda
```bash
cd aws
./deploy_lambda_with_model.sh
```

---

## 📋 Detailed Implementation

### Gallery Auto-Delete System

```python
# apps/api/app/services/gallery/cleanup_service.py

from datetime import datetime, timedelta
from app.database import db
import boto3

class GalleryCleanupService:
    """Auto-delete old generations"""

    def __init__(self, delete_after_days: int = 15):
        self.delete_after_days = delete_after_days
        self.s3 = boto3.client('s3')

    async def cleanup_old_generations(self):
        """
        Delete generations older than delete_after_days

        Process:
        1. Find old generations (createdAt < now - days)
        2. Delete images from S3
        3. Soft delete in database
        4. Log cleanup stats
        """

        cutoff_date = datetime.utcnow() - timedelta(days=self.delete_after_days)

        # Find old generations
        old_generations = await db.generation.find_many(
            where={
                'createdAt': {'lt': cutoff_date},
                'isDeleted': False,
                'isFavorite': False  # Don't delete favorites
            }
        )

        deleted_count = 0
        freed_storage = 0

        for gen in old_generations:
            try:
                # Delete from S3
                urls = gen.outputUrls  # JSON array of URLs
                for url in urls:
                    key = self._extract_s3_key(url)
                    self.s3.delete_object(
                        Bucket='photogenius-images-dev',
                        Key=key
                    )
                    freed_storage += self._get_object_size(key)

                # Soft delete in DB
                await db.generation.update(
                    where={'id': gen.id},
                    data={
                        'isDeleted': True,
                        'deletedAt': datetime.utcnow()
                    }
                )

                deleted_count += 1

            except Exception as e:
                print(f"Failed to delete generation {gen.id}: {e}")
                continue

        return {
            'deleted_count': deleted_count,
            'freed_storage_mb': freed_storage / (1024 * 1024),
            'cutoff_date': cutoff_date
        }

    def _extract_s3_key(self, url: str) -> str:
        """Extract S3 key from URL"""
        # https://bucket.s3.region.amazonaws.com/key
        return url.split('.com/')[-1]
```

### Scheduler (Cron Job)

```python
# apps/api/app/tasks/scheduled.py

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.services.gallery.cleanup_service import GalleryCleanupService

scheduler = AsyncIOScheduler()
cleanup_service = GalleryCleanupService(delete_after_days=15)

@scheduler.scheduled_job('cron', hour=3)  # Run daily at 3 AM
async def daily_cleanup():
    """Clean up old generations daily"""
    print("🧹 Starting daily cleanup...")

    result = await cleanup_service.cleanup_old_generations()

    print(f"✅ Cleanup complete:")
    print(f"   Deleted: {result['deleted_count']} generations")
    print(f"   Freed: {result['freed_storage_mb']:.2f} MB")

def start_scheduler():
    """Start the background scheduler"""
    scheduler.start()
    print("⏰ Scheduler started - daily cleanup at 3 AM")
```

### Gallery API

```python
# apps/api/app/api/v1/endpoints/gallery.py

from fastapi import APIRouter, Depends, Query
from typing import Optional
from app.core.dependencies import CurrentUserId, DbSession
from app.services.gallery.gallery_service import GalleryService

router = APIRouter()
gallery_service = GalleryService()

@router.get("")
async def list_generations(
    user_id: CurrentUserId,
    db: DbSession,
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    mode: Optional[str] = None,
    is_favorite: Optional[bool] = None
):
    """
    List user's generations

    Filters:
    - mode: Filter by generation mode (REALISM, CINEMATIC, etc.)
    - is_favorite: Show only favorites
    - Excludes deleted generations
    """

    where = {
        'userId': user_id,
        'isDeleted': False
    }

    if mode:
        where['mode'] = mode

    if is_favorite is not None:
        where['isFavorite'] = is_favorite

    generations = await db.generation.find_many(
        where=where,
        order_by={'createdAt': 'desc'},
        skip=offset,
        take=limit,
        include={
            'identity': True
        }
    )

    total = await db.generation.count(where=where)

    return {
        'generations': generations,
        'total': total,
        'limit': limit,
        'offset': offset
    }

@router.get("/public")
async def public_gallery(
    db: DbSession,
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    category: Optional[str] = None
):
    """
    Public gallery - only approved, public generations
    """

    where = {
        'isPublic': True,
        'isDeleted': False,
        'galleryModeration': 'APPROVED'
    }

    if category:
        where['galleryCategory'] = category

    generations = await db.generation.find_many(
        where=where,
        order_by={'galleryLikesCount': 'desc'},
        skip=offset,
        take=limit
    )

    return {
        'generations': generations,
        'total': await db.generation.count(where=where)
    }

@router.get("/{generation_id}")
async def get_generation(
    generation_id: str,
    user_id: CurrentUserId,
    db: DbSession
):
    """Get single generation"""

    generation = await db.generation.find_unique(
        where={'id': generation_id}
    )

    if not generation:
        raise HTTPException(404, "Generation not found")

    # Check ownership or public
    if generation.userId != user_id and not generation.isPublic:
        raise HTTPException(403, "Access denied")

    return generation

@router.delete("/{generation_id}")
async def delete_generation(
    generation_id: str,
    user_id: CurrentUserId,
    db: DbSession
):
    """Soft delete a generation"""

    generation = await db.generation.find_unique(
        where={'id': generation_id}
    )

    if not generation:
        raise HTTPException(404, "Generation not found")

    if generation.userId != user_id:
        raise HTTPException(403, "Access denied")

    # Soft delete
    await db.generation.update(
        where={'id': generation_id},
        data={
            'isDeleted': True,
            'deletedAt': datetime.utcnow()
        }
    )

    # Delete from S3
    await gallery_service.delete_images_from_s3(generation.outputUrls)

    return {'message': 'Generation deleted'}

@router.post("/{generation_id}/favorite")
async def toggle_favorite(
    generation_id: str,
    user_id: CurrentUserId,
    db: DbSession
):
    """Toggle favorite status"""

    generation = await db.generation.find_unique(
        where={'id': generation_id}
    )

    if generation.userId != user_id:
        raise HTTPException(403, "Access denied")

    await db.generation.update(
        where={'id': generation_id},
        data={'isFavorite': not generation.isFavorite}
    )

    return {'is_favorite': not generation.isFavorite}
```

---

## 💡 Recommendation

### Quick Win Strategy:

1. **Today**: Implement gallery + auto-delete ✅
2. **Tomorrow**: Deploy generation using existing Modal/Lambda
3. **Day 3**: Build AI services (mode detection, enhancement)
4. **Day 4-5**: Frontend integration + testing

**Total time**: 5 days to full system! 🚀

---

## 📁 Files to Create

```
apps/api/app/services/gallery/
├── __init__.py
├── gallery_service.py       # CRUD operations
├── cleanup_service.py       # Auto-delete
└── scheduler.py             # Cron jobs

apps/api/app/tasks/
├── __init__.py
└── scheduled.py             # Daily tasks

apps/api/app/services/smart/
├── __init__.py
├── mode_detector.py         # Auto mode detection
├── prompt_enhancer.py       # Auto enhancement
└── quality_router.py        # Route to endpoints
```

---

**Status**: 📋 **Ready to Implement - Gallery Auto-Delete First!**
