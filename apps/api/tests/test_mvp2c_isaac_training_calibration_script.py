from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[3]


def load_script(name: str) -> Any:
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def write_actual_success_trace(script: Any, path: Path, *, scenario_id: str, seed: int) -> None:
    script.write_json(
        path,
        {
            "schema_version": "rdf_mvp2b_isaac_runtime_trace_v0.1.0",
            "runtime_backend": "isaac_runtime",
            "scenario": {"scenario_id": scenario_id, "seed": seed},
            "summary": {"success": True, "failure_reason": "", "steps": 3},
            "trace": [
                {
                    "step": 0,
                    "phase": "APPROACH",
                    "insertion_depth_m": 0.010,
                    "relative_x_m": 0.006,
                    "relative_y_m": -0.003,
                    "lateral_error_m": 0.0067,
                    "orientation_error_deg": 2.0,
                    "normalized_action": [-0.018, 0.009, -0.080, 0.0, 0.0, 0.0, 1.0],
                },
                {
                    "step": 1,
                    "phase": "INSERT",
                    "insertion_depth_m": 0.024,
                    "relative_x_m": 0.002,
                    "relative_y_m": -0.001,
                    "lateral_error_m": 0.0022,
                    "orientation_error_deg": 1.0,
                    "normalized_action": [-0.006, 0.003, -0.100, 0.0, 0.0, 0.0, 1.0],
                },
                {
                    "step": 2,
                    "phase": "SEAT",
                    "insertion_depth_m": 0.034,
                    "relative_x_m": 0.0,
                    "relative_y_m": 0.0,
                    "lateral_error_m": 0.001,
                    "orientation_error_deg": 0.5,
                    "normalized_action": [0.0, 0.0, -0.020, 0.0, 0.0, 0.0, 1.0],
                },
            ],
        },
    )


def v06a_branch_a_direction_results() -> dict[str, dict[str, Any]]:
    return {
        "+x": {"max_successful_delta_m": 0.0006, "nonzero_success_count": 3},
        "-x": {"max_successful_delta_m": 0.0006, "nonzero_success_count": 3},
        "+y": {"max_successful_delta_m": 0.0004, "nonzero_success_count": 2},
        "-y": {"max_successful_delta_m": 0.0006, "nonzero_success_count": 3},
    }


def write_valid_v06_repair_probe_gate(script: Any, path: Path, *, preflight: dict[str, Any]) -> dict[str, Any]:
    gate = {
        "proof_authority": False,
        "proof_runtime": "isaac_scripted_expert_repair_probe",
        "runtime_backend": "isaac_runtime",
        "probe_seeds": list(script.V06_REPAIR_PROBE_SEEDS),
        "hold_mode_passed": True,
        "lateral_success_mode_passed": True,
        "lateral_divergence_stopped": True,
        "green_light_for_40_run_gate": True,
        "hard_stop": False,
        "probe_results": {
            str(seed): {
                "env_native_rollout_success": True,
                "env_native_max_consecutive_success_steps": 10,
                "lateral_divergence_stopped": True,
            }
            for seed in script.V06_REPAIR_PROBE_SEEDS
        },
        "chamfer_preflight": preflight,
        "v0_6a_post_repair_probe_gate": {
            "green_light_for_40_run_gate": True,
            "reason": "repair_probe_green_light",
            "proof_authority": False,
        },
        "v0_6b_native_metric_trace_validation": {
            "valid": True,
            "reasons": [],
            "validated_trace_count": 3,
        },
    }
    gate["repair_probe_gate_sha256"] = script._sha256_payload_excluding(gate, "repair_probe_gate_sha256")
    script.write_json(path, gate)
    return gate


