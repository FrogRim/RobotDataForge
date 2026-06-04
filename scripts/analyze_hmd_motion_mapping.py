#!/usr/bin/env python3
"""Analyze Quest/OpenXR handtracking motion to robot EEF motion mapping."""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
from typing import Any, Callable


DEFAULT_STORAGE_ROOT = Path("storage")
DEFAULT_XR_ANCHOR_POS = [-0.1, -0.5, -1.05]
EPS = 1.0e-9
SIGN_EPS = 1.0e-5
AXIS_INDEX = {"x": 0, "y": 1, "z": 2}
AxisMap = tuple[tuple[int, float], tuple[int, float], tuple[int, float]]
PROVENANCE_TIMELINE_SCHEMA_VERSION = "rdf_hmd_provenance_timeline_v0.1.0"


def stable_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected top-level JSON object")
    return data


def latest_trajectory_path(storage_root: Path, *, include_empty: bool = False) -> Path:
    paths = sorted(
        (storage_root / "trajectories").glob("*.json"),
        key=lambda path: path.stat().st_mtime,
    )
    if not paths:
        raise FileNotFoundError(
            f"No trajectory JSON files found under {storage_root / 'trajectories'}"
        )
    if include_empty:
        return paths[-1]
    for path in reversed(paths):
        try:
            frames = load_json(path).get("frames")
        except Exception:
            continue
        if isinstance(frames, list) and any(
            isinstance(frame, dict) for frame in frames
        ):
            return path
    return paths[-1]


