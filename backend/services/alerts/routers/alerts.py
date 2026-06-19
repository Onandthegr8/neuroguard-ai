"""POST /clinician/alerts, GET /alerts — alert management."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ....shared.db.session import get_db
from ....shared.models.alert import Alert
from ....shared.schemas.alerts import AlertCreate, AlertResponse
from ....shared.security.jwt import get_current_user
from ....shared.security.rbac import Role, require_role

router = APIRouter()


@router.post("/clinician/alerts", response_model=AlertResponse, status_code=status.HTTP_201_CREATED)
async def create_clinician_alert(
    body: AlertCreate,
    current_user: dict = Depends(require_role(Role.CLINICIAN, Role.HOSPITAL_ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    clinician_id = uuid.UUID(current_user["sub"])
    alert = Alert(
        user_id=body.patient_id,
        clinician_id=clinician_id,
        alert_type="clinician_message",
        severity=body.severity,
        title="Message from your care team",
        body=body.message,
        metadata_={"send_to_patient": body.send_to_patient},
    )
    db.add(alert)
    await db.flush()

    if body.send_to_patient:
        await _deliver_push_notification(alert, db)

    await db.commit()
    await db.refresh(alert)
    return AlertResponse(
        id=alert.id, alert_type=alert.alert_type, severity=alert.severity,
        title=alert.title, body=alert.body, is_read=alert.is_read,
        created_at=alert.created_at, delivered_at=alert.delivered_at,
    )


@router.get("/alerts", response_model=list[AlertResponse])
async def list_my_alerts(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user_id = uuid.UUID(current_user["sub"])
    result = await db.execute(
        select(Alert).where(Alert.user_id == user_id).order_by(Alert.created_at.desc()).limit(50)
    )
    alerts = result.scalars().all()
    return [
        AlertResponse(id=a.id, alert_type=a.alert_type, severity=a.severity,
                      title=a.title, body=a.body, is_read=a.is_read,
                      created_at=a.created_at, delivered_at=a.delivered_at)
        for a in alerts
    ]


async def _deliver_push_notification(alert: Alert, db: AsyncSession) -> None:
    """Deliver FCM push notification. Production: use firebase-admin SDK."""
    alert.delivered_at = datetime.now(timezone.utc)
