from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class TrajectorySource(BaseModel):
    input_device: str
    runtime: str
    simulator: str
    robot: str
    task_name: str


class TrajectoryFrame(BaseModel):
    t: float
    step: int
    end_effector_position: list[float] = Field(default_factory=list)
    end_effector_quaternion: list[float] = Field(default_factory=list)
    object_position: list[float] = Field(default_factory=list)
    object_quaternion: list[float] = Field(default_factory=list)
    action: dict[str, Any] = Field(default_factory=dict)
    contacts: list[Any] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Timestamped(OrmModel):
    created_at: datetime | None = None
