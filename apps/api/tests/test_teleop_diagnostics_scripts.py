from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
from types import SimpleNamespace
import sys
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[3]


def load_script(name: str):
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


analyzer = load_script("analyze_teleop_calibration")
motion_mapping = load_script("analyze_hmd_motion_mapping")
verifier = load_script("verify_latest_rdf_recording")
preflight = load_script("check_rdf_runtime_env")
offline_bundle = load_script("run_mvp0_offline_diagnostics")
forge_response = load_script("check_forge_direct_action_response")
runtime_recorder = load_script("rdf_isaac_runtime_recorder")
log_summary = load_script("summarize_hmd_run_log")
gate0 = load_script("run_gate0_xr_input_viability")
input_sources = load_script("rdf_input_sources")


def frame(index: int, *, raw: list[float], applied: list[float]) -> dict[str, Any]:
    return {
        "t": index * 0.05,
        "step": index,
        "end_effector_position": [0.5 + index * 0.01, 0.1, 0.2],
        "object_position": [0.4, 0.0, 0.06],
        "action": {
            "raw": raw,
            "applied": applied,
            "control_filter": {
                "enabled": True,
                "config": {"position_gain": 0.5, "position_axis_map": "x,y,z"},
                "suppressed_after_recenter": index == 1,
            },
            "retargeted_robot_action": {"command": applied},
        },
        "metadata": {
            "right_hand_tracked": True,
            "xr_frame_valid": True,
            "sim_fps": 20.0,
            "raw_xr": {"right_wrist_pose": [0.1 + index, 0.2, 0.3, 1.0, 0.0, 0.0, 0.0]},
            "aligned_xr": {
                "right_wrist_pose": [0.4 + index, 0.5, 0.6, 1.0, 0.0, 0.0, 0.0],
                "control_filter": {
                    "enabled": True,
                    "config": {"position_gain": 0.5, "position_axis_map": "x,y,z"},
                    "suppressed_after_recenter": index == 1,
                },
            },
            "calibration": {"type": "workspace_alignment_v2"},
            "retargeted": {
                "raw_robot_action": raw,
                "robot_action": applied,
                "control_filter": {"enabled": True},
            },
        },
    }


def trajectory_payload(name: str = "latest") -> dict[str, Any]:
    return {
        "id": f"traj_{name}",
        "episode_id": f"episode_{name}",
        "task_id": "task_001",
        "schema_version": "0.1.0",
        "source": {
            "input_device": "quest3_handtracking",
            "runtime": "steamvr_openxr",
            "simulator": "isaac_lab",
            "robot": "franka",
            "task_name": "Isaac-Stack-Cube-Franka-IK-Rel-v0",
        },
        "frames": [
            frame(0, raw=[0.2, 0.0, 0.0, 0.0], applied=[0.1, 0.0, 0.0, 0.0]),
            frame(1, raw=[0.2, 0.0, 0.0, 0.0], applied=[0.0, 0.0, 0.0, 0.0]),
            frame(2, raw=[0.4, 0.0, 0.0, 0.0], applied=[0.2, 0.0, 0.0, 0.0]),
        ],
        "summary": {
            "episode_status": "success",
            "episode_started_at": "2026-05-04T00:00:00+00:00",
            "episode_finalized_at": "2026-05-04T00:00:01+00:00",
            "episode_finalize_reason": "operator_success",
            "calibration": {"type": "workspace_alignment_v2"},
            "calibration_events": [
                {"type": "workspace_alignment_v2", "reason": "auto_first_valid_frame"},
                {"type": "workspace_alignment_v2", "reason": "operator_command"},
            ],
            "control_filter": {"enabled": True, "config": {"position_gain": 0.5}},
        },
    }


def empty_trajectory_payload(name: str = "empty") -> dict[str, Any]:
    payload = trajectory_payload(name)
    payload["frames"] = []
    payload["summary"]["episode_status"] = "incomplete"
    payload["summary"]["episode_finalize_reason"] = "sim_shutdown"
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def hmd_mapping_frame(
    index: int,
    *,
    eef: list[float],
    input_delta: list[float],
    command: list[float],
    workspace_clamped: bool = False,
) -> dict[str, Any]:
    return {
        "t": index * 0.05,
        "step": index,
        "end_effector_position": eef,
        "action": {
            "raw": input_delta + [0.0, 0.0, 0.0, 1.0],
            "applied": command + [0.0, 0.0, 0.0, 1.0],
            "control_filter": {
                "config": {
                    "position_axis_map": "x,z,y",
                    "rotation_axis_map": "x,y,z",
                    "position_gain": 0.45,
                },
                "teleop_control_mode": {
                    "name": "bounded_direct_ee_target",
                    "control_semantics": "bounded_direct_end_effector_target_servo",
                    "input_delta_xyz": input_delta,
                    "hand_delta_m": input_delta,
                    "desired_ee_target_xyz": eef,
                    "applied_ee_delta_m": command,
                    "actual_ee_xyz": eef,
                    "target_error_norm": sum(value * value for value in command) ** 0.5,
                    "command_step_norm": sum(value * value for value in command) ** 0.5,
                    "max_step_m": 0.05,
                    "deadzone_m": 0.001,
                    "workspace_clamped": workspace_clamped,
                },
            },
        },
        "metadata": {
            "right_hand_tracked": True,
            "xr_frame_valid": True,
            "raw_xr": {
                "right_wrist_pose": [index * 0.01, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0]
            },
        },
    }


def hmd_mapping_payload() -> dict[str, Any]:
    return {
        "id": "traj_hmd_mapping",
        "episode_id": "episode_hmd_mapping",
        "task_id": "task_001",
        "source": {
            "input_device": "quest3_handtracking",
            "runtime": "steamvr_openxr",
            "robot": "franka",
        },
        "frames": [
            hmd_mapping_frame(
                0,
                eef=[0.50, 0.00, 0.20],
                input_delta=[0.01, 0.0, 0.0],
                command=[0.01, 0.0, 0.0],
            ),
            hmd_mapping_frame(
                1,
                eef=[0.51, 0.00, 0.20],
                input_delta=[0.01, 0.0, 0.0],
                command=[0.01, 0.0, 0.0],
            ),
            hmd_mapping_frame(
                2,
                eef=[0.52, 0.00, 0.20],
                input_delta=[0.00, 0.0, 0.0],
                command=[0.00, 0.0, 0.0],
            ),
            hmd_mapping_frame(
                3,
                eef=[0.52, 0.00, 0.20],
                input_delta=[0.00, 0.0, 0.0],
                command=[0.00, 0.0, 0.0],
            ),
        ],
        "summary": {"episode_status": "success"},
    }


def hmd_deadzone_boundary_jump_payload() -> dict[str, Any]:
    payload = hmd_mapping_payload()
    payload["id"] = "traj_deadzone_boundary_jump"
    payload["frames"] = [
        hmd_mapping_frame(
            0,
            eef=[0.58, 0.05, 0.10],
            input_delta=[0.0, 0.0, 0.0],
            command=[0.0, 0.0, 0.0],
        ),
        hmd_mapping_frame(
            1,
            eef=[0.58, 0.05, 0.10],
            input_delta=[0.004, 0.0, 0.0],
            command=[-0.02, -0.02, 0.03],
        ),
    ]
    payload["frames"][0]["action"]["control_filter"]["teleop_control_mode"].update(
        {
            "hand_delta_m": [0.0, 0.0, 0.0],
            "desired_ee_target_xyz": [0.58, 0.05, 0.10],
            "deadzone_m": 0.003,
        }
    )
    payload["frames"][1]["action"]["control_filter"]["teleop_control_mode"].update(
        {
            "hand_delta_m": [0.004, 0.0, 0.0],
            "desired_ee_target_xyz": [0.50, 0.00, 0.20],
            "deadzone_m": 0.003,
        }
    )
    return payload


def hmd_deadzone_entry_snap_payload() -> dict[str, Any]:
    payload = hmd_mapping_payload()
    payload["id"] = "traj_deadzone_entry_snap"
    payload["frames"] = [
        hmd_mapping_frame(
            0,
            eef=[0.58, 0.05, 0.10],
            input_delta=[0.004, 0.0, 0.0],
            command=[0.02, 0.02, -0.03],
        ),
        hmd_mapping_frame(
            1,
            eef=[0.58, 0.05, 0.10],
            input_delta=[0.0, 0.0, 0.0],
            command=[0.0, 0.0, 0.0],
        ),
    ]
    payload["frames"][0]["action"]["control_filter"]["teleop_control_mode"].update(
        {
            "hand_delta_m": [0.004, 0.0, 0.0],
            "desired_ee_target_xyz": [0.50, 0.00, 0.20],
            "deadzone_m": 0.003,
        }
    )
    payload["frames"][1]["action"]["control_filter"]["teleop_control_mode"].update(
        {
            "hand_delta_m": [0.0, 0.0, 0.0],
            "desired_ee_target_xyz": [0.58, 0.05, 0.10],
            "deadzone_m": 0.003,
        }
    )
    return payload


def hmd_valid_wrist_jitter_payload() -> dict[str, Any]:
    payload = hmd_mapping_payload()
    payload["id"] = "traj_valid_wrist_jitter"
    payload["frames"][1]["metadata"]["raw_xr"]["right_wrist_pose"] = [
        0.25,
        0.0,
        0.0,
        1.0,
        0.0,
        0.0,
        0.0,
    ]
    payload["frames"][1]["action"]["control_filter"]["teleop_control_mode"][
        "raw_right_wrist_pose"
    ] = [
        0.25,
        0.0,
        0.0,
        1.0,
        0.0,
        0.0,
        0.0,
    ]
    return payload


def hmd_anchor_fallback_payload() -> dict[str, Any]:
    payload = hmd_mapping_payload()
    payload["id"] = "traj_anchor_fallback"
    anchor_pose = [-0.1, -0.5, -1.05, 1.0, 0.0, 0.0, 0.0]
    for index in (1, 2):
        frame = payload["frames"][index]
        frame["metadata"]["raw_xr"]["right_wrist_pose"] = list(anchor_pose)
        frame["action"]["control_filter"]["teleop_control_mode"][
            "raw_right_wrist_pose"
        ] = list(anchor_pose)
    return payload


def hmd_gated_anchor_fallback_payload() -> dict[str, Any]:
    payload = hmd_anchor_fallback_payload()
    payload["id"] = "traj_gated_anchor_fallback"
    for index in (1, 2):
        frame = payload["frames"][index]
        frame["metadata"]["right_hand_tracked"] = False
        frame["metadata"]["xr_frame_valid"] = False
        frame["metadata"]["tracking_confidence"] = 0.0
    return payload


def test_analyze_teleop_calibration_reports_filter_and_action_stats(
    tmp_path: Path,
) -> None:
    trajectory_path = tmp_path / "traj_latest.json"
    write_json(trajectory_path, trajectory_payload())

    report = analyzer.analyze_trajectory(trajectory_path)

    assert report["trajectory_id"] == "traj_latest"
    assert report["frame_count"] == 3
    assert report["operator_recenter_event_count"] == 1
    assert report["control_filter_frame_count"] == 3
    assert report["suppressed_after_recenter_frame_count"] == 1
    assert report["raw_applied_delta"]["max"] > 0.0
    assert report["position_suppression_ratio"] == 1 / 3
    assert report["raw_position_axes"]["dominant_axis"] == "x"
    assert report["applied_position_axes"]["dominant_axis"] == "x"
    assert report["tracking_quality"]["right_hand_tracked_rate"] == 1.0
    assert report["calibration_summary"]["type"] == "workspace_alignment_v2"
    assert isinstance(report["recommendations"], list)
    assert report["issues"] == []


def test_analyze_hmd_motion_mapping_reports_command_response(tmp_path: Path) -> None:
    trajectory_path = tmp_path / "traj_hmd_mapping.json"
    write_json(trajectory_path, hmd_mapping_payload())

    report = motion_mapping.analyze_trajectory(trajectory_path)

    assert report["trajectory_id"] == "traj_hmd_mapping"
    assert report["config"]["position_axis_map"] == "x,z,y"
    assert (
        report["response"]["raw_action_axis_mapped_to_input_delta"][
            "overall_sign_agree_ratio"
        ]
        == 1.0
    )
    assert (
        report["response"]["command_to_next_eef_delta"]["axis"]["x"]["sign_agree_ratio"]
        == 1.0
    )
    assert report["controller"]["workspace_clamped_ratio"] == 0.0
    assert report["tracking_quality"]["right_hand_tracked_rate"] == 1.0
    assert {item["id"]: item["status"] for item in report["hypotheses"]}["H7"] == "PASS"


def test_analyze_hmd_motion_mapping_flags_dead_hand_command(tmp_path: Path) -> None:
    payload = hmd_mapping_payload()
    payload["id"] = "traj_dead_hand"
    payload["frames"][2] = hmd_mapping_frame(
        2,
        eef=[0.52, 0.00, 0.20],
        input_delta=[0.0, 0.0, 0.0],
        command=[0.02, 0.0, 0.0],
    )
    trajectory_path = tmp_path / "traj_dead_hand.json"
    write_json(trajectory_path, payload)

    report = motion_mapping.analyze_trajectory(trajectory_path)

    assert report["dead_hand"]["command_nonzero_ratio"] > 0.0
    assert {item["id"]: item["status"] for item in report["hypotheses"]}["H4"] in {
        "WARN",
        "FAIL",
    }


