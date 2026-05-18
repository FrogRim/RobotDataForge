from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import sys
from typing import Any


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
verifier = load_script("verify_latest_rdf_recording")
preflight = load_script("check_rdf_runtime_env")
offline_bundle = load_script("run_mvp0_offline_diagnostics")
forge_response = load_script("check_forge_direct_action_response")


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


def test_analyze_teleop_calibration_reports_filter_and_action_stats(tmp_path: Path) -> None:
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


def test_verify_latest_recording_passes_with_new_fields_and_paired_evaluation(tmp_path: Path) -> None:
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


def test_verify_latest_recording_prefers_latest_non_empty_trajectory(tmp_path: Path) -> None:
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
    assert analyzer.latest_trajectory_path(storage_root, include_empty=True) == empty_path


def test_verify_latest_recording_flags_missing_new_filter_metadata(tmp_path: Path) -> None:
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
        home / ".local/share/ALVR-Launcher/installations/v20.14.1/alvr_streamer_linux/bin/alvr_dashboard",
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
    (repo / "scripts/run_live_rdf_smoke_test.sh").write_text("#!/usr/bin/env bash\ntrue\n", encoding="utf-8")
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
    (home / "IsaacLab/scripts/environments/teleoperation/teleop_se3_agent.py").write_text(
        "--rdf_record --rdf_action_pos_gain --rdf_visual_debug --rdf_teleop_control_mode "
        "--rdf_direct_ee_pos_gain RdfBoundedDirectEeTargetController bounded_direct_end_effector_target_servo "
        "--rdf_operator_follow_preset RdfOperatorFollowController operator_workspace_target_following "
        "enable_cartesian_delta_control factory_cartesian_delta_control --rdf_visual_debug_input_scale "
        "--rdf_xr_anchor_yaw_offset_deg RdfUsdVisualDebugMarkers compute_rdf_visual_targets "
        "start_rdf_terminal_hotkeys request_recenter_calibration RdfTeleopActionFilter\n",
        encoding="utf-8",
    )
    for extension_name in preflight.XR_LOCAL_EXTENSIONS:
        extension_dir = home / "IsaacLab/_isaac_sim/extscache" / f"{extension_name}-1.0.0"
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
        return {"passed": True, "summary": {"pass": 3, "warn": 0, "fail": 0}, "checks": []}

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
            "recommendations": ["Run one short test with P recenter after hand tracking stabilizes."],
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


def test_mvp0_offline_diagnostics_selects_latest_nonempty_trajectory(monkeypatch, tmp_path: Path) -> None:
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
        return {"passed": True, "summary": {"pass": 3, "warn": 0, "fail": 0}, "checks": []}

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
