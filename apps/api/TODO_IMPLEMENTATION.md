# TODO Implementation Guide

This document lists features that need manual implementation based on business requirements and external service integrations.

## 1. Generation Job Queue System

**Location:** `apps/api/app/api/v1/endpoints/generation.py`

**Current Status:** Placeholder implementation

**What Needs Implementation:**

### Option A: Using Celery + Redis

```python
# apps/api/app/workers/generation_worker.py
from celery import Celery

celery_app = Celery(
    'photogenius',
    broker='redis://localhost:6379/0',
    backend='redis://localhost:6379/0'
)

@celery_app.task
def generate_image_task(generation_id: str, prompt: str, mode: str, identity_id: Optional[str]):
    # 1. Load AI model
    # 2. Generate image
    # 3. Run post-generation safety checks
    # 4. Upload to S3/R2
    # 5. Save to database
    # 6. Update status
    pass
```

**Steps:**
1. Install: `pip install celery redis`
2. Create `apps/api/app/workers/generation_worker.py`
3. Update `create_generation` endpoint to enqueue task
4. Run worker: `celery -A app.workers.generation_worker worker --loglevel=info`

### Option B: Using Modal.com (Recommended for GPU)

```python
# apps/api/app/services/ai/modal_generation.py
import modal

stub = modal.Stub("photogenius-generation")

@stub.function(
    image=modal.Image.debian_slim().pip_install("torch", "diffusers"),
    gpu="A10G",
    timeout=300
)
def generate_image(prompt: str, mode: str):
    # Modal handles GPU allocation
    # Generate image
    # Return image bytes
    pass
```

**Steps:**
1. Install: `pip install modal`
2. Run: `modal token new`
3. Create modal function
4. Update endpoint to call modal function

### Option C: Using FastAPI BackgroundTasks

```python
from fastapi import BackgroundTasks

@router.post("")
async def create_generation(
    background_tasks: BackgroundTasks,
    ...
):
    # Enqueue background task
    background_tasks.add_task(
        process_generation,
        generation_id=generation_id,
        prompt=prompt,
        mode=mode
    )
```

**Note:** BackgroundTasks are not suitable for long-running GPU tasks. Use Celery or Modal for production.

---

## 2. Stripe Payment Integration

**Location:** `apps/web/app/api/webhooks/stripe/route.ts`

**Current Status:** Webhook receives events but doesn't process payments

**What Needs Implementation:**

### Step 1: Create Subscription Plans

```typescript
// apps/web/lib/stripe.ts
import Stripe from 'stripe';

const stripe = new Stripe(process.env.STRIPE_SECRET_KEY!);

export async function createCheckoutSession(userId: string, priceId: string) {
  return await stripe.checkout.sessions.create({
    customer_email: user.email,
    line_items: [
      {
        price: priceId,
        quantity: 1,
      },
    ],
    mode: 'subscription',
    success_url: `${process.env.NEXT_PUBLIC_APP_URL}/dashboard?success=true`,
    cancel_url: `${process.env.NEXT_PUBLIC_APP_URL}/pricing?canceled=true`,
    metadata: {
      userId: userId,
    },
  });
}
```

### Step 2: Grant Credits on Payment

```typescript
// apps/web/app/api/webhooks/stripe/route.ts
if (event.type === "checkout.session.completed") {
  const session = event.data.object as Stripe.Checkout.Session;
  const userId = session.metadata?.userId;
  
  if (userId) {
    // Grant credits to user
    await UserRepository.updateCredits(userId, {
      credits: 100, // or based on plan
      plan: 'premium',
      expiresAt: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000) // 30 days
    });
  }
}
```

### Step 3: Create Pricing Page

```typescript
// apps/web/app/(dashboard)/pricing/page.tsx
// Display plans, create checkout sessions, handle redirects
```

**Steps:**
1. Create products/prices in Stripe Dashboard
2. Implement checkout session creation
3. Update webhook to grant credits
4. Create pricing UI
5. Add credit balance display

---

## 3. Admin Role-Based Access Control

**Location:** `apps/api/app/api/v1/endpoints/admin.py`

**Current Status:** No role checking

**What Needs Implementation:**

### Step 1: Add Role to User Model

```python
# apps/api/app/models/user.py
class User(Base):
    # ... existing fields
    role = Column(String(20), default="user")  # user, admin, moderator
```

### Step 2: Create Migration

```bash
cd apps/api
alembic revision -m "add_user_role"
# Edit migration to add role column
alembic upgrade head
```

### Step 3: Create Admin Dependency

```python
# apps/api/app/core/dependencies.py
from fastapi import HTTPException, Depends
from app.core.database import get_db
from app.models.user import User

async def require_admin(
    user_id: CurrentUserId = Depends(),
    db: DbSession = Depends()
) -> User:
    """Require user to be admin"""
    user = await db.get(User, user_id)
    if not user or user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
```

