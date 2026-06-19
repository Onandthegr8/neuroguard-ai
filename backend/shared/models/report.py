import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class Report(Base, TimestampMixin):
    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    clinician_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("clinicians.id", ondelete="SET NULL"))
    report_type: Mapped[str] = mapped_column(String(30), nullable=False)    # 'monthly_summary' | 'clinical_assessment'
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    s3_key: Mapped[str] = mapped_column(String(500), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer)

    user: Mapped["User"] = relationship("User", back_populates="reports")
    clinician: Mapped[Optional["Clinician"]] = relationship("Clinician", back_populates="reports")

    def __repr__(self) -> str:
        return f"<Report id={self.id} type={self.report_type} period={self.period_start}–{self.period_end}>"
