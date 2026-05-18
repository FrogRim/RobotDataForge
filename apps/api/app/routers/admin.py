from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.collection_session import CollectionSession
from app.models.data_usability_score import DataUsabilityScore
from app.models.episode import Episode
from app.models.evaluation import Evaluation
from app.models.human_review import HumanReview
from app.models.learning_experiment import LearningExperiment
from app.models.sync_metrics import SyncMetrics
from app.models.trajectory import Trajectory
from app.schemas.admin import AdminKpiResponse

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/kpis", response_model=AdminKpiResponse)
def get_kpis(
    task_id: str | None = None,
    collection_session_id: str | None = None,
    started_after: datetime | None = None,
    db: Session = Depends(get_db),
) -> AdminKpiResponse:
    episode_query = db.query(Episode)
    if task_id:
        episode_query = episode_query.filter(Episode.task_id == task_id)
    if collection_session_id:
        episode_query = episode_query.filter(Episode.collection_session_id == collection_session_id)
    if started_after:
        episode_query = episode_query.filter(Episode.started_at >= started_after)
    episodes = episode_query.all()
    episode_ids = {episode.id for episode in episodes}
    trajectory_ids = {episode.trajectory_id for episode in episodes if episode.trajectory_id}

    session_query = db.query(CollectionSession)
    if task_id:
        session_query = session_query.filter(CollectionSession.task_id == task_id)
    if collection_session_id:
        session_query = session_query.filter(CollectionSession.id == collection_session_id)
    sessions = session_query.all()

    evaluation_query = db.query(Evaluation)
    if task_id:
        evaluation_query = evaluation_query.filter(Evaluation.task_id == task_id)
    if episode_ids:
        evaluation_query = evaluation_query.filter(Evaluation.episode_id.in_(episode_ids))
    elif task_id or collection_session_id or started_after:
        evaluation_query = evaluation_query.filter(False)
    evaluations = evaluation_query.all()

    review_query = db.query(HumanReview)
    if episode_ids:
        review_query = review_query.filter(HumanReview.episode_id.in_(episode_ids))
    elif task_id or collection_session_id or started_after:
        review_query = review_query.filter(False)
    reviews = review_query.all()

    experiment_query = db.query(LearningExperiment)
    if task_id:
        experiment_query = experiment_query.filter(LearningExperiment.task_id == task_id)
    experiments = experiment_query.all()

    trajectory_query = db.query(Trajectory)
    if task_id:
        trajectory_query = trajectory_query.filter(Trajectory.task_id == task_id)
    if trajectory_ids:
        trajectory_query = trajectory_query.filter(Trajectory.id.in_(trajectory_ids))
    elif task_id or collection_session_id or started_after:
        trajectory_query = trajectory_query.filter(False)
    trajectories = trajectory_query.all()

    sync_query = db.query(SyncMetrics)
    if episode_ids:
        sync_query = sync_query.filter(SyncMetrics.episode_id.in_(episode_ids))
    elif task_id or collection_session_id or started_after:
        sync_query = sync_query.filter(False)
    sync_metrics = sync_query.all()

    usability_query = db.query(DataUsabilityScore)
    if episode_ids:
        usability_query = usability_query.filter(DataUsabilityScore.episode_id.in_(episode_ids))
    elif task_id or collection_session_id or started_after:
        usability_query = usability_query.filter(False)
    usability_scores = usability_query.all()

    completed = [
        episode
        for episode in episodes
        if episode.status in {"success", "failure", "reset", "completed"}
    ]
    replayable = [episode for episode in episodes if episode.replayable]
    invalid = [
        episode
        for episode in episodes
        if episode.status in {"incomplete", "invalid"} or (episode.invalid_reason and episode.status != "failure")
    ]
    successful = [evaluation for evaluation in evaluations if evaluation.success]
    accepted = [
        evaluation
        for evaluation in evaluations
        if evaluation.success and evaluation.quality_score >= 0.7 and (evaluation.data_usability_score is None or evaluation.data_usability_score >= 0.7)
    ]
    agreements = [review for review in reviews if review.agreement is not None]

    def avg(values: list[float]) -> float | None:
        return sum(values) / len(values) if values else None

    def metric_values(key: str) -> list[float]:
        values: list[float] = []
        for item in sync_metrics:
            value = (item.metrics_json or {}).get(key)
            if value is not None:
                values.append(float(value))
        return values

    def p95(values: list[float]) -> float | None:
        if not values:
            return None
        ordered = sorted(values)
        index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * 0.95)))
        return ordered[index]

    rejection_distribution: dict[str, int] = {}
    for episode in episodes:
        for reason in episode.rejection_reasons or []:
            rejection_distribution[str(reason)] = rejection_distribution.get(str(reason), 0) + 1

    frame_counts = [len(trajectory.frames or []) for trajectory in trajectories]
    sync_error_values = metric_values("sync_error_ms_mean")

    return AdminKpiResponse(
        collection={
            "recorded_episodes": len(episodes),
            "completed_episodes": len(completed),
            "invalid_episode_rate": len(invalid) / len(episodes) if episodes else 0.0,
            "average_episode_duration": avg([e.duration_sec for e in episodes if e.duration_sec is not None]),
            "frames_per_episode": avg(frame_counts),
            "replayable_trajectory_rate": len(replayable) / len(episodes) if episodes else 0.0,
        },
        xr_runtime={
            "hand_tracking_loss_rate": avg(metric_values("hand_tracking_loss_rate")) or avg([s.runtime_metrics.get("hand_tracking_loss_rate", 0.0) for s in sessions]) or 0.0,
            "frame_drop_rate": avg(metric_values("frame_drop_rate")) or avg([s.runtime_metrics.get("frame_drop_rate", 0.0) for s in sessions]) or 0.0,
            "average_input_latency_ms": avg(metric_values("average_input_latency_ms")) or avg([s.runtime_metrics.get("average_input_latency_ms", 0.0) for s in sessions]),
            "max_input_latency_ms": max(metric_values("max_input_latency_ms") or [s.runtime_metrics.get("max_input_latency_ms", 0.0) for s in sessions], default=None),
            "retargeting_error": avg([s.runtime_metrics.get("retargeting_error", 0.0) for s in sessions]),
            "session_crash_rate": sum(1 for s in sessions if s.runtime_metrics.get("session_crashed")) / len(sessions) if sessions else 0.0,
            "sync_error_ms_mean": avg(sync_error_values),
            "sync_error_ms_p95": p95(metric_values("sync_error_ms_p95") or sync_error_values),
        },
        evaluation={
            "task_success_rate": len(successful) / len(evaluations) if evaluations else 0.0,
            "evaluator_agreement_rate": sum(1 for r in agreements if r.agreement) / len(agreements) if agreements else None,
            "false_positive_rate": sum(1 for r in reviews if r.evaluator_success_label is True and r.human_success_label is False) / len(reviews) if reviews else None,
            "false_negative_rate": sum(1 for r in reviews if r.evaluator_success_label is False and r.human_success_label is True) / len(reviews) if reviews else None,
            "accepted_trajectory_rate": len(accepted) / len(evaluations) if evaluations else 0.0,
            "average_quality_score": avg([e.quality_score for e in accepted]),
            "average_data_usability_score": avg([e.data_usability_score for e in evaluations if e.data_usability_score is not None]),
        },
        learning={
            "curated_vs_uncurated_uplift": avg([e.metrics.get("success_rate_uplift", 0.0) for e in experiments]),
            "data_efficiency_gain": None,
            "learning_curve_slope": None,
            "rollout_success_rate": avg([e.metrics.get("policy_success_rate", 0.0) for e in experiments]),
            "failure_reduction_rate": None,
        },
        curation={
            "accepted_trajectory_rate": len(accepted) / len(evaluations) if evaluations else 0.0,
            "export_included_episodes": sum(1 for e in episodes if e.export_included),
            "rejection_reason_distribution": rejection_distribution,
            "average_quality_score": avg([e.quality_score for e in accepted]),
        },
        data_usability={
            "usable_trajectory_rate": sum(1 for item in usability_scores if item.usable) / len(usability_scores) if usability_scores else 0.0,
            "average_data_usability_score": avg([item.score for item in usability_scores]),
            "not_usable_count": sum(1 for item in usability_scores if not item.usable),
            "low_usability_rejection_count": rejection_distribution.get("LOW_DATA_USABILITY_SCORE", 0),
        },
    )
