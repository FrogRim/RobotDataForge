from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.database import Base, get_db
from app.main import app


def make_client(tmp_path: Path) -> TestClient:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    settings.storage_root = tmp_path / "storage"

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def valid_task_payload() -> dict:
    return {
        "name": "Peg-in-Hole",
        "description": "Move the peg into the target hole.",
        "task_type": "peg_in_hole",
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


def valid_trajectory_payload() -> dict:
    source = {
        "input_device": "quest3_handtracking",
        "runtime": "steamvr_openxr",
        "simulator": "isaac_lab",
        "robot": "franka",
        "task_name": "Isaac-Stack-Cube-Franka-IK-Rel-v0",
    }
    frames = [
        {
            "t": 0.0,
            "step": 0,
            "end_effector_position": [0.15, 0.5],
            "object_position": [0.15, 0.5],
            "action": {"delta_position": [0.0, 0.0], "gripper": 1.0},
            "metadata": {"right_hand_tracked": True, "xr_frame_valid": True},
        },
        {
            "t": 5.0,
            "step": 1,
            "end_effector_position": [0.75, 0.5],
            "object_position": [0.75, 0.5],
            "action": {"delta_position": [0.6, 0.0], "gripper": 1.0},
            "metadata": {"right_hand_tracked": True, "xr_frame_valid": True},
        },
        {
            "t": 6.0,
            "step": 2,
            "end_effector_position": [0.75, 0.5],
            "object_position": [0.75, 0.5],
            "action": {"delta_position": [0.0, 0.0], "gripper": 1.0},
            "metadata": {"right_hand_tracked": True, "xr_frame_valid": True},
        },
    ]
    return {
        "schema_version": "0.1.0",
        "source": source,
        "frames": frames,
        "summary": {"duration_sec": 6.0, "collision_count": 0},
    }


def test_task_episode_dataset_contract(tmp_path: Path) -> None:
    client = make_client(tmp_path)

    task_response = client.post("/api/tasks", json=valid_task_payload())
    assert task_response.status_code == 200
    task_id = task_response.json()["id"]

    session_response = client.post(
        "/api/collection-sessions/start",
        json={
            "task_id": task_id,
            "contributor_id": "user_001",
            "isaac_task_name": "Isaac-Stack-Cube-Franka-IK-Rel-v0",
            "input_device": "quest3_handtracking",
            "xr_runtime": "steamvr_openxr",
            "streaming_stack": "alvr",
        },
    )
    assert session_response.status_code == 200
    session_id = session_response.json()["session_id"]

    complete_session_response = client.post(
        f"/api/collection-sessions/{session_id}/complete",
        json={
            "runtime_metrics": {
                "average_fps": 72,
                "frame_drop_rate": 0.04,
                "hand_tracking_loss_rate": 0.03,
                "average_input_latency_ms": 35,
                "session_crashed": False,
            }
        },
    )
    assert complete_session_response.json()["status"] == "completed"

    episode_response = client.post(
        "/api/episodes/start",
        json={"task_id": task_id, "contributor_id": "user_001", "collection_session_id": session_id},
    )
    assert episode_response.status_code == 200
    episode_id = episode_response.json()["episode_id"]

    complete_response = client.post(
        f"/api/episodes/{episode_id}/complete",
        json={
            "trajectory": valid_trajectory_payload(),
            "unit_economics": {
                "human_time_per_episode": 6.0,
                "compute_time_per_episode": 0.1,
                "cost_per_recorded_episode": 0.01,
                "cost_per_valid_episode": 0.01,
                "cost_per_accepted_trajectory": 0.01,
            },
        },
    )
    assert complete_response.status_code == 200
    body = complete_response.json()
    assert body["success"] is True
    trajectory_id = body["trajectory_id"]

    review_response = client.post(
        "/api/human-reviews",
        json={
            "episode_id": episode_id,
            "trajectory_id": trajectory_id,
            "reviewer_id": "admin_001",
            "human_success_label": True,
            "notes": "Looks successful and stable.",
        },
    )
    assert review_response.status_code == 200
    assert review_response.json()["agreement"] is True

    dataset_response = client.post(
        "/api/datasets/export",
        json={
            "task_id": task_id,
            "name": "peg_in_hole_validated_v0",
            "only_success": True,
            "min_quality_score": 0.7,
            "export_format": "json",
        },
    )
    assert dataset_response.status_code == 200
    assert Path(dataset_response.json()["export_path"]).exists()

    kpi_response = client.get("/api/admin/kpis")
    assert kpi_response.status_code == 200
    assert kpi_response.json()["collection"]["recorded_episodes"] == 1
    assert kpi_response.json()["evaluation"]["evaluator_agreement_rate"] == 1.0

    app.dependency_overrides.clear()
