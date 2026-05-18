#!/usr/bin/env python3
"""Verify the latest RDF trajectory/evaluation files after a live run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_STORAGE_ROOT = Path("storage")
REQUIRED_SOURCE_FIELDS = {"input_device", "runtime", "simulator", "robot", "task_name"}
EXPECTED_LIFECYCLE_STATUSES = {"running", "success", "failure", "reset", "incomplete", "completed", "recording"}


def stable_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: top-level JSON must be an object")
    return data


def _has_frame_objects(path: Path) -> bool:
    try:
        data = load_json(path)
    except Exception:
        return False
    frames = data.get("frames")
    return isinstance(frames, list) and any(isinstance(frame, dict) for frame in frames)


def latest_file(directory: Path, *, include_empty: bool = False) -> Path | None:
    paths = sorted(directory.glob("*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return None
    if include_empty:
        return paths[-1]
    for path in reversed(paths):
        if _has_frame_objects(path):
            return path
    return paths[-1]


def _flatten_numeric(value: Any) -> list[float]:
    if value is None or isinstance(value, bool):
        return []
    if isinstance(value, (int, float)):
        return [float(value)]
    if isinstance(value, (list, tuple)):
        values: list[float] = []
        for item in value:
            values.extend(_flatten_numeric(item))
        return values
    return []


def _command_vector(value: Any) -> list[float]:
    vector = _flatten_numeric(value)
    if vector:
        return vector
    if not isinstance(value, dict):
        return []
    for key in ("command", "robot_action", "applied", "raw", "retargeted_robot_action", "action"):
        vector = _command_vector(value.get(key))
        if vector:
            return vector
    return []


def _action_command(frame: dict[str, Any], key: str) -> list[float]:
    action = frame.get("action")
    if isinstance(action, dict):
        return _command_vector(action.get(key))
    return []


def _action_sections(frame: dict[str, Any]) -> tuple[list[float], list[float], list[float]]:
    action = frame.get("action")
    if not isinstance(action, dict):
        vector = _command_vector(action)
        return vector, vector, vector
    raw = _command_vector(action.get("raw"))
    applied = _command_vector(action.get("applied"))
    retargeted = _command_vector(action.get("retargeted_robot_action"))
    if not applied:
        applied = retargeted or raw
    if not retargeted:
        retargeted = applied or raw
    return raw, applied, retargeted


def _metadata_dict(frame: dict[str, Any], key: str) -> dict[str, Any]:
    metadata = frame.get("metadata")
    if not isinstance(metadata, dict):
        return {}
    value = metadata.get(key)
    return value if isinstance(value, dict) else {}


def _frame_control_filter(frame: dict[str, Any]) -> dict[str, Any]:
    action = frame.get("action")
    if isinstance(action, dict) and isinstance(action.get("control_filter"), dict):
        return action["control_filter"]

    retargeted = _metadata_dict(frame, "retargeted")
    if isinstance(retargeted.get("control_filter"), dict):
        return retargeted["control_filter"]

    aligned = _metadata_dict(frame, "aligned_xr")
    if isinstance(aligned.get("control_filter"), dict):
        return aligned["control_filter"]

    return {}


def _frame_has_workspace_alignment_v2(frame: dict[str, Any]) -> bool:
    calibration = _metadata_dict(frame, "calibration")
    if calibration.get("type") == "workspace_alignment_v2":
        return True

    aligned = _metadata_dict(frame, "aligned_xr")
    return bool(aligned.get("calibration_valid") and aligned.get("calibration_id"))


def _timestamp_summary(frames: list[dict[str, Any]]) -> dict[str, Any]:
    timestamps: list[float] = []
    for frame in frames:
        value = frame.get("t")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            timestamps.append(float(value))
    if len(timestamps) < 2:
        return {
            "timestamp_count": len(timestamps),
            "timestamp_monotonic": True,
            "frame_interval_mean_ms": None,
            "frame_interval_jitter_ms": None,
        }
    intervals = [current - previous for previous, current in zip(timestamps, timestamps[1:])]
    mean = sum(intervals) / len(intervals)
    jitter = max(abs(interval - mean) for interval in intervals)
    return {
        "timestamp_count": len(timestamps),
        "timestamp_monotonic": all(interval >= 0.0 for interval in intervals),
        "frame_interval_mean_ms": mean * 1000.0,
        "frame_interval_jitter_ms": jitter * 1000.0,
    }


def _find_evaluation(storage_root: Path, trajectory: dict[str, Any]) -> tuple[Path | None, dict[str, Any] | None, str]:
    evaluations_dir = storage_root / "evaluations"
    trajectory_id = trajectory.get("id")
    episode_id = trajectory.get("episode_id")
    latest_unlinked: tuple[Path, dict[str, Any]] | None = None
    for path in sorted(evaluations_dir.glob("*.json"), key=lambda item: item.stat().st_mtime):
        evaluation = load_json(path)
        if trajectory_id and evaluation.get("trajectory_id") == trajectory_id:
            return path, evaluation, "trajectory_id"
        if episode_id and evaluation.get("episode_id") == episode_id:
            return path, evaluation, "episode_id"
        latest_unlinked = (path, evaluation)
    if latest_unlinked:
        return latest_unlinked[0], latest_unlinked[1], "latest_unlinked_fallback"
    return None, None, "missing"


def verify_recording(
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    trajectory_path: Path | None = None,
    *,
    allow_legacy: bool = False,
    include_empty_latest: bool = False,
) -> dict[str, Any]:
    trajectory_path = trajectory_path or latest_file(
        storage_root / "trajectories",
        include_empty=include_empty_latest,
    )
    issues: list[str] = []
    warnings: list[str] = []

    if trajectory_path is None:
        return {
            "passed": False,
            "trajectory_path": None,
            "evaluation_path": None,
            "issues": [f"No trajectory JSON files found under {storage_root / 'trajectories'}"],
            "warnings": [],
        }

    trajectory = load_json(trajectory_path)
    frames = trajectory.get("frames")
    frame_dicts = [frame for frame in frames if isinstance(frame, dict)] if isinstance(frames, list) else []
    summary = trajectory.get("summary") if isinstance(trajectory.get("summary"), dict) else {}
    source = trajectory.get("source") if isinstance(trajectory.get("source"), dict) else {}

    if not trajectory.get("schema_version"):
        issues.append("missing schema_version")
    missing_source = sorted(REQUIRED_SOURCE_FIELDS - set(source.keys()))
    if missing_source:
        issues.append(f"source missing required fields: {', '.join(missing_source)}")
    if not isinstance(frames, list):
        issues.append("frames must be a list")
    if not frame_dicts:
        issues.append("trajectory has no frame objects")

    episode_status = summary.get("episode_status")
    if episode_status not in EXPECTED_LIFECYCLE_STATUSES:
        warnings.append(f"episode_status is missing or legacy: {episode_status!r}")

    lifecycle_fields = {
        "episode_status": summary.get("episode_status"),
        "episode_started_at": summary.get("episode_started_at"),
        "episode_finalized_at": summary.get("episode_finalized_at"),
        "episode_finalize_reason": summary.get("episode_finalize_reason"),
    }
    if not lifecycle_fields["episode_status"]:
        issues.append("summary.episode_status missing")

    field_counts = {
        "raw_action": 0,
        "applied_action": 0,
        "retargeted_robot_action": 0,
        "teleop_intent": 0,
        "executed_control": 0,
        "learning_action": 0,
        "raw_xr": 0,
        "aligned_xr": 0,
        "control_filter": 0,
        "workspace_alignment_v2": 0,
        "end_effector_position": 0,
        "object_position": 0,
        "right_hand_tracked": 0,
        "xr_frame_valid": 0,
        "input_latency_ms": 0,
        "sim_fps": 0,
    }
    action_dimensions = {
        "raw_action": [],
        "applied_action": [],
        "retargeted_robot_action": [],
        "teleop_intent": [],
        "executed_control": [],
        "learning_action": [],
    }

    for frame in frame_dicts:
        raw, applied, retargeted = _action_sections(frame)
        teleop_intent = _action_command(frame, "teleop_intent")
        executed_control = _action_command(frame, "executed_control")
        learning_action = _action_command(frame, "learning_action")
        if raw:
            field_counts["raw_action"] += 1
            action_dimensions["raw_action"].append(len(raw))
        if applied:
            field_counts["applied_action"] += 1
            action_dimensions["applied_action"].append(len(applied))
        if retargeted:
            field_counts["retargeted_robot_action"] += 1
            action_dimensions["retargeted_robot_action"].append(len(retargeted))
        if teleop_intent:
            field_counts["teleop_intent"] += 1
            action_dimensions["teleop_intent"].append(len(teleop_intent))
        if executed_control:
            field_counts["executed_control"] += 1
            action_dimensions["executed_control"].append(len(executed_control))
        if learning_action:
            field_counts["learning_action"] += 1
            action_dimensions["learning_action"].append(len(learning_action))
        if _metadata_dict(frame, "raw_xr").get("right_wrist_pose"):
            field_counts["raw_xr"] += 1
        aligned = _metadata_dict(frame, "aligned_xr")
        if aligned.get("right_wrist_pose"):
            field_counts["aligned_xr"] += 1
        if _frame_control_filter(frame):
            field_counts["control_filter"] += 1
        if _frame_has_workspace_alignment_v2(frame):
            field_counts["workspace_alignment_v2"] += 1
        if frame.get("end_effector_position"):
            field_counts["end_effector_position"] += 1
        if frame.get("object_position"):
            field_counts["object_position"] += 1
        metadata = frame.get("metadata") if isinstance(frame.get("metadata"), dict) else {}
        if metadata.get("right_hand_tracked") is not None:
            field_counts["right_hand_tracked"] += 1
        if metadata.get("xr_frame_valid") is not None:
            field_counts["xr_frame_valid"] += 1
        if metadata.get("input_latency_ms") is not None:
            field_counts["input_latency_ms"] += 1
        if metadata.get("sim_fps") is not None:
            field_counts["sim_fps"] += 1

    required_frame_fields = ("raw_action", "applied_action", "retargeted_robot_action", "raw_xr", "aligned_xr")
    for key in required_frame_fields:
        if frame_dicts and field_counts[key] == 0:
            issues.append(f"{key} missing from all frames")
    for key in ("end_effector_position", "object_position"):
        if frame_dicts and field_counts[key] == 0:
            issues.append(f"{key} missing from all frames")
    for key in ("teleop_intent", "executed_control", "learning_action"):
        if frame_dicts and field_counts[key] == 0 and not allow_legacy:
            warnings.append(f"{key} missing from all frames; trajectory uses legacy action contract")
    timestamp_summary = _timestamp_summary(frame_dicts)
    if frame_dicts and timestamp_summary["timestamp_count"] != len(frame_dicts):
        issues.append("not every frame has numeric t timestamp")
    if not timestamp_summary["timestamp_monotonic"]:
        issues.append("frame timestamps are not monotonic")
    unique_action_dimensions = {
        key: sorted(set(dimensions)) for key, dimensions in action_dimensions.items()
    }
    for key, dimensions in unique_action_dimensions.items():
        if len(dimensions) > 1:
            warnings.append(f"{key} has inconsistent dimensions: {dimensions}")
    if unique_action_dimensions["applied_action"] and max(unique_action_dimensions["applied_action"]) < 4:
        warnings.append("applied_action dimension is below expected teleop command size")

    if frame_dicts and field_counts["control_filter"] == 0:
        message = "control_filter metadata missing from frames"
        if allow_legacy:
            warnings.append(message)
        else:
            issues.append(message)
    if frame_dicts and field_counts["workspace_alignment_v2"] == 0:
        message = "workspace_alignment_v2 metadata missing from frames"
        summary_calibration = summary.get("calibration") if isinstance(summary.get("calibration"), dict) else {}
        created_frame_index = summary_calibration.get("created_frame_index")
        if (
            summary_calibration.get("type") == "workspace_alignment_v2"
            and isinstance(created_frame_index, int)
            and created_frame_index >= len(frame_dicts)
        ):
            message = (
                "workspace_alignment_v2 was created after captured frames "
                f"(created_frame_index={created_frame_index}, frame_count={len(frame_dicts)}); "
                "press P earlier or increase RDF_MAX_FRAMES"
            )
        if allow_legacy:
            warnings.append(message)
        else:
            issues.append(message)

    evaluation_path, evaluation, pairing_source = _find_evaluation(storage_root, trajectory)
    evaluation_summary: dict[str, Any] = {"pairing_source": pairing_source}
    if evaluation is None:
        warnings.append("evaluation JSON could not be paired")
    else:
        if pairing_source == "latest_unlinked_fallback":
            warnings.append("evaluation paired by latest_unlinked_fallback")
        evaluation_summary.update(
            {
                "evaluation_id": evaluation.get("id"),
                "trajectory_id": evaluation.get("trajectory_id"),
                "episode_id": evaluation.get("episode_id"),
                "success": evaluation.get("success"),
                "score": evaluation.get("score"),
                "failure_reason": evaluation.get("failure_reason"),
                "metrics_available": isinstance(evaluation.get("metrics"), dict),
            }
        )

    report = {
        "schema_version": "rdf_latest_recording_verification_v0.1.0",
        "passed": not issues,
        "storage_root": str(storage_root),
        "trajectory_path": str(trajectory_path),
        "evaluation_path": str(evaluation_path) if evaluation_path else None,
        "trajectory_id": trajectory.get("id"),
        "episode_id": trajectory.get("episode_id"),
        "task_id": trajectory.get("task_id"),
        "source": source,
        "frame_count": len(frame_dicts),
        "episode_lifecycle": lifecycle_fields,
        "field_counts": field_counts,
        "action_dimensions": unique_action_dimensions,
        "timestamp_summary": timestamp_summary,
        "summary_calibration": summary.get("calibration") if isinstance(summary.get("calibration"), dict) else {},
        "summary_control_filter": summary.get("control_filter") if isinstance(summary.get("control_filter"), dict) else {},
        "evaluation": evaluation_summary,
        "issues": issues,
        "warnings": warnings,
    }
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify the latest RDF recording files.")
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--trajectory", type=Path, help="Specific trajectory JSON to verify instead of latest.")
    parser.add_argument(
        "--include-empty-latest",
        action="store_true",
        help="When selecting latest automatically, inspect the newest file even if it has zero frames.",
    )
    parser.add_argument("--allow-legacy", action="store_true", help="Treat new calibration/filter metadata gaps as warnings.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = verify_recording(
        args.storage_root,
        args.trajectory,
        allow_legacy=args.allow_legacy,
        include_empty_latest=args.include_empty_latest,
    )
    if args.pretty:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(stable_json(report))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
