"""Tests for encryption, RBAC, and HIPAA audit utilities."""
import pytest


class TestFieldEncryption:
    def test_encrypt_decrypt_roundtrip(self):
        from backend.shared.security.encryption import encrypt_field, decrypt_field

        plaintext = "sensitive-wearable-token-abc123"
        ciphertext = encrypt_field(plaintext)

        assert ciphertext != plaintext
        assert isinstance(ciphertext, bytes)

        recovered = decrypt_field(ciphertext)
        assert recovered == plaintext

    def test_different_nonce_each_encrypt(self):
        from backend.shared.security.encryption import encrypt_field

        ct1 = encrypt_field("same-plaintext")
        ct2 = encrypt_field("same-plaintext")
        # Each call uses a fresh 12-byte nonce → ciphertexts differ
        assert ct1 != ct2

    def test_tampered_ciphertext_raises(self):
        from backend.shared.security.encryption import encrypt_field, decrypt_field
        from cryptography.exceptions import InvalidTag

        ct = encrypt_field("secret")
        tampered = ct[:-3] + bytes([ct[-1] ^ 0xFF, ct[-2] ^ 0xFF, ct[-3] ^ 0xFF])

        with pytest.raises((InvalidTag, Exception)):
            decrypt_field(tampered)

    def test_empty_string_encrypts(self):
        from backend.shared.security.encryption import encrypt_field, decrypt_field

        ct = encrypt_field("")
        assert decrypt_field(ct) == ""


class TestRBAC:
    def test_role_ordering(self):
        from backend.shared.security.rbac import Role

        assert Role.USER != Role.CLINICIAN
        assert Role.HOSPITAL_ADMIN != Role.SUPER_ADMIN

    def test_all_roles_defined(self):
        from backend.shared.security.rbac import Role

        roles = [r.value for r in Role]
        assert "user" in roles
        assert "clinician" in roles
        assert "hospital_admin" in roles
        assert "super_admin" in roles


class TestRiskTierConfig:
    def test_risk_tiers_cover_full_range(self):
        from backend.shared.config import get_settings

        settings = get_settings()
        test_scores = [0.0, 0.10, 0.20, 0.40, 0.60, 0.80, 1.0]
        valid_tiers = {"very_low", "low", "moderate", "high", "very_high"}

        for score in test_scores:
            tier = settings.risk_tier(score)
            assert tier in valid_tiers, f"Score {score} → unexpected tier '{tier}'"

    def test_boundary_scores(self):
        from backend.shared.config import get_settings

        s = get_settings()
        assert s.risk_tier(0.00) == "very_low"
        assert s.risk_tier(0.14) == "very_low"
        assert s.risk_tier(0.15) == "low"
        assert s.risk_tier(0.29) == "low"
        assert s.risk_tier(0.30) == "moderate"
        assert s.risk_tier(0.54) == "moderate"
        assert s.risk_tier(0.55) == "high"
        assert s.risk_tier(0.74) == "high"
        assert s.risk_tier(0.75) == "very_high"
        assert s.risk_tier(1.00) == "very_high"
