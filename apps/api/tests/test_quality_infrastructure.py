from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from app.services.curator import curate_episodes_with_reasons
from tests.test_api_contract import make_client, valid_task_payload, valid_trajectory_payload


def quality_trajectory_payload() -> dict:
    trajectory = valid_trajectory_payload()
    phases = ["APPROACH", "ALIGN", "CONTACT"]
    for index, frame in enumerate(trajectory["frames"]):
        frame["metadata"] = {
            **frame.get("metadata", {}),
            "right_hand_tracked": True,
            "xr_frame_valid": True,
            "input_latency_ms": 25 + index,
            "sync_error_ms": 2 + index,
            "timestamp_source": "isaac_sim",
            "action_phase": phases[index],
            "raw_xr": {"right_wrist_pose": [0.1 + index * 0.01, 0.2, 0.3, 0.0, 0.0, 0.0, 1.0]},
            "aligned_xr": {"right_wrist_pose": [0.2 + index * 0.01, 0.3, 0.4, 0.0, 0.0, 0.0, 1.0]},
        }
        frame["action"] = {
            **frame.get("action", {}),
            "retargeted_robot_action": {"command": [0.01 * index, 0.0, 0.0, 1.0]},
        }
    return trajectory


def insertion_phase_trajectory_payload() -> dict:
    trajectory = valid_trajectory_payload()
    phases = ["APPROACH", "ALIGN", "CONTACT", "INSERT", "SEAT", "RELEASE"]
    trajectory["frames"] = []
    for index, phase in enumerate(phases):
        trajectory["frames"].append(
            {
                "t": index * 0.1,
                "step": index,
                "end_effector_position": [0.5 + index * 0.01, 0.2, 0.1],
                "object_position": [0.5 + index * 0.01, 0.2, 0.1],
                "action": {"retargeted_robot_action": {"command": [0.01 * index, 0.0, 0.0, 1.0]}},
                "metadata": {
                    "right_hand_tracked": True,
                    "xr_frame_valid": True,
                    "action_phase": phase,
                    "raw_xr": {"right_wrist_pose": [0.1, 0.2, 0.3, 0.0, 0.0, 0.0, 1.0]},
                    "aligned_xr": {"right_wrist_pose": [0.2, 0.3, 0.4, 0.0, 0.0, 0.0, 1.0]},
                },
            }
        )
    trajectory["summary"] = {"duration_sec": 0.5, "collision_count": 0}
    return trajectory


def create_completed_episode(client) -> dict:
    task_response = client.post("/api/tasks", json=valid_task_payload())
    assert task_response.status_code == 200
    task_id = task_response.json()["id"]
    episode_response = client.post(
        "/api/episodes/start",
        json={"task_id": task_id, "contributor_id": "user_001"},
    )
    episode_id = episode_response.json()["episode_id"]
    complete_response = client.post(
        f"/api/episodes/{episode_id}/finalize",
        json={
            "trajectory": quality_trajectory_payload(),
            "episode_status": "success",
            "episode_finalize_reason": "operator_success",
        },
    )
    assert complete_response.status_code == 200
    return {"task_id": task_id, "episode_id": episode_id, **complete_response.json()}


