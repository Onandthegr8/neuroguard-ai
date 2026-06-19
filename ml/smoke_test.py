"""
Full smoke test of the inference pipeline.

Runs:
  1. Model load
  2. Normalization stats load
  3. Inference on 3 sample patients (healthy / moderate / PD)
  4. SHAP / gradient attribution
  5. Risk tier mapping
  6. Latency benchmark (50 inferences, report p50/p95)

Usage:
    python -m ml.smoke_test
"""

import statistics
import sys
import time
from pathlib import Path

import numpy as np
import torch

from ml.inference.pipeline import InferencePipeline


SAMPLES = {
    "healthy_30yo": {
        "keystroke": {
            "mean_dwell_ms": 78, "std_dwell_ms": 16, "mean_iki_ms": 175, "std_iki_ms": 48,
            "p25_iki": 130, "p75_iki": 220, "iki_entropy": 0.25, "typing_speed_wpm": 52,
            "correction_freq": 0.03, "autocorrect_rate": 0.02, "rhythm_score": 0.78,
            "velocity_decay_coeff": 0.04, "diurnal_var": 1.5, "session_count_7d": 32,
            "typing_consistency_7d": 0.82, "bigram_transition_mean": 175, "bigram_transition_std": 45,
            "pause_frequency": 0.05, "burst_typing_rate": 0.28, "fatigue_index": 0.12,
        },
        "sleep": {
            "rem_duration_min": 105, "rem_fragmentation_idx": 0.14, "sleep_efficiency": 0.90,
            "stage_transition_count": 14, "nocturnal_movement_idx": 0.18, "hrv_rmssd": 48,
            "resting_hr": 58, "deep_sleep_pct": 0.22, "awakenings": 2, "sleep_onset_min": 8,
            "rem_7d_trend": 0.01, "hrv_14d_trend": 0.02, "sleep_eff_30d_trend": 0.00,
            "rem_behavior_score": 0.08, "circadian_regularity_score": 0.86,
        },
    },
    "moderate_55yo": {
        "keystroke": {
            "mean_dwell_ms": 95, "std_dwell_ms": 28, "mean_iki_ms": 225, "std_iki_ms": 85,
            "p25_iki": 160, "p75_iki": 295, "iki_entropy": 0.40, "typing_speed_wpm": 36,
            "correction_freq": 0.08, "autocorrect_rate": 0.05, "rhythm_score": 0.58,
            "velocity_decay_coeff": 0.08, "diurnal_var": 2.2, "session_count_7d": 22,
            "typing_consistency_7d": 0.66, "bigram_transition_mean": 220, "bigram_transition_std": 75,
            "pause_frequency": 0.12, "burst_typing_rate": 0.18, "fatigue_index": 0.24,
        },
        "sleep": {
            "rem_duration_min": 85, "rem_fragmentation_idx": 0.35, "sleep_efficiency": 0.78,
            "stage_transition_count": 22, "nocturnal_movement_idx": 0.32, "hrv_rmssd": 34,
            "resting_hr": 68, "deep_sleep_pct": 0.16, "awakenings": 5, "sleep_onset_min": 18,
            "rem_7d_trend": -0.02, "hrv_14d_trend": -0.03, "sleep_eff_30d_trend": -0.01,
            "rem_behavior_score": 0.22, "circadian_regularity_score": 0.68,
        },
    },
    "pd_likely_68yo": {
        "keystroke": {
            "mean_dwell_ms": 118, "std_dwell_ms": 45, "mean_iki_ms": 295, "std_iki_ms": 145,
            "p25_iki": 195, "p75_iki": 380, "iki_entropy": 0.62, "typing_speed_wpm": 22,
            "correction_freq": 0.16, "autocorrect_rate": 0.09, "rhythm_score": 0.35,
            "velocity_decay_coeff": 0.18, "diurnal_var": 3.1, "session_count_7d": 12,
            "typing_consistency_7d": 0.42, "bigram_transition_mean": 285, "bigram_transition_std": 120,
            "pause_frequency": 0.28, "burst_typing_rate": 0.08, "fatigue_index": 0.45,
        },
        "sleep": {
            "rem_duration_min": 58, "rem_fragmentation_idx": 0.72, "sleep_efficiency": 0.62,
            "stage_transition_count": 42, "nocturnal_movement_idx": 0.62, "hrv_rmssd": 19,
            "resting_hr": 78, "deep_sleep_pct": 0.08, "awakenings": 11, "sleep_onset_min": 38,
            "rem_7d_trend": -0.08, "hrv_14d_trend": -0.10, "sleep_eff_30d_trend": -0.05,
            "rem_behavior_score": 0.62, "circadian_regularity_score": 0.40,
        },
    },
}


def main() -> int:
    model_path = "ml/models/best_model.pt"
    if not Path(model_path).exists():
        print(f"[FAIL] Model not found at {model_path}")
        return 1

    print(f"Loading inference pipeline from {model_path}...")
    pipeline = InferencePipeline(model_path=model_path, model_version="v1.0.0-synth")
    print(f"[OK] Pipeline loaded\n")

    # ── Run inference on each sample ──────────────────────────────────────────
    results = []
    for name, sample in SAMPLES.items():
        result = pipeline.predict(
            keystroke_features=sample["keystroke"],
            sleep_features=sample["sleep"],
            compute_shap=True,
            n_mc_samples=10,
        )
        results.append((name, result))

        print(f"── {name} ─────────────────────────────────────")
        print(f"  Risk score      : {result.risk_score:.3f}  ({result.risk_tier})")
        print(f"  Confidence      : [{result.confidence_low:.3f}, {result.confidence_high:.3f}]")
        print(f"  KS contribution : {result.keystroke_contribution:+.3f}")
        print(f"  SL contribution : {result.sleep_contribution:+.3f}")
        print(f"  Top features    :")
        for c in result.top_contributors[:3]:
            print(f"    - {c['feature']:30s} {c['contribution_pct']:>5.1f}% ({c['direction']})")
        print(f"  Inference time  : {result.latency_ms:.1f}ms\n")

    # ── Differentiation check ─────────────────────────────────────────────────
    healthy_score = results[0][1].risk_score
    pd_score      = results[2][1].risk_score
    diff = pd_score - healthy_score
    if diff > 0.2:
        print(f"[OK] Model differentiates: PD score {pd_score:.2f} > healthy {healthy_score:.2f} (Δ={diff:+.2f})")
    else:
        print(f"[WARN] Weak differentiation: Δ={diff:+.2f}")

    # ── Latency benchmark ─────────────────────────────────────────────────────
    sample = SAMPLES["moderate_55yo"]
    timings = []
    for _ in range(50):
        t0 = time.perf_counter()
        pipeline.predict(sample["keystroke"], sample["sleep"], compute_shap=False, n_mc_samples=1)
        timings.append((time.perf_counter() - t0) * 1000)

    p50 = statistics.median(timings)
    p95 = sorted(timings)[int(len(timings) * 0.95)]
    print(f"\nLatency over 50 runs (SHAP disabled): p50={p50:.1f}ms, p95={p95:.1f}ms")
    print(f"Target: <80ms server-side — {'PASS' if p95 < 80 else 'OVER BUDGET'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
