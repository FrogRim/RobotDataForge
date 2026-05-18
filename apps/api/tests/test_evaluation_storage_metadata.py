from __future__ import annotations

import json
from pathlib import Path

from tests.test_api_contract import make_client, valid_task_payload, valid_trajectory_payload


def create_finalized_episode(client) -> tuple[str, str, str]:
    task_response = client.post("/api/tasks", json=valid_task_payload())
    assert task_response.status_code == 200
    task_id = task_response.json()["id"]
    episode_response = client.post(
        "/api/episodes/start",
        json={"task_id": task_id, "contributor_id": "user_001"},
    )
    assert episode_response.status_code == 200
    episode_id = episode_response.json()["episode_id"]
    finalize_response = client.post(
        f"/api/episodes/{episode_id}/finalize",
        json={
            "trajectory": valid_trajectory_payload(),
            "episode_status": "success",
            "episode_finalize_reason": "operator_success",
        },
    )
    assert finalize_response.status_code == 200
    trajectory_id = finalize_response.json()["trajectory_id"]
    evaluation_id = finalize_response.json()["evaluation_id"]
    return episode_id, trajectory_id, evaluation_id


def test_finalize_stored_evaluation_json_includes_pairing_metadata(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    episode_id, trajectory_id, evaluation_id = create_finalized_episode(client)

    evaluation_path = tmp_path / "storage" / "evaluations" / f"{evaluation_id}.json"
    stored = json.loads(evaluation_path.read_text(encoding="utf-8"))

    assert stored["id"] == evaluation_id
    assert stored["trajectory_id"] == trajectory_id
    assert stored["episode_id"] == episode_id
    assert stored["task_id"]
    assert stored["evaluated_at"]
    app_cleanup()


def test_manual_evaluation_stored_json_includes_pairing_metadata(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    episode_id, trajectory_id, _ = create_finalized_episode(client)

    response = client.post("/api/evaluations", json={"trajectory_id": trajectory_id})
    assert response.status_code == 200
    evaluation_id = response.json()["evaluation_id"]

    evaluation_path = tmp_path / "storage" / "evaluations" / f"{evaluation_id}.json"
    stored = json.loads(evaluation_path.read_text(encoding="utf-8"))

    assert stored["id"] == evaluation_id
    assert stored["trajectory_id"] == trajectory_id
    assert stored["episode_id"] == episode_id
    assert stored["task_id"]
    assert stored["evaluated_at"]
    app_cleanup()


def app_cleanup() -> None:
    from app.main import app

    app.dependency_overrides.clear()
