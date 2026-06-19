import uuid
from typing import Optional

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class Clinician(Base, TimestampMixin):
    __tablename__ = "clinicians"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    hospital_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("hospitals.id", ondelete="SET NULL"), index=True)
    npi_number: Mapped[Optional[str]] = mapped_column(String(20), unique=True)  # National Provider Identifier
    specialty: Mapped[Optional[str]] = mapped_column(String(50))                # 'neurology' | 'movement_disorders'
    license_state: Mapped[Optional[str]] = mapped_column(String(5))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    user: Mapped["User"] = relationship("User")
    hospital: Mapped[Optional["Hospital"]] = relationship("Hospital", back_populates="clinicians")
    alerts: Mapped[list["Alert"]] = relationship("Alert", back_populates="clinician")
    reports: Mapped[list["Report"]] = relationship("Report", back_populates="clinician")

    def __repr__(self) -> str:
        return f"<Clinician id={self.id} specialty={self.specialty}>"
