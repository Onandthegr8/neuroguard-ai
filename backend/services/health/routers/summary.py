"""GET /health/summary — wellness snapshot for the home dashboard."""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from ....shared.db.session import get_db
from ....shared.models.keystroke_metrics import KeystrokeMetrics
from ....shared.models.risk_prediction import RiskPrediction
from ....shared.models.sleep_metrics import SleepMetrics
from ....shared.models.wearable import Wearable
from ....shared.schemas.health import HealthSummaryResponse
from ....shared.security.jwt import get_current_user

router = APIRouter()


@router.get("/summary", response_model=HealthSummaryResponse)
async def get_health_summary(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user_id = uuid.UUID(current_user["sub"])
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)

    # Latest risk prediction
    rp_result = await db.execute(
        select(RiskPrediction).where(RiskPrediction.user_id == user_id).order_by(desc(RiskPrediction.predicted_at)).limit(1)
    )
    latest_risk = rp_result.scalar_one_or_none()

    # Last night's sleep
    yesterday = (now - timedelta(days=1)).date()
    sleep_result = await db.execute(
        select(SleepMetrics).where(SleepMetrics.user_id == user_id, SleepMetrics.sleep_date == yesterday)
    )
    last_sleep = sleep_result.scalar_one_or_none()

    # 7-day keystroke stability
    ks_result = await db.execute(
        select(KeystrokeMetrics).where(KeystrokeMetrics.user_id == user_id, KeystrokeMetrics.session_start >= week_ago)
    )
    ks_sessions = ks_result.scalars().all()

    # Wearable sync status
    w_result = await db.execute(
        select(Wearable).where(Wearable.user_id == user_id, Wearable.is_active == True).limit(1)
    )
    wearable = w_result.scalar_one_or_none()
    sync_status = "synced" if (wearable and wearable.last_synced_at and (now - wearable.last_synced_at).days < 2) else "not_synced"

    # Compute typing stability from entropy variance
    typing_stability = None
    if ks_sessions:
        entropies = [s.typing_entropy for s in ks_sessions if s.typing_entropy is not None]
        if entropies:
            avg_e = sum(entropies) / len(entropies)
            typing_stability = round(max(0.0, 1.0 - avg_e), 3)

    risk_score = latest_risk.risk_score if latest_risk else 0.0
    wellness_score = max(0, min(100, int((1 - risk_score) * 100)))

    # Data completeness: days with data in last 7 days / 7
    days_with_data = len(set(s.session_start.date() for s in ks_sessions))
    data_completeness = round(days_with_data / 7, 3)

    return HealthSummaryResponse(
        wellness_score=wellness_score,
        risk_score=risk_score,
        risk_tier=latest_risk.risk_tier if latest_risk else "very_low",
        sleep_quality_last_night=last_sleep.sleep_efficiency if last_sleep else None,
        typing_stability_7d=typing_stability,
        wearable_sync_status=sync_status,
        data_completeness=data_completeness,
        last_updated=latest_risk.predicted_at if latest_risk else now,
    )
