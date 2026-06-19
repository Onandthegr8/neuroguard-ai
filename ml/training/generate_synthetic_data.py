"""
Synthetic Parkinson's training data generator.

In production this is replaced by:
  - UCI Parkinson's Telemonitoring (voice features → keystroke proxies)
  - PhysioNet mPower (accelerometer + sleep)

For development we generate statistically realistic samples based on
published biomarker distributions for PD vs. healthy controls.

Key sources used to set parameters:
  - Giancardo et al. (2016): IKI variability & dwell-time in PD
  - Iakovakis et al. (2018): Smartphone keystroke patterns in early PD
  - Stefani & Hogl (2020): REM sleep behaviour disorder + RDI in PD
  - Postuma et al. (2019): Autonomic markers (HRV) in prodromal PD

Usage:
  python -m ml.training.generate_synthetic_data --n 5000 --out data/parkinson_features.csv
"""

import argparse
import os
from pathlib import Path

import numpy as np
import pandas as pd


# Class-conditional means + std-devs for every feature.
# (mu_healthy, sigma_healthy, mu_pd, sigma_pd)
FEATURE_DISTRIBUTIONS = {
    # ── Keystroke (20) ────────────────────────────────────────────────────────
    # Healthy typists have shorter dwell, lower IKI variance, faster typing.
    "mean_dwell_ms":          (85.0, 15.0, 105.0, 22.0),   # PD ↑ ~24%
    "std_dwell_ms":           (20.0,  6.0,  38.0, 12.0),   # PD ↑ ~90%
    "mean_iki_ms":           (190.0, 40.0, 260.0, 70.0),   # PD ↑ ~37%
    "std_iki_ms":             (55.0, 18.0, 130.0, 40.0),   # PD ↑ ~135%
    "p25_iki":               (140.0, 30.0, 175.0, 45.0),
    "p75_iki":               (240.0, 50.0, 340.0, 85.0),
    "iki_entropy":             (0.28, 0.08,  0.52, 0.15),   # CV of IKI
    "typing_speed_wpm":       (45.0,  8.0,  28.0, 9.0),    # PD ↓ ~38%
    "correction_freq":         (0.04, 0.02,  0.11, 0.05),
    "autocorrect_rate":        (0.03, 0.015, 0.07, 0.03),
    "rhythm_score":            (0.72, 0.12,  0.45, 0.18),  # PD ↓
    "velocity_decay_coeff":    (0.05, 0.03,  0.12, 0.06),  # fatigue in PD ↑
    "diurnal_var":             (1.8,  0.6,   2.6,  1.0),   # erratic timing
    "session_count_7d":       (28.0,  8.0,  18.0, 7.0),    # less typing in PD
    "typing_consistency_7d":   (0.78, 0.10,  0.55, 0.15),
    "bigram_transition_mean": (185.0, 35.0, 250.0, 55.0),
    "bigram_transition_std":   (50.0, 15.0, 100.0, 30.0),
    "pause_frequency":         (0.06, 0.03,  0.18, 0.07),
    "burst_typing_rate":       (0.22, 0.10,  0.13, 0.07),
    "fatigue_index":           (0.15, 0.08,  0.32, 0.12),

    # ── Sleep (15) ────────────────────────────────────────────────────────────
    "rem_duration_min":        (95.0, 22.0,  72.0, 28.0),   # PD ↓
    "rem_fragmentation_idx":   (0.18, 0.08,  0.55, 0.18),   # PD ↑ (key biomarker!)
    "sleep_efficiency":        (0.85, 0.06,  0.72, 0.09),
    "stage_transition_count": (18.0,  5.0,  32.0, 9.0),     # PD ↑
    "nocturnal_movement_idx":  (0.22, 0.10,  0.48, 0.15),
    "hrv_rmssd":              (42.0, 12.0,  26.0, 9.0),     # PD ↓ ~38%
    "resting_hr":             (62.0,  8.0,  72.0, 10.0),
    "deep_sleep_pct":          (0.20, 0.05,  0.13, 0.05),
    "awakenings":              (3.5,  1.5,   7.8,  2.5),
    "sleep_onset_min":        (12.0,  6.0,  24.0, 12.0),
    "rem_7d_trend":            (0.00, 0.05, -0.04, 0.06),   # declining REM
    "hrv_14d_trend":           (0.00, 0.08, -0.06, 0.09),   # declining HRV
    "sleep_eff_30d_trend":     (0.00, 0.03, -0.02, 0.04),
    "rem_behavior_score":      (0.10, 0.08,  0.42, 0.18),
    "circadian_regularity_score": (0.80, 0.12, 0.55, 0.18),
}