def test_analyze_hmd_motion_mapping_flags_deadzone_boundary_target_jump(
    tmp_path: Path,
) -> None:
    trajectory_path = tmp_path / "traj_deadzone_boundary_jump.json"
    write_json(trajectory_path, hmd_deadzone_boundary_jump_payload())

    report = motion_mapping.analyze_trajectory(trajectory_path)

    assert report["deadzone_boundary"]["target_jump_count"] == 1
    assert report["deadzone_boundary"]["target_jump_max"] > 0.10
    assert {item["id"]: item["status"] for item in report["hypotheses"]}[
        "H11"
    ] == "WARN"


def test_analyze_hmd_motion_mapping_ignores_deadzone_entry_snap(tmp_path: Path) -> None:
    trajectory_path = tmp_path / "traj_deadzone_entry_snap.json"
    write_json(trajectory_path, hmd_deadzone_entry_snap_payload())

    report = motion_mapping.analyze_trajectory(trajectory_path)

    assert report["deadzone_boundary"]["target_jump_count"] == 0
    assert report["deadzone_boundary"]["entry_snap_count"] == 1
    assert report["deadzone_boundary"]["entry_snap_max"] > 0.10
    assert {item["id"]: item["status"] for item in report["hypotheses"]}[
        "H11"
    ] == "PASS"


def test_analyze_hmd_motion_mapping_flags_valid_wrist_jitter(tmp_path: Path) -> None:
    trajectory_path = tmp_path / "traj_valid_wrist_jitter.json"
    write_json(trajectory_path, hmd_valid_wrist_jitter_payload())

    report = motion_mapping.analyze_trajectory(trajectory_path)

    assert report["anchor_fallback"]["raw_wrist_jump_gt_10cm_valid_to_valid_count"] == 2
    assert report["anchor_fallback"]["raw_wrist_jump_gt_10cm_valid_to_valid_max"] > 0.20
    assert {item["id"]: item["status"] for item in report["hypotheses"]}[
        "H13"
    ] == "WARN"


