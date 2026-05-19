from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[3]


def load_script(name: str):
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


diag = load_script("run_mvp2_curation_diagnostic")


def make_frame(
    phase: str,
    native_action: list[float] | None = None,
    delta_m: list[float] | None = None,
    workspace_clamped: bool = False,
) -> dict:
    return {
        "metadata": {"action_phase": phase},
        "action": {
            "native_isaac_action": native_action
            if native_action is not None
            else [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            "control_filter": {
                "teleop_control_mode": {
                    "applied_ee_delta_m": delta_m
                    if delta_m is not None
                    else [0.0, 0.0, 0.0],
                    "workspace_clamped": workspace_clamped,
                }
            },
        },
    }


def _cfg() -> dict:
    return {
        "insert_min_frames": 20,
        "seat_min_frames": 8,
        "approach_min_frames": 10,
        "action_sat_value_threshold": 0.999,
        "max_native_action_sat_ratio": 0.05,
    }


def test_read_phase_primary_metadata() -> None:
    frame = {"metadata": {"action_phase": "INSERT"}, "action": {}}
    assert diag.read_phase(frame) == ("INSERT", "metadata")


def test_read_phase_fallback_task_state() -> None:
    frame = {"metadata": {"task_state": {"action_phase": "SEAT"}}, "action": {}}
    assert diag.read_phase(frame) == ("SEAT", "task_state")


def test_read_phase_fallback_action_level() -> None:
    frame = {"metadata": {}, "action_phase": "CONTACT", "action": {}}
    assert diag.read_phase(frame) == ("CONTACT", "action")


def test_read_phase_default_unknown() -> None:
    frame = {"metadata": {}, "action": {}}
    assert diag.read_phase(frame) == ("UNKNOWN", "default")


def test_read_phase_unsupported_value_becomes_unknown() -> None:
    frame = {"metadata": {"action_phase": "WIGGLE"}, "action": {}}
    assert diag.read_phase(frame) == ("UNKNOWN", "default")


def test_compute_phase_coverage_counts_and_rates() -> None:
    frames = (
        [make_frame("INSERT")] * 20
        + [make_frame("SEAT")] * 8
        + [make_frame("CONTACT")] * 2
    )
    result = diag.compute_phase_coverage(frames)
    assert result["phase_counts"]["INSERT"] == 20
    assert result["phase_counts"]["SEAT"] == 8
    assert result["phase_counts"]["CONTACT"] == 2
    assert abs(result["phase_rates"]["INSERT"] - 20 / 30) < 1e-9
    assert result["phase_source_distribution"]["metadata"] == 30


def test_is_frame_saturated_true() -> None:
    frame = make_frame("INSERT", native_action=[1.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    assert diag.is_frame_saturated(frame, threshold=0.999) is True


def test_is_frame_saturated_false() -> None:
    frame = make_frame("INSERT", native_action=[0.5, 0.0, 0.0, 0.0, 0.0, 0.0])
    assert diag.is_frame_saturated(frame, threshold=0.999) is False


def test_is_frame_saturated_missing_action() -> None:
    frame = {"metadata": {}, "action": {}}
    assert diag.is_frame_saturated(frame, threshold=0.999) is None


def test_is_frame_saturated_ignores_gripper() -> None:
    frame = make_frame("SEAT", native_action=[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0])
    assert diag.is_frame_saturated(frame, threshold=0.999) is False


def test_is_frame_saturated_short_vector_returns_none() -> None:
    frame = make_frame("INSERT", native_action=[1.0, 0.0, 0.0])
    assert diag.is_frame_saturated(frame, threshold=0.999) is None


def test_consecutive_max_basic() -> None:
    assert diag._consecutive_max([True, True, False, True]) == 2
    assert diag._consecutive_max([True, True, True]) == 3
    assert diag._consecutive_max([False, False]) == 0
    assert diag._consecutive_max([]) == 0


def test_phase_conditional_saturation_ratios() -> None:
    frames = (
        [make_frame("INSERT", native_action=[1.0, 0.0, 0.0, 0.0, 0.0, 0.0])] * 10
        + [make_frame("INSERT", native_action=[0.1, 0.0, 0.0, 0.0, 0.0, 0.0])] * 10
        + [make_frame("SEAT", native_action=[1.0, 0.0, 0.0, 0.0, 0.0, 0.0])] * 5
        + [make_frame("SEAT", native_action=[0.0, 0.0, 0.0, 0.0, 0.0, 0.0])] * 5
    )
    result = diag.compute_phase_conditional_saturation(frames, threshold=0.999)
    assert result["sat_ratio_INSERT"] == 0.5
    assert result["sat_ratio_SEAT"] == 0.5
    assert result["sat_ratio_CONTACT"] == 0.0
    assert result["consecutive_sat_max_INSERT"] == 10
    assert result["consecutive_sat_max_SEAT"] == 5
    assert 0.0 < result["sat_ratio_aggregate"] < 1.0


def test_phase_conditional_saturation_empty_frames() -> None:
    result = diag.compute_phase_conditional_saturation([], threshold=0.999)
    assert result["sat_ratio_aggregate"] == 0.0
    assert result["sat_ratio_INSERT"] == 0.0


def make_frame_with_delta(
    phase: str, delta_m: list[float], clamped: bool = False
) -> dict:
    return make_frame(phase, delta_m=delta_m, workspace_clamped=clamped)


def test_get_applied_ee_delta_primary() -> None:
    frame = make_frame_with_delta("INSERT", [0.01, 0.02, 0.03])
    assert diag.get_applied_ee_delta(frame) == [0.01, 0.02, 0.03]


def test_get_applied_ee_delta_fallback_executed_control() -> None:
    frame = {
        "metadata": {},
        "action": {
            "executed_control": {
                "applied_end_effector_action": {"delta_position": [0.005, 0.0, 0.0]}
            }
        },
    }
    assert diag.get_applied_ee_delta(frame) == [0.005, 0.0, 0.0]


def test_get_applied_ee_delta_fallback_learning_action() -> None:
    frame = {
        "metadata": {},
        "action": {"learning_action": {"command": [0.004, 0.0, 0.0, 1.0]}},
    }
    assert diag.get_applied_ee_delta(frame) == [0.004, 0.0, 0.0]


def test_get_applied_ee_delta_none_when_missing() -> None:
    assert diag.get_applied_ee_delta({"metadata": {}, "action": {}}) is None


def test_get_command_step_norm_precomputed() -> None:
    frame = {
        "metadata": {},
        "action": {
            "control_filter": {"teleop_control_mode": {"command_step_norm": 0.025}}
        },
    }
    assert diag.get_command_step_norm(frame) == 0.025


def test_get_command_step_norm_computed_from_delta() -> None:
    frame = make_frame_with_delta("INSERT", [0.03, 0.04, 0.0])
    norm = diag.get_command_step_norm(frame)
    assert norm is not None
    assert abs(norm - 0.05) < 1e-9


def test_get_workspace_clamped() -> None:
    frame_clamped = make_frame_with_delta("INSERT", [0.01, 0.0, 0.0], clamped=True)
    frame_free = make_frame_with_delta("INSERT", [0.01, 0.0, 0.0], clamped=False)
    assert diag.get_workspace_clamped(frame_clamped) is True
    assert diag.get_workspace_clamped(frame_free) is False
    assert diag.get_workspace_clamped({"metadata": {}, "action": {}}) is None


def test_compute_command_quality_basic() -> None:
    frames = [
        make_frame_with_delta("INSERT", [0.01, 0.0, 0.0]),
        make_frame_with_delta("INSERT", [0.02, 0.0, 0.0]),
        make_frame_with_delta("INSERT", [0.02, 0.0, 0.0]),
    ]
    result = diag.compute_command_quality(frames)
    assert abs(result["command_step_norm_mean"] - (0.01 + 0.02 + 0.02) / 3) < 1e-9
    assert abs(result["jerk_mean"] - 0.005) < 1e-9
    assert result["workspace_clamped_ratio"] == 0.0


def test_compute_command_quality_no_frames() -> None:
    result = diag.compute_command_quality([])
    assert result["command_step_norm_mean"] is None
    assert result["jerk_mean"] is None


def test_gate_a_pass_no_approach_needed() -> None:
    result = diag.compute_gate_judgment(
        {"INSERT": 25, "SEAT": 10, "CONTACT": 3}, _cfg()
    )
    assert result["gate_A_pass"] is True
    assert result["gate_B_pass"] is False
    assert result["gate_C_pass"] is True
    assert result["gate_B_fail_reason"] == "APPROACH_ABSENT"


def test_gate_b_pass_all_phases() -> None:
    counts = {"APPROACH": 15, "CONTACT": 5, "INSERT": 25, "SEAT": 10}
    result = diag.compute_gate_judgment(counts, _cfg())
    assert result["gate_A_pass"] is True
    assert result["gate_B_pass"] is True
    assert result["gate_C_pass"] is True
    assert result["gate_B_fail_reason"] is None


def test_gate_b_fail_approach_insufficient() -> None:
    counts = {"APPROACH": 5, "CONTACT": 3, "INSERT": 25, "SEAT": 10}
    result = diag.compute_gate_judgment(counts, _cfg())
    assert result["gate_B_pass"] is False
    assert result["gate_B_fail_reason"] == "APPROACH_INSUFFICIENT"


def test_gate_c_only_insert_present() -> None:
    result = diag.compute_gate_judgment({"INSERT": 25}, _cfg())
    assert result["gate_A_pass"] is False
    assert result["gate_B_pass"] is False
    assert result["gate_C_pass"] is True


def test_gate_all_fail_no_data() -> None:
    result = diag.compute_gate_judgment({}, _cfg())
    assert result["gate_A_pass"] is False
    assert result["gate_B_pass"] is False
    assert result["gate_C_pass"] is False


def test_cross_validation_match_both_fail() -> None:
    result = diag.compute_cross_validation(
        0.20, "NATIVE_ACTION_SATURATION", max_ratio=0.05
    )
    assert result["recomputed_sat_fail"] is True
    assert result["recorded_sat_fail"] is True
    assert result["gate_match"] is True


def test_cross_validation_mismatch() -> None:
    result = diag.compute_cross_validation(
        0.001, "NATIVE_ACTION_SATURATION", max_ratio=0.05
    )
    assert result["recomputed_sat_fail"] is False
    assert result["recorded_sat_fail"] is True
    assert result["gate_match"] is False


def test_cross_validation_both_pass() -> None:
    result = diag.compute_cross_validation(0.001, None, max_ratio=0.05)
    assert result["recomputed_sat_fail"] is False
    assert result["recorded_sat_fail"] is False
    assert result["gate_match"] is True


def test_cross_validation_other_reason_skipped() -> None:
    result = diag.compute_cross_validation(0.20, "RETARGETING_JUMP", max_ratio=0.05)
    assert result["gate_match"] is None
    assert result["gate_match_skipped_reason"] == "other_failure_reason"


def test_cross_validation_uses_recorded_native_action_status() -> None:
    result = diag.compute_cross_validation(
        0.20,
        "TIMEOUT",
        max_ratio=0.05,
        recorded_native_action_saturation="fail",
    )
    assert result["recorded_sat_fail"] is True
    assert result["gate_match"] is True
    assert result["gate_match_skipped_reason"] is None


def _make_traj_json(episode_id: str, frames: list[dict]) -> dict:
    return {
        "id": f"traj_{episode_id[:8]}",
        "episode_id": episode_id,
        "schema_version": "v1",
        "source": {},
        "frames": frames,
        "summary": {"episode_status": "reset"},
    }


def _make_eval_json(episode_id: str, failure_reason: str | None) -> dict:
    return {
        "id": f"eval_{episode_id[:8]}",
        "episode_id": episode_id,
        "trajectory_id": f"traj_{episode_id[:8]}",
        "success": failure_reason is None,
        "failure_reason": failure_reason,
        "metrics": {},
    }


def test_extract_recorded_state_prefers_native_action_saturation_gate_reason() -> None:
    record = _make_eval_json("episode_quality01", "TIMEOUT")
    record["metrics"] = {
        "data_quality": {
            "native_action_saturation": "fail",
            "native_action_saturation_ratio": 0.12,
        },
        "curation": {
            "training_eligible": False,
            "rejection_reasons": ["NATIVE_ACTION_SATURATION"],
        },
    }

    result = diag._extract_recorded_state(record)
    assert result["recorded_evaluator_failure_reason"] == "TIMEOUT"
    assert result["recorded_failure_reason"] == "NATIVE_ACTION_SATURATION"
    assert result["recorded_native_action_saturation"] == "fail"
    assert result["old_live_gate_pass"] is False


def test_load_eval_index(tmp_path: Path) -> None:
    episode_id = "episode_abc123"
    (tmp_path / "eval_abc123.json").write_text(
        json.dumps(_make_eval_json(episode_id, "NATIVE_ACTION_SATURATION")),
        encoding="utf-8",
    )
    (tmp_path / "eval_broken.json").write_text("not json", encoding="utf-8")

    index = diag.load_eval_index(tmp_path)
    assert episode_id in index
    assert index[episode_id]["failure_reason"] == "NATIVE_ACTION_SATURATION"


def test_analyze_episode_full(tmp_path: Path) -> None:
    episode_id = "episode_test01"
    frames = (
        [make_frame("CONTACT")] * 3
        + [
            make_frame(
                "INSERT",
                native_action=[1.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                delta_m=[0.025, 0.0, 0.0],
            )
        ]
        * 25
        + [make_frame("SEAT", delta_m=[0.0, 0.0, 0.0])] * 10
    )
    traj_path = tmp_path / "traj_test01.json"
    traj_path.write_text(
        json.dumps(_make_traj_json(episode_id, frames)), encoding="utf-8"
    )

    result = diag.analyze_episode(
        traj_path,
        {episode_id: _make_eval_json(episode_id, "NATIVE_ACTION_SATURATION")},
        _cfg(),
    )

    assert result["episode_id"] == episode_id
    assert result["frame_count"] == 38
    assert result["gate_A_pass"] is True
    assert result["gate_B_pass"] is False
    assert result["gate_C_pass"] is True
    assert result["recorded_failure_reason"] == "NATIVE_ACTION_SATURATION"
    assert result["old_live_gate_pass"] is False
    assert result["sat_ratio_INSERT"] > 0.0
    assert result["sat_ratio_SEAT"] == 0.0
    assert result["command_step_norm_mean"] is not None


def test_run_diagnostic_creates_report(tmp_path: Path) -> None:
    episode_id = "episode_run01"
    frames = (
        [make_frame("CONTACT")] * 2
        + [make_frame("INSERT", delta_m=[0.01, 0.0, 0.0])] * 25
        + [make_frame("SEAT", delta_m=[0.0, 0.0, 0.0])] * 10
    )
    traj_dir = tmp_path / "trajectories"
    eval_dir = tmp_path / "evaluations"
    out_dir = tmp_path / "output"
    traj_dir.mkdir()
    eval_dir.mkdir()

    (traj_dir / "traj_run01.json").write_text(
        json.dumps(_make_traj_json(episode_id, frames)), encoding="utf-8"
    )
    (eval_dir / "eval_run01.json").write_text(
        json.dumps(_make_eval_json(episode_id, None)), encoding="utf-8"
    )

    report = diag.run_diagnostic(traj_dir, eval_dir, out_dir, _cfg())

    assert report["schema_version"] == diag.SCHEMA_VERSION
    assert len(report["episodes"]) == 1
    assert report["summary"]["total_episodes"] == 1
    assert report["summary"]["gate_A_pass_count"] == 1
    assert (out_dir / "mvp2_curation_diagnostic_report.json").exists()


def test_cli_help() -> None:
    result = subprocess.run(
        ["uv", "run", "python", "scripts/run_mvp2_curation_diagnostic.py", "--help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "--trajectories-dir" in result.stdout
    assert "--action-sat-value-threshold" in result.stdout
    assert "--max-native-action-sat-ratio" in result.stdout


def test_cli_runs_with_empty_dirs(tmp_path: Path) -> None:
    traj_dir = tmp_path / "trajectories"
    eval_dir = tmp_path / "evaluations"
    out_dir = tmp_path / "output"
    traj_dir.mkdir()
    eval_dir.mkdir()

    result = subprocess.run(
        [
            "uv",
            "run",
            "python",
            "scripts/run_mvp2_curation_diagnostic.py",
            "--trajectories-dir",
            str(traj_dir),
            "--evaluations-dir",
            str(eval_dir),
            "--output-dir",
            str(out_dir),
            "--pretty",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert (out_dir / "mvp2_curation_diagnostic_report.json").exists()
    report = json.loads((out_dir / "mvp2_curation_diagnostic_report.json").read_text())
    assert report["summary"]["total_episodes"] == 0


def test_cli_end_to_end(tmp_path: Path) -> None:
    episode_id = "episode_e2e01"
    frames = (
        [make_frame("CONTACT")] * 3
        + [
            make_frame(
                "INSERT",
                native_action=[1.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                delta_m=[0.025, 0.0, 0.0],
            )
        ]
        * 25
        + [make_frame("SEAT", delta_m=[0.001, 0.0, 0.0])] * 10
    )
    traj_dir = tmp_path / "trajectories"
    eval_dir = tmp_path / "evaluations"
    out_dir = tmp_path / "output"
    traj_dir.mkdir()
    eval_dir.mkdir()

    (traj_dir / "traj_e2e01.json").write_text(
        json.dumps(_make_traj_json(episode_id, frames)), encoding="utf-8"
    )
    (eval_dir / "eval_e2e01.json").write_text(
        json.dumps(_make_eval_json(episode_id, "NATIVE_ACTION_SATURATION")),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            "uv",
            "run",
            "python",
            "scripts/run_mvp2_curation_diagnostic.py",
            "--trajectories-dir",
            str(traj_dir),
            "--evaluations-dir",
            str(eval_dir),
            "--output-dir",
            str(out_dir),
            "--pretty",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads((out_dir / "mvp2_curation_diagnostic_report.json").read_text())
    episode = report["episodes"][0]
    assert episode["gate_A_pass"] is True
    assert episode["old_live_gate_pass"] is False
    assert episode["sat_ratio_INSERT"] > 0.0
    assert episode["sat_ratio_SEAT"] == 0.0
    assert "gate_match" in episode
