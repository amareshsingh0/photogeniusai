"""Generation endpoints: create, status, with AWS GPU (SageMaker/Lambda) integration."""
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks, status  # type: ignore[reportMissingImports]
from pydantic import BaseModel, Field  # type: ignore[reportMissingImports]
from typing import Optional, List
import logging
import uuid
import base64
from datetime import datetime

from app.core.dependencies import CurrentUserId, DbSession
from app.core.security import require_auth
from app.services.safety import (
    dual_pipeline,
    audit_logger,
    AuditEventType,
    SafetyStage,
)
from app.services.safety.adversarial_defense_bridge import analyze_prompt_for_api
from app.services.safety.rate_limiter import rate_limiter
from app.services.gpu_client import get_gpu_client, get_client_exceptions
from app.services.storage.s3_service import get_s3_service
from app.services.tier_enforcer import (
    fetch_user_context,
    check_and_enforce,
    apply_generation_charges,
)
from app.models.identity import Identity, TrainingStatus
from app.models.generation import Generation, GenerationStatus, GenerationMode
from app.schemas.generation import (
    GenerationCreate,
    GenerationResponse,
)
from app.core.database import AsyncSessionLocal
from sqlalchemy import text  # type: ignore[reportMissingImports]

logger = logging.getLogger(__name__)
router = APIRouter()

# ==================== Request/Response Models ====================

# All AI pipeline modes (match ai-pipeline generation_service + multi_variant_generator)
VALID_MODES = "REALISM|CREATIVE|ROMANTIC|CINEMATIC|FASHION|COOL_EDGY|ARTISTIC|MAX_SURPRISE"

class GenerationRequest(BaseModel):
    """Request body for image generation"""
    prompt: str = Field(..., min_length=1, max_length=1000)
    mode: str = Field(default="REALISM", pattern=f"^({VALID_MODES})$")
    identity_id: Optional[str] = None
    num_images: int = Field(default=2, ge=1, le=4)
    guidance_scale: float = Field(default=7.5, ge=1.0, le=20.0)
    num_inference_steps: int = Field(default=40, ge=20, le=100)
    seed: Optional[int] = None


class GenerationResponse(BaseModel):
    """Response for generation request"""
    job_id: str
    status: str
    message: str
    images: Optional[List[dict]] = None
    error: Optional[str] = None


class GenerationStatusResponse(BaseModel):
    """Response for generation status check"""
    job_id: str
    status: str
    progress: Optional[float] = None
    images: Optional[List[dict]] = None
    error: Optional[str] = None
    created_at: Optional[str] = None
    completed_at: Optional[str] = None


# In-memory job storage (replace with Redis/DB in production)
generation_jobs = {}


# ==================== Endpoints ====================

