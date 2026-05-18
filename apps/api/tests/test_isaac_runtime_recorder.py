from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


RECORDER_PATH = Path(__file__).resolve().parents[3] / "scripts" / "rdf_isaac_runtime_recorder.py"
SPEC = importlib.util.spec_from_file_location("rdf_isaac_runtime_recorder", RECORDER_PATH)
assert SPEC is not None
recorder_module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(recorder_module)


class FakeRigidData:
    root_pos_w = [[0.4, 0.0, 0.0203]]
    root_quat_w = [[1.0, 0.0, 0.0, 0.0]]


class FakeCube2Data:
    root_pos_w = [[0.4, 0.0, 0.0609]]
    root_quat_w = [[1.0, 0.0, 0.0, 0.0]]


class FakeEeData:
    target_pos_w = [[[0.5, 0.1, 0.2]]]
    target_quat_w = [[[1.0, 0.0, 0.0, 0.0]]]


class FakePegData:
    root_pos_w = [[0.0, 0.0, 0.08]]
    root_quat_w = [[1.0, 0.0, 0.0, 0.0]]


class FakeHoleData:
    root_pos_w = [[0.0, 0.0, 0.05]]
    root_quat_w = [[1.0, 0.0, 0.0, 0.0]]


class FakeAsset:
    def __init__(self, data):
        self.data = data


class FakeScene:
    env_origins = [[0.0, 0.0, 0.0]]

    def __init__(self):
        self.assets = {
            "cube_1": FakeAsset(FakeRigidData()),
            "cube_2": FakeAsset(FakeCube2Data()),
            "cube_3": FakeAsset(FakeRigidData()),
            "ee_frame": FakeAsset(FakeEeData()),
            "peg": FakeAsset(FakePegData()),
            "hole": FakeAsset(FakeHoleData()),
            "held_asset": FakeAsset(FakePegData()),
            "fixed_asset": FakeAsset(FakeHoleData()),
        }

    def __getitem__(self, key):
        return self.assets[key]


class FakeEnv:
    step_dt = 0.02

    def __init__(self):
        self.scene = FakeScene()


class FakeTeleop:
    _previous_joint_poses_right = {"wrist": [0.1, 0.2, 0.3, 1.0, 0.0, 0.0, 0.0]}
    _previous_joint_poses_left = {"wrist": [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0]}
    _previous_headpose = [0.4, 0.5, 0.6, 1.0, 0.0, 0.0, 0.0]


class FakeTeleopLost:
    _previous_joint_poses_right = {"wrist": [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0]}
    _previous_joint_poses_left = {"wrist": [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0]}
    _previous_headpose = [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0]


def test_build_frame_extracts_real_isaac_state_shape():
    frame = recorder_module.build_frame(
        env=FakeEnv(),
        action=[0.1, 0.0, -0.1, 0.7],
        teleoperation_active=True,
        teleop_interface=FakeTeleop(),
        step=3,
        started_at_monotonic=0.0,
    )

    assert frame["t"] == 0.06
    assert frame["step"] == 3
    assert frame["end_effector_position"] == [0.5, 0.1, 0.2]
    assert frame["object_position"] == [0.4, 0.0, 0.0609]
    assert frame["action"]["pinch_or_gripper"] == 0.7
    assert frame["action"]["retargeted_robot_action"]["command"] == [0.1, 0.0, -0.1, 0.7]
    assert frame["action"]["teleop_intent"]["role"] == "operator_intent"
    assert frame["action"]["teleop_intent"]["command"] == [0.1, 0.0, -0.1, 0.7]
    assert frame["action"]["executed_control"]["role"] == "robot_control_command"
    assert frame["action"]["executed_control"]["command"] == [0.1, 0.0, -0.1, 0.7]
    assert frame["action"]["learning_action"]["role"] == "candidate_robot_action_for_learning"
    assert frame["action"]["learning_action"]["validation_state"] == "requires_evaluation_and_curation"
    assert frame["action"]["relative"]["delta_position"] == [0.1, 0.0, -0.1]
    assert frame["metadata"]["right_hand_tracked"] is True
    assert frame["metadata"]["head_tracked"] is True
    assert frame["metadata"]["raw_xr"]["right_wrist_pose"] == [0.1, 0.2, 0.3, 1.0, 0.0, 0.0, 0.0]
    assert frame["metadata"]["aligned_xr"]["right_wrist_pose"] == [0.1, 0.2, 0.3, 1.0, 0.0, 0.0, 0.0]
    assert frame["metadata"]["aligned_xr"]["calibration_valid"] is False
    assert frame["metadata"]["retargeted"]["robot_action"] == [0.1, 0.0, -0.1, 0.7]
    assert frame["metadata"]["teleop_pipeline"]["product_role"] == "xr_teleop_trajectory_to_validated_learning_dataset"
    assert frame["metadata"]["teleop_pipeline"]["learning_action_status"] == "candidate_requires_evaluation_and_curation"
    assert frame["metadata"]["cube_states"]["cube_1"]["position"] == [0.4, 0.0, 0.0203]


