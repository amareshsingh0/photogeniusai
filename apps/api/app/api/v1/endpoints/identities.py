"""Identity Management Endpoints with file uploads and LoRA training (AWS/GPU backend)."""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks, Request
from typing import List, Optional
import uuid
import logging
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from urllib.parse import urlparse

from fastapi import status
from app.core.dependencies import CurrentUserId, DbSession
from app.core.security import require_auth
from app.services.gpu_client import get_gpu_client, get_client_exceptions
from app.services.storage.s3_service import get_s3_service
from app.services.tier_enforcer import fetch_user_context
from config.tier_config import get_tier_limits, normalize_tier
from app.models.identity import Identity, TrainingStatus
from app.schemas.identity import (
    IdentityResponse,
    IdentityListResponse,
)
from sqlalchemy import text

logger = logging.getLogger(__name__)
router = APIRouter()


async def get_user_db_id(clerk_id: str, db: AsyncSession) -> uuid.UUID:
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


def extract_s3_key_from_url(url: str) -> str:
    """Extract S3 key from full URL"""
    try:
        parsed = urlparse(url)
        # Remove leading slash
        key = parsed.path.lstrip("/")
        return key
    except Exception:
        # If parsing fails, assume it's already a key
        return url


from pydantic import BaseModel
import base64


class PhotoData(BaseModel):
    data: str  # base64 encoded
    filename: str
    contentType: str


class UploadPhotosRequest(BaseModel):
    photos: List[PhotoData]
    userId: str


class UploadPhotosResponse(BaseModel):
    urls: List[str]
    count: int


@router.post("/upload", response_model=UploadPhotosResponse)
async def upload_identity_photos(
    request_data: UploadPhotosRequest,
    request: Request = None,
):
    """
    Upload identity reference photos to S3.
    
    Accepts base64-encoded photos and uploads to S3.
    Returns array of presigned S3 URLs (work even for private buckets).
    """
    try:
        s3_service = get_s3_service()
        uploaded_urls: List[str] = []
        s3_keys: List[str] = []
        identity_folder = str(uuid.uuid4())
        
        for i, photo in enumerate(request_data.photos):
            try:
                # Decode base64
                image_data = base64.b64decode(photo.data)
                
                # Generate filename
                ext = photo.filename.split(".")[-1] if "." in photo.filename else "jpg"
                filename = f"{uuid.uuid4()}.{ext}"
                
                # Upload to S3 using async method
                s3_key = f"identities/{request_data.userId}/{identity_folder}/{filename}"
                s3_keys.append(s3_key)
                
                # Upload (we'll get presigned URLs separately)
                await s3_service.upload_file_async(
                    file_data=image_data,
                    s3_key=s3_key,
                    content_type=photo.contentType or "image/jpeg",
                )
                
                logger.info(f"Uploaded photo {i+1}/{len(request_data.photos)} to {s3_key}")
                
            except Exception as e:
                logger.error(f"Failed to upload photo {i+1}: {e}")
                continue
        
        if not s3_keys:
            raise HTTPException(
                status_code=400,
                detail="Failed to upload any photos"
            )
        
        # Generate presigned URLs (long expiration - 7 days)
        # These work even if bucket is private
        for s3_key in s3_keys:
            try:
                presigned_url = await s3_service.generate_presigned_url_async(
                    s3_key=s3_key,
                    expiration=7 * 24 * 3600  # 7 days
                )
                uploaded_urls.append(presigned_url)
            except Exception as e:
                logger.error(f"Failed to generate presigned URL for {s3_key}: {e}")
                # Fallback to direct URL
                bucket = s3_service.bucket
                region = s3_service.region
                uploaded_urls.append(f"https://{bucket}.s3.{region}.amazonaws.com/{s3_key}")
        
        return UploadPhotosResponse(
            urls=uploaded_urls,
            count=len(uploaded_urls)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to upload photos: {str(e)}"
        )


