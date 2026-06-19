import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import INET, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class ConsentRecord(Base, TimestampMixin):
    """Immutable consent history — rows must never be mutated, only new rows inserted."""

    __tablename__ = "consent_records"
    __table_args__ = (
        UniqueConstraint("user_id", "consent_type", "version", name="uq_consent_user_type_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    consent_type: Mapped[str] = mapped_column(String(40), nullable=False)
    # 'keystroke_collection' | 'sleep_data' | 'location' | 'research_use' | 'federated_learning' | 'biometric_data'
    version: Mapped[str] = mapped_column(String(10), nullable=False)        # consent document version e.g. "v1.2"
    granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    granted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    ip_address: Mapped[Optional[str]] = mapped_column(INET)
    device_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("devices.id", ondelete="SET NULL"))

    user: Mapped["User"] = relationship("User", back_populates="consent_records")

    def __repr__(self) -> str:
        return f"<ConsentRecord user={self.user_id} type={self.consent_type} granted={self.granted}>"
