from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Dataset(Base):
    __tablename__ = "datasets"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    task_id: Mapped[str] = mapped_column(String(64), ForeignKey("tasks.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(64), default="exported")
    num_episodes: Mapped[int] = mapped_column(Integer, default=0)
    num_success: Mapped[int] = mapped_column(Integer, default=0)
    num_failed: Mapped[int] = mapped_column(Integer, default=0)
    export_format: Mapped[str] = mapped_column(String(32), default="json")
    export_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    dataset_card_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    lerobot_metadata_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
