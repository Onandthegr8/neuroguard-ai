"""
GDPR right-to-erasure worker.

Runs daily at 03:00 UTC.  For every user whose `deleted_at` is older than
30 days, permanently delete all PHI: keystroke_metrics, sleep_metrics,
risk_predictions, alerts, consents, devices, wearables, and the user row
itself.  Audit log rows are intentionally preserved (HIPAA §164.312(b)
requires 6-year retention).
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...shared.db.session import AsyncSessionLocal
from ...shared.models.alert import Alert
from ...shared.models.consent_record import ConsentRecord
from ...shared.models.device import Device
from ...shared.models.keystroke_metrics import KeystrokeMetrics
from ...shared.models.report import Report
from ...shared.models.risk_prediction import RiskPrediction
from ...shared.models.sleep_metrics import SleepMetrics
from ...shared.models.user import User
from ...shared.models.wearable import Wearable

logger = logging.getLogger(__name__)

# In production: 30 days.  Override via env for fast testing.
GRACE_PERIOD_DAYS = 30


async def run_erasure_worker() -> dict:
    """
    Hard-delete users whose soft-delete grace period has expired.
    Returns a summary dict.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=GRACE_PERIOD_DAYS)
    summary = {"users_erased": 0, "rows_deleted": 0}

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(User).where(
                User.deleted_at.is_not(None),
                User.deleted_at <= cutoff,
            )
        )
        eligible_users = result.scalars().all()

        if not eligible_users:
            logger.info("GDPR worker: no users due for erasure")
            return summary

        for user in eligible_users:
            rows = await _erase_user_data(user.id, db)
            summary["users_erased"] += 1
            summary["rows_deleted"] += rows
            logger.info("GDPR erasure: user=%s rows_deleted=%d", user.id, rows)

        await db.commit()

    logger.info("GDPR worker: %s", summary)
    return summary


async def _erase_user_data(user_id, db: AsyncSession) -> int:
    """Delete every PHI row for a user. Returns total row count deleted."""
    total = 0

    # Order matters because of FK constraints
    tables = [
        (Alert,             "user_id"),
        (Report,            "user_id"),
        (RiskPrediction,    "user_id"),
        (SleepMetrics,      "user_id"),
        (KeystrokeMetrics,  "user_id"),
        (Wearable,          "user_id"),
        (Device,            "user_id"),
        (ConsentRecord,     "user_id"),
    ]
    for model, fk in tables:
        result = await db.execute(
            delete(model).where(getattr(model, fk) == user_id)
        )
        total += result.rowcount or 0

    # Finally delete the user row itself
    result = await db.execute(delete(User).where(User.id == user_id))
    total += result.rowcount or 0

    return total
