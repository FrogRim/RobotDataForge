from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class HumanReview(Base):
    __tablename__ = "human_reviews"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    episode_id: Mapped[str] = mapped_column(String(64), ForeignKey("episodes.id"), nullable=False)
    trajectory_id: Mapped[str] = mapped_column(String(64), ForeignKey("trajectories.id"), nullable=False)
    reviewer_id: Mapped[str] = mapped_column(String(128), nullable=False)
    human_success_label: Mapped[bool] = mapped_column(Boolean, nullable=False)
    evaluator_success_label: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    agreement: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    notes: Mapped[str] = mapped_column(String(2048), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
