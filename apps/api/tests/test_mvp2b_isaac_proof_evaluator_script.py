from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[3]


def load_script(name: str) -> Any:
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_mvp2b_scenario_manifest_is_pre_registered_and_hashed(tmp_path: Path) -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    manifest = script.build_scenario_manifest(output_dir=tmp_path / "mvp2b")

    assert manifest["manifest_version"] == "rdf_mvp2b_scenario_manifest_v0.1.0"
    assert manifest["success_metric"]["insertion_depth_m_min"] == 0.03
    assert manifest["success_metric"]["lateral_error_m_max"] == 0.006
    assert manifest["success_metric"]["orientation_error_deg_max"] == 8.0
    assert manifest["success_metric"]["stable_steps_required"] == 10
    assert manifest["success_metric"]["max_steps"] == 150
    assert manifest["manifest_sha256"]
    assert (tmp_path / "mvp2b" / "scenario_manifest.json").exists()


def test_mvp2b_default_output_dir_uses_persistent_proof_evidence_storage() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")

    assert script.DEFAULT_OUTPUT_DIR == ROOT / "storage" / "proof_evidence" / "mvp2b_isaac_proof_evaluator"


def test_mvp2b_build_writes_evidence_manifest_with_file_hashes(tmp_path: Path) -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    output_dir = tmp_path / "mvp2b"

    report = script.build_mvp2b_isaac_proof_evaluator(output_dir=output_dir, clean=True, skip_isaac=True)

    manifest_path = output_dir / "evidence_manifest.json"
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "rdf_proof_evidence_manifest_v0.1.0"
    assert manifest["proof_slice"] == "mvp2b_isaac_proof_evaluator"
    assert manifest["output_dir"] == str(output_dir)
    assert manifest["reproducible_command"] == report["reproducible_command"]
    assert manifest["evidence_manifest_sha256"]
    files = {item["path"]: item for item in manifest["files"]}
    assert "evidence_manifest.json" not in files
    assert "scenario_manifest.json" in files
    assert "mvp2b_isaac_proof_evaluator_report.json" in files
    assert files["scenario_manifest.json"]["sha256"] == script._sha256_file(output_dir / "scenario_manifest.json")
    assert files["mvp2b_isaac_proof_evaluator_report.json"]["size_bytes"] > 0
    assert report["artifact_paths"]["evidence_manifest"] == str(manifest_path)


def test_mvp2b_scenario_manifest_has_disjoint_splits(tmp_path: Path) -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    manifest = script.build_scenario_manifest(output_dir=tmp_path / "mvp2b")

    split_to_seeds = {
        split: {row["seed"] for row in manifest["scenarios"] if row["split"] == split}
        for split in ("train_success", "train_failure", "calibration", "held_out")
    }
    assert split_to_seeds["held_out"] == set(range(3000, 3020))
    for left_name, left_seeds in split_to_seeds.items():
        for right_name, right_seeds in split_to_seeds.items():
            if left_name != right_name:
                assert left_seeds.isdisjoint(right_seeds)


def test_mvp2b_leak_guard_rejects_heldout_training_use(tmp_path: Path) -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    manifest = script.build_scenario_manifest(output_dir=tmp_path / "mvp2b")
    heldout_id = next(row["scenario_id"] for row in manifest["scenarios"] if row["split"] == "held_out")

    leakage_report = script.validate_no_heldout_leakage(
        manifest=manifest,
        training_scenario_ids=["train_success_1000", heldout_id],
        curation_tuning_scenario_ids=[],
        threshold_tuning_scenario_ids=[],
        hyperparameter_scenario_ids=[],
    )

    assert leakage_report["passed"] is False
    assert heldout_id in leakage_report["leaked_scenario_ids"]


def test_mvp2b_threshold_freeze_requires_new_manifest_version(tmp_path: Path) -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    manifest = script.build_scenario_manifest(output_dir=tmp_path / "mvp2b")
    changed_metric = dict(manifest["success_metric"])
    changed_metric["lateral_error_m_max"] = 0.008

    freeze_report = script.validate_threshold_freeze(
        original_manifest=manifest,
        proposed_success_metric=changed_metric,
        proposed_manifest_version=manifest["manifest_version"],
    )

    assert freeze_report["passed"] is False
    assert freeze_report["requires_new_manifest_version"] is True


def test_mvp2b_success_requires_geometry_and_stability() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    trace = [
        {
            "step": index,
            "insertion_depth_m": 0.031,
            "lateral_error_m": 0.004,
            "orientation_error_deg": 5.0,
        }
        for index in range(12)
    ]

    result = script.evaluate_rollout_trace(trace)

    assert result["success"] is True
    assert result["stable_steps_observed"] >= 10
    assert result["failure_reason"] == ""


def test_mvp2b_runtime_metric_uses_rdf_depth_and_axis_alignment() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")

    row = script.rdf_compatible_metric_row_from_pose_values(
        step=7,
        held_pos=[0.6097, 0.0140, 0.1082],
        fixed_pos=[0.6011, 0.0223, 0.0644],
        held_quat=[1.0, 0.0, 0.0, 0.0],
        fixed_quat=[1.0, 0.0, 0.0, 0.0],
    )

    assert row["step"] == 7
    assert row["insertion_depth_m"] == pytest.approx(0.0438)
    assert row["lateral_error_m"] == pytest.approx(0.011951, rel=1.0e-4)
    assert row["orientation_error_deg"] == 0.0
    assert row["phase"] == "SEAT"


def test_v06d_trace_phase_normalization_maps_runtime_phase_to_controller_phase() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")

    assert script.normalize_v06_controller_phase("APPROACH") == {
        "input_phase": "APPROACH",
        "controller_phase": "ALIGN",
        "phase_vocabulary_mismatch": False,
        "phase_normalized": True,
    }
    assert script.normalize_v06_controller_phase("CONTACT")["controller_phase"] == "DESCEND"
    assert script.normalize_v06_controller_phase("INSERT")["controller_phase"] == "INSERT"
    assert script.normalize_v06_controller_phase("SEAT")["controller_phase"] == "HOLD"
    assert script.normalize_v06_controller_phase("UNKNOWN") == {
        "input_phase": "UNKNOWN",
        "controller_phase": "UNKNOWN",
        "phase_vocabulary_mismatch": True,
        "phase_normalized": False,
    }


def test_v06d_action_diagnostics_allow_approach_phase_z_motion_when_aligned() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    policy_artifact = {
        "selected_action_adapter_id": "isaac_signed_xy_downward_servo_v0",
        "selected_action_adapter_config": {
            "controller_version": "v0_6_active_state_controller",
            "xy_source": "state_feedback",
            "xy_state_feedback_gain": 4.0,
            "xy_action_clip": 0.035,
            "z_action_scale": 24.0,
            "z_action_clip": 0.12,
            "rotation_action_scale": 0.0,
        },
    }
    metric_row = {
        "phase": "APPROACH",
        "lateral_error_m": 0.0003,
        "orientation_error_deg": 0.01,
        "insertion_depth_m": 0.0,
        "relative_x_m": -0.0001,
        "relative_y_m": 0.0002,
        "env_native_success": False,
        "env_native_current_consecutive_success_steps": 0,
    }

    action, diagnostics = script._apply_selected_action_adapter_with_diagnostics(
        policy_artifact=policy_artifact,
        raw_action=script.np.asarray([0.0, 0.0, -0.005, 0.0, 0.0, 0.0, 1.0]),
        action_scale=1.0,
        metric_row=metric_row,
    )

    assert diagnostics["raw_action_vector"][2] < 0.0
    assert diagnostics["pre_controller_action_vector"][2] < 0.0
    assert action[2] < 0.0
    assert diagnostics["input_metric_phase"] == "APPROACH"
    assert diagnostics["controller_input_phase"] == "ALIGN"
    assert diagnostics["phase_normalized"] is True
    assert diagnostics["phase_vocabulary_mismatch"] is False
    assert diagnostics["z_motion_suppressed"] is False
    assert diagnostics["z_motion_block_reason"] == "z_motion_allowed"


def test_v06e_capture_radius_gate_suppresses_z_until_inside_capture_radius() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    policy_artifact = {
        "selected_action_adapter_id": "isaac_signed_xy_downward_servo_v0",
        "selected_action_adapter_config": {
            "controller_version": "v0_6_active_state_controller",
            "capture_radius_m": 0.003,
            "align_lateral_gate_m": 0.003,
            "align_orientation_gate_rad": 0.25,
            "xy_source": "state_feedback",
            "xy_state_feedback_gain": 4.0,
            "xy_action_clip": 0.035,
            "z_action_scale": 24.0,
            "z_action_clip": 0.12,
            "rotation_action_scale": 0.0,
        },
    }
    metric_row = {
        "phase": "APPROACH",
        "lateral_error_m": 0.004,
        "orientation_error_deg": 0.01,
        "insertion_depth_m": 0.0,
        "relative_x_m": 0.004,
        "relative_y_m": 0.0,
        "env_native_success": False,
        "env_native_current_consecutive_success_steps": 0,
    }

    action, diagnostics = script._apply_selected_action_adapter_with_diagnostics(
        policy_artifact=policy_artifact,
        raw_action=script.np.asarray([0.0, 0.0, -0.005, 0.0, 0.0, 0.0, 1.0]),
        action_scale=1.0,
        metric_row=metric_row,
    )

    assert diagnostics["pre_controller_action_vector"][2] < 0.0
    assert action[2] == 0.0
    assert diagnostics["z_motion_suppressed"] is True
    assert diagnostics["z_motion_block_reason"] == "alignment_gate_not_satisfied"
    assert diagnostics["align_lateral_gate_m"] == 0.003


def test_v06e_capture_radius_gate_allows_z_inside_capture_radius() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    policy_artifact = {
        "selected_action_adapter_id": "isaac_signed_xy_downward_servo_v0",
        "selected_action_adapter_config": {
            "controller_version": "v0_6_active_state_controller",
            "capture_radius_m": 0.003,
            "align_lateral_gate_m": 0.003,
            "align_orientation_gate_rad": 0.25,
            "xy_source": "state_feedback",
            "xy_state_feedback_gain": 4.0,
            "xy_action_clip": 0.035,
            "z_action_scale": 24.0,
            "z_action_clip": 0.12,
            "rotation_action_scale": 0.0,
        },
    }
    metric_row = {
        "phase": "APPROACH",
        "lateral_error_m": 0.0025,
        "orientation_error_deg": 0.01,
        "insertion_depth_m": 0.0,
        "relative_x_m": 0.0025,
        "relative_y_m": 0.0,
        "env_native_success": False,
        "env_native_current_consecutive_success_steps": 0,
    }

    action, diagnostics = script._apply_selected_action_adapter_with_diagnostics(
        policy_artifact=policy_artifact,
        raw_action=script.np.asarray([0.0, 0.0, -0.005, 0.0, 0.0, 0.0, 1.0]),
        action_scale=1.0,
        metric_row=metric_row,
    )

    assert action[2] < 0.0
    assert diagnostics["z_motion_suppressed"] is False
    assert diagnostics["z_motion_block_reason"] == "z_motion_allowed"
    assert diagnostics["align_lateral_gate_m"] == 0.003


def test_v06f_approach_gate_allows_z_inside_approach_gate_without_claiming_success() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    policy_artifact = {
        "selected_action_adapter_id": "isaac_signed_xy_downward_servo_v0",
        "selected_action_adapter_config": {
            "controller_repair_version": "v0_6f",
            "straight_down_capture_radius_m": 0.0001,
            "approach_lateral_gate_m": 0.001,
            "align_lateral_gate_m": 0.001,
            "z_push_gate": "lateral_error_m <= approach_lateral_gate_m",
            "align_orientation_gate_rad": 0.25,
            "xy_source": "state_feedback",
            "xy_state_feedback_gain": 4.0,
            "xy_action_clip": 0.035,
            "z_action_scale": 24.0,
            "z_action_clip": 0.12,
            "rotation_action_scale": 0.0,
        },
    }
    outside_metric_row = {
        "phase": "APPROACH",
        "relative_x_m": 0.0012,
        "relative_y_m": 0.0,
        "lateral_error_m": 0.0012,
        "orientation_error_deg": 0.0,
        "insertion_depth_m": 0.0,
        "env_native_success": False,
        "env_native_current_consecutive_success_steps": 0,
    }
    inside_metric_row = {
        **outside_metric_row,
        "relative_x_m": 0.0009,
        "lateral_error_m": 0.0009,
    }

    outside_action, outside_diagnostics = script._apply_selected_action_adapter_with_diagnostics(
        policy_artifact=policy_artifact,
        raw_action=script.np.asarray([0.0, 0.0, -0.005, 0.0, 0.0, 0.0, 1.0]),
        action_scale=1.0,
        metric_row=outside_metric_row,
    )
    inside_action, inside_diagnostics = script._apply_selected_action_adapter_with_diagnostics(
        policy_artifact=policy_artifact,
        raw_action=script.np.asarray([0.0, 0.0, -0.005, 0.0, 0.0, 0.0, 1.0]),
        action_scale=1.0,
        metric_row=inside_metric_row,
    )

    assert outside_action[2] == 0.0
    assert outside_diagnostics["z_motion_suppressed"] is True
    assert outside_diagnostics["z_motion_block_reason"] == "alignment_gate_not_satisfied"
    assert inside_action[2] < 0.0
    assert inside_diagnostics["z_motion_suppressed"] is False
    assert inside_diagnostics["align_lateral_gate_m"] == 0.001


def test_factory_peg_insert_native_height_threshold_matches_factory_config() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")

    diag = script.build_factory_peg_insert_native_success_diagnostics(
        held_base_pos=[0.0, 0.0, 0.045],
        target_held_base_pos=[0.0, 0.0, 0.0],
        fixed_asset_height_m=0.025,
        success_threshold=0.04,
    )

    assert diag["env_native_height_threshold_m"] == 0.001
    assert diag["env_native_z_disp_m"] == 0.045
    assert diag["env_native_is_close_or_below"] is False
    assert diag["env_native_success_mask"] is False


def test_native_aligned_metric_row_does_not_label_high_z_disp_as_seat() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")

    row = script.factory_peg_insert_native_aligned_metric_row_from_pose_values(
        step=0,
        held_pos=[0.0, 0.0, 0.045],
        fixed_pos=[0.0, 0.0, 0.0],
        held_base_pos=[0.0, 0.0, 0.045],
        target_held_base_pos=[0.0, 0.0, 0.0],
        held_base_quat=[1.0, 0.0, 0.0, 0.0],
        target_held_base_quat=[1.0, 0.0, 0.0, 0.0],
        held_quat=[1.0, 0.0, 0.0, 0.0],
        fixed_quat=[1.0, 0.0, 0.0, 0.0],
        fixed_asset_height_m=0.025,
        success_threshold=0.04,
    )

    assert row["legacy_positive_z_disp_m"] == 0.045
    assert row["approach_height_m"] == 0.045
    assert row["native_seating_progress_m"] == 0.0
    assert row["runtime_depth_feature_m"] == 0.0
    assert row["insertion_depth_m"] == 0.0
    assert row["phase"] != "SEAT"


def test_native_aligned_metric_row_labels_near_native_target_as_seat_candidate() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")

    row = script.factory_peg_insert_native_aligned_metric_row_from_pose_values(
        step=0,
        held_pos=[0.0002, 0.0002, 0.0005],
        fixed_pos=[0.0, 0.0, 0.0],
        held_base_pos=[0.0002, 0.0002, 0.0005],
        target_held_base_pos=[0.0, 0.0, 0.0],
        held_base_quat=[1.0, 0.0, 0.0, 0.0],
        target_held_base_quat=[1.0, 0.0, 0.0, 0.0],
        held_quat=[1.0, 0.0, 0.0, 0.0],
        fixed_quat=[1.0, 0.0, 0.0, 0.0],
        fixed_asset_height_m=0.025,
        success_threshold=0.04,
    )

    assert row["env_native_xy_dist_m"] < 0.0025
    assert row["env_native_z_disp_m"] < 0.001
    assert row["env_native_success_mask"] is True
    assert row["phase"] == "SEAT"


def test_legacy_rdf_metric_row_remains_available_for_deterministic_fixtures() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")

    row = script.rdf_compatible_metric_row_from_pose_values(
        step=0,
        held_pos=[0.0, 0.0, 0.034],
        fixed_pos=[0.0, 0.0, 0.0],
        held_quat=[1.0, 0.0, 0.0, 0.0],
        fixed_quat=[1.0, 0.0, 0.0, 0.0],
    )

    assert row["insertion_depth_m"] == 0.034
    assert row["phase"] == "SEAT"
    assert "rdf_metric_semantics" not in row


def test_mvp2b_success_fails_without_consecutive_stable_steps() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    trace = []
    for index in range(12):
        trace.append(
            {
                "step": index,
                "insertion_depth_m": 0.031,
                "lateral_error_m": 0.004 if index != 9 else 0.009,
                "orientation_error_deg": 5.0,
            }
        )

    result = script.evaluate_rollout_trace(trace)

    assert result["success"] is False
    assert result["failure_reason"] == "STABILITY_WINDOW_NOT_REACHED"


def test_env_native_success_requires_ten_consecutive_steps() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")

    summary = script.evaluate_env_native_success_window(
        [False, True, True, True, False, True, True, True, True, True, True, True, True, True, True],
        stable_steps_required=10,
    )

    assert summary["first_success_step"] == 1
    assert summary["max_consecutive_success_steps"] == 10
    assert summary["rollout_success"] is True

    near_miss = script.evaluate_env_native_success_window(
        [False, True, True, True, True, True, True, True, True, True],
        stable_steps_required=10,
    )
    assert near_miss["max_consecutive_success_steps"] == 9
    assert near_miss["rollout_success"] is False


def test_env_native_trace_summary_preserves_rdf_metric_as_secondary() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    trace = [
        {
            "step": index,
            "env_native_success": index >= 3,
            "insertion_depth_m": 0.031,
            "lateral_error_m": 0.004,
            "orientation_error_deg": 5.0,
        }
        for index in range(13)
    ]

    summary = script.evaluate_env_native_rollout_trace(trace, success_metric=script.SUCCESS_METRIC)

    assert summary["env_native_rollout_success"] is True
    assert summary["env_native_max_consecutive_success_steps"] == 10
    assert summary["rdf_peg_in_hole_metric"]["closure_authority"] is False


def test_v06_phase_controller_holds_z_until_lateral_and_orientation_are_aligned() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")

    phase = script.v06_phase_controller_step(
        current_phase="ALIGN",
        lateral_error_m=0.009,
        orientation_error_rad=0.01,
        insertion_depth_m=0.0,
        env_native_success=False,
        stable_steps=0,
    )

    assert phase["next_phase"] == "ALIGN"
    assert phase["z_motion_allowed"] is False


def test_v06_phase_controller_descends_only_while_alignment_gate_holds() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")

    phase = script.v06_phase_controller_step(
        current_phase="DESCEND",
        lateral_error_m=0.009,
        orientation_error_rad=0.01,
        insertion_depth_m=0.010,
        env_native_success=False,
        stable_steps=0,
    )

    assert phase["next_phase"] == "DESCEND"
    assert phase["z_motion_allowed"] is False


def test_mvp2b_peg_insert_orientation_error_is_relative_to_downward_target() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")

    error = script.quaternion_angle_error_deg([0.0, 1.0, 0.0, 0.0], target_angle_deg=180.0)

    assert error == 0.0


def test_mvp2b_controlled_failure_taxonomy_covers_rejection_reasons(tmp_path: Path) -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    manifest = script.build_scenario_manifest(output_dir=tmp_path / "mvp2b")

    bundle = script.generate_training_trajectory_bundle(
        manifest=manifest,
        output_dir=tmp_path / "mvp2b",
    )

    rejected_reasons = {
        item["rejection_reason"]
        for item in bundle["curation_manifest"]["items"]
        if item["accepted"] is False
    }
    assert rejected_reasons == set(script.CONTROLLED_FAILURE_REASONS)


def test_mvp2b_generated_trajectory_contracts_pass_validator(tmp_path: Path) -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    manifest = script.build_scenario_manifest(output_dir=tmp_path / "mvp2b")

    bundle = script.generate_training_trajectory_bundle(
        manifest=manifest,
        output_dir=tmp_path / "mvp2b",
    )

    assert bundle["contract_validation"]["passed"] is True
    assert bundle["accepted_count"] > 0
    assert bundle["rejected_count"] > 0


def test_mvp2b_curation_outputs_baseline_and_candidate_train_views(tmp_path: Path) -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    report = script.build_mvp2b_isaac_proof_evaluator(
        output_dir=tmp_path / "mvp2b",
        clean=True,
        skip_isaac=True,
        min_rollouts_per_policy=20,
    )

    assert Path(report["artifact_paths"]["baseline_uncurated_train_hdf5"]).exists()
    assert Path(report["artifact_paths"]["candidate_curated_train_hdf5"]).exists()
    assert report["training_views"]["baseline"]["includes_rejected_material"] is True
    assert report["training_views"]["candidate"]["includes_rejected_material"] is False
    assert report["training_views"]["candidate"]["accepted_count"] > 0


