"""Tests for the NeuroGuard hybrid ML model."""
import pytest
import torch
import numpy as np


class TestNeuroGuardModel:
    @pytest.fixture
    def model(self):
        from ml.models.neuroguard_model import NeuroGuardModel
        return NeuroGuardModel()

    def test_forward_pass_shape(self, model):
        """Output should be (B, 1) with batch of 4."""
        ks = torch.randn(4, 20)
        sl = torch.randn(4, 15)
        out = model(ks, sl)
        assert out.shape == (4, 1), f"Expected (4,1), got {out.shape}"

    def test_output_in_zero_one(self, model):
        """Sigmoid output must be in [0, 1]."""
        ks = torch.randn(8, 20)
        sl = torch.randn(8, 15)
        out = model(ks, sl)
        assert (out >= 0).all() and (out <= 1).all(), "Output outside [0, 1]"

    def test_single_sample(self, model):
        """Model works with batch size of 1."""
        ks = torch.randn(1, 20)
        sl = torch.randn(1, 15)
        out = model(ks, sl)
        assert out.shape == (1, 1)
        assert 0.0 <= out.item() <= 1.0

    def test_eval_mode_deterministic(self, model):
        """In eval mode (no dropout), repeated forward passes should be equal."""
        model.eval()
        ks = torch.randn(2, 20)
        sl = torch.randn(2, 15)
        with torch.no_grad():
            out1 = model(ks, sl)
            out2 = model(ks, sl)
        assert torch.allclose(out1, out2), "Eval mode should be deterministic"

    def test_train_mode_mc_dropout_variance(self, model):
        """In train mode (dropout active), outputs should vary across samples."""
        model.train()
        ks = torch.randn(1, 20)
        sl = torch.randn(1, 15)
        outputs = [model(ks, sl).item() for _ in range(20)]
        # With dropout active there should be some variance
        assert np.std(outputs) > 0, "MC dropout should produce variance"

    def test_feature_count(self, model):
        """Model should declare exactly 35 feature names."""
        from ml.models.neuroguard_model import NeuroGuardModel
        assert len(NeuroGuardModel.FEATURE_NAMES) == 35
        assert len(NeuroGuardModel.KEYSTROKE_FEATURES) == 20
        assert len(NeuroGuardModel.SLEEP_FEATURES) == 15

    def test_predict_with_uncertainty(self, model):
        """predict_with_uncertainty should return mean + std + samples."""
        ks = torch.randn(1, 20)
        sl = torch.randn(1, 15)
        result = model.predict_with_uncertainty(ks, sl, n_samples=10)
        assert "mean" in result
        assert "std" in result
        assert "samples" in result
        assert len(result["samples"]) == 10
        assert 0.0 <= result["mean"] <= 1.0
        assert result["std"] >= 0.0

    def test_gradient_flows(self, model):
        """Backpropagation should produce non-None, non-zero gradients."""
        model.train()
        ks = torch.randn(2, 20, requires_grad=False)
        sl = torch.randn(2, 15, requires_grad=False)
        out = model(ks, sl)
        loss = out.mean()
        loss.backward()
        # Check that at least one parameter has a gradient
        has_grad = any(
            p.grad is not None and p.grad.abs().sum().item() > 0
            for p in model.parameters()
        )
        assert has_grad, "No gradients flowed through the model"


class TestDPMechanism:
    @pytest.fixture
    def dp(self):
        from ml.privacy.dp_mechanism import DPMechanism
        return DPMechanism(epsilon_per_round=0.5, delta=1e-5, max_grad_norm=1.0, noise_multiplier=1.1)

    def test_noise_applied(self, dp):
        """Adding noise should change the gradient arrays."""
        from ml.models.neuroguard_model import NeuroGuardModel
        model = NeuroGuardModel()
        grads_original = [np.random.randn(10, 10) for _ in range(3)]
        grads_noisy = dp.add_noise([g.copy() for g in grads_original])
        any_changed = any(
            not np.allclose(a, b) for a, b in zip(grads_original, grads_noisy)
        )
        assert any_changed, "Noise should change at least one gradient array"

    def test_epsilon_accumulation(self, dp):
        """Each round should increase accumulated epsilon."""
        eps1 = dp.compute_epsilon(num_rounds=1, num_samples=1000, batch_size=32)
        eps2 = dp.compute_epsilon(num_rounds=5, num_samples=1000, batch_size=32)
        assert eps2 > eps1, "More rounds should accumulate more epsilon"

    def test_clip_reduces_large_norm(self, dp):
        """Clipping should reduce gradients with norm > max_grad_norm."""
        from ml.models.neuroguard_model import NeuroGuardModel
        model = NeuroGuardModel()
        # Set all parameters to large values to ensure large norm
        with torch.no_grad():
            for p in model.parameters():
                p.grad = torch.ones_like(p) * 100.0
        norm = dp.clip_gradients(model)
        # After clipping, norm should be ≤ max_grad_norm
        assert norm <= dp.max_grad_norm + 1e-5
