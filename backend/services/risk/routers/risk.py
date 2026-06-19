"""GET /risk/score, GET /risk/history."""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from ....shared.db.session import get_db
from ....shared.models.keystroke_metrics import KeystrokeMetrics
from ....shared.models.risk_prediction import RiskPrediction
from ....shared.models.sleep_metrics import SleepMetrics
from ....shared.schemas.risk import RiskHistoryResponse, RiskHistoryPoint, RiskScoreResponse, SHAPContributor
from ....shared.security.jwt import get_current_user
from ....shared.config import get_settings

router = APIRouter()
settings = get_settings()


@router.get("/score", response_model=RiskScoreResponse)
async def get_risk_score(
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user_id = uuid.UUID(current_user["sub"])

    # Return the most recent cached prediction
    result = await db.execute(
        select(RiskPrediction).where(RiskPrediction.user_id == user_id).order_by(desc(RiskPrediction.predicted_at)).limit(1)
    )
    prediction = result.scalar_one_or_none()
    if not prediction:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No risk prediction available yet. Data collection in progress.")

    shap = prediction.shap_values or {}
    total_shap = sum(abs(v) for v in shap.values()) or 1.0
    contributors = sorted(
        [
            SHAPContributor(
                feature=k,
                contribution_pct=round(abs(v) / total_shap * 100, 1),
                direction="increases_risk" if v > 0 else "decreases_risk",
            )
            for k, v in shap.items()
        ],
        key=lambda x: x.contribution_pct,
        reverse=True,
    )[:5]

    return RiskScoreResponse(
        prediction_id=prediction.id,
        risk_score=prediction.risk_score,
        risk_tier=prediction.risk_tier,
        confidence_interval=(prediction.confidence_low or 0.0, prediction.confidence_high or 1.0),
        model_version=prediction.model_version,
        shap_explanations=shap,
        top_contributors=contributors,
        keystroke_contribution=prediction.keystroke_contribution,
        sleep_contribution=prediction.sleep_contribution,
        predicted_at=prediction.predicted_at,
    )


@router.get("/history", response_model=RiskHistoryResponse)
async def get_risk_history(
    days: int = 90,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user_id = uuid.UUID(current_user["sub"])
    since = datetime.now(timezone.utc) - timedelta(days=min(days, 365))

    result = await db.execute(
        select(RiskPrediction)
        .where(RiskPrediction.user_id == user_id, RiskPrediction.predicted_at >= since)
        .order_by(RiskPrediction.predicted_at)
    )
    predictions = result.scalars().all()

    history = [
        RiskHistoryPoint(date=p.predicted_at.date().isoformat(), risk_score=p.risk_score, risk_tier=p.risk_tier)
        for p in predictions
    ]
    return RiskHistoryResponse(user_id=user_id, history=history, days=days)