def test_build_frame_adds_mvp1_insertion_task_state(monkeypatch):
    monkeypatch.setenv("RDF_TASK_TYPE", "peg_in_hole")
    monkeypatch.setenv("RDF_PEG_TIP_LOCAL_OFFSET", "0,0,-0.05")
    config = recorder_module._task_state_config("peg_in_hole")

    frame = recorder_module.build_frame(
        env=FakeEnv(),
        action=[0.1, 0.0, -0.1, 0.7],
        teleoperation_active=True,
        teleop_interface=FakeTeleop(),
        step=3,
        started_at_monotonic=0.0,
        task_state_config=config,
    )

    task_state = frame["metadata"]["task_state"]
    assert frame["object_position"] == [0.0, 0.0, 0.08]
    assert frame["metadata"]["action_phase"] in {"CONTACT", "INSERT", "SEAT"}
    assert task_state["task_state_source"] == "isaac_scene_assets"
    assert task_state["peg_asset_name"] == "peg"
    assert task_state["hole_asset_name"] == "hole"
    assert task_state["peg_position"] == [0.0, 0.0, 0.08]
    assert task_state["hole_position"] == [0.0, 0.0, 0.05]
    assert task_state["peg_tip_position"] == pytest.approx([0.0, 0.0, 0.03])
    assert task_state["peg_tip_distance_to_target"] == pytest.approx(0.02)
    assert task_state["peg_tip_distance_3d_to_target"] == pytest.approx(0.02)
    assert task_state["peg_lateral_distance_to_target"] == pytest.approx(0.0)
    assert task_state["peg_axial_distance_to_target"] == pytest.approx(0.02)
    assert task_state["peg_distance_metric"] == "lateral_projection"
    assert task_state["axis_alignment_error_rad"] == pytest.approx(0.0)
    assert task_state["insertion_depth"] == pytest.approx(0.02)
    assert task_state["contact_sequence_valid"] is True


def test_runtime_recorder_submits_episode_and_session(monkeypatch):
    calls = []

    def fake_post_json(api_base, path, payload, timeout=20.0):
        calls.append((path, payload))
        if path == "/api/tasks":
            return {"id": "task_001"}
        if path == "/api/collection-sessions/start":
            return {"session_id": "session_001", "status": "recording"}
        if path == "/api/episodes/start":
            return {"episode_id": "episode_001", "task_id": "task_001", "status": "running"}
        if path == "/api/episodes/episode_001/finalize":
            return {"success": True, "score": 0.9}
        if path == "/api/collection-sessions/session_001/complete":
            return {"session_id": "session_001", "status": "completed"}
        raise AssertionError(path)

    monkeypatch.setattr(recorder_module, "post_json", fake_post_json)

    runtime_recorder = recorder_module.RdfIsaacRuntimeRecorder(
        api_base="http://localhost:8000",
        contributor_id="user_001",
        isaac_task_name="Isaac-Stack-Cube-Franka-IK-Rel-v0",
    )
    runtime_recorder.start(FakeEnv())
    runtime_recorder.record(FakeEnv(), [0.1, 0.0, 0.0, 1.0], True, FakeTeleop())
    runtime_recorder.finish(reason="closed")

    paths = [path for path, _ in calls]
    assert paths == [
        "/api/tasks",
        "/api/collection-sessions/start",
        "/api/episodes/start",
        "/api/episodes/episode_001/finalize",
        "/api/collection-sessions/session_001/complete",
    ]
    task_payload = calls[0][1]
    assert task_payload["environment_config"]["target_position"] == [0.4, 0.0, 0.0609]
    episode_payload = calls[3][1]
    assert episode_payload["episode_status"] == "incomplete"
    assert episode_payload["episode_finalize_reason"] == "closed"
    assert episode_payload["trajectory"]["schema_version"] == "0.1.0"
    assert episode_payload["trajectory"]["source"]["input_device"] == "quest3_handtracking"
    assert len(episode_payload["trajectory"]["frames"]) == 1
    assert episode_payload["trajectory"]["summary"]["episode_status"] == "incomplete"
    session_payload = calls[4][1]
    assert session_payload["runtime_metrics"]["hand_tracking_loss_rate"] == 0.0


