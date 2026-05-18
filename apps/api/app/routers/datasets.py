from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.dataset import Dataset
from app.models.episode import Episode
from app.models.evaluation import Evaluation
from app.models.lerobot_export_metadata import LeRobotExportMetadata
from app.models.task import Task
from app.models.trajectory import Trajectory
from app.schemas.dataset import DatasetExportRequest, DatasetExportResponse, DatasetRead
from app.services.curator import curate_episodes_with_reasons
from app.services.dataset_card import build_dataset_card
from app.services.exporter import SUPPORTED_EXPORT_FORMATS, export_dataset
from app.services.storage import save_dataset_card

router = APIRouter(prefix="/api/datasets", tags=["datasets"])


@router.post("/export", response_model=DatasetExportResponse)
def create_dataset_export(payload: DatasetExportRequest, db: Session = Depends(get_db)) -> DatasetExportResponse:
    export_format = payload.export_format.strip().lower()
    if export_format not in SUPPORTED_EXPORT_FORMATS:
        raise HTTPException(status_code=422, detail=f"Unsupported export_format: {payload.export_format}")
    task = db.get(Task, payload.task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    evaluations = db.query(Evaluation).filter(Evaluation.task_id == payload.task_id).all()
    episode_payloads = []
    for evaluation in evaluations:
        trajectory = db.get(Trajectory, evaluation.trajectory_id)
        episode = db.get(Episode, evaluation.episode_id)
        if trajectory is None or episode is None:
            continue
        episode_payloads.append({
            "episode": {
                "id": episode.id,
                "task_id": episode.task_id,
                "status": episode.status,
                "replayable": episode.replayable,
                "usable": episode.usable,
                "data_usability_score": episode.data_usability_score,
                "rejection_reasons": episode.rejection_reasons,
            },
            "trajectory": {
                "id": trajectory.id,
                "schema_version": trajectory.schema_version,
                "source": trajectory.source,
                "frames": trajectory.frames,
                "summary": trajectory.summary,
            },
            "evaluation": {
                "success": evaluation.success,
                "score": evaluation.score,
                "quality_score": evaluation.quality_score,
                "fraud_risk_score": evaluation.fraud_risk_score,
                "task_completion_score": evaluation.task_completion_score,
                "interaction_quality_score": evaluation.interaction_quality_score,
                "contact_sequence_score": evaluation.contact_sequence_score,
                "physical_plausibility_score": evaluation.physical_plausibility_score,
                "data_usability_score": evaluation.data_usability_score,
                "evaluator_confidence": evaluation.evaluator_confidence,
                "failure_mode": evaluation.failure_mode,
                "failure_reason": evaluation.failure_reason,
                "metrics": evaluation.metrics,
            },
            "data_usability": (trajectory.summary or {}).get("data_usability") or {},
        })
    curation = curate_episodes_with_reasons(episode_payloads, payload.min_quality_score)
    exported_episodes = curation["accepted"] if payload.only_success else curation["accepted"] + curation["rejected"]
    dataset_id = f"dataset_{uuid4().hex[:12]}"
    curation_rules = {
        "only_success": payload.only_success,
        "min_quality_score": payload.min_quality_score,
        "min_data_usability_score": 0.7,
        "fraud_threshold": 0.3,
        "remove_duplicates": True,
    }
    splits = {"train": 0.8, "validation": 0.1, "test": 0.1}
    dataset_card = build_dataset_card(
        dataset_id=dataset_id,
        dataset_name=payload.name,
        task={
            "description": task.description,
            "task_type": task.task_type,
            "success_criteria": task.success_criteria,
        },
        episodes=exported_episodes,
        curation_rules=curation_rules,
        splits=splits,
        export_format=export_format,
    )
    metadata = {
        "curation_rules": curation_rules,
        "rejected_episode_count": len(curation["rejected"]),
        "rejection_reasons": [
            {
                "episode_id": (item.get("episode") or {}).get("id"),
                "rejection_reasons": (item.get("curation") or {}).get("rejection_reasons", []),
            }
            for item in curation["rejected"]
        ],
        "dataset_card": dataset_card,
        "splits": splits,
    }
    export_path = export_dataset(dataset_id, payload.name, exported_episodes, export_format, metadata=metadata)
    dataset_card_path = save_dataset_card(dataset_id, dataset_card)
    num_success = sum(1 for item in exported_episodes if item["evaluation"]["success"])
    num_failed = sum(1 for item in exported_episodes if not item["evaluation"]["success"])
    dataset = Dataset(
        id=dataset_id,
        name=payload.name,
        task_id=payload.task_id,
        status="exported" if export_format == "json" else "placeholder",
        num_episodes=len(exported_episodes),
        num_success=num_success,
        num_failed=num_failed,
        export_format=export_format,
        export_path=export_path,
        dataset_card_path=dataset_card_path,
        metadata_json=metadata,
    )
    db.add(dataset)
    if export_format == "lerobot_v3":
        db.add(
            LeRobotExportMetadata(
                id=f"lerobot_{uuid4().hex[:12]}",
                dataset_id=dataset_id,
                schema_version="0.1.0",
                metadata_json={
                    "robot_type": dataset_card["robot"],
                    "fps": None,
                    "total_episodes": len(exported_episodes),
                    "total_frames": sum(len(((item.get("trajectory") or {}).get("frames") or [])) for item in exported_episodes),
                    "features": {
                        "observation.state": "robot/object state arrays when available",
                        "action": "retargeted robot action when available",
                    },
                    "splits": splits,
                    "status": "placeholder_mapping_only",
                },
            )
        )
        dataset.lerobot_metadata_path = export_path
    for item in exported_episodes:
        episode_id = (item.get("episode") or {}).get("id")
        episode = db.get(Episode, episode_id) if episode_id else None
        if episode is not None:
            episode.export_included = True
    db.commit()
    return DatasetExportResponse(
        dataset_id=dataset.id,
        status=dataset.status,
        export_path=dataset.export_path,
        dataset_card_path=dataset.dataset_card_path,
    )


@router.get("", response_model=list[DatasetRead])
def list_datasets(db: Session = Depends(get_db)) -> list[Dataset]:
    return list(db.query(Dataset).order_by(Dataset.created_at.desc()).all())


@router.get("/{dataset_id}/download")
def download_dataset(dataset_id: str, db: Session = Depends(get_db)) -> FileResponse:
    dataset = db.get(Dataset, dataset_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset not found")
    path = Path(dataset.export_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Export file not found")
    return FileResponse(path, filename=path.name, media_type="application/json")


@router.get("/{dataset_id}/card")
def get_dataset_card(dataset_id: str, db: Session = Depends(get_db)) -> dict:
    dataset = db.get(Dataset, dataset_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset not found")
    card = (dataset.metadata_json or {}).get("dataset_card")
    if not card:
        raise HTTPException(status_code=404, detail="Dataset card not found")
    return card
