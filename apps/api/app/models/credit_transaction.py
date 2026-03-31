"""Credit transaction model for generation deductions and top-ups."""
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class CreditTransaction(Base):
    """Logs credit deductions (generation) and additions (purchase, refund, bonus)."""

    __tablename__ = "credit_transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    amount = Column(Integer, nullable=False)  # negative = deduction, positive = addition
    transaction_type = Column(String(50), nullable=False)  # generation, purchase, refund, bonus
    description = Column(String(500), nullable=True)
    balance_after = Column(Integer, nullable=False)
    reference_id = Column(String(255), nullable=True)  # e.g. generation job_id
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
