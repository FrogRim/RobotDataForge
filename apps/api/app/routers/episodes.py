from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.action_segment import ActionSegment
from app.models.data_usability_score import DataUsabilityScore
from app.models.episode import Episode
from app.models.evaluation import Evaluation
from app.models.sync_metrics import SyncMetrics
from app.models.task import Task
from app.models.trajectory import Trajectory
from app.schemas.episode import (
    EpisodeCompleteRequest,
    EpisodeCompleteResponse,
    EpisodeRead,
    EpisodeStartRequest,
    EpisodeStartResponse,
)
from app.schemas.quality import DataUsabilityScoreRead, SyncMetricsRead
from app.services.evaluator import add_evaluation_semantics, evaluate_trajectory
from app.services.segmentation import segment_actions
from app.services.storage import save_evaluation, save_trajectory
from app.services.sync import compute_sync_metrics
from app.services.usability import compute_data_usability

router = APIRouter(prefix="/api/episodes", tags=["episodes"])

EPISODE_STATUSES = {"running", "success", "failure", "reset", "incomplete"}


def _normalize_episode_status(status: str | None) -> str | None:
    if status is None:
        return None
    normalized = status.strip().lower()
    if normalized in EPISODE_STATUSES:
        return normalized
    if normalized == "recording":
        return "running"
    if normalized == "completed":
        return None
    if normalized == "invalid":
        return "incomplete"
    raise HTTPException(status_code=422, detail=f"Unsupported episode_status: {status}")


def _lifecycle_summary(
    episode: Episode,
    payload: EpisodeCompleteRequest,
    status: str,
    finalized_at: datetime,
) -> dict:
    return {
        "episode_status": status,
        "episode_started_at": episode.started_at.isoformat() if episode.started_at else None,
        "episode_finalized_at": finalized_at.isoformat(),
        "episode_finalize_reason": payload.episode_finalize_reason,
        "episode_failure_reason": payload.episode_failure_reason,
        "episode_failure_note": payload.episode_failure_note,
        "reset_count": payload.reset_count or 0,
    }


def _infer_legacy_status(payload: EpisodeCompleteRequest, evaluator_success: bool) -> str:
    summary = payload.trajectory.summary or {}
    reason = str(
        payload.episode_finalize_reason
        or summary.get("episode_finalize_reason")
        or summary.get("complete_reason")
        or ""
    ).lower()
    if reason in {"reset", "operator_reset"}:
        return "reset"
    if reason in {"closed", "sim_shutdown", "shutdown", "error", "runtime_error"}:
        return "incomplete"
    if reason in {"operator_success", "success", "auto_success_ready"}:
        return "success"
    if reason in {"operator_failure", "failure"}:
        return "failure"
    return "success" if evaluator_success else "failure"


@router.post("/start", response_model=EpisodeStartResponse)
def start_episode(payload: EpisodeStartRequest, db: Session = Depends(get_db)) -> EpisodeStartResponse:
    if db.get(Task, payload.task_id) is None:
        raise HTTPException(status_code=404, detail="Task not found")
    episode = Episode(
        id=f"episode_{uuid4().hex[:12]}",
        task_id=payload.task_id,
        contributor_id=payload.contributor_id,
        collection_session_id=payload.collection_session_id,
        status="running",
    )
    db.add(episode)
    db.commit()
    return EpisodeStartResponse(episode_id=episode.id, task_id=episode.task_id, status=episode.status)


