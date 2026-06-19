import uuid
from typing import Optional

from sqlalchemy import Boolean, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class Hospital(Base, TimestampMixin):
    __tablename__ = "hospitals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    address: Mapped[Optional[dict]] = mapped_column(JSONB)
    license_type: Mapped[Optional[str]] = mapped_column(String(50))         # 'hipaa_covered_entity'
    fl_node_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    subscription_tier: Mapped[str] = mapped_column(String(20), default="basic", nullable=False)

    clinicians: Mapped[list["Clinician"]] = relationship("Clinician", back_populates="hospital")
    federated_nodes: Mapped[list["FederatedNode"]] = relationship("FederatedNode", back_populates="hospital")

    def __repr__(self) -> str:
        return f"<Hospital id={self.id} name={self.name}>"
