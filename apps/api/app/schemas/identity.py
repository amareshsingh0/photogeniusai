"""Identity schemas for request/response."""
from pydantic import BaseModel, Field  # type: ignore[reportMissingImports]
from typing import List, Optional
from datetime import datetime
from enum import Enum


class TrainingStatus(str, Enum):
    """Training status enum"""
    PENDING = "PENDING"
    VALIDATING = "VALIDATING"
    PREPROCESSING = "PREPROCESSING"
    TRAINING = "TRAINING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class IdentityCreate(BaseModel):
    """Request schema for creating identity (with image URLs)"""
    name: str = Field(..., min_length=1, max_length=100)
    image_urls: List[str] = Field(..., min_items=5, max_items=20)
    trigger_word: str = Field(default="sks", min_length=2, max_length=20)
    training_steps: int = Field(default=1000, ge=100, le=3000)


class IdentityResponse(BaseModel):
    """Response schema for identity"""
    id: str
    user_id: str
    name: str
    description: Optional[str] = None
    trigger_word: str
    reference_photo_urls: List[str]
    reference_photo_count: int
    lora_file_path: Optional[str] = None
    face_embedding: Optional[List[float]] = None
    training_status: str
    training_progress: int = Field(ge=0, le=100)
    training_started_at: Optional[datetime] = None
    training_completed_at: Optional[datetime] = None
    training_error: Optional[str] = None
    quality_score: Optional[float] = None
    face_consistency_score: Optional[float] = None
    consent_given: bool
    total_generations: int
    last_used_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class IdentityListResponse(BaseModel):
    """Response schema for listing identities"""
    identities: List[IdentityResponse]
    total: int


class IdentityOut(BaseModel):
    """Simplified identity output"""
    id: str
    name: str
    training_status: str
    thumbnail_url: Optional[str] = None
