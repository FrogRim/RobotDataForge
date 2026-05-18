from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import OrmModel


class TaskCreate(BaseModel):
    name: str
    description: str = ""
    task_type: str
    environment_config: dict[str, Any] = Field(default_factory=dict)
    success_criteria: dict[str, Any] = Field(default_factory=dict)


class TaskSummary(OrmModel):
    id: str
    name: str
    task_type: str
    status: str


class TaskRead(TaskSummary):
    description: str
    environment_config: dict[str, Any]
    success_criteria: dict[str, Any]
    created_at: datetime
    updated_at: datetime