def dict_or_empty(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def list3(value: Any) -> list[float] | None:
    if not isinstance(value, list) or len(value) < 3:
        return None
    try:
        return [float(value[0]), float(value[1]), float(value[2])]
    except (TypeError, ValueError):
        return None


def parse_vector3(text: str | None, default: list[float]) -> list[float]:
    if text is None or not text.strip():
        return list(default)
    parts = [part.strip() for part in text.split(",")]
    if len(parts) != 3:
        return list(default)
    try:
        return [float(part) for part in parts]
    except ValueError:
        return list(default)


def configured_xr_anchor_pos() -> list[float]:
    return parse_vector3(os.environ.get("RDF_XR_ANCHOR_POS"), DEFAULT_XR_ANCHOR_POS)


def parse_signed_axis_map(spec: Any) -> AxisMap | None:
    if not isinstance(spec, str) or not spec.strip():
        return None
    parts = [part.strip().lower() for part in spec.split(",")]
    if len(parts) != 3:
        return None
    parsed: list[tuple[int, float]] = []
    used: set[int] = set()
    for part in parts:
        sign = 1.0
        axis = part
        if axis.startswith("+"):
            axis = axis[1:]
        elif axis.startswith("-"):
            sign = -1.0
            axis = axis[1:]
        if axis not in AXIS_INDEX:
            return None
        index = AXIS_INDEX[axis]
        if index in used:
            return None
        used.add(index)
        parsed.append((index, sign))
    return (parsed[0], parsed[1], parsed[2])


def apply_axis_map(values: list[float], axis_map: AxisMap) -> list[float]:
    return [values[index] * sign for index, sign in axis_map]


def apply_yaw_offset(values: list[float], yaw_offset_deg: float) -> list[float]:
    if abs(yaw_offset_deg) <= 1.0e-9:
        return list(values)
    yaw = math.radians(float(yaw_offset_deg))
    cos_yaw = math.cos(yaw)
    sin_yaw = math.sin(yaw)
    return [
        cos_yaw * values[0] + sin_yaw * values[2],
        values[1],
        -sin_yaw * values[0] + cos_yaw * values[2],
    ]


def remap_series(
    values: list[list[float] | None], axis_map: AxisMap | None
) -> list[list[float] | None]:
    if axis_map is None:
        return [value[:] if value is not None else None for value in values]
    return [
        apply_axis_map(value, axis_map) if value is not None else None
        for value in values
    ]


def yaw_series(
    values: list[list[float] | None], yaw_offset_deg: float
) -> list[list[float] | None]:
    return [
        apply_yaw_offset(value, yaw_offset_deg) if value is not None else None
        for value in values
    ]


def vector_norm(values: list[float]) -> float:
    return math.sqrt(sum(value * value for value in values))


def subtract(lhs: list[float], rhs: list[float]) -> list[float]:
    return [lhs[index] - rhs[index] for index in range(3)]


def dot(lhs: list[float], rhs: list[float]) -> float:
    return sum(lhs[index] * rhs[index] for index in range(3))


def action_dict(frame: dict[str, Any]) -> dict[str, Any]:
    return dict_or_empty(frame.get("action"))


def control_filter(frame: dict[str, Any]) -> dict[str, Any]:
    return dict_or_empty(action_dict(frame).get("control_filter"))


def teleop_control_mode(frame: dict[str, Any]) -> dict[str, Any]:
    return dict_or_empty(control_filter(frame).get("teleop_control_mode"))


def metadata(frame: dict[str, Any]) -> dict[str, Any]:
    return dict_or_empty(frame.get("metadata"))


def nested_command(value: Any) -> list[float] | None:
    if isinstance(value, list):
        return list3(value)
    if not isinstance(value, dict):
        return None
    for key in (
        "command",
        "robot_action",
        "action",
        "applied",
        "raw",
        "delta_position",
    ):
        nested = nested_command(value.get(key))
        if nested is not None:
            return nested
    return None


def raw_action_xyz(frame: dict[str, Any]) -> list[float] | None:
    action = action_dict(frame)
    return nested_command(action.get("raw")) or nested_command(action)


def applied_action_xyz(frame: dict[str, Any]) -> list[float] | None:
    action = action_dict(frame)
    return nested_command(action.get("applied")) or nested_command(
        action.get("retargeted_robot_action")
    )


def raw_wrist_xyz(frame: dict[str, Any]) -> list[float] | None:
    tcm = teleop_control_mode(frame)
    return list3(tcm.get("raw_right_wrist_pose")) or list3(
        dict_or_empty(metadata(frame).get("raw_xr")).get("right_wrist_pose")
    )


def aligned_wrist_xyz(frame: dict[str, Any]) -> list[float] | None:
    return list3(
        dict_or_empty(metadata(frame).get("aligned_xr")).get("right_wrist_pose")
    )


def raw_wrist_origin_xyz(frame: dict[str, Any]) -> list[float] | None:
    return list3(raw_wrist_direct_metadata(frame).get("raw_wrist_origin_pose"))


def wrist_offset_robot_xyz(frame: dict[str, Any]) -> list[float] | None:
    raw_wrist = raw_wrist_direct_metadata(frame)
    return list3(raw_wrist.get("wrist_offset_robot")) or list3(
        teleop_control_mode(frame).get("hand_delta_m")
    )


def desired_target_xyz(frame: dict[str, Any]) -> list[float] | None:
    return list3(teleop_control_mode(frame).get("desired_ee_target_xyz"))


def executed_command_xyz(frame: dict[str, Any]) -> list[float] | None:
    tcm_command = list3(teleop_control_mode(frame).get("applied_ee_delta_m"))
    if tcm_command is not None:
        return tcm_command
    return nested_command(action_dict(frame).get("executed_control"))


def eef_xyz(frame: dict[str, Any]) -> list[float] | None:
    return list3(frame.get("end_effector_position")) or list3(
        teleop_control_mode(frame).get("actual_ee_xyz")
    )


def series(
    frames: list[dict[str, Any]], getter: Callable[[dict[str, Any]], list[float] | None]
) -> list[list[float] | None]:
    return [getter(frame) for frame in frames]


def vector_stats(values: list[list[float] | None]) -> dict[str, Any]:
    rows = [value for value in values if value is not None]
    if not rows:
        return {"count": 0, "axes": {}, "norm": {}}
    axes: dict[str, Any] = {}
    for index, label in enumerate(("x", "y", "z")):
        axis_values = [row[index] for row in rows]
        abs_values = [abs(value) for value in axis_values]
        axes[label] = {
            "min": min(axis_values),
            "max": max(axis_values),
            "mean": sum(axis_values) / len(axis_values),
            "mean_abs": sum(abs_values) / len(abs_values),
            "max_abs": max(abs_values),
        }
    norms = [vector_norm(row) for row in rows]
    return {
        "count": len(rows),
        "axes": axes,
        "norm": {
            "mean": sum(norms) / len(norms),
            "max": max(norms),
            "zero_ratio": sum(1 for norm in norms if norm <= SIGN_EPS) / len(norms),
        },
    }


def delta_series(values: list[list[float] | None]) -> list[list[float] | None]:
    deltas: list[list[float] | None] = [None]
    for previous, current in zip(values, values[1:]):
        deltas.append(
            subtract(current, previous)
            if previous is not None and current is not None
            else None
        )
    return deltas


def pearson(lhs: list[float], rhs: list[float]) -> float | None:
    if len(lhs) < 2 or len(rhs) < 2 or len(lhs) != len(rhs):
        return None
    lhs_mean = sum(lhs) / len(lhs)
    rhs_mean = sum(rhs) / len(rhs)
    lhs_var = sum((value - lhs_mean) ** 2 for value in lhs)
    rhs_var = sum((value - rhs_mean) ** 2 for value in rhs)
    if lhs_var <= EPS or rhs_var <= EPS:
        return None
    covariance = sum(
        (left - lhs_mean) * (right - rhs_mean) for left, right in zip(lhs, rhs)
    )
    return covariance / math.sqrt(lhs_var * rhs_var)


def response_stats(
    command_values: list[list[float] | None],
    response_values: list[list[float] | None],
    *,
    command_label: str,
    response_label: str,
) -> dict[str, Any]:
    axis_reports: dict[str, Any] = {}
    total_considered = 0
    total_agree = 0
    for index, axis in enumerate(("x", "y", "z")):
        pairs = [
            (command[index], response[index])
            for command, response in zip(command_values, response_values)
            if command is not None
            and response is not None
            and abs(command[index]) > SIGN_EPS
        ]
        considered = len(pairs)
        agree = sum(
            1
            for command, response in pairs
            if abs(response) > SIGN_EPS and command * response > 0
        )
        total_considered += considered
        total_agree += agree
        axis_reports[axis] = {
            "sample_count": considered,
            "sign_agree_count": agree,
            "sign_agree_ratio": (agree / considered) if considered else None,
            "correlation": pearson(
                [pair[0] for pair in pairs], [pair[1] for pair in pairs]
            ),
            "mean_abs_command": (sum(abs(pair[0]) for pair in pairs) / considered)
            if considered
            else None,
            "mean_abs_response": (sum(abs(pair[1]) for pair in pairs) / considered)
            if considered
            else None,
        }
    return {
        "command_label": command_label,
        "response_label": response_label,
        "axis": axis_reports,
        "overall_sign_agree_ratio": (total_agree / total_considered)
        if total_considered
        else None,
        "overall_sample_count": total_considered,
    }


def numeric_tcm_series(frames: list[dict[str, Any]], key: str) -> list[float]:
    values: list[float] = []
    for frame in frames:
        value = teleop_control_mode(frame).get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            values.append(float(value))
    return values


def bool_tcm_ratio(frames: list[dict[str, Any]], key: str) -> float | None:
    values = [teleop_control_mode(frame).get(key) for frame in frames]
    bool_values = [value for value in values if isinstance(value, bool)]
    if not bool_values:
        return None
    return sum(1 for value in bool_values if value) / len(bool_values)


def scalar_stats(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"count": 0, "mean": None, "max": None}
    ordered = sorted(values)
    p95_index = min(len(ordered) - 1, int(0.95 * (len(ordered) - 1)))
    return {
        "count": len(values),
        "mean": sum(values) / len(values),
        "max": max(values),
        "p95": ordered[p95_index],
    }


def quantile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(q * (len(ordered) - 1))))
    return ordered[index]


def tracking_quality(frames: list[dict[str, Any]]) -> dict[str, Any]:
    if not frames:
        return {
            "frame_count": 0,
            "right_hand_tracked_rate": None,
            "xr_frame_valid_rate": None,
        }
    right = [metadata(frame).get("right_hand_tracked") is True for frame in frames]
    valid = [metadata(frame).get("xr_frame_valid") is True for frame in frames]
    return {
        "frame_count": len(frames),
        "right_hand_tracked_rate": sum(right) / len(frames),
        "xr_frame_valid_rate": sum(valid) / len(frames),
    }