@router.post("/", response_model=IdentityResponse)
async def create_identity(
    name: str = Form(..., min_length=1, max_length=100),
    photos: List[UploadFile] = File(...),
    consent_agreed: bool = Form(...),
    trigger_word: str = Form(default="sks", min_length=2, max_length=20),
    training_steps: int = Form(default=1000, ge=100, le=3000),
    user_id: CurrentUserId = None,  # type: ignore[reportInvalidTypeForm]
    db: DbSession = None,
    background_tasks: BackgroundTasks = None,
    request: Request = None,
):
    """
    Create new identity with photo upload.
    
    Steps:
    1. Validate photos (min 5, max 20)
    2. Upload to S3
    3. Create identity record
    4. Trigger LoRA training on AWS (background)
    
    Requires:
    - Authentication (Bearer token)
    - Consent agreement
    - 5-20 photos of the same person
    """
    require_auth(user_id)
    uid = str(user_id) if user_id is not None else ""

    # Validate consent
    if not consent_agreed:
        raise HTTPException(
            status_code=400,
            detail="Consent agreement is required to create an identity"
        )
    
    # Validate photo count
    if len(photos) < 5:
        raise HTTPException(
            status_code=400,
            detail="Minimum 5 photos required for identity training"
        )
    
    if len(photos) > 20:
        raise HTTPException(
            status_code=400,
            detail="Maximum 20 photos allowed"
        )
    
    # Get user's database UUID
    user_db_id = await get_user_db_id(user_id, db)
    
    # Tier limit: identity creation
    user_ctx = await fetch_user_context(db, user_id)
    if user_ctx:
        tier = normalize_tier(user_ctx.get("tier"))
        limits = get_tier_limits(tier)
        max_id = limits.get("max_identities", 0)
        current = int(user_ctx.get("identity_count", 0) or 0)
        if max_id >= 0 and current >= max_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "identity_limit_exceeded",
                    "message": f"Identity limit reached ({max_id} for {tier.value} tier). Upgrade to create more.",
                    "current_count": current,
                    "max_allowed": max_id,
                    "upgrade_tier": "hobby" if tier.value == "free" else "pro",
                },
            )
    
    # Generate identity ID
    identity_id = uuid.uuid4()
    
    logger.info(f"Creating identity: {identity_id}, user={user_id}, photos={len(photos)}")
    
    # Get S3 service
    s3_service = get_s3_service()
    
    # Create identity record
    identity = Identity(
        id=identity_id,
        user_id=user_db_id,
        name=name,
        trigger_word=trigger_word,
        reference_photo_urls=[],
        reference_photo_count=len(photos),
        training_status=TrainingStatus.VALIDATING,
        training_progress=0,
        consent_given=True,
        consent_timestamp=datetime.utcnow(),
        consent_ip_address=request.client.host if request.client else None,
        consent_user_agent=request.headers.get("user-agent"),
    )
    
    db.add(identity)
    await db.commit()
    await db.refresh(identity)
    
    try:
        # Upload photos to S3
        photo_urls = []
        
        for idx, photo in enumerate(photos):
            try:
                # Read file content
                content = await photo.read()
                
                # Validate file size (max 10MB per photo)
                if len(content) > 10 * 1024 * 1024:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Photo {idx + 1} exceeds 10MB limit"
                    )
                
                # Validate content type
                if not photo.content_type or not photo.content_type.startswith("image/"):
                    raise HTTPException(
                        status_code=400,
                        detail=f"Photo {idx + 1} must be an image file"
                    )
                
                # Upload to S3
                s3_key = f"identities/{user_id}/{identity_id}/photo_{idx}.jpg"
                url = await s3_service.upload_file_async(
                    file_data=content,
                    s3_key=s3_key,
                    content_type=photo.content_type or "image/jpeg",
                )
                photo_urls.append(url)
                
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Failed to upload photo {idx + 1}: {e}")
                # Clean up uploaded photos on error
                for uploaded_url in photo_urls:
                    try:
                        s3_key = extract_s3_key_from_url(uploaded_url)
                        await s3_service.delete_file_async(s3_key)
                    except Exception:
                        pass
                
                # Update identity status
                identity.training_status = TrainingStatus.FAILED
                identity.training_error = f"Failed to upload photo {idx + 1}: {str(e)}"
                await db.commit()
                
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to upload photos: {str(e)}"
                )
        
        # Update identity with photo URLs
        identity.reference_photo_urls = photo_urls
        identity.training_status = TrainingStatus.PENDING
        await db.commit()
        
        # Start training in background
        background_tasks.add_task(
            train_identity_background,
            identity_id=str(identity_id),
            user_id=uid,
            photo_urls=photo_urls,
            trigger_word=trigger_word,
            training_steps=training_steps,
        )
        
        logger.info(f"Identity created: {identity_id}, training started")
        
        return IdentityResponse.model_validate(identity)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error creating identity: {identity_id}")
        
        # Update identity status
        identity.training_status = TrainingStatus.FAILED
        identity.training_error = str(e)
        await db.commit()
        
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create identity: {str(e)}"
        )