@router.post("", response_model=GenerationResponse)
async def create_generation(
    body: GenerationRequest,
    user_id: CurrentUserId,  # type: ignore[reportInvalidTypeForm]
    db: DbSession,
    request: Request,
    background_tasks: BackgroundTasks,
):
    """
    Submit image generation request with safety checks.
    
    Flow:
    1. Pre-generation safety check (prompt filtering)
    2. Queue generation on AWS GPU
    3. Post-generation safety check (NSFW/age detection)
    4. Return safe images
    
    NOTE: Credit checks are DISABLED during development/testing phase.
    """
    require_auth(user_id)
    uid = str(user_id) if user_id is not None else ""

    # Generate unique job ID
    job_id = f"gen_{uuid.uuid4().hex[:12]}"
    
    # Get client IP and user agent for audit logging
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    
    logger.info(f"Generation request: job_id={job_id}, user_id={user_id}, mode={body.mode}")

    # ===== ADVERSARIAL DEFENSE (before queuing) =====
    try:
        adv_safe, adv_threats, adv_sanitized = analyze_prompt_for_api(body.prompt, user_id=uid)
        if not adv_safe and adv_threats:
            logger.warning(f"Adversarial block: job_id={job_id}, threats={adv_threats}")
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "adversarial_prompt_blocked",
                    "message": "Prompt contains adversarial content and cannot be processed.",
                    "violations": adv_threats,
                    "suggested_prompt": adv_sanitized,
                },
            )
        prompt_for_check = (adv_sanitized or body.prompt) if adv_safe else body.prompt
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("Adversarial defense check error: %s", e)
        prompt_for_check = body.prompt

    # ===== STAGE 1: PRE-GENERATION SAFETY CHECK =====
    try:
        uid = str(user_id) if user_id is not None else ""
        pre_result = await dual_pipeline.pre_generation_check(
            user_id=uid,
            prompt=prompt_for_check,
            mode=body.mode,
            identity_id=body.identity_id or "",
            db_session=db
        )
        
        # Log pre-generation check
        await audit_logger.log_event(
            event_type=AuditEventType.PRE_GEN_BLOCK if not pre_result.allowed else AuditEventType.PRE_GEN_ALLOW,
            user_id=uid,
            stage=SafetyStage.PRE_GENERATION.value,
            action="BLOCK" if not pre_result.allowed else "ALLOW",
            violations={"items": pre_result.violations} if (not pre_result.allowed and pre_result.violations) else None,  # type: ignore[reportArgumentType]
            prompt=prompt_for_check,
            ip_address=client_ip,
            user_agent=user_agent,
            metadata=pre_result.metadata,
            db_session=db
        )
        
        # Block if safety check failed
        if not pre_result.allowed:
            logger.warning(f"Pre-gen safety block: job_id={job_id}, violations={pre_result.violations}")
            raise HTTPException(
                status_code=403,
                detail={
                    "error": pre_result.reason,
                    "violations": pre_result.violations,
                    "suggested_prompt": pre_result.modified_prompt
                }
            )
        
        # Increment rate limit (on successful safety check)
        await rate_limiter.increment_rate_limit(uid)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Safety check error: {e}")
        raise HTTPException(status_code=500, detail="Safety check failed")
    
    # ===== TIER & CREDITS ENFORCEMENT =====
    user_ctx = await fetch_user_context(db, uid)
    if not user_ctx:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    params = {
        "width": 1024,
        "height": 1024,
        "identity_id": body.identity_id,
        "num_images": body.num_images,
        "quality_tier": "BALANCED",
    }
    enforcement = check_and_enforce(user_ctx, params)
    if not enforcement.get("allowed"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "tier_limit_exceeded",
                "message": enforcement.get("reason", "Limit exceeded"),
                "upgrade_tier": enforcement.get("upgrade_tier"),
                "add_credits_url": enforcement.get("add_credits_url"),
            },
        )
    cost = enforcement["cost"]
    user_db_id = user_ctx["user_id"]
    tier = user_ctx.get("tier", "free")
    
    # ===== STAGE 2: QUEUE GENERATION =====
    generation_jobs[job_id] = {
        "status": "queued",
        "user_id": user_id,
        "prompt": prompt_for_check,
        "mode": body.mode,
        "identity_id": body.identity_id,
        "num_images": body.num_images,
        "created_at": datetime.utcnow().isoformat(),
        "images": None,
        "error": None,
    }
    
    background_tasks.add_task(
        run_generation_task,
        job_id=job_id,
        user_id=uid,
        user_db_id=str(user_db_id),
        cost=cost,
        tier=tier,
        prompt=prompt_for_check,
        mode=body.mode,
        identity_id=body.identity_id,
        num_candidates=body.num_images + 2,
        guidance_scale=body.guidance_scale,
        num_inference_steps=body.num_inference_steps,
        seed=body.seed,
    )
    
    return GenerationResponse(
        job_id=job_id,
        status="queued",
        message="Generation queued. Safety checks passed.",
    )


