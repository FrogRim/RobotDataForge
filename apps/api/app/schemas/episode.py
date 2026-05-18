from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import OrmModel, TrajectoryFrame, TrajectorySource


class EpisodeStartRequest(BaseModel):
    task_id: str
    contributor_id: str
    collection_session_id: str | None = None


class EpisodeStartResponse(BaseModel):
    episode_id: str
    task_id: str
    status: str


class TrajectoryPayload(BaseModel):
    schema_version: str
    source: TrajectorySource
    frames: list[TrajectoryFrame]
    summary: dict[str, Any] = Field(default_factory=dict)


class EpisodeCompleteRequest(BaseModel):
    trajectory: TrajectoryPayload
    unit_economics: dict[str, Any] = Field(default_factory=dict)
    episode_status: str | None = None
    episode_finalize_reason: str | None = None
    episode_failure_reason: str | None = None
    episode_failure_note: str | None = None
    reset_count: int | None = None


class EpisodeCompleteResponse(BaseModel):
    episode_id: str
    trajectory_id: str
    evaluation_id: str
    episode_status: str
    episode_finalize_reason: str | None = None
    success: bool
    score: float


class EpisodeRead(OrmModel):
    id: str
    task_id: str
    contributor_id: str
    status: str
    started_at: datetime
    ended_at: datetime | None = None
    duration_sec: float | None = None
    trajectory_id: str | None = None
    evaluation_id: str | None = None
    accepted: bool | None = None
    replayable: bool
    usable: bool | None = None
    data_usability_score: float | None = None
    rejection_reasons: list[Any] | None = None
    invalid_reason: str | None = None
    finalize_reason: str | None = None
    failure_reason: str | None = None
    failure_note: str | None = None
    reset_count: int = 0
