"""SHAP-based explainability for NeuroGuardModel."""

from typing import Dict

import numpy as np
import torch

try:
    import shap
    _SHAP_AVAILABLE = True
except ImportError:
    _SHAP_AVAILABLE = False


class SHAPExplainer:
    """Wraps shap.GradientExplainer for NeuroGuardModel.

    Falls back to gradient-based attribution if SHAP is unavailable (mobile inference).
    """

    def __init__(self, model):
        self.model = model
        self._explainer = None

    def _get_explainer(self, ks_background: torch.Tensor, sl_background: torch.Tensor):
        if not _SHAP_AVAILABLE:
            return None
        if self._explainer is None:
            self._explainer = shap.GradientExplainer(
                self.model,
                [ks_background, sl_background],
            )
        return self._explainer

    def explain(
        self,
        ks_tensor: torch.Tensor,
        sl_tensor: torch.Tensor,
        background_size: int = 50,
    ) -> Dict[str, float]:
        from ..models.neuroguard_model import NeuroGuardModel
        feature_names = NeuroGuardModel.FEATURE_NAMES

        if not _SHAP_AVAILABLE:
            return self._gradient_attribution(ks_tensor, sl_tensor, feature_names)

        # Use zero background for fast inference (replace with training set mean in production)
        ks_bg = torch.zeros(background_size, 20)
        sl_bg = torch.zeros(background_size, 15)
        explainer = self._get_explainer(ks_bg, sl_bg)

        shap_values = explainer.shap_values([ks_tensor, sl_tensor])
        ks_shap = shap_values[0][0]
        sl_shap = shap_values[1][0]
        all_shap = np.concatenate([ks_shap, sl_shap])

        return {name: round(float(val), 6) for name, val in zip(feature_names, all_shap)}

    def _gradient_attribution(
        self,
        ks_tensor: torch.Tensor,
        sl_tensor: torch.Tensor,
        feature_names: list,
    ) -> Dict[str, float]:
        """Integrated gradients fallback."""
        ks_tensor = ks_tensor.requires_grad_(True)
        sl_tensor = sl_tensor.requires_grad_(True)
        output = self.model(ks_tensor, sl_tensor)
        output.backward(torch.ones_like(output))

        ks_grads = ks_tensor.grad.squeeze().detach().numpy()
        sl_grads = sl_tensor.grad.squeeze().detach().numpy()
        all_grads = np.concatenate([ks_grads, sl_grads])
        return {name: round(float(val), 6) for name, val in zip(feature_names, all_grads)}