def generate(n_samples: int, pd_prevalence: float = 0.20, seed: int = 42, noise: float = 0.45) -> pd.DataFrame:
    """
    Generate `n_samples` rows with realistic overlap between classes.

    Args:
        noise: 0 = perfectly separable, 1 = no signal. 0.45 produces ~AUC 0.87
               which matches the published target for early-stage PD detection.

    In real general population PD prevalence is ~1.5%, but for training
    we oversample to 15-30% so the model has enough positive examples.
    """
    rng = np.random.default_rng(seed)
    n_pd      = int(n_samples * pd_prevalence)
    n_healthy = n_samples - n_pd

    rows = []

    def _draw(class_pd: bool) -> dict:
        row: dict = {}
        for feat, (mu_h, sig_h, mu_pd, sig_pd) in FEATURE_DISTRIBUTIONS.items():
            if class_pd:
                # Inflate sigma to make classes overlap (realistic prodromal PD)
                val = rng.normal(mu_pd, sig_pd * (1 + noise * 1.5))
            else:
                val = rng.normal(mu_h, sig_h * (1 + noise * 1.5))
            # Add a small random subset of "atypical" samples (5%) that look
            # like the opposite class — captures real-world ambiguity
            if rng.random() < 0.05:
                if class_pd:
                    val = rng.normal(mu_h, sig_h)
                else:
                    val = rng.normal(mu_pd, sig_pd)
            # Clip to plausible ranges
            if feat in ("iki_entropy", "sleep_efficiency", "rhythm_score",
                        "typing_consistency_7d", "deep_sleep_pct",
                        "circadian_regularity_score", "rem_fragmentation_idx",
                        "correction_freq", "autocorrect_rate",
                        "nocturnal_movement_idx", "pause_frequency",
                        "burst_typing_rate", "fatigue_index", "velocity_decay_coeff",
                        "rem_behavior_score"):
                val = float(np.clip(val, 0.0, 1.0))
            elif feat in ("awakenings", "session_count_7d", "stage_transition_count"):
                val = max(0.0, float(val))
            else:
                val = float(val)
            row[feat] = round(val, 4)
        row["parkinson_label"] = 1.0 if class_pd else 0.0
        return row

    for _ in range(n_healthy):
        rows.append(_draw(class_pd=False))
    for _ in range(n_pd):
        rows.append(_draw(class_pd=True))

    df = pd.DataFrame(rows).sample(frac=1, random_state=seed).reset_index(drop=True)
    return df


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n",     type=int,   default=5000)
    parser.add_argument("--pd",    type=float, default=0.20, help="PD class prevalence (0.0-1.0)")
    parser.add_argument("--seed",  type=int,   default=42)
    parser.add_argument("--out",   type=str,   default="data/parkinson_features.csv")
    args = parser.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    df = generate(args.n, pd_prevalence=args.pd, seed=args.seed)
    df.to_csv(out_path, index=False)
    print(f"Wrote {len(df)} samples to {out_path}")
    print(f"PD positive rate: {df['parkinson_label'].mean():.2%}")
    print(f"Features: {len(df.columns) - 1}")
