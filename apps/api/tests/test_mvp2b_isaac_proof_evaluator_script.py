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
