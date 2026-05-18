from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.learning_experiment import LearningExperiment
from app.schemas.learning_experiment import LearningExperimentCreateRequest, LearningExperimentCreateResponse

router = APIRouter(prefix="/api/learning-experiments", tags=["learning-experiments"])


@router.post("", response_model=LearningExperimentCreateResponse)
def create_learning_experiment(
    payload: LearningExperimentCreateRequest,
    db: Session = Depends(get_db),
) -> LearningExperimentCreateResponse:
    experiment = LearningExperiment(id=f"experiment_{uuid4().hex[:12]}", **payload.model_dump())
    db.add(experiment)
    db.commit()
    return LearningExperimentCreateResponse(
        experiment_id=experiment.id,
        success_rate_uplift=payload.metrics.get("success_rate_uplift"),
    )
