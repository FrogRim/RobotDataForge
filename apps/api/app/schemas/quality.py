from __future__ import annotations

from datetime import datetime
from typing import Any

from app.schemas.common import OrmModel


class SyncMetricsRead(OrmModel):
    id: str
    episode_id: str
    trajectory_id: str
    collection_session_id: str | None = None
    schema_version: str
    quality_score: float
    metrics_json: dict[str, Any]
    created_at: datetime


class DataUsabilityScoreRead(OrmModel):
    id: str
    episode_id: str
    trajectory_id: str
    evaluation_id: str | None = None
    schema_version: str
    score: float
    usable: bool
    rejection_reasons_json: list[Any]
    components_json: dict[str, Any]
    created_at: datetime


class ActionSegmentRead(OrmModel):
    id: str
    episode_id: str
    trajectory_id: str
    phase: str
    start_frame: int
    end_frame: int
    confidence: float
    source: str
    metadata_json: dict[str, Any]
    created_at: datetime
