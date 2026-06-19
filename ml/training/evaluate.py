"""Model evaluation: AUC-ROC, precision, recall, F1, calibration."""

import numpy as np
import torch
from sklearn.calibration import calibration_curve
from sklearn.metrics import (
    average_precision_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from torch.utils.data import DataLoader


def evaluate_model(model, loader: DataLoader, device: torch.device) -> dict:
    model.eval()
    all_preds, all_labels = [], []

    with torch.no_grad():
        for ks, sl, labels in loader:
            ks, sl = ks.to(device), sl.to(device)
            preds = model(ks, sl).cpu().squeeze().numpy()
            all_preds.extend(preds.tolist() if preds.ndim > 0 else [float(preds)])
            all_labels.extend(labels.squeeze().numpy().tolist() if labels.squeeze().ndim > 0 else [float(labels.squeeze())])

    preds_arr = np.array(all_preds)
    labels_arr = np.array(all_labels)
    binary_preds = (preds_arr >= 0.5).astype(int)

    try:
        auc_roc = roc_auc_score(labels_arr, preds_arr)
        auc_pr = average_precision_score(labels_arr, preds_arr)
    except ValueError:
        auc_roc = auc_pr = 0.5

    return {
        "auc_roc": round(float(auc_roc), 4),
        "auc_pr": round(float(auc_pr), 4),
        "precision": round(float(precision_score(labels_arr, binary_preds, zero_division=0)), 4),
        "recall": round(float(recall_score(labels_arr, binary_preds, zero_division=0)), 4),
        "f1": round(float(f1_score(labels_arr, binary_preds, zero_division=0)), 4),
        "n_samples": len(labels_arr),
        "positive_rate": round(float(labels_arr.mean()), 4),
    }
