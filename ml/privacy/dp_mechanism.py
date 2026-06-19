"""Gaussian differential privacy mechanism for federated learning.

Implements gradient clipping + Gaussian noise addition per the
(ε, δ)-DP guarantee with privacy accounting.
"""

import math
from typing import List

import numpy as np


class DPMechanism:
    """
    Implements (ε, δ)-differential privacy for gradient updates.

    Privacy guarantee per round:
        σ = noise_multiplier * max_grad_norm
        Each gradient element is perturbed by N(0, σ²)

    Privacy accounting:
        Uses the moments accountant (simplified Gaussian mechanism).
        epsilon_per_round ≈ max_grad_norm / (noise_multiplier * max_grad_norm) * sqrt(2 * log(1.25/δ))
    """

    def __init__(
        self,
        max_grad_norm: float = 1.0,
        noise_multiplier: float = 1.1,
        delta: float = 1e-5,
    ):
        self.max_grad_norm = max_grad_norm
        self.noise_multiplier = noise_multiplier
        self.delta = delta
        self.sigma = noise_multiplier * max_grad_norm

    def clip_gradients(self, model) -> float:
        """Clip all parameter gradients to max_grad_norm. Returns actual norm."""
        total_norm = 0.0
        for p in model.parameters():
            if p.grad is not None:
                param_norm = p.grad.data.norm(2).item()
                total_norm += param_norm ** 2
        total_norm = total_norm ** 0.5

        clip_coef = self.max_grad_norm / (total_norm + 1e-9)
        if clip_coef < 1.0:
            for p in model.parameters():
                if p.grad is not None:
                    p.grad.data.mul_(clip_coef)
        return total_norm

    def add_noise(self, gradients: List[np.ndarray]) -> List[np.ndarray]:
        """Add Gaussian noise N(0, σ²) to each gradient tensor."""
        noisy = []
        for g in gradients:
            noise = np.random.normal(0, self.sigma, size=g.shape).astype(g.dtype)
            noisy.append(g + noise)
        return noisy

    def compute_epsilon(self, num_rounds: int, num_samples: int, batch_size: int) -> float:
        """
        Compute the accumulated epsilon after num_rounds using the simplified
        Gaussian mechanism formula:
            ε ≈ (q * sqrt(T) * sqrt(2 * log(1.25/δ))) / (σ / C)
        where q = batch_size / num_samples (sampling rate)
        """
        q = batch_size / max(num_samples, 1)
        sens_ratio = 1.0 / self.noise_multiplier  # C / sigma = 1 / noise_multiplier when C=1
        epsilon = q * math.sqrt(num_rounds) * math.sqrt(2 * math.log(1.25 / self.delta)) * sens_ratio
        return round(epsilon, 4)

    @property
    def epsilon_per_round(self) -> float:
        return round(math.sqrt(2 * math.log(1.25 / self.delta)) / self.noise_multiplier, 4)
