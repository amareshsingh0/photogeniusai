"""
Pydantic models for API v1 requests and responses.
"""

from pydantic import BaseModel, Field, HttpUrl  # type: ignore[reportMissingImports]
from typing import List, Optional, Literal
from enum import Enum


class QualityTier(str, Enum):
    """Quality tiers for generation"""
    STANDARD = "standard"
    BALANCED = "balanced"
    PREMIUM = "premium"
    ULTRA = "ultra"


class GenerationMode(str, Enum):
    """Generation modes - all AI pipeline types"""
    REALISM = "REALISM"
    CREATIVE = "CREATIVE"
    ROMANTIC = "ROMANTIC"
    FASHION = "FASHION"
    CINEMATIC = "CINEMATIC"
    COOL_EDGY = "COOL_EDGY"
    ARTISTIC = "ARTISTIC"
    MAX_SURPRISE = "MAX_SURPRISE"


class JobStatus(str, Enum):
    """Job status values"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ==================== Request Models ====================

class GenerateRequest(BaseModel):
    """Request for image generation"""
    prompt: str = Field(..., min_length=1, max_length=1000, description="Generation prompt")
    mode: GenerationMode = Field(default=GenerationMode.REALISM, description="Generation mode")
    identity_id: Optional[str] = Field(None, description="Optional identity ID for face consistency")
    quality_tier: QualityTier = Field(default=QualityTier.BALANCED, description="Quality tier")
    num_images: int = Field(default=2, ge=1, le=4, description="Number of images to generate")
    webhook_url: Optional[HttpUrl] = Field(None, description="Webhook URL for job completion notification")
    seed: Optional[int] = Field(None, description="Random seed for reproducibility")
    creative: Optional[float] = Field(None, ge=0.0, le=1.0, description="Creative level 0–1; when > 0 uses Creative Engine")
    style: Optional[str] = Field(None, description="Style or preset name for Creative Engine (e.g. cinematic_lighting, Pro Headshot)")
    use_mutations: bool = Field(default=True, description="Enable mutation-based ensemble when using Creative Engine")
    width: int = Field(default=1024, ge=256, le=4096, description="Requested width (capped by user_tier)")
    height: int = Field(default=1024, ge=256, le=4096, description="Requested height (capped by user_tier)")
    user_tier: Optional[str] = Field(None, description="Subscription tier for resolution caps: free|hobby|pro|studio|enterprise")
    use_face_ensemble: bool = Field(default=False, description="Use InsightFace+DeepFace+FaceNet ensemble for face scoring when reference image available")


class RefineRequest(BaseModel):
    """Request for image refinement"""
    image_base64: str = Field(..., description="Base64 encoded image")
    refinement_request: str = Field(..., min_length=1, max_length=500, description="Natural language refinement request")
    generation_history: List[dict] = Field(..., description="Generation/refinement history")
    mode: GenerationMode = Field(default=GenerationMode.REALISM, description="Generation mode")
    seed: Optional[int] = Field(None, description="Random seed for reproducibility")
    webhook_url: Optional[HttpUrl] = Field(None, description="Webhook URL for job completion notification")


class TrainIdentityRequest(BaseModel):
    """Request for identity training"""
    images: List[str] = Field(..., min_items=5, max_items=20, description="Base64 encoded images (min 5)")
    identity_name: str = Field(..., min_length=1, max_length=100, description="Name for the identity")
    webhook_url: Optional[HttpUrl] = Field(None, description="Webhook URL for training completion notification")


# ==================== Response Models ====================

class JobResponse(BaseModel):
    """Response for job creation"""
    job_id: str = Field(..., description="Unique job identifier")
    status: JobStatus = Field(..., description="Current job status")
    estimated_time: int = Field(..., description="Estimated completion time in seconds")
    status_url: str = Field(..., description="URL to check job status")


class ImageResult(BaseModel):
    """Single image result"""
    image_url: str = Field(..., description="CDN URL of generated image")
    rank: int = Field(..., description="Rank/quality score (1 = best)")
    similarity: Optional[float] = Field(None, ge=0.0, le=1.0, description="Face similarity score if identity_id provided")
    score: Optional[float] = Field(None, description="Overall quality score")


class StatusResponse(BaseModel):
    """Job status response"""
    job_id: str = Field(..., description="Job identifier")
    status: JobStatus = Field(..., description="Current status")
    progress: int = Field(..., ge=0, le=100, description="Progress percentage")
    results: Optional[List[ImageResult]] = Field(None, description="Results if completed")
    error: Optional[str] = Field(None, description="Error message if failed")
    created_at: Optional[str] = Field(None, description="Job creation timestamp")
    completed_at: Optional[str] = Field(None, description="Job completion timestamp")


class TrainingJobResponse(BaseModel):
    """Response for training job creation"""
    training_job_id: str = Field(..., description="Unique training job identifier")
    status: JobStatus = Field(..., description="Current status")
    estimated_time: int = Field(..., description="Estimated completion time in seconds")
    status_url: str = Field(..., description="URL to check training status")


class StyleInfo(BaseModel):
    """Style information"""
    id: str = Field(..., description="Style identifier")
    name: str = Field(..., description="Style display name")
    description: str = Field(..., description="Style description")
    preview_url: Optional[str] = Field(None, description="Preview image URL")


class StylesResponse(BaseModel):
    """Response for styles list"""
    styles: List[StyleInfo] = Field(..., description="Available styles")


class ErrorResponse(BaseModel):
    """Error response"""
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Detailed error information")
    code: Optional[str] = Field(None, description="Error code")


# ==================== Webhook Models ====================

class WebhookPayload(BaseModel):
    """Webhook payload structure"""
    job_id: str = Field(..., description="Job identifier")
    status: JobStatus = Field(..., description="Job status")
    results: Optional[List[ImageResult]] = Field(None, description="Results if completed")
    error: Optional[str] = Field(None, description="Error if failed")
    timestamp: str = Field(..., description="Event timestamp")


class TrainingWebhookPayload(BaseModel):
    """Training webhook payload"""
    training_job_id: str = Field(..., description="Training job identifier")
    status: JobStatus = Field(..., description="Status")
    identity_id: Optional[str] = Field(None, description="Created identity ID if completed")
    error: Optional[str] = Field(None, description="Error if failed")
    timestamp: str = Field(..., description="Event timestamp")
