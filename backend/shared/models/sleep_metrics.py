import uuid
from datetime import date, datetime

from sqlalchemy import Date, Float, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional

from .base import Base, TimestampMixin


class SleepMetrics(Base, TimestampMixin):
    __tablename__ = "sleep_metrics"
    __table_args__ = (UniqueConstraint("user_id", "sleep_date", name="uq_sleep_user_date"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    wearable_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("wearables.id", ondelete="CASCADE"), nullable=False)
    sleep_date: Mapped[date] = mapped_column(Date, nullable=False)

    sleep_efficiency: Mapped[Optional[float]] = mapped_column(Float)        # 0-1
    rem_duration_min: Mapped[Optional[float]] = mapped_column(Float)
    rem_fragmentation_idx: Mapped[Optional[float]] = mapped_column(Float)   # RDI
    sleep_stage_transitions: Mapped[Optional[int]] = mapped_column(Integer)
    nocturnal_movement_idx: Mapped[Optional[float]] = mapped_column(Float)
    hrv_rmssd: Mapped[Optional[float]] = mapped_column(Float)
    resting_hr: Mapped[Optional[float]] = mapped_column(Float)
    total_sleep_min: Mapped[Optional[float]] = mapped_column(Float)
    deep_sleep_min: Mapped[Optional[float]] = mapped_column(Float)
    awakenings: Mapped[Optional[int]] = mapped_column(Integer)
    sleep_onset_min: Mapped[Optional[float]] = mapped_column(Float)
    raw_stages: Mapped[Optional[dict]] = mapped_column(JSONB)               # minute-by-minute stage array

    user: Mapped["User"] = relationship("User", back_populates="sleep_metrics")
    wearable: Mapped["Wearable"] = relationship("Wearable", back_populates="sleep_metrics")

    def __repr__(self) -> str:
        return f"<SleepMetrics id={self.id} user_id={self.user_id} date={self.sleep_date}>"
