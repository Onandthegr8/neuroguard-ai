import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class RiskPrediction(Base, TimestampMixin):
    __tablename__ = "risk_predictions"
    __table_args__ = (CheckConstraint("risk_score BETWEEN 0 AND 1", name="ck_risk_score_range"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    predicted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    risk_score: Mapped[float] = mapped_column(Float, nullable=False)
    risk_tier: Mapped[str] = mapped_column(String(20), nullable=False)      # very_low|low|moderate|high|very_high
    confidence_low: Mapped[Optional[float]] = mapped_column(Float)
    confidence_high: Mapped[Optional[float]] = mapped_column(Float)
    model_version: Mapped[str] = mapped_column(String(20), nullable=False)
    shap_values: Mapped[Optional[dict]] = mapped_column(JSONB)              # {feature_name: shap_value}
    feature_inputs: Mapped[Optional[dict]] = mapped_column(JSONB)           # snapshot of 35 input features
    keystroke_contribution: Mapped[Optional[float]] = mapped_column(Float)
    sleep_contribution: Mapped[Optional[float]] = mapped_column(Float)

    user: Mapped["User"] = relationship("User", back_populates="risk_predictions")

    def __repr__(self) -> str:
        return f"<RiskPrediction id={self.id} score={self.risk_score:.3f} tier={self.risk_tier}>"