### Step 4: Use in Admin Endpoints

```python
# apps/api/app/api/v1/endpoints/admin.py
from app.core.dependencies import require_admin

@router.get("/stats")
async def admin_stats(admin: User = Depends(require_admin)):
    # Only admins can access
    return {"users": 0, "generations": 0}
```

**Steps:**
1. Add role column to database
2. Create admin dependency
3. Protect admin endpoints
4. Create admin UI (optional)

---

## 4. User Deletion Implementation

**Location:** `apps/web/app/api/webhooks/clerk/route.ts`

**Current Status:** Only logs deletion, doesn't actually delete

**What Needs Implementation:**

### Option A: Soft Delete (Recommended)

```typescript
// packages/database/src/repositories/user.repository.ts
async softDelete(userId: string) {
  return await this.prisma.user.update({
    where: { id: userId },
    data: {
      deletedAt: new Date(),
      isDeleted: true,
    },
  });
}
```

### Option B: Hard Delete with Cascade

```typescript
async function handleUserDeleted(data: any) {
  const user = await UserRepository.findByClerkId(data.id);
  
  if (!user) {
    return;
  }

  // Delete all related data
  await Promise.all([
    // Delete generations
    prisma.generation.deleteMany({ where: { userId: user.id } }),
    // Delete identities
    prisma.identity.deleteMany({ where: { userId: user.id } }),
    // Delete audit logs (or anonymize)
    prisma.safetyAuditLog.updateMany({
      where: { userId: user.clerkId },
      data: { userId: null }, // Anonymize
    }),
    // Delete user
    prisma.user.delete({ where: { id: user.id } }),
  ]);
}
```

**Steps:**
1. Add `deletedAt` and `isDeleted` fields to User model
2. Create migration
3. Implement soft delete or hard delete logic
4. Update queries to filter deleted users
5. Handle GDPR compliance (data retention, anonymization)

---

## 5. Generation Status Polling/WebSocket

**Location:** `apps/api/app/api/v1/endpoints/generation.py`

**Current Status:** Basic GET endpoint, no real-time updates

**What Needs Implementation:**

### Option A: WebSocket (Recommended)

```python
# apps/api/app/services/websocket/manager.py
from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        self.active_connections[user_id] = websocket
    
    async def send_generation_update(self, user_id: str, generation_id: str, status: str):
        if user_id in self.active_connections:
            await self.active_connections[user_id].send_json({
                "generation_id": generation_id,
                "status": status,
                "progress": 50  # percentage
            })
```

### Option B: Server-Sent Events (SSE)

```python
# apps/api/app/api/v1/endpoints/generation.py
from fastapi.responses import StreamingResponse

@router.get("/{job_id}/stream")
async def stream_generation_status(job_id: str):
    async def event_generator():
        while True:
            status = await get_generation_status(job_id)
            yield f"data: {json.dumps(status)}\n\n"
            if status["status"] in ["completed", "failed"]:
                break
            await asyncio.sleep(1)
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

**Steps:**
1. Choose WebSocket or SSE
2. Implement connection manager
3. Update generation worker to send updates
4. Update frontend to connect and display progress

---

## 6. Image Post-Generation Safety Check Integration

**Location:** `apps/api/app/services/safety/dual_pipeline.py`

**Current Status:** Post-generation check exists but not called after image generation

**What Needs Implementation:**

```python
# In generation worker or after image generation
post_result = await dual_pipeline.post_generation_check(
    image_path=generated_image_path,
    user_id=user_id,
    generation_id=generation_id,
    mode=mode,
    db_session=db
)

if not post_result.safe:
    # Delete image, log violation, add strike
    await storage_service.delete_image(image_url)
    # Return error to user
else:
    # Save image URL to database
    await save_generation_result(generation_id, image_url)
```

**Steps:**
1. Integrate post-check into generation workflow
2. Handle QUARANTINE mode (store separately)
3. Handle BLOCK mode (delete image, notify user)
4. Update generation status based on result

---

## Priority Order

1. **High Priority:**
   - Generation Job Queue System (required for core functionality)
   - Image Post-Generation Safety Check Integration (required for safety)

2. **Medium Priority:**
   - Admin Role-Based Access Control (security)
   - Generation Status Polling/WebSocket (UX)

3. **Low Priority:**
   - Stripe Payment Integration (monetization)
   - User Deletion Implementation (compliance)

---

## Additional Resources

- [Celery Documentation](https://docs.celeryproject.org/)
- [Modal.com Documentation](https://modal.com/docs)
- [Stripe Webhooks Guide](https://stripe.com/docs/webhooks)
- [FastAPI WebSockets](https://fastapi.tiangolo.com/advanced/websockets/)
- [GDPR Compliance Guide](https://gdpr.eu/)