def test_runtime_recorder_rejects_configured_xr_anchor_pose(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RDF_XR_ANCHOR_POS", "-0.1,-0.5,-1.05")

    assert (
        runtime_recorder._pose_is_valid([-0.1, -0.5, -1.05, 1.0, 0.0, 0.0, 0.0])
        is False
    )
    assert (
        runtime_recorder._pose_is_valid([-0.099, -0.5, -1.05, 1.0, 0.0, 0.0, 0.0])
        is True
    )


def test_analyze_hmd_motion_mapping_flags_xr_anchor_fallback(tmp_path: Path) -> None:
    trajectory_path = tmp_path / "traj_anchor_fallback.json"
    write_json(trajectory_path, hmd_anchor_fallback_payload())

    report = motion_mapping.analyze_trajectory(trajectory_path)

    assert report["anchor_fallback"]["anchor_like_frame_count"] == 2
    assert report["anchor_fallback"]["anchor_like_frame_ratio"] == 0.5
    assert {item["id"]: item["status"] for item in report["hypotheses"]}[
        "H12"
    ] == "WARN"


def test_analyze_hmd_motion_mapping_distinguishes_gated_anchor_fallback(
    tmp_path: Path,
) -> None:
    trajectory_path = tmp_path / "traj_gated_anchor_fallback.json"
    write_json(trajectory_path, hmd_gated_anchor_fallback_payload())

    report = motion_mapping.analyze_trajectory(trajectory_path)

    assert report["anchor_fallback"]["anchor_like_frame_count"] == 2
    assert report["anchor_fallback"]["anchor_like_valid_frame_count"] == 0
    assert {item["id"]: item["status"] for item in report["hypotheses"]}[
        "H12"
    ] == "PASS"
    assert {item["id"]: item["status"] for item in report["hypotheses"]}["H9"] == "WARN"


def test_live_teleop_rejects_xr_anchor_pose_as_valid_hand() -> None:
    source = Path(
        "/home/kangrim/IsaacLab/scripts/environments/teleoperation/teleop_se3_agent.py"
    ).read_text(encoding="utf-8")

    assert "rdf_pose_is_anchor_fallback" in source
    assert "not rdf_pose_is_anchor_fallback" in source
    assert "tracking_gate_blocked" in source
    assert "not right_hand_valid" in source
    assert "apply_control_active = False" in source


def test_live_teleop_rebases_after_tracking_loss_before_resuming_control() -> None:
    source = Path(
        "/home/kangrim/IsaacLab/scripts/environments/teleoperation/teleop_se3_agent.py"
    ).read_text(encoding="utf-8")

    assert "tracking_reentry_pending" in source
    assert "tracking_resume_valid_count" in source
    assert "tracking_resumed" in source
    assert '.reset(env, "tracking_resumed"' in source


def test_live_teleop_auto_recenter_requires_stable_right_wrist_window() -> None:
    source = Path(
        "/home/kangrim/IsaacLab/scripts/environments/teleoperation/teleop_se3_agent.py"
    ).read_text(encoding="utf-8")

    assert "rdf_auto_recenter_stable_m" in source
    assert "auto_recenter_last_wrist_pose" in source
    assert "auto_recenter_wrist_jump_m" in source
    assert "AUTO_RECENTER_UNSTABLE_RIGHT_WRIST" in source


def test_hmd_axis_debug_uses_hardened_raw_wrist_preflight_defaults() -> None:
    source = (ROOT / "scripts" / "run_hmd_axis_debug.sh").read_text(encoding="utf-8")

    assert 'RDF_WARMUP_VALID_FRAMES="${RDF_WARMUP_VALID_FRAMES:-15}"' in source
    assert (
        'RDF_AUTO_RECENTER_VALID_FRAMES="${RDF_AUTO_RECENTER_VALID_FRAMES:-15}"'
        in source
    )
    assert 'RDF_AUTO_RECENTER_STABLE_M="${RDF_AUTO_RECENTER_STABLE_M:-0.03}"' in source


def test_hmd_axis_debug_uses_close_readable_hmd_panel_defaults() -> None:
    source = (ROOT / "scripts" / "run_hmd_axis_debug.sh").read_text(encoding="utf-8")

    assert 'RDF_TASK_GUIDANCE_PANEL_SIZE="${RDF_TASK_GUIDANCE_PANEL_SIZE:-1.25}"' in source
    assert (
        'RDF_TASK_GUIDANCE_PANEL_TRANSLATION="${RDF_TASK_GUIDANCE_PANEL_TRANSLATION:-0.00,0.10,-1.60}"'
        in source
    )
    assert (
        'RDF_TASK_GUIDANCE_PANEL_LOOK_AT_CAMERA="${RDF_TASK_GUIDANCE_PANEL_LOOK_AT_CAMERA:-1}"'
        in source
    )
    assert (
        'RDF_TASK_GUIDANCE_PANEL_BACKGROUND_ALPHA="${RDF_TASK_GUIDANCE_PANEL_BACKGROUND_ALPHA:-0.90}"'
        in source
    )
    assert (
        'RDF_TASK_GUIDANCE_PANEL_ANCHOR_MODE="${RDF_TASK_GUIDANCE_PANEL_ANCHOR_MODE:-upstream_instruction}"'
        in source
    )
    assert "HMD panel: visibility-probe XR overlay" in source


def test_live_smoke_default_hmd_panel_is_close_and_readable() -> None:
    source = (ROOT / "scripts" / "run_live_rdf_smoke_test.sh").read_text(
        encoding="utf-8"
    )

    assert 'RDF_TASK_GUIDANCE_PANEL_SIZE="${RDF_TASK_GUIDANCE_PANEL_SIZE:-1.25}"' in source
    assert (
        'RDF_TASK_GUIDANCE_PANEL_TRANSLATION="${RDF_TASK_GUIDANCE_PANEL_TRANSLATION:-0.00,0.10,-1.60}"'
        in source
    )
    assert (
        'RDF_TASK_GUIDANCE_PANEL_LOOK_AT_CAMERA="${RDF_TASK_GUIDANCE_PANEL_LOOK_AT_CAMERA:-1}"'
        in source
    )
    assert (
        'RDF_TASK_GUIDANCE_PANEL_BACKGROUND_ALPHA="${RDF_TASK_GUIDANCE_PANEL_BACKGROUND_ALPHA:-0.90}"'
        in source
    )
    assert (
        'RDF_TASK_GUIDANCE_PANEL_ANCHOR_MODE="${RDF_TASK_GUIDANCE_PANEL_ANCHOR_MODE:-upstream_instruction}"'
        in source
    )
    assert "RDF_TASK_GUIDANCE_PANEL_SIZE Default: 1.25" in source
    assert "RDF_TASK_GUIDANCE_PANEL_TRANSLATION Default: 0.00,0.10,-1.60" in source
    assert "RDF_TASK_GUIDANCE_PANEL_LOOK_AT_CAMERA Default: 1" in source
    assert "RDF_TASK_GUIDANCE_PANEL_BACKGROUND_ALPHA Default: 0.90" in source
    assert "RDF_TASK_GUIDANCE_PANEL_ANCHOR_MODE Default: upstream_instruction" in source


def test_live_teleop_hmd_guidance_panel_exposes_input_and_motion_status() -> None:
    source = Path(
        "/home/kangrim/IsaacLab/scripts/environments/teleoperation/teleop_se3_agent.py"
    ).read_text(encoding="utf-8")

    assert "TRACKING:" in source
    assert "CONTROL:" in source
    assert "MOTION:" in source
    assert "RAW_JUMP:" in source
    assert "rdf_task_guidance_panel_look_at_camera" in source
    assert "rdf_task_guidance_panel_background_alpha" in source
    assert "rdf_task_guidance_panel_anchor_mode" in source
    assert "new_look_at_camera_source" in source
    assert "show_instruction" in source
    assert "update_instruction" in source
    assert "upstream_instruction_anchor" in source
    assert "CopyPrim" in source
    assert "HMD task guidance widget CopyPrim failed" in source
    assert "copy_follow_anchor" in source
    assert "ComputeLocalToWorldTransform" in source
    assert "_sync_target_to_source" in source
    widget_start = source.index("class RdfXrTaskGuidanceWidget:")
    widget_end = source.index("\n\nclass RdfUsdTaskGuidancePanel")
    widget_class = source[widget_start:widget_end]
    create_body = widget_class[
        widget_class.index("    def _create_widget(") : widget_class.index("    def _prepare_target_transform_op")
    ]
    assert "self._copy_failed_logged" in widget_class
    assert "not self._stage.GetPrimAtPath(target_prim_path).IsValid()" in create_body
    assert "copy_follow transform setup failed" in create_body
    assert create_body.index("HMD task guidance widget CopyPrim failed") < create_body.index(
        "if space_stack is None:"
    )
    update_body = widget_class[widget_class.index("    def update(") :]
    assert "self._sync_target_to_source()" in update_body
    assert update_body.index("self._sync_target_to_source()") < update_body.index(
        "if text == self._last_text"
    )
    assert "hmd_motion_debug" in source
    assert "last_motion_delta_norm" in source


def test_hmd_log_summary_surfaces_openxr_session_failures(tmp_path: Path) -> None:
    import importlib.util

    script_path = ROOT / "scripts" / "summarize_hmd_run_log.py"
    spec = importlib.util.spec_from_file_location("summarize_hmd_run_log", script_path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    storage_root = tmp_path / "storage"
    storage_root.mkdir()
    log_file = storage_root / "hmd.log"
    log_file.write_text(
        "\n".join(
            (
                "Error [GENERAL | xrCreateInstance | OpenXR-Loader] : xrCreateInstance failed",
                "[omni.kit.xr.core.scripts.xr_core_extension] /app/hydra/renderSettings/useUsdAttributes is disabled at XR session start",
            )
        ),
        encoding="utf-8",
    )

    summary = module.build_summary(storage_root=storage_root, log_file=log_file)

    assert summary["log_counts"]["OPENXR_CREATE_INSTANCE_FAILED"] == 1
    assert summary["log_counts"]["XR_SESSION_START"] == 1
    assert "OPENXR_CREATE_INSTANCE_FAILED" in summary["decision"]["reasons"]


def test_hmd_axis_debug_captures_operator_log_to_storage() -> None:
    script_path = ROOT / "scripts" / "run_hmd_axis_debug.sh"
    source = script_path.read_text(encoding="utf-8")

    assert 'RDF_HMD_LOG_CAPTURE="${RDF_HMD_LOG_CAPTURE:-1}"' in source
    assert "logs/hmd_axis_debug" in source
    assert 'tee -a "$RDF_HMD_LOG_FILE"' in source
    assert "summarize_hmd_run_log.py" in source


def test_hmd_log_summary_blocks_gate_a_on_unstable_recenter_and_raw_wrist_jump(
    tmp_path: Path,
) -> None:
    log_file = tmp_path / "hmd.log"
    log_file.write_text(
        "\n".join(
            [
                "[RDF] AUTO_RECENTER_UNSTABLE_RIGHT_WRIST",
                "[RDF] raw_wrist_spike_reacquire_pending",
                "[RDF] AUTO_RECENTER_UNSTABLE_RIGHT_WRIST",
            ]
        ),
        encoding="utf-8",
    )
    evaluation_file = tmp_path / "eval.json"
    write_json(
        evaluation_file,
        {
            "id": "eval_input_quality",
            "trajectory_id": "traj_input_quality",
            "episode_id": "episode_input_quality",
            "failure_reason": "RAW_WRIST_JUMP",
            "failure_category": "DATA_QUALITY_FAILURE",
            "metrics": {
                "tracking_loss_rate": 0.0,
                "raw_wrist_valid_to_valid_jump": {
                    "fail": True,
                    "threshold_m": 0.1,
                    "max_m": 0.42,
                    "count_over_threshold": 4,
                    "gate_reason_counts": {
                        "raw_wrist_spike_reacquire_pending": 3,
                    },
                },
            },
        },
    )
    analysis_file = tmp_path / "analysis.json"
    write_json(
        analysis_file,
        {
            "aggregate": {"warning_or_fail_count": 1},
            "trajectories": [
                {
                    "trajectory_id": "traj_input_quality",
                    "tracking_quality": {
                        "right_hand_tracked_rate": 1.0,
                        "xr_frame_valid_rate": 1.0,
                    },
                    "anchor_fallback": {
                        "raw_wrist_jump_gt_10cm_valid_to_valid_count": 4,
                        "raw_wrist_jump_gt_10cm_valid_to_valid_max": 0.42,
                    },
                    "hypotheses": [
                        {"id": "H9", "status": "PASS"},
                        {"id": "H13", "status": "WARN"},
                    ],
                }
            ],
        },
    )

    summary = log_summary.build_summary(
        storage_root=tmp_path,
        log_file=log_file,
        evaluation_file=evaluation_file,
        analysis_file=analysis_file,
    )

    assert summary["log_counts"]["AUTO_RECENTER_UNSTABLE_RIGHT_WRIST"] == 2
    assert summary["log_counts"]["raw_wrist_spike_reacquire_pending"] == 1
    assert summary["evaluation"]["failure_reason"] == "RAW_WRIST_JUMP"
    assert summary["classification"] == "input_quality_failure"
    assert summary["analysis"]["H13_status"] == "WARN"
    assert summary["decision"]["gate_a_collection_allowed"] is False
    assert (
        "AUTO_RECENTER_UNSTABLE_RIGHT_WRIST_PRESENT" in summary["decision"]["reasons"]
    )
    assert "RAW_WRIST_JUMP_INPUT_QUALITY_FAILURE" in summary["decision"]["reasons"]
    assert "H13_NOT_PASS" in summary["decision"]["reasons"]


def gate0_viability_frame(
    index: int,
    *,
    t: float | None = None,
    wrist_xyz: list[float] | None,
    right_hand_tracked: bool = True,
    xr_frame_valid: bool = True,
    input_latency_ms: float = 25.0,
    action_hold: bool = False,
    hold_reason: str | None = None,
    tracking_epoch_id: int = 0,
) -> dict[str, Any]:
    pose = None
    if wrist_xyz is not None:
        pose = [*wrist_xyz, 1.0, 0.0, 0.0, 0.0]
    frame = {
        "step": index,
        "end_effector_position": [0.5, 0.0, 0.2],
        "object_position": [0.4, 0.0, 0.1],
        "action": {
            "raw": [0.0, 0.0, 0.0, 0.0],
            "applied": [0.0, 0.0, 0.0, 0.0],
        },
        "metadata": {
            "right_hand_tracked": right_hand_tracked,
            "xr_frame_valid": xr_frame_valid,
            "right_wrist_pose": pose or [],
            "raw_xr": {"right_wrist_pose": pose or []},
            "input_latency_ms": input_latency_ms,
            "action_hold": action_hold,
            "hold_reason": hold_reason,
            "tracking_epoch_id": tracking_epoch_id,
        },
    }
    if t is not None:
        frame["t"] = t
    return frame


def gate0_viability_payload(frames: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "id": "traj_gate0",
        "episode_id": "episode_gate0",
        "task_id": "task_gate0",
        "schema_version": "0.1.0",
        "source": {
            "input_device": "quest3_handtracking",
            "runtime": "steamvr_openxr",
            "simulator": "isaac_lab",
            "robot": "franka",
            "task_name": "Isaac-Forge-PegInsert-Direct-v0",
        },
        "frames": frames,
        "summary": {
            "episode_status": "incomplete",
            "gate0_test_type": "tracking_reacquire",
            "gate_a_collection_blocked": True,
        },
    }


def test_wrist_pose_sample_normalizes_legacy_quest_openxr_frame() -> None:
    frame = gate0_viability_frame(
        7,
        t=1.25,
        wrist_xyz=[0.12, -0.34, 0.56],
        input_latency_ms=37.5,
        action_hold=True,
        hold_reason="tracking_resume_warmup",
        tracking_epoch_id=2,
    )

    adapter = input_sources.QuestOpenXrHandtrackingAdapter()
    sample = adapter.sample_from_frame(frame, fallback_index=7)

    assert sample.schema_version == input_sources.WRIST_POSE_SAMPLE_SCHEMA_VERSION
    assert sample.source_id == "quest_openxr_handtracking"
    assert sample.source_kind == "handtracking"
    assert sample.runtime == "steamvr_openxr"
    assert sample.device == "quest3"
    assert sample.input_channel == "right_wrist"
    assert sample.frame_index == 7
    assert sample.timestamp_sec == pytest.approx(1.25)
    assert sample.pose == pytest.approx([0.12, -0.34, 0.56, 1.0, 0.0, 0.0, 0.0])
    assert sample.position_xyz == pytest.approx([0.12, -0.34, 0.56])
    assert sample.tracked is True
    assert sample.frame_valid is True
    assert sample.sample_valid is True
    assert sample.input_latency_ms == pytest.approx(37.5)
    assert sample.action_hold is True
    assert sample.hold_reason == "tracking_resume_warmup"
    assert sample.tracking_epoch_id == 2
    assert sample.quality_flags == []

    signal_state = sample.input_signal_state()

    assert (
        signal_state.schema_version == input_sources.INPUT_SIGNAL_STATE_SCHEMA_VERSION
    )
    assert signal_state.sample_valid is True
    assert signal_state.tracking_valid is True
    assert signal_state.control_safe is False
    assert signal_state.learning_label_eligible is False
    assert signal_state.learning_label_ineligible_reason == (
        "hold:tracking_resume_warmup"
    )
    assert signal_state.timestamp_source == "frame_t"
    assert signal_state.input_latency_source == "metadata.input_latency_ms"
    assert signal_state.tracking_confidence is None
    assert signal_state.tracking_confidence_source == "not_available"
    assert "action_hold" in signal_state.control_safety_flags


def test_input_signal_state_marks_clean_sample_control_safe() -> None:
    frame = gate0_viability_frame(
        9,
        t=1.35,
        wrist_xyz=[0.20, -0.10, 0.40],
        input_latency_ms=18.0,
        action_hold=False,
        hold_reason=None,
        tracking_epoch_id=3,
    )
    frame["metadata"]["tracking_confidence"] = 0.82

    sample = input_sources.QuestOpenXrHandtrackingAdapter().sample_from_frame(
        frame, fallback_index=9
    )
    signal_state = sample.input_signal_state()

    assert signal_state.sample_valid is True
    assert signal_state.tracking_valid is True
    assert signal_state.control_safe is True
    assert signal_state.control_safety_flags == []
    assert signal_state.learning_label_eligible is True
    assert signal_state.learning_label_ineligible_reason is None
    assert signal_state.tracking_confidence == pytest.approx(0.82)
    assert signal_state.tracking_confidence_source == "metadata.tracking_confidence"
    assert signal_state.tracking_epoch_id == 3


def test_input_truth_classification_prioritizes_invalid_over_unsafe_and_never_allows() -> None:
    frame = gate0_viability_frame(
        10,
        t=None,
        wrist_xyz=None,
        right_hand_tracked=False,
        xr_frame_valid=False,
        action_hold=True,
        hold_reason="raw_wrist_spike_reacquire_pending",
    )

    sample = input_sources.QuestOpenXrHandtrackingAdapter().sample_from_frame(
        frame, fallback_index=10
    )
    signal_state = sample.input_signal_state()
    classification = signal_state.input_truth_classification

    assert classification["schema_version"] == (
        input_sources.INPUT_TRUTH_CLASSIFICATION_SCHEMA_VERSION
    )
    assert classification["truth_state"] == "invalid"
    assert classification["primary_reason"] == "MISSING_RIGHT_WRIST_POSE"
    assert classification["sample_valid"] is False
    assert classification["tracking_valid"] is False
    assert classification["timestamp_state"] == "fallback"
    assert classification["confidence_state"] == "not_available"
    assert classification["position_truth_state"] == "missing"
    assert classification["action_hold_required"] is True
    assert classification["resume_block"] is True
    assert classification["recenter_block"] is True
    assert classification["allow_authority"] is False
    assert "UNTRACKED_RIGHT_HAND" in classification["frame_reason_codes"]
    assert "INVALID_XR_FRAME" in classification["frame_reason_codes"]
    assert "RAW_WRIST_SPIKE_REACQUIRE_PENDING" in classification["frame_reason_codes"]
    assert "TIMESTAMP_FALLBACK_INDEX" in classification["frame_reason_codes"]
    assert "TRACKING_CONFIDENCE_NOT_AVAILABLE" in classification["frame_reason_codes"]


def test_input_truth_classification_detects_anchor_fallback_and_provenance_only_valid() -> None:
    anchor_frame = gate0_viability_frame(
        11,
        t=0.55,
        wrist_xyz=[0.0, 0.0, 0.0],
        right_hand_tracked=True,
        xr_frame_valid=True,
    )
    anchor_frame["metadata"]["right_wrist_anchor_fallback"] = True
    anchor_sample = input_sources.QuestOpenXrHandtrackingAdapter().sample_from_frame(
        anchor_frame, fallback_index=11
    )

    anchor_signal_state = anchor_sample.input_signal_state()
    anchor_classification = anchor_signal_state.input_truth_classification

    assert anchor_classification["truth_state"] == "invalid"
    assert anchor_classification["primary_reason"] == "ANCHOR_FALLBACK_POSE"
    assert anchor_classification["position_truth_state"] == "anchor_fallback"
    assert anchor_classification["allow_authority"] is False
    assert anchor_signal_state.action_hold is True
    assert anchor_signal_state.control_safe is False
    assert anchor_signal_state.input_truth_control_state["resume_block"] is True
    assert anchor_signal_state.input_truth_control_state["recenter_block"] is True
    assert "resume_allowed" not in anchor_signal_state.input_truth_control_state
    assert "recenter_allowed" not in anchor_signal_state.input_truth_control_state

    provenance_frame = gate0_viability_frame(
        12,
        t=None,
        wrist_xyz=[0.12, 0.0, 0.0],
        right_hand_tracked=True,
        xr_frame_valid=True,
    )
    provenance_sample = (
        input_sources.QuestOpenXrHandtrackingAdapter().sample_from_frame(
            provenance_frame, fallback_index=12
        )
    )

    provenance_classification = (
        provenance_sample.input_signal_state().input_truth_classification
    )

    assert provenance_classification["truth_state"] == "valid"
    assert provenance_classification["primary_reason"] == "TIMESTAMP_FALLBACK_INDEX"
    assert "TRACKING_CONFIDENCE_NOT_AVAILABLE" in (
        provenance_classification["frame_reason_codes"]
    )
    assert provenance_classification["resume_block"] is False
    assert provenance_classification["recenter_block"] is False
    assert provenance_classification["allow_authority"] is False


def test_input_truth_block_only_merge_preserves_existing_blocks_and_never_grants() -> None:
    frame = gate0_viability_frame(
        13,
        t=0.65,
        wrist_xyz=[0.40, 0.0, 0.0],
        right_hand_tracked=True,
        xr_frame_valid=True,
    )
    sample = input_sources.QuestOpenXrHandtrackingAdapter().sample_from_frame(
        frame, fallback_index=13
    )
    classification = input_sources.classify_input_truth(
        sample,
        previous_valid_position_xyz=[0.0, 0.0, 0.0],
        raw_wrist_jump_warn_m=0.10,
        raw_wrist_jump_reject_m=0.15,
    ).as_dict()

    merged = input_sources.merge_input_truth_soft_blocks(
        {
            "action_hold": True,
            "hold_reason": "procedural_stable_window",
            "resume_block": True,
            "resume_block_reason": "existing_resume_block",
            "recenter_block": False,
            "resume_allowed": False,
            "recenter_allowed": False,
        },
        classification,
    )

    assert classification["truth_state"] == "unsafe"
    assert classification["primary_reason"] == "RAW_WRIST_JUMP_REJECT"
    assert merged["action_hold"] is True
    assert merged["hold_reason"] == "procedural_stable_window"
    assert merged["resume_block"] is True
    assert merged["resume_block_reason"] == "existing_resume_block"
    assert merged["recenter_block"] is True
    assert merged["recenter_block_reason"] == "RAW_WRIST_JUMP_REJECT"
    assert merged["allow_authority"] is False
    assert "resume_allowed" not in merged
    assert "recenter_allowed" not in merged
    assert "gate0_pass" not in merged
    assert "gate_a_collection_allowed" not in merged


def test_wrist_pose_sample_preserves_legacy_invalid_frame_without_interpolation() -> (
    None
):
    frame = gate0_viability_frame(
        8,
        t=1.30,
        wrist_xyz=None,
        right_hand_tracked=False,
        xr_frame_valid=False,
        action_hold=True,
        hold_reason="invalid_right_hand",
    )

    sample = input_sources.QuestOpenXrHandtrackingAdapter().sample_from_frame(
        frame, fallback_index=8
    )

    assert sample.pose is None
    assert sample.position_xyz is None
    assert sample.tracked is False
    assert sample.frame_valid is False
    assert sample.sample_valid is False
    assert sample.action_hold is True
    assert sample.hold_reason == "invalid_right_hand"
    assert "missing_right_wrist_pose" in sample.quality_flags
    assert "untracked_right_hand" in sample.quality_flags
    assert "invalid_xr_frame" in sample.quality_flags

    signal_state = sample.input_signal_state()

    assert signal_state.sample_valid is False
    assert signal_state.tracking_valid is False
    assert signal_state.control_safe is False
    assert signal_state.learning_label_eligible is False
    assert signal_state.learning_label_ineligible_reason == "invalid_input_sample"
    assert "invalid_input_sample" in signal_state.control_safety_flags
    assert "action_hold" in signal_state.control_safety_flags


def test_input_source_adapter_factory_selects_quest_openxr_handtracking() -> None:
    adapter = input_sources.adapter_for_trajectory_source(
        {
            "input_device": "quest3_handtracking",
            "runtime": "steamvr_openxr",
            "simulator": "isaac_lab",
            "robot": "franka",
            "task_name": "Isaac-Forge-PegInsert-Direct-v0",
        }
    )

    assert isinstance(adapter, input_sources.QuestOpenXrHandtrackingAdapter)


def test_input_source_adapter_factory_leaves_unimplemented_sources_unclaimed() -> None:
    assert (
        input_sources.adapter_for_trajectory_source(
            {
                "input_device": "mediapipe_wrist_tracking",
                "runtime": "webcam",
            }
        )
        is None
    )


def test_gate0_report_separates_tracking_loss_raw_wrist_jump_and_recenter_instability(
    tmp_path: Path,
) -> None:
    trajectory_file = tmp_path / "traj_gate0_fail.json"
    log_file = tmp_path / "gate0.log"
    write_json(
        trajectory_file,
        gate0_viability_payload(
            [
                gate0_viability_frame(0, t=0.00, wrist_xyz=[0.00, 0.0, 0.0]),
                gate0_viability_frame(1, t=0.05, wrist_xyz=[0.01, 0.0, 0.0]),
                gate0_viability_frame(
                    2,
                    t=0.10,
                    wrist_xyz=None,
                    right_hand_tracked=False,
                    xr_frame_valid=False,
                    input_latency_ms=120.0,
                    action_hold=True,
                    hold_reason="invalid_right_hand",
                ),
                gate0_viability_frame(
                    3,
                    t=0.30,
                    wrist_xyz=[0.40, 0.0, 0.0],
                    input_latency_ms=80.0,
                    action_hold=True,
                    hold_reason="tracking_resume_warmup",
                    tracking_epoch_id=1,
                ),
                gate0_viability_frame(
                    4,
                    t=0.35,
                    wrist_xyz=[0.405, 0.0, 0.0],
                    tracking_epoch_id=1,
                ),
            ]
        ),
    )
    log_file.write_text(
        "\n".join(
            [
                "[RDF][RECENTER] AUTO_RECENTER_UNSTABLE_RIGHT_WRIST jump=0.4m",
                "[RDF][RECENTER] AUTO_RECENTER_UNSTABLE_RIGHT_WRIST jump=0.3m",
                "[RDF][TRACKING_GATE] right wrist tracking not ready reason=invalid_right_hand",
            ]
        ),
        encoding="utf-8",
    )

    report = gate0.build_report(
        trajectory_path=trajectory_file,
        log_file=log_file,
        test_type="tracking_reacquire",
    )
    metrics = report["metrics"]

    assert report["gate0_pass"] is False
    assert report["gate_a_collection_allowed"] is False
    assert metrics["right_hand_tracked_rate"] == pytest.approx(0.8)
    assert metrics["xr_frame_valid_rate"] == pytest.approx(0.8)
    assert metrics["tracking_loss_count"] == 1
    assert metrics["tracking_loss_duration_ms"] > 0.0
    assert metrics["raw_wrist_jump_count"] == 1
    assert metrics["auto_recenter_unstable_count"] == 2
    assert metrics["wrist_position_delta_max"] == pytest.approx(0.39)
    assert metrics["frame_drop_rate"] == pytest.approx(0.25)
    assert metrics["input_latency_ms"]["max"] == pytest.approx(120.0)
    assert report["H13"]["status"] == "FAIL"
    assert "RAW_WRIST_JUMP" in report["failure_reasons"]
    assert "TRACKING_LOSS" in report["failure_reasons"]
    assert "AUTO_RECENTER_UNSTABLE_RIGHT_WRIST" in report["failure_reasons"]
    assert report["action_hold"]["hold_frame_count"] == 2
    assert report["tracking_epochs"]["epoch_ids"] == [0, 1]
    assert report["input_source"]["source_id"] == "quest_openxr_handtracking"
    assert report["input_source"]["adapter_status"] == "matched_source"


def test_gate0_report_emits_frame_and_epoch_input_truth_summaries(
    tmp_path: Path,
) -> None:
    trajectory_file = tmp_path / "traj_gate0_truth_summary.json"
    write_json(
        trajectory_file,
        gate0_viability_payload(
            [
                gate0_viability_frame(
                    0,
                    t=0.00,
                    wrist_xyz=[0.00, 0.0, 0.0],
                    tracking_epoch_id=0,
                ),
                gate0_viability_frame(
                    1,
                    t=0.05,
                    wrist_xyz=[0.01, 0.0, 0.0],
                    tracking_epoch_id=0,
                ),
                gate0_viability_frame(
                    2,
                    t=0.10,
                    wrist_xyz=None,
                    right_hand_tracked=False,
                    xr_frame_valid=False,
                    action_hold=True,
                    hold_reason="invalid_right_hand",
                    tracking_epoch_id=1,
                ),
                gate0_viability_frame(
                    3,
                    t=0.15,
                    wrist_xyz=[0.35, 0.0, 0.0],
                    action_hold=True,
                    hold_reason="raw_wrist_spike_reacquire_pending",
                    tracking_epoch_id=2,
                ),
                gate0_viability_frame(
                    4,
                    t=0.20,
                    wrist_xyz=[0.355, 0.0, 0.0],
                    action_hold=True,
                    hold_reason="raw_wrist_spike_reacquired",
                    tracking_epoch_id=2,
                ),
            ]
        ),
    )

    report = gate0.build_report(
        trajectory_path=trajectory_file,
        test_type="tracking_reacquire",
    )

    assert report["classification_schema_version"] == (
        input_sources.INPUT_TRUTH_CLASSIFICATION_SCHEMA_VERSION
    )
    frame_summary = report["frame_classification_summary"]
    assert frame_summary["truth_state_counts"]["valid"] >= 2
    assert frame_summary["truth_state_counts"]["invalid"] == 1
    assert frame_summary["reason_counts"]["MISSING_RIGHT_WRIST_POSE"] == 1
    assert frame_summary["reason_counts"]["RAW_WRIST_JUMP_REJECT"] >= 1
    assert frame_summary["reason_counts"]["RAW_WRIST_SPIKE_REACQUIRE_PENDING"] == 1
    assert frame_summary["primary_reason_counts"]["MISSING_RIGHT_WRIST_POSE"] == 1

    epoch_summary = report["epoch_classification_summary"]
    assert epoch_summary["epoch_count"] == 3
    epochs = {epoch["tracking_epoch_id"]: epoch for epoch in epoch_summary["epochs"]}
    assert epochs[0]["valid_count"] == 2
    assert epochs[1]["invalid_count"] == 1
    assert epochs[2]["unsafe_count"] >= 1
    assert "RAW_WRIST_SPIKE_REACQUIRE_PENDING" in epochs[2]["epoch_reason_codes"]
    assert epochs[2]["transition_reason"] in {
        "RAW_WRIST_JUMP_REJECT",
        "RAW_WRIST_SPIKE_REACQUIRE_PENDING",
    }
    assert report["metrics"]["raw_wrist_jump_count"] == 1
    assert report["action_hold"]["hold_frame_count"] == 3
    assert report["tracking_epochs"]["epoch_ids"] == [0, 1, 2]


def test_gate0_report_passes_clean_static_hand_stream(tmp_path: Path) -> None:
    trajectory_file = tmp_path / "traj_gate0_pass.json"
    write_json(
        trajectory_file,
        gate0_viability_payload(
            [
                gate0_viability_frame(0, t=0.00, wrist_xyz=[0.000, 0.0, 0.0]),
                gate0_viability_frame(1, t=0.05, wrist_xyz=[0.002, 0.0, 0.0]),
                gate0_viability_frame(2, t=0.10, wrist_xyz=[0.003, 0.0, 0.0]),
                gate0_viability_frame(3, t=0.15, wrist_xyz=[0.004, 0.0, 0.0]),
            ]
        ),
    )

    report = gate0.build_report(trajectory_path=trajectory_file, test_type="static")

    assert report["gate0_pass"] is True
    assert report["gate_a_collection_allowed"] is True
    assert report["H13"]["status"] == "PASS"
    assert report["failure_reasons"] == []
    assert report["metrics"]["right_hand_tracked_rate"] == pytest.approx(1.0)
    assert report["metrics"]["raw_wrist_jump_count"] == 0
    assert report["metrics"]["auto_recenter_unstable_count"] == 0
    assert report["input_source"]["sample_schema_version"] == (
        input_sources.WRIST_POSE_SAMPLE_SCHEMA_VERSION
    )


def test_gate0_report_rejects_unimplemented_input_source(tmp_path: Path) -> None:
    trajectory_file = tmp_path / "traj_gate0_unsupported.json"
    payload = gate0_viability_payload(
        [
            gate0_viability_frame(0, t=0.00, wrist_xyz=[0.000, 0.0, 0.0]),
            gate0_viability_frame(1, t=0.05, wrist_xyz=[0.002, 0.0, 0.0]),
        ]
    )
    payload["source"] = {
        "input_device": "mediapipe_wrist_tracking",
        "runtime": "webcam",
        "simulator": "isaac_lab",
        "robot": "franka",
        "task_name": "Isaac-Forge-PegInsert-Direct-v0",
    }
    write_json(trajectory_file, payload)

    report = gate0.build_report(trajectory_path=trajectory_file, test_type="static")

    assert report["gate0_pass"] is False
    assert report["gate_a_collection_allowed"] is False
    assert "UNSUPPORTED_INPUT_SOURCE" in report["failure_reasons"]
    assert report["input_source"]["source_id"] is None
    assert report["input_source"]["adapter_status"] == "unsupported_source"


def test_gate0_report_rejects_missing_input_source(tmp_path: Path) -> None:
    trajectory_file = tmp_path / "traj_gate0_unknown_source.json"
    payload = gate0_viability_payload(
        [
            gate0_viability_frame(0, t=0.00, wrist_xyz=[0.000, 0.0, 0.0]),
            gate0_viability_frame(1, t=0.05, wrist_xyz=[0.002, 0.0, 0.0]),
        ]
    )
    payload.pop("source")
    write_json(trajectory_file, payload)

    report = gate0.build_report(trajectory_path=trajectory_file, test_type="static")

    assert report["gate0_pass"] is False
    assert report["gate_a_collection_allowed"] is False
    assert "UNKNOWN_INPUT_SOURCE" in report["failure_reasons"]
    assert report["input_source"]["source_id"] is None
    assert report["input_source"]["adapter_status"] == "unknown_source"
    assert report["metrics"]["right_hand_tracked_rate"] == pytest.approx(0.0)


def test_hmd_axis_debug_exposes_gate0_diagnostic_modes() -> None:
    source = (ROOT / "scripts" / "run_hmd_axis_debug.sh").read_text(encoding="utf-8")

    for mode in (
        "gate0-static",
        "gate0-slow-motion",
        "gate0-recenter",
        "gate0-reacquire",
    ):
        assert mode in source
    assert "RDF_GATE0_TEST_TYPE" in source
    assert 'RDF_GATE_A_COLLECTION_BLOCKED="1"' in source
    assert "run_gate0_xr_input_viability.py" in source
    assert "Gate 0" in source


def test_hmd_axis_debug_exposes_gate0_all_batch_mode() -> None:
    source = (ROOT / "scripts" / "run_hmd_axis_debug.sh").read_text(encoding="utf-8")

    assert "gate0-all" in source
    assert "GATE0_ALL_MODES" in source
    assert "RDF_GATE0_ALL_REPORT_FILE" in source
    assert "gate0_all_pass" in source
    for mode in (
        "gate0-static",
        "gate0-slow-motion",
        "gate0-recenter",
        "gate0-reacquire",
    ):
        assert mode in source


def test_collection_loop_hard_blocks_gate_a_until_gate0_all_passes() -> None:
    source = (ROOT / "scripts" / "run_collection_loop.sh").read_text(encoding="utf-8")

    assert "require_gate0_pass" in source
    assert "RDF_REQUIRE_GATE0_FOR_GATE_A" not in source
    assert "*.gate0_all.json" in source
    assert "gate0_all_pass" in source
    assert "gate_a_collection_allowed" in source
    assert "exit 42" in source


GATE0_ALL_MODES = [
    "gate0-static",
    "gate0-slow-motion",
    "gate0-recenter",
    "gate0-reacquire",
]


def gate0_all_payload(*, passed: bool) -> dict[str, Any]:
    failure_reasons = [] if passed else ["RAW_WRIST_JUMP"]
    stages = [
        {
            "mode": mode,
            "report_path": f"/tmp/{mode}.gate0.json",
            "exists": True,
            "gate0_pass": passed,
            "gate_a_collection_allowed": passed,
            "failure_reasons": failure_reasons,
            "input_source": {
                "source_id": "quest_openxr_handtracking",
                "adapter": "QuestOpenXrHandtrackingAdapter",
                "adapter_status": "matched_source",
                "sample_schema_version": input_sources.WRIST_POSE_SAMPLE_SCHEMA_VERSION,
                "trajectory_source": {
                    "input_device": "quest3_handtracking",
                    "runtime": "steamvr_openxr",
                },
            },
        }
        for mode in GATE0_ALL_MODES
    ]
    return {
        "schema_version": "rdf_gate0_all_report_v0.1.0",
        "gate0_all_pass": passed,
        "gate_a_collection_allowed": passed,
        "stage_order": GATE0_ALL_MODES,
        "failure_reasons": failure_reasons,
        "stages": stages,
    }


def run_collection_loop_gate0_preflight(
    tmp_path: Path,
    *,
    report: dict[str, Any] | None = None,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    storage_root = tmp_path / "storage"
    if report is not None:
        report_path = (
            storage_root
            / "logs"
            / "hmd_axis_debug"
            / "hmd_axis_debug_test_gate0-all.log.gate0_all.json"
        )
        write_json(report_path, report)

    env = os.environ.copy()
    env.update(
        {
            "STORAGE_ROOT": str(storage_root),
            "RDF_COLLECTION_LOOP_GATE0_PREFLIGHT_ONLY": "1",
        }
    )
    if extra_env:
        env.update(extra_env)

    return subprocess.run(
        ["bash", "scripts/run_collection_loop.sh"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=20,
        check=False,
    )


def test_collection_loop_blocks_missing_gate0_all_report(tmp_path: Path) -> None:
    result = run_collection_loop_gate0_preflight(tmp_path)

    assert result.returncode == 42
    assert "missing Gate 0 aggregate report" in result.stdout


def test_collection_loop_blocks_failed_gate0_all_report(tmp_path: Path) -> None:
    result = run_collection_loop_gate0_preflight(
        tmp_path,
        report=gate0_all_payload(passed=False),
    )

    assert result.returncode == 42
    assert "GATE0_STAGE_FAILED" in result.stdout


def test_collection_loop_blocks_unverified_gate0_input_source(tmp_path: Path) -> None:
    report = gate0_all_payload(passed=True)
    report["stages"][0]["input_source"] = {
        "source_id": None,
        "adapter": None,
        "adapter_status": "unsupported_source",
    }

    result = run_collection_loop_gate0_preflight(tmp_path, report=report)

    assert result.returncode == 42
    assert "INPUT_SOURCE_UNVERIFIED" in result.stdout


def test_collection_loop_ignores_attempted_gate0_bypass_env(tmp_path: Path) -> None:
    result = run_collection_loop_gate0_preflight(
        tmp_path,
        extra_env={"RDF_REQUIRE_GATE0_FOR_GATE_A": "0"},
    )

    assert result.returncode == 42
    assert "missing Gate 0 aggregate report" in result.stdout


def test_collection_loop_accepts_recent_complete_gate0_all_report(
    tmp_path: Path,
) -> None:
    result = run_collection_loop_gate0_preflight(
        tmp_path,
        report=gate0_all_payload(passed=True),
    )

    assert result.returncode == 0
    assert "[LOOP][GATE0] PASS" in result.stdout
    assert "preflight-only check passed" in result.stdout


def test_runtime_recorder_adds_gate0_action_hold_and_tracking_epoch_metadata(
    monkeypatch,
) -> None:
    frames_to_return = [
        {
            "t": 0.0,
            "step": 0,
            "action": {"applied": [0.0, 0.0, 0.0]},
            "metadata": {"right_hand_tracked": False, "xr_frame_valid": False},
        },
        {
            "t": 0.05,
            "step": 1,
            "action": {"applied": [0.0, 0.0, 0.0]},
            "metadata": {"right_hand_tracked": True, "xr_frame_valid": True},
        },
    ]

    def fake_build_frame(**_kwargs):
        return json.loads(json.dumps(frames_to_return.pop(0)))

    monkeypatch.setattr(runtime_recorder, "build_frame", fake_build_frame)
    recorder = runtime_recorder.RdfIsaacRuntimeRecorder(
        api_base="http://127.0.0.1:8000",
        contributor_id="user_test",
        isaac_task_name="Isaac-Forge-PegInsert-Direct-v0",
    )
    recorder.task_id = "task_test"
    recorder.session_id = "session_test"
    recorder.episode_id = "episode_test"
    recorder.started_at_monotonic = 0.0
    recorder.episode_started_at = "2026-05-28T00:00:00+00:00"

    recorder.record(
        env=SimpleNamespace(),
        action=[0.0, 0.0, 0.0],
        teleoperation_active=False,
        teleop_interface=SimpleNamespace(),
        control_filter={
            "selected_teleop_control_mode": "raw_wrist_direct_ee_target",
            "tracking_gate_reason": "invalid_right_hand",
        },
    )
    recorder.record(
        env=SimpleNamespace(),
        action=[0.0, 0.0, 0.0],
        teleoperation_active=True,
        teleop_interface=SimpleNamespace(),
        control_filter={},
    )

    first_metadata = recorder.frames[0]["metadata"]
    second_metadata = recorder.frames[1]["metadata"]
    assert first_metadata["action_hold"] is True
    assert first_metadata["hold_reason"] == "invalid_right_hand"
    assert first_metadata["tracking_epoch_id"] == 0
    assert first_metadata["tracking_epoch_state"] == "invalid"
    assert second_metadata["action_hold"] is False
    assert second_metadata["hold_reason"] is None
    assert second_metadata["tracking_epoch_id"] == 1
    assert second_metadata["tracking_epoch_state"] == "valid"


def test_forge_direct_action_response_deadzone_resets_target_state() -> None:
    source = (ROOT / "scripts" / "check_forge_direct_action_response.py").read_text(
        encoding="utf-8"
    )
    deadzone_block = source.split("if tensor_norm(hand_delta_m) <", maxsplit=1)[
        1
    ].split(
        "self.target_pos = self.target_pos + hand_delta_m",
        maxsplit=1,
    )[0]

    assert "self.target_pos = current_pos.detach().clone()" in deadzone_block
    assert "self.previous_step = torch.zeros_like(self.previous_step)" in deadzone_block


def test_verify_latest_recording_passes_with_new_fields_and_paired_evaluation(
    tmp_path: Path,
) -> None:
    storage_root = tmp_path / "storage"
    write_json(storage_root / "trajectories" / "traj_latest.json", trajectory_payload())
    write_json(
        storage_root / "evaluations" / "eval_latest.json",
        {
            "id": "eval_latest",
            "trajectory_id": "traj_latest",
            "episode_id": "episode_latest",
            "success": True,
            "score": 0.9,
            "metrics": {"retargeting_jump_max": 0.01},
        },
    )

    report = verifier.verify_recording(storage_root)

    assert report["passed"] is True
    assert report["field_counts"]["raw_action"] == 3
    assert report["field_counts"]["applied_action"] == 3
    assert report["field_counts"]["control_filter"] == 3
    assert report["field_counts"]["workspace_alignment_v2"] == 3
    assert report["field_counts"]["end_effector_position"] == 3
    assert report["field_counts"]["object_position"] == 3
    assert report["action_dimensions"]["applied_action"] == [4]
    assert report["timestamp_summary"]["timestamp_monotonic"] is True
    assert report["timestamp_summary"]["timestamp_count"] == 3
    assert report["evaluation"]["pairing_source"] == "trajectory_id"


def test_verify_latest_recording_prefers_latest_non_empty_trajectory(
    tmp_path: Path,
) -> None:
    storage_root = tmp_path / "storage"
    good_path = storage_root / "trajectories" / "traj_good.json"
    empty_path = storage_root / "trajectories" / "traj_empty.json"
    write_json(good_path, trajectory_payload("good"))
    write_json(empty_path, empty_trajectory_payload("empty"))
    os.utime(good_path, (100.0, 100.0))
    os.utime(empty_path, (200.0, 200.0))

    report = verifier.verify_recording(storage_root)

    assert report["trajectory_id"] == "traj_good"
    assert report["frame_count"] == 3
    assert report["passed"] is True

    empty_report = verifier.verify_recording(storage_root, include_empty_latest=True)

    assert empty_report["trajectory_id"] == "traj_empty"
    assert empty_report["frame_count"] == 0
    assert empty_report["passed"] is False


def test_analyze_latest_prefers_latest_non_empty_trajectory(tmp_path: Path) -> None:
    storage_root = tmp_path / "storage"
    good_path = storage_root / "trajectories" / "traj_good.json"
    empty_path = storage_root / "trajectories" / "traj_empty.json"
    write_json(good_path, trajectory_payload("good"))
    write_json(empty_path, empty_trajectory_payload("empty"))
    os.utime(good_path, (100.0, 100.0))
    os.utime(empty_path, (200.0, 200.0))

    assert analyzer.latest_trajectory_path(storage_root) == good_path
    assert (
        analyzer.latest_trajectory_path(storage_root, include_empty=True) == empty_path
    )


def test_verify_latest_recording_flags_missing_new_filter_metadata(
    tmp_path: Path,
) -> None:
    storage_root = tmp_path / "storage"
    payload = trajectory_payload()
    for item in payload["frames"]:
        item["action"].pop("applied", None)
        item["action"].pop("control_filter", None)
        item["metadata"]["aligned_xr"].pop("control_filter", None)
        item["metadata"]["retargeted"].pop("control_filter", None)
        item["metadata"]["calibration"]["type"] = "translation_only"
    write_json(storage_root / "trajectories" / "traj_legacy.json", payload)

    report = verifier.verify_recording(storage_root)

    assert report["passed"] is False
    assert "control_filter metadata missing from frames" in report["issues"]
    assert "workspace_alignment_v2 metadata missing from frames" in report["issues"]


def test_runtime_env_preflight_passes_with_stubbed_environment(tmp_path: Path) -> None:
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    files = [
        repo / "pyproject.toml",
        home / "run_isaac_handtracking.sh",
        repo / "scripts/run_live_rdf_smoke_test.sh",
        home / "IsaacLab/_isaac_sim/python.sh",
        home / "IsaacLab/apps/isaaclab.python.xr.openxr.kit",
        home / "IsaacLab/scripts/environments/teleoperation/teleop_se3_agent.py",
        home
        / ".local/share/ALVR-Launcher/installations/v20.14.1/alvr_streamer_linux/bin/alvr_dashboard",
        home / ".steam/debian-installation/steamapps/common/SteamVR/bin/vrmonitor.sh",
        home / ".config/openxr/1/active_runtime.json",
        tmp_path / "nvidia_icd.json",
    ]
    for file_path in files:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text("# test\n", encoding="utf-8")
        file_path.chmod(0o755)

    (home / "run_isaac_handtracking.sh").write_text(
        "XR_RUNTIME_JSON=1 RDF_ACTION_FILTER=1 RDF_ACTION_POS_GAIN=1 "
        "RDF_ACTION_POS_AXIS_MAP=1 RDF_VISUAL_DEBUG=1 RDF_TELEOP_CONTROL_MODE=1 "
        "RDF_DIRECT_EE_POS_GAIN=1 RDF_DIRECT_EE_MAX_STEP_M=1 "
        "RDF_OPERATOR_FOLLOW_PRESET=1 RDF_CARTESIAN_DELTA_POS_GAIN=1 RDF_VISUAL_DEBUG_INPUT_SCALE=1 "
        "RDF_XR_ANCHOR_YAW_OFFSET_DEG=1 --rdf_record\n",
        encoding="utf-8",
    )
    (repo / "scripts/run_live_rdf_smoke_test.sh").write_text(
        "#!/usr/bin/env bash\ntrue\n", encoding="utf-8"
    )
    (home / "IsaacLab/apps/isaaclab.python.xr.openxr.kit").write_text(
        """
[dependencies]
"isaaclab.python" = {}
"omni.kit.xr.system.openxr" = {}
"omni.kit.xr.profile.ar" = {}
"omni.kit.xr.core" = {}
"omni.kit.xr.profile.common" = {}
"omni.kit.xr.ui.stage" = {}
"omni.kit.xr.scene_view.core" = {}
"omni.kit.xr.scene_view.utils" = {}
"omni.ui.scene" = {}

[settings]
app.xr.enabled = true
xr.openxr.components."omni.kit.xr.openxr.ext.hand_tracking".enabled = true
xr.openxr.components."isaacsim.xr.openxr.hand_tracking".enabled = true
""",
        encoding="utf-8",
    )
    (
        home / "IsaacLab/scripts/environments/teleoperation/teleop_se3_agent.py"
    ).write_text(
        "--rdf_record --rdf_action_pos_gain --rdf_visual_debug --rdf_teleop_control_mode "
        "--rdf_direct_ee_pos_gain RdfBoundedDirectEeTargetController bounded_direct_end_effector_target_servo "
        "--rdf_operator_follow_preset RdfOperatorFollowController operator_workspace_target_following "
        "enable_cartesian_delta_control factory_cartesian_delta_control --rdf_visual_debug_input_scale "
        "--rdf_xr_anchor_yaw_offset_deg RdfUsdVisualDebugMarkers compute_rdf_visual_targets "
        "start_rdf_terminal_hotkeys request_recenter_calibration RdfTeleopActionFilter\n",
        encoding="utf-8",
    )
    for extension_name in preflight.XR_LOCAL_EXTENSIONS:
        extension_dir = (
            home / "IsaacLab/_isaac_sim/extscache" / f"{extension_name}-1.0.0"
        )
        extension_dir.mkdir(parents=True, exist_ok=True)

    def command_exists(command: str) -> bool:
        return command in {"uv", "nvidia-smi", "bash"}

    def run_command(command: list[str], timeout: float) -> tuple[int, str, str]:
        if command[0] == "nvidia-smi":
            return 0, "NVIDIA GeForce RTX 4060 Ti, 570.211.01\n", ""
        if command[:2] == ["pgrep", "-f"]:
            return 0, "123\n", ""
        return 0, "", ""

    def url_probe(url: str, timeout: float) -> tuple[bool, str]:
        return True, '{"status":"ok"}'

    report = preflight.check_environment(
        repo_root=repo,
        home=home,
        env={"RDF_NVIDIA_ICD": str(tmp_path / "nvidia_icd.json")},
        command_exists=command_exists,
        run_command=run_command,
        url_probe=url_probe,
    )

    assert report["passed"] is True
    assert report["summary"]["fail"] == 0
    names = {check["name"] for check in report["checks"]}
    assert {
        "repo_root",
        "alvr_dashboard",
        "steamvr_vrmonitor",
        "isaac_xr_openxr_kit",
        "isaac_xr_kit_dependencies",
        "isaac_xr_kit_handtracking_settings",
        "isaac_xr_local_extensions",
        "openxr_runtime",
        "rdf_api_health",
        "live_runner_syntax",
        "live_smoke_runner_syntax",
        "teleop_rdf_hooks",
    } <= names


def test_mvp0_offline_diagnostics_bundle_combines_reports(monkeypatch) -> None:
    def fake_check_environment(**kwargs):
        return {
            "passed": True,
            "summary": {"pass": 3, "warn": 0, "fail": 0},
            "checks": [],
        }

    def fake_verify_recording(*args, **kwargs):
        return {
            "passed": True,
            "trajectory_path": "storage/trajectories/traj_latest.json",
            "trajectory_id": "traj_latest",
            "frame_count": 3,
            "issues": [],
            "warnings": [],
        }

    def fake_analyze_trajectory(path):
        return {
            "trajectory_id": "traj_latest",
            "frame_count": 3,
            "issues": [],
            "warnings": [],
            "recommendations": [
                "Run one short test with P recenter after hand tracking stabilizes."
            ],
        }

    monkeypatch.setattr(offline_bundle, "check_environment", fake_check_environment)
    monkeypatch.setattr(offline_bundle, "verify_recording", fake_verify_recording)
    monkeypatch.setattr(offline_bundle, "analyze_trajectory", fake_analyze_trajectory)

    report = offline_bundle.run_diagnostics(
        repo_root=Path("/repo"),
        home=Path("/home/kangrim"),
        storage_root=Path("storage"),
        api_base="http://127.0.0.1:8000",
        trajectory_path=Path("storage/trajectories/traj_latest.json"),
        allow_legacy=False,
        require_running_xr=False,
    )

    assert report["passed"] is True
    assert report["live_quest_isaac_required_for_codex_completion"] is False
    assert report["calibration_analysis"]["aggregate"]["issue_count"] == 0


def test_mvp0_offline_diagnostics_selects_latest_nonempty_trajectory(
    monkeypatch, tmp_path: Path
) -> None:
    storage_root = tmp_path / "storage"
    nonempty_path = storage_root / "trajectories" / "traj_nonempty.json"
    empty_path = storage_root / "trajectories" / "traj_empty.json"
    write_json(nonempty_path, trajectory_payload("nonempty"))
    empty_payload = trajectory_payload("empty")
    empty_payload["frames"] = []
    write_json(empty_path, empty_payload)
    empty_path.touch()

    write_json(
        storage_root / "evaluations" / "eval_nonempty.json",
        {
            "id": "eval_nonempty",
            "trajectory_id": "traj_nonempty",
            "episode_id": "episode_nonempty",
            "success": True,
            "score": 0.9,
            "metrics": {"retargeting_jump_max": 0.01},
        },
    )

    def fake_check_environment(**kwargs):
        return {
            "passed": True,
            "summary": {"pass": 3, "warn": 0, "fail": 0},
            "checks": [],
        }

    monkeypatch.setattr(offline_bundle, "check_environment", fake_check_environment)

    report = offline_bundle.run_diagnostics(
        repo_root=Path("/repo"),
        home=Path("/home/kangrim"),
        storage_root=storage_root,
        api_base="http://127.0.0.1:8000",
        trajectory_path=None,
        allow_legacy=False,
        require_running_xr=False,
    )

    assert report["passed"] is True
    assert report["trajectory_selection"]["mode"] == "latest_nonempty"
    assert report["trajectory_selection"]["path"] == str(nonempty_path)
    assert report["recording"]["trajectory_id"] == "traj_nonempty"


def test_operator_follow_config_uses_safe_defaults() -> None:
    args = forge_response.parse_args([])

    assert args.control_mode == "bounded_direct_ee_target"
    config = forge_response.operator_follow_config(args)

    assert config["preset"] == "safe"
    assert config["workspace_gain"] == 0.03
    assert config["max_step_m"] == 0.01
    assert config["smoothing_alpha"] == 0.35
    assert config["workspace_radius_m"] == 0.09


def test_operator_follow_config_allows_fast_override() -> None:
    args = forge_response.parse_args(
        [
            "--operator-follow-preset",
            "fast",
            "--operator-follow-max-step-m",
            "0.015",
        ]
    )

    config = forge_response.operator_follow_config(args)

    assert config["preset"] == "fast"
    assert config["workspace_gain"] == 0.06
    assert config["max_step_m"] == 0.015
    assert config["smoothing_alpha"] == 0.70


def test_operator_follow_config_supports_responsive_preset() -> None:
    args = forge_response.parse_args(["--operator-follow-preset", "responsive"])

    config = forge_response.operator_follow_config(args)

    assert config["preset"] == "responsive"
    assert config["workspace_gain"] == 0.12
    assert config["max_step_m"] == 0.04
    assert config["smoothing_alpha"] == 0.90
    assert config["workspace_radius_m"] == 0.25


def test_bounded_direct_ee_config_uses_mvp1_defaults() -> None:
    args = forge_response.parse_args([])

    config = forge_response.bounded_direct_ee_config(args)

    assert config["preset"] == "bounded_direct_ee_target"
    assert config["position_gain"] == 0.18
    assert config["rotation_gain"] == 0.25
    assert config["max_step_m"] == 0.06
    assert config["smoothing_alpha"] == 0.95
    assert config["workspace_radius_m"] == 0.35
    assert config["control_semantics"] == "bounded_direct_end_effector_target_servo"


def test_raw_wrist_direct_ee_config_has_explicit_mode_and_thresholds() -> None:
    args = forge_response.parse_args(["--control-mode", "raw_wrist_direct_ee_target"])

    config = forge_response.raw_wrist_direct_ee_config(args)

    assert args.control_mode == "raw_wrist_direct_ee_target"
    assert config["preset"] == "raw_wrist_direct_ee_target"
    assert config["input_source"] == "raw_right_wrist_pose"
    assert config["position_axis_map"] == "x,z,y"
    assert config["raw_wrist_jump_warn_m"] == 0.10
    assert config["raw_wrist_jump_reject_m"] == 0.15
    assert (
        config["control_semantics"]
        == "raw_wrist_bounded_direct_end_effector_target_servo"
    )


def test_raw_wrist_direct_ee_config_has_reacquire_window_defaults() -> None:
    args = forge_response.parse_args(["--control-mode", "raw_wrist_direct_ee_target"])

    config = forge_response.raw_wrist_direct_ee_config(args)

    assert config["raw_wrist_reacquire_valid_frames"] == 3
    assert config["raw_wrist_reacquire_stable_m"] == 0.03


def test_live_teleop_exposes_raw_wrist_spike_reacquire_policy() -> None:
    source = Path(
        "/home/kangrim/IsaacLab/scripts/environments/teleoperation/teleop_se3_agent.py"
    ).read_text(encoding="utf-8")

    assert "rdf_raw_wrist_reacquire_valid_frames" in source
    assert "raw_wrist_spike_reacquire_pending" in source
    assert "raw_wrist_reacquire_valid_count" in source


def test_bounded_direct_ee_smoke_target_is_absolute_hand_offset_not_incremental_velocity() -> (
    None
):
    source = (ROOT / "scripts" / "check_forge_direct_action_response.py").read_text(
        encoding="utf-8"
    )

    assert "self.target_pos = self.target_pos + hand_delta_m" not in source
    assert "self.target_pos = self.anchor_pos + hand_delta_m" in source


def test_bounded_direct_ee_smoke_deadzone_keeps_current_target_not_anchor_zero() -> (
    None
):
    source = (ROOT / "scripts" / "check_forge_direct_action_response.py").read_text(
        encoding="utf-8"
    )
    deadzone_body = source.split("if tensor_norm(hand_delta_m) <", maxsplit=1)[1].split(
        "else:", maxsplit=1
    )[0]
    active_body = source.split("if tensor_norm(hand_delta_m) <", maxsplit=1)[1].split(
        "else:", maxsplit=1
    )[1]

    assert "self.target_pos = current_pos.detach().clone()" in deadzone_body
    assert "self.anchor_pos = current_pos.detach().clone()" in deadzone_body
    assert "self.previous_step = torch.zeros_like(self.previous_step)" in deadzone_body
    assert "self.target_pos = self.anchor_pos + hand_delta_m" not in deadzone_body
    assert "self.target_pos = self.anchor_pos + hand_delta_m" in active_body


def test_bounded_direct_ee_smoke_deadzone_rebases_anchor_for_continuous_exit() -> None:
    torch = pytest.importorskip("torch")

    env = SimpleNamespace(
        action_space=SimpleNamespace(shape=(7,)),
        device=torch.device("cpu"),
        fingertip_midpoint_pos=torch.tensor([[1.0, 2.0, 3.0]], dtype=torch.float32),
        pos_threshold=torch.ones((1, 3), dtype=torch.float32),
    )
    controller = forge_response.OperatorFollowSmoke(
        env,
        {
            "preset": "bounded_direct_ee_target",
            "workspace_gain": 1.0,
            "deadzone_m": 0.01,
            "workspace_radius_m": 1.0,
            "max_step_m": 1.0,
            "smoothing_alpha": 1.0,
        },
    )
    env.fingertip_midpoint_pos = torch.tensor([[1.1, 2.0, 3.0]], dtype=torch.float32)

    controller.build_action(env, [0.0, 0.0, 0.0])
    action = controller.build_action(env, [0.02, 0.0, 0.0])

    assert action[0, 0].item() > 0.0
    assert action[0, 0].item() == pytest.approx(0.02, abs=1.0e-5)


def test_raw_wrist_direct_smoke_maps_wrist_pose_from_raw_origin() -> None:
    torch = pytest.importorskip("torch")

    env = SimpleNamespace(
        action_space=SimpleNamespace(shape=(7,)),
        device=torch.device("cpu"),
        fingertip_midpoint_pos=torch.tensor([[1.0, 2.0, 3.0]], dtype=torch.float32),
        pos_threshold=torch.ones((1, 3), dtype=torch.float32),
    )
    controller = forge_response.RawWristDirectSmoke(
        env,
        {
            "preset": "raw_wrist_direct_ee_target",
            "workspace_gain": 1.0,
            "deadzone_m": 0.001,
            "workspace_radius_m": 1.0,
            "max_step_m": 1.0,
            "smoothing_alpha": 1.0,
            "position_axis_map": "x,y,z",
            "position_yaw_offset_deg": 0.0,
            "raw_wrist_jump_warn_m": 0.10,
            "raw_wrist_jump_reject_m": 0.15,
        },
        raw_wrist_origin_pose=[0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0],
    )

    action = controller.build_action_from_wrist_pose(
        env, [0.02, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0]
    )

    assert action[0, 0].item() == pytest.approx(0.02, abs=1.0e-5)
    assert controller.last_metadata["raw_wrist_direct_control"][
        "wrist_offset_raw"
    ] == pytest.approx([0.02, 0.0, 0.0])
    assert controller.last_metadata["raw_wrist_direct_control"][
        "wrist_offset_robot"
    ] == pytest.approx([0.02, 0.0, 0.0])
    assert (
        controller.last_metadata["raw_wrist_direct_control"]["gate_state"] == "accepted"
    )


def test_raw_wrist_direct_smoke_rejects_large_valid_to_valid_jump() -> None:
    torch = pytest.importorskip("torch")

    env = SimpleNamespace(
        action_space=SimpleNamespace(shape=(7,)),
        device=torch.device("cpu"),
        fingertip_midpoint_pos=torch.tensor([[1.0, 2.0, 3.0]], dtype=torch.float32),
        pos_threshold=torch.ones((1, 3), dtype=torch.float32),
    )
    controller = forge_response.RawWristDirectSmoke(
        env,
        {
            "preset": "raw_wrist_direct_ee_target",
            "workspace_gain": 1.0,
            "deadzone_m": 0.001,
            "workspace_radius_m": 1.0,
            "max_step_m": 1.0,
            "smoothing_alpha": 1.0,
            "position_axis_map": "x,y,z",
            "position_yaw_offset_deg": 0.0,
            "raw_wrist_jump_warn_m": 0.10,
            "raw_wrist_jump_reject_m": 0.15,
            "raw_wrist_reacquire_valid_frames": 2,
            "raw_wrist_reacquire_stable_m": 0.03,
        },
        raw_wrist_origin_pose=[0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0],
    )
    controller.build_action_from_wrist_pose(env, [0.02, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0])

    action = controller.build_action_from_wrist_pose(
        env, [0.30, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0]
    )

    assert action[0, 0].item() == pytest.approx(0.0, abs=1.0e-6)
    assert controller.last_metadata["raw_wrist_direct_control"]["gate_state"] == "held"
    assert (
        controller.last_metadata["raw_wrist_direct_control"]["gate_reason"]
        == "raw_wrist_spike_reacquire_pending"
    )
    assert controller.last_metadata["raw_wrist_direct_control"][
        "valid_to_valid_jump_m"
    ] == pytest.approx(0.28)


def test_raw_wrist_direct_smoke_debounces_single_frame_valid_to_valid_spike_without_rebasing() -> (
    None
):
    torch = pytest.importorskip("torch")

    env = SimpleNamespace(
        action_space=SimpleNamespace(shape=(7,)),
        device=torch.device("cpu"),
        fingertip_midpoint_pos=torch.tensor([[1.0, 2.0, 3.0]], dtype=torch.float32),
        pos_threshold=torch.ones((1, 3), dtype=torch.float32),
    )
    controller = forge_response.RawWristDirectSmoke(
        env,
        {
            "preset": "raw_wrist_direct_ee_target",
            "workspace_gain": 1.0,
            "deadzone_m": 0.001,
            "workspace_radius_m": 1.0,
            "max_step_m": 1.0,
            "smoothing_alpha": 1.0,
            "position_axis_map": "x,y,z",
            "position_yaw_offset_deg": 0.0,
            "raw_wrist_jump_warn_m": 0.10,
            "raw_wrist_jump_reject_m": 0.15,
            "raw_wrist_reacquire_valid_frames": 2,
            "raw_wrist_reacquire_stable_m": 0.03,
        },
        raw_wrist_origin_pose=[0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0],
    )
    controller.build_action_from_wrist_pose(env, [0.02, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0])

    spike_action = controller.build_action_from_wrist_pose(
        env, [0.30, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0]
    )
    returned_action = controller.build_action_from_wrist_pose(
        env, [0.03, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0]
    )

    assert spike_action[0, 0].item() == pytest.approx(0.0, abs=1.0e-6)
    assert (
        controller.last_metadata["raw_wrist_direct_control"]["gate_state"] == "accepted"
    )
    assert controller.last_metadata["raw_wrist_direct_control"]["gate_reason"] is None
    assert controller.last_metadata["raw_wrist_direct_control"][
        "raw_wrist_origin_pose"
    ] == pytest.approx([0.0, 0.0, 0.0])
    assert controller.last_metadata["raw_wrist_direct_control"][
        "wrist_offset_raw"
    ] == pytest.approx([0.03, 0.0, 0.0])
    assert returned_action[0, 0].item() > 0.0


def test_raw_wrist_direct_smoke_rebases_after_stable_spike_reacquire_window() -> None:
    torch = pytest.importorskip("torch")

    env = SimpleNamespace(
        action_space=SimpleNamespace(shape=(7,)),
        device=torch.device("cpu"),
        fingertip_midpoint_pos=torch.tensor([[1.0, 2.0, 3.0]], dtype=torch.float32),
        pos_threshold=torch.ones((1, 3), dtype=torch.float32),
    )
    controller = forge_response.RawWristDirectSmoke(
        env,
        {
            "preset": "raw_wrist_direct_ee_target",
            "workspace_gain": 1.0,
            "deadzone_m": 0.001,
            "workspace_radius_m": 1.0,
            "max_step_m": 1.0,
            "smoothing_alpha": 1.0,
            "position_axis_map": "x,y,z",
            "position_yaw_offset_deg": 0.0,
            "raw_wrist_jump_warn_m": 0.10,
            "raw_wrist_jump_reject_m": 0.15,
            "raw_wrist_reacquire_valid_frames": 2,
            "raw_wrist_reacquire_stable_m": 0.03,
        },
        raw_wrist_origin_pose=[0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0],
    )
    controller.build_action_from_wrist_pose(env, [0.02, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0])
    controller.build_action_from_wrist_pose(env, [0.30, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0])

    reacquired_action = controller.build_action_from_wrist_pose(
        env, [0.305, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0]
    )
    next_action = controller.build_action_from_wrist_pose(
        env, [0.315, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0]
    )

    assert reacquired_action[0, 0].item() == pytest.approx(0.0, abs=1.0e-6)
    assert (
        controller.last_metadata["raw_wrist_direct_control"]["gate_state"] == "accepted"
    )
    assert controller.last_metadata["raw_wrist_direct_control"][
        "raw_wrist_origin_pose"
    ] == pytest.approx([0.305, 0.0, 0.0])
    assert controller.last_metadata["raw_wrist_direct_control"][
        "wrist_offset_raw"
    ] == pytest.approx([0.01, 0.0, 0.0])
    assert next_action[0, 0].item() > 0.0


def test_bounded_direct_ee_smoke_tracking_resume_rebases_current_pose_before_next_valid_delta() -> (
    None
):
    torch = pytest.importorskip("torch")

    env = SimpleNamespace(
        action_space=SimpleNamespace(shape=(7,)),
        device=torch.device("cpu"),
        fingertip_midpoint_pos=torch.tensor([[1.0, 2.0, 3.0]], dtype=torch.float32),
        pos_threshold=torch.ones((1, 3), dtype=torch.float32),
    )
    controller = forge_response.OperatorFollowSmoke(
        env,
        {
            "preset": "bounded_direct_ee_target",
            "workspace_gain": 1.0,
            "deadzone_m": 0.01,
            "workspace_radius_m": 1.0,
            "max_step_m": 1.0,
            "smoothing_alpha": 1.0,
        },
    )
    controller.build_action(env, [0.20, 0.0, 0.0])

    env.fingertip_midpoint_pos = torch.tensor([[1.05, 2.0, 3.0]], dtype=torch.float32)
    controller.hold_current_pose(env)
    action = controller.build_action(env, [0.02, 0.0, 0.0])

    assert action[0, 0].item() > 0.0
    assert action[0, 0].item() == pytest.approx(0.02, abs=1.0e-5)


def test_runtime_recorder_action_payload_records_raw_wrist_direct_contract() -> None:
    payload = runtime_recorder._action_payload(
        [0.02, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0],
        True,
        raw_action=[9.0, 8.0, 7.0, 0.0, 0.0, 0.0, -1.0],
        control_filter={
            "teleop_control_mode": {
                "name": "raw_wrist_direct_ee_target",
                "control_semantics": "raw_wrist_bounded_direct_end_effector_target_servo",
                "raw_wrist_direct_control": {
                    "input_source": "raw_right_wrist_pose",
                    "gate_state": "accepted",
                    "wrist_offset_raw": [0.10, 0.0, 0.0],
                    "wrist_offset_robot": [0.10, 0.0, 0.0],
                },
                "applied_end_effector_action": {"delta_position": [0.02, 0.0, 0.0]},
                "native_isaac_action": [0.02, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0],
            }
        },
    )

    assert payload["raw_wrist_direct"]["input_source"] == "raw_right_wrist_pose"
    assert payload["raw_wrist_direct"]["wrist_offset_raw"] == [0.10, 0.0, 0.0]
    assert payload["executed_control"]["control_mode"] == "raw_wrist_direct_ee_target"
    assert (
        payload["learning_action"]["representation"]
        == "desired_applied_end_effector_action"
    )
    assert payload["learning_action"]["command"] == [0.02, 0.0, 0.0]
    assert payload["learning_action"]["eligible"] is True
    assert payload["learning_action"]["ineligible_reason"] is None
    assert payload["retargeted_robot_action"]["command"] == [
        9.0,
        8.0,
        7.0,
        0.0,
        0.0,
        0.0,
        -1.0,
    ]
    assert payload["retargeted_robot_action"]["applied_to_env"] is False


def test_runtime_recorder_action_payload_preserves_raw_wrist_contract_when_tracking_gate_holds_control() -> (
    None
):
    payload = runtime_recorder._action_payload(
        [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        False,
        raw_action=[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        control_filter={
            "selected_teleop_control_mode": "raw_wrist_direct_ee_target",
            "tracking_gate_reason": "invalid_right_hand",
            "right_wrist_pose": [-0.1, -0.5, -1.05],
            "right_wrist_anchor_fallback": True,
            "tracking_resume_progress": {"valid": 0, "required": 3},
            "config": {
                "position_axis_map": "x,z,y",
                "position_yaw_offset_deg": 0.0,
            },
        },
    )

    assert payload["executed_control"]["control_mode"] == "raw_wrist_direct_ee_target"
    assert (
        payload["executed_control"]["control_semantics"]
        == "raw_wrist_bounded_direct_end_effector_target_servo"
    )
    assert payload["executed_control"]["applied_to_env"] is False
    assert (
        payload["learning_action"]["representation"]
        == "desired_applied_end_effector_action"
    )
    assert payload["learning_action"]["command"] == [0.0, 0.0, 0.0]
    assert payload["learning_action"]["eligible"] is False
    assert payload["learning_action"]["ineligible_reason"] == "invalid_right_hand"
    assert payload["raw_wrist_direct"]["gate_state"] == "held"
    assert payload["raw_wrist_direct"]["gate_reason"] == "invalid_right_hand"
    assert payload["raw_wrist_direct"]["raw_wrist_pose"] == [-0.1, -0.5, -1.05]
    assert payload["raw_wrist_direct"]["right_wrist_anchor_fallback"] is True
    classification = payload["input_signal_state"]["input_truth_classification"]
    assert classification["truth_state"] == "invalid"
    assert classification["primary_reason"] == "ANCHOR_FALLBACK_POSE"
    assert classification["action_hold_required"] is True
    assert classification["resume_block"] is True
    assert classification["recenter_block"] is True
    assert classification["allow_authority"] is False
    truth_control = payload["input_signal_state"]["input_truth_control_state"]
    assert truth_control["action_hold"] is True
    assert truth_control["resume_block"] is True
    assert truth_control["recenter_block"] is True
    assert truth_control["allow_authority"] is False
    assert "resume_allowed" not in truth_control
    assert "recenter_allowed" not in truth_control
    assert payload["retargeted_robot_action"]["applied_to_env"] is False
    assert payload["retargeted_robot_action"]["used_for_comparison"] is True


def test_runtime_recorder_action_payload_preserves_input_signal_state() -> None:
    signal_state = {
        "schema_version": "rdf_input_signal_state_v0.1.0",
        "sample_valid": True,
        "tracking_valid": True,
        "control_safe": True,
        "learning_label_eligible": True,
    }
    payload = runtime_recorder._action_payload(
        [0.01, 0.0, 0.0, 0.0],
        True,
        raw_action=[0.01, 0.0, 0.0, 0.0],
        control_filter={
            "teleop_control_mode": {
                "name": "raw_wrist_direct_ee_target",
                "raw_wrist_direct_control": {
                    "gate_state": "accepted",
                    "input_signal_state": signal_state,
                },
                "applied_end_effector_action": {"delta_position": [0.01, 0.0, 0.0]},
            }
        },
    )

    assert payload["input_signal_state"] == signal_state
    assert payload["learning_action"]["eligible"] is True


def test_runtime_recorder_builds_sim_step_boundary_metadata_from_env_step_tuple() -> (
    None
):
    metadata = runtime_recorder._env_step_boundary_metadata(
        (
            {"obs": "ignored"},
            [0.0],
            [True],
            [False],
            {"final_observation": {"episode": 1}},
        )
    )

    assert metadata["schema_version"] == "rdf_sim_step_boundary_v0.1.0"
    assert metadata["source"] == "isaac_env_step_return"
    assert metadata["env_step_return_available"] is True
    assert metadata["terminated"]["any"] is True
    assert metadata["truncated"]["any"] is False
    assert metadata["done"]["any"] is True
    assert metadata["reset_boundary"] is True
    assert metadata["reset_boundary_reason"] == "terminated"
    assert "final_observation" in metadata["info_keys"]


def test_live_teleop_tracks_raw_wrist_mode_metadata_while_tracking_gate_holds_control() -> (
    None
):
    teleop_path = Path(
        "/home/kangrim/IsaacLab/scripts/environments/teleoperation/teleop_se3_agent.py"
    )
    if not teleop_path.exists():
        pytest.skip("IsaacLab teleop_se3_agent.py is not installed in this environment")

    source = teleop_path.read_text(encoding="utf-8")

    assert '"selected_teleop_control_mode": teleop_control_mode' in source
    assert '"tracking_gate_reason": tracking_gate_reason' in source
    assert '"tracking_resume_progress"' in source
    assert "raw_wrist_gate_state" in source
    assert "def rdf_input_signal_state_from_pose" in source
    assert '"input_signal_state": rdf_input_signal_state_from_pose' in source
    assert '"control_safe"' in source
    assert '"learning_label_eligible"' in source


def test_live_teleop_passes_env_step_result_to_runtime_recorder() -> None:
    teleop_path = Path(
        "/home/kangrim/IsaacLab/scripts/environments/teleoperation/teleop_se3_agent.py"
    )
    if not teleop_path.exists():
        pytest.skip("IsaacLab teleop_se3_agent.py is not installed in this environment")

    source = teleop_path.read_text(encoding="utf-8")

    assert "env_step_result = env.step(actions)" in source
    assert "env_step_result=env_step_result" in source


def raw_wrist_motion_frame(
    index: int,
    *,
    hand_delta: list[float],
    target: list[float],
    current: list[float],
    origin: list[float] | None = None,
    gate_state: str = "accepted",
    gate_reason: str | None = None,
    object_position: list[float] | None = None,
    hole_target: list[float] | None = None,
    raw_wrist_pose: list[float] | None = None,
    aligned_wrist_pose: list[float] | None = None,
    applied_command: list[float] | None = None,
) -> dict[str, Any]:
    origin = origin or [0.0, 0.0, 0.0]
    object_position = object_position or [0.5, 0.0, 0.1]
    hole_target = hole_target or [0.6, 0.0, 0.1]
    raw_wrist_pose = raw_wrist_pose or hand_delta
    aligned_wrist_pose = aligned_wrist_pose or raw_wrist_pose
    applied_command = applied_command or [0.0, 0.0, 0.0]
    raw_wrist_direct = {
        "gate_state": gate_state,
        "gate_reason": gate_reason,
        "raw_wrist_origin_pose": origin,
        "wrist_offset_robot": hand_delta,
        "valid_to_valid_jump_m": 0.0,
    }
    return {
        "t": index / 15.0,
        "step": index,
        "end_effector_position": current,
        "object_position": object_position,
        "action": {
            "raw": [0.0, 0.0, 0.0, 0.0],
            "applied": [0.0, 0.0, 0.0, 0.0],
            "control_filter": {
                "enabled": True,
                "config": {"position_gain": 0.4, "position_axis_map": "x,z,y"},
                "teleop_control_mode": {
                    "name": "raw_wrist_direct_ee_target",
                    "control_semantics": "raw_wrist_bounded_direct_end_effector_target_servo",
                    "position_gain": 1.0,
                    "max_step_m": 0.04,
                    "smoothing_alpha": 0.5,
                    "deadzone_m": 0.003,
                    "workspace_radius_m": 0.35,
                    "input_delta_xyz": hand_delta,
                    "hand_delta_m": hand_delta,
                    "desired_ee_target_xyz": target,
                    "applied_ee_delta_m": applied_command,
                    "actual_ee_xyz": current,
                    "target_error_norm": 0.0,
                    "workspace_clamped": False,
                    "raw_wrist_direct_control": raw_wrist_direct,
                },
            },
            "raw_wrist_direct": raw_wrist_direct,
        },
        "metadata": {
            "right_hand_tracked": True,
            "xr_frame_valid": True,
            "raw_xr": {
                "right_wrist_pose": [
                    raw_wrist_pose[0],
                    raw_wrist_pose[1],
                    raw_wrist_pose[2],
                    1.0,
                    0.0,
                    0.0,
                    0.0,
                ]
            },
            "aligned_xr": {
                "right_wrist_pose": [
                    aligned_wrist_pose[0],
                    aligned_wrist_pose[1],
                    aligned_wrist_pose[2],
                    1.0,
                    0.0,
                    0.0,
                    0.0,
                ]
            },
            "task_state": {
                "peg_position": object_position,
                "hole_target_position": hole_target,
                "hole_position": [
                    hole_target[0],
                    hole_target[1],
                    hole_target[2] - 0.025,
                ],
                "action_phase": "APPROACH",
            },
        },
    }


def raw_wrist_trajectory_payload(frames: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "id": "traj_raw_wrist",
        "episode_id": "episode_raw_wrist",
        "task_id": "task_raw_wrist",
        "schema_version": "0.1.0",
        "source": {
            "input_device": "quest3_handtracking",
            "runtime": "steamvr_openxr",
            "simulator": "isaac_lab",
            "robot": "franka",
            "task_name": "Isaac-Forge-PegInsert-Direct-v0",
        },
        "frames": frames,
        "summary": {"episode_status": "incomplete"},
    }


def test_motion_mapping_reports_target_accumulation_when_target_exceeds_current_hand_delta(
    tmp_path: Path,
) -> None:
    path = tmp_path / "traj_accumulation.json"
    write_json(
        path,
        raw_wrist_trajectory_payload(
            [
                raw_wrist_motion_frame(
                    0,
                    hand_delta=[0.0, 0.0, 0.0],
                    target=[1.0, 0.0, 0.0],
                    current=[1.0, 0.0, 0.0],
                ),
                raw_wrist_motion_frame(
                    1,
                    hand_delta=[0.01, 0.0, 0.0],
                    target=[1.01, 0.0, 0.0],
                    current=[1.0, 0.0, 0.0],
                ),
                raw_wrist_motion_frame(
                    2,
                    hand_delta=[0.02, 0.0, 0.0],
                    target=[1.08, 0.0, 0.0],
                    current=[1.0, 0.0, 0.0],
                ),
            ]
        ),
    )

    report = motion_mapping.analyze_trajectory(path)
    accumulation = report["target_accumulation"]

    assert accumulation["max_anchor_est_residual_m"] > 0.02
    assert any(
        item["id"] == "H14" and item["status"] == "WARN"
        for item in report["hypotheses"]
    )


def test_motion_mapping_reports_scene_state_discontinuity(tmp_path: Path) -> None:
    path = tmp_path / "traj_scene_jump.json"
    write_json(
        path,
        raw_wrist_trajectory_payload(
            [
                raw_wrist_motion_frame(
                    0,
                    hand_delta=[0.0, 0.0, 0.0],
                    target=[1.0, 0.0, 0.0],
                    current=[1.0, 0.0, 0.0],
                ),
                raw_wrist_motion_frame(
                    1,
                    hand_delta=[0.01, 0.0, 0.0],
                    target=[1.01, 0.0, 0.0],
                    current=[1.01, 0.0, 0.0],
                ),
                raw_wrist_motion_frame(
                    2,
                    hand_delta=[0.02, 0.0, 0.0],
                    target=[1.02, 0.0, 0.0],
                    current=[1.30, 0.20, 0.0],
                    object_position=[1.30, 0.20, 0.0],
                    hole_target=[1.35, 0.20, 0.0],
                ),
            ]
        ),
    )

    report = motion_mapping.analyze_trajectory(path)
    scene = report["scene_state_discontinuity"]

    assert scene["event_count"] >= 3
    assert scene["frames"] == [2]
    assert any(
        item["id"] == "H15" and item["status"] == "WARN"
        for item in report["hypotheses"]
    )


def test_motion_mapping_provenance_timeline_classifies_raw_wrist_first_jump(
    tmp_path: Path,
) -> None:
    path = tmp_path / "traj_raw_first.json"
    write_json(
        path,
        raw_wrist_trajectory_payload(
            [
                raw_wrist_motion_frame(
                    0,
                    hand_delta=[0.0, 0.0, 0.0],
                    target=[1.0, 0.0, 0.0],
                    current=[1.0, 0.0, 0.0],
                    raw_wrist_pose=[0.0, 0.0, 0.0],
                    aligned_wrist_pose=[0.0, 0.0, 0.0],
                ),
                raw_wrist_motion_frame(
                    1,
                    hand_delta=[0.0, 0.0, 0.0],
                    target=[1.0, 0.0, 0.0],
                    current=[1.0, 0.0, 0.0],
                    raw_wrist_pose=[0.25, 0.0, 0.0],
                    aligned_wrist_pose=[0.0, 0.0, 0.0],
                ),
            ]
        ),
    )

    report = motion_mapping.analyze_trajectory(path)
    event = report["provenance_timeline"]["events"][0]

    assert event["first_discontinuity_stage"] == "raw_wrist"
    assert report["provenance_timeline"]["first_stage_counts"] == {"raw_wrist": 1}


def test_motion_mapping_provenance_timeline_classifies_aligned_wrist_first_jump(
    tmp_path: Path,
) -> None:
    path = tmp_path / "traj_aligned_first.json"
    write_json(
        path,
        raw_wrist_trajectory_payload(
            [
                raw_wrist_motion_frame(
                    0,
                    hand_delta=[0.0, 0.0, 0.0],
                    target=[1.0, 0.0, 0.0],
                    current=[1.0, 0.0, 0.0],
                    raw_wrist_pose=[0.0, 0.0, 0.0],
                    aligned_wrist_pose=[0.0, 0.0, 0.0],
                ),
                raw_wrist_motion_frame(
                    1,
                    hand_delta=[0.0, 0.0, 0.0],
                    target=[1.0, 0.0, 0.0],
                    current=[1.0, 0.0, 0.0],
                    raw_wrist_pose=[0.0, 0.0, 0.0],
                    aligned_wrist_pose=[0.20, 0.0, 0.0],
                ),
            ]
        ),
    )

    report = motion_mapping.analyze_trajectory(path)
    event = report["provenance_timeline"]["events"][0]

    assert event["first_discontinuity_stage"] == "aligned_wrist"
    assert report["provenance_timeline"]["first_stage_counts"] == {"aligned_wrist": 1}


def test_motion_mapping_provenance_timeline_classifies_target_first_jump(
    tmp_path: Path,
) -> None:
    path = tmp_path / "traj_target_first.json"
    write_json(
        path,
        raw_wrist_trajectory_payload(
            [
                raw_wrist_motion_frame(
                    0,
                    hand_delta=[0.0, 0.0, 0.0],
                    target=[1.0, 0.0, 0.0],
                    current=[1.0, 0.0, 0.0],
                    raw_wrist_pose=[0.0, 0.0, 0.0],
                    aligned_wrist_pose=[0.0, 0.0, 0.0],
                ),
                raw_wrist_motion_frame(
                    1,
                    hand_delta=[0.0, 0.0, 0.0],
                    target=[1.08, 0.0, 0.0],
                    current=[1.0, 0.0, 0.0],
                    raw_wrist_pose=[0.0, 0.0, 0.0],
                    aligned_wrist_pose=[0.0, 0.0, 0.0],
                ),
            ]
        ),
    )

    report = motion_mapping.analyze_trajectory(path)
    event = report["provenance_timeline"]["events"][0]

    assert event["first_discontinuity_stage"] == "desired_target"
    assert report["provenance_timeline"]["first_stage_counts"] == {"desired_target": 1}


def test_motion_mapping_provenance_timeline_classifies_eef_first_jump(
    tmp_path: Path,
) -> None:
    path = tmp_path / "traj_eef_first.json"
    write_json(
        path,
        raw_wrist_trajectory_payload(
            [
                raw_wrist_motion_frame(
                    0,
                    hand_delta=[0.0, 0.0, 0.0],
                    target=[1.0, 0.0, 0.0],
                    current=[1.0, 0.0, 0.0],
                    raw_wrist_pose=[0.0, 0.0, 0.0],
                    aligned_wrist_pose=[0.0, 0.0, 0.0],
                ),
                raw_wrist_motion_frame(
                    1,
                    hand_delta=[0.0, 0.0, 0.0],
                    target=[1.0, 0.0, 0.0],
                    current=[1.12, 0.0, 0.0],
                    raw_wrist_pose=[0.0, 0.0, 0.0],
                    aligned_wrist_pose=[0.0, 0.0, 0.0],
                ),
            ]
        ),
    )

    report = motion_mapping.analyze_trajectory(path)
    event = report["provenance_timeline"]["events"][0]

    assert event["first_discontinuity_stage"] == "actual_eef"
    assert report["provenance_timeline"]["first_stage_counts"] == {"actual_eef": 1}
