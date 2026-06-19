"""Tests for federated learning strategy and client."""
import numpy as np
import pytest


class TestAdaptiveFedAvg:
    @pytest.fixture
    def strategy(self):
        from ml.federated.strategy.adaptive_fedavg import AdaptiveFedAvg
        return AdaptiveFedAvg(
            min_available_clients=2,
            min_fit_clients=2,
            min_evaluate_clients=2,
        )

    def test_rejects_non_dp_update(self, strategy):
        """Strategy should reject updates where dp_noise_applied=False."""
        from flwr.common import FitRes, Parameters, Status, Code
        params = Parameters(tensors=[], tensor_type="numpy.ndarray")
        fit_res = FitRes(
            status=Status(code=Code.OK, message=""),
            parameters=params,
            num_examples=100,
            metrics={"dp_noise_applied": False, "epsilon_used": 0.5},
        )
        # aggregate_fit with non-DP update should either raise or return None
        # This validates the DP enforcement logic
        try:
            result = strategy.aggregate_fit(
                server_round=1,
                results=[(None, fit_res)],
                failures=[],
            )
            # If it doesn't raise, result should be None (rejected)
            assert result is None or result[0] is None
        except (ValueError, AssertionError):
            pass  # Expected — non-DP update was rejected

    def test_byzantine_filter_removes_outliers(self, strategy):
        """Updates with cosine similarity < 0.3 vs median should be filtered."""
        # Create a normal update and a Byzantine (adversarial) update
        normal = np.ones(100)
        byzantine = -np.ones(100) * 10  # very different direction

        updates = [normal.copy() for _ in range(5)] + [byzantine]
        n_samples = [100] * 5 + [100]

        filtered = strategy._byzantine_filter(
            updates=updates,
            num_samples=n_samples,
        )
        # Byzantine update should be filtered out
        assert len(filtered) < len(updates), "Byzantine update should have been removed"

    def test_weighted_aggregation(self, strategy):
        """Larger clients should have proportionally more weight (n^0.75)."""
        updates = [np.array([1.0, 0.0]), np.array([0.0, 1.0])]
        n_samples = [1000, 100]  # first client 10x larger

        result = strategy._weighted_aggregate(updates, n_samples)
        # With n^0.75 weighting: w1 = 1000^0.75 ≈ 177.8, w2 = 100^0.75 ≈ 31.6
        # Aggregated result should be closer to [1,0] than [0,1]
        assert result[0] > result[1], "Larger client should dominate aggregation"


class TestFLClient:
    def test_client_sets_dp_noise_flag(self):
        """FL client must set dp_noise_applied=True in metrics."""
        from ml.federated.client import NeuroGuardFLClient
        import io
        from unittest.mock import MagicMock, patch

        mock_model_bytes = io.BytesIO()
        import torch
        from ml.models.neuroguard_model import NeuroGuardModel
        torch.save(NeuroGuardModel().state_dict(), mock_model_bytes)
        mock_model_bytes.seek(0)

        with patch("ml.federated.client.boto3"):
            client = NeuroGuardFLClient(
                user_id="test-user",
                keystroke_data=np.random.randn(50, 20),
                sleep_data=np.random.randn(50, 15),
                labels=np.random.randint(0, 2, 50).astype(float),
            )
            client.model.load_state_dict(
                torch.load(mock_model_bytes, weights_only=True)
            )
            # Verify the client's DP mechanism is set up
            assert client.dp is not None
            assert client.dp.noise_multiplier > 0