async def train_identity_background(
    identity_id: str,
    user_id: str,
    photo_urls: List[str],
    trigger_word: str,
    training_steps: int,
):
    """
    Background task for LoRA training.
    
    Creates a new database session since background tasks run outside request context.
    """
    from app.core.database import AsyncSessionLocal
    
    client_exceptions = get_client_exceptions()
    async with AsyncSessionLocal() as db:
        try:
            # Get identity
            identity = await db.get(Identity, uuid.UUID(identity_id))
            
            if not identity:
                logger.error(f"Identity not found: {identity_id}")
                return
            
            # Update status
            identity.training_status = TrainingStatus.TRAINING
            identity.training_started_at = datetime.utcnow()
            identity.training_progress = 10
            await db.commit()
            
            logger.info(f"Starting LoRA training: {identity_id}")
            
            # Call GPU backend (AWS) for training
            result = await get_gpu_client().train_lora(
                user_id=user_id,
                identity_id=identity_id,
                image_urls=photo_urls,
                trigger_word=trigger_word,
                training_steps=training_steps,
            )
            
            # Update identity with results
            # AWS: training may be async (queued) or sync (completed)
            if result.get("status") == "queued":
                identity.training_status = TrainingStatus.TRAINING
                identity.training_progress = 20
            else:
                identity.training_status = TrainingStatus.COMPLETED
                identity.training_progress = 100
                identity.training_completed_at = datetime.utcnow()
            identity.lora_file_path = result.get("lora_path")
            identity.face_embedding = result.get("face_embedding")
            identity.trigger_word = result.get("trigger_word", trigger_word)
            
            # Extract quality scores if available
            if "quality_score" in result:
                identity.quality_score = result["quality_score"]
            if "face_consistency_score" in result:
                identity.face_consistency_score = result["face_consistency_score"]
            
            await db.commit()
            
            logger.info(f"LoRA training completed: {identity_id}")
            
        except client_exceptions as e:
            logger.error(f"GPU backend training error: {identity_id}, {e}")
            
            identity = await db.get(Identity, uuid.UUID(identity_id))
            if identity:
                identity.training_status = TrainingStatus.FAILED
                identity.training_error = str(e)
                await db.commit()
                
        except Exception as e:
            logger.exception(f"Training error: {identity_id}")
            
            identity = await db.get(Identity, uuid.UUID(identity_id))
            if identity:
                identity.training_status = TrainingStatus.FAILED
                identity.training_error = "Training failed with internal error"
                await db.commit()


@router.get("/{identity_id}", response_model=IdentityResponse)
async def get_identity(
    identity_id: str,
    user_id: CurrentUserId = None,  # type: ignore[reportInvalidTypeForm]
    db: DbSession = None,
):
    """Get identity details and training status."""
    require_auth(user_id)
    uid = str(user_id) if user_id is not None else ""

    # Get user's database UUID
    user_db_id = await get_user_db_id(uid, db)
    
    try:
        identity = await db.get(Identity, uuid.UUID(identity_id))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid identity ID format")
    
    if not identity:
        raise HTTPException(status_code=404, detail="Identity not found")
    
    if identity.is_deleted:
        raise HTTPException(status_code=404, detail="Identity not found")
    
    if identity.user_id != user_db_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return IdentityResponse.model_validate(identity)


