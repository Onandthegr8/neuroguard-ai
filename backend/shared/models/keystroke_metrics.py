import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class KeystrokeMetrics(Base, TimestampMixin):
    __tablename__ = "keystroke_metrics"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    device_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False)
    session_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    session_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Raw timing arrays (metadata only — never message content)
    key_press_duration_ms: Mapped[Optional[list]] = mapped_column(ARRAY(Float))
    inter_key_interval_ms: Mapped[Optional[list]] = mapped_column(ARRAY(Float))

    # Computed aggregate features
    typing_speed_wpm: Mapped[Optional[float]] = mapped_column(Float)
    correction_frequency: Mapped[Optional[float]] = mapped_column(Float)
    typing_entropy: Mapped[Optional[float]] = mapped_column(Float)
    autocorrect_rate: Mapped[Optional[float]] = mapped_column(Float)
    diurnal_hour: Mapped[Optional[int]] = mapped_column(Integer)
    quality_score: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    app_context: Mapped[Optional[str]] = mapped_column(String(30))  # 'messaging','email' — NO content

    user: Mapped["User"] = relationship("User", back_populates="keystroke_metrics")
    device: Mapped["Device"] = relationship("Device", back_populates="keystroke_metrics")

    def __repr__(self) -> str:
        return f"<KeystrokeMetrics id={self.id} user_id={self.user_id}>"
