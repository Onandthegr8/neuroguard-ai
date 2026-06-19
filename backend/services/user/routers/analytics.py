"""
Population analytics for clinicians and hospital admins.

GET /analytics/overview                — patient counts by risk tier, alert rate, ML drift
GET /analytics/risk-distribution       — count of patients per risk tier
GET /analytics/alert-rate              — alerts per day for the last N days
GET /analytics/model-performance       — model_version vs. avg risk score over time
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import List

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select, distinct
from sqlalchemy.ext.asyncio import AsyncSession

from ....shared.db.session import get_db
from ....shared.models.alert import Alert
from ....shared.models.risk_prediction import RiskPrediction
from ....shared.models.user import User
from ....shared.security.jwt import get_current_user
from ....shared.security.rbac import Role, require_role

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class TierCount(BaseModel):
    tier:  str
    count: int


class DailyCount(BaseModel):
    date:  str
    count: int


class ModelPerformance(BaseModel):
    model_version: str
    avg_risk_score: float
    n_predictions: int


class AnalyticsOverview(BaseModel):
    total_patients:        int
    total_alerts_30d:      int
    avg_risk_score:        float
    high_risk_count:       int
    risk_distribution:     List[TierCount]
    alerts_per_day:        List[DailyCount]
    model_performance:     List[ModelPerformance]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/overview", response_model=AnalyticsOverview)
async def analytics_overview(
    current_user: dict = Depends(require_role(Role.CLINICIAN, Role.HOSPITAL_ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """Single endpoint returning everything for the /analytics dashboard page."""
    cutoff_30d = datetime.now(timezone.utc) - timedelta(days=30)

    # ── Total patients (non-deleted) ──────────────────────────────────────────
    total_q = await db.execute(
        select(func.count(User.id)).where(User.deleted_at.is_(None))
    )
    total_patients = int(total_q.scalar() or 0)

    # ── Latest risk score per user → distribution by tier ─────────────────────
    # Subquery: latest prediction per user
    subq = (
        select(
            RiskPrediction.user_id,
            func.max(RiskPrediction.predicted_at).label("latest"),
        )
        .group_by(RiskPrediction.user_id)
        .subquery()
    )
    latest_q = await db.execute(
        select(RiskPrediction.risk_tier, func.count(RiskPrediction.id))
        .join(subq, (RiskPrediction.user_id == subq.c.user_id) &
                    (RiskPrediction.predicted_at == subq.c.latest))
        .group_by(RiskPrediction.risk_tier)
    )
    distribution_raw = {row[0]: int(row[1]) for row in latest_q.all()}
    # Make sure every tier appears
    risk_distribution = [
        TierCount(tier=t, count=distribution_raw.get(t, 0))
        for t in ("very_low", "low", "moderate", "high", "very_high")
    ]

    high_risk_count = distribution_raw.get("high", 0) + distribution_raw.get("very_high", 0)

    avg_q = await db.execute(
        select(func.avg(RiskPrediction.risk_score))
        .join(subq, (RiskPrediction.user_id == subq.c.user_id) &
                    (RiskPrediction.predicted_at == subq.c.latest))
    )
    avg_risk_score = float(avg_q.scalar() or 0.0)

    # ── Alerts in last 30 days, by day ────────────────────────────────────────
    alerts_q = await db.execute(
        select(
            func.date_trunc("day", Alert.created_at).label("day"),
            func.count(Alert.id),
        )
        .where(Alert.created_at >= cutoff_30d)
        .group_by("day")
        .order_by("day")
    )
    alerts_per_day = [
        DailyCount(date=row[0].date().isoformat(), count=int(row[1]))
        for row in alerts_q.all()
    ]
    total_alerts_30d = sum(d.count for d in alerts_per_day)

    # ── Model performance over time (per version) ─────────────────────────────
    perf_q = await db.execute(
        select(
            RiskPrediction.model_version,
            func.avg(RiskPrediction.risk_score),
            func.count(RiskPrediction.id),
        )
        .group_by(RiskPrediction.model_version)
    )
    model_performance = [
        ModelPerformance(
            model_version  = row[0] or "unknown",
            avg_risk_score = round(float(row[1] or 0.0), 4),
            n_predictions  = int(row[2]),
        )
        for row in perf_q.all()
    ]

    return AnalyticsOverview(
        total_patients     = total_patients,
        total_alerts_30d   = total_alerts_30d,
        avg_risk_score     = round(avg_risk_score, 4),
        high_risk_count    = high_risk_count,
        risk_distribution  = risk_distribution,
        alerts_per_day     = alerts_per_day,
        model_performance  = model_performance,
    )
