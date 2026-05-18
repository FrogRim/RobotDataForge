from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.evaluation import Evaluation
from app.models.task import Task
from app.models.trajectory import Trajectory
from app.schemas.evaluation import EvaluationCreateRequest, EvaluationCreateResponse, EvaluationRead
from app.services.evaluator import evaluate_trajectory
from app.services.storage import save_evaluation

router = APIRouter(prefix="/api/evaluations", tags=["evaluations"])


@router.post("", response_model=EvaluationCreateResponse)
def evaluate_existing_trajectory(payload: EvaluationCreateRequest, db: Session = Depends(get_db)) -> EvaluationCreateResponse:
    trajectory = db.get(Trajectory, payload.trajectory_id)
    if trajectory is None:
        raise HTTPException(status_code=404, detail="Trajectory not found")
    task = db.get(Task, trajectory.task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    trajectory_data = {
        "id": trajectory.id,
        "episode_id": trajectory.episode_id,
        "task_id": trajectory.task_id,
        "schema_version": trajectory.schema_version,
        "source": trajectory.source,
        "frames": trajectory.frames,
        "summary": trajectory.summary,
    }
    task_config = {**(task.environment_config or {}), "task_type": task.task_type}
    result = evaluate_trajectory(task_config, task.success_criteria, trajectory_data)
    evaluation_id = f"eval_{uuid4().hex[:12]}"
    evaluated_at = datetime.now(timezone.utc)
    save_evaluation(
        evaluation_id,
        {
            "id": evaluation_id,
            "trajectory_id": trajectory.id,
            "episode_id": trajectory.episode_id,
            "task_id": trajectory.task_id,
            "evaluated_at": evaluated_at.isoformat(),
            **result.__dict__,
        },
    )
    evaluation = Evaluation(
        id=evaluation_id,
        episode_id=trajectory.episode_id,
        trajectory_id=trajectory.id,
        task_id=trajectory.task_id,
        success=result.success,
        score=result.score,
        quality_score=result.quality_score,
        novelty_score=result.novelty_score,
        stability_score=result.stability_score,
        efficiency_score=result.efficiency_score,
        smoothness_score=result.smoothness_score,
        fraud_risk_score=result.fraud_risk_score,
        task_completion_score=result.task_completion_score,
        interaction_quality_score=result.interaction_quality_score,
        contact_sequence_score=result.contact_sequence_score,
        physical_plausibility_score=result.physical_plausibility_score,
        data_usability_score=result.data_usability_score,
        evaluator_confidence=result.evaluator_confidence,
        failure_mode=result.failure_mode,
        failure_reason=result.failure_reason,
        metrics=result.metrics,
    )
    db.add(evaluation)
    db.commit()
    return EvaluationCreateResponse(
        evaluation_id=evaluation_id,
        success=result.success,
        score=result.score,
        failure_reason=result.failure_reason,
    )


@router.get("/{evaluation_id}", response_model=EvaluationRead)
def get_evaluation(evaluation_id: str, db: Session = Depends(get_db)) -> Evaluation:
    evaluation = db.get(Evaluation, evaluation_id)
    if evaluation is None:
        raise HTTPException(status_code=404, detail="Evaluation not found")
    return evaluation