@router.get("/{job_id}", response_model=GenerationStatusResponse)
async def get_generation_status(job_id: str, user_id: CurrentUserId, db: DbSession):  # type: ignore[reportInvalidTypeForm]
    """Get generation job status and results."""
    require_auth(user_id)
    
    job = generation_jobs.get(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Generation job not found")
    
    # Verify ownership
    if job["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return GenerationStatusResponse(
        job_id=job_id,
        status=job["status"],
        progress=job.get("progress"),
        images=job.get("images"),
        error=job.get("error"),
        created_at=job.get("created_at"),
        completed_at=job.get("completed_at"),
    )


@router.post("/sync", response_model=GenerationResponse)
async def create_generation_sync(
    body: GenerationRequest,
    user_id: CurrentUserId,  # type: ignore[reportInvalidTypeForm]
    db: DbSession,
    request: Request,
):
    """
    Synchronous generation - waits for result.
    
    Use for testing or when immediate response is needed.
    WARNING: Can take 30-60 seconds to complete.
    """
    require_auth(user_id)
    
    job_id = f"gen_{uuid.uuid4().hex[:12]}"
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    
    uid = str(user_id) if user_id is not None else ""
    logger.info(f"Sync generation: job_id={job_id}, user_id={uid}")
    
    # ===== PRE-GENERATION SAFETY CHECK =====
    try:
        pre_result = await dual_pipeline.pre_generation_check(
            user_id=uid,
            prompt=body.prompt,
            mode=body.mode,
            identity_id=body.identity_id or "",
            db_session=db
        )
        
        if not pre_result.allowed:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": pre_result.reason,
                    "violations": pre_result.violations,
                }
            )
        
        await rate_limiter.increment_rate_limit(uid)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Safety check error: {e}")
        raise HTTPException(status_code=500, detail="Safety check failed")
    
    # ===== CALL GPU BACKEND (AWS / MODAL) FOR GENERATION =====
    try:
        result = await get_gpu_client().generate_with_safety(
            user_id=uid,
            identity_id=body.identity_id or "default",
            prompt=body.prompt,
            mode=body.mode,
            num_candidates=body.num_images + 2,
            guidance_scale=body.guidance_scale,
            num_inference_steps=body.num_inference_steps,
            seed=body.seed,
        )
        
        if not result["success"]:
            return GenerationResponse(
                job_id=job_id,
                status="failed",
                message="Generation failed safety checks",
                error=result.get("error"),
            )
        
        # Upload images to S3 and get URLs
        s3_service = get_s3_service()
        uploaded_images = []
        
        for i, img in enumerate(result["images"][:body.num_images]):
            try:
                # Decode base64 and upload
                img_bytes = base64.b64decode(img["image_base64"])
                key = f"generations/{user_id}/{job_id}_{i}.png"
                
                url = await s3_service.upload_file_async(
                    file_data=img_bytes,
                    s3_key=key,
                    content_type="image/png",
                )
                
                uploaded_images.append({
                    "url": url,
                    "seed": img.get("seed"),
                    "scores": img.get("scores"),
                })
            except Exception as e:
                logger.error(f"Failed to upload image: {e}")
                continue
        
        return GenerationResponse(
            job_id=job_id,
            status="completed",
            message=f"Generated {len(uploaded_images)} images",
            images=uploaded_images,
        )
        
    except get_client_exceptions() as e:
        logger.error("GPU client error: %s", e)
        return GenerationResponse(
            job_id=job_id,
            status="failed",
            message="Generation service error",
            error=str(e),
        )
    except Exception as e:
        logger.exception("Generation error")
        raise HTTPException(status_code=500, detail="Generation failed")


# ==================== Background Task ====================

def _watermark_free_tier(img_bytes: bytes) -> bytes:
    """Add subtle watermark for Free tier. Returns JPEG bytes."""
    try:
        import io
        from PIL import Image, ImageDraw, ImageFont  # type: ignore[reportMissingImports]
        img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        draw = ImageDraw.Draw(img)
        w, h = img.size
        txt = "PhotoGenius"
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", max(12, min(w, h) // 64))
        except Exception:
            font = ImageFont.load_default()
        bbox = draw.textbbox((0, 0), txt, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        x, y = w - tw - 12, h - th - 12
        draw.rectangle([x - 2, y - 2, x + tw + 2, y + th + 2], fill=(40, 40, 40))
        draw.text((x, y), txt, fill=(200, 200, 200), font=font)
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=92)
        return out.getvalue()
    except Exception as e:
        logger.warning("Watermark failed: %s", e)
        return img_bytes


