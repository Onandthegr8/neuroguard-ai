"""
Alert rule engine — runs on an APScheduler background schedule.
Evaluates 4 rule types against the latest patient data and creates Alert rows.

Rules:
  1. risk_threshold_crossed   — latest score ≥ 0.55 and no alert in last 7 days
  2. rapid_progression        — 14-day delta ≥ 0.20
  3. rem_behavior_anomaly     — REM fragmentation index > 0.5 on 3+ consecutive nights
  4. data_gap                 — no keystroke sessions for 3+ days
"""

import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import desc, select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ...shared.config import get_settings
from ...shared.db.session import AsyncSessionLocal
from ...shared.models.alert import Alert
from ...shared.models.keystroke_metrics import KeystrokeMetrics
from ...shared.models.risk_prediction import RiskPrediction
from ...shared.models.sleep_metrics import SleepMetrics
from ...shared.models.user import User
from .delivery import deliver_alert

logger = logging.getLogger(__name__)
settings = get_settings()

scheduler = AsyncIOScheduler(timezone="UTC")


# ── Scheduler entry points ────────────────────────────────────────────────────

def start_scheduler() -> None:
    from .gdpr_worker import run_erasure_worker
    scheduler.add_job(run_all_rules,      "cron",     hour=2, minute=0, id="nightly_rules",   replace_existing=True)
    scheduler.add_job(run_all_rules,      "interval", hours=1,          id="hourly_rules",    replace_existing=True)
    scheduler.add_job(run_erasure_worker, "cron",     hour=3, minute=0, id="gdpr_erasure",    replace_existing=True)
    scheduler.start()
    logger.info("Alert + GDPR scheduler started (rules: hourly + 02:00 UTC, erasure: 03:00 UTC)")


def stop_scheduler() -> None:
    scheduler.shutdown(wait=False)


async def run_all_rules() -> None:
    logger.info("Running alert rules...")
    async with AsyncSessionLocal() as db:
        users_result = await db.execute(select(User).where(User.deleted_at.is_(None)))
        users = users_result.scalars().all()
        for user in users:
            await _rule_risk_threshold(user.id, db)
            await _rule_rapid_progression(user.id, db)
            await _rule_rem_anomaly(user.id, db)
            await _rule_data_gap(user.id, db)
        await db.commit()
    logger.info("Alert rules complete")


# ── Rule 1: Risk threshold crossed ───────────────────────────────────────────

async def _rule_risk_threshold(user_id, db: AsyncSession) -> None:
    latest = await _latest_prediction(user_id, db)
    if not latest or latest.risk_score < settings.alert_risk_threshold:
        return

    # Avoid duplicate alert within 7 days
    if await _recent_alert_exists(user_id, "risk_threshold_crossed", days=7, db=db):
        return

    severity = "critical" if latest.risk_score >= 0.75 else "warning"
    await _create_alert(
        user_id=user_id,
        alert_type="risk_threshold_crossed",
        severity=severity,
        title="Risk Score Alert",
        body=(
            f"Your risk score has reached {latest.risk_score:.0%} "
            f"({latest.risk_tier.replace('_', ' ').title()}). "
            "Please consult your care team."
        ),
        metadata={"risk_score": latest.risk_score, "risk_tier": latest.risk_tier},
        db=db,
    )


# ── Rule 2: Rapid progression ─────────────────────────────────────────────────

async def _rule_rapid_progression(user_id, db: AsyncSession) -> None:
    cutoff_14 = datetime.now(timezone.utc) - timedelta(days=14)
    result = await db.execute(
        select(RiskPrediction)
        .where(RiskPrediction.user_id == user_id, RiskPrediction.predicted_at >= cutoff_14)
        .order_by(RiskPrediction.predicted_at)
    )
    preds = result.scalars().all()
    if len(preds) < 2:
        return

    delta = preds[-1].risk_score - preds[0].risk_score
    if delta < settings.alert_rapid_progression_delta:
        return

    if await _recent_alert_exists(user_id, "rapid_progression", days=7, db=db):
        return

    await _create_alert(
        user_id=user_id,
        alert_type="rapid_progression",
        severity="critical",
        title="Rapid Risk Progression Detected",
        body=(
            f"Risk score increased by {delta:.0%} over the past 14 days "
            f"({preds[0].risk_score:.0%} → {preds[-1].risk_score:.0%}). "
            "Immediate clinical review recommended."
        ),
        metadata={"delta": round(delta, 3), "from_score": preds[0].risk_score, "to_score": preds[-1].risk_score},
        db=db,
    )


