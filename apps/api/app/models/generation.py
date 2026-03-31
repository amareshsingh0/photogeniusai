"""Generation model for SQLAlchemy."""
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, JSON, ForeignKey, BigInteger, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid
import enum

from app.core.database import Base


class GenerationMode(str, enum.Enum):
    """Generation mode enum - all AI pipeline types"""
    REALISM = "REALISM"
    CREATIVE = "CREATIVE"
    ROMANTIC = "ROMANTIC"
    CINEMATIC = "CINEMATIC"
    FASHION = "FASHION"
    COOL_EDGY = "COOL_EDGY"
    ARTISTIC = "ARTISTIC"
    MAX_SURPRISE = "MAX_SURPRISE"


class GenerationStatus(str, enum.Enum):
    """Generation status enum"""
    PENDING = "PENDING"
    SAFETY_CHECK = "SAFETY_CHECK"
    GENERATING = "GENERATING"
    POST_SAFETY_CHECK = "POST_SAFETY_CHECK"
    UPLOADING = "UPLOADING"
    COMPLETED = "COMPLETED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"


class Generation(Base):
    """Generation model for image generation."""
    
    __tablename__ = "generations"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Foreign keys
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    identity_id = Column(UUID(as_uuid=True), ForeignKey("identities.id", ondelete="RESTRICT"), nullable=True, index=True)
    
    # Generation config
    mode = Column(SQLEnum(GenerationMode), nullable=False)
    original_prompt = Column(String(1000), nullable=False)
    enhanced_prompt = Column(String, nullable=True)
    negative_prompt = Column(String, nullable=True)
    
    # Generation parameters
    num_inference_steps = Column(Integer, default=30, nullable=False)
    guidance_scale = Column(Float, default=7.5, nullable=False)
    seed = Column(BigInteger, nullable=True)
    width = Column(Integer, default=1024, nullable=False)
    height = Column(Integer, default=1024, nullable=False)
    
    # Output
    output_urls = Column(JSON, nullable=True)  # Array of S3 URLs with metadata
    selected_output_url = Column(String, nullable=True)  # User's favorite
    thumbnail_url = Column(String, nullable=True)
    
    # Quality scores
    face_match_score = Column(Float, nullable=True)  # 0-100
    aesthetic_score = Column(Float, nullable=True)  # 0-100
    technical_score = Column(Float, nullable=True)  # 0-100
    overall_score = Column(Float, nullable=True)  # 0-100
    
    # Safety
    safety_status = Column(String(50), nullable=True)  # ALLOW, BLOCK, QUARANTINE
    safety_violations = Column(JSON, nullable=True)  # List of violations
    block_reason = Column(String, nullable=True)
    
    # Status tracking
    status = Column(SQLEnum(GenerationStatus), default=GenerationStatus.PENDING, nullable=False, index=True)
    error_message = Column(String, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    # user = relationship("User", back_populates="generations")
    # identity = relationship("Identity", back_populates="generations")
