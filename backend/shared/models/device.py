import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class Device(Base, TimestampMixin):
    __tablename__ = "devices"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(10), nullable=False)  # 'android' | 'ios'
    device_model: Mapped[Optional[str]] = mapped_column(String(100))
    os_version: Mapped[Optional[str]] = mapped_column(String(20))
    app_version: Mapped[Optional[str]] = mapped_column(String(20))
    fcm_token: Mapped[Optional[str]] = mapped_column(Text)
    last_active_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    user: Mapped["User"] = relationship("User", back_populates="devices")
    keystroke_metrics: Mapped[list["KeystrokeMetrics"]] = relationship("KeystrokeMetrics", back_populates="device")

    def __repr__(self) -> str:
        return f"<Device id={self.id} platform={self.platform}>"
