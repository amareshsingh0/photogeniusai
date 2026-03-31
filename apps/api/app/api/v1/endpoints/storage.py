"""Storage endpoints: upload, download, signed URLs."""
from fastapi import APIRouter, File, UploadFile, HTTPException
from fastapi.responses import StreamingResponse

from app.core.dependencies import CurrentUserId
from app.core.security import require_auth
from app.services.storage import get_s3_service

router = APIRouter()


@router.post("/upload")
async def upload_file(
    user_id: CurrentUserId,
    file: UploadFile = File(...),
    folder: str = "uploads",
):
    """
    Upload file to S3/R2.
    Returns: { "url": "...", "key": "..." }
    """
    require_auth(user_id)

    s3_service = get_s3_service()
    if not s3_service.bucket or not s3_service.access_key:
        raise HTTPException(status_code=503, detail="S3 storage not configured")

    # Generate S3 key: folder/user_id/filename
    import uuid
    from pathlib import Path

    ext = Path(file.filename or "file").suffix
    s3_key = f"{folder}/{user_id}/{uuid.uuid4()}{ext}"

    try:
        # Read file data
        file_data = await file.read()
        content_type = file.content_type or "application/octet-stream"

        # Upload to S3/R2
        url = await s3_service.upload_file_async(
            file_data,
            s3_key,
            content_type=content_type,
        )

        return {"url": url, "key": s3_key, "filename": file.filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}") from e


@router.get("/presigned/{key:path}")
async def get_presigned_url(
    key: str,
    user_id: CurrentUserId,
    expiration: int = 3600,
):
    """
    Generate presigned URL for file access.
    expiration: seconds (default 1 hour, max 7 days).
    """
    require_auth(user_id)

    s3_service = get_s3_service()
    if not s3_service.bucket or not s3_service.access_key:
        raise HTTPException(status_code=503, detail="S3 storage not configured")

    try:
        url = await s3_service.generate_presigned_url_async(
            key,
            expiration=min(expiration, 604800),  # Max 7 days
        )
        return {"url": url, "expires_in": expiration}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate URL: {str(e)}") from e


@router.delete("/{key:path}")
async def delete_file(
    key: str,
    user_id: CurrentUserId,
):
    """Delete file from S3/R2."""
    require_auth(user_id)

    s3_service = get_s3_service()
    if not s3_service.bucket or not s3_service.access_key:
        raise HTTPException(status_code=503, detail="S3 storage not configured")

    try:
        await s3_service.delete_file_async(key)
        return {"deleted": key}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}") from e
