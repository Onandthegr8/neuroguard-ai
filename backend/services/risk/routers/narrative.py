"""
Narrative AI explanation generator.

Converts SHAP attributions + recent biomarker trends into human-readable prose:

  "Your risk score increased to 0.62 (high). The main drivers were typing
   entropy (up 18% vs. your 30-day baseline) and REM fragmentation (rising
   to 0.68, above the 0.5 threshold). Sleep efficiency held steady."

Pure rule-based — no LLM dependency. Always deterministic, always cite-able,
always defensible to a clinical reviewer.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from ....shared.models.keystroke_metrics import KeystrokeMetrics
from ....shared.models.risk_prediction  import RiskPrediction
from ....shared.models.sleep_metrics    import SleepMetrics


# Feature display names + plain-English direction.  "high_is_bad" means rising
# values increase Parkinson's risk; "low_is_bad" means falling values do.
_FEATURE_META: dict[str, dict] = {
    # Keystroke
    "iki_entropy":            {"label": "typing rhythm variability",   "polarity": "high_is_bad", "unit": ""},
    "mean_iki_ms":            {"label": "average pause between keys",  "polarity": "high_is_bad", "unit": " ms"},
    "std_iki_ms":             {"label": "typing-pause variability",    "polarity": "high_is_bad", "unit": " ms"},
    "std_dwell_ms":           {"label": "key-press hold variability",  "polarity": "high_is_bad", "unit": " ms"},
    "mean_dwell_ms":          {"label": "average key-press hold time", "polarity": "high_is_bad", "unit": " ms"},
    "typing_speed_wpm":       {"label": "typing speed",                "polarity": "low_is_bad",  "unit": " WPM"},
    "correction_freq":        {"label": "backspace frequency",         "polarity": "high_is_bad", "unit": ""},
    "rhythm_score":           {"label": "typing rhythm consistency",   "polarity": "low_is_bad",  "unit": ""},
    "pause_frequency":        {"label": "long-pause frequency",        "polarity": "high_is_bad", "unit": ""},
    # Sleep
    "rem_fragmentation":      {"label": "REM-sleep fragmentation",     "polarity": "high_is_bad", "unit": ""},
    "rem_duration":           {"label": "REM-sleep duration",          "polarity": "low_is_bad",  "unit": " min"},
    "sleep_efficiency":       {"label": "sleep efficiency",            "polarity": "low_is_bad",  "unit": ""},
    "stage_transitions":      {"label": "sleep-stage transitions",     "polarity": "high_is_bad", "unit": ""},
    "hrv_rmssd":              {"label": "heart-rate variability (RMSSD)", "polarity": "low_is_bad", "unit": " ms"},
    "resting_hr":             {"label": "resting heart rate",          "polarity": "high_is_bad", "unit": " bpm"},
    "awakenings":             {"label": "nightly awakenings",          "polarity": "high_is_bad", "unit": ""},
    "nocturnal_movement":     {"label": "nocturnal movement",          "polarity": "high_is_bad", "unit": ""},
    "rem_7d_trend":           {"label": "7-day REM trend",             "polarity": "high_is_bad", "unit": ""},
    "hrv_14d_trend":          {"label": "14-day HRV trend",            "polarity": "low_is_bad",  "unit": ""},
    "circadian_regularity":   {"label": "circadian regularity",        "polarity": "low_is_bad",  "unit": ""},
    "rem_behavior_score":     {"label": "REM-behavior pattern",        "polarity": "high_is_bad", "unit": ""},
}


def _tier_phrase(tier: str) -> str:
    return {
        "very_low":  "very low",
        "low":       "low",
        "moderate":  "moderate",
        "high":      "high",
        "very_high": "very high",
    }.get(tier, tier)


def _direction_phrase(direction: str, polarity: str) -> str:
    """
    direction = 'increases_risk' | 'decreases_risk' (from SHAP sign)
    polarity  = 'high_is_bad'    | 'low_is_bad'      (clinical reading of the feature)

    Returns a clause like "rising above the typical range" or "below your baseline".
    """
    rising = direction == "increases_risk"
    bad    = polarity   == "high_is_bad"

    if rising and bad:    return "above your typical range"
    if rising and not bad:return "below your typical range"
    if not rising and bad:return "trending in a favourable direction"
    return "above your typical range (a positive sign)"


async def _compare_baseline(
    user_id: uuid.UUID, db: AsyncSession,
) -> dict[str, float]:
    """
    Return a per-feature percent change of the most recent 7-day window vs. the
    prior 30-day window.  Used to anchor the prose in concrete deltas.
    """
    deltas: dict[str, float] = {}

    # Keystroke deltas
    now      = datetime.now(timezone.utc)
    recent_q = await db.execute(
        select(KeystrokeMetrics)
        .where(KeystrokeMetrics.user_id == user_id,
               KeystrokeMetrics.session_start >= now - timedelta(days=7))
    )
    baseline_q = await db.execute(
        select(KeystrokeMetrics)
        .where(KeystrokeMetrics.user_id == user_id,
               KeystrokeMetrics.session_start <  now - timedelta(days=7),
               KeystrokeMetrics.session_start >= now - timedelta(days=37))
    )
    recent_k   = recent_q.scalars().all()
    baseline_k = baseline_q.scalars().all()

    def _avg(rows, attr):
        vals = [getattr(r, attr) for r in rows if getattr(r, attr) is not None]
        return sum(vals) / len(vals) if vals else None

    for sql_attr, narrative_key in [
        ("typing_entropy",       "iki_entropy"),
        ("typing_speed_wpm",     "typing_speed_wpm"),
        ("correction_frequency", "correction_freq"),
    ]:
        r = _avg(recent_k, sql_attr); b = _avg(baseline_k, sql_attr)
        if r is not None and b is not None and b > 0.01:
            deltas[narrative_key] = (r - b) / b * 100

    # Sleep deltas
    recent_s   = (await db.execute(
        select(SleepMetrics).where(
            SleepMetrics.user_id == user_id,
            SleepMetrics.sleep_date >= (now - timedelta(days=7)).date(),
        )
    )).scalars().all()
    baseline_s = (await db.execute(
        select(SleepMetrics).where(
            SleepMetrics.user_id == user_id,
            SleepMetrics.sleep_date <  (now - timedelta(days=7)).date(),
            SleepMetrics.sleep_date >= (now - timedelta(days=37)).date(),
        )
    )).scalars().all()

    for sql_attr, narrative_key in [
        ("rem_fragmentation_idx", "rem_fragmentation"),
        ("sleep_efficiency",      "sleep_efficiency"),
        ("hrv_rmssd",             "hrv_rmssd"),
        ("resting_hr",            "resting_hr"),
        ("rem_duration_min",      "rem_duration"),
    ]:
        r = _avg(recent_s, sql_attr); b = _avg(baseline_s, sql_attr)
        if r is not None and b is not None and abs(b) > 0.01:
            deltas[narrative_key] = (r - b) / b * 100

    return deltas


async def build_narrative(
    prediction: RiskPrediction,
    db: AsyncSession,
    previous: Optional[RiskPrediction] = None,
) -> dict:
    """
    Build a structured narrative:
      headline:   one-sentence summary
      drivers:    list of plain-English driver phrases (top 3)
      protective: list of plain-English protective factor phrases (top 2)
      callouts:   short clinical notes worth highlighting
      paragraph:  the full prose paragraph that can be shown verbatim
    """
    shap = prediction.shap_values or {}
    if not shap:
        return {
            "headline":   f"Risk score: {prediction.risk_score:.0%} ({_tier_phrase(prediction.risk_tier)}).",
            "drivers":    [],
            "protective": [],
            "callouts":   [],
            "paragraph":  f"Risk score: {prediction.risk_score:.0%} ({_tier_phrase(prediction.risk_tier)}). "
                          "Detailed feature explanations will become available after more data has been collected.",
        }

    # Rank features by |SHAP|
    ranked = sorted(shap.items(), key=lambda kv: abs(kv[1]), reverse=True)
    risk_increasing  = [(k, v) for k, v in ranked if v > 0]
    risk_decreasing  = [(k, v) for k, v in ranked if v < 0]

    deltas = await _compare_baseline(prediction.user_id, db)

    # Top 3 drivers
    drivers = []
    for feat, val in risk_increasing[:3]:
        meta  = _FEATURE_META.get(feat, {"label": feat.replace("_", " "), "polarity": "high_is_bad", "unit": ""})
        delta = deltas.get(feat)
        phrase = meta["label"]
        if delta is not None:
            sign = "↑" if delta > 0 else "↓"
            phrase += f" ({sign}{abs(delta):.0f}% vs. your 30-day baseline)"
        else:
            phrase += f" — {_direction_phrase('increases_risk', meta['polarity'])}"
        drivers.append(phrase)

    # Top 2 protective factors
    protective = []
    for feat, val in risk_decreasing[:2]:
        meta = _FEATURE_META.get(feat, {"label": feat.replace("_", " "), "polarity": "high_is_bad", "unit": ""})
        protective.append(meta["label"] + " — holding within healthy range")

    # Tier-change callouts
    callouts = []
    if previous and previous.risk_tier != prediction.risk_tier:
        movement = "worsened" if prediction.risk_score > previous.risk_score else "improved"
        callouts.append(
            f"Tier {movement}: previously {_tier_phrase(previous.risk_tier)}, "
            f"now {_tier_phrase(prediction.risk_tier)}."
        )
    if prediction.keystroke_contribution and prediction.sleep_contribution is not None:
        if prediction.keystroke_contribution > 0.75:
            callouts.append("This score is driven primarily by typing-pattern changes.")
        elif prediction.sleep_contribution > 0.75:
            callouts.append("This score is driven primarily by sleep-biomarker changes.")

    # Compose the paragraph
    parts = [
        f"Your risk score is {prediction.risk_score:.0%} "
        f"({_tier_phrase(prediction.risk_tier)} risk band)."
    ]
    if drivers:
        parts.append("The main factors raising it are " + _join_natural(drivers) + ".")
    if protective:
        parts.append("On the positive side, " + _join_natural(protective) + ".")
    if callouts:
        parts.extend(callouts)
    paragraph = " ".join(parts)

    return {
        "headline":   f"Risk score: {prediction.risk_score:.0%} ({_tier_phrase(prediction.risk_tier)}).",
        "drivers":    drivers,
        "protective": protective,
        "callouts":   callouts,
        "paragraph":  paragraph,
    }


def _join_natural(items: list[str]) -> str:
    if not items:          return ""
    if len(items) == 1:    return items[0]
    if len(items) == 2:    return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + f", and {items[-1]}"


# ── FastAPI route ─────────────────────────────────────────────────────────────

from fastapi import APIRouter, Depends, HTTPException, status
from ....shared.db.session    import get_db
from ....shared.security.jwt  import get_current_user

router = APIRouter()


@router.get("/score/narrative")
async def get_narrative_explanation(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession   = Depends(get_db),
):
    """Return a plain-English explanation for the user's latest risk score."""
    user_id = uuid.UUID(current_user["sub"])

    rows = (await db.execute(
        select(RiskPrediction)
        .where(RiskPrediction.user_id == user_id)
        .order_by(desc(RiskPrediction.predicted_at))
        .limit(2)
    )).scalars().all()

    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No risk prediction available yet.",
        )

    latest   = rows[0]
    previous = rows[1] if len(rows) > 1 else None
    return await build_narrative(latest, db, previous)
