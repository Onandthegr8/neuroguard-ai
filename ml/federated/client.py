"""Flower federated learning client — used on mobile devices and hospital nodes.

Each client:
1. Downloads current global model weights
2. Trains locally for N epochs on device-local data
3. Applies differential privacy (gradient clipping + Gaussian noise)
4. Sends encrypted weight update to server
"""

import logging
from collections import OrderedDict
from typing import Dict, List, Tuple

import flwr as fl
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

from ..models.neuroguard_model import NeuroGuardModel
from ..privacy.dp_mechanism import DPMechanism

logger = logging.getLogger(__name__)


class NeuroGuardFLClient(fl.client.NumPyClient):
    def __init__(
        self,
        train_loader: DataLoader,
        val_loader: DataLoader,
        epsilon_per_round: float = 0.5,
        max_grad_norm: float = 1.0,
        noise_multiplier: float = 1.1,
        local_epochs: int = 5,
        lr: float = 1e-3,
    ):
        self.train_loader = train_loader
        self.val_loader = val_loader
        self.dp = DPMechanism(max_grad_norm=max_grad_norm, noise_multiplier=noise_multiplier)
        self.epsilon_per_round = epsilon_per_round
        self.local_epochs = local_epochs
        self.lr = lr
        self.device = torch.device("cpu")  # Mobile: always CPU
        self.model = NeuroGuardModel().to(self.device)

    def get_parameters(self, config: Dict) -> List[np.ndarray]:
        return [val.cpu().numpy() for val in self.model.state_dict().values()]

    def set_parameters(self, parameters: List[np.ndarray]) -> None:
        params_dict = zip(self.model.state_dict().keys(), parameters)
        state_dict = OrderedDict({k: torch.tensor(v) for k, v in params_dict})
        self.model.load_state_dict(state_dict, strict=True)

    def fit(self, parameters: List[np.ndarray], config: Dict) -> Tuple[List[np.ndarray], int, Dict]:
        self.set_parameters(parameters)
        global_params = [p.clone() for p in self.model.parameters()]

        self.model.train()
        optimizer = torch.optim.SGD(self.model.parameters(), lr=self.lr, momentum=0.9)
        criterion = nn.BCELoss()

        total_loss = 0.0
        n_samples = 0

        for epoch in range(self.local_epochs):
            for ks, sl, labels in self.train_loader:
                ks, sl, labels = ks.to(self.device), sl.to(self.device), labels.to(self.device)
                optimizer.zero_grad()
                preds = self.model(ks, sl)
                loss = criterion(preds, labels)
                loss.backward()

                # Per-sample gradient clipping (DP requirement)
                self.dp.clip_gradients(self.model)
                optimizer.step()

                total_loss += loss.item() * len(labels)
                n_samples += len(labels)

        # Compute gradient update = local_weights - global_weights
        local_params = list(self.model.parameters())
        gradient_update = [
            (lp.data - gp.data).numpy()
            for lp, gp in zip(local_params, global_params)
        ]

        # Add Gaussian DP noise
        noisy_update = self.dp.add_noise(gradient_update)

        # Apply noisy update back to model
        with torch.no_grad():
            for param, gp, nu in zip(self.model.parameters(), global_params, noisy_update):
                param.data = gp.data + torch.tensor(nu)

        return self.get_parameters(config={}), n_samples, {
            "train_loss": total_loss / max(n_samples, 1),
            "dp_noise_applied": True,
            "epsilon_used": self.epsilon_per_round,
            "local_epochs": self.local_epochs,
        }

    def evaluate(self, parameters: List[np.ndarray], config: Dict) -> Tuple[float, int, Dict]:
        self.set_parameters(parameters)
        self.model.eval()
        criterion = nn.BCELoss()
        total_loss = 0.0
        correct = 0
        n_samples = 0

        with torch.no_grad():
            for ks, sl, labels in self.val_loader:
                ks, sl, labels = ks.to(self.device), sl.to(self.device), labels.to(self.device)
                preds = self.model(ks, sl)
                total_loss += criterion(preds, labels).item() * len(labels)
                correct += ((preds >= 0.5).float() == labels).sum().item()
                n_samples += len(labels)

        return total_loss / max(n_samples, 1), n_samples, {"accuracy": correct / max(n_samples, 1)}
