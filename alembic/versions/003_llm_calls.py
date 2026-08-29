"""Add llm_calls table for LLM API cost persistence

Revision ID: 003
Revises: 002
Create Date: 2026-07-22

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create llm_calls table for LLM cost persistence."""
    op.create_table(
        "llm_calls",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("model", sa.String(64), nullable=False, index=True),
        sa.Column("endpoint", sa.String(64), nullable=False, index=True),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            server_default="success",
            comment="success, error",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False, index=True),
    )

    op.create_index(
        "ix_llm_calls_model_endpoint",
        "llm_calls",
        ["model", "endpoint"],
    )
    op.create_index(
        "ix_llm_calls_created_model",
        "llm_calls",
        ["created_at", "model"],
    )


def downgrade() -> None:
    """Drop llm_calls table."""
    op.drop_index("ix_llm_calls_created_model")
    op.drop_index("ix_llm_calls_model_endpoint")
    op.drop_table("llm_calls")
