"""
GDPR endpoints (Articles 17 & 20):
  GET  /user/export                — right to data portability (zip of all PHI)
  POST /user/delete                — right to erasure (soft-delete; hard-delete by worker after 30 days)
  GET  /user/deletion-status       — check status of a pending deletion request
"""

import csv
import io
import json
import uuid
import zipfile
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ....shared.db.session import get_db
from ....shared.models.alert import Alert
from ....shared.models.consent_record import ConsentRecord
from ....shared.models.device import Device
from ....shared.models.keystroke_metrics import KeystrokeMetrics
from ....shared.models.risk_prediction import RiskPrediction
from ....shared.models.sleep_metrics import SleepMetrics
from ....shared.models.user import User
from ....shared.models.wearable import Wearable
from ....shared.security.hipaa_logger import log_explicit
from ....shared.security.jwt import get_current_user

router = APIRouter()


# ── GDPR Article 20 — Right to data portability ───────────────────────────────

@router.get("/export")
async def export_user_data(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate a zip containing every row of PHI belonging to the calling user.
    One CSV file per table.  Streams the zip directly.
    """
    user_id = uuid.UUID(current_user["sub"])

    # Pull all PHI tables for this user
    tables = {
        "user.csv":               [(await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()],
        "devices.csv":            (await db.execute(select(Device).where(Device.user_id == user_id))).scalars().all(),
        "wearables.csv":          (await db.execute(select(Wearable).where(Wearable.user_id == user_id))).scalars().all(),
        "keystroke_metrics.csv":  (await db.execute(select(KeystrokeMetrics).where(KeystrokeMetrics.user_id == user_id))).scalars().all(),
        "sleep_metrics.csv":      (await db.execute(select(SleepMetrics).where(SleepMetrics.user_id == user_id))).scalars().all(),
        "risk_predictions.csv":   (await db.execute(select(RiskPrediction).where(RiskPrediction.user_id == user_id))).scalars().all(),
        "alerts.csv":             (await db.execute(select(Alert).where(Alert.user_id == user_id))).scalars().all(),
        "consents.csv":           (await db.execute(select(ConsentRecord).where(ConsentRecord.user_id == user_id))).scalars().all(),
    }

    # Build the zip in memory
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # Manifest with metadata
        zf.writestr("MANIFEST.json", json.dumps({
            "user_id":           str(user_id),
            "exported_at":       datetime.now(timezone.utc).isoformat(),
            "gdpr_article":      "20 (Right to data portability)",
            "schema_version":    "1.0",
            "data_controller":   "NeuroGuard AI",
            "files":             list(tables.keys()),
            "notes": (
                "Encrypted columns (wearable access/refresh tokens) are exported as base64 "
                "ciphertext. Free-form key arrays are stored as JSON in their respective columns."
            ),
        }, indent=2))

        for filename, rows in tables.items():
            zf.writestr(filename, _rows_to_csv(rows))

    zip_bytes = zip_buf.getvalue()

    await log_explicit(
        "EXPORT", "user_data_archive",
        actor_id=user_id, actor_role=current_user.get("role", "user"),
        patient_id=user_id, outcome="success",
        details={"size_bytes": len(zip_bytes), "table_count": len(tables)},
    )

    return StreamingResponse(
        io.BytesIO(zip_bytes),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="neuroguard_export_{user_id}.zip"',
            "X-Export-Size":       str(len(zip_bytes)),
        },
    )


# ── GDPR Article 17 — Right to erasure ────────────────────────────────────────

@router.post("/delete", status_code=status.HTTP_202_ACCEPTED)
async def request_deletion(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Mark the user for deletion.  The user is soft-deleted immediately
    (deleted_at is set) and a scheduled worker performs the hard delete
    after a 30-day grace period.
    """
    user_id = uuid.UUID(current_user["sub"])
    now     = datetime.now(timezone.utc)

    await db.execute(
        update(User)
        .where(User.id == user_id)
        .values(deleted_at=now)
    )
    await log_explicit(
        "DELETE", "user", resource_id=str(user_id),
        actor_id=user_id, actor_role=current_user.get("role", "user"),
        patient_id=user_id, outcome="success",
        details={"erasure_scheduled_after": "30 days", "soft_delete_at": now.isoformat()},
    )
    await db.commit()

    return {
        "status":            "scheduled",
        "soft_deleted_at":   now.isoformat(),
        "hard_delete_after": "30 days",
        "message": (
            "Your account has been soft-deleted. You can request restoration within 30 days "
            "by contacting support. After that, all PHI will be permanently removed."
        ),
    }


@router.get("/deletion-status")
async def deletion_status(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user_id = uuid.UUID(current_user["sub"])
    result  = await db.execute(select(User).where(User.id == user_id))
    user    = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return {
        "user_id":          str(user.id),
        "soft_deleted_at":  user.deleted_at.isoformat() if user.deleted_at else None,
        "scheduled_for_erasure": user.deleted_at is not None,
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _rows_to_csv(rows) -> str:
    """Serialise an iterable of SQLAlchemy ORM rows into CSV text."""
    rows = [r for r in (rows or []) if r is not None]
    if not rows:
        return "no data\n"

    # Discover columns from the first row's mapped attributes
    sample = rows[0]
    cols   = [c.name for c in sample.__table__.columns]

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(cols)
    for row in rows:
        writer.writerow([_serialise(getattr(row, c, None)) for c in cols])
    return buf.getvalue()


def _serialise(v):
    if v is None:
        return ""
    if isinstance(v, (datetime,)):
        return v.isoformat()
    if isinstance(v, uuid.UUID):
        return str(v)
    if isinstance(v, (bytes, bytearray)):
        import base64
        return "base64:" + base64.b64encode(v).decode()
    if isinstance(v, (list, dict)):
        return json.dumps(v, default=str)
    return v
