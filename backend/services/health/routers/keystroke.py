"""POST /keystroke/features — ingest keystroke metadata sessions."""

import math
import statistics
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ....shared.db.session import get_db
from ....shared.models.keystroke_metrics import KeystrokeMetrics
from ....shared.schemas.health import KeystrokeIngestResponse, KeystrokePayload
from ....shared.security.jwt import get_current_user

router = APIRouter()


@router.post("/features", response_model=KeystrokeIngestResponse, status_code=status.HTTP_201_CREATED)
async def ingest_keystroke_features(
    payload: KeystrokePayload,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user_id = uuid.UUID(current_user["sub"])
    quality = _compute_quality_score(payload)

    if quality < 0.3:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Session quality too low (< 0.3). Minimum 30 keystrokes required.")

    metrics = KeystrokeMetrics(
        user_id=user_id,
        device_id=payload.device_id,
        session_start=payload.session_start,
        session_end=payload.session_end,
        key_press_duration_ms=payload.key_press_duration_ms,
        inter_key_interval_ms=payload.inter_key_interval_ms,
        typing_speed_wpm=payload.typing_speed_wpm,
        correction_frequency=payload.correction_frequency,
        typing_entropy=payload.typing_entropy or _compute_entropy(payload.inter_key_interval_ms),
        autocorrect_rate=payload.autocorrect_rate,
        diurnal_hour=payload.diurnal_hour,
        quality_score=quality,
        app_context=payload.app_context,
    )
    db.add(metrics)
    await db.commit()
    await db.refresh(metrics)
    return KeystrokeIngestResponse(session_id=metrics.id, quality_score=quality)


def _compute_quality_score(payload: KeystrokePayload) -> float:
    """Quality = function of session length, keystroke count, and IKI completeness."""
    iki = payload.inter_key_interval_ms
    if len(iki) < 30:
        return 0.0
    duration_sec = (payload.session_end - payload.session_start).total_seconds()
    completeness = min(len(iki) / 200, 1.0)
    duration_score = min(duration_sec / 60, 1.0)
    outlier_ratio = sum(1 for v in iki if v > 5000) / len(iki)
    return round(completeness * 0.5 + duration_score * 0.3 + (1 - outlier_ratio) * 0.2, 3)


def _compute_entropy(iki: list) -> float:
    if not iki or len(iki) < 2:
        return 0.0
    try:
        return round(statistics.stdev(iki) / (statistics.mean(iki) + 1e-9), 4)
    except statistics.StatisticsError:
        return 0.0
