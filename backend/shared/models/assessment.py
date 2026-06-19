"""
Active screening assessment results.

Captures the output of clinician-validated screening tests performed by
patients via the app or web dashboard:
  - voice_tremor   — vocal jitter, shimmer, F0 stability
  - finger_tap     — tap count, inter-tap interval CV, fatigue index
  - spiral_drawing — drawing deviation from ideal spiral, tremor frequency
  - reaction_time  — simple + choice reaction time
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class Assessment(Base, TimestampMixin):
    __tablename__ = "assessments"

    id:      Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True,
    )

    # 'voice_tremor' | 'finger_tap' | 'spiral_drawing' | 'reaction_time' | 'typing'
    assessment_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)

    # Composite score from this test, 0-100 (higher = better motor/cognitive performance)
    overall_score:  Mapped[Optional[float]] = mapped_column(Float)

    # Test-specific metrics. Schema differs per test type:
    #   voice_tremor:   {jitter_pct, shimmer_pct, f0_std_hz, voice_breaks, hnr_db}
    #   finger_tap:     {tap_count, mean_iti_ms, iti_cv, fatigue_index, hand}
    #   spiral_drawing: {mean_deviation_px, peak_deviation_px, tremor_freq_hz, drawing_time_ms}
    #   reaction_time:  {mean_rt_ms, std_rt_ms, errors, trials, simple_or_choice}
    #   typing:         see web/src/lib/keystroke/analyzer.ts
    metrics: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Free-form notes (e.g. "patient reports tremor in dominant hand today")
    notes:    Mapped[Optional[str]] = mapped_column(String(500))

    user: Mapped["User"] = relationship("User", back_populates="assessments")

    def __repr__(self) -> str:
        return f"<Assessment id={self.id} type={self.assessment_type} score={self.overall_score}>"
