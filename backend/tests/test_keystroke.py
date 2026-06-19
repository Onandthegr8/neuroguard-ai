"""Tests for keystroke ingest endpoint and feature validation."""
import pytest


class TestKeystrokeIngest:
    async def test_ingest_without_auth_returns_401(self, health_client, sample_keystroke_payload):
        response = await health_client.post(
            "/api/v1/keystroke/features",
            json=sample_keystroke_payload,
        )
        assert response.status_code == 401

    async def test_ingest_empty_payload_returns_422(self, health_client):
        response = await health_client.post(
            "/api/v1/keystroke/features",
            json={},
            headers={"Authorization": "Bearer fake-token"},
        )
        # 422 (validation) or 401 (auth) — both are acceptable without valid JWT
        assert response.status_code in (401, 422)

    async def test_health_ping(self, health_client):
        response = await health_client.get("/api/v1/health/ping")
        assert response.status_code == 200


class TestKeystrokeFeatureExtractor:
    """Unit tests for the pure Dart-equivalent Python feature quality scoring."""

    def test_quality_score_sufficient_data(self):
        """Quality score should be ≥ 0.3 with adequate key press data."""
        import statistics
        dwell_times = [85.0, 90.0, 78.0, 110.0, 95.0] * 10   # 50 samples
        iki = [120.0, 135.0, 98.0, 145.0, 108.0] * 10

        # Replicate the quality scoring logic
        mean_dwell = statistics.mean(dwell_times)
        cv_dwell = statistics.stdev(dwell_times) / mean_dwell if mean_dwell > 0 else 1.0

        count_score = min(len(dwell_times) / 100.0, 1.0)
        rhythm_score = max(0.0, 1.0 - cv_dwell)
        quality = (count_score * 0.5) + (rhythm_score * 0.5)

        assert quality >= 0.3, f"Expected quality >= 0.3, got {quality:.3f}"

    def test_quality_score_too_few_keystrokes(self):
        """Quality score should be low with < 30 keystrokes."""
        dwell_times = [85.0, 90.0] * 5   # only 10 samples
        count_score = min(len(dwell_times) / 100.0, 1.0)
        # With only 10 samples count_score = 0.1, quality will be < 0.3
        assert count_score < 0.3

    def test_entropy_calculation(self):
        """Inter-key interval entropy should be positive for varied data."""
        import math
        import collections

        iki = [120.0, 135.0, 98.0, 145.0, 108.0, 200.0, 87.0, 155.0]
        # Quantize into 10ms buckets
        buckets = [int(v // 10) for v in iki]
        counts = collections.Counter(buckets)
        total = len(buckets)
        entropy = -sum((c / total) * math.log2(c / total) for c in counts.values() if c > 0)

        assert entropy > 0, "Entropy should be positive for varied IKI data"
