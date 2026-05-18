#!/usr/bin/env python3
"""Offline RDF JSON trajectory -> HDF5 dataset converter.

The live recorder intentionally remains JSON/state-first. This script is an
offline training-export boundary that reads finished trajectory JSON files and
writes a deterministic HDF5 dataset.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any

import h5py
import numpy as np


EXPORT_SCHEMA_VERSION = "rdf-hdf5-0.1.0"
REQUIRED_SOURCE_FIELDS = {"input_device", "runtime", "simulator", "robot", "task_name"}
EXPORTABLE_STATUSES = {"success", "failure", "reset", "incomplete"}
LEGACY_INCOMPLETE_REASONS = {"closed", "sim_shutdown", "shutdown", "error", "runtime_error"}


class ExportValidationError(ValueError):
    """Raised when a trajectory JSON file cannot be converted safely."""


@dataclass(frozen=True)
class EvaluationIndex:
    by_trajectory_id: dict[str, dict[str, Any]]
    by_episode_id: dict[str, dict[str, Any]]
    unlinked: list[dict[str, Any]]


@dataclass(frozen=True)
class ExportRecord:
    trajectory_path: Path
    trajectory: dict[str, Any]
    evaluation: dict[str, Any] | None
    episode_id: str
    trajectory_id: str
    task_id: str | None
    episode_status: str
    status_inferred: bool
    status_source: str
    evaluation_link_inferred: bool = False
    evaluation_pairing_source: str = "missing"


@dataclass(frozen=True)
class ExportResult:
    output_path: Path
    exported_episode_ids: list[str]
    skipped_by_status: dict[str, int]
    warnings: list[str] = field(default_factory=list)


def stable_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ExportValidationError(f"{path}: invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ExportValidationError(f"{path}: top-level JSON must be an object")
    return data


def _as_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _flatten_numeric(value: Any) -> list[float]:
    if value is None:
        return []
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return [float(value)]
    if isinstance(value, (list, tuple)):
        values: list[float] = []
        for item in value:
            values.extend(_flatten_numeric(item))
        return values
    return []


def _nested_dict(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key)
    return value if isinstance(value, dict) else {}


def _command_vector(value: Any) -> list[float]:
    vector = _flatten_numeric(value)
    if vector:
        return vector
    if not isinstance(value, dict):
        return []
    for key in ("command", "robot_action", "action", "raw", "retargeted_robot_action"):
        vector = _command_vector(value.get(key))
        if vector:
            return vector
    relative: list[float] = []
    relative.extend(_flatten_numeric(value.get("delta_position")))
    relative.extend(_flatten_numeric(value.get("delta_rotation")))
    gripper = _as_float(value.get("gripper"))
    if gripper is not None:
        relative.append(gripper)
    return relative


def _raw_action(frame: dict[str, Any]) -> list[float]:
    action = frame.get("action")
    if isinstance(action, dict):
        raw = _command_vector(action.get("raw"))
        return raw or _command_vector(action)
    return _command_vector(action)


def _retargeted_action(frame: dict[str, Any]) -> list[float]:
    action = frame.get("action")
    if isinstance(action, dict):
        for key in ("retargeted_robot_action", "relative", "raw"):
            vector = _command_vector(action.get(key))
            if vector:
                return vector
    metadata = frame.get("metadata")
    if isinstance(metadata, dict):
        retargeted = metadata.get("retargeted")
        if isinstance(retargeted, dict):
            for key in ("robot_action", "action", "retargeted_robot_action"):
                vector = _command_vector(retargeted.get(key))
                if vector:
                    return vector
    return []


def _action_role(frame: dict[str, Any], key: str, fallback: list[float] | None = None) -> list[float]:
    action = frame.get("action")
    if isinstance(action, dict):
        vector = _command_vector(action.get(key))
        if vector:
            return vector
    return list(fallback or [])


def _pose_from_metadata(frame: dict[str, Any], section_name: str, pose_key: str = "right_wrist_pose") -> list[float]:
    metadata = frame.get("metadata")
    if not isinstance(metadata, dict):
        return []
    section = metadata.get(section_name)
    if isinstance(section, dict):
        return _flatten_numeric(section.get(pose_key))[:7]
    return []


def _safe_group_name(value: str, *, label: str) -> str:
    if not value or "/" in value or value in {".", ".."}:
        raise ExportValidationError(f"{label} is not safe as an HDF5 group name: {value!r}")
    return value


def _validate_trajectory(path: Path, trajectory: dict[str, Any]) -> None:
    if not trajectory.get("schema_version"):
        raise ExportValidationError(f"{path}: missing required field schema_version")
    source = trajectory.get("source")
    if not isinstance(source, dict):
        raise ExportValidationError(f"{path}: source must be an object")
    missing_source = sorted(REQUIRED_SOURCE_FIELDS - set(source.keys()))
    if missing_source:
        raise ExportValidationError(f"{path}: source missing required fields: {', '.join(missing_source)}")
    frames = trajectory.get("frames")
    if not isinstance(frames, list):
        raise ExportValidationError(f"{path}: frames must be a list")
    for index, frame in enumerate(frames):
        if not isinstance(frame, dict):
            raise ExportValidationError(f"{path}: frame {index} must be an object")
        if _as_float(frame.get("t")) is None:
            raise ExportValidationError(f"{path}: frame {index} missing numeric t")
        if _as_float(frame.get("step")) is None:
            raise ExportValidationError(f"{path}: frame {index} missing numeric step")


def _evaluation_index(evaluation_paths: list[Path]) -> EvaluationIndex:
    by_trajectory_id: dict[str, dict[str, Any]] = {}
    by_episode_id: dict[str, dict[str, Any]] = {}
    unlinked: list[dict[str, Any]] = []
    for path in sorted(evaluation_paths):
        evaluation = load_json(path)
        evaluation["_rdf_evaluation_path"] = str(path)
        trajectory_id = evaluation.get("trajectory_id")
        episode_id = evaluation.get("episode_id")
        if isinstance(trajectory_id, str) and trajectory_id:
            by_trajectory_id[trajectory_id] = evaluation
        elif isinstance(episode_id, str) and episode_id:
            by_episode_id[episode_id] = evaluation
        else:
            unlinked.append(evaluation)
    return EvaluationIndex(by_trajectory_id, by_episode_id, unlinked)


def _find_evaluation(
    trajectory: dict[str, Any],
    index: EvaluationIndex,
    *,
    single_unlinked_allowed: bool,
) -> tuple[dict[str, Any] | None, bool, str]:
    trajectory_id = trajectory.get("id")
    episode_id = trajectory.get("episode_id")
    if isinstance(trajectory_id, str) and trajectory_id in index.by_trajectory_id:
        return index.by_trajectory_id[trajectory_id], False, "trajectory_id"
    if isinstance(episode_id, str) and episode_id in index.by_episode_id:
        return index.by_episode_id[episode_id], False, "episode_id"
    if single_unlinked_allowed and len(index.unlinked) == 1:
        return index.unlinked[0], True, "single_unlinked_legacy"
    return None, False, "missing"


def infer_episode_status(
    trajectory: dict[str, Any],
    evaluation: dict[str, Any] | None,
) -> tuple[str, bool, str]:
    summary = trajectory.get("summary") if isinstance(trajectory.get("summary"), dict) else {}
    status = summary.get("episode_status")
    if isinstance(status, str) and status in EXPORTABLE_STATUSES:
        return status, False, "trajectory.summary.episode_status"
    if status == "running":
        return "incomplete", True, "trajectory.summary.episode_status.running"

    reason = summary.get("episode_finalize_reason") or summary.get("complete_reason")
    if isinstance(reason, str):
        normalized = reason.strip().lower()
        if normalized in {"operator_success", "success"}:
            return "success", True, "trajectory.summary.complete_reason"
        if normalized in {"operator_failure", "failure"}:
            return "failure", True, "trajectory.summary.complete_reason"
        if normalized in {"operator_reset", "reset"}:
            return "reset", True, "trajectory.summary.complete_reason"
        if normalized in LEGACY_INCOMPLETE_REASONS:
            return "incomplete", True, "trajectory.summary.complete_reason"

    if isinstance(evaluation, dict) and isinstance(evaluation.get("success"), bool):
        return ("success" if evaluation["success"] else "failure"), True, "evaluation.success"

    return "incomplete", True, "missing_lifecycle_metadata"


def collect_export_records(
    *,
    trajectories_dir: Path,
    evaluations_dir: Path | None,
    include_statuses: set[str],
) -> tuple[list[ExportRecord], dict[str, int], list[str]]:
    trajectory_paths = sorted(trajectories_dir.glob("*.json"))
    if not trajectory_paths:
        raise ExportValidationError(f"No trajectory JSON files found in {trajectories_dir}")

    evaluation_paths = sorted(evaluations_dir.glob("*.json")) if evaluations_dir and evaluations_dir.exists() else []
    evaluation_index = _evaluation_index(evaluation_paths)
    allow_single_unlinked = len(trajectory_paths) == 1
    records: list[ExportRecord] = []
    skipped: dict[str, int] = {}
    warnings: list[str] = []

    if evaluation_index.unlinked and not allow_single_unlinked:
        warnings.append(
            "Some evaluation JSON files have no trajectory_id/episode_id; "
            "they were not attached because multiple trajectories are present."
        )

    for path in trajectory_paths:
        trajectory = load_json(path)
        _validate_trajectory(path, trajectory)
        evaluation, evaluation_link_inferred, evaluation_pairing_source = _find_evaluation(
            trajectory,
            evaluation_index,
            single_unlinked_allowed=allow_single_unlinked,
        )
        status, status_inferred, status_source = infer_episode_status(trajectory, evaluation)
        if status not in include_statuses:
            skipped[status] = skipped.get(status, 0) + 1
            continue

        frames = trajectory.get("frames") or []
        if status == "success" and not frames:
            raise ExportValidationError(f"{path}: success episode has no frames")

        trajectory_id = str(trajectory.get("id") or path.stem)
        episode_id = str(trajectory.get("episode_id") or f"episode_for_{trajectory_id}")
        _safe_group_name(episode_id, label="episode_id")
        _safe_group_name(trajectory_id, label="trajectory_id")
        records.append(
            ExportRecord(
                trajectory_path=path,
                trajectory=trajectory,
                evaluation=evaluation,
                episode_id=episode_id,
                trajectory_id=trajectory_id,
                task_id=trajectory.get("task_id") if isinstance(trajectory.get("task_id"), str) else None,
                episode_status=status,
                status_inferred=status_inferred,
                status_source=status_source,
                evaluation_link_inferred=evaluation_link_inferred,
                evaluation_pairing_source=evaluation_pairing_source,
            )
        )
        if evaluation_link_inferred:
            warnings.append(
                f"{path.name}: attached the only unlinked evaluation JSON as a legacy compatibility fallback."
            )
        if evaluation is None:
            warnings.append(
                f"{path.name}: no evaluation JSON matched by trajectory_id or episode_id; "
                "evaluation metrics will be empty."
            )
        elif not isinstance(evaluation.get("metrics"), dict) or not evaluation.get("metrics"):
            warnings.append(
                f"{path.name}: matched evaluation has no metrics; optional evaluation metrics will be empty."
            )

    records.sort(key=lambda item: (item.episode_id, item.trajectory_id))
    return records, skipped, warnings


def _matrix(rows: list[list[float]], *, dtype: str = "float32") -> np.ndarray:
    width = max((len(row) for row in rows), default=0)
    data = np.full((len(rows), width), np.nan, dtype=dtype)
    for row_index, row in enumerate(rows):
        if row:
            data[row_index, : len(row)] = np.asarray(row, dtype=dtype)
    return data


def _create_matrix(group: h5py.Group, name: str, rows: list[list[float]], *, source_field: str) -> None:
    data = _matrix(rows)
    compression = {"compression": "gzip", "compression_opts": 4} if data.shape[0] and data.shape[1] else {}
    dataset = group.create_dataset(name, data=data, **compression)
    dataset.attrs["source_field"] = source_field
    dataset.attrs["width"] = dataset.shape[1] if len(dataset.shape) == 2 else 0


def _create_json_scalar(group: h5py.Group, name: str, data: Any) -> None:
    group.create_dataset(name, data=stable_json(data), dtype=h5py.string_dtype("utf-8"))


def _create_json_array(group: h5py.Group, name: str, rows: list[Any]) -> None:
    values = np.asarray([stable_json(row) for row in rows], dtype=object)
    compression = {"compression": "gzip", "compression_opts": 4} if len(values) else {}
    group.create_dataset(name, data=values, dtype=h5py.string_dtype("utf-8"), **compression)


def _write_record(h5: h5py.File, record: ExportRecord) -> None:
    trajectory = record.trajectory
    frames = trajectory.get("frames") or []
    source = trajectory.get("source") or {}
    summary = trajectory.get("summary") if isinstance(trajectory.get("summary"), dict) else {}

    episode_group = h5["episodes"].create_group(record.episode_id)
    episode_group.attrs["episode_id"] = record.episode_id
    episode_group.attrs["trajectory_id"] = record.trajectory_id
    episode_group.attrs["task_id"] = record.task_id or ""
    episode_group.attrs["episode_status"] = record.episode_status
    episode_group.attrs["episode_status_inferred"] = record.status_inferred
    episode_group.attrs["episode_status_source"] = record.status_source
    episode_group.attrs["evaluation_link_inferred"] = record.evaluation_link_inferred
    episode_group.attrs["evaluation_pairing_source"] = record.evaluation_pairing_source
    episode_group.attrs["frame_count"] = len(frames)
    episode_group.attrs["trajectory_file"] = str(record.trajectory_path)

    observations = h5["observations"].create_group(record.episode_id)
    _create_matrix(
        observations,
        "end_effector_position",
        [_flatten_numeric(frame.get("end_effector_position")) for frame in frames],
        source_field="frame.end_effector_position",
    )
    _create_matrix(
        observations,
        "end_effector_quaternion",
        [_flatten_numeric(frame.get("end_effector_quaternion")) for frame in frames],
        source_field="frame.end_effector_quaternion",
    )
    _create_matrix(
        observations,
        "object_position",
        [_flatten_numeric(frame.get("object_position")) for frame in frames],
        source_field="frame.object_position",
    )
    _create_matrix(
        observations,
        "object_quaternion",
        [_flatten_numeric(frame.get("object_quaternion")) for frame in frames],
        source_field="frame.object_quaternion",
    )
    _create_matrix(
        observations,
        "raw_xr_right_wrist_pose",
        [_pose_from_metadata(frame, "raw_xr") for frame in frames],
        source_field="frame.metadata.raw_xr.right_wrist_pose",
    )
    _create_matrix(
        observations,
        "aligned_xr_right_wrist_pose",
        [_pose_from_metadata(frame, "aligned_xr") for frame in frames],
        source_field="frame.metadata.aligned_xr.right_wrist_pose",
    )
    _create_json_array(observations, "metadata_json", [frame.get("metadata") or {} for frame in frames])

    states = h5["states"].create_group(record.episode_id)
    _create_matrix(
        states,
        "robot_end_effector_position",
        [_flatten_numeric(frame.get("end_effector_position")) for frame in frames],
        source_field="frame.end_effector_position",
    )
    _create_matrix(
        states,
        "object_position",
        [_flatten_numeric(frame.get("object_position")) for frame in frames],
        source_field="frame.object_position",
    )
    _create_json_array(states, "cube_states_json", [_nested_dict(frame.get("metadata") or {}, "cube_states") for frame in frames])

    actions = h5["actions"].create_group(record.episode_id)
    raw_action_rows = [_raw_action(frame) for frame in frames]
    retargeted_action_rows = [_retargeted_action(frame) for frame in frames]
    teleop_intent_rows = [
        _action_role(frame, "teleop_intent", raw_action_rows[index] if index < len(raw_action_rows) else [])
        for index, frame in enumerate(frames)
    ]
    executed_control_rows = [
        _action_role(
            frame,
            "executed_control",
            retargeted_action_rows[index] if index < len(retargeted_action_rows) else [],
        )
        for index, frame in enumerate(frames)
    ]
    learning_action_rows = [
        _action_role(
            frame,
            "learning_action",
            retargeted_action_rows[index] if index < len(retargeted_action_rows) else [],
        )
        for index, frame in enumerate(frames)
    ]
    _create_matrix(
        actions,
        "raw_action",
        raw_action_rows,
        source_field="frame.action.raw or frame.action",
    )
    _create_matrix(
        actions,
        "teleop_intent",
        teleop_intent_rows,
        source_field="frame.action.teleop_intent.command or frame.action.raw",
    )
    _create_matrix(
        actions,
        "executed_control",
        executed_control_rows,
        source_field="frame.action.executed_control.command or frame.action.retargeted_robot_action.command",
    )
    _create_matrix(
        actions,
        "learning_action",
        learning_action_rows,
        source_field="frame.action.learning_action.command or frame.action.retargeted_robot_action.command",
    )
    _create_matrix(
        actions,
        "retargeted_robot_action",
        retargeted_action_rows,
        source_field="frame.action.retargeted_robot_action.command or frame.metadata.retargeted.robot_action",
    )
    _create_json_array(actions, "action_json", [frame.get("action") or {} for frame in frames])

    timestamps = h5["timestamps"].create_group(record.episode_id)
    timestamp_compression = {"compression": "gzip", "compression_opts": 4} if frames else {}
    timestamps.create_dataset(
        "t",
        data=np.asarray([float(frame["t"]) for frame in frames], dtype="float64"),
        **timestamp_compression,
    )
    timestamps.create_dataset(
        "step",
        data=np.asarray([int(float(frame["step"])) for frame in frames], dtype="int64"),
        **timestamp_compression,
    )

    lifecycle = {
        "episode_status": record.episode_status,
        "episode_status_inferred": record.status_inferred,
        "episode_status_source": record.status_source,
        "episode_started_at": summary.get("episode_started_at"),
        "episode_finalized_at": summary.get("episode_finalized_at"),
        "episode_finalize_reason": summary.get("episode_finalize_reason") or summary.get("complete_reason"),
        "episode_failure_reason": summary.get("episode_failure_reason"),
        "episode_failure_note": summary.get("episode_failure_note"),
        "reset_count": summary.get("reset_count", 0),
    }
    metadata = h5["metadata"].create_group(record.episode_id)
    _create_json_scalar(metadata, "source_json", source)
    _create_json_scalar(metadata, "summary_json", summary)
    _create_json_scalar(metadata, "lifecycle_json", lifecycle)
    _create_json_scalar(metadata, "trajectory_file_json", {"path": str(record.trajectory_path)})

    evaluation_group = h5["evaluation"].create_group(record.episode_id)
    evaluation = record.evaluation or {}
    evaluation_group.attrs["evaluation_available"] = bool(record.evaluation)
    evaluation_group.attrs["evaluation_pairing_source"] = record.evaluation_pairing_source
    evaluation_group.attrs["evaluator_success"] = bool(evaluation.get("success")) if isinstance(evaluation.get("success"), bool) else False
    evaluation_group.attrs["failure_reason"] = evaluation.get("failure_reason") or ""
    for key in ("score", "quality_score", "novelty_score", "stability_score", "efficiency_score", "smoothness_score", "fraud_risk_score"):
        value = _as_float(evaluation.get(key))
        if value is not None:
            evaluation_group.attrs[key] = value
    _create_json_scalar(evaluation_group, "evaluation_json", evaluation)
    _create_json_scalar(evaluation_group, "metrics_json", evaluation.get("metrics") or {})


def export_hdf5(
    *,
    output_path: Path,
    trajectories_dir: Path,
    evaluations_dir: Path | None = None,
    include_statuses: set[str] | None = None,
) -> ExportResult:
    include_statuses = include_statuses or {"success"}
    unsupported = include_statuses - EXPORTABLE_STATUSES
    if unsupported:
        raise ExportValidationError(f"Unsupported include statuses: {', '.join(sorted(unsupported))}")

    records, skipped, warnings = collect_export_records(
        trajectories_dir=trajectories_dir,
        evaluations_dir=evaluations_dir,
        include_statuses=include_statuses,
    )
    if not records:
        raise ExportValidationError(
            "No trajectories matched the requested lifecycle filter "
            f"({', '.join(sorted(include_statuses))})."
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with h5py.File(output_path, "w") as h5:
        for group_name in ("episodes", "observations", "states", "actions", "timestamps", "metadata", "evaluation"):
            h5.create_group(group_name)
        h5.attrs["schema_version"] = EXPORT_SCHEMA_VERSION
        h5.attrs["source_format"] = "robot_data_forge_json_state_first"
        h5.attrs["include_statuses"] = stable_json(sorted(include_statuses))
        h5.attrs["episode_count"] = len(records)
        h5.attrs["skipped_by_status"] = stable_json(skipped)

        episode_ids = [record.episode_id for record in records]
        h5["episodes"].create_dataset(
            "episode_ids",
            data=np.asarray(episode_ids, dtype=object),
            dtype=h5py.string_dtype("utf-8"),
        )
        h5["episodes"].create_dataset(
            "trajectory_ids",
            data=np.asarray([record.trajectory_id for record in records], dtype=object),
            dtype=h5py.string_dtype("utf-8"),
        )

        _create_json_scalar(
            h5["metadata"],
            "dataset_json",
            {
                "schema_version": EXPORT_SCHEMA_VERSION,
                "source_format": "robot_data_forge_json_state_first",
                "include_statuses": sorted(include_statuses),
                "episode_count": len(records),
                "skipped_by_status": skipped,
                "warnings": warnings,
                "evaluation_pairing_order": ["trajectory_id", "episode_id", "single_unlinked_legacy"],
                "field_mapping": {
                    "/observations/<episode_id>/raw_xr_right_wrist_pose": "frame.metadata.raw_xr.right_wrist_pose",
                    "/observations/<episode_id>/aligned_xr_right_wrist_pose": "frame.metadata.aligned_xr.right_wrist_pose",
                    "/actions/<episode_id>/teleop_intent": "frame.action.teleop_intent.command",
                    "/actions/<episode_id>/executed_control": "frame.action.executed_control.command",
                    "/actions/<episode_id>/learning_action": "frame.action.learning_action.command",
                    "/actions/<episode_id>/retargeted_robot_action": "frame.action.retargeted_robot_action.command",
                    "/states/<episode_id>/robot_end_effector_position": "frame.end_effector_position",
                    "/timestamps/<episode_id>/t": "frame.t",
                    "/evaluation/<episode_id>/metrics_json": "evaluation.metrics",
                },
            },
        )

        for record in records:
            _write_record(h5, record)

    return ExportResult(
        output_path=output_path,
        exported_episode_ids=[record.episode_id for record in records],
        skipped_by_status=skipped,
        warnings=warnings,
    )


def _include_statuses_from_args(args: argparse.Namespace) -> set[str]:
    statuses = {"success"}
    if args.include_failure:
        statuses.add("failure")
    if args.include_reset:
        statuses.add("reset")
    if args.include_incomplete:
        statuses.add("incomplete")
    return statuses


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export RDF JSON trajectories to HDF5.")
    parser.add_argument("--storage-root", type=Path, default=Path("storage"), help="RDF storage root.")
    parser.add_argument("--trajectories-dir", type=Path, help="Directory containing trajectory JSON files.")
    parser.add_argument("--evaluations-dir", type=Path, help="Directory containing evaluation JSON files.")
    parser.add_argument("--output", type=Path, required=True, help="Output HDF5 file path.")
    parser.add_argument("--include-failure", action="store_true", help="Include lifecycle failure episodes.")
    parser.add_argument("--include-reset", action="store_true", help="Include lifecycle reset episodes.")
    parser.add_argument("--include-incomplete", action="store_true", help="Include lifecycle incomplete episodes.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    trajectories_dir = args.trajectories_dir or args.storage_root / "trajectories"
    evaluations_dir = args.evaluations_dir or args.storage_root / "evaluations"
    try:
        result = export_hdf5(
            output_path=args.output,
            trajectories_dir=trajectories_dir,
            evaluations_dir=evaluations_dir,
            include_statuses=_include_statuses_from_args(args),
        )
    except ExportValidationError as exc:
        raise SystemExit(f"export failed: {exc}") from exc
    print(
        stable_json(
            {
                "output_path": str(result.output_path),
                "exported_episode_ids": result.exported_episode_ids,
                "skipped_by_status": result.skipped_by_status,
                "warnings": result.warnings,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
