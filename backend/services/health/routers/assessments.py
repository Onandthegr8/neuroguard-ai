"""
POST /assessments       — record a new active screening test result
GET  /assessments       — list this user's recent assessment results
GET  /assessments/latest — latest result of each test type for a user
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from ....shared.db.session import get_db
from ....shared.models.assessment import Assessment
from ....shared.security.hipaa_logger import log_explicit
from ....shared.security.jwt import get_current_user

router = APIRouter()

# Composite-score reference ranges (above = healthy, below = concerning).
# Calibrated against published cut-off scores in the active-screening literature.
_REFERENCE_RANGES = {
    "voice_tremor":   {"healthy_min": 70.0, "warning_min": 50.0},  # higher = better
    "finger_tap":     {"healthy_min": 70.0, "warning_min": 50.0},
    "spiral_drawing": {"healthy_min": 70.0, "warning_min": 50.0},
    "reaction_time":  {"healthy_min": 70.0, "warning_min": 50.0},
    "typing":         {"healthy_min": 60.0, "warning_min": 40.0},
}


class AssessmentCreate(BaseModel):
    assessment_type: str   = Field(..., pattern="^(voice_tremor|finger_tap|spiral_drawing|reaction_time|typing)$")
    overall_score:   Optional[float] = Field(default=None, ge=0, le=100)
    metrics:         dict             = Field(default_factory=dict)
    notes:           Optional[str]    = Field(default=None, max_length=500)


class AssessmentResponse(BaseModel):
    id:              uuid.UUID
    assessment_type: str
    overall_score:   Optional[float]
    metrics:         dict
    notes:           Optional[str]
    interpretation:  str
    created_at:      datetime

    model_config = {"from_attributes": True}


def _interpret(assessment_type: str, score: Optional[float]) -> str:
    """Human-readable interpretation of the composite score."""
    if score is None:
        return "Score not available."
    ref = _REFERENCE_RANGES.get(assessment_type)
    if not ref:
        return f"Score: {score:.1f}"
    if score >= ref["healthy_min"]:
        return f"Within healthy range ({score:.1f}/100)."
    if score >= ref["warning_min"]:
        return f"Mildly impaired ({score:.1f}/100) — consider re-testing in 7 days."
    return f"Below normal range ({score:.1f}/100) — clinical follow-up recommended."


@router.post("", response_model=AssessmentResponse, status_code=status.HTTP_201_CREATED)
async def create_assessment(
    body: AssessmentCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user_id = uuid.UUID(current_user["sub"])

    assessment = Assessment(
        user_id         = user_id,
        assessment_type = body.assessment_type,
        overall_score   = body.overall_score,
        metrics         = body.metrics,
        notes           = body.notes,
    )
    db.add(assessment)
    await db.flush()

    await log_explicit(
        "CREATE", "assessment", resource_id=str(assessment.id),
        actor_id=user_id, actor_role=current_user.get("role", "user"),
        outcome="success", details={"type": body.assessment_type, "score": body.overall_score},
    )
    await db.commit()
    await db.refresh(assessment)

    return AssessmentResponse(
        id              = assessment.id,
        assessment_type = assessment.assessment_type,
        overall_score   = assessment.overall_score,
        metrics         = assessment.metrics,
        notes           = assessment.notes,
        interpretation  = _interpret(assessment.assessment_type, assessment.overall_score),
        created_at      = assessment.created_at,
    )


@router.get("", response_model=list[AssessmentResponse])
async def list_assessments(
    assessment_type: Optional[str] = None,
    limit:           int           = 50,
    current_user:    dict          = Depends(get_current_user),
    db:              AsyncSession  = Depends(get_db),
):
    user_id = uuid.UUID(current_user["sub"])
    stmt = select(Assessment).where(Assessment.user_id == user_id)
    if assessment_type:
        stmt = stmt.where(Assessment.assessment_type == assessment_type)
    stmt = stmt.order_by(desc(Assessment.created_at)).limit(limit)
    result = await db.execute(stmt)
    rows   = result.scalars().all()
    return [
        AssessmentResponse(
            id              = a.id,
            assessment_type = a.assessment_type,
            overall_score   = a.overall_score,
            metrics         = a.metrics,
            notes           = a.notes,
            interpretation  = _interpret(a.assessment_type, a.overall_score),
            created_at      = a.created_at,
        )
        for a in rows
    ]


@router.get("/latest", response_model=dict)
async def latest_assessments(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the latest score per test type — used by the assessment dashboard tile."""
    user_id = uuid.UUID(current_user["sub"])
    result: dict[str, dict] = {}
    for test_type in ("voice_tremor", "finger_tap", "spiral_drawing", "reaction_time", "typing"):
        row = await db.execute(
            select(Assessment)
            .where(Assessment.user_id == user_id, Assessment.assessment_type == test_type)
            .order_by(desc(Assessment.created_at))
            .limit(1)
        )
        a = row.scalar_one_or_none()
        result[test_type] = {
            "score":          a.overall_score if a else None,
            "taken_at":       a.created_at.isoformat() if a else None,
            "interpretation": _interpret(test_type, a.overall_score) if a else "Not taken yet",
        }
    return result
