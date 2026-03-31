"""
AI Orchestrator API - v3 endpoints

Unified AI generation with automatic service coordination
"""

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from app.services.ai_orchestrator import ai_orchestrator

logger = logging.getLogger(__name__)
router = APIRouter(tags=["v3-ai-orchestrator"])


# ==================== Request/Response Models ====================


class GenerateRequest(BaseModel):
    """Smart generation request with automatic AI coordination"""

    prompt: str = Field(..., description="User prompt", min_length=1, max_length=2000)
    quality: str = Field('STANDARD', description="Quality tier: FAST, STANDARD, PREMIUM")
    width: int = Field(1024, ge=512, le=2048, description="Image width")
    height: int = Field(1024, ge=512, le=2048, description="Image height")
    mode: Optional[str] = Field(None, description="Override mode detection (REALISM, CINEMATIC, etc.)")
    enhancement_level: str = Field('standard', description="Prompt enhancement: simple, standard, advanced, cinematic")
    use_two_pass: bool = Field(False, description="Use preview + full quality workflow")
    use_identity: Optional[str] = Field(None, description="Identity ID for face consistency")
    user_id: Optional[str] = Field(None, description="User ID for personalization")


class TwoPassRequest(BaseModel):
    """Two-pass generation request"""

    prompt: str = Field(..., description="User prompt", min_length=1, max_length=2000)
    quality: str = Field('STANDARD', description="Quality tier: STANDARD or PREMIUM")
    width: int = Field(1024, ge=512, le=2048, description="Image width")
    height: int = Field(1024, ge=512, le=2048, description="Image height")
    skip_preview: bool = Field(False, description="Skip preview pass, only generate full quality")


class CreateIdentityRequest(BaseModel):
    """Create identity from reference photos"""

    photos: List[str] = Field(..., description="5-20 reference photos (URLs or base64)", min_items=5, max_items=20)
    identity_name: str = Field(..., description="Name for this identity", min_length=1, max_length=100)
    user_id: str = Field(..., description="User ID")


class IdentityGenerateRequest(BaseModel):
    """Generate with existing identity"""

    prompt: str = Field(..., description="Generation prompt", min_length=1, max_length=2000)
    identity_id: str = Field(..., description="Identity ID")
    quality: str = Field('STANDARD', description="Quality tier: FAST, STANDARD, PREMIUM")
    width: int = Field(1024, ge=512, le=2048, description="Image width")
    height: int = Field(1024, ge=512, le=2048, description="Image height")


class GroupPhotoRequest(BaseModel):
    """Generate group photo with multiple identities"""

    identities: List[str] = Field(..., description="Identity IDs (2-5 people)", min_items=2, max_items=5)
    prompt: str = Field(..., description="Generation prompt", min_length=1, max_length=2000)
    layout: str = Field('auto', description="Group layout: auto, line, circle, casual")
    quality: str = Field('STANDARD', description="Quality tier: FAST, STANDARD, PREMIUM")


class GenerateResponse(BaseModel):
    """Generation response with full metadata"""

    request_id: str
    success: bool
    image_url: Optional[str] = None
    preview_url: Optional[str] = None
    orchestration: Dict[str, Any]
    quality_scores: Optional[Dict[str, float]] = None
    metadata: Dict[str, Any]
    error: Optional[str] = None


class StatusResponse(BaseModel):
    """AI system status"""

    status: str
    services: Dict[str, Any]
    available_modes: List[str]
    available_categories: List[str]
    quality_tiers: List[str]
    backends: Dict[str, bool]


# ==================== Endpoints ====================


@router.post(
    "/generate",
    response_model=GenerateResponse,
    summary="Smart AI generation",
    description="Main endpoint - automatic mode detection, prompt enhancement, quality routing"
)
async def generate_image(request: GenerateRequest) -> GenerateResponse:
    """
    Smart AI generation with automatic coordination

    Features:
    - Auto-detect mode (REALISM, CINEMATIC, etc.)
    - Auto-detect category (portrait, landscape, etc.)
    - Enhance prompt based on mode + category
    - Route to appropriate quality tier
    - Score quality
    - Return complete metadata
    """
    request_id = f"gen_{uuid.uuid4().hex[:16]}"
    start_time = time.time()

    try:
        # Initialize orchestrator if needed
        if not ai_orchestrator.services_loaded:
            await ai_orchestrator.initialize()

        # Generate
        result = await ai_orchestrator.generate(
            prompt=request.prompt,
            quality=request.quality,
            width=request.width,
            height=request.height,
            mode=request.mode,
            use_two_pass=request.use_two_pass,
            use_identity=request.use_identity,
            enhancement_level=request.enhancement_level
        )

        # Add request metadata
        result['request_id'] = request_id
        result['metadata'] = result.get('metadata', {})
        result['metadata']['request_time'] = datetime.now(timezone.utc).isoformat()
        result['metadata']['total_time'] = time.time() - start_time

        logger.info(
            f"Generation complete: {request_id}",
            extra={
                'request_id': request_id,
                'quality': request.quality,
                'mode': result.get('orchestration', {}).get('detected_mode'),
                'time': round(time.time() - start_time, 2)
            }
        )

        return GenerateResponse(
            request_id=request_id,
            success=result.get('success', False),
            image_url=result.get('image_url'),
            preview_url=result.get('preview_url'),
            orchestration=result.get('orchestration', {}),
            quality_scores=result.get('quality_scores'),
            metadata=result.get('metadata', {}),
            error=result.get('error')
        )

    except Exception as e:
        logger.error(f"Generation failed: {request_id}", exc_info=True)
        return GenerateResponse(
            request_id=request_id,
            success=False,
            image_url=None,
            orchestration={},
            metadata={'error_time': datetime.now(timezone.utc).isoformat()},
            error=str(e)
        )


