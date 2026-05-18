"""add episode lifecycle metadata

Revision ID: 0002_episode_lifecycle_metadata
Revises: 0001_initial_schema
Create Date: 2026-05-01
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0002_episode_lifecycle_metadata"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("episodes", sa.Column("finalize_reason", sa.String(length=128), nullable=True))
    op.add_column("episodes", sa.Column("failure_reason", sa.String(length=128), nullable=True))
    op.add_column("episodes", sa.Column("failure_note", sa.String(length=2048), nullable=True))
    op.add_column("episodes", sa.Column("reset_count", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("episodes", "reset_count")
    op.drop_column("episodes", "failure_note")
    op.drop_column("episodes", "failure_reason")
    op.drop_column("episodes", "finalize_reason")