def test_mvp2b_phase_conditioned_bc_uses_identical_feature_schema(tmp_path: Path) -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    report = script.build_mvp2b_isaac_proof_evaluator(
        output_dir=tmp_path / "mvp2b",
        clean=True,
        skip_isaac=True,
        min_rollouts_per_policy=20,
    )

    baseline = report["policy_artifacts"]["baseline"]
    candidate = report["policy_artifacts"]["candidate"]
    assert baseline["policy_class"] == "phase_conditioned_numpy_bc_policy_v0"
    assert candidate["policy_class"] == baseline["policy_class"]
    assert candidate["trainer"] == baseline["trainer"]
    assert candidate["feature_schema"] == baseline["feature_schema"]
    assert candidate["phase_schema"] == baseline["phase_schema"]
    assert candidate["hyperparameters"] == baseline["hyperparameters"]


def test_mvp2b_policy_features_pad_short_previous_action() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")

    feature, _ = script.featurize_step(
        {
            "phase": "APPROACH",
            "insertion_depth_m": 0.0,
            "relative_x_m": 0.001,
            "relative_y_m": -0.002,
            "lateral_error_m": 0.01,
            "orientation_error_deg": 5.0,
            "normalized_action": [0.0] * len(script.ACTION_SCHEMA),
        },
        previous_action=[0.25],
    )

    assert feature.shape[0] == len(script.FEATURE_SCHEMA)
    assert feature[-7] == 0.25
    assert feature[-1] == 0.0


def test_v07a_feature_schema_uses_behavior_state_phase_without_mutating_phase() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")

    feature, _ = script.featurize_step(
        {
            "phase": "APPROACH",
            "behavior_state_phase": "DESCEND",
            "insertion_depth_m": 0.012,
            "relative_x_m": 0.0,
            "relative_y_m": 0.0,
            "lateral_error_m": 0.0008,
            "orientation_error_deg": 0.0,
            "normalized_action": [0.0] * len(script.ACTION_SCHEMA),
        },
        previous_action=[0.0] * len(script.ACTION_SCHEMA),
        feature_schema=script.FEATURE_SCHEMA_V07A,
    )

    assert len(feature) == len(script.FEATURE_SCHEMA_V07A)
    assert feature[0:3].tolist() == [0.0, 1.0, 0.0]


def test_v07a_runtime_prediction_derives_behavior_state_phase_from_metric_row() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    weights = [[0.0] * len(script.ACTION_SCHEMA) for _ in script.FEATURE_SCHEMA_V07A]
    weights[1][2] = -0.16
    policy = {
        "policy_id": "candidate_curated_mvp2e_v07a_behavior_phase_numpy_bc",
        "policy_class": script.POLICY_CLASS,
        "feature_schema": list(script.FEATURE_SCHEMA_V07A),
        "phase_schema": list(script.BEHAVIOR_STATE_PHASES),
        "behavior_state_phase_input": True,
        "selected_action_adapter_id": "isaac_delta_pose_direct_v0",
        "selected_action_adapter_config": {"adapter_mode": "global_action_scale"},
        "weights": weights,
        "bias": [0.0] * len(script.ACTION_SCHEMA),
    }

    action, diagnostics = script._predict_policy_action_with_diagnostics(
        policy,
        metric_row={
            "phase": "APPROACH",
            "lateral_error_m": 0.0008,
            "insertion_depth_m": 0.012,
            "relative_x_m": 0.0,
            "relative_y_m": 0.0,
            "orientation_error_deg": 0.0,
        },
        previous_action=[0.0] * len(script.ACTION_SCHEMA),
        action_scale=1.0,
    )

    assert diagnostics["behavior_state_phase"] == "DESCEND"
    assert diagnostics["behavior_state_phase_source"] == "derived_v0_7a_runtime_rule"
    assert round(float(action[2]), 6) == -0.16


def test_v07a1_runtime_policy_prediction_derives_same_behavior_phase_rule() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    artifact = {
        "feature_schema": script.FEATURE_SCHEMA_V07A,
        "feature_schema_version": script.FEATURE_SCHEMA_V07A_VERSION,
        "behavior_state_phase_input": True,
        "behavior_phase_rule_version": "env_native_hold_v0_7a_1",
        "weights": [[0.0] * len(script.ACTION_SCHEMA) for _ in script.FEATURE_SCHEMA_V07A],
        "bias": [0.0] * len(script.ACTION_SCHEMA),
        "selected_action_adapter_config": {"action_scale": 1.0},
    }

    _, diagnostics = script._predict_policy_action_with_diagnostics(
        artifact,
        metric_row={
            "env_native_success_mask": True,
            "phase": "APPROACH",
            "insertion_depth_m": 0.0,
            "relative_x_m": 0.2,
            "relative_y_m": 0.0,
            "lateral_error_m": 0.2,
            "orientation_error_deg": 0.0,
        },
        previous_action=[0.0] * len(script.ACTION_SCHEMA),
        action_scale=1.0,
    )

    assert diagnostics["behavior_state_phase"] == "HOLD"
    assert diagnostics["behavior_state_phase_source"] == "derived_v0_7a_1_runtime_rule"


def test_v07a1_runtime_ignores_untrusted_provided_behavior_phase() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    artifact = {
        "feature_schema": script.FEATURE_SCHEMA_V07A,
        "feature_schema_version": script.FEATURE_SCHEMA_V07A_VERSION,
        "behavior_state_phase_input": True,
        "behavior_phase_rule_version": "env_native_hold_v0_7a_1",
        "weights": [[0.0] * len(script.ACTION_SCHEMA) for _ in script.FEATURE_SCHEMA_V07A],
        "bias": [0.0] * len(script.ACTION_SCHEMA),
        "selected_action_adapter_config": {"action_scale": 1.0},
    }

    _, diagnostics = script._predict_policy_action_with_diagnostics(
        artifact,
        metric_row={
            "behavior_state_phase": "ALIGN",
            "env_native_success": True,
            "phase": "APPROACH",
            "insertion_depth_m": 0.0,
            "relative_x_m": 0.2,
            "relative_y_m": 0.0,
            "lateral_error_m": 0.2,
            "orientation_error_deg": 0.0,
        },
        previous_action=[0.0] * len(script.ACTION_SCHEMA),
        action_scale=1.0,
    )

    assert diagnostics["behavior_state_phase"] == "HOLD"
    assert diagnostics["behavior_state_phase_source"] == "derived_v0_7a_1_runtime_rule"
    assert diagnostics["provided_behavior_state_phase_ignored"] is True


def test_v07a2_runtime_prediction_uses_trace_native_rule() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    artifact = {
        "feature_schema": script.FEATURE_SCHEMA_V07A,
        "feature_schema_version": script.FEATURE_SCHEMA_V07A_VERSION,
        "behavior_state_phase_input": True,
        "behavior_phase_rule_version": "env_native_hold_v0_7a_2",
        "weights": [[0.0] * len(script.ACTION_SCHEMA) for _ in script.FEATURE_SCHEMA_V07A],
        "bias": [0.0] * len(script.ACTION_SCHEMA),
        "selected_action_adapter_config": {"action_scale": 1.0},
    }

    _, diagnostics = script._predict_policy_action_with_diagnostics(
        artifact,
        metric_row={
            "behavior_state_phase": "ALIGN",
            "env_native_success": True,
            "env_native_success_mask": True,
            "phase": "APPROACH",
            "insertion_depth_m": 0.0,
            "relative_x_m": 0.2,
            "relative_y_m": 0.0,
            "lateral_error_m": 0.2,
            "orientation_error_deg": 0.0,
        },
        previous_action=[0.0] * len(script.ACTION_SCHEMA),
        action_scale=1.0,
    )

    assert diagnostics["behavior_state_phase"] == "HOLD"
    assert diagnostics["behavior_state_phase_source"] == "derived_v0_7a_2_runtime_rule"
    assert diagnostics["provided_behavior_state_phase_ignored"] is True


def test_v07a_historical_runtime_rule_still_uses_depth_proxy() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")

    assert (
        script.derive_v07a_behavior_state_phase_from_metrics(
            {"env_native_success": True, "lateral_error_m": 0.2, "insertion_depth_m": 0.0}
        )
        == "ALIGN"
    )
    assert (
        script.derive_v07a_behavior_state_phase_from_metrics(
            {"env_native_success": False, "lateral_error_m": 0.0, "insertion_depth_m": 0.03}
        )
        == "HOLD"
    )


def test_mvp2b_predict_policy_action_applies_residual_servo_before_adapter() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    base_config = {
        "xy_gain": 0.5,
        "approach_z": -0.001,
        "contact_z": -0.0015,
        "insert_z": -0.002,
        "seat_z": -0.0005,
        "gripper": 1.0,
    }
    policy = {
        "policy_id": "candidate_curated_mvp2d_v05_residual_servo_bc",
        "policy_class": "phase_conditioned_residual_servo_bc_policy_v0",
        "trainer_family": "phase_conditioned_residual_servo_bc",
        "weak_base_servo_config": base_config,
        "selected_action_adapter_id": "isaac_signed_xy_downward_servo_v0",
        "selected_action_adapter_config": {
            "xy_action_scale": 3.0,
            "xy_action_clip": 0.05,
            "xy_source": "policy_only",
            "z_action_scale": 32.0,
            "z_action_clip": 0.16,
            "rotation_action_scale": 0.0,
        },
        "weights": [[0.0] * len(script.ACTION_SCHEMA) for _ in script.FEATURE_SCHEMA],
        "bias": [0.001, -0.002, -0.001, 0.0, 0.0, 0.0, 0.0],
    }

    action = script._predict_policy_action(
        policy,
        metric_row={
            "phase": "INSERT",
            "insertion_depth_m": 0.02,
            "relative_x_m": 0.006,
            "relative_y_m": -0.004,
            "lateral_error_m": 0.007,
            "orientation_error_deg": 2.0,
        },
        previous_action=[0.0] * len(script.ACTION_SCHEMA),
        action_scale=1.0,
    )

    assert action.tolist()[:3] == [-0.006, 0.0, -0.096]


def test_v07b_residual_policy_fails_closed_without_frozen_base_metadata() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    policy = {
        "policy_id": "candidate_curated_mvp2e_v07b_residual_servo_bc",
        "policy_slice": "v0_7b",
        "policy_class": "phase_conditioned_residual_servo_bc_policy_v0",
        "trainer_family": "phase_conditioned_residual_servo_bc",
        "feature_schema": script.FEATURE_SCHEMA_V07A,
        "feature_schema_version": script.FEATURE_SCHEMA_V07A_VERSION,
        "behavior_state_phase_input": True,
        "behavior_phase_rule_version": "env_native_hold_v0_7a_2",
        "weights": [[0.0] * len(script.ACTION_SCHEMA) for _ in script.FEATURE_SCHEMA_V07A],
        "bias": [0.0] * len(script.ACTION_SCHEMA),
        "selected_action_adapter_config": {"action_scale": 1.0},
    }

    with pytest.raises(ValueError, match="v0_7b_residual_metadata_missing"):
        script._predict_policy_action_with_diagnostics(
            policy,
            metric_row={
                "phase": "APPROACH",
                "env_native_success_mask": False,
                "insertion_depth_m": 0.0,
                "relative_x_m": 0.002,
                "relative_y_m": 0.0,
                "lateral_error_m": 0.002,
                "orientation_error_deg": 0.0,
            },
            previous_action=[0.0] * len(script.ACTION_SCHEMA),
            action_scale=1.0,
        )


def test_v07b_residual_policy_diagnostics_show_base_plus_residual_before_adapter() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    base_config = {
        **script.WEAK_BASE_SERVO_CONFIG,
        "base_servo_id": "frozen_base_geometry_servo_v0_7b",
        "closing_gate": False,
    }
    policy = {
        "policy_id": "candidate_curated_mvp2e_v07b_residual_servo_bc",
        "policy_slice": "v0_7b",
        "policy_class": "phase_conditioned_residual_servo_bc_policy_v0",
        "trainer_family": "phase_conditioned_residual_servo_bc",
        "base_servo_id": "frozen_base_geometry_servo_v0_7b",
        "base_servo_config": base_config,
        "base_servo_config_sha256": script._sha256_payload(base_config),
        "residual_target_definition": "actual_trace_action_minus_frozen_base_geometry_servo_action",
        "feature_schema": script.FEATURE_SCHEMA_V07A,
        "feature_schema_version": script.FEATURE_SCHEMA_V07A_VERSION,
        "behavior_state_phase_input": True,
        "behavior_phase_rule_version": "env_native_hold_v0_7a_2",
        "weights": [[0.0] * len(script.ACTION_SCHEMA) for _ in script.FEATURE_SCHEMA_V07A],
        "bias": [0.001, -0.002, -0.003, 0.0, 0.0, 0.0, 0.0],
        "selected_action_adapter_config": {"action_scale": 1.0},
    }

    _, diagnostics = script._predict_policy_action_with_diagnostics(
        policy,
        metric_row={
            "phase": "INSERT",
            "env_native_success_mask": False,
            "insertion_depth_m": 0.02,
            "relative_x_m": 0.006,
            "relative_y_m": -0.004,
            "lateral_error_m": 0.007,
            "orientation_error_deg": 2.0,
        },
        previous_action=[0.0] * len(script.ACTION_SCHEMA),
        action_scale=1.0,
    )

    base = script.np.asarray(diagnostics["base_servo_action"])
    residual = script.np.asarray(diagnostics["residual_prediction"])
    reconstructed = script.np.asarray(diagnostics["raw_action_before_adapter"])
    assert diagnostics["base_servo_id"] == "frozen_base_geometry_servo_v0_7b"
    assert diagnostics["base_servo_config_sha256"] == script._sha256_payload(base_config)
    assert diagnostics["residual_target_definition"] == (
        "actual_trace_action_minus_frozen_base_geometry_servo_action"
    )
    assert script.np.allclose(base + residual, reconstructed)


def _v07c_authority_config(script: Any, *, filter_id: str = "frozen_residual_action_authority_gate_v0_7c") -> dict[str, Any]:
    config = {
        "schema_version": "rdf_mvp2e_v07c_action_authority_config_v0.1.0",
        "policy_slice": "v0_7c",
        "slice_id": "mvp2e_v07c_residual_action_authority_gate",
        "authority_filter_id": filter_id,
        "base_servo_id": "frozen_base_geometry_servo_v0_7b",
        "base_servo_config_sha256": "filled-below",
        "residual_target_definition": "actual_trace_action_minus_frozen_base_geometry_servo_action",
        "behavior_phase_rule_version": "env_native_hold_v0_7a_2",
        "selected_action_adapter_id": "identity_fixture_adapter",
        "align_z_authority": "base_servo_z_only",
        "descend_z_authority": "base_plus_residual",
        "hold_z_authority": "base_plus_residual",
        "heldout_21000_21049_accessed": False,
        "candidate_specific": False,
        "baseline_specific": False,
    }
    base_config = {
        **script.WEAK_BASE_SERVO_CONFIG,
        "base_servo_id": "frozen_base_geometry_servo_v0_7b",
        "base_servo_source": "weak_base_servo_action_v0_wrapped_for_v0_7b",
        "closing_gate": False,
        "proof_authority": False,
    }
    config["base_servo_config_sha256"] = script._sha256_payload(base_config)
    config["authority_filter_config_sha256"] = script._sha256_payload_excluding(
        config,
        "authority_filter_config_sha256",
    )
    return config


def _v07c_eval_policy(script: Any, *, authority_config: dict[str, Any] | None = None) -> dict[str, Any]:
    base_config = {
        **script.WEAK_BASE_SERVO_CONFIG,
        "base_servo_id": "frozen_base_geometry_servo_v0_7b",
        "base_servo_source": "weak_base_servo_action_v0_wrapped_for_v0_7b",
        "closing_gate": False,
        "proof_authority": False,
    }
    config = authority_config or _v07c_authority_config(script)
    return {
        "policy_id": "candidate_curated_mvp2e_v07c_residual_action_authority_bc",
        "policy_slice": "v0_7c",
        "policy_class": "phase_conditioned_residual_servo_bc_policy_v0",
        "trainer_family": "phase_conditioned_residual_servo_bc",
        "base_servo_id": "frozen_base_geometry_servo_v0_7b",
        "base_servo_config": base_config,
        "base_servo_config_sha256": script._sha256_payload(base_config),
        "residual_target_definition": "actual_trace_action_minus_frozen_base_geometry_servo_action",
        "authority_filter_id": config["authority_filter_id"],
        "authority_filter_config": config,
        "authority_filter_config_sha256": config["authority_filter_config_sha256"],
        "feature_schema": script.FEATURE_SCHEMA_V07A,
        "feature_schema_version": script.FEATURE_SCHEMA_V07A_VERSION,
        "behavior_state_phase_input": True,
        "behavior_phase_rule_version": "env_native_hold_v0_7a_2",
        "weights": [[0.0] * len(script.ACTION_SCHEMA) for _ in script.FEATURE_SCHEMA_V07A],
        "bias": [0.0, 0.0, -0.09, 0.0, 0.0, 0.0, 0.0],
        "selected_action_adapter_id": "identity_fixture_adapter",
        "selected_action_adapter_config": {"adapter_mode": "identity_fixture"},
    }


def _v07d_policy_artifact(
    script: Any,
    *,
    stable_hold_authority: str = "env_native_success_mask",
    include_controller_version: bool = True,
) -> dict[str, Any]:
    base_config = {
        **script.WEAK_BASE_SERVO_CONFIG,
        "base_servo_id": "frozen_base_geometry_servo_v0_7b",
        "base_servo_source": "weak_base_servo_action_v0_wrapped_for_v0_7b",
        "closing_gate": False,
        "proof_authority": False,
    }
    authority_config = _v07c_authority_config(script)
    authority_config["selected_action_adapter_id"] = "isaac_signed_xy_downward_servo_v0"
    authority_config["authority_filter_config_sha256"] = script._sha256_payload_excluding(
        authority_config,
        "authority_filter_config_sha256",
    )
    final_config = {
        "schema_version": "rdf_mvp2e_v07d_final_action_authority_config_v0.1.0",
        "policy_slice": "v0_7d",
        "slice_id": "mvp2e_v07d_action_authority_post_adapter_z_gate",
        "final_post_adapter_authority_id": "final_post_adapter_z_authority_gate_v0_7d",
        "inherited_authority_filter_id": "frozen_residual_action_authority_gate_v0_7c",
        "inherited_authority_filter_config_sha256": authority_config["authority_filter_config_sha256"],
        "selected_action_adapter_id": "isaac_signed_xy_downward_servo_v0",
        "stable_hold_authority": stable_hold_authority,
        "align_final_z_authority": "zero_after_adapter_until_z_motion_allowed",
        "heldout_21000_21049_accessed": False,
        "candidate_specific": False,
        "baseline_specific": False,
    }
    final_config["final_post_adapter_authority_config_sha256"] = script._sha256_payload_excluding(
        final_config,
        "final_post_adapter_authority_config_sha256",
    )
    adapter_config = {
        "xy_action_scale": 1.0,
        "xy_action_clip": 0.05,
        "z_action_scale": 32.0,
        "z_action_clip": 0.16,
        "stable_hold_action": [0.0, 0.0, -0.02, 0.0, 0.0, 0.0, 1.0],
        "stable_hold_depth_m": 0.03,
        "stable_hold_lateral_m": 0.006,
        "stable_hold_orientation_deg": 8.0,
    }
    if include_controller_version:
        adapter_config["controller_version"] = "legacy_no_v06_controller"
    return {
        "policy_id": "candidate_curated_mvp2e_v07d_action_authority_bc",
        "policy_slice": "v0_7d",
        "policy_class": "phase_conditioned_residual_servo_bc_policy_v0",
        "trainer_family": "phase_conditioned_residual_servo_bc",
        "base_servo_id": "frozen_base_geometry_servo_v0_7b",
        "base_servo_config": base_config,
        "base_servo_config_sha256": script._sha256_payload(base_config),
        "residual_target_definition": "actual_trace_action_minus_frozen_base_geometry_servo_action",
        "authority_filter_id": authority_config["authority_filter_id"],
        "authority_filter_config": authority_config,
        "authority_filter_config_sha256": authority_config["authority_filter_config_sha256"],
        "feature_schema": script.FEATURE_SCHEMA_V07A,
        "feature_schema_version": script.FEATURE_SCHEMA_V07A_VERSION,
        "behavior_state_phase_input": True,
        "behavior_phase_rule_version": "env_native_hold_v0_7a_2",
        "weights": [[0.0] * len(script.ACTION_SCHEMA) for _ in script.FEATURE_SCHEMA_V07A],
        "bias": [0.0, 0.0, -0.09, 0.0, 0.0, 0.0, 0.0],
        "selected_action_adapter_id": "isaac_signed_xy_downward_servo_v0",
        "selected_action_adapter_config": adapter_config,
        "selected_action_adapter_config_sha256": script._sha256_payload(adapter_config),
        "stable_hold_authority": stable_hold_authority,
        "final_post_adapter_authority_id": "final_post_adapter_z_authority_gate_v0_7d",
        "final_post_adapter_authority_config": final_config,
        "final_post_adapter_authority_config_sha256": final_config[
            "final_post_adapter_authority_config_sha256"
        ],
    }