@router.post(
    "/generate/two-pass",
    response_model=Dict,
    summary="Two-pass generation",
    description="Generate preview + full quality (fast preview shown first, then full quality)"
)
async def generate_two_pass(request: TwoPassRequest) -> Dict:
    """
    Two-pass generation workflow

    Returns:
    - preview: Fast preview image (SDXL-Turbo, 3-5s)
    - full: Full quality image (SDXL-Base or Base+Refiner, 25-50s)
    - metadata: Timing and quality information
    """
    request_id = f"2pass_{uuid.uuid4().hex[:16]}"

    try:
        # Initialize orchestrator if needed
        if not ai_orchestrator.services_loaded:
            await ai_orchestrator.initialize()

        # Import two-pass generator
        from app.services.generation.two_pass_generator import two_pass_generator

        # Generate
        result = await two_pass_generator.generate_two_pass(
            prompt=request.prompt,
            quality=request.quality,
            width=request.width,
            height=request.height,
            skip_preview=request.skip_preview
        )

        result['request_id'] = request_id
        result['timestamp'] = datetime.now(timezone.utc).isoformat()

        logger.info(f"Two-pass generation complete: {request_id}")

        return result

    except Exception as e:
        logger.error(f"Two-pass generation failed: {request_id}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/identity/create",
    response_model=Dict,
    summary="Create identity from photos",
    description="Create reusable identity from 5-20 reference photos"
)
async def create_identity(request: CreateIdentityRequest) -> Dict:
    """
    Create identity from reference photos

    Requires:
    - 5-20 high-quality reference photos
    - Clear, well-lit face shots
    - Consistent person across all photos

    Returns:
    - identity_id: Use this for identity-based generation
    - quality_score: How good the identity extraction was
    - metadata: Analysis of reference photos
    """
    request_id = f"ident_{uuid.uuid4().hex[:16]}"

    try:
        # Initialize orchestrator if needed
        if not ai_orchestrator.services_loaded:
            await ai_orchestrator.initialize()

        # Import identity engine
        from app.services.identity.identity_engine import identity_engine

        # Create identity
        result = await identity_engine.create_identity_from_photos(
            photos=request.photos,
            identity_name=request.identity_name,
            user_id=request.user_id
        )

        result['request_id'] = request_id
        result['timestamp'] = datetime.now(timezone.utc).isoformat()

        logger.info(f"Identity created: {request_id} -> {result.get('identity_id')}")

        return result

    except Exception as e:
        logger.error(f"Identity creation failed: {request_id}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/identity/generate",
    response_model=GenerateResponse,
    summary="Generate with identity",
    description="Generate image with consistent face from identity"
)
async def generate_with_identity(request: IdentityGenerateRequest) -> GenerateResponse:
    """
    Generate image with consistent face

    Uses InstantID to maintain face consistency across generations
    """
    request_id = f"idgen_{uuid.uuid4().hex[:16]}"
    start_time = time.time()

    try:
        # Initialize orchestrator if needed
        if not ai_orchestrator.services_loaded:
            await ai_orchestrator.initialize()

        # Generate with identity
        result = await ai_orchestrator.generate(
            prompt=request.prompt,
            quality=request.quality,
            width=request.width,
            height=request.height,
            use_identity=request.identity_id
        )

        result['request_id'] = request_id
        result['metadata'] = result.get('metadata', {})
        result['metadata']['total_time'] = time.time() - start_time

        logger.info(f"Identity generation complete: {request_id}")

        return GenerateResponse(
            request_id=request_id,
            success=result.get('success', False),
            image_url=result.get('image_url'),
            preview_url=result.get('preview_url'),
            orchestration=result.get('orchestration', {}),
            quality_scores=result.get('quality_scores'),
            metadata=result.get('metadata', {}),
            error=result.get('error')
        )

    except Exception as e:
        logger.error(f"Identity generation failed: {request_id}", exc_info=True)
        return GenerateResponse(
            request_id=request_id,
            success=False,
            image_url=None,
            orchestration={},
            metadata={},
            error=str(e)
        )


