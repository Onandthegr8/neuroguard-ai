import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, LargeBinary, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class Wearable(Base, TimestampMixin):
    __tablename__ = "wearables"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    vendor: Mapped[str] = mapped_column(String(30), nullable=False)  # 'fitbit','apple','oura','samsung','garmin'
    model: Mapped[Optional[str]] = mapped_column(String(50))
    access_token: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)  # AES-256-GCM encrypted
    refresh_token: Mapped[Optional[bytes]] = mapped_column(LargeBinary)
    token_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="wearables")
    sleep_metrics: Mapped[list["SleepMetrics"]] = relationship("SleepMetrics", back_populates="wearable")

    def __repr__(self) -> str:
        return f"<Wearable id={self.id} vendor={self.vendor}>"
