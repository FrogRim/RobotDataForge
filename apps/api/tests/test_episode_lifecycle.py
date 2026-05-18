from __future__ import annotations

import json
from pathlib import Path

from tests.test_api_contract import make_client, valid_task_payload, valid_trajectory_payload


def create_task_and_episode(client) -> tuple[str, str]:
    task_response = client.post("/api/tasks", json=valid_task_payload())
    assert task_response.status_code == 200
    task_id = task_response.json()["id"]
    episode_response = client.post(
        "/api/episodes/start",
        json={"task_id": task_id, "contributor_id": "user_001"},
    )
    assert episode_response.status_code == 200
    return task_id, episode_response.json()["episode_id"]


def empty_trajectory_payload() -> dict:
    trajectory = valid_trajectory_payload()
    trajectory["frames"] = []
    trajectory["summary"] = {"duration_sec": 0.0}
    return trajectory


def test_episode_start_uses_running_status(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    task_response = client.post("/api/tasks", json=valid_task_payload())
    assert task_response.status_code == 200
    episode_response = client.post(
        "/api/episodes/start",
        json={"task_id": task_response.json()["id"], "contributor_id": "user_001"},
    )
    assert episode_response.status_code == 200
    assert episode_response.json()["status"] == "running"
    app_cleanup()


def test_success_finalize_is_separate_from_evaluation_result(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    _, episode_id = create_task_and_episode(client)
    response = client.post(
        f"/api/episodes/{episode_id}/finalize",
        json={
            "trajectory": valid_trajectory_payload(),
            "episode_status": "success",
            "episode_finalize_reason": "operator_success",
            "unit_economics": {"human_time_per_episode": 6.0},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["episode_status"] == "success"
    assert body["success"] is True

    episode = client.get(f"/api/episodes/{episode_id}").json()
    assert episode["status"] == "success"
    assert episode["accepted"] is True
    assert episode["finalize_reason"] == "operator_success"

    trajectory_path = tmp_path / "storage" / "trajectories" / f"{body['trajectory_id']}.json"
    summary = json.loads(trajectory_path.read_text())["summary"]
    assert summary["episode_status"] == "success"
    assert summary["episode_finalize_reason"] == "operator_success"
    assert summary["episode_started_at"]
    assert summary["episode_finalized_at"]
    app_cleanup()


def test_failure_finalize_can_store_failure_note_even_if_evaluator_succeeds(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    _, episode_id = create_task_and_episode(client)
    response = client.post(
        f"/api/episodes/{episode_id}/finalize",
        json={
            "trajectory": valid_trajectory_payload(),
            "episode_status": "failure",
            "episode_finalize_reason": "operator_failure",
            "episode_failure_reason": "OPERATOR_MARKED_FAILURE",
            "episode_failure_note": "Operator stopped because hand mapping felt wrong.",
        },
    )
    assert response.status_code == 200
    assert response.json()["episode_status"] == "failure"
    assert response.json()["success"] is True

    episode = client.get(f"/api/episodes/{episode_id}").json()
    assert episode["status"] == "failure"
    assert episode["accepted"] is False
    assert episode["failure_reason"] == "OPERATOR_MARKED_FAILURE"
    assert episode["failure_note"] == "Operator stopped because hand mapping felt wrong."
    app_cleanup()


def test_reset_finalize_is_distinguishable_from_success_or_failure(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    _, episode_id = create_task_and_episode(client)
    response = client.post(
        f"/api/episodes/{episode_id}/finalize",
        json={
            "trajectory": valid_trajectory_payload(),
            "episode_status": "reset",
            "episode_finalize_reason": "operator_reset",
            "reset_count": 2,
        },
    )
    assert response.status_code == 200
    assert response.json()["episode_status"] == "reset"

    episode = client.get(f"/api/episodes/{episode_id}").json()
    assert episode["status"] == "reset"
    assert episode["accepted"] is False
    assert episode["reset_count"] == 2
    app_cleanup()


def test_incomplete_episode_is_marked_without_replayable_frames(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    _, episode_id = create_task_and_episode(client)
    response = client.post(
        f"/api/episodes/{episode_id}/finalize",
        json={
            "trajectory": empty_trajectory_payload(),
            "episode_status": "incomplete",
            "episode_finalize_reason": "sim_shutdown",
            "episode_failure_note": "Isaac closed before operator finalized the episode.",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["episode_status"] == "incomplete"
    assert body["success"] is False

    episode = client.get(f"/api/episodes/{episode_id}").json()
    assert episode["status"] == "incomplete"
    assert episode["replayable"] is False
    assert episode["invalid_reason"] == "sim_shutdown"
    app_cleanup()


def test_legacy_complete_request_still_works(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    _, episode_id = create_task_and_episode(client)
    response = client.post(
        f"/api/episodes/{episode_id}/complete",
        json={"trajectory": valid_trajectory_payload()},
    )
    assert response.status_code == 200
    assert response.json()["episode_status"] == "success"
    assert response.json()["success"] is True

    episode = client.get(f"/api/episodes/{episode_id}").json()
    assert episode["status"] == "success"
    app_cleanup()


def test_evaluator_remains_compatible_with_lifecycle_metadata(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    _, episode_id = create_task_and_episode(client)
    trajectory = valid_trajectory_payload()
    trajectory["summary"]["episode_status"] = "success"
    trajectory["summary"]["episode_finalize_reason"] = "operator_success"
    response = client.post(
        f"/api/episodes/{episode_id}/finalize",
        json={"trajectory": trajectory, "episode_status": "success"},
    )
    assert response.status_code == 200
    evaluation_id = response.json()["evaluation_id"]

    evaluation = client.get(f"/api/evaluations/{evaluation_id}").json()
    assert evaluation["success"] is True
    assert "final_distance_to_target" in evaluation["metrics"]
    app_cleanup()


def app_cleanup() -> None:
    from app.main import app

    app.dependency_overrides.clear()