@router.post(
    "/group-photo",
    response_model=Dict,
    summary="Generate group photo",
    description="Generate photo with multiple identities (2-5 people)"
)
async def generate_group_photo(request: GroupPhotoRequest) -> Dict:
    """
    Generate group photo with multiple identities

    Features:
    - Automatic layout selection
    - Natural positioning
    - Consistent lighting across all faces
    """
    request_id = f"group_{uuid.uuid4().hex[:16]}"

    try:
        # Initialize orchestrator if needed
        if not ai_orchestrator.services_loaded:
            await ai_orchestrator.initialize()

        # Generate group photo
        result = await ai_orchestrator.generate_group_photo(
            identities=request.identities,
            prompt=request.prompt,
            layout=request.layout,
            quality=request.quality
        )

        result['request_id'] = request_id
        result['timestamp'] = datetime.now(timezone.utc).isoformat()

        logger.info(f"Group photo generated: {request_id}")

        return result

    except Exception as e:
        logger.error(f"Group photo generation failed: {request_id}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/status",
    response_model=StatusResponse,
    summary="AI system status",
    description="Check AI orchestrator and all services status"
)
async def get_status() -> StatusResponse:
    """
    Get AI system status and capabilities

    Returns:
    - Available services and their status
    - Supported modes and categories
    - Backend configuration
    """
    try:
        # Initialize orchestrator if needed
        if not ai_orchestrator.services_loaded:
            await ai_orchestrator.initialize()

        status = await ai_orchestrator.get_status()

        # Add backend status
        from app.services.smart.generation_router import generation_router
        import os

        # Check which backends are configured
        backends = {
            'huggingface': os.getenv('HUGGINGFACE_API_TOKEN', '') != '',
            'replicate': bool(generation_router.replicate_api_token),
            'sagemaker': bool(generation_router.sagemaker_fast_endpoint or
                            generation_router.sagemaker_standard_endpoint or
                            generation_router.sagemaker_premium_endpoint)
        }

        return StatusResponse(
            status=status['status'],
            services=status['services'],
            available_modes=list(status['available_modes']),
            available_categories=list(status['available_categories']),
            quality_tiers=status['quality_tiers'],
            backends=backends
        )

    except Exception as e:
        logger.error("Status check failed", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/health",
    summary="Health check (v3)",
    description="Simple health check for monitoring"
)
async def health_check() -> Dict[str, Any]:
    """Health check for load balancers and monitoring"""
    try:
        status = await ai_orchestrator.get_status()
        return {
            'status': 'healthy' if status['status'] == 'ready' else 'degraded',
            'version': '3.0.0',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'ai_orchestrator': status['status']
        }
    except Exception as e:
        return {
            'status': 'unhealthy',
            'version': '3.0.0',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'error': str(e)
        }


@router.get(
    "/modes",
    summary="List generation modes",
    description="Get all available generation modes with descriptions"
)
async def list_modes() -> Dict[str, Any]:
    """List all available generation modes"""
    from app.services.smart.mode_detector import mode_detector

    # Mode descriptions
    descriptions = {
        'REALISM': 'Photorealistic images',
        'CINEMATIC': 'Movie-like, dramatic scenes',
        'CREATIVE': 'Artistic, imaginative',
        'FANTASY': 'Magical, mythical worlds',
        'ANIME': 'Anime/manga style'
    }

    return {
        'modes': [
            {
                'id': mode_id,
                'name': mode_id.title(),
                'description': descriptions.get(mode_id, ''),
                'example_keywords': keywords[:5]
            }
            for mode_id, keywords in mode_detector.MODES.items()
        ]
    }


@router.get(
    "/categories",
    summary="List image categories",
    description="Get all available image categories"
)
async def list_categories() -> Dict[str, Any]:
    """List all available image categories"""
    from app.services.smart.category_detector import category_detector

    # Category descriptions
    descriptions = {
        'portrait': 'People, faces, headshots',
        'landscape': 'Nature, scenery, outdoor',
        'product': 'Objects, items, commercial',
        'architecture': 'Buildings, structures',
        'food': 'Meals, dishes, cuisine',
        'animal': 'Pets, wildlife',
        'abstract': 'Patterns, geometric, design',
        'interior': 'Room, indoor spaces'
    }

    return {
        'categories': [
            {
                'id': cat_id,
                'name': cat_id.title(),
                'description': descriptions.get(cat_id, ''),
                'example_keywords': keywords[:5]
            }
            for cat_id, keywords in category_detector.CATEGORIES.items()
        ]
    }
