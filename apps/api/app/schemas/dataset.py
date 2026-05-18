from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.schemas.common import OrmModel


class DatasetExportRequest(BaseModel):
    task_id: str
    name: str
    only_success: bool = True
    min_quality_score: float = 0.7
    export_format: str = "json"


class DatasetExportResponse(BaseModel):
    dataset_id: str
    status: str
    export_path: str
    dataset_card_path: str | None = None


class DatasetRead(OrmModel):
    id: str
    name: str
    task_id: str
    status: str
    num_episodes: int
    num_success: int
    num_failed: int
    export_format: str
    export_path: str
    dataset_card_path: str | None = None
    lerobot_metadata_path: str | None = None
    metadata_json: dict[str, Any]
    created_at: datetime
