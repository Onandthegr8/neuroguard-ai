"""
Quick smoke test: load the trained model and run inference on two samples
(one healthy-looking, one PD-looking) to confirm the model differentiates.

Usage:
    python -m ml.verify_model
"""

import sys
from pathlib import Path

import numpy as np
import torch

from ml.models.neuroguard_model import NeuroGuardModel


def main() -> int:
    model_path = Path("ml/models/best_model.pt")
    if not model_path.exists():
        print(f"[FAIL] Model not found at {model_path}")
        return 1

    checkpoint = torch.load(model_path, map_location="cpu", weights_only=False)
    state_dict = checkpoint.get("model_state_dict", checkpoint) if isinstance(checkpoint, dict) else checkpoint

    model = NeuroGuardModel()
    model.load_state_dict(state_dict)
    model.eval()

    val_metrics = checkpoint.get("val_metrics") if isinstance(checkpoint, dict) else None
    print(f"[OK] Model loaded ({sum(p.numel() for p in model.parameters()):,} params)")
    if val_metrics:
        print(f"     Validation metrics: AUC={val_metrics.get('auc_roc')}, F1={val_metrics.get('f1')}")

    # ── Two test samples ──────────────────────────────────────────────────────
    # Healthy-looking: short dwell, low IKI variance, good sleep
    healthy_ks = np.array([
        85, 20, 190, 55, 140, 240, 0.28, 45, 0.04, 0.03,
        0.72, 0.05, 1.8, 28, 0.78, 185, 50, 0.06, 0.22, 0.15,
    ], dtype=np.float32)
    healthy_sl = np.array([
        95, 0.18, 0.85, 18, 0.22, 42, 62, 0.20, 3.5, 12,
        0.0, 0.0, 0.0, 0.10, 0.80,
    ], dtype=np.float32)

    # PD-looking: long dwell, high IKI variance, REM fragmentation
    pd_ks = np.array([
        108, 40, 270, 130, 175, 350, 0.55, 28, 0.13, 0.08,
        0.42, 0.13, 2.7, 17, 0.52, 255, 105, 0.20, 0.12, 0.34,
    ], dtype=np.float32)
    pd_sl = np.array([
        68, 0.58, 0.70, 33, 0.50, 24, 73, 0.12, 8.2, 26,
        -0.05, -0.07, -0.03, 0.45, 0.52,
    ], dtype=np.float32)

    with torch.no_grad():
        h_score = float(model(
            torch.tensor(healthy_ks).unsqueeze(0),
            torch.tensor(healthy_sl).unsqueeze(0),
        ).item())
        p_score = float(model(
            torch.tensor(pd_ks).unsqueeze(0),
            torch.tensor(pd_sl).unsqueeze(0),
        ).item())

    print(f"\n  Healthy-looking sample -> risk score: {h_score:.3f}")
    print(f"  PD-looking sample      -> risk score: {p_score:.3f}")
    print(f"  Differentiation        : {p_score - h_score:+.3f}")

    if p_score > h_score:
        print("\n[OK] Model correctly assigns higher risk to PD-looking sample.")
        return 0
    else:
        print("\n[WARN] Model did not differentiate — check training.")
        return 2


if __name__ == "__main__":
    sys.exit(main())
