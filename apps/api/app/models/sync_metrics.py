from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SyncMetrics(Base):
    __tablename__ = "sync_metrics"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    episode_id: Mapped[str] = mapped_column(String(64), ForeignKey("episodes.id"), nullable=False)
    trajectory_id: Mapped[str] = mapped_column(String(64), ForeignKey("trajectories.id"), nullable=False)
    collection_session_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("collection_sessions.id"), nullable=True)
    schema_version: Mapped[str] = mapped_column(String(32), default="0.1.0")
    quality_score: Mapped[float] = mapped_column(Float, default=0.0)
    metrics_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
