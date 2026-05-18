"""initial Robot Data Forge schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-04-30
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tasks",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=2048), nullable=False),
        sa.Column("task_type", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("environment_config", sa.JSON(), nullable=False),
        sa.Column("success_criteria", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "collection_sessions",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("task_id", sa.String(length=64), nullable=False),
        sa.Column("contributor_id", sa.String(length=128), nullable=False),
        sa.Column("isaac_task_name", sa.String(length=255), nullable=False),
        sa.Column("input_device", sa.String(length=128), nullable=False),
        sa.Column("xr_runtime", sa.String(length=128), nullable=False),
        sa.Column("streaming_stack", sa.String(length=128), nullable=False),
        sa.Column("simulator", sa.String(length=128), nullable=False),
        sa.Column("robot", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("runtime_metrics", sa.JSON(), nullable=False),
    )
    op.create_table(
        "episodes",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("task_id", sa.String(length=64), sa.ForeignKey("tasks.id"), nullable=False),
        sa.Column("contributor_id", sa.String(length=128), nullable=False),
        sa.Column("collection_session_id", sa.String(length=64), sa.ForeignKey("collection_sessions.id"), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_sec", sa.Float(), nullable=True),
        sa.Column("trajectory_id", sa.String(length=64), nullable=True),
        sa.Column("evaluation_id", sa.String(length=64), nullable=True),
        sa.Column("accepted", sa.Boolean(), nullable=True),
        sa.Column("invalid_reason", sa.String(length=255), nullable=True),
        sa.Column("replayable", sa.Boolean(), nullable=False),
        sa.Column("export_included", sa.Boolean(), nullable=False),
        sa.Column("storage_size_bytes", sa.Integer(), nullable=True),
        sa.Column("task_difficulty", sa.String(length=64), nullable=True),
        sa.Column("human_time_per_episode", sa.Float(), nullable=True),
        sa.Column("compute_time_per_episode", sa.Float(), nullable=True),
        sa.Column("cost_per_recorded_episode", sa.Float(), nullable=True),
        sa.Column("cost_per_valid_episode", sa.Float(), nullable=True),
        sa.Column("cost_per_accepted_trajectory", sa.Float(), nullable=True),
    )
    op.create_table(
        "trajectories",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("episode_id", sa.String(length=64), sa.ForeignKey("episodes.id"), nullable=False),
        sa.Column("task_id", sa.String(length=64), sa.ForeignKey("tasks.id"), nullable=False),
        sa.Column("schema_version", sa.String(length=32), nullable=False),
        sa.Column("source", sa.JSON(), nullable=False),
        sa.Column("frames", sa.JSON(), nullable=False),
        sa.Column("summary", sa.JSON(), nullable=False),
        sa.Column("storage_path", sa.String(length=1024), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "evaluations",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("episode_id", sa.String(length=64), sa.ForeignKey("episodes.id"), nullable=False),
        sa.Column("trajectory_id", sa.String(length=64), sa.ForeignKey("trajectories.id"), nullable=False),
        sa.Column("task_id", sa.String(length=64), sa.ForeignKey("tasks.id"), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("quality_score", sa.Float(), nullable=False),
        sa.Column("novelty_score", sa.Float(), nullable=False),
        sa.Column("stability_score", sa.Float(), nullable=False),
        sa.Column("efficiency_score", sa.Float(), nullable=False),
        sa.Column("smoothness_score", sa.Float(), nullable=False),
        sa.Column("fraud_risk_score", sa.Float(), nullable=False),
        sa.Column("failure_reason", sa.String(length=128), nullable=True),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("human_review_label", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "datasets",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("task_id", sa.String(length=64), sa.ForeignKey("tasks.id"), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("num_episodes", sa.Integer(), nullable=False),
        sa.Column("num_success", sa.Integer(), nullable=False),
        sa.Column("num_failed", sa.Integer(), nullable=False),
        sa.Column("export_format", sa.String(length=32), nullable=False),
        sa.Column("export_path", sa.String(length=1024), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "human_reviews",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("episode_id", sa.String(length=64), sa.ForeignKey("episodes.id"), nullable=False),
        sa.Column("trajectory_id", sa.String(length=64), sa.ForeignKey("trajectories.id"), nullable=False),
        sa.Column("reviewer_id", sa.String(length=128), nullable=False),
        sa.Column("human_success_label", sa.Boolean(), nullable=False),
        sa.Column("evaluator_success_label", sa.Boolean(), nullable=True),
        sa.Column("agreement", sa.Boolean(), nullable=True),
        sa.Column("notes", sa.String(length=2048), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "learning_experiments",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("task_id", sa.String(length=64), sa.ForeignKey("tasks.id"), nullable=False),
        sa.Column("dataset_id", sa.String(length=64), sa.ForeignKey("datasets.id"), nullable=False),
        sa.Column("experiment_type", sa.String(length=128), nullable=False),
        sa.Column("baseline_type", sa.String(length=128), nullable=False),
        sa.Column("num_train_trajectories", sa.Integer(), nullable=False),
        sa.Column("num_eval_rollouts", sa.Integer(), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("learning_experiments")
    op.drop_table("human_reviews")
    op.drop_table("datasets")
    op.drop_table("evaluations")
    op.drop_table("trajectories")
    op.drop_table("episodes")
    op.drop_table("collection_sessions")
    op.drop_table("tasks")