def calibration_summary(summary: dict[str, Any]) -> dict[str, Any]:
    calibration = dict_or_empty(summary.get("calibration"))
    events = summary.get("calibration_events")
    if not isinstance(events, list):
        events = []
    event_dicts = [event for event in events if isinstance(event, dict)]
    return {
        "type": calibration.get("type"),
        "reason": calibration.get("reason"),
        "calibration_id": calibration.get("calibration_id"),
        "event_count": len(event_dicts),
        "event_reasons": [event.get("reason") for event in event_dicts],
        "has_rotation_offset": bool(calibration.get("rotation_offset_quat")),
        "has_translation_offset": bool(calibration.get("translation_offset")),
    }


def dead_hand_stats(frames: list[dict[str, Any]]) -> dict[str, Any]:
    rows: list[dict[str, float]] = []
    for frame in frames:
        tcm = teleop_control_mode(frame)
        hand_delta = list3(tcm.get("hand_delta_m"))
        command = list3(tcm.get("applied_ee_delta_m"))
        if hand_delta is None or command is None:
            continue
        deadzone = float(tcm.get("deadzone_m") or 0.0)
        hand_norm = vector_norm(hand_delta)
        command_norm = vector_norm(command)
        if hand_norm <= max(deadzone, SIGN_EPS):
            rows.append({"hand_norm": hand_norm, "command_norm": command_norm})
    if not rows:
        return {"count": 0, "command_nonzero_ratio": None, "command_norm_max": None}
    return {
        "count": len(rows),
        "command_nonzero_ratio": sum(
            1 for row in rows if row["command_norm"] > SIGN_EPS
        )
        / len(rows),
        "command_norm_max": max(row["command_norm"] for row in rows),
    }


def deadzone_boundary_stats(frames: list[dict[str, Any]]) -> dict[str, Any]:
    exit_jumps: list[dict[str, Any]] = []
    entry_snaps: list[dict[str, Any]] = []
    for index, (previous, current) in enumerate(zip(frames, frames[1:]), start=1):
        previous_tcm = teleop_control_mode(previous)
        current_tcm = teleop_control_mode(current)
        previous_hand = list3(previous_tcm.get("hand_delta_m"))
        current_hand = list3(current_tcm.get("hand_delta_m"))
        previous_target = list3(previous_tcm.get("desired_ee_target_xyz"))
        current_target = list3(current_tcm.get("desired_ee_target_xyz"))
        if (
            previous_hand is None
            or current_hand is None
            or previous_target is None
            or current_target is None
        ):
            continue
        previous_deadzone = float(previous_tcm.get("deadzone_m") or 0.0)
        current_deadzone = float(current_tcm.get("deadzone_m") or previous_deadzone)
        previous_inside = vector_norm(previous_hand) <= max(previous_deadzone, SIGN_EPS)
        current_inside = vector_norm(current_hand) <= max(current_deadzone, SIGN_EPS)
        if previous_inside == current_inside:
            continue
        target_jump = vector_norm(subtract(current_target, previous_target))
        hand_jump = vector_norm(subtract(current_hand, previous_hand))
        if target_jump <= 0.03 or target_jump <= 5.0 * max(hand_jump, SIGN_EPS):
            continue
        jump = {
            "from_index": index - 1,
            "to_index": index,
            "target_jump_m": target_jump,
            "hand_jump_m": hand_jump,
            "from_inside_deadzone": previous_inside,
            "to_inside_deadzone": current_inside,
        }
        if previous_inside and not current_inside:
            exit_jumps.append(jump)
        elif not previous_inside and current_inside:
            entry_snaps.append(jump)
    return {
        "target_jump_count": len(exit_jumps),
        "target_jump_max": max(
            (jump["target_jump_m"] for jump in exit_jumps), default=0.0
        ),
        "hand_jump_max": max((jump["hand_jump_m"] for jump in exit_jumps), default=0.0),
        "jumps": exit_jumps,
        "entry_snap_count": len(entry_snaps),
        "entry_snap_max": max(
            (jump["target_jump_m"] for jump in entry_snaps), default=0.0
        ),
        "entry_snaps": entry_snaps,
    }


