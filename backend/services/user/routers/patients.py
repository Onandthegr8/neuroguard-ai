"""GET /clinician/patients, GET /patients/{id}/timeline — clinician patient access."""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from ....shared.db.session import get_db
from ....shared.models.alert import Alert
from ....shared.models.keystroke_metrics import KeystrokeMetrics
from ....shared.models.risk_prediction import RiskPrediction
from ....shared.models.sleep_metrics import SleepMetrics
from ....shared.models.user import User
from ....shared.security.jwt import get_current_user
from ....shared.security.rbac import Role, require_role

router = APIRouter()


@router.get("/clinician/patients")
async def list_patients(
    search: Optional[str] = None,
    risk_tier: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(require_role(Role.CLINICIAN, Role.HOSPITAL_ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    query = select(User).where(User.deleted_at.is_(None))
    if search:
        query = query.where(User.email.ilike(f"%{search}%"))
    total_result = await db.execute(query)
    total = len(total_result.scalars().all())
    query = query.offset((page - 1) * limit).limit(limit)
    result = await db.execute(query)
    users = result.scalars().all()

    patients = []
    for u in users:
        rp = await db.execute(
            select(RiskPrediction).where(RiskPrediction.user_id == u.id).order_by(desc(RiskPrediction.predicted_at)).limit(1)
        )
        latest_risk = rp.scalar_one_or_none()
        if risk_tier and (not latest_risk or latest_risk.risk_tier != risk_tier):
            continue
        patients.append({
            "id": str(u.id), "email": u.email, "age": u.age, "risk_group": u.risk_group,
            "latest_risk_score": latest_risk.risk_score if latest_risk else None,
            "latest_risk_tier": latest_risk.risk_tier if latest_risk else "unknown",
            "latest_prediction_at": latest_risk.predicted_at.isoformat() if latest_risk else None,
        })

    return {"patients": patients, "total": total, "page": page, "limit": limit}


@router.get("/patients/{patient_id}/timeline")
async def get_patient_timeline(
    patient_id: uuid.UUID,
    days: int = Query(90, ge=7, le=365),
    current_user: dict = Depends(require_role(Role.CLINICIAN, Role.HOSPITAL_ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    since = datetime.now(timezone.utc) - timedelta(days=days)

    risk_result = await db.execute(
        select(RiskPrediction)
        .where(RiskPrediction.user_id == patient_id, RiskPrediction.predicted_at >= since)
        .order_by(RiskPrediction.predicted_at)
    )
    risks = risk_result.scalars().all()

    sleep_result = await db.execute(
        select(SleepMetrics)
        .where(SleepMetrics.user_id == patient_id, SleepMetrics.created_at >= since)
        .order_by(SleepMetrics.sleep_date)
    )
    sleeps = sleep_result.scalars().all()

    ks_result = await db.execute(
        select(KeystrokeMetrics)
        .where(KeystrokeMetrics.user_id == patient_id, KeystrokeMetrics.session_start >= since)
        .order_by(KeystrokeMetrics.session_start)
    )
    keystrokes = ks_result.scalars().all()

    alerts_result = await db.execute(
        select(Alert).where(Alert.user_id == patient_id, Alert.created_at >= since).order_by(desc(Alert.created_at)).limit(20)
    )
    alerts = alerts_result.scalars().all()

    return {
        "risk_trend": [{"date": r.predicted_at.date().isoformat(), "score": r.risk_score, "tier": r.risk_tier} for r in risks],
        "sleep_trend": [{"date": s.sleep_date.isoformat(), "rem_fragmentation": s.rem_fragmentation_idx, "efficiency": s.sleep_efficiency} for s in sleeps],
        "keystroke_trend": [{"date": k.session_start.date().isoformat(), "entropy": k.typing_entropy, "typing_speed": k.typing_speed_wpm} for k in keystrokes],
        "alerts": [{"id": str(a.id), "type": a.alert_type, "severity": a.severity, "title": a.title, "created_at": a.created_at.isoformat()} for a in alerts],
    }