def test_runtime_recorder_creates_mvp1_insertion_task_payload_and_summary(monkeypatch):
    calls = []
    monkeypatch.setenv("RDF_TASK_TYPE", "peg_in_hole")
    monkeypatch.setenv("RDF_PEG_TIP_LOCAL_OFFSET", "0,0,-0.05")

    def fake_post_json(api_base, path, payload, timeout=20.0):
        calls.append((path, payload))
        if path == "/api/tasks":
            return {"id": "task_001"}
        if path == "/api/collection-sessions/start":
            return {"session_id": "session_001", "status": "recording"}
        if path == "/api/episodes/start":
            return {"episode_id": "episode_001", "task_id": "task_001", "status": "running"}
        if path == "/api/episodes/episode_001/finalize":
            return {"success": True, "score": 0.9}
        if path == "/api/collection-sessions/session_001/complete":
            return {"session_id": "session_001", "status": "completed"}
        raise AssertionError(path)

    monkeypatch.setattr(recorder_module, "post_json", fake_post_json)

    runtime_recorder = recorder_module.RdfIsaacRuntimeRecorder(
        api_base="http://localhost:8000",
        contributor_id="user_001",
        isaac_task_name="Isaac-Forge-PegInsert-Direct-v0",
    )
    runtime_recorder.start(FakeEnv())
    runtime_recorder.record(FakeEnv(), [0.1, 0.0, 0.0, 1.0], True, FakeTeleop())
    runtime_recorder.finish(reason="operator_success", episode_status="success")

    task_payload = calls[0][1]
    assert task_payload["task_type"] == "peg_in_hole"
    assert task_payload["environment_config"]["task_state_source"] == "isaac_scene_assets"
    assert task_payload["environment_config"]["peg_asset_name"] == "held_asset"
    assert task_payload["environment_config"]["hole_asset_name"] == "fixed_asset"
    assert task_payload["success_criteria"]["peg_tip_distance_to_target_max"] == 0.015

    episode_payload = calls[3][1]
    trajectory = episode_payload["trajectory"]
    assert trajectory["summary"]["task_type"] == "peg_in_hole"
    assert trajectory["summary"]["task_state_source"] == "isaac_scene_assets"
    assert trajectory["summary"]["task_state_frame_count"] == 1
    assert trajectory["frames"][0]["metadata"]["task_state"]["insertion_depth"] == pytest.approx(0.02)
    assert calls[4][1]["runtime_metrics"]["task_state_available"] is True
    assert calls[4][1]["runtime_metrics"]["task_state_frame_count"] == 1


def test_runtime_recorder_records_calibrated_xr_pose_and_retargeted_action(monkeypatch):
    calls = []

    def fake_post_json(api_base, path, payload, timeout=20.0):
        calls.append((path, payload))
        if path == "/api/tasks":
            return {"id": "task_001"}
        if path == "/api/collection-sessions/start":
            return {"session_id": "session_001", "status": "recording"}
        if path == "/api/episodes/start":
            return {"episode_id": "episode_001", "task_id": "task_001", "status": "running"}
        if path == "/api/episodes/episode_001/finalize":
            return {"success": True, "score": 0.9}
        if path == "/api/collection-sessions/session_001/complete":
            return {"session_id": "session_001", "status": "completed"}
        raise AssertionError(path)

    monkeypatch.setattr(recorder_module, "post_json", fake_post_json)

    runtime_recorder = recorder_module.RdfIsaacRuntimeRecorder(
        api_base="http://localhost:8000",
        contributor_id="user_001",
        isaac_task_name="Isaac-Stack-Cube-Franka-IK-Rel-v0",
        auto_calibrate_on_first_valid=False,
    )
    runtime_recorder.start(FakeEnv())
    assert runtime_recorder.calibrate(FakeEnv(), FakeTeleop(), reason="operator_command") is True
    runtime_recorder.record(FakeEnv(), [0.1, 0.0, -0.1, 0.0, 0.0, 0.2, 1.0], True, FakeTeleop())
    runtime_recorder.finish(reason="closed")

    episode_payload = calls[3][1]
    frame = episode_payload["trajectory"]["frames"][0]
    metadata = frame["metadata"]
    assert metadata["raw_xr"]["right_wrist_pose"] == [0.1, 0.2, 0.3, 1.0, 0.0, 0.0, 0.0]
    assert metadata["aligned_xr"]["calibration_valid"] is True
    assert metadata["aligned_xr"]["right_wrist_pose"] == pytest.approx([0.5, 0.1, 0.2, 1.0, 0.0, 0.0, 0.0])
    assert metadata["aligned_xr"]["calibration_reason"] == "operator_command"
    assert metadata["aligned_xr"]["rotation_offset_quat"] == pytest.approx([1.0, 0.0, 0.0, 0.0])
    assert metadata["retargeted"]["robot_action"] == [0.1, 0.0, -0.1, 0.0, 0.0, 0.2, 1.0]
    assert metadata["retargeted"]["raw_robot_action"] == [0.1, 0.0, -0.1, 0.0, 0.0, 0.2, 1.0]
    assert frame["action"]["retargeted_robot_action"]["action_type"] == "delta_ee_pose_plus_gripper"
    assert frame["action"]["relative"]["delta_rotation"] == [0.0, 0.0, 0.2]
    summary = episode_payload["trajectory"]["summary"]
    assert summary["calibration"]["reason"] == "operator_command"
    assert summary["calibration"]["type"] == "workspace_alignment_v2"
    session_payload = calls[4][1]
    assert session_payload["runtime_metrics"]["calibration_valid"] is True
    assert session_payload["runtime_metrics"]["calibration_event_count"] == 1


def test_runtime_recorder_preserves_raw_and_filtered_action(monkeypatch):
    calls = []

    def fake_post_json(api_base, path, payload, timeout=20.0):
        calls.append((path, payload))
        if path == "/api/tasks":
            return {"id": "task_001"}
        if path == "/api/collection-sessions/start":
            return {"session_id": "session_001", "status": "recording"}
        if path == "/api/episodes/start":
            return {"episode_id": "episode_001", "task_id": "task_001", "status": "running"}
        if path == "/api/episodes/episode_001/finalize":
            return {"success": True, "score": 0.9}
        if path == "/api/collection-sessions/session_001/complete":
            return {"session_id": "session_001", "status": "completed"}
        raise AssertionError(path)

    monkeypatch.setattr(recorder_module, "post_json", fake_post_json)

    control_filter = {
        "name": "rdf_teleop_action_filter",
        "applied": True,
        "config": {
            "enabled": True,
            "position_gain": 0.4,
            "rotation_gain": 0.3,
            "position_axis_map": "x,-z,y",
        },
    }
    runtime_recorder = recorder_module.RdfIsaacRuntimeRecorder(
        api_base="http://localhost:8000",
        contributor_id="user_001",
        isaac_task_name="Isaac-Stack-Cube-Franka-IK-Rel-v0",
        auto_calibrate_on_first_valid=False,
    )
    runtime_recorder.start(FakeEnv())
    assert runtime_recorder.calibrate(
        FakeEnv(),
        FakeTeleop(),
        reason="operator_command",
        control_filter=control_filter,
    )
    runtime_recorder.record(
        FakeEnv(),
        [0.04, 0.0, -0.04, 0.0, 0.0, 0.06, 1.0],
        True,
        FakeTeleop(),
        raw_action=[0.1, 0.0, -0.1, 0.0, 0.0, 0.2, 1.0],
        control_filter=control_filter,
    )
    runtime_recorder.finish(reason="closed")

    episode_payload = calls[3][1]
    frame = episode_payload["trajectory"]["frames"][0]
    assert frame["action"]["raw"] == [0.1, 0.0, -0.1, 0.0, 0.0, 0.2, 1.0]
    assert frame["action"]["applied"] == [0.04, 0.0, -0.04, 0.0, 0.0, 0.06, 1.0]
    assert frame["action"]["retargeted_robot_action"]["command"] == [0.04, 0.0, -0.04, 0.0, 0.0, 0.06, 1.0]
    assert frame["action"]["teleop_intent"]["command"] == [0.1, 0.0, -0.1, 0.0, 0.0, 0.2, 1.0]
    assert frame["action"]["executed_control"]["command"] == [0.04, 0.0, -0.04, 0.0, 0.0, 0.06, 1.0]
    assert frame["action"]["learning_action"]["command"] == [0.04, 0.0, -0.04, 0.0, 0.0, 0.06, 1.0]
    assert frame["metadata"]["retargeted"]["raw_robot_action"] == [0.1, 0.0, -0.1, 0.0, 0.0, 0.2, 1.0]
    assert frame["metadata"]["retargeted"]["robot_action"] == [0.04, 0.0, -0.04, 0.0, 0.0, 0.06, 1.0]
    assert frame["metadata"]["aligned_xr"]["position_gain"] == 0.4
    assert frame["metadata"]["aligned_xr"]["control_filter"]["config"]["position_axis_map"] == "x,-z,y"
    assert episode_payload["trajectory"]["summary"]["control_filter"]["config"]["position_gain"] == 0.4
    assert calls[4][1]["runtime_metrics"]["control_filter_enabled"] is True


