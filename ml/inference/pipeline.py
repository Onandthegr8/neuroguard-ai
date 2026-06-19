"""Production inference pipeline: raw features → normalized → model → SHAP → risk score."""

import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
import torch

from ..models.neuroguard_model import NeuroGuardModel
from .explainer import SHAPExplainer


@dataclass
class InferenceResult:
    risk_score: float
    risk_tier: str
    confidence_low: float
    confidence_high: float
    shap_values: Dict[str, float]
    top_contributors: List[Dict]
    keystroke_contribution: float
    sleep_contribution: float
    model_version: str
    latency_ms: float


class InferencePipeline:
    """
    End-to-end inference: feature dict → InferenceResult.
    Designed for < 80ms latency on mid-range mobile (TFLite) and < 10ms server-side.
    """

    _RISK_TIERS = [
        (0.15, "very_low"),
        (0.30, "low"),
        (0.55, "moderate"),
        (0.75, "high"),
        (1.01, "very_high"),
    ]

    def __init__(self, model_path: str, model_version: str = "v1.0.0"):
        self.model_version = model_version
        self.device = torch.device("cpu")
        self.model = NeuroGuardModel()
        checkpoint = torch.load(model_path, map_location=self.device)
        if "model_state_dict" in checkpoint:
            self.model.load_state_dict(checkpoint["model_state_dict"])
        else:
            self.model.load_state_dict(checkpoint)
        self.model.eval()
        self.explainer = SHAPExplainer(self.model)

        # Load normalization stats (mean/std from training set — saved alongside model)
        import os, json
        stats_path = model_path.replace(".pt", "_norm_stats.json")
        if os.path.exists(stats_path):
            with open(stats_path) as f:
                stats = json.load(f)
            self._ks_mean = np.array(stats["keystroke_mean"], dtype=np.float32)
            self._ks_std = np.array(stats["keystroke_std"], dtype=np.float32)
            self._sl_mean = np.array(stats["sleep_mean"], dtype=np.float32)
            self._sl_std = np.array(stats["sleep_std"], dtype=np.float32)
        else:
            self._ks_mean = np.zeros(20, dtype=np.float32)
            self._ks_std = np.ones(20, dtype=np.float32)
            self._sl_mean = np.zeros(15, dtype=np.float32)
            self._sl_std = np.ones(15, dtype=np.float32)

    def predict(
        self,
        keystroke_features: Dict[str, float],
        sleep_features: Dict[str, float],
        compute_shap: bool = True,
        n_mc_samples: int = 20,
    ) -> InferenceResult:
        t0 = time.perf_counter()

        ks_vec = self._extract_keystroke_vector(keystroke_features)
        sl_vec = self._extract_sleep_vector(sleep_features)

        # Normalize
        ks_norm = (ks_vec - self._ks_mean) / (self._ks_std + 1e-9)
        sl_norm = (sl_vec - self._sl_mean) / (self._sl_std + 1e-9)

        ks_tensor = torch.tensor(ks_norm).unsqueeze(0)
        sl_tensor = torch.tensor(sl_norm).unsqueeze(0)

        # MC Dropout uncertainty
        mean, ci_low, ci_high = self.model.predict_with_uncertainty(ks_tensor, sl_tensor, n_samples=n_mc_samples)
        risk_score = float(mean.squeeze())
        confidence_low = max(0.0, float(ci_low.squeeze()))
        confidence_high = min(1.0, float(ci_high.squeeze()))

        # SHAP explanations
        shap_values: Dict[str, float] = {}
        if compute_shap:
            shap_values = self.explainer.explain(ks_tensor, sl_tensor)

        # Feature-group contributions
        ks_contrib = float(sum(v for k, v in shap_values.items() if k in NeuroGuardModel.FEATURE_NAMES[:20]))
        sl_contrib = float(sum(v for k, v in shap_values.items() if k in NeuroGuardModel.FEATURE_NAMES[20:]))

        # Top contributors
        sorted_shap = sorted(shap_values.items(), key=lambda x: abs(x[1]), reverse=True)[:5]
        total = sum(abs(v) for _, v in sorted_shap) or 1.0
        top_contributors = [
            {"feature": k, "contribution_pct": round(abs(v) / total * 100, 1),
             "direction": "increases_risk" if v > 0 else "decreases_risk"}
            for k, v in sorted_shap
        ]

        latency_ms = (time.perf_counter() - t0) * 1000
        return InferenceResult(
            risk_score=round(risk_score, 4),
            risk_tier=self._score_to_tier(risk_score),
            confidence_low=round(confidence_low, 4),
            confidence_high=round(confidence_high, 4),
            shap_values=shap_values,
            top_contributors=top_contributors,
            keystroke_contribution=round(ks_contrib, 4),
            sleep_contribution=round(sl_contrib, 4),
            model_version=self.model_version,
            latency_ms=round(latency_ms, 1),
        )

    def _extract_keystroke_vector(self, features: Dict[str, float]) -> np.ndarray:
        return np.array([features.get(k, 0.0) for k in NeuroGuardModel.FEATURE_NAMES[:20]], dtype=np.float32)

    def _extract_sleep_vector(self, features: Dict[str, float]) -> np.ndarray:
        return np.array([features.get(k, 0.0) for k in NeuroGuardModel.FEATURE_NAMES[20:]], dtype=np.float32)

    def _score_to_tier(self, score: float) -> str:
        for threshold, tier in self._RISK_TIERS:
            if score < threshold:
                return tier
        return "very_high"
