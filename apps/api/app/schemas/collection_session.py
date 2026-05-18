from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import OrmModel


class CollectionSessionStartRequest(BaseModel):
    task_id: str
    contributor_id: str
    isaac_task_name: str
    input_device: str = "quest3_handtracking"
    xr_runtime: str = "steamvr_openxr"
    streaming_stack: str = "alvr"


class CollectionSessionStartResponse(BaseModel):
    session_id: str
    status: str


class CollectionSessionCompleteRequest(BaseModel):
    runtime_metrics: dict[str, Any] = Field(default_factory=dict)


class CollectionSessionCompleteResponse(BaseModel):
    session_id: str
    status: str


class CollectionSessionRead(OrmModel):
    id: str
    task_id: str
    contributor_id: str
    isaac_task_name: str
    input_device: str
    xr_runtime: str
    streaming_stack: str
    simulator: str
    robot: str
    status: str
    started_at: datetime
    ended_at: datetime | None = None
    runtime_metrics: dict[str, Any]
