from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class LearningExperimentCreateRequest(BaseModel):
    task_id: str
    dataset_id: str
    experiment_type: str
    baseline_type: str
    num_train_trajectories: int
    num_eval_rollouts: int
    metrics: dict[str, Any]


class LearningExperimentCreateResponse(BaseModel):
    experiment_id: str
    success_rate_uplift: float | None = None
