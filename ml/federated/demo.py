"""
Federated Learning Demo — Server + 2 simulated clients in one process.

Each client trains locally on a partition of the synthetic dataset, then
sends a DP-noised gradient update to the Flower server.

Run:
    python -m ml.federated.demo --rounds 3 --clients 2 --epochs 2
"""

import argparse
import multiprocessing
import os
import sys
import time
from pathlib import Path

import flwr as fl
import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader

# Import paths — works when run from project root via `python -m ml.federated.demo`
from ..models.neuroguard_model import NeuroGuardModel
from ..training.dataset import ParkinsonsDataset
from ..training.generate_synthetic_data import generate
from .strategy.adaptive_fedavg import AdaptiveFedAvg
from .client import NeuroGuardFLClient


SERVER_PORT = 8765


# ── Server process ────────────────────────────────────────────────────────────

def _run_server(num_rounds: int, min_clients: int) -> None:
    """Run Flower server. Blocks until all rounds complete."""
    strategy = AdaptiveFedAvg(
        min_fit_clients         = min_clients,
        min_available_clients   = min_clients,
        fraction_fit            = 1.0,    # use all available clients each round
        fraction_evaluate       = 1.0,
        min_epsilon_per_round   = 0.5,
    )
    # Initialise global weights
    model = NeuroGuardModel()
    weights = [v.cpu().numpy() for v in model.state_dict().values()]
    strategy.initial_parameters = fl.common.ndarrays_to_parameters(weights)

    print(f"[server] Starting on 0.0.0.0:{SERVER_PORT} — waiting for {min_clients} clients...")
    fl.server.start_server(
        server_address=f"0.0.0.0:{SERVER_PORT}",
        config=fl.server.ServerConfig(num_rounds=num_rounds),
        strategy=strategy,
    )
    print("[server] All rounds complete.")


# ── Client process ────────────────────────────────────────────────────────────

def _run_client(client_id: int, n_samples: int, local_epochs: int, server_port: int) -> None:
    """Run a single Flower client with its own data partition."""
    # Each client gets a different random seed → different local data
    df = generate(n_samples=n_samples, pd_prevalence=0.25, seed=42 + client_id, noise=0.45)

    train_size = int(0.8 * len(df))
    train_df   = df.iloc[:train_size]
    val_df     = df.iloc[train_size:]

    train_ds = ParkinsonsDataset(train_df)
    val_ds   = ParkinsonsDataset(val_df, fit_scaler=False)
    val_ds.ks_scaler = train_ds.ks_scaler
    val_ds.sl_scaler = train_ds.sl_scaler
    val_ds.ks_data   = train_ds.ks_scaler.transform(val_ds.ks_data).astype("float32")
    val_ds.sl_data   = train_ds.sl_scaler.transform(val_ds.sl_data).astype("float32")

    train_loader = DataLoader(train_ds, batch_size=32, shuffle=True,  num_workers=0)
    val_loader   = DataLoader(val_ds,   batch_size=32, shuffle=False, num_workers=0)

    client = NeuroGuardFLClient(
        train_loader     = train_loader,
        val_loader       = val_loader,
        local_epochs     = local_epochs,
        lr               = 1e-3,
        epsilon_per_round= 0.5,
        max_grad_norm    = 1.0,
        noise_multiplier = 1.1,
    )

    print(f"[client {client_id}] Connecting to server (n_samples={len(train_ds)})...")
    fl.client.start_client(
        server_address=f"localhost:{server_port}",
        client=client.to_client(),
    )
    print(f"[client {client_id}] Done.")


# ── Demo orchestrator ─────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rounds",        type=int, default=3)
    parser.add_argument("--clients",       type=int, default=2)
    parser.add_argument("--epochs",        type=int, default=2)
    parser.add_argument("--samples",       type=int, default=400)
    parser.add_argument("--server_port",   type=int, default=SERVER_PORT)
    args = parser.parse_args()

    # Use spawn on Windows; fork is unavailable
    ctx = multiprocessing.get_context("spawn")

    # Start server in background
    server_proc = ctx.Process(target=_run_server, args=(args.rounds, args.clients))
    server_proc.start()
    time.sleep(3)  # let server bind to port

    # Start clients
    client_procs = []
    for i in range(args.clients):
        p = ctx.Process(target=_run_client, args=(i, args.samples, args.epochs, args.server_port))
        p.start()
        client_procs.append(p)
        time.sleep(1)

    # Wait for clients
    for p in client_procs:
        p.join()

    # Server should also exit when rounds are done
    server_proc.join(timeout=30)
    if server_proc.is_alive():
        server_proc.terminate()

    print("\n[demo] Federated learning round(s) complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