def anchor_fallback_stats(
    frames: list[dict[str, Any]], tolerance: float = 1.0e-4
) -> dict[str, Any]:
    anchor = configured_xr_anchor_pos()
    anchor_like_indices: list[int] = []
    anchor_like_valid_indices: list[int] = []
    anchor_like_invalid_indices: list[int] = []
    anchor_like_unknown_indices: list[int] = []
    raw_jumps: list[dict[str, Any]] = []
    raw_jumps_valid_to_valid: list[dict[str, Any]] = []
    previous_wrist: list[float] | None = None
    previous_right_hand_tracked: Any = None
    previous_xr_frame_valid: Any = None
    for index, frame in enumerate(frames):
        wrist = raw_wrist_xyz(frame)
        if wrist is None:
            previous_wrist = None
            previous_right_hand_tracked = None
            previous_xr_frame_valid = None
            continue
        frame_metadata = metadata(frame)
        right_hand_tracked = frame_metadata.get("right_hand_tracked")
        xr_frame_valid = frame_metadata.get("xr_frame_valid")
        anchor_like = all(
            abs(float(wrist[axis]) - anchor[axis]) <= tolerance for axis in range(3)
        )
        if anchor_like:
            anchor_like_indices.append(index)
            if right_hand_tracked is True or xr_frame_valid is True:
                anchor_like_valid_indices.append(index)
            elif right_hand_tracked is False or xr_frame_valid is False:
                anchor_like_invalid_indices.append(index)
            else:
                anchor_like_unknown_indices.append(index)
        if previous_wrist is not None:
            jump = vector_norm(subtract(wrist, previous_wrist))
            if jump > 0.10:
                raw_jumps.append(
                    {
                        "from_index": index - 1,
                        "to_index": index,
                        "jump_m": jump,
                        "to_anchor_like": index in anchor_like_indices,
                        "to_anchor_like_valid": index in anchor_like_valid_indices,
                    }
                )
                if (
                    previous_right_hand_tracked is True
                    and previous_xr_frame_valid is True
                    and right_hand_tracked is True
                    and xr_frame_valid is True
                ):
                    raw_jumps_valid_to_valid.append(
                        {
                            "from_index": index - 1,
                            "to_index": index,
                            "jump_m": jump,
                            "to_anchor_like": index in anchor_like_indices,
                        }
                    )
        previous_wrist = wrist
        previous_right_hand_tracked = right_hand_tracked
        previous_xr_frame_valid = xr_frame_valid

    return {
        "configured_anchor_pos": anchor,
        "tolerance_m": tolerance,
        "frame_count": len(frames),
        "anchor_like_frame_count": len(anchor_like_indices),
        "anchor_like_frame_ratio": (len(anchor_like_indices) / len(frames))
        if frames
        else None,
        "anchor_like_valid_frame_count": len(anchor_like_valid_indices),
        "anchor_like_valid_frame_ratio": (len(anchor_like_valid_indices) / len(frames))
        if frames
        else None,
        "anchor_like_invalid_frame_count": len(anchor_like_invalid_indices),
        "anchor_like_invalid_frame_ratio": (
            len(anchor_like_invalid_indices) / len(frames)
        )
        if frames
        else None,
        "anchor_like_unknown_frame_count": len(anchor_like_unknown_indices),
        "anchor_like_unknown_frame_ratio": (
            len(anchor_like_unknown_indices) / len(frames)
        )
        if frames
        else None,
        "anchor_like_frame_indices": anchor_like_indices[:50],
        "anchor_like_valid_frame_indices": anchor_like_valid_indices[:50],
        "anchor_like_invalid_frame_indices": anchor_like_invalid_indices[:50],
        "anchor_like_unknown_frame_indices": anchor_like_unknown_indices[:50],
        "raw_wrist_jump_gt_10cm_count": len(raw_jumps),
        "raw_wrist_jump_gt_10cm_max": max(
            (jump["jump_m"] for jump in raw_jumps), default=0.0
        ),
        "raw_wrist_jump_examples": raw_jumps[:20],
        "raw_wrist_jump_gt_10cm_valid_to_valid_count": len(raw_jumps_valid_to_valid),
        "raw_wrist_jump_gt_10cm_valid_to_valid_max": max(
            (jump["jump_m"] for jump in raw_jumps_valid_to_valid), default=0.0
        ),
        "raw_wrist_jump_valid_to_valid_examples": raw_jumps_valid_to_valid[:20],
    }


def raw_wrist_direct_metadata(frame: dict[str, Any]) -> dict[str, Any]:
    return dict_or_empty(
        teleop_control_mode(frame).get("raw_wrist_direct_control")
    ) or dict_or_empty(action_dict(frame).get("raw_wrist_direct"))


