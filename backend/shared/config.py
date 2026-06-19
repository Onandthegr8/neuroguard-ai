"""Central configuration via Pydantic Settings — reads from environment variables."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)

    # App
    app_env: Literal["development", "staging", "production"] = "development"
    app_version: str = "1.0.0"
    service_name: str = "neuroguard"
    debug: bool = False

    # Auth0
    auth0_domain: str = Field(default="dev.neuroguard.local", description="e.g. neuroguard.us.auth0.com")
    auth0_audience: str = "https://api.neuroguard.health"

    # Database
    database_url: PostgresDsn = Field(default="postgresql+asyncpg://neuroguard:neuroguard@postgres:5432/neuroguard", description="async+psycopg2 DSN")
    database_pool_size: int = 10
    database_max_overflow: int = 20

    # Redis
    redis_url: RedisDsn = Field(default="redis://redis:6379/0", description="redis://... DSN")
    redis_ttl_seconds: int = 3600

    # S3
    aws_region: str = "us-east-1"
    s3_bucket_models: str = "neuroguard-models"
    s3_bucket_reports: str = "neuroguard-reports"

    # Encryption
    field_encryption_key: str = Field(
        default="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",   # dev only — 32 zero-bytes base64
        description="Base64-encoded 32-byte AES key",
    )

    # JWT secret for HS256 dev mode (used when RS256 key file absent)
    jwt_secret_key: str = Field(default="dev-jwt-secret-change-in-production", description="HS256 secret for dev")

    # ML
    model_version: str = "v1.0.0"
    model_path: str = "/app/ml/models/best_model.pt"

    # JWT
    access_token_ttl: int = 900          # 15 min
    refresh_token_ttl: int = 2_592_000   # 30 days

    # Federated Learning
    fl_min_clients: int = 10
    fl_client_fraction: float = 0.2
    fl_epsilon_per_round: float = 0.5
    fl_total_epsilon_budget: float = 10.0
    fl_delta: float = 1e-5
    fl_max_grad_norm: float = 1.0
    fl_noise_multiplier: float = 1.1

    # Risk tier thresholds
    risk_tier_very_low_max: float = 0.15
    risk_tier_low_max: float = 0.30
    risk_tier_moderate_max: float = 0.55
    risk_tier_high_max: float = 0.75

    # Alert thresholds
    alert_risk_threshold: float = 0.55
    alert_rapid_progression_delta: float = 0.20
    alert_rem_anomaly_rdi: float = 0.5
    alert_keystroke_degradation_pct: float = 0.15

    # Wearable integrations
    fitbit_client_id: str = Field(default="", description="Fitbit OAuth2 client ID")
    fitbit_client_secret: str = Field(default="", description="Fitbit OAuth2 client secret")
    fitbit_redirect_uri: str = Field(
        default="https://api.neuroguard.health/api/v1/wearable/fitbit/callback",
        description="Must match Fitbit app settings",
    )

    # Notifications
    firebase_credentials_path: str = "/app/secrets/firebase.json"
    sendgrid_api_key: str = ""
    sendgrid_from_email: str = "alerts@neuroguard.health"

    # Sentry
    sentry_dsn: str = ""

    @field_validator("app_env")
    @classmethod
    def validate_env(cls, v: str) -> str:
        allowed = {"development", "staging", "production"}
        if v not in allowed:
            raise ValueError(f"app_env must be one of {allowed}")
        return v

    def risk_tier(self, score: float) -> str:
        if score < self.risk_tier_very_low_max:
            return "very_low"
        if score < self.risk_tier_low_max:
            return "low"
        if score < self.risk_tier_moderate_max:
            return "moderate"
        if score < self.risk_tier_high_max:
            return "high"
        return "very_high"


@lru_cache
def get_settings() -> Settings:
    return Settings()
