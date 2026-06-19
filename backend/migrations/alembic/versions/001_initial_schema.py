"""Initial schema — all 13 tables

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-05-12
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable pgcrypto for gen_random_uuid() and field encryption
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")  # for text search

    # -----------------------------------------------------------------------
    # hospitals (no FK deps)
    # -----------------------------------------------------------------------
    op.create_table(
        "hospitals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("address", postgresql.JSONB),
        sa.Column("license_type", sa.String(50)),
        sa.Column("fl_node_enabled", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("subscription_tier", sa.String(20), nullable=False, server_default="basic"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )

    # -----------------------------------------------------------------------
    # users
    # -----------------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.Text, nullable=False, unique=True),
        sa.Column("phone", sa.String(20)),
        sa.Column("password_hash", sa.Text),
        sa.Column("auth_provider", sa.String(20), nullable=False, server_default="email"),
        sa.Column("age", sa.Integer),
        sa.Column("gender", sa.String(20)),
        sa.Column("risk_group", sa.String(20), nullable=False, server_default="general"),
        sa.Column("family_history", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
    )
    op.create_index("idx_users_email", "users", ["email"])

    # -----------------------------------------------------------------------
    # devices
    # -----------------------------------------------------------------------
    op.create_table(
        "devices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("platform", sa.String(10), nullable=False),
        sa.Column("device_model", sa.String(100)),
        sa.Column("os_version", sa.String(20)),
        sa.Column("app_version", sa.String(20)),
        sa.Column("fcm_token", sa.Text),
        sa.Column("last_active_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_devices_user_id", "devices", ["user_id"])

    # -----------------------------------------------------------------------
    # wearables
    # -----------------------------------------------------------------------
    op.create_table(
        "wearables",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("vendor", sa.String(30), nullable=False),
        sa.Column("model", sa.String(50)),
        sa.Column("access_token", sa.LargeBinary, nullable=False),
        sa.Column("refresh_token", sa.LargeBinary),
        sa.Column("token_expires_at", sa.DateTime(timezone=True)),
        sa.Column("last_synced_at", sa.DateTime(timezone=True)),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_wearables_user_id", "wearables", ["user_id"])

    # -----------------------------------------------------------------------
    # keystroke_metrics
    # -----------------------------------------------------------------------
    op.create_table(
        "keystroke_metrics",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("devices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("session_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("key_press_duration_ms", postgresql.ARRAY(sa.Float)),
        sa.Column("inter_key_interval_ms", postgresql.ARRAY(sa.Float)),
        sa.Column("typing_speed_wpm", sa.Float),
        sa.Column("correction_frequency", sa.Float),
        sa.Column("typing_entropy", sa.Float),
        sa.Column("autocorrect_rate", sa.Float),
        sa.Column("diurnal_hour", sa.Integer),
        sa.Column("quality_score", sa.Float, nullable=False, server_default="1.0"),
        sa.Column("app_context", sa.String(30)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_keystroke_user_time", "keystroke_metrics", ["user_id", "session_start"])

    # -----------------------------------------------------------------------
    # sleep_metrics
    # -----------------------------------------------------------------------
    op.create_table(
        "sleep_metrics",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("wearable_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("wearables.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sleep_date", sa.Date, nullable=False),
        sa.Column("sleep_efficiency", sa.Float),
        sa.Column("rem_duration_min", sa.Float),
        sa.Column("rem_fragmentation_idx", sa.Float),
        sa.Column("sleep_stage_transitions", sa.Integer),
        sa.Column("nocturnal_movement_idx", sa.Float),
        sa.Column("hrv_rmssd", sa.Float),
        sa.Column("resting_hr", sa.Float),
        sa.Column("total_sleep_min", sa.Float),
        sa.Column("deep_sleep_min", sa.Float),
        sa.Column("awakenings", sa.Integer),
        sa.Column("sleep_onset_min", sa.Float),
        sa.Column("raw_stages", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("user_id", "sleep_date", name="uq_sleep_user_date"),
    )
    op.create_index("idx_sleep_user_date", "sleep_metrics", ["user_id", "sleep_date"])

    # -----------------------------------------------------------------------
    # risk_predictions
    # -----------------------------------------------------------------------
    op.create_table(
        "risk_predictions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("predicted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("risk_score", sa.Float, nullable=False),
        sa.Column("risk_tier", sa.String(20), nullable=False),
        sa.Column("confidence_low", sa.Float),
        sa.Column("confidence_high", sa.Float),
        sa.Column("model_version", sa.String(20), nullable=False),
        sa.Column("shap_values", postgresql.JSONB),
        sa.Column("feature_inputs", postgresql.JSONB),
        sa.Column("keystroke_contribution", sa.Float),
        sa.Column("sleep_contribution", sa.Float),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.CheckConstraint("risk_score BETWEEN 0 AND 1", name="ck_risk_score_range"),
    )
    op.create_index("idx_risk_user_time", "risk_predictions", ["user_id", "predicted_at"])

    # -----------------------------------------------------------------------
    # clinicians (depends on hospitals, users)
    # -----------------------------------------------------------------------
    op.create_table(
        "clinicians",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("hospital_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("hospitals.id", ondelete="SET NULL")),
        sa.Column("npi_number", sa.String(20), unique=True),
        sa.Column("specialty", sa.String(50)),
        sa.Column("license_state", sa.String(5)),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_clinicians_hospital", "clinicians", ["hospital_id"])

    # -----------------------------------------------------------------------
    # alerts (depends on users, clinicians)
    # -----------------------------------------------------------------------
    op.create_table(
        "alerts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("clinician_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clinicians.id", ondelete="SET NULL")),
        sa.Column("alert_type", sa.String(50), nullable=False),
        sa.Column("severity", sa.String(10), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("metadata", postgresql.JSONB),
        sa.Column("is_read", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("delivered_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_alerts_user_id", "alerts", ["user_id"])

    # -----------------------------------------------------------------------
    # reports (depends on users, clinicians)
    # -----------------------------------------------------------------------
    op.create_table(
        "reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("clinician_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clinicians.id", ondelete="SET NULL")),
        sa.Column("report_type", sa.String(30), nullable=False),
        sa.Column("period_start", sa.Date, nullable=False),
        sa.Column("period_end", sa.Date, nullable=False),
        sa.Column("s3_key", sa.String(500), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("file_size_bytes", sa.Integer),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_reports_user_id", "reports", ["user_id"])

    # -----------------------------------------------------------------------
    # federated_nodes (depends on hospitals)
    # -----------------------------------------------------------------------
    op.create_table(
        "federated_nodes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("hospital_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("hospitals.id", ondelete="SET NULL")),
        sa.Column("node_identifier", sa.String(100), nullable=False, unique=True),
        sa.Column("public_key", sa.Text, nullable=False),
        sa.Column("current_epsilon", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("epsilon_budget", sa.Float, nullable=False, server_default="10.0"),
        sa.Column("rounds_participated", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_round_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )

    # -----------------------------------------------------------------------
    # audit_logs — HIPAA §164.312(b). Append-only enforced via GRANT.
    # -----------------------------------------------------------------------
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()"), index=True),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True)),
        sa.Column("actor_role", sa.String(30)),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True)),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("resource_type", sa.String(50), nullable=False),
        sa.Column("resource_id", sa.String(100)),
        sa.Column("ip_address", postgresql.INET),
        sa.Column("user_agent", sa.Text),
        sa.Column("outcome", sa.String(10), nullable=False),
        sa.Column("details", postgresql.JSONB),
    )
    op.create_index("idx_audit_timestamp", "audit_logs", ["timestamp"])
    op.create_index("idx_audit_patient", "audit_logs", ["patient_id"])
    # Revoke mutation rights from the app role (app only gets INSERT + SELECT)
    op.execute("REVOKE UPDATE, DELETE ON audit_logs FROM PUBLIC")

    # -----------------------------------------------------------------------
    # consent_records
    # -----------------------------------------------------------------------
    op.create_table(
        "consent_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("consent_type", sa.String(40), nullable=False),
        sa.Column("version", sa.String(10), nullable=False),
        sa.Column("granted", sa.Boolean, nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("ip_address", postgresql.INET),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("devices.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("user_id", "consent_type", "version", name="uq_consent_user_type_version"),
    )
    op.create_index("idx_consent_user_id", "consent_records", ["user_id"])


def downgrade() -> None:
    op.drop_table("consent_records")
    op.drop_table("audit_logs")
    op.drop_table("federated_nodes")
    op.drop_table("reports")
    op.drop_table("alerts")
    op.drop_table("clinicians")
    op.drop_table("risk_predictions")
    op.drop_table("sleep_metrics")
    op.drop_table("keystroke_metrics")
    op.drop_table("wearables")
    op.drop_table("devices")
    op.drop_table("users")
    op.drop_table("hospitals")
