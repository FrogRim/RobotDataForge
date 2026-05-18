from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.schemas.common import OrmModel


class EvaluationCreateRequest(BaseModel):
    trajectory_id: str


class EvaluationCreateResponse(BaseModel):
    evaluation_id: str
    success: bool
    score: float
    failure_reason: str | None = None


class EvaluationRead(OrmModel):
    id: str
    episode_id: str
    trajectory_id: str
    task_id: str
    success: bool
    score: float
    quality_score: float
    novelty_score: float
    stability_score: float
    efficiency_score: float
    smoothness_score: float
    fraud_risk_score: float
    task_completion_score: float
    interaction_quality_score: float
    contact_sequence_score: float
    physical_plausibility_score: float
    data_usability_score: float | None = None
    evaluator_confidence: float
    failure_mode: str | None = None
    failure_reason: str | None = None
    metrics: dict[str, Any]
    created_at: datetime