def target_accumulation_stats(frames: list[dict[str, Any]]) -> dict[str, Any]:
    """Check whether target position drifts beyond current absolute hand offset within stable segments."""
    rows: list[dict[str, Any]] = []
    for index, frame in enumerate(frames):
        tcm = teleop_control_mode(frame)
        hand_delta = list3(tcm.get("hand_delta_m"))
        target = list3(tcm.get("desired_ee_target_xyz"))
        if hand_delta is None or target is None:
            continue
        raw_wrist = raw_wrist_direct_metadata(frame)
        gate_state = raw_wrist.get("gate_state")
        if gate_state not in (None, "accepted", "warn"):
            rows.append({"index": index, "break": True})
            continue
        origin = list3(raw_wrist.get("raw_wrist_origin_pose"))
        rows.append(
            {
                "index": index,
                "origin": tuple(round(value, 5) for value in origin)
                if origin
                else None,
                "anchor_estimate": subtract(target, hand_delta),
                "target": target,
                "hand_delta": hand_delta,
                "gate_state": gate_state,
            }
        )

    segments: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    previous_index: int | None = None
    previous_origin: tuple[float, float, float] | None = None
    for row in rows:
        if row.get("break"):
            if current:
                segments.append(current)
                current = []
            previous_index = None
            previous_origin = None
            continue
        origin = row.get("origin")
        if current and (
            previous_index is None
            or row["index"] != previous_index + 1
            or (
                origin is not None
                and previous_origin is not None
                and origin != previous_origin
            )
        ):
            segments.append(current)
            current = []
        current.append(row)
        previous_index = row["index"]
        previous_origin = origin
    if current:
        segments.append(current)

    segment_reports: list[dict[str, Any]] = []
    all_residuals: list[float] = []
    for segment in segments:
        anchors = [row["anchor_estimate"] for row in segment]
        median_anchor = [
            sorted(anchor[axis] for anchor in anchors)[len(anchors) // 2]
            for axis in range(3)
        ]
        residuals = [vector_norm(subtract(anchor, median_anchor)) for anchor in anchors]
        all_residuals.extend(residuals)
        segment_reports.append(
            {
                "start_index": segment[0]["index"],
                "end_index": segment[-1]["index"],
                "count": len(segment),
                "origin": list(segment[0]["origin"])
                if segment[0].get("origin")
                else None,
                "anchor_estimate_median": [round(value, 6) for value in median_anchor],
                "anchor_estimate_residual_max_m": max(residuals) if residuals else 0.0,
                "anchor_estimate_residual_p95_m": quantile(residuals, 0.95),
            }
        )

    max_residual = max(all_residuals, default=0.0)
    return {
        "sample_count": sum(len(segment) for segment in segments),
        "segment_count": len(segments),
        "max_anchor_est_residual_m": max_residual,
        "p95_anchor_est_residual_m": quantile(all_residuals, 0.95),
        "warn_threshold_m": 0.02,
        "accumulation_warn": max_residual > 0.02,
        "segments": segment_reports[:20],
    }


def task_state(frame: dict[str, Any]) -> dict[str, Any]:
    return dict_or_empty(metadata(frame).get("task_state"))


def scene_vector(frame: dict[str, Any], field: str) -> list[float] | None:
    if field == "eef":
        return eef_xyz(frame)
    if field == "object":
        return list3(frame.get("object_position"))
    state = task_state(frame)
    if field == "peg":
        return list3(state.get("peg_position"))
    if field == "hole":
        return list3(state.get("hole_position"))
    if field == "hole_target":
        return list3(state.get("hole_target_position"))
    return None


def scene_state_discontinuity_stats(frames: list[dict[str, Any]]) -> dict[str, Any]:
    thresholds = {
        "eef": 0.05,
        "object": 0.05,
        "peg": 0.05,
        "hole": 0.02,
        "hole_target": 0.02,
    }
    events: list[dict[str, Any]] = []
    for field, threshold in thresholds.items():
        previous: list[float] | None = None
        for index, frame in enumerate(frames):
            current = scene_vector(frame, field)
            if current is not None and previous is not None:
                jump = vector_norm(subtract(current, previous))
                if jump > threshold:
                    raw_wrist = raw_wrist_direct_metadata(frame)
                    events.append(
                        {
                            "field": field,
                            "frame_index": index,
                            "jump_m": jump,
                            "threshold_m": threshold,
                            "gate_state": raw_wrist.get("gate_state"),
                            "gate_reason": raw_wrist.get("gate_reason"),
                            "phase_before": task_state(frames[index - 1]).get(
                                "action_phase"
                            ),
                            "phase_after": task_state(frame).get("action_phase"),
                        }
                    )
            if current is not None:
                previous = current
    return {
        "event_count": len(events),
        "frames": sorted({int(event["frame_index"]) for event in events}),
        "events": events[:50],
        "warn": bool(events),
    }


def _frame_index(frame: dict[str, Any], fallback: int) -> int:
    try:
        return int(frame.get("step", fallback))
    except (TypeError, ValueError):
        return fallback


def _tracking_valid(frame: dict[str, Any]) -> bool:
    frame_metadata = metadata(frame)
    return bool(
        frame_metadata.get("right_hand_tracked") is True
        and frame_metadata.get("xr_frame_valid") is True
    )


def provenance_timeline_stats(frames: list[dict[str, Any]]) -> dict[str, Any]:
    """Decompose transition discontinuities across the input-to-robot pipeline."""

    stage_specs: list[
        tuple[str, str, float, Callable[[dict[str, Any]], list[float] | None]]
    ] = [
        ("raw_wrist", "input", 0.10, raw_wrist_xyz),
        ("aligned_wrist", "transform", 0.10, aligned_wrist_xyz),
        ("raw_wrist_origin", "recenter", 0.02, raw_wrist_origin_xyz),
        ("wrist_offset_robot", "transform", 0.10, wrist_offset_robot_xyz),
        ("desired_target", "control_target", 0.05, desired_target_xyz),
        ("executed_command", "robot_command", 0.04, executed_command_xyz),
        ("actual_eef", "robot_state", 0.05, eef_xyz),
        ("object", "scene_state", 0.05, lambda frame: scene_vector(frame, "object")),
        ("peg", "scene_state", 0.05, lambda frame: scene_vector(frame, "peg")),
        ("hole", "scene_state", 0.02, lambda frame: scene_vector(frame, "hole")),
        (
            "hole_target",
            "scene_state",
            0.02,
            lambda frame: scene_vector(frame, "hole_target"),
        ),
    ]
    thresholds = {stage: threshold for stage, _, threshold, _ in stage_specs}
    categories = {stage: category for stage, category, _, _ in stage_specs}
    stage_counts = {stage: 0 for stage, _, _, _ in stage_specs}
    first_stage_counts: dict[str, int] = {}
    availability = {
        stage: {"available_transition_count": 0, "missing_transition_count": 0}
        for stage, _, _, _ in stage_specs
    }
    events: list[dict[str, Any]] = []

    for transition_index, (previous, current) in enumerate(
        zip(frames, frames[1:]), start=1
    ):
        stages: dict[str, dict[str, Any]] = {}
        over_threshold: list[str] = []
        for stage, category, threshold, getter in stage_specs:
            previous_value = getter(previous)
            current_value = getter(current)
            available = previous_value is not None and current_value is not None
            if available:
                delta_m = vector_norm(subtract(current_value, previous_value))
                over = delta_m > threshold
                availability[stage]["available_transition_count"] += 1
                if over:
                    stage_counts[stage] += 1
                    over_threshold.append(stage)
                stages[stage] = {
                    "category": category,
                    "available": True,
                    "delta_m": round(delta_m, 6),
                    "threshold_m": threshold,
                    "over_threshold": over,
                }
            else:
                availability[stage]["missing_transition_count"] += 1
                stages[stage] = {
                    "category": category,
                    "available": False,
                    "delta_m": None,
                    "threshold_m": threshold,
                    "over_threshold": False,
                }

        if not over_threshold:
            continue

        first_stage = over_threshold[0]
        first_stage_counts[first_stage] = first_stage_counts.get(first_stage, 0) + 1
        raw_wrist = raw_wrist_direct_metadata(current)
        events.append(
            {
                "transition_index": transition_index,
                "from_index": _frame_index(previous, transition_index - 1),
                "to_index": _frame_index(current, transition_index),
                "first_discontinuity_stage": first_stage,
                "over_threshold_stages": over_threshold,
                "stages": stages,
                "tracking": {
                    "previous_valid": _tracking_valid(previous),
                    "current_valid": _tracking_valid(current),
                },
                "raw_wrist_gate": {
                    "state": raw_wrist.get("gate_state"),
                    "reason": raw_wrist.get("gate_reason"),
                },
            }
        )

    return {
        "schema_version": PROVENANCE_TIMELINE_SCHEMA_VERSION,
        "transition_count": max(0, len(frames) - 1),
        "event_count": len(events),
        "thresholds_m": thresholds,
        "stage_categories": categories,
        "stage_counts": {key: value for key, value in stage_counts.items() if value},
        "first_stage_counts": first_stage_counts,
        "availability": availability,
        "events": events[:100],
        "event_limit": 100,
    }


def config_summary(
    frames: list[dict[str, Any]], summary: dict[str, Any]
) -> dict[str, Any]:
    first_filter = next(
        (control_filter(frame) for frame in frames if control_filter(frame)), {}
    )
    first_tcm = next(
        (teleop_control_mode(frame) for frame in frames if teleop_control_mode(frame)),
        {},
    )
    summary_filter = dict_or_empty(summary.get("control_filter"))
    config = dict_or_empty(first_filter.get("config")) or dict_or_empty(
        summary_filter.get("config")
    )
    return {
        "control_mode": first_tcm.get("name"),
        "control_semantics": first_tcm.get("control_semantics"),
        "position_axis_map": config.get("position_axis_map"),
        "rotation_axis_map": config.get("rotation_axis_map"),
        "position_yaw_offset_deg": config.get("position_yaw_offset_deg"),
        "action_position_gain": config.get("position_gain"),
        "direct_position_gain": first_tcm.get("position_gain"),
        "max_step_m": first_tcm.get("max_step_m"),
        "smoothing_alpha": first_tcm.get("smoothing_alpha"),
        "deadzone_m": first_tcm.get("deadzone_m"),
        "workspace_radius_m": first_tcm.get("workspace_radius_m"),
    }


def hypothesis_results(report: dict[str, Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    config = report["config"]
    command_response = report["response"]["command_to_next_eef_delta"]
    response_ratio = command_response.get("overall_sign_agree_ratio")
    clamp_ratio = report["controller"]["workspace_clamped_ratio"]
    saturation_ratio = report["controller"]["command_saturation_ratio"]
    dead = report["dead_hand"]
    boundary = report["deadzone_boundary"]
    anchor_fallback = report["anchor_fallback"]
    target_accumulation = report["target_accumulation"]
    scene_discontinuity = report["scene_state_discontinuity"]
    tracking = report["tracking_quality"]
    axis_map = config.get("position_axis_map")
    raw_wrist_norm = report["series"]["raw_wrist_delta"]["norm"]
    input_norm = report["series"]["input_delta_xyz"]["norm"]
    calibration = report["calibration"]

    raw_wrist_max = raw_wrist_norm.get("max")
    input_max = input_norm.get("max")
    raw_action_to_input = report["response"][
        "raw_action_axis_mapped_to_input_delta"
    ].get("overall_sign_agree_ratio")
    raw_wrist_to_input = report["response"][
        "raw_wrist_delta_to_input_delta_unmapped"
    ].get("overall_sign_agree_ratio")

    results.append(
        {
            "id": "H1",
            "name": "OpenXR/Isaac coordinate-frame mismatch",
            "status": (
                "UNKNOWN"
                if not raw_wrist_max or raw_wrist_max <= SIGN_EPS
                else "PASS"
                if isinstance(raw_action_to_input, float)
                and raw_action_to_input >= 0.80
                else "WARN"
            ),
            "detail": (
                f"raw_wrist_delta_norm_max={raw_wrist_max} input_delta_norm_max={input_max} "
                f"raw_action_axis_mapped_to_input_delta_sign_agree={raw_action_to_input} "
                f"raw_wrist_delta_to_input_delta_unmapped_sign_agree={raw_wrist_to_input}"
            ),
        }
    )

    results.append(
        {
            "id": "H2",
            "name": "axis map default/passthrough",
            "status": "PASS" if axis_map else "UNKNOWN",
            "detail": f"trajectory position_axis_map={axis_map!r}",
        }
    )
    results.append(
        {
            "id": "H3",
            "name": "recenter/start-box calibration offset",
            "status": (
                "PASS"
                if calibration.get("reason") == "auto_robot_start_box"
                or "auto_robot_start_box" in (calibration.get("event_reasons") or [])
                else "WARN"
                if calibration.get("reason") or calibration.get("event_count")
                else "UNKNOWN"
            ),
            "detail": (
                f"calibration_reason={calibration.get('reason')} "
                f"event_reasons={calibration.get('event_reasons')}"
            ),
        }
    )
    results.append(
        {
            "id": "H6",
            "name": "workspace clamp/rate limit blocks motion",
            "status": (
                "WARN"
                if (isinstance(clamp_ratio, float) and clamp_ratio > 0.05)
                or (isinstance(saturation_ratio, float) and saturation_ratio > 0.30)
                else "PASS"
            ),
            "detail": f"workspace_clamped_ratio={clamp_ratio} command_saturation_ratio={saturation_ratio}",
        }
    )
    results.append(
        {
            "id": "H7",
            "name": "Isaac EEF follows command direction",
            "status": (
                "PASS"
                if isinstance(response_ratio, float) and response_ratio >= 0.70
                else "WARN"
                if response_ratio is not None
                else "UNKNOWN"
            ),
            "detail": f"command_to_next_eef_delta overall_sign_agree_ratio={response_ratio}",
        }
    )
    results.append(
        {
            "id": "H4",
            "name": "dead-hand target runaway",
            "status": (
                "PASS"
                if dead.get("command_nonzero_ratio") in (None, 0.0)
                else "WARN"
                if dead.get("command_nonzero_ratio", 0.0) < 0.25
                else "FAIL"
            ),
            "detail": (
                "near-zero hand_delta command_nonzero_ratio="
                f"{dead.get('command_nonzero_ratio')} max={dead.get('command_norm_max')}"
            ),
        }
    )
    results.append(
        {
            "id": "H5",
            "name": "deadzone/smoothing hides small motion",
            "status": (
                "UNKNOWN"
                if report["frame_count"] < 60
                else "WARN"
                if report["series"]["input_delta_xyz"]["norm"].get("zero_ratio", 0.0)
                > 0.75
                else "PASS"
            ),
            "detail": (
                "input_delta_zero_ratio="
                f"{report['series']['input_delta_xyz']['norm'].get('zero_ratio')} "
                f"smoothing_alpha={config.get('smoothing_alpha')} deadzone_m={config.get('deadzone_m')}"
            ),
        }
    )
    results.append(
        {
            "id": "H11",
            "name": "deadzone boundary target discontinuity",
            "status": "WARN" if boundary.get("target_jump_count", 0) else "PASS",
            "detail": (
                "deadzone_boundary_target_jump_count="
                f"{boundary.get('target_jump_count')} max={boundary.get('target_jump_max')} "
                f"hand_jump_max={boundary.get('hand_jump_max')}"
            ),
        }
    )
    anchor_count = int(anchor_fallback.get("anchor_like_frame_count") or 0)
    anchor_valid_count = int(anchor_fallback.get("anchor_like_valid_frame_count") or 0)
    anchor_invalid_count = int(
        anchor_fallback.get("anchor_like_invalid_frame_count") or 0
    )
    anchor_ratio = anchor_fallback.get("anchor_like_frame_ratio")
    valid_wrist_jump_count = int(
        anchor_fallback.get("raw_wrist_jump_gt_10cm_valid_to_valid_count") or 0
    )
    valid_wrist_jump_max = anchor_fallback.get(
        "raw_wrist_jump_gt_10cm_valid_to_valid_max"
    )
    results.append(
        {
            "id": "H12",
            "name": "XR anchor fallback pose accepted as hand tracking",
            "status": "WARN" if anchor_valid_count else "PASS",
            "detail": (
                f"anchor_like_frame_count={anchor_count} valid={anchor_valid_count} "
                f"invalid={anchor_invalid_count} ratio={anchor_ratio} "
                f"raw_wrist_jump_gt_10cm_count={anchor_fallback.get('raw_wrist_jump_gt_10cm_count')} "
                f"max_jump={anchor_fallback.get('raw_wrist_jump_gt_10cm_max')}"
            ),
        }
    )
    results.append(
        {
            "id": "H13",
            "name": "valid handtracking wrist pose spikes",
            "status": "WARN" if valid_wrist_jump_count else "PASS",
            "detail": (
                f"raw_wrist_jump_gt_10cm_valid_to_valid_count={valid_wrist_jump_count} "
                f"max_jump={valid_wrist_jump_max}"
            ),
        }
    )
    results.append(
        {
            "id": "H14",
            "name": "controller target accumulation drift",
            "status": "WARN"
            if target_accumulation.get("accumulation_warn")
            else "PASS",
            "detail": (
                "max_anchor_est_residual_m="
                f"{target_accumulation.get('max_anchor_est_residual_m')} "
                f"p95={target_accumulation.get('p95_anchor_est_residual_m')} "
                f"segments={target_accumulation.get('segment_count')}"
            ),
        }
    )
    results.append(
        {
            "id": "H15",
            "name": "sim/task-state discontinuity inside one recorded trajectory",
            "status": "WARN" if scene_discontinuity.get("warn") else "PASS",
            "detail": (
                f"event_count={scene_discontinuity.get('event_count')} "
                f"frames={scene_discontinuity.get('frames')}"
            ),
        }
    )
    results.append(
        {
            "id": "H9",
            "name": "handtracking loss/jitter",
            "status": (
                "PASS"
                if isinstance(tracking.get("right_hand_tracked_rate"), float)
                and tracking["right_hand_tracked_rate"] >= 0.95
                and isinstance(tracking.get("xr_frame_valid_rate"), float)
                and tracking["xr_frame_valid_rate"] >= 0.95
                else "WARN"
            ),
            "detail": (
                f"right_hand_tracked_rate={tracking.get('right_hand_tracked_rate')} "
                f"xr_frame_valid_rate={tracking.get('xr_frame_valid_rate')}"
            ),
        }
    )
    results.append(
        {
            "id": "H8",
            "name": "visual perspective/HMD camera perceived mismatch",
            "status": "UNKNOWN",
            "detail": "Requires live HMD/monitor six-direction validation with target/current visual markers.",
        }
    )
    results.append(
        {
            "id": "H10",
            "name": "rotation/orientation mapping interferes with insertion",
            "status": "UNKNOWN",
            "detail": "Position mapping analysis does not prove rotation mapping; run a separate orientation/alignment test.",
        }
    )
    return results


def recommendations(report: dict[str, Any]) -> list[str]:
    items: list[str] = []
    command_response = report["response"]["command_to_next_eef_delta"]
    if command_response.get("overall_sample_count", 0) < 12:
        items.append(
            "Run a longer controlled six-direction HMD test; this trajectory has too few nonzero command samples."
        )
    for axis, axis_report in command_response["axis"].items():
        ratio = axis_report.get("sign_agree_ratio")
        if ratio is not None and ratio < 0.70:
            items.append(
                f"Inspect {axis}-axis mapping/control response; command-to-EEF sign agreement is {ratio:.2f}."
            )
    if report["dead_hand"].get("command_nonzero_ratio", 0.0):
        items.append(
            "Inspect dead-hand behavior; near-zero hand_delta still produced command motion."
        )
    if report["deadzone_boundary"].get("target_jump_count", 0):
        items.append(
            "Rebase the bounded direct-EE anchor before leaving deadzone; target jumps on deadzone exit."
        )
    if report["deadzone_boundary"].get("entry_snap_count", 0):
        items.append(
            "Deadzone entry snapped the target back to the current EEF; treat this as expected unless motion resumes from a stale target."
        )
    anchor_fallback = report["anchor_fallback"]
    if anchor_fallback.get("raw_wrist_jump_gt_10cm_valid_to_valid_count", 0):
        items.append(
            "Gate or debounce implausible valid-to-valid wrist pose jumps before tuning axis maps; hand tracking is reporting large discontinuities while still marked valid."
        )
    if anchor_fallback.get("anchor_like_valid_frame_count", 0):
        items.append(
            "Reject configured XR anchor fallback poses as invalid hand tracking and gate robot control while they occur."
        )
    elif anchor_fallback.get("anchor_like_invalid_frame_count", 0):
        items.append(
            "Configured XR anchor fallback poses were gated invalid; inspect tracking-loss duration and rebase control on tracking resume."
        )
    if report["target_accumulation"].get("accumulation_warn"):
        items.append(
            "Inspect target construction; desired target drifts beyond the current absolute hand offset inside a stable control segment."
        )
    if report["scene_state_discontinuity"].get("warn"):
        items.append(
            "Treat scene-state jumps as trajectory boundaries or hidden simulator resets before blaming hand/target accumulation."
        )
    if report["controller"].get("workspace_clamped_ratio"):
        items.append(
            "Repeat the debug run with smaller movements or larger debug workspace; workspace clamp was active."
        )
    if not items:
        items.append(
            "Offline mapping evidence is internally consistent; next step is live six-direction HMD validation."
        )
    return items


def analyze_trajectory(path: Path) -> dict[str, Any]:
    trajectory = load_json(path)
    frames = [
        frame for frame in trajectory.get("frames", []) if isinstance(frame, dict)
    ]
    summary = dict_or_empty(trajectory.get("summary"))
    eef = series(frames, eef_xyz)
    eef_delta = delta_series(eef)
    raw_wrist = series(frames, raw_wrist_xyz)
    raw_wrist_delta = delta_series(raw_wrist)
    raw_action = series(frames, raw_action_xyz)
    applied_action = series(frames, applied_action_xyz)
    input_delta = series(
        frames, lambda frame: list3(teleop_control_mode(frame).get("input_delta_xyz"))
    )
    hand_delta = series(
        frames, lambda frame: list3(teleop_control_mode(frame).get("hand_delta_m"))
    )
    desired_target = series(
        frames,
        lambda frame: list3(teleop_control_mode(frame).get("desired_ee_target_xyz")),
    )
    command = series(
        frames,
        lambda frame: list3(teleop_control_mode(frame).get("applied_ee_delta_m")),
    )
    config = config_summary(frames, summary)
    position_axis_map = parse_signed_axis_map(config.get("position_axis_map"))
    try:
        position_yaw_offset_deg = float(config.get("position_yaw_offset_deg") or 0.0)
    except (TypeError, ValueError):
        position_yaw_offset_deg = 0.0
    raw_action_yaw_mapped = yaw_series(raw_action, position_yaw_offset_deg)
    raw_action_axis_mapped = remap_series(raw_action_yaw_mapped, position_axis_map)

    command_norms = numeric_tcm_series(frames, "command_step_norm")
    max_step_values = [teleop_control_mode(frame).get("max_step_m") for frame in frames]
    max_step_m = next(
        (float(value) for value in max_step_values if isinstance(value, (int, float))),
        None,
    )
    saturation_ratio = None
    if max_step_m and command_norms:
        saturation_ratio = sum(
            1 for value in command_norms if value >= max_step_m * 0.95
        ) / len(command_norms)

    report: dict[str, Any] = {
        "schema_version": "rdf_hmd_motion_mapping_analysis_v0.1.0",
        "path": str(path),
        "trajectory_id": trajectory.get("id"),
        "episode_id": trajectory.get("episode_id"),
        "task_id": trajectory.get("task_id"),
        "episode_status": summary.get("episode_status"),
        "frame_count": len(frames),
        "source": trajectory.get("source")
        if isinstance(trajectory.get("source"), dict)
        else {},
        "config": config,
        "series": {
            "raw_wrist_delta": vector_stats(raw_wrist_delta),
            "raw_action_xyz": vector_stats(raw_action),
            "applied_action_xyz": vector_stats(applied_action),
            "input_delta_xyz": vector_stats(input_delta),
            "hand_delta_m": vector_stats(hand_delta),
            "desired_ee_target_xyz": vector_stats(desired_target),
            "applied_ee_delta_m": vector_stats(command),
            "actual_eef_delta": vector_stats(eef_delta),
        },
        "response": {
            "raw_action_axis_mapped_to_input_delta": response_stats(
                raw_action_axis_mapped,
                input_delta,
                command_label="raw_action_axis_mapped",
                response_label="input_delta_xyz",
            ),
            "raw_wrist_delta_to_input_delta_unmapped": response_stats(
                raw_wrist_delta,
                input_delta,
                command_label="raw_wrist_delta",
                response_label="input_delta_xyz",
            ),
            "raw_wrist_delta_to_input_delta": response_stats(
                raw_wrist_delta,
                input_delta,
                command_label="raw_wrist_delta",
                response_label="input_delta_xyz",
            ),
            "input_delta_to_command": response_stats(
                input_delta,
                command,
                command_label="input_delta_xyz",
                response_label="applied_ee_delta_m",
            ),
            "command_to_same_frame_eef_delta": response_stats(
                command,
                eef_delta,
                command_label="applied_ee_delta_m",
                response_label="eef_delta_prev_to_current",
            ),
            "command_to_next_eef_delta": response_stats(
                command[:-1],
                eef_delta[1:],
                command_label="applied_ee_delta_m",
                response_label="eef_delta_current_to_next",
            ),
        },
        "controller": {
            "command_step_norm": scalar_stats(command_norms),
            "target_error_norm": scalar_stats(
                numeric_tcm_series(frames, "target_error_norm")
            ),
            "workspace_clamped_ratio": bool_tcm_ratio(frames, "workspace_clamped"),
            "command_saturation_ratio": saturation_ratio,
        },
        "calibration": calibration_summary(summary),
        "dead_hand": dead_hand_stats(frames),
        "deadzone_boundary": deadzone_boundary_stats(frames),
        "anchor_fallback": anchor_fallback_stats(frames),
        "target_accumulation": target_accumulation_stats(frames),
        "scene_state_discontinuity": scene_state_discontinuity_stats(frames),
        "provenance_timeline": provenance_timeline_stats(frames),
        "tracking_quality": tracking_quality(frames),
    }
    report["hypotheses"] = hypothesis_results(report)
    report["recommendations"] = recommendations(report)
    return report


def aggregate_report(reports: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "trajectory_count": len(reports),
        "total_frames": sum(int(report.get("frame_count") or 0) for report in reports),
        "trajectory_ids": [report.get("trajectory_id") for report in reports],
        "warning_or_fail_count": sum(
            1
            for report in reports
            for item in report.get("hypotheses", [])
            if item.get("status") in {"WARN", "FAIL"}
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze HMD handtracking-to-robot EEF motion mapping."
    )
    parser.add_argument(
        "paths", nargs="*", type=Path, help="Trajectory JSON files to analyze."
    )
    parser.add_argument(
        "--storage-root",
        type=Path,
        default=DEFAULT_STORAGE_ROOT,
        help="Storage root for --latest.",
    )
    parser.add_argument(
        "--latest", action="store_true", help="Analyze the latest non-empty trajectory."
    )
    parser.add_argument(
        "--include-empty-latest",
        action="store_true",
        help="With --latest, inspect the newest file even if it has zero frames.",
    )
    parser.add_argument(
        "--pretty", action="store_true", help="Pretty-print JSON output."
    )
    parser.add_argument(
        "--output", type=Path, help="Optional path to write the JSON report."
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    paths = list(args.paths)
    if args.latest:
        paths.append(
            latest_trajectory_path(
                args.storage_root, include_empty=args.include_empty_latest
            )
        )
    if not paths:
        raise SystemExit("Provide at least one trajectory JSON path or pass --latest.")

    reports = [analyze_trajectory(path) for path in paths]
    output = {
        "schema_version": "rdf_hmd_motion_mapping_analysis_v0.1.0",
        "aggregate": aggregate_report(reports),
        "trajectories": reports,
    }
    text = (
        json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True)
        if args.pretty
        else stable_json(output)
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
