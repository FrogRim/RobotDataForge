from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CollectionSession(Base):
    __tablename__ = "collection_sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(64), nullable=False)
    contributor_id: Mapped[str] = mapped_column(String(128), nullable=False)
    isaac_task_name: Mapped[str] = mapped_column(String(255), nullable=False)
    input_device: Mapped[str] = mapped_column(String(128), default="quest3_handtracking")
    xr_runtime: Mapped[str] = mapped_column(String(128), default="steamvr_openxr")
    streaming_stack: Mapped[str] = mapped_column(String(128), default="alvr")
    simulator: Mapped[str] = mapped_column(String(128), default="isaac_lab")
    robot: Mapped[str] = mapped_column(String(128), default="franka")
    status: Mapped[str] = mapped_column(String(64), default="recording")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    runtime_metrics: Mapped[dict] = mapped_column(JSON, default=dict)
