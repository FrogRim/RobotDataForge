#!/usr/bin/env python3
"""Analyze RDF teleop calibration/action-filter data from trajectory JSON files."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Any


DEFAULT_STORAGE_ROOT = Path("storage")
ACTION_EPSILON = 1e-9
POSITION_ZERO_EPSILON = 1e-6


@dataclass(frozen=True)
class NumericSeriesStats:
    count: int
    dimension: int
    norm_mean: float | None
    norm_max: float | None
    zero_ratio: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "count": self.count,
            "dimension": self.dimension,
            "norm_mean": self.norm_mean,
            "norm_max": self.norm_max,
            "zero_ratio": self.zero_ratio,
        }


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


def latest_trajectory_path(storage_root: Path, *, include_empty: bool = False) -> Path:
    trajectories_dir = storage_root / "trajectories"
    paths = sorted(trajectories_dir.glob("*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        raise FileNotFoundError(f"No trajectory JSON files found in {trajectories_dir}")
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
    for key in ("command", "robot_action", "action", "applied", "raw", "retargeted_robot_action"):
        vector = _command_vector(value.get(key))
        if vector:
            return vector
    relative: list[float] = []
    relative.extend(_flatten_numeric(value.get("delta_position")))
    relative.extend(_flatten_numeric(value.get("delta_rotation")))
    gripper = value.get("gripper")
    if isinstance(gripper, (int, float)) and not isinstance(gripper, bool):
        relative.append(float(gripper))
    return relative


def raw_action(frame: dict[str, Any]) -> list[float]:
    action = frame.get("action")
    if isinstance(action, dict):
        raw = _command_vector(action.get("raw"))
        return raw or _command_vector(action)
    return _command_vector(action)


def applied_action(frame: dict[str, Any]) -> list[float]:
    action = frame.get("action")
    if isinstance(action, dict):
        applied = _command_vector(action.get("applied"))
        if applied:
            return applied
        retargeted = _command_vector(action.get("retargeted_robot_action"))
        if retargeted:
            return retargeted
    metadata = frame.get("metadata")
    if isinstance(metadata, dict):
        retargeted_meta = metadata.get("retargeted")
        if isinstance(retargeted_meta, dict):
            applied = _command_vector(retargeted_meta.get("robot_action"))
            if applied:
                return applied
    return raw_action(frame)


def control_filter_metadata(frame: dict[str, Any]) -> dict[str, Any]:
    action = frame.get("action")
    if isinstance(action, dict) and isinstance(action.get("control_filter"), dict):
        return action["control_filter"]
    metadata = frame.get("metadata")
    if isinstance(metadata, dict):
        aligned = metadata.get("aligned_xr")
        if isinstance(aligned, dict) and isinstance(aligned.get("control_filter"), dict):
            return aligned["control_filter"]
        retargeted = metadata.get("retargeted")
        if isinstance(retargeted, dict) and isinstance(retargeted.get("control_filter"), dict):
            return retargeted["control_filter"]
    return {}


def _vector_norm(values: list[float]) -> float:
    return math.sqrt(sum(value * value for value in values))


def _pad(vector: list[float], width: int) -> list[float]:
    return vector + [0.0] * max(0, width - len(vector))


def series_stats(vectors: list[list[float]]) -> NumericSeriesStats:
    if not vectors:
        return NumericSeriesStats(count=0, dimension=0, norm_mean=None, norm_max=None, zero_ratio=None)
    width = max(len(vector) for vector in vectors)
    norms = [_vector_norm(_pad(vector, width)) for vector in vectors]
    return NumericSeriesStats(
        count=len(vectors),
        dimension=width,
        norm_mean=sum(norms) / len(norms),
        norm_max=max(norms),
        zero_ratio=sum(1 for norm in norms if norm <= ACTION_EPSILON) / len(norms),
    )


def jump_stats(vectors: list[list[float]]) -> dict[str, Any]:
    if len(vectors) < 2:
        return {"count": 0, "mean": None, "max": None, "stddev": None}
    width = max(len(vector) for vector in vectors)
    jumps = [
        _vector_norm([b - a for a, b in zip(_pad(previous, width), _pad(current, width))])
        for previous, current in zip(vectors, vectors[1:])
    ]
    mean = sum(jumps) / len(jumps)
    variance = sum((jump - mean) ** 2 for jump in jumps) / len(jumps)
    return {
        "count": len(jumps),
        "mean": mean,
        "max": max(jumps),
        "stddev": math.sqrt(variance),
    }


def axis_stats(vectors: list[list[float]], start: int, labels: tuple[str, str, str]) -> dict[str, Any]:
    rows = [_pad(vector, start + 3)[start : start + 3] for vector in vectors if len(vector) > start]
    if not rows:
        return {"count": 0, "dominant_axis": None, "axes": {}}
    axes: dict[str, dict[str, float]] = {}
    max_abs_by_axis: dict[str, float] = {}
    for axis_index, label in enumerate(labels):
        values = [row[axis_index] for row in rows]
        abs_values = [abs(value) for value in values]
        max_abs = max(abs_values)
        max_abs_by_axis[label] = max_abs
        axes[label] = {
            "mean": sum(values) / len(values),
            "mean_abs": sum(abs_values) / len(abs_values),
            "max_abs": max_abs,
        }
    dominant_axis = max(max_abs_by_axis, key=max_abs_by_axis.get)
    return {"count": len(rows), "dominant_axis": dominant_axis, "axes": axes}


def raw_applied_delta_stats(raw_vectors: list[list[float]], applied_vectors: list[list[float]]) -> dict[str, Any]:
    if not raw_vectors or not applied_vectors:
        return {"count": 0, "mean": None, "max": None}
    count = min(len(raw_vectors), len(applied_vectors))
    width = max(max(len(vector) for vector in raw_vectors[:count]), max(len(vector) for vector in applied_vectors[:count]))
    deltas = [
        _vector_norm([applied - raw for raw, applied in zip(_pad(raw_vectors[index], width), _pad(applied_vectors[index], width))])
        for index in range(count)
    ]
    return {"count": count, "mean": sum(deltas) / len(deltas), "max": max(deltas)}


def position_suppression_ratio(raw_vectors: list[list[float]], applied_vectors: list[list[float]]) -> float | None:
    count = min(len(raw_vectors), len(applied_vectors))
    if count == 0:
        return None
    raw_nonzero = 0
    suppressed = 0
    for raw, applied in zip(raw_vectors[:count], applied_vectors[:count]):
        raw_pos = _pad(raw[:3], 3)
        applied_pos = _pad(applied[:3], 3)
        if _vector_norm(raw_pos) > POSITION_ZERO_EPSILON:
            raw_nonzero += 1
            if _vector_norm(applied_pos) <= POSITION_ZERO_EPSILON:
                suppressed += 1
    if raw_nonzero == 0:
        return None
    return suppressed / raw_nonzero


def timestamp_stats(frames: list[dict[str, Any]]) -> dict[str, Any]:
    times: list[float] = []
    for frame in frames:
        value = frame.get("t")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            times.append(float(value))
    if len(times) < 2:
        return {
            "timestamp_count": len(times),
            "timestamp_monotonic": True,
            "frame_interval_mean_ms": None,
            "frame_interval_jitter_ms": None,
        }
    diffs = [current - previous for previous, current in zip(times, times[1:])]
    mean = sum(diffs) / len(diffs)
    jitter = max(abs(diff - mean) for diff in diffs)
    return {
        "timestamp_count": len(times),
        "timestamp_monotonic": all(diff >= 0.0 for diff in diffs),
        "frame_interval_mean_ms": mean * 1000.0,
        "frame_interval_jitter_ms": jitter * 1000.0,
    }


def tracking_quality(frames: list[dict[str, Any]]) -> dict[str, Any]:
    if not frames:
        return {
            "frame_count": 0,
            "right_hand_tracked_rate": None,
            "xr_frame_valid_rate": None,
            "input_latency_available_rate": None,
            "sim_fps_available_rate": None,
        }
    metadata_items = [frame.get("metadata") if isinstance(frame.get("metadata"), dict) else {} for frame in frames]

    def rate(key: str, expected: Any | None = None) -> float:
        if expected is None:
            count = sum(1 for metadata in metadata_items if metadata.get(key) is not None)
        else:
            count = sum(1 for metadata in metadata_items if metadata.get(key) is expected)
        return count / len(metadata_items)

    return {
        "frame_count": len(frames),
        "right_hand_tracked_rate": rate("right_hand_tracked", True),
        "xr_frame_valid_rate": rate("xr_frame_valid", True),
        "input_latency_available_rate": rate("input_latency_ms"),
        "sim_fps_available_rate": rate("sim_fps"),
    }


def _calibration_events(summary: dict[str, Any]) -> list[dict[str, Any]]:
    events = summary.get("calibration_events")
    if isinstance(events, list):
        return [event for event in events if isinstance(event, dict)]
    calibration = summary.get("calibration")
    if isinstance(calibration, dict):
        return [calibration]
    return []


def calibration_summary(calibration: dict[str, Any]) -> dict[str, Any]:
    translation = _flatten_numeric(calibration.get("translation_offset"))[:3]
    rotation = _flatten_numeric(calibration.get("rotation_offset_quat"))[:4]
    translation_norm = _vector_norm(translation) if len(translation) == 3 else None
    rotation_angle_deg = None
    if len(rotation) == 4:
        normalized = _pad(rotation, 4)[:4]
        norm = _vector_norm(normalized)
        if norm > 1e-9:
            w = max(-1.0, min(1.0, abs(normalized[0] / norm)))
            rotation_angle_deg = math.degrees(2.0 * math.acos(w))
    return {
        "calibration_id": calibration.get("calibration_id"),
        "type": calibration.get("type"),
        "reason": calibration.get("reason"),
        "translation_offset_norm": translation_norm,
        "rotation_offset_angle_deg": rotation_angle_deg,
        "position_gain": calibration.get("position_gain"),
        "control_filter": calibration.get("control_filter") if isinstance(calibration.get("control_filter"), dict) else {},
    }


def recommendations(report: dict[str, Any]) -> list[str]:
    items: list[str] = []
    if report["operator_recenter_event_count"] == 0:
        items.append("Run one short test with P recenter after hand tracking stabilizes.")
    if not report["control_filter"]:
        items.append("Run with RDF_ACTION_FILTER=1 so raw/applied action deltas are recorded.")
    applied_jump_max = (report.get("applied_action_jump") or {}).get("max")
    raw_jump_max = (report.get("raw_action_jump") or {}).get("max")
    if isinstance(applied_jump_max, (int, float)) and applied_jump_max > 0.5:
        items.append("Applied action jump is high; try lower RDF_ACTION_POS_GAIN/RDF_ACTION_ROT_GAIN.")
    if (
        isinstance(raw_jump_max, (int, float))
        and isinstance(applied_jump_max, (int, float))
        and raw_jump_max > 0
        and applied_jump_max >= raw_jump_max
    ):
        items.append("Filter is not reducing action jumps; inspect RDF_ACTION_* gain/smoothing settings.")
    suppression = report.get("position_suppression_ratio")
    if isinstance(suppression, (int, float)) and suppression > 0.25:
        items.append("Many nonzero position commands are suppressed; check deadzone and recenter timing.")
    tracking = report.get("tracking_quality") or {}
    if isinstance(tracking.get("right_hand_tracked_rate"), (int, float)) and tracking["right_hand_tracked_rate"] < 0.9:
        items.append("Right hand tracking rate is low; keep hands in Quest camera view before recording.")
    return items


def analyze_trajectory(path: Path) -> dict[str, Any]:
    trajectory = load_json(path)
    frames = trajectory.get("frames")
    if not isinstance(frames, list):
        frames = []
    frame_dicts = [frame for frame in frames if isinstance(frame, dict)]
    summary = trajectory.get("summary") if isinstance(trajectory.get("summary"), dict) else {}

    raw_vectors = [raw_action(frame) for frame in frame_dicts]
    applied_vectors = [applied_action(frame) for frame in frame_dicts]
    filter_entries = [control_filter_metadata(frame) for frame in frame_dicts]
    filter_entries = [entry for entry in filter_entries if entry]
    calibration_events = _calibration_events(summary)
    recenter_events = [
        event for event in calibration_events if event.get("reason") in {"operator_command", "operator_recenter"}
    ]
    suppressed_frames = [
        entry for entry in filter_entries if entry.get("suppressed_after_recenter") is True
    ]

    issues: list[str] = []
    warnings: list[str] = []
    if not frame_dicts:
        issues.append("trajectory has no frames")
    if not any(raw_vectors):
        issues.append("raw action is unavailable")
    if not any(applied_vectors):
        issues.append("applied action is unavailable")
    if not filter_entries:
        warnings.append("control_filter metadata is unavailable; trajectory may be legacy or filter was disabled")
    if not calibration_events:
        warnings.append("calibration metadata is unavailable")

    report = {
        "path": str(path),
        "trajectory_id": trajectory.get("id"),
        "episode_id": trajectory.get("episode_id"),
        "task_id": trajectory.get("task_id"),
        "schema_version": trajectory.get("schema_version"),
        "source": trajectory.get("source") if isinstance(trajectory.get("source"), dict) else {},
        "episode_status": summary.get("episode_status"),
        "frame_count": len(frame_dicts),
        "raw_action": series_stats(raw_vectors).to_dict(),
        "applied_action": series_stats(applied_vectors).to_dict(),
        "raw_position_axes": axis_stats(raw_vectors, 0, ("x", "y", "z")),
        "applied_position_axes": axis_stats(applied_vectors, 0, ("x", "y", "z")),
        "raw_rotation_axes": axis_stats(raw_vectors, 3, ("rx", "ry", "rz")),
        "applied_rotation_axes": axis_stats(applied_vectors, 3, ("rx", "ry", "rz")),
        "raw_action_jump": jump_stats(raw_vectors),
        "applied_action_jump": jump_stats(applied_vectors),
        "raw_applied_delta": raw_applied_delta_stats(raw_vectors, applied_vectors),
        "position_suppression_ratio": position_suppression_ratio(raw_vectors, applied_vectors),
        "timestamps": timestamp_stats(frame_dicts),
        "tracking_quality": tracking_quality(frame_dicts),
        "calibration": summary.get("calibration") if isinstance(summary.get("calibration"), dict) else {},
        "calibration_summary": calibration_summary(summary.get("calibration")) if isinstance(summary.get("calibration"), dict) else {},
        "calibration_event_count": len(calibration_events),
        "operator_recenter_event_count": len(recenter_events),
        "control_filter": summary.get("control_filter") if isinstance(summary.get("control_filter"), dict) else (
            filter_entries[-1] if filter_entries else {}
        ),
        "control_filter_frame_count": len(filter_entries),
        "suppressed_after_recenter_frame_count": len(suppressed_frames),
        "issues": issues,
        "warnings": warnings,
    }
    report["recommendations"] = recommendations(report)
    return report


def aggregate_report(reports: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "trajectory_count": len(reports),
        "total_frames": sum(int(report.get("frame_count") or 0) for report in reports),
        "issue_count": sum(len(report.get("issues") or []) for report in reports),
        "warning_count": sum(len(report.get("warnings") or []) for report in reports),
        "trajectory_ids": [report.get("trajectory_id") for report in reports],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze RDF teleop calibration/action-filter trajectory JSON.")
    parser.add_argument("paths", nargs="*", type=Path, help="Trajectory JSON files to analyze.")
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT, help="Storage root for --latest.")
    parser.add_argument("--latest", action="store_true", help="Analyze the latest trajectory under storage/trajectories.")
    parser.add_argument(
        "--include-empty-latest",
        action="store_true",
        help="With --latest, inspect the newest file even if it has zero frames.",
    )
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    paths = list(args.paths)
    if args.latest:
        paths.append(latest_trajectory_path(args.storage_root, include_empty=args.include_empty_latest))
    if not paths:
        raise SystemExit("Provide at least one trajectory JSON path or pass --latest.")

    reports = [analyze_trajectory(path) for path in paths]
    output = {
        "schema_version": "rdf_teleop_calibration_analysis_v0.1.0",
        "aggregate": aggregate_report(reports),
        "trajectories": reports,
    }
    if args.pretty:
        print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(stable_json(output))
    return 1 if output["aggregate"]["issue_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
