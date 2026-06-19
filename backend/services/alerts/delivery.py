"""
Alert delivery — FCM (Android), APNs (iOS), Email (SendGrid).

In dev mode, missing credentials make each channel a no-op that logs the
delivery attempt instead of failing.  Set the corresponding env var to
enable a real provider.
"""

import logging
import os
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...shared.models.alert import Alert
from ...shared.models.device import Device
from ...shared.models.user import User

logger = logging.getLogger(__name__)

# ── Firebase (Android FCM + iOS APNs via HTTP v1 API) ─────────────────────────

_firebase_app = None


def _init_firebase() -> bool:
    """Lazy-init Firebase Admin SDK. Returns True if available."""
    global _firebase_app
    if _firebase_app is not None:
        return True

    creds_path = os.getenv("FIREBASE_CREDENTIALS_PATH", "/app/secrets/firebase.json")
    if not os.path.exists(creds_path):
        logger.info("FCM disabled — no credentials at %s", creds_path)
        return False

    try:
        import firebase_admin
        from firebase_admin import credentials
        _firebase_app = firebase_admin.initialize_app(credentials.Certificate(creds_path))
        logger.info("Firebase Admin SDK initialised")
        return True
    except Exception as e:
        logger.warning("Firebase init failed: %s", e)
        return False


async def send_fcm(device: Device, alert: Alert) -> bool:
    """Send FCM push notification to the device. Returns True on success."""
    if not device.fcm_token:
        return False
    if not _init_firebase():
        logger.info("[stub-fcm] Would push to device %s: %s", device.id, alert.title)
        return False

    try:
        from firebase_admin import messaging
        message = messaging.Message(
            notification=messaging.Notification(title=alert.title, body=alert.body),
            data={
                "alert_id":   str(alert.id),
                "alert_type": alert.alert_type,
                "severity":   alert.severity,
            },
            token=device.fcm_token,
        )
        response = messaging.send(message)
        logger.info("FCM sent: %s", response)
        return True
    except Exception as e:
        logger.warning("FCM send failed: %s", e)
        return False


# ── Email (SendGrid) ──────────────────────────────────────────────────────────

async def send_email(user: User, alert: Alert) -> bool:
    """Send email alert via SendGrid. Returns True on success."""
    api_key = os.getenv("SENDGRID_API_KEY", "")
    from_email = os.getenv("SENDGRID_FROM_EMAIL", "alerts@neuroguard.health")
    if not api_key:
        logger.info("[stub-email] Would email %s: %s", user.email, alert.title)
        return False

    try:
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                "https://api.sendgrid.com/v3/mail/send",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type":  "application/json",
                },
                json={
                    "personalizations": [{"to": [{"email": user.email}]}],
                    "from":    {"email": from_email, "name": "NeuroGuard AI"},
                    "subject": f"[{alert.severity.upper()}] {alert.title}",
                    "content": [{"type": "text/plain", "value": alert.body}],
                },
            )
        if resp.status_code in (200, 202):
            logger.info("Email sent to %s", user.email)
            return True
        logger.warning("SendGrid returned %d: %s", resp.status_code, resp.text[:200])
        return False
    except Exception as e:
        logger.warning("SendGrid send failed: %s", e)
        return False


# ── Orchestrator ──────────────────────────────────────────────────────────────

async def deliver_alert(alert: Alert, db: AsyncSession) -> dict:
    """
    Deliver an alert to all of the user's registered channels.
    Returns a dict summarising what was attempted.
    """
    result = {"fcm": 0, "email": 0, "errors": []}

    # Fetch user + active devices
    user_q = await db.execute(select(User).where(User.id == alert.user_id))
    user   = user_q.scalar_one_or_none()
    if not user:
        result["errors"].append("user_not_found")
        return result

    devices_q = await db.execute(
        select(Device).where(Device.user_id == alert.user_id, Device.fcm_token.is_not(None))
    )
    devices = devices_q.scalars().all()

    # Push
    for device in devices:
        if await send_fcm(device, alert):
            result["fcm"] += 1

    # Email
    if await send_email(user, alert):
        result["email"] += 1

    # Mark delivered
    alert.delivered_at = datetime.now(timezone.utc)
    await db.flush()

    return result
