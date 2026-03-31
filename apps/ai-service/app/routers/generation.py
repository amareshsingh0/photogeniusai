from fastapi import APIRouter, HTTPException  # type: ignore[reportMissingImports]
from app.models.generation import GenerationRequest, PreviewResponse, FullQualityResponse  # type: ignore[reportAttributeAccessIssue]
from app.services.ai import sdxl_pipeline  # type: ignore[reportAttributeAccessIssue]
from app.services.safety.dual_pipeline import run_pipeline  # type: ignore[reportAttributeAccessIssue]

router = APIRouter()


@router.post("/preview", response_model=PreviewResponse)
async def preview(req: GenerationRequest) -> PreviewResponse:
    """
    Generate a quick preview (~3s) using SDXL-Turbo.
    Runs Layer 1 safety check before generation.
    """
    # Layer 1: Pre-generation safety check
    safety = run_pipeline(req.prompt)
    if not safety.allowed:
        raise HTTPException(status_code=400, detail=safety.blocked_reason)
    
    # Generate preview
    preview_url = await sdxl_pipeline.generate_preview(
        prompt=safety.pre_check.modified_prompt,
        identity_embedding=None,  # TODO: Load from identity_id
    )
    
    return PreviewResponse(
        preview_image=preview_url,
        message="Quick preview ready! Generating full quality...",
        estimated_time="25 seconds",
        quality_level="Preview (Full quality coming soon)",
    )


@router.post("/full", response_model=FullQualityResponse)
async def full_quality(req: GenerationRequest) -> FullQualityResponse:
    """
    Generate full-quality image with Best-of-N selection.
    Runs Layer 1 + Layer 2 safety checks.
    """
    # Layer 1: Pre-generation safety check
    safety = run_pipeline(req.prompt)
    if not safety.allowed:
        raise HTTPException(status_code=400, detail=safety.blocked_reason)
    
    # Generate full quality with Best-of-N
    full_url = await sdxl_pipeline.generate_full(
        prompt=safety.pre_check.modified_prompt,
        identity_embedding=None,  # TODO: Load from identity_id
        num_outputs=req.num_outputs,
    )
    
    # Layer 2: Post-generation safety check
    post_safety = run_pipeline(req.prompt, image_url=full_url)
    if not post_safety.allowed:
        raise HTTPException(status_code=400, detail=post_safety.blocked_reason)
    
    return FullQualityResponse(
        final_image=full_url,
        message="Final best-of-2 ready",
    )
