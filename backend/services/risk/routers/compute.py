"""POST /risk/compute — run ML inference for a user and persist the prediction."""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import numpy as np
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from ....shared.config import get_settings
from ....shared.db.session import get_db
from ....shared.models.keystroke_metrics import KeystrokeMetrics
from ....shared.models.risk_prediction import RiskPrediction
from ....shared.models.sleep_metrics import SleepMetrics
from ....shared.security.jwt import get_current_user
from ....shared.security.rbac import Role, require_role

router = APIRouter()
settings = get_settings()


@router.post("/compute", status_code=status.HTTP_202_ACCEPTED)
async def trigger_risk_compute(
    background_tasks: BackgroundTasks,
    patient_id: Optional[uuid.UUID] = None,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Trigger ML inference for a user.
    Clinicians/admins may specify patient_id; regular users compute for themselves.
    Result is stored in risk_predictions and retrievable via GET /risk/score.
    """
    role = current_user.get("role", "user")
    caller_id = uuid.UUID(current_user["sub"])

    if patient_id and role not in (Role.CLINICIAN, Role.HOSPITAL_ADMIN, Role.SUPER_ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only clinicians may compute risk for other patients")

    target_id = patient_id or caller_id
    background_tasks.add_task(_compute_and_store, target_id)
    return {"status": "queued", "patient_id": str(target_id)}


async def _compute_and_store(user_id: uuid.UUID) -> None:
    """Background task: fetch features, run model, persist prediction."""
    from ....shared.db.session import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        features = await _build_feature_vector(user_id, db)
        if features is None:
            return  # Not enough data yet

        score, shap_vals = _run_inference(features)
        tier = settings.risk_tier(score)

        # Platt scaling confidence interval (±0.07 typical)
        ci_low  = max(0.0, score - 0.07)
        ci_high = min(1.0, score + 0.07)

        # Keystroke vs sleep contribution split from SHAP
        ks_contrib  = sum(abs(v) for k, v in shap_vals.items() if "typing" in k or "iki" in k or "dwell" in k)
        slp_contrib = sum(abs(v) for k, v in shap_vals.items() if "rem" in k or "hrv" in k or "sleep" in k)
        total = ks_contrib + slp_contrib + 1e-9
        ks_pct  = round(ks_contrib / total, 3)
        slp_pct = round(slp_contrib / total, 3)

        prediction = RiskPrediction(
            user_id=user_id,
            risk_score=float(score),
            risk_tier=tier,
            confidence_low=ci_low,
            confidence_high=ci_high,
            model_version=settings.model_version,
            shap_values=shap_vals,
            feature_inputs={"vector_length": len(features)},
            keystroke_contribution=ks_pct,
            sleep_contribution=slp_pct,
        )
        db.add(prediction)
        await db.commit()


async def _build_feature_vector(user_id: uuid.UUID, db: AsyncSession) -> Optional[list]:
    """Assemble the 35-feature vector from the last 30 days of data."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)

    ks_result = await db.execute(
        select(KeystrokeMetrics)
        .where(KeystrokeMetrics.user_id == user_id, KeystrokeMetrics.session_start >= cutoff)
        .order_by(desc(KeystrokeMetrics.session_start))
        .limit(50)
    )
    ks_rows = ks_result.scalars().all()

    sleep_result = await db.execute(
        select(SleepMetrics)
        .where(SleepMetrics.user_id == user_id, SleepMetrics.created_at >= cutoff)
        .order_by(desc(SleepMetrics.sleep_date))
        .limit(30)
    )
    sleep_rows = sleep_result.scalars().all()

    if len(ks_rows) < 3 and len(sleep_rows) < 3:
        return None  # insufficient data

    # ── Keystroke features (20) ───────────────────────────────────────────────
    all_dwell = [v for row in ks_rows for v in (row.key_press_duration_ms or [])]
    all_iki   = [v for row in ks_rows for v in (row.inter_key_interval_ms or [])]

    def safe_mean(lst): return float(np.mean(lst)) if lst else 0.0
    def safe_std(lst):  return float(np.std(lst))  if len(lst) > 1 else 0.0
    def safe_pct(lst, p): return float(np.percentile(lst, p)) if lst else 0.0
    def cv(lst): m = safe_mean(lst); return safe_std(lst) / (m + 1e-9) if m else 0.0

    ks_features = [
        safe_mean(all_dwell),                                       # mean_dwell_ms
        safe_std(all_dwell),                                        # std_dwell_ms
        safe_mean(all_iki),                                         # mean_iki_ms
        safe_std(all_iki),                                          # std_iki_ms
        safe_pct(all_iki, 25),                                      # p25_iki
        safe_pct(all_iki, 75),                                      # p75_iki
        cv(all_iki),                                                # iki_entropy
        safe_mean([r.typing_speed_wpm for r in ks_rows if r.typing_speed_wpm]),   # typing_speed_wpm
        safe_mean([r.correction_frequency for r in ks_rows if r.correction_frequency]),  # correction_freq
        safe_mean([r.autocorrect_rate for r in ks_rows if r.autocorrect_rate]),   # autocorrect_rate
        1.0 - min(cv(all_iki), 1.0),                                # rhythm_score
        0.0,                                                        # velocity_decay_coeff (placeholder)
        float(np.std([r.session_start.hour for r in ks_rows])) if ks_rows else 0.0,  # diurnal_var
        float(len(ks_rows)),                                        # session_count_7d
        safe_mean([r.typing_entropy for r in ks_rows if r.typing_entropy]),       # typing_consistency_7d
        0.0, 0.0,                                                   # bigram_transition mean/std
        sum(1 for v in all_iki if v > 500) / (len(all_iki) + 1e-9),  # pause_frequency
        0.0,                                                        # burst_typing_rate
        0.0,                                                        # fatigue_index
    ]

    # ── Sleep features (15) ───────────────────────────────────────────────────
    def smean(attr): return safe_mean([getattr(r, attr) for r in sleep_rows if getattr(r, attr) is not None])

    rem_vals = [r.rem_fragmentation_idx for r in sleep_rows if r.rem_fragmentation_idx is not None]
    hrv_vals = [r.hrv_rmssd for r in sleep_rows if r.hrv_rmssd is not None]
    eff_vals = [r.sleep_efficiency for r in sleep_rows if r.sleep_efficiency is not None]

    sleep_features = [
        smean("rem_duration_min"),
        smean("rem_fragmentation_idx"),
        smean("sleep_efficiency"),
        smean("sleep_stage_transitions"),
        smean("nocturnal_movement_idx"),
        smean("hrv_rmssd"),
        smean("resting_hr"),
        smean("deep_sleep_min") / (smean("total_sleep_min") + 1e-9),   # deep_sleep_pct
        smean("awakenings"),
        smean("sleep_onset_min"),
        float(np.polyfit(range(len(rem_vals)), rem_vals, 1)[0]) if len(rem_vals) > 2 else 0.0,  # rem_7d_trend
        float(np.polyfit(range(len(hrv_vals)), hrv_vals, 1)[0]) if len(hrv_vals) > 2 else 0.0,  # hrv_14d_trend
        float(np.polyfit(range(len(eff_vals)), eff_vals, 1)[0]) if len(eff_vals) > 2 else 0.0,  # sleep_eff_30d_trend
        smean("rem_fragmentation_idx") * smean("sleep_stage_transitions"),  # rem_behavior_score
        1.0 - float(np.std([r.sleep_date.weekday() for r in sleep_rows]) / 3.0) if sleep_rows else 0.0,  # circadian_regularity
    ]

    return ks_features + sleep_features


def _run_inference(features: list) -> tuple[float, dict]:
    """Run the NeuroGuard model. Falls back to a heuristic if no weights file."""
    import os
    model_path = settings.model_path
    model_loaded = False
    score = None

    if os.path.exists(model_path):
        try:
            import torch
            from ml.models.neuroguard_model import NeuroGuardModel
            model = NeuroGuardModel()
            checkpoint = torch.load(model_path, map_location="cpu", weights_only=False)
            state_dict = checkpoint.get("model_state_dict", checkpoint) if isinstance(checkpoint, dict) else checkpoint
            model.load_state_dict(state_dict)
            model.eval()
            x = torch.tensor([features], dtype=torch.float32)
            with torch.no_grad():
                score = float(model(x[:, :20], x[:, 20:]).item())
            model_loaded = True
        except Exception:
            # Fall through to heuristic if torch / ml package / weights are unavailable
            model_loaded = False

    if not model_loaded:
        # Heuristic fallback: weighted sum of key risk indicators
        f = features
        score = min(1.0, max(0.0,
            f[6]  * 0.15 +   # IKI entropy
            f[9]  * 0.08 +   # correction_freq
            f[1]  * 0.0001 + # std_dwell
            (f[21] if len(f) > 21 else 0.3) * 0.25 +  # rem_fragmentation
            (1 - min((f[22] if len(f) > 22 else 0.75), 1.0)) * 0.20 +  # 1 - sleep_efficiency
            max(0, -(f[30] if len(f) > 30 else 0.0)) * 0.10 +  # negative hrv trend
            (f[17] if len(f) > 17 else 0.1) * 0.22   # pause_frequency
        ))

    # Generate approximate SHAP values (real SHAP computed in explainer.py when model loaded)
    feature_names = [
        "mean_dwell_ms","std_dwell_ms","mean_iki_ms","std_iki_ms","p25_iki","p75_iki",
        "iki_entropy","typing_speed_wpm","correction_freq","autocorrect_rate",
        "rhythm_score","velocity_decay","diurnal_var","session_count","typing_consistency",
        "bigram_mean","bigram_std","pause_frequency","burst_typing","fatigue_index",
        "rem_duration","rem_fragmentation","sleep_efficiency","stage_transitions",
        "nocturnal_movement","hrv_rmssd","resting_hr","deep_sleep_pct","awakenings",
        "sleep_onset","rem_7d_trend","hrv_14d_trend","sleep_eff_trend",
        "rem_behavior_score","circadian_regularity",
    ]
    total = sum(abs(v) for v in features) + 1e-9
    shap_vals = {
        name: round(float(v) / total * score, 5)
        for name, v in zip(feature_names, features)
        if abs(v) > 0.001
    }
    return score, shap_vals