def _finalize_episode(
    episode_id: str,
    payload: EpisodeCompleteRequest,
    db: Session = Depends(get_db),
) -> EpisodeCompleteResponse:
    episode = db.get(Episode, episode_id)
    if episode is None:
        raise HTTPException(status_code=404, detail="Episode not found")
    task = db.get(Task, episode.task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    trajectory_id = f"traj_{uuid4().hex[:12]}"
    evaluation_id = f"eval_{uuid4().hex[:12]}"
    ended_at = datetime.now(timezone.utc)
    requested_status = _normalize_episode_status(payload.episode_status)
    summary = {
        **payload.trajectory.summary,
    }
    trajectory_data = {
        "id": trajectory_id,
        "episode_id": episode.id,
        "task_id": episode.task_id,
        **payload.trajectory.model_dump(),
        "summary": summary,
    }
    task_config = {**(task.environment_config or {}), "task_type": task.task_type}
    result = evaluate_trajectory(task_config, task.success_criteria, trajectory_data)
    lifecycle_status = requested_status or _infer_legacy_status(payload, result.success)
    lifecycle_metadata = _lifecycle_summary(episode, payload, lifecycle_status, ended_at)
    summary.update(lifecycle_metadata)
    summary.setdefault("complete_reason", payload.episode_finalize_reason)
    trajectory_data["summary"] = summary

    sync_metric_values = compute_sync_metrics(trajectory_data)
    action_segments = segment_actions(trajectory_data)
    replayable = bool(payload.trajectory.frames)
    result_payload = {**result.__dict__}
    data_usability = compute_data_usability(
        trajectory_data,
        result_payload,
        sync_metric_values,
        replayable=replayable,
        episode_status=lifecycle_status,
    )
    result_payload["data_usability_score"] = data_usability["score"]
    result_metrics = {
        **result.metrics,
        "sync_metrics": sync_metric_values,
        "data_usability": data_usability,
        "action_segment_count": len(action_segments),
    }
    result_payload["metrics"] = add_evaluation_semantics(
        result_metrics,
        trajectory_data,
        success=result.success,
        failure_reason=result.failure_reason,
        failure_category=result.failure_category,
        evaluator_confidence=result.evaluator_confidence,
        data_usability=data_usability,
    )
    summary["sync_metrics"] = sync_metric_values
    summary["data_usability"] = data_usability
    summary["action_segments"] = action_segments
    trajectory_data["summary"] = summary

    trajectory_path = save_trajectory(trajectory_id, trajectory_data)
    save_evaluation(
        evaluation_id,
        {
            "id": evaluation_id,
            "trajectory_id": trajectory_id,
            "episode_id": episode.id,
            "task_id": episode.task_id,
            "evaluated_at": ended_at.isoformat(),
            **result_payload,
        },
    )

    trajectory = Trajectory(
        id=trajectory_id,
        episode_id=episode.id,
        task_id=episode.task_id,
        schema_version=payload.trajectory.schema_version,
        source=payload.trajectory.source.model_dump(),
        frames=[frame.model_dump() for frame in payload.trajectory.frames],
        summary=summary,
        storage_path=trajectory_path,
    )
    evaluation = Evaluation(
        id=evaluation_id,
        episode_id=episode.id,
        trajectory_id=trajectory_id,
        task_id=episode.task_id,
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
        data_usability_score=data_usability["score"],
        evaluator_confidence=result.evaluator_confidence,
        failure_mode=result.failure_mode,
        failure_reason=result.failure_reason,
        metrics=result_payload["metrics"],
    )
    sync_metrics = SyncMetrics(
        id=f"sync_{uuid4().hex[:12]}",
        episode_id=episode.id,
        trajectory_id=trajectory_id,
        collection_session_id=episode.collection_session_id,
        schema_version="0.1.0",
        quality_score=sync_metric_values["quality_score"],
        metrics_json=sync_metric_values,
    )
    usability_score = DataUsabilityScore(
        id=f"usable_{uuid4().hex[:12]}",
        episode_id=episode.id,
        trajectory_id=trajectory_id,
        evaluation_id=evaluation_id,
        schema_version="0.1.0",
        score=data_usability["score"],
        usable=data_usability["usable"],
        rejection_reasons_json=data_usability["rejection_reasons"],
        components_json=data_usability["components"],
    )
    segment_rows = [
        ActionSegment(
            id=f"seg_{uuid4().hex[:12]}",
            episode_id=episode.id,
            trajectory_id=trajectory_id,
            phase=segment["phase"],
            start_frame=segment["start_frame"],
            end_frame=segment["end_frame"],
            confidence=segment["confidence"],
            source=segment["source"],
            metadata_json=segment.get("metadata") or {},
        )
        for segment in action_segments
    ]

    episode.status = lifecycle_status
    episode.ended_at = ended_at
    episode.duration_sec = result.metrics.get("completion_time_sec") or summary.get("duration_sec")
    episode.trajectory_id = trajectory_id
    episode.evaluation_id = evaluation_id
    episode.accepted = result.success and lifecycle_status == "success" and bool(data_usability["usable"])
    episode.replayable = replayable
    episode.usable = bool(data_usability["usable"])
    episode.data_usability_score = data_usability["score"]
    episode.rejection_reasons = data_usability["rejection_reasons"]
    episode.finalize_reason = payload.episode_finalize_reason
    episode.failure_reason = payload.episode_failure_reason
    episode.failure_note = payload.episode_failure_note
    episode.reset_count = payload.reset_count or 0
    if lifecycle_status == "incomplete":
        episode.invalid_reason = payload.episode_failure_reason or payload.episode_finalize_reason or "incomplete"
    elif lifecycle_status == "failure":
        episode.invalid_reason = None
    elif lifecycle_status == "reset":
        episode.invalid_reason = None
    episode.human_time_per_episode = payload.unit_economics.get("human_time_per_episode")
    episode.compute_time_per_episode = payload.unit_economics.get("compute_time_per_episode")
    episode.cost_per_recorded_episode = payload.unit_economics.get("cost_per_recorded_episode")
    episode.cost_per_valid_episode = payload.unit_economics.get("cost_per_valid_episode")
    episode.cost_per_accepted_trajectory = payload.unit_economics.get("cost_per_accepted_trajectory")

    db.add_all([trajectory, evaluation, sync_metrics, usability_score, *segment_rows])
    db.commit()
    return EpisodeCompleteResponse(
        episode_id=episode.id,
        trajectory_id=trajectory_id,
        evaluation_id=evaluation_id,
        episode_status=lifecycle_status,
        episode_finalize_reason=payload.episode_finalize_reason,
        success=result.success,
        score=result.score,
    )


@router.post("/{episode_id}/complete", response_model=EpisodeCompleteResponse)
def complete_episode(
    episode_id: str,
    payload: EpisodeCompleteRequest,
    db: Session = Depends(get_db),
) -> EpisodeCompleteResponse:
    return _finalize_episode(episode_id, payload, db)


@router.post("/{episode_id}/finalize", response_model=EpisodeCompleteResponse)
def finalize_episode(
    episode_id: str,
    payload: EpisodeCompleteRequest,
    db: Session = Depends(get_db),
) -> EpisodeCompleteResponse:
    return _finalize_episode(episode_id, payload, db)


@router.get("/{episode_id}", response_model=EpisodeRead)
def get_episode(episode_id: str, db: Session = Depends(get_db)) -> Episode:
    episode = db.get(Episode, episode_id)
    if episode is None:
        raise HTTPException(status_code=404, detail="Episode not found")
    return episode


@router.get("", response_model=list[EpisodeRead])
def list_episodes(
    task_id: str | None = None,
    status: str | None = None,
    started_after: datetime | None = None,
    collection_session_id: str | None = None,
    db: Session = Depends(get_db),
) -> list[Episode]:
    query = db.query(Episode)
    if task_id:
        query = query.filter(Episode.task_id == task_id)
    if status:
        query = query.filter(Episode.status == status)
    if started_after:
        query = query.filter(Episode.started_at >= started_after)
    if collection_session_id:
        query = query.filter(Episode.collection_session_id == collection_session_id)
    return list(query.order_by(Episode.started_at.desc()).all())


@router.get("/{episode_id}/sync-metrics", response_model=SyncMetricsRead)
def get_episode_sync_metrics(episode_id: str, db: Session = Depends(get_db)) -> SyncMetrics:
    metrics = (
        db.query(SyncMetrics)
        .filter(SyncMetrics.episode_id == episode_id)
        .order_by(SyncMetrics.created_at.desc())
        .first()
    )
    if metrics is None:
        raise HTTPException(status_code=404, detail="Sync metrics not found")
    return metrics


@router.get("/{episode_id}/usability", response_model=DataUsabilityScoreRead)
def get_episode_usability(episode_id: str, db: Session = Depends(get_db)) -> DataUsabilityScore:
    usability = (
        db.query(DataUsabilityScore)
        .filter(DataUsabilityScore.episode_id == episode_id)
        .order_by(DataUsabilityScore.created_at.desc())
        .first()
    )
    if usability is None:
        raise HTTPException(status_code=404, detail="Data usability score not found")
    return usability