def test_episode_finalize_stores_sync_usability_and_segments(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    ids = create_completed_episode(client)

    episode = client.get(f"/api/episodes/{ids['episode_id']}").json()
    assert episode["usable"] is True
    assert episode["data_usability_score"] >= 0.7

    evaluation = client.get(f"/api/evaluations/{ids['evaluation_id']}").json()
    assert evaluation["task_completion_score"] > 0.0
    assert evaluation["interaction_quality_score"] > 0.0
    assert evaluation["physical_plausibility_score"] > 0.0
    assert evaluation["evaluator_confidence"] > 0.0
    assert evaluation["failure_mode"] == "SUCCESS"
    assert evaluation["data_usability_score"] >= 0.7

    sync = client.get(f"/api/episodes/{ids['episode_id']}/sync-metrics").json()
    assert sync["metrics_json"]["sync_error_ms_mean"] == 3.0
    assert sync["metrics_json"]["timestamp_source"] == "isaac_sim"

    usability = client.get(f"/api/episodes/{ids['episode_id']}/usability").json()
    assert usability["usable"] is True
    assert usability["components_json"]["sync_quality_score"] > 0.0

    segments = client.get(f"/api/trajectories/{ids['trajectory_id']}/segments").json()
    assert [segment["phase"] for segment in segments] == ["APPROACH", "ALIGN", "CONTACT"]

    stored = json.loads((tmp_path / "storage" / "trajectories" / f"{ids['trajectory_id']}.json").read_text())
    assert "sync_metrics" in stored["summary"]
    assert "data_usability" in stored["summary"]
    assert "action_segments" in stored["summary"]
    client.app.dependency_overrides.clear()


def test_episode_finalize_accepts_insertion_seat_phase(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    task_response = client.post("/api/tasks", json=valid_task_payload())
    assert task_response.status_code == 200
    task_id = task_response.json()["id"]
    episode_response = client.post(
        "/api/episodes/start",
        json={"task_id": task_id, "contributor_id": "user_001"},
    )
    episode_id = episode_response.json()["episode_id"]
    complete_response = client.post(
        f"/api/episodes/{episode_id}/finalize",
        json={
            "trajectory": insertion_phase_trajectory_payload(),
            "episode_status": "success",
            "episode_finalize_reason": "operator_success",
        },
    )
    assert complete_response.status_code == 200

    segments = client.get(f"/api/trajectories/{complete_response.json()['trajectory_id']}/segments").json()
    assert [segment["phase"] for segment in segments] == [
        "APPROACH",
        "ALIGN",
        "CONTACT",
        "INSERT",
        "SEAT",
        "RELEASE",
    ]
    client.app.dependency_overrides.clear()


def test_admin_kpis_include_curation_and_data_usability_groups(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    create_completed_episode(client)

    response = client.get("/api/admin/kpis")
    assert response.status_code == 200
    body = response.json()
    assert "curation" in body
    assert "data_usability" in body
    assert body["data_usability"]["usable_trajectory_rate"] == 1.0
    assert body["xr_runtime"]["sync_error_ms_mean"] is not None
    client.app.dependency_overrides.clear()


def test_curator_reports_rejection_reasons() -> None:
    episodes = [
        {
            "episode": {"id": "episode_good", "replayable": True},
            "trajectory": {"frames": [{"object_position": [0, 0]}], "summary": {"sync_metrics": {"quality_score": 0.95}}},
            "evaluation": {"success": True, "quality_score": 0.9, "fraud_risk_score": 0.0, "data_usability_score": 0.9},
            "data_usability": {"usable": True, "score": 0.9, "rejection_reasons": []},
        },
        {
            "episode": {"id": "episode_bad", "replayable": False},
            "trajectory": {"frames": [{"object_position": [1, 1]}], "summary": {"sync_metrics": {"quality_score": 0.2}}},
            "evaluation": {"success": False, "quality_score": 0.2, "fraud_risk_score": 0.5, "data_usability_score": 0.2},
            "data_usability": {"usable": False, "score": 0.2, "rejection_reasons": ["LOW_SYNC_QUALITY"]},
        },
    ]

    result = curate_episodes_with_reasons(episodes, min_quality_score=0.7)
    assert len(result["accepted"]) == 1
    assert len(result["rejected"]) == 1
    reasons = result["rejected"][0]["curation"]["rejection_reasons"]
    assert "EVALUATION_FAILED" in reasons
    assert "NOT_REPLAYABLE" in reasons
    assert "LOW_SYNC_QUALITY" in reasons


def test_dataset_export_format_contract_and_dataset_card(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    ids = create_completed_episode(client)

    unsupported = client.post(
        "/api/datasets/export",
        json={"task_id": ids["task_id"], "name": "bad", "export_format": "parquet"},
    )
    assert unsupported.status_code == 422

    placeholder = client.post(
        "/api/datasets/export",
        json={"task_id": ids["task_id"], "name": "lerobot_ready", "export_format": "lerobot_v3"},
    )
    assert placeholder.status_code == 200
    assert placeholder.json()["status"] == "placeholder"
    assert Path(placeholder.json()["dataset_card_path"]).exists()

    manifest = json.loads(Path(placeholder.json()["export_path"]).read_text())
    assert manifest["export_status"] == "placeholder"
    assert manifest["placeholder"]["requested_format"] == "lerobot_v3"

    card = client.get(f"/api/datasets/{placeholder.json()['dataset_id']}/card")
    assert card.status_code == 200
    assert card.json()["dataset_name"] == "lerobot_ready"
    assert card.json()["num_accepted"] == 1
    client.app.dependency_overrides.clear()


def test_incomplete_episode_is_not_data_usable_even_with_frames(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    task_response = client.post("/api/tasks", json=valid_task_payload())
    task_id = task_response.json()["id"]
    episode_response = client.post(
        "/api/episodes/start",
        json={"task_id": task_id, "contributor_id": "user_001"},
    )
    episode_id = episode_response.json()["episode_id"]

    response = client.post(
        f"/api/episodes/{episode_id}/finalize",
        json={
            "trajectory": quality_trajectory_payload(),
            "episode_status": "incomplete",
            "episode_finalize_reason": "sim_shutdown",
        },
    )
    assert response.status_code == 200

    usability = client.get(f"/api/episodes/{episode_id}/usability").json()
    assert usability["usable"] is False
    assert "INCOMPLETE_EPISODE" in usability["rejection_reasons_json"]
    episode = client.get(f"/api/episodes/{episode_id}").json()
    assert episode["usable"] is False
    assert "INCOMPLETE_EPISODE" in episode["rejection_reasons"]
    client.app.dependency_overrides.clear()


def test_success_export_metadata_keeps_rejected_episode_reasons(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    task_response = client.post("/api/tasks", json=valid_task_payload())
    task_id = task_response.json()["id"]

    for status, reason in [("success", "operator_success"), ("failure", "operator_failure")]:
        episode_response = client.post(
            "/api/episodes/start",
            json={"task_id": task_id, "contributor_id": "user_001"},
        )
        episode_id = episode_response.json()["episode_id"]
        response = client.post(
            f"/api/episodes/{episode_id}/finalize",
            json={
                "trajectory": quality_trajectory_payload(),
                "episode_status": status,
                "episode_finalize_reason": reason,
            },
        )
        assert response.status_code == 200

    export_response = client.post(
        "/api/datasets/export",
        json={
            "task_id": task_id,
            "name": "success_with_rejection_metadata",
            "only_success": True,
            "min_quality_score": 0.7,
            "export_format": "json",
        },
    )
    assert export_response.status_code == 200
    manifest = json.loads(Path(export_response.json()["export_path"]).read_text())
    assert len(manifest["episodes"]) == 1
    assert manifest["metadata"]["rejected_episode_count"] == 1
    rejected_reasons = manifest["metadata"]["rejection_reasons"][0]["rejection_reasons"]
    assert "EPISODE_STATUS:failure" in rejected_reasons
    client.app.dependency_overrides.clear()


def test_live_validation_filters_scope_episodes_and_kpis(tmp_path: Path) -> None:
    client = make_client(tmp_path)

    first = create_completed_episode(client)
    boundary = datetime.now(timezone.utc).isoformat()

    second_task = valid_task_payload()
    second_task["name"] = "Peg-in-Hole scoped run"
    second_task["task_type"] = "peg_in_hole_scoped"
    task_response = client.post("/api/tasks", json=second_task)
    second_task_id = task_response.json()["id"]
    episode_response = client.post(
        "/api/episodes/start",
        json={"task_id": second_task_id, "contributor_id": "user_001"},
    )
    second_episode_id = episode_response.json()["episode_id"]
    complete_response = client.post(
        f"/api/episodes/{second_episode_id}/finalize",
        json={
            "trajectory": quality_trajectory_payload(),
            "episode_status": "success",
            "episode_finalize_reason": "operator_success",
        },
    )
    assert complete_response.status_code == 200

    by_task = client.get(f"/api/admin/kpis?task_id={first['task_id']}").json()
    assert by_task["collection"]["recorded_episodes"] == 1

    by_started_after = client.get("/api/episodes", params={"started_after": boundary}).json()
    assert [episode["id"] for episode in by_started_after] == [second_episode_id]

    kpis_after = client.get("/api/admin/kpis", params={"started_after": boundary}).json()
    assert kpis_after["collection"]["recorded_episodes"] == 1
    assert kpis_after["data_usability"]["usable_trajectory_rate"] == 1.0
    client.app.dependency_overrides.clear()
