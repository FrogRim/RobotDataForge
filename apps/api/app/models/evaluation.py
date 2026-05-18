from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Evaluation(Base):
    __tablename__ = "evaluations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    episode_id: Mapped[str] = mapped_column(String(64), ForeignKey("episodes.id"), nullable=False)
    trajectory_id: Mapped[str] = mapped_column(String(64), ForeignKey("trajectories.id"), nullable=False)
    task_id: Mapped[str] = mapped_column(String(64), ForeignKey("tasks.id"), nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, default=False)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    quality_score: Mapped[float] = mapped_column(Float, default=0.0)
    novelty_score: Mapped[float] = mapped_column(Float, default=0.0)
    stability_score: Mapped[float] = mapped_column(Float, default=0.0)
    efficiency_score: Mapped[float] = mapped_column(Float, default=0.0)
    smoothness_score: Mapped[float] = mapped_column(Float, default=0.0)
    fraud_risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    task_completion_score: Mapped[float] = mapped_column(Float, default=0.0)
    interaction_quality_score: Mapped[float] = mapped_column(Float, default=0.0)
    contact_sequence_score: Mapped[float] = mapped_column(Float, default=0.0)
    physical_plausibility_score: Mapped[float] = mapped_column(Float, default=0.0)
    data_usability_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    evaluator_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    failure_mode: Mapped[str | None] = mapped_column(String(128), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String(128), nullable=True)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    human_review_label: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