def _v07e_hysteresis_authority_config(
    script: Any,
    *,
    parent_policy: dict[str, Any] | None = None,
    candidate_specific: bool = False,
    baseline_specific: bool = False,
    heldout_accessed: bool = False,
) -> dict[str, Any]:
    parent = parent_policy or _v07d_policy_artifact(script)
    config = {
        "schema_version": "rdf_mvp2e_v07e_hysteresis_authority_config_v0.1.0",
        "policy_slice": "v0_7e",
        "parent_policy_slice": "v0_7d",
        "shared_hysteresis_authority_id": "shared_stateful_hysteresis_authority_v0_7e",
        "parent_final_post_adapter_authority_config_sha256": parent[
            "final_post_adapter_authority_config_sha256"
        ],
        "min_descend_window_reference_steps": 28,
        "z_window_hold_steps": 28,
        "same_hysteresis_config_as_peer": True,
        "candidate_specific": candidate_specific,
        "baseline_specific": baseline_specific,
        "heldout_21000_21049_accessed": heldout_accessed,
    }
    config["shared_hysteresis_authority_config_sha256"] = script._sha256_payload_excluding(
        config,
        "shared_hysteresis_authority_config_sha256",
    )
    return config


def _v07e_policy_artifact(script: Any, *, role: str = "candidate") -> dict[str, Any]:
    policy = _v07d_policy_artifact(script)
    hysteresis_config = _v07e_hysteresis_authority_config(script, parent_policy=policy)
    policy.update(
        {
            "policy_id": f"{role}_mvp2e_v07e_shared_hysteresis_parity_policy",
            "policy_slice": "v0_7e",
            "parent_policy_slice": "v0_7d",
            "shared_hysteresis_authority_id": hysteresis_config["shared_hysteresis_authority_id"],
            "shared_hysteresis_authority_config": hysteresis_config,
            "shared_hysteresis_authority_config_sha256": hysteresis_config[
                "shared_hysteresis_authority_config_sha256"
            ],
            "same_hysteresis_config_as_peer": True,
        }
    )
    return policy


def _v07g_xy_authority_config(
    script: Any,
    *,
    parent_policy: dict[str, Any] | None = None,
    candidate_specific: bool = False,
    baseline_specific: bool = False,
    heldout_accessed: bool = False,
) -> dict[str, Any]:
    parent = parent_policy or _v07e_policy_artifact(script)
    config = {
        "schema_version": "rdf_mvp2e_v07g_xy_authority_config_v0.1.0",
        "policy_slice": "v0_7g",
        "parent_policy_slice": "v0_7e",
        "slice_id": "mvp2e_v07g_xy_authority_saturation_repair",
        "final_post_adapter_xy_authority_id": "final_post_adapter_xy_authority_gate_v0_7g",
        "parent_shared_hysteresis_authority_config_sha256": parent[
            "shared_hysteresis_authority_config_sha256"
        ],
        "parent_final_post_adapter_authority_config_sha256": parent[
            "final_post_adapter_authority_config_sha256"
        ],
        "selected_action_adapter_id": "isaac_signed_xy_downward_servo_v0",
        "stable_hold_authority": "env_native_success_mask",
        "xy_authority_strategy": "post_adapter_state_feedback_clip",
        "xy_authority_axis_scope": ["x", "y"],
        "xy_authority_gain": 4.0,
        "xy_authority_clip_abs": 0.02,
        "xy_saturation_threshold_abs": 0.049,
        "xy_near_center_lateral_m": 0.006,
        "same_xy_authority_config_as_peer": True,
        "candidate_specific": candidate_specific,
        "baseline_specific": baseline_specific,
        "heldout_21000_21049_accessed": heldout_accessed,
    }
    config["final_post_adapter_xy_authority_config_sha256"] = script._sha256_payload_excluding(
        config,
        "final_post_adapter_xy_authority_config_sha256",
    )
    return config


def _v07g_policy_artifact(script: Any, *, role: str = "candidate") -> dict[str, Any]:
    policy = _v07e_policy_artifact(script, role=role)
    xy_authority_config = _v07g_xy_authority_config(script, parent_policy=policy)
    policy.update(
        {
            "policy_id": f"{role}_mvp2e_v07g_xy_authority_saturation_repair_policy",
            "policy_slice": "v0_7g",
            "parent_policy_slice": "v0_7e",
            "final_post_adapter_xy_authority_id": xy_authority_config[
                "final_post_adapter_xy_authority_id"
            ],
            "final_post_adapter_xy_authority_config": xy_authority_config,
            "final_post_adapter_xy_authority_config_sha256": xy_authority_config[
                "final_post_adapter_xy_authority_config_sha256"
            ],
            "same_xy_authority_config_as_peer": True,
        }
    )
    return policy


def _v07j_xy_authority_config(script: Any, *, parent_policy: dict[str, Any] | None = None) -> dict[str, Any]:
    parent = parent_policy or _v07g_policy_artifact(script)
    config = {
        "schema_version": "rdf_mvp2e_v07j_xy_authority_config_v0.1.0",
        "policy_slice": "v0_7j",
        "parent_policy_slice": "v0_7g",
        "slice_id": "mvp2e_v07j_off_center_xy_authority_repair",
        "final_post_adapter_xy_authority_id": "final_post_adapter_xy_authority_gate_v0_7j",
        "parent_xy_authority_config_sha256": parent["final_post_adapter_xy_authority_config_sha256"],
        "parent_shared_hysteresis_authority_config_sha256": parent[
            "shared_hysteresis_authority_config_sha256"
        ],
        "parent_final_post_adapter_authority_config_sha256": parent[
            "final_post_adapter_authority_config_sha256"
        ],
        "selected_action_adapter_id": "isaac_signed_xy_downward_servo_v0",
        "stable_hold_authority": "env_native_success_mask",
        "xy_authority_strategy": "piecewise_off_center_state_feedback_clip",
        "xy_authority_axis_scope": ["x", "y"],
        "xy_authority_gain": 4.0,
        "xy_near_center_clip_abs": 0.02,
        "xy_off_center_clip_abs": 0.05,
        "xy_saturation_threshold_abs": 0.049,
        "xy_near_center_lateral_m": 0.006,
        "same_xy_authority_config_as_peer": True,
        "candidate_specific": False,
        "baseline_specific": False,
        "heldout_21000_21049_accessed": False,
    }
    config["final_post_adapter_xy_authority_config_sha256"] = script._sha256_payload_excluding(
        config,
        "final_post_adapter_xy_authority_config_sha256",
    )
    return config


def _v07j_policy_artifact(script: Any, *, role: str = "candidate") -> dict[str, Any]:
    policy = _v07g_policy_artifact(script, role=role)
    xy_authority_config = _v07j_xy_authority_config(script, parent_policy=policy)
    policy.update(
        {
            "policy_id": f"{role}_mvp2e_v07j_off_center_xy_authority_repair_policy",
            "policy_slice": "v0_7j",
            "parent_policy_slice": "v0_7g",
            "final_post_adapter_xy_authority_id": xy_authority_config[
                "final_post_adapter_xy_authority_id"
            ],
            "final_post_adapter_xy_authority_config": xy_authority_config,
            "final_post_adapter_xy_authority_config_sha256": xy_authority_config[
                "final_post_adapter_xy_authority_config_sha256"
            ],
            "same_xy_authority_config_as_peer": True,
        }
    )
    return policy


def test_v07j_runtime_applies_piecewise_xy_authority_off_center() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    policy = _v07j_policy_artifact(script)

    action, diagnostics = script._apply_selected_action_adapter_with_diagnostics(
        policy_artifact=policy,
        raw_action=script.np.array([-0.05, 0.05, -0.001, 0.0, 0.0, 0.0, 1.0]),
        action_scale=1.0,
        metric_row={
            "phase": "APPROACH",
            "behavior_state_phase": "DESCEND",
            "lateral_error_m": 0.017,
            "relative_x_m": 0.003,
            "relative_y_m": -0.017,
            "orientation_error_deg": 0.0,
            "insertion_depth_m": 0.0,
            "env_native_success": False,
        },
        behavior_state_phase="DESCEND",
        hysteresis_state={
            "current_hysteresis_phase": "DESCEND",
            "last_z_motion_allowed": True,
        },
    )

    assert diagnostics["final_post_adapter_xy_authority_id"] == "final_post_adapter_xy_authority_gate_v0_7j"
    assert diagnostics["xy_authority_applied"] is True
    assert diagnostics["xy_authority_reason"] == "xy_saturation_off_center_state_feedback_clamped"
    assert diagnostics["xy_authority_zone"] == "off_center"
    assert action.tolist()[:2] == pytest.approx([-0.012, 0.05])
    assert action.tolist()[2] == pytest.approx(diagnostics["post_z_pre_xy_authority_action_vector"][2])


def test_v07j_runtime_keeps_near_center_clip_abs_from_v07g() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    policy = _v07j_policy_artifact(script)

    action, diagnostics = script._apply_selected_action_adapter_with_diagnostics(
        policy_artifact=policy,
        raw_action=script.np.array([0.05, -0.05, -0.001, 0.0, 0.0, 0.0, 1.0]),
        action_scale=1.0,
        metric_row={
            "phase": "APPROACH",
            "behavior_state_phase": "DESCEND",
            "lateral_error_m": 0.0007,
            "relative_x_m": -0.0005,
            "relative_y_m": 0.0005,
            "orientation_error_deg": 0.0,
            "insertion_depth_m": 0.0,
            "env_native_success": False,
        },
        behavior_state_phase="DESCEND",
        hysteresis_state={
            "current_hysteresis_phase": "DESCEND",
            "last_z_motion_allowed": True,
        },
    )

    assert diagnostics["xy_authority_applied"] is True
    assert diagnostics["xy_authority_zone"] == "near_center"
    assert abs(action.tolist()[0]) <= 0.02


def _v07k_policy_artifact(script: Any, *, role: str = "candidate") -> dict[str, Any]:
    policy = _v07j_policy_artifact(script, role=role)
    policy.update(
        {
            "policy_id": f"{role}_mvp2e_v07k_runtime_hysteresis_wiring_repair_policy",
            "policy_slice": "v0_7k",
            "slice_id": "mvp2e_v07k_runtime_hysteresis_wiring_repair",
            "parent_policy_slice": "v0_7j",
            "runtime_hysteresis_wiring_repair_id": "runtime_hysteresis_wiring_repair_v0_7k",
        }
    )
    return policy


def _v07m_policy_artifact(script: Any, *, role: str = "candidate") -> dict[str, Any]:
    policy = _v07k_policy_artifact(script, role=role)
    parent_hysteresis_sha = policy["shared_hysteresis_authority_config_sha256"]
    hysteresis_config = dict(policy["shared_hysteresis_authority_config"])
    hysteresis_config.update(
        {
            "schema_version": "rdf_mvp2e_v07m_hysteresis_authority_config_v0.1.0",
            "policy_slice": "v0_7m",
            "slice_id": "mvp2e_v07m_z_window_progress_authority_repair",
            "parent_policy_slice": "v0_7k",
            "parent_shared_hysteresis_authority_config_sha256": parent_hysteresis_sha,
            "z_window_hold_steps": 70,
            "z_window_realign_lateral_m": 0.006,
        }
    )
    hysteresis_config["shared_hysteresis_authority_config_sha256"] = script._sha256_payload_excluding(
        hysteresis_config,
        "shared_hysteresis_authority_config_sha256",
    )
    policy.update(
        {
            "policy_id": f"{role}_mvp2e_v07m_z_window_progress_authority_repair_policy",
            "policy_slice": "v0_7m",
            "slice_id": "mvp2e_v07m_z_window_progress_authority_repair",
            "parent_policy_slice": "v0_7k",
            "z_window_progress_authority_repair_id": "z_window_progress_authority_repair_v0_7m",
            "parent_shared_hysteresis_authority_config_sha256": parent_hysteresis_sha,
            "shared_hysteresis_authority_config": hysteresis_config,
            "shared_hysteresis_authority_config_sha256": hysteresis_config[
                "shared_hysteresis_authority_config_sha256"
            ],
            "same_hysteresis_config_as_peer": True,
        }
    )
    return policy


def _v07n_policy_artifact(script: Any, *, role: str = "candidate") -> dict[str, Any]:
    policy = _v07m_policy_artifact(script, role=role)
    parent_xy_sha = policy["final_post_adapter_xy_authority_config_sha256"]
    xy_config = dict(policy["final_post_adapter_xy_authority_config"])
    xy_config.update(
        {
            "schema_version": "rdf_mvp2e_v07n_xy_authority_config_v0.1.0",
            "policy_slice": "v0_7n",
            "parent_policy_slice": "v0_7m",
            "slice_id": "mvp2e_v07n_z_open_xy_center_maintenance",
            "final_post_adapter_xy_authority_id": "final_post_adapter_xy_authority_gate_v0_7n",
            "parent_xy_authority_config_sha256": parent_xy_sha,
            "parent_shared_hysteresis_authority_config_sha256": policy[
                "shared_hysteresis_authority_config_sha256"
            ],
            "xy_authority_strategy": "z_open_center_maintenance_state_feedback_clip",
            "z_open_centering_depth_max_m": 0.001,
            "z_open_centering_lateral_m": 0.006,
            "z_open_xy_authority_gain": 4.0,
            "z_open_xy_clip_abs": 0.05,
            "allow_sign_flip_during_z_open_low_depth": True,
        }
    )
    xy_config["final_post_adapter_xy_authority_config_sha256"] = script._sha256_payload_excluding(
        xy_config,
        "final_post_adapter_xy_authority_config_sha256",
    )
    policy.update(
        {
            "policy_id": f"{role}_mvp2e_v07n_z_open_xy_center_maintenance_policy",
            "policy_slice": "v0_7n",
            "slice_id": "mvp2e_v07n_z_open_xy_center_maintenance",
            "parent_policy_slice": "v0_7m",
            "z_open_xy_center_maintenance_repair_id": "z_open_xy_center_maintenance_repair_v0_7n",
            "parent_xy_authority_config_sha256": parent_xy_sha,
            "final_post_adapter_xy_authority_id": xy_config["final_post_adapter_xy_authority_id"],
            "final_post_adapter_xy_authority_config": xy_config,
            "final_post_adapter_xy_authority_config_sha256": xy_config[
                "final_post_adapter_xy_authority_config_sha256"
            ],
            "same_xy_authority_config_as_peer": True,
        }
    )
    return policy


def _v07o_policy_artifact(script: Any, *, role: str = "candidate") -> dict[str, Any]:
    policy = _v07n_policy_artifact(script, role=role)
    parent_xy_sha = policy["final_post_adapter_xy_authority_config_sha256"]
    xy_config = dict(policy["final_post_adapter_xy_authority_config"])
    xy_config.update(
        {
            "schema_version": "rdf_mvp2e_v07o_xy_authority_config_v0.1.0",
            "policy_slice": "v0_7o",
            "parent_policy_slice": "v0_7n",
            "slice_id": "mvp2e_v07o_composed_xy_authority",
            "final_post_adapter_xy_authority_id": "final_post_adapter_xy_authority_gate_v0_7o",
            "parent_xy_authority_config_sha256": parent_xy_sha,
            "xy_authority_strategy": "composed_piecewise_plus_z_open_center_maintenance",
        }
    )
    xy_config["final_post_adapter_xy_authority_config_sha256"] = script._sha256_payload_excluding(
        xy_config,
        "final_post_adapter_xy_authority_config_sha256",
    )
    policy.update(
        {
            "policy_id": f"{role}_mvp2e_v07o_composed_xy_authority_policy",
            "policy_slice": "v0_7o",
            "slice_id": "mvp2e_v07o_composed_xy_authority",
            "parent_policy_slice": "v0_7n",
            "composed_xy_authority_repair_id": "composed_xy_authority_repair_v0_7o",
            "parent_xy_authority_config_sha256": parent_xy_sha,
            "final_post_adapter_xy_authority_id": xy_config["final_post_adapter_xy_authority_id"],
            "final_post_adapter_xy_authority_config": xy_config,
            "final_post_adapter_xy_authority_config_sha256": xy_config[
                "final_post_adapter_xy_authority_config_sha256"
            ],
            "same_xy_authority_config_as_peer": True,
        }
    )
    return policy


def _v08a_seat_window_config(script: Any) -> dict[str, Any]:
    config = {
        "schema_version": "rdf_mvp2e_v08a_seat_window_authority_config_v0.1.0",
        "seat_window_authority_id": "seat_window_progress_authority_v0_8a",
        "policy_slice": "v0_8a",
        "parent_policy_slice": "v0_7o",
        "slice_id": "mvp2e_v08a_fresh_seat_window_authority",
        "latest_z_open_step": 81,
        "z_open_centering_lateral_m": 0.006,
        "seat_region_depth_m": 0.024,
        "z_progress_action": -0.16,
        "candidate_specific": False,
        "baseline_specific": False,
        "proof_authority": False,
        "fresh_calibration_seed_range": [23000, 23029],
        "fresh_heldout_seed_range": [24000, 24049],
        "burned_heldout_seed_range": [21000, 21049],
    }
    config["seat_window_authority_config_sha256"] = script._sha256_payload_excluding(
        config,
        "seat_window_authority_config_sha256",
    )
    return config


def _v08a_policy_artifact(script: Any, *, role: str = "candidate") -> dict[str, Any]:
    policy = _v07o_policy_artifact(script, role=role)
    config = _v08a_seat_window_config(script)
    policy.update(
        {
            "policy_id": f"{role}_mvp2e_v08a_fresh_seat_window_authority_policy",
            "policy_slice": "v0_8a",
            "slice_id": "mvp2e_v08a_fresh_seat_window_authority",
            "parent_policy_slice": "v0_7o",
            "seat_window_authority_id": config["seat_window_authority_id"],
            "seat_window_authority_config": config,
            "seat_window_authority_config_sha256": config["seat_window_authority_config_sha256"],
            "same_seat_window_authority_config_as_peer": True,
            "source_diagnostic_heldout_21000_21049_accessed": True,
            "fresh_heldout_24000_24049_accessed": False,
        }
    )
    return policy


def _v08b_seat_window_config(script: Any) -> dict[str, Any]:
    config = {
        "schema_version": "rdf_mvp2e_v08b_scenario_aware_seat_window_authority_config_v0.1.0",
        "seat_window_authority_id": "scenario_aware_seat_window_authority_v0_8b",
        "policy_slice": "v0_8b",
        "parent_policy_slice": "v0_8a",
        "slice_id": "mvp2e_v08b_scenario_aware_seat_window_authority",
        "latest_z_open_step_train_max": 81,
        "scenario_aware_deadline_step": 74,
        "seat_window_required_steps": 10,
        "terminal_guard_steps": 2,
        "descent_latency_steps_p95": 57,
        "scenario_aware_deadline_formula": (
            "max_steps_minus_stable_window_minus_terminal_guard_minus_descent_latency_p95"
        ),
        "z_open_centering_lateral_m": 0.006,
        "seat_region_depth_m": 0.024,
        "z_progress_action": -0.16,
        "candidate_specific": False,
        "baseline_specific": False,
        "proof_authority": False,
        "fresh_calibration_seed_range": [25000, 25029],
        "fresh_heldout_seed_range": [26000, 26049],
        "burned_heldout_seed_ranges": [[21000, 21049], [24000, 24049]],
        "heldout_24000_24049_used_for_parameter_derivation": False,
    }
    config["seat_window_authority_config_sha256"] = script._sha256_payload_excluding(
        config,
        "seat_window_authority_config_sha256",
    )
    return config


def _v08b_policy_artifact(script: Any, *, role: str = "candidate") -> dict[str, Any]:
    policy = _v08a_policy_artifact(script, role=role)
    config = _v08b_seat_window_config(script)
    policy.update(
        {
            "policy_id": f"{role}_mvp2e_v08b_scenario_aware_seat_window_authority_policy",
            "policy_slice": "v0_8b",
            "slice_id": "mvp2e_v08b_scenario_aware_seat_window_authority",
            "parent_policy_slice": "v0_8a",
            "seat_window_authority_id": config["seat_window_authority_id"],
            "seat_window_authority_config": config,
            "seat_window_authority_config_sha256": config["seat_window_authority_config_sha256"],
            "same_seat_window_authority_config_as_peer": True,
            "source_diagnostic_heldout_24000_24049_accessed": True,
            "fresh_heldout_26000_26049_accessed": False,
        }
    )
    return policy


