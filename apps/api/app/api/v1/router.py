"""
API v1 router. Mounts auth, identities, generation, gallery, admin, storage, unified_generate, variants, preferences.
"""
from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    generation,
    identities,
    gallery,
    admin,
    storage,
    unified_generate,
    generate_stream,
    variants,
    preferences,
    edit_image,
    upscale_image,
    logo_overlay,
)

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(identities.router, prefix="/identities", tags=["identities"])
api_router.include_router(generation.router, prefix="/generation", tags=["generation"])
api_router.include_router(unified_generate.router, tags=["unified-generation"])
api_router.include_router(generate_stream.router, tags=["streaming"])
api_router.include_router(variants.router, prefix="/variants", tags=["variants"])
api_router.include_router(preferences.router, prefix="/preferences", tags=["preferences"])
api_router.include_router(gallery.router, prefix="/gallery", tags=["gallery"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(storage.router, prefix="/storage", tags=["storage"])
api_router.include_router(edit_image.router, tags=["edit"])
api_router.include_router(upscale_image.router, tags=["upscale"])
api_router.include_router(logo_overlay.router, tags=["logo"])