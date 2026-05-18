#!/usr/bin/env python3
"""Submit a local MVP-0 trajectory to the Robot Data Forge API.

This script is the stable local-recorder boundary for #18.12. Real Isaac frame
hooks should feed the same submit flow. Until that hook exists, --mock-submit
uses MockSimAdapter and prints that fallback explicitly.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen

API_ROOT = Path(__file__).resolve().parents[1] / "apps" / "api"
sys.path.insert(0, str(API_ROOT))

from app.adapters import MockSimAdapter, select_collection_adapter


def post_json(api_base: str, path: str, payload: dict) -> dict:
    request = Request(
        f"{api_base.rstrip('/')}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8")
        raise RuntimeError(f"POST {path} failed: {exc.code} {body}") from exc


def default_task_payload() -> dict:
    return {
        "name": "MVP-0 Franka Stack Smoke Test",
        "description": "Engineering smoke test for the Quest/OpenXR/Isaac Lab collection loop.",
        "task_type": "franka_stack_smoke_test",
        "environment_config": {
            "target_position": [0.75, 0.5],
            "success_tolerance": 0.03,
        },
        "success_criteria": {
            "distance_to_target_max": 0.03,
            "min_stable_steps": 2,
            "max_completion_time_sec": 30,
        },
    }


def build_mock_trajectory(task_id: str, episode_id: str) -> dict:
    adapter = MockSimAdapter()
    trajectory = adapter.sample_success_trajectory(task_id, episode_id)
    trajectory.pop("id", None)
    trajectory.pop("episode_id", None)
    trajectory.pop("task_id", None)
    trajectory["source"] = {
        "input_device": "quest3_handtracking",
        "runtime": "steamvr_openxr",
        "simulator": "isaac_lab",
        "robot": "franka",
        "task_name": "Isaac-Stack-Cube-Franka-IK-Rel-v0",
    }
    return trajectory


def submit_mock_episode(api_base: str, contributor_id: str) -> dict:
    task = post_json(api_base, "/api/tasks", default_task_payload())
    task_id = task["id"]
    session = post_json(
        api_base,
        "/api/collection-sessions/start",
        {
            "task_id": task_id,
            "contributor_id": contributor_id,
            "isaac_task_name": "Isaac-Stack-Cube-Franka-IK-Rel-v0",
            "input_device": "quest3_handtracking",
            "xr_runtime": "steamvr_openxr",
            "streaming_stack": "alvr",
        },
    )
    post_json(
        api_base,
        f"/api/collection-sessions/{session['session_id']}/complete",
        {
            "runtime_metrics": {
                "average_fps": 72,
                "frame_drop_rate": 0.04,
                "hand_tracking_loss_rate": 0.03,
                "average_input_latency_ms": 35,
                "session_crashed": False,
            }
        },
    )
    episode = post_json(
        api_base,
        "/api/episodes/start",
        {
            "task_id": task_id,
            "contributor_id": contributor_id,
            "collection_session_id": session["session_id"],
        },
    )
    trajectory = build_mock_trajectory(task_id, episode["episode_id"])
    completed = post_json(
        api_base,
        f"/api/episodes/{episode['episode_id']}/complete",
        {
            "trajectory": trajectory,
            "unit_economics": {
                "human_time_per_episode": 6.0,
                "compute_time_per_episode": 0.1,
                "cost_per_recorded_episode": 0.01,
                "cost_per_valid_episode": 0.01,
                "cost_per_accepted_trajectory": 0.01,
            },
        },
    )
    return {
        "task_id": task_id,
        "session_id": session["session_id"],
        "episode_id": episode["episode_id"],
        **completed,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-base", default="http://localhost:8000")
    parser.add_argument("--contributor-id", default="user_001")
    parser.add_argument("--mock-submit", action="store_true", help="Submit a fallback/debug trajectory to the API.")
    args = parser.parse_args()

    selection = select_collection_adapter()
    if selection.fallback_used:
        print(f"FALLBACK: {selection.reason}")
    else:
        print(f"PRIMARY: {selection.adapter.build_command('Isaac-Stack-Cube-Franka-IK-Rel-v0')}")

    if not args.mock_submit:
        print("No episode submitted. Use --mock-submit to exercise backend submit flow.")
        return

    result = submit_mock_episode(args.api_base, args.contributor_id)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
