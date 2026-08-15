"""Initial schema — predictions, api_keys, feedback, drift_events

Revision ID: 001
Revises:
Create Date: 2026-07-21

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all core tables."""

    # ─── Predictions ──────────────────────────────────────────
    op.create_table(
        "predictions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("transaction_id", sa.String(64), nullable=True, index=True),
        sa.Column("fraud_probability", sa.Float(), nullable=False),
        sa.Column("decision", sa.String(32), nullable=False),
        sa.Column("threshold_used", sa.Float(), nullable=False),
        sa.Column("is_fraud", sa.Boolean(), nullable=False),
        sa.Column("model_version", sa.String(64), nullable=True),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("features", JSONB().with_variant(sa.JSON(), "sqlite"), nullable=True),
        sa.Column(
            "shap_values", JSONB().with_variant(sa.JSON(), "sqlite"), nullable=True
        ),
        sa.Column("anomaly_score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, index=True),
    )

    # ─── API Keys ─────────────────────────────────────────────
    op.create_table(
        "api_keys",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("key_hash", sa.String(64), nullable=False, unique=True, index=True),
        sa.Column("role", sa.String(32), nullable=False, server_default="readonly"),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
    )

    # ─── Feedback ─────────────────────────────────────────────
    op.create_table(
        "feedback",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("prediction_id", sa.String(36), nullable=False, index=True),
        sa.Column("confirmed_fraud", sa.Boolean(), nullable=False),
        sa.Column("analyst_notes", sa.Text(), nullable=True),
        sa.Column("reviewed_by", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["prediction_id"], ["predictions.id"], ondelete="CASCADE"
        ),
    )

    # ─── Drift Events ─────────────────────────────────────────
    op.create_table(
        "drift_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("feature_name", sa.String(64), nullable=False, index=True),
        sa.Column("drift_score", sa.Float(), nullable=False),
        sa.Column("p_value", sa.Float(), nullable=True),
        sa.Column("alert_type", sa.String(32), nullable=False, server_default="drift"),
        sa.Column("window_size", sa.Integer(), nullable=True),
        sa.Column("details", JSONB().with_variant(sa.JSON(), "sqlite"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, index=True),
    )

    # ─── Indexes ──────────────────────────────────────────────
    op.create_index(
        "ix_predictions_decision_created", "predictions", ["decision", "created_at"]
    )
    op.create_index(
        "ix_feedback_prediction_created", "feedback", ["prediction_id", "created_at"]
    )
    op.create_index(
        "ix_drift_events_feature_created",
        "drift_events",
        ["feature_name", "created_at"],
    )


def downgrade() -> None:
    """Drop all core tables."""
    op.drop_table("drift_events")
    op.drop_table("feedback")
    op.drop_table("api_keys")
    op.drop_table("predictions")
