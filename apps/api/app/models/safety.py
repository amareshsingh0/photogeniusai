"""
Safety audit log model for SQLAlchemy.
Stores all safety check events with 180-day retention.
"""
from datetime import datetime
from typing import Optional, Dict, Any

from sqlalchemy import Column, String, DateTime, Text, Integer, JSON, Index, ForeignKey  # type: ignore[reportMissingImports]
from sqlalchemy.dialects.postgresql import JSONB, UUID  # type: ignore[reportMissingImports]

from app.core.database import Base


class SafetyAuditLog(Base):
    """
    Safety audit log table.
    Stores all safety check events for compliance and analytics.
    """
    __tablename__ = "safety_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    
    # Event information
    event_type = Column(String(50), nullable=False, index=True)
    stage = Column(String(50))  # PRE_GENERATION or POST_GENERATION
    action = Column(String(50))  # ALLOW, BLOCK, QUARANTINE
    
    # User and generation tracking
    user_id = Column(String(255), index=True)
    generation_id = Column(String(255), index=True)
    
    # Safety data
    violations = Column(JSONB)  # List of violation objects
    scores = Column(JSONB)  # NSFW scores, age estimates, etc.
    
    # Content (truncated for privacy)
    prompt = Column(Text)  # Truncated to 500 chars
    image_url = Column(Text)
    
    # Request metadata
    ip_address = Column(String(45))  # IPv4 or IPv6
    user_agent = Column(Text)  # Truncated to 500 chars
    
    # Additional metadata (renamed to avoid SQLAlchemy conflict)
    extra_metadata = Column(JSONB, name="metadata")
    
    # Timestamps
    timestamp = Column(DateTime, nullable=False, index=True, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Indexes for performance
    __table_args__ = (
        Index('idx_safety_audit_user_timestamp', 'user_id', 'timestamp'),
        Index('idx_safety_audit_generation_timestamp', 'generation_id', 'timestamp'),
        Index('idx_safety_audit_event_timestamp', 'event_type', 'timestamp'),
        Index('idx_safety_audit_expires', 'expires_at'),
        # GIN index for JSONB fields (created via migration)
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "event_type": self.event_type,
            "user_id": self.user_id,
            "generation_id": self.generation_id,
            "stage": self.stage,
            "action": self.action,
            "violations": self.violations,
            "scores": self.scores,
            "prompt": self.prompt,
            "image_url": self.image_url,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "metadata": self.extra_metadata,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class AdversarialLog(Base):
    """
    Adversarial detection log table.
    Stores attempts to bypass safety filters for analysis and improvement.
    """
    __tablename__ = "adversarial_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # User tracking
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    # Prompt and detection data
    prompt = Column(Text, nullable=False)  # Original prompt (truncated to 500 chars)
    detections = Column(JSONB)  # List of detection objects with type, confidence, message
    sanitized_prompt = Column(Text, nullable=True)  # Sanitized version if not blocked
    was_blocked = Column(String(10), nullable=False, default="false")  # "true" or "false"

    # Request metadata
    ip_address = Column(String(45))  # IPv4 or IPv6
    user_agent = Column(Text)  # Truncated to 500 chars

    # Timestamps
    timestamp = Column(DateTime, nullable=False, index=True, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Indexes for performance
    __table_args__ = (
        Index('idx_adversarial_user_timestamp', 'user_id', 'timestamp'),
        Index('idx_adversarial_timestamp', 'timestamp'),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "user_id": str(self.user_id) if self.user_id else None,
            "prompt": self.prompt,
            "detections": self.detections,
            "sanitized_prompt": self.sanitized_prompt,
            "was_blocked": self.was_blocked,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
