"""Generation schemas for request/response."""
from pydantic import BaseModel, Field  # type: ignore[reportMissingImports]
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class GenerationMode(str, Enum):
    """Generation mode enum - all AI pipeline types"""
    REALISM = "REALISM"
    CREATIVE = "CREATIVE"
    ROMANTIC = "ROMANTIC"
    CINEMATIC = "CINEMATIC"
    FASHION = "FASHION"
    COOL_EDGY = "COOL_EDGY"
    ARTISTIC = "ARTISTIC"
    MAX_SURPRISE = "MAX_SURPRISE"


class GenerationStatus(str, Enum):
    """Generation status enum"""
    PENDING = "PENDING"
    SAFETY_CHECK = "SAFETY_CHECK"
    GENERATING = "GENERATING"
    POST_SAFETY_CHECK = "POST_SAFETY_CHECK"
    UPLOADING = "UPLOADING"
    COMPLETED = "COMPLETED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"


class GenerationCreate(BaseModel):
    """Request schema for creating generation"""
    prompt: str = Field(..., min_length=1, max_length=1000)
    mode: str = Field(default="REALISM", pattern="^(REALISM|CREATIVE|ROMANTIC|CINEMATIC|FASHION|COOL_EDGY|ARTISTIC|MAX_SURPRISE)$")
    identity_id: Optional[str] = None
    num_candidates: Optional[int] = Field(default=4, ge=1, le=8)
    guidance_scale: Optional[float] = Field(default=7.5, ge=1.0, le=20.0)
    num_inference_steps: Optional[int] = Field(default=40, ge=20, le=100)
    seed: Optional[int] = None


class GenerationResponse(BaseModel):
    """Response schema for generation"""
    id: str
    user_id: str
    identity_id: Optional[str] = None
    mode: str
    original_prompt: str
    enhanced_prompt: Optional[str] = None
    negative_prompt: Optional[str] = None
    num_inference_steps: int
    guidance_scale: float
    seed: Optional[int] = None
    width: int
    height: int
    output_urls: Optional[List[Dict[str, Any]]] = None
    selected_output_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    face_match_score: Optional[float] = None
    aesthetic_score: Optional[float] = None
    technical_score: Optional[float] = None
    overall_score: Optional[float] = None
    safety_status: Optional[str] = None
    safety_violations: Optional[List[Dict[str, Any]]] = None
    block_reason: Optional[str] = None
    status: str
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class GenerationOut(BaseModel):
    """Simplified generation output"""
    id: str
    status: str
    outputUrls: List[str] = Field(default_factory=list)
