#!/usr/bin/env python3
"""Capture MVP-3C Isaac Sim embodiment source evidence.

Run this script with Isaac Sim Kit Python, not the uv environment:

    /home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/capture_mvp3c_isaac_sim_embodiment_source.py --pretty

The script deliberately keeps Isaac imports inside the runtime capture function so
regular pytest can import/inspect this file without launching Isaac Sim.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    ROOT
    / "storage"
    / "proof_evidence"
    / "mvp3c_isaac_sim_embodiment_source"
    / "runtime_capture.json"
)
SOURCE_KIND = "isaac_sim_runtime_backed_command_state_log"
TASK_NAME = "mvp3c_isaac_sim_embodiment_source"
REQUIRED_ACTION_ROLES = (
    "teleop_intent",
    "executed_control",
    "learning_action",
    "retargeted_robot_action",
)
EMBODIMENT_SPECS = (
    {
        "embodiment_id": "franka_panda_isaac_sim",
        "prim_path": "/World/Franka",
        "asset_rel_path": "/Isaac/Robots/FrankaRobotics/FrankaPanda/franka.usd",
        "end_effector_prim_path": "/World/Franka/panda_rightfinger",
    },
    {
        "embodiment_id": "universal_robots_ur10e_isaac_sim",
        "prim_path": "/World/UR10e",
        "asset_rel_path": "/Isaac/Robots/UniversalRobots/ur10e/ur10e.usd",
        "end_effector_prim_path": "/World/UR10e/ee_link",
    },
)


def capture_runtime_evidence(
    *,
    output: Path = DEFAULT_OUTPUT,
    steps: int = 5,
    headless: bool = True,
    pretty: bool = False,
    close_app: bool = False,
) -> dict[str, Any]:
    from isaacsim import SimulationApp

    simulation_app = SimulationApp({"headless": headless})
    payload = _capture_with_running_app(steps=max(1, steps))
    write_json(output, payload, pretty=pretty)
    if close_app:
        simulation_app.close()
    return payload


def _capture_with_running_app(*, steps: int) -> dict[str, Any]:
    import numpy as np
    from isaacsim.core.api import World
    from isaacsim.core.utils.stage import add_reference_to_stage
    from isaacsim.core.utils.types import ArticulationAction
    from isaacsim.robot.manipulators import SingleManipulator
    from isaacsim.storage.native import get_assets_root_path

    World.clear_instance()
    world = World()
    world.scene.add_default_ground_plane()
    assets_root = get_assets_root_path()
    if not assets_root:
        raise RuntimeError("Isaac Sim assets root was not available")

    robot_entries = []
    for spec in EMBODIMENT_SPECS:
        usd_path = assets_root + spec["asset_rel_path"]
        prim = add_reference_to_stage(usd_path=usd_path, prim_path=spec["prim_path"])
        robot = world.scene.add(
            SingleManipulator(
                prim_path=spec["prim_path"],
                name=spec["embodiment_id"],
                end_effector_prim_path=spec["end_effector_prim_path"],
            )
        )
        robot_entries.append({"spec": spec, "prim": prim, "robot": robot, "usd_path": usd_path})

    world.reset()
    for _ in range(steps):
        world.step(render=False)

    captured: dict[str, Any] = {}
    for entry in robot_entries:
        captured[entry["spec"]["embodiment_id"]] = _capture_robot(
            world=world,
            entry=entry,
            np=np,
            articulation_action_cls=ArticulationAction,
        )

    return {
        "schema_version": "rdf_mvp3c_isaac_sim_runtime_capture_v0.1.0",
        "status": "runtime_evidence_captured",
        "evidence_kind": "isaac_sim_runtime_backed_source_log",
        "captured_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "runtime": "isaac_sim",
        "simulator": "isaac_sim",
        "platform": "linux",
        "task_name": TASK_NAME,
        "embodiments": captured,
    }


def _capture_robot(
    *,
    world: Any,
    entry: dict[str, Any],
    np: Any,
    articulation_action_cls: Any,
) -> dict[str, Any]:
    spec = entry["spec"]
    embodiment_id = spec["embodiment_id"]
    robot = entry["robot"]
    capture_id = capture_id_for(embodiment_id)

    before = _joint_state(robot)
    target_positions = list(before["positions"])
    if target_positions:
        target_positions[0] = float(target_positions[0]) + 0.001

    action_command_writable = False
    try:
        robot.apply_action(articulation_action_cls(joint_positions=np.array(target_positions)))
        action_command_writable = True
    except Exception:
        action_command_writable = False

    world.step(render=False)
    after = _joint_state(robot)

    source_rows = {
        "accepted": [
            _source_row(
                embodiment_id=embodiment_id,
                capture_id=capture_id,
                accepted=True,
                row_index=0,
                state=before,
                target_positions=target_positions,
            )
        ],
        "rejected": [
            _source_row(
                embodiment_id=embodiment_id,
                capture_id=capture_id,
                accepted=False,
                row_index=0,
                state=after,
                target_positions=target_positions,
            )
        ],
    }
    return {
        "runtime_metadata": {
            "schema_version": "rdf_mvp3c_runtime_metadata_v0.1.0",
            "embodiment_id": embodiment_id,
            "runtime_capture_id": capture_id,
            "runtime": "isaac_sim",
            "simulator": "isaac_sim",
            "platform": "linux",
            "source_kind": SOURCE_KIND,
            "capture_origin": "isaac_sim_process",
            "asset_path": entry["usd_path"],
            "prim_path": spec["prim_path"],
            "real_robot_success": False,
            "physical_robot_readiness": False,
            "live_runtime_support": False,
        },
        "preflight": {
            "schema_version": "rdf_mvp3c_preflight_v0.1.0",
            "embodiment_id": embodiment_id,
            "runtime_capture_id": capture_id,
            "asset_loaded": bool(entry["prim"].IsValid()),
            "articulation_detected": bool(before["positions"]),
            "joint_state_readable": bool(before["readable"]),
            "action_command_writable": bool(action_command_writable),
            "source_log_rows_emitted": 2,
            "runtime_metadata_recorded": True,
        },
        "source_rows": source_rows,
    }


def _joint_state(robot: Any) -> dict[str, Any]:
    state = robot.get_joints_state()
    positions = _float_list(getattr(state, "positions", []))
    velocities = _float_list(getattr(state, "velocities", []))
    return {
        "readable": True,
        "positions": positions,
        "velocities": velocities,
        "eef_pose": _eef_pose(robot),
    }


def _eef_pose(robot: Any) -> list[float]:
    try:
        position, orientation = robot.end_effector.get_world_pose()
    except Exception as exc:
        raise RuntimeError("end effector pose unreadable") from exc
    pose = _float_list(position)[:3] + _float_list(orientation)[:4]
    if len(pose) != 7:
        raise RuntimeError(
            f"end effector pose unreadable: expected 7 values, got {len(pose)}"
        )
    return pose


def _source_row(
    *,
    embodiment_id: str,
    capture_id: str,
    accepted: bool,
    row_index: int,
    state: dict[str, Any],
    target_positions: list[float],
) -> dict[str, Any]:
    positions = list(state["positions"])
    action_delta = [
        float(target_positions[index]) - float(positions[index])
        for index in range(min(len(target_positions), len(positions)))
    ]
    actions_by_role = {
        "teleop_intent": action_delta,
        "executed_control": target_positions,
        "learning_action": target_positions,
        "retargeted_robot_action": target_positions,
    }
    return {
        "embodiment_id": embodiment_id,
        "runtime_capture_id": capture_id,
        "row_id": f"{embodiment_id}_{'accepted' if accepted else 'rejected'}_{row_index}",
        "timestamp_ns": 1_000_000 if accepted else 2_000_000,
        "runtime": "isaac_sim",
        "simulator": "isaac_sim",
        "source_kind": SOURCE_KIND,
        "accepted": accepted,
        "command_state": {
            "joint_positions": positions,
            "joint_velocities": list(state["velocities"]),
            "eef_pose": list(state["eef_pose"]),
            "actions_by_role": actions_by_role,
        },
    }


def _float_list(value: Any) -> list[float]:
    if value is None:
        return []
    if hasattr(value, "detach"):
        value = value.detach()
    if hasattr(value, "cpu"):
        value = value.cpu()
    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, (int, float)):
        return [float(value)]
    if isinstance(value, (list, tuple)):
        values: list[float] = []
        for item in value:
            values.extend(_float_list(item))
        return values
    return []


def capture_id_for(embodiment_id: str) -> str:
    return f"{embodiment_id}_runtime_capture_20260622T010000Z"


def stable_json(payload: Any, *, pretty: bool) -> str:
    if pretty:
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2)
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def write_json(path: Path, payload: dict[str, Any], *, pretty: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(payload, pretty=pretty) + "\n", encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--steps", type=int, default=5)
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--no-headless", action="store_true")
    parser.add_argument(
        "--close-app",
        action="store_true",
        help="Call SimulationApp.close() after writing evidence. Off by default because Isaac Sim 5.1 can terminate before caller-side handling completes.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = capture_runtime_evidence(
        output=args.output,
        steps=args.steps,
        headless=not args.no_headless,
        pretty=args.pretty,
        close_app=args.close_app,
    )
    print(stable_json({"status": payload["status"], "output": str(args.output)}, pretty=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