@router.get("/", response_model=IdentityListResponse)
async def list_identities(
    user_id: CurrentUserId = None,  # type: ignore[reportInvalidTypeForm]
    db: DbSession = None,
):
    """List user's identities."""
    require_auth(user_id)
    uid = str(user_id) if user_id is not None else ""

    # Get user's database UUID
    user_db_id = await get_user_db_id(uid, db)
    
    result = await db.execute(
        select(Identity)
        .where(Identity.user_id == user_db_id)
        .where(Identity.is_deleted == False)
        .order_by(Identity.created_at.desc())
    )
    identities = result.scalars().all()
    
    return IdentityListResponse(
        identities=[IdentityResponse.model_validate(identity) for identity in identities],
        total=len(identities),
    )


@router.delete("/{identity_id}")
async def delete_identity(
    identity_id: str,
    user_id: CurrentUserId = None,  # type: ignore[reportInvalidTypeForm]
    db: DbSession = None,
):
    """Delete identity and its associated files."""
    require_auth(user_id)
    uid = str(user_id) if user_id is not None else ""

    # Get user's database UUID
    user_db_id = await get_user_db_id(uid, db)
    
    try:
        identity = await db.get(Identity, uuid.UUID(identity_id))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid identity ID format")
    
    if not identity:
        raise HTTPException(status_code=404, detail="Identity not found")
    
    if identity.is_deleted:
        raise HTTPException(status_code=404, detail="Identity already deleted")
    
    if identity.user_id != user_db_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Soft delete
    identity.is_deleted = True
    identity.deleted_at = datetime.utcnow()
    
    # Delete photos from S3
    s3_service = get_s3_service()
    
    for url in identity.reference_photo_urls or []:
        try:
            s3_key = extract_s3_key_from_url(url)
            await s3_service.delete_file_async(s3_key)
        except Exception as e:
            logger.warning(f"Failed to delete S3 file {s3_key}: {e}")
    
    # Delete LoRA file from S3 if exists
    if identity.lora_file_path:
        try:
            s3_key = extract_s3_key_from_url(identity.lora_file_path)
            await s3_service.delete_file_async(s3_key)
        except Exception as e:
            logger.warning(f"Failed to delete LoRA file {s3_key}: {e}")
    
    await db.commit()
    
    logger.info(f"Identity deleted: {identity_id}")
    
    return {"status": "deleted", "id": identity_id}


@router.post("/{identity_id}/retrain", response_model=IdentityResponse)
async def retrain_identity(
    identity_id: str,
    training_steps: int = Form(default=1000, ge=100, le=3000),
    user_id: CurrentUserId = None,  # type: ignore[reportInvalidTypeForm]
    db: DbSession = None,
    background_tasks: BackgroundTasks = None,
):
    """Retrain an existing identity's LoRA model."""
    require_auth(user_id)
    uid = str(user_id) if user_id is not None else ""

    # Get user's database UUID
    user_db_id = await get_user_db_id(uid, db)
    
    try:
        identity = await db.get(Identity, uuid.UUID(identity_id))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid identity ID format")
    
    if not identity:
        raise HTTPException(status_code=404, detail="Identity not found")
    
    if identity.is_deleted:
        raise HTTPException(status_code=404, detail="Identity not found")
    
    if identity.user_id != user_db_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    if identity.training_status == TrainingStatus.TRAINING:
        raise HTTPException(
            status_code=400,
            detail="Training already in progress"
        )
    
    if not identity.reference_photo_urls:
        raise HTTPException(
            status_code=400,
            detail="No reference photos available for retraining"
        )
    
    logger.info(f"Retraining identity: {identity_id}")
    
    # Reset training status
    identity.training_status = TrainingStatus.PENDING
    identity.training_progress = 0
    identity.training_error = None
    identity.training_started_at = None
    identity.training_completed_at = None
    await db.commit()
    
    # Start training
    background_tasks.add_task(
        train_identity_background,
        identity_id=identity_id,
        user_id=uid,
        photo_urls=identity.reference_photo_urls,
        trigger_word=identity.trigger_word,
        training_steps=training_steps,
    )
    
    return IdentityResponse.model_validate(identity)
