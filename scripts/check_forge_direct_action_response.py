#!/usr/bin/env python3
"""Check whether Forge direct insertion live-control actions move the robot fingertip.

Run this with Isaac's Python, not regular uv Python:

    /home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/check_forge_direct_action_response.py --pretty

The script is intentionally HMD-free. By default it verifies the MVP-1 live
collection semantics: Forge/Factory-like direct environments use RDF
bounded_direct_ee_target, a bounded hand-target to EEF-target servo. The older
operator_follow, lower-level cartesian_delta, and legacy Forge asset-relative
paths can still be checked explicitly, but they are not the primary collection
UX.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
from types import MethodType
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "storage" / "logs" / "forge_direct_action_response.json"
DEFAULT_TASK = "Isaac-Forge-PegInsert-Direct-v0"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", default=DEFAULT_TASK)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--steps", type=int, default=30)
    parser.add_argument(
        "--control-mode",
        choices=("bounded_direct_ee_target", "operator_follow", "cartesian_delta", "asset_relative"),
        default="bounded_direct_ee_target",
        help="Control semantics to verify. bounded_direct_ee_target is the current MVP-1 live teleop collection path.",
    )
    parser.add_argument("--direct-ee-pos-gain", type=float, default=0.18)
    parser.add_argument("--direct-ee-rot-gain", type=float, default=0.25)
    parser.add_argument("--direct-ee-max-step-m", type=float, default=0.06)
    parser.add_argument("--direct-ee-max-rot-step-rad", type=float, default=0.20)
    parser.add_argument("--direct-ee-smoothing-alpha", type=float, default=0.95)
    parser.add_argument("--direct-ee-deadzone-m", type=float, default=0.0001)
    parser.add_argument("--direct-ee-workspace-radius-m", type=float, default=0.35)
    parser.add_argument("--operator-follow-preset", choices=("safe", "fast", "responsive"), default="safe")
    parser.add_argument("--operator-follow-workspace-gain", type=float, default=-1.0)
    parser.add_argument("--operator-follow-max-step-m", type=float, default=-1.0)
    parser.add_argument("--operator-follow-smoothing-alpha", type=float, default=-1.0)
    parser.add_argument("--operator-follow-deadzone-m", type=float, default=-1.0)
    parser.add_argument("--operator-follow-workspace-radius-m", type=float, default=-1.0)
    parser.add_argument("--cartesian-pos-gain", type=float, default=3.0)
    parser.add_argument("--cartesian-rot-gain", type=float, default=1.0)
    parser.add_argument("--cartesian-ema", type=float, default=1.0)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--no-headless", action="store_true")
    return parser.parse_args(argv)


def stable_json(payload: dict[str, Any], *, pretty: bool) -> str:
    if pretty:
        return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def refresh_env(env: Any) -> None:
    if hasattr(env, "_compute_intermediate_values"):
        env._compute_intermediate_values(dt=env.physics_dt)


def vec3(value: Any) -> list[float]:
    if hasattr(value, "detach"):
        value = value.detach()
    if hasattr(value, "cpu"):
        value = value.cpu()
    if hasattr(value, "tolist"):
        value = value.tolist()
    if value and isinstance(value[0], list):
        value = value[0]
    return [float(item) for item in value[:3]]


def delta_norm(before: list[float], after: list[float]) -> float:
    return sum((after[index] - before[index]) ** 2 for index in range(3)) ** 0.5


def tensor_norm(value: Any) -> float:
    import torch

    return float(torch.linalg.vector_norm(value).item())


def clamp_vector_norm(vector: Any, max_norm: float):
    import torch

    if max_norm <= 0.0:
        return torch.zeros_like(vector)
    norm = torch.linalg.vector_norm(vector)
    if float(norm.item()) <= max_norm:
        return vector
    return vector * (max_norm / (norm + 1.0e-9))


def set_env_ema(env: Any, value: float) -> None:
    value = max(0.0, min(1.0, float(value)))
    if hasattr(env, "ema_factor"):
        if hasattr(env.ema_factor, "fill_"):
            env.ema_factor.fill_(value)
        else:
            env.ema_factor = value


def reset_env_actions(env: Any) -> None:
    if hasattr(env, "actions"):
        env.actions.zero_()
    if hasattr(env, "prev_actions"):
        env.prev_actions.zero_()
    if hasattr(env, "pos_threshold"):
        import torch

        env.delta_pos = torch.zeros((env.num_envs, 3), device=env.device)
    if hasattr(env, "rot_threshold"):
        import torch

        env.delta_yaw = torch.zeros((env.num_envs,), device=env.device)
    if hasattr(env, "rdf_operator_follow_direct_target_pos"):
        env.rdf_operator_follow_direct_target_pos = None
    if hasattr(env, "rdf_direct_ee_target_pos"):
        env.rdf_direct_ee_target_pos = None


def apply_cartesian_delta_action(env: Any) -> None:
    from isaaclab_tasks.direct.factory.factory_env import FactoryEnv
    import torch

    FactoryEnv._apply_action(env)
    if hasattr(env, "actions") and hasattr(env, "pos_threshold"):
        env.delta_pos = env.actions[:, 0:3] * env.pos_threshold
    if hasattr(env, "actions") and hasattr(env, "rot_threshold") and env.actions.shape[-1] >= 6:
        env.delta_yaw = env.actions[:, 5] * env.rot_threshold[:, 2]
    elif hasattr(env, "rot_threshold"):
        env.delta_yaw = torch.zeros((env.num_envs,), device=env.device)


def apply_operator_follow_direct_action(env: Any) -> None:
    import torch

    if getattr(env, "last_update_timestamp", 0.0) < env._robot._data._sim_timestamp:
        env._compute_intermediate_values(dt=env.physics_dt)

    target_pos = getattr(env, "rdf_direct_ee_target_pos", None)
    if target_pos is None:
        target_pos = getattr(env, "rdf_operator_follow_direct_target_pos", None)
    if target_pos is None:
        apply_cartesian_delta_action(env)
        return

    target_pos = target_pos.to(device=env.device, dtype=env.fingertip_midpoint_pos.dtype)
    if target_pos.ndim == 1:
        target_pos = target_pos.unsqueeze(0)
    if target_pos.shape[0] != env.num_envs:
        target_pos = target_pos[0:1].repeat(env.num_envs, 1)

    env.delta_pos = target_pos - env.fingertip_midpoint_pos
    if hasattr(env, "rot_threshold"):
        env.delta_yaw = torch.zeros((env.num_envs,), device=env.device)
    env.generate_ctrl_signals(
        ctrl_target_fingertip_midpoint_pos=target_pos,
        ctrl_target_fingertip_midpoint_quat=env.fingertip_midpoint_quat,
        ctrl_target_gripper_dof_pos=0.0,
    )


def enable_cartesian_delta_control(env: Any, *, ema: float) -> None:
    env._apply_action = MethodType(apply_cartesian_delta_action, env)
    reset_env_actions(env)
    set_env_ema(env, ema)


def enable_operator_follow_direct_control(env: Any, *, ema: float) -> None:
    env._apply_action = MethodType(apply_operator_follow_direct_action, env)
    reset_env_actions(env)
    set_env_ema(env, ema)


def enable_bounded_direct_ee_target_control(env: Any, *, ema: float) -> None:
    env._apply_action = MethodType(apply_operator_follow_direct_action, env)
    reset_env_actions(env)
    set_env_ema(env, ema)


def build_cartesian_delta_action(env: Any, delta_xyz: list[float], args: argparse.Namespace):
    import torch

    action_dim = int(env.action_space.shape[-1])
    action = torch.zeros((1, action_dim), dtype=torch.float32, device=env.device)
    delta = torch.tensor(delta_xyz, dtype=torch.float32, device=env.device)
    action[0, 0:3] = torch.clamp(delta * float(args.cartesian_pos_gain), -1.0, 1.0)
    if action_dim >= 6:
        action[0, 3:6] = 0.0 * float(args.cartesian_rot_gain)
    if action_dim >= 7:
        action[0, 6] = -1.0
    return action


def operator_follow_preset_defaults(preset: str) -> dict[str, float]:
    if preset == "responsive":
        return {
            "workspace_gain": 0.12,
            "max_step_m": 0.04,
            "smoothing_alpha": 0.90,
            "deadzone_m": 0.0002,
            "workspace_radius_m": 0.25,
        }
    if preset == "fast":
        return {
            "workspace_gain": 0.06,
            "max_step_m": 0.02,
            "smoothing_alpha": 0.70,
            "deadzone_m": 0.0003,
            "workspace_radius_m": 0.12,
        }
    return {
        "workspace_gain": 0.03,
        "max_step_m": 0.01,
        "smoothing_alpha": 0.35,
        "deadzone_m": 0.0005,
        "workspace_radius_m": 0.09,
    }


def operator_follow_config(args: argparse.Namespace) -> dict[str, float | str]:
    defaults = operator_follow_preset_defaults(args.operator_follow_preset)

    def override(name: str, value: float) -> float:
        return float(defaults[name] if value < 0.0 else value)

    return {
        "preset": args.operator_follow_preset,
        "workspace_gain": max(0.0, override("workspace_gain", args.operator_follow_workspace_gain)),
        "max_step_m": max(0.0, override("max_step_m", args.operator_follow_max_step_m)),
        "smoothing_alpha": max(0.0, min(1.0, override("smoothing_alpha", args.operator_follow_smoothing_alpha))),
        "deadzone_m": max(0.0, override("deadzone_m", args.operator_follow_deadzone_m)),
        "workspace_radius_m": max(0.0, override("workspace_radius_m", args.operator_follow_workspace_radius_m)),
    }


def bounded_direct_ee_config(args: argparse.Namespace) -> dict[str, float | str]:
    return {
        "preset": "bounded_direct_ee_target",
        "workspace_gain": max(0.0, float(args.direct_ee_pos_gain)),
        "position_gain": max(0.0, float(args.direct_ee_pos_gain)),
        "rotation_gain": max(0.0, float(args.direct_ee_rot_gain)),
        "max_step_m": max(0.0, float(args.direct_ee_max_step_m)),
        "max_rot_step_rad": max(0.0, float(args.direct_ee_max_rot_step_rad)),
        "smoothing_alpha": max(0.0, min(1.0, float(args.direct_ee_smoothing_alpha))),
        "deadzone_m": max(0.0, float(args.direct_ee_deadzone_m)),
        "workspace_radius_m": max(0.0, float(args.direct_ee_workspace_radius_m)),
        "control_semantics": "bounded_direct_end_effector_target_servo",
    }


class OperatorFollowSmoke:
    def __init__(self, env: Any, config: dict[str, float | str]):
        import torch

        refresh_env(env)
        self.config = config
        self.anchor_pos = env.fingertip_midpoint_pos[0].detach().clone()
        self.target_pos = self.anchor_pos.clone()
        self.previous_step = torch.zeros_like(self.anchor_pos)

    def build_action(self, env: Any, delta_xyz: list[float]):
        import torch

        refresh_env(env)
        action_dim = int(env.action_space.shape[-1])
        action = torch.zeros((1, action_dim), dtype=torch.float32, device=env.device)
        current_pos = env.fingertip_midpoint_pos[0]
        input_delta = torch.tensor(delta_xyz, dtype=torch.float32, device=env.device)
        hand_delta_m = input_delta * float(self.config["workspace_gain"])
        if tensor_norm(hand_delta_m) < float(self.config["deadzone_m"]):
            hand_delta_m.zero_()
        self.target_pos = self.target_pos + hand_delta_m
        target_offset = self.target_pos - self.anchor_pos
        self.target_pos = self.anchor_pos + clamp_vector_norm(target_offset, float(self.config["workspace_radius_m"]))
        error = self.target_pos - current_pos
        raw_step = clamp_vector_norm(error, float(self.config["max_step_m"]))
        alpha = float(self.config["smoothing_alpha"])
        command_step = alpha * raw_step + (1.0 - alpha) * self.previous_step
        command_step = clamp_vector_norm(command_step, float(self.config["max_step_m"]))
        self.previous_step = command_step.detach().clone()
        target_attr = (
            "rdf_direct_ee_target_pos"
            if self.config.get("preset") == "bounded_direct_ee_target"
            else "rdf_operator_follow_direct_target_pos"
        )
        setattr(env, target_attr, (current_pos + command_step).detach().clone().unsqueeze(0))
        action[0, 0:3] = torch.clamp(command_step / torch.clamp(env.pos_threshold[0], min=1.0e-6), -1.0, 1.0)
        if action_dim >= 7:
            action[0, 6] = -1.0
        return action


def build_asset_relative_action_from_delta(env: Any, delta_xyz: list[float]):
    import torch

    refresh_env(env)
    action_dim = int(env.action_space.shape[-1])
    action = torch.zeros((1, action_dim), dtype=torch.float32, device=env.device)
    fingertip_pos = env.fingertip_midpoint_pos[0]
    fixed_action_frame = (env.fixed_pos_obs_frame + env.init_fixed_pos_obs_noise)[0]
    pos_threshold = env.pos_threshold[0]
    pos_bounds = torch.tensor(env.cfg.ctrl.pos_action_bounds, dtype=torch.float32, device=env.device)
    delta = torch.tensor(delta_xyz, dtype=torch.float32, device=env.device)

    target_pos = fingertip_pos + delta * pos_threshold
    action[0, 0:3] = torch.clamp((target_pos - fixed_action_frame) / pos_bounds, -1.0, 1.0)
    if hasattr(env, "actions") and env.actions.shape[-1] >= 7:
        action[0, 5] = env.actions[0, 5]
    action[0, 6] = -1.0
    return action


def run_check(args: argparse.Namespace) -> dict[str, Any]:
    from isaaclab.app import AppLauncher

    app_launcher = AppLauncher(
        {
            "headless": not args.no_headless,
            "device": args.device,
            "enable_cameras": False,
        }
    )
    simulation_app = app_launcher.app

    import gymnasium as gym

    import isaaclab_tasks  # noqa: F401
    from isaaclab_tasks.utils import parse_env_cfg

    env = None
    patterns = {
        "zero": [0.0, 0.0, 0.0],
        "plus_x": [1.0, 0.0, 0.0],
        "plus_y": [0.0, 1.0, 0.0],
        "plus_z": [0.0, 0.0, 1.0],
        "minus_z": [0.0, 0.0, -1.0],
    }
    results: list[dict[str, Any]] = []
    try:
        env_cfg = parse_env_cfg(args.task, device=args.device, num_envs=1)
        env = gym.make(args.task, cfg=env_cfg).unwrapped
        target_config = None
        if args.control_mode == "bounded_direct_ee_target":
            target_config = bounded_direct_ee_config(args)
            enable_bounded_direct_ee_target_control(env, ema=args.cartesian_ema)
        elif args.control_mode == "operator_follow":
            target_config = operator_follow_config(args)
            enable_operator_follow_direct_control(env, ema=args.cartesian_ema)
        elif args.control_mode == "cartesian_delta":
            enable_cartesian_delta_control(env, ema=args.cartesian_ema)
        for name, delta_xyz in patterns.items():
            env.reset()
            reset_env_actions(env)
            if args.control_mode in {"bounded_direct_ee_target", "operator_follow", "cartesian_delta"}:
                set_env_ema(env, args.cartesian_ema)
            refresh_env(env)
            before = vec3(env.fingertip_midpoint_pos)
            if args.control_mode in {"bounded_direct_ee_target", "operator_follow"}:
                assert target_config is not None
                follower = OperatorFollowSmoke(env, target_config)
                action = None
                for step_index in range(max(args.steps, 1)):
                    step_input = delta_xyz if step_index < 5 else [0.0, 0.0, 0.0]
                    action = follower.build_action(env, step_input)
                    env.step(action)
                    if not simulation_app.is_running():
                        break
            elif args.control_mode == "cartesian_delta":
                action = build_cartesian_delta_action(env, delta_xyz, args)
                for _ in range(max(args.steps, 1)):
                    env.step(action)
                    if not simulation_app.is_running():
                        break
            else:
                action = build_asset_relative_action_from_delta(env, delta_xyz)
                for _ in range(max(args.steps, 1)):
                    env.step(action)
                    if not simulation_app.is_running():
                        break
            refresh_env(env)
            after = vec3(env.fingertip_midpoint_pos)
            results.append(
                {
                    "name": name,
                    "input_delta_xyz": delta_xyz,
                    "start_fingertip_pos": before,
                    "end_fingertip_pos": after,
                    "fingertip_delta_norm": delta_norm(before, after),
                    "step_action_xyz": vec3(action),
                }
            )
    finally:
        if env is not None:
            env.close()

    moved_patterns = [row for row in results if row["name"] != "zero" and row["fingertip_delta_norm"] > 0.001]
    return {
        "schema_version": "rdf_forge_direct_action_response_v0.1.0",
        "created_at": datetime.now(UTC).isoformat(),
        "task": args.task,
        "device": args.device,
        "steps": args.steps,
        "control_mode": args.control_mode,
        "bounded_direct_ee_target": bounded_direct_ee_config(args)
        if args.control_mode == "bounded_direct_ee_target"
        else None,
        "operator_follow": operator_follow_config(args) if args.control_mode == "operator_follow" else None,
        "cartesian_delta": {
            "position_gain": args.cartesian_pos_gain,
            "rotation_gain": args.cartesian_rot_gain,
            "ema_factor": args.cartesian_ema,
            "control_semantics": "current_fingertip_delta",
        }
        if args.control_mode == "cartesian_delta"
        else None,
        "passed": bool(moved_patterns),
        "results": results,
        "recommendations": [
            "Use control_mode=bounded_direct_ee_target for the current Quest/Isaac live teleop collection proof.",
            "If passed=false in bounded_direct_ee_target mode, fix RDF direct EEF target servo before debugging Quest handtracking.",
            "If passed=true but live robot still does not move, inspect Teleop control mode, action_debug, and motion_debug during Start XR.",
        ],
    }


def main() -> None:
    args = parse_args()
    report = run_check(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(stable_json(report, pretty=True) + "\n", encoding="utf-8")
    print(stable_json(report, pretty=args.pretty))


if __name__ == "__main__":
    main()
