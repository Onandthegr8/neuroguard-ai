"""Add assessments table for active screening tests

Revision ID: 003_assessments
Revises: 002_row_level_security
Create Date: 2026-05-14

Active screening tests captured by the patient app / web dashboard:
  - voice_tremor
  - finger_tap
  - spiral_drawing
  - reaction_time
  - typing  (also stored here for unified history view)
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision      = "003_assessments"
down_revision = "002_row_level_security"
branch_labels = None
depends_on    = None


def upgrade() -> None:
    op.create_table(
        "assessments",
        sa.Column("id",             postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id",        postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("assessment_type", sa.String(30),                nullable=False),
        sa.Column("overall_score",  sa.Float,                      nullable=True),
        sa.Column("metrics",        postgresql.JSONB,              nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("notes",          sa.String(500),                nullable=True),
        sa.Column("created_at",     sa.DateTime(timezone=True), server_default=sa.text("NOW()"),  nullable=False),
        sa.Column("updated_at",     sa.DateTime(timezone=True), server_default=sa.text("NOW()"),  nullable=False),
    )
    op.create_index("idx_assessments_user_type",    "assessments", ["user_id", "assessment_type"])
    op.create_index("idx_assessments_user_created", "assessments", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("idx_assessments_user_created", table_name="assessments")
    op.drop_index("idx_assessments_user_type",    table_name="assessments")
    op.drop_table("assessments")
