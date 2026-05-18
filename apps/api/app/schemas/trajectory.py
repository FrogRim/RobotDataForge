from __future__ import annotations

from datetime import datetime
from typing import Any

from app.schemas.common import OrmModel, TrajectoryFrame, TrajectorySource


class TrajectoryRead(OrmModel):
    id: str
    episode_id: str
    task_id: str
    schema_version: str
    source: TrajectorySource
    frames: list[TrajectoryFrame]
    summary: dict[str, Any]
    storage_path: str | None = None
    created_at: datetime