def test_runtime_recorder_skips_frames_until_handtracking_warmup(monkeypatch):
    calls = []

    def fake_post_json(api_base, path, payload, timeout=20.0):
        calls.append((path, payload))
        if path == "/api/tasks":
            return {"id": "task_001"}
        if path == "/api/collection-sessions/start":
            return {"session_id": "session_001", "status": "recording"}
        if path == "/api/episodes/start":
            return {"episode_id": "episode_001", "task_id": "task_001", "status": "running"}
        if path == "/api/episodes/episode_001/finalize":
            return {"success": True, "score": 0.9}
        if path == "/api/collection-sessions/session_001/complete":
            return {"session_id": "session_001", "status": "completed"}
        raise AssertionError(path)

    monkeypatch.setattr(recorder_module, "post_json", fake_post_json)

    runtime_recorder = recorder_module.RdfIsaacRuntimeRecorder(
        api_base="http://localhost:8000",
        contributor_id="user_001",
        isaac_task_name="Isaac-Stack-Cube-Franka-IK-Rel-v0",
        warmup_valid_frames=2,
    )
    runtime_recorder.start(FakeEnv())
    runtime_recorder.record(FakeEnv(), [0.0, 0.0, 0.0, -1.0], True, FakeTeleopLost())
    runtime_recorder.record(FakeEnv(), [0.0, 0.0, 0.0, -1.0], True, FakeTeleopLost())
    runtime_recorder.record(FakeEnv(), [0.1, 0.0, 0.0, 1.0], True, FakeTeleop())
    assert runtime_recorder.frames == []

    runtime_recorder.record(FakeEnv(), [0.2, 0.0, 0.0, 1.0], True, FakeTeleop())
    runtime_recorder.record(FakeEnv(), [0.3, 0.0, 0.0, 1.0], True, FakeTeleop())
    assert len(runtime_recorder.frames) == 2
    assert runtime_recorder.frames[0]["step"] == 0
    assert runtime_recorder.frames[0]["t"] == 0.0
    assert runtime_recorder.frames[0]["metadata"]["recording_started_after_warmup"] is True
    assert runtime_recorder.frames[0]["metadata"]["warmup_dropped_frames"] == 3

    runtime_recorder.finish(reason="closed")

    episode_payload = calls[3][1]
    frames = episode_payload["trajectory"]["frames"]
    assert len(frames) == 2
    assert all(frame["metadata"]["right_hand_tracked"] for frame in frames)
    assert episode_payload["trajectory"]["summary"]["warmup_valid_frames"] == 2
    assert episode_payload["trajectory"]["summary"]["warmup_dropped_frames"] == 3
    session_payload = calls[4][1]
    assert session_payload["runtime_metrics"]["hand_tracking_loss_rate"] == 0.0
    assert session_payload["runtime_metrics"]["warmup_dropped_frames"] == 3


def test_runtime_recorder_submits_explicit_success_lifecycle(monkeypatch):
    calls = []

    def fake_post_json(api_base, path, payload, timeout=20.0):
        calls.append((path, payload))
        if path == "/api/tasks":
            return {"id": "task_001"}
        if path == "/api/collection-sessions/start":
            return {"session_id": "session_001", "status": "recording"}
        if path == "/api/episodes/start":
            return {"episode_id": "episode_001", "task_id": "task_001", "status": "running"}
        if path == "/api/episodes/episode_001/finalize":
            return {"episode_status": payload["episode_status"], "success": True, "score": 0.9}
        if path == "/api/collection-sessions/session_001/complete":
            return {"session_id": "session_001", "status": "completed"}
        raise AssertionError(path)

    monkeypatch.setattr(recorder_module, "post_json", fake_post_json)

    runtime_recorder = recorder_module.RdfIsaacRuntimeRecorder(
        api_base="http://localhost:8000",
        contributor_id="user_001",
        isaac_task_name="Isaac-Stack-Cube-Franka-IK-Rel-v0",
    )
    runtime_recorder.start(FakeEnv())
    runtime_recorder.record(FakeEnv(), [0.1, 0.0, 0.0, 1.0], True, FakeTeleop())
    runtime_recorder.finish(reason="operator_success", episode_status="success")

    episode_payload = calls[3][1]
    assert episode_payload["episode_status"] == "success"
    assert episode_payload["episode_finalize_reason"] == "operator_success"
    assert episode_payload["trajectory"]["summary"]["episode_status"] == "success"
    assert episode_payload["trajectory"]["summary"]["episode_finalize_reason"] == "operator_success"
