"""Identity model for SQLAlchemy."""
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, JSON, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid
import enum

from app.core.database import Base


class TrainingStatus(str, enum.Enum):
    """Training status enum"""
    PENDING = "PENDING"
    VALIDATING = "VALIDATING"
    PREPROCESSING = "PREPROCESSING"
    TRAINING = "TRAINING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class Identity(Base):
    """Identity model for LoRA training."""
    
    __tablename__ = "identities"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Foreign key
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Identity info
    name = Column(String(100), nullable=False)
    description = Column(String(500), nullable=True)
    trigger_word = Column(String(20), default="sks", nullable=False)
    
    # Training data
    reference_photo_urls = Column(JSON, nullable=False)  # Array of S3 URLs
    reference_photo_count = Column(Integer, default=0, nullable=False)
    
    # LoRA & Embedding
    lora_file_path = Column(String, nullable=True)  # S3 URL to .safetensors
    lora_file_size = Column(Integer, nullable=True)  # Bytes
    face_embedding = Column(JSON, nullable=True)  # 512-dim vector for InstantID
    
    # Training status
    training_status = Column(SQLEnum(TrainingStatus), default=TrainingStatus.PENDING, nullable=False, index=True)
    training_progress = Column(Integer, default=0, nullable=False)  # 0-100
    training_started_at = Column(DateTime(timezone=True), nullable=True)
    training_completed_at = Column(DateTime(timezone=True), nullable=True)
    training_error = Column(String, nullable=True)
    training_logs = Column(JSON, nullable=True)
    
    # Quality metrics
    quality_score = Column(Float, nullable=True)  # 0-1
    face_consistency_score = Column(Float, nullable=True)  # 0-1
    
    # Consent
    consent_given = Column(Boolean, default=False, nullable=False)
    consent_timestamp = Column(DateTime(timezone=True), nullable=True)
    consent_ip_address = Column(String(45), nullable=True)
    consent_user_agent = Column(String, nullable=True)
    consent_version = Column(String(20), nullable=True)
    
    # Usage
    total_generations = Column(Integer, default=0, nullable=False)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    
    # Soft delete
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    # user = relationship("User", back_populates="identities")
    # generations = relationship("Generation", back_populates="identity")