async def run_generation_task(
    job_id: str,
    user_id: str,
    user_db_id: str,
    cost: int,
    tier: str,
    prompt: str,
    mode: str,
    identity_id: Optional[str],
    num_candidates: int,
    guidance_scale: float,
    num_inference_steps: int,
    seed: Optional[int],
):
    """Background task: AWS generation, S3 upload, credit deduction, optional Free-tier watermark."""
    try:
        generation_jobs[job_id]["status"] = "processing"
        generation_jobs[job_id]["progress"] = 0.1
        logger.info("Starting generation task: %s", job_id)
        
        result = await get_gpu_client().generate_with_safety(
            user_id=user_id,
            identity_id=identity_id or "default",
            prompt=prompt,
            mode=mode,
            num_candidates=num_candidates,
            guidance_scale=guidance_scale,
            num_inference_steps=num_inference_steps,
            seed=seed,
        )
        
        generation_jobs[job_id]["progress"] = 0.8
        
        if not result["success"]:
            generation_jobs[job_id]["status"] = "failed"
            generation_jobs[job_id]["error"] = result.get("error")
            logger.warning("Generation failed: %s, %s", job_id, result.get("error"))
            return
        
        s3_service = get_s3_service()
        uploaded_images = []
        use_watermark = (tier or "free").lower() == "free"
        
        for i, img in enumerate(result["images"]):
            try:
                img_bytes = base64.b64decode(img["image_base64"])
                if use_watermark:
                    img_bytes = _watermark_free_tier(img_bytes)
                key = f"generations/{user_id}/{job_id}_{i}.png"
                if use_watermark:
                    key = key.replace(".png", ".jpg")
                url = await s3_service.upload_file_async(
                    file_data=img_bytes,
                    s3_key=key,
                    content_type="image/jpeg" if use_watermark else "image/png",
                )
                uploaded_images.append({
                    "url": url,
                    "seed": img.get("seed"),
                    "scores": img.get("scores"),
                    "watermarked": use_watermark,
                })
            except Exception as e:
                logger.error("S3 upload error: %s", e)
                continue
        
        generation_jobs[job_id]["status"] = "completed"
        generation_jobs[job_id]["progress"] = 1.0
        generation_jobs[job_id]["images"] = uploaded_images
        generation_jobs[job_id]["completed_at"] = datetime.utcnow().isoformat()
        logger.info("Generation completed: %s, %d images", job_id, len(uploaded_images))
        
        # Deduct credits and increment usage (new session)
        import uuid
        uid = uuid.UUID(user_db_id)
        async with AsyncSessionLocal() as db:
            await apply_generation_charges(db, uid, cost, job_id)
        
    except get_client_exceptions() as e:
        generation_jobs[job_id]["status"] = "failed"
        generation_jobs[job_id]["error"] = str(e)
        logger.error("GPU error: %s, %s", job_id, e)
    except Exception as e:
        generation_jobs[job_id]["status"] = "failed"
        generation_jobs[job_id]["error"] = "Internal error"
        logger.exception("Generation task error: %s", job_id)


# ==================== Database-Backed Endpoints ====================

async def get_user_db_id(clerk_id: str, db: DbSession) -> uuid.UUID:
    """Get user's database UUID from Clerk ID"""
    result = await db.execute(
        text("SELECT id FROM users WHERE clerk_id = :clerk_id"),
        {"clerk_id": clerk_id}
    )
    row = result.fetchone()
    
    if not row:
        raise HTTPException(
            status_code=404,
            detail="User not found in database"
        )
    
    return row.id