def _v08d_capture_conditioned_progress_config(script: Any) -> dict[str, Any]:
    config = {
        "schema_version": "rdf_mvp2e_v08d_capture_conditioned_progress_authority_config_v0.1.0",
        "capture_conditioned_progress_authority_id": "capture_conditioned_progress_authority_v0_8d",
        "policy_slice": "v0_8d",
        "parent_policy_slice": "v0_8b",
        "slice_id": "mvp2e_v08d_capture_conditioned_progress_authority",
        "source_v08c_shortfall_diagnosis_sha256": "fake-v08c-diagnosis-sha",
        "parent_v08b_seat_window_authority_config_sha256": "fake-v08b-seat-window-config-sha",
        "early_z_deadline_step": 68,
        "capture_prepare_start_step": 56,
        "capture_lateral_gate_m": 0.0035,
        "seat_region_depth_m": 0.024,
        "z_progress_action": -0.16,
        "depth_progress_window_steps": 12,
        "minimum_depth_progress_m": 0.001,
        "under_depth_progress_threshold_m": 0.024,
        "candidate_specific": False,
        "baseline_specific": False,
        "proof_authority": False,
        "fresh_calibration_seed_range": [26500, 26529],
        "fresh_heldout_seed_range": [27000, 27049],
        "burned_heldout_seed_ranges": [[21000, 21049], [24000, 24049], [26000, 26049]],
        "forbidden_mechanisms": ["retry", "withdraw", "search", "force_control"],
    }
    config["capture_conditioned_progress_authority_config_sha256"] = script._sha256_payload_excluding(
        config,
        "capture_conditioned_progress_authority_config_sha256",
    )
    return config


def _v08d_policy_artifact(script: Any, *, role: str = "candidate") -> dict[str, Any]:
    policy = _v08b_policy_artifact(script, role=role)
    config = _v08d_capture_conditioned_progress_config(script)
    policy.update(
        {
            "policy_id": f"{role}_mvp2e_v08d_capture_conditioned_progress_authority_policy",
            "policy_slice": "v0_8d",
            "slice_id": "mvp2e_v08d_capture_conditioned_progress_authority",
            "parent_policy_slice": "v0_8b",
            "capture_conditioned_progress_authority_id": config[
                "capture_conditioned_progress_authority_id"
            ],
            "capture_conditioned_progress_authority_config": config,
            "capture_conditioned_progress_authority_config_sha256": config[
                "capture_conditioned_progress_authority_config_sha256"
            ],
            "same_capture_conditioned_progress_authority_config_as_peer": True,
            "fresh_heldout_27000_27049_accessed": False,
        }
    )
    return policy


def _v08f_horizon_reserved_capture_config(script: Any) -> dict[str, Any]:
    parent_config = _v08d_capture_conditioned_progress_config(script)
    config = {
        "schema_version": "rdf_mvp2e_v08f_horizon_reserved_capture_authority_config_v0.1.0",
        "horizon_reserved_capture_authority_id": "horizon_reserved_capture_authority_v0_8f",
        "policy_slice": "v0_8f",
        "parent_policy_slice": "v0_8d",
        "source_policy_slice": "v0_8e",
        "slice_id": "mvp2e_v08f_horizon_reserved_capture_authority",
        "source_v08e_calibration_shortfall_diagnosis_sha256": "fake-v08e-diagnosis-sha",
        "parent_v08d_capture_conditioned_progress_authority_config_sha256": parent_config[
            "capture_conditioned_progress_authority_config_sha256"
        ],
        "capture_prepare_start_step": 56,
        "horizon_reserved_z_deadline_step": 68,
        "capture_lateral_gate_m": 0.0035,
        "capture_wait_xy_authority_enabled": True,
        "capture_wait_xy_authority_gain": 4.0,
        "capture_wait_xy_clip_abs": 0.05,
        "capture_wait_sign_flip_allowed": True,
        "seat_completion_until_env_native_success": True,
        "seat_region_depth_m": 0.024,
        "z_progress_action": -0.16,
        "candidate_specific": False,
        "baseline_specific": False,
        "proof_authority": False,
        "fresh_calibration_seed_range": [27500, 27529],
        "fresh_heldout_seed_range": [27000, 27049],
        "burned_heldout_seed_ranges": [[21000, 21049], [24000, 24049], [26000, 26049]],
        "burned_calibration_seed_ranges": [[26500, 26529]],
        "forbidden_mechanisms": ["retry", "withdraw", "search", "force_control"],
        "fresh_heldout_27000_27049_accessed": False,
    }
    config["horizon_reserved_capture_authority_config_sha256"] = script._sha256_payload_excluding(
        config,
        "horizon_reserved_capture_authority_config_sha256",
    )
    return config


def _v08f_policy_artifact(script: Any, *, role: str = "candidate") -> dict[str, Any]:
    policy = _v08d_policy_artifact(script, role=role)
    config = _v08f_horizon_reserved_capture_config(script)
    policy.update(
        {
            "policy_id": f"{role}_mvp2e_v08f_horizon_reserved_capture_authority_policy",
            "policy_slice": "v0_8f",
            "slice_id": "mvp2e_v08f_horizon_reserved_capture_authority",
            "parent_policy_slice": "v0_8d",
            "horizon_reserved_capture_authority_id": config[
                "horizon_reserved_capture_authority_id"
            ],
            "horizon_reserved_capture_authority_config": config,
            "horizon_reserved_capture_authority_config_sha256": config[
                "horizon_reserved_capture_authority_config_sha256"
            ],
            "same_horizon_reserved_capture_authority_config_as_peer": True,
            "fresh_calibration_27500_27529_accessed": False,
            "fresh_heldout_27000_27049_accessed": False,
        }
    )
    return policy


def _v08g_deadline_precedence_config(script: Any) -> dict[str, Any]:
    parent_config = _v08f_horizon_reserved_capture_config(script)
    config = {
        "schema_version": "rdf_mvp2e_v08g_deadline_precedence_horizon_authority_config_v0.1.0",
        "deadline_precedence_horizon_authority_id": "deadline_precedence_horizon_authority_v0_8g",
        "policy_slice": "v0_8g",
        "parent_policy_slice": "v0_8f",
        "source_policy_slice": "v0_8f",
        "slice_id": "mvp2e_v08g_deadline_precedence_horizon_authority",
        "source_v08f_calibration_presignal_gate_sha256": "fake-v08f-calibration-sha",
        "parent_v08f_horizon_reserved_capture_authority_config_sha256": parent_config[
            "horizon_reserved_capture_authority_config_sha256"
        ],
        "capture_prepare_start_step": 56,
        "horizon_reserved_z_deadline_step": 68,
        "capture_lateral_gate_m": 0.0035,
        "capture_wait_xy_authority_enabled": True,
        "capture_wait_xy_authority_gain": 4.0,
        "capture_wait_xy_clip_abs": 0.05,
        "capture_wait_sign_flip_allowed": True,
        "deadline_precedence_over_capture_wait": True,
        "seat_completion_until_env_native_success": True,
        "seat_region_depth_m": 0.024,
        "z_progress_action": -0.16,
        "candidate_specific": False,
        "baseline_specific": False,
        "proof_authority": False,
        "fresh_calibration_seed_range": [28000, 28029],
        "fresh_heldout_seed_range": [27000, 27049],
        "burned_heldout_seed_ranges": [[21000, 21049], [24000, 24049], [26000, 26049]],
        "burned_calibration_seed_ranges": [[26500, 26529], [27500, 27529]],
        "forbidden_mechanisms": ["retry", "withdraw", "search", "force_control"],
        "fresh_heldout_27000_27049_accessed": False,
    }
    config["deadline_precedence_horizon_authority_config_sha256"] = script._sha256_payload_excluding(
        config,
        "deadline_precedence_horizon_authority_config_sha256",
    )
    return config


def _v08g_policy_artifact(script: Any, *, role: str = "candidate") -> dict[str, Any]:
    policy = _v08f_policy_artifact(script, role=role)
    config = _v08g_deadline_precedence_config(script)
    policy.update(
        {
            "policy_id": f"{role}_mvp2e_v08g_deadline_precedence_horizon_authority_policy",
            "policy_slice": "v0_8g",
            "slice_id": "mvp2e_v08g_deadline_precedence_horizon_authority",
            "parent_policy_slice": "v0_8f",
            "deadline_precedence_horizon_authority_id": config[
                "deadline_precedence_horizon_authority_id"
            ],
            "deadline_precedence_horizon_authority_config": config,
            "deadline_precedence_horizon_authority_config_sha256": config[
                "deadline_precedence_horizon_authority_config_sha256"
            ],
            "same_deadline_precedence_horizon_authority_config_as_peer": True,
            "fresh_calibration_28000_28029_accessed": False,
            "fresh_heldout_27000_27049_accessed": False,
        }
    )
    return policy


def _v08h_safe_entry_config(script: Any) -> dict[str, Any]:
    parent_config = _v08g_deadline_precedence_config(script)
    config = {
        "schema_version": "rdf_mvp2e_v08h_early_centered_z_open_safe_entry_config_v0.1.0",
        "early_centered_z_open_safe_entry_authority_id": (
            "early_centered_z_open_safe_entry_authority_v0_8h"
        ),
        "policy_slice": "v0_8h",
        "parent_policy_slice": "v0_8g",
        "source_policy_slice": "v0_8g",
        "slice_id": "mvp2e_v08h_early_centered_z_open_safe_entry",
        "source_v08g_calibration_presignal_gate_sha256": "fake-v08g-calibration-sha",
        "parent_v08g_deadline_precedence_horizon_authority_config_sha256": parent_config[
            "deadline_precedence_horizon_authority_config_sha256"
        ],
        "capture_prepare_start_step": 56,
        "reference_deadline_step": 68,
        "safe_entry_lateral_gate_m": 0.005,
        "depth_progress_continuation_lateral_gate_m": 0.006,
        "capture_wait_xy_authority_enabled": True,
        "capture_wait_xy_authority_gain": 4.0,
        "capture_wait_xy_clip_abs": 0.05,
        "capture_wait_sign_flip_allowed": True,
        "unsafe_lateral_z_block_after_reference_deadline": True,
        "early_centered_z_open_enabled": True,
        "depth_progress_continuation_enabled": True,
        "seat_completion_until_env_native_success": True,
        "seat_region_depth_m": 0.024,
        "z_progress_action": -0.16,
        "candidate_specific": False,
        "baseline_specific": False,
        "proof_authority": False,
        "fresh_calibration_seed_range": [28500, 28529],
        "fresh_heldout_seed_range": [27000, 27049],
        "burned_heldout_seed_ranges": [[21000, 21049], [24000, 24049], [26000, 26049]],
        "burned_calibration_seed_ranges": [[26500, 26529], [27500, 27529], [28000, 28029]],
        "forbidden_mechanisms": ["retry", "withdraw", "search", "force_control"],
        "fresh_heldout_27000_27049_accessed": False,
    }
    config["early_centered_z_open_safe_entry_config_sha256"] = script._sha256_payload_excluding(
        config,
        "early_centered_z_open_safe_entry_config_sha256",
    )
    return config


def _v08h_policy_artifact(script: Any, *, role: str = "candidate") -> dict[str, Any]:
    policy = _v08g_policy_artifact(script, role=role)
    config = _v08h_safe_entry_config(script)
    policy.update(
        {
            "policy_id": f"{role}_mvp2e_v08h_early_centered_z_open_safe_entry_policy",
            "policy_slice": "v0_8h",
            "slice_id": "mvp2e_v08h_early_centered_z_open_safe_entry",
            "parent_policy_slice": "v0_8g",
            "early_centered_z_open_safe_entry_authority_id": config[
                "early_centered_z_open_safe_entry_authority_id"
            ],
            "early_centered_z_open_safe_entry_config": config,
            "early_centered_z_open_safe_entry_config_sha256": config[
                "early_centered_z_open_safe_entry_config_sha256"
            ],
            "same_early_centered_z_open_safe_entry_config_as_peer": True,
            "fresh_calibration_28500_28529_accessed": False,
            "fresh_heldout_27000_27049_accessed": False,
        }
    )
    return policy


def _v13_policy_artifact(script: Any, *, role: str = "candidate") -> dict[str, Any]:
    policy = _v07e_policy_artifact(script, role=role)
    adapter_config = dict(policy["selected_action_adapter_config"])
    adapter_config.update(
        {
            "xy_source": "policy_plus_state_feedback",
            "xy_state_feedback_gain": 0.5,
            "xy_action_scale": 1.0,
            "xy_action_clip": 0.05,
            "z_action_clip": 0.16,
            "policy_influence_authority_ceiling_id": "policy_influence_authority_ceiling_v0_13",
        }
    )
    policy_influence_config = {
        "schema_version": "rdf_mvp2e_v13_policy_influence_authority_ceiling_config_v0.1.0",
        "policy_slice": "v0_13",
        "authority_id": "policy_influence_authority_ceiling_v0_13",
        "source_policy_slice": "v0_12",
        "state_feedback_gain_ceiling": 0.5,
        "xy_action_clip": 0.05,
        "z_action_clip": 0.16,
        "z_progress_injection_enabled": False,
        "final_xy_state_feedback_replacement_enabled": False,
        "min_post_adapter_delta_retention_ratio": 0.35,
        "max_post_adapter_identical_fraction": 0.50,
        "same_config_for_baseline_and_candidate": True,
        "heldout_excluded": True,
    }
    policy_influence_config["policy_influence_authority_ceiling_config_sha256"] = script._sha256_payload_excluding(
        policy_influence_config,
        "policy_influence_authority_ceiling_config_sha256",
    )
    policy.update(
        {
            "policy_id": f"{role}_mvp2e_v13_policy_influence_authority_ceiling_policy",
            "policy_slice": "v0_13",
            "slice_id": "mvp2e_v13_policy_influence_authority_ceiling_slice",
            "parent_policy_slice": "v0_12",
            "source_policy_slice": "v0_12a",
            "selected_action_adapter_config": adapter_config,
            "selected_action_adapter_config_sha256": script._sha256_payload(adapter_config),
            "policy_influence_authority_ceiling_id": policy_influence_config["authority_id"],
            "policy_influence_authority_ceiling_config": policy_influence_config,
            "policy_influence_authority_ceiling_config_sha256": policy_influence_config[
                "policy_influence_authority_ceiling_config_sha256"
            ],
            "z_progress_injection_enabled": False,
            "final_xy_state_feedback_replacement_enabled": False,
        }
    )
    policy.pop("early_centered_z_open_safe_entry_config", None)
    policy.pop("early_centered_z_open_safe_entry_config_sha256", None)
    policy.pop("early_centered_z_open_safe_entry_authority_id", None)
    return policy


def _v08k_policy_artifact(script: Any, *, role: str = "candidate") -> dict[str, Any]:
    policy = _v08h_policy_artifact(script, role=role)
    policy.update(
        {
            "policy_id": f"{role}_mvp2e_v08k_candidate_training_signal_rebalance_policy",
            "policy_slice": "v0_8k",
            "slice_id": "mvp2e_v08k_candidate_training_signal_rebalance",
            "parent_policy_slice": "v0_8h",
            "source_policy_slice": "v0_8h",
            "candidate_training_signal_rebalance_id": "candidate_training_signal_rebalance_v0_8k",
            "fresh_calibration_seed_range": [29000, 29029],
            "fresh_heldout_seed_range": [27000, 27049],
            "fresh_heldout_27000_27049_accessed": False,
        }
    )
    return policy


def _v09_policy_artifact(script: Any, *, role: str = "candidate") -> dict[str, Any]:
    policy = _v08k_policy_artifact(script, role=role)
    policy.update(
        {
            "policy_id": f"{role}_mvp2e_v09_fresh_uncurated_mix_rebase_policy",
            "policy_slice": "v0_9",
            "slice_id": "mvp2e_v09_fresh_attribution_preserving_uncurated_mix_rebase",
            "parent_policy_slice": "v0_8k",
            "source_policy_slice": "v0_8k",
            "uncurated_mix_config_sha256": "same_uncurated_mix_sha",
            "fresh_calibration_seed_range": [30000, 30029],
            "fresh_heldout_seed_range": [27000, 27049],
            "fresh_calibration_30000_30029_accessed": False,
            "fresh_heldout_27000_27049_accessed": False,
        }
    )
    return policy


def test_v08d_capture_conditioning_blocks_z_when_off_center() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    config = _v08d_capture_conditioned_progress_config(script)

    action, diagnostics = script._apply_v08d_capture_conditioned_progress_authority(
        action=script.np.asarray([0.01, -0.01, -0.16, 0.0, 0.0, 0.0, 1.0]),
        metric_row={
            "step": 60,
            "lateral_error_m": 0.0041,
            "insertion_depth_m": 0.0,
            "env_native_success": False,
        },
        config=config,
    )

    assert action.tolist()[2] == 0.0
    assert diagnostics["capture_conditioned_progress_authority_id"] == (
        "capture_conditioned_progress_authority_v0_8d"
    )
    assert diagnostics["capture_conditioning_applied"] is True
    assert diagnostics["capture_conditioning_reason"] == "capture_conditioning_wait"
    assert diagnostics["effective_z_open_for_xy_authority"] is False


