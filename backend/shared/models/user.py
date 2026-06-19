import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False, index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20))
    password_hash: Mapped[Optional[str]] = mapped_column(Text)
    auth_provider: Mapped[str] = mapped_column(String(20), default="email", nullable=False)
    age: Mapped[Optional[int]] = mapped_column(Integer)
    gender: Mapped[Optional[str]] = mapped_column(String(20))
    risk_group: Mapped[str] = mapped_column(String(20), default="general", nullable=False)
    family_history: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    devices: Mapped[list["Device"]] = relationship("Device", back_populates="user", cascade="all, delete-orphan")
    wearables: Mapped[list["Wearable"]] = relationship("Wearable", back_populates="user", cascade="all, delete-orphan")
    keystroke_metrics: Mapped[list["KeystrokeMetrics"]] = relationship("KeystrokeMetrics", back_populates="user")
    sleep_metrics: Mapped[list["SleepMetrics"]] = relationship("SleepMetrics", back_populates="user")
    risk_predictions: Mapped[list["RiskPrediction"]] = relationship("RiskPrediction", back_populates="user")
    alerts: Mapped[list["Alert"]] = relationship("Alert", back_populates="user")
    reports: Mapped[list["Report"]] = relationship("Report", back_populates="user")
    consent_records: Mapped[list["ConsentRecord"]] = relationship("ConsentRecord", back_populates="user")
    assessments: Mapped[list["Assessment"]] = relationship("Assessment", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email}>"
