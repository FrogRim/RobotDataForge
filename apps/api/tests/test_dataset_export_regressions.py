from __future__ import annotations

import json
from pathlib import Path

from tests.test_api_contract import make_client, valid_task_payload, valid_trajectory_payload


def complete_episode(client, task_id: str, trajectory: dict) -> dict:
    episode_response = client.post(
        "/api/episodes/start",
        json={"task_id": task_id, "contributor_id": "user_001"},
    )
    assert episode_response.status_code == 200
    episode_id = episode_response.json()["episode_id"]
    complete_response = client.post(
        f"/api/episodes/{episode_id}/complete",
        json={"trajectory": trajectory},
    )
    assert complete_response.status_code == 200
    return complete_response.json()


def failed_trajectory_payload() -> dict:
    trajectory = valid_trajectory_payload()
    for frame in trajectory["frames"]:
        frame["end_effector_position"] = [0.15, 0.5]
        frame["object_position"] = [0.15, 0.5]
    trajectory["summary"]["duration_sec"] = 6.0
    return trajectory


def export_payload(task_id: str, name: str, only_success: bool) -> dict:
    return {
        "task_id": task_id,
        "name": name,
        "only_success": only_success,
        "min_quality_score": 0.7,
        "export_format": "json",
    }


def read_export(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def test_export_uses_server_generated_file_id_for_path_traversal_name(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    task_response = client.post("/api/tasks", json=valid_task_payload())
    task_id = task_response.json()["id"]
    complete_episode(client, task_id, valid_trajectory_payload())

    escape_target = tmp_path / "rdf_escape.json"
    dataset_response = client.post(
        "/api/datasets/export",
        json=export_payload(task_id, f"../{escape_target.stem}", only_success=True),
    )

    assert dataset_response.status_code == 200
    export_path = Path(dataset_response.json()["export_path"]).resolve()
    exports_dir = (tmp_path / "storage" / "exports").resolve()
    assert export_path.is_relative_to(exports_dir)
    assert export_path.name.startswith("dataset_")
    assert not escape_target.exists()

    client.app.dependency_overrides.clear()


def test_export_only_success_false_includes_failed_episodes(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    task_response = client.post("/api/tasks", json=valid_task_payload())
    task_id = task_response.json()["id"]
    complete_episode(client, task_id, valid_trajectory_payload())
    complete_episode(client, task_id, failed_trajectory_payload())

    success_only_response = client.post(
        "/api/datasets/export",
        json=export_payload(task_id, "success_only", only_success=True),
    )
    assert success_only_response.status_code == 200
    success_only = client.get("/api/datasets").json()[0]
    assert success_only["num_episodes"] == 1
    assert success_only["num_success"] == 1
    assert success_only["num_failed"] == 0
    success_only_export = read_export(success_only_response.json()["export_path"])
    assert len(success_only_export["episodes"]) == 1

    all_response = client.post(
        "/api/datasets/export",
        json=export_payload(task_id, "all_episodes", only_success=False),
    )
    assert all_response.status_code == 200
    all_dataset = client.get("/api/datasets").json()[0]
    assert all_dataset["num_episodes"] == 2
    assert all_dataset["num_success"] == 1
    assert all_dataset["num_failed"] == 1
    all_export = read_export(all_response.json()["export_path"])
    assert len(all_export["episodes"]) == 2
    assert {item["evaluation"]["success"] for item in all_export["episodes"]} == {True, False}

    client.app.dependency_overrides.clear()