def test_v08d_forces_z_at_early_deadline_and_records_depth_watch() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    policy = _v08d_policy_artifact(script)

    action, diagnostics = script._predict_policy_action_with_diagnostics(
        policy,
        metric_row={
            "step": 68,
            "behavior_state_phase": "ALIGN",
            "relative_x_m": -0.0003,
            "relative_y_m": 0.0001,
            "lateral_error_m": 0.00032,
            "insertion_depth_m": 0.0004,
            "orientation_error_deg": 0.0,
            "env_native_success": False,
            "z_open_step": 56,
            "z_open_depth_reference_m": 0.0,
        },
        previous_action=[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
        action_scale=1.0,
        hysteresis_state={"current_hysteresis_phase": "ALIGN", "last_z_motion_allowed": False},
    )

    assert action.tolist()[2] == -0.16
    assert diagnostics["capture_conditioning_applied"] is True
    assert diagnostics["capture_conditioning_reason"] == "forced_capture_conditioned_progress_z"
    assert diagnostics["early_z_deadline_step"] == 68
    assert diagnostics["z_open_step"] == 56
    assert diagnostics["depth_progress_window_steps"] == 12
    assert diagnostics["depth_progress_delta_m"] == 0.0004
    assert diagnostics["under_depth_progress_watch"] is True
    assert diagnostics["effective_z_open_for_xy_authority"] is True
    assert diagnostics["capture_conditioned_xy_recomputed_with_forced_z"] is True


def test_v08f_capture_wait_xy_override_blocks_z_and_recomputes_xy() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    policy = _v08f_policy_artifact(script)

    action, diagnostics = script._predict_policy_action_with_diagnostics(
        policy,
        metric_row={
            "step": 60,
            "behavior_state_phase": "ALIGN",
            "relative_x_m": 0.006,
            "relative_y_m": -0.002,
            "lateral_error_m": 0.006,
            "insertion_depth_m": 0.0,
            "orientation_error_deg": 0.0,
            "env_native_success": False,
        },
        previous_action=[0.05, -0.05, -0.16, 0.0, 0.0, 0.0, 1.0],
        action_scale=1.0,
        hysteresis_state={"current_hysteresis_phase": "ALIGN", "last_z_motion_allowed": False},
    )

    assert action.tolist()[:3] == pytest.approx([-0.024, 0.008, 0.0])
    assert diagnostics["horizon_reserved_capture_authority_id"] == (
        "horizon_reserved_capture_authority_v0_8f"
    )
    assert diagnostics["horizon_reserved_capture_authority_applied"] is True
    assert diagnostics["horizon_reserved_capture_authority_reason"] == "capture_wait_xy_authority"
    assert diagnostics["horizon_reserved_xy_recomputed"] is True
    assert diagnostics["horizon_reserved_preserved_rotation_gripper"] is True


def test_v08f_seat_region_keeps_z_until_env_native_success() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    policy = _v08f_policy_artifact(script)
    metric_row = {
        "step": 120,
        "behavior_state_phase": "DESCEND",
        "relative_x_m": 0.0002,
        "relative_y_m": 0.0,
        "lateral_error_m": 0.0002,
        "insertion_depth_m": 0.0245,
        "orientation_error_deg": 0.0,
        "env_native_success": False,
    }

    action, diagnostics = script._predict_policy_action_with_diagnostics(
        policy,
        metric_row=metric_row,
        previous_action=[0.0, 0.0, -0.03, 0.0, 0.0, 0.0, 1.0],
        action_scale=1.0,
        hysteresis_state={"current_hysteresis_phase": "DESCEND", "last_z_motion_allowed": True},
    )

    assert action.tolist()[2] == pytest.approx(-0.16)
    assert diagnostics["horizon_reserved_capture_authority_reason"] == (
        "forced_horizon_reserved_progress_z"
    )

    success_row = dict(metric_row)
    success_row["env_native_success"] = True
    success_action, success_diagnostics = script._predict_policy_action_with_diagnostics(
        policy,
        metric_row=success_row,
        previous_action=[0.0, 0.0, -0.03, 0.0, 0.0, 0.0, 1.0],
        action_scale=1.0,
        hysteresis_state={"current_hysteresis_phase": "HOLD", "last_z_motion_allowed": True},
    )

    assert success_action.tolist()[2] != pytest.approx(-0.16)
    assert success_diagnostics["horizon_reserved_capture_authority_reason"] == (
        "env_native_success_already_true"
    )


def test_v08g_deadline_precedence_overrides_capture_wait() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    policy = _v08g_policy_artifact(script)

    action, diagnostics = script._predict_policy_action_with_diagnostics(
        policy,
        metric_row={
            "step": 80,
            "behavior_state_phase": "ALIGN",
            "relative_x_m": 0.006,
            "relative_y_m": -0.002,
            "lateral_error_m": 0.006,
            "insertion_depth_m": 0.0,
            "orientation_error_deg": 0.0,
            "env_native_success": False,
        },
        previous_action=[0.05, -0.05, 0.0, 0.0, 0.0, 0.0, 1.0],
        action_scale=1.0,
        hysteresis_state={"current_hysteresis_phase": "ALIGN", "last_z_motion_allowed": False},
    )

    assert action.tolist()[:3] == pytest.approx([-0.024, 0.008, -0.16])
    assert diagnostics["deadline_precedence_horizon_authority_id"] == (
        "deadline_precedence_horizon_authority_v0_8g"
    )
    assert diagnostics["deadline_precedence_horizon_authority_applied"] is True
    assert diagnostics["deadline_precedence_horizon_authority_reason"] == (
        "forced_horizon_reserved_progress_z_deadline_precedence"
    )
    assert diagnostics["deadline_precedence_xy_recomputed"] is True
    assert diagnostics["effective_z_open_for_xy_authority"] is True


def test_v08g_env_native_success_stops_forced_z() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    policy = _v08g_policy_artifact(script)

    action, diagnostics = script._predict_policy_action_with_diagnostics(
        policy,
        metric_row={
            "step": 120,
            "behavior_state_phase": "HOLD",
            "relative_x_m": 0.006,
            "relative_y_m": -0.002,
            "lateral_error_m": 0.006,
            "insertion_depth_m": 0.0245,
            "orientation_error_deg": 0.0,
            "env_native_success": True,
        },
        previous_action=[0.0, 0.0, -0.03, 0.0, 0.0, 0.0, 1.0],
        action_scale=1.0,
        hysteresis_state={"current_hysteresis_phase": "HOLD", "last_z_motion_allowed": True},
    )

    assert action.tolist()[2] != pytest.approx(-0.16)
    assert diagnostics["deadline_precedence_horizon_authority_reason"] == (
        "env_native_success_already_true"
    )


def test_v08h_early_centered_z_opens_before_reference_deadline() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    policy = _v08h_policy_artifact(script)

    action, diagnostics = script._predict_policy_action_with_diagnostics(
        policy,
        metric_row={
            "step": 58,
            "behavior_state_phase": "ALIGN",
            "relative_x_m": 0.004,
            "relative_y_m": 0.0,
            "lateral_error_m": 0.004,
            "insertion_depth_m": 0.0,
            "orientation_error_deg": 0.0,
            "env_native_success": False,
        },
        previous_action=[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
        action_scale=1.0,
        hysteresis_state={"current_hysteresis_phase": "ALIGN", "last_z_motion_allowed": False},
    )

    assert action.tolist()[2] == pytest.approx(-0.16)
    assert diagnostics["early_centered_z_open_safe_entry_authority_id"] == (
        "early_centered_z_open_safe_entry_authority_v0_8h"
    )
    assert diagnostics["early_centered_z_open_safe_entry_applied"] is True
    assert diagnostics["early_centered_z_open_safe_entry_reason"] == "early_centered_safe_entry_z"
    assert diagnostics["effective_z_open_for_xy_authority"] is True


def test_v08h_unsafe_lateral_blocks_z_after_reference_deadline() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    policy = _v08h_policy_artifact(script)

    action, diagnostics = script._predict_policy_action_with_diagnostics(
        policy,
        metric_row={
            "step": 80,
            "behavior_state_phase": "ALIGN",
            "relative_x_m": 0.007,
            "relative_y_m": -0.001,
            "lateral_error_m": 0.007,
            "insertion_depth_m": 0.0,
            "orientation_error_deg": 0.0,
            "env_native_success": False,
        },
        previous_action=[0.05, -0.05, -0.16, 0.0, 0.0, 0.0, 1.0],
        action_scale=1.0,
        hysteresis_state={"current_hysteresis_phase": "ALIGN", "last_z_motion_allowed": False},
    )

    assert action.tolist()[:3] == pytest.approx([-0.028, 0.004, 0.0])
    assert diagnostics["early_centered_z_open_safe_entry_applied"] is True
    assert diagnostics["early_centered_z_open_safe_entry_reason"] == "unsafe_lateral_z_block"
    assert diagnostics["safe_entry_xy_recomputed"] is True
    assert diagnostics["effective_z_open_for_xy_authority"] is False


def test_v08h_depth_progress_continuation_keeps_z_open() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    policy = _v08h_policy_artifact(script)

    action, diagnostics = script._predict_policy_action_with_diagnostics(
        policy,
        metric_row={
            "step": 96,
            "behavior_state_phase": "DESCEND",
            "relative_x_m": 0.0058,
            "relative_y_m": 0.0,
            "lateral_error_m": 0.0058,
            "insertion_depth_m": 0.010,
            "orientation_error_deg": 0.0,
            "env_native_success": False,
        },
        previous_action=[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
        action_scale=1.0,
        hysteresis_state={"current_hysteresis_phase": "DESCEND", "last_z_motion_allowed": True},
    )

    assert action.tolist()[2] == pytest.approx(-0.16)
    assert diagnostics["early_centered_z_open_safe_entry_reason"] == (
        "depth_progress_continuation_z"
    )
    assert diagnostics["depth_progress_continuation_active"] is True
    assert diagnostics["effective_z_open_for_xy_authority"] is True


def test_v08h_env_native_success_stops_forced_z() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    policy = _v08h_policy_artifact(script)

    action, diagnostics = script._predict_policy_action_with_diagnostics(
        policy,
        metric_row={
            "step": 120,
            "behavior_state_phase": "HOLD",
            "relative_x_m": 0.006,
            "relative_y_m": -0.002,
            "lateral_error_m": 0.006,
            "insertion_depth_m": 0.0245,
            "orientation_error_deg": 0.0,
            "env_native_success": True,
        },
        previous_action=[0.0, 0.0, -0.03, 0.0, 0.0, 0.0, 1.0],
        action_scale=1.0,
        hysteresis_state={"current_hysteresis_phase": "HOLD", "last_z_motion_allowed": True},
    )

    assert action.tolist()[2] != pytest.approx(-0.16)
    assert diagnostics["early_centered_z_open_safe_entry_reason"] == (
        "env_native_success_already_true"
    )


def test_v08b_scenario_aware_seat_window_forces_z_before_xy_authority() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    policy = _v08b_policy_artifact(script)

    action, diagnostics = script._predict_policy_action_with_diagnostics(
        policy,
        metric_row={
            "step": 74,
            "behavior_state_phase": "ALIGN",
            "relative_x_m": -0.001388,
            "relative_y_m": 0.001388,
            "lateral_error_m": 0.001388,
            "insertion_depth_m": 0.0,
            "orientation_error_deg": 0.0,
            "env_native_success": False,
        },
        previous_action=[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
        action_scale=1.0,
        hysteresis_state={"current_hysteresis_phase": "ALIGN", "last_z_motion_allowed": False},
    )

    assert action.tolist()[2] == -0.16
    assert diagnostics["seat_window_authority_id"] == "scenario_aware_seat_window_authority_v0_8b"
    assert diagnostics["seat_window_authority_applied"] is True
    assert diagnostics["effective_z_open_for_xy_authority"] is True
    assert diagnostics["seat_window_xy_recomputed_with_forced_z"] is True
    assert diagnostics["xy_authority_reason"] == "z_open_center_maintenance_state_feedback"
    assert diagnostics["xy_authority_zone"] == "z_open_low_depth_center"


def test_v08b_scenario_aware_seat_window_blocks_z_when_off_center() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    config = _v08b_seat_window_config(script)

    action, diagnostics = script._apply_v08b_scenario_aware_seat_window_authority(
        action=script.np.asarray([0.02, -0.02, 0.0, 0.0, 0.0, 0.0, 1.0]),
        metric_row={
            "step": 90,
            "lateral_error_m": 0.02,
            "insertion_depth_m": 0.010,
            "env_native_success": False,
        },
        config=config,
    )

    assert action.tolist()[2] == 0.0
    assert diagnostics["seat_window_authority_applied"] is False
    assert diagnostics["seat_window_authority_reason"] == "not_centered_for_seat_window_progress"


def test_v08a_seat_window_authority_forces_z_after_train_derived_deadline() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    config = _v08a_seat_window_config(script)

    action, diagnostics = script._apply_v08a_seat_window_progress_authority(
        action=script.np.asarray([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0]),
        metric_row={
            "step": 82,
            "lateral_error_m": 0.0005,
            "insertion_depth_m": 0.010,
            "env_native_success": False,
        },
        config=config,
    )

    assert action.tolist()[2] == -0.16
    assert diagnostics["seat_window_authority_id"] == "seat_window_progress_authority_v0_8a"
    assert diagnostics["seat_window_authority_applied"] is True
    assert diagnostics["seat_window_authority_reason"] == "forced_train_derived_seat_progress_z"
    assert diagnostics["seat_window_authority_preserved_xy"] is True


def test_v08a_seat_window_authority_does_not_change_z_before_deadline_or_off_center() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    config = _v08a_seat_window_config(script)

    before_deadline, before_diag = script._apply_v08a_seat_window_progress_authority(
        action=script.np.asarray([0.02, -0.02, 0.0, 0.0, 0.0, 0.0, 1.0]),
        metric_row={
            "step": 80,
            "lateral_error_m": 0.0005,
            "insertion_depth_m": 0.010,
            "env_native_success": False,
        },
        config=config,
    )
    off_center, off_center_diag = script._apply_v08a_seat_window_progress_authority(
        action=script.np.asarray([0.02, -0.02, 0.0, 0.0, 0.0, 0.0, 1.0]),
        metric_row={
            "step": 82,
            "lateral_error_m": 0.02,
            "insertion_depth_m": 0.010,
            "env_native_success": False,
        },
        config=config,
    )

    assert before_deadline.tolist()[2] == 0.0
    assert before_diag["seat_window_authority_applied"] is False
    assert before_diag["seat_window_authority_reason"] == "before_train_derived_z_open_deadline"
    assert off_center.tolist()[2] == 0.0
    assert off_center_diag["seat_window_authority_applied"] is False
    assert off_center_diag["seat_window_authority_reason"] == "not_centered_for_seat_window_progress"


def test_v07k_runtime_wires_stateful_hysteresis_before_final_z_authority() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    policy = _v07k_policy_artifact(script)

    action, diagnostics = script._predict_policy_action_with_diagnostics(
        policy,
        metric_row={
            "step": 12,
            "phase": "APPROACH",
            "lateral_error_m": 0.0005,
            "relative_x_m": -0.0004,
            "relative_y_m": 0.0003,
            "orientation_error_deg": 0.0,
            "insertion_depth_m": 0.0,
            "env_native_success": False,
        },
        previous_action=[0.0] * len(script.ACTION_SCHEMA),
        action_scale=1.0,
        hysteresis_state=script.initial_v07e_hysteresis_state(),
    )

    assert diagnostics["policy_slice"] == "v0_7k"
    assert diagnostics["behavior_state_phase_source"] == script.V07E_SHARED_HYSTERESIS_AUTHORITY_ID
    assert diagnostics["shared_hysteresis_state_after"]["last_z_motion_allowed"] is True
    assert diagnostics["final_post_adapter_z_motion_allowed"] is True
    assert diagnostics["z_motion_block_reason"] == "z_motion_allowed_by_v07e_hysteresis"
    assert action.tolist()[2] < 0.0
    assert abs(action.tolist()[1]) <= 0.02


def test_v07m_runtime_extends_z_window_beyond_v07k_28_steps() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    policy = _v07m_policy_artifact(script)

    action, diagnostics = script._predict_policy_action_with_diagnostics(
        policy,
        metric_row={
            "step": 45,
            "phase": "APPROACH",
            "lateral_error_m": 0.0008,
            "relative_x_m": -0.0004,
            "relative_y_m": 0.0003,
            "orientation_error_deg": 0.0,
            "insertion_depth_m": 0.0,
            "env_native_success": False,
        },
        previous_action=[0.0] * len(script.ACTION_SCHEMA),
        action_scale=1.0,
        hysteresis_state={
            "current_hysteresis_phase": "DESCEND",
            "z_window_remaining_steps": 40,
            "entered_descend_step": 12,
            "last_z_motion_allowed": True,
            "hard_safety_escape_triggered": False,
        },
    )

    state_after = diagnostics["shared_hysteresis_state_after"]
    assert diagnostics["policy_slice"] == "v0_7m"
    assert state_after["current_hysteresis_phase"] == "DESCEND"
    assert state_after["last_z_motion_allowed"] is True
    assert state_after["z_window_remaining_steps"] == 39
    assert diagnostics["z_motion_block_reason"] == "z_motion_allowed_by_v07e_hysteresis"
    assert action.tolist()[2] < 0.0


def test_v07m_runtime_soft_realign_blocks_z_without_sticky_hard_escape() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    policy = _v07m_policy_artifact(script)

    action, diagnostics = script._predict_policy_action_with_diagnostics(
        policy,
        metric_row={
            "step": 46,
            "phase": "APPROACH",
            "lateral_error_m": 0.007,
            "relative_x_m": -0.006,
            "relative_y_m": 0.0036,
            "orientation_error_deg": 0.0,
            "insertion_depth_m": 0.0,
            "env_native_success": False,
        },
        previous_action=[0.0] * len(script.ACTION_SCHEMA),
        action_scale=1.0,
        hysteresis_state={
            "current_hysteresis_phase": "DESCEND",
            "z_window_remaining_steps": 40,
            "entered_descend_step": 12,
            "last_z_motion_allowed": True,
            "hard_safety_escape_triggered": False,
        },
    )

    state_after = diagnostics["shared_hysteresis_state_after"]
    assert state_after["current_hysteresis_phase"] == "ALIGN"
    assert state_after["last_z_motion_allowed"] is False
    assert state_after["soft_realign_triggered"] is True
    assert state_after["hard_safety_escape_triggered"] is False
    assert diagnostics["z_motion_block_reason"] == "final_post_adapter_align_z_blocked"
    assert action.tolist()[2] == 0.0


def test_v13_runtime_policy_slice_uses_hysteresis_without_v08h_safe_entry() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")

    assert script.V13_POLICY_SLICE_ID == "v0_13"
    assert script.V13_POLICY_SLICE_ID in script.V07E_HYSTERESIS_RUNTIME_POLICY_SLICE_IDS
    assert script.V13_POLICY_SLICE_ID in script.V07B_BASE_SERVO_RUNTIME_POLICY_SLICE_IDS
    assert script.V13_POLICY_SLICE_ID in script.V07C_AUTHORITY_RUNTIME_POLICY_SLICE_IDS
    assert script.V13_POLICY_SLICE_ID in script.V07D_FINAL_AUTHORITY_RUNTIME_POLICY_SLICE_IDS
    assert script.V13_POLICY_SLICE_ID not in script.V08H_DERIVED_POLICY_SLICE_IDS


def test_v14_runtime_policy_slice_uses_v13_hysteresis_and_policy_influence() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")

    assert script.V14_POLICY_SLICE_ID == "v0_14"
    assert script.V14_POLICY_SLICE_ID in script.V07E_HYSTERESIS_RUNTIME_POLICY_SLICE_IDS
    assert script.V14_POLICY_SLICE_ID in script.V07B_BASE_SERVO_RUNTIME_POLICY_SLICE_IDS
    assert script.V14_POLICY_SLICE_ID in script.V07C_AUTHORITY_RUNTIME_POLICY_SLICE_IDS
    assert script.V14_POLICY_SLICE_ID in script.V07D_FINAL_AUTHORITY_RUNTIME_POLICY_SLICE_IDS
    assert script.V14_POLICY_SLICE_ID not in script.V08H_DERIVED_POLICY_SLICE_IDS


def test_v13_runtime_reduces_selected_adapter_state_feedback_and_keeps_policy_delta() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    policy = _v13_policy_artifact(script)

    action, diagnostics = script._apply_selected_action_adapter_with_diagnostics(
        policy_artifact=policy,
        raw_action=script.np.array([0.02, -0.01, -0.001, 0.0, 0.0, 0.0, 1.0]),
        action_scale=1.0,
        metric_row={
            "step": 12,
            "phase": "APPROACH",
            "behavior_state_phase": "DESCEND",
            "lateral_error_m": 0.0007,
            "relative_x_m": 0.002,
            "relative_y_m": -0.002,
            "orientation_error_deg": 0.0,
            "insertion_depth_m": 0.0,
            "env_native_success": False,
        },
        behavior_state_phase="DESCEND",
        hysteresis_state={
            "current_hysteresis_phase": "DESCEND",
            "z_window_remaining_steps": 20,
            "last_z_motion_allowed": True,
            "hard_safety_escape_triggered": False,
        },
    )

    assert diagnostics["policy_slice"] == "v0_13"
    assert diagnostics["selected_action_adapter_id"] == "isaac_signed_xy_downward_servo_v0"
    assert diagnostics["policy_influence_authority_ceiling_id"] == "policy_influence_authority_ceiling_v0_13"
    assert diagnostics["policy_influence_state_feedback_gain_ceiling"] == pytest.approx(0.5)
    assert diagnostics.get("early_centered_z_open_safe_entry_applied") is None
    assert diagnostics.get("final_post_adapter_xy_authority_id") is None
    assert action.tolist()[0] == pytest.approx(0.019)
    assert action.tolist()[1] == pytest.approx(-0.009)
    assert action.tolist()[2] < 0.0


def test_v07n_runtime_overrides_z_open_xy_sign_mismatch_without_mutating_z() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    policy = _v07n_policy_artifact(script)

    action, diagnostics = script._apply_selected_action_adapter_with_diagnostics(
        policy_artifact=policy,
        raw_action=script.np.array([0.05, 0.05, -0.001, 0.0, 0.0, 0.0, 1.0]),
        action_scale=1.0,
        metric_row={
            "step": 110,
            "phase": "APPROACH",
            "behavior_state_phase": "DESCEND",
            "lateral_error_m": 0.0007,
            "relative_x_m": 0.003,
            "relative_y_m": 0.003,
            "orientation_error_deg": 0.0,
            "insertion_depth_m": 0.0,
            "env_native_success": False,
        },
        behavior_state_phase="DESCEND",
        hysteresis_state={
            "current_hysteresis_phase": "DESCEND",
            "last_z_motion_allowed": True,
            "hard_safety_escape_triggered": False,
        },
    )

    assert diagnostics["final_post_adapter_xy_authority_id"] == "final_post_adapter_xy_authority_gate_v0_7n"
    assert diagnostics["xy_authority_applied"] is True
    assert diagnostics["xy_authority_reason"] == "z_open_center_maintenance_state_feedback"
    assert diagnostics["xy_authority_preserved_sign"] is False
    assert diagnostics["xy_authority_preserved_z"] is True
    assert action.tolist()[:2] == pytest.approx([-0.012, -0.012])
    assert action.tolist()[2] < 0.0


def test_v07o_runtime_keeps_parent_piecewise_xy_before_z_open() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    policy = _v07o_policy_artifact(script)

    action, diagnostics = script._apply_selected_action_adapter_with_diagnostics(
        policy_artifact=policy,
        raw_action=script.np.array([0.05, 0.05, 0.0, 0.0, 0.0, 0.0, 1.0]),
        action_scale=1.0,
        metric_row={
            "step": 10,
            "phase": "APPROACH",
            "behavior_state_phase": "ALIGN",
            "lateral_error_m": 0.03,
            "relative_x_m": -0.003,
            "relative_y_m": -0.017,
            "orientation_error_deg": 0.0,
            "insertion_depth_m": 0.0,
            "env_native_success": False,
        },
        behavior_state_phase="ALIGN",
        hysteresis_state={
            "current_hysteresis_phase": "ALIGN",
            "last_z_motion_allowed": False,
            "hard_safety_escape_triggered": False,
        },
    )

    assert diagnostics["final_post_adapter_xy_authority_id"] == "final_post_adapter_xy_authority_gate_v0_7o"
    assert diagnostics["xy_authority_applied"] is True
    assert diagnostics["xy_authority_reason"] == "xy_saturation_off_center_state_feedback_clamped"
    assert diagnostics["xy_authority_preserved_sign"] is True
    assert action.tolist()[:2] == pytest.approx([0.012, 0.05])
    assert action.tolist()[2] == 0.0


def test_v07o_runtime_still_overrides_z_open_low_depth_sign_mismatch() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    policy = _v07o_policy_artifact(script)

    action, diagnostics = script._apply_selected_action_adapter_with_diagnostics(
        policy_artifact=policy,
        raw_action=script.np.array([0.05, 0.05, -0.001, 0.0, 0.0, 0.0, 1.0]),
        action_scale=1.0,
        metric_row={
            "step": 110,
            "phase": "APPROACH",
            "behavior_state_phase": "DESCEND",
            "lateral_error_m": 0.0007,
            "relative_x_m": 0.003,
            "relative_y_m": 0.003,
            "orientation_error_deg": 0.0,
            "insertion_depth_m": 0.0,
            "env_native_success": False,
        },
        behavior_state_phase="DESCEND",
        hysteresis_state={
            "current_hysteresis_phase": "DESCEND",
            "last_z_motion_allowed": True,
            "hard_safety_escape_triggered": False,
        },
    )

    assert diagnostics["xy_authority_applied"] is True
    assert diagnostics["xy_authority_reason"] == "z_open_center_maintenance_state_feedback"
    assert diagnostics["xy_authority_preserved_sign"] is False
    assert diagnostics["xy_authority_preserved_z"] is True
    assert action.tolist()[:2] == pytest.approx([-0.012, -0.012])
    assert action.tolist()[2] < 0.0


def test_v07g_final_xy_authority_config_is_hash_stable() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    policy = _v07g_policy_artifact(script)

    config = script._validated_v07g_final_xy_authority_config(policy)

    assert config["policy_slice"] == "v0_7g"
    assert config["parent_policy_slice"] == "v0_7e"
    assert config["candidate_specific"] is False
    assert config["baseline_specific"] is False
    assert config["heldout_21000_21049_accessed"] is False
    assert config["final_post_adapter_xy_authority_config_sha256"] == script._sha256_payload_excluding(
        config,
        "final_post_adapter_xy_authority_config_sha256",
    )


def test_v07g_runtime_applies_xy_authority_after_adapter_and_final_z() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    policy = _v07g_policy_artifact(script)

    action, diagnostics = script._apply_selected_action_adapter_with_diagnostics(
        policy_artifact=policy,
        raw_action=script.np.array([0.05, -0.05, -0.001, 0.0, 0.0, 0.0, 1.0]),
        action_scale=1.0,
        metric_row={
            "phase": "APPROACH",
            "behavior_state_phase": "DESCEND",
            "lateral_error_m": 0.0007,
            "relative_x_m": -0.0005,
            "relative_y_m": 0.0005,
            "orientation_error_deg": 0.0,
            "insertion_depth_m": 0.0,
            "env_native_success": False,
        },
        behavior_state_phase="DESCEND",
        hysteresis_state={
            "current_hysteresis_phase": "DESCEND",
            "z_window_remaining_steps": 20,
            "last_z_motion_allowed": True,
            "hard_safety_escape_triggered": False,
        },
    )

    assert diagnostics["final_post_adapter_authority_id"] == "final_post_adapter_z_authority_gate_v0_7d"
    assert diagnostics["final_post_adapter_xy_authority_id"] == "final_post_adapter_xy_authority_gate_v0_7g"
    assert diagnostics["post_z_pre_xy_authority_action_vector"][2] == pytest.approx(-0.032)
    assert diagnostics["post_xy_authority_action_vector"] == pytest.approx(action.tolist())
    assert abs(action.tolist()[0]) < abs(diagnostics["pre_xy_authority_action_vector"][0])
    assert abs(action.tolist()[1]) < abs(diagnostics["pre_xy_authority_action_vector"][1])


def test_v07g_runtime_reduces_saturated_xy_near_center() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    policy = _v07g_policy_artifact(script)

    action, diagnostics = script._apply_selected_action_adapter_with_diagnostics(
        policy_artifact=policy,
        raw_action=script.np.array([0.05, 0.05, 0.0, 0.0, 0.0, 0.0, 1.0]),
        action_scale=1.0,
        metric_row={
            "phase": "APPROACH",
            "behavior_state_phase": "ALIGN",
            "lateral_error_m": 0.001,
            "relative_x_m": -0.0004,
            "relative_y_m": -0.0004,
            "orientation_error_deg": 0.0,
            "insertion_depth_m": 0.0,
            "env_native_success": False,
        },
        behavior_state_phase="ALIGN",
        hysteresis_state=script.initial_v07e_hysteresis_state(),
    )

    assert diagnostics["xy_authority_applied"] is True
    assert max(abs(float(action[0])), abs(float(action[1]))) <= 0.02


def test_v07g_runtime_preserves_xy_sign() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    policy = _v07g_policy_artifact(script)

    action, diagnostics = script._apply_selected_action_adapter_with_diagnostics(
        policy_artifact=policy,
        raw_action=script.np.array([0.05, -0.05, 0.0, 0.0, 0.0, 0.0, 1.0]),
        action_scale=1.0,
        metric_row={
            "phase": "APPROACH",
            "behavior_state_phase": "ALIGN",
            "lateral_error_m": 0.001,
            "relative_x_m": -0.0004,
            "relative_y_m": 0.0004,
            "orientation_error_deg": 0.0,
            "insertion_depth_m": 0.0,
            "env_native_success": False,
        },
        behavior_state_phase="ALIGN",
        hysteresis_state=script.initial_v07e_hysteresis_state(),
    )

    assert diagnostics["xy_authority_preserved_sign"] is True
    assert float(action[0]) > 0.0
    assert float(action[1]) < 0.0


def test_v07g_runtime_does_not_mutate_z_authority() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    policy = _v07g_policy_artifact(script)

    action, diagnostics = script._apply_selected_action_adapter_with_diagnostics(
        policy_artifact=policy,
        raw_action=script.np.array([0.05, -0.05, -0.001, 0.0, 0.0, 0.0, 1.0]),
        action_scale=1.0,
        metric_row={
            "phase": "APPROACH",
            "behavior_state_phase": "DESCEND",
            "lateral_error_m": 0.0007,
            "relative_x_m": -0.0005,
            "relative_y_m": 0.0005,
            "orientation_error_deg": 0.0,
            "insertion_depth_m": 0.0,
            "env_native_success": False,
        },
        behavior_state_phase="DESCEND",
        hysteresis_state={
            "current_hysteresis_phase": "DESCEND",
            "z_window_remaining_steps": 20,
            "last_z_motion_allowed": True,
            "hard_safety_escape_triggered": False,
        },
    )

    assert action.tolist()[2] == pytest.approx(diagnostics["post_z_pre_xy_authority_action_vector"][2])
    assert diagnostics["xy_authority_preserved_z"] is True


def test_v07g_runtime_keeps_env_native_stable_hold_authority() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    policy = _v07g_policy_artifact(script)

    action, diagnostics = script._apply_selected_action_adapter_with_diagnostics(
        policy_artifact=policy,
        raw_action=script.np.array([0.05, -0.05, -0.001, 0.0, 0.0, 0.0, 1.0]),
        action_scale=1.0,
        metric_row={
            "phase": "SEAT",
            "behavior_state_phase": "HOLD",
            "lateral_error_m": 0.02,
            "relative_x_m": 0.02,
            "relative_y_m": 0.0,
            "orientation_error_deg": 0.0,
            "insertion_depth_m": 0.024,
            "env_native_success": True,
            "env_native_success_mask": True,
        },
        behavior_state_phase="HOLD",
        hysteresis_state={
            "current_hysteresis_phase": "HOLD",
            "z_window_remaining_steps": 0,
            "last_z_motion_allowed": False,
            "hard_safety_escape_triggered": False,
        },
    )

    assert diagnostics["stable_hold_authority"] == "env_native_success_mask"
    assert diagnostics["z_motion_block_reason"] == "stable_hold_ready_env_native"
    assert action.tolist()[2] == pytest.approx(-0.02)


def test_v07g_runtime_rejects_candidate_specific_xy_authority() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    policy = _v07g_policy_artifact(script)
    config = _v07g_xy_authority_config(script, parent_policy=policy, candidate_specific=True)
    policy["final_post_adapter_xy_authority_config"] = config
    policy["final_post_adapter_xy_authority_config_sha256"] = config[
        "final_post_adapter_xy_authority_config_sha256"
    ]

    with pytest.raises(ValueError, match="v0_7g_xy_authority_config_must_be_shared"):
        script._validated_v07g_final_xy_authority_config(policy)


def test_v07g_runtime_records_pre_and_post_xy_authority_vectors() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    policy = _v07g_policy_artifact(script)

    _action, diagnostics = script._apply_selected_action_adapter_with_diagnostics(
        policy_artifact=policy,
        raw_action=script.np.array([0.05, -0.05, 0.0, 0.0, 0.0, 0.0, 1.0]),
        action_scale=1.0,
        metric_row={
            "phase": "APPROACH",
            "behavior_state_phase": "ALIGN",
            "lateral_error_m": 0.001,
            "relative_x_m": -0.0005,
            "relative_y_m": 0.0005,
            "orientation_error_deg": 0.0,
            "insertion_depth_m": 0.0,
            "env_native_success": False,
        },
        behavior_state_phase="ALIGN",
        hysteresis_state=script.initial_v07e_hysteresis_state(),
    )

    assert diagnostics["pre_xy_authority_action_vector"] != diagnostics["post_xy_authority_action_vector"]
    assert diagnostics["post_xy_authority_action_vector"] == diagnostics["post_adapter_action_vector"]


def test_v07g_runtime_records_post_z_pre_xy_authority_vector() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    policy = _v07g_policy_artifact(script)

    _action, diagnostics = script._apply_selected_action_adapter_with_diagnostics(
        policy_artifact=policy,
        raw_action=script.np.array([0.05, 0.05, -0.001, 0.0, 0.0, 0.0, 1.0]),
        action_scale=1.0,
        metric_row={
            "phase": "APPROACH",
            "behavior_state_phase": "DESCEND",
            "lateral_error_m": 0.001,
            "relative_x_m": -0.0005,
            "relative_y_m": -0.0005,
            "orientation_error_deg": 0.0,
            "insertion_depth_m": 0.0,
            "env_native_success": False,
        },
        behavior_state_phase="DESCEND",
        hysteresis_state={
            "current_hysteresis_phase": "DESCEND",
            "z_window_remaining_steps": 20,
            "last_z_motion_allowed": True,
            "hard_safety_escape_triggered": False,
        },
    )

    assert diagnostics["post_z_pre_xy_authority_action_vector"][2] == pytest.approx(-0.032)
    assert diagnostics["post_z_pre_xy_authority_action_vector"][0] == pytest.approx(0.05)


def test_v07g_runtime_has_no_mutation_after_final_xy_authority() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    policy = _v07g_policy_artifact(script)

    action, diagnostics = script._apply_selected_action_adapter_with_diagnostics(
        policy_artifact=policy,
        raw_action=script.np.array([0.05, -0.05, 0.0, 0.0, 0.0, 0.0, 1.0]),
        action_scale=1.0,
        metric_row={
            "phase": "APPROACH",
            "behavior_state_phase": "ALIGN",
            "lateral_error_m": 0.001,
            "relative_x_m": -0.0005,
            "relative_y_m": 0.0005,
            "orientation_error_deg": 0.0,
            "insertion_depth_m": 0.0,
            "env_native_success": False,
        },
        behavior_state_phase="ALIGN",
        hysteresis_state=script.initial_v07e_hysteresis_state(),
    )

    assert diagnostics["post_xy_authority_action_vector"] == pytest.approx(action.tolist())
    assert diagnostics["no_mutation_after_final_post_adapter_authority"] is True


def test_v07g_runtime_fails_if_xy_authority_changes_z_component() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    policy = _v07g_policy_artifact(script)
    config = dict(policy["final_post_adapter_xy_authority_config"])
    config["xy_authority_axis_scope"] = ["x", "y", "z"]
    config["final_post_adapter_xy_authority_config_sha256"] = script._sha256_payload_excluding(
        config,
        "final_post_adapter_xy_authority_config_sha256",
    )
    policy["final_post_adapter_xy_authority_config"] = config
    policy["final_post_adapter_xy_authority_config_sha256"] = config[
        "final_post_adapter_xy_authority_config_sha256"
    ]

    with pytest.raises(ValueError, match="v0_7g_xy_authority_must_not_mutate_z"):
        script._validated_v07g_final_xy_authority_config(policy)


def test_v07e_hysteresis_config_is_hash_stable() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    policy = _v07e_policy_artifact(script)

    config = script._validated_v07e_hysteresis_authority_config(policy)

    assert config["policy_slice"] == "v0_7e"
    assert config["parent_policy_slice"] == "v0_7d"
    assert config["candidate_specific"] is False
    assert config["baseline_specific"] is False
    assert config["heldout_21000_21049_accessed"] is False
    assert config["shared_hysteresis_authority_config_sha256"] == script._sha256_payload_excluding(
        config,
        "shared_hysteresis_authority_config_sha256",
    )


def test_v07e_runtime_tracks_rollout_local_hysteresis_state() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    policy = _v07e_policy_artifact(script)
    state = script.initial_v07e_hysteresis_state()

    _action, diagnostics = script._predict_policy_action_with_diagnostics(
        policy,
        metric_row={
            "phase": "APPROACH",
            "behavior_state_phase": "ALIGN",
            "lateral_error_m": 0.0008,
            "orientation_error_deg": 0.0,
            "insertion_depth_m": 0.0,
            "relative_x_m": 0.0008,
            "relative_y_m": 0.0,
            "env_native_success": False,
        },
        previous_action=[0.0] * len(script.ACTION_SCHEMA),
        action_scale=1.0,
        hysteresis_state=state,
    )

    assert diagnostics["shared_hysteresis_authority_id"] == "shared_stateful_hysteresis_authority_v0_7e"
    assert diagnostics["shared_hysteresis_state_before"]["current_hysteresis_phase"] == "ALIGN"
    assert diagnostics["shared_hysteresis_state_after"]["current_hysteresis_phase"] == "DESCEND"
    assert diagnostics["shared_hysteresis_state_after"]["z_window_remaining_steps"] > 0


def test_v07e_runtime_holds_descend_window_after_lateral_gate_entry() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    policy = _v07e_policy_artifact(script)
    state = script.initial_v07e_hysteresis_state()

    _action, first_diagnostics = script._predict_policy_action_with_diagnostics(
        policy,
        metric_row={
            "phase": "APPROACH",
            "behavior_state_phase": "ALIGN",
            "lateral_error_m": 0.0009,
            "orientation_error_deg": 0.0,
            "insertion_depth_m": 0.0,
            "relative_x_m": 0.0009,
            "relative_y_m": 0.0,
            "env_native_success": False,
        },
        previous_action=[0.0] * len(script.ACTION_SCHEMA),
        action_scale=1.0,
        hysteresis_state=state,
    )

    second_action, second_diagnostics = script._predict_policy_action_with_diagnostics(
        policy,
        metric_row={
            "phase": "APPROACH",
            "behavior_state_phase": "ALIGN",
            "lateral_error_m": 0.0016,
            "orientation_error_deg": 0.0,
            "insertion_depth_m": 0.0,
            "relative_x_m": 0.0016,
            "relative_y_m": 0.0,
            "env_native_success": False,
        },
        previous_action=[0.0] * len(script.ACTION_SCHEMA),
        action_scale=1.0,
        hysteresis_state=first_diagnostics["shared_hysteresis_state_after"],
    )

    assert second_diagnostics["shared_hysteresis_state_after"]["current_hysteresis_phase"] == "DESCEND"
    assert second_diagnostics["final_post_adapter_z_motion_allowed"] is True
    assert second_diagnostics["z_motion_block_reason"] == "z_motion_allowed_by_v07e_hysteresis"
    assert second_action.tolist()[2] < 0.0


def test_v07e_runtime_preserves_v07d_align_block_when_hysteresis_closed() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    policy = _v07e_policy_artifact(script)

    action, diagnostics = script._apply_selected_action_adapter_with_diagnostics(
        policy_artifact=policy,
        raw_action=script.np.array([0.0, 0.0, -0.001, 0.0, 0.0, 0.0, 1.0], dtype=script.np.float64),
        action_scale=1.0,
        metric_row={
            "phase": "APPROACH",
            "behavior_state_phase": "ALIGN",
            "lateral_error_m": 0.02,
            "orientation_error_deg": 0.0,
            "insertion_depth_m": 0.0,
            "env_native_success": False,
        },
        behavior_state_phase="ALIGN",
        hysteresis_state=script.initial_v07e_hysteresis_state(),
    )

    assert diagnostics["final_post_adapter_authority_id"] == "final_post_adapter_z_authority_gate_v0_7d"
    assert diagnostics["final_post_adapter_z_motion_allowed"] is False
    assert diagnostics["z_motion_block_reason"] == "final_post_adapter_align_z_blocked"
    assert action.tolist()[2] == pytest.approx(0.0)


def test_v07e_runtime_does_not_mutate_after_final_post_adapter_authority() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    policy = _v07e_policy_artifact(script)

    action, diagnostics = script._predict_policy_action_with_diagnostics(
        policy,
        metric_row={
            "phase": "APPROACH",
            "behavior_state_phase": "ALIGN",
            "lateral_error_m": 0.02,
            "orientation_error_deg": 0.0,
            "insertion_depth_m": 0.0,
            "relative_x_m": 0.02,
            "relative_y_m": 0.0,
            "env_native_success": False,
        },
        previous_action=[0.0] * len(script.ACTION_SCHEMA),
        action_scale=1.0,
        hysteresis_state=script.initial_v07e_hysteresis_state(),
    )

    assert diagnostics["post_adapter_action_vector"] == pytest.approx(action.tolist())
    assert diagnostics["no_mutation_after_final_post_adapter_authority"] is True


def test_v07e_runtime_records_xy_saturation_chatter_diagnostics() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    policy = _v07e_policy_artifact(script)

    _action, diagnostics = script._predict_policy_action_with_diagnostics(
        policy,
        metric_row={
            "phase": "APPROACH",
            "behavior_state_phase": "ALIGN",
            "lateral_error_m": 0.0016,
            "orientation_error_deg": 0.0,
            "insertion_depth_m": 0.0,
            "relative_x_m": 0.034,
            "relative_y_m": 0.0,
            "env_native_success": False,
        },
        previous_action=[0.0] * len(script.ACTION_SCHEMA),
        action_scale=1.0,
        hysteresis_state={
            "current_hysteresis_phase": "DESCEND",
            "z_window_remaining_steps": 20,
            "entered_descend_step": 4,
            "last_z_motion_allowed": True,
            "hard_safety_escape_triggered": False,
        },
    )

    assert diagnostics["xy_saturation_rate_during_z_open"] >= 0.0
    assert diagnostics["lateral_gate_exit_step"] is not None
    assert diagnostics["z_motion_block_reason_after_gate_exit"] in {
        "z_motion_allowed_by_v07e_hysteresis",
        "hard_safety_escape_triggered",
    }


def test_v07e_runtime_applies_same_hysteresis_config_to_baseline_and_candidate() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    candidate = _v07e_policy_artifact(script, role="candidate")
    baseline = _v07e_policy_artifact(script, role="baseline")

    assert candidate["shared_hysteresis_authority_config_sha256"] == baseline[
        "shared_hysteresis_authority_config_sha256"
    ]
    assert script._validated_v07e_hysteresis_authority_config(candidate) == script._validated_v07e_hysteresis_authority_config(
        baseline
    )

    candidate["shared_hysteresis_authority_config"] = _v07e_hysteresis_authority_config(
        script,
        parent_policy=candidate,
        candidate_specific=True,
    )
    candidate["shared_hysteresis_authority_config_sha256"] = candidate[
        "shared_hysteresis_authority_config"
    ]["shared_hysteresis_authority_config_sha256"]
    with pytest.raises(ValueError, match="v0_7e_hysteresis_config_must_be_shared"):
        script._validated_v07e_hysteresis_authority_config(candidate)


def test_v07c_runtime_fails_closed_without_authority_metadata() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    policy = _v07c_eval_policy(script)
    del policy["authority_filter_config_sha256"]

    with pytest.raises(ValueError, match="v0_7c_authority_metadata_missing"):
        script._predict_policy_action_with_diagnostics(
            policy,
            metric_row={
                "phase": "APPROACH",
                "env_native_success_mask": False,
                "insertion_depth_m": 0.0,
                "relative_x_m": 0.2,
                "relative_y_m": 0.0,
                "lateral_error_m": 0.2,
                "orientation_error_deg": 0.0,
            },
            previous_action=[0.0] * len(script.ACTION_SCHEMA),
            action_scale=1.0,
        )


def test_v07c_runtime_rejects_authority_hash_mismatch() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    policy = _v07c_eval_policy(script)
    policy["authority_filter_config_sha256"] = "wrong"

    with pytest.raises(ValueError, match="v0_7c_authority_config_hash_mismatch"):
        script._predict_policy_action_with_diagnostics(
            policy,
            metric_row={
                "phase": "APPROACH",
                "env_native_success_mask": False,
                "insertion_depth_m": 0.0,
                "relative_x_m": 0.2,
                "relative_y_m": 0.0,
                "lateral_error_m": 0.2,
                "orientation_error_deg": 0.0,
            },
            previous_action=[0.0] * len(script.ACTION_SCHEMA),
            action_scale=1.0,
        )


def test_v07c_runtime_rejects_wrong_authority_filter_id() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    config = _v07c_authority_config(script, filter_id="wrong_filter")
    policy = _v07c_eval_policy(script, authority_config=config)

    with pytest.raises(ValueError, match="v0_7c_authority_filter_mismatch"):
        script._predict_policy_action_with_diagnostics(
            policy,
            metric_row={
                "phase": "APPROACH",
                "env_native_success_mask": False,
                "insertion_depth_m": 0.0,
                "relative_x_m": 0.2,
                "relative_y_m": 0.0,
                "lateral_error_m": 0.2,
                "orientation_error_deg": 0.0,
            },
            previous_action=[0.0] * len(script.ACTION_SCHEMA),
            action_scale=1.0,
        )


def test_v07c_runtime_logs_before_after_authority_and_adapter() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    policy = _v07c_eval_policy(script)

    _, diagnostics = script._predict_policy_action_with_diagnostics(
        policy,
        metric_row={
            "phase": "APPROACH",
            "env_native_success_mask": False,
            "insertion_depth_m": 0.0,
            "relative_x_m": 0.2,
            "relative_y_m": 0.0,
            "lateral_error_m": 0.2,
            "orientation_error_deg": 0.0,
        },
        previous_action=[0.0] * len(script.ACTION_SCHEMA),
        action_scale=1.0,
    )

    for key in (
        "behavior_state_phase",
        "base_servo_action",
        "residual_prediction",
        "raw_action_before_authority",
        "raw_action_after_authority",
        "post_adapter_action_vector",
        "authority_filter_id",
        "authority_filter_config_sha256",
        "align_residual_z_suppressed",
        "residual_z_before_authority",
        "residual_z_after_authority",
        "z_authority_source",
    ):
        assert key in diagnostics


def test_v07c_runtime_align_z_authority_applied_before_adapter() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    policy = _v07c_eval_policy(script)

    action, diagnostics = script._predict_policy_action_with_diagnostics(
        policy,
        metric_row={
            "phase": "APPROACH",
            "env_native_success_mask": False,
            "insertion_depth_m": 0.0,
            "relative_x_m": 0.2,
            "relative_y_m": 0.0,
            "lateral_error_m": 0.2,
            "orientation_error_deg": 0.0,
        },
        previous_action=[0.0] * len(script.ACTION_SCHEMA),
        action_scale=1.0,
    )

    assert diagnostics["behavior_state_phase"] == "ALIGN"
    assert diagnostics["raw_action_before_authority"][2] == pytest.approx(-0.091)
    assert diagnostics["raw_action_after_authority"][2] == pytest.approx(-0.001)
    assert diagnostics["post_adapter_action_vector"][2] == pytest.approx(-0.001)
    assert action.tolist()[2] == pytest.approx(-0.001)
    assert diagnostics["residual_z_after_authority"] == pytest.approx(0.0)
    assert diagnostics["z_authority_source"] == "base_servo"


def test_v07c_runtime_descend_keeps_residual_z_before_adapter() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    policy = _v07c_eval_policy(script)

    action, diagnostics = script._predict_policy_action_with_diagnostics(
        policy,
        metric_row={
            "phase": "INSERT",
            "env_native_success_mask": False,
            "insertion_depth_m": 0.02,
            "relative_x_m": 0.0,
            "relative_y_m": 0.0,
            "lateral_error_m": 0.0,
            "orientation_error_deg": 0.0,
        },
        previous_action=[0.0] * len(script.ACTION_SCHEMA),
        action_scale=1.0,
    )

    assert diagnostics["behavior_state_phase"] == "DESCEND"
    assert diagnostics["raw_action_after_authority"] == diagnostics["raw_action_before_authority"]
    assert diagnostics["post_adapter_action_vector"][2] == pytest.approx(-0.092)
    assert action.tolist()[2] == pytest.approx(-0.092)
    assert diagnostics["z_authority_source"] == "base_plus_residual"


def test_v07d_runtime_blocks_align_z_after_selected_adapter_scale() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    policy = _v07d_policy_artifact(script)
    raw_action = script.np.array([0.0, 0.0, -0.001, 0.0, 0.0, 0.0, 1.0], dtype=script.np.float64)

    action, diagnostics = script._apply_selected_action_adapter_with_diagnostics(
        policy_artifact=policy,
        raw_action=raw_action,
        action_scale=1.0,
        metric_row={
            "phase": "APPROACH",
            "behavior_state_phase": "ALIGN",
            "lateral_error_m": 0.03,
            "orientation_error_deg": 0.0,
            "insertion_depth_m": 0.0,
            "env_native_success": False,
            "env_native_current_consecutive_success_steps": 0,
        },
        behavior_state_phase="ALIGN",
    )

    assert diagnostics["pre_final_authority_action_vector"][2] == pytest.approx(-0.032)
    assert action.tolist()[2] == pytest.approx(0.0)
    assert diagnostics["post_adapter_action_vector"][2] == pytest.approx(0.0)
    assert diagnostics["final_post_adapter_authority_id"] == "final_post_adapter_z_authority_gate_v0_7d"
    assert diagnostics["z_motion_block_reason"] == "final_post_adapter_align_z_blocked"


def test_v07d_runtime_final_z_gate_is_config_independent() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    policy = _v07d_policy_artifact(script, include_controller_version=False)

    action, diagnostics = script._apply_selected_action_adapter_with_diagnostics(
        policy_artifact=policy,
        raw_action=script.np.array([0.0, 0.0, -0.001, 0.0, 0.0, 0.0, 1.0], dtype=script.np.float64),
        action_scale=1.0,
        metric_row={"phase": "APPROACH", "behavior_state_phase": "ALIGN", "lateral_error_m": 0.02},
        behavior_state_phase="ALIGN",
    )

    assert action.tolist()[2] == pytest.approx(0.0)
    assert diagnostics["z_motion_block_reason"] == "final_post_adapter_align_z_blocked"
    assert diagnostics["z_motion_block_reason"] != "adapter_not_instrumented"


def test_v07d_runtime_rejects_missing_selected_adapter_config() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    policy = _v07d_policy_artifact(script)
    del policy["selected_action_adapter_config"]

    with pytest.raises(ValueError, match="v0_7d_selected_action_adapter_config_missing"):
        script._apply_selected_action_adapter_with_diagnostics(
            policy_artifact=policy,
            raw_action=script.np.array([0.0, 0.0, -0.001, 0.0, 0.0, 0.0, 1.0], dtype=script.np.float64),
            action_scale=1.0,
            metric_row={"phase": "APPROACH", "behavior_state_phase": "ALIGN", "lateral_error_m": 0.02},
            behavior_state_phase="ALIGN",
        )


def test_v07d_runtime_rejects_selected_adapter_config_hash_mismatch() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    policy = _v07d_policy_artifact(script)
    policy["selected_action_adapter_config_sha256"] = "stale-selected-adapter-config-hash"

    with pytest.raises(ValueError, match="v0_7d_selected_action_adapter_config_hash_mismatch"):
        script._apply_selected_action_adapter_with_diagnostics(
            policy_artifact=policy,
            raw_action=script.np.array([0.0, 0.0, -0.001, 0.0, 0.0, 0.0, 1.0], dtype=script.np.float64),
            action_scale=1.0,
            metric_row={"phase": "APPROACH", "behavior_state_phase": "ALIGN", "lateral_error_m": 0.02},
            behavior_state_phase="ALIGN",
        )


def test_v07d_runtime_stable_hold_uses_env_native_mask() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    policy = _v07d_policy_artifact(script)

    action, diagnostics = script._apply_selected_action_adapter_with_diagnostics(
        policy_artifact=policy,
        raw_action=script.np.zeros(len(script.ACTION_SCHEMA), dtype=script.np.float64),
        action_scale=1.0,
        metric_row={
            "phase": "SEAT",
            "behavior_state_phase": "HOLD",
            "insertion_depth_m": 0.0245,
            "lateral_error_m": 0.02,
            "orientation_error_deg": 0.0,
            "env_native_success_mask": True,
        },
        behavior_state_phase="HOLD",
    )

    assert diagnostics["stable_hold_authority"] == "env_native_success_mask"
    assert diagnostics["z_motion_block_reason"] == "stable_hold_ready_env_native"
    assert action.tolist() == pytest.approx([0.0, 0.0, -0.02, 0.0, 0.0, 0.0, 1.0])


def test_v07d_runtime_rejects_conflicting_env_native_hold_mask() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    policy = _v07d_policy_artifact(script)

    with pytest.raises(ValueError, match="env_native_mask_conflict"):
        script._apply_selected_action_adapter_with_diagnostics(
            policy_artifact=policy,
            raw_action=script.np.zeros(len(script.ACTION_SCHEMA), dtype=script.np.float64),
            action_scale=1.0,
            metric_row={
                "phase": "SEAT",
                "behavior_state_phase": "HOLD",
                "insertion_depth_m": 0.0245,
                "lateral_error_m": 0.02,
                "orientation_error_deg": 0.0,
                "env_native_success": False,
                "env_native_success_mask": True,
            },
            behavior_state_phase="HOLD",
        )


def test_v07d_runtime_does_not_hold_when_geometry_true_but_env_native_false() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    policy = _v07d_policy_artifact(script)

    _action, diagnostics = script._apply_selected_action_adapter_with_diagnostics(
        policy_artifact=policy,
        raw_action=script.np.zeros(len(script.ACTION_SCHEMA), dtype=script.np.float64),
        action_scale=1.0,
        metric_row={
            "phase": "SEAT",
            "behavior_state_phase": "HOLD",
            "insertion_depth_m": 0.031,
            "lateral_error_m": 0.001,
            "orientation_error_deg": 0.0,
            "env_native_success": False,
        },
        behavior_state_phase="HOLD",
    )

    assert diagnostics["stable_hold_authority"] == "env_native_success_mask"
    assert diagnostics["z_motion_block_reason"] != "stable_hold_ready_env_native"


def test_v07d_runtime_rejects_geometry_threshold_stable_hold_authority() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    policy = _v07d_policy_artifact(script, stable_hold_authority="geometry_thresholds")

    with pytest.raises(ValueError, match="v0_7d_stable_hold_authority_mismatch"):
        script._validated_v07d_final_action_authority_config(policy)


def test_v07d_runtime_rejects_inherited_authority_hash_mismatch() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    policy = _v07d_policy_artifact(script)
    final_config = dict(policy["final_post_adapter_authority_config"])
    final_config["inherited_authority_filter_config_sha256"] = "stale-v0-7c-authority-hash"
    final_config["final_post_adapter_authority_config_sha256"] = script._sha256_payload_excluding(
        final_config,
        "final_post_adapter_authority_config_sha256",
    )
    policy["final_post_adapter_authority_config"] = final_config
    policy["final_post_adapter_authority_config_sha256"] = final_config[
        "final_post_adapter_authority_config_sha256"
    ]

    with pytest.raises(ValueError, match="v0_7d_inherited_authority_config_hash_mismatch"):
        script._validated_v07d_final_action_authority_config(policy)


def test_v07d_full_policy_inference_uses_v07c_base_and_final_authority() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    policy = _v07d_policy_artifact(script)

    action, diagnostics = script._predict_policy_action_with_diagnostics(
        policy,
        metric_row={
            "phase": "APPROACH",
            "behavior_state_phase": "ALIGN",
            "lateral_error_m": 0.03,
            "orientation_error_deg": 0.0,
            "insertion_depth_m": 0.0,
            "relative_x_m": 0.03,
            "relative_y_m": 0.0,
            "env_native_success": False,
        },
        previous_action=[0.0] * len(script.ACTION_SCHEMA),
        action_scale=1.0,
    )

    assert diagnostics["policy_slice"] == "v0_7d"
    assert diagnostics["base_servo_source_policy_slice"] == "v0_7c"
    assert diagnostics["pre_adapter_authority_source_policy_slice"] == "v0_7c"
    assert diagnostics["selected_action_adapter_id"] == "isaac_signed_xy_downward_servo_v0"
    assert diagnostics["final_post_adapter_authority_id"] == "final_post_adapter_z_authority_gate_v0_7d"
    assert action.tolist()[2] == pytest.approx(0.0)


def test_v08k_runtime_inherits_v08h_authority_lineage() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    policy = _v08k_policy_artifact(script)

    action, diagnostics = script._predict_policy_action_with_diagnostics(
        policy,
        metric_row={
            "step": 60,
            "phase": "APPROACH",
            "behavior_state_phase": "ALIGN",
            "lateral_error_m": 0.002,
            "orientation_error_deg": 0.0,
            "insertion_depth_m": 0.0,
            "relative_x_m": 0.002,
            "relative_y_m": 0.0,
            "env_native_success": False,
            "env_native_current_consecutive_success_steps": 0,
        },
        previous_action=[0.0] * len(script.ACTION_SCHEMA),
        action_scale=1.0,
    )

    assert diagnostics["policy_slice"] == "v0_8k"
    assert diagnostics["base_servo_id"] == "frozen_base_geometry_servo_v0_7b"
    assert diagnostics["base_servo_source_policy_slice"] == "v0_7c"
    assert diagnostics["pre_adapter_authority_source_policy_slice"] == "v0_7c"
    assert diagnostics["shared_hysteresis_authority_id"] == "shared_stateful_hysteresis_authority_v0_7e"
    assert diagnostics["final_post_adapter_authority_id"] == "final_post_adapter_z_authority_gate_v0_7d"
    assert diagnostics["final_post_adapter_xy_authority_id"] == "final_post_adapter_xy_authority_gate_v0_7o"
    assert diagnostics["early_centered_z_open_safe_entry_authority_id"] == (
        "early_centered_z_open_safe_entry_authority_v0_8h"
    )
    assert diagnostics["selected_action_adapter_id"] == "isaac_signed_xy_downward_servo_v0"
    assert diagnostics["z_motion_block_reason"] != "adapter_not_instrumented"
    assert diagnostics["no_mutation_after_final_post_adapter_authority"] is True
    assert action.tolist()[2] <= 0.0


def test_v09_runtime_inherits_v08h_authority_lineage() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    policy = _v09_policy_artifact(script)

    action, diagnostics = script._predict_policy_action_with_diagnostics(
        policy,
        metric_row={
            "step": 60,
            "phase": "APPROACH",
            "behavior_state_phase": "ALIGN",
            "lateral_error_m": 0.002,
            "orientation_error_deg": 0.0,
            "insertion_depth_m": 0.0,
            "relative_x_m": 0.002,
            "relative_y_m": 0.0,
            "env_native_success": False,
            "env_native_current_consecutive_success_steps": 0,
        },
        previous_action=[0.0] * len(script.ACTION_SCHEMA),
        action_scale=1.0,
    )

    assert diagnostics["policy_slice"] == "v0_9"
    assert diagnostics["base_servo_id"] == "frozen_base_geometry_servo_v0_7b"
    assert diagnostics["base_servo_source_policy_slice"] == "v0_7c"
    assert diagnostics["pre_adapter_authority_source_policy_slice"] == "v0_7c"
    assert diagnostics["shared_hysteresis_authority_id"] == "shared_stateful_hysteresis_authority_v0_7e"
    assert diagnostics["final_post_adapter_authority_id"] == "final_post_adapter_z_authority_gate_v0_7d"
    assert diagnostics["final_post_adapter_xy_authority_id"] == "final_post_adapter_xy_authority_gate_v0_7o"
    assert diagnostics["early_centered_z_open_safe_entry_authority_id"] == (
        "early_centered_z_open_safe_entry_authority_v0_8h"
    )
    assert diagnostics["selected_action_adapter_id"] == "isaac_signed_xy_downward_servo_v0"
    assert diagnostics["z_motion_block_reason"] != "adapter_not_instrumented"
    assert diagnostics["no_mutation_after_final_post_adapter_authority"] is True
    assert action.tolist()[2] <= 0.0


def test_mvp2b_feature_schema_includes_signed_relative_offsets(tmp_path: Path) -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    report = script.build_mvp2b_isaac_proof_evaluator(
        output_dir=tmp_path / "mvp2b",
        clean=True,
        skip_isaac=True,
        min_rollouts_per_policy=20,
    )

    schema = report["training_views"]["candidate"]["feature_schema"]
    assert "relative_x_m" in schema
    assert "relative_y_m" in schema
    assert report["policy_artifacts"]["baseline"]["feature_schema"] == schema
    assert report["policy_artifacts"]["candidate"]["feature_schema"] == schema


def test_mvp2b_generated_success_rows_encode_signed_offset_corrections(tmp_path: Path) -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    manifest = script.build_scenario_manifest(output_dir=tmp_path / "mvp2b")

    bundle = script.generate_training_trajectory_bundle(
        manifest=manifest,
        output_dir=tmp_path / "mvp2b",
    )

    row = next(
        item
        for item in bundle["training_rows"]
        if item["accepted"] is True and abs(float(item["relative_x_m"])) > 0.0
    )
    action = row["normalized_action"]
    assert row["lateral_error_m"] > 0.0
    assert action[0] == -round(float(row["relative_x_m"]) * script.XY_CORRECTION_GAIN, 6)
    assert action[1] == -round(float(row["relative_y_m"]) * script.XY_CORRECTION_GAIN, 6)


def test_mvp2b_isaac_metric_row_reports_signed_relative_offsets() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")

    class FakeTensor:
        def __init__(self, value: list[list[float]]) -> None:
            self.value = value

        def detach(self) -> "FakeTensor":
            return self

        def cpu(self) -> "FakeTensor":
            return self

        def numpy(self) -> Any:
            import numpy as np

            return np.asarray(self.value, dtype=float)

    class FakeUnwrapped:
        physics_dt = 1.0 / 60.0
        held_pos = FakeTensor([[0.5, 1.0, 0.01]])
        fixed_pos = FakeTensor([[0.25, 0.75, 0.0]])
        held_quat = FakeTensor([[0.0, 1.0, 0.0, 0.0]])

        def _compute_intermediate_values(self, *, dt: float) -> None:
            assert dt == self.physics_dt

    class FakeEnv:
        unwrapped = FakeUnwrapped()

    backend = script.IsaacConnectorInsertionEvaluatorBackend(device="cpu")
    row = backend._metric_row(env=FakeEnv(), step=7)

    assert row["relative_x_m"] == 0.25
    assert row["relative_y_m"] == 0.25
    assert row["lateral_error_m"] == 0.353553


def test_mvp2b_isaac_metric_row_uses_factory_native_diagnostics_when_available(monkeypatch: Any) -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")

    class FakeTensor:
        def __init__(self, value: list[list[float]]) -> None:
            self.value = value

        def detach(self) -> "FakeTensor":
            return self

        def cpu(self) -> "FakeTensor":
            return self

        def numpy(self) -> Any:
            import numpy as np

            return np.asarray(self.value, dtype=float)

    class FakeFixedAssetCfg:
        height = 0.025

    class FakeCfgTask:
        name = "peg_insert"
        fixed_asset_cfg = FakeFixedAssetCfg()
        success_threshold = 0.04

    class FakeUnwrapped:
        physics_dt = 1.0 / 60.0
        cfg_task = FakeCfgTask()
        held_pos = FakeTensor([[0.0, 0.0, 0.045]])
        fixed_pos = FakeTensor([[0.0, 0.0, 0.0]])
        held_quat = FakeTensor([[1.0, 0.0, 0.0, 0.0]])
        fixed_quat = FakeTensor([[1.0, 0.0, 0.0, 0.0]])

        def _compute_intermediate_values(self, *, dt: float) -> None:
            assert dt == self.physics_dt

    class FakeEnv:
        unwrapped = FakeUnwrapped()

    monkeypatch.setattr(
        script,
        "_factory_peg_insert_base_target_pose_from_env",
        lambda _unwrapped: {
            "held_base_pos": [0.0, 0.0, 0.045],
            "held_base_quat": [1.0, 0.0, 0.0, 0.0],
            "target_held_base_pos": [0.0, 0.0, 0.0],
            "target_held_base_quat": [1.0, 0.0, 0.0, 0.0],
        },
    )

    backend = script.IsaacConnectorInsertionEvaluatorBackend(device="cpu")
    row = backend._metric_row(env=FakeEnv(), step=7)

    assert row["rdf_metric_semantics"] == "factory_native_aligned_v0_6b"
    assert row["env_native_diagnostics_source"] == "factory_utils_base_target"
    assert row["env_native_height_threshold_m"] == 0.001
    assert row["env_native_success_mask"] is False
    assert row["legacy_positive_z_disp_m"] == 0.045
    assert row["runtime_depth_feature_m"] == 0.0
    assert row["phase"] == "APPROACH"


def test_v06g_rollout_budget_never_steps_past_env_reset_boundary(tmp_path: Path, monkeypatch: Any) -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")

    class FakeActionSpace:
        shape = (len(script.ACTION_SCHEMA),)

    class FakeEnv:
        unwrapped: Any
        action_space = FakeActionSpace()
        device = "cpu"
        max_episode_length = 148

        def __init__(self) -> None:
            self.unwrapped = self
            self.step_count = 0

        def reset(self, *, seed: int) -> None:
            assert seed == 19000

        def step(self, action: Any) -> None:
            del action
            self.step_count += 1

    class FakeSimulationApp:
        def is_running(self) -> bool:
            return True

    class FakeTorch:
        float32 = "float32"

        @staticmethod
        def as_tensor(value: Any, *, dtype: Any, device: str) -> Any:
            del dtype, device
            return value

    fake_env = FakeEnv()
    backend = script.IsaacConnectorInsertionEvaluatorBackend(device="cpu", max_steps=150)
    monkeypatch.setattr(backend, "_apply_scenario_initial_offset", lambda **_: {"applied": True})
    monkeypatch.setattr(
        backend,
        "_metric_row",
        lambda *, env, step: {
            "step": step,
            "phase": "APPROACH",
            "insertion_depth_m": 0.0,
            "relative_x_m": 0.0,
            "relative_y_m": 0.0,
            "lateral_error_m": 0.01,
            "orientation_error_deg": 0.0,
        },
    )
    monkeypatch.setattr(
        script,
        "_predict_policy_action_with_diagnostics",
        lambda *_, **__: (script.np.zeros(len(script.ACTION_SCHEMA), dtype=float), {}),
    )
    monkeypatch.setattr(script, "_read_env_native_success", lambda _env: False)

    trace_path, rollout = backend._run_one_rollout(
        env=fake_env,
        simulation_app=FakeSimulationApp(),
        torch=FakeTorch(),
        policy_artifact={"policy_id": "fake_policy"},
        scenario={"scenario_id": "v06g_fake_boundary", "seed": 19000},
        role="v0_6_repair_probe",
        rollout_index=0,
        trace_dir=tmp_path,
        manifest={
            "manifest_sha256": "manifest",
            "success_metric": script.SUCCESS_METRIC,
            "success_authority": {
                "primary": "isaac_env_native_consecutive_success_v0",
                "stable_steps_required": 10,
            },
        },
    )

    trace_payload = script.read_json(trace_path)
    assert fake_env.step_count == 146
    assert len(trace_payload["trace"]) == 146
    assert trace_payload["env_reset_boundary_steps"] == 148
    assert trace_payload["effective_rollout_budget_steps"] == 146
    assert trace_payload["env_reset_post_step_guard_steps"] == 2
    assert trace_payload["horizon_increase_applied"] is False
    assert rollout["env_reset_boundary_steps"] == 148
    assert rollout["effective_rollout_budget_steps"] == 146
    assert rollout["env_reset_post_step_guard_steps"] == 2


def test_v06g_budget_is_not_horizon_increase(tmp_path: Path, monkeypatch: Any) -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")

    class FakeActionSpace:
        shape = (len(script.ACTION_SCHEMA),)

    class FakeEnv:
        unwrapped: Any
        action_space = FakeActionSpace()
        device = "cpu"
        max_episode_length = 250

        def __init__(self) -> None:
            self.unwrapped = self
            self.step_count = 0

        def reset(self, *, seed: int) -> None:
            del seed

        def step(self, action: Any) -> None:
            del action
            self.step_count += 1

    class FakeSimulationApp:
        def is_running(self) -> bool:
            return True

    class FakeTorch:
        float32 = "float32"

        @staticmethod
        def as_tensor(value: Any, *, dtype: Any, device: str) -> Any:
            del dtype, device
            return value

    fake_env = FakeEnv()
    backend = script.IsaacConnectorInsertionEvaluatorBackend(device="cpu", max_steps=150)
    monkeypatch.setattr(backend, "_apply_scenario_initial_offset", lambda **_: {})
    monkeypatch.setattr(
        backend,
        "_metric_row",
        lambda *, env, step: {
            "step": step,
            "phase": "APPROACH",
            "insertion_depth_m": 0.0,
            "relative_x_m": 0.0,
            "relative_y_m": 0.0,
            "lateral_error_m": 0.01,
            "orientation_error_deg": 0.0,
        },
    )
    monkeypatch.setattr(
        script,
        "_predict_policy_action_with_diagnostics",
        lambda *_, **__: (script.np.zeros(len(script.ACTION_SCHEMA), dtype=float), {}),
    )
    monkeypatch.setattr(script, "_read_env_native_success", lambda _env: False)

    trace_path, rollout = backend._run_one_rollout(
        env=fake_env,
        simulation_app=FakeSimulationApp(),
        torch=FakeTorch(),
        policy_artifact={"policy_id": "fake_policy"},
        scenario={"scenario_id": "v06g_fake_no_increase", "seed": 19001},
        role="v0_6_repair_probe",
        rollout_index=0,
        trace_dir=tmp_path,
        manifest={
            "manifest_sha256": "manifest",
            "success_metric": script.SUCCESS_METRIC,
            "success_authority": {
                "primary": "isaac_env_native_consecutive_success_v0",
                "stable_steps_required": 10,
            },
        },
    )

    trace_payload = script.read_json(trace_path)
    assert fake_env.step_count == script.SUCCESS_METRIC["max_steps"]
    assert trace_payload["env_reset_boundary_steps"] == 250
    assert trace_payload["effective_rollout_budget_steps"] == script.SUCCESS_METRIC["max_steps"]
    assert trace_payload["env_reset_post_step_guard_steps"] == 2
    assert trace_payload["effective_rollout_budget_steps"] <= script.SUCCESS_METRIC["max_steps"]
    assert trace_payload["horizon_increase_applied"] is False
    assert rollout["effective_rollout_budget_steps"] <= script.SUCCESS_METRIC["max_steps"]


def test_v06g_rollout_budget_accounts_for_post_step_timeout_reset(tmp_path: Path, monkeypatch: Any) -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")

    class FakeActionSpace:
        shape = (len(script.ACTION_SCHEMA),)

    class FakeEnv:
        unwrapped: Any
        action_space = FakeActionSpace()
        device = "cpu"
        max_episode_length = 150

        def __init__(self) -> None:
            self.unwrapped = self
            self.step_count = 0

        def reset(self, *, seed: int) -> None:
            del seed

        def step(self, action: Any) -> None:
            del action
            self.step_count += 1

    class FakeSimulationApp:
        def is_running(self) -> bool:
            return True

    class FakeTorch:
        float32 = "float32"

        @staticmethod
        def as_tensor(value: Any, *, dtype: Any, device: str) -> Any:
            del dtype, device
            return value

    fake_env = FakeEnv()
    backend = script.IsaacConnectorInsertionEvaluatorBackend(device="cpu", max_steps=150)
    monkeypatch.setattr(backend, "_apply_scenario_initial_offset", lambda **_: {})
    monkeypatch.setattr(
        backend,
        "_metric_row",
        lambda *, env, step: {
            "step": step,
            "phase": "APPROACH",
            "insertion_depth_m": 0.0,
            "relative_x_m": 0.0,
            "relative_y_m": 0.0,
            "lateral_error_m": 0.01,
            "orientation_error_deg": 0.0,
        },
    )
    monkeypatch.setattr(
        script,
        "_predict_policy_action_with_diagnostics",
        lambda *_, **__: (script.np.zeros(len(script.ACTION_SCHEMA), dtype=float), {}),
    )
    monkeypatch.setattr(script, "_read_env_native_success", lambda _env: False)

    trace_path, rollout = backend._run_one_rollout(
        env=fake_env,
        simulation_app=FakeSimulationApp(),
        torch=FakeTorch(),
        policy_artifact={"policy_id": "fake_policy"},
        scenario={"scenario_id": "v06g_fake_post_step_timeout", "seed": 19002},
        role="v0_6_repair_probe",
        rollout_index=0,
        trace_dir=tmp_path,
        manifest={
            "manifest_sha256": "manifest",
            "success_metric": script.SUCCESS_METRIC,
            "success_authority": {
                "primary": "isaac_env_native_consecutive_success_v0",
                "stable_steps_required": 10,
            },
        },
    )

    trace_payload = script.read_json(trace_path)
    assert fake_env.step_count == 148
    assert len(trace_payload["trace"]) == 148
    assert trace_payload["env_reset_boundary_steps"] == 150
    assert trace_payload["effective_rollout_budget_steps"] == 148
    assert trace_payload["env_reset_post_step_guard_steps"] == 2
    assert rollout["effective_rollout_budget_steps"] == 148


def test_mvp2b_external_rollout_json_has_required_validator_metadata(tmp_path: Path) -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    report = script.build_mvp2b_isaac_proof_evaluator(
        output_dir=tmp_path / "mvp2b",
        clean=True,
        skip_isaac=False,
        use_deterministic_eval_backend=True,
        min_rollouts_per_policy=20,
    )

    baseline = script.read_json(Path(report["artifact_paths"]["baseline_external_rollouts"]))
    candidate = script.read_json(Path(report["artifact_paths"]["candidate_external_rollouts"]))
    assert baseline["source_kind"] == "external_heldout_policy_eval"
    assert candidate["proof_role"] == "external_trainer_policy_eval"
    assert baseline["heldout_suite"]["source_kind"] == "external_trainer_eval_suite"
    assert candidate["heldout_suite"]["proof_role"] == "external_policy_eval_suite"
    assert len(baseline["rollout_results"]) >= 20
    assert len(candidate["rollout_results"]) >= 20


def test_mvp2b_deterministic_backend_never_closes_mvp2_even_if_uplift_positive(tmp_path: Path) -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    report = script.build_mvp2b_isaac_proof_evaluator(
        output_dir=tmp_path / "mvp2b",
        clean=True,
        skip_isaac=False,
        use_deterministic_eval_backend=True,
        deterministic_profile="candidate_positive",
        min_rollouts_per_policy=20,
        bootstrap_iterations=200,
    )

    learning_report = script.read_json(Path(report["artifact_paths"]["mvp2_learning_proven_report"]))
    assert learning_report["curated_vs_uncurated_uplift"] >= 0.20
    assert report["runtime_backend"] == "deterministic_test_backend"
    assert report["proof_runtime"] == "test_only_not_isaac"
    assert report["runtime_gate"]["passed"] is False
    assert report["mvp2_closed"] is False
    assert report["proof_eligible"] is False


def test_mvp2b_default_path_dispatches_to_isaac_runtime_backend(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")

    class FakeIsaacBackend:
        runtime_backend = "isaac_runtime"
        proof_runtime = "dedicated_isaac_connector_insertion_evaluator"

        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

        def run(self, **kwargs: Any) -> Any:
            manifest = kwargs["manifest"]
            output_dir = kwargs["output_dir"]
            trace_dir = output_dir / "fake_isaac_traces"
            trace_dir.mkdir(parents=True, exist_ok=True)
            heldout = [row for row in manifest["scenarios"] if row["split"] == "held_out"]
            baseline_rollouts = []
            candidate_rollouts = []
            baseline_paths = []
            candidate_paths = []
            for index, scenario in enumerate(heldout):
                baseline_success = index < 8
                candidate_success = index < 14
                for role, success, rollouts, paths in (
                    ("baseline", baseline_success, baseline_rollouts, baseline_paths),
                    ("candidate", candidate_success, candidate_rollouts, candidate_paths),
                ):
                    trace_path = trace_dir / f"{role}_{index:04d}.json"
                    script.write_json(
                        trace_path,
                        {
                            "scenario_id": scenario["scenario_id"],
                            "role": role,
                            "runtime_backend": "isaac_runtime",
                            "trace": script._success_trace()
                            if success
                            else script._failure_trace("STABILITY_WINDOW_NOT_REACHED"),
                        },
                    )
                    paths.append(str(trace_path))
                    rollouts.append(
                        {
                            "rollout_id": f"{role}_fake_isaac_{index:04d}",
                            "scenario_id": scenario["scenario_id"],
                            "success": success,
                            "failure_reason": "" if success else "STABILITY_WINDOW_NOT_REACHED",
                            "steps": 12,
                            "rollout_log_ref": str(trace_path),
                        }
                    )
            return script.BackendResult(
                runtime_backend="isaac_runtime",
                proof_runtime="dedicated_isaac_connector_insertion_evaluator",
                runtime_gate={
                    "passed": True,
                    "runtime_backend": "isaac_runtime",
                    "proof_runtime": "dedicated_isaac_connector_insertion_evaluator",
                },
                baseline_rollouts=baseline_rollouts,
                candidate_rollouts=candidate_rollouts,
                baseline_trace_paths=baseline_paths,
                candidate_trace_paths=candidate_paths,
                runtime_metadata={
                    "runtime_backend": "isaac_runtime",
                    "proof_runtime": "dedicated_isaac_connector_insertion_evaluator",
                    "scenario_manifest_sha256": manifest["manifest_sha256"],
                    "isaac_task_or_scene_id": "test_fake_isaac_scene",
                    "headless": True,
                    "device": "cpu",
                },
            )

    monkeypatch.setattr(script, "IsaacConnectorInsertionEvaluatorBackend", FakeIsaacBackend)

    report = script.build_mvp2b_isaac_proof_evaluator(
        output_dir=tmp_path / "mvp2b",
        clean=True,
        skip_isaac=False,
        use_deterministic_eval_backend=False,
        min_rollouts_per_policy=20,
        bootstrap_iterations=200,
    )

    assert report["runtime_backend"] == "isaac_runtime"
    assert report["proof_runtime"] == "dedicated_isaac_connector_insertion_evaluator"
    assert report["mvp2_closed"] is True
    assert report["proof_eligible"] is True
    assert report["curated_vs_uncurated_uplift"] >= 0.20
    assert report["actual_rollouts_per_policy"] == 20


def test_mvp2b_closure_uses_actual_rollout_count_not_requested_count(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")

    class FakeIsaacBackend:
        runtime_backend = "isaac_runtime"
        proof_runtime = "dedicated_isaac_connector_insertion_evaluator"

        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

        def run(self, **kwargs: Any) -> Any:
            manifest = kwargs["manifest"]
            output_dir = kwargs["output_dir"]
            trace_dir = output_dir / "fake_isaac_traces"
            trace_dir.mkdir(parents=True, exist_ok=True)
            heldout = [row for row in manifest["scenarios"] if row["split"] == "held_out"]
            baseline_rollouts = []
            candidate_rollouts = []
            baseline_paths = []
            candidate_paths = []
            for index, scenario in enumerate(heldout):
                for role, success, rollouts, paths in (
                    ("baseline", index < 8, baseline_rollouts, baseline_paths),
                    ("candidate", index < 14, candidate_rollouts, candidate_paths),
                ):
                    trace_path = trace_dir / f"{role}_{index:04d}.json"
                    script.write_json(
                        trace_path,
                        {
                            "scenario_id": scenario["scenario_id"],
                            "role": role,
                            "runtime_backend": "isaac_runtime",
                            "trace": script._success_trace()
                            if success
                            else script._failure_trace("STABILITY_WINDOW_NOT_REACHED"),
                        },
                    )
                    paths.append(str(trace_path))
                    rollouts.append(
                        {
                            "rollout_id": f"{role}_fake_isaac_{index:04d}",
                            "scenario_id": scenario["scenario_id"],
                            "success": success,
                            "failure_reason": "" if success else "STABILITY_WINDOW_NOT_REACHED",
                            "steps": 12,
                            "rollout_log_ref": str(trace_path),
                        }
                    )
            return script.BackendResult(
                runtime_backend="isaac_runtime",
                proof_runtime="dedicated_isaac_connector_insertion_evaluator",
                runtime_gate={
                    "passed": True,
                    "runtime_backend": "isaac_runtime",
                    "proof_runtime": "dedicated_isaac_connector_insertion_evaluator",
                },
                baseline_rollouts=baseline_rollouts,
                candidate_rollouts=candidate_rollouts,
                baseline_trace_paths=baseline_paths,
                candidate_trace_paths=candidate_paths,
                runtime_metadata={
                    "runtime_backend": "isaac_runtime",
                    "proof_runtime": "dedicated_isaac_connector_insertion_evaluator",
                    "scenario_manifest_sha256": manifest["manifest_sha256"],
                },
            )

    monkeypatch.setattr(script, "IsaacConnectorInsertionEvaluatorBackend", FakeIsaacBackend)

    report = script.build_mvp2b_isaac_proof_evaluator(
        output_dir=tmp_path / "mvp2b",
        clean=True,
        skip_isaac=False,
        use_deterministic_eval_backend=False,
        min_rollouts_per_policy=2,
        bootstrap_iterations=200,
    )

    assert report["requested_rollouts_per_policy"] == 2
    assert report["actual_rollouts_per_policy"] == 20
    assert report["mvp2_closed"] is True


def test_mvp2b_isaac_runtime_gate_and_learning_report_close_together() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")

    closure = script.derive_mvp2b_closure(
        learning_report={
            "learning_proven": True,
            "proof_eligible": True,
            "curated_vs_uncurated_uplift": 0.25,
        },
        runtime_gate={
            "passed": True,
            "runtime_backend": "isaac_runtime",
            "proof_runtime": "dedicated_isaac_connector_insertion_evaluator",
        },
    )

    assert closure["mvp2_closed"] is True
    assert closure["proof_eligible"] is True


def test_mvp2b_closure_requires_at_least_twenty_rollouts_per_policy() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")

    closure = script.derive_mvp2b_closure(
        learning_report={
            "learning_proven": True,
            "proof_eligible": True,
            "curated_vs_uncurated_uplift": 0.25,
        },
        runtime_gate={
            "passed": True,
            "runtime_backend": "isaac_runtime",
            "proof_runtime": "dedicated_isaac_connector_insertion_evaluator",
        },
        min_rollouts_per_policy=2,
    )

    assert closure["mvp2_closed"] is False
    assert closure["proof_eligible"] is False
    assert any("20" in blocker for blocker in closure["blockers"])


def test_mvp2b_non_positive_uplift_keeps_mvp2_open(tmp_path: Path) -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    report = script.build_mvp2b_isaac_proof_evaluator(
        output_dir=tmp_path / "mvp2b",
        clean=True,
        skip_isaac=False,
        use_deterministic_eval_backend=True,
        deterministic_profile="tie",
        min_rollouts_per_policy=20,
        bootstrap_iterations=200,
    )

    assert report["mvp2_closed"] is False
    assert report["learning_proven"] is False


def test_mvp2b_threshold_freeze_rejects_post_heldout_threshold_change(tmp_path: Path) -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    manifest = script.build_scenario_manifest(output_dir=tmp_path / "mvp2b")

    result = script.validate_manifest_threshold_freeze(
        original_manifest=manifest,
        proposed_manifest={
            **manifest,
            "success_metric": {
                **manifest["success_metric"],
                "lateral_error_m_max": 0.010,
            },
        },
        heldout_results_exist=True,
    )

    assert result["passed"] is False
    assert result["requires_new_manifest_version"] is True


def test_mvp2b_skip_isaac_never_claims_proof(tmp_path: Path) -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    report = script.build_mvp2b_isaac_proof_evaluator(
        output_dir=tmp_path / "mvp2b",
        clean=True,
        skip_isaac=True,
        min_rollouts_per_policy=20,
    )

    assert report["mvp2_closed"] is False
    assert report["proof_eligible"] is False
    assert report["runtime_backend"] == "skipped"


def test_mvp2b_hmd_openxr_is_not_primary_path(tmp_path: Path) -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    report = script.build_mvp2b_isaac_proof_evaluator(
        output_dir=tmp_path / "mvp2b",
        clean=True,
        skip_isaac=True,
        min_rollouts_per_policy=20,
    )

    primary_claims = json.dumps(report["non_claims"]).lower()
    assert "hmd" in primary_claims
    assert "openxr" in primary_claims
    assert report["primary_proof_path"] == "dedicated_isaac_connector_insertion_evaluator"


def test_mvp2b_visual_evidence_paths_are_written_from_rollout_logs(tmp_path: Path) -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    report = script.build_mvp2b_isaac_proof_evaluator(
        output_dir=tmp_path / "mvp2b",
        clean=True,
        skip_isaac=False,
        use_deterministic_eval_backend=True,
        min_rollouts_per_policy=20,
    )

    visual_paths = report["visual_evidence"]
    assert Path(visual_paths["metric_trace_comparison_png"]).exists()
    assert Path(visual_paths["baseline_representative_rollout"]).exists()
    assert Path(visual_paths["candidate_representative_rollout"]).exists()
    assert report["visual_evidence_is_proof_override"] is False


def test_mvp2b_visual_source_trace_provenance_is_required(tmp_path: Path) -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    report = script.build_mvp2b_isaac_proof_evaluator(
        output_dir=tmp_path / "mvp2b",
        clean=True,
        skip_isaac=False,
        use_deterministic_eval_backend=True,
        min_rollouts_per_policy=20,
    )

    assert report["visual_evidence_is_proof_override"] is False
    assert report["visual_evidence_source"] in {"rollout_metric_traces", "isaac_runtime_capture"}
    assert report["visual_evidence_source_trace_paths"]
