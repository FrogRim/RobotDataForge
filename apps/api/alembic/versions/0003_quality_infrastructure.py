"""add quality infrastructure tables

Revision ID: 0003_quality_infrastructure
Revises: 0002_episode_lifecycle_metadata
Create Date: 2026-05-03
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0003_quality_infrastructure"
down_revision = "0002_episode_lifecycle_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("episodes", sa.Column("usable", sa.Boolean(), nullable=True))
    op.add_column("episodes", sa.Column("data_usability_score", sa.Float(), nullable=True))
    op.add_column("episodes", sa.Column("rejection_reasons", sa.JSON(), nullable=True))

    op.add_column("evaluations", sa.Column("task_completion_score", sa.Float(), nullable=False, server_default="0"))
    op.add_column("evaluations", sa.Column("interaction_quality_score", sa.Float(), nullable=False, server_default="0"))
    op.add_column("evaluations", sa.Column("contact_sequence_score", sa.Float(), nullable=False, server_default="0"))
    op.add_column("evaluations", sa.Column("physical_plausibility_score", sa.Float(), nullable=False, server_default="0"))
    op.add_column("evaluations", sa.Column("data_usability_score", sa.Float(), nullable=True))
    op.add_column("evaluations", sa.Column("evaluator_confidence", sa.Float(), nullable=False, server_default="0"))
    op.add_column("evaluations", sa.Column("failure_mode", sa.String(length=128), nullable=True))

    op.add_column("datasets", sa.Column("dataset_card_path", sa.String(length=1024), nullable=True))
    op.add_column("datasets", sa.Column("lerobot_metadata_path", sa.String(length=1024), nullable=True))

    op.create_table(
        "acquisition_configs",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("task_id", sa.String(length=64), sa.ForeignKey("tasks.id"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("schema_version", sa.String(length=32), nullable=False, server_default="0.1.0"),
        sa.Column("config_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "sync_metrics",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("episode_id", sa.String(length=64), sa.ForeignKey("episodes.id"), nullable=False),
        sa.Column("trajectory_id", sa.String(length=64), sa.ForeignKey("trajectories.id"), nullable=False),
        sa.Column("collection_session_id", sa.String(length=64), sa.ForeignKey("collection_sessions.id"), nullable=True),
        sa.Column("schema_version", sa.String(length=32), nullable=False, server_default="0.1.0"),
        sa.Column("quality_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("metrics_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "action_segments",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("episode_id", sa.String(length=64), sa.ForeignKey("episodes.id"), nullable=False),
        sa.Column("trajectory_id", sa.String(length=64), sa.ForeignKey("trajectories.id"), nullable=False),
        sa.Column("phase", sa.String(length=32), nullable=False, server_default="UNKNOWN"),
        sa.Column("start_frame", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("end_frame", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("source", sa.String(length=128), nullable=False, server_default="unknown"),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "data_usability_scores",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("episode_id", sa.String(length=64), sa.ForeignKey("episodes.id"), nullable=False),
        sa.Column("trajectory_id", sa.String(length=64), sa.ForeignKey("trajectories.id"), nullable=False),
        sa.Column("evaluation_id", sa.String(length=64), sa.ForeignKey("evaluations.id"), nullable=True),
        sa.Column("schema_version", sa.String(length=32), nullable=False, server_default="0.1.0"),
        sa.Column("score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("usable", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("rejection_reasons_json", sa.JSON(), nullable=False),
        sa.Column("components_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "lerobot_export_metadata",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("dataset_id", sa.String(length=64), sa.ForeignKey("datasets.id"), nullable=False),
        sa.Column("schema_version", sa.String(length=32), nullable=False, server_default="0.1.0"),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("lerobot_export_metadata")
    op.drop_table("data_usability_scores")
    op.drop_table("action_segments")
    op.drop_table("sync_metrics")
    op.drop_table("acquisition_configs")

    op.drop_column("datasets", "lerobot_metadata_path")
    op.drop_column("datasets", "dataset_card_path")

    op.drop_column("evaluations", "failure_mode")
    op.drop_column("evaluations", "evaluator_confidence")
    op.drop_column("evaluations", "data_usability_score")
    op.drop_column("evaluations", "physical_plausibility_score")
    op.drop_column("evaluations", "contact_sequence_score")
    op.drop_column("evaluations", "interaction_quality_score")
    op.drop_column("evaluations", "task_completion_score")

    op.drop_column("episodes", "rejection_reasons")
    op.drop_column("episodes", "data_usability_score")
    op.drop_column("episodes", "usable")
