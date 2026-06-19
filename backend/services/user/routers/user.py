"""POST /user/register, POST /user/consent, GET /user/consents."""

import uuid
from datetime import datetime, timezone

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ....shared.db.session import get_db
from ....shared.models.consent_record import ConsentRecord
from ....shared.models.device import Device
from ....shared.models.user import User
from ....shared.schemas.user import ConsentRequest, ConsentResponse, UserCreate, UserResponse
from ....shared.security.hipaa_logger import log_explicit
from ....shared.security.jwt import get_current_user
from pydantic import BaseModel
from typing import Optional

router = APIRouter()


class DeviceCreate(BaseModel):
    platform:     str             # 'android' | 'ios'
    device_model: Optional[str] = None
    os_version:   Optional[str] = None
    app_version:  Optional[str] = None
    fcm_token:    Optional[str] = None


class DeviceResponse(BaseModel):
    id:           uuid.UUID
    platform:     str
    device_model: Optional[str] = None
    os_version:   Optional[str] = None
    app_version:  Optional[str] = None
    created_at:   datetime


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(body: UserCreate, request: Request, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    pw_hash = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt()).decode()
    user = User(
        email=body.email,
        password_hash=pw_hash,
        age=body.age,
        gender=body.gender,
        family_history=body.family_history,
        risk_group=body.risk_group,
        auth_provider="email",
    )
    db.add(user)
    await db.flush()
    await log_explicit("CREATE", "user", resource_id=str(user.id), actor_id=user.id, actor_role="user", outcome="success")
    await db.commit()
    await db.refresh(user)
    return UserResponse(id=user.id, email=user.email, age=user.age, gender=user.gender,
                        risk_group=user.risk_group, family_history=user.family_history, created_at=user.created_at)


@router.post("/consent", response_model=ConsentResponse, status_code=status.HTTP_201_CREATED)
async def record_consent(
    body: ConsentRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user_id = uuid.UUID(current_user["sub"])
    client_ip = request.client.host if request.client else None

    existing = await db.execute(
        select(ConsentRecord).where(
            ConsentRecord.user_id == user_id,
            ConsentRecord.consent_type == body.consent_type,
            ConsentRecord.version == body.version,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Consent record already exists for this version. Revoke first.")

    now = datetime.now(timezone.utc)
    consent = ConsentRecord(
        user_id=user_id,
        consent_type=body.consent_type,
        version=body.version,
        granted=body.granted,
        granted_at=now if body.granted else None,
        ip_address=client_ip,
        device_id=body.device_id,
    )
    db.add(consent)
    await log_explicit("CONSENT", "consent_record", actor_id=user_id, patient_id=user_id,
                       outcome="success", details={"type": body.consent_type, "granted": body.granted})
    await db.commit()
    await db.refresh(consent)
    return ConsentResponse(consent_id=consent.id, consent_type=consent.consent_type,
                           granted=consent.granted, granted_at=consent.granted_at)


@router.get("/consents", response_model=list[ConsentResponse])
async def list_consents(current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    user_id = uuid.UUID(current_user["sub"])
    result = await db.execute(select(ConsentRecord).where(ConsentRecord.user_id == user_id))
    consents = result.scalars().all()
    return [ConsentResponse(consent_id=c.id, consent_type=c.consent_type, granted=c.granted, granted_at=c.granted_at) for c in consents]


# ── Devices ───────────────────────────────────────────────────────────────────

@router.post("/devices", response_model=DeviceResponse, status_code=status.HTTP_201_CREATED)
async def register_device(
    body: DeviceCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Register a new mobile device for the authenticated user."""
    user_id = uuid.UUID(current_user["sub"])
    device = Device(
        user_id      = user_id,
        platform     = body.platform,
        device_model = body.device_model,
        os_version   = body.os_version,
        app_version  = body.app_version,
        fcm_token    = body.fcm_token,
        last_active_at = datetime.now(timezone.utc),
    )
    db.add(device)
    await db.flush()
    await log_explicit("CREATE", "device", resource_id=str(device.id),
                       actor_id=user_id, actor_role=current_user.get("role", "user"),
                       outcome="success")
    await db.commit()
    await db.refresh(device)
    return DeviceResponse(
        id           = device.id,
        platform     = device.platform,
        device_model = device.device_model,
        os_version   = device.os_version,
        app_version  = device.app_version,
        created_at   = device.created_at,
    )


@router.get("/devices", response_model=list[DeviceResponse])
async def list_devices(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user_id = uuid.UUID(current_user["sub"])
    result  = await db.execute(select(Device).where(Device.user_id == user_id))
    devices = result.scalars().all()
    return [
        DeviceResponse(
            id=d.id, platform=d.platform, device_model=d.device_model,
            os_version=d.os_version, app_version=d.app_version, created_at=d.created_at,
        )
        for d in devices
    ]