@router.post("/db", response_model=GenerationResponse)
async def create_generation_db(
    data: GenerationCreate,
    user_id: CurrentUserId = None,  # type: ignore[reportInvalidTypeForm]
    db: DbSession = None,
    request: Request = None,
):
    """
    Generate images with safety checks (database-backed).
    
    Flow:
    1. Validate identity
    2. Check prompt safety
    3. Generate images on AWS
    4. Check image safety
    5. Upload safe images to S3
    6. Return results
    """
    require_auth(user_id)
    uid = str(user_id) if user_id is not None else ""
    
    # Get user's database UUID
    user_db_id = await get_user_db_id(uid, db)
    
    # Validate identity (required in this endpoint)
    if not data.identity_id:
        raise HTTPException(status_code=400, detail="identity_id is required")
    
    try:
        identity_db_id = uuid.UUID(data.identity_id)
        identity = await db.get(Identity, identity_db_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid identity ID format")
    
    if not identity:
        raise HTTPException(status_code=404, detail="Identity not found")
    
    if identity.user_id != user_db_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    if identity.training_status != TrainingStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Identity not ready (status: {identity.training_status.value})"
        )
    
    # Create generation record
    generation_id = uuid.uuid4()
    
    generation = Generation(
        id=generation_id,
        user_id=user_db_id,
        identity_id=identity_db_id,
        mode=GenerationMode(data.mode.upper()),
        original_prompt=data.prompt,
        num_inference_steps=data.num_inference_steps or 40,
        guidance_scale=data.guidance_scale or 7.5,
        seed=data.seed,
        status=GenerationStatus.SAFETY_CHECK,
    )
    
    db.add(generation)
    await db.commit()
    await db.refresh(generation)
    
    try:
        # STEP 1: Prompt Safety Check
        prompt_safety = await get_gpu_client().check_prompt_safety(
            prompt=data.prompt,
            mode=data.mode,
        )
        
        if not prompt_safety.get("allowed", False):
            generation.status = GenerationStatus.BLOCKED
            generation.block_reason = "prompt_unsafe"
            generation.safety_violations = prompt_safety.get("violations", [])
            generation.safety_status = "BLOCK"
            await db.commit()
            
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Prompt blocked by safety check",
                    "violations": prompt_safety.get("violations", [])
                }
            )
        
        # STEP 2: Generate Images
        generation.status = GenerationStatus.GENERATING
        await db.commit()
        
        results = await get_gpu_client().generate_images(
            user_id=uid,
            identity_id=data.identity_id,
            prompt=data.prompt,
            mode=data.mode,
            num_candidates=data.num_candidates or 4,
            guidance_scale=data.guidance_scale or 7.5,
            num_inference_steps=data.num_inference_steps or 40,
            seed=data.seed,
            face_embedding=identity.face_embedding,
        )
        
        # STEP 3: Image Safety Checks
        generation.status = GenerationStatus.POST_SAFETY_CHECK
        await db.commit()
        
        safe_images = []
        
        for result in results:
            image_safety = await get_gpu_client().check_image_safety(
                image_base64=result["image_base64"],
                mode=data.mode,
            )
            
            if image_safety.get("safe", False):
                safe_images.append(result)
            else:
                # Log blocked image
                logger.warning(f"Image blocked: {image_safety.get('violations', [])}")
        
        if len(safe_images) == 0:
            generation.status = GenerationStatus.BLOCKED
            generation.block_reason = "all_images_unsafe"
            generation.safety_status = "BLOCK"
            await db.commit()
            
            raise HTTPException(
                status_code=400,
                detail="All generated images failed safety check"
            )
        
        # STEP 4: Upload to S3
        generation.status = GenerationStatus.UPLOADING
        await db.commit()
        
        s3_service = get_s3_service()
        uploaded_urls = []
        
        for idx, img_data in enumerate(safe_images):
            try:
                # Decode base64
                img_bytes = base64.b64decode(img_data["image_base64"])
                
                # Upload to S3
                s3_key = f"generations/{uid}/{generation_id}/image_{idx}.png"
                url = await s3_service.upload_file_async(
                    file_data=img_bytes,
                    s3_key=s3_key,
                    content_type="image/png",
                )
                
                uploaded_urls.append({
                    "url": url,
                    "scores": img_data.get("scores", {}),
                    "seed": img_data.get("seed"),
                })
                
                # Extract quality scores from first image
                if idx == 0 and img_data.get("scores"):
                    scores = img_data["scores"]
                    generation.face_match_score = scores.get("face_match", {}).get("score")
                    generation.aesthetic_score = scores.get("aesthetic", {}).get("score")
                    generation.technical_score = scores.get("technical", {}).get("score")
                    generation.overall_score = scores.get("total")
                    
            except Exception as e:
                logger.error(f"Failed to upload image {idx}: {e}")
                continue
        
        if len(uploaded_urls) == 0:
            generation.status = GenerationStatus.FAILED
            generation.error_message = "Failed to upload images to S3"
            await db.commit()
            raise HTTPException(status_code=500, detail="Failed to upload images")
        
        # STEP 5: Complete
        generation.status = GenerationStatus.COMPLETED
        generation.output_urls = uploaded_urls
        generation.selected_output_url = uploaded_urls[0]["url"] if uploaded_urls else None
        generation.thumbnail_url = uploaded_urls[0]["url"] if uploaded_urls else None
        generation.safety_status = "ALLOW"
        generation.completed_at = datetime.utcnow()
        await db.commit()
        
        logger.info(f"Generation completed: {generation_id}, {len(uploaded_urls)} images")
        
        return GenerationResponse.model_validate(generation)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error in generation: {generation_id}")
        
        generation.status = GenerationStatus.FAILED
        generation.error_message = str(e)
        await db.commit()
        
        raise HTTPException(
            status_code=500,
            detail=f"Generation failed: {str(e)}"
        )


@router.get("/db/{generation_id}", response_model=GenerationResponse)
async def get_generation_db(
    generation_id: str,
    user_id: CurrentUserId = None,  # type: ignore[reportInvalidTypeForm]
    db: DbSession = None,
):
    """Get generation details (database-backed)"""
    require_auth(user_id)
    uid = str(user_id) if user_id is not None else ""
    
    # Get user's database UUID
    user_db_id = await get_user_db_id(uid, db)
    
    try:
        generation = await db.get(Generation, uuid.UUID(generation_id))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid generation ID format")
    
    if not generation:
        raise HTTPException(status_code=404, detail="Generation not found")
    
    if generation.user_id != user_db_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return GenerationResponse.model_validate(generation)
