#!/usr/bin/env python3
"""Check whether Forge PegInsert is viable before policy A/B claims.

Run with Isaac's Python:

    /home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/check_peg_insert_viability.py --pretty

This is intentionally HMD-free. It separates three questions:

1. Can the environment/evaluator report success for a known successful state?
2. Can a closed-loop scripted controller solve the current PegInsert reset?
3. Do accepted trajectory actions replay successfully in the live Isaac env?

If (1) or (2) fails, policy uplift evaluation is premature. If (3) fails, the
accepted dataset action contract is not physically replayable as-is and should
not be treated as proof-grade policy training material.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TASK = "Isaac-Forge-PegInsert-Direct-v0"
DEFAULT_OUTPUT = ROOT / "storage" / "logs" / "peg_insert_viability_report.json"
DEFAULT_CURATION_MANIFEST = ROOT / "storage" / "mvp1_readiness" / "curation_manifest.json"
DEFAULT_READINESS_TRAJ_DIR = ROOT / "storage" / "mvp1_readiness" / "raw" / "trajectories"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", default=DEFAULT_TASK)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--oracle-steps", type=int, default=180)
    parser.add_argument("--replay-repeat", type=int, default=1)
    parser.add_argument("--trajectory", action="append", type=Path, default=[])
    parser.add_argument(
        "--replay-success-evaluator",
        choices=("auto", "env_native", "rdf_peg_in_hole"),
        default="auto",
        help=(
            "Success evaluator for recorded-action replay. auto uses the RDF "
            "peg-in-hole evaluator when trajectory.summary.task_state_config is available."
        ),
    )
    parser.add_argument(
        "--replay-scope",
        choices=("accepted", "raw_success", "all"),
        default="accepted",
        help="Which readiness trajectories to replay when --trajectory is not supplied.",
    )
    parser.add_argument("--curation-manifest", type=Path, default=DEFAULT_CURATION_MANIFEST)
    parser.add_argument("--readiness-trajectory-dir", type=Path, default=DEFAULT_READINESS_TRAJ_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--no-headless", action="store_true")
    return parser.parse_args(argv)


def stable_json(payload: Any, *, pretty: bool = True) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2 if pretty else None)


def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected top-level JSON object")
    return data


def flatten_numeric(value: Any) -> list[float]:
    if value is None:
        return []
    if isinstance(value, bool):
        return []
    if isinstance(value, (int, float)):
        return [float(value)]
    if isinstance(value, (list, tuple)):
        values: list[float] = []
        for item in value:
            values.extend(flatten_numeric(item))
        return values
    return []


def command_vector(value: Any) -> list[float]:
    vector = flatten_numeric(value)
    if vector:
        return vector
    if not isinstance(value, dict):
        return []
    for key in ("command", "robot_action", "action", "raw", "applied", "retargeted_robot_action"):
        vector = command_vector(value.get(key))
        if vector:
            return vector
    relative: list[float] = []
    relative.extend(flatten_numeric(value.get("delta_position")))
    relative.extend(flatten_numeric(value.get("delta_rotation")))
    relative.extend(flatten_numeric(value.get("gripper")))
    return relative


def extract_action(frame: dict[str, Any], action_field: str) -> tuple[list[float], str | None]:
    action = frame.get("action")
    action_type: str | None = None
    if isinstance(action, dict):
        selected = action.get(action_field)
        if isinstance(selected, dict):
            action_type = str(selected.get("action_type")) if selected.get("action_type") is not None else None
        vector = command_vector(selected)
        if vector:
            return vector, action_type
        for fallback in ("learning_action", "executed_control", "retargeted_robot_action", "applied", "raw"):
            selected = action.get(fallback)
            if isinstance(selected, dict) and action_type is None:
                action_type = str(selected.get("action_type")) if selected.get("action_type") is not None else None
            vector = command_vector(selected)
            if vector:
                return vector, action_type
    return command_vector(action), action_type


def vec(value: Any, length: int | None = None) -> list[float]:
    if hasattr(value, "detach"):
        value = value.detach()
    if hasattr(value, "cpu"):
        value = value.cpu()
    if hasattr(value, "tolist"):
        value = value.tolist()
    if value and isinstance(value[0], list):
        value = value[0]
    values = [float(item) for item in value]
    return values[:length] if length is not None else values


def _vec_add(left: list[float], right: list[float]) -> list[float]:
    return [float(a) + float(b) for a, b in zip(left, right, strict=True)] if len(left) == len(right) == 3 else []


def _vec_sub(left: list[float], right: list[float]) -> list[float]:
    return [float(a) - float(b) for a, b in zip(left, right, strict=True)] if len(left) == len(right) == 3 else []


def _vec_scale(vector: list[float], scalar: float) -> list[float]:
    return [float(value) * float(scalar) for value in vector] if len(vector) == 3 else []


def _vec_dot(left: list[float], right: list[float]) -> float | None:
    if len(left) != 3 or len(right) != 3:
        return None
    return sum(float(a) * float(b) for a, b in zip(left, right, strict=True))


def _vec_norm(vector: list[float]) -> float | None:
    if len(vector) != 3:
        return None
    return math.sqrt(sum(float(value) * float(value) for value in vector))


def _vec_normalize(vector: list[float], fallback: list[float] | None = None) -> list[float]:
    norm = _vec_norm(vector)
    if norm is None or norm <= 1.0e-9:
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


def _quat_normalize_wxyz(quat: list[float]) -> list[float]:
    if len(quat) != 4:
        return []
    norm = math.sqrt(sum(float(value) * float(value) for value in quat))
    if norm <= 1.0e-9:
        return [1.0, 0.0, 0.0, 0.0]
    return [float(value) / norm for value in quat]


def _quat_inverse_wxyz(quat: list[float]) -> list[float]:
    normalized = _quat_normalize_wxyz(quat)
    if len(normalized) != 4:
        return []
    return [normalized[0], -normalized[1], -normalized[2], -normalized[3]]


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
    normalized = _quat_normalize_wxyz(quat)
    if len(normalized) != 4:
        return []
    vector_quat = [0.0, float(vector[0]), float(vector[1]), float(vector[2])]
    rotated = _quat_multiply_raw_wxyz(
        _quat_multiply_raw_wxyz(normalized, vector_quat),
        _quat_inverse_wxyz(normalized),
    )
    return rotated[1:4] if len(rotated) == 4 else []


def find_replay_trajectories(args: argparse.Namespace) -> list[Path]:
    explicit = [path.resolve() for path in args.trajectory]
    if explicit:
        return explicit
    paths: list[Path] = []
    if not args.readiness_trajectory_dir.exists():
        return paths
    accepted_ids: set[str] = set()
    if args.curation_manifest.exists():
        manifest = read_json(args.curation_manifest)
        accepted_ids = {str(value) for value in manifest.get("accepted_episode_ids") or []}
    for path in sorted(args.readiness_trajectory_dir.glob("*.json")):
        try:
            trajectory = read_json(path)
        except (OSError, json.JSONDecodeError, ValueError):
            continue
        summary = trajectory.get("summary") if isinstance(trajectory.get("summary"), dict) else {}
        episode_id = trajectory.get("episode_id")
        include = False
        if args.replay_scope == "accepted":
            include = isinstance(episode_id, str) and episode_id in accepted_ids
        elif args.replay_scope == "raw_success":
            include = summary.get("episode_status") == "success"
        else:
            include = True
        if include:
            paths.append(path.resolve())
    return paths


def refresh_env(env: Any) -> None:
    if hasattr(env, "_compute_intermediate_values"):
        env._compute_intermediate_values(dt=env.physics_dt)


def set_ema_one(env: Any) -> None:
    if hasattr(env, "ema_factor"):
        if hasattr(env.ema_factor, "fill_"):
            env.ema_factor.fill_(1.0)
        else:
            env.ema_factor = 1.0
    if hasattr(env, "actions"):
        env.actions.zero_()
    if hasattr(env, "prev_actions"):
        env.prev_actions.zero_()


def success_metrics(env: Any) -> dict[str, Any]:
    import torch

    import isaaclab_tasks.direct.factory.factory_utils as factory_utils

    refresh_env(env)
    check_rot = getattr(env.cfg_task, "name", "") == "nut_thread"
    success_tensor = env._get_curr_successes(success_threshold=env.cfg_task.success_threshold, check_rot=check_rot)
    held_base_pos, _held_base_quat = factory_utils.get_held_base_pose(
        env.held_pos,
        env.held_quat,
        env.cfg_task.name,
        env.cfg_task.fixed_asset_cfg,
        env.num_envs,
        env.device,
    )
    target_held_base_pos, _target_held_base_quat = factory_utils.get_target_held_base_pose(
        env.fixed_pos,
        env.fixed_quat,
        env.cfg_task.name,
        env.cfg_task.fixed_asset_cfg,
        env.num_envs,
        env.device,
    )
    xy_dist = torch.linalg.vector_norm(target_held_base_pos[:, 0:2] - held_base_pos[:, 0:2], dim=1)
    z_disp = held_base_pos[:, 2] - target_held_base_pos[:, 2]
    fixed_cfg = env.cfg_task.fixed_asset_cfg
    if env.cfg_task.name in {"peg_insert", "gear_mesh"}:
        height_threshold = float(fixed_cfg.height * env.cfg_task.success_threshold)
    elif env.cfg_task.name == "nut_thread":
        height_threshold = float(fixed_cfg.thread_pitch * env.cfg_task.success_threshold)
    else:
        height_threshold = None
    return {
        "success": bool(success_tensor.detach().cpu().tolist()[0]),
        "xy_dist_m": float(xy_dist.detach().cpu().tolist()[0]),
        "z_disp_m": float(z_disp.detach().cpu().tolist()[0]),
        "height_threshold_m": height_threshold,
        "fingertip_pos": vec(env.fingertip_midpoint_pos, 3),
        "held_pos": vec(env.held_pos, 3),
        "fixed_pos": vec(env.fixed_pos, 3),
        "fixed_pos_obs_frame": vec(env.fixed_pos_obs_frame, 3),
        "target_held_base_pos": vec(target_held_base_pos, 3),
    }


def _asset_pose_for_task_state(env: Any, asset_name: str) -> tuple[list[float], list[float]]:
    aliases = {
        "held_asset": ("held_pos", "held_quat"),
        "peg": ("held_pos", "held_quat"),
        "fixed_asset": ("fixed_pos", "fixed_quat"),
        "hole": ("fixed_pos", "fixed_quat"),
    }
    pos_attr, quat_attr = aliases.get(asset_name, ("", ""))
    position = vec(getattr(env, pos_attr, []), 3) if pos_attr else []
    quaternion = vec(getattr(env, quat_attr, []), 4) if quat_attr else []
    if position and quaternion:
        return position, quaternion

    scene = getattr(env, "scene", None)
    asset = scene[asset_name] if scene is not None and asset_name in scene.keys() else None
    data = getattr(asset, "data", None)
    if data is None:
        return [], []
    return vec(getattr(data, "root_pos_w", []), 3), vec(getattr(data, "root_quat_w", []), 4)


def _float_threshold(source: dict[str, Any], key: str, default: float) -> float:
    value = source.get(key)
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    return default


def _trajectory_task_state_config(trajectory: dict[str, Any]) -> dict[str, Any] | None:
    summary = trajectory.get("summary") if isinstance(trajectory.get("summary"), dict) else {}
    config = summary.get("task_state_config")
    if isinstance(config, dict) and str(config.get("task_type") or "").lower() in {"peg_in_hole", "peg_insert"}:
        return config
    if str(summary.get("task_type") or "").lower() in {"peg_in_hole", "peg_insert"}:
        return {
            "task_type": "peg_in_hole",
            "peg_asset_name": "held_asset",
            "hole_asset_name": "fixed_asset",
            "peg_tip_local_offset": [0.0, 0.0, 0.0],
            "hole_target_local_offset": [0.0, 0.0, 0.0],
            "peg_axis_local": [0.0, 0.0, -1.0],
            "hole_axis_local": [0.0, 0.0, -1.0],
            "insertion_axis_world": [0.0, 0.0, 1.0],
            "success_criteria": {
                "peg_tip_distance_to_target_max": 0.015,
                "peg_axis_alignment_error_max_rad": 0.25,
                "insertion_depth_min": 0.025,
            },
        }
    return None


def _rdf_peg_in_hole_task_state(env: Any, trajectory: dict[str, Any]) -> dict[str, Any] | None:
    config = _trajectory_task_state_config(trajectory)
    if config is None:
        return None

    peg_asset = str(config.get("peg_asset_name") or "held_asset")
    hole_asset = str(config.get("hole_asset_name") or "fixed_asset")
    peg_position, peg_quaternion = _asset_pose_for_task_state(env, peg_asset)
    hole_position, hole_quaternion = _asset_pose_for_task_state(env, hole_asset)
    if len(peg_position) != 3 or len(hole_position) != 3:
        return None
    if len(peg_quaternion) != 4:
        peg_quaternion = [1.0, 0.0, 0.0, 0.0]
    if len(hole_quaternion) != 4:
        hole_quaternion = [1.0, 0.0, 0.0, 0.0]

    peg_offset = [float(value) for value in config.get("peg_tip_local_offset") or [0.0, 0.0, 0.0]]
    hole_offset = [float(value) for value in config.get("hole_target_local_offset") or [0.0, 0.0, 0.0]]
    peg_tip = _vec_add(peg_position, _quat_rotate_vector_wxyz(peg_quaternion, peg_offset) or [0.0, 0.0, 0.0])
    hole_target = _vec_add(hole_position, _quat_rotate_vector_wxyz(hole_quaternion, hole_offset) or [0.0, 0.0, 0.0])
    if len(peg_tip) != 3 or len(hole_target) != 3:
        return None

    fallback_axis = [0.0, 0.0, 1.0]
    insertion_axis = _vec_normalize([float(value) for value in config.get("insertion_axis_world") or fallback_axis], fallback_axis)
    peg_axis = _quat_rotate_vector_wxyz(
        peg_quaternion,
        [float(value) for value in config.get("peg_axis_local") or [0.0, 0.0, -1.0]],
    )
    hole_axis = _quat_rotate_vector_wxyz(
        hole_quaternion,
        [float(value) for value in config.get("hole_axis_local") or [0.0, 0.0, -1.0]],
    )
    peg_axis = _vec_normalize(peg_axis, insertion_axis)
    hole_axis = _vec_normalize(hole_axis, insertion_axis)

    delta_to_target = _vec_sub(peg_tip, hole_target)
    distance_3d = _vec_norm(delta_to_target)
    axial_distance = _vec_dot(delta_to_target, insertion_axis)
    lateral_distance = None
    if axial_distance is not None:
        axial_component = _vec_scale(insertion_axis, axial_distance)
        lateral_distance = _vec_norm(_vec_sub(delta_to_target, axial_component))
    depth_projection = _vec_dot(_vec_sub(peg_tip, hole_position), insertion_axis)
    alignment = _angle_between(peg_axis, hole_axis)
    success_criteria = config.get("success_criteria") if isinstance(config.get("success_criteria"), dict) else {}
    distance_max = _float_threshold(success_criteria, "peg_tip_distance_to_target_max", 0.015)
    alignment_max = _float_threshold(success_criteria, "peg_axis_alignment_error_max_rad", 0.25)
    depth_min = _float_threshold(success_criteria, "insertion_depth_min", 0.025)
    distance_for_gate = lateral_distance if lateral_distance is not None else distance_3d
    insertion_depth = max(0.0, float(depth_projection or 0.0))
    success = bool(
        distance_for_gate is not None
        and alignment is not None
        and distance_for_gate <= distance_max
        and alignment <= alignment_max
        and insertion_depth >= depth_min
    )
    return {
        "success": success,
        "peg_tip_distance_to_target": distance_for_gate,
        "peg_tip_distance_3d_to_target": distance_3d,
        "peg_lateral_distance_to_target": lateral_distance,
        "peg_distance_metric": "lateral_projection" if lateral_distance is not None else "legacy_3d",
        "axis_alignment_error_rad": alignment,
        "insertion_depth": insertion_depth,
        "peg_tip_distance_to_target_max": distance_max,
        "peg_axis_alignment_error_max_rad": alignment_max,
        "insertion_depth_min": depth_min,
        "peg_position": peg_position,
        "hole_position": hole_position,
        "peg_axis_vector": peg_axis,
        "hole_axis_vector": hole_axis,
    }


def replay_success_metrics(env: Any, trajectory: dict[str, Any], evaluator: str) -> dict[str, Any]:
    native = success_metrics(env)
    rdf_task_state = _rdf_peg_in_hole_task_state(env, trajectory)
    selected = evaluator
    if selected == "auto":
        selected = "rdf_peg_in_hole" if rdf_task_state is not None else "env_native"

    metrics = dict(native)
    metrics["env_native_success"] = native["success"]
    metrics["selected_success_evaluator"] = selected
    if rdf_task_state is not None:
        metrics["rdf_peg_in_hole"] = rdf_task_state
    if selected == "rdf_peg_in_hole" and rdf_task_state is not None:
        metrics["success"] = bool(rdf_task_state["success"])
    return metrics


def step_sim_no_action(env: Any) -> None:
    if hasattr(env, "step_sim_no_action"):
        env.step_sim_no_action()
        return
    env.scene.write_data_to_sim()
    env.sim.step(render=False)
    env.scene.update(dt=env.physics_dt)
    refresh_env(env)


def run_evaluator_teleport_check(env: Any, seed: int) -> dict[str, Any]:
    import isaaclab_tasks.direct.factory.factory_utils as factory_utils

    try:
        env.reset(seed=seed)
    except TypeError:
        env.reset()
    refresh_env(env)
    before = success_metrics(env)
    target_held_base_pos, target_held_base_quat = factory_utils.get_target_held_base_pose(
        env.fixed_pos,
        env.fixed_quat,
        env.cfg_task.name,
        env.cfg_task.fixed_asset_cfg,
        env.num_envs,
        env.device,
    )
    held_state = env._held_asset.data.root_state_w.clone()
    held_state[:, 0:3] = target_held_base_pos + env.scene.env_origins
    held_state[:, 3:7] = target_held_base_quat
    held_state[:, 7:] = 0.0
    env._held_asset.write_root_pose_to_sim(held_state[:, 0:7])
    env._held_asset.write_root_velocity_to_sim(held_state[:, 7:])
    env._held_asset.reset()
    step_sim_no_action(env)
    after = success_metrics(env)
    return {
        "name": "evaluator_teleport_success_state",
        "passed": after["success"] is True,
        "before": before,
        "after": after,
        "interpretation": "Checks evaluator/success threshold with held asset placed at target success pose.",
    }


def build_native_action_to_target(env: Any, target_pos: Any):
    import torch

    refresh_env(env)
    action_dim = int(env.action_space.shape[-1])
    action = torch.zeros((1, action_dim), dtype=torch.float32, device=env.device)
    pos_threshold = torch.clamp(env.pos_threshold[0], min=1.0e-6)
    delta = target_pos - env.fingertip_midpoint_pos[0]
    action[0, 0:3] = torch.clamp(delta / pos_threshold, -1.0, 1.0)
    if action_dim >= 7:
        action[0, 6] = -1.0
    return action


def run_scripted_oracle_check(env: Any, seed: int, max_steps: int) -> dict[str, Any]:
    import torch

    import isaaclab_tasks.direct.factory.factory_utils as factory_utils

    try:
        env.reset(seed=seed)
    except TypeError:
        env.reset()
    set_ema_one(env)
    refresh_env(env)
    before = success_metrics(env)
    target_held_base_pos, _target_held_base_quat = factory_utils.get_target_held_base_pose(
        env.fixed_pos,
        env.fixed_quat,
        env.cfg_task.name,
        env.cfg_task.fixed_asset_cfg,
        env.num_envs,
        env.device,
    )
    fingertip_to_held_offset = env.fingertip_midpoint_pos[0] - env.held_pos[0]
    final_fingertip_target = target_held_base_pos[0] + fingertip_to_held_offset
    phase_targets = [
        final_fingertip_target + torch.tensor([0.0, 0.0, 0.045], dtype=torch.float32, device=env.device),
        final_fingertip_target + torch.tensor([0.0, 0.0, 0.020], dtype=torch.float32, device=env.device),
        final_fingertip_target + torch.tensor([0.0, 0.0, 0.006], dtype=torch.float32, device=env.device),
        final_fingertip_target,
    ]
    success_seen = False
    success_step: int | None = None
    samples: list[dict[str, Any]] = []
    for step in range(max(max_steps, 1)):
        phase_index = min(len(phase_targets) - 1, int(step / max(max_steps, 1) * len(phase_targets)))
        target = phase_targets[phase_index]
        action = build_native_action_to_target(env, target)
        env.step(action)
        if step % 20 == 0 or step == max_steps - 1:
            metrics = success_metrics(env)
            samples.append(
                {
                    "step": step + 1,
                    "phase_index": phase_index,
                    "target_fingertip_pos": vec(target, 3),
                    "action_xyz": vec(action, 3),
                    "success": metrics["success"],
                    "xy_dist_m": metrics["xy_dist_m"],
                    "z_disp_m": metrics["z_disp_m"],
                    "fingertip_pos": metrics["fingertip_pos"],
                    "held_pos": metrics["held_pos"],
                }
            )
        metrics = success_metrics(env)
        if metrics["success"]:
            success_seen = True
            success_step = step + 1
            break
    after = success_metrics(env)
    return {
        "name": "closed_loop_scripted_oracle",
        "passed": success_seen,
        "success_step": success_step,
        "before": before,
        "after": after,
        "samples": samples,
        "interpretation": "Uses env native actions in a closed-loop controller targeting the held asset success pose.",
    }


def native_action_from_vector(env: Any, vector: list[float], mode: str):
    import torch

    action_dim = int(env.action_space.shape[-1])
    action = torch.zeros((1, action_dim), dtype=torch.float32, device=env.device)
    values = torch.tensor(vector[:action_dim], dtype=torch.float32, device=env.device)
    action[0, : values.numel()] = values
    if mode == "metric_delta_to_native":
        if values.numel() >= 3 and hasattr(env, "pos_threshold"):
            action[0, 0:3] = torch.clamp(values[0:3] / torch.clamp(env.pos_threshold[0], min=1.0e-6), -1.0, 1.0)
        if values.numel() >= 6 and hasattr(env, "rot_threshold"):
            action[0, 3:6] = torch.clamp(values[3:6] / torch.clamp(env.rot_threshold[0], min=1.0e-6), -1.0, 1.0)
        if values.numel() >= 7 and action_dim >= 7:
            action[0, 6] = values[6]
    else:
        action = torch.clamp(action, -1.0, 1.0)
    return action


def replay_seed_for_trajectory(trajectory: dict[str, Any], fallback_seed: int) -> tuple[int, str]:
    summary = trajectory.get("summary") if isinstance(trajectory.get("summary"), dict) else {}
    contract = summary.get("action_replay_contract") if isinstance(summary.get("action_replay_contract"), dict) else {}
    initial_state = contract.get("initial_state") if isinstance(contract.get("initial_state"), dict) else {}
    seed = initial_state.get("seed")
    if isinstance(seed, int):
        return seed, "trajectory.summary.action_replay_contract.initial_state.seed"
    return fallback_seed, "diagnostic_seed"


def run_replay_check(
    env: Any,
    *,
    trajectory_path: Path,
    seed: int,
    mode: str,
    repeat: int,
    action_field: str = "retargeted_robot_action",
    success_evaluator: str = "auto",
) -> dict[str, Any]:
    trajectory = read_json(trajectory_path)
    frames = trajectory.get("frames") if isinstance(trajectory.get("frames"), list) else []
    replay_seed, replay_seed_source = replay_seed_for_trajectory(trajectory, seed)
    try:
        env.reset(seed=replay_seed)
    except TypeError:
        env.reset()
    set_ema_one(env)
    refresh_env(env)
    before = replay_success_metrics(env, trajectory, success_evaluator)
    success_seen = False
    success_step: int | None = None
    missing_action_count = 0
    action_types: set[str] = set()
    first_action: list[float] = []
    last_action: list[float] = []
    total_steps = 0
    samples: list[dict[str, Any]] = []
    for frame_index, frame in enumerate(frames):
        if not isinstance(frame, dict):
            missing_action_count += 1
            continue
        vector, action_type = extract_action(frame, action_field)
        if action_type:
            action_types.add(action_type)
        if not vector:
            missing_action_count += 1
            continue
        if not first_action:
            first_action = list(vector)
        last_action = list(vector)
        action = native_action_from_vector(env, vector, mode)
        for _repeat_index in range(max(repeat, 1)):
            env.step(action)
            total_steps += 1
            metrics = replay_success_metrics(env, trajectory, success_evaluator)
            if frame_index in {0, max(len(frames) // 2, 0), len(frames) - 1} and _repeat_index == 0:
                samples.append(
                    {
                        "frame_index": frame_index,
                        "step": total_steps,
                        "raw_vector": vector[:7],
                        "native_action": vec(action, 7),
                        "success": metrics["success"],
                        "selected_success_evaluator": metrics["selected_success_evaluator"],
                        "rdf_peg_in_hole": metrics.get("rdf_peg_in_hole"),
                        "xy_dist_m": metrics["xy_dist_m"],
                        "z_disp_m": metrics["z_disp_m"],
                    }
                )
            if metrics["success"]:
                success_seen = True
                success_step = total_steps
                break
        if success_seen:
            break
    after = replay_success_metrics(env, trajectory, success_evaluator)
    return {
        "name": "accepted_recorded_action_replay",
        "trajectory_path": str(trajectory_path),
        "trajectory_id": trajectory.get("id"),
        "episode_id": trajectory.get("episode_id"),
        "frame_count": len(frames),
        "action_field": action_field,
        "action_types": sorted(action_types),
        "mode": mode,
        "requested_success_evaluator": success_evaluator,
        "selected_success_evaluator": after["selected_success_evaluator"],
        "repeat": repeat,
        "requested_seed": seed,
        "replay_seed": replay_seed,
        "replay_seed_source": replay_seed_source,
        "passed": success_seen,
        "success_step": success_step,
        "missing_action_count": missing_action_count,
        "first_action": first_action[:7],
        "last_action": last_action[:7],
        "before": before,
        "after": after,
        "samples": samples,
    }


def run_report(args: argparse.Namespace) -> dict[str, Any]:
    from isaaclab.app import AppLauncher

    app_launcher = AppLauncher(
        {
            "headless": not args.no_headless,
            "device": args.device,
            "enable_cameras": False,
        }
    )
    _simulation_app = app_launcher.app

    import gymnasium as gym

    import isaaclab_tasks  # noqa: F401
    from isaaclab_tasks.utils import parse_env_cfg

    env = None
    accepted_paths = find_replay_trajectories(args)
    try:
        env_cfg = parse_env_cfg(args.task, device=args.device, num_envs=1)
        env_cfg.seed = args.seed
        env = gym.make(args.task, cfg=env_cfg).unwrapped
        teleport = run_evaluator_teleport_check(env, seed=args.seed)
        scripted = run_scripted_oracle_check(env, seed=args.seed + 1, max_steps=args.oracle_steps)
        replay_results: list[dict[str, Any]] = []
        for path in accepted_paths:
            for mode in ("native_direct", "metric_delta_to_native"):
                replay_results.append(
                    run_replay_check(
                        env,
                        trajectory_path=path,
                        seed=args.seed + 100 + len(replay_results),
                        mode=mode,
                        repeat=args.replay_repeat,
                        success_evaluator=args.replay_success_evaluator,
                    )
                )
    finally:
        if env is not None:
            env.close()

    native_replays = [row for row in replay_results if row["mode"] == "native_direct"]
    metric_replays = [row for row in replay_results if row["mode"] == "metric_delta_to_native"]
    native_pass_count = sum(1 for row in native_replays if row["passed"])
    metric_pass_count = sum(1 for row in metric_replays if row["passed"])
    replay_native_any_passed = native_pass_count > 0
    replay_metric_any_passed = metric_pass_count > 0
    replay_native_all_passed = bool(native_replays) and native_pass_count == len(native_replays)
    replay_metric_all_passed = bool(metric_replays) and metric_pass_count == len(metric_replays)
    accepted_replay_viability = replay_native_all_passed or replay_metric_all_passed
    policy_loop_viability = bool(teleport["passed"] and scripted["passed"] and accepted_replay_viability)
    issues: list[str] = []
    if not teleport["passed"]:
        issues.append("evaluator_teleport_success_state failed; success/evaluator target may be inconsistent")
    if not scripted["passed"]:
        issues.append("closed_loop_scripted_oracle failed; env/controller may not produce successful insertion")
    if not replay_results:
        issues.append("no accepted trajectories found for replay")
    elif not replay_native_any_passed:
        issues.append("accepted replay failed in native_direct mode; current policy eval may use incompatible action semantics")
    elif not replay_native_all_passed:
        issues.append(
            f"accepted replay only partially passed in native_direct mode ({native_pass_count}/{len(native_replays)})"
        )
    if replay_results and not replay_metric_any_passed:
        issues.append("accepted replay failed even with metric_delta_to_native conversion")
    elif replay_results and not replay_metric_all_passed:
        issues.append(
            f"accepted replay only partially passed in metric_delta_to_native mode ({metric_pass_count}/{len(metric_replays)})"
        )

    recommendations: list[str] = []
    if not scripted["passed"]:
        recommendations.append("Fix PegInsert scripted/oracle control before running another policy A/B.")
    if replay_metric_all_passed and not replay_native_all_passed:
        recommendations.append("Convert exported metric delta actions to env-native actions for headless policy eval, or change eval env to consume executed_control semantics.")
    if not accepted_replay_viability:
        recommendations.append("Do not treat current accepted fixture set as physically replayable proof until every accepted replay succeeds under one replay contract.")
    if policy_loop_viability:
        recommendations.append("Policy A/B can proceed, but use the replay-compatible action semantics identified by this report.")

    return {
        "schema_version": "rdf_peg_insert_viability_v0.1.0",
        "created_at": datetime.now(UTC).isoformat(),
        "task": args.task,
        "device": args.device,
        "seed": args.seed,
        "replay_scope": args.replay_scope if not args.trajectory else "explicit_trajectory_list",
        "replay_success_evaluator": args.replay_success_evaluator,
        "replay_trajectory_paths": [str(path) for path in accepted_paths],
        "accepted_trajectory_paths": [str(path) for path in accepted_paths],
        "checks": {
            "evaluator_teleport": teleport,
            "scripted_oracle": scripted,
            "accepted_replays": replay_results,
        },
        "summary": {
            "evaluator_success_state_passed": teleport["passed"],
            "scripted_oracle_passed": scripted["passed"],
            "accepted_replay_native_direct_passed_count": native_pass_count,
            "accepted_replay_native_direct_total": len(native_replays),
            "accepted_replay_native_direct_any_passed": replay_native_any_passed,
            "accepted_replay_native_direct_all_passed": replay_native_all_passed,
            "accepted_replay_metric_delta_to_native_passed_count": metric_pass_count,
            "accepted_replay_metric_delta_to_native_total": len(metric_replays),
            "accepted_replay_metric_delta_to_native_any_passed": replay_metric_any_passed,
            "accepted_replay_metric_delta_to_native_all_passed": replay_metric_all_passed,
            "accepted_replay_viability": accepted_replay_viability,
            "policy_loop_viability": policy_loop_viability,
            "issues": issues,
            "recommendations": recommendations,
        },
    }


def main() -> None:
    args = parse_args()
    report = run_report(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(stable_json(report, pretty=True) + "\n", encoding="utf-8")
    print(stable_json(report, pretty=args.pretty))


if __name__ == "__main__":
    main()
