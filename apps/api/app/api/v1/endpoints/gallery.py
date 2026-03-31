"""
Gallery API - Manage user generations

Features:
- List user generations with filtering
- Public gallery
- Get single generation
- Delete generation
- Toggle favorite
- Auto-delete after 15 days
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional

from app.core.dependencies import CurrentUserId, DbSession
from app.core.security import require_auth
from app.services.gallery import GalleryService, GalleryCleanupService

router = APIRouter()
gallery_service = GalleryService()
cleanup_service = GalleryCleanupService(delete_after_days=15)


@router.get("")
async def list_generations(
    user_id: CurrentUserId,
    db: DbSession,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    mode: Optional[str] = Query(None),
    is_favorite: Optional[bool] = Query(None)
):
    """
    List generations for current user

    Query Parameters:
    - limit: Max results (1-100, default: 20)
    - offset: Skip N results (default: 0)
    - mode: Filter by mode (REALISM, CINEMATIC, etc.)
    - is_favorite: Filter favorites (true/false)

    Returns:
    - generations: List of generation objects
    - total: Total count
    - has_more: Whether more results exist
    """
    require_auth(user_id)

    result = await gallery_service.list_user_generations(
        db=db,
        user_id=user_id,
        limit=limit,
        offset=offset,
        mode=mode,
        is_favorite=is_favorite
    )

    return result


@router.get("/public")
async def public_gallery(
    db: DbSession,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    category: Optional[str] = Query(None),
    style: Optional[str] = Query(None)
):
    """
    Public gallery - approved public generations

    Query Parameters:
    - limit: Max results (1-100, default: 20)
    - offset: Skip N results
    - category: Filter by category (portrait, landscape, etc.)
    - style: Filter by style (cinematic, artistic, etc.)
    """

    result = await gallery_service.get_public_gallery(
        db=db,
        limit=limit,
        offset=offset,
        category=category,
        style=style
    )

    return result


@router.get("/stats")
async def storage_stats(
    user_id: CurrentUserId,
    db: DbSession
):
    """
    Get storage statistics

    Shows:
    - Total generations
    - Generations eligible for auto-deletion
    - Protected favorites
    - Deletion cutoff date
    """
    require_auth(user_id)

    stats = await cleanup_service.get_storage_stats(db)

    return stats


@router.get("/{generation_id}")
async def get_generation(
    generation_id: str,
    user_id: CurrentUserId,
    db: DbSession
):
    """
    Get single generation

    Access:
    - Owner can always access
    - Public generations accessible to all
    """
    require_auth(user_id)

    generation = await gallery_service.get_generation(
        db=db,
        generation_id=generation_id,
        user_id=user_id
    )

    if not generation:
        raise HTTPException(404, "Generation not found or access denied")

    return generation


@router.delete("/{generation_id}")
async def delete_generation(
    generation_id: str,
    user_id: CurrentUserId,
    db: DbSession
):
    """
    Soft delete a generation

    Process:
    1. Verify ownership
    2. Delete images from S3
    3. Soft delete in database (isDeleted = true)

    Note: Favorites are never auto-deleted
    """
    require_auth(user_id)

    result = await gallery_service.delete_generation(
        db=db,
        generation_id=generation_id,
        user_id=user_id
    )

    if not result['success']:
        raise HTTPException(400, result.get('error', 'Delete failed'))

    return result


@router.post("/{generation_id}/favorite")
async def toggle_favorite(
    generation_id: str,
    user_id: CurrentUserId,
    db: DbSession
):
    """
    Toggle favorite status

    Favorites are protected from auto-deletion
    """
    require_auth(user_id)

    result = await gallery_service.toggle_favorite(
        db=db,
        generation_id=generation_id,
        user_id=user_id
    )

    if not result['success']:
        raise HTTPException(400, result.get('error', 'Toggle failed'))

    return result


@router.post("/cleanup/run")
async def run_cleanup(
    user_id: CurrentUserId,
    db: DbSession
):
    """
    Manually trigger cleanup (admin only)

    Deletes generations older than 15 days
    """
    require_auth(user_id)

    # TODO: Add admin check
    # if not is_admin(user_id):
    #     raise HTTPException(403, "Admin only")

    result = await cleanup_service.cleanup_old_generations(db)

    return result