# ── Rule 3: REM behavior anomaly ─────────────────────────────────────────────

async def _rule_rem_anomaly(user_id, db: AsyncSession) -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(days=5)
    result = await db.execute(
        select(SleepMetrics)
        .where(SleepMetrics.user_id == user_id, SleepMetrics.created_at >= cutoff)
        .order_by(SleepMetrics.sleep_date)
    )
    nights = result.scalars().all()
    if len(nights) < 3:
        return

    # Check last 3 consecutive nights
    last_3 = nights[-3:]
    anomalous = [n for n in last_3 if (n.rem_fragmentation_idx or 0) > settings.alert_rem_anomaly_rdi]
    if len(anomalous) < 3:
        return

    if await _recent_alert_exists(user_id, "rem_behavior_anomaly", days=7, db=db):
        return

    avg_rdi = sum(n.rem_fragmentation_idx for n in anomalous) / 3
    await _create_alert(
        user_id=user_id,
        alert_type="rem_behavior_anomaly",
        severity="warning",
        title="REM Sleep Anomaly Detected",
        body=(
            f"REM fragmentation index exceeded {settings.alert_rem_anomaly_rdi} "
            f"on 3 consecutive nights (avg RDI: {avg_rdi:.2f}). "
            "This pattern may warrant clinical attention."
        ),
        metadata={"avg_rdi": round(avg_rdi, 3), "nights": [str(n.sleep_date) for n in anomalous]},
        db=db,
    )


# ── Rule 4: Data gap ──────────────────────────────────────────────────────────

async def _rule_data_gap(user_id, db: AsyncSession) -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(days=3)
    result = await db.execute(
        select(KeystrokeMetrics)
        .where(KeystrokeMetrics.user_id == user_id, KeystrokeMetrics.session_start >= cutoff)
        .limit(1)
    )
    if result.scalar_one_or_none():
        return   # data present — no gap

    if await _recent_alert_exists(user_id, "data_gap", days=3, db=db):
        return

    await _create_alert(
        user_id=user_id,
        alert_type="data_gap",
        severity="info",
        title="Monitoring Data Gap",
        body=(
            "No typing activity has been detected in the last 3 days. "
            "Please ensure the NeuroGuard app is active on your device."
        ),
        metadata={"gap_days": 3},
        db=db,
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _latest_prediction(user_id, db: AsyncSession):
    result = await db.execute(
        select(RiskPrediction)
        .where(RiskPrediction.user_id == user_id)
        .order_by(desc(RiskPrediction.predicted_at))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _recent_alert_exists(user_id, alert_type: str, days: int, db: AsyncSession) -> bool:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(
        select(Alert).where(
            and_(
                Alert.user_id == user_id,
                Alert.alert_type == alert_type,
                Alert.created_at >= cutoff,
            )
        ).limit(1)
    )
    return result.scalar_one_or_none() is not None


async def _create_alert(
    user_id, alert_type: str, severity: str, title: str, body: str,
    metadata: dict, db: AsyncSession
) -> Alert:
    alert = Alert(
        user_id=user_id,
        alert_type=alert_type,
        severity=severity,
        title=title,
        body=body,
        metadata_=metadata,
    )
    db.add(alert)
    await db.flush()
    logger.info("Created alert type=%s severity=%s user=%s", alert_type, severity, user_id)

    # Fan out to FCM / email — non-blocking, errors logged but not raised
    try:
        delivery = await deliver_alert(alert, db)
        logger.info(
            "Delivery for alert %s: fcm=%d email=%d errors=%s",
            alert.id, delivery["fcm"], delivery["email"], delivery["errors"],
        )
    except Exception as e:
        logger.warning("Delivery failed for alert %s: %s", alert.id, e)

    return alert
