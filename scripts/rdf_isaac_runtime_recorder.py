#!/usr/bin/env python3
"""Runtime recorder hook for Isaac Lab teleoperation.

This module is intentionally standard-library only. It is imported from the
Isaac Sim Python process, not from the Robot Data Forge uv environment.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import math
import os
import time
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

SCHEMA_VERSION = "0.1.0"
STACK_BLOCK_HEIGHT_M = 0.0406
DEFAULT_XR_POSE = [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0]
DEFAULT_XR_ANCHOR_POS = [-0.1, -0.5, -1.05]
XR_JOINTS_TO_LOG = ("wrist", "palm", "thumb_tip", "index_tip")
INSERTION_TASK_MARKERS = ("peg", "hole", "insert", "connector")
TELEOP_PIPELINE_SCHEMA_VERSION = "rdf_xr_teleop_dataset_pipeline_v0.1.0"
INPUT_SIGNAL_STATE_SCHEMA_VERSION = "rdf_input_signal_state_v0.1.0"
INPUT_TRUTH_CLASSIFICATION_SCHEMA_VERSION = "rdf_input_truth_classification_v0.1.0"
DEFAULT_INSERTION_SUCCESS_CRITERIA = {
    "task_type": "peg_in_hole",
    "peg_tip_distance_to_target_max": 0.015,
    "peg_axis_alignment_error_max_rad": 0.25,
    "insertion_depth_min": 0.025,
    "min_stable_steps": 4,
    "max_completion_time_sec": 45.0,
    "max_tracking_loss_after_warmup": 0.25,
    "max_retargeting_jump": 1.50,
    "max_average_input_latency_ms": 80.0,
    "max_frame_interval_jitter_ms": 25.0,
    "max_collision_count": 1,
}


def post_json(
    api_base: str, path: str, payload: dict[str, Any], timeout: float = 20.0
) -> dict[str, Any]:
    request = Request(
        f"{api_base.rstrip('/')}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}
    except HTTPError as exc:
        body = exc.read().decode("utf-8")
        raise RuntimeError(f"POST {path} failed: {exc.code} {body}") from exc


def _as_python(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "detach"):
        value = value.detach()
    if hasattr(value, "cpu"):
        value = value.cpu()
    if hasattr(value, "tolist"):
        return value.tolist()
    return value


def _select(value: Any, *indices: int) -> Any:
    data = _as_python(value)
    for index in indices:
        if isinstance(data, (list, tuple)) and len(data) > index:
            data = data[index]
        else:
            return None
    return data


def _float_list(value: Any) -> list[float]:
    data = _as_python(value)
    if data is None:
        return []
    if isinstance(data, (int, float)):
        return [float(data)]
    if isinstance(data, (list, tuple)):
        result: list[float] = []
        for item in data:
            if isinstance(item, (list, tuple)):
                result.extend(_float_list(item))
            else:
                try:
                    result.append(float(item))
                except (TypeError, ValueError):
                    continue
        return result
    return []


def _flatten_bool_values(value: Any) -> list[bool]:
    data = _as_python(value)
    if data is None:
        return []
    if isinstance(data, bool):
        return [data]
    if isinstance(data, (int, float)):
        return [bool(data)]
    if isinstance(data, (list, tuple)):
        values: list[bool] = []
        for item in data:
            values.extend(_flatten_bool_values(item))
        return values
    return []


def _bool_signal_summary(value: Any) -> dict[str, Any]:
    values = _flatten_bool_values(value)
    if not values:
        return {
            "available": False,
            "any": False,
            "all": False,
            "true_count": 0,
            "count": 0,
        }
    true_count = sum(1 for item in values if item)
    return {
        "available": True,
        "any": true_count > 0,
        "all": true_count == len(values),
        "true_count": true_count,
        "count": len(values),
    }


def _info_keys(info: Any) -> list[str]:
    data = _as_python(info)
    if isinstance(data, dict):
        return sorted(str(key) for key in data.keys())
    if isinstance(data, (list, tuple)):
        keys: set[str] = set()
        for item in data:
            if isinstance(item, dict):
                keys.update(str(key) for key in item.keys())
        return sorted(keys)
    return []


def _env_step_boundary_metadata(env_step_result: Any | None) -> dict[str, Any]:
    """Summarize Isaac/Gymnasium step boundary signals for trajectory evidence."""

    if env_step_result is None:
        return {
            "schema_version": "rdf_sim_step_boundary_v0.1.0",
            "source": "not_available",
            "env_step_return_available": False,
            "terminated": _bool_signal_summary(None),
            "truncated": _bool_signal_summary(None),
            "done": _bool_signal_summary(None),
            "reset_boundary": False,
            "reset_boundary_reason": None,
            "info_keys": [],
        }

    terminated = None
    truncated = None
    done = None
    info = None
    if isinstance(env_step_result, dict):
        terminated = env_step_result.get("terminated")
        truncated = env_step_result.get("truncated")
        done = env_step_result.get("done")
        info = env_step_result.get("info")
    elif isinstance(env_step_result, (list, tuple)):
        if len(env_step_result) >= 5:
            terminated = env_step_result[2]
            truncated = env_step_result[3]
            info = env_step_result[4]
        elif len(env_step_result) >= 4:
            done = env_step_result[2]
            info = env_step_result[3]

    terminated_summary = _bool_signal_summary(terminated)
    truncated_summary = _bool_signal_summary(truncated)
    done_summary = _bool_signal_summary(done)
    if not done_summary["available"] and (
        terminated_summary["available"] or truncated_summary["available"]
    ):
        done_summary = {
            "available": True,
            "any": bool(terminated_summary["any"] or truncated_summary["any"]),
            "all": bool(
                (
                    terminated_summary["all"]
                    if terminated_summary["available"]
                    else False
                )
                or (
                    truncated_summary["all"]
                    if truncated_summary["available"]
                    else False
                )
            ),
            "true_count": max(
                int(terminated_summary["true_count"]),
                int(truncated_summary["true_count"]),
            ),
            "count": max(
                int(terminated_summary["count"]), int(truncated_summary["count"])
            ),
        }

    reasons = []
    if terminated_summary["any"]:
        reasons.append("terminated")
    if truncated_summary["any"]:
        reasons.append("truncated")
    if done_summary["any"] and not reasons:
        reasons.append("done")
    return {
        "schema_version": "rdf_sim_step_boundary_v0.1.0",
        "source": "isaac_env_step_return",
        "env_step_return_available": True,
        "terminated": terminated_summary,
        "truncated": truncated_summary,
        "done": done_summary,
        "reset_boundary": bool(reasons),
        "reset_boundary_reason": "+".join(reasons) if reasons else None,
        "info_keys": _info_keys(info),
    }


def _env_text(name: str, default: str) -> str:
    value = os.environ.get(name)
    if value is None or not value.strip():
        return default
    return value.strip()


def _env_float(name: str, default: float) -> float:
    value = os.environ.get(name)
    if value is None or not value.strip():
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _parse_vector3(value: str | None, default: list[float]) -> list[float]:
    if value is None or not value.strip():
        return list(default)
    parts = [part.strip() for part in value.split(",")]
    if len(parts) != 3:
        return list(default)
    try:
        return [float(part) for part in parts]
    except ValueError:
        return list(default)


def _vec_add(left: list[float], right: list[float]) -> list[float]:
    return (
        [float(a) + float(b) for a, b in zip(left, right, strict=True)]
        if len(left) == len(right) == 3
        else []
    )


def _vec_sub(left: list[float], right: list[float]) -> list[float]:
    return (
        [float(a) - float(b) for a, b in zip(left, right, strict=True)]
        if len(left) == len(right) == 3
        else []
    )


def _vec_scale(vector: list[float], scalar: float) -> list[float]:
    return (
        [float(value) * float(scalar) for value in vector] if len(vector) == 3 else []
    )


def _vec_dot(left: list[float], right: list[float]) -> float | None:
    if len(left) != 3 or len(right) != 3:
        return None
    return sum(float(a) * float(b) for a, b in zip(left, right, strict=True))


def _vec_norm(vector: list[float]) -> float | None:
    if len(vector) != 3:
        return None
    return math.sqrt(sum(float(value) * float(value) for value in vector))


def _vec_normalize(
    vector: list[float], fallback: list[float] | None = None
) -> list[float]:
    norm = _vec_norm(vector)
    if norm is None or norm <= 1e-9:
        return list(fallback or [])
    return [float(value) / norm for value in vector]


def _angle_between(left: list[float], right: list[float]) -> float | None:
    left_unit = _vec_normalize(left)
    right_unit = _vec_normalize(right)
    if len(left_unit) != 3 or len(right_unit) != 3:
        return None
    dot = _vec_dot(left_unit, right_unit)
    if dot is None:
        return None
    return math.acos(max(-1.0, min(1.0, dot)))


def _clamp01(value: float) -> float:
    if math.isnan(value):
        return 0.0
    return max(0.0, min(1.0, value))


def _pose_is_default(pose: list[float]) -> bool:
    return len(pose) == 7 and all(
        abs(a - b) <= 1e-6 for a, b in zip(pose, DEFAULT_XR_POSE, strict=True)
    )


def _configured_xr_anchor_pos() -> list[float]:
    return _parse_vector3(os.environ.get("RDF_XR_ANCHOR_POS"), DEFAULT_XR_ANCHOR_POS)


def _pose_matches_configured_xr_anchor(
    pose: list[float], tolerance: float = 1.0e-4
) -> bool:
    if len(pose) < 3:
        return False
    anchor = _configured_xr_anchor_pos()
    return all(
        abs(float(pose[index]) - anchor[index]) <= tolerance for index in range(3)
    )


def _pose_is_valid(pose: list[float]) -> bool:
    if len(pose) != 7:
        return False
    if any(not math.isfinite(float(value)) for value in pose[:7]):
        return False
    return not _pose_is_default(pose) and not _pose_matches_configured_xr_anchor(pose)


def _scene_get(env: Any, name: str) -> Any:
    scene = getattr(env, "scene", None)
    if scene is None:
        return None
    try:
        return scene[name]
    except Exception:
        return None


def _env_origin(env: Any) -> list[float]:
    origins = getattr(getattr(env, "scene", None), "env_origins", None)
    return _float_list(_select(origins, 0))[:3]


def _direct_env_pose(env: Any, name: str) -> tuple[list[float], list[float]]:
    aliases = {
        "held_asset": ("held_pos", "held_quat"),
        "peg": ("held_pos", "held_quat"),
        "fixed_asset": ("fixed_pos", "fixed_quat"),
        "hole": ("fixed_pos", "fixed_quat"),
    }
    pos_attr, quat_attr = aliases.get(name, ("", ""))
    if not pos_attr:
        return [], []
    position = _float_list(_select(getattr(env, pos_attr, None), 0))[:3]
    quaternion = _float_list(_select(getattr(env, quat_attr, None), 0))[:4]
    if len(position) == 3:
        origin = _env_origin(env)
        if len(origin) == 3:
            position = _vec_add(position, origin)
    return position, quaternion


def _asset_pose(env: Any, name: str) -> tuple[list[float], list[float]]:
    asset = _scene_get(env, name)
    data = getattr(asset, "data", None)
    if data is not None:
        position = _float_list(_select(getattr(data, "root_pos_w", None), 0))[:3]
        quaternion = _float_list(_select(getattr(data, "root_quat_w", None), 0))[:4]
        if len(position) == 3:
            return position, quaternion
    position, quaternion = _direct_env_pose(env, name)
    return position, quaternion


def _end_effector_pose(env: Any) -> tuple[list[float], list[float]]:
    ee_frame = _scene_get(env, "ee_frame")
    data = getattr(ee_frame, "data", None)
    if data is not None:
        position = _float_list(_select(getattr(data, "target_pos_w", None), 0, 0))[:3]
        quaternion = _float_list(_select(getattr(data, "target_quat_w", None), 0, 0))[
            :4
        ]
        if len(position) == 3:
            return position, quaternion
    position = _float_list(_select(getattr(env, "fingertip_midpoint_pos", None), 0))[:3]
    quaternion = _float_list(_select(getattr(env, "fingertip_midpoint_quat", None), 0))[
        :4
    ]
    if len(position) == 3:
        origin = _env_origin(env)
        if len(origin) == 3:
            position = _vec_add(position, origin)
    return position, quaternion


def _cube_states(env: Any) -> dict[str, dict[str, list[float]]]:
    states: dict[str, dict[str, list[float]]] = {}
    for cube_name in ("cube_1", "cube_2", "cube_3"):
        position, quaternion = _asset_pose(env, cube_name)
        states[cube_name] = {"position": position, "quaternion": quaternion}
    return states


def stack_target_position(env: Any) -> list[float]:
    cube_1_position, _ = _asset_pose(env, "cube_1")
    if len(cube_1_position) == 3:
        return [
            round(cube_1_position[0], 6),
            round(cube_1_position[1], 6),
            round(cube_1_position[2] + STACK_BLOCK_HEIGHT_M, 6),
        ]
    return [0.4, 0.0, 0.0609]


def _tracking_gate_input_signal_state(
    control_filter: dict[str, Any],
    gate_reason: str,
) -> dict[str, Any]:
    anchor_fallback = bool(control_filter.get("right_wrist_anchor_fallback", False))
    primary_reason = "ANCHOR_FALLBACK_POSE" if anchor_fallback else str(gate_reason)
    reason_codes = ["TRACKING_GATE_HOLD", str(gate_reason)]
    if anchor_fallback:
        reason_codes.append("ANCHOR_FALLBACK_POSE")
    classification = {
        "schema_version": INPUT_TRUTH_CLASSIFICATION_SCHEMA_VERSION,
        "truth_state": "invalid",
        "primary_reason": primary_reason,
        "frame_reason_codes": list(dict.fromkeys(reason_codes)),
        "sample_valid": False,
        "tracking_valid": False,
        "timestamp_state": "not_available",
        "confidence_state": "not_available",
        "position_truth_state": "anchor_fallback" if anchor_fallback else "missing",
        "action_hold_required": True,
        "resume_block": True,
        "recenter_block": True,
        "allow_authority": False,
    }
    return {
        "schema_version": INPUT_SIGNAL_STATE_SCHEMA_VERSION,
        "source_id": "quest_openxr_handtracking",
        "source_kind": "handtracking",
        "runtime": "steamvr_openxr",
        "device": "quest3",
        "input_channel": "right_wrist",
        "timestamp_source": "not_available_live_openxr_cache",
        "input_latency_ms": None,
        "input_latency_source": "not_available",
        "tracking_confidence": None,
        "tracking_confidence_source": "not_available",
        "sample_valid": False,
        "tracking_valid": False,
        "control_safe": False,
        "control_safety_flags": ["tracking_gate_hold", "action_hold"],
        "action_hold": True,
        "hold_reason": str(gate_reason),
        "tracking_epoch_id": control_filter.get("tracking_epoch_id"),
        "tracking_epoch_state": control_filter.get("tracking_epoch_state") or "invalid",
        "learning_label_eligible": False,
        "learning_label_ineligible_reason": str(gate_reason),
        "quality_flags": ["tracking_gate_hold"],
        "input_truth_classification": classification,
        "input_truth_control_state": {
            "action_hold": True,
            "hold_reason": str(gate_reason),
            "resume_block": True,
            "resume_block_reason": primary_reason,
            "recenter_block": True,
            "recenter_block_reason": primary_reason,
            "allow_authority": False,
        },
    }


def _input_signal_state_from_control_mode(
    control_mode: dict[str, Any],
    raw_wrist_direct: Any,
) -> dict[str, Any] | None:
    candidates = []
    if isinstance(raw_wrist_direct, dict):
        candidates.append(raw_wrist_direct.get("input_signal_state"))
    candidates.append(control_mode.get("input_signal_state"))
    for candidate in candidates:
        if isinstance(candidate, dict):
            return candidate
    return None


def _learning_action_eligibility(
    *,
    teleoperation_active: bool,
    control_mode: dict[str, Any],
    raw_wrist_direct: Any,
    input_signal_state: dict[str, Any] | None,
) -> tuple[bool, str | None]:
    if (
        isinstance(raw_wrist_direct, dict)
        and raw_wrist_direct.get("gate_state") == "held"
    ):
        return False, str(raw_wrist_direct.get("gate_reason") or "raw_wrist_held")

    if isinstance(input_signal_state, dict):
        if input_signal_state.get("learning_label_eligible") is False:
            return False, str(
                input_signal_state.get("learning_label_ineligible_reason")
                or input_signal_state.get("hold_reason")
                or "input_signal_state_ineligible"
            )
        if input_signal_state.get("control_safe") is False:
            return False, str(
                input_signal_state.get("hold_reason") or "input_not_control_safe"
            )

    if control_mode.get("direct_control_apply") is False:
        return False, str(
            control_mode.get("gate_reason")
            or control_mode.get("tracking_gate_reason")
            or "direct_control_not_applied"
        )

    if not teleoperation_active:
        return False, "teleoperation_inactive"

    return True, None


def _action_payload(
    action: Any,
    teleoperation_active: bool,
    raw_action: Any | None = None,
    control_filter: dict[str, Any] | None = None,
) -> dict[str, Any]:
    applied = _float_list(action)
    raw = _float_list(raw_action) if raw_action is not None else list(applied)
    action_type = (
        "delta_ee_pose_plus_gripper" if len(applied) >= 7 else "teleop_command"
    )
    intent_action_type = (
        "openxr_retargeted_delta_ee_pose_plus_gripper"
        if len(raw) >= 7
        else "teleop_command"
    )
    control_mode = _teleop_control_mode(control_filter)
    raw_wrist_direct = control_mode.get("raw_wrist_direct_control")
    input_signal_state = _input_signal_state_from_control_mode(
        control_mode, raw_wrist_direct
    )
    learning_eligible, learning_ineligible_reason = _learning_action_eligibility(
        teleoperation_active=teleoperation_active,
        control_mode=control_mode,
        raw_wrist_direct=raw_wrist_direct,
        input_signal_state=input_signal_state,
    )
    raw_wrist_direct_mode = control_mode.get("name") == "raw_wrist_direct_ee_target"
    raw_wrist_retargeted_action = (
        raw_wrist_direct.get("retargeted_action_for_comparison")
        if isinstance(raw_wrist_direct, dict)
        else None
    )
    retargeted_robot_command = (
        _float_list(raw_wrist_retargeted_action)
        if raw_wrist_direct_mode and raw_wrist_retargeted_action is not None
        else (raw if raw_wrist_direct_mode else applied)
    )
    relative: dict[str, Any] = {}
    if len(applied) >= 3:
        relative["delta_position"] = applied[:3]
    if len(applied) >= 6:
        relative["delta_rotation"] = applied[3:6]
    if applied:
        relative["gripper"] = applied[-1]
    payload = {
        "raw": raw,
        "applied": applied,
        "teleoperation_active": bool(teleoperation_active),
        "pinch_or_gripper": applied[-1] if applied else None,
        "relative": relative,
        "action_contract_version": control_mode.get("action_contract_version")
        or "rdf_action_contract_v0.1.0",
        "replay_contract_version": control_mode.get("replay_contract_version")
        or "rdf_replay_contract_v0.1.0",
        "desired_end_effector_pose": control_mode.get("desired_end_effector_pose"),
        "applied_end_effector_action": control_mode.get("applied_end_effector_action"),
        "native_isaac_action": control_mode.get("native_isaac_action") or applied,
        "raw_wrist_direct": raw_wrist_direct,
        "teleop_intent": {
            "command": raw,
            "role": "operator_intent",
            "representation": intent_action_type,
            "source": "teleop_interface.advance",
            "coordinate_frame": "openxr_retargeter_output",
        },
        "executed_control": {
            "command": applied,
            "role": "robot_control_command",
            "representation": action_type,
            "source": "rdf_live_teleop_controller",
            "control_mode": control_mode.get("name") or "native_env_action",
            "control_semantics": control_mode.get("control_semantics")
            or "env_action_command",
            "applied_to_env": bool(teleoperation_active),
            "desired_end_effector_pose": control_mode.get("desired_end_effector_pose"),
            "applied_end_effector_action": control_mode.get(
                "applied_end_effector_action"
            ),
            "native_isaac_action": control_mode.get("native_isaac_action") or applied,
            "action_contract_version": control_mode.get("action_contract_version")
            or "rdf_action_contract_v0.1.0",
            "replay_contract_version": control_mode.get("replay_contract_version")
            or "rdf_replay_contract_v0.1.0",
        },
        "learning_action": {
            "command": control_mode.get("applied_end_effector_action", {}).get(
                "delta_position", applied
            )
            if isinstance(control_mode.get("applied_end_effector_action"), dict)
            else applied,
            "role": "candidate_robot_action_for_learning",
            "representation": "desired_applied_end_effector_action"
            if control_mode.get("name")
            in {"bounded_direct_ee_target", "raw_wrist_direct_ee_target"}
            else action_type,
            "source": "executed_control",
            "validation_state": "requires_evaluation_and_curation",
            "dataset_semantics": "not_learning_ready_until_curated",
            "eligible": bool(learning_eligible),
            "eligibility_scope": "frame",
            "ineligible_reason": learning_ineligible_reason,
            "control_safe_required": True,
            "action_contract_version": control_mode.get("action_contract_version")
            or "rdf_action_contract_v0.1.0",
        },
        "retargeted_robot_action": {
            "command": retargeted_robot_command,
            "action_type": action_type,
            "source": "teleop_interface.advance",
            "applied_to_env": bool(teleoperation_active and not raw_wrist_direct_mode),
            "used_for_comparison": bool(raw_wrist_direct_mode),
        },
    }
    if input_signal_state is not None:
        payload["input_signal_state"] = input_signal_state
    if control_filter is not None:
        payload["control_filter"] = control_filter
    return payload


def _teleop_control_mode(control_filter: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(control_filter, dict):
        return {}
    for key in ("teleop_control_mode", "action_adapter"):
        value = control_filter.get(key)
        if isinstance(value, dict):
            return value
    selected_mode = control_filter.get("selected_teleop_control_mode")
    if selected_mode != "raw_wrist_direct_ee_target":
        return {}

    config = control_filter.get("raw_wrist_direct_config")
    if not isinstance(config, dict):
        config = (
            control_filter.get("config")
            if isinstance(control_filter.get("config"), dict)
            else {}
        )
    gate_reason = (
        control_filter.get("tracking_gate_reason")
        or control_filter.get("gate_reason")
        or "tracking_gate_hold"
    )
    raw_wrist_direct_control: dict[str, Any] = {
        "input_source": "raw_right_wrist_pose",
        "gate_state": "held",
        "gate_reason": gate_reason,
        "translation_mode": "held_by_tracking_gate",
        "raw_wrist_pose": _float_list(control_filter.get("right_wrist_pose")) or None,
        "right_wrist_anchor_fallback": bool(
            control_filter.get("right_wrist_anchor_fallback", False)
        ),
        "tracking_resume_progress": control_filter.get("tracking_resume_progress"),
        "position_axis_map": config.get("position_axis_map", "x,z,y"),
        "position_yaw_offset_deg": float(
            config.get("position_yaw_offset_deg", 0.0) or 0.0
        ),
        "input_signal_state": _tracking_gate_input_signal_state(
            control_filter, str(gate_reason)
        ),
    }
    retargeted_action = control_filter.get("retargeted_action_for_comparison")
    if retargeted_action is not None:
        raw_wrist_direct_control["retargeted_action_for_comparison"] = _float_list(
            retargeted_action
        )
    return {
        "name": "raw_wrist_direct_ee_target",
        "preset": "raw_wrist_direct_ee_target",
        "control_semantics": "raw_wrist_bounded_direct_end_effector_target_servo",
        "direct_control_apply": False,
        "action_contract_version": "rdf_action_contract_v0.2.0",
        "replay_contract_version": "rdf_replay_contract_v0.2.0",
        "applied_end_effector_action": {
            "delta_position": [0.0, 0.0, 0.0],
            "delta_rotation": [0.0, 0.0, 0.0],
            "frame": "isaac_world",
            "gate_reason": gate_reason,
        },
        "native_isaac_action": control_filter.get("held_native_isaac_action"),
        "raw_wrist_direct_control": raw_wrist_direct_control,
    }


def _tracking_hold_reason_from_control_filter(
    control_filter: dict[str, Any] | None,
) -> str | None:
    if not isinstance(control_filter, dict):
        return None
    direct_reason = control_filter.get("tracking_gate_reason") or control_filter.get(
        "gate_reason"
    )
    if direct_reason:
        return str(direct_reason)
    control_mode = _teleop_control_mode(control_filter)
    raw_wrist_direct = control_mode.get("raw_wrist_direct_control")
    if (
        isinstance(raw_wrist_direct, dict)
        and raw_wrist_direct.get("gate_state") == "held"
    ):
        return str(raw_wrist_direct.get("gate_reason") or "tracking_gate_hold")
    return None


def _pose_from_dict(data: Any, key: str) -> list[float]:
    if isinstance(data, dict) and key in data:
        return _float_list(data[key])[:7]
    return []


def _selected_joint_poses(data: Any) -> dict[str, list[float]]:
    if not isinstance(data, dict):
        return {}
    joints: dict[str, list[float]] = {}
    for key in XR_JOINTS_TO_LOG:
        pose = _pose_from_dict(data, key)
        if pose:
            joints[key] = pose
    return joints


def _head_pose(teleop_interface: Any) -> list[float]:
    return _float_list(getattr(teleop_interface, "_previous_headpose", None))[:7]


def _quat_normalize_wxyz(quat: list[float]) -> list[float]:
    if len(quat) != 4:
        return []
    norm = math.sqrt(sum(float(value) * float(value) for value in quat))
    if norm <= 1e-9:
        return [1.0, 0.0, 0.0, 0.0]
    return [float(value) / norm for value in quat]


def _quat_inverse_wxyz(quat: list[float]) -> list[float]:
    normalized = _quat_normalize_wxyz(quat)
    if len(normalized) != 4:
        return []
    return [normalized[0], -normalized[1], -normalized[2], -normalized[3]]


def _quat_multiply_wxyz(left: list[float], right: list[float]) -> list[float]:
    left = _quat_normalize_wxyz(left)
    right = _quat_normalize_wxyz(right)
    if len(left) != 4 or len(right) != 4:
        return []
    lw, lx, ly, lz = left
    rw, rx, ry, rz = right
    return _quat_normalize_wxyz(
        [
            lw * rw - lx * rx - ly * ry - lz * rz,
            lw * rx + lx * rw + ly * rz - lz * ry,
            lw * ry - lx * rz + ly * rw + lz * rx,
            lw * rz + lx * ry - ly * rx + lz * rw,
        ]
    )


def _quat_multiply_raw_wxyz(left: list[float], right: list[float]) -> list[float]:
    if len(left) != 4 or len(right) != 4:
        return []
    lw, lx, ly, lz = [float(value) for value in left]
    rw, rx, ry, rz = [float(value) for value in right]
    return [
        lw * rw - lx * rx - ly * ry - lz * rz,
        lw * rx + lx * rw + ly * rz - lz * ry,
        lw * ry - lx * rz + ly * rw + lz * rx,
        lw * rz + lx * ry - ly * rx + lz * rw,
    ]


def _quat_rotate_vector_wxyz(quat: list[float], vector: list[float]) -> list[float]:
    if len(vector) != 3:
        return []
    vector_quat = [0.0, float(vector[0]), float(vector[1]), float(vector[2])]
    normalized = _quat_normalize_wxyz(quat)
    rotated = _quat_multiply_raw_wxyz(
        _quat_multiply_raw_wxyz(normalized, vector_quat),
        _quat_inverse_wxyz(normalized),
    )
    return rotated[1:4] if len(rotated) == 4 else []


def _task_type_from_env_or_name(isaac_task_name: str) -> str:
    explicit = _env_text("RDF_TASK_TYPE", "").lower()
    if explicit:
        return explicit
    lower_name = str(isaac_task_name or "").lower()
    if any(marker in lower_name for marker in INSERTION_TASK_MARKERS):
        return "peg_in_hole"
    return "franka_stack_smoke_test"


def _is_insertion_task_type(task_type: str) -> bool:
    text = task_type.lower()
    return any(marker in text for marker in INSERTION_TASK_MARKERS)


def _task_state_config(
    task_type: str, isaac_task_name: str = ""
) -> dict[str, Any] | None:
    if not _is_insertion_task_type(task_type):
        return None
    direct_factory_task = any(
        marker in str(isaac_task_name or "").lower() for marker in ("factory", "forge")
    )
    default_peg_asset = "held_asset" if direct_factory_task else "peg"
    default_hole_asset = "fixed_asset" if direct_factory_task else "hole"
    return {
        "task_type": task_type,
        "peg_asset_name": _env_text(
            "RDF_PEG_ASSET_NAME", _env_text("RDF_PEG_ASSET", default_peg_asset)
        ),
        "hole_asset_name": _env_text(
            "RDF_HOLE_ASSET_NAME", _env_text("RDF_HOLE_ASSET", default_hole_asset)
        ),
        "peg_tip_local_offset": _parse_vector3(
            os.environ.get("RDF_PEG_TIP_LOCAL_OFFSET"), [0.0, 0.0, 0.0]
        ),
        "hole_target_local_offset": _parse_vector3(
            os.environ.get("RDF_HOLE_TARGET_LOCAL_OFFSET"), [0.0, 0.0, 0.0]
        ),
        "peg_axis_local": _parse_vector3(
            os.environ.get("RDF_PEG_AXIS_LOCAL"), [0.0, 0.0, -1.0]
        ),
        "hole_axis_local": _parse_vector3(
            os.environ.get("RDF_HOLE_AXIS_LOCAL"), [0.0, 0.0, -1.0]
        ),
        "insertion_axis_world": _vec_normalize(
            _parse_vector3(
                os.environ.get("RDF_INSERTION_AXIS_WORLD"), [0.0, 0.0, -1.0]
            ),
            [0.0, 0.0, -1.0],
        ),
        "success_criteria": {
            **DEFAULT_INSERTION_SUCCESS_CRITERIA,
            "peg_tip_distance_to_target_max": _env_float(
                "RDF_PEG_TIP_DISTANCE_MAX", 0.015
            ),
            "peg_axis_alignment_error_max_rad": _env_float(
                "RDF_PEG_AXIS_ALIGNMENT_MAX_RAD", 0.25
            ),
            "insertion_depth_min": _env_float("RDF_INSERTION_DEPTH_MIN", 0.025),
        },
    }


def _world_point_from_asset(
    env: Any, asset_name: str, local_offset: list[float]
) -> tuple[list[float], list[float], list[float]]:
    position, quaternion = _asset_pose(env, asset_name)
    if len(position) != 3:
        return [], [], []
    if len(quaternion) != 4:
        quaternion = [1.0, 0.0, 0.0, 0.0]
    rotated_offset = (
        _quat_rotate_vector_wxyz(quaternion, local_offset)
        if len(local_offset) == 3
        else []
    )
    point = _vec_add(position, rotated_offset or [0.0, 0.0, 0.0])
    return point, position, quaternion


def _infer_insertion_phase(
    task_state: dict[str, Any], success_criteria: dict[str, Any]
) -> str:
    distance = task_state.get("peg_lateral_distance_to_target")
    if not isinstance(distance, (int, float)):
        distance = task_state.get("peg_tip_distance_to_target")
    alignment = task_state.get("axis_alignment_error_rad")
    depth = task_state.get("insertion_depth")
    if (
        not isinstance(distance, (int, float))
        or not isinstance(alignment, (int, float))
        or not isinstance(depth, (int, float))
    ):
        return "UNKNOWN"
    distance_max = float(
        success_criteria.get("peg_tip_distance_to_target_max", 0.015) or 0.015
    )
    alignment_max = float(
        success_criteria.get("peg_axis_alignment_error_max_rad", 0.25) or 0.25
    )
    depth_min = float(success_criteria.get("insertion_depth_min", 0.025) or 0.025)
    if depth >= depth_min and distance <= distance_max and alignment <= alignment_max:
        return "SEAT"
    if depth > depth_min * 0.35:
        return "INSERT"
    if distance <= distance_max * 2.0:
        return "CONTACT"
    if alignment <= alignment_max * 1.5:
        return "ALIGN"
    return "APPROACH"


def _insertion_task_state(env: Any, config: dict[str, Any] | None) -> dict[str, Any]:
    if not config:
        return {}
    peg_tip, peg_position, peg_quaternion = _world_point_from_asset(
        env,
        str(config.get("peg_asset_name") or "peg"),
        list(config.get("peg_tip_local_offset") or [0.0, 0.0, 0.0]),
    )
    hole_target, hole_position, hole_quaternion = _world_point_from_asset(
        env,
        str(config.get("hole_asset_name") or "hole"),
        list(config.get("hole_target_local_offset") or [0.0, 0.0, 0.0]),
    )
    if len(peg_tip) != 3 or len(hole_target) != 3:
        return {}
    peg_axis = _quat_rotate_vector_wxyz(
        peg_quaternion, list(config.get("peg_axis_local") or [0.0, 0.0, -1.0])
    )
    hole_axis = _quat_rotate_vector_wxyz(
        hole_quaternion, list(config.get("hole_axis_local") or [0.0, 0.0, -1.0])
    )
    peg_axis = _vec_normalize(
        peg_axis, list(config.get("insertion_axis_world") or [0.0, 0.0, -1.0])
    )
    hole_axis = _vec_normalize(
        hole_axis, list(config.get("insertion_axis_world") or [0.0, 0.0, -1.0])
    )
    delta_to_target = _vec_sub(peg_tip, hole_target)
    distance_3d = _vec_norm(delta_to_target)
    insertion_axis = _vec_normalize(
        list(config.get("insertion_axis_world") or [0.0, 0.0, -1.0]), [0.0, 0.0, -1.0]
    )
    axial_distance_to_target = _vec_dot(delta_to_target, insertion_axis)
    lateral_distance = None
    if axial_distance_to_target is not None:
        axial_component = _vec_scale(insertion_axis, axial_distance_to_target)
        lateral_distance = _vec_norm(_vec_sub(delta_to_target, axial_component))
    depth_projection = _vec_dot(_vec_sub(peg_tip, hole_target), insertion_axis)
    alignment = _angle_between(peg_axis, hole_axis)
    success_criteria = dict(
        config.get("success_criteria") or DEFAULT_INSERTION_SUCCESS_CRITERIA
    )
    task_state = {
        "task_type": config.get("task_type", "peg_in_hole"),
        "peg_asset_name": config.get("peg_asset_name"),
        "hole_asset_name": config.get("hole_asset_name"),
        "peg_position": peg_position,
        "peg_quaternion": peg_quaternion,
        "hole_position": hole_position,
        "hole_quaternion": hole_quaternion,
        "peg_tip_position": peg_tip,
        "hole_target_position": hole_target,
        "peg_axis_vector": peg_axis,
        "hole_axis_vector": hole_axis,
        # Keep the legacy 3D distance key for backward compatibility, but use
        # lateral projection for insertion success gates.
        "peg_tip_distance_to_target": float(distance_3d)
        if distance_3d is not None
        else None,
        "peg_tip_distance_3d_to_target": float(distance_3d)
        if distance_3d is not None
        else None,
        "peg_lateral_distance_to_target": float(lateral_distance)
        if lateral_distance is not None
        else None,
        "peg_axial_distance_to_target": (
            float(axial_distance_to_target)
            if axial_distance_to_target is not None
            else None
        ),
        "peg_distance_metric": "lateral_projection",
        "axis_alignment_error_rad": float(alignment) if alignment is not None else None,
        "insertion_depth": max(0.0, float(depth_projection or 0.0)),
        "contact_count": None,
        "contact_sequence_valid": bool(
            depth_projection is not None and depth_projection > 0.0
        ),
        "object_drop_detected": False,
        "task_state_source": "isaac_scene_assets",
    }
    task_state["action_phase"] = _infer_insertion_phase(task_state, success_criteria)
    return task_state


def _alignment_pose(
    pose: list[float], calibration: dict[str, Any] | None
) -> list[float]:
    if len(pose) != 7 or not calibration:
        return []
    raw_origin_pose = calibration.get("raw_origin_pose") or []
    aligned_origin_pose = calibration.get("aligned_origin_pose") or []
    rotation_offset = calibration.get("rotation_offset_quat") or [1.0, 0.0, 0.0, 0.0]
    position_gain = float(calibration.get("position_gain") or 1.0)
    if len(raw_origin_pose) != 7 or len(aligned_origin_pose) != 7:
        translation_offset = calibration.get("translation_offset") or []
        if len(translation_offset) != 3:
            return []
        return [
            float(pose[0] + translation_offset[0]),
            float(pose[1] + translation_offset[1]),
            float(pose[2] + translation_offset[2]),
            *[float(value) for value in pose[3:7]],
        ]

    raw_delta = [
        float(pose[0] - raw_origin_pose[0]),
        float(pose[1] - raw_origin_pose[1]),
        float(pose[2] - raw_origin_pose[2]),
    ]
    aligned_delta = _quat_rotate_vector_wxyz(rotation_offset, raw_delta) or raw_delta
    aligned_quat = _quat_multiply_wxyz(rotation_offset, pose[3:7]) or pose[3:7]
    return [
        float(aligned_origin_pose[0] + aligned_delta[0] * position_gain),
        float(aligned_origin_pose[1] + aligned_delta[1] * position_gain),
        float(aligned_origin_pose[2] + aligned_delta[2] * position_gain),
        *[float(value) for value in aligned_quat[:4]],
    ]


def _apply_alignment_metadata(
    metadata: dict[str, Any], calibration: dict[str, Any] | None
) -> None:
    raw_xr = metadata.get("raw_xr") or {}
    raw_right_wrist = raw_xr.get("right_wrist_pose") or []
    aligned_right_wrist = _alignment_pose(raw_right_wrist, calibration)
    translation_offset = (calibration or {}).get("translation_offset") or []
    rotation_offset = (calibration or {}).get("rotation_offset_quat") or [
        1.0,
        0.0,
        0.0,
        0.0,
    ]
    calibration_valid = bool(calibration and aligned_right_wrist)
    metadata["aligned_xr"] = {
        "tracking_origin": "rdf_calibrated_workspace"
        if calibration_valid
        else raw_xr.get("tracking_origin"),
        "right_wrist_pose": aligned_right_wrist
        if calibration_valid
        else raw_right_wrist,
        "calibration_id": (calibration or {}).get("calibration_id"),
        "calibration_valid": calibration_valid,
        "calibration_reason": (calibration or {}).get("reason"),
        "translation_offset": translation_offset,
        "rotation_offset_quat": rotation_offset,
        "position_gain": (calibration or {}).get("position_gain", 1.0),
        "control_filter": (calibration or {}).get("control_filter"),
    }
    metadata["calibration"] = {
        "calibration_id": (calibration or {}).get("calibration_id"),
        "status": "calibrated" if calibration_valid else "uncalibrated",
        "type": (calibration or {}).get("type"),
    }


def _xr_metadata(
    teleop_interface: Any,
    action: Any,
    teleoperation_active: bool,
    sim_fps: float | None,
    raw_action: Any | None = None,
    control_filter: dict[str, Any] | None = None,
) -> dict[str, Any]:
    applied_action = _float_list(action)
    original_action = (
        _float_list(raw_action) if raw_action is not None else list(applied_action)
    )
    right_poses = getattr(teleop_interface, "_previous_joint_poses_right", {})
    left_poses = getattr(teleop_interface, "_previous_joint_poses_left", {})
    right_wrist = _pose_from_dict(right_poses, "wrist")
    left_wrist = _pose_from_dict(left_poses, "wrist")
    head_pose = _head_pose(teleop_interface)
    right_hand_tracked = _pose_is_valid(right_wrist)
    left_hand_tracked = _pose_is_valid(left_wrist)
    head_tracked = _pose_is_valid(head_pose)

    retargeted = {
        "robot_action": applied_action,
        "raw_robot_action": original_action,
        "action_type": "delta_ee_pose_plus_gripper"
        if len(applied_action) >= 7
        else "teleop_command",
        "applied_to_env": bool(teleoperation_active),
        "source": "teleop_interface.advance",
        "control_filter": control_filter,
    }
    teleop_control_mode = _teleop_control_mode(control_filter)
    return {
        "teleop_pipeline": {
            "schema_version": TELEOP_PIPELINE_SCHEMA_VERSION,
            "product_role": "xr_teleop_trajectory_to_validated_learning_dataset",
            "teleop_intent_field": "action.teleop_intent",
            "executed_control_field": "action.executed_control",
            "learning_action_field": "action.learning_action",
            "learning_action_status": "candidate_requires_evaluation_and_curation",
            "control_mode": teleop_control_mode.get("name") or "native_env_action",
            "control_semantics": teleop_control_mode.get("control_semantics")
            or "env_action_command",
        },
        "right_hand_tracked": right_hand_tracked,
        "left_hand_tracked": left_hand_tracked,
        "head_tracked": head_tracked,
        "pinch_strength": _clamp01(applied_action[-1]) if applied_action else 0.0,
        "tracking_confidence": 1.0 if right_hand_tracked else 0.0,
        "xr_frame_valid": bool(teleoperation_active and right_hand_tracked),
        "input_latency_ms": None,
        "sim_fps": sim_fps,
        "right_wrist_pose": right_wrist,
        "left_wrist_pose": left_wrist,
        "head_pose": head_pose,
        "raw_xr": {
            "tracking_origin": "steamvr_openxr_virtual_world",
            "right_wrist_pose": right_wrist,
            "left_wrist_pose": left_wrist,
            "head_pose": head_pose,
            "right_hand_joints": _selected_joint_poses(right_poses),
            "left_hand_joints": _selected_joint_poses(left_poses),
        },
        "retargeted": retargeted,
        "metadata_source": "isaac_openxr_device_cache",
    }


def build_stack_task_payload(
    isaac_task_name: str, target_position: list[float]
) -> dict[str, Any]:
    return {
        "name": "MVP-0 Franka Stack Smoke Test",
        "description": "Engineering smoke test for the Quest/OpenXR/Isaac Lab collection loop.",
        "task_type": "franka_stack_smoke_test",
        "environment_config": {
            "isaac_task_name": isaac_task_name,
            "target_position": target_position,
            "success_tolerance": 0.05,
            "target_object": "cube_2",
            "base_object": "cube_1",
        },
        "success_criteria": {
            "distance_to_target_max": 0.05,
            "min_stable_steps": 2,
            "max_completion_time_sec": 30,
            "max_collision_count": 999999,
        },
    }


def build_insertion_task_payload(
    isaac_task_name: str,
    target_position: list[float],
    task_state_config: dict[str, Any],
) -> dict[str, Any]:
    task_type = str(task_state_config.get("task_type") or "peg_in_hole")
    success_criteria = dict(
        task_state_config.get("success_criteria") or DEFAULT_INSERTION_SUCCESS_CRITERIA
    )
    return {
        "name": "MVP-1 Peg-in-Hole Live Validation",
        "description": "MVP-1A live insertion data-path task for Quest/OpenXR/Isaac Lab trajectory validation.",
        "task_type": task_type,
        "environment_config": {
            "isaac_task_name": isaac_task_name,
            "task_type": task_type,
            "target_position": target_position,
            "peg_asset_name": task_state_config.get("peg_asset_name"),
            "hole_asset_name": task_state_config.get("hole_asset_name"),
            "peg_tip_local_offset": task_state_config.get("peg_tip_local_offset"),
            "hole_target_local_offset": task_state_config.get(
                "hole_target_local_offset"
            ),
            "peg_axis_local": task_state_config.get("peg_axis_local"),
            "hole_axis_local": task_state_config.get("hole_axis_local"),
            "insertion_axis_world": task_state_config.get("insertion_axis_world"),
            "task_state_source": "isaac_scene_assets",
        },
        "success_criteria": success_criteria,
    }


def build_frame(
    env: Any,
    action: Any,
    teleoperation_active: bool,
    teleop_interface: Any,
    step: int,
    started_at_monotonic: float,
    calibration: dict[str, Any] | None = None,
    raw_action: Any | None = None,
    control_filter: dict[str, Any] | None = None,
    task_state_config: dict[str, Any] | None = None,
    env_step_result: Any | None = None,
) -> dict[str, Any]:
    ee_position, ee_quaternion = _end_effector_pose(env)
    task_state = _insertion_task_state(env, task_state_config)
    if task_state:
        object_position = list(task_state.get("peg_position") or [])
        object_quaternion = list(task_state.get("peg_quaternion") or [])
    else:
        object_position, object_quaternion = _asset_pose(env, "cube_2")
    step_dt = float(getattr(env, "step_dt", 0.0) or 0.0)
    sim_fps = 1.0 / step_dt if step_dt > 0 else None
    t = step * step_dt if step_dt > 0 else time.monotonic() - started_at_monotonic

    metadata = {
        **_xr_metadata(
            teleop_interface,
            action,
            teleoperation_active,
            sim_fps,
            raw_action=raw_action,
            control_filter=control_filter,
        ),
        "env_origin": _env_origin(env),
        "cube_states": _cube_states(env),
        "sim_step_boundary": _env_step_boundary_metadata(env_step_result),
    }
    if task_state:
        metadata["task_state"] = task_state
        metadata["action_phase"] = task_state.get("action_phase") or "UNKNOWN"
    _apply_alignment_metadata(metadata, calibration)

    return {
        "t": float(t),
        "step": int(step),
        "end_effector_position": ee_position,
        "end_effector_quaternion": ee_quaternion,
        "object_position": object_position,
        "object_quaternion": object_quaternion,
        "action": _action_payload(
            action,
            teleoperation_active,
            raw_action=raw_action,
            control_filter=control_filter,
        ),
        "contacts": [],
        "metadata": metadata,
    }


class RdfIsaacRuntimeRecorder:
    def __init__(
        self,
        api_base: str,
        contributor_id: str,
        isaac_task_name: str,
        input_device: str = "quest3_handtracking",
        xr_runtime: str = "steamvr_openxr",
        streaming_stack: str = "alvr",
        max_frames: int = 0,
        warmup_valid_frames: int = 0,
        auto_calibrate_on_first_valid: bool = True,
    ) -> None:
        self.api_base = api_base
        self.contributor_id = contributor_id
        self.isaac_task_name = isaac_task_name
        self.input_device = input_device
        self.xr_runtime = xr_runtime
        self.streaming_stack = streaming_stack
        self.max_frames = max(0, int(max_frames))
        self.warmup_valid_frames = max(0, int(warmup_valid_frames))
        self.auto_calibrate_on_first_valid = bool(auto_calibrate_on_first_valid)
        self.task_type = _task_type_from_env_or_name(isaac_task_name)
        self.task_state_config = _task_state_config(
            self.task_type, self.isaac_task_name
        )
        self.collection_task_id: str | None = os.environ.get("RDF_TASK_ID") or None
        self.task_id: str | None = None
        self.session_id: str | None = None
        self.episode_id: str | None = None
        self.frames: list[dict[str, Any]] = []
        self.started_at_monotonic = 0.0
        self.episode_started_at: str | None = None
        self.target_position: list[float] = []
        self.calibration: dict[str, Any] | None = None
        self.calibration_events: list[dict[str, Any]] = []
        self.control_filter_summary: dict[str, Any] | None = None
        self._calibration_counter = 0
        self.reset_count = 0
        self.warmup_dropped_frames = 0
        self._warmup_consecutive_valid = 0
        self._recording_started = self.warmup_valid_frames == 0
        self.task_state_frame_count = 0
        self._task_state_warning_printed = False
        self._tracking_epoch_id = 0
        self._last_tracking_valid: bool | None = None

    @property
    def active(self) -> bool:
        return (
            self.task_id is not None
            and self.session_id is not None
            and self.episode_id is not None
        )

    def start(self, env: Any) -> None:
        initial_task_state = _insertion_task_state(env, self.task_state_config)
        self.task_state_frame_count = 0
        self._task_state_warning_printed = False
        if initial_task_state:
            self.target_position = list(
                initial_task_state.get("hole_target_position") or []
            )
        else:
            self.target_position = stack_target_position(env)
        if self.task_state_config:
            task_payload = build_insertion_task_payload(
                self.isaac_task_name, self.target_position, self.task_state_config
            )
        else:
            task_payload = build_stack_task_payload(
                self.isaac_task_name, self.target_position
            )
        if self.collection_task_id is None:
            task = post_json(self.api_base, "/api/tasks", task_payload)
            self.collection_task_id = task["id"]
            print(f"[RDF] Using collection task {self.collection_task_id}")
        else:
            print(f"[RDF] Reusing collection task {self.collection_task_id}")
            if self.task_state_config:
                print(
                    "[RDF] WARNING: RDF_TASK_ID is set while RDF_TASK_TYPE is insertion-like. "
                    "Ensure the reused task has task_type=peg_in_hole or evaluator metrics may stay generic."
                )
        self.task_id = self.collection_task_id
        session = post_json(
            self.api_base,
            "/api/collection-sessions/start",
            {
                "task_id": self.task_id,
                "contributor_id": self.contributor_id,
                "isaac_task_name": self.isaac_task_name,
                "input_device": self.input_device,
                "xr_runtime": self.xr_runtime,
                "streaming_stack": self.streaming_stack,
            },
        )
        self.session_id = session["session_id"]
        episode = post_json(
            self.api_base,
            "/api/episodes/start",
            {
                "task_id": self.task_id,
                "contributor_id": self.contributor_id,
                "collection_session_id": self.session_id,
            },
        )
        self.episode_id = episode["episode_id"]
        self.frames = []
        self.started_at_monotonic = time.monotonic()
        self.episode_started_at = datetime.now(timezone.utc).isoformat()
        self.calibration = None
        self.calibration_events = []
        self.control_filter_summary = None
        self._calibration_counter = 0
        self.warmup_dropped_frames = 0
        self._warmup_consecutive_valid = 0
        self._recording_started = self.warmup_valid_frames == 0
        self._tracking_epoch_id = 0
        self._last_tracking_valid = None
        print(f"[RDF] Recording episode {self.episode_id} for task {self.task_id}")
        if self.task_state_config:
            print(
                "[RDF] MVP-1A task_state extraction enabled: "
                f"task_type={self.task_type} peg={self.task_state_config.get('peg_asset_name')} "
                f"hole={self.task_state_config.get('hole_asset_name')}"
            )
            if not initial_task_state:
                print(
                    "[RDF] WARNING: task_state unavailable at start. "
                    "Check RDF_PEG_ASSET_NAME/RDF_HOLE_ASSET_NAME against Isaac scene asset names."
                )
        if self.warmup_valid_frames:
            print(
                "[RDF] Waiting for "
                f"{self.warmup_valid_frames} consecutive valid handtracking frames before saving trajectory frames"
            )
        if self.auto_calibrate_on_first_valid:
            print(
                "[RDF] Auto calibration enabled: first valid handtracking frame will set RDF workspace alignment"
            )

    def calibrate(
        self,
        env: Any,
        teleop_interface: Any,
        reason: str = "operator_command",
        control_filter: dict[str, Any] | None = None,
    ) -> bool:
        right_poses = getattr(teleop_interface, "_previous_joint_poses_right", {})
        raw_right_wrist = _pose_from_dict(right_poses, "wrist")
        if not _pose_is_valid(raw_right_wrist):
            print(
                f"[RDF] Calibration skipped: right wrist is not tracked (reason={reason})"
            )
            return False

        ee_position, ee_quaternion = _end_effector_pose(env)
        if len(ee_position) != 3:
            ee_position = self.target_position[:3]
        if len(ee_position) != 3:
            print(
                f"[RDF] Calibration skipped: no robot workspace pose available (reason={reason})"
            )
            return False

        aligned_origin_pose = [
            *[float(value) for value in ee_position[:3]],
            *(
                [float(value) for value in ee_quaternion[:4]]
                if len(ee_quaternion) == 4
                else raw_right_wrist[3:7]
            ),
        ]
        rotation_offset_quat = _quat_multiply_wxyz(
            aligned_origin_pose[3:7], _quat_inverse_wxyz(raw_right_wrist[3:7])
        )
        if len(rotation_offset_quat) != 4:
            rotation_offset_quat = [1.0, 0.0, 0.0, 0.0]
        translation_offset = [
            float(aligned_origin_pose[0] - raw_right_wrist[0]),
            float(aligned_origin_pose[1] - raw_right_wrist[1]),
            float(aligned_origin_pose[2] - raw_right_wrist[2]),
        ]
        filter_config = (control_filter or {}).get("config") or {}
        position_gain = float(filter_config.get("position_gain", 1.0) or 1.0)
        self._calibration_counter += 1
        calibration_id = f"calib_{self._calibration_counter:03d}"
        self.calibration = {
            "calibration_id": calibration_id,
            "type": "workspace_alignment_v2",
            "translation_only_compatible": True,
            "reason": reason,
            "tracking_origin": "steamvr_openxr_virtual_world",
            "aligned_origin": "rdf_robot_workspace",
            "raw_origin_pose": raw_right_wrist,
            "aligned_origin_pose": aligned_origin_pose,
            "translation_offset": translation_offset,
            "rotation_offset_quat": rotation_offset_quat,
            "position_gain": position_gain,
            "control_filter": control_filter,
            "created_frame_index": len(self.frames),
            "created_at_monotonic": time.monotonic(),
        }
        self.calibration_events.append(dict(self.calibration))
        print(
            "[RDF] Calibration updated "
            f"{calibration_id}: reason={reason} offset={translation_offset} "
            f"rotation_offset={rotation_offset_quat} position_gain={position_gain}"
        )
        return True

    def _annotate_gate0_frame_metadata(
        self,
        frame: dict[str, Any],
        *,
        teleoperation_active: bool,
        control_filter: dict[str, Any] | None,
    ) -> None:
        metadata = frame.setdefault("metadata", {})
        tracking_valid = bool(
            metadata.get("right_hand_tracked") and metadata.get("xr_frame_valid")
        )
        if self._last_tracking_valid is False and tracking_valid:
            self._tracking_epoch_id += 1

        hold_reason = _tracking_hold_reason_from_control_filter(control_filter)
        if not tracking_valid:
            hold_reason = hold_reason or "tracking_invalid"
        elif not teleoperation_active:
            hold_reason = hold_reason or "teleoperation_inactive"
        action_hold = hold_reason is not None

        metadata["action_hold"] = bool(action_hold)
        metadata["hold_reason"] = hold_reason
        metadata["tracking_epoch_id"] = int(self._tracking_epoch_id)
        metadata["tracking_epoch_state"] = "valid" if tracking_valid else "invalid"
        metadata["tracking_gate_reason"] = hold_reason if action_hold else None
        gate0_test_type = os.environ.get("RDF_GATE0_TEST_TYPE")
        if gate0_test_type:
            metadata["gate0_test_type"] = gate0_test_type
        metadata["gate_a_collection_blocked"] = (
            os.environ.get("RDF_GATE_A_COLLECTION_BLOCKED", "0") == "1"
        )

        action_payload = frame.setdefault("action", {})
        if isinstance(action_payload, dict):
            action_payload["action_hold"] = bool(action_hold)
            action_payload["hold_reason"] = hold_reason

        self._last_tracking_valid = tracking_valid

    def record(
        self,
        env: Any,
        action: Any,
        teleoperation_active: bool,
        teleop_interface: Any,
        raw_action: Any | None = None,
        control_filter: dict[str, Any] | None = None,
        env_step_result: Any | None = None,
    ) -> None:
        if not self.active:
            return
        if self.max_frames and len(self.frames) >= self.max_frames:
            return
        if control_filter is not None:
            self.control_filter_summary = control_filter
        frame = build_frame(
            env=env,
            action=action,
            teleoperation_active=teleoperation_active,
            teleop_interface=teleop_interface,
            step=len(self.frames),
            started_at_monotonic=self.started_at_monotonic,
            calibration=self.calibration,
            raw_action=raw_action,
            control_filter=control_filter,
            task_state_config=self.task_state_config,
            env_step_result=env_step_result,
        )
        self._annotate_gate0_frame_metadata(
            frame,
            teleoperation_active=teleoperation_active,
            control_filter=control_filter,
        )
        frame_task_state = (frame.get("metadata") or {}).get("task_state")
        if (
            not frame_task_state
            and self.task_state_config
            and not self._task_state_warning_printed
        ):
            print(
                "[RDF] WARNING: insertion task_state missing on recorded frame. "
                "Check peg/hole asset names and offsets before using this episode for MVP-1A proof."
            )
            self._task_state_warning_printed = True
        if not self._recording_started:
            metadata = frame.get("metadata", {})
            frame_valid = bool(
                metadata.get("xr_frame_valid") and metadata.get("right_hand_tracked")
            )
            self._warmup_consecutive_valid = (
                self._warmup_consecutive_valid + 1 if frame_valid else 0
            )
            if self._warmup_consecutive_valid < self.warmup_valid_frames:
                self.warmup_dropped_frames += 1
                return
            self._recording_started = True
            self.started_at_monotonic = time.monotonic()
            if self.auto_calibrate_on_first_valid and self.calibration is None:
                self.calibrate(
                    env,
                    teleop_interface,
                    reason="auto_first_valid_frame",
                    control_filter=control_filter,
                )
                _apply_alignment_metadata(
                    frame.setdefault("metadata", {}), self.calibration
                )
            frame["step"] = 0
            frame["t"] = 0.0
            frame.setdefault("metadata", {})["recording_started_after_warmup"] = True
            frame["metadata"]["warmup_dropped_frames"] = self.warmup_dropped_frames
            print(
                f"[RDF] Recording frames started after dropping {self.warmup_dropped_frames} warm-up frames"
            )
            self.frames.append(frame)
            if frame_task_state:
                self.task_state_frame_count += 1
            return

        if self.auto_calibrate_on_first_valid and self.calibration is None:
            metadata = frame.get("metadata", {})
            if metadata.get("xr_frame_valid") and metadata.get("right_hand_tracked"):
                self.calibrate(
                    env,
                    teleop_interface,
                    reason="auto_first_valid_frame",
                    control_filter=control_filter,
                )
                _apply_alignment_metadata(
                    frame.setdefault("metadata", {}), self.calibration
                )
        frame.setdefault("metadata", {})["warmup_dropped_frames"] = (
            self.warmup_dropped_frames
        )
        self.frames.append(frame)
        if frame_task_state:
            self.task_state_frame_count += 1

    def finish(
        self,
        reason: str = "closed",
        session_crashed: bool = False,
        episode_status: str | None = None,
        failure_reason: str | None = None,
        failure_note: str | None = None,
        episode_metadata: dict[str, Any] | None = None,
    ) -> None:
        if not self.active:
            return

        status = episode_status or self._status_from_reason(reason)
        finalized_at = datetime.now(timezone.utc).isoformat()
        duration_sec = time.monotonic() - self.started_at_monotonic
        if self.frames:
            duration_sec = max(duration_sec, float(self.frames[-1]["t"]))
        hand_tracking_losses = sum(
            1
            for frame in self.frames
            if frame.get("metadata", {}).get("right_hand_tracked") is False
        )
        input_latencies = [
            float(frame["metadata"]["input_latency_ms"])
            for frame in self.frames
            if frame.get("metadata", {}).get("input_latency_ms") is not None
        ]
        sim_reset_boundary_frames = [
            int(frame.get("step", index))
            for index, frame in enumerate(self.frames)
            if (
                (frame.get("metadata", {}).get("sim_step_boundary") or {}).get(
                    "reset_boundary"
                )
                is True
            )
        ]
        average_fps = len(self.frames) / duration_sec if duration_sec > 0 else 0.0
        action_hold_frames = [
            int(frame.get("step", index))
            for index, frame in enumerate(self.frames)
            if (frame.get("metadata") or {}).get("action_hold") is True
        ]
        hold_reason_counts: dict[str, int] = {}
        tracking_epoch_ids: list[int] = []
        for frame in self.frames:
            metadata = frame.get("metadata") or {}
            if metadata.get("action_hold") is True:
                reason = str(metadata.get("hold_reason") or "unspecified")
                hold_reason_counts[reason] = hold_reason_counts.get(reason, 0) + 1
            epoch_id = metadata.get("tracking_epoch_id")
            if isinstance(epoch_id, int):
                tracking_epoch_ids.append(epoch_id)

        lifecycle_metadata = {
            "episode_status": status,
            "episode_started_at": self.episode_started_at,
            "episode_finalized_at": finalized_at,
            "episode_finalize_reason": reason,
            "episode_failure_reason": failure_reason,
            "episode_failure_note": failure_note,
            "reset_count": self.reset_count,
        }
        if episode_metadata:
            lifecycle_metadata.update(episode_metadata)

        trajectory_payload = {
            "schema_version": SCHEMA_VERSION,
            "source": {
                "input_device": self.input_device,
                "runtime": self.xr_runtime,
                "simulator": "isaac_lab",
                "robot": "franka",
                "task_name": self.isaac_task_name,
            },
            "frames": self.frames,
            "summary": {
                "duration_sec": duration_sec,
                "frame_count": len(self.frames),
                "target_position": self.target_position,
                "complete_reason": reason,
                **lifecycle_metadata,
                "collision_count": 0,
                "runtime_metadata_source": "rdf_isaac_runtime_recorder",
                "warmup_valid_frames": self.warmup_valid_frames,
                "warmup_dropped_frames": self.warmup_dropped_frames,
                "auto_calibrate_on_first_valid": self.auto_calibrate_on_first_valid,
                "calibration": self.calibration,
                "calibration_events": self.calibration_events,
                "control_filter": self.control_filter_summary,
                "task_type": self.task_type,
                "task_state_source": "isaac_scene_assets"
                if self.task_state_frame_count
                else None,
                "task_state_config": self.task_state_config,
                "task_state_frame_count": self.task_state_frame_count,
                "sim_reset_boundary_frame_count": len(sim_reset_boundary_frames),
                "sim_reset_boundary_frames": sim_reset_boundary_frames,
                "gate0_test_type": os.environ.get("RDF_GATE0_TEST_TYPE"),
                "gate_a_collection_blocked": os.environ.get(
                    "RDF_GATE_A_COLLECTION_BLOCKED", "0"
                )
                == "1",
                "action_hold_frame_count": len(action_hold_frames),
                "action_hold_frames": action_hold_frames,
                "hold_reason_counts": hold_reason_counts,
                "tracking_epoch_ids": sorted(set(tracking_epoch_ids)),
                "tracking_epoch_count": len(set(tracking_epoch_ids)),
            },
        }
        runtime_metrics = {
            "average_fps": average_fps,
            "frame_drop_rate": 0.0,
            "hand_tracking_loss_rate": hand_tracking_losses / len(self.frames)
            if self.frames
            else 1.0,
            "average_input_latency_ms": sum(input_latencies) / len(input_latencies)
            if input_latencies
            else 0.0,
            "max_input_latency_ms": max(input_latencies) if input_latencies else 0.0,
            "session_crashed": session_crashed,
            "minimum_required_frames": 1,
            "missing_required_object_state": not any(
                frame.get("object_position") for frame in self.frames
            ),
            "missing_required_robot_state": not any(
                frame.get("end_effector_position") for frame in self.frames
            ),
            "complete_reason": reason,
            "episode_status": status,
            "episode_finalize_reason": reason,
            "episode_failure_reason": failure_reason,
            "episode_failure_note": failure_note,
            "reset_count": self.reset_count,
            "warmup_valid_frames": self.warmup_valid_frames,
            "warmup_dropped_frames": self.warmup_dropped_frames,
            "calibration_valid": bool(self.calibration),
            "calibration_event_count": len(self.calibration_events),
            "control_filter_enabled": bool(
                self.control_filter_summary
                and (self.control_filter_summary.get("config") or {}).get("enabled")
            ),
            "task_state_frame_count": self.task_state_frame_count,
            "task_state_available": self.task_state_frame_count > 0,
            "sim_reset_boundary_frame_count": len(sim_reset_boundary_frames),
            "action_hold_frame_count": len(action_hold_frames),
            "hold_reason_counts": hold_reason_counts,
            "tracking_epoch_count": len(set(tracking_epoch_ids)),
        }

        try:
            completed = post_json(
                self.api_base,
                f"/api/episodes/{self.episode_id}/finalize",
                {
                    "trajectory": trajectory_payload,
                    "episode_status": status,
                    "episode_finalize_reason": reason,
                    "episode_failure_reason": failure_reason,
                    "episode_failure_note": failure_note,
                    "reset_count": self.reset_count,
                    "unit_economics": {
                        "human_time_per_episode": duration_sec,
                        "compute_time_per_episode": 0.0,
                        "cost_per_recorded_episode": 0.0,
                        "cost_per_valid_episode": 0.0,
                        "cost_per_accepted_trajectory": 0.0,
                    },
                },
            )
            post_json(
                self.api_base,
                f"/api/collection-sessions/{self.session_id}/complete",
                {"runtime_metrics": runtime_metrics},
            )
            print(
                "[RDF] Submitted episode "
                f"{self.episode_id}: status={completed.get('episode_status')} "
                f"success={completed.get('success')} score={completed.get('score')}"
            )
        finally:
            self.task_id = None
            self.session_id = None
            self.episode_id = None
            self.frames = []
            self.episode_started_at = None
            self.calibration = None
            self.calibration_events = []
            self.control_filter_summary = None
            self._calibration_counter = 0
            self.warmup_dropped_frames = 0
            self._warmup_consecutive_valid = 0
            self._recording_started = self.warmup_valid_frames == 0
            self._tracking_epoch_id = 0
            self._last_tracking_valid = None

    def finish_and_restart(
        self,
        env: Any,
        episode_status: str,
        reason: str,
        failure_reason: str | None = None,
        failure_note: str | None = None,
        episode_metadata: dict[str, Any] | None = None,
    ) -> None:
        if episode_status == "reset":
            self.reset_count += 1
        self.finish(
            reason=reason,
            episode_status=episode_status,
            failure_reason=failure_reason,
            failure_note=failure_note,
            episode_metadata=episode_metadata,
        )
        self.start(env)

    @staticmethod
    def _status_from_reason(reason: str) -> str:
        normalized = reason.lower()
        if normalized in {"operator_success", "success", "auto_success_ready"}:
            return "success"
        if normalized in {"operator_failure", "failure"}:
            return "failure"
        if normalized in {"operator_reset", "reset"}:
            return "reset"
        return "incomplete"
