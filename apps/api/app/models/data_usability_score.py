from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DataUsabilityScore(Base):
    __tablename__ = "data_usability_scores"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    episode_id: Mapped[str] = mapped_column(String(64), ForeignKey("episodes.id"), nullable=False)
    trajectory_id: Mapped[str] = mapped_column(String(64), ForeignKey("trajectories.id"), nullable=False)
    evaluation_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("evaluations.id"), nullable=True)
    schema_version: Mapped[str] = mapped_column(String(32), default="0.1.0")
    score: Mapped[float] = mapped_column(Float, default=0.0)
    usable: Mapped[bool] = mapped_column(Boolean, default=False)
    rejection_reasons_json: Mapped[list] = mapped_column(JSON, default=list)
    components_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
