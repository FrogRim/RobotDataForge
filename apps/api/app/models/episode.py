from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Episode(Base):
    __tablename__ = "episodes"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(64), ForeignKey("tasks.id"), nullable=False)
    contributor_id: Mapped[str] = mapped_column(String(128), nullable=False)
    collection_session_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("collection_sessions.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(64), default="running")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_sec: Mapped[float | None] = mapped_column(Float, nullable=True)
    trajectory_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    evaluation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    accepted: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    invalid_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    finalize_reason: Mapped[str | None] = mapped_column(String(128), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String(128), nullable=True)
    failure_note: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    reset_count: Mapped[int] = mapped_column(Integer, default=0)
    replayable: Mapped[bool] = mapped_column(Boolean, default=False)
    usable: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    data_usability_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    rejection_reasons: Mapped[list | None] = mapped_column(JSON, nullable=True)
    export_included: Mapped[bool] = mapped_column(Boolean, default=False)
    storage_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    task_difficulty: Mapped[str | None] = mapped_column(String(64), nullable=True)
    human_time_per_episode: Mapped[float | None] = mapped_column(Float, nullable=True)
    compute_time_per_episode: Mapped[float | None] = mapped_column(Float, nullable=True)
    cost_per_recorded_episode: Mapped[float | None] = mapped_column(Float, nullable=True)
    cost_per_valid_episode: Mapped[float | None] = mapped_column(Float, nullable=True)
    cost_per_accepted_trajectory: Mapped[float | None] = mapped_column(Float, nullable=True)
