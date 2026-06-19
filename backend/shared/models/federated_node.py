import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class FederatedNode(Base, TimestampMixin):
    __tablename__ = "federated_nodes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("hospitals.id", ondelete="SET NULL"))
    node_identifier: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    public_key: Mapped[str] = mapped_column(Text, nullable=False)           # PEM public key for secure aggregation
    current_epsilon: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    epsilon_budget: Mapped[float] = mapped_column(Float, default=10.0, nullable=False)
    rounds_participated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_round_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)

    hospital: Mapped[Optional["Hospital"]] = relationship("Hospital", back_populates="federated_nodes")

    @property
    def remaining_epsilon(self) -> float:
        return self.epsilon_budget - self.current_epsilon

    @property
    def is_budget_exhausted(self) -> bool:
        return self.current_epsilon >= self.epsilon_budget

    def __repr__(self) -> str:
        return f"<FederatedNode id={self.node_identifier} ε={self.current_epsilon:.2f}/{self.epsilon_budget}>"
