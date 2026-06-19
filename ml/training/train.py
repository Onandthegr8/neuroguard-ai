"""Supervised pre-training script for NeuroGuardModel on public datasets.

Usage:
    python -m ml.training.train --data_path data/parkinson_features.csv --epochs 50 --output models/
"""

import argparse
import json
import os
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

from ..models.neuroguard_model import NeuroGuardModel
from .dataset import ParkinsonsDataset
from .evaluate import evaluate_model


def train(args) -> None:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Training on {device}")

    df = pd.read_csv(args.data_path)
    train_ds, val_ds, test_ds = ParkinsonsDataset.random_split(df, train_frac=0.7, val_frac=0.15)
    print(f"Train: {len(train_ds)} | Val: {len(val_ds)} | Test: {len(test_ds)}")

    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True, num_workers=4, pin_memory=True)
    val_loader = DataLoader(val_ds, batch_size=args.batch_size, shuffle=False, num_workers=2)
    test_loader = DataLoader(test_ds, batch_size=args.batch_size, shuffle=False, num_workers=2)

    model = NeuroGuardModel(dropout=0.4).to(device)
    print(f"Model parameters: {model.n_parameters:,}")

    # Class weights for imbalanced dataset (PD prevalence ~1.5% general population)
    pos_weight = torch.tensor([args.pos_weight]).to(device)
    criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs)

    best_val_auc = 0.0
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    history = []

    for epoch in range(1, args.epochs + 1):
        model.train()
        epoch_loss = 0.0
        t0 = time.time()

        for ks, sl, labels in train_loader:
            ks, sl, labels = ks.to(device), sl.to(device), labels.to(device)
            optimizer.zero_grad()
            preds = model(ks, sl)
            loss = criterion(preds, labels)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()
            epoch_loss += loss.item()

        scheduler.step()
        avg_loss = epoch_loss / len(train_loader)
        val_metrics = evaluate_model(model, val_loader, device)
        elapsed = time.time() - t0

        print(
            f"Epoch {epoch:03d}/{args.epochs} | Loss: {avg_loss:.4f} | "
            f"Val AUC: {val_metrics['auc_roc']:.4f} | Val F1: {val_metrics['f1']:.4f} | {elapsed:.1f}s"
        )
        history.append({"epoch": epoch, "train_loss": avg_loss, **val_metrics})

        if val_metrics["auc_roc"] > best_val_auc:
            best_val_auc = val_metrics["auc_roc"]
            torch.save({"model_state_dict": model.state_dict(), "val_metrics": val_metrics, "epoch": epoch}, output_dir / "best_model.pt")
            print(f"  [OK] New best model saved (AUC: {best_val_auc:.4f})")

    # Final test evaluation
    checkpoint = torch.load(output_dir / "best_model.pt", map_location=device)
    model.load_state_dict(checkpoint["model_state_dict"])
    test_metrics = evaluate_model(model, test_loader, device)
    print(f"\nTest AUC-ROC: {test_metrics['auc_roc']:.4f} | Precision: {test_metrics['precision']:.4f} | Recall: {test_metrics['recall']:.4f}")

    with open(output_dir / "training_history.json", "w") as f:
        json.dump({"history": history, "test_metrics": test_metrics, "best_val_auc": best_val_auc}, f, indent=2)

    # Persist normalization stats alongside the model so the inference pipeline
    # can apply the same transform at serving time.
    norm_stats = {
        "keystroke_mean": train_ds.ks_scaler.mean_.tolist(),
        "keystroke_std":  train_ds.ks_scaler.scale_.tolist(),
        "sleep_mean":     train_ds.sl_scaler.mean_.tolist(),
        "sleep_std":      train_ds.sl_scaler.scale_.tolist(),
    }
    with open(output_dir / "best_model_norm_stats.json", "w") as f:
        json.dump(norm_stats, f, indent=2)

    print(f"\nTraining complete. Best model at {output_dir / 'best_model.pt'}")
    print(f"Normalization stats at {output_dir / 'best_model_norm_stats.json'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_path", required=True)
    parser.add_argument("--output", default="models/")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--batch_size", type=int, default=64)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--pos_weight", type=float, default=10.0, help="Weight for positive class (PD)")
    train(parser.parse_args())