def test_mvp2c_scenario_manifest_is_pre_registered_and_hashed(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    manifest = script.build_mvp2c_scenario_manifest(output_dir=tmp_path / "mvp2c")

    assert manifest["manifest_version"] == "rdf_mvp2c_scenario_manifest_v0.1.0"
    assert manifest["success_metric"]["insertion_depth_m_min"] == 0.03
    assert manifest["success_metric"]["lateral_error_m_max"] == 0.006
    assert manifest["success_metric"]["orientation_error_deg_max"] == 8.0
    assert manifest["success_metric"]["stable_steps_required"] == 10
    assert manifest["success_metric"]["max_steps"] == 150
    assert manifest["manifest_sha256"]
    assert (tmp_path / "mvp2c" / "scenario_manifest.json").exists()


def test_mvp2c_scenario_manifest_uses_fresh_disjoint_seed_ranges(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    manifest = script.build_mvp2c_scenario_manifest(output_dir=tmp_path / "mvp2c")

    split_to_seeds = {
        split: {row["seed"] for row in manifest["scenarios"] if row["split"] == split}
        for split in ("train_success", "train_failure", "calibration", "held_out")
    }
    assert split_to_seeds["train_success"] == set(range(4000, 4080))
    assert split_to_seeds["train_failure"] == set(range(4100, 4180))
    assert split_to_seeds["calibration"] == set(range(5000, 5020))
    assert split_to_seeds["held_out"] == set(range(6000, 6020))
    assert split_to_seeds["held_out"].isdisjoint(set(range(3000, 3020)))
    for left_name, left_seeds in split_to_seeds.items():
        for right_name, right_seeds in split_to_seeds.items():
            if left_name != right_name:
                assert left_seeds.isdisjoint(right_seeds)


def test_mvp2c_scenario_manifest_v02_excludes_prior_heldout_ranges(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    manifest = script.build_mvp2c_scenario_manifest(output_dir=tmp_path / "mvp2c", scenario_profile="v0_2")

    split_to_seeds = {
        split: {row["seed"] for row in manifest["scenarios"] if row["split"] == split}
        for split in ("train_success", "train_failure", "calibration", "held_out")
    }

    assert manifest["manifest_version"] == "rdf_mvp2c_scenario_manifest_v0.2.0"
    assert split_to_seeds["train_success"] == set(range(7000, 7080))
    assert split_to_seeds["train_failure"] == set(range(7100, 7180))
    assert split_to_seeds["calibration"] == set(range(8000, 8020))
    assert split_to_seeds["held_out"] == set(range(9000, 9020))
    assert split_to_seeds["held_out"].isdisjoint(set(range(3000, 3020)))
    assert split_to_seeds["held_out"].isdisjoint(set(range(6000, 6020)))
    assert manifest["excluded_prior_heldout_seed_ranges"] == [[3000, 3019], [6000, 6019]]


def test_mvp2d_scenario_manifest_v03_burns_prior_heldout_ranges(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    manifest = script.build_mvp2c_scenario_manifest(output_dir=tmp_path / "mvp2d", scenario_profile="v0_3")

    split_to_seeds = {
        split: {row["seed"] for row in manifest["scenarios"] if row["split"] == split}
        for split in ("train_success", "train_failure", "calibration", "held_out")
    }

    assert manifest["manifest_version"] == "rdf_mvp2d_scenario_manifest_v0.3.0"
    assert split_to_seeds["train_success"] == set(range(10000, 10080))
    assert split_to_seeds["train_failure"] == set(range(10100, 10180))
    assert split_to_seeds["calibration"] == set(range(11000, 11020))
    assert split_to_seeds["held_out"] == set(range(12000, 12020))
    assert manifest["excluded_prior_heldout_seed_ranges"] == [[3000, 3019], [6000, 6019], [9000, 9019]]
    for start, end in manifest["excluded_prior_heldout_seed_ranges"]:
        assert split_to_seeds["held_out"].isdisjoint(set(range(start, end + 1)))


def test_mvp2d_scenario_manifest_v04_burns_v03_diagnostic_heldout(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    manifest = script.build_mvp2c_scenario_manifest(output_dir=tmp_path / "mvp2d", scenario_profile="v0_4")

    split_to_seeds = {
        split: {row["seed"] for row in manifest["scenarios"] if row["split"] == split}
        for split in ("train_success", "train_failure", "calibration", "held_out")
    }

    assert manifest["manifest_version"] == "rdf_mvp2d_scenario_manifest_v0.4.0"
    assert split_to_seeds["train_success"] == set(range(13000, 13080))
    assert split_to_seeds["train_failure"] == set(range(13100, 13180))
    assert split_to_seeds["calibration"] == set(range(14000, 14020))
    assert split_to_seeds["held_out"] == set(range(15000, 15020))
    assert manifest["excluded_prior_heldout_seed_ranges"] == [
        [3000, 3019],
        [6000, 6019],
        [9000, 9019],
        [12000, 12019],
    ]
    for start, end in manifest["excluded_prior_heldout_seed_ranges"]:
        assert split_to_seeds["held_out"].isdisjoint(set(range(start, end + 1)))


def test_mvp2d_scenario_manifest_v05_burns_all_prior_heldout_ranges(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    manifest = script.build_mvp2c_scenario_manifest(output_dir=tmp_path / "mvp2d", scenario_profile="v0_5")

    split_to_seeds = {
        split: {row["seed"] for row in manifest["scenarios"] if row["split"] == split}
        for split in ("train_success", "train_failure", "calibration", "held_out")
    }

    assert manifest["manifest_version"] == "rdf_mvp2d_scenario_manifest_v0.5.0"
    assert split_to_seeds["train_success"] == set(range(16000, 16160))
    assert split_to_seeds["train_failure"] == set(range(16200, 16360))
    assert split_to_seeds["calibration"] == set(range(17000, 17030))
    assert split_to_seeds["held_out"] == set(range(18000, 18020))
    assert manifest["excluded_prior_heldout_seed_ranges"] == [
        [3000, 3019],
        [6000, 6019],
        [9000, 9019],
        [12000, 12019],
        [15000, 15019],
    ]
    for start, end in manifest["excluded_prior_heldout_seed_ranges"]:
        assert split_to_seeds["held_out"].isdisjoint(set(range(start, end + 1)))


def test_v06_scenario_manifest_uses_fresh_env_native_seed_ranges(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    manifest = script.build_mvp2c_scenario_manifest(output_dir=tmp_path / "mvp2e", scenario_profile="v0_6")

    assert manifest["scenario_profile"] == "v0_6"
    assert manifest["manifest_version"] == "rdf_mvp2e_scenario_manifest_v0.6.0"
    assert manifest["success_authority"]["primary"] == "isaac_env_native_consecutive_success_v0"
    assert manifest["success_authority"]["stable_steps_required"] == 10
    assert manifest["success_authority"]["check_rot"] is False

    split_to_seeds = {
        split: {row["seed"] for row in manifest["scenarios"] if row["split"] == split}
        for split in ("train_success", "train_failure", "calibration", "held_out")
    }
    assert split_to_seeds["train_success"] == set(range(19000, 19160))
    assert split_to_seeds["train_failure"] == set(range(19200, 19360))
    assert split_to_seeds["calibration"] == set(range(20000, 20030))
    assert split_to_seeds["held_out"] == set(range(21000, 21050))


def test_v06_manifest_excludes_prior_heldout_v05_train_and_probe_seeds(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    manifest = script.build_mvp2c_scenario_manifest(output_dir=tmp_path / "mvp2e", scenario_profile="v0_6")

    all_scenario_seeds = {row["seed"] for row in manifest["scenarios"]}
    excluded = set()
    for start, end in manifest["excluded_prior_heldout_seed_ranges"]:
        excluded.update(range(start, end + 1))

    assert {16023, 16042, 16096}.issubset(excluded)
    assert all_scenario_seeds.isdisjoint(excluded)
    assert all_scenario_seeds.isdisjoint(set(range(16000, 16160)))
    assert all_scenario_seeds.isdisjoint(set(range(18000, 18020)))


def test_v06_train_gate_seed_selection_is_deterministic_config_only(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    manifest_a = script.build_mvp2c_scenario_manifest(output_dir=tmp_path / "a", scenario_profile="v0_6")
    manifest_b = script.build_mvp2c_scenario_manifest(output_dir=tmp_path / "b", scenario_profile="v0_6")

    selection_a = manifest_a["v0_6_train_gate_seed_selection"]
    selection_b = manifest_b["v0_6_train_gate_seed_selection"]

    assert selection_a["source_range"] == [19000, 19159]
    assert len(selection_a["selected_40_seed_ids"]) == 40
    assert len(set(selection_a["selected_40_seed_ids"])) == 40
    assert set(selection_a["selected_40_seed_ids"]).issubset(set(range(19000, 19160)))
    assert selection_a["selected_40_seed_ids"] == selection_b["selected_40_seed_ids"]
    assert selection_a["selection_config_sha256"] == selection_b["selection_config_sha256"]
    assert selection_a["selected_seed_list_sha256"] == selection_b["selected_seed_list_sha256"]
    assert selection_a["uses_isaac_results"] is False
    assert selection_a["uses_rng"] is False


def test_lateral_divergence_stopped_uses_gap_derived_cap_and_last10_median() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    stopped = script.evaluate_lateral_divergence_stopped(
        lateral_errors_m=[0.0020, 0.0021, 0.0022, 0.0021, 0.0020, 0.0021, 0.0022, 0.0021, 0.0020, 0.0021],
        divergence_cap_m=0.008,
        final_drift_margin_m=0.002,
        last_k=10,
    )
    assert stopped["lateral_divergence_stopped"] is True

    divergent = script.evaluate_lateral_divergence_stopped(
        lateral_errors_m=[0.0020, 0.003, 0.006, 0.009, 0.011, 0.012, 0.012, 0.012, 0.012, 0.012],
        divergence_cap_m=0.008,
        final_drift_margin_m=0.002,
        last_k=10,
    )
    assert divergent["lateral_divergence_stopped"] is False
    assert divergent["max_lateral_error_m"] >= 0.008


def test_v06_repair_probe_green_light_requires_hold_and_lateral_modes() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    probe = script.evaluate_v06_repair_probe_gate(
        {
            16023: {"env_native_rollout_success": True, "env_native_max_consecutive_success_steps": 10},
            16042: {
                "env_native_rollout_success": True,
                "env_native_max_consecutive_success_steps": 10,
                "lateral_divergence_stopped": True,
            },
            16096: {
                "env_native_rollout_success": False,
                "env_native_max_consecutive_success_steps": 0,
                "lateral_divergence_stopped": True,
            },
        }
    )

    assert probe["green_light_for_40_run_gate"] is True
    assert probe["proof_authority"] is False


def test_v06_repair_probe_gate_rejects_rdf_only_success() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    gate = script.evaluate_v06_repair_probe_gate(
        {
            16023: {
                "env_native_rollout_success": False,
                "lateral_divergence_stopped": True,
                "rdf_peg_in_hole_metric": {"summary": {"success": True}},
            },
            16042: {
                "env_native_rollout_success": False,
                "lateral_divergence_stopped": True,
                "rdf_peg_in_hole_metric": {"summary": {"success": True}},
            },
            16096: {
                "env_native_rollout_success": False,
                "lateral_divergence_stopped": True,
                "rdf_peg_in_hole_metric": {"summary": {"success": True}},
            },
        }
    )

    assert gate["green_light_for_40_run_gate"] is False
    assert gate["hard_stop"] is True


def test_v06c_controller_action_diagnosis_summarizes_phase_mismatch_root_cause() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    diagnosis = script.summarize_v06c_controller_action_diagnosis(
        [
            {
                "step": step,
                "phase": "APPROACH",
                "lateral_error_m": 0.0003,
                "env_native_z_disp_m": 0.040,
                "normalized_action": [0.001, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
                "controller_action_diagnostics": {
                    "controller_version": "v0_6_active_state_controller",
                    "raw_action_vector": [0.0, 0.0, -0.005, 0.0, 0.0, 0.0, 1.0],
                    "pre_controller_action_vector": [0.0, 0.0, -0.12, 0.0, 0.0, 0.0, 1.0],
                    "post_adapter_action_vector": [0.001, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
                    "phase_vocabulary_mismatch": True,
                    "z_motion_suppressed": True,
                    "z_motion_block_reason": "controller_phase_vocabulary_mismatch",
                },
            }
            for step in range(12)
        ]
    )

    assert diagnosis["schema_version"] == "rdf_mvp2e_v06c_controller_action_diagnosis_v0.1.0"
    assert diagnosis["diagnosis_complete"] is True
    assert diagnosis["root_cause_hypothesis"] == "controller_phase_vocabulary_mismatch_blocks_z_motion"
    assert diagnosis["raw_negative_z_action_steps"] == 12
    assert diagnosis["final_negative_z_action_steps"] == 0
    assert diagnosis["z_motion_block_reason_counts"]["controller_phase_vocabulary_mismatch"] == 12


def test_v06b_trace_semantic_validator_requires_factory_base_target_source() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    verdict = script.validate_v06b_native_metric_trace_rows(
        [
            {
                "env_native_success": True,
                "env_native_success_mask": True,
                "env_native_diagnostics_source": "raw_asset_delta_approximation",
                "legacy_positive_z_disp_m": 0.045,
                "runtime_depth_feature_m": 0.0,
            }
        ]
    )

    assert verdict["valid"] is False
    assert "env_native_diagnostics_source" in verdict["reasons"]


def test_v06b_trace_semantic_validator_rejects_legacy_depth_feature_use() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    verdict = script.validate_v06b_native_metric_trace_rows(
        [
            {
                "env_native_success": False,
                "env_native_success_mask": False,
                "env_native_diagnostics_source": "factory_utils_base_target",
                "env_native_xy_dist_m": 0.0002,
                "env_native_z_disp_m": 0.045,
                "env_native_height_threshold_m": 0.001,
                "legacy_positive_z_disp_m": 0.045,
                "runtime_depth_feature_m": 0.045,
                "insertion_depth_m": 0.045,
                "held_asset_pose_w": {"position_m": [0, 0, 0.045], "quaternion_wxyz": [1, 0, 0, 0]},
                "fixed_asset_pose_w": {"position_m": [0, 0, 0], "quaternion_wxyz": [1, 0, 0, 0]},
                "held_base_pose_w": {"position_m": [0, 0, 0.045], "quaternion_wxyz": [1, 0, 0, 0]},
                "target_held_base_pose_w": {"position_m": [0, 0, 0], "quaternion_wxyz": [1, 0, 0, 0]},
            }
        ]
    )

    assert verdict["valid"] is False
    assert "runtime_depth_feature_m" in verdict["reasons"]


def test_v06b_trace_semantic_validator_requires_read_env_native_success_field() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    verdict = script.validate_v06b_native_metric_trace_rows(
        [
            {
                "env_native_success_mask": False,
                "env_native_diagnostics_source": "factory_utils_base_target",
                "env_native_xy_dist_m": 0.0002,
                "env_native_z_disp_m": 0.045,
                "env_native_height_threshold_m": 0.001,
                "legacy_positive_z_disp_m": 0.045,
                "runtime_depth_feature_m": 0.0,
                "held_asset_pose_w": {"position_m": [0, 0, 0.045], "quaternion_wxyz": [1, 0, 0, 0]},
                "fixed_asset_pose_w": {"position_m": [0, 0, 0], "quaternion_wxyz": [1, 0, 0, 0]},
                "held_base_pose_w": {"position_m": [0, 0, 0.045], "quaternion_wxyz": [1, 0, 0, 0]},
                "target_held_base_pose_w": {"position_m": [0, 0, 0], "quaternion_wxyz": [1, 0, 0, 0]},
            }
        ]
    )

    assert verdict["valid"] is False
    assert "missing_required_native_metric_fields" in verdict["reasons"]


def test_v06b_trace_semantic_validator_rejects_native_mask_mismatch() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    verdict = script.validate_v06b_native_metric_trace_rows(
        [
            {
                "env_native_success": True,
                "env_native_success_mask": False,
                "env_native_diagnostics_source": "factory_utils_base_target",
                "env_native_xy_dist_m": 0.0002,
                "env_native_z_disp_m": 0.045,
                "env_native_height_threshold_m": 0.001,
                "legacy_positive_z_disp_m": 0.045,
                "runtime_depth_feature_m": 0.0,
                "held_asset_pose_w": {"position_m": [0, 0, 0.045], "quaternion_wxyz": [1, 0, 0, 0]},
                "fixed_asset_pose_w": {"position_m": [0, 0, 0], "quaternion_wxyz": [1, 0, 0, 0]},
                "held_base_pose_w": {"position_m": [0, 0, 0.045], "quaternion_wxyz": [1, 0, 0, 0]},
                "target_held_base_pose_w": {"position_m": [0, 0, 0], "quaternion_wxyz": [1, 0, 0, 0]},
            }
        ]
    )

    assert verdict["valid"] is False
    assert "env_native_success_mask_mismatch" in verdict["reasons"]


def test_chamfer_preflight_branch_c_blocks_insert_probe_and_train_gate() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    preflight = script.evaluate_chamfer_preflight_gate(
        source_asset_paths=["missing_factory_hole_8mm.usd"],
        inspection_result={"chamfer_present": False, "inspection_method": "static_usd"},
    )

    assert preflight["preflight_branch"] == "C"
    assert preflight["insert_parameter_freeze_allowed"] is False
    assert preflight["repair_probe_allowed"] is False
    assert preflight["train_generation_gate_allowed"] is False


def test_v06a_geometry_probe_seed_namespace_is_disjoint_from_proof_seeds(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    manifest = script.build_mvp2c_scenario_manifest(output_dir=tmp_path / "mvp2e", scenario_profile="v0_6")

    geometry_seeds = set(script.V06A_CAPTURE_RADIUS_GEOMETRY_PROBE_SEEDS)
    scenario_seeds = {int(row["seed"]) for row in manifest["scenarios"]}

    assert script.V06A_CAPTURE_RADIUS_PRIMARY_SEED == 18500
    assert geometry_seeds == set(range(18500, 18510))
    assert geometry_seeds.isdisjoint(scenario_seeds)
    assert geometry_seeds.isdisjoint(set(script.V06_REPAIR_PROBE_SEEDS))
    assert geometry_seeds.isdisjoint(set(range(21000, 21050)))


def test_v06a_insert_envelope_is_pre_registered_and_not_probe_derived() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    assert script.V06A_PRE_REGISTERED_INSERT_ENVELOPE == {
        "vertical_push_scale": 24.0,
        "correction_gain_limit": 4.0,
        "max_insert_steps": 145,
        "rotation_action_scale": 0.0,
        "value_source": "frozen_v0_6_adapter_and_horizon_not_probe_results",
    }


def test_v06a_capture_radius_branch_a_requires_all_direction_capture(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    probe = script.build_v06a_capture_radius_probe_artifact(
        output_dir=tmp_path,
        measurement=script.evaluate_runtime_capture_radius_probe(
            {
                "runtime_loaded": True,
                "env_native_success_mask_available": True,
                "zero_offset_passed": True,
                "direction_results": v06a_branch_a_direction_results(),
            }
        ),
        prior_static_preflight={"preflight_branch": "C", "inspection_method": "static_config_only_geometry_uninspectable"},
    )
    preflight = script.build_v06a_runtime_chamfer_preflight_from_probe(
        output_dir=tmp_path,
        capture_radius_probe=probe,
        prior_static_preflight={"preflight_branch": "C", "inspection_method": "static_config_only_geometry_uninspectable"},
    )

    assert probe["preflight_branch"] == "A"
    assert probe["offset_sweep_m"] == list(script.V06A_CAPTURE_RADIUS_OFFSET_SWEEP_M)
    assert probe["capture_radius_m"] == 0.0004
    assert probe["measurement"]["nonzero_success_count_by_direction"]["+y"] == 2
    assert probe["proof_authority"] is False
    assert probe["repair_probe_green_light"] is False
    assert probe["train_generation_gate_allowed"] is False
    assert probe["train_generation_gate_status"] == "pending_repair_probe"
    assert preflight["preflight_branch"] == "A"
    assert preflight["repair_probe_allowed"] is True
    assert preflight["train_generation_gate_allowed"] is False
    assert preflight["train_generation_gate_status"] == "pending_repair_probe"
    assert script.validate_v06a_verified_chamfer_preflight(
        preflight,
        capture_radius_probe=probe,
    )["preflight_branch"] == "A"


def test_v06a_capture_radius_branch_b_for_weak_asymmetric_capture(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    probe = script.build_v06a_capture_radius_probe_artifact(
        output_dir=tmp_path,
        measurement=script.evaluate_runtime_capture_radius_probe(
            {
                "runtime_loaded": True,
                "env_native_success_mask_available": True,
                "zero_offset_passed": True,
                "direction_results": {
                    "+x": {"max_successful_delta_m": 0.0010},
                    "-x": {"max_successful_delta_m": 0.0},
                    "+y": {"max_successful_delta_m": 0.0},
                    "-y": {"max_successful_delta_m": 0.0},
                },
            }
        ),
        prior_static_preflight={"preflight_branch": "C", "inspection_method": "static_config_only_geometry_uninspectable"},
    )
    preflight = script.build_v06a_runtime_chamfer_preflight_from_probe(
        output_dir=tmp_path,
        capture_radius_probe=probe,
        prior_static_preflight={"preflight_branch": "C", "inspection_method": "static_config_only_geometry_uninspectable"},
    )

    assert probe["preflight_branch"] == "B"
    assert probe["capture_radius_m"] == "approximate"
    assert preflight["preflight_branch"] == "B"
    assert preflight["repair_probe_allowed"] is True
    assert preflight["train_generation_gate_status"] == "pending_repair_probe"


def test_v06a_capture_radius_branch_b_when_all_directions_are_below_branch_a_bar(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    measurement = script.evaluate_runtime_capture_radius_probe(
        {
            "runtime_loaded": True,
            "env_native_success_mask_available": True,
            "zero_offset_passed": True,
            "direction_results": {
                "+x": {"max_successful_delta_m": 0.0002, "nonzero_success_count": 1},
                "-x": {"max_successful_delta_m": 0.0002, "nonzero_success_count": 1},
                "+y": {"max_successful_delta_m": 0.0002, "nonzero_success_count": 1},
                "-y": {"max_successful_delta_m": 0.0002, "nonzero_success_count": 1},
            },
        }
    )
    probe = script.build_v06a_capture_radius_probe_artifact(
        output_dir=tmp_path,
        measurement=measurement,
        prior_static_preflight={"preflight_branch": "C", "inspection_method": "static_config_only_geometry_uninspectable"},
    )
    preflight = script.build_v06a_runtime_chamfer_preflight_from_probe(
        output_dir=tmp_path,
        capture_radius_probe=probe,
        prior_static_preflight={"preflight_branch": "C", "inspection_method": "static_config_only_geometry_uninspectable"},
    )

    assert measurement["preflight_branch"] == "B"
    assert measurement["capture_radius_m"] == 0.0002
    assert probe["repair_probe_allowed"] is True
    assert preflight["train_generation_gate_allowed"] is False


def test_v06a_capture_radius_partial_runtime_timeout_keeps_partial_branch_b() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    measurement = script.evaluate_runtime_capture_radius_probe(
        {
            "runtime_loaded": True,
            "env_native_success_mask_available": True,
            "zero_offset_passed": True,
            "direction_results": {
                "+x": {
                    "max_successful_delta_m": 0.002,
                    "partial_due_to_timeout": False,
                },
                "-x": {
                    "max_successful_delta_m": 0.00025,
                    "partial_due_to_timeout": True,
                },
            },
            "partial_due_to_timeout": True,
            "error": "v0_6a capture-radius trial exceeded runtime deadline",
        }
    )

    assert measurement["preflight_branch"] == "B"
    assert measurement["runtime_loaded"] is True
    assert measurement["env_native_success_mask_available"] is True
    assert measurement["zero_offset_passed"] is True
    assert measurement["blocker_reasons"] == []


def test_v06a_capture_radius_branch_c_blocks_when_zero_offset_fails(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    probe = script.build_v06a_capture_radius_probe_artifact(
        output_dir=tmp_path,
        measurement=script.evaluate_runtime_capture_radius_probe(
            {
                "runtime_loaded": True,
                "env_native_success_mask_available": True,
                "zero_offset_passed": False,
                "direction_results": {},
            }
        ),
        prior_static_preflight={"preflight_branch": "C", "inspection_method": "static_config_only_geometry_uninspectable"},
    )
    preflight = script.build_v06a_runtime_chamfer_preflight_from_probe(
        output_dir=tmp_path,
        capture_radius_probe=probe,
        prior_static_preflight={"preflight_branch": "C", "inspection_method": "static_config_only_geometry_uninspectable"},
    )

    assert probe["preflight_branch"] == "C"
    assert probe["train_generation_gate_allowed"] is False
    assert probe["train_generation_gate_status"] == "blocked_by_preflight"
    assert preflight["repair_probe_allowed"] is False
    assert preflight["train_generation_gate_status"] == "blocked_by_preflight"
    assert preflight["heldout_allowed"] is False


def test_v06a_verified_preflight_validator_rejects_wrong_profile(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    probe = script.build_v06a_capture_radius_probe_artifact(
        output_dir=tmp_path,
        measurement=script.evaluate_runtime_capture_radius_probe(
            {
                "runtime_loaded": True,
                "env_native_success_mask_available": True,
                "zero_offset_passed": True,
                "direction_results": v06a_branch_a_direction_results(),
            }
        ),
        prior_static_preflight={"preflight_branch": "C", "inspection_method": "static_config_only_geometry_uninspectable"},
    )
    preflight = script.build_v06a_runtime_chamfer_preflight_from_probe(
        output_dir=tmp_path,
        capture_radius_probe=probe,
        prior_static_preflight={"preflight_branch": "C", "inspection_method": "static_config_only_geometry_uninspectable"},
    )
    preflight["scenario_profile"] = "v0_6"

    try:
        script.validate_v06a_verified_chamfer_preflight(preflight, capture_radius_probe=probe)
    except ValueError as exc:
        assert "scenario_profile" in str(exc)
    else:
        raise AssertionError("wrong scenario_profile must be rejected")


def test_v06a_verified_preflight_requires_matching_capture_probe_artifact(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    probe = script.build_v06a_capture_radius_probe_artifact(
        output_dir=tmp_path,
        measurement=script.evaluate_runtime_capture_radius_probe(
            {
                "runtime_loaded": True,
                "env_native_success_mask_available": True,
                "zero_offset_passed": True,
                "direction_results": v06a_branch_a_direction_results(),
            }
        ),
        prior_static_preflight={"preflight_branch": "C", "inspection_method": "static_config_only_geometry_uninspectable"},
    )
    script.build_v06a_runtime_chamfer_preflight_from_probe(
        output_dir=tmp_path,
        capture_radius_probe=probe,
        prior_static_preflight={"preflight_branch": "C", "inspection_method": "static_config_only_geometry_uninspectable"},
    )

    resolved = script.resolve_v06_repair_probe_preflight(output_dir=tmp_path, require_runtime_capture_preflight=True)
    assert resolved["preflight_branch"] == "A"

    (tmp_path / "capture_radius_probe.json").unlink()
    missing = script.resolve_v06_repair_probe_preflight(output_dir=tmp_path, require_runtime_capture_preflight=True)
    assert missing["repair_probe_allowed"] is False
    assert missing["reason"] == "missing_matching_v0_6a_capture_radius_probe"

    script.write_json(tmp_path / "capture_radius_probe.json", {**probe, "preflight_branch": "B"})
    tampered = script.resolve_v06_repair_probe_preflight(output_dir=tmp_path, require_runtime_capture_preflight=True)
    assert tampered["repair_probe_allowed"] is False
    assert "invalid_verified_v0_6a_chamfer_preflight" in tampered["reason"]


def test_v06_repair_probe_requires_verified_v06a_preflight(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    resolved = script.resolve_v06_repair_probe_preflight(output_dir=tmp_path, require_runtime_capture_preflight=True)

    assert resolved["repair_probe_allowed"] is False
    assert resolved["reason"] == "missing_verified_v0_6a_chamfer_preflight"
    assert resolved["train_generation_gate_allowed"] is False


def test_v06_train_generation_gate_requires_verified_preflight_and_repair_green_light(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    probe = script.build_v06a_capture_radius_probe_artifact(
        output_dir=tmp_path,
        measurement=script.evaluate_runtime_capture_radius_probe(
            {
                "runtime_loaded": True,
                "env_native_success_mask_available": True,
                "zero_offset_passed": True,
                "direction_results": v06a_branch_a_direction_results(),
            }
        ),
        prior_static_preflight={"preflight_branch": "C", "inspection_method": "static_config_only_geometry_uninspectable"},
    )
    preflight = script.build_v06a_runtime_chamfer_preflight_from_probe(
        output_dir=tmp_path,
        capture_radius_probe=probe,
        prior_static_preflight={"preflight_branch": "C", "inspection_method": "static_config_only_geometry_uninspectable"},
    )

    blocked_without_repair = script.resolve_v06_train_generation_gate_preflight(output_dir=tmp_path)
    assert blocked_without_repair["train_generation_gate_allowed"] is False
    assert blocked_without_repair["reason"] == "missing_v0_6_repair_probe_green_light"

    script.write_json(
        tmp_path / "repair_probe_gate.json",
        {"green_light_for_40_run_gate": False, "hard_stop": True, "proof_authority": False},
    )
    blocked_red = script.resolve_v06_train_generation_gate_preflight(output_dir=tmp_path)
    assert blocked_red["train_generation_gate_allowed"] is False
    assert blocked_red["reason"] == "v0_6_repair_probe_not_green"

    script.write_json(
        tmp_path / "repair_probe_gate.json",
        {"green_light_for_40_run_gate": True, "hard_stop": False, "proof_authority": False},
    )
    blocked_invalid_green = script.resolve_v06_train_generation_gate_preflight(output_dir=tmp_path)
    assert blocked_invalid_green["train_generation_gate_allowed"] is False
    assert blocked_invalid_green["reason"].startswith("invalid_v0_6_repair_probe_gate:")

    semantically_fake_green = {
        "proof_authority": False,
        "proof_runtime": "isaac_scripted_expert_repair_probe",
        "runtime_backend": "isaac_runtime",
        "probe_seeds": list(script.V06_REPAIR_PROBE_SEEDS),
        "hold_mode_passed": True,
        "lateral_success_mode_passed": True,
        "lateral_divergence_stopped": True,
        "green_light_for_40_run_gate": True,
        "hard_stop": False,
        "probe_results": {str(seed): {} for seed in script.V06_REPAIR_PROBE_SEEDS},
        "chamfer_preflight": preflight,
        "v0_6a_post_repair_probe_gate": {
            "green_light_for_40_run_gate": True,
            "reason": "repair_probe_green_light",
            "proof_authority": False,
        },
        "v0_6b_native_metric_trace_validation": {
            "valid": True,
            "reasons": [],
            "validated_trace_count": 3,
        },
    }
    semantically_fake_green["repair_probe_gate_sha256"] = script._sha256_payload_excluding(
        semantically_fake_green,
        "repair_probe_gate_sha256",
    )
    script.write_json(tmp_path / "repair_probe_gate.json", semantically_fake_green)
    blocked_semantic_fake = script.resolve_v06_train_generation_gate_preflight(output_dir=tmp_path)
    assert blocked_semantic_fake["train_generation_gate_allowed"] is False
    assert "does not match probe_results" in blocked_semantic_fake["reason"]

    green_without_trace_validation = {
        "proof_authority": False,
        "proof_runtime": "isaac_scripted_expert_repair_probe",
        "runtime_backend": "isaac_runtime",
        "probe_seeds": list(script.V06_REPAIR_PROBE_SEEDS),
        "hold_mode_passed": True,
        "lateral_success_mode_passed": True,
        "lateral_divergence_stopped": True,
        "green_light_for_40_run_gate": True,
        "hard_stop": False,
        "probe_results": {
            str(seed): {
                "env_native_rollout_success": True,
                "env_native_max_consecutive_success_steps": 10,
                "lateral_divergence_stopped": True,
            }
            for seed in script.V06_REPAIR_PROBE_SEEDS
        },
        "chamfer_preflight": preflight,
        "v0_6a_post_repair_probe_gate": {
            "green_light_for_40_run_gate": True,
            "reason": "repair_probe_green_light",
            "proof_authority": False,
        },
    }
    green_without_trace_validation["repair_probe_gate_sha256"] = script._sha256_payload_excluding(
        green_without_trace_validation,
        "repair_probe_gate_sha256",
    )
    script.write_json(tmp_path / "repair_probe_gate.json", green_without_trace_validation)
    blocked_missing_v06b_validation = script.resolve_v06_train_generation_gate_preflight(output_dir=tmp_path)
    assert blocked_missing_v06b_validation["train_generation_gate_allowed"] is False
    assert "v0_6b_native_metric_trace_validation" in blocked_missing_v06b_validation["reason"]

    write_valid_v06_repair_probe_gate(script, tmp_path / "repair_probe_gate.json", preflight=preflight)
    allowed = script.resolve_v06_train_generation_gate_preflight(output_dir=tmp_path)
    assert allowed["train_generation_gate_allowed"] is True
    assert allowed["preflight"]["preflight_branch"] == "A"
    assert allowed["repair_probe_gate"]["proof_runtime"] == "isaac_scripted_expert_repair_probe"


def test_v06_full_build_preserves_runtime_preflight_and_blocks_without_repair_green(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    probe = script.build_v06a_capture_radius_probe_artifact(
        output_dir=tmp_path,
        measurement=script.evaluate_runtime_capture_radius_probe(
            {
                "runtime_loaded": True,
                "env_native_success_mask_available": True,
                "zero_offset_passed": True,
                "direction_results": {
                    "+x": {"max_successful_delta_m": 0.0002, "nonzero_success_count": 1},
                    "-x": {"max_successful_delta_m": 0.0002, "nonzero_success_count": 1},
                    "+y": {"max_successful_delta_m": 0.0002, "nonzero_success_count": 1},
                    "-y": {"max_successful_delta_m": 0.0002, "nonzero_success_count": 1},
                },
            }
        ),
        prior_static_preflight={"preflight_branch": "C", "inspection_method": "static_config_only_geometry_uninspectable"},
    )
    preflight = script.build_v06a_runtime_chamfer_preflight_from_probe(
        output_dir=tmp_path,
        capture_radius_probe=probe,
        prior_static_preflight={"preflight_branch": "C", "inspection_method": "static_config_only_geometry_uninspectable"},
    )

    report = script.build_mvp2c_isaac_training_calibration(
        output_dir=tmp_path,
        scenario_profile="v0_6",
        clean=False,
        skip_isaac=False,
        use_deterministic_eval_backend=False,
    )
    persisted = script.read_json(tmp_path / "chamfer_preflight.json")
    train_gate = script.read_json(tmp_path / "train_generation_runtime_gate.json")

    assert persisted["chamfer_preflight_sha256"] == preflight["chamfer_preflight_sha256"]
    assert persisted["preflight_branch"] == "B"
    assert report["v0_6_chamfer_preflight"]["preflight_branch"] == "B"
    assert train_gate["runtime_backend"] == "isaac_runtime_not_started"
    assert train_gate["reason"] == "missing_v0_6_repair_probe_green_light"


def test_v06a_branch_b_align_then_jam_blocks_40_run_gate() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    gate = script.evaluate_v06a_post_repair_probe_gate(
        preflight={"preflight_branch": "B", "repair_probe_allowed": True},
        repair_probe_gate={"green_light_for_40_run_gate": False, "failure_mode": "align_then_jam"},
    )

    assert gate["green_light_for_40_run_gate"] is False
    assert gate["reason"] == "branch_b_align_then_jam_escalated_to_blocker"


def test_v06_static_preflight_still_fail_closes_without_runtime_capture_probe(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    preflight = script.build_v06_chamfer_preflight(output_dir=tmp_path)

    assert preflight["preflight_branch"] == "C"
    assert preflight["inspection_method"] == "static_config_only_geometry_uninspectable"
    assert preflight["repair_probe_allowed"] is False
    assert preflight["train_generation_gate_allowed"] is False


def test_v06a_capture_radius_probe_only_rejects_wrong_profile_before_cleaning(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    marker = tmp_path / "keep.txt"
    marker.write_text("must survive invalid profile", encoding="utf-8")

    try:
        script.main(
            [
                "--output-dir",
                str(tmp_path),
                "--clean",
                "--scenario-profile",
                "v0_5",
                "--capture-radius-probe-only",
            ]
        )
    except ValueError as exc:
        assert "--capture-radius-probe-only" in str(exc)
    else:
        raise AssertionError("wrong profile must be rejected before cleaning output_dir")

    assert marker.read_text(encoding="utf-8") == "must survive invalid profile"


def test_mvp2c_baseline_noise_mix_is_pre_registered_and_hashed(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    config = script.build_baseline_noise_mix_config(output_dir=tmp_path / "mvp2c")

    assert config["baseline_noise_mix_ratio"] == 0.25
    assert config["accepted_failure_ratio"] == {"accepted": 3, "failure_or_noisy": 1}
    assert config["failure_type_distribution"] == {
        "LATERAL_OFFSET_FAILURE": 0.2,
        "UNDER_INSERTION_FAILURE": 0.2,
        "ORIENTATION_MISALIGNMENT_FAILURE": 0.2,
        "ACTION_JITTER_FAILURE": 0.2,
        "EARLY_STOP_FAILURE": 0.2,
    }
    assert config["noise_profile_config_sha256"]
    assert (tmp_path / "mvp2c" / "baseline_noise_mix_config.json").exists()


def test_mvp2d_v05_baseline_noise_mix_and_generator_hashes_are_pre_registered(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    mix = script.build_baseline_noise_mix_config(output_dir=tmp_path / "mvp2d", scenario_profile="v0_5")
    hashes = script.build_generator_config_hashes(output_dir=tmp_path / "mvp2d", scenario_profile="v0_5")

    assert mix["baseline_noise_mix_ratio"] == 0.40
    assert mix["accepted_failure_ratio"] == {"accepted": 3, "failure_or_noisy": 2}
    assert mix["failure_type_distribution"] == {
        "lateral_offset": 1 / 3,
        "stability_window_loss": 1 / 3,
        "under_insertion": 1 / 3,
    }
    assert hashes["train_generation_config"]["actual_isaac_success_trace_minimum"] == 20
    assert hashes["train_generation_config"]["actual_isaac_success_trace_cap"] == 40
    assert hashes["train_generation_config"]["trainer_family"] == "phase_conditioned_residual_servo_bc"
    assert hashes["train_generation_config"]["residual_target_definition"] == (
        "actual_trace_action_minus_weak_base_servo_action"
    )
    assert hashes["weak_base_servo_config_sha256"]


def test_mvp2c_generator_hashes_are_immutable_after_calibration_starts(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    hashes = script.build_generator_config_hashes(output_dir=tmp_path / "mvp2c")
    changed = {**hashes, "train_generation_config_sha256": "changed"}

    result = script.validate_generator_config_immutability(
        frozen_hashes=hashes,
        proposed_hashes=changed,
        calibration_started=True,
        heldout_started=False,
    )

    assert hashes["scripted_expert_config_sha256"]
    assert hashes["controlled_failure_config_sha256"]
    assert hashes["train_generation_config_sha256"]
    assert result["passed"] is False
    assert "train_generation_config_sha256" in result["changed_fields"]
    assert "calibration" in result["phase"]


def test_mvp2d_v05_train_generation_gate_requires_twenty_actual_success_traces() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    gate = script.derive_train_generation_runtime_gate_from_probe_result(
        script.BackendResult(
            runtime_backend="isaac_runtime",
            proof_runtime="dedicated_isaac_connector_insertion_evaluator",
            runtime_gate={"passed": True, "runtime_backend": "isaac_runtime"},
            baseline_rollouts=[
                {
                    "rollout_id": f"train_generation_probe_{index:04d}",
                    "scenario_id": f"train_success_{16000 + index}",
                    "success": True,
                    "failure_reason": "",
                    "rollout_log_ref": f"/tmp/train_generation_probe_{index:04d}.json",
                }
                for index in range(19)
            ],
            candidate_rollouts=[],
            baseline_trace_paths=[f"/tmp/train_generation_probe_{index:04d}.json" for index in range(19)],
            candidate_trace_paths=[],
            runtime_metadata={"runtime_backend": "isaac_runtime"},
        ),
        device="cuda:0",
        headless=True,
        min_success_count=20,
        success_trace_cap=40,
    )

    assert gate["passed"] is False
    assert gate["actual_train_generation_evidence"] is False
    assert gate["generated_success_count"] == 19
    assert gate["required_success_count"] == 20
    assert gate["success_trace_cap"] == 40


def test_mvp2c_calibration_selector_rejects_heldout_channels(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    manifest = script.build_mvp2c_scenario_manifest(output_dir=tmp_path / "mvp2c")
    heldout_id = next(row["scenario_id"] for row in manifest["scenarios"] if row["split"] == "held_out")

    result = script.validate_calibration_selector_inputs(
        manifest=manifest,
        calibration_summaries=[{"adapter_id": "isaac_delta_pose_direct_v0", "scenario_ids": ["calibration_5000"]}],
        forbidden_inputs={
            "heldout_trace_paths": ["/tmp/heldout_trace.json"],
            "heldout_rollout_json_paths": [],
            "heldout_success_metrics": {"candidate_success_rate": 0.7},
            "heldout_scenario_ids": [heldout_id],
        },
    )

    assert result["passed"] is False
    assert "heldout_trace_paths" in result["blocked_channels"]
    assert "heldout_success_metrics" in result["blocked_channels"]
    assert heldout_id in result["blocked_heldout_scenario_ids"]


def test_mvp2c_action_adapter_registry_is_hashed_and_selector_freezes_choice(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    manifest = script.build_mvp2c_scenario_manifest(output_dir=tmp_path / "mvp2c")
    registry = script.build_action_adapter_registry(output_dir=tmp_path / "mvp2c")
    selection = script.select_action_adapter_from_calibration(
        adapter_registry=registry,
        manifest=manifest,
        calibration_summaries=[
            {
                "adapter_id": "isaac_delta_pose_direct_v0",
                "scenario_ids": ["calibration_5000"],
                "candidate_success_rate": 0.55,
                "baseline_success_rate": 0.45,
                "candidate_stability_margin": 0.10,
                "candidate_action_saturation_rate": 0.05,
            },
            {
                "adapter_id": "isaac_signed_xy_downward_servo_v0",
                "scenario_ids": ["calibration_5000"],
                "candidate_success_rate": 0.75,
                "baseline_success_rate": 0.45,
                "candidate_stability_margin": 0.25,
                "candidate_action_saturation_rate": 0.03,
            },
            {
                "adapter_id": "isaac_stability_damped_servo_v0",
                "scenario_ids": ["calibration_5000"],
                "candidate_success_rate": 0.65,
                "baseline_success_rate": 0.50,
                "candidate_stability_margin": 0.40,
                "candidate_action_saturation_rate": 0.02,
            },
        ],
        output_dir=tmp_path / "mvp2c",
    )

    assert {item["adapter_id"] for item in registry["adapters"]} == {
        "isaac_delta_pose_direct_v0",
        "isaac_signed_xy_downward_servo_v0",
        "isaac_stability_damped_servo_v0",
    }
    assert registry["action_adapter_registry_sha256"]
    assert selection["selected_adapter_id"] == "isaac_signed_xy_downward_servo_v0"
    assert selection["selector_score_pre_registered"] is True
    assert selection["same_adapter_used_for_baseline_and_candidate"] is True
    assert selection["heldout_excluded"] is True
    assert selection["selected_adapter_frozen_before_heldout"] is True
    assert selection["selected_adapter_sha256"]
    assert selection["selected_adapter_config"]["z_action_scale"] > selection["selected_adapter_config"]["xy_action_scale"]
    assert selection["selected_adapter_config"]["xy_action_clip"] < 0.10
    assert selection["action_adapter_registry_sha256"] == registry["action_adapter_registry_sha256"]
    assert selection["leakage_guard_result"]["passed"] is True


def test_mvp2c_policy_artifacts_preserve_selected_action_adapter_config(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    manifest = script.build_mvp2c_scenario_manifest(output_dir=tmp_path / "mvp2c")
    registry = script.build_action_adapter_registry(output_dir=tmp_path / "mvp2c")
    selection = script.select_action_adapter_from_calibration(
        adapter_registry=registry,
        manifest=manifest,
        calibration_summaries=script._build_calibration_summaries(manifest, output_dir=tmp_path / "mvp2c"),
        output_dir=tmp_path / "mvp2c",
    )
    mix = script.build_baseline_noise_mix_config(output_dir=tmp_path / "mvp2c")
    hashes = script.build_generator_config_hashes(output_dir=tmp_path / "mvp2c")
    bundle = script.generate_mvp2c_training_trajectory_bundle(
        manifest=manifest,
        baseline_noise_mix_config=mix,
        generator_config_hashes=hashes,
        output_dir=tmp_path / "mvp2c",
        train_generation_runtime_backend="deterministic_test_backend",
    )

    artifacts = script._write_policy_artifacts(
        output_dir=tmp_path / "mvp2c",
        baseline_rows=bundle["baseline_train_rows"],
        candidate_rows=bundle["candidate_train_rows"],
        selected_adapter_id=selection["selected_adapter_id"],
        selected_adapter_config=selection["selected_adapter_config"],
    )

    assert artifacts["baseline"]["selected_action_adapter_config"] == selection["selected_adapter_config"]
    assert artifacts["candidate"]["selected_action_adapter_config"] == selection["selected_adapter_config"]
    assert artifacts["baseline"]["selected_action_adapter_config_sha256"]
    assert artifacts["candidate"]["selected_action_adapter_config_sha256"]


def test_mvp2c_selected_action_adapter_scales_z_without_xy_saturation() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    policy = {
        "policy_id": "candidate_curated_mvp2c_phase_conditioned_numpy_bc",
        "selected_action_adapter_id": "isaac_signed_xy_downward_servo_v0",
        "selected_action_adapter_config": {
            "xy_action_scale": 4.0,
            "xy_action_clip": 0.035,
            "xy_source": "state_feedback",
            "xy_state_feedback_gain": 4.0,
            "z_action_scale": 24.0,
            "z_action_clip": 0.12,
            "rotation_action_scale": 1.0,
            "stable_hold_depth_m": 0.03,
            "stable_hold_lateral_m": 0.006,
            "stable_hold_orientation_deg": 8.0,
            "stable_hold_action": [0.0, 0.0, -0.02, 0.0, 0.0, 0.0, 1.0],
        },
        "weights": [[0.0] * len(script.ACTION_SCHEMA) for _ in script.FEATURE_SCHEMA],
        "bias": [-0.004, 0.002, -0.004, 0.20, -0.20, 0.20, 1.0],
    }

    action = script._predict_policy_action(
        policy,
        metric_row={
            "phase": "APPROACH",
            "insertion_depth_m": 0.0,
            "relative_x_m": 0.008,
            "relative_y_m": -0.004,
            "lateral_error_m": 0.009,
            "orientation_error_deg": 2.0,
        },
        previous_action=[0.0] * len(script.ACTION_SCHEMA),
        action_scale=20.0,
    )

    assert action.tolist() == [-0.032, 0.016, -0.096, 0.2, -0.2, 0.2, 1.0]
    assert abs(float(action[0])) < 0.035
    assert abs(float(action[2])) > 2 * abs(float(action[0]))


def test_mvp2c_selected_action_adapter_can_use_hybrid_policy_xy_signal() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    policy = {
        "policy_id": "candidate_curated_mvp2c_phase_conditioned_numpy_bc",
        "selected_action_adapter_id": "isaac_signed_xy_downward_servo_v0",
        "selected_action_adapter_config": {
            "xy_action_scale": 3.0,
            "xy_action_clip": 0.04,
            "xy_source": "policy_plus_state_feedback",
            "xy_state_feedback_gain": 1.5,
            "z_action_scale": 32.0,
            "z_action_clip": 0.16,
            "rotation_action_scale": 0.0,
        },
        "weights": [[0.0] * len(script.ACTION_SCHEMA) for _ in script.FEATURE_SCHEMA],
        "bias": [-0.004, 0.002, -0.004, 0.20, -0.20, 0.20, 1.0],
    }

    action = script._predict_policy_action(
        policy,
        metric_row={
            "phase": "APPROACH",
            "insertion_depth_m": 0.0,
            "relative_x_m": 0.008,
            "relative_y_m": -0.004,
            "lateral_error_m": 0.009,
            "orientation_error_deg": 2.0,
        },
        previous_action=[0.0] * len(script.ACTION_SCHEMA),
        action_scale=20.0,
    )

    assert action.tolist() == [-0.024, 0.012, -0.128, 0.0, 0.0, 0.0, 1.0]
    assert abs(float(action[0])) < 0.04
    assert abs(float(action[2])) > 5 * abs(float(action[1]))


def test_mvp2c_selected_action_adapter_holds_when_stable() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    policy = {
        "policy_id": "candidate_curated_mvp2c_phase_conditioned_numpy_bc",
        "selected_action_adapter_id": "isaac_signed_xy_downward_servo_v0",
        "selected_action_adapter_config": {
            "xy_action_scale": 4.0,
            "xy_action_clip": 0.035,
            "xy_source": "state_feedback",
            "xy_state_feedback_gain": 4.0,
            "z_action_scale": 24.0,
            "z_action_clip": 0.12,
            "rotation_action_scale": 1.0,
            "stable_hold_depth_m": 0.03,
            "stable_hold_lateral_m": 0.006,
            "stable_hold_orientation_deg": 8.0,
            "stable_hold_action": [0.0, 0.0, -0.02, 0.0, 0.0, 0.0, 1.0],
        },
        "weights": [[0.0] * len(script.ACTION_SCHEMA) for _ in script.FEATURE_SCHEMA],
        "bias": [-0.004, 0.002, -0.004, 0.20, -0.20, 0.20, 1.0],
    }

    action = script._predict_policy_action(
        policy,
        metric_row={
            "phase": "SEAT",
            "insertion_depth_m": 0.031,
            "relative_x_m": 0.001,
            "relative_y_m": -0.001,
            "lateral_error_m": 0.002,
            "orientation_error_deg": 2.0,
        },
        previous_action=[0.0] * len(script.ACTION_SCHEMA),
        action_scale=20.0,
    )

    assert action.tolist() == [0.0, 0.0, -0.02, 0.0, 0.0, 0.0, 1.0]


def test_mvp2c_training_bundle_contracts_pass_and_baseline_mix_matches(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    manifest = script.build_mvp2c_scenario_manifest(output_dir=tmp_path / "mvp2c")
    mix = script.build_baseline_noise_mix_config(output_dir=tmp_path / "mvp2c")
    hashes = script.build_generator_config_hashes(output_dir=tmp_path / "mvp2c")

    bundle = script.generate_mvp2c_training_trajectory_bundle(
        manifest=manifest,
        baseline_noise_mix_config=mix,
        generator_config_hashes=hashes,
        output_dir=tmp_path / "mvp2c",
        train_generation_runtime_backend="deterministic_test_backend",
    )

    assert bundle["contract_validation"]["passed"] is True
    assert bundle["accepted_count"] == 80
    assert bundle["rejected_count"] == 80
    assert all(item["rollout_eval"]["success"] is True for item in bundle["curation_manifest"]["items"] if item["accepted"])
    assert all(item["rollout_eval"]["success"] is False for item in bundle["curation_manifest"]["items"] if not item["accepted"])
    assert bundle["baseline_mix_evidence"]["baseline_noise_mix_ratio"] == 0.25
    assert bundle["baseline_mix_evidence"]["failure_type_coverage"] == 1.0


def test_mvp2c_skip_isaac_never_closes_and_writes_nonclaims(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    report = script.build_mvp2c_isaac_training_calibration(
        output_dir=tmp_path / "mvp2c",
        clean=True,
        skip_isaac=True,
        min_rollouts_per_policy=20,
    )

    assert report["mvp2_closed"] is False
    assert report["mvp2c_close_minimum_passed"] is False
    assert report["train_generation_runtime_gate"]["passed"] is False
    assert report["proof_boundary"]["skip_isaac_can_close_mvp2c"] is False
    assert report["non_claims"]["deployable_real_robot_policy"] is False
    assert report["non_claims"]["visual_policy_performance"] is False
    assert report["non_claims"]["real_robot_success"] is False
    assert report["non_claims"]["physical_robot_readiness"] is False
    assert report["non_claims"]["universal_robot_support"] is False
    assert "privileged task-state features" in report["non_claims"]["privileged_feature_statement"]


def test_mvp2c_deterministic_path_cannot_close_even_with_positive_uplift(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    report = script.build_mvp2c_isaac_training_calibration(
        output_dir=tmp_path / "mvp2c",
        clean=True,
        skip_isaac=False,
        use_deterministic_eval_backend=True,
        deterministic_profile="candidate_positive",
        min_rollouts_per_policy=20,
        bootstrap_iterations=200,
    )

    assert report["curated_vs_uncurated_uplift"] >= 0.20
    assert report["runtime_backend"] == "deterministic_test_backend"
    assert report["train_generation_runtime_backend"] == "deterministic_test_backend"
    assert report["mvp2_closed"] is False
    assert report["mvp2c_close_minimum_passed"] is False
    assert report["proof_eligible"] is False
    assert report["learning_validator"]["proof_eligible"] is False
    assert report["learning_validator"]["evidence_tier"] == "local_phase_conditioned_policy_eval_proxy"


def test_mvp2c_closure_requires_train_generation_runtime_gate() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    closure = script.derive_mvp2c_closure(
        learning_report={
            "learning_proven": True,
            "proof_eligible": True,
            "curated_vs_uncurated_uplift": 0.25,
            "baseline_success_rate": 0.40,
            "candidate_success_rate": 0.70,
        },
        runtime_gate={
            "passed": True,
            "runtime_backend": "isaac_runtime",
            "proof_runtime": "dedicated_isaac_connector_insertion_evaluator",
        },
        train_generation_runtime_gate={
            "passed": False,
            "runtime_backend": "deterministic_test_backend",
        },
        calibration_selection_report={
            "calibration_only_selection_passed": True,
            "heldout_excluded": True,
            "selected_adapter_frozen_before_heldout": True,
            "same_adapter_used_for_baseline_and_candidate": True,
        },
        heldout_leakage_guard={"passed": True},
        actual_rollouts_per_policy=20,
    )

    assert closure["mvp2_closed"] is False
    assert closure["proof_eligible"] is False
    assert any("train generation" in blocker.lower() for blocker in closure["blockers"])


def test_mvp2c_import_only_train_generation_probe_cannot_close() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    closure = script.derive_mvp2c_closure(
        learning_report={
            "learning_proven": True,
            "proof_eligible": True,
            "curated_vs_uncurated_uplift": 0.25,
            "baseline_success_rate": 0.40,
            "candidate_success_rate": 0.70,
        },
        runtime_gate={
            "passed": True,
            "runtime_backend": "isaac_runtime",
            "proof_runtime": "dedicated_isaac_connector_insertion_evaluator",
        },
        train_generation_runtime_gate={
            "passed": True,
            "runtime_backend": "isaac_runtime",
            "proof_runtime": "isaac_scripted_expert_train_generation_probe",
            "runtime_import_probe_passed": True,
            "actual_train_generation_evidence": False,
        },
        calibration_selection_report={
            "calibration_only_selection_passed": True,
            "heldout_excluded": True,
            "selected_adapter_frozen_before_heldout": True,
            "same_adapter_used_for_baseline_and_candidate": True,
        },
        heldout_leakage_guard={"passed": True},
        actual_rollouts_per_policy=20,
    )

    assert closure["mvp2_closed"] is False
    assert any("actual Isaac runtime train generation" in blocker for blocker in closure["blockers"])


def test_mvp2c_train_generation_gate_passes_only_with_actual_isaac_success() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    gate = script.derive_train_generation_runtime_gate_from_probe_result(
        script.BackendResult(
            runtime_backend="isaac_runtime",
            proof_runtime="dedicated_isaac_connector_insertion_evaluator",
            runtime_gate={"passed": True, "runtime_backend": "isaac_runtime"},
            baseline_rollouts=[
                {
                    "rollout_id": "train_generation_probe_0000",
                    "scenario_id": "train_success_7000",
                    "success": True,
                    "failure_reason": "",
                    "rollout_log_ref": "/tmp/train_generation_probe_0000.json",
                }
            ],
            candidate_rollouts=[],
            baseline_trace_paths=["/tmp/train_generation_probe_0000.json"],
            candidate_trace_paths=[],
            runtime_metadata={"runtime_backend": "isaac_runtime"},
        ),
        device="cuda:0",
        headless=True,
    )

    assert gate["passed"] is True
    assert gate["runtime_backend"] == "isaac_runtime"
    assert gate["actual_train_generation_evidence"] is True
    assert gate["training_trajectory_source"] == "isaac_runtime_scripted_expert_rollout"
    assert gate["generated_success_count"] == 1
    assert gate["generated_success_trace_paths"] == ["/tmp/train_generation_probe_0000.json"]


def test_mvp2c_actual_isaac_success_trace_rows_are_candidate_only(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    manifest = script.build_mvp2c_scenario_manifest(output_dir=tmp_path / "mvp2c", scenario_profile="v0_3")
    mix = script.build_baseline_noise_mix_config(output_dir=tmp_path / "mvp2c")
    hashes = script.build_generator_config_hashes(output_dir=tmp_path / "mvp2c", scenario_profile="v0_3")
    trace_path = tmp_path / "mvp2c" / "actual_success_trace.json"
    script.write_json(
        trace_path,
        {
            "schema_version": "rdf_mvp2b_isaac_runtime_trace_v0.1.0",
            "runtime_backend": "isaac_runtime",
            "scenario": {"scenario_id": "train_success_10000", "seed": 10000},
            "summary": {"success": True, "failure_reason": "", "steps": 2},
            "trace": [
                {
                    "step": 0,
                    "phase": "SEAT",
                    "insertion_depth_m": 0.033,
                    "relative_x_m": 0.004,
                    "relative_y_m": -0.002,
                    "lateral_error_m": 0.0045,
                    "orientation_error_deg": 0.5,
                    "normalized_action": [-0.020, 0.010, -0.120, 0.0, 0.0, 0.0, 1.0],
                },
                {
                    "step": 1,
                    "phase": "SEAT",
                    "insertion_depth_m": 0.034,
                    "relative_x_m": 0.002,
                    "relative_y_m": -0.001,
                    "lateral_error_m": 0.0025,
                    "orientation_error_deg": 0.4,
                    "normalized_action": [0.0, 0.0, -0.020, 0.0, 0.0, 0.0, 1.0],
                },
            ],
        },
    )

    bundle = script.generate_mvp2c_training_trajectory_bundle(
        manifest=manifest,
        baseline_noise_mix_config=mix,
        generator_config_hashes=hashes,
        output_dir=tmp_path / "mvp2c",
        train_generation_runtime_backend="isaac_runtime",
        train_generation_runtime_gate={
            "passed": True,
            "runtime_backend": "isaac_runtime",
            "actual_train_generation_evidence": True,
            "generated_success_trace_paths": [str(trace_path)],
        },
        selected_adapter_config={
            "xy_source": "policy_plus_state_feedback",
            "xy_state_feedback_gain": 1.5,
            "xy_action_scale": 3.0,
            "xy_action_clip": 0.04,
            "z_action_scale": 32.0,
            "z_action_clip": 0.16,
            "stable_hold_depth_m": 0.03,
            "stable_hold_lateral_m": 0.006,
            "stable_hold_orientation_deg": 8.0,
            "stable_hold_action": [0.0, 0.0, -0.03, 0.0, 0.0, 0.0, 1.0],
        },
    )

    actual_candidate_rows = [
        row for row in bundle["candidate_train_rows"] if row.get("source_kind") == "isaac_runtime_scripted_expert_rollout"
    ]
    actual_baseline_rows = [
        row for row in bundle["baseline_train_rows"] if row.get("source_kind") == "isaac_runtime_scripted_expert_rollout"
    ]
    assert bundle["actual_isaac_train_generation_evidence"]["success_trace_count"] == 1
    assert bundle["actual_isaac_train_generation_evidence"]["candidate_replay_weight"] >= 1
    assert len(actual_candidate_rows) == 2 * bundle["actual_isaac_train_generation_evidence"]["candidate_replay_weight"]
    assert actual_baseline_rows == []
    assert actual_candidate_rows[0]["normalized_action"][2] == -0.00375
    assert actual_candidate_rows[0]["runtime_trace_sha256"]
    assert actual_candidate_rows[0]["accepted"] is True


def test_mvp2d_v05_dataset_views_use_equal_trace_count_and_exact_60_40_mix(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    output_dir = tmp_path / "mvp2d"
    manifest = script.build_mvp2c_scenario_manifest(output_dir=output_dir, scenario_profile="v0_5")
    mix = script.build_baseline_noise_mix_config(output_dir=output_dir, scenario_profile="v0_5")
    hashes = script.build_generator_config_hashes(output_dir=output_dir, scenario_profile="v0_5")
    trace_paths = []
    for index in range(25):
        trace_path = output_dir / "actual_traces" / f"actual_success_{index:04d}.json"
        write_actual_success_trace(
            script,
            trace_path,
            scenario_id=f"train_success_{16000 + index}",
            seed=16000 + index,
        )
        trace_paths.append(str(trace_path))

    bundle = script.generate_mvp2c_training_trajectory_bundle(
        manifest=manifest,
        baseline_noise_mix_config=mix,
        generator_config_hashes=hashes,
        output_dir=output_dir,
        train_generation_runtime_backend="isaac_runtime",
        train_generation_runtime_gate={
            "passed": True,
            "runtime_backend": "isaac_runtime",
            "actual_train_generation_evidence": True,
            "generated_success_count": 25,
            "generated_success_trace_paths": trace_paths,
        },
        selected_adapter_config={
            "xy_source": "policy_plus_state_feedback",
            "xy_state_feedback_gain": 1.5,
            "xy_action_scale": 3.0,
            "xy_action_clip": 0.04,
            "z_action_scale": 32.0,
            "z_action_clip": 0.16,
            "rotation_action_scale": 0.0,
        },
    )

    evidence = bundle["v0_5_dataset_view_evidence"]
    assert evidence["proof_eligible"] is True
    assert evidence["actual_isaac_success_trace_count"] == 25
    assert evidence["used_success_trace_count"] == 25
    assert evidence["trace_count_equal"] is True
    assert evidence["candidate_trace_count"] == 25
    assert evidence["baseline_trace_count"] == 25
    assert evidence["baseline_accepted_trace_count"] == 15
    assert evidence["baseline_rejected_noisy_trace_count"] == 10
    assert evidence["failure_bucket_cycle"] == ["lateral_offset", "stability_window_loss", "under_insertion"]
    assert bundle["baseline_mix_evidence"]["baseline_noise_mix_ratio"] == 0.40
    assert bundle["baseline_mix_evidence"]["pre_registered_mix_enforced"] is True
    assert bundle["baseline_mix_evidence"]["failure_type_counts"] == {
        "lateral_offset": 4,
        "stability_window_loss": 3,
        "under_insertion": 3,
    }
    assert len({row["trajectory_id"] for row in bundle["candidate_train_rows"]}) == 25
    assert len({row["trajectory_id"] for row in bundle["baseline_train_rows"]}) == 25
    assert all(row["source_kind"] == "isaac_runtime_scripted_expert_rollout" for row in bundle["candidate_train_rows"])
    assert any(row.get("accepted") is False for row in bundle["baseline_train_rows"])


def test_mvp2d_v05_policy_artifacts_use_residual_servo_bc_metadata(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    output_dir = tmp_path / "mvp2d"
    manifest = script.build_mvp2c_scenario_manifest(output_dir=output_dir, scenario_profile="v0_5")
    mix = script.build_baseline_noise_mix_config(output_dir=output_dir, scenario_profile="v0_5")
    hashes = script.build_generator_config_hashes(output_dir=output_dir, scenario_profile="v0_5")
    trace_paths = []
    for index in range(20):
        trace_path = output_dir / "actual_traces" / f"actual_success_{index:04d}.json"
        write_actual_success_trace(
            script,
            trace_path,
            scenario_id=f"train_success_{16000 + index}",
            seed=16000 + index,
        )
        trace_paths.append(str(trace_path))
    selection = script.select_action_adapter_from_calibration(
        adapter_registry=script.build_action_adapter_registry(output_dir=output_dir, scenario_profile="v0_5"),
        manifest=manifest,
        calibration_summaries=script._build_calibration_summaries(manifest, output_dir=output_dir),
        output_dir=output_dir,
    )
    bundle = script.generate_mvp2c_training_trajectory_bundle(
        manifest=manifest,
        baseline_noise_mix_config=mix,
        generator_config_hashes=hashes,
        output_dir=output_dir,
        train_generation_runtime_backend="isaac_runtime",
        train_generation_runtime_gate={
            "passed": True,
            "runtime_backend": "isaac_runtime",
            "actual_train_generation_evidence": True,
            "generated_success_count": 20,
            "generated_success_trace_paths": trace_paths,
        },
        selected_adapter_config=selection["selected_adapter_config"],
    )

    artifacts = script._write_policy_artifacts(
        output_dir=output_dir,
        baseline_rows=bundle["baseline_train_rows"],
        candidate_rows=bundle["candidate_train_rows"],
        selected_adapter_id=selection["selected_adapter_id"],
        selected_adapter_config=selection["selected_adapter_config"],
        scenario_profile="v0_5",
    )

    baseline = artifacts["baseline"]
    candidate = artifacts["candidate"]
    assert baseline["trainer_family"] == "phase_conditioned_residual_servo_bc"
    assert candidate["trainer_family"] == baseline["trainer_family"]
    assert baseline["residual_target_definition"] == "actual_trace_action_minus_weak_base_servo_action"
    assert candidate["weak_base_servo_config_sha256"] == baseline["weak_base_servo_config_sha256"]
    assert candidate["same_trainer_hyperparameters_as_peer"] is True
    assert candidate["same_feature_schema_as_peer"] is True


def test_mvp2d_v05_insufficient_train_success_traces_do_not_schedule_heldout(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    class HeldoutMustNotRun:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

        def run(self, **kwargs: Any) -> Any:
            raise AssertionError("held-out evaluator must not run before v0_5 train-generation gate passes")

    monkeypatch.setattr(script, "IsaacConnectorInsertionEvaluatorBackend", HeldoutMustNotRun)
    monkeypatch.setattr(
        script,
        "probe_isaac_train_generation_runtime",
        lambda **_: {
            "passed": False,
            "runtime_backend": "isaac_runtime",
            "proof_runtime": "isaac_scripted_expert_train_generation_probe",
            "actual_train_generation_evidence": False,
            "training_trajectory_source": "isaac_runtime_scripted_expert_rollout",
            "generated_success_count": 19,
            "required_success_count": 20,
            "generated_success_trace_paths": [],
            "reason": "only 19 actual success traces generated",
        },
    )

    report = script.build_mvp2c_isaac_training_calibration(
        output_dir=tmp_path / "mvp2d",
        clean=True,
        scenario_profile="v0_5",
        skip_isaac=False,
        use_deterministic_eval_backend=False,
        min_rollouts_per_policy=20,
        bootstrap_iterations=20,
    )

    assert report["mvp2_closed"] is False
    assert report["actual_rollouts_per_policy"] == 0
    assert report["heldout_schedule"]["scheduled"] is False
    assert report["heldout_schedule"]["blocked_by_train_generation_gate"] is True
    assert report["actual_isaac_success_trace_count"] == 0
    assert report["actual_isaac_success_trace_minimum"] == 20


def test_v06_train_generation_failure_blocks_heldout(tmp_path: Path, monkeypatch: Any) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    class HeldoutMustNotRun:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

        def run(self, **kwargs: Any) -> Any:
            raise AssertionError("held-out evaluator must not run before v0_6 train-generation gate passes")

    monkeypatch.setattr(script, "IsaacConnectorInsertionEvaluatorBackend", HeldoutMustNotRun)
    monkeypatch.setattr(
        script,
        "probe_isaac_train_generation_runtime",
        lambda **_: {
            "passed": False,
            "runtime_backend": "isaac_runtime",
            "proof_runtime": "isaac_scripted_expert_train_generation_probe",
            "actual_train_generation_evidence": False,
            "training_trajectory_source": "isaac_runtime_scripted_expert_rollout",
            "generated_rollout_count": 40,
            "generated_success_count": 19,
            "required_success_count": 20,
            "generated_success_trace_paths": [],
            "reason": "only 19 actual env-native success traces generated",
        },
    )

    report = script.build_mvp2c_isaac_training_calibration(
        output_dir=tmp_path / "mvp2e",
        clean=True,
        scenario_profile="v0_6",
        skip_isaac=False,
        use_deterministic_eval_backend=False,
        min_rollouts_per_policy=20,
        bootstrap_iterations=20,
    )

    assert report["mvp2_closed"] is False
    assert report["actual_rollouts_per_policy"] == 0
    assert report["heldout_schedule"]["scheduled"] is False
    assert report["heldout_schedule"]["blocked_by_train_generation_gate"] is True
    assert "v0_6 train-generation gate" in report["heldout_schedule"]["reason"]


def test_mvp2c_train_generation_probe_uses_dedicated_scripted_expert_controller() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    policy = script._scripted_expert_probe_policy_artifact(
        selected_adapter_id="isaac_signed_xy_downward_servo_v0",
        selected_adapter_config={
            "xy_source": "policy_plus_state_feedback",
            "xy_state_feedback_gain": 1.5,
            "xy_action_clip": 0.04,
            "z_action_scale": 32.0,
            "z_action_clip": 0.16,
        },
    )

    config = policy["selected_action_adapter_config"]
    assert policy["policy_class"] == "scripted_expert_probe_policy_v0"
    assert config["xy_source"] == "state_feedback"
    assert config["xy_state_feedback_gain"] >= 4.0
    assert config["z_action_scale"] >= 24.0
    assert config["z_action_clip"] <= 0.12
    assert policy["train_generation_controller_config_sha256"]


def test_mvp2c_closure_requires_calibration_and_leakage_guards() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    closure = script.derive_mvp2c_closure(
        learning_report={
            "learning_proven": True,
            "proof_eligible": True,
            "curated_vs_uncurated_uplift": 0.25,
            "baseline_success_rate": 0.40,
            "candidate_success_rate": 0.70,
        },
        runtime_gate={
            "passed": True,
            "runtime_backend": "isaac_runtime",
            "proof_runtime": "dedicated_isaac_connector_insertion_evaluator",
        },
        train_generation_runtime_gate={
            "passed": True,
            "runtime_backend": "isaac_runtime",
            "actual_train_generation_evidence": True,
            "training_trajectory_source": "isaac_runtime_scripted_expert_rollout",
        },
        calibration_selection_report={
            "calibration_only_selection_passed": False,
            "heldout_excluded": True,
            "selected_adapter_frozen_before_heldout": True,
            "same_adapter_used_for_baseline_and_candidate": True,
        },
        heldout_leakage_guard={"passed": False},
        actual_rollouts_per_policy=20,
    )

    assert closure["mvp2_closed"] is False
    assert any("calibration-only action adapter selection" in blocker for blocker in closure["blockers"])
    assert any("held-out leakage guard" in blocker for blocker in closure["blockers"])


def test_mvp2c_fake_actual_runtime_closes_with_same_adapter_and_policy_fairness(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

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
            rollout_count = max(int(kwargs["min_rollouts_per_policy"]), len(heldout))
            baseline_rollouts = []
            candidate_rollouts = []
            baseline_paths = []
            candidate_paths = []
            for index in range(rollout_count):
                scenario = heldout[index % len(heldout)]
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
    monkeypatch.setattr(
        script,
        "probe_isaac_train_generation_runtime",
        lambda **_: {
            "passed": True,
            "runtime_backend": "isaac_runtime",
            "proof_runtime": "isaac_scripted_expert_train_generation_probe",
            "actual_train_generation_evidence": True,
            "training_trajectory_source": "isaac_runtime_scripted_expert_rollout",
            "reason": "",
        },
    )

    report = script.build_mvp2c_isaac_training_calibration(
        output_dir=tmp_path / "mvp2c",
        clean=True,
        skip_isaac=False,
        use_deterministic_eval_backend=False,
        min_rollouts_per_policy=20,
        bootstrap_iterations=200,
    )

    baseline = report["policy_artifacts"]["baseline"]
    candidate = report["policy_artifacts"]["candidate"]
    assert report["mvp2_closed"] is True
    assert report["mvp2c_close_minimum_passed"] is True
    assert report["stronger_public_evidence_target_passed"] is False
    assert report["actual_rollouts_per_policy"] == 20
    assert baseline["trainer"] == candidate["trainer"]
    assert baseline["policy_class"] == candidate["policy_class"]
    assert baseline["feature_schema"] == candidate["feature_schema"]
    assert baseline["phase_schema"] == candidate["phase_schema"]
    assert baseline["selected_action_adapter_id"] == candidate["selected_action_adapter_id"]
    assert report["policy_eval_binding"]["same_adapter_used_for_baseline_and_candidate"] is True
    assert report["manifest_version"] == "rdf_mvp2c_scenario_manifest_v0.1.0"
    assert report["selector_score_config_sha256"]
    assert report["selected_action_adapter_id"] == baseline["selected_action_adapter_id"]
    assert report["selected_action_adapter_sha256"]
    assert report["selector_score_pre_registered"] is True
    assert report["heldout_excluded"] is True
    assert report["calibration_only_selection_passed"] is True
    assert report["heldout_leakage_guard_passed"] is True
    assert "--max-steps" in report["reproducible_command"]
    assert "--action-scale" in report["reproducible_command"]
