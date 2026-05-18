from __future__ import annotations

from typing import Any

from app.services.evaluator import REQUIRED_SOURCE_FIELDS
from app.utils.scoring import clamp01


def _frames(trajectory: dict[str, Any]) -> list[dict[str, Any]]:
    frames = trajectory.get("frames") or []
    return frames if isinstance(frames, list) else []


def _has_retargeted_action(frame: dict[str, Any]) -> bool:
    action = frame.get("action")
    if isinstance(action, dict):
        if action.get("retargeted_robot_action") is not None:
            return True
        if action.get("delta_position") is not None or action.get("delta_rotation") is not None:
            return True
    metadata = frame.get("metadata") or {}
    retargeted = metadata.get("retargeted")
    return isinstance(retargeted, dict) and bool(retargeted)


def _required_modality_report(trajectory: dict[str, Any]) -> tuple[float, list[str]]:
    frames = _frames(trajectory)
    source = trajectory.get("source") or {}
    missing: list[str] = []
    if not REQUIRED_SOURCE_FIELDS.issubset(source.keys()):
        missing.extend(sorted(REQUIRED_SOURCE_FIELDS - set(source.keys())))
    if not frames:
        missing.append("frames")
        return 0.0, missing
    if not any(frame.get("end_effector_position") for frame in frames):
        missing.append("end_effector_position")
    if not any(frame.get("object_position") for frame in frames):
        missing.append("object_position")
    if not any(_has_retargeted_action(frame) for frame in frames):
        missing.append("retargeted_robot_action")
    if not any((frame.get("metadata") or {}).get("raw_xr") for frame in frames):
        missing.append("raw_xr_pose")
    if not any((frame.get("metadata") or {}).get("aligned_xr") for frame in frames):
        missing.append("aligned_xr_pose")

    hard_missing = {"frames", "end_effector_position", "object_position", "retargeted_robot_action"}
    if any(item in hard_missing for item in missing):
        return 0.0, missing
    if missing:
        return 0.75, missing
    return 1.0, missing


def compute_data_usability(
    trajectory: dict[str, Any],
    evaluation: dict[str, Any],
    sync_metrics: dict[str, Any],
    *,
    replayable: bool,
    episode_status: str | None = None,
    min_usable_score: float = 0.7,
) -> dict[str, Any]:
    modality_score, missing_modalities = _required_modality_report(trajectory)
    sync_quality_score = float(sync_metrics.get("quality_score") or 0.0)
    evaluator_confidence = float(evaluation.get("evaluator_confidence") or evaluation.get("quality_score") or 0.0)
    physical_plausibility_score = float(evaluation.get("physical_plausibility_score") or 0.0)
    replayable_score = 1.0 if replayable else 0.0

    score = clamp01(
        0.2 * replayable_score
        + 0.25 * sync_quality_score
        + 0.25 * modality_score
        + 0.15 * evaluator_confidence
        + 0.15 * physical_plausibility_score
    )

    rejection_reasons: list[str] = []
    if not replayable:
        rejection_reasons.append("NOT_REPLAYABLE")
    if episode_status == "incomplete":
        rejection_reasons.append("INCOMPLETE_EPISODE")
    for modality in missing_modalities:
        rejection_reasons.append(f"MISSING_MODALITY:{modality}")
    if sync_quality_score < 0.7:
        rejection_reasons.append("LOW_SYNC_QUALITY")
    if physical_plausibility_score < 0.5:
        rejection_reasons.append("LOW_PHYSICAL_PLAUSIBILITY")
    if evaluator_confidence < 0.5:
        rejection_reasons.append("LOW_EVALUATOR_CONFIDENCE")
    if score < min_usable_score:
        rejection_reasons.append("LOW_DATA_USABILITY_SCORE")

    return {
        "schema_version": "data_usability_v0.1.0",
        "score": score,
        "usable": score >= min_usable_score and not any(
            reason.startswith("MISSING_MODALITY:frames")
            or reason.startswith("MISSING_MODALITY:end_effector_position")
            or reason.startswith("MISSING_MODALITY:object_position")
            or reason == "NOT_REPLAYABLE"
            or reason == "INCOMPLETE_EPISODE"
            for reason in rejection_reasons
        ),
        "rejection_reasons": rejection_reasons,
        "components": {
            "replayable_score": replayable_score,
            "sync_quality_score": sync_quality_score,
            "required_modality_score": modality_score,
            "evaluator_confidence_score": evaluator_confidence,
            "physical_plausibility_score": physical_plausibility_score,
        },
        "missing_modalities": missing_modalities,
    }
