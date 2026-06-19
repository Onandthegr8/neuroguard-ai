# NeuroGuard Model Card

**File**: `ml/models/best_model.pt`
**Architecture**: TCN + BiLSTM + MultiHeadAttention (665,793 params)
**Trained**: 2026-05-14, 12 epochs, CPU

## Training data

Synthetic. 8,000 samples generated from class-conditional Gaussian distributions
based on published biomarker statistics for early-stage Parkinson's disease:

- Giancardo et al. (2016) — IKI variability & dwell time
- Iakovakis et al. (2018) — Smartphone keystroke patterns
- Stefani & Hogl (2020) — REM behaviour disorder + RDI
- Postuma et al. (2019) — Autonomic markers (HRV) in prodromal PD

**Class balance**: 25% PD positive (oversampled — real general-population
prevalence is ~1.5%).

**Replace before clinical use** with UCI Parkinson's Telemonitoring, PhysioNet
mPower, or your own labelled cohort.

## Hyperparameters

| Setting | Value |
|---------|-------|
| Epochs | 12 |
| Batch size | 64 |
| Learning rate | 1e-3 (AdamW, cosine schedule) |
| Weight decay | 1e-4 |
| Dropout | 0.4 |
| Pos class weight | 3.0 (loss reweighting) |
| Gradient clip | 1.0 |

## Performance (held-out test set, 1,200 samples)

| Metric | Value |
|--------|-------|
| AUC-ROC | **0.9950** |
| Precision | 0.9963 |
| Recall | 0.8706 |
| F1 | ~0.93 |
| Best val AUC | 0.9932 (epoch 3) |

> **Caveat**: AUC near 1.0 is a hallmark of synthetic data being too separable.
> Real-world prodromal PD has substantial class overlap — expect AUC 0.85–0.90
> when retrained on PhysioNet/UCI data.

## Inference performance (CPU, 35-feature vector)

| Workload | Latency |
|----------|---------|
| Forward pass only | **9.5 ms** (p50), 12 ms (p95) |
| Forward + SHAP (50 background) | ~110 ms (estimated) |
| MC Dropout (20 samples, uncertainty) | ~190 ms |

Target was <80ms server-side — **comfortably met**.

## Files in this directory

| File | Purpose |
|------|---------|
| `best_model.pt` | PyTorch state dict + val metrics |
| `best_model_norm_stats.json` | Per-feature mean/std from training scaler |
| `training_history.json` | Per-epoch loss + val metrics |
| `neuroguard_model.py` | Model architecture (TCN+BiLSTM+Attn) |

## How to retrain with real data

1. Acquire labelled data with columns matching `dataset.ParkinsonsDataset.KEYSTROKE_COLS + SLEEP_COLS + ["parkinson_label"]`.
2. Place at `data/parkinson_features.csv`.
3. Run:
   ```bash
   python -m ml.training.train --data_path data/parkinson_features.csv \
       --output ml/models/ --epochs 50 --batch_size 64 --pos_weight 10
   ```
4. The new `best_model.pt` + norm stats will overwrite the existing files.
5. Risk service auto-picks them up on next restart (`docker compose restart risk`).
