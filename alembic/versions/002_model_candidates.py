"""Add model_candidates table for retraining candidate management

Revision ID: 002
Revises: 001
Create Date: 2026-07-22

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create model_candidates table."""

    op.create_table(
        "model_candidates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "model_version",
            sa.String(64),
            nullable=False,
            unique=True,
            index=True,
        ),
        sa.Column(
            "trigger",
            sa.String(32),
            nullable=False,
            comment='"drift" or "feedback_volume"',
        ),
        sa.Column("trigger_detail", sa.Text(), nullable=True),
        sa.Column("pr_auc", sa.Float(), nullable=True),
        sa.Column("f1_score", sa.Float(), nullable=True),
        sa.Column("precision", sa.Float(), nullable=True),
        sa.Column("recall", sa.Float(), nullable=True),
        sa.Column("threshold", sa.Float(), nullable=True),
        sa.Column("mlflow_run_id", sa.String(64), nullable=True),
        sa.Column("model_path", sa.String(512), nullable=True),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default="candidate",
            comment="candidate, promoted, rejected",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False, index=True),
        sa.Column("evaluated_at", sa.DateTime(), nullable=True),
        sa.Column("promoted_at", sa.DateTime(), nullable=True),
    )

    op.create_index(
        "ix_model_candidates_status_created",
        "model_candidates",
        ["status", "created_at"],
    )


def downgrade() -> None:
    """Drop model_candidates table."""
    op.drop_index("ix_model_candidates_status_created")
    op.drop_table("model_candidates")
