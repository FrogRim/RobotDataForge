from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
from typing import Any

import h5py
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


def write_v07a2_runtime_trace(
    script: Any,
    path: Path,
    *,
    scenario_id: str,
    seed: int,
    success: bool,
    hold_tail_count: int = 2,
) -> None:
    trace: list[dict[str, Any]] = [
        {
            "step": 0,
            "phase": "APPROACH",
            "env_native_success": False,
            "env_native_success_mask": False,
            "insertion_depth_m": 0.0,
            "relative_x_m": 0.004,
            "relative_y_m": 0.0,
            "lateral_error_m": 0.004,
            "orientation_error_deg": 2.0,
            "normalized_action": [-0.02, 0.0, 0.0, 0.0, 0.0, 0.0],
        },
        {
            "step": 1,
            "phase": "CONTACT",
            "env_native_success": False,
            "env_native_success_mask": False,
            "insertion_depth_m": 0.012,
            "relative_x_m": 0.0008,
            "relative_y_m": 0.0,
            "lateral_error_m": 0.0008,
            "orientation_error_deg": 1.0,
            "normalized_action": [-0.004, 0.0, -0.16, 0.0, 0.0, 0.0],
        },
    ]
    for offset in range(hold_tail_count if success else 0):
        trace.append(
            {
                "step": 2 + offset,
                "phase": "SEAT",
                "env_native_success": True,
                "env_native_success_mask": True,
                "insertion_depth_m": 0.024,
                "relative_x_m": 0.0002,
                "relative_y_m": 0.0,
                "lateral_error_m": 0.0002,
                "orientation_error_deg": 0.2,
                "normalized_action": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            }
        )
    script.write_json(
        path,
        {
            "schema_version": "rdf_mvp2c_isaac_runtime_trace_v0.1.0",
            "runtime_backend": "isaac_runtime",
            "scenario": {"scenario_id": scenario_id, "seed": seed},
            "summary": {"success": success, "failure_reason": "" if success else "env_native_window_missing"},
            "trace": trace,
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


def test_v07a_behavior_state_phase_assignment_uses_lateral_gate_and_depth() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    assert script.derive_v07a_behavior_state_phase(
        {"lateral_error_m": 0.0011, "insertion_depth_m": 0.040}
    ) == "ALIGN"
    assert script.derive_v07a_behavior_state_phase(
        {"lateral_error_m": 0.001, "insertion_depth_m": 0.029}
    ) == "DESCEND"
    assert script.derive_v07a_behavior_state_phase(
        {"lateral_error_m": 0.001, "insertion_depth_m": 0.03}
    ) == "HOLD"


def test_v07a_relabel_preserves_original_depth_phase() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    row = script.relabel_v07a_training_row(
        {
            "phase": "APPROACH",
            "lateral_error_m": 0.0008,
            "insertion_depth_m": 0.012,
            "normalized_action": [0.0] * len(script.ACTION_SCHEMA),
        }
    )

    assert row["phase"] == "APPROACH"
    assert row["original_depth_phase"] == "APPROACH"
    assert row["behavior_state_phase"] == "DESCEND"
    assert row["phase_label_source"] == "frozen_v0_7a_behavior_state_rule"


def test_v07a_relabel_rejects_missing_required_metrics() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    with pytest.raises(ValueError, match="row_missing_required_metric"):
        script.relabel_v07a_training_row({"phase": "APPROACH", "insertion_depth_m": 0.0})

    with pytest.raises(ValueError, match="relabel_config_invalid"):
        script.relabel_v07a_training_row(
            {"phase": "APPROACH", "lateral_error_m": float("nan"), "insertion_depth_m": 0.0}
        )


def test_v07a1_behavior_state_phase_uses_env_native_mask_as_hold_authority() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    assert (
        script.derive_v07a1_behavior_state_phase(
            {"env_native_success": True, "lateral_error_m": 0.2, "insertion_depth_m": 0.0}
        )
        == "HOLD"
    )
    assert (
        script.derive_v07a1_behavior_state_phase(
            {"env_native_success": False, "lateral_error_m": 0.001, "insertion_depth_m": 0.025}
        )
        == "DESCEND"
    )
    assert (
        script.derive_v07a1_behavior_state_phase(
            {"env_native_success": False, "lateral_error_m": 0.0011, "insertion_depth_m": 0.025}
        )
        == "ALIGN"
    )


def test_v07a1_behavior_state_phase_rejects_missing_env_native_mask() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    with pytest.raises(ValueError, match="env_native_mask_missing"):
        script.derive_v07a1_behavior_state_phase({"lateral_error_m": 0.0, "insertion_depth_m": 0.025})


def test_v07a1_relabel_config_removes_geometry_seat_depth_threshold(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    config = script.build_v07a1_relabel_config(
        output_dir=tmp_path,
        parent_artifact_hashes={"parent_train_generation_runtime_gate_file_sha256": "abc"},
    )

    text = script.stable_json(config)
    assert "seat_depth_threshold_m" not in config
    assert "SUCCESS_METRIC.insertion_depth_m_min" not in text
    assert config["hold_authority"] == "env_native_success_mask"


def test_v07a2_trace_native_config_forbids_geometry_hold_threshold(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    config = script.build_v07a2_trace_native_config(
        output_dir=tmp_path,
        parent_train_generation_runtime_gate_sha256="abc",
    )

    text = script.stable_json(config)
    assert "seat_depth_threshold_m" not in config
    assert "SUCCESS_METRIC.insertion_depth_m_min" not in text
    assert config["hold_authority"] == "env_native_success_mask"
    assert config["behavior_phase_rule_version"] == "env_native_hold_v0_7a_2"


def test_v07b_residual_servo_config_is_hash_stable_and_non_closing(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    config = script.build_v07b_residual_servo_config(
        output_dir=tmp_path,
        parent_config_sha256="parent-v07a2-config-sha",
    )

    assert config["schema_version"] == script.V07B_RESIDUAL_SERVO_CONFIG_SCHEMA_VERSION
    assert config["policy_slice"] == "v0_7b"
    assert config["base_servo_id"] == "frozen_base_geometry_servo_v0_7b"
    assert config["residual_target_definition"] == (
        "actual_trace_action_minus_frozen_base_geometry_servo_action"
    )
    assert config["base_servo_config"]["closing_gate"] is False
    assert config["heldout_21000_21049_accessed"] is False
    assert config["base_servo_config_sha256"] == script._sha256_payload(config["base_servo_config"])
    assert config["v0_7b_residual_servo_config_sha256"] == script._sha256_payload_excluding(
        config,
        "v0_7b_residual_servo_config_sha256",
    )
    assert (tmp_path / "v0_7b_residual_servo_config.json").exists()

    script.validate_v07b_residual_servo_config_contract(config)
    tampered = {**config, "residual_target_definition": "wrong"}
    with pytest.raises(ValueError, match="v0_7b_residual_servo_config"):
        script.validate_v07b_residual_servo_config_contract(tampered)


def test_v07b_trace_row_residual_target_is_actual_minus_base(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    config = script.build_v07b_residual_servo_config(
        output_dir=tmp_path,
        parent_config_sha256="parent-v07a2-config-sha",
    )
    v07a2_row = script.trace_row_to_v07a2_train_row(
        {
            "step": 4,
            "phase": "INSERT",
            "env_native_success_mask": False,
            "lateral_error_m": 0.002,
            "insertion_depth_m": 0.024,
            "relative_x_m": 0.002,
            "relative_y_m": -0.001,
            "orientation_error_deg": 1.0,
            "normalized_action": [-0.011, 0.007, -0.12, 0.0, 0.0, 0.0, 1.0],
        },
        source_trace_path=Path("/tmp/train_success_19003_isaac_trace.json"),
        source_trace_sha256="trace-sha",
        trajectory_id="train_success_19003",
        source_trace_role="candidate_success",
        accepted=True,
    )

    residual_row = script.trace_row_to_v07b_residual_train_row(
        v07a2_row,
        residual_servo_config=config,
    )

    actual = script.np.asarray(residual_row["actual_trace_action"])
    base = script.np.asarray(residual_row["base_servo_action"])
    residual = script.np.asarray(residual_row["normalized_action"])
    assert script.np.allclose(base + residual, actual)
    assert residual_row["policy_slice"] == script.V07B_POLICY_SLICE_ID
    assert residual_row["base_servo_id"] == script.V07B_BASE_SERVO_ID
    assert residual_row["residual_target_definition"] == script.V07B_RESIDUAL_TARGET_DEFINITION
    assert residual_row["proof_role"] == "trace_native_residual_train"

    heldout_row = {**v07a2_row, "trajectory_id": "held_out_21000"}
    with pytest.raises(ValueError, match="protected_heldout_seed_range_access"):
        script.trace_row_to_v07b_residual_train_row(heldout_row, residual_servo_config=config)


def test_v07b_recovery_overlay_requires_shared_non_policy_source(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    config = script.build_v07b_residual_servo_config(
        output_dir=tmp_path,
        parent_config_sha256="parent-v07a2-config-sha",
    )
    source_path = tmp_path / "shared_train_recovery_induction_v0_7b.json"
    script.write_json(
        source_path,
        {
            "schema_version": "rdf_mvp2e_v07b_shared_recovery_induction_v0.1.0",
            "source_seeds": [19003, 19012, 19129, 19030, 19119],
            "state_induction_policy": "candidate_v0_7a_2_policy",
            "source_policy_slice": "v0_7a_2",
            "policy_specific_source": True,
            "shared_overlay_for_both_views": False,
            "proof_authority": False,
            "traces": [],
        },
    )

    with pytest.raises(ValueError, match="recovery_overlay_labeler_unavailable"):
        script.build_v07b_train_recovery_overlay(
            source_path=source_path,
            residual_servo_config=config,
            parent_controller_repair_config={"controller_repair_version": "v0_6i"},
        )


def test_v07b_recovery_overlay_rejects_empty_or_failed_shared_source(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    config = script.build_v07b_residual_servo_config(
        output_dir=tmp_path,
        parent_config_sha256="parent-v07a2-config-sha",
    )
    source_path = tmp_path / "shared_train_recovery_induction_v0_7b.json"
    script.write_json(
        source_path,
        {
            "schema_version": script.V07B_SHARED_RECOVERY_INDUCTION_SCHEMA_VERSION,
            "source_seeds": list(script.V07B_RECOVERY_SOURCE_SEEDS),
            "state_induction_policy": "shared_frozen_base_servo",
            "source_policy_slice": "none",
            "policy_specific_source": False,
            "shared_overlay_for_both_views": True,
            "proof_authority": False,
            "passed": False,
            "traces": [],
        },
    )

    with pytest.raises(ValueError, match="recovery_overlay_source_unavailable"):
        script.build_v07b_train_recovery_overlay(
            source_path=source_path,
            residual_servo_config=config,
            parent_controller_repair_config={"controller_repair_version": "v0_6i"},
        )


def test_v07b_recovery_induction_manifest_uses_fixed_train_seeds_as_probe_only(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    source_manifest = script.build_mvp2c_scenario_manifest(output_dir=tmp_path, scenario_profile="v0_6")

    recovery_manifest = script.build_v07b_shared_recovery_induction_manifest(source_manifest)

    assert recovery_manifest["schema_version"] == "rdf_mvp2e_v07b_shared_recovery_induction_manifest_v0.1.0"
    assert recovery_manifest["selected_seed_ids"] == list(script.V07B_RECOVERY_SOURCE_SEEDS)
    assert recovery_manifest["heldout_21000_21049_accessed"] is False
    assert all(row["split"] == "held_out" for row in recovery_manifest["scenarios"])
    assert all(row["source_split"] == "train_success" for row in recovery_manifest["scenarios"])
    assert {row["seed"] for row in recovery_manifest["scenarios"]} == set(script.V07B_RECOVERY_SOURCE_SEEDS)


def test_v07b_shared_base_servo_policy_artifact_is_not_candidate_or_baseline(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    residual_config = script.build_v07b_residual_servo_config(
        output_dir=tmp_path,
        parent_config_sha256="parent-v07a2-config-sha",
    )
    selected_adapter = {
        "selected_adapter_id": "isaac_signed_xy_downward_servo_v0",
        "selected_adapter_config": {"adapter_mode": "global_action_scale", "z_action_scale": 1.0},
    }

    policy = script.build_v07b_shared_base_servo_recovery_policy_artifact(
        residual_servo_config=residual_config,
        selected_adapter=selected_adapter,
    )

    assert policy["policy_id"] == "shared_frozen_base_servo_v0_7b_recovery_induction"
    assert policy["source_policy_slice"] == "none"
    assert policy["policy_specific_source"] is False
    assert policy["shared_overlay_for_both_views"] is True
    assert policy["base_servo_id"] == script.V07B_BASE_SERVO_ID
    assert policy["residual_target_definition"] == script.V07B_RESIDUAL_TARGET_DEFINITION
    assert policy["policy_artifact_sha256"] == script._sha256_payload_excluding(policy, "policy_artifact_sha256")


def test_v07b_recovery_induction_runtime_builds_source_from_backend_trace_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    script.build_mvp2c_scenario_manifest(output_dir=tmp_path, scenario_profile="v0_6")
    script.write_json(
        tmp_path / "selected_action_adapter.json",
        {
            "selected_adapter_id": "isaac_signed_xy_downward_servo_v0",
            "selected_adapter_config": {"adapter_mode": "global_action_scale", "z_action_scale": 1.0},
            "selected_adapter_config_sha256": "fixture",
        },
    )

    class FakeBackend:
        runtime_backend = "isaac_runtime"
        proof_runtime = "dedicated_isaac_connector_insertion_evaluator"

        def __init__(self, **_: object) -> None:
            pass

        def run_single_policy_probe(self, *, manifest, output_dir, policy_artifact, role, max_rollouts, stop_after_first_success):
            del policy_artifact, max_rollouts, stop_after_first_success
            trace_dir = output_dir / "isaac_runtime_heldout_rollout_traces"
            trace_dir.mkdir(parents=True, exist_ok=True)
            paths = []
            rollouts = []
            for index, scenario in enumerate(manifest["scenarios"]):
                trace_path = trace_dir / f"{role}_{index:04d}_{scenario['scenario_id']}_isaac_trace.json"
                script.write_json(
                    trace_path,
                    {
                        "schema_version": "rdf_mvp2b_isaac_runtime_trace_v0.1.0",
                        "scenario": scenario,
                        "trace": [
                            {
                                "step": 0,
                                "phase": "APPROACH",
                                "behavior_state_phase": "ALIGN",
                                "relative_x_m": 0.002,
                                "relative_y_m": 0.0,
                                "lateral_error_m": 0.002,
                                "insertion_depth_m": 0.0,
                                "orientation_error_deg": 0.0,
                                "normalized_action": [0.0] * len(script.ACTION_SCHEMA),
                            }
                        ],
                        "summary": {"success": False, "failure_reason": "diagnostic_recovery_source"},
                    },
                )
                paths.append(str(trace_path))
                rollouts.append(
                    {
                        "rollout_id": f"{role}_{index:04d}",
                        "scenario_id": scenario["scenario_id"],
                        "success": False,
                        "failure_reason": "diagnostic_recovery_source",
                        "rollout_log_ref": str(trace_path),
                    }
                )
            return script.BackendResult(
                runtime_backend="isaac_runtime",
                proof_runtime="dedicated_isaac_connector_insertion_evaluator",
                runtime_gate={"passed": True, "runtime_backend": "isaac_runtime"},
                baseline_rollouts=rollouts,
                candidate_rollouts=[],
                baseline_trace_paths=paths,
                candidate_trace_paths=[],
                runtime_metadata={"runtime_backend": "isaac_runtime"},
            )

    monkeypatch.setattr(script, "IsaacConnectorInsertionEvaluatorBackend", FakeBackend)

    artifact = script.run_v07b_shared_train_recovery_induction_runtime(
        output_dir=tmp_path,
        device="cpu",
        headless=True,
        isaac_task="Isaac-Factory-PegInsert-Direct-v0",
        max_steps=150,
        action_scale=1.0,
    )

    assert artifact["passed"] is True
    assert artifact["source_policy_slice"] == "none"
    assert artifact["policy_specific_source"] is False
    assert artifact["source_seeds"] == list(script.V07B_RECOVERY_SOURCE_SEEDS)
    assert len(artifact["trace_paths"]) == len(script.V07B_RECOVERY_SOURCE_SEEDS)
    assert artifact["heldout_21000_21049_accessed"] is False

    overlay = script.build_v07b_train_recovery_overlay(
        source_path=tmp_path / script.V07B_CHILD_OUTPUT_DIRNAME / "shared_train_recovery_induction_v0_7b.json",
        residual_servo_config=script.read_json(
            tmp_path / script.V07B_CHILD_OUTPUT_DIRNAME / "v0_7b_residual_servo_config.json"
        ),
        parent_controller_repair_config={"controller_repair_version": "v0_6i"},
    )
    assert overlay["manifest"]["row_count"] == len(script.V07B_RECOVERY_SOURCE_SEEDS)
    assert all(row["proof_role"] == "train_closed_loop_recovery_correction" for row in overlay["rows"])


def test_v07b_offline_residual_fit_gate_uses_reconstructed_action_metrics(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    config = script.build_v07b_residual_servo_config(
        output_dir=tmp_path,
        parent_config_sha256="parent-v07a2-config-sha",
    )
    rows = []
    for phase, z in (("ALIGN", 0.0), ("DESCEND", -0.16), ("HOLD", 0.0)):
        row = {
            "trajectory_id": f"fixture_{phase.lower()}",
            "step": 0,
            "phase": "APPROACH" if phase == "ALIGN" else "INSERT",
            "behavior_state_phase": phase,
            "insertion_depth_m": 0.0 if phase == "ALIGN" else 0.024,
            "relative_x_m": 0.001,
            "relative_y_m": 0.0,
            "lateral_error_m": 0.001,
            "orientation_error_deg": 0.0,
            "normalized_action": [0.0, 0.0, z, 0.0, 0.0, 0.0, 0.0],
            "base_servo_action": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
            "actual_trace_action": [0.0, 0.0, z, 0.0, 0.0, 0.0, 1.0],
            "accepted": True,
        }
        rows.append(row)

    gate = script.derive_v07b_offline_residual_fit_gate(
        candidate_rows=rows,
        candidate_predictions=[row["normalized_action"] for row in rows],
        candidate_policy_artifact_sha256="candidate-sha",
        residual_servo_config_sha256=config["v0_7b_residual_servo_config_sha256"],
        baseline_rows=rows,
        baseline_predictions=[row["normalized_action"] for row in rows],
        baseline_policy_artifact_sha256="baseline-sha",
    )

    assert gate["schema_version"] == script.V07B_OFFLINE_RESIDUAL_FIT_GATE_SCHEMA_VERSION
    assert gate["passed"] is True
    assert gate["candidate_residual_action_rmse_max"] == 0.0
    assert gate["candidate_reconstructed_action_rmse_max"] == 0.0
    assert gate["candidate_descend_reconstructed_negative_z_rate"] == 1.0
    assert gate["baseline_same_metrics_report_only"]["metric_role"] == "baseline_report_only"


def test_v07c_action_authority_config_is_hash_stable_and_shared(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    residual_config = script.build_v07b_residual_servo_config(
        output_dir=tmp_path / "v07b",
        parent_config_sha256="parent-v07a2-config-sha",
    )

    config = script.build_v07c_action_authority_config(
        output_dir=tmp_path,
        residual_servo_config=residual_config,
        selected_action_adapter_id="isaac_signed_xy_downward_servo_v0",
    )

    assert config["schema_version"] == script.V07C_ACTION_AUTHORITY_CONFIG_SCHEMA_VERSION
    assert config["policy_slice"] == "v0_7c"
    assert config["authority_filter_id"] == "frozen_residual_action_authority_gate_v0_7c"
    assert config["base_servo_id"] == "frozen_base_geometry_servo_v0_7b"
    assert config["behavior_phase_rule_version"] == "env_native_hold_v0_7a_2"
    assert config["align_z_authority"] == "base_servo_z_only"
    assert config["descend_z_authority"] == "base_plus_residual"
    assert config["hold_z_authority"] == "base_plus_residual"
    assert config["candidate_specific"] is False
    assert config["baseline_specific"] is False
    assert config["heldout_21000_21049_accessed"] is False
    assert config["authority_filter_config_sha256"] == script._sha256_payload_excluding(
        config,
        "authority_filter_config_sha256",
    )
    assert (tmp_path / "v0_7c_action_authority_config.json").exists()
    script.validate_v07c_action_authority_config_contract(script.read_json(tmp_path / "v0_7c_action_authority_config.json"))


def test_v07c_authority_filter_suppresses_align_residual_z(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    residual_config = script.build_v07b_residual_servo_config(
        output_dir=tmp_path,
        parent_config_sha256="parent-v07a2-config-sha",
    )
    config = script.build_v07c_action_authority_config(
        output_dir=tmp_path,
        residual_servo_config=residual_config,
        selected_action_adapter_id="isaac_signed_xy_downward_servo_v0",
    )
    base = script.np.asarray([0.0, 0.0, -0.001, 0.0, 0.0, 0.0, 1.0])
    residual = script.np.asarray([0.0, 0.0, -0.09, 0.0, 0.0, 0.0, 0.0])
    before = base + residual

    after, diagnostics = script.apply_v07c_action_authority_filter(
        behavior_state_phase="ALIGN",
        base_action=base,
        residual_prediction=residual,
        raw_action_before_authority=before,
        authority_config=config,
    )

    assert before[2] == pytest.approx(-0.091)
    assert after[2] == pytest.approx(-0.001)
    assert diagnostics["residual_z_before_authority"] == pytest.approx(-0.09)
    assert diagnostics["residual_z_after_authority"] == pytest.approx(0.0)
    assert diagnostics["align_residual_z_suppressed"] is True
    assert diagnostics["z_authority_source"] == "base_servo"


def test_v07c_authority_filter_preserves_descend_and_hold_residual_z(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    residual_config = script.build_v07b_residual_servo_config(
        output_dir=tmp_path,
        parent_config_sha256="parent-v07a2-config-sha",
    )
    config = script.build_v07c_action_authority_config(
        output_dir=tmp_path,
        residual_servo_config=residual_config,
        selected_action_adapter_id="isaac_signed_xy_downward_servo_v0",
    )
    base = script.np.asarray([0.0, 0.0, -0.002, 0.0, 0.0, 0.0, 1.0])
    residual = script.np.asarray([0.0, 0.0, -0.07, 0.0, 0.0, 0.0, 0.0])
    before = base + residual

    for phase in ("DESCEND", "HOLD"):
        after, diagnostics = script.apply_v07c_action_authority_filter(
            behavior_state_phase=phase,
            base_action=base,
            residual_prediction=residual,
            raw_action_before_authority=before,
            authority_config=config,
        )
        assert script.np.allclose(after, before)
        assert diagnostics["align_residual_z_suppressed"] is False
        assert diagnostics["residual_z_after_authority"] == pytest.approx(-0.07)
        assert diagnostics["z_authority_source"] == "base_plus_residual"


def _v07c_policy_artifact(script: Any, config: dict[str, Any], *, role: str, adapter_id: str | None = None) -> dict[str, Any]:
    return {
        "policy_id": f"{role}_policy",
        "policy_slice": "v0_7c",
        "dataset_view_role": role,
        "policy_class": "phase_conditioned_residual_servo_bc_policy_v0",
        "trainer": "rdf_numpy_phase_conditioned_residual_servo_bc_trainer_v0",
        "trainer_family": "phase_conditioned_residual_servo_bc",
        "hyperparameters": {"ridge_lambda": 1e-3},
        "base_servo_id": script.V07B_BASE_SERVO_ID,
        "base_servo_config_sha256": config["base_servo_config_sha256"],
        "residual_target_definition": script.V07B_RESIDUAL_TARGET_DEFINITION,
        "authority_filter_id": script.V07C_AUTHORITY_FILTER_ID,
        "authority_filter_config": dict(config),
        "authority_filter_config_sha256": config["authority_filter_config_sha256"],
        "selected_action_adapter_id": adapter_id or "isaac_signed_xy_downward_servo_v0",
        "heldout_21000_21049_accessed": False,
    }


def _v07c_rows(script: Any) -> list[dict[str, Any]]:
    return [
        {
            "trajectory_id": "fixture_align",
            "behavior_state_phase": "ALIGN",
            "phase": "APPROACH",
            "normalized_action": [0.0, 0.0, -0.09, 0.0, 0.0, 0.0, 0.0],
            "base_servo_action": [0.0, 0.0, -0.001, 0.0, 0.0, 0.0, 1.0],
            "actual_trace_action": [0.0, 0.0, -0.091, 0.0, 0.0, 0.0, 1.0],
        },
        {
            "trajectory_id": "fixture_descend",
            "behavior_state_phase": "DESCEND",
            "phase": "INSERT",
            "normalized_action": [0.0, 0.0, -0.07, 0.0, 0.0, 0.0, 0.0],
            "base_servo_action": [0.0, 0.0, -0.002, 0.0, 0.0, 0.0, 1.0],
            "actual_trace_action": [0.0, 0.0, -0.072, 0.0, 0.0, 0.0, 1.0],
        },
        {
            "trajectory_id": "fixture_hold",
            "behavior_state_phase": "HOLD",
            "phase": "SEAT",
            "normalized_action": [0.0, 0.0, 0.002, 0.0, 0.0, 0.0, 0.0],
            "base_servo_action": [0.0, 0.0, -0.0005, 0.0, 0.0, 0.0, 1.0],
            "actual_trace_action": [0.0, 0.0, 0.0015, 0.0, 0.0, 0.0, 1.0],
        },
    ]


def _write_mvp2e_harness_fixture(
    script: Any,
    output_dir: Path,
    *,
    seed: int = 19003,
    include_required_diagnostics: bool = True,
    post_adapter_z: float = -0.032,
    base_servo_z: float = 0.0,
    baseline_adapter_id: str | None = None,
) -> Path:
    child_dir = output_dir / script.V07C_CHILD_OUTPUT_DIRNAME
    residual_config = script.build_v07b_residual_servo_config(
        output_dir=child_dir / "v07b_config",
        parent_config_sha256="parent-v07a2-config-sha",
    )
    authority_config = script.build_v07c_action_authority_config(
        output_dir=child_dir,
        residual_servo_config=residual_config,
        selected_action_adapter_id="isaac_signed_xy_downward_servo_v0",
    )
    script.write_json(
        child_dir / "candidate_policy_artifact_v0_7c.json",
        _v07c_policy_artifact(script, authority_config, role="candidate_curated"),
    )
    script.write_json(
        child_dir / "baseline_policy_artifact_v0_7c.json",
        _v07c_policy_artifact(
            script,
            authority_config,
            role="baseline_uncurated",
            adapter_id=baseline_adapter_id,
        ),
    )
    trace_dir = (
        child_dir
        / "isaac_runtime_expressibility_sanity_v0_7c"
        / "isaac_runtime_heldout_rollout_traces"
    )
    trace_path = trace_dir / f"v0_7c_expressibility_sanity_0000_train_success_{seed}_isaac_trace.json"
    diagnostics = {
        "schema_version": "rdf_mvp2e_controller_action_diagnostics_v0.1.0",
        "behavior_state_phase": "ALIGN",
        "selected_action_adapter_id": "isaac_signed_xy_downward_servo_v0",
        "base_servo_action": [0.0, 0.0, base_servo_z, 0.0, 0.0, 0.0, 1.0],
        "residual_prediction": [0.0, 0.0, -0.09, 0.0, 0.0, 0.0, 0.0],
        "raw_action_before_authority": [0.0, 0.0, -0.09, 0.0, 0.0, 0.0, 1.0],
        "raw_action_after_authority": [0.0, 0.0, base_servo_z, 0.0, 0.0, 0.0, 1.0],
        "post_adapter_action_vector": [0.0, 0.0, post_adapter_z, 0.0, 0.0, 0.0, 1.0],
        "residual_z_after_authority": 0.0,
        "authority_filter_config_sha256": authority_config["authority_filter_config_sha256"],
    }
    row: dict[str, Any] = {
        "step": 0,
        "phase": "APPROACH",
        "insertion_depth_m": 0.0,
        "relative_x_m": 0.010,
        "relative_y_m": 0.0,
        "lateral_error_m": 0.010,
        "orientation_error_deg": 0.0,
        "normalized_action": [0.0, 0.0, post_adapter_z, 0.0, 0.0, 0.0, 1.0],
    }
    if include_required_diagnostics:
        row["controller_action_diagnostics"] = diagnostics
    script.write_json(
        trace_path,
        {
            "schema_version": "rdf_mvp2c_isaac_runtime_trace_v0.1.0",
            "runtime_backend": "isaac_runtime",
            "scenario": {"scenario_id": f"train_success_{seed}", "seed": seed},
            "summary": {"success": False, "failure_reason": "fixture_failure"},
            "trace": [row],
        },
    )
    script.write_json(
        child_dir / "expressibility_sanity_gate_v0_7c.json",
        {
            "schema_version": script.V07C_EXPRESSIBILITY_SANITY_GATE_SCHEMA_VERSION,
            "policy_slice": "v0_7c",
            "passed": False,
            "rollout_count": 1,
            "success_count": 0,
            "heldout_21000_21049_accessed": False,
            "trace_paths": [str(trace_path)],
        },
    )
    return trace_path


def test_mvp2e_harness_config_is_hash_stable_and_seals_heldout(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    config = script.build_mvp2e_harness_config(output_dir=tmp_path)

    assert config["schema_version"] == script.MVP2E_HARNESS_CONFIG_SCHEMA_VERSION
    assert config["scenario_profile"] == "v0_6"
    assert config["policy_slice_under_test"] == "v0_7c"
    assert config["protected_heldout_seed_range"] == [21000, 21049]
    assert config["calibration_accessed"] is False
    assert config["heldout_21000_21049_accessed"] is False
    assert config["downstream_slice_created"] is False
    assert config["mvp2_closed"] is False
    assert config["mvp2e_harness_config_sha256"] == script._sha256_payload_excluding(
        config,
        "mvp2e_harness_config_sha256",
    )
    script.validate_mvp2e_harness_config(config)


def test_mvp2e_harness_report_contains_all_harnesses_and_classifies_v07c_leak(
    tmp_path: Path,
) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_mvp2e_harness_fixture(script, tmp_path, post_adapter_z=-0.032)

    report = script.build_mvp2e_harness_report(output_dir=tmp_path)

    assert set(report["harnesses"]) == {f"H{index}" for index in range(18)}
    assert report["harnesses"]["H1"]["status"] == "failed"
    assert report["harnesses"]["H2"]["status"] == "failed"
    assert report["root_cause_status"] == "classified"
    assert report["primary_root_cause_class"] == "ACTION_AUTHORITY_POST_ADAPTER_Z_LEAK"
    assert report["root_cause_class"] == report["primary_root_cause_class"]
    assert report["recommended_downstream_slice"] == "v0_7d_action_authority_post_adapter_z_gate"
    assert report["downstream_slice_created"] is False
    assert report["mvp2_closed"] is False


def test_mvp2e_harness_missing_real_trace_evidence_blocks_downstream_recommendation(
    tmp_path: Path,
) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_mvp2e_harness_fixture(script, tmp_path, include_required_diagnostics=False)

    report = script.build_mvp2e_harness_report(output_dir=tmp_path)

    assert report["root_cause_status"] == "missing_evidence"
    assert report["primary_root_cause_class"] is None
    assert report["root_cause_class"] is None
    assert report["recommended_downstream_slice"] is None
    assert report["missing_required_evidence"]
    assert report["harnesses"]["H1"]["status"] == "missing_evidence"
    assert report["harnesses"]["H2"]["status"] == "missing_evidence"
    assert report["harnesses"]["H3"]["status"] == "missing_evidence"


def test_mvp2e_harness_h15_adapter_mismatch_takes_precedence(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_mvp2e_harness_fixture(
        script,
        tmp_path,
        baseline_adapter_id="different_adapter",
        post_adapter_z=-0.032,
    )

    report = script.build_mvp2e_harness_report(output_dir=tmp_path)

    assert report["harnesses"]["H15"]["status"] == "failed"
    assert report["primary_root_cause_class"] == "NORMALIZATION_OR_ADAPTER_SCHEMA_MISMATCH"
    assert "ACTION_AUTHORITY_POST_ADAPTER_Z_LEAK" in report["secondary_root_cause_candidates"]


def test_mvp2e_harness_close_critical_not_evaluated_is_explicit_and_blocks_pass(
    tmp_path: Path,
) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_mvp2e_harness_fixture(script, tmp_path, post_adapter_z=0.0, base_servo_z=0.0)

    report = script.build_mvp2e_harness_report(output_dir=tmp_path)

    assert report["close_critical_passed"] is False
    assert "H5" in report["unevaluated_close_critical_harnesses"]
    assert "H17" in report["unevaluated_close_critical_harnesses"]
    for harness_id in report["unevaluated_close_critical_harnesses"]:
        harness = report["harnesses"][harness_id]
        assert harness["close_critical"] is True
        assert harness["status"] == "not_evaluated"
    for harness in report["harnesses"].values():
        if harness["close_critical"] is True:
            assert harness["tier"] == "close_critical"


def test_mvp2e_harness_h12_flags_stable_hold_geometry_constants(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_mvp2e_harness_fixture(script, tmp_path, post_adapter_z=0.0, base_servo_z=0.0)
    script.write_json(
        tmp_path / "selected_action_adapter.json",
        {
            "selected_adapter_id": "isaac_signed_xy_downward_servo_v0",
            "selected_adapter_config": {
                "stable_hold_depth_m": 0.03,
                "stable_hold_lateral_m": 0.006,
                "stable_hold_orientation_deg": 8.0,
                "z_action_scale": 32.0,
            },
        },
    )

    report = script.build_mvp2e_harness_report(output_dir=tmp_path)

    h12 = report["harnesses"]["H12"]
    assert h12["status"] == "failed"
    assert h12["reason"] == "stable_hold_uses_geometry_thresholds_instead_of_env_native_mask"
    assert h12["root_cause_candidates"] == ["PHASE_LABEL_RUNTIME_MISMATCH"]
    assert h12["evidence"]["stable_hold_depth_m"] == 0.03
    assert "replace_stable_hold_geometry_thresholds_with_env_native_mask" in report[
        "recommended_downstream_repair_requirements"
    ]


def test_mvp2e_harness_heldout_leakage_uses_protected_seed_not_legacy_path_label(
    tmp_path: Path,
) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_mvp2e_harness_fixture(script, tmp_path, seed=19003, post_adapter_z=0.0)

    report = script.build_mvp2e_harness_report(output_dir=tmp_path)

    assert report["protected_heldout_21000_21049_accessed"] is False
    assert report["legacy_heldout_path_label_interpretation"] == "directory_name_only_not_protected_seed_split"
    assert report["harnesses"]["H0"]["status"] == "passed"
    assert report["harnesses"]["H14"]["status"] == "passed"

    leak_dir = tmp_path / "leak"
    _write_mvp2e_harness_fixture(script, leak_dir, seed=21000, post_adapter_z=0.0)
    leak_report = script.build_mvp2e_harness_report(output_dir=leak_dir)

    assert leak_report["protected_heldout_21000_21049_accessed"] is True
    assert leak_report["harnesses"]["H0"]["status"] == "failed"
    assert leak_report["primary_root_cause_class"] == "EVALUATOR_OR_SCENARIO_MUTATION"


def test_mvp2e_harness_only_cli_rejects_clean_before_deleting_output(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    sentinel = tmp_path / "must_survive.txt"
    sentinel.write_text("existing evidence", encoding="utf-8")

    with pytest.raises(ValueError, match="harness-gated-closure-only.*--clean"):
        script.main(
            [
                "--scenario-profile",
                "v0_6",
                "--policy-slice",
                "v0_7c",
                "--harness-gated-closure-only",
                "--clean",
                "--output-dir",
                str(tmp_path),
            ]
        )

    assert sentinel.exists()


def _v07f_diag(
    *,
    action: list[float],
    phase: str = "DESCEND",
) -> dict[str, Any]:
    return {
        "schema_version": "rdf_mvp2e_v07f_test_controller_action_diagnostics_v0.1.0",
        "behavior_state_phase": phase,
        "post_adapter_action_vector": action,
        "raw_action_after_authority": action,
        "base_servo_action": [0.0, 0.0, -0.001, 0.0, 0.0, 0.0, 1.0],
        "residual_z_after_authority": action[2],
        "selected_action_adapter_id": "isaac_signed_xy_downward_servo_v0",
    }


def _v07f_row(
    step: int,
    *,
    lateral: float,
    depth: float,
    action: list[float],
    include_diagnostics: bool = True,
    include_relative: bool = True,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "step": step,
        "phase": "APPROACH",
        "insertion_depth_m": depth,
        "lateral_error_m": lateral,
        "orientation_error_deg": 0.1,
        "normalized_action": action[:6],
        "env_native_success": False,
        "env_native_success_mask": False,
    }
    if include_relative:
        row["relative_x_m"] = lateral
        row["relative_y_m"] = 0.0
    if include_diagnostics:
        row["controller_action_diagnostics"] = _v07f_diag(action=action)
    return row


def _write_v07f_policy_trace_fixture(
    script: Any,
    output_dir: Path,
    *,
    seed: int = 19030,
    include_diagnostics: bool = True,
    include_relative: bool = True,
) -> Path:
    trace_dir = (
        output_dir
        / script.V07E_CHILD_OUTPUT_DIRNAME
        / "isaac_runtime_expressibility_sanity_v0_7e"
        / "isaac_runtime_heldout_rollout_traces"
    )
    trace_path = trace_dir / f"v0_7e_expressibility_sanity_0000_train_success_{seed}_isaac_trace.json"
    rows = [
        _v07f_row(
            0,
            lateral=0.003,
            depth=0.0,
            action=[-0.01, 0.0, 0.0, 0, 0, 0, 1],
            include_diagnostics=include_diagnostics,
            include_relative=include_relative,
        ),
        _v07f_row(
            1,
            lateral=0.0005,
            depth=0.0,
            action=[-0.05, 0.05, -0.16, 0, 0, 0, 1],
            include_diagnostics=include_diagnostics,
            include_relative=include_relative,
        ),
        _v07f_row(
            2,
            lateral=0.006,
            depth=0.0,
            action=[-0.05, 0.05, -0.16, 0, 0, 0, 1],
            include_diagnostics=include_diagnostics,
            include_relative=include_relative,
        ),
    ]
    script.write_json(
        trace_path,
        {
            "schema_version": "rdf_mvp2c_isaac_runtime_trace_v0.1.0",
            "runtime_backend": "isaac_runtime",
            "proof_runtime": "v0_7e_expressibility_sanity",
            "scenario": {"scenario_id": f"train_success_{seed}", "seed": seed},
            "summary": {
                "success": False,
                "env_native_rollout_success": False,
                "env_native_max_consecutive_success_steps": 0,
                "failure_reason": "ENV_NATIVE_STABILITY_WINDOW_NOT_REACHED",
            },
            "trace": rows,
        },
    )
    return trace_path


def _write_v07f_expert_trace_fixture(script: Any, output_dir: Path, *, seed: int = 19030) -> Path:
    trace_dir = (
        output_dir
        / "isaac_runtime_train_generation_probe"
        / "isaac_runtime_heldout_rollout_traces"
    )
    trace_path = trace_dir / f"train_generation_probe_0000_train_success_{seed}_isaac_trace.json"
    rows = [
        _v07f_row(0, lateral=0.003, depth=0.0, action=[-0.01, 0.0, 0.0, 0, 0, 0, 1]),
        _v07f_row(1, lateral=0.0003, depth=0.012, action=[0.0002, 0.0, -0.16, 0, 0, 0, 1]),
        _v07f_row(2, lateral=0.0001, depth=0.025, action=[0.0, 0.0, -0.16, 0, 0, 0, 1]),
    ]
    script.write_json(
        trace_path,
        {
            "schema_version": "rdf_mvp2c_isaac_runtime_trace_v0.1.0",
            "runtime_backend": "isaac_runtime",
            "proof_runtime": "isaac_train_generation_probe",
            "scenario": {"scenario_id": f"train_success_{seed}", "seed": seed},
            "summary": {
                "success": True,
                "env_native_rollout_success": True,
                "env_native_max_consecutive_success_steps": 10,
                "failure_reason": "",
            },
            "trace": rows,
        },
    )
    return trace_path


def test_v07f_diagnostic_config_is_hash_stable_and_seals_heldout(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    config = script.build_v07f_diagnostic_config(output_dir=tmp_path)

    assert config["schema_version"] == script.V07F_DIAGNOSTIC_CONFIG_SCHEMA_VERSION
    assert config["policy_slice_under_test"] == "v0_7e"
    assert config["diagnostic_slice"] == "v0_7f"
    assert config["protected_heldout_seed_range"] == [21000, 21049]
    assert config["calibration_opened"] is False
    assert config["heldout_21000_21049_accessed"] is False
    assert config["mvp2_closed"] is False
    assert config["v0_7f_diagnostic_config_sha256"] == script._sha256_payload_excluding(
        config,
        "v0_7f_diagnostic_config_sha256",
    )
    script.validate_v07f_diagnostic_config(config)


def test_v07f_extracts_trace_summary_z_windows_depth_and_xy_saturation(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_v07f_policy_trace_fixture(script, tmp_path)
    trace_path = next(script._discover_v07f_policy_trace_paths(tmp_path))
    rows = script.read_json(trace_path)["trace"]

    summary = script._summarize_v07f_trace(rows)

    assert summary["row_count"] == 3
    assert summary["longest_nonzero_z"] == 2
    assert summary["z_open_spans"] == [{"start_step": 1, "end_step": 2, "length": 2}]
    assert summary["max_insertion_depth_m"] == 0.0
    assert summary["first_depth_positive_step"] is None
    assert summary["xy_saturation_count"] == 2
    assert summary["xy_saturation_during_z_open_ratio"] == 1.0


def test_v07f_extracts_z_open_lateral_regression(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_v07f_policy_trace_fixture(script, tmp_path)
    trace_path = next(script._discover_v07f_policy_trace_paths(tmp_path))

    summary = script._summarize_v07f_trace(script.read_json(trace_path)["trace"])

    assert summary["z_open_start_lateral_m"] == 0.0005
    assert summary["z_open_min_lateral_m"] == 0.0005
    assert summary["z_open_end_lateral_m"] == 0.006
    assert summary["z_open_regression_m"] == pytest.approx(0.0055)


def test_v07f_computes_action_to_state_sign_agreement_when_fields_exist(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_v07f_policy_trace_fixture(script, tmp_path)
    trace_path = next(script._discover_v07f_policy_trace_paths(tmp_path))

    agreement = script._v07f_action_to_state_sign_agreement(script.read_json(trace_path)["trace"])

    assert agreement["status"] == "evaluated"
    assert agreement["sample_count"] >= 2
    assert agreement["xy_sign_agreement_ratio"] > 0.5


def test_v07f_marks_sign_agreement_not_evaluated_when_fields_missing(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_v07f_policy_trace_fixture(script, tmp_path, include_relative=False)
    trace_path = next(script._discover_v07f_policy_trace_paths(tmp_path))

    agreement = script._v07f_action_to_state_sign_agreement(script.read_json(trace_path)["trace"])

    assert agreement["status"] == "not_evaluated"
    assert "relative_x_m" in agreement["missing_fields"]


def test_v07f_rejects_missing_controller_action_diagnostics(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_v07f_policy_trace_fixture(script, tmp_path, include_diagnostics=False)
    _write_v07f_expert_trace_fixture(script, tmp_path)

    report = script.build_v07f_depth_zero_harness_report(output_dir=tmp_path)

    assert report["root_cause_status"] == "missing_evidence"
    assert report["primary_root_cause_class"] == "TRACE_DIAGNOSTICS_INCOMPLETE"
    assert report["recommended_downstream_slice"] is None
    assert report["harnesses"]["H24"]["status"] == "failed"


def test_v07f_report_classifies_xy_saturation_and_preserves_claim_boundary(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_v07f_policy_trace_fixture(script, tmp_path)
    _write_v07f_expert_trace_fixture(script, tmp_path)

    report = script.build_v07f_depth_zero_harness_report(output_dir=tmp_path)

    assert report["root_cause_status"] == "classified"
    assert report["primary_root_cause_class"] == "XY_SATURATION_CENTERING_INSTABILITY"
    assert "Z_OPEN_LATERAL_REGRESSION" in report["secondary_root_cause_candidates"]
    assert report["recommended_downstream_slice"] == "v0_7g_xy_authority_saturation_repair"
    assert report["proof_authority"] == "diagnostic_only_not_closure_authority"
    assert report["mvp2_closed"] is False
    assert report["policy_uplift_proven"] is False
    assert report["phase_e_passed"] is False
    assert report["calibration_opened"] is False
    assert report["heldout_21000_21049_accessed"] is False


def test_v07f_rejects_protected_seed_in_policy_trace_discovery(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_v07f_policy_trace_fixture(script, tmp_path, seed=21000)
    _write_v07f_expert_trace_fixture(script, tmp_path, seed=19030)

    report = script.build_v07f_depth_zero_harness_report(output_dir=tmp_path)

    assert report["root_cause_status"] == "protected_seed_access_detected"
    assert report["protected_seed_violation"]["trace_set"] == "policy"
    assert report["heldout_21000_21049_accessed"] is True
    assert report["recommended_downstream_slice"] is None


def test_v07f_rejects_protected_seed_in_expert_reference_discovery(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_v07f_policy_trace_fixture(script, tmp_path, seed=19030)
    _write_v07f_expert_trace_fixture(script, tmp_path, seed=21000)

    report = script.build_v07f_depth_zero_harness_report(output_dir=tmp_path)

    assert report["root_cause_status"] == "protected_seed_access_detected"
    assert report["protected_seed_violation"]["trace_set"] == "expert_reference"
    assert report["heldout_21000_21049_accessed"] is True
    assert report["recommended_downstream_slice"] is None


def test_v07f_h22_not_evaluated_blocks_downstream_repair_recommendation(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_v07f_policy_trace_fixture(script, tmp_path, include_relative=False)
    _write_v07f_expert_trace_fixture(script, tmp_path)

    report = script.build_v07f_depth_zero_harness_report(output_dir=tmp_path)

    assert report["harnesses"]["H22"]["status"] == "not_evaluated"
    assert report["root_cause_status"] == "missing_evidence"
    assert report["recommended_downstream_slice"] is None


def test_v07f_cli_writes_artifacts_and_rejects_closure_leakage(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_v07f_policy_trace_fixture(script, tmp_path)
    _write_v07f_expert_trace_fixture(script, tmp_path)

    script.main(
        [
            "--scenario-profile",
            "v0_6",
            "--policy-slice",
            "v0_7f",
            "--depth-zero-diagnosis-only",
            "--output-dir",
            str(tmp_path),
        ]
    )

    diag_dir = tmp_path / script.V07F_OUTPUT_DIRNAME
    report = script.read_json(diag_dir / "mvp2e_v07f_depth_zero_harness_report.json")
    manifest = script.read_json(diag_dir / "mvp2e_v07f_gate_manifest.json")
    assert report["mvp2_closed"] is False
    assert report["phase_e_passed"] is False
    assert manifest["mvp2_closed"] is False
    assert manifest["phase_e_passed"] is False
    assert set(manifest["artifacts"]) == {
        "diagnostic_config",
        "depth_zero_harness_report",
        "trace_comparison_table",
        "gate_manifest",
    }


def test_v07f_cli_rejects_clean_before_deleting_source_evidence(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    sentinel = tmp_path / "must_survive.txt"
    sentinel.write_text("existing evidence", encoding="utf-8")

    with pytest.raises(ValueError, match="depth-zero-diagnosis-only.*--clean"):
        script.main(
            [
                "--scenario-profile",
                "v0_6",
                "--policy-slice",
                "v0_7f",
                "--depth-zero-diagnosis-only",
                "--clean",
                "--output-dir",
                str(tmp_path),
            ]
        )

    assert sentinel.exists()


def test_v07f_policy_slice_rejects_full_run(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    with pytest.raises(ValueError, match="policy-slice v0_7f is only valid"):
        script.main(
            [
                "--scenario-profile",
                "v0_6",
                "--policy-slice",
                "v0_7f",
                "--output-dir",
                str(tmp_path),
            ]
        )


def test_v07c_offline_action_authority_gate_detects_align_z_violation(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    residual_config = script.build_v07b_residual_servo_config(
        output_dir=tmp_path,
        parent_config_sha256="parent-v07a2-config-sha",
    )
    config = script.build_v07c_action_authority_config(
        output_dir=tmp_path,
        residual_servo_config=residual_config,
        selected_action_adapter_id="isaac_signed_xy_downward_servo_v0",
    )
    rows = _v07c_rows(script)
    predictions = [row["normalized_action"] for row in rows]
    bad_config = {**config, "align_z_authority": "base_plus_residual"}
    bad_config["authority_filter_config_sha256"] = script._sha256_payload_excluding(
        bad_config,
        "authority_filter_config_sha256",
    )

    gate = script.derive_v07c_offline_action_authority_gate(
        candidate_rows=rows,
        baseline_rows=rows,
        candidate_policy_artifact=_v07c_policy_artifact(script, bad_config, role="candidate_curated"),
        baseline_policy_artifact=_v07c_policy_artifact(script, bad_config, role="baseline_uncurated"),
        candidate_predictions=predictions,
        baseline_predictions=predictions,
        authority_config=bad_config,
    )

    assert gate["passed"] is False
    assert gate["failure_reason"] == "align_z_authority_violation"


def test_v07c_offline_action_authority_gate_rejects_adapter_mismatch(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    residual_config = script.build_v07b_residual_servo_config(
        output_dir=tmp_path,
        parent_config_sha256="parent-v07a2-config-sha",
    )
    config = script.build_v07c_action_authority_config(
        output_dir=tmp_path,
        residual_servo_config=residual_config,
        selected_action_adapter_id="isaac_signed_xy_downward_servo_v0",
    )
    rows = _v07c_rows(script)

    gate = script.derive_v07c_offline_action_authority_gate(
        candidate_rows=rows,
        baseline_rows=rows,
        candidate_policy_artifact=_v07c_policy_artifact(script, config, role="candidate_curated"),
        baseline_policy_artifact=_v07c_policy_artifact(
            script,
            config,
            role="baseline_uncurated",
            adapter_id="different_adapter",
        ),
        candidate_predictions=[row["normalized_action"] for row in rows],
        baseline_predictions=[row["normalized_action"] for row in rows],
        authority_config=config,
    )

    assert gate["passed"] is False
    assert gate["failure_reason"] == "selected_action_adapter_mismatch"


def test_v07c_offline_action_authority_gate_rejects_hash_mismatch(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    residual_config = script.build_v07b_residual_servo_config(
        output_dir=tmp_path,
        parent_config_sha256="parent-v07a2-config-sha",
    )
    config = script.build_v07c_action_authority_config(
        output_dir=tmp_path,
        residual_servo_config=residual_config,
        selected_action_adapter_id="isaac_signed_xy_downward_servo_v0",
    )
    rows = _v07c_rows(script)
    baseline = _v07c_policy_artifact(script, config, role="baseline_uncurated")
    baseline["authority_filter_config_sha256"] = "wrong"

    gate = script.derive_v07c_offline_action_authority_gate(
        candidate_rows=rows,
        baseline_rows=rows,
        candidate_policy_artifact=_v07c_policy_artifact(script, config, role="candidate_curated"),
        baseline_policy_artifact=baseline,
        candidate_predictions=[row["normalized_action"] for row in rows],
        baseline_predictions=[row["normalized_action"] for row in rows],
        authority_config=config,
    )

    assert gate["passed"] is False
    assert gate["failure_reason"] == "authority_filter_config_mismatch"


def test_v07c_policy_slice_rejects_full_run_and_parses_modes(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    args = script.parse_args(
        [
            "--scenario-profile",
            "v0_6",
            "--policy-slice",
            "v0_7c",
            "--offline-relabel-only",
            "--output-dir",
            str(tmp_path),
        ]
    )
    assert args.policy_slice == "v0_7c"
    assert args.offline_relabel_only is True

    with pytest.raises(ValueError, match="policy-slice v0_7c is only valid"):
        script.main(
            [
                "--scenario-profile",
                "v0_6",
                "--policy-slice",
                "v0_7c",
                "--output-dir",
                str(tmp_path / "rdf-v07c-full-run-test"),
            ]
        )


def test_v07c_expressibility_gate_blocks_without_offline_gates(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    gate = script.run_v07c_expressibility_sanity_runtime(
        output_dir=tmp_path,
        manifest={"manifest_sha256": "manifest"},
        device="cpu",
        headless=True,
        isaac_task="Isaac-Factory-PegInsert-Direct-v0",
        max_steps=150,
        action_scale=1.0,
    )

    assert gate["passed"] is False
    assert gate["runtime_backend"] == "isaac_runtime_not_started"
    assert gate["reason"] == "missing_passed_v0_7c_offline_gate"
    assert (
        tmp_path
        / script.V07C_CHILD_OUTPUT_DIRNAME
        / "expressibility_sanity_gate_v0_7c.json"
    ).exists()


def _minimal_v07d_parent_policy(
    script: Any,
    authority_config: dict[str, Any],
    *,
    role: str,
) -> dict[str, Any]:
    adapter_config = {
        "controller_version": "legacy_no_v06_controller",
        "xy_action_scale": 1.0,
        "xy_action_clip": 0.05,
        "z_action_scale": 32.0,
        "z_action_clip": 0.16,
        "stable_hold_depth_m": 0.03,
        "stable_hold_lateral_m": 0.006,
        "stable_hold_orientation_deg": 8.0,
        "stable_hold_action": [0.0, 0.0, -0.02, 0.0, 0.0, 0.0, 1.0],
    }
    parent = _v07c_policy_artifact(script, authority_config, role=role)
    parent.update(
        {
            "policy_slice": script.V07C_POLICY_SLICE_ID,
            "trainer_family": script.RESIDUAL_TRAINER_FAMILY,
            "selected_action_adapter_config": adapter_config,
            "selected_action_adapter_config_sha256": script._sha256_payload(adapter_config),
            "base_servo_config": {
                **script.WEAK_BASE_SERVO_CONFIG,
                "base_servo_id": script.V07B_BASE_SERVO_ID,
                "base_servo_source": "weak_base_servo_action_v0_wrapped_for_v0_7b",
                "closing_gate": False,
                "proof_authority": False,
            },
            "hyperparameters": {"ridge_lambda": 1e-3},
            "feature_schema": script.FEATURE_SCHEMA_V07A,
            "feature_schema_version": script.FEATURE_SCHEMA_V07A_VERSION,
            "weights": [[0.0] * len(script.ACTION_SCHEMA) for _ in script.FEATURE_SCHEMA_V07A],
            "bias": [0.0] * len(script.ACTION_SCHEMA),
        }
    )
    parent["base_servo_config_sha256"] = script._sha256_payload(parent["base_servo_config"])
    parent["policy_artifact_sha256"] = script._sha256_payload_excluding(parent, "policy_artifact_sha256")
    return parent


def _v07d_rows() -> list[dict[str, Any]]:
    return [
        {
            "trajectory_id": "fixture_align",
            "behavior_state_phase": "ALIGN",
            "phase": "APPROACH",
            "normalized_action": [0.0, 0.0, -0.09, 0.0, 0.0, 0.0, 0.0],
            "base_servo_action": [0.0, 0.0, -0.001, 0.0, 0.0, 0.0, 1.0],
        },
        {
            "trajectory_id": "fixture_descend",
            "behavior_state_phase": "DESCEND",
            "phase": "INSERT",
            "normalized_action": [0.0, 0.0, -0.07, 0.0, 0.0, 0.0, 0.0],
            "base_servo_action": [0.0, 0.0, -0.002, 0.0, 0.0, 0.0, 1.0],
        },
        {
            "trajectory_id": "fixture_hold",
            "behavior_state_phase": "HOLD",
            "phase": "SEAT",
            "normalized_action": [0.0, 0.0, 0.002, 0.0, 0.0, 0.0, 0.0],
            "base_servo_action": [0.0, 0.0, -0.0005, 0.0, 0.0, 0.0, 1.0],
        },
    ]


def _write_minimal_v07c_parent_slice_for_v07d(
    script: Any,
    output_dir: Path,
    *,
    include_harness_report: bool,
) -> dict[str, Any]:
    v07c_dir = output_dir / script.V07C_CHILD_OUTPUT_DIRNAME
    v07c_dir.mkdir(parents=True, exist_ok=True)
    residual_config = script.build_v07b_residual_servo_config(
        output_dir=output_dir / "v07b-source",
        parent_config_sha256="parent-v07a2-config-sha",
    )
    authority_config = script.build_v07c_action_authority_config(
        output_dir=v07c_dir,
        residual_servo_config=residual_config,
        selected_action_adapter_id="isaac_signed_xy_downward_servo_v0",
    )
    rows = _v07d_rows()
    script.write_v07c_residual_train_view_hdf5(
        path=v07c_dir / "candidate_curated_train_v0_7c.hdf5",
        rows=rows,
        view_id="candidate_curated_v0_7c_residual_action_authority",
        authority_config=authority_config,
    )
    script.write_v07c_residual_train_view_hdf5(
        path=v07c_dir / "baseline_uncurated_train_v0_7c.hdf5",
        rows=rows,
        view_id="baseline_uncurated_v0_7c_residual_action_authority",
        authority_config=authority_config,
    )
    candidate_policy = _minimal_v07d_parent_policy(script, authority_config, role="candidate_curated")
    baseline_policy = _minimal_v07d_parent_policy(script, authority_config, role="baseline_uncurated")
    script.write_json(v07c_dir / "candidate_policy_artifact_v0_7c.json", candidate_policy)
    script.write_json(v07c_dir / "baseline_policy_artifact_v0_7c.json", baseline_policy)
    manifest = {
        "schema_version": script.V07C_MANIFEST_SCHEMA_VERSION,
        "slice_id": script.V07C_SLICE_ID,
        "policy_slice": script.V07C_POLICY_SLICE_ID,
        "authority_filter_config": authority_config,
        "authority_filter_config_sha256": authority_config["authority_filter_config_sha256"],
        "failed_closed": False,
        "heldout_21000_21049_accessed": False,
        "mvp2_closed": False,
        "proof_authority": False,
    }
    manifest["v0_7c_residual_action_authority_manifest_sha256"] = script._sha256_payload_excluding(
        manifest,
        "v0_7c_residual_action_authority_manifest_sha256",
    )
    script.write_json(v07c_dir / "v0_7c_residual_action_authority_manifest.json", manifest)
    if include_harness_report:
        harness_dir = output_dir / script.MVP2E_HARNESS_OUTPUT_DIRNAME
        harness_dir.mkdir(parents=True, exist_ok=True)
        report = {
            "schema_version": script.MVP2E_HARNESS_REPORT_SCHEMA_VERSION,
            "policy_slice_under_test": script.V07C_POLICY_SLICE_ID,
            "root_cause_status": "classified",
            "primary_root_cause_class": "ACTION_AUTHORITY_POST_ADAPTER_Z_LEAK",
            "recommended_downstream_slice": "v0_7d_action_authority_post_adapter_z_gate",
            "protected_heldout_21000_21049_accessed": False,
            "calibration_opened": False,
            "heldout_opened": False,
            "mvp2_closed": False,
        }
        report["mvp2e_harness_report_sha256"] = script._sha256_payload_excluding(
            report,
            "mvp2e_harness_report_sha256",
        )
        script.write_json(harness_dir / "mvp2e_harness_report.json", report)
    return authority_config


def test_v07d_final_action_authority_config_is_hash_stable(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    config = script.build_v07d_final_action_authority_config(
        output_dir=tmp_path,
        inherited_authority_filter_config_sha256="v07c-authority-sha",
        selected_action_adapter_id="isaac_signed_xy_downward_servo_v0",
    )

    assert config["schema_version"] == script.V07D_FINAL_ACTION_AUTHORITY_CONFIG_SCHEMA_VERSION
    assert config["policy_slice"] == "v0_7d"
    assert config["final_post_adapter_authority_id"] == "final_post_adapter_z_authority_gate_v0_7d"
    assert config["stable_hold_authority"] == "env_native_success_mask"
    assert config["final_post_adapter_authority_config_sha256"] == script._sha256_payload_excluding(
        config,
        "final_post_adapter_authority_config_sha256",
    )
    assert (tmp_path / "v0_7d_final_action_authority_config.json").exists()
    script.validate_v07d_final_action_authority_config_contract(config)


def test_v07d_policy_artifacts_share_final_authority_and_preserve_parent_adapter(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    residual_config = script.build_v07b_residual_servo_config(
        output_dir=tmp_path / "v07b",
        parent_config_sha256="parent-v07a2-config-sha",
    )
    authority_config = script.build_v07c_action_authority_config(
        output_dir=tmp_path / "v07c",
        residual_servo_config=residual_config,
        selected_action_adapter_id="isaac_signed_xy_downward_servo_v0",
    )
    final_config = script.build_v07d_final_action_authority_config(
        output_dir=tmp_path,
        inherited_authority_filter_config_sha256=authority_config["authority_filter_config_sha256"],
        selected_action_adapter_id="isaac_signed_xy_downward_servo_v0",
    )
    parent = _minimal_v07d_parent_policy(script, authority_config, role="candidate_curated")
    parent_adapter_config = dict(parent["selected_action_adapter_config"])

    candidate = script.build_v07d_policy_artifact_payload(
        base_policy_artifact=parent,
        final_authority_config=final_config,
        dataset_view_role="candidate_curated",
    )
    baseline = script.build_v07d_policy_artifact_payload(
        base_policy_artifact=_minimal_v07d_parent_policy(script, authority_config, role="baseline_uncurated"),
        final_authority_config=final_config,
        dataset_view_role="baseline_uncurated",
    )

    assert candidate["policy_slice"] == "v0_7d"
    assert candidate["parent_policy_slice"] == "v0_7c"
    assert candidate["selected_action_adapter_config"] == parent_adapter_config
    assert "stable_hold_authority" not in candidate["selected_action_adapter_config"]
    assert candidate["stable_hold_authority"] == "env_native_success_mask"
    assert candidate["final_post_adapter_authority_config_sha256"] == baseline[
        "final_post_adapter_authority_config_sha256"
    ]
    assert candidate["parent_selected_action_adapter_config_sha256"] == candidate[
        "effective_v07d_adapter_view_sha256"
    ]


def test_v07d_policy_artifact_rejects_parent_authority_hash_mismatch(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    residual_config = script.build_v07b_residual_servo_config(
        output_dir=tmp_path / "v07b",
        parent_config_sha256="parent-v07a2-config-sha",
    )
    authority_config = script.build_v07c_action_authority_config(
        output_dir=tmp_path / "v07c",
        residual_servo_config=residual_config,
        selected_action_adapter_id="isaac_signed_xy_downward_servo_v0",
    )
    final_config = script.build_v07d_final_action_authority_config(
        output_dir=tmp_path,
        inherited_authority_filter_config_sha256=authority_config["authority_filter_config_sha256"],
        selected_action_adapter_id="isaac_signed_xy_downward_servo_v0",
    )
    stale_parent = _minimal_v07d_parent_policy(script, authority_config, role="candidate_curated")
    stale_parent["authority_filter_config_sha256"] = "stale-v07c-authority-sha"

    with pytest.raises(ValueError, match="v0_7d_parent_authority_filter_config_mismatch"):
        script.build_v07d_policy_artifact_payload(
            base_policy_artifact=stale_parent,
            final_authority_config=final_config,
            dataset_view_role="candidate_curated",
        )


def test_v07d_policy_artifact_requires_parent_selected_adapter_config(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    residual_config = script.build_v07b_residual_servo_config(
        output_dir=tmp_path / "v07b",
        parent_config_sha256="parent-v07a2-config-sha",
    )
    authority_config = script.build_v07c_action_authority_config(
        output_dir=tmp_path / "v07c",
        residual_servo_config=residual_config,
        selected_action_adapter_id="isaac_signed_xy_downward_servo_v0",
    )
    final_config = script.build_v07d_final_action_authority_config(
        output_dir=tmp_path,
        inherited_authority_filter_config_sha256=authority_config["authority_filter_config_sha256"],
        selected_action_adapter_id="isaac_signed_xy_downward_servo_v0",
    )
    parent = _minimal_v07d_parent_policy(script, authority_config, role="candidate_curated")
    del parent["selected_action_adapter_config"]

    with pytest.raises(ValueError, match="v0_7d_parent_selected_action_adapter_config_missing"):
        script.build_v07d_policy_artifact_payload(
            base_policy_artifact=parent,
            final_authority_config=final_config,
            dataset_view_role="candidate_curated",
        )


def test_v07d_policy_artifact_rejects_parent_selected_adapter_hash_mismatch(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    residual_config = script.build_v07b_residual_servo_config(
        output_dir=tmp_path / "v07b",
        parent_config_sha256="parent-v07a2-config-sha",
    )
    authority_config = script.build_v07c_action_authority_config(
        output_dir=tmp_path / "v07c",
        residual_servo_config=residual_config,
        selected_action_adapter_id="isaac_signed_xy_downward_servo_v0",
    )
    final_config = script.build_v07d_final_action_authority_config(
        output_dir=tmp_path,
        inherited_authority_filter_config_sha256=authority_config["authority_filter_config_sha256"],
        selected_action_adapter_id="isaac_signed_xy_downward_servo_v0",
    )
    parent = _minimal_v07d_parent_policy(script, authority_config, role="candidate_curated")
    parent["selected_action_adapter_config_sha256"] = "stale-selected-adapter-config-sha"

    with pytest.raises(ValueError, match="v0_7d_parent_selected_action_adapter_config_hash_mismatch"):
        script.build_v07d_policy_artifact_payload(
            base_policy_artifact=parent,
            final_authority_config=final_config,
            dataset_view_role="candidate_curated",
        )


def test_v07d_builder_requires_classified_v07c_harness_report(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_minimal_v07c_parent_slice_for_v07d(
        script,
        tmp_path,
        include_harness_report=False,
    )

    with pytest.raises(ValueError, match="missing_v0_7c_classified_harness_report"):
        script.build_v07d_action_authority_post_adapter_z_gate_slice(output_dir=tmp_path)


def test_v07d_train_view_records_child_schema_and_final_authority(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    residual_config = script.build_v07b_residual_servo_config(
        output_dir=tmp_path / "v07b",
        parent_config_sha256="parent-v07a2-config-sha",
    )
    authority_config = script.build_v07c_action_authority_config(
        output_dir=tmp_path / "v07c",
        residual_servo_config=residual_config,
        selected_action_adapter_id="isaac_signed_xy_downward_servo_v0",
    )
    final_config = script.build_v07d_final_action_authority_config(
        output_dir=tmp_path,
        inherited_authority_filter_config_sha256=authority_config["authority_filter_config_sha256"],
        selected_action_adapter_id="isaac_signed_xy_downward_servo_v0",
    )
    path = tmp_path / "candidate_curated_train_v0_7d.hdf5"

    view = script.write_v07c_residual_train_view_hdf5(
        path=path,
        rows=_v07d_rows(),
        view_id="candidate_curated_v0_7d_action_authority_post_adapter_z_gate",
        authority_config=authority_config,
        schema_version=script.V07D_MANIFEST_SCHEMA_VERSION,
        extra_hdf5_attrs={
            "policy_slice": "v0_7d",
            "final_post_adapter_authority_id": "final_post_adapter_z_authority_gate_v0_7d",
            "final_post_adapter_authority_config_sha256": final_config[
                "final_post_adapter_authority_config_sha256"
            ],
            "stable_hold_authority": "env_native_success_mask",
        },
        extra_view_fields={
            "policy_slice": "v0_7d",
            "final_post_adapter_authority_id": "final_post_adapter_z_authority_gate_v0_7d",
            "final_post_adapter_authority_config_sha256": final_config[
                "final_post_adapter_authority_config_sha256"
            ],
            "stable_hold_authority": "env_native_success_mask",
        },
    )

    assert view["schema_version"] == script.V07D_MANIFEST_SCHEMA_VERSION
    assert view["policy_slice"] == "v0_7d"
    assert view["final_post_adapter_authority_config_sha256"] == final_config[
        "final_post_adapter_authority_config_sha256"
    ]
    with h5py.File(path, "r") as h5:
        assert h5.attrs["schema_version"] == script.V07D_MANIFEST_SCHEMA_VERSION
        assert h5.attrs["policy_slice"] == "v0_7d"
        assert h5.attrs["final_post_adapter_authority_id"] == "final_post_adapter_z_authority_gate_v0_7d"


def test_v07d_offline_gate_passes_when_final_align_z_is_zero(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    residual_config = script.build_v07b_residual_servo_config(
        output_dir=tmp_path / "v07b",
        parent_config_sha256="parent-v07a2-config-sha",
    )
    authority_config = script.build_v07c_action_authority_config(
        output_dir=tmp_path / "v07c",
        residual_servo_config=residual_config,
        selected_action_adapter_id="isaac_signed_xy_downward_servo_v0",
    )
    final_config = script.build_v07d_final_action_authority_config(
        output_dir=tmp_path,
        inherited_authority_filter_config_sha256=authority_config["authority_filter_config_sha256"],
        selected_action_adapter_id="isaac_signed_xy_downward_servo_v0",
    )
    candidate = script.build_v07d_policy_artifact_payload(
        base_policy_artifact=_minimal_v07d_parent_policy(script, authority_config, role="candidate_curated"),
        final_authority_config=final_config,
        dataset_view_role="candidate_curated",
    )
    baseline = script.build_v07d_policy_artifact_payload(
        base_policy_artifact=_minimal_v07d_parent_policy(script, authority_config, role="baseline_uncurated"),
        final_authority_config=final_config,
        dataset_view_role="baseline_uncurated",
    )
    rows = _v07d_rows()

    gate = script.derive_v07d_offline_final_action_authority_gate(
        candidate_rows=rows,
        baseline_rows=rows,
        candidate_policy_artifact=candidate,
        baseline_policy_artifact=baseline,
        final_authority_config=final_config,
        candidate_predictions=[row["normalized_action"] for row in rows],
        baseline_predictions=[row["normalized_action"] for row in rows],
    )

    assert gate["passed"] is True
    assert gate["phase_e_candidate_expressibility_unblocked"] is True
    assert gate["future_ab_ready"] is False
    assert gate["candidate_align_final_z_violation_count"] == 0
    assert gate["baseline_align_final_z_violation_count"] == 0
    assert gate["stable_hold_authority"] == "env_native_success_mask"


def test_v07d_offline_gate_rejects_missing_selected_adapter_config(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    residual_config = script.build_v07b_residual_servo_config(
        output_dir=tmp_path / "v07b",
        parent_config_sha256="parent-v07a2-config-sha",
    )
    authority_config = script.build_v07c_action_authority_config(
        output_dir=tmp_path / "v07c",
        residual_servo_config=residual_config,
        selected_action_adapter_id="isaac_signed_xy_downward_servo_v0",
    )
    final_config = script.build_v07d_final_action_authority_config(
        output_dir=tmp_path,
        inherited_authority_filter_config_sha256=authority_config["authority_filter_config_sha256"],
        selected_action_adapter_id="isaac_signed_xy_downward_servo_v0",
    )
    candidate = script.build_v07d_policy_artifact_payload(
        base_policy_artifact=_minimal_v07d_parent_policy(script, authority_config, role="candidate_curated"),
        final_authority_config=final_config,
        dataset_view_role="candidate_curated",
    )
    baseline = script.build_v07d_policy_artifact_payload(
        base_policy_artifact=_minimal_v07d_parent_policy(script, authority_config, role="baseline_uncurated"),
        final_authority_config=final_config,
        dataset_view_role="baseline_uncurated",
    )
    del candidate["selected_action_adapter_config"]

    gate = script.derive_v07d_offline_final_action_authority_gate(
        candidate_rows=_v07d_rows(),
        baseline_rows=_v07d_rows(),
        candidate_policy_artifact=candidate,
        baseline_policy_artifact=baseline,
        final_authority_config=final_config,
        candidate_predictions=[row["normalized_action"] for row in _v07d_rows()],
        baseline_predictions=[row["normalized_action"] for row in _v07d_rows()],
    )

    assert gate["passed"] is False
    assert gate["failure_reason"] == "candidate_selected_action_adapter_config_missing"
    assert gate["phase_e_candidate_expressibility_unblocked"] is False
    assert gate["future_ab_ready"] is False


def test_v07d_offline_adapter_simulation_rejects_missing_selected_adapter_config(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    residual_config = script.build_v07b_residual_servo_config(
        output_dir=tmp_path / "v07b",
        parent_config_sha256="parent-v07a2-config-sha",
    )
    authority_config = script.build_v07c_action_authority_config(
        output_dir=tmp_path / "v07c",
        residual_servo_config=residual_config,
        selected_action_adapter_id="isaac_signed_xy_downward_servo_v0",
    )
    final_config = script.build_v07d_final_action_authority_config(
        output_dir=tmp_path,
        inherited_authority_filter_config_sha256=authority_config["authority_filter_config_sha256"],
        selected_action_adapter_id="isaac_signed_xy_downward_servo_v0",
    )
    policy = script.build_v07d_policy_artifact_payload(
        base_policy_artifact=_minimal_v07d_parent_policy(script, authority_config, role="candidate_curated"),
        final_authority_config=final_config,
        dataset_view_role="candidate_curated",
    )
    del policy["selected_action_adapter_config"]

    with pytest.raises(ValueError, match="v0_7d_selected_action_adapter_config_missing"):
        script._simulate_selected_action_adapter_for_offline_gate(
            policy_artifact=policy,
            raw_action=script.np.array([0.0, 0.0, -0.001, 0.0, 0.0, 0.0, 1.0], dtype=script.np.float64),
        )


def test_v07d_offline_gate_requires_env_native_stable_hold_authority(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    final_config = {
        "schema_version": "rdf_mvp2e_v07d_final_action_authority_config_v0.1.0",
        "policy_slice": "v0_7d",
        "slice_id": "mvp2e_v07d_action_authority_post_adapter_z_gate",
        "final_post_adapter_authority_id": "final_post_adapter_z_authority_gate_v0_7d",
        "inherited_authority_filter_id": "frozen_residual_action_authority_gate_v0_7c",
        "inherited_authority_filter_config_sha256": "v07c-authority-sha",
        "selected_action_adapter_id": "isaac_signed_xy_downward_servo_v0",
        "stable_hold_authority": "geometry_thresholds",
        "align_final_z_authority": "zero_after_adapter_until_z_motion_allowed",
        "heldout_21000_21049_accessed": False,
        "candidate_specific": False,
        "baseline_specific": False,
    }
    final_config["final_post_adapter_authority_config_sha256"] = script._sha256_payload_excluding(
        final_config,
        "final_post_adapter_authority_config_sha256",
    )

    with pytest.raises(ValueError, match="v0_7d_stable_hold_authority_mismatch"):
        script.validate_v07d_final_action_authority_config_contract(final_config)


def test_v07d_cli_mode_requires_v06_profile_and_blocks_full_run(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    args = script.parse_args(
        [
            "--scenario-profile",
            "v0_6",
            "--policy-slice",
            "v0_7d",
            "--offline-relabel-only",
            "--output-dir",
            str(tmp_path),
        ]
    )
    assert args.policy_slice == "v0_7d"
    assert args.offline_relabel_only is True

    with pytest.raises(ValueError, match="policy-slice v0_7d is only valid"):
        script.main(
            [
                "--scenario-profile",
                "v0_6",
                "--policy-slice",
                "v0_7d",
                "--output-dir",
                str(tmp_path / "rdf-v07d-full-run-test"),
            ]
        )


def test_v07d_cli_blocks_harness_only_shared_parent_report_overwrite(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    with pytest.raises(ValueError, match="v0_7d harness diagnostics must not overwrite classified v0_7c parent report"):
        script.main(
            [
                "--scenario-profile",
                "v0_6",
                "--policy-slice",
                "v0_7d",
                "--harness-gated-closure-only",
                "--output-dir",
                str(tmp_path),
            ]
        )


def test_mvp2e_h12_v07d_reads_final_authority_not_selected_adapter_geometry(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    final_config = script.build_v07d_final_action_authority_config(
        output_dir=tmp_path,
        inherited_authority_filter_config_sha256="v07c-authority-sha",
        selected_action_adapter_id="isaac_signed_xy_downward_servo_v0",
    )
    child_dir = tmp_path / script.V07D_CHILD_OUTPUT_DIRNAME
    child_dir.mkdir(parents=True, exist_ok=True)
    script.write_json(
        child_dir / "candidate_policy_artifact_v0_7d.json",
        {
            "policy_slice": "v0_7d",
            "selected_action_adapter_id": "isaac_signed_xy_downward_servo_v0",
            "selected_action_adapter_config": {
                "stable_hold_depth_m": 0.03,
                "stable_hold_lateral_m": 0.006,
                "stable_hold_orientation_deg": 8.0,
            },
            "stable_hold_authority": "env_native_success_mask",
            "final_post_adapter_authority_config": final_config,
            "final_post_adapter_authority_config_sha256": final_config[
                "final_post_adapter_authority_config_sha256"
            ],
        },
    )
    config = script.build_mvp2e_harness_config(output_dir=tmp_path, policy_slice_under_test="v0_7d")

    report = script.build_mvp2e_harness_report(output_dir=tmp_path, config=config)

    h12 = report["harnesses"]["H12"]
    assert h12["status"] == "passed"
    assert h12["reason"] == "stable_hold_uses_env_native_success_mask_authority"
    assert h12["evidence"]["stable_hold_authority"] == "env_native_success_mask"
    assert "candidate_policy_artifact_v0_7d.json" in h12["evidence"]["path"]


def _minimal_v07e_parent_policy(
    script: Any,
    output_dir: Path,
    *,
    role: str,
) -> dict[str, Any]:
    authority_config = _write_minimal_v07c_parent_slice_for_v07d(
        script,
        output_dir,
        include_harness_report=True,
    )
    final_config = script.build_v07d_final_action_authority_config(
        output_dir=output_dir / "v07d-parent",
        inherited_authority_filter_config_sha256=authority_config["authority_filter_config_sha256"],
        selected_action_adapter_id="isaac_signed_xy_downward_servo_v0",
    )
    return script.build_v07d_policy_artifact_payload(
        base_policy_artifact=_minimal_v07d_parent_policy(script, authority_config, role=role),
        final_authority_config=final_config,
        dataset_view_role=role,
    )


def _v07e_counterfactual_windows() -> list[dict[str, Any]]:
    return [
        {
            "seed": 19003,
            "expert_max_consecutive_z_descent_steps": 32,
            "v0_7d_policy_max_consecutive_z_descent_steps": 0,
            "v0_7e_counterfactual_max_consecutive_z_descent_steps": 32,
            "protected_heldout_seed": False,
        },
        {
            "seed": 19012,
            "expert_max_consecutive_z_descent_steps": 43,
            "v0_7d_policy_max_consecutive_z_descent_steps": 4,
            "v0_7e_counterfactual_max_consecutive_z_descent_steps": 30,
            "protected_heldout_seed": False,
        },
        {
            "seed": 19030,
            "expert_max_consecutive_z_descent_steps": 28,
            "v0_7d_policy_max_consecutive_z_descent_steps": 4,
            "v0_7e_counterfactual_max_consecutive_z_descent_steps": 28,
            "protected_heldout_seed": False,
        },
        {
            "seed": 19119,
            "expert_max_consecutive_z_descent_steps": 38,
            "v0_7d_policy_max_consecutive_z_descent_steps": 2,
            "v0_7e_counterfactual_max_consecutive_z_descent_steps": 27,
            "protected_heldout_seed": False,
        },
        {
            "seed": 19129,
            "expert_max_consecutive_z_descent_steps": 32,
            "v0_7d_policy_max_consecutive_z_descent_steps": 3,
            "v0_7e_counterfactual_max_consecutive_z_descent_steps": 29,
            "protected_heldout_seed": False,
        },
    ]


def test_v07e_hysteresis_config_is_hash_stable_and_shared(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    config = script.build_v07e_hysteresis_authority_config(
        output_dir=tmp_path,
        parent_final_post_adapter_authority_config_sha256="parent-final-authority-sha",
    )

    assert config["schema_version"] == script.V07E_SHARED_HYSTERESIS_AUTHORITY_CONFIG_SCHEMA_VERSION
    assert config["policy_slice"] == "v0_7e"
    assert config["parent_policy_slice"] == "v0_7d"
    assert config["shared_hysteresis_authority_id"] == "shared_stateful_hysteresis_authority_v0_7e"
    assert config["z_window_hold_steps"] == 28
    assert config["same_hysteresis_config_as_peer"] is True
    assert config["candidate_specific"] is False
    assert config["baseline_specific"] is False
    assert config["heldout_21000_21049_accessed"] is False
    assert config["shared_hysteresis_authority_config_sha256"] == script._sha256_payload_excluding(
        config,
        "shared_hysteresis_authority_config_sha256",
    )
    assert (tmp_path / "v0_7e_hysteresis_authority_config.json").exists()
    script.validate_v07e_hysteresis_authority_config_contract(config)


def test_v07e_policy_artifacts_inherit_v07d_and_share_hysteresis(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    parent_candidate = _minimal_v07e_parent_policy(script, tmp_path / "candidate-parent", role="candidate_curated")
    parent_baseline = _minimal_v07e_parent_policy(script, tmp_path / "baseline-parent", role="baseline_uncurated")
    config = script.build_v07e_hysteresis_authority_config(
        output_dir=tmp_path,
        parent_final_post_adapter_authority_config_sha256=parent_candidate[
            "final_post_adapter_authority_config_sha256"
        ],
    )

    candidate = script.build_v07e_policy_artifact_payload(
        base_policy_artifact=parent_candidate,
        hysteresis_config=config,
        dataset_view_role="candidate_curated",
    )
    baseline = script.build_v07e_policy_artifact_payload(
        base_policy_artifact=parent_baseline,
        hysteresis_config=config,
        dataset_view_role="baseline_uncurated",
    )

    assert candidate["policy_slice"] == "v0_7e"
    assert candidate["parent_policy_slice"] == "v0_7d"
    assert candidate["selected_action_adapter_config"] == parent_candidate["selected_action_adapter_config"]
    assert candidate["final_post_adapter_authority_config_sha256"] == parent_candidate[
        "final_post_adapter_authority_config_sha256"
    ]
    assert candidate["shared_hysteresis_authority_config_sha256"] == baseline[
        "shared_hysteresis_authority_config_sha256"
    ]
    assert candidate["same_hysteresis_config_as_peer"] is True
    assert candidate["heldout_21000_21049_accessed"] is False


def test_v07e_offline_hysteresis_parity_gate_uses_train_side_counterfactual_windows(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    config = script.build_v07e_hysteresis_authority_config(
        output_dir=tmp_path,
        parent_final_post_adapter_authority_config_sha256="parent-final-authority-sha",
    )

    gate = script.derive_v07e_offline_hysteresis_parity_gate(
        counterfactual_windows=_v07e_counterfactual_windows(),
        hysteresis_config=config,
    )

    assert gate["passed"] is True
    assert gate["policy_slice"] == "v0_7e"
    assert gate["min_passing_counterfactual_windows"] == 3
    assert gate["passing_counterfactual_windows"] >= 3
    assert gate["heldout_21000_21049_accessed"] is False
    assert gate["phase_e_candidate_expressibility_unblocked"] is False
    assert gate["proof_authority"] is False


def test_v07e_offline_hysteresis_parity_gate_fails_closed_on_protected_heldout_seed(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    config = script.build_v07e_hysteresis_authority_config(
        output_dir=tmp_path,
        parent_final_post_adapter_authority_config_sha256="parent-final-authority-sha",
    )
    windows = _v07e_counterfactual_windows()
    windows[0] = {**windows[0], "seed": 21000, "protected_heldout_seed": True}

    gate = script.derive_v07e_offline_hysteresis_parity_gate(
        counterfactual_windows=windows,
        hysteresis_config=config,
    )

    assert gate["passed"] is False
    assert gate["failure_reason"] == "protected_heldout_seed_accessed"
    assert gate["heldout_21000_21049_accessed"] is True
    assert gate["phase_e_candidate_expressibility_unblocked"] is False


def test_v07e_attribution_preservation_gate_requires_candidate_baseline_delta(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    config = script.build_v07e_hysteresis_authority_config(
        output_dir=tmp_path,
        parent_final_post_adapter_authority_config_sha256="parent-final-authority-sha",
    )

    gate = script.derive_v07e_attribution_preservation_gate(
        candidate_final_actions=[
            [0.01, 0.0, -0.16, 0.0, 0.0, 0.0, 1.0],
            [0.02, 0.0, -0.16, 0.0, 0.0, 0.0, 1.0],
        ],
        baseline_final_actions=[
            [0.0, 0.0, -0.12, 0.0, 0.0, 0.0, 1.0],
            [0.0, 0.0, -0.12, 0.0, 0.0, 0.0, 1.0],
        ],
        hysteresis_config=config,
    )

    assert gate["passed"] is True
    assert gate["same_hysteresis_config_for_baseline_and_candidate"] is True
    assert gate["candidate_baseline_final_action_delta_l2_mean"] > 0.0
    assert gate["phase_e_candidate_expressibility_unblocked"] is False
    assert gate["future_ab_ready"] is False


def test_v07e_final_authority_regression_gate_requires_all_offline_gates(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    config = script.build_v07e_hysteresis_authority_config(
        output_dir=tmp_path,
        parent_final_post_adapter_authority_config_sha256="parent-final-authority-sha",
    )
    parity_gate = script.derive_v07e_offline_hysteresis_parity_gate(
        counterfactual_windows=_v07e_counterfactual_windows(),
        hysteresis_config=config,
    )
    attribution_gate = script.derive_v07e_attribution_preservation_gate(
        candidate_final_actions=[[0.01, 0.0, -0.16, 0.0, 0.0, 0.0, 1.0]],
        baseline_final_actions=[[0.0, 0.0, -0.12, 0.0, 0.0, 0.0, 1.0]],
        hysteresis_config=config,
    )

    gate = script.derive_v07e_final_action_authority_regression_gate(
        final_align_rows=[
            {"behavior_state_phase": "ALIGN", "final_post_adapter_action": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0]}
        ],
        hysteresis_gate=parity_gate,
        attribution_gate=attribution_gate,
        hysteresis_config=config,
    )

    assert gate["passed"] is True
    assert gate["all_offline_gates_passed"] is True
    assert gate["align_final_z_violation_count"] == 0
    assert gate["phase_e_candidate_expressibility_unblocked"] is True
    assert gate["future_ab_ready"] is False


def test_v07e_cli_guard_and_expressibility_fail_closed_without_offline_gates(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    args = script.parse_args(
        [
            "--scenario-profile",
            "v0_6",
            "--policy-slice",
            "v0_7e",
            "--offline-relabel-only",
            "--output-dir",
            str(tmp_path),
        ]
    )
    assert args.policy_slice == "v0_7e"
    assert args.offline_relabel_only is True

    with pytest.raises(ValueError, match="policy-slice v0_7e is only valid"):
        script.main(
            [
                "--scenario-profile",
                "v0_6",
                "--policy-slice",
                "v0_7e",
                "--output-dir",
                str(tmp_path / "rdf-v07e-full-run-test"),
            ]
        )

    gate = script.run_v07e_expressibility_sanity_runtime(
        output_dir=tmp_path,
        backend=script.DeterministicTrainingCalibrationBackend(),
    )

    assert gate["passed"] is False
    assert gate["reason"] == "missing_passed_v0_7e_offline_gates"
    assert gate["phase_e_candidate_expressibility_unblocked"] is False
    assert gate["heldout_21000_21049_accessed"] is False
    assert (tmp_path / script.V07E_CHILD_OUTPUT_DIRNAME / "expressibility_sanity_gate_v0_7e.json").exists()


def _write_v07e_phase_e_ready_artifacts(script: Any, output_dir: Path) -> dict[str, Any]:
    manifest = script.build_mvp2c_scenario_manifest(output_dir=output_dir, scenario_profile="v0_6")
    script.write_json(
        output_dir / "train_generation_runtime_gate.json",
        {
            "passed": True,
            "runtime_backend": "isaac_runtime",
            "actual_train_generation_evidence": True,
            "training_trajectory_source": "isaac_runtime_scripted_expert_rollout",
            "generated_rollout_count": script.V06_TRAIN_GATE_ATTEMPT_COUNT,
            "generated_success_count": script.V06_TRAIN_GATE_SUCCESS_MINIMUM,
            "required_success_count": script.V06_TRAIN_GATE_SUCCESS_MINIMUM,
            "success_trace_cap": script.V06_TRAIN_GATE_ATTEMPT_COUNT,
            "generated_success_trace_paths": [
                f"/tmp/train_generation_probe_{index:04d}_train_success_{seed}_isaac_trace.json"
                for index, seed in enumerate([19003, 19012, 19129, 19021, 19030])
            ],
        },
    )
    child_dir = output_dir / script.V07E_CHILD_OUTPUT_DIRNAME
    child_dir.mkdir(parents=True, exist_ok=True)
    parent_candidate = _minimal_v07e_parent_policy(script, output_dir / "candidate-parent", role="candidate_curated")
    config = script.build_v07e_hysteresis_authority_config(
        output_dir=child_dir,
        parent_final_post_adapter_authority_config_sha256=parent_candidate[
            "final_post_adapter_authority_config_sha256"
        ],
    )
    policy = script.build_v07e_policy_artifact_payload(
        base_policy_artifact=parent_candidate,
        hysteresis_config=config,
        dataset_view_role="candidate_curated",
    )
    script.write_json(child_dir / "candidate_policy_artifact_v0_7e.json", policy)
    parity_gate = script.derive_v07e_offline_hysteresis_parity_gate(
        counterfactual_windows=_v07e_counterfactual_windows(),
        hysteresis_config=config,
    )
    attribution_gate = script.derive_v07e_attribution_preservation_gate(
        candidate_final_actions=[
            [0.02, 0.0, -0.16, 0.0, 0.0, 0.0, 1.0],
            [0.01, 0.0, -0.12, 0.0, 0.0, 0.0, 1.0],
        ],
        baseline_final_actions=[
            [0.0, 0.0, -0.08, 0.0, 0.0, 0.0, 1.0],
            [0.0, 0.0, -0.08, 0.0, 0.0, 0.0, 1.0],
        ],
        hysteresis_config=config,
    )
    final_gate = script.derive_v07e_final_action_authority_regression_gate(
        final_align_rows=[
            {"behavior_state_phase": "ALIGN", "final_post_adapter_action": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0]}
        ],
        hysteresis_gate=parity_gate,
        attribution_gate=attribution_gate,
        hysteresis_config=config,
    )
    assert parity_gate["passed"] is True
    assert attribution_gate["passed"] is True
    assert final_gate["passed"] is True
    script.write_json(child_dir / "offline_hysteresis_parity_gate_v0_7e.json", parity_gate)
    script.write_json(child_dir / "attribution_preservation_gate_v0_7e.json", attribution_gate)
    script.write_json(child_dir / "final_action_authority_regression_gate_v0_7e.json", final_gate)
    return manifest


def test_v07e_expressibility_uses_backend_after_offline_gates_pass(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    manifest = _write_v07e_phase_e_ready_artifacts(script, tmp_path)
    calls: list[dict[str, Any]] = []

    class FakeBackend:
        runtime_backend = "isaac_runtime"

        def run_single_policy_probe(self, **kwargs: Any) -> Any:
            calls.append(kwargs)
            output_dir = kwargs["output_dir"]
            output_dir.mkdir(parents=True, exist_ok=True)
            trace_paths = []
            rollouts = []
            for index, scenario in enumerate(kwargs["manifest"]["scenarios"]):
                trace_path = output_dir / f"v0_7e_fake_trace_{index}.json"
                script.write_json(trace_path, {"scenario_id": scenario["scenario_id"], "seed": scenario["seed"]})
                trace_paths.append(str(trace_path))
                rollouts.append(
                    {
                        "rollout_id": f"v0_7e_fake_{index}",
                        "success": index < 2,
                        "env_native_rollout_success": index < 2,
                    }
                )
            return script.BackendResult(
                runtime_backend="isaac_runtime",
                proof_runtime="dedicated_isaac_connector_insertion_evaluator",
                runtime_gate={"passed": True, "runtime_backend": "isaac_runtime"},
                baseline_rollouts=rollouts,
                candidate_rollouts=[],
                baseline_trace_paths=trace_paths,
                candidate_trace_paths=[],
                runtime_metadata={"runtime_backend": "isaac_runtime"},
            )

    gate = script.run_v07e_expressibility_sanity_runtime(
        output_dir=tmp_path,
        manifest=manifest,
        backend=FakeBackend(),
    )

    assert calls, "v0_7e must run the Isaac evaluator backend after offline gates pass"
    call = calls[0]
    assert call["role"] == "v0_7e_expressibility_sanity"
    assert call["policy_artifact"]["policy_slice"] == "v0_7e"
    assert call["manifest"]["heldout_21000_21049_accessed"] is False
    assert [row["seed"] for row in call["manifest"]["scenarios"]] == [19003, 19012, 19129, 19021, 19030]
    assert gate["passed"] is True
    assert gate["runtime_backend"] == "isaac_runtime"
    assert gate["success_count"] == 2
    assert gate["shared_hysteresis_authority_id"] == "shared_stateful_hysteresis_authority_v0_7e"
    assert gate["phase_e_candidate_expressibility_unblocked"] is True
    assert gate["future_ab_ready"] is False
    assert gate["mvp2_closed"] is False
    assert gate["policy_uplift_proven"] is False
    assert gate["heldout_21000_21049_accessed"] is False
    assert (tmp_path / script.V07E_CHILD_OUTPUT_DIRNAME / "expressibility_sanity_gate_v0_7e.json").exists()


def test_v07e_builds_child_slice_without_mutating_v07d(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_minimal_v07c_parent_slice_for_v07d(script, tmp_path, include_harness_report=True)
    v07d_manifest = script.build_v07d_action_authority_post_adapter_z_gate_slice(output_dir=tmp_path)
    v07d_manifest_path = tmp_path / script.V07D_CHILD_OUTPUT_DIRNAME / "v0_7d_action_authority_manifest.json"
    v07d_before_sha = script._sha256_file(v07d_manifest_path)

    manifest = script.build_v07e_shared_hysteresis_parity_repair_slice(
        output_dir=tmp_path,
        counterfactual_windows=_v07e_counterfactual_windows(),
    )

    child_dir = tmp_path / script.V07E_CHILD_OUTPUT_DIRNAME
    assert manifest["schema_version"] == script.V07E_MANIFEST_SCHEMA_VERSION
    assert manifest["policy_slice"] == "v0_7e"
    assert manifest["parent_policy_slice"] == "v0_7d"
    assert manifest["v0_7d_action_authority_manifest_sha256"] == v07d_manifest[
        "v0_7d_action_authority_manifest_sha256"
    ]
    assert manifest["offline_hysteresis_parity_gate_v0_7e"]["passed"] is True
    assert manifest["attribution_preservation_gate_v0_7e"]["passed"] is False
    assert manifest["final_action_authority_regression_gate_v0_7e"]["passed"] is False
    assert manifest["failed_closed"] is True
    assert manifest["phase_e_candidate_expressibility_unblocked"] is False
    assert manifest["future_ab_ready"] is False
    assert manifest["mvp2_closed"] is False
    assert manifest["policy_uplift_proven"] is False
    assert manifest["heldout_21000_21049_accessed"] is False
    assert (child_dir / "v0_7e_hysteresis_authority_config.json").exists()
    assert (child_dir / "candidate_policy_artifact_v0_7e.json").exists()
    assert (child_dir / "baseline_policy_artifact_v0_7e.json").exists()
    assert (child_dir / "offline_hysteresis_parity_gate_v0_7e.json").exists()
    assert (child_dir / "attribution_preservation_gate_v0_7e.json").exists()
    assert (child_dir / "final_action_authority_regression_gate_v0_7e.json").exists()
    assert (child_dir / "v0_7e_shared_hysteresis_parity_manifest.json").exists()
    assert script._sha256_file(v07d_manifest_path) == v07d_before_sha


def test_v07e_offline_relabel_cli_builds_child_slice(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_minimal_v07c_parent_slice_for_v07d(script, tmp_path, include_harness_report=True)
    script.build_v07d_action_authority_post_adapter_z_gate_slice(output_dir=tmp_path)

    result = script.main(
        [
            "--scenario-profile",
            "v0_6",
            "--policy-slice",
            "v0_7e",
            "--offline-relabel-only",
            "--output-dir",
            str(tmp_path),
        ]
    )

    child_dir = tmp_path / script.V07E_CHILD_OUTPUT_DIRNAME
    evidence_manifest = script.read_json(tmp_path / "evidence_manifest.json")
    assert result == 0
    assert (child_dir / "v0_7e_shared_hysteresis_parity_manifest.json").exists()
    assert evidence_manifest["policy_slice"] == "v0_7e"
    assert evidence_manifest["mvp2_closed"] is False
    assert evidence_manifest["heldout_21000_21049_accessed"] is False
    assert evidence_manifest["v0_7e_shared_hysteresis_parity_manifest"] == (
        f"{script.V07E_CHILD_OUTPUT_DIRNAME}/v0_7e_shared_hysteresis_parity_manifest.json"
    )


def _write_v07g_parent_diagnosis_report(script: Any, output_dir: Path) -> dict[str, Any]:
    report = {
        "schema_version": script.V07F_HARNESS_REPORT_SCHEMA_VERSION,
        "diagnostic_slice": "v0_7f",
        "root_cause_status": "classified",
        "primary_root_cause_class": "XY_SATURATION_CENTERING_INSTABILITY",
        "secondary_root_cause_candidates": [
            "Z_OPEN_LATERAL_REGRESSION",
            "Z_OPEN_WITH_NO_VERTICAL_PROGRESS",
        ],
        "recommended_downstream_slice": "v0_7g_xy_authority_saturation_repair",
        "policy_slice_under_test": "v0_7e",
        "phase_e_passed": False,
        "calibration_opened": False,
        "heldout_21000_21049_accessed": False,
        "mvp2_closed": False,
        "policy_uplift_proven": False,
        "proof_authority": "diagnostic_only_not_closure_authority",
    }
    diag_dir = output_dir / script.V07F_OUTPUT_DIRNAME
    script.write_json(diag_dir / "mvp2e_v07f_depth_zero_harness_report.json", report)
    return report


def _write_v07g_parent_chain(script: Any, output_dir: Path) -> dict[str, Any]:
    _write_minimal_v07c_parent_slice_for_v07d(script, output_dir, include_harness_report=True)
    script.build_v07d_action_authority_post_adapter_z_gate_slice(output_dir=output_dir)
    v07e_manifest = script.build_v07e_shared_hysteresis_parity_repair_slice(
        output_dir=output_dir,
        counterfactual_windows=_v07e_counterfactual_windows(),
    )
    _write_v07g_parent_diagnosis_report(script, output_dir)
    return v07e_manifest


def test_v07g_builds_policy_artifacts_from_v07e_parent(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_v07g_parent_chain(script, tmp_path)

    manifest = script.build_v07g_xy_authority_saturation_repair_slice(output_dir=tmp_path)

    child_dir = tmp_path / script.V07G_CHILD_OUTPUT_DIRNAME
    candidate = script.read_json(child_dir / "candidate_policy_artifact_v0_7g.json")
    baseline = script.read_json(child_dir / "baseline_policy_artifact_v0_7g.json")
    assert manifest["policy_slice"] == "v0_7g"
    assert manifest["parent_policy_slice"] == "v0_7e"
    assert candidate["policy_slice"] == "v0_7g"
    assert candidate["parent_policy_slice"] == "v0_7e"
    assert candidate["shared_hysteresis_authority_config_sha256"] == baseline[
        "shared_hysteresis_authority_config_sha256"
    ]
    assert candidate["final_post_adapter_xy_authority_config_sha256"] == baseline[
        "final_post_adapter_xy_authority_config_sha256"
    ]
    assert candidate["future_ab_ready"] is False
    assert candidate["mvp2_closed"] is False


def test_v07g_requires_v07f_classified_xy_saturation_parent_report(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_minimal_v07c_parent_slice_for_v07d(script, tmp_path, include_harness_report=True)
    script.build_v07d_action_authority_post_adapter_z_gate_slice(output_dir=tmp_path)
    script.build_v07e_shared_hysteresis_parity_repair_slice(
        output_dir=tmp_path,
        counterfactual_windows=_v07e_counterfactual_windows(),
    )

    with pytest.raises(ValueError, match="missing_v0_7f_xy_saturation_parent_report"):
        script.build_v07g_xy_authority_saturation_repair_slice(output_dir=tmp_path)


def test_v07g_offline_gate_requires_after_authority_saturation_below_expert_bound(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    config = script.build_v07g_xy_authority_config(
        output_dir=tmp_path,
        parent_shared_hysteresis_authority_config_sha256="parent-hyst",
        parent_final_post_adapter_authority_config_sha256="parent-final-z",
    )

    gate = script.derive_v07g_offline_xy_authority_gate(
        rows=[
            {
                "seed": 19030,
                "lateral_error_m": 0.001,
                "relative_x_m": -0.02,
                "relative_y_m": 0.0,
            }
        ],
        candidate_pre_xy_authority_actions=[[0.05, 0.0, -0.032, 0.0, 0.0, 0.0, 1.0]],
        baseline_pre_xy_authority_actions=[[0.01, 0.0, -0.032, 0.0, 0.0, 0.0, 1.0]],
        xy_authority_config=config,
        expert_reference_xy_saturation_ratio=0.0,
    )

    assert gate["passed"] is False
    assert gate["failure_reason"] == "post_xy_authority_saturation_above_expert_bound"
    assert gate["phase_e_candidate_expressibility_unblocked"] is False


def test_v07g_offline_gate_preserves_candidate_baseline_attribution(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    config = script.build_v07g_xy_authority_config(
        output_dir=tmp_path,
        parent_shared_hysteresis_authority_config_sha256="parent-hyst",
        parent_final_post_adapter_authority_config_sha256="parent-final-z",
    )

    gate = script.derive_v07g_offline_xy_authority_gate(
        rows=[
            {"seed": 19030, "lateral_error_m": 0.001, "relative_x_m": -0.0005, "relative_y_m": 0.0},
            {"seed": 19031, "lateral_error_m": 0.001, "relative_x_m": 0.0005, "relative_y_m": 0.0},
        ],
        candidate_pre_xy_authority_actions=[
            [0.05, 0.0, -0.032, 0.0, 0.0, 0.0, 1.0],
            [-0.05, 0.0, -0.032, 0.0, 0.0, 0.0, 1.0],
        ],
        baseline_pre_xy_authority_actions=[
            [0.01, 0.0, -0.032, 0.0, 0.0, 0.0, 1.0],
            [-0.01, 0.0, -0.032, 0.0, 0.0, 0.0, 1.0],
        ],
        xy_authority_config=config,
    )

    assert gate["passed"] is True
    assert gate["pre_xy_authority_candidate_baseline_xy_delta_l2_mean"] > 1.0e-6
    assert gate["post_xy_authority_candidate_baseline_xy_delta_l2_mean"] > 1.0e-6
    assert gate["xy_delta_retention_ratio"] >= 0.10


def test_v07g_offline_gate_fails_when_xy_authority_erases_attribution(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    config = script.build_v07g_xy_authority_config(
        output_dir=tmp_path,
        parent_shared_hysteresis_authority_config_sha256="parent-hyst",
        parent_final_post_adapter_authority_config_sha256="parent-final-z",
    )

    gate = script.derive_v07g_offline_xy_authority_gate(
        rows=[{"seed": 19030, "lateral_error_m": 0.001, "relative_x_m": -0.0005, "relative_y_m": 0.0}],
        candidate_pre_xy_authority_actions=[[0.05, 0.0, -0.032, 0.0, 0.0, 0.0, 1.0]],
        baseline_pre_xy_authority_actions=[[0.05, 0.0, -0.032, 0.0, 0.0, 0.0, 1.0]],
        xy_authority_config=config,
    )

    assert gate["passed"] is False
    assert gate["failure_reason"] == "candidate_baseline_pre_xy_delta_absent"


def test_v07g_offline_gate_reports_pre_post_xy_delta_and_retention_ratio(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    config = script.build_v07g_xy_authority_config(
        output_dir=tmp_path,
        parent_shared_hysteresis_authority_config_sha256="parent-hyst",
        parent_final_post_adapter_authority_config_sha256="parent-final-z",
    )

    gate = script.derive_v07g_offline_xy_authority_gate(
        rows=[{"seed": 19030, "lateral_error_m": 0.001, "relative_x_m": -0.0005, "relative_y_m": 0.0}],
        candidate_pre_xy_authority_actions=[[0.05, 0.0, -0.032, 0.0, 0.0, 0.0, 1.0]],
        baseline_pre_xy_authority_actions=[[0.01, 0.0, -0.032, 0.0, 0.0, 0.0, 1.0]],
        xy_authority_config=config,
    )

    assert "pre_xy_authority_candidate_baseline_xy_delta_l2_mean" in gate
    assert "post_xy_authority_candidate_baseline_xy_delta_l2_mean" in gate
    assert "post_xy_authority_candidate_baseline_xy_delta_nonzero_fraction" in gate
    assert "xy_delta_retention_ratio" in gate


def test_v07g_offline_gate_keeps_z_and_stable_hold_authority(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    config = script.build_v07g_xy_authority_config(
        output_dir=tmp_path,
        parent_shared_hysteresis_authority_config_sha256="parent-hyst",
        parent_final_post_adapter_authority_config_sha256="parent-final-z",
    )

    gate = script.derive_v07g_offline_xy_authority_gate(
        rows=[{"seed": 19030, "lateral_error_m": 0.001, "relative_x_m": -0.0005, "relative_y_m": 0.0}],
        candidate_pre_xy_authority_actions=[[0.05, 0.0, -0.032, 0.0, 0.0, 0.0, 1.0]],
        baseline_pre_xy_authority_actions=[[0.01, 0.0, -0.032, 0.0, 0.0, 0.0, 1.0]],
        xy_authority_config=config,
    )

    assert gate["z_authority_preserved"] is True
    assert gate["stable_hold_authority"] == "env_native_success_mask"


def test_v07g_offline_gate_blocks_closure_claims(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_v07g_parent_chain(script, tmp_path)

    manifest = script.build_v07g_xy_authority_saturation_repair_slice(output_dir=tmp_path)

    assert manifest["mvp2_closed"] is False
    assert manifest["policy_uplift_proven"] is False
    assert manifest["proof_authority"] is False
    assert manifest["calibration_opened"] is False
    assert manifest["heldout_21000_21049_accessed"] is False


def test_v07g_cli_offline_relabel_generates_artifacts(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_v07g_parent_chain(script, tmp_path)

    result = script.main(
        [
            "--scenario-profile",
            "v0_6",
            "--policy-slice",
            "v0_7g",
            "--offline-relabel-only",
            "--output-dir",
            str(tmp_path),
        ]
    )

    child_dir = tmp_path / script.V07G_CHILD_OUTPUT_DIRNAME
    evidence_manifest = script.read_json(tmp_path / "evidence_manifest.json")
    assert result == 0
    assert (child_dir / "v0_7g_xy_authority_config.json").exists()
    assert (child_dir / "offline_xy_authority_gate_v0_7g.json").exists()
    assert evidence_manifest["policy_slice"] == "v0_7g"
    assert evidence_manifest["mvp2_closed"] is False


def test_v07g_expressibility_sanity_requires_passed_offline_gate(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    gate = script.run_v07g_expressibility_sanity_runtime(
        output_dir=tmp_path,
        manifest={"manifest_sha256": "sha", "scenarios": []},
        backend=script.DeterministicTrainingCalibrationBackend(),
    )

    assert gate["passed"] is False
    assert gate["reason"] == "missing_passed_v0_7g_offline_xy_authority_gate"
    assert gate["heldout_21000_21049_accessed"] is False


def test_v07g_expressibility_sanity_rejects_failed_offline_gate(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    child_dir = tmp_path / script.V07G_CHILD_OUTPUT_DIRNAME
    script.write_json(
        child_dir / "offline_xy_authority_gate_v0_7g.json",
        {
            "schema_version": script.V07G_OFFLINE_XY_AUTHORITY_GATE_SCHEMA_VERSION,
            "policy_slice": "v0_7g",
            "passed": False,
            "offline_xy_authority_gate_sha256": "sha",
        },
    )

    gate = script.run_v07g_expressibility_sanity_runtime(
        output_dir=tmp_path,
        manifest={"manifest_sha256": "sha", "scenarios": []},
        backend=script.DeterministicTrainingCalibrationBackend(),
    )

    assert gate["passed"] is False
    assert gate["reason"] == "missing_passed_v0_7g_offline_xy_authority_gate"


def test_v07g_rejects_protected_heldout_seed_access(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    config = script.build_v07g_xy_authority_config(
        output_dir=tmp_path,
        parent_shared_hysteresis_authority_config_sha256="parent-hyst",
        parent_final_post_adapter_authority_config_sha256="parent-final-z",
    )

    gate = script.derive_v07g_offline_xy_authority_gate(
        rows=[{"seed": 21000, "lateral_error_m": 0.001, "relative_x_m": -0.0005, "relative_y_m": 0.0}],
        candidate_pre_xy_authority_actions=[[0.05, 0.0, -0.032, 0.0, 0.0, 0.0, 1.0]],
        baseline_pre_xy_authority_actions=[[0.01, 0.0, -0.032, 0.0, 0.0, 0.0, 1.0]],
        xy_authority_config=config,
    )

    assert gate["passed"] is False
    assert gate["failure_reason"] == "protected_heldout_seed_accessed"
    assert gate["heldout_21000_21049_accessed"] is True


def _write_v07h_parent_chain(script: Any, output_dir: Path) -> dict[str, Any]:
    manifest = script.build_mvp2c_scenario_manifest(output_dir=output_dir, scenario_profile="v0_6")
    _write_v07g_parent_chain(script, output_dir)
    script.build_v07g_xy_authority_saturation_repair_slice(output_dir=output_dir)
    child_dir = output_dir / script.V07G_CHILD_OUTPUT_DIRNAME
    expressibility_gate = {
        "schema_version": script.V07G_EXPRESSIBILITY_SANITY_GATE_SCHEMA_VERSION,
        "policy_slice": "v0_7g",
        "slice_id": script.V07G_SLICE_ID,
        "passed": True,
        "runtime_backend": "isaac_runtime",
        "proof_runtime": "isaac_candidate_policy_train_split_expressibility_sanity",
        "rollout_count": 5,
        "success_count": 2,
        "required_success_count": 2,
        "calibration_opened": False,
        "heldout_opened": False,
        "heldout_21000_21049_accessed": False,
        "mvp2_closed": False,
        "policy_uplift_proven": False,
        "phase_e_candidate_expressibility_unblocked": True,
        "expressibility_sanity_gate_sha256": "v07g-expressibility-sha",
    }
    script.write_json(child_dir / "expressibility_sanity_gate_v0_7g.json", expressibility_gate)
    return manifest


def _rollouts(success_count: int, total: int = 30, *, seed_start: int = 20000) -> list[dict[str, Any]]:
    return [
        {
            "rollout_id": f"calibration_{index:04d}",
            "scenario_id": f"calibration_{seed_start + index}",
            "seed": seed_start + index,
            "success": index < success_count,
            "env_native_rollout_success": index < success_count,
        }
        for index in range(total)
    ]


def test_v07h_builds_calibration_runtime_manifest_without_heldout_access(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    manifest = script.build_mvp2c_scenario_manifest(output_dir=tmp_path, scenario_profile="v0_6")

    runtime_manifest = script.build_v07h_calibration_runtime_manifest(output_dir=tmp_path, manifest=manifest)

    seeds = [int(row["seed"]) for row in runtime_manifest["scenarios"]]
    assert len(seeds) == 30
    assert seeds == list(range(20000, 20030))
    assert all(row["split"] == "held_out" for row in runtime_manifest["scenarios"])
    assert all(row["source_split"] == "calibration" for row in runtime_manifest["scenarios"])
    assert all(row["semantic_eval_split"] == "calibration" for row in runtime_manifest["scenarios"])
    assert runtime_manifest["heldout_21000_21049_accessed"] is False
    assert not any(21000 <= seed <= 21049 for seed in seeds)


def test_v07h_gate_passes_on_candidate_calibration_presignal(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    gate = script.derive_v07h_calibration_presignal_gate(
        baseline_rollouts=_rollouts(6),
        candidate_rollouts=_rollouts(10),
        runtime_gate={"passed": True, "runtime_backend": "isaac_runtime", "proof_runtime": script.ISAAC_PROOF_RUNTIME},
        runtime_metadata={"runtime_backend": "isaac_runtime"},
        trace_paths={"baseline": [], "candidate": []},
        output_dir=tmp_path,
    )

    assert gate["passed"] is True
    assert gate["heldout_allowed"] is True
    assert gate["baseline_calibration_success_rate"] == 0.2
    assert gate["candidate_calibration_success_rate"] == round(10 / 30, 12)
    assert gate["mvp2_closed"] is False
    assert gate["policy_uplift_proven"] is False
    assert gate["heldout_21000_21049_accessed"] is False


def test_v07h_gate_fails_when_candidate_not_above_baseline(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    gate = script.derive_v07h_calibration_presignal_gate(
        baseline_rollouts=_rollouts(10),
        candidate_rollouts=_rollouts(10),
        runtime_gate={"passed": True, "runtime_backend": "isaac_runtime", "proof_runtime": script.ISAAC_PROOF_RUNTIME},
        runtime_metadata={"runtime_backend": "isaac_runtime"},
        trace_paths={"baseline": [], "candidate": []},
        output_dir=tmp_path,
    )

    assert gate["passed"] is False
    assert gate["heldout_allowed"] is False
    assert gate["failure_reason"] == "candidate_calibration_not_above_baseline"


def test_v07h_gate_fails_when_candidate_below_minimum_success(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    gate = script.derive_v07h_calibration_presignal_gate(
        baseline_rollouts=_rollouts(1),
        candidate_rollouts=_rollouts(8),
        runtime_gate={"passed": True, "runtime_backend": "isaac_runtime", "proof_runtime": script.ISAAC_PROOF_RUNTIME},
        runtime_metadata={"runtime_backend": "isaac_runtime"},
        trace_paths={"baseline": [], "candidate": []},
        output_dir=tmp_path,
    )

    assert gate["passed"] is False
    assert gate["failure_reason"] == "candidate_calibration_success_below_minimum"


def test_v07h_gate_rejects_protected_heldout_seed_access(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    candidate = _rollouts(10)
    candidate[0] = {**candidate[0], "seed": 21000, "scenario_id": "held_out_21000"}

    gate = script.derive_v07h_calibration_presignal_gate(
        baseline_rollouts=_rollouts(6),
        candidate_rollouts=candidate,
        runtime_gate={"passed": True, "runtime_backend": "isaac_runtime", "proof_runtime": script.ISAAC_PROOF_RUNTIME},
        runtime_metadata={"runtime_backend": "isaac_runtime"},
        trace_paths={"baseline": [], "candidate": []},
        output_dir=tmp_path,
    )

    assert gate["passed"] is False
    assert gate["failure_reason"] == "protected_heldout_seed_accessed"
    assert gate["heldout_21000_21049_accessed"] is True


def test_v07h_requires_passed_v07g_expressibility_gate(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_v07g_parent_chain(script, tmp_path)
    script.build_v07g_xy_authority_saturation_repair_slice(output_dir=tmp_path)

    with pytest.raises(ValueError, match="missing_passed_v0_7g_expressibility_gate"):
        script.load_required_v07h_parent_expressibility_gate(tmp_path)


def test_v07h_cli_calibration_presignal_generates_nonclosure_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_v07h_parent_chain(script, tmp_path)

    class FakeBackend:
        runtime_backend = "isaac_runtime"
        proof_runtime = script.ISAAC_PROOF_RUNTIME

        def __init__(self, **_: object) -> None:
            pass

        def run(self, *, manifest, output_dir, min_rollouts_per_policy, deterministic_profile, policy_artifacts):
            del deterministic_profile, policy_artifacts
            output_dir.mkdir(parents=True, exist_ok=True)
            trace_dir = output_dir / "isaac_runtime_heldout_rollout_traces"
            trace_dir.mkdir(parents=True, exist_ok=True)
            baseline = _rollouts(6, total=min_rollouts_per_policy)
            candidate = _rollouts(10, total=min_rollouts_per_policy)
            baseline_paths = []
            candidate_paths = []
            for role, rollouts, paths in (
                ("baseline", baseline, baseline_paths),
                ("candidate", candidate, candidate_paths),
            ):
                for index, rollout in enumerate(rollouts):
                    trace_path = trace_dir / f"{role}_{index:04d}_{rollout['scenario_id']}.json"
                    script.write_json(trace_path, {"scenario": manifest["scenarios"][index], "summary": rollout})
                    paths.append(str(trace_path))
            return script.BackendResult(
                runtime_backend="isaac_runtime",
                proof_runtime=script.ISAAC_PROOF_RUNTIME,
                runtime_gate={"passed": True, "runtime_backend": "isaac_runtime", "proof_runtime": script.ISAAC_PROOF_RUNTIME},
                baseline_rollouts=baseline,
                candidate_rollouts=candidate,
                baseline_trace_paths=baseline_paths,
                candidate_trace_paths=candidate_paths,
                runtime_metadata={"runtime_backend": "isaac_runtime"},
            )

    monkeypatch.setattr(script, "IsaacConnectorInsertionEvaluatorBackend", FakeBackend)

    result = script.main(
        [
            "--scenario-profile",
            "v0_6",
            "--policy-slice",
            "v0_7g",
            "--calibration-presignal-only",
            "--output-dir",
            str(tmp_path),
        ]
    )

    child_dir = tmp_path / script.V07H_CHILD_OUTPUT_DIRNAME
    evidence_manifest = script.read_json(tmp_path / "evidence_manifest.json")
    gate = script.read_json(child_dir / "calibration_presignal_gate_v0_7h.json")
    compatibility_gate = script.read_json(tmp_path / "calibration_presignal_gate.json")
    assert result == 0
    assert gate["passed"] is True
    assert gate["calibration_opened"] is True
    assert gate["mvp2_closed"] is False
    assert compatibility_gate["source_gate_path"] == (
        f"{script.V07H_CHILD_OUTPUT_DIRNAME}/calibration_presignal_gate_v0_7h.json"
    )
    assert evidence_manifest["policy_slice"] == "v0_7g"
    assert evidence_manifest["proof_runtime"] == script.V07H_SLICE_ID
    assert evidence_manifest["heldout_21000_21049_accessed"] is False


def _v07i_trace(
    *,
    success: bool = False,
    initial_lateral: float = 0.018,
    min_lateral: float = 0.0004,
    final_lateral: float = 0.006,
    max_depth: float = 0.0,
    first_env_native_step: int | None = None,
    env_native_run: int = 0,
    xy_authority_applied_after_step: int | None = None,
) -> dict[str, Any]:
    trace: list[dict[str, Any]] = []
    for step in range(148):
        progress = step / 147.0
        lateral = max(final_lateral, initial_lateral - (initial_lateral - min_lateral) * progress)
        depth = max_depth * progress
        env_native = (
            first_env_native_step is not None
            and first_env_native_step <= step < first_env_native_step + env_native_run
        )
        xy_applied = xy_authority_applied_after_step is not None and step >= xy_authority_applied_after_step
        trace.append(
            {
                "step": step,
                "lateral_error_m": round(lateral, 6),
                "insertion_depth_m": round(depth, 6),
                "env_native_success_mask": env_native,
                "normalized_action": [0.05, 0.05, -0.16 if step > 70 else 0.0, 0.0, 0.0, 0.0],
                "controller_action_diagnostics": {
                    "policy_slice": "v0_7g",
                    "xy_authority_applied": xy_applied,
                    "xy_authority_reason": (
                        "xy_saturation_near_center_clamped_to_state_feedback"
                        if xy_applied
                        else "xy_authority_not_needed"
                    ),
                },
            }
        )
    return {
        "scenario": {"scenario_id": "calibration_20000", "seed": 20000},
        "summary": {
            "success": success,
            "failure_reason": "" if success else "ENV_NATIVE_STABILITY_WINDOW_NOT_REACHED",
            "env_native_rollout_success": success,
            "env_native_max_consecutive_success_steps": env_native_run,
        },
        "trace": trace,
    }


def test_v07i_classifies_off_center_xy_authority_gap_depth_zero() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    classification = script.classify_v07i_calibration_trace(
        _v07i_trace(max_depth=0.0, final_lateral=0.006, xy_authority_applied_after_step=130),
        role="candidate",
        trace_path="candidate_0000_calibration_20000_isaac_trace.json",
    )

    assert classification["failure_class"] == "OFF_CENTER_XY_AUTHORITY_GAP_DEPTH_ZERO"
    assert classification["off_center_xy_saturation_count"] > 0
    assert classification["near_center_xy_authority_applied_count"] > 0


def test_v07i_classifies_under_insertion_late_seat_window() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    classification = script.classify_v07i_calibration_trace(
        _v07i_trace(
            max_depth=0.0249,
            final_lateral=0.0005,
            first_env_native_step=140,
            env_native_run=8,
            xy_authority_applied_after_step=100,
        ),
        role="candidate",
        trace_path="candidate_0011_calibration_20011_isaac_trace.json",
    )

    assert classification["failure_class"] == "UNDER_INSERTION_LATE_SEAT_WINDOW"
    assert classification["env_native_max_consecutive_success_steps"] == 8


def test_v07i_builds_calibration_failure_diagnosis_and_recommends_v07j(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    child_dir = tmp_path / script.V07H_CHILD_OUTPUT_DIRNAME
    trace_dir = child_dir / "isaac_runtime_calibration_presignal_v0_7h" / "isaac_runtime_heldout_rollout_traces"
    trace_dir.mkdir(parents=True)
    script.write_json(
        child_dir / "calibration_presignal_gate_v0_7h.json",
        {
            "schema_version": script.V07H_CALIBRATION_PRESIGNAL_SCHEMA_VERSION,
            "policy_slice": "v0_7g",
            "slice_id": script.V07H_SLICE_ID,
            "passed": False,
            "failure_reason": "candidate_calibration_success_below_minimum",
            "runtime_backend": "isaac_runtime",
            "baseline_calibration_success_count": 2,
            "candidate_calibration_success_count": 5,
            "baseline_calibration_rollout_count": 30,
            "candidate_calibration_rollout_count": 30,
            "baseline_calibration_success_rate": 0.066666666667,
            "candidate_calibration_success_rate": 0.166666666667,
            "heldout_21000_21049_accessed": False,
            "mvp2_closed": False,
            "policy_uplift_proven": False,
        },
    )
    baseline_paths = []
    candidate_paths = []
    for index in range(30):
        baseline_path = trace_dir / f"baseline_{index:04d}_calibration_{20000 + index}_isaac_trace.json"
        candidate_path = trace_dir / f"candidate_{index:04d}_calibration_{20000 + index}_isaac_trace.json"
        script.write_json(baseline_path, _v07i_trace(max_depth=0.0))
        script.write_json(
            candidate_path,
            _v07i_trace(
                max_depth=0.0249 if index in {1, 11, 23} else 0.0,
                final_lateral=0.0005 if index in {1, 11, 23} else 0.006,
                first_env_native_step=140 if index in {11, 23} else None,
                env_native_run=8 if index in {11, 23} else 0,
                xy_authority_applied_after_step=100 if index in {1, 11, 23} else 130,
            ),
        )
        baseline_paths.append(str(baseline_path))
        candidate_paths.append(str(candidate_path))
    gate = script.read_json(child_dir / "calibration_presignal_gate_v0_7h.json")
    gate["trace_paths"] = {"baseline": baseline_paths, "candidate": candidate_paths}
    script.write_json(child_dir / "calibration_presignal_gate_v0_7h.json", gate)

    diagnosis = script.build_v07i_calibration_failure_diagnosis(output_dir=tmp_path)

    assert diagnosis["diagnosis_confident"] is True
    assert diagnosis["recommended_downstream_slice"] == "v0_7j_off_center_xy_authority_repair"
    assert diagnosis["heldout_21000_21049_accessed"] is False
    assert diagnosis["candidate_failure_class_counts"]["OFF_CENTER_XY_AUTHORITY_GAP_DEPTH_ZERO"] >= 20


def test_v07i_cli_calibration_failure_diagnosis_writes_evidence_manifest(
    tmp_path: Path,
) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    child_dir = tmp_path / script.V07H_CHILD_OUTPUT_DIRNAME
    trace_dir = child_dir / "isaac_runtime_calibration_presignal_v0_7h" / "isaac_runtime_heldout_rollout_traces"
    trace_dir.mkdir(parents=True)
    baseline_paths = []
    candidate_paths = []
    for index in range(30):
        baseline_path = trace_dir / f"baseline_{index:04d}_calibration_{20000 + index}_isaac_trace.json"
        candidate_path = trace_dir / f"candidate_{index:04d}_calibration_{20000 + index}_isaac_trace.json"
        script.write_json(baseline_path, _v07i_trace(max_depth=0.0))
        script.write_json(candidate_path, _v07i_trace(max_depth=0.0, xy_authority_applied_after_step=130))
        baseline_paths.append(str(baseline_path))
        candidate_paths.append(str(candidate_path))
    script.write_json(
        child_dir / "calibration_presignal_gate_v0_7h.json",
        {
            "schema_version": script.V07H_CALIBRATION_PRESIGNAL_SCHEMA_VERSION,
            "policy_slice": "v0_7g",
            "slice_id": script.V07H_SLICE_ID,
            "passed": False,
            "failure_reason": "candidate_calibration_success_below_minimum",
            "runtime_backend": "isaac_runtime",
            "baseline_calibration_success_count": 2,
            "candidate_calibration_success_count": 5,
            "baseline_calibration_rollout_count": 30,
            "candidate_calibration_rollout_count": 30,
            "baseline_calibration_success_rate": 0.066666666667,
            "candidate_calibration_success_rate": 0.166666666667,
            "trace_paths": {"baseline": baseline_paths, "candidate": candidate_paths},
            "heldout_21000_21049_accessed": False,
            "mvp2_closed": False,
            "policy_uplift_proven": False,
        },
    )

    result = script.main(
        [
            "--scenario-profile",
            "v0_6",
            "--policy-slice",
            "v0_7g",
            "--calibration-failure-diagnosis-only",
            "--output-dir",
            str(tmp_path),
        ]
    )

    evidence_manifest = script.read_json(tmp_path / "evidence_manifest.json")
    assert result == 0
    assert evidence_manifest["proof_runtime"] == script.V07I_SLICE_ID
    assert evidence_manifest["heldout_21000_21049_accessed"] is False


def _write_v07j_parent_chain(script: Any, output_dir: Path) -> dict[str, Any]:
    manifest = _write_v07h_parent_chain(script, output_dir)
    diagnosis_dir = output_dir / script.V07I_CHILD_OUTPUT_DIRNAME
    diagnosis = {
        "schema_version": script.V07I_DIAGNOSIS_SCHEMA_VERSION,
        "policy_slice": "v0_7g",
        "slice_id": script.V07I_SLICE_ID,
        "runtime_backend": "offline_calibration_failure_diagnosis",
        "primary_root_cause_class": "OFF_CENTER_XY_AUTHORITY_GAP_AND_LATE_ALIGNMENT",
        "diagnosis_confident": True,
        "recommended_downstream_slice": "v0_7j_off_center_xy_authority_repair",
        "calibration_opened": True,
        "heldout_opened": False,
        "heldout_21000_21049_accessed": False,
        "proof_authority": False,
        "mvp2_closed": False,
        "policy_uplift_proven": False,
    }
    diagnosis["calibration_failure_diagnosis_sha256"] = script._sha256_payload_excluding(
        diagnosis,
        "calibration_failure_diagnosis_sha256",
    )
    script.write_json(diagnosis_dir / "calibration_failure_diagnosis_v0_7i.json", diagnosis)
    return manifest


def test_v07j_builds_off_center_xy_authority_repair_slice(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_v07j_parent_chain(script, tmp_path)

    manifest = script.build_v07j_off_center_xy_authority_repair_slice(output_dir=tmp_path)

    child_dir = tmp_path / script.V07J_CHILD_OUTPUT_DIRNAME
    config = script.read_json(child_dir / "v0_7j_xy_authority_config.json")
    candidate = script.read_json(child_dir / "candidate_policy_artifact_v0_7j.json")
    baseline = script.read_json(child_dir / "baseline_policy_artifact_v0_7j.json")
    offline_gate = script.read_json(child_dir / "offline_xy_authority_gate_v0_7j.json")
    assert manifest["policy_slice"] == "v0_7j"
    assert manifest["parent_policy_slice"] == "v0_7g"
    assert manifest["parent_primary_root_cause_class"] == "OFF_CENTER_XY_AUTHORITY_GAP_AND_LATE_ALIGNMENT"
    assert config["xy_authority_strategy"] == "piecewise_off_center_state_feedback_clip"
    assert config["xy_off_center_clip_abs"] == 0.05
    assert config["xy_near_center_clip_abs"] == 0.02
    assert candidate["policy_slice"] == "v0_7j"
    assert baseline["policy_slice"] == "v0_7j"
    assert candidate["final_post_adapter_xy_authority_config_sha256"] == baseline[
        "final_post_adapter_xy_authority_config_sha256"
    ]
    assert offline_gate["passed"] is True
    assert offline_gate["off_center_xy_authority_applied"] is True
    assert offline_gate["near_center_xy_authority_applied"] is True
    assert manifest["mvp2_closed"] is False
    assert manifest["heldout_21000_21049_accessed"] is False


def test_v07j_cli_offline_relabel_generates_nonclosure_artifacts(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_v07j_parent_chain(script, tmp_path)

    result = script.main(
        [
            "--scenario-profile",
            "v0_6",
            "--policy-slice",
            "v0_7j",
            "--offline-relabel-only",
            "--output-dir",
            str(tmp_path),
        ]
    )

    child_dir = tmp_path / script.V07J_CHILD_OUTPUT_DIRNAME
    evidence_manifest = script.read_json(tmp_path / "evidence_manifest.json")
    assert result == 0
    assert (child_dir / "v0_7j_xy_authority_config.json").exists()
    assert (child_dir / "offline_xy_authority_gate_v0_7j.json").exists()
    assert evidence_manifest["policy_slice"] == "v0_7j"
    assert evidence_manifest["proof_runtime"] == script.V07J_SLICE_ID
    assert evidence_manifest["mvp2_closed"] is False
    assert evidence_manifest["heldout_21000_21049_accessed"] is False


def test_v07j_cli_calibration_presignal_generates_nonclosure_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_v07j_parent_chain(script, tmp_path)

    class FakeBackend:
        runtime_backend = "isaac_runtime"
        proof_runtime = script.ISAAC_PROOF_RUNTIME

        def __init__(self, **_: object) -> None:
            pass

        def run(self, *, manifest, output_dir, min_rollouts_per_policy, deterministic_profile, policy_artifacts):
            del deterministic_profile
            output_dir.mkdir(parents=True, exist_ok=True)
            trace_dir = output_dir / "isaac_runtime_heldout_rollout_traces"
            trace_dir.mkdir(parents=True, exist_ok=True)
            assert policy_artifacts["candidate"]["policy_slice"] == "v0_7j"
            assert policy_artifacts["baseline"]["policy_slice"] == "v0_7j"
            assert all(int(row["seed"]) < 21000 for row in manifest["scenarios"])
            baseline = _rollouts(6, total=min_rollouts_per_policy)
            candidate = _rollouts(10, total=min_rollouts_per_policy)
            baseline_paths = []
            candidate_paths = []
            for role, rollouts, paths in (
                ("baseline", baseline, baseline_paths),
                ("candidate", candidate, candidate_paths),
            ):
                for index, rollout in enumerate(rollouts):
                    trace_path = trace_dir / f"{role}_{index:04d}_{rollout['scenario_id']}.json"
                    script.write_json(trace_path, {"scenario": manifest["scenarios"][index], "summary": rollout})
                    paths.append(str(trace_path))
            return script.BackendResult(
                runtime_backend="isaac_runtime",
                proof_runtime=script.ISAAC_PROOF_RUNTIME,
                runtime_gate={
                    "passed": True,
                    "runtime_backend": "isaac_runtime",
                    "proof_runtime": script.ISAAC_PROOF_RUNTIME,
                },
                baseline_rollouts=baseline,
                candidate_rollouts=candidate,
                baseline_trace_paths=baseline_paths,
                candidate_trace_paths=candidate_paths,
                runtime_metadata={"runtime_backend": "isaac_runtime"},
            )

    monkeypatch.setattr(script, "IsaacConnectorInsertionEvaluatorBackend", FakeBackend)

    result = script.main(
        [
            "--scenario-profile",
            "v0_6",
            "--policy-slice",
            "v0_7j",
            "--calibration-presignal-only",
            "--output-dir",
            str(tmp_path),
        ]
    )

    child_dir = tmp_path / script.V07J_CHILD_OUTPUT_DIRNAME
    evidence_manifest = script.read_json(tmp_path / "evidence_manifest.json")
    gate = script.read_json(child_dir / "calibration_presignal_gate_v0_7j.json")
    compatibility_gate = script.read_json(tmp_path / "calibration_presignal_gate.json")
    assert result == 0
    assert gate["passed"] is True
    assert gate["policy_slice"] == "v0_7j"
    assert gate["calibration_opened"] is True
    assert gate["heldout_opened"] is False
    assert gate["mvp2_closed"] is False
    assert compatibility_gate["source_gate_path"] == (
        f"{script.V07J_CHILD_OUTPUT_DIRNAME}/calibration_presignal_gate_v0_7j.json"
    )
    assert evidence_manifest["policy_slice"] == "v0_7j"
    assert evidence_manifest["proof_runtime"] == script.V07J_SLICE_ID
    assert evidence_manifest["heldout_21000_21049_accessed"] is False


def _write_v07k_parent_chain(script: Any, output_dir: Path) -> dict[str, Any]:
    manifest = _write_v07j_parent_chain(script, output_dir)
    script.build_v07j_off_center_xy_authority_repair_slice(output_dir=output_dir)
    child_dir = output_dir / script.V07J_CHILD_OUTPUT_DIRNAME
    failed_gate = {
        "schema_version": script.V07J_CALIBRATION_PRESIGNAL_SCHEMA_VERSION,
        "policy_slice": "v0_7j",
        "slice_id": script.V07J_SLICE_ID,
        "passed": False,
        "failure_reason": "candidate_calibration_not_above_baseline",
        "runtime_backend": "isaac_runtime",
        "proof_runtime": script.ISAAC_PROOF_RUNTIME,
        "baseline_calibration_success_count": 0,
        "candidate_calibration_success_count": 0,
        "baseline_calibration_rollout_count": 30,
        "candidate_calibration_rollout_count": 30,
        "baseline_calibration_success_rate": 0.0,
        "candidate_calibration_success_rate": 0.0,
        "calibration_opened": True,
        "heldout_opened": False,
        "heldout_21000_21049_accessed": False,
        "mvp2_closed": False,
        "policy_uplift_proven": False,
    }
    failed_gate["calibration_presignal_gate_sha256"] = script._sha256_payload_excluding(
        failed_gate,
        "calibration_presignal_gate_sha256",
    )
    script.write_json(child_dir / "calibration_presignal_gate_v0_7j.json", failed_gate)
    return manifest


def test_v07k_builds_runtime_hysteresis_wiring_repair_slice(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_v07k_parent_chain(script, tmp_path)

    manifest = script.build_v07k_runtime_hysteresis_wiring_repair_slice(output_dir=tmp_path)

    child_dir = tmp_path / script.V07K_CHILD_OUTPUT_DIRNAME
    candidate = script.read_json(child_dir / "candidate_policy_artifact_v0_7k.json")
    baseline = script.read_json(child_dir / "baseline_policy_artifact_v0_7k.json")
    gate = script.read_json(child_dir / "runtime_wiring_gate_v0_7k.json")
    assert manifest["policy_slice"] == "v0_7k"
    assert manifest["parent_policy_slice"] == "v0_7j"
    assert candidate["policy_slice"] == "v0_7k"
    assert baseline["policy_slice"] == "v0_7k"
    assert candidate["runtime_hysteresis_wiring_repair_id"] == script.V07K_RUNTIME_HYSTERESIS_WIRING_REPAIR_ID
    assert candidate["shared_hysteresis_authority_config_sha256"] == baseline[
        "shared_hysteresis_authority_config_sha256"
    ]
    assert candidate["final_post_adapter_xy_authority_config_sha256"] == baseline[
        "final_post_adapter_xy_authority_config_sha256"
    ]
    assert gate["passed"] is True
    assert gate["success_metric_changed"] is False
    assert gate["trainer_changed"] is False
    assert gate["heldout_21000_21049_accessed"] is False


def test_v07k_cli_offline_relabel_generates_nonclosure_artifacts(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_v07k_parent_chain(script, tmp_path)

    result = script.main(
        [
            "--scenario-profile",
            "v0_6",
            "--policy-slice",
            "v0_7k",
            "--offline-relabel-only",
            "--output-dir",
            str(tmp_path),
        ]
    )

    child_dir = tmp_path / script.V07K_CHILD_OUTPUT_DIRNAME
    evidence_manifest = script.read_json(tmp_path / "evidence_manifest.json")
    assert result == 0
    assert (child_dir / "runtime_wiring_gate_v0_7k.json").exists()
    assert evidence_manifest["policy_slice"] == "v0_7k"
    assert evidence_manifest["proof_runtime"] == script.V07K_SLICE_ID
    assert evidence_manifest["mvp2_closed"] is False
    assert evidence_manifest["heldout_21000_21049_accessed"] is False


def test_v07k_cli_calibration_presignal_generates_nonclosure_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_v07k_parent_chain(script, tmp_path)

    class FakeBackend:
        runtime_backend = "isaac_runtime"
        proof_runtime = script.ISAAC_PROOF_RUNTIME

        def __init__(self, **_: object) -> None:
            pass

        def run(self, *, manifest, output_dir, min_rollouts_per_policy, deterministic_profile, policy_artifacts):
            del deterministic_profile
            output_dir.mkdir(parents=True, exist_ok=True)
            trace_dir = output_dir / "isaac_runtime_heldout_rollout_traces"
            trace_dir.mkdir(parents=True, exist_ok=True)
            assert policy_artifacts["candidate"]["policy_slice"] == "v0_7k"
            assert policy_artifacts["baseline"]["policy_slice"] == "v0_7k"
            assert all(int(row["seed"]) < 21000 for row in manifest["scenarios"])
            baseline = _rollouts(6, total=min_rollouts_per_policy)
            candidate = _rollouts(10, total=min_rollouts_per_policy)
            baseline_paths = []
            candidate_paths = []
            for role, rollouts, paths in (
                ("baseline", baseline, baseline_paths),
                ("candidate", candidate, candidate_paths),
            ):
                for index, rollout in enumerate(rollouts):
                    trace_path = trace_dir / f"{role}_{index:04d}_{rollout['scenario_id']}.json"
                    script.write_json(trace_path, {"scenario": manifest["scenarios"][index], "summary": rollout})
                    paths.append(str(trace_path))
            return script.BackendResult(
                runtime_backend="isaac_runtime",
                proof_runtime=script.ISAAC_PROOF_RUNTIME,
                runtime_gate={
                    "passed": True,
                    "runtime_backend": "isaac_runtime",
                    "proof_runtime": script.ISAAC_PROOF_RUNTIME,
                },
                baseline_rollouts=baseline,
                candidate_rollouts=candidate,
                baseline_trace_paths=baseline_paths,
                candidate_trace_paths=candidate_paths,
                runtime_metadata={"runtime_backend": "isaac_runtime"},
            )

    monkeypatch.setattr(script, "IsaacConnectorInsertionEvaluatorBackend", FakeBackend)

    result = script.main(
        [
            "--scenario-profile",
            "v0_6",
            "--policy-slice",
            "v0_7k",
            "--calibration-presignal-only",
            "--output-dir",
            str(tmp_path),
        ]
    )

    child_dir = tmp_path / script.V07K_CHILD_OUTPUT_DIRNAME
    evidence_manifest = script.read_json(tmp_path / "evidence_manifest.json")
    gate = script.read_json(child_dir / "calibration_presignal_gate_v0_7k.json")
    compatibility_gate = script.read_json(tmp_path / "calibration_presignal_gate.json")
    assert result == 0
    assert gate["passed"] is True
    assert gate["policy_slice"] == "v0_7k"
    assert gate["calibration_opened"] is True
    assert gate["heldout_opened"] is False
    assert gate["mvp2_closed"] is False
    assert compatibility_gate["source_gate_path"] == (
        f"{script.V07K_CHILD_OUTPUT_DIRNAME}/calibration_presignal_gate_v0_7k.json"
    )
    assert evidence_manifest["policy_slice"] == "v0_7k"
    assert evidence_manifest["proof_runtime"] == script.V07K_SLICE_ID
    assert evidence_manifest["heldout_21000_21049_accessed"] is False


def _v07l_trace(
    *,
    success: bool = False,
    max_depth: float = 0.0,
    env_native_run: int = 0,
    z_start_step: int | None = 60,
    z_run_steps: int = 28,
    z_lateral_end: float = 0.003,
    seed: int = 20000,
) -> dict[str, Any]:
    trace: list[dict[str, Any]] = []
    for step in range(148):
        z_open = z_start_step is not None and z_start_step <= step < z_start_step + z_run_steps
        z_progress = 0.0
        if z_open and z_run_steps > 1:
            z_progress = (step - z_start_step) / float(z_run_steps - 1)
        lateral = 0.0008 + (z_lateral_end - 0.0008) * z_progress if z_open else 0.0008
        depth = max_depth * max(0.0, (step - (z_start_step or 0)) / 60.0)
        env_native = success and 100 <= step < 100 + env_native_run
        trace.append(
            {
                "step": step,
                "lateral_error_m": round(lateral, 6),
                "insertion_depth_m": round(depth, 6),
                "env_native_success_mask": env_native,
                "normalized_action": [0.0, 0.0, -0.16 if z_open else 0.0, 0.0, 0.0, 0.0],
                "controller_action_diagnostics": {
                    "policy_slice": "v0_7k",
                    "z_motion_block_reason": (
                        "z_motion_allowed_by_v07e_hysteresis"
                        if z_open
                        else "final_post_adapter_align_z_blocked"
                    ),
                    "shared_hysteresis_state_after": {
                        "current_hysteresis_phase": "DESCEND" if z_open else "ALIGN",
                        "last_z_motion_allowed": z_open,
                    },
                },
            }
        )
    return {
        "scenario": {"scenario_id": f"calibration_{seed}", "seed": seed},
        "summary": {
            "success": success,
            "env_native_rollout_success": success,
            "env_native_max_consecutive_success_steps": env_native_run,
            "failure_reason": "" if success else "ENV_NATIVE_STABILITY_WINDOW_NOT_REACHED",
        },
        "trace": trace,
    }


def test_v07l_classifies_z_window_no_vertical_progress_with_centering() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    classification = script.classify_v07l_calibration_trace(
        _v07l_trace(max_depth=0.0, z_lateral_end=0.003),
        role="candidate",
        trace_path="candidate_0000_calibration_20000_isaac_trace.json",
    )

    assert classification["failure_class"] == "Z_WINDOW_NO_VERTICAL_PROGRESS_WITH_CENTERING"
    assert classification["max_consecutive_z_motion_steps"] == 28
    assert classification["z_window_max_lateral_error_m"] <= 0.006


def test_v07l_classifies_z_window_lateral_escape_no_depth() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    classification = script.classify_v07l_calibration_trace(
        _v07l_trace(max_depth=0.0, z_lateral_end=0.009),
        role="candidate",
        trace_path="candidate_0002_calibration_20002_isaac_trace.json",
    )

    assert classification["failure_class"] == "Z_WINDOW_LATERAL_ESCAPE_NO_DEPTH"
    assert classification["z_window_max_lateral_error_m"] > 0.006


def test_v07l_builds_calibration_failure_diagnosis_and_recommends_v07m(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    child_dir = tmp_path / script.V07K_CHILD_OUTPUT_DIRNAME
    trace_dir = child_dir / "isaac_runtime_calibration_presignal_v0_7k" / "isaac_runtime_heldout_rollout_traces"
    trace_dir.mkdir(parents=True)
    baseline_paths = []
    candidate_paths = []
    for index in range(30):
        baseline_path = trace_dir / f"baseline_{index:04d}_calibration_{20000 + index}_isaac_trace.json"
        candidate_path = trace_dir / f"candidate_{index:04d}_calibration_{20000 + index}_isaac_trace.json"
        script.write_json(baseline_path, _v07l_trace(max_depth=0.0, seed=20000 + index))
        script.write_json(
            candidate_path,
            _v07l_trace(
                success=index in {1, 3, 7, 20},
                max_depth=0.025 if index in {1, 3, 7, 20} else 0.0,
                env_native_run=10 if index in {1, 3, 7, 20} else 0,
                z_lateral_end=0.009 if index in {2, 4, 6, 10, 16, 22, 24} else 0.003,
                seed=20000 + index,
            ),
        )
        baseline_paths.append(str(baseline_path))
        candidate_paths.append(str(candidate_path))
    gate = {
        "schema_version": script.V07K_CALIBRATION_PRESIGNAL_SCHEMA_VERSION,
        "policy_slice": "v0_7k",
        "slice_id": script.V07K_SLICE_ID,
        "passed": False,
        "failure_reason": "candidate_calibration_success_below_minimum",
        "runtime_backend": "isaac_runtime",
        "baseline_calibration_success_count": 3,
        "candidate_calibration_success_count": 4,
        "baseline_calibration_rollout_count": 30,
        "candidate_calibration_rollout_count": 30,
        "baseline_calibration_success_rate": 0.1,
        "candidate_calibration_success_rate": 0.133333333333,
        "trace_paths": {"baseline": baseline_paths, "candidate": candidate_paths},
        "heldout_21000_21049_accessed": False,
        "mvp2_closed": False,
        "policy_uplift_proven": False,
    }
    gate["calibration_presignal_gate_sha256"] = script._sha256_payload_excluding(
        gate,
        "calibration_presignal_gate_sha256",
    )
    script.write_json(child_dir / "calibration_presignal_gate_v0_7k.json", gate)

    diagnosis = script.build_v07l_calibration_failure_diagnosis(output_dir=tmp_path)

    assert diagnosis["diagnosis_confident"] is True
    assert diagnosis["primary_root_cause_class"] == "Z_DESCENT_WINDOW_INSUFFICIENT_AND_CENTERING_ESCAPE"
    assert diagnosis["recommended_downstream_slice"] == "v0_7m_z_window_progress_authority_repair"
    assert diagnosis["candidate_failure_class_counts"]["Z_WINDOW_NO_VERTICAL_PROGRESS_WITH_CENTERING"] >= 10
    assert diagnosis["heldout_21000_21049_accessed"] is False
    assert diagnosis["mvp2_closed"] is False


def test_v07l_cli_calibration_failure_diagnosis_writes_evidence_manifest(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    child_dir = tmp_path / script.V07K_CHILD_OUTPUT_DIRNAME
    trace_dir = child_dir / "isaac_runtime_calibration_presignal_v0_7k" / "isaac_runtime_heldout_rollout_traces"
    trace_dir.mkdir(parents=True)
    baseline_paths = []
    candidate_paths = []
    for index in range(30):
        baseline_path = trace_dir / f"baseline_{index:04d}_calibration_{20000 + index}_isaac_trace.json"
        candidate_path = trace_dir / f"candidate_{index:04d}_calibration_{20000 + index}_isaac_trace.json"
        script.write_json(baseline_path, _v07l_trace(max_depth=0.0, seed=20000 + index))
        script.write_json(candidate_path, _v07l_trace(max_depth=0.0, seed=20000 + index))
        baseline_paths.append(str(baseline_path))
        candidate_paths.append(str(candidate_path))
    gate = {
        "schema_version": script.V07K_CALIBRATION_PRESIGNAL_SCHEMA_VERSION,
        "policy_slice": "v0_7k",
        "slice_id": script.V07K_SLICE_ID,
        "passed": False,
        "failure_reason": "candidate_calibration_success_below_minimum",
        "runtime_backend": "isaac_runtime",
        "baseline_calibration_success_count": 3,
        "candidate_calibration_success_count": 4,
        "baseline_calibration_rollout_count": 30,
        "candidate_calibration_rollout_count": 30,
        "baseline_calibration_success_rate": 0.1,
        "candidate_calibration_success_rate": 0.133333333333,
        "trace_paths": {"baseline": baseline_paths, "candidate": candidate_paths},
        "heldout_21000_21049_accessed": False,
        "mvp2_closed": False,
        "policy_uplift_proven": False,
    }
    gate["calibration_presignal_gate_sha256"] = script._sha256_payload_excluding(
        gate,
        "calibration_presignal_gate_sha256",
    )
    script.write_json(child_dir / "calibration_presignal_gate_v0_7k.json", gate)

    result = script.main(
        [
            "--scenario-profile",
            "v0_6",
            "--policy-slice",
            "v0_7k",
            "--calibration-failure-diagnosis-only",
            "--output-dir",
            str(tmp_path),
        ]
    )

    evidence_manifest = script.read_json(tmp_path / "evidence_manifest.json")
    assert result == 0
    assert evidence_manifest["proof_runtime"] == script.V07L_SLICE_ID
    assert evidence_manifest["policy_slice"] == "v0_7k"
    assert evidence_manifest["heldout_21000_21049_accessed"] is False
    assert evidence_manifest["mvp2_closed"] is False


def _write_v07m_parent_chain(script: Any, output_dir: Path) -> None:
    _write_v07k_parent_chain(script, output_dir)
    script.build_v07k_runtime_hysteresis_wiring_repair_slice(output_dir=output_dir)
    parent_child_dir = output_dir / script.V07L_CHILD_OUTPUT_DIRNAME
    parent_child_dir.mkdir(parents=True, exist_ok=True)
    diagnosis = {
        "schema_version": script.V07L_DIAGNOSIS_SCHEMA_VERSION,
        "policy_slice": script.V07L_POLICY_SLICE_ID,
        "slice_id": script.V07L_SLICE_ID,
        "parent_slice_id": script.V07K_SLICE_ID,
        "parent_calibration_presignal_gate_sha256": "parent-gate-sha",
        "baseline_success_count": 3,
        "candidate_success_count": 4,
        "candidate_failure_count": 26,
        "candidate_dominant_z_window_failure_count": 23,
        "candidate_failure_class_counts": {
            "SUCCESS": 4,
            "Z_WINDOW_NO_VERTICAL_PROGRESS_WITH_CENTERING": 14,
            "Z_WINDOW_LATERAL_ESCAPE_NO_DEPTH": 7,
            "Z_WINDOW_TOO_SHORT_OR_NEVER_OPENED": 2,
            "SEAT_WINDOW_NOT_HELD": 2,
            "PARTIAL_INSERTION_NO_STABILITY": 1,
        },
        "dominant_failure_classes": list(script.V07L_DOMINANT_FAILURE_CLASSES),
        "primary_root_cause_class": "Z_DESCENT_WINDOW_INSUFFICIENT_AND_CENTERING_ESCAPE",
        "diagnosis_confident": True,
        "recommended_downstream_slice": "v0_7m_z_window_progress_authority_repair",
        "calibration_opened": True,
        "heldout_opened": False,
        "heldout_21000_21049_accessed": False,
        "proof_authority": False,
        "mvp2_closed": False,
        "policy_uplift_proven": False,
    }
    diagnosis["calibration_failure_diagnosis_sha256"] = script._sha256_payload_excluding(
        diagnosis,
        "calibration_failure_diagnosis_sha256",
    )
    script.write_json(parent_child_dir / "calibration_failure_diagnosis_v0_7l.json", diagnosis)


def test_v07m_builds_z_window_progress_authority_repair_slice(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_v07m_parent_chain(script, tmp_path)

    manifest = script.build_v07m_z_window_progress_authority_repair_slice(output_dir=tmp_path)

    child_dir = tmp_path / script.V07M_CHILD_OUTPUT_DIRNAME
    candidate = script.read_json(child_dir / "candidate_policy_artifact_v0_7m.json")
    baseline = script.read_json(child_dir / "baseline_policy_artifact_v0_7m.json")
    config = script.read_json(child_dir / "v0_7m_hysteresis_authority_config.json")
    gate = script.read_json(child_dir / "z_window_progress_authority_gate_v0_7m.json")
    assert manifest["policy_slice"] == "v0_7m"
    assert manifest["parent_policy_slice"] == "v0_7k"
    assert candidate["policy_slice"] == "v0_7m"
    assert baseline["policy_slice"] == "v0_7m"
    assert config["z_window_hold_steps"] == 70
    assert config["z_window_realign_lateral_m"] == pytest.approx(0.006)
    assert candidate["shared_hysteresis_authority_config_sha256"] == baseline[
        "shared_hysteresis_authority_config_sha256"
    ]
    assert gate["passed"] is True
    assert gate["parent_diagnosis_confident"] is True
    assert gate["success_metric_changed"] is False
    assert gate["trainer_changed"] is False
    assert gate["heldout_21000_21049_accessed"] is False


def test_v07m_cli_offline_relabel_generates_nonclosure_artifacts(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_v07m_parent_chain(script, tmp_path)

    result = script.main(
        [
            "--scenario-profile",
            "v0_6",
            "--policy-slice",
            "v0_7m",
            "--offline-relabel-only",
            "--output-dir",
            str(tmp_path),
        ]
    )

    child_dir = tmp_path / script.V07M_CHILD_OUTPUT_DIRNAME
    evidence_manifest = script.read_json(tmp_path / "evidence_manifest.json")
    assert result == 0
    assert (child_dir / "z_window_progress_authority_gate_v0_7m.json").exists()
    assert evidence_manifest["policy_slice"] == "v0_7m"
    assert evidence_manifest["proof_runtime"] == script.V07M_SLICE_ID
    assert evidence_manifest["mvp2_closed"] is False
    assert evidence_manifest["heldout_21000_21049_accessed"] is False


def test_v07m_cli_calibration_presignal_generates_nonclosure_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_v07m_parent_chain(script, tmp_path)

    class FakeBackend:
        runtime_backend = "isaac_runtime"
        proof_runtime = script.ISAAC_PROOF_RUNTIME

        def __init__(self, **_: object) -> None:
            pass

        def run(self, *, manifest, output_dir, min_rollouts_per_policy, deterministic_profile, policy_artifacts):
            del deterministic_profile
            output_dir.mkdir(parents=True, exist_ok=True)
            trace_dir = output_dir / "isaac_runtime_heldout_rollout_traces"
            trace_dir.mkdir(parents=True, exist_ok=True)
            assert policy_artifacts["candidate"]["policy_slice"] == "v0_7m"
            assert policy_artifacts["baseline"]["policy_slice"] == "v0_7m"
            assert all(int(row["seed"]) < 21000 for row in manifest["scenarios"])
            baseline = _rollouts(6, total=min_rollouts_per_policy)
            candidate = _rollouts(10, total=min_rollouts_per_policy)
            baseline_paths = []
            candidate_paths = []
            for role, rollouts, paths in (
                ("baseline", baseline, baseline_paths),
                ("candidate", candidate, candidate_paths),
            ):
                for index, rollout in enumerate(rollouts):
                    trace_path = trace_dir / f"{role}_{index:04d}_{rollout['scenario_id']}.json"
                    script.write_json(trace_path, {"scenario": manifest["scenarios"][index], "summary": rollout})
                    paths.append(str(trace_path))
            return script.BackendResult(
                runtime_backend="isaac_runtime",
                proof_runtime=script.ISAAC_PROOF_RUNTIME,
                runtime_gate={
                    "passed": True,
                    "runtime_backend": "isaac_runtime",
                    "proof_runtime": script.ISAAC_PROOF_RUNTIME,
                },
                baseline_rollouts=baseline,
                candidate_rollouts=candidate,
                baseline_trace_paths=baseline_paths,
                candidate_trace_paths=candidate_paths,
                runtime_metadata={"runtime_backend": "isaac_runtime"},
            )

    monkeypatch.setattr(script, "IsaacConnectorInsertionEvaluatorBackend", FakeBackend)

    result = script.main(
        [
            "--scenario-profile",
            "v0_6",
            "--policy-slice",
            "v0_7m",
            "--calibration-presignal-only",
            "--output-dir",
            str(tmp_path),
        ]
    )

    child_dir = tmp_path / script.V07M_CHILD_OUTPUT_DIRNAME
    evidence_manifest = script.read_json(tmp_path / "evidence_manifest.json")
    gate = script.read_json(child_dir / "calibration_presignal_gate_v0_7m.json")
    compatibility_gate = script.read_json(tmp_path / "calibration_presignal_gate.json")
    assert result == 0
    assert gate["passed"] is True
    assert gate["policy_slice"] == "v0_7m"
    assert gate["calibration_opened"] is True
    assert gate["heldout_opened"] is False
    assert gate["mvp2_closed"] is False
    assert compatibility_gate["source_gate_path"] == (
        f"{script.V07M_CHILD_OUTPUT_DIRNAME}/calibration_presignal_gate_v0_7m.json"
    )
    assert evidence_manifest["policy_slice"] == "v0_7m"
    assert evidence_manifest["proof_runtime"] == script.V07M_SLICE_ID
    assert evidence_manifest["heldout_21000_21049_accessed"] is False


def _write_v07n_parent_chain(script: Any, output_dir: Path) -> None:
    _write_v07m_parent_chain(script, output_dir)
    script.build_v07m_z_window_progress_authority_repair_slice(output_dir=output_dir)
    child_dir = output_dir / script.V07M_CHILD_OUTPUT_DIRNAME
    failed_gate = {
        "schema_version": script.V07M_CALIBRATION_PRESIGNAL_SCHEMA_VERSION,
        "policy_slice": "v0_7m",
        "slice_id": script.V07M_SLICE_ID,
        "passed": False,
        "failure_reason": "candidate_calibration_success_below_minimum",
        "runtime_backend": "isaac_runtime",
        "proof_runtime": script.ISAAC_PROOF_RUNTIME,
        "baseline_calibration_success_count": 3,
        "candidate_calibration_success_count": 4,
        "baseline_calibration_rollout_count": 30,
        "candidate_calibration_rollout_count": 30,
        "baseline_calibration_success_rate": 0.1,
        "candidate_calibration_success_rate": 0.133333333333,
        "curated_vs_uncurated_calibration_uplift": 0.033333333333,
        "calibration_opened": True,
        "heldout_opened": False,
        "heldout_21000_21049_accessed": False,
        "mvp2_closed": False,
        "policy_uplift_proven": False,
    }
    failed_gate["calibration_presignal_gate_sha256"] = script._sha256_payload_excluding(
        failed_gate,
        "calibration_presignal_gate_sha256",
    )
    script.write_json(child_dir / "calibration_presignal_gate_v0_7m.json", failed_gate)


def _write_v07o_parent_chain(script: Any, output_dir: Path) -> None:
    _write_v07n_parent_chain(script, output_dir)
    script.build_v07n_z_open_xy_center_maintenance_slice(output_dir=output_dir)
    child_dir = output_dir / script.V07N_CHILD_OUTPUT_DIRNAME
    failed_gate = {
        "schema_version": script.V07N_CALIBRATION_PRESIGNAL_SCHEMA_VERSION,
        "policy_slice": "v0_7n",
        "slice_id": script.V07N_SLICE_ID,
        "passed": False,
        "failure_reason": "candidate_calibration_not_above_baseline",
        "runtime_backend": "isaac_runtime",
        "proof_runtime": script.ISAAC_PROOF_RUNTIME,
        "baseline_calibration_success_count": 1,
        "candidate_calibration_success_count": 1,
        "baseline_calibration_rollout_count": 30,
        "candidate_calibration_rollout_count": 30,
        "baseline_calibration_success_rate": 0.033333333333,
        "candidate_calibration_success_rate": 0.033333333333,
        "curated_vs_uncurated_calibration_uplift": 0.0,
        "calibration_opened": True,
        "heldout_opened": False,
        "heldout_21000_21049_accessed": False,
        "mvp2_closed": False,
        "policy_uplift_proven": False,
    }
    failed_gate["calibration_presignal_gate_sha256"] = script._sha256_payload_excluding(
        failed_gate,
        "calibration_presignal_gate_sha256",
    )
    script.write_json(child_dir / "calibration_presignal_gate_v0_7n.json", failed_gate)


def test_v07n_builds_z_open_xy_center_maintenance_slice(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_v07n_parent_chain(script, tmp_path)

    manifest = script.build_v07n_z_open_xy_center_maintenance_slice(output_dir=tmp_path)

    child_dir = tmp_path / script.V07N_CHILD_OUTPUT_DIRNAME
    candidate = script.read_json(child_dir / "candidate_policy_artifact_v0_7n.json")
    baseline = script.read_json(child_dir / "baseline_policy_artifact_v0_7n.json")
    config = script.read_json(child_dir / "v0_7n_xy_authority_config.json")
    gate = script.read_json(child_dir / "z_open_xy_center_maintenance_gate_v0_7n.json")
    assert manifest["policy_slice"] == "v0_7n"
    assert manifest["parent_policy_slice"] == "v0_7m"
    assert candidate["policy_slice"] == "v0_7n"
    assert baseline["policy_slice"] == "v0_7n"
    assert config["allow_sign_flip_during_z_open_low_depth"] is True
    assert config["z_open_centering_depth_max_m"] == pytest.approx(0.001)
    assert candidate["final_post_adapter_xy_authority_config_sha256"] == baseline[
        "final_post_adapter_xy_authority_config_sha256"
    ]
    assert gate["passed"] is True
    assert gate["success_metric_changed"] is False
    assert gate["trainer_changed"] is False
    assert gate["heldout_21000_21049_accessed"] is False


def test_v07n_cli_offline_relabel_generates_nonclosure_artifacts(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_v07n_parent_chain(script, tmp_path)

    result = script.main(
        [
            "--scenario-profile",
            "v0_6",
            "--policy-slice",
            "v0_7n",
            "--offline-relabel-only",
            "--output-dir",
            str(tmp_path),
        ]
    )

    child_dir = tmp_path / script.V07N_CHILD_OUTPUT_DIRNAME
    evidence_manifest = script.read_json(tmp_path / "evidence_manifest.json")
    assert result == 0
    assert (child_dir / "z_open_xy_center_maintenance_gate_v0_7n.json").exists()
    assert evidence_manifest["policy_slice"] == "v0_7n"
    assert evidence_manifest["proof_runtime"] == script.V07N_SLICE_ID
    assert evidence_manifest["mvp2_closed"] is False
    assert evidence_manifest["heldout_21000_21049_accessed"] is False


def test_v07n_cli_calibration_presignal_generates_nonclosure_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_v07n_parent_chain(script, tmp_path)

    class FakeBackend:
        runtime_backend = "isaac_runtime"
        proof_runtime = script.ISAAC_PROOF_RUNTIME

        def __init__(self, **_: object) -> None:
            pass

        def run(self, *, manifest, output_dir, min_rollouts_per_policy, deterministic_profile, policy_artifacts):
            del deterministic_profile
            output_dir.mkdir(parents=True, exist_ok=True)
            trace_dir = output_dir / "isaac_runtime_heldout_rollout_traces"
            trace_dir.mkdir(parents=True, exist_ok=True)
            assert policy_artifacts["candidate"]["policy_slice"] == "v0_7n"
            assert policy_artifacts["baseline"]["policy_slice"] == "v0_7n"
            assert all(int(row["seed"]) < 21000 for row in manifest["scenarios"])
            baseline = _rollouts(6, total=min_rollouts_per_policy)
            candidate = _rollouts(10, total=min_rollouts_per_policy)
            baseline_paths = []
            candidate_paths = []
            for role, rollouts, paths in (
                ("baseline", baseline, baseline_paths),
                ("candidate", candidate, candidate_paths),
            ):
                for index, rollout in enumerate(rollouts):
                    trace_path = trace_dir / f"{role}_{index:04d}_{rollout['scenario_id']}.json"
                    script.write_json(trace_path, {"scenario": manifest["scenarios"][index], "summary": rollout})
                    paths.append(str(trace_path))
            return script.BackendResult(
                runtime_backend="isaac_runtime",
                proof_runtime=script.ISAAC_PROOF_RUNTIME,
                runtime_gate={
                    "passed": True,
                    "runtime_backend": "isaac_runtime",
                    "proof_runtime": script.ISAAC_PROOF_RUNTIME,
                },
                baseline_rollouts=baseline,
                candidate_rollouts=candidate,
                baseline_trace_paths=baseline_paths,
                candidate_trace_paths=candidate_paths,
                runtime_metadata={"runtime_backend": "isaac_runtime"},
            )

    monkeypatch.setattr(script, "IsaacConnectorInsertionEvaluatorBackend", FakeBackend)

    result = script.main(
        [
            "--scenario-profile",
            "v0_6",
            "--policy-slice",
            "v0_7n",
            "--calibration-presignal-only",
            "--output-dir",
            str(tmp_path),
        ]
    )

    child_dir = tmp_path / script.V07N_CHILD_OUTPUT_DIRNAME
    evidence_manifest = script.read_json(tmp_path / "evidence_manifest.json")
    gate = script.read_json(child_dir / "calibration_presignal_gate_v0_7n.json")
    compatibility_gate = script.read_json(tmp_path / "calibration_presignal_gate.json")
    assert result == 0
    assert gate["passed"] is True
    assert gate["policy_slice"] == "v0_7n"
    assert gate["calibration_opened"] is True
    assert gate["heldout_opened"] is False
    assert gate["mvp2_closed"] is False
    assert compatibility_gate["source_gate_path"] == (
        f"{script.V07N_CHILD_OUTPUT_DIRNAME}/calibration_presignal_gate_v0_7n.json"
    )
    assert evidence_manifest["policy_slice"] == "v0_7n"
    assert evidence_manifest["proof_runtime"] == script.V07N_SLICE_ID
    assert evidence_manifest["heldout_21000_21049_accessed"] is False


def test_v07o_builds_composed_xy_authority_slice(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_v07o_parent_chain(script, tmp_path)

    manifest = script.build_v07o_composed_xy_authority_slice(output_dir=tmp_path)

    child_dir = tmp_path / script.V07O_CHILD_OUTPUT_DIRNAME
    candidate = script.read_json(child_dir / "candidate_policy_artifact_v0_7o.json")
    baseline = script.read_json(child_dir / "baseline_policy_artifact_v0_7o.json")
    config = script.read_json(child_dir / "v0_7o_xy_authority_config.json")
    gate = script.read_json(child_dir / "composed_xy_authority_gate_v0_7o.json")
    assert manifest["policy_slice"] == "v0_7o"
    assert manifest["parent_policy_slice"] == "v0_7n"
    assert candidate["policy_slice"] == "v0_7o"
    assert baseline["policy_slice"] == "v0_7o"
    assert config["xy_authority_strategy"] == "composed_piecewise_plus_z_open_center_maintenance"
    assert config["parent_policy_slice"] == "v0_7n"
    assert config["allow_sign_flip_during_z_open_low_depth"] is True
    assert config["xy_authority_gain"] > 0.0
    assert config["xy_off_center_clip_abs"] > 0.0
    assert candidate["final_post_adapter_xy_authority_config_sha256"] == baseline[
        "final_post_adapter_xy_authority_config_sha256"
    ]
    assert gate["passed"] is True
    assert gate["success_metric_changed"] is False
    assert gate["trainer_changed"] is False
    assert gate["parent_piecewise_xy_authority_preserved"] is True
    assert gate["z_open_override_added"] is True
    assert gate["heldout_21000_21049_accessed"] is False


def test_v07o_cli_offline_relabel_generates_nonclosure_artifacts(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_v07o_parent_chain(script, tmp_path)

    result = script.main(
        [
            "--scenario-profile",
            "v0_6",
            "--policy-slice",
            "v0_7o",
            "--offline-relabel-only",
            "--output-dir",
            str(tmp_path),
        ]
    )

    child_dir = tmp_path / script.V07O_CHILD_OUTPUT_DIRNAME
    evidence_manifest = script.read_json(tmp_path / "evidence_manifest.json")
    assert result == 0
    assert (child_dir / "composed_xy_authority_gate_v0_7o.json").exists()
    assert evidence_manifest["policy_slice"] == "v0_7o"
    assert evidence_manifest["proof_runtime"] == script.V07O_SLICE_ID
    assert evidence_manifest["mvp2_closed"] is False
    assert evidence_manifest["heldout_21000_21049_accessed"] is False


def test_v07o_cli_calibration_presignal_generates_nonclosure_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_v07o_parent_chain(script, tmp_path)

    class FakeBackend:
        runtime_backend = "isaac_runtime"
        proof_runtime = script.ISAAC_PROOF_RUNTIME

        def __init__(self, **_: object) -> None:
            pass

        def run(self, *, manifest, output_dir, min_rollouts_per_policy, deterministic_profile, policy_artifacts):
            del deterministic_profile
            output_dir.mkdir(parents=True, exist_ok=True)
            trace_dir = output_dir / "isaac_runtime_heldout_rollout_traces"
            trace_dir.mkdir(parents=True, exist_ok=True)
            assert policy_artifacts["candidate"]["policy_slice"] == "v0_7o"
            assert policy_artifacts["baseline"]["policy_slice"] == "v0_7o"
            assert all(int(row["seed"]) < 21000 for row in manifest["scenarios"])
            baseline = _rollouts(6, total=min_rollouts_per_policy)
            candidate = _rollouts(10, total=min_rollouts_per_policy)
            baseline_paths = []
            candidate_paths = []
            for role, rollouts, paths in (
                ("baseline", baseline, baseline_paths),
                ("candidate", candidate, candidate_paths),
            ):
                for index, rollout in enumerate(rollouts):
                    trace_path = trace_dir / f"{role}_{index:04d}_{rollout['scenario_id']}.json"
                    script.write_json(trace_path, {"scenario": manifest["scenarios"][index], "summary": rollout})
                    paths.append(str(trace_path))
            return script.BackendResult(
                runtime_backend="isaac_runtime",
                proof_runtime=script.ISAAC_PROOF_RUNTIME,
                runtime_gate={
                    "passed": True,
                    "runtime_backend": "isaac_runtime",
                    "proof_runtime": script.ISAAC_PROOF_RUNTIME,
                },
                baseline_rollouts=baseline,
                candidate_rollouts=candidate,
                baseline_trace_paths=baseline_paths,
                candidate_trace_paths=candidate_paths,
                runtime_metadata={"runtime_backend": "isaac_runtime"},
            )

    monkeypatch.setattr(script, "IsaacConnectorInsertionEvaluatorBackend", FakeBackend)

    result = script.main(
        [
            "--scenario-profile",
            "v0_6",
            "--policy-slice",
            "v0_7o",
            "--calibration-presignal-only",
            "--output-dir",
            str(tmp_path),
        ]
    )

    child_dir = tmp_path / script.V07O_CHILD_OUTPUT_DIRNAME
    evidence_manifest = script.read_json(tmp_path / "evidence_manifest.json")
    gate = script.read_json(child_dir / "calibration_presignal_gate_v0_7o.json")
    compatibility_gate = script.read_json(tmp_path / "calibration_presignal_gate.json")
    assert result == 0
    assert gate["passed"] is True
    assert gate["policy_slice"] == "v0_7o"
    assert gate["calibration_opened"] is True
    assert gate["heldout_opened"] is False
    assert gate["mvp2_closed"] is False
    assert compatibility_gate["source_gate_path"] == (
        f"{script.V07O_CHILD_OUTPUT_DIRNAME}/calibration_presignal_gate_v0_7o.json"
    )
    assert evidence_manifest["policy_slice"] == "v0_7o"
    assert evidence_manifest["proof_runtime"] == script.V07O_SLICE_ID
    assert evidence_manifest["heldout_21000_21049_accessed"] is False


def _write_passed_v07o_calibration_gate(script: Any, output_dir: Path) -> None:
    _write_v07o_parent_chain(script, output_dir)
    script.write_json(
        output_dir / "train_generation_runtime_gate.json",
        {
            "passed": True,
            "runtime_backend": "isaac_runtime",
            "proof_runtime": "isaac_scripted_expert_train_generation_probe",
            "actual_train_generation_evidence": True,
            "training_trajectory_source": "isaac_runtime_scripted_expert_rollout",
            "generated_rollout_count": script.V06_TRAIN_GATE_ATTEMPT_COUNT,
            "generated_success_count": script.V06_TRAIN_GATE_SUCCESS_MINIMUM,
            "required_success_count": script.V06_TRAIN_GATE_SUCCESS_MINIMUM,
            "success_trace_cap": script.V06_TRAIN_GATE_ATTEMPT_COUNT,
            "generated_success_trace_paths": [],
            "generated_trace_paths": [],
        },
    )
    script.write_json(
        output_dir / "calibration_selection_report.json",
        {
            "selector_score_pre_registered": True,
            "same_adapter_used_for_baseline_and_candidate": True,
            "heldout_excluded": True,
            "selected_adapter_frozen_before_heldout": True,
            "calibration_only_selection_passed": True,
            "selected_action_adapter_id": "isaac_signed_xy_downward_servo_v0",
            "calibration_scenario_ids": [f"calibration_{seed}" for seed in range(20000, 20030)],
            "heldout_scenario_ids_observed": [],
        },
    )
    script.write_json(
        output_dir / "curation_manifest.json",
        {
            "items": [
                {"scenario_id": f"train_success_{seed}", "decision": "accepted"}
                for seed in range(19000, 19040)
            ]
        },
    )
    (output_dir / "baseline_uncurated_train.hdf5").write_bytes(b"test-baseline-train-view")
    (output_dir / "candidate_curated_train.hdf5").write_bytes(b"test-candidate-train-view")
    script.build_v07o_composed_xy_authority_slice(output_dir=output_dir)
    child_dir = output_dir / script.V07O_CHILD_OUTPUT_DIRNAME
    gate = {
        "schema_version": script.V07O_CALIBRATION_PRESIGNAL_SCHEMA_VERSION,
        "policy_slice": "v0_7o",
        "slice_id": script.V07O_SLICE_ID,
        "passed": True,
        "failure_reason": "",
        "heldout_allowed": True,
        "runtime_backend": "isaac_runtime",
        "proof_runtime": script.ISAAC_PROOF_RUNTIME,
        "baseline_calibration_success_count": 19,
        "candidate_calibration_success_count": 21,
        "baseline_calibration_rollout_count": 30,
        "candidate_calibration_rollout_count": 30,
        "baseline_calibration_success_rate": 0.633333333333,
        "candidate_calibration_success_rate": 0.7,
        "curated_vs_uncurated_calibration_uplift": 0.066666666667,
        "calibration_opened": True,
        "heldout_opened": False,
        "heldout_21000_21049_accessed": False,
        "mvp2_closed": False,
        "policy_uplift_proven": False,
    }
    gate["calibration_presignal_gate_sha256"] = script._sha256_payload_excluding(
        gate,
        "calibration_presignal_gate_sha256",
    )
    script.write_json(child_dir / "calibration_presignal_gate_v0_7o.json", gate)


def test_v07p_heldout_closure_requires_passed_v07o_calibration_gate(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_v07o_parent_chain(script, tmp_path)
    script.build_v07o_composed_xy_authority_slice(output_dir=tmp_path)
    manifest = script.read_json(tmp_path / "scenario_manifest.json")

    with pytest.raises(ValueError, match="missing_passed_v0_7o_calibration_presignal_gate"):
        script.run_v07p_heldout_closure_runtime(
            output_dir=tmp_path,
            manifest=manifest,
            device="cpu",
            headless=True,
            isaac_task="fake-task",
            max_steps=150,
            action_scale=1.0,
            min_rollouts_per_policy=20,
            bootstrap_iterations=20,
            bootstrap_seed=23,
        )


def test_v07p_cli_heldout_closure_uses_v07o_artifacts_and_can_close_with_fake_isaac(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_passed_v07o_calibration_gate(script, tmp_path)

    class FakeHeldoutBackend:
        runtime_backend = "isaac_runtime"
        proof_runtime = script.ISAAC_PROOF_RUNTIME

        def __init__(self, **_: object) -> None:
            pass

        def run(self, *, manifest, output_dir, min_rollouts_per_policy, deterministic_profile, policy_artifacts):
            del deterministic_profile
            output_dir.mkdir(parents=True, exist_ok=True)
            trace_dir = output_dir / "isaac_runtime_heldout_rollout_traces"
            trace_dir.mkdir(parents=True, exist_ok=True)
            assert policy_artifacts["candidate"]["policy_slice"] == "v0_7o"
            assert policy_artifacts["baseline"]["policy_slice"] == "v0_7o"
            heldout = [row for row in manifest["scenarios"] if row["split"] == "held_out"]
            seeds = [int(row["seed"]) for row in heldout]
            assert seeds == list(range(21000, 21050))
            rollout_count = max(int(min_rollouts_per_policy), len(heldout))
            baseline_rollouts = []
            candidate_rollouts = []
            baseline_paths = []
            candidate_paths = []
            for index in range(rollout_count):
                scenario = heldout[index % len(heldout)]
                for role, success_limit, rollouts, paths in (
                    ("baseline", 20, baseline_rollouts, baseline_paths),
                    ("candidate", 35, candidate_rollouts, candidate_paths),
                ):
                    success = index < success_limit
                    trace_path = trace_dir / f"{role}_{index:04d}_{scenario['scenario_id']}.json"
                    script.write_json(
                        trace_path,
                        {
                            "scenario": scenario,
                            "role": role,
                            "summary": {
                                "success": success,
                                "failure_reason": "" if success else "ENV_NATIVE_WINDOW_NOT_REACHED",
                            },
                            "trace": script._success_trace()
                            if success
                            else script._failure_trace("ENV_NATIVE_WINDOW_NOT_REACHED"),
                        },
                    )
                    paths.append(str(trace_path))
                    rollouts.append(
                        {
                            "rollout_id": f"{role}_heldout_{index:04d}",
                            "scenario_id": scenario["scenario_id"],
                            "seed": int(scenario["seed"]),
                            "success": success,
                            "env_native_rollout_success": success,
                            "failure_reason": "" if success else "ENV_NATIVE_WINDOW_NOT_REACHED",
                            "steps": 120,
                            "rollout_log_ref": str(trace_path),
                        }
                    )
            return script.BackendResult(
                runtime_backend="isaac_runtime",
                proof_runtime=script.ISAAC_PROOF_RUNTIME,
                runtime_gate={
                    "passed": True,
                    "runtime_backend": "isaac_runtime",
                    "proof_runtime": script.ISAAC_PROOF_RUNTIME,
                },
                baseline_rollouts=baseline_rollouts,
                candidate_rollouts=candidate_rollouts,
                baseline_trace_paths=baseline_paths,
                candidate_trace_paths=candidate_paths,
                runtime_metadata={"runtime_backend": "isaac_runtime"},
            )

    monkeypatch.setattr(script, "IsaacConnectorInsertionEvaluatorBackend", FakeHeldoutBackend)

    result = script.main(
        [
            "--scenario-profile",
            "v0_6",
            "--policy-slice",
            "v0_7o",
            "--heldout-closure-only",
            "--output-dir",
            str(tmp_path),
            "--rollouts-per-policy",
            "20",
            "--bootstrap-iterations",
            "50",
        ]
    )

    child_dir = tmp_path / script.V07P_CHILD_OUTPUT_DIRNAME
    evidence_manifest = script.read_json(tmp_path / "evidence_manifest.json")
    gate = script.read_json(child_dir / "heldout_closure_gate_v0_7p.json")
    assert result == 0
    assert gate["policy_slice"] == "v0_7o"
    assert gate["heldout_opened"] is True
    assert gate["heldout_21000_21049_accessed"] is True
    assert gate["baseline_success_rate"] == 0.4
    assert gate["candidate_success_rate"] == 0.7
    assert gate["curated_vs_uncurated_uplift"] == pytest.approx(0.3)
    assert gate["actual_rollouts_per_policy"] == 50
    assert gate["mvp2_closed"] is True
    assert evidence_manifest["proof_runtime"] == script.V07P_SLICE_ID
    assert evidence_manifest["mvp2_closed"] is True
    assert evidence_manifest["heldout_21000_21049_accessed"] is True


def _write_fake_v07p_heldout_shortfall_result(script: Any, output_dir: Path) -> None:
    child_dir = output_dir / script.V07P_CHILD_OUTPUT_DIRNAME
    trace_dir = child_dir / "isaac_runtime_heldout_rollout_traces"
    trace_dir.mkdir(parents=True, exist_ok=True)

    both_success = set(range(21000, 21034))
    candidate_only = {21034, 21035, 21036, 21037, 21038, 21039, 21040}
    near_seat_fail = {21041, 21042, 21043}
    under_insertion_fail = {21044, 21045, 21046, 21047, 21048}
    alignment_stall_fail = {21049}

    def trace_for(*, success: bool, failure_class: str | None = None) -> list[dict[str, Any]]:
        if success:
            return [
                {
                    "step": step,
                    "insertion_depth_m": 0.025,
                    "lateral_error_m": 0.0001,
                    "env_native_success": True,
                    "controller_action_diagnostics": {
                        "post_adapter_action_vector": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
                        "effective_behavior_state_phase_for_final_authority": "HOLD",
                    },
                }
                for step in range(10)
            ]
        if failure_class == "near_seat":
            return [
                {
                    "step": step,
                    "insertion_depth_m": 0.0249,
                    "lateral_error_m": 0.00005,
                    "env_native_success": step >= 6,
                    "controller_action_diagnostics": {
                        "post_adapter_action_vector": [0.0, 0.0, -0.16, 0.0, 0.0, 0.0, 1.0],
                        "effective_behavior_state_phase_for_final_authority": "HOLD",
                    },
                }
                for step in range(8)
            ]
        if failure_class == "alignment_stall":
            return [
                {
                    "step": step,
                    "insertion_depth_m": 0.0,
                    "lateral_error_m": 0.0002,
                    "env_native_success": False,
                    "controller_action_diagnostics": {
                        "post_adapter_action_vector": [0.05, 0.05, 0.0, 0.0, 0.0, 0.0, 1.0],
                        "effective_behavior_state_phase_for_final_authority": "ALIGN",
                    },
                }
                for step in range(8)
            ]
        return [
            {
                "step": step,
                "insertion_depth_m": 0.018,
                "lateral_error_m": 0.0002,
                "env_native_success": False,
                "controller_action_diagnostics": {
                    "post_adapter_action_vector": [0.0, 0.0, -0.16, 0.0, 0.0, 0.0, 1.0],
                    "effective_behavior_state_phase_for_final_authority": "DESCEND",
                },
            }
            for step in range(8)
        ]

    baseline_success_count = 0
    candidate_success_count = 0
    for index, seed in enumerate(range(21000, 21050)):
        baseline_success = seed in both_success
        candidate_success = seed in both_success or seed in candidate_only
        baseline_success_count += int(baseline_success)
        candidate_success_count += int(candidate_success)
        for role, success in (("baseline", baseline_success), ("candidate", candidate_success)):
            failure_class = None
            if not success and role == "candidate":
                if seed in near_seat_fail:
                    failure_class = "near_seat"
                elif seed in alignment_stall_fail:
                    failure_class = "alignment_stall"
                elif seed in under_insertion_fail:
                    failure_class = "under_insertion"
            trace = trace_for(success=success, failure_class=failure_class)
            summary = {
                "success": success,
                "env_native_rollout_success": success,
                "env_native_max_consecutive_success_steps": 10
                if success
                else sum(1 for row in trace if row["env_native_success"]),
                "failure_reason": "" if success else "ENV_NATIVE_STABILITY_WINDOW_NOT_REACHED",
                "steps": len(trace),
            }
            script.write_json(
                trace_dir / f"{role}_{index:04d}_held_out_{seed}_isaac_trace.json",
                {
                    "policy_role": role,
                    "scenario": {"scenario_id": f"held_out_{seed}", "split": "held_out", "seed": seed},
                    "summary": summary,
                    "trace": trace,
                },
            )

    gate = {
        "schema_version": script.V07P_HELDOUT_CLOSURE_SCHEMA_VERSION,
        "policy_slice": "v0_7o",
        "slice_id": script.V07P_SLICE_ID,
        "runtime_backend": "isaac_runtime",
        "proof_runtime": script.ISAAC_PROOF_RUNTIME,
        "actual_rollouts_per_policy": 50,
        "baseline_success_rate": baseline_success_count / 50,
        "candidate_success_rate": candidate_success_count / 50,
        "curated_vs_uncurated_uplift": (candidate_success_count - baseline_success_count) / 50,
        "heldout_opened": True,
        "heldout_21000_21049_accessed": True,
        "mvp2_closed": False,
        "policy_uplift_proven": False,
        "blockers": ["Existing MVP-2 learning validator did not produce proof-eligible positive uplift >= 0.20."],
    }
    gate["heldout_closure_gate_sha256"] = script._sha256_payload_excluding(
        gate,
        "heldout_closure_gate_sha256",
    )
    script.write_json(child_dir / "heldout_closure_gate_v0_7p.json", gate)


def test_v07q_heldout_shortfall_diagnosis_requires_v07p_gate(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    with pytest.raises(ValueError, match="missing_v0_7p_heldout_closure_gate"):
        script.build_v07q_heldout_shortfall_diagnosis(output_dir=tmp_path)


def test_v07q_cli_classifies_heldout_shortfall_and_marks_post_heldout_integrity(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_fake_v07p_heldout_shortfall_result(script, tmp_path)

    result = script.main(
        [
            "--scenario-profile",
            "v0_6",
            "--policy-slice",
            "v0_7o",
            "--heldout-shortfall-diagnosis-only",
            "--output-dir",
            str(tmp_path),
        ]
    )

    child_dir = tmp_path / script.V07Q_CHILD_OUTPUT_DIRNAME
    diagnosis = script.read_json(child_dir / "heldout_shortfall_diagnosis_v0_7q.json")
    marker = script.read_json(tmp_path / "post_heldout_tuning_marker.json")
    evidence_manifest = script.read_json(tmp_path / "evidence_manifest.json")
    assert result == 0
    assert diagnosis["mvp2_closed"] is False
    assert diagnosis["proof_authority"] is False
    assert diagnosis["close_shortfall_success_count"] == 3
    assert diagnosis["paired_outcome_counts"] == {
        "B1_C1": 34,
        "B0_C1": 7,
        "B1_C0": 0,
        "B0_C0": 9,
    }
    assert diagnosis["candidate_failure_class_counts"]["NEAR_SEAT_HOLD_WINDOW_SHORT"] == 3
    assert diagnosis["candidate_failure_class_counts"]["UNDER_INSERTION_WITH_GOOD_CENTERING"] == 5
    assert diagnosis["candidate_failure_class_counts"]["ALIGNMENT_STALL_NO_DESCENT"] == 1
    assert diagnosis["recommended_downstream_slice"] == "v0_8a_fresh_seat_window_authority_slice"
    assert diagnosis["same_heldout_reuse_allowed_for_closure"] is False
    assert marker["same_heldout_reuse_allowed_for_closure"] is False
    assert marker["fresh_slice_required"] is True
    assert evidence_manifest["proof_runtime"] == script.V07Q_SLICE_ID
    assert evidence_manifest["heldout_21000_21049_accessed"] is True


def _write_v08a_parent_artifacts(script: Any, output_dir: Path) -> None:
    _write_v07o_parent_chain(script, output_dir)
    script.build_v07o_composed_xy_authority_slice(output_dir=output_dir)
    trace_dir = output_dir / "v0_8a_train_success_traces"
    trace_dir.mkdir(parents=True, exist_ok=True)

    trace_paths = []
    for index, (first_z_step, first_success_step) in enumerate(((63, 115), (81, 136))):
        path = trace_dir / f"train_success_{index}.json"
        trace = [
            {
                "step": step,
                "seed": 19000 + index,
                "lateral_error_m": 0.0004,
                "insertion_depth_m": 0.010 if step < first_success_step else 0.025,
                "env_native_success": step >= first_success_step,
                "normalized_action": [
                    0.0,
                    0.0,
                    -0.16 if step >= first_z_step else 0.0,
                    0.0,
                    0.0,
                    0.0,
                    1.0,
                ],
            }
            for step in range(140)
        ]
        script.write_json(
            path,
            {
                "scenario": {"scenario_id": f"train_success_{19000 + index}", "seed": 19000 + index},
                "summary": {"success": True, "env_native_rollout_success": True},
                "trace": trace,
            },
        )
        trace_paths.append(str(path))

    script.write_json(
        output_dir / "train_generation_runtime_gate.json",
        {
            "passed": True,
            "runtime_backend": "isaac_runtime",
            "proof_runtime": "isaac_scripted_expert_train_generation_probe",
            "actual_train_generation_evidence": True,
            "training_trajectory_source": "isaac_runtime_scripted_expert_rollout",
            "generated_rollout_count": script.V06_TRAIN_GATE_ATTEMPT_COUNT,
            "generated_success_count": script.V06_TRAIN_GATE_SUCCESS_MINIMUM,
            "required_success_count": script.V06_TRAIN_GATE_SUCCESS_MINIMUM,
            "success_trace_cap": script.V06_TRAIN_GATE_ATTEMPT_COUNT,
            "generated_success_trace_paths": trace_paths,
            "generated_trace_paths": trace_paths,
            "heldout_21000_21049_accessed": False,
        },
    )
    script.write_json(
        output_dir / "post_heldout_tuning_marker.json",
        {
            "schema_version": script.V07Q_DIAGNOSIS_SCHEMA_VERSION,
            "policy_slice": "v0_7o",
            "slice_id": script.V07Q_SLICE_ID,
            "source_heldout_closure_gate_sha256": "fake-heldout-gate-sha",
            "recommended_downstream_slice": "v0_8a_fresh_seat_window_authority_slice",
            "fresh_slice_required": True,
            "same_heldout_reuse_allowed_for_closure": False,
            "heldout_21000_21049_accessed": True,
            "mvp2_closed": False,
            "policy_uplift_proven": False,
        },
    )
    script.write_json(
        output_dir / "calibration_selection_report.json",
        {
            "schema_version": "rdf_mvp2c_calibration_selector_report_v0.1.0",
            "calibration_only_selection_passed": True,
            "selector_score_pre_registered": True,
            "same_adapter_used_for_baseline_and_candidate": True,
            "heldout_excluded": True,
            "selected_adapter_frozen_before_heldout": True,
            "calibration_scenario_ids": [f"calibration_{seed}" for seed in range(20000, 20030)],
            "selected_action_adapter_id": "isaac_signed_xy_downward_servo_v0",
        },
    )
    script.write_json(
        output_dir / "curation_manifest.json",
        {
            "schema_version": "rdf_mvp2c_curation_manifest_v0.1.0",
            "items": [
                {"scenario_id": f"train_success_{seed}", "accepted": True}
                for seed in range(19000, 19040)
            ],
        },
    )
    (output_dir / "baseline_uncurated_train.hdf5").write_bytes(b"test-baseline-train-view")
    (output_dir / "candidate_curated_train.hdf5").write_bytes(b"test-candidate-train-view")


def test_v08a_requires_v07q_post_heldout_marker(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    with pytest.raises(ValueError, match="missing_v0_7q_post_heldout_marker"):
        script.build_v08a_fresh_seat_window_authority_slice(output_dir=tmp_path)


def test_v08a_builds_fresh_manifest_and_peer_fair_policy_artifacts(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_v08a_parent_artifacts(script, tmp_path)

    manifest = script.build_v08a_fresh_seat_window_authority_slice(output_dir=tmp_path)

    child_dir = tmp_path / script.V08A_CHILD_OUTPUT_DIRNAME
    candidate = script.read_json(child_dir / "candidate_policy_artifact_v0_8a.json")
    baseline = script.read_json(child_dir / "baseline_policy_artifact_v0_8a.json")
    config = script.read_json(child_dir / "v0_8a_seat_window_authority_config.json")
    calibration = manifest["fresh_split_manifest"]["calibration"]
    heldout = manifest["fresh_split_manifest"]["held_out"]
    assert manifest["policy_slice"] == "v0_8a"
    assert manifest["parent_policy_slice"] == "v0_7o"
    assert candidate["policy_slice"] == "v0_8a"
    assert baseline["policy_slice"] == "v0_8a"
    assert candidate["seat_window_authority_config_sha256"] == baseline[
        "seat_window_authority_config_sha256"
    ]
    assert config["latest_z_open_step"] == 81
    assert config["train_success_first_z_step_max"] == 81
    assert config["train_success_first_env_success_step_max"] == 136
    assert calibration["seed_range"] == [23000, 23029]
    assert heldout["seed_range"] == [24000, 24049]
    assert manifest["burned_heldout_seed_range"] == [21000, 21049]
    assert manifest["heldout_21000_21049_accessed"] is True
    assert manifest["fresh_heldout_24000_24049_accessed"] is False
    assert candidate["fresh_heldout_24000_24049_accessed"] is False


def test_v08a_cli_parses_fresh_seat_window_authority_flag(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    args = script.parse_args(
        [
            "--scenario-profile",
            "v0_6",
            "--policy-slice",
            "v0_8a",
            "--fresh-seat-window-authority-only",
            "--output-dir",
            str(tmp_path),
        ]
    )

    assert args.policy_slice == "v0_8a"
    assert args.fresh_seat_window_authority_only is True


def test_v08a_cli_runs_fresh_calibration_then_fresh_heldout_with_fake_isaac(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_v08a_parent_artifacts(script, tmp_path)

    seen_seed_sets: list[list[int]] = []

    class FakeFreshBackend:
        runtime_backend = "isaac_runtime"
        proof_runtime = script.ISAAC_PROOF_RUNTIME

        def __init__(self, **_: object) -> None:
            pass

        def run(self, *, manifest, output_dir, min_rollouts_per_policy, deterministic_profile, policy_artifacts):
            del deterministic_profile
            output_dir.mkdir(parents=True, exist_ok=True)
            trace_dir = output_dir / "fake_isaac_fresh_traces"
            trace_dir.mkdir(parents=True, exist_ok=True)
            scenarios = [row for row in manifest["scenarios"] if row["split"] == "held_out"]
            seeds = [int(row["seed"]) for row in scenarios]
            seen_seed_sets.append(seeds)
            assert policy_artifacts["candidate"]["policy_slice"] == "v0_8a"
            assert policy_artifacts["baseline"]["policy_slice"] == "v0_8a"
            assert not any(21000 <= seed <= 21049 for seed in seeds)
            if seeds == list(range(23000, 23030)):
                baseline_success_limit = 10
                candidate_success_limit = 25
                rollout_count = max(int(min_rollouts_per_policy), len(scenarios))
            else:
                assert seeds == list(range(24000, 24050))
                baseline_success_limit = 30
                candidate_success_limit = 50
                rollout_count = max(int(min_rollouts_per_policy), len(scenarios))

            baseline_rollouts = []
            candidate_rollouts = []
            baseline_paths = []
            candidate_paths = []
            for index in range(rollout_count):
                scenario = scenarios[index % len(scenarios)]
                for role, success_limit, rollouts, paths in (
                    ("baseline", baseline_success_limit, baseline_rollouts, baseline_paths),
                    ("candidate", candidate_success_limit, candidate_rollouts, candidate_paths),
                ):
                    success = index < success_limit
                    trace_path = trace_dir / f"{role}_{index:04d}_{scenario['scenario_id']}.json"
                    script.write_json(
                        trace_path,
                        {
                            "scenario": scenario,
                            "role": role,
                            "summary": {
                                "success": success,
                                "failure_reason": "" if success else "ENV_NATIVE_WINDOW_NOT_REACHED",
                            },
                            "trace": script._success_trace()
                            if success
                            else script._failure_trace("ENV_NATIVE_WINDOW_NOT_REACHED"),
                        },
                    )
                    paths.append(str(trace_path))
                    rollouts.append(
                        {
                            "rollout_id": f"{role}_fresh_{index:04d}",
                            "scenario_id": scenario["scenario_id"],
                            "seed": int(scenario["seed"]),
                            "success": success,
                            "env_native_rollout_success": success,
                            "failure_reason": "" if success else "ENV_NATIVE_WINDOW_NOT_REACHED",
                            "steps": 120,
                            "rollout_log_ref": str(trace_path),
                        }
                    )
            return script.BackendResult(
                runtime_backend="isaac_runtime",
                proof_runtime=script.ISAAC_PROOF_RUNTIME,
                runtime_gate={
                    "passed": True,
                    "runtime_backend": "isaac_runtime",
                    "proof_runtime": script.ISAAC_PROOF_RUNTIME,
                },
                baseline_rollouts=baseline_rollouts,
                candidate_rollouts=candidate_rollouts,
                baseline_trace_paths=baseline_paths,
                candidate_trace_paths=candidate_paths,
                runtime_metadata={"runtime_backend": "isaac_runtime"},
            )

    monkeypatch.setattr(script, "IsaacConnectorInsertionEvaluatorBackend", FakeFreshBackend)

    result = script.main(
        [
            "--scenario-profile",
            "v0_6",
            "--policy-slice",
            "v0_8a",
            "--fresh-seat-window-authority-only",
            "--output-dir",
            str(tmp_path),
            "--rollouts-per-policy",
            "20",
            "--bootstrap-iterations",
            "50",
        ]
    )

    child_dir = tmp_path / script.V08A_CHILD_OUTPUT_DIRNAME
    evidence_manifest = script.read_json(tmp_path / "evidence_manifest.json")
    closure_gate = script.read_json(child_dir / "heldout_closure_gate_v0_8a.json")
    assert result == 0
    assert seen_seed_sets == [list(range(23000, 23030)), list(range(24000, 24050))]
    assert closure_gate["policy_slice"] == "v0_8a"
    assert closure_gate["heldout_opened"] is True
    assert closure_gate["fresh_heldout_24000_24049_accessed"] is True
    assert closure_gate["heldout_21000_21049_accessed"] is False
    assert closure_gate["mvp2_closed"] is True
    assert closure_gate["baseline_success_rate"] == pytest.approx(0.6)
    assert closure_gate["candidate_success_rate"] == pytest.approx(1.0)
    assert evidence_manifest["proof_runtime"] == script.V08A_SLICE_ID
    assert evidence_manifest["mvp2_closed"] is True
    assert evidence_manifest["heldout_21000_21049_accessed"] is False
    assert evidence_manifest["fresh_heldout_24000_24049_accessed"] is True


def _write_v08b_parent_artifacts(script: Any, output_dir: Path) -> None:
    _write_v08a_parent_artifacts(script, output_dir)
    script.build_v08a_fresh_seat_window_authority_slice(output_dir=output_dir)
    child_dir = output_dir / script.V08A_CHILD_OUTPUT_DIRNAME
    gate = {
        "schema_version": script.V08A_HELDOUT_CLOSURE_SCHEMA_VERSION,
        "policy_slice": "v0_8a",
        "slice_id": script.V08A_SLICE_ID,
        "parent_policy_slice": "v0_7o",
        "runtime_backend": "isaac_runtime",
        "heldout_opened": True,
        "heldout_21000_21049_accessed": False,
        "fresh_calibration_23000_23029_accessed": True,
        "fresh_heldout_24000_24049_accessed": True,
        "same_heldout_reuse_allowed_for_closure": False,
        "actual_rollouts_per_policy": 50,
        "baseline_success_rate": 0.76,
        "candidate_success_rate": 0.90,
        "curated_vs_uncurated_uplift": 0.14,
        "mvp2_closed": False,
        "mvp2c_close_minimum_passed": False,
        "policy_uplift_proven": False,
        "proof_eligible": False,
        "blockers": ["curated_vs_uncurated_uplift_below_close_minimum"],
    }
    gate["heldout_closure_gate_sha256"] = script._sha256_payload_excluding(
        gate,
        "heldout_closure_gate_sha256",
    )
    script.write_json(child_dir / "heldout_closure_gate_v0_8a.json", gate)
    script.write_json(output_dir / "heldout_closure_gate.json", gate)


def test_v08b_requires_v08a_failed_closure_gate(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_v08a_parent_artifacts(script, tmp_path)
    script.build_v08a_fresh_seat_window_authority_slice(output_dir=tmp_path)

    with pytest.raises(ValueError, match="missing_v0_8a_failed_heldout_gate"):
        script.build_v08b_scenario_aware_seat_window_authority_slice(output_dir=tmp_path)


def test_v08b_builds_fresh_manifest_and_peer_fair_policy_artifacts(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_v08b_parent_artifacts(script, tmp_path)

    manifest = script.build_v08b_scenario_aware_seat_window_authority_slice(output_dir=tmp_path)

    child_dir = tmp_path / script.V08B_CHILD_OUTPUT_DIRNAME
    candidate = script.read_json(child_dir / "candidate_policy_artifact_v0_8b.json")
    baseline = script.read_json(child_dir / "baseline_policy_artifact_v0_8b.json")
    config = script.read_json(child_dir / "v0_8b_seat_window_authority_config.json")
    calibration = manifest["fresh_split_manifest"]["calibration"]
    heldout = manifest["fresh_split_manifest"]["held_out"]
    assert manifest["policy_slice"] == "v0_8b"
    assert manifest["parent_policy_slice"] == "v0_8a"
    assert candidate["policy_slice"] == "v0_8b"
    assert baseline["policy_slice"] == "v0_8b"
    assert candidate["seat_window_authority_config_sha256"] == baseline[
        "seat_window_authority_config_sha256"
    ]
    assert config["seat_window_authority_id"] == "scenario_aware_seat_window_authority_v0_8b"
    assert config["scenario_aware_deadline_step"] == 74
    assert config["latest_z_open_step_train_max"] == 81
    assert config["heldout_24000_24049_used_for_parameter_derivation"] is False
    assert calibration["seed_range"] == [25000, 25029]
    assert heldout["seed_range"] == [26000, 26049]
    assert manifest["burned_heldout_seed_ranges"] == [[21000, 21049], [24000, 24049]]
    assert manifest["fresh_heldout_26000_26049_accessed"] is False
    assert candidate["fresh_heldout_26000_26049_accessed"] is False


def test_v08b_cli_parses_scenario_aware_seat_window_flag(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    args = script.parse_args(
        [
            "--scenario-profile",
            "v0_6",
            "--policy-slice",
            "v0_8b",
            "--scenario-aware-seat-window-authority-only",
            "--output-dir",
            str(tmp_path),
        ]
    )

    assert args.policy_slice == "v0_8b"
    assert args.scenario_aware_seat_window_authority_only is True


def test_v08b_cli_runs_fresh_calibration_then_fresh_heldout_with_fake_isaac(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_v08b_parent_artifacts(script, tmp_path)

    seen_seed_sets: list[list[int]] = []

    class FakeScenarioAwareBackend:
        runtime_backend = "isaac_runtime"
        proof_runtime = script.ISAAC_PROOF_RUNTIME

        def __init__(self, **_: object) -> None:
            pass

        def run(self, *, manifest, output_dir, min_rollouts_per_policy, deterministic_profile, policy_artifacts):
            del deterministic_profile
            output_dir.mkdir(parents=True, exist_ok=True)
            trace_dir = output_dir / "fake_isaac_v08b_traces"
            trace_dir.mkdir(parents=True, exist_ok=True)
            scenarios = [row for row in manifest["scenarios"] if row["split"] == "held_out"]
            seeds = [int(row["seed"]) for row in scenarios]
            seen_seed_sets.append(seeds)
            assert policy_artifacts["candidate"]["policy_slice"] == "v0_8b"
            assert policy_artifacts["baseline"]["policy_slice"] == "v0_8b"
            assert not any(21000 <= seed <= 21049 for seed in seeds)
            assert not any(24000 <= seed <= 24049 for seed in seeds)
            if seeds == list(range(25000, 25030)):
                baseline_success_limit = 10
                candidate_success_limit = 25
                rollout_count = max(int(min_rollouts_per_policy), len(scenarios))
            else:
                assert seeds == list(range(26000, 26050))
                baseline_success_limit = 30
                candidate_success_limit = 50
                rollout_count = max(int(min_rollouts_per_policy), len(scenarios))

            baseline_rollouts = []
            candidate_rollouts = []
            baseline_paths = []
            candidate_paths = []
            for index in range(rollout_count):
                scenario = scenarios[index % len(scenarios)]
                for role, success_limit, rollouts, paths in (
                    ("baseline", baseline_success_limit, baseline_rollouts, baseline_paths),
                    ("candidate", candidate_success_limit, candidate_rollouts, candidate_paths),
                ):
                    success = index < success_limit
                    trace_path = trace_dir / f"{role}_{index:04d}_{scenario['scenario_id']}.json"
                    script.write_json(
                        trace_path,
                        {
                            "scenario": scenario,
                            "role": role,
                            "summary": {
                                "success": success,
                                "failure_reason": "" if success else "ENV_NATIVE_WINDOW_NOT_REACHED",
                            },
                            "trace": script._success_trace()
                            if success
                            else script._failure_trace("ENV_NATIVE_WINDOW_NOT_REACHED"),
                        },
                    )
                    paths.append(str(trace_path))
                    rollouts.append(
                        {
                            "rollout_id": f"{role}_v08b_{index:04d}",
                            "scenario_id": scenario["scenario_id"],
                            "seed": int(scenario["seed"]),
                            "success": success,
                            "env_native_rollout_success": success,
                            "failure_reason": "" if success else "ENV_NATIVE_WINDOW_NOT_REACHED",
                            "steps": 120,
                            "rollout_log_ref": str(trace_path),
                        }
                    )
            return script.BackendResult(
                runtime_backend="isaac_runtime",
                proof_runtime=script.ISAAC_PROOF_RUNTIME,
                runtime_gate={
                    "passed": True,
                    "runtime_backend": "isaac_runtime",
                    "proof_runtime": script.ISAAC_PROOF_RUNTIME,
                },
                baseline_rollouts=baseline_rollouts,
                candidate_rollouts=candidate_rollouts,
                baseline_trace_paths=baseline_paths,
                candidate_trace_paths=candidate_paths,
                runtime_metadata={"runtime_backend": "isaac_runtime"},
            )

    monkeypatch.setattr(script, "IsaacConnectorInsertionEvaluatorBackend", FakeScenarioAwareBackend)

    result = script.main(
        [
            "--scenario-profile",
            "v0_6",
            "--policy-slice",
            "v0_8b",
            "--scenario-aware-seat-window-authority-only",
            "--output-dir",
            str(tmp_path),
            "--rollouts-per-policy",
            "20",
            "--bootstrap-iterations",
            "50",
        ]
    )

    child_dir = tmp_path / script.V08B_CHILD_OUTPUT_DIRNAME
    evidence_manifest = script.read_json(tmp_path / "evidence_manifest.json")
    closure_gate = script.read_json(child_dir / "heldout_closure_gate_v0_8b.json")
    assert result == 0
    assert seen_seed_sets == [list(range(25000, 25030)), list(range(26000, 26050))]
    assert closure_gate["policy_slice"] == "v0_8b"
    assert closure_gate["heldout_opened"] is True
    assert closure_gate["fresh_heldout_26000_26049_accessed"] is True
    assert closure_gate["fresh_heldout_24000_24049_accessed"] is False
    assert closure_gate["heldout_21000_21049_accessed"] is False
    assert closure_gate["mvp2_closed"] is True
    assert closure_gate["baseline_success_rate"] == pytest.approx(0.6)
    assert closure_gate["candidate_success_rate"] == pytest.approx(1.0)
    assert evidence_manifest["proof_runtime"] == script.V08B_SLICE_ID
    assert evidence_manifest["mvp2_closed"] is True
    assert evidence_manifest["fresh_heldout_26000_26049_accessed"] is True


def _write_fake_v08b_heldout_shortfall_result(
    script: Any,
    output_dir: Path,
    *,
    omit_candidate_trace: bool = False,
) -> None:
    child_dir = output_dir / script.V08B_CHILD_OUTPUT_DIRNAME
    trace_dir = child_dir / "isaac_runtime_fresh_heldout_v0_8b" / "isaac_runtime_heldout_rollout_traces"
    trace_dir.mkdir(parents=True, exist_ok=True)

    baseline_success_count = 38
    candidate_success_count = 44
    failure_classes = {
        26007: "late",
        26008: "centered_under_depth",
        26009: "off_center_no_capture",
        26034: "centered_under_depth",
        26043: "off_center_no_capture",
        26047: "late",
    }

    def trace_for(*, success: bool, failure_class: str | None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        if success:
            rows = [
                {
                    "step": step,
                    "insertion_depth_m": 0.025,
                    "lateral_error_m": 0.00005,
                    "env_native_success": step >= 2,
                    "normalized_action": [0.0, 0.0, -0.16, 0.0, 0.0, 0.0],
                    "controller_action_diagnostics": {
                        "seat_window_authority_applied": step < 4,
                    },
                }
                for step in range(12)
            ]
            return (
                {
                    "success": True,
                    "env_native_rollout_success": True,
                    "env_native_first_success_step": 2,
                    "env_native_max_consecutive_success_steps": 10,
                    "failure_reason": "",
                    "steps": len(rows),
                },
                rows,
            )
        if failure_class == "late":
            rows = [
                {
                    "step": step,
                    "insertion_depth_m": 0.0249,
                    "lateral_error_m": 0.0001,
                    "env_native_success": step >= 4,
                    "normalized_action": [0.0, 0.0, -0.16, 0.0, 0.0, 0.0],
                    "controller_action_diagnostics": {
                        "seat_window_authority_applied": True,
                    },
                }
                for step in range(8)
            ]
            return (
                {
                    "success": False,
                    "env_native_rollout_success": False,
                    "env_native_first_success_step": 144,
                    "env_native_max_consecutive_success_steps": 4,
                    "failure_reason": "ENV_NATIVE_STABILITY_WINDOW_NOT_REACHED",
                    "steps": len(rows),
                },
                rows,
            )
        if failure_class == "centered_under_depth":
            rows = [
                {
                    "step": step,
                    "insertion_depth_m": 0.022 if step >= 60 else 0.0,
                    "lateral_error_m": 0.0003,
                    "env_native_success": False,
                    "normalized_action": [0.0, 0.0, -0.16, 0.0, 0.0, 0.0],
                    "controller_action_diagnostics": {
                        "seat_window_authority_applied": True,
                    },
                }
                for step in range(68)
            ]
            return (
                {
                    "success": False,
                    "env_native_rollout_success": False,
                    "env_native_first_success_step": None,
                    "env_native_max_consecutive_success_steps": 0,
                    "failure_reason": "ENV_NATIVE_STABILITY_WINDOW_NOT_REACHED",
                    "steps": len(rows),
                },
                rows,
            )
        rows = [
            {
                "step": step,
                "insertion_depth_m": 0.0,
                "lateral_error_m": 0.0024,
                "env_native_success": False,
                "normalized_action": [0.0, 0.0, -0.16, 0.0, 0.0, 0.0],
                "controller_action_diagnostics": {
                    "seat_window_authority_applied": True,
                },
            }
            for step in range(67)
        ]
        return (
            {
                "success": False,
                "env_native_rollout_success": False,
                "env_native_first_success_step": None,
                "env_native_max_consecutive_success_steps": 0,
                "failure_reason": "ENV_NATIVE_STABILITY_WINDOW_NOT_REACHED",
                "steps": len(rows),
            },
            rows,
        )

    for index, seed in enumerate(range(26000, 26050)):
        baseline_success = index < baseline_success_count
        candidate_success = seed not in failure_classes
        for role, success in (("baseline", baseline_success), ("candidate", candidate_success)):
            if omit_candidate_trace and role == "candidate" and seed == 26049:
                continue
            failure_class = failure_classes.get(seed) if role == "candidate" else None
            summary, trace = trace_for(success=success, failure_class=failure_class)
            script.write_json(
                trace_dir / f"{role}_{index:04d}_held_out_{seed}_isaac_trace.json",
                {
                    "policy_role": role,
                    "scenario": {
                        "scenario_id": f"held_out_{seed}",
                        "seed": seed,
                        "split": "held_out",
                    },
                    "summary": summary,
                    "trace": trace,
                },
            )

    config = {
        "schema_version": script.V08B_SEAT_WINDOW_AUTHORITY_CONFIG_SCHEMA_VERSION,
        "policy_slice": "v0_8b",
        "slice_id": script.V08B_SLICE_ID,
        "seat_window_authority_id": script.V08B_SEAT_WINDOW_AUTHORITY_ID,
        "scenario_aware_deadline_step": 74,
        "z_open_centering_lateral_m": 0.006,
    }
    config["seat_window_authority_config_sha256"] = script._sha256_payload_excluding(
        config,
        "seat_window_authority_config_sha256",
    )
    script.write_json(child_dir / "v0_8b_seat_window_authority_config.json", config)
    gate = {
        "schema_version": script.V08B_HELDOUT_CLOSURE_SCHEMA_VERSION,
        "policy_slice": "v0_8b",
        "slice_id": script.V08B_SLICE_ID,
        "runtime_backend": "isaac_runtime",
        "proof_runtime": script.ISAAC_PROOF_RUNTIME,
        "actual_rollouts_per_policy": 50,
        "baseline_success_rate": baseline_success_count / 50,
        "candidate_success_rate": candidate_success_count / 50,
        "curated_vs_uncurated_uplift": (candidate_success_count - baseline_success_count) / 50,
        "heldout_opened": True,
        "fresh_heldout_26000_26049_accessed": True,
        "fresh_heldout_24000_24049_accessed": False,
        "heldout_21000_21049_accessed": False,
        "mvp2_closed": False,
        "mvp2c_close_minimum_passed": False,
        "policy_uplift_proven": False,
        "proof_eligible": False,
    }
    gate["heldout_closure_gate_sha256"] = script._sha256_payload_excluding(
        gate,
        "heldout_closure_gate_sha256",
    )
    script.write_json(child_dir / "heldout_closure_gate_v0_8b.json", gate)


def test_v08c_requires_v08b_failed_closure_gate(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    with pytest.raises(ValueError, match="missing_v0_8b_heldout_closure_gate"):
        script.build_v08c_heldout_shortfall_diagnosis(output_dir=tmp_path)


def test_v08c_incomplete_candidate_traces_fail_closed(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_fake_v08b_heldout_shortfall_result(script, tmp_path, omit_candidate_trace=True)

    with pytest.raises(ValueError, match="v0_8c_requires_100_v0_8b_heldout_traces"):
        script.build_v08c_heldout_shortfall_diagnosis(output_dir=tmp_path)


def test_v08c_classifies_v08b_shortfall_taxonomy(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_fake_v08b_heldout_shortfall_result(script, tmp_path)

    diagnosis = script.build_v08c_heldout_shortfall_diagnosis(output_dir=tmp_path)

    taxonomy = diagnosis["failure_taxonomy"]
    assert diagnosis["policy_slice"] == "v0_8c"
    assert diagnosis["source_policy_slice"] == "v0_8b"
    assert diagnosis["mvp2_closed"] is False
    assert diagnosis["proof_authority"] is False
    assert diagnosis["candidate_failures_total"] == 6
    assert taxonomy["late_seat_window_shortfall"]["count"] == 2
    assert taxonomy["centered_under_depth_progress"]["count"] == 2
    assert taxonomy["off_center_no_capture"]["count"] == 2
    assert taxonomy["unclassified"]["count"] == 0
    assert diagnosis["burned_heldout_seed_ranges"] == [[21000, 21049], [24000, 24049], [26000, 26049]]
    assert diagnosis["recommended_downstream_slice"] == "v0_8d_capture_conditioned_progress_authority"


def test_v08c_cli_runs_artifact_only_shortfall_diagnosis(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_fake_v08b_heldout_shortfall_result(script, tmp_path)

    result = script.main(
        [
            "--scenario-profile",
            "v0_6",
            "--policy-slice",
            "v0_8c",
            "--heldout-shortfall-diagnosis-only",
            "--output-dir",
            str(tmp_path),
        ]
    )

    child_dir = tmp_path / script.V08C_CHILD_OUTPUT_DIRNAME
    diagnosis = script.read_json(child_dir / "v0_8c_shortfall_diagnosis.json")
    evidence_manifest = script.read_json(tmp_path / "evidence_manifest.json")
    assert result == 0
    assert diagnosis["runtime_backend"] == "offline_artifact_diagnosis"
    assert diagnosis["heldout_opened"] is False
    assert diagnosis["fresh_heldout_27000_27049_accessed"] is False
    assert evidence_manifest["proof_runtime"] == script.V08C_SLICE_ID
    assert evidence_manifest["mvp2_closed"] is False
    assert evidence_manifest["recommended_downstream_slice"] == (
        "v0_8d_capture_conditioned_progress_authority"
    )


def _write_v08d_parent_artifacts(script: Any, output_dir: Path) -> None:
    _write_v08b_parent_artifacts(script, output_dir)
    script.build_v08b_scenario_aware_seat_window_authority_slice(output_dir=output_dir)
    _write_fake_v08b_heldout_shortfall_result(script, output_dir)
    script.build_v08c_heldout_shortfall_diagnosis(output_dir=output_dir)


def test_v08d_requires_v08c_shortfall_diagnosis(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_v08b_parent_artifacts(script, tmp_path)
    script.build_v08b_scenario_aware_seat_window_authority_slice(output_dir=tmp_path)

    with pytest.raises(ValueError, match="missing_v0_8c_shortfall_diagnosis"):
        script.build_v08d_capture_conditioned_progress_authority_slice(output_dir=tmp_path)


def test_v08d_builds_capture_conditioned_manifest_and_peer_fair_artifacts(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_v08d_parent_artifacts(script, tmp_path)

    manifest = script.build_v08d_capture_conditioned_progress_authority_slice(output_dir=tmp_path)

    child_dir = tmp_path / script.V08D_CHILD_OUTPUT_DIRNAME
    candidate = script.read_json(child_dir / "candidate_policy_artifact_v0_8d.json")
    baseline = script.read_json(child_dir / "baseline_policy_artifact_v0_8d.json")
    config = script.read_json(child_dir / "v0_8d_capture_conditioned_progress_authority_config.json")
    calibration = manifest["fresh_split_manifest"]["calibration"]
    heldout = manifest["fresh_split_manifest"]["held_out"]

    assert manifest["policy_slice"] == "v0_8d"
    assert manifest["parent_policy_slice"] == "v0_8b"
    assert candidate["policy_slice"] == "v0_8d"
    assert baseline["policy_slice"] == "v0_8d"
    assert candidate["capture_conditioned_progress_authority_config_sha256"] == baseline[
        "capture_conditioned_progress_authority_config_sha256"
    ]
    assert config["capture_conditioned_progress_authority_id"] == (
        "capture_conditioned_progress_authority_v0_8d"
    )
    assert config["early_z_deadline_step"] == 68
    assert config["capture_prepare_start_step"] == 56
    assert config["capture_lateral_gate_m"] == 0.0035
    assert config["depth_progress_window_steps"] == 12
    assert config["minimum_depth_progress_m"] == 0.001
    assert calibration["seed_range"] == [26500, 26529]
    assert heldout["seed_range"] == [27000, 27049]
    assert manifest["burned_heldout_seed_ranges"] == [[21000, 21049], [24000, 24049], [26000, 26049]]
    assert manifest["fresh_heldout_27000_27049_accessed"] is False


def test_v08d_cli_parses_capture_conditioned_progress_flag(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    args = script.parse_args(
        [
            "--scenario-profile",
            "v0_6",
            "--policy-slice",
            "v0_8d",
            "--capture-conditioned-progress-authority-only",
            "--output-dir",
            str(tmp_path),
        ]
    )

    assert args.policy_slice == "v0_8d"
    assert args.capture_conditioned_progress_authority_only is True


def test_v08d_cli_runs_fresh_calibration_before_fresh_heldout_with_fake_isaac(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_v08d_parent_artifacts(script, tmp_path)

    seen_seed_sets: list[list[int]] = []

    class FakeCaptureConditionedBackend:
        runtime_backend = "isaac_runtime"
        proof_runtime = script.ISAAC_PROOF_RUNTIME

        def __init__(self, **_: object) -> None:
            pass

        def run(self, *, manifest, output_dir, min_rollouts_per_policy, deterministic_profile, policy_artifacts):
            del deterministic_profile
            output_dir.mkdir(parents=True, exist_ok=True)
            trace_dir = output_dir / "fake_isaac_v08d_traces"
            trace_dir.mkdir(parents=True, exist_ok=True)
            scenarios = [row for row in manifest["scenarios"] if row["split"] == "held_out"]
            seeds = [int(row["seed"]) for row in scenarios]
            seen_seed_sets.append(seeds)
            assert policy_artifacts["candidate"]["policy_slice"] == "v0_8d"
            assert policy_artifacts["baseline"]["policy_slice"] == "v0_8d"
            assert not any(21000 <= seed <= 21049 for seed in seeds)
            assert not any(24000 <= seed <= 24049 for seed in seeds)
            assert not any(26000 <= seed <= 26049 for seed in seeds)
            if seeds == list(range(26500, 26530)):
                baseline_success_limit = 20
                candidate_success_limit = 28
                rollout_count = max(int(min_rollouts_per_policy), len(scenarios))
            else:
                assert seeds == list(range(27000, 27050))
                baseline_success_limit = 30
                candidate_success_limit = 50
                rollout_count = max(int(min_rollouts_per_policy), len(scenarios))

            baseline_rollouts = []
            candidate_rollouts = []
            baseline_paths = []
            candidate_paths = []
            for index in range(rollout_count):
                scenario = scenarios[index % len(scenarios)]
                for role, success_limit, rollouts, paths, action_x in (
                    ("baseline", baseline_success_limit, baseline_rollouts, baseline_paths, 0.01),
                    ("candidate", candidate_success_limit, candidate_rollouts, candidate_paths, 0.02),
                ):
                    success = index < success_limit
                    trace_path = trace_dir / f"{role}_{index:04d}_{scenario['scenario_id']}.json"
                    script.write_json(
                        trace_path,
                        {
                            "scenario": scenario,
                            "policy_role": role,
                            "summary": {
                                "success": success,
                                "env_native_rollout_success": success,
                                "failure_reason": "" if success else "ENV_NATIVE_WINDOW_NOT_REACHED",
                            },
                            "trace": [
                                {
                                    "step": step,
                                    "insertion_depth_m": 0.025 if success and step >= 4 else 0.0,
                                    "lateral_error_m": 0.0002,
                                    "env_native_success": success and step >= 4,
                                    "normalized_action": [action_x, 0.0, -0.16, 0.0, 0.0, 0.0, 1.0],
                                    "controller_action_diagnostics": {
                                        "post_adapter_action_vector": [
                                            action_x,
                                            0.0,
                                            -0.16,
                                            0.0,
                                            0.0,
                                            0.0,
                                            1.0,
                                        ],
                                        "capture_conditioning_applied": True,
                                    },
                                }
                                for step in range(14)
                            ],
                        },
                    )
                    paths.append(str(trace_path))
                    rollouts.append(
                        {
                            "rollout_id": f"{role}_v08d_{index:04d}",
                            "scenario_id": scenario["scenario_id"],
                            "seed": int(scenario["seed"]),
                            "success": success,
                            "env_native_rollout_success": success,
                            "failure_reason": "" if success else "ENV_NATIVE_WINDOW_NOT_REACHED",
                            "steps": 120,
                            "rollout_log_ref": str(trace_path),
                        }
                    )
            return script.BackendResult(
                runtime_backend="isaac_runtime",
                proof_runtime=script.ISAAC_PROOF_RUNTIME,
                runtime_gate={
                    "passed": True,
                    "runtime_backend": "isaac_runtime",
                    "proof_runtime": script.ISAAC_PROOF_RUNTIME,
                },
                baseline_rollouts=baseline_rollouts,
                candidate_rollouts=candidate_rollouts,
                baseline_trace_paths=baseline_paths,
                candidate_trace_paths=candidate_paths,
                runtime_metadata={"runtime_backend": "isaac_runtime"},
            )

    monkeypatch.setattr(script, "IsaacConnectorInsertionEvaluatorBackend", FakeCaptureConditionedBackend)

    result = script.main(
        [
            "--scenario-profile",
            "v0_6",
            "--policy-slice",
            "v0_8d",
            "--capture-conditioned-progress-authority-only",
            "--output-dir",
            str(tmp_path),
            "--rollouts-per-policy",
            "20",
            "--bootstrap-iterations",
            "50",
        ]
    )

    child_dir = tmp_path / script.V08D_CHILD_OUTPUT_DIRNAME
    evidence_manifest = script.read_json(tmp_path / "evidence_manifest.json")
    calibration_gate = script.read_json(child_dir / "calibration_presignal_gate_v0_8d.json")
    closure_gate = script.read_json(child_dir / "heldout_closure_gate_v0_8d.json")

    assert result == 0
    assert seen_seed_sets == [list(range(26500, 26530)), list(range(27000, 27050))]
    assert calibration_gate["passed"] is True
    assert calibration_gate["candidate_failures_total"] == 2
    assert calibration_gate["candidate_baseline_success_gap"] == pytest.approx(8 / 30)
    assert calibration_gate["attribution_preservation_gate_passed"] is True
    assert calibration_gate["fresh_heldout_27000_27049_accessed"] is False
    assert closure_gate["policy_slice"] == "v0_8d"
    assert closure_gate["heldout_opened"] is True
    assert closure_gate["fresh_heldout_27000_27049_accessed"] is True
    assert closure_gate["fresh_heldout_26000_26049_accessed"] is False
    assert closure_gate["mvp2_closed"] is True
    assert closure_gate["baseline_success_rate"] == pytest.approx(0.6)
    assert closure_gate["candidate_success_rate"] == pytest.approx(1.0)
    assert evidence_manifest["proof_runtime"] == script.V08D_SLICE_ID
    assert evidence_manifest["mvp2_closed"] is True
    assert evidence_manifest["fresh_heldout_27000_27049_accessed"] is True


def _v08e_fake_trace(
    *,
    success: bool,
    failure_kind: str | None = None,
    z_open_step: int = 68,
    first_depth_step: int = 92,
    first_success_step: int | None = 126,
    max_consecutive_success: int = 10,
) -> dict[str, Any]:
    rows = []
    for step in range(148):
        z_open = step >= z_open_step
        if success:
            depth = 0.025 if step >= first_success_step else max(0.0, (step - first_depth_step) * 0.00075)
            lateral = 0.0002
            env_native_success = first_success_step is not None and step >= first_success_step
        elif failure_kind == "late_z_open_depth_shortfall":
            depth = max(0.0, min(0.010, (step - first_depth_step) * 0.00075))
            lateral = 0.0002
            env_native_success = False
        elif failure_kind == "late_seat_window_shortfall":
            depth = max(0.0, min(0.0249, (step - first_depth_step) * 0.00075))
            lateral = 0.0002
            env_native_success = first_success_step is not None and step >= first_success_step
        elif failure_kind == "off_center_no_capture":
            depth = 0.000005 if step >= first_depth_step else 0.0
            lateral = 0.003
            env_native_success = False
        else:
            depth = 0.0
            lateral = 0.004
            env_native_success = False
        rows.append(
            {
                "step": step,
                "insertion_depth_m": round(depth, 6),
                "lateral_error_m": round(lateral, 6),
                "env_native_success": env_native_success,
                "env_native_success_mask": env_native_success,
                "normalized_action": [0.01, 0.0, -0.16 if z_open else 0.0, 0.0, 0.0, 0.0, 1.0],
                "controller_action_diagnostics": {
                    "z_open_step": z_open_step if z_open else None,
                    "capture_conditioning_reason": (
                        "forced_capture_conditioned_progress_z"
                        if z_open
                        else "capture_conditioning_wait"
                    ),
                },
            }
        )
    return {
        "summary": {
            "success": success,
            "env_native_rollout_success": success,
            "env_native_first_success_step": first_success_step if not success else first_success_step,
            "env_native_max_consecutive_success_steps": (
                max_consecutive_success if success or failure_kind == "late_seat_window_shortfall" else 0
            ),
            "failure_reason": "" if success else "ENV_NATIVE_STABILITY_WINDOW_NOT_REACHED",
        },
        "trace": rows,
    }


def _write_fake_v08d_failed_calibration_result(script: Any, output_dir: Path) -> None:
    child_dir = output_dir / script.V08D_CHILD_OUTPUT_DIRNAME
    trace_dir = (
        child_dir
        / "isaac_runtime_fresh_calibration_v0_8d"
        / "isaac_runtime_heldout_rollout_traces"
    )
    trace_dir.mkdir(parents=True, exist_ok=True)
    baseline_success_count = 17
    candidate_success_count = 21
    baseline_paths = []
    candidate_paths = []
    for index, seed in enumerate(range(26500, 26530)):
        baseline_success = index < baseline_success_count
        baseline_trace = _v08e_fake_trace(success=baseline_success)
        baseline_path = trace_dir / f"baseline_{index:04d}_calibration_{seed}_isaac_trace.json"
        script.write_json(baseline_path, baseline_trace)
        baseline_paths.append(str(baseline_path))

        if index < candidate_success_count:
            candidate_trace = _v08e_fake_trace(success=True)
        elif index < candidate_success_count + 5:
            candidate_trace = _v08e_fake_trace(
                success=False,
                failure_kind="late_z_open_depth_shortfall",
                z_open_step=110,
                first_depth_step=132,
                first_success_step=None,
                max_consecutive_success=0,
            )
        elif index < candidate_success_count + 8:
            candidate_trace = _v08e_fake_trace(
                success=False,
                failure_kind="late_seat_window_shortfall",
                z_open_step=73,
                first_depth_step=103,
                first_success_step=140,
                max_consecutive_success=8,
            )
        else:
            candidate_trace = _v08e_fake_trace(
                success=False,
                failure_kind="off_center_no_capture",
                z_open_step=75,
                first_depth_step=96,
                first_success_step=None,
                max_consecutive_success=0,
            )
        candidate_path = trace_dir / f"candidate_{index:04d}_calibration_{seed}_isaac_trace.json"
        script.write_json(candidate_path, candidate_trace)
        candidate_paths.append(str(candidate_path))

    gate = {
        "schema_version": script.V08D_CALIBRATION_PRESIGNAL_SCHEMA_VERSION,
        "policy_slice": "v0_8d",
        "slice_id": script.V08D_SLICE_ID,
        "runtime_backend": "isaac_runtime",
        "proof_runtime": script.ISAAC_PROOF_RUNTIME,
        "passed": False,
        "failure_reason": "candidate_failures_above_maximum",
        "baseline_calibration_rollout_count": 30,
        "candidate_calibration_rollout_count": 30,
        "baseline_calibration_success_count": baseline_success_count,
        "candidate_calibration_success_count": candidate_success_count,
        "baseline_calibration_success_rate": baseline_success_count / 30,
        "candidate_calibration_success_rate": candidate_success_count / 30,
        "candidate_baseline_success_gap": (candidate_success_count - baseline_success_count) / 30,
        "candidate_failures_total": 9,
        "candidate_failures_maximum": 3,
        "calibration_opened": True,
        "heldout_opened": False,
        "fresh_heldout_27000_27049_accessed": False,
        "mvp2_closed": False,
        "policy_uplift_proven": False,
        "trace_paths": {"baseline": baseline_paths, "candidate": candidate_paths},
    }
    script.write_json(child_dir / "calibration_presignal_gate_v0_8d.json", gate)


def test_v08e_requires_failed_v08d_calibration_gate(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    with pytest.raises(ValueError, match="missing_v0_8d_calibration_presignal_gate"):
        script.build_v08e_calibration_shortfall_diagnosis(output_dir=tmp_path)


def test_v08e_classifies_v08d_calibration_shortfall(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_fake_v08d_failed_calibration_result(script, tmp_path)

    diagnosis = script.build_v08e_calibration_shortfall_diagnosis(output_dir=tmp_path)

    taxonomy = diagnosis["failure_taxonomy"]
    assert diagnosis["policy_slice"] == "v0_8e"
    assert diagnosis["source_policy_slice"] == "v0_8d"
    assert diagnosis["mvp2_closed"] is False
    assert diagnosis["proof_authority"] is False
    assert diagnosis["fresh_heldout_27000_27049_accessed"] is False
    assert diagnosis["candidate_failures_total"] == 9
    assert diagnosis["candidate_failures_to_recover_for_calibration_gate"] == 6
    assert taxonomy["late_z_open_depth_shortfall"]["count"] == 5
    assert taxonomy["late_seat_window_shortfall"]["count"] == 3
    assert taxonomy["off_center_no_capture"]["count"] == 1
    assert taxonomy["unclassified"]["count"] == 0
    assert diagnosis["recommended_downstream_slice"] == "v0_8f_horizon_reserved_capture_authority"


def test_v08e_cli_runs_artifact_only_calibration_diagnosis(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_fake_v08d_failed_calibration_result(script, tmp_path)

    result = script.main(
        [
            "--scenario-profile",
            "v0_6",
            "--policy-slice",
            "v0_8e",
            "--calibration-failure-diagnosis-only",
            "--output-dir",
            str(tmp_path),
        ]
    )

    child_dir = tmp_path / script.V08E_CHILD_OUTPUT_DIRNAME
    diagnosis = script.read_json(child_dir / "v0_8e_calibration_shortfall_diagnosis.json")
    evidence_manifest = script.read_json(tmp_path / "evidence_manifest.json")
    assert result == 0
    assert diagnosis["runtime_backend"] == "offline_artifact_diagnosis"
    assert evidence_manifest["proof_runtime"] == script.V08E_SLICE_ID
    assert evidence_manifest["mvp2_closed"] is False
    assert evidence_manifest["fresh_heldout_27000_27049_accessed"] is False
    assert evidence_manifest["recommended_downstream_slice"] == (
        "v0_8f_horizon_reserved_capture_authority"
    )


def _write_v08f_parent_artifacts(script: Any, output_dir: Path) -> None:
    _write_v08d_parent_artifacts(script, output_dir)
    script.build_v08d_capture_conditioned_progress_authority_slice(output_dir=output_dir)
    _write_fake_v08d_failed_calibration_result(script, output_dir)
    script.build_v08e_calibration_shortfall_diagnosis(output_dir=output_dir)


def test_v08f_requires_v08e_calibration_shortfall_diagnosis(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    with pytest.raises(ValueError, match="missing_v0_8e_calibration_shortfall_diagnosis"):
        script.build_v08f_horizon_reserved_capture_authority_slice(output_dir=tmp_path)


def test_v08f_builds_fresh_manifest_and_peer_fair_artifacts(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_v08f_parent_artifacts(script, tmp_path)

    manifest = script.build_v08f_horizon_reserved_capture_authority_slice(output_dir=tmp_path)

    child_dir = tmp_path / script.V08F_CHILD_OUTPUT_DIRNAME
    candidate = script.read_json(child_dir / "candidate_policy_artifact_v0_8f.json")
    baseline = script.read_json(child_dir / "baseline_policy_artifact_v0_8f.json")
    config = script.read_json(child_dir / "v0_8f_horizon_reserved_capture_authority_config.json")
    calibration = manifest["fresh_split_manifest"]["calibration"]
    heldout = manifest["fresh_split_manifest"]["held_out"]

    assert manifest["policy_slice"] == "v0_8f"
    assert manifest["parent_policy_slice"] == "v0_8d"
    assert candidate["policy_slice"] == "v0_8f"
    assert baseline["policy_slice"] == "v0_8f"
    assert candidate["horizon_reserved_capture_authority_config_sha256"] == baseline[
        "horizon_reserved_capture_authority_config_sha256"
    ]
    assert config["horizon_reserved_capture_authority_id"] == (
        "horizon_reserved_capture_authority_v0_8f"
    )
    assert config["capture_prepare_start_step"] == 56
    assert config["horizon_reserved_z_deadline_step"] == 68
    assert config["capture_lateral_gate_m"] == 0.0035
    assert config["capture_wait_sign_flip_allowed"] is True
    assert config["seat_completion_until_env_native_success"] is True
    assert calibration["seed_range"] == [27500, 27529]
    assert heldout["seed_range"] == [27000, 27049]
    assert manifest["burned_heldout_seed_ranges"] == [[21000, 21049], [24000, 24049], [26000, 26049]]
    assert manifest["burned_calibration_seed_ranges"] == [[26500, 26529]]
    assert manifest["fresh_heldout_27000_27049_accessed"] is False


def test_v08f_cli_runs_fresh_calibration_before_fresh_heldout_with_fake_isaac(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_v08f_parent_artifacts(script, tmp_path)

    seen_seed_sets: list[list[int]] = []

    class FakeHorizonReservedBackend:
        runtime_backend = "isaac_runtime"
        proof_runtime = script.ISAAC_PROOF_RUNTIME

        def __init__(self, **_: object) -> None:
            pass

        def run(self, *, manifest, output_dir, min_rollouts_per_policy, deterministic_profile, policy_artifacts):
            del deterministic_profile
            output_dir.mkdir(parents=True, exist_ok=True)
            trace_dir = output_dir / "fake_isaac_v08f_traces"
            trace_dir.mkdir(parents=True, exist_ok=True)
            scenarios = [row for row in manifest["scenarios"] if row["split"] == "held_out"]
            seeds = [int(row["seed"]) for row in scenarios]
            seen_seed_sets.append(seeds)
            assert policy_artifacts["candidate"]["policy_slice"] == "v0_8f"
            assert policy_artifacts["baseline"]["policy_slice"] == "v0_8f"
            assert not any(21000 <= seed <= 21049 for seed in seeds)
            assert not any(24000 <= seed <= 24049 for seed in seeds)
            assert not any(26000 <= seed <= 26049 for seed in seeds)
            assert not any(26500 <= seed <= 26529 for seed in seeds)
            if seeds == list(range(27500, 27530)):
                baseline_success_limit = 17
                candidate_success_limit = 28
                rollout_count = max(int(min_rollouts_per_policy), len(scenarios))
            else:
                assert seeds == list(range(27000, 27050))
                baseline_success_limit = 30
                candidate_success_limit = 50
                rollout_count = max(int(min_rollouts_per_policy), len(scenarios))

            baseline_rollouts = []
            candidate_rollouts = []
            baseline_paths = []
            candidate_paths = []
            for index in range(rollout_count):
                scenario = scenarios[index % len(scenarios)]
                for role, success_limit, rollouts, paths, action_x in (
                    ("baseline", baseline_success_limit, baseline_rollouts, baseline_paths, 0.01),
                    ("candidate", candidate_success_limit, candidate_rollouts, candidate_paths, 0.02),
                ):
                    success = index < success_limit
                    trace_path = trace_dir / f"{role}_{index:04d}_{scenario['scenario_id']}.json"
                    script.write_json(
                        trace_path,
                        {
                            "scenario": scenario,
                            "policy_role": role,
                            "summary": {
                                "success": success,
                                "env_native_rollout_success": success,
                                "failure_reason": "" if success else "ENV_NATIVE_WINDOW_NOT_REACHED",
                            },
                            "trace": [
                                {
                                    "step": step,
                                    "insertion_depth_m": 0.025 if success and step >= 4 else 0.0,
                                    "lateral_error_m": 0.0002,
                                    "env_native_success": success and step >= 4,
                                    "normalized_action": [action_x, 0.0, -0.16, 0.0, 0.0, 0.0, 1.0],
                                    "controller_action_diagnostics": {
                                        "post_adapter_action_vector": [
                                            action_x,
                                            0.0,
                                            -0.16,
                                            0.0,
                                            0.0,
                                            0.0,
                                            1.0,
                                        ],
                                        "horizon_reserved_capture_authority_applied": True,
                                    },
                                }
                                for step in range(14)
                            ],
                        },
                    )
                    paths.append(str(trace_path))
                    rollouts.append(
                        {
                            "rollout_id": f"{role}_v08f_{index:04d}",
                            "scenario_id": scenario["scenario_id"],
                            "seed": int(scenario["seed"]),
                            "success": success,
                            "env_native_rollout_success": success,
                            "failure_reason": "" if success else "ENV_NATIVE_WINDOW_NOT_REACHED",
                            "steps": 120,
                            "rollout_log_ref": str(trace_path),
                        }
                    )
            return script.BackendResult(
                runtime_backend="isaac_runtime",
                proof_runtime=script.ISAAC_PROOF_RUNTIME,
                runtime_gate={
                    "passed": True,
                    "runtime_backend": "isaac_runtime",
                    "proof_runtime": script.ISAAC_PROOF_RUNTIME,
                },
                baseline_rollouts=baseline_rollouts,
                candidate_rollouts=candidate_rollouts,
                baseline_trace_paths=baseline_paths,
                candidate_trace_paths=candidate_paths,
                runtime_metadata={"runtime_backend": "isaac_runtime"},
            )

    monkeypatch.setattr(script, "IsaacConnectorInsertionEvaluatorBackend", FakeHorizonReservedBackend)

    result = script.main(
        [
            "--scenario-profile",
            "v0_6",
            "--policy-slice",
            "v0_8f",
            "--horizon-reserved-capture-authority-only",
            "--output-dir",
            str(tmp_path),
            "--rollouts-per-policy",
            "20",
            "--bootstrap-iterations",
            "50",
        ]
    )

    child_dir = tmp_path / script.V08F_CHILD_OUTPUT_DIRNAME
    evidence_manifest = script.read_json(tmp_path / "evidence_manifest.json")
    calibration_gate = script.read_json(child_dir / "calibration_presignal_gate_v0_8f.json")
    closure_gate = script.read_json(child_dir / "heldout_closure_gate_v0_8f.json")

    assert result == 0
    assert seen_seed_sets == [list(range(27500, 27530)), list(range(27000, 27050))]
    assert calibration_gate["passed"] is True
    assert calibration_gate["candidate_failures_total"] == 2
    assert calibration_gate["candidate_baseline_success_gap"] == pytest.approx(11 / 30)
    assert calibration_gate["attribution_preservation_gate_passed"] is True
    assert calibration_gate["fresh_calibration_27500_27529_accessed"] is True
    assert calibration_gate["fresh_heldout_27000_27049_accessed"] is False
    assert closure_gate["policy_slice"] == "v0_8f"
    assert closure_gate["heldout_opened"] is True
    assert closure_gate["fresh_heldout_27000_27049_accessed"] is True
    assert closure_gate["mvp2_closed"] is True
    assert closure_gate["baseline_success_rate"] == pytest.approx(0.6)
    assert closure_gate["candidate_success_rate"] == pytest.approx(1.0)
    assert evidence_manifest["proof_runtime"] == script.V08F_SLICE_ID
    assert evidence_manifest["mvp2_closed"] is True
    assert evidence_manifest["fresh_heldout_27000_27049_accessed"] is True


def _write_fake_v08f_failed_calibration_result(script: Any, output_dir: Path) -> None:
    _write_v08f_parent_artifacts(script, output_dir)
    script.build_v08f_horizon_reserved_capture_authority_slice(output_dir=output_dir)
    child_dir = output_dir / script.V08F_CHILD_OUTPUT_DIRNAME
    gate = {
        "schema_version": script.V08F_CALIBRATION_PRESIGNAL_SCHEMA_VERSION,
        "policy_slice": "v0_8f",
        "slice_id": script.V08F_SLICE_ID,
        "parent_policy_slice": script.V08D_POLICY_SLICE_ID,
        "runtime_backend": "isaac_runtime",
        "proof_runtime": script.ISAAC_PROOF_RUNTIME,
        "passed": False,
        "failure_reason": "candidate_baseline_success_gap_below_minimum",
        "baseline_success_count": 15,
        "candidate_success_count": 17,
        "total_rollouts_per_policy": 30,
        "baseline_success_rate": 0.5,
        "candidate_success_rate": 17 / 30,
        "candidate_baseline_success_gap": 2 / 30,
        "candidate_failures_total": 13,
        "candidate_failures_maximum": 3,
        "calibration_opened": True,
        "heldout_opened": False,
        "fresh_calibration_26500_26529_accessed": True,
        "fresh_calibration_27500_27529_accessed": True,
        "fresh_heldout_27000_27049_accessed": False,
        "mvp2_closed": False,
        "policy_uplift_proven": False,
        "heldout_allowed": False,
        "blockers": ["candidate_baseline_success_gap_below_minimum"],
    }
    gate["calibration_presignal_gate_sha256"] = script._sha256_payload_excluding(
        gate,
        "calibration_presignal_gate_sha256",
    )
    script.write_json(child_dir / "calibration_presignal_gate_v0_8f.json", gate)


def test_v08g_requires_failed_v08f_calibration_gate(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    with pytest.raises(ValueError, match="missing_v0_8f_failed_calibration_presignal_gate"):
        script.build_v08g_deadline_precedence_horizon_authority_slice(output_dir=tmp_path)


def test_v08g_builds_fresh_manifest_and_peer_fair_artifacts(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_fake_v08f_failed_calibration_result(script, tmp_path)

    manifest = script.build_v08g_deadline_precedence_horizon_authority_slice(output_dir=tmp_path)

    child_dir = tmp_path / script.V08G_CHILD_OUTPUT_DIRNAME
    candidate = script.read_json(child_dir / "candidate_policy_artifact_v0_8g.json")
    baseline = script.read_json(child_dir / "baseline_policy_artifact_v0_8g.json")
    config = script.read_json(child_dir / "v0_8g_deadline_precedence_horizon_authority_config.json")
    calibration = manifest["fresh_split_manifest"]["calibration"]
    heldout = manifest["fresh_split_manifest"]["held_out"]

    assert manifest["policy_slice"] == "v0_8g"
    assert manifest["parent_policy_slice"] == "v0_8f"
    assert candidate["policy_slice"] == "v0_8g"
    assert baseline["policy_slice"] == "v0_8g"
    assert candidate["deadline_precedence_horizon_authority_config_sha256"] == baseline[
        "deadline_precedence_horizon_authority_config_sha256"
    ]
    assert config["deadline_precedence_horizon_authority_id"] == (
        "deadline_precedence_horizon_authority_v0_8g"
    )
    assert config["deadline_precedence_over_capture_wait"] is True
    assert config["horizon_reserved_z_deadline_step"] == 68
    assert calibration["seed_range"] == [28000, 28029]
    assert heldout["seed_range"] == [27000, 27049]
    assert manifest["burned_heldout_seed_ranges"] == [[21000, 21049], [24000, 24049], [26000, 26049]]
    assert manifest["burned_calibration_seed_ranges"] == [[26500, 26529], [27500, 27529]]
    assert manifest["fresh_heldout_27000_27049_accessed"] is False


def test_v08g_cli_runs_fresh_calibration_before_fresh_heldout_with_fake_isaac(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_fake_v08f_failed_calibration_result(script, tmp_path)

    seen_seed_sets: list[list[int]] = []

    class FakeDeadlinePrecedenceBackend:
        runtime_backend = "isaac_runtime"
        proof_runtime = script.ISAAC_PROOF_RUNTIME

        def __init__(self, **_: object) -> None:
            pass

        def run(self, *, manifest, output_dir, min_rollouts_per_policy, deterministic_profile, policy_artifacts):
            del deterministic_profile
            output_dir.mkdir(parents=True, exist_ok=True)
            trace_dir = output_dir / "fake_isaac_v08g_traces"
            trace_dir.mkdir(parents=True, exist_ok=True)
            scenarios = [row for row in manifest["scenarios"] if row["split"] == "held_out"]
            seeds = [int(row["seed"]) for row in scenarios]
            seen_seed_sets.append(seeds)
            assert policy_artifacts["candidate"]["policy_slice"] == "v0_8g"
            assert policy_artifacts["baseline"]["policy_slice"] == "v0_8g"
            assert not any(21000 <= seed <= 21049 for seed in seeds)
            assert not any(24000 <= seed <= 24049 for seed in seeds)
            assert not any(26000 <= seed <= 26049 for seed in seeds)
            assert not any(26500 <= seed <= 26529 for seed in seeds)
            assert not any(27500 <= seed <= 27529 for seed in seeds)
            if seeds == list(range(28000, 28030)):
                baseline_success_limit = 15
                candidate_success_limit = 29
                rollout_count = max(int(min_rollouts_per_policy), len(scenarios))
            else:
                assert seeds == list(range(27000, 27050))
                baseline_success_limit = 30
                candidate_success_limit = 50
                rollout_count = max(int(min_rollouts_per_policy), len(scenarios))

            baseline_rollouts = []
            candidate_rollouts = []
            baseline_paths = []
            candidate_paths = []
            for index in range(rollout_count):
                scenario = scenarios[index % len(scenarios)]
                for role, success_limit, rollouts, paths, action_x in (
                    ("baseline", baseline_success_limit, baseline_rollouts, baseline_paths, 0.01),
                    ("candidate", candidate_success_limit, candidate_rollouts, candidate_paths, 0.02),
                ):
                    success = index < success_limit
                    trace_path = trace_dir / f"{role}_{index:04d}_{scenario['scenario_id']}.json"
                    script.write_json(
                        trace_path,
                        {
                            "scenario": scenario,
                            "policy_role": role,
                            "summary": {
                                "success": success,
                                "env_native_rollout_success": success,
                                "failure_reason": "" if success else "ENV_NATIVE_WINDOW_NOT_REACHED",
                            },
                            "trace": [
                                {
                                    "step": step,
                                    "insertion_depth_m": 0.025 if success and step >= 4 else 0.0,
                                    "lateral_error_m": 0.0002,
                                    "env_native_success": success and step >= 4,
                                    "normalized_action": [action_x, 0.0, -0.16, 0.0, 0.0, 0.0, 1.0],
                                    "controller_action_diagnostics": {
                                        "post_adapter_action_vector": [
                                            action_x,
                                            0.0,
                                            -0.16,
                                            0.0,
                                            0.0,
                                            0.0,
                                            1.0,
                                        ],
                                        "deadline_precedence_horizon_authority_applied": True,
                                    },
                                }
                                for step in range(14)
                            ],
                        },
                    )
                    paths.append(str(trace_path))
                    rollouts.append(
                        {
                            "rollout_id": f"{role}_v08g_{index:04d}",
                            "scenario_id": scenario["scenario_id"],
                            "seed": int(scenario["seed"]),
                            "success": success,
                            "env_native_rollout_success": success,
                            "failure_reason": "" if success else "ENV_NATIVE_WINDOW_NOT_REACHED",
                            "steps": 120,
                            "rollout_log_ref": str(trace_path),
                        }
                    )
            return script.BackendResult(
                runtime_backend="isaac_runtime",
                proof_runtime=script.ISAAC_PROOF_RUNTIME,
                runtime_gate={
                    "passed": True,
                    "runtime_backend": "isaac_runtime",
                    "proof_runtime": script.ISAAC_PROOF_RUNTIME,
                },
                baseline_rollouts=baseline_rollouts,
                candidate_rollouts=candidate_rollouts,
                baseline_trace_paths=baseline_paths,
                candidate_trace_paths=candidate_paths,
                runtime_metadata={"runtime_backend": "isaac_runtime"},
            )

    monkeypatch.setattr(script, "IsaacConnectorInsertionEvaluatorBackend", FakeDeadlinePrecedenceBackend)

    result = script.main(
        [
            "--scenario-profile",
            "v0_6",
            "--policy-slice",
            "v0_8g",
            "--deadline-precedence-horizon-authority-only",
            "--output-dir",
            str(tmp_path),
            "--rollouts-per-policy",
            "20",
            "--bootstrap-iterations",
            "50",
        ]
    )

    child_dir = tmp_path / script.V08G_CHILD_OUTPUT_DIRNAME
    evidence_manifest = script.read_json(tmp_path / "evidence_manifest.json")
    calibration_gate = script.read_json(child_dir / "calibration_presignal_gate_v0_8g.json")
    closure_gate = script.read_json(child_dir / "heldout_closure_gate_v0_8g.json")

    assert result == 0
    assert seen_seed_sets == [list(range(28000, 28030)), list(range(27000, 27050))]
    assert calibration_gate["passed"] is True
    assert calibration_gate["candidate_failures_total"] == 1
    assert calibration_gate["candidate_baseline_success_gap"] == pytest.approx(14 / 30)
    assert calibration_gate["fresh_calibration_28000_28029_accessed"] is True
    assert calibration_gate["fresh_heldout_27000_27049_accessed"] is False
    assert closure_gate["policy_slice"] == "v0_8g"
    assert closure_gate["heldout_opened"] is True
    assert closure_gate["fresh_heldout_27000_27049_accessed"] is True
    assert closure_gate["mvp2_closed"] is True
    assert closure_gate["baseline_success_rate"] == pytest.approx(0.6)
    assert closure_gate["candidate_success_rate"] == pytest.approx(1.0)
    assert evidence_manifest["proof_runtime"] == script.V08G_SLICE_ID
    assert evidence_manifest["mvp2_closed"] is True
    assert evidence_manifest["fresh_calibration_28000_28029_accessed"] is True
    assert evidence_manifest["fresh_heldout_27000_27049_accessed"] is True


def _write_fake_v08g_failed_calibration_result(script: Any, output_dir: Path) -> None:
    _write_fake_v08f_failed_calibration_result(script, output_dir)
    script.build_v08g_deadline_precedence_horizon_authority_slice(output_dir=output_dir)
    child_dir = output_dir / script.V08G_CHILD_OUTPUT_DIRNAME
    gate = {
        "schema_version": script.V08G_CALIBRATION_PRESIGNAL_SCHEMA_VERSION,
        "policy_slice": "v0_8g",
        "slice_id": script.V08G_SLICE_ID,
        "parent_policy_slice": script.V08F_POLICY_SLICE_ID,
        "runtime_backend": "isaac_runtime",
        "proof_runtime": script.ISAAC_PROOF_RUNTIME,
        "passed": False,
        "failure_reason": "candidate_failures_above_maximum",
        "baseline_success_count": 17,
        "candidate_success_count": 20,
        "total_rollouts_per_policy": 30,
        "baseline_success_rate": 17 / 30,
        "candidate_success_rate": 20 / 30,
        "candidate_baseline_success_gap": 0.10,
        "candidate_failures_total": 10,
        "candidate_failures_maximum": 3,
        "calibration_opened": True,
        "heldout_opened": False,
        "fresh_calibration_26500_26529_accessed": True,
        "fresh_calibration_27500_27529_accessed": True,
        "fresh_calibration_28000_28029_accessed": True,
        "fresh_heldout_27000_27049_accessed": False,
        "mvp2_closed": False,
        "policy_uplift_proven": False,
        "heldout_allowed": False,
        "blockers": ["candidate_failures_above_maximum"],
    }
    gate["calibration_presignal_gate_sha256"] = script._sha256_payload_excluding(
        gate,
        "calibration_presignal_gate_sha256",
    )
    script.write_json(child_dir / "calibration_presignal_gate_v0_8g.json", gate)


def test_v08h_requires_failed_v08g_calibration_gate(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    with pytest.raises(ValueError, match="missing_v0_8g_failed_calibration_presignal_gate"):
        script.build_v08h_early_centered_z_open_safe_entry_slice(output_dir=tmp_path)


def test_v08h_builds_fresh_manifest_and_peer_fair_artifacts(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_fake_v08g_failed_calibration_result(script, tmp_path)

    manifest = script.build_v08h_early_centered_z_open_safe_entry_slice(output_dir=tmp_path)

    child_dir = tmp_path / script.V08H_CHILD_OUTPUT_DIRNAME
    candidate = script.read_json(child_dir / "candidate_policy_artifact_v0_8h.json")
    baseline = script.read_json(child_dir / "baseline_policy_artifact_v0_8h.json")
    config = script.read_json(child_dir / "v0_8h_early_centered_z_open_safe_entry_config.json")
    calibration = manifest["fresh_split_manifest"]["calibration"]
    heldout = manifest["fresh_split_manifest"]["held_out"]

    assert manifest["policy_slice"] == "v0_8h"
    assert manifest["parent_policy_slice"] == "v0_8g"
    assert candidate["policy_slice"] == "v0_8h"
    assert baseline["policy_slice"] == "v0_8h"
    assert candidate["early_centered_z_open_safe_entry_config_sha256"] == baseline[
        "early_centered_z_open_safe_entry_config_sha256"
    ]
    assert config["early_centered_z_open_safe_entry_authority_id"] == (
        "early_centered_z_open_safe_entry_authority_v0_8h"
    )
    assert config["early_centered_z_open_enabled"] is True
    assert config["unsafe_lateral_z_block_after_reference_deadline"] is True
    assert config["safe_entry_lateral_gate_m"] == pytest.approx(0.005)
    assert config["depth_progress_continuation_lateral_gate_m"] == pytest.approx(0.006)
    assert calibration["seed_range"] == [28500, 28529]
    assert heldout["seed_range"] == [27000, 27049]
    assert manifest["burned_heldout_seed_ranges"] == [[21000, 21049], [24000, 24049], [26000, 26049]]
    assert manifest["burned_calibration_seed_ranges"] == [
        [26500, 26529],
        [27500, 27529],
        [28000, 28029],
    ]
    assert manifest["fresh_heldout_27000_27049_accessed"] is False


def test_v08h_cli_runs_fresh_calibration_before_fresh_heldout_with_fake_isaac(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_fake_v08g_failed_calibration_result(script, tmp_path)

    seen_seed_sets: list[list[int]] = []

    class FakeSafeEntryBackend:
        runtime_backend = "isaac_runtime"
        proof_runtime = script.ISAAC_PROOF_RUNTIME

        def __init__(self, **_: object) -> None:
            pass

        def run(self, *, manifest, output_dir, min_rollouts_per_policy, deterministic_profile, policy_artifacts):
            del deterministic_profile
            output_dir.mkdir(parents=True, exist_ok=True)
            trace_dir = output_dir / "fake_isaac_v08h_traces"
            trace_dir.mkdir(parents=True, exist_ok=True)
            scenarios = [row for row in manifest["scenarios"] if row["split"] == "held_out"]
            seeds = [int(row["seed"]) for row in scenarios]
            seen_seed_sets.append(seeds)
            assert policy_artifacts["candidate"]["policy_slice"] == "v0_8h"
            assert policy_artifacts["baseline"]["policy_slice"] == "v0_8h"
            assert not any(21000 <= seed <= 21049 for seed in seeds)
            assert not any(24000 <= seed <= 24049 for seed in seeds)
            assert not any(26000 <= seed <= 26049 for seed in seeds)
            assert not any(26500 <= seed <= 26529 for seed in seeds)
            assert not any(27500 <= seed <= 27529 for seed in seeds)
            assert not any(28000 <= seed <= 28029 for seed in seeds)
            if seeds == list(range(28500, 28530)):
                baseline_success_limit = 15
                candidate_success_limit = 29
                rollout_count = max(int(min_rollouts_per_policy), len(scenarios))
            else:
                assert seeds == list(range(27000, 27050))
                baseline_success_limit = 30
                candidate_success_limit = 50
                rollout_count = max(int(min_rollouts_per_policy), len(scenarios))

            baseline_rollouts = []
            candidate_rollouts = []
            baseline_paths = []
            candidate_paths = []
            for index in range(rollout_count):
                scenario = scenarios[index % len(scenarios)]
                for role, success_limit, rollouts, paths, action_x in (
                    ("baseline", baseline_success_limit, baseline_rollouts, baseline_paths, 0.01),
                    ("candidate", candidate_success_limit, candidate_rollouts, candidate_paths, 0.02),
                ):
                    success = index < success_limit
                    trace_path = trace_dir / f"{role}_{index:04d}_{scenario['scenario_id']}.json"
                    script.write_json(
                        trace_path,
                        {
                            "scenario": scenario,
                            "policy_role": role,
                            "summary": {
                                "success": success,
                                "env_native_rollout_success": success,
                                "failure_reason": "" if success else "ENV_NATIVE_WINDOW_NOT_REACHED",
                            },
                            "trace": [
                                {
                                    "step": step,
                                    "insertion_depth_m": 0.025 if success and step >= 4 else 0.0,
                                    "lateral_error_m": 0.0002,
                                    "env_native_success": success and step >= 4,
                                    "normalized_action": [action_x, 0.0, -0.16, 0.0, 0.0, 0.0, 1.0],
                                    "controller_action_diagnostics": {
                                        "post_adapter_action_vector": [
                                            action_x,
                                            0.0,
                                            -0.16,
                                            0.0,
                                            0.0,
                                            0.0,
                                            1.0,
                                        ],
                                        "early_centered_z_open_safe_entry_applied": True,
                                    },
                                }
                                for step in range(14)
                            ],
                        },
                    )
                    paths.append(str(trace_path))
                    rollouts.append(
                        {
                            "rollout_id": f"{role}_v08h_{index:04d}",
                            "scenario_id": scenario["scenario_id"],
                            "seed": int(scenario["seed"]),
                            "success": success,
                            "env_native_rollout_success": success,
                            "failure_reason": "" if success else "ENV_NATIVE_WINDOW_NOT_REACHED",
                            "steps": 120,
                            "rollout_log_ref": str(trace_path),
                        }
                    )
            return script.BackendResult(
                runtime_backend="isaac_runtime",
                proof_runtime=script.ISAAC_PROOF_RUNTIME,
                runtime_gate={
                    "passed": True,
                    "runtime_backend": "isaac_runtime",
                    "proof_runtime": script.ISAAC_PROOF_RUNTIME,
                },
                baseline_rollouts=baseline_rollouts,
                candidate_rollouts=candidate_rollouts,
                baseline_trace_paths=baseline_paths,
                candidate_trace_paths=candidate_paths,
                runtime_metadata={"runtime_backend": "isaac_runtime"},
            )

    monkeypatch.setattr(script, "IsaacConnectorInsertionEvaluatorBackend", FakeSafeEntryBackend)

    result = script.main(
        [
            "--scenario-profile",
            "v0_6",
            "--policy-slice",
            "v0_8h",
            "--early-centered-z-open-safe-entry-only",
            "--output-dir",
            str(tmp_path),
            "--rollouts-per-policy",
            "20",
            "--bootstrap-iterations",
            "50",
        ]
    )

    child_dir = tmp_path / script.V08H_CHILD_OUTPUT_DIRNAME
    evidence_manifest = script.read_json(tmp_path / "evidence_manifest.json")
    calibration_gate = script.read_json(child_dir / "calibration_presignal_gate_v0_8h.json")
    closure_gate = script.read_json(child_dir / "heldout_closure_gate_v0_8h.json")

    assert result == 0
    assert seen_seed_sets == [list(range(28500, 28530)), list(range(27000, 27050))]
    assert calibration_gate["passed"] is True
    assert calibration_gate["candidate_failures_total"] == 1
    assert calibration_gate["candidate_baseline_success_gap"] == pytest.approx(14 / 30)
    assert calibration_gate["fresh_calibration_28500_28529_accessed"] is True
    assert calibration_gate["fresh_heldout_27000_27049_accessed"] is False
    assert closure_gate["policy_slice"] == "v0_8h"
    assert closure_gate["heldout_opened"] is True
    assert closure_gate["fresh_heldout_27000_27049_accessed"] is True
    assert closure_gate["mvp2_closed"] is True
    assert closure_gate["baseline_success_rate"] == pytest.approx(0.6)
    assert closure_gate["candidate_success_rate"] == pytest.approx(1.0)
    assert evidence_manifest["proof_runtime"] == script.V08H_SLICE_ID
    assert evidence_manifest["mvp2_closed"] is True
    assert evidence_manifest["fresh_calibration_28500_28529_accessed"] is True
    assert evidence_manifest["fresh_heldout_27000_27049_accessed"] is True


def _write_fake_v08h_failed_calibration_result(script: Any, output_dir: Path) -> None:
    child_dir = output_dir / script.V08H_CHILD_OUTPUT_DIRNAME
    trace_dir = (
        child_dir
        / "isaac_runtime_fresh_calibration_v0_8h"
        / "isaac_runtime_heldout_rollout_traces"
    )
    trace_dir.mkdir(parents=True, exist_ok=True)
    baseline_paths = []
    candidate_paths = []
    for index, seed in enumerate(range(28500, 28530)):
        baseline_success = index < 23
        if baseline_success:
            baseline_trace = _v08e_fake_trace(success=True)
        else:
            baseline_trace = _v08e_fake_trace(
                success=False,
                failure_kind="late_z_open_depth_shortfall",
                z_open_step=92,
                first_depth_step=122,
                first_success_step=None,
                max_consecutive_success=0,
            )
        baseline_path = trace_dir / f"baseline_{index:04d}_calibration_{seed}_isaac_trace.json"
        script.write_json(baseline_path, baseline_trace)
        baseline_paths.append(str(baseline_path))

        if index < 25:
            candidate_trace = _v08e_fake_trace(success=True)
        elif index == 25:
            candidate_trace = _v08e_fake_trace(
                success=False,
                failure_kind="late_seat_window_shortfall",
                z_open_step=81,
                first_depth_step=111,
                first_success_step=145,
                max_consecutive_success=3,
            )
        elif index < 29:
            candidate_trace = _v08e_fake_trace(
                success=False,
                failure_kind="late_z_open_depth_shortfall",
                z_open_step=90,
                first_depth_step=122,
                first_success_step=None,
                max_consecutive_success=0,
            )
        else:
            candidate_trace = _v08e_fake_trace(
                success=False,
                failure_kind="off_center_no_capture",
                z_open_step=74,
                first_depth_step=120,
                first_success_step=None,
                max_consecutive_success=0,
            )
        candidate_path = trace_dir / f"candidate_{index:04d}_calibration_{seed}_isaac_trace.json"
        script.write_json(candidate_path, candidate_trace)
        candidate_paths.append(str(candidate_path))

    gate = {
        "schema_version": script.V08H_CALIBRATION_PRESIGNAL_SCHEMA_VERSION,
        "policy_slice": "v0_8h",
        "slice_id": script.V08H_SLICE_ID,
        "runtime_backend": "isaac_runtime",
        "proof_runtime": script.ISAAC_PROOF_RUNTIME,
        "passed": False,
        "failure_reason": "candidate_baseline_success_gap_below_minimum",
        "baseline_calibration_rollout_count": 30,
        "candidate_calibration_rollout_count": 30,
        "baseline_calibration_success_count": 23,
        "candidate_calibration_success_count": 25,
        "baseline_calibration_success_rate": 23 / 30,
        "candidate_calibration_success_rate": 25 / 30,
        "candidate_baseline_success_gap": 2 / 30,
        "candidate_failures_total": 5,
        "candidate_failures_maximum": 3,
        "calibration_opened": True,
        "heldout_opened": False,
        "fresh_calibration_28500_28529_accessed": True,
        "fresh_heldout_27000_27049_accessed": False,
        "mvp2_closed": False,
        "policy_uplift_proven": False,
        "trace_paths": {"baseline": baseline_paths, "candidate": candidate_paths},
    }
    script.write_json(child_dir / "calibration_presignal_gate_v0_8h.json", gate)


def _set_v08j_fake_residual_margin(
    trace_payload: dict[str, Any],
    *,
    z_open_residual_z: float,
    z_closed_residual_z: float = 0.001,
    z_open_lateral_m: float | None = None,
) -> None:
    for row in trace_payload["trace"]:
        action = row["normalized_action"]
        z_open = float(action[2]) < -1e-9
        if z_open and z_open_lateral_m is not None:
            row["lateral_error_m"] = round(z_open_lateral_m, 6)
        residual_z = z_open_residual_z if z_open else z_closed_residual_z
        diagnostics = row.setdefault("controller_action_diagnostics", {})
        diagnostics["residual_prediction"] = [0.0, 0.0, residual_z, 0.0, 0.0, 0.0, 0.0]
        diagnostics["raw_action_before_adapter"] = [0.0, 0.0, residual_z - 0.001, 0.0, 0.0, 0.0, 1.0]


def _write_fake_v08h_failed_calibration_result_with_v08j_residuals(
    script: Any,
    output_dir: Path,
) -> None:
    _write_fake_v08h_failed_calibration_result(script, output_dir)
    trace_dir = (
        output_dir
        / script.V08H_CHILD_OUTPUT_DIRNAME
        / "isaac_runtime_fresh_calibration_v0_8h"
        / "isaac_runtime_heldout_rollout_traces"
    )
    for path in trace_dir.glob("*_isaac_trace.json"):
        payload = script.read_json(path)
        role = path.name.split("_")[0]
        seed = int(path.name.split("_")[3])
        if seed in {28523, 28524} and role == "candidate":
            _set_v08j_fake_residual_margin(
                payload,
                z_open_residual_z=-0.151,
                z_open_lateral_m=0.0005,
            )
        elif seed in {28523, 28524} and role == "baseline":
            _set_v08j_fake_residual_margin(
                payload,
                z_open_residual_z=-0.086,
                z_open_lateral_m=0.003,
            )
        else:
            _set_v08j_fake_residual_margin(payload, z_open_residual_z=-0.088)
        script.write_json(path, payload)


def _fake_v08k_training_row(
    *,
    trajectory_id: str,
    step: int,
    phase: str | None,
    accepted: bool = True,
) -> dict[str, Any]:
    action_z = -0.12 if phase == "DESCEND" else 0.0
    trace_seed = 19003 if accepted else 19203
    trace_id = f"train_success_{trace_seed}" if accepted else f"train_failure_{trace_seed}"
    return {
        "trajectory_id": trajectory_id,
        "step": step,
        "accepted": accepted,
        "proof_role": "trace_native_residual_train",
        "source_trace_path": (
            "/tmp/rdf/isaac_runtime_train_generation_probe/"
            "isaac_runtime_heldout_rollout_traces/"
            f"train_generation_probe_0000_{trace_id}_isaac_trace.json"
        ),
        "runtime_trace_path": (
            "/tmp/rdf/isaac_runtime_train_generation_probe/"
            "isaac_runtime_heldout_rollout_traces/"
            f"train_generation_probe_0000_{trace_id}_isaac_trace.json"
        ),
        "behavior_state_phase": phase,
        "env_native_success_mask": phase == "HOLD",
        "insertion_depth_m": 0.025 if phase == "HOLD" else 0.012,
        "relative_x_m": 0.0,
        "relative_y_m": 0.0,
        "lateral_error_m": 0.001,
        "orientation_error_deg": 0.0,
        "previous_action_dx": 0.0,
        "previous_action_dy": 0.0,
        "previous_action_dz": 0.0,
        "previous_action_rx": 0.0,
        "previous_action_ry": 0.0,
        "previous_action_rz": 0.0,
        "previous_action_gripper": 1.0,
        "normalized_action": [0.0, 0.0, action_z, 0.0, 0.0, 0.0, 1.0],
    }


def _write_fake_v08k_parent_chain(script: Any, output_dir: Path) -> None:
    _write_fake_v08h_failed_calibration_result_with_v08j_residuals(script, output_dir)
    script.build_v08i_calibration_uplift_compression_diagnosis(output_dir=output_dir)
    script.build_v08j_attribution_preserving_candidate_margin_diagnosis(output_dir=output_dir)


def _write_fake_v08k_source_train_views(script: Any, output_dir: Path) -> None:
    child_dir = output_dir / script.V07D_CHILD_OUTPUT_DIRNAME
    child_dir.mkdir(parents=True, exist_ok=True)
    residual_config = script.build_v07b_residual_servo_config(
        output_dir=child_dir,
        parent_config_sha256="fake_parent_trace_native_config_sha256",
    )
    authority_config = script.build_v07c_action_authority_config(
        output_dir=child_dir,
        residual_servo_config=residual_config,
        selected_action_adapter_id="isaac_signed_xy_downward_servo_v0",
    )
    candidate_rows = [
        _fake_v08k_training_row(trajectory_id="candidate_success", step=index, phase=phase)
        for index, phase in enumerate(["ALIGN", "DESCEND", "DESCEND", "HOLD", "HOLD"])
    ]
    baseline_rows = candidate_rows + [
        _fake_v08k_training_row(
            trajectory_id="baseline_rejected",
            step=100,
            phase="ALIGN",
            accepted=False,
        )
    ]
    script.write_v07c_residual_train_view_hdf5(
        path=child_dir / "candidate_curated_train_v0_7d.hdf5",
        rows=candidate_rows,
        view_id="candidate_curated_v0_7d_action_authority_post_adapter_z_gate",
        authority_config=authority_config,
    )
    script.write_v07c_residual_train_view_hdf5(
        path=child_dir / "baseline_uncurated_train_v0_7d.hdf5",
        rows=baseline_rows,
        view_id="baseline_uncurated_v0_7d_action_authority_post_adapter_z_gate",
        authority_config=authority_config,
    )


def _write_fake_v08l_v08k_evidence(script: Any, output_dir: Path) -> None:
    child_dir = output_dir / script.V08K_CHILD_OUTPUT_DIRNAME
    trace_dir = (
        child_dir
        / "isaac_runtime_fresh_calibration_v0_8k"
        / "isaac_runtime_heldout_rollout_traces"
    )
    trace_dir.mkdir(parents=True, exist_ok=True)
    child_dir.mkdir(parents=True, exist_ok=True)
    gate = {
        "schema_version": script.V08K_CALIBRATION_PRESIGNAL_SCHEMA_VERSION,
        "policy_slice": "v0_8k",
        "slice_id": script.V08K_SLICE_ID,
        "passed": False,
        "failure_reason": "candidate_baseline_success_gap_below_minimum",
        "baseline_calibration_success_count": 26,
        "candidate_calibration_success_count": 27,
        "baseline_calibration_success_rate": 26 / 30,
        "candidate_calibration_success_rate": 27 / 30,
        "candidate_baseline_success_gap": 1 / 30,
        "heldout_opened": False,
        "fresh_heldout_27000_27049_accessed": False,
        "trace_paths": {"baseline": [], "candidate": []},
    }
    residual_config = script.build_v07b_residual_servo_config(
        output_dir=child_dir,
        parent_config_sha256="fake_parent_trace_native_config_sha256",
    )
    authority_config = script.build_v07c_action_authority_config(
        output_dir=child_dir,
        residual_servo_config=residual_config,
        selected_action_adapter_id="isaac_signed_xy_downward_servo_v0",
    )
    candidate_rows = [
        _fake_v08k_training_row(trajectory_id="candidate_success", step=index, phase=phase)
        for index, phase in enumerate(["ALIGN", "DESCEND", "DESCEND", "HOLD"])
    ]
    baseline_rows = candidate_rows + [
        _fake_v08k_training_row(
            trajectory_id="baseline_rejected_descent",
            step=100 + index,
            phase="DESCEND",
            accepted=False,
        )
        for index in range(4)
    ]
    script.write_v07c_residual_train_view_hdf5(
        path=child_dir / "candidate_curated_train_v0_8k.hdf5",
        rows=candidate_rows,
        view_id="candidate_curated_fake_v0_8k",
        authority_config=authority_config,
    )
    script.write_v07c_residual_train_view_hdf5(
        path=child_dir / "baseline_uncurated_train_v0_8k.hdf5",
        rows=baseline_rows,
        view_id="baseline_uncurated_fake_v0_8k",
        authority_config=authority_config,
    )
    for role, success_count in (("baseline", 26), ("candidate", 27)):
        trace_paths: list[str] = []
        for index in range(30):
            success = index < success_count
            trace = {
                "summary": {
                    "success": success,
                    "failure_reason": "" if success else "ENV_NATIVE_STABILITY_WINDOW_NOT_REACHED",
                    "env_native_max_consecutive_success_steps": 10 if success else 0,
                    "steps": 12,
                },
                "trace": [
                    {
                        "step": step,
                        "insertion_depth_m": 0.024 if success else 0.012,
                        "lateral_error_m": 0.001,
                        "controller_action_diagnostics": {
                            "residual_prediction": [
                                0.0,
                                0.0,
                                -0.110 if role == "baseline" else -0.111,
                                0.0,
                                0.0,
                                0.0,
                                0.0,
                            ],
                            "post_adapter_action_vector": [0.0, 0.0, -0.16, 0.0, 0.0, 0.0, 1.0],
                            "early_centered_z_open_safe_entry_applied": True,
                        },
                    }
                    for step in range(12)
                ],
            }
            path = trace_dir / f"{role}_{index:04d}_calibration_{29000 + index}_isaac_trace.json"
            script.write_json(path, trace)
            trace_paths.append(str(path))
        gate["trace_paths"][role] = trace_paths
    gate["calibration_presignal_gate_sha256"] = script._sha256_payload_excluding(
        gate,
        "calibration_presignal_gate_sha256",
    )
    script.write_json(child_dir / "calibration_presignal_gate_v0_8k.json", gate)


def _write_fake_v09_train_generation_gate(script: Any, output_dir: Path) -> None:
    trace_dir = output_dir / "isaac_runtime_train_generation_probe" / "isaac_runtime_heldout_rollout_traces"
    trace_dir.mkdir(parents=True, exist_ok=True)
    trace_paths: list[str] = []
    success_paths: list[str] = []
    for index in range(5):
        success = index < 3
        trace_id = f"train_success_{19000 + index}" if success else f"train_failure_{19200 + index}"
        rows = [
            {
                "step": step,
                "accepted": success,
                "proof_role": "trace_native_residual_train",
                "behavior_state_phase": "DESCEND" if step >= 2 else "ALIGN",
                "env_native_success_mask": success and step >= 4,
                "insertion_depth_m": 0.025 if success and step >= 4 else 0.012,
                "relative_x_m": 0.0 if success else 0.012,
                "relative_y_m": 0.0 if success else -0.004,
                "lateral_error_m": 0.001 if success else 0.013,
                "orientation_error_deg": 0.0,
                "previous_action_dx": 0.0,
                "previous_action_dy": 0.0,
                "previous_action_dz": 0.0,
                "previous_action_rx": 0.0,
                "previous_action_ry": 0.0,
                "previous_action_rz": 0.0,
                "previous_action_gripper": 1.0,
                "normalized_action": [0.0, 0.0, -0.12, 0.0, 0.0, 0.0, 1.0],
            }
            for step in range(6)
        ]
        payload = {
            "scenario": {"seed": 19000 + index, "scenario_id": trace_id},
            "summary": {
                "success": success,
                "failure_reason": "" if success else "ENV_NATIVE_STABILITY_WINDOW_NOT_REACHED",
                "env_native_max_consecutive_success_steps": 10 if success else 0,
            },
            "trace": rows,
        }
        path = trace_dir / f"train_generation_probe_{index:04d}_{trace_id}_isaac_trace.json"
        script.write_json(path, payload)
        trace_paths.append(str(path))
        if success:
            success_paths.append(str(path))
    gate = {
        "passed": True,
        "runtime_backend": "isaac_runtime",
        "actual_train_generation_evidence": True,
        "generated_success_count": 3,
        "generated_trace_paths": trace_paths,
        "generated_success_trace_paths": success_paths,
    }
    script.write_json(output_dir / "train_generation_runtime_gate.json", gate)


def _write_fake_v09_parent_evidence(script: Any, output_dir: Path) -> None:
    _write_fake_v08l_v08k_evidence(script, output_dir)
    script.build_v08l_authority_ceiling_uncurated_mix_audit(output_dir=output_dir)
    _write_fake_v09_train_generation_gate(script, output_dir)
    child_dir = output_dir / script.V08K_CHILD_OUTPUT_DIRNAME
    baseline = _fake_v08k_parent_policy(script, role="baseline")
    candidate = _fake_v08k_parent_policy(script, role="candidate")
    for payload, role in ((baseline, "baseline"), (candidate, "candidate")):
        payload.update(
            {
                "schema_version": script.V08K_POLICY_ARTIFACT_SCHEMA_VERSION,
                "policy_artifact_schema_version": script.V08K_POLICY_ARTIFACT_SCHEMA_VERSION,
                "policy_id": f"{role}_fake_v08k_policy",
                "policy_slice": "v0_8k",
                "slice_id": script.V08K_SLICE_ID,
                "parent_policy_slice": script.V08H_POLICY_SLICE_ID,
                "source_policy_slice": script.V08H_POLICY_SLICE_ID,
                "fresh_calibration_29000_29029_accessed": True,
                "fresh_heldout_27000_27049_accessed": False,
                "heldout_opened": False,
                "mvp2_closed": False,
                "policy_uplift_proven": False,
            }
        )
        payload["policy_artifact_sha256"] = script._sha256_payload_excluding(
            payload,
            "policy_artifact_sha256",
        )
    script.write_json(child_dir / "baseline_policy_artifact_v0_8k.json", baseline)
    script.write_json(child_dir / "candidate_policy_artifact_v0_8k.json", candidate)


def _fake_v08k_parent_policy(script: Any, *, role: str) -> dict[str, Any]:
    feature_count = len(script.FEATURE_SCHEMA_V07A)
    payload = {
        "schema_version": script.V08H_POLICY_ARTIFACT_SCHEMA_VERSION,
        "policy_id": f"{role}_fake_v08h_parent_policy",
        "policy_slice": "v0_8h",
        "slice_id": script.V08H_SLICE_ID,
        "parent_policy_slice": script.V08G_POLICY_SLICE_ID,
        "dataset_view_role": "candidate_curated" if role == "candidate" else "baseline_uncurated",
        "policy_class": script.RESIDUAL_POLICY_CLASS,
        "trainer": script.RESIDUAL_TRAINER,
        "trainer_family": script.RESIDUAL_TRAINER_FAMILY,
        "feature_schema": list(script.FEATURE_SCHEMA_V07A),
        "feature_schema_version": script.FEATURE_SCHEMA_V07A_VERSION,
        "phase_schema": list(script.BEHAVIOR_STATE_PHASES),
        "action_schema": list(script.ACTION_SCHEMA),
        "hyperparameters": {
            "ridge_lambda": 0.001,
            "phase_input_shared": True,
            "feature_standardization": "none_deterministic_domain_units",
            "selected_action_adapter_id": "isaac_signed_xy_downward_servo_v0",
            "trainer_family": script.RESIDUAL_TRAINER_FAMILY,
        },
        "weights": [[0.0] * len(script.ACTION_SCHEMA) for _ in range(feature_count)],
        "bias": [0.0] * len(script.ACTION_SCHEMA),
        "train_sample_count": 5,
        "selected_action_adapter_id": "isaac_signed_xy_downward_servo_v0",
        "selected_action_adapter_config": {"adapter_mode": "fake"},
        "selected_action_adapter_config_sha256": "same_selected_adapter_sha",
        "base_servo_config_sha256": "same_base_servo_sha",
        "authority_filter_config_sha256": "same_authority_sha",
        "final_post_adapter_authority_config_sha256": "same_final_z_sha",
        "final_post_adapter_xy_authority_config_sha256": "same_final_xy_sha",
        "shared_hysteresis_authority_config_sha256": "same_hysteresis_sha",
        "capture_conditioned_progress_authority_config_sha256": "same_capture_sha",
        "horizon_reserved_capture_authority_config_sha256": "same_horizon_sha",
        "deadline_precedence_horizon_authority_config_sha256": "same_deadline_sha",
        "early_centered_z_open_safe_entry_config_sha256": "same_safe_entry_sha",
        "fresh_calibration_28500_28529_accessed": False,
        "fresh_heldout_27000_27049_accessed": False,
        "mvp2_closed": False,
        "policy_uplift_proven": False,
    }
    payload["policy_artifact_sha256"] = script._sha256_payload_excluding(payload, "policy_artifact_sha256")
    return payload


def test_v08i_requires_failed_v08h_calibration_gate(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    with pytest.raises(ValueError, match="missing_v0_8h_failed_calibration_presignal_gate"):
        script.build_v08i_calibration_uplift_compression_diagnosis(output_dir=tmp_path)


def test_v08i_classifies_v08h_calibration_uplift_compression(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_fake_v08h_failed_calibration_result(script, tmp_path)

    diagnosis = script.build_v08i_calibration_uplift_compression_diagnosis(output_dir=tmp_path)

    taxonomy = diagnosis["failure_taxonomy"]
    assert diagnosis["policy_slice"] == "v0_8i"
    assert diagnosis["source_policy_slice"] == "v0_8h"
    assert diagnosis["mvp2_closed"] is False
    assert diagnosis["proof_authority"] is False
    assert diagnosis["fresh_heldout_27000_27049_accessed"] is False
    assert diagnosis["candidate_failures_total"] == 5
    assert diagnosis["candidate_failures_to_recover_for_calibration_gate"] == 2
    assert diagnosis["paired_outcome_counts"] == {"B1_C1": 23, "B0_C1": 2, "B1_C0": 0, "B0_C0": 5}
    assert diagnosis["baseline_success_compression"] is True
    assert taxonomy["late_seat_window_shortfall"]["count"] == 1
    assert taxonomy["under_depth_late_entry"]["count"] == 3
    assert taxonomy["centered_no_depth_contact_miss"]["count"] == 1
    assert taxonomy["unclassified"]["count"] == 0
    assert diagnosis["recommended_downstream_slice"] == "v0_8j_attribution_preserving_candidate_margin_repair"


def test_v08i_cli_runs_artifact_only_uplift_compression_diagnosis(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_fake_v08h_failed_calibration_result(script, tmp_path)

    result = script.main(
        [
            "--scenario-profile",
            "v0_6",
            "--policy-slice",
            "v0_8i",
            "--calibration-failure-diagnosis-only",
            "--output-dir",
            str(tmp_path),
        ]
    )

    child_dir = tmp_path / script.V08I_CHILD_OUTPUT_DIRNAME
    diagnosis = script.read_json(child_dir / "v0_8i_calibration_uplift_compression_diagnosis.json")
    evidence_manifest = script.read_json(tmp_path / "evidence_manifest.json")
    assert result == 0
    assert diagnosis["runtime_backend"] == "offline_artifact_diagnosis"
    assert evidence_manifest["proof_runtime"] == script.V08I_SLICE_ID
    assert evidence_manifest["mvp2_closed"] is False
    assert evidence_manifest["fresh_heldout_27000_27049_accessed"] is False
    assert evidence_manifest["recommended_downstream_slice"] == (
        "v0_8j_attribution_preserving_candidate_margin_repair"
    )


def test_v08j_requires_v08i_diagnosis(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_fake_v08h_failed_calibration_result_with_v08j_residuals(script, tmp_path)

    with pytest.raises(ValueError, match="missing_v0_8i_uplift_compression_diagnosis"):
        script.build_v08j_attribution_preserving_candidate_margin_diagnosis(output_dir=tmp_path)


def test_v08j_extracts_residual_margin_table_from_v08h_traces(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_fake_v08h_failed_calibration_result_with_v08j_residuals(script, tmp_path)
    script.build_v08i_calibration_uplift_compression_diagnosis(output_dir=tmp_path)

    table = script.build_v08j_residual_margin_table(output_dir=tmp_path)

    by_seed = {row["seed"]: row for row in table["pairs"]}
    assert table["paired_outcome_counts"] == {"B1_C1": 23, "B0_C1": 2, "B1_C0": 0, "B0_C0": 5}
    assert by_seed[28523]["paired_outcome"] == "B0_C1"
    assert by_seed[28523]["candidate"]["z_open_residual_z_median"] == pytest.approx(-0.151)
    assert by_seed[28523]["baseline"]["z_open_residual_z_median"] == pytest.approx(-0.086)
    assert by_seed[28523]["candidate_minus_baseline"]["z_open_residual_z_median_delta"] == pytest.approx(-0.065)


def test_v08j_recommends_rebalance_when_no_candidate_specific_recoverability(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_fake_v08h_failed_calibration_result_with_v08j_residuals(script, tmp_path)
    script.build_v08i_calibration_uplift_compression_diagnosis(output_dir=tmp_path)

    diagnosis = script.build_v08j_attribution_preserving_candidate_margin_diagnosis(output_dir=tmp_path)

    assert diagnosis["policy_slice"] == "v0_8j"
    assert diagnosis["source_policy_slice"] == "v0_8h"
    assert diagnosis["parent_diagnosis_policy_slice"] == "v0_8i"
    assert diagnosis["mvp2_closed"] is False
    assert diagnosis["proof_authority"] is False
    assert diagnosis["heldout_opened"] is False
    assert diagnosis["fresh_heldout_27000_27049_accessed"] is False
    assert diagnosis["paired_outcome_counts"] == {"B1_C1": 23, "B0_C1": 2, "B1_C0": 0, "B0_C0": 5}
    assert diagnosis["candidate_failures_total"] == 5
    assert diagnosis["candidate_failures_to_recover_for_calibration_gate"] == 2
    assert diagnosis["candidate_margin_positive_failure_count"] == 0
    assert diagnosis["unclassified_recoverability_count"] == 0
    assert diagnosis["recommended_downstream_slice"] == "v0_8k_candidate_training_signal_rebalance"


def test_v08j_cli_runs_artifact_only_candidate_margin_diagnosis(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_fake_v08h_failed_calibration_result_with_v08j_residuals(script, tmp_path)
    script.build_v08i_calibration_uplift_compression_diagnosis(output_dir=tmp_path)

    result = script.main(
        [
            "--scenario-profile",
            "v0_6",
            "--policy-slice",
            "v0_8j",
            "--calibration-failure-diagnosis-only",
            "--output-dir",
            str(tmp_path),
        ]
    )

    child_dir = tmp_path / script.V08J_CHILD_OUTPUT_DIRNAME
    diagnosis = script.read_json(child_dir / "v0_8j_attribution_preserving_candidate_margin_diagnosis.json")
    evidence_manifest = script.read_json(tmp_path / "evidence_manifest.json")
    assert result == 0
    assert diagnosis["runtime_backend"] == "offline_artifact_diagnosis"
    assert evidence_manifest["proof_runtime"] == script.V08J_SLICE_ID
    assert evidence_manifest["mvp2_closed"] is False
    assert evidence_manifest["fresh_heldout_27000_27049_accessed"] is False
    assert evidence_manifest["recommended_downstream_slice"] == "v0_8k_candidate_training_signal_rebalance"


def test_v08k_requires_v08j_rebalance_recommendation(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    with pytest.raises(ValueError, match="missing_v0_8j_candidate_margin_diagnosis"):
        script.build_v08k_candidate_training_signal_rebalance_slice(output_dir=tmp_path)


def test_v08k_rebalances_candidate_rows_without_changing_baseline(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_fake_v08k_parent_chain(script, tmp_path)
    _write_fake_v08k_source_train_views(script, tmp_path)
    child_dir = tmp_path / script.V08H_CHILD_OUTPUT_DIRNAME
    script.write_json(
        child_dir / "candidate_policy_artifact_v0_8h.json",
        _fake_v08k_parent_policy(script, role="candidate"),
    )
    script.write_json(
        child_dir / "baseline_policy_artifact_v0_8h.json",
        _fake_v08k_parent_policy(script, role="baseline"),
    )

    manifest = script.build_v08k_candidate_training_signal_rebalance_slice(output_dir=tmp_path)

    gate = manifest["training_signal_rebalance_gate"]
    assert manifest["policy_slice"] == "v0_8k"
    assert manifest["mvp2_closed"] is False
    assert manifest["heldout_opened"] is False
    assert manifest["fresh_heldout_27000_27049_accessed"] is False
    assert gate["passed"] is True
    assert gate["candidate_duplicate_rows"] > 0
    assert gate["candidate_rebalanced_rows"] > gate["candidate_source_rows"]
    assert gate["baseline_rebalanced_rows"] == gate["baseline_source_rows"]
    assert gate["candidate_duplicate_rows_by_reason"]["seat_hold_rows"] > 0
    assert gate["candidate_duplicate_rows_by_reason"]["centered_descent_rows"] > 0


def test_v08k_cli_builds_artifact_only_rebalance_slice(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_fake_v08k_parent_chain(script, tmp_path)
    _write_fake_v08k_source_train_views(script, tmp_path)
    child_dir = tmp_path / script.V08H_CHILD_OUTPUT_DIRNAME
    script.write_json(
        child_dir / "candidate_policy_artifact_v0_8h.json",
        _fake_v08k_parent_policy(script, role="candidate"),
    )
    script.write_json(
        child_dir / "baseline_policy_artifact_v0_8h.json",
        _fake_v08k_parent_policy(script, role="baseline"),
    )

    result = script.main(
        [
            "--scenario-profile",
            "v0_6",
            "--policy-slice",
            "v0_8k",
            "--candidate-training-signal-rebalance-only",
            "--output-dir",
            str(tmp_path),
        ]
    )

    manifest = script.read_json(
        tmp_path / script.V08K_CHILD_OUTPUT_DIRNAME / "v0_8k_candidate_training_signal_rebalance_manifest.json"
    )
    evidence_manifest = script.read_json(tmp_path / "evidence_manifest.json")
    assert result == 0
    assert manifest["proof_authority"] is False
    assert evidence_manifest["proof_runtime"] == script.V08K_SLICE_ID
    assert evidence_manifest["fresh_heldout_27000_27049_accessed"] is False


def test_v08l_detects_authority_ceiling_and_recommends_rebase(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_fake_v08l_v08k_evidence(script, tmp_path)

    report = script.build_v08l_authority_ceiling_uncurated_mix_audit(output_dir=tmp_path)

    assert report["policy_slice"] == "v0_8l"
    assert report["source_policy_slice"] == "v0_8k"
    assert report["baseline_calibration_success_rate"] == pytest.approx(26 / 30)
    assert report["candidate_calibration_success_rate"] == pytest.approx(27 / 30)
    assert report["candidate_baseline_success_gap"] == pytest.approx(1 / 30)
    assert report["authority_ceiling_detected"] is True
    assert report["uncurated_comparator_weak"] is True
    assert report["candidate_baseline_residual_z_mean_delta"] == pytest.approx(-0.001)
    assert report["baseline_rejected_row_count"] == 4
    assert report["baseline_rejected_descend_negative_z_fraction"] == pytest.approx(1.0)
    assert report["recommended_downstream_slice"] == "v0_9_fresh_attribution_preserving_uncurated_mix_rebase"
    assert report["heldout_opened"] is False
    assert report["fresh_heldout_27000_27049_accessed"] is False
    assert report["mvp2_closed"] is False
    assert report["policy_uplift_proven"] is False


def test_v08l_cli_runs_artifact_only_authority_ceiling_audit(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_fake_v08l_v08k_evidence(script, tmp_path)

    result = script.main(
        [
            "--scenario-profile",
            "v0_6",
            "--policy-slice",
            "v0_8l",
            "--authority-ceiling-audit-only",
            "--output-dir",
            str(tmp_path),
        ]
    )

    report = script.read_json(
        tmp_path
        / script.V08L_CHILD_OUTPUT_DIRNAME
        / "v0_8l_authority_ceiling_audit_report.json"
    )
    evidence_manifest = script.read_json(tmp_path / "evidence_manifest.json")
    assert result == 0
    assert report["proof_authority"] is False
    assert report["mvp2_closed"] is False
    assert report["recommended_downstream_slice"] == "v0_9_fresh_attribution_preserving_uncurated_mix_rebase"
    assert evidence_manifest["proof_runtime"] == script.V08L_SLICE_ID
    assert evidence_manifest["fresh_heldout_27000_27049_accessed"] is False


def test_v09_requires_v08l_authority_ceiling_audit(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    with pytest.raises(ValueError, match="missing_v0_8l_authority_ceiling_audit"):
        script.build_v09_fresh_uncurated_mix_rebase_slice(output_dir=tmp_path)


def test_v09_builds_preregistered_uncurated_mix_and_keeps_candidate_unchanged(
    tmp_path: Path,
) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_fake_v09_parent_evidence(script, tmp_path)

    manifest = script.build_v09_fresh_uncurated_mix_rebase_slice(output_dir=tmp_path)

    gate = manifest["uncurated_mix_rebase_gate"]
    assert manifest["policy_slice"] == "v0_9"
    assert manifest["heldout_opened"] is False
    assert manifest["fresh_heldout_27000_27049_accessed"] is False
    assert manifest["fresh_calibration_seed_range"] == [30000, 30029]
    assert gate["passed"] is True
    assert gate["baseline_noise_mix_ratio"] == pytest.approx(0.40)
    assert gate["accepted_failure_ratio"] == pytest.approx(0.40)
    assert gate["baseline_failure_material_row_count"] > 0
    assert 0.35 <= gate["baseline_actual_failure_material_ratio"] <= 0.45
    assert gate["candidate_rows_unchanged_from_v08k"] is True
    assert gate["peer_fairness_mismatch_keys"] == []
    assert gate["fresh_heldout_27000_27049_accessed"] is False


def test_v09_cli_builds_artifact_only_uncurated_mix_rebase(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_fake_v09_parent_evidence(script, tmp_path)

    result = script.main(
        [
            "--scenario-profile",
            "v0_6",
            "--policy-slice",
            "v0_9",
            "--fresh-uncurated-mix-rebase-only",
            "--output-dir",
            str(tmp_path),
        ]
    )

    manifest = script.read_json(
        tmp_path / script.V09_CHILD_OUTPUT_DIRNAME / "v0_9_uncurated_mix_rebase_manifest.json"
    )
    evidence_manifest = script.read_json(tmp_path / "evidence_manifest.json")
    assert result == 0
    assert manifest["proof_authority"] is False
    assert evidence_manifest["proof_runtime"] == script.V09_SLICE_ID
    assert evidence_manifest["fresh_heldout_27000_27049_accessed"] is False


def test_v09_fresh_manifest_uses_30000_calibration_and_sealed_27000_heldout(
    tmp_path: Path,
) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_fake_v09_parent_evidence(script, tmp_path)
    rebase_manifest = script.build_v09_fresh_uncurated_mix_rebase_slice(output_dir=tmp_path)

    fresh_manifest = script.build_v09_fresh_manifest(
        output_dir=tmp_path,
        rebase_manifest=rebase_manifest,
    )
    calibration_manifest = script._v09_runtime_manifest_for_split(
        fresh_manifest=fresh_manifest,
        split="calibration",
    )
    heldout_manifest = script._v09_runtime_manifest_for_split(
        fresh_manifest=fresh_manifest,
        split="held_out",
    )

    assert fresh_manifest["policy_slice"] == "v0_9"
    assert fresh_manifest["fresh_split_manifest"]["calibration"]["seed_range"] == [30000, 30029]
    assert fresh_manifest["fresh_split_manifest"]["held_out"]["seed_range"] == [27000, 27049]
    assert [row["seed"] for row in calibration_manifest["scenarios"]] == list(range(30000, 30030))
    assert [row["seed"] for row in heldout_manifest["scenarios"]] == list(range(27000, 27050))
    assert calibration_manifest["calibration_opened"] is True
    assert calibration_manifest["heldout_opened"] is False
    assert calibration_manifest["fresh_calibration_30000_30029_accessed"] is True
    assert calibration_manifest["fresh_heldout_27000_27049_accessed"] is False
    assert heldout_manifest["calibration_opened"] is True
    assert heldout_manifest["heldout_opened"] is True
    assert heldout_manifest["proof_authority"] is True
    assert heldout_manifest["fresh_calibration_30000_30029_accessed"] is True
    assert heldout_manifest["fresh_heldout_27000_27049_accessed"] is True


def test_v09_runtime_cli_rejects_clean_before_isaac(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    with pytest.raises(ValueError, match="fresh-uncurated-mix-rebase-runtime.*do not pass --clean"):
        script.main(
            [
                "--scenario-profile",
                "v0_6",
                "--policy-slice",
                "v0_9",
                "--fresh-uncurated-mix-rebase-runtime",
                "--clean",
                "--output-dir",
                str(tmp_path),
            ]
        )


def _write_fake_v09a_heldout_trace(
    script: Any,
    path: Path,
    *,
    scenario_id: str,
    seed: int,
    success: bool,
    max_depth: float,
    min_lateral: float,
) -> None:
    rows = []
    for step in range(5):
        rows.append(
            {
                "step": step,
                "phase": "DESCEND" if step >= 1 else "APPROACH",
                "env_native_success_mask": success and step >= 3,
                "insertion_depth_m": max_depth * (step + 1) / 5.0,
                "relative_x_m": min_lateral,
                "relative_y_m": 0.0,
                "lateral_error_m": min_lateral + (0.0005 if step == 0 else 0.0),
                "orientation_error_deg": 0.0,
                "normalized_action": [0.0, 0.0, -0.12 if step >= 1 else 0.0, 0.0, 0.0, 0.0, 1.0],
            }
        )
    script.write_json(
        path,
        {
            "schema_version": "rdf_mvp2b_isaac_runtime_trace_v0.1.0",
            "runtime_backend": "isaac_runtime",
            "scenario": {"scenario_id": scenario_id, "seed": seed},
            "summary": {
                "success": success,
                "failure_reason": "" if success else "ENV_NATIVE_STABILITY_WINDOW_NOT_REACHED",
                "env_native_max_consecutive_success_steps": 10 if success else 0,
            },
            "trace": rows,
        },
    )


def _write_fake_v09a_failed_heldout_evidence(script: Any, output_dir: Path) -> dict[str, Any]:
    child_dir = output_dir / script.V09_CHILD_OUTPUT_DIRNAME
    trace_dir = child_dir / "isaac_runtime_fresh_heldout_v0_9" / "isaac_runtime_heldout_rollout_traces"
    trace_dir.mkdir(parents=True, exist_ok=True)
    baseline_failures = {27002, 27009, 27016, 27022, 27041, 27045}
    candidate_failures = {27002, 27016, 27041}

    def rollout(role: str, seed: int, success: bool, index: int) -> dict[str, Any]:
        scenario_id = f"held_out_{seed}"
        trace_path = trace_dir / f"{role}_{index:04d}_{scenario_id}_isaac_trace.json"
        _write_fake_v09a_heldout_trace(
            script,
            trace_path,
            scenario_id=scenario_id,
            seed=seed,
            success=success,
            max_depth=0.025 if success else 0.021 + (seed % 3) * 0.001,
            min_lateral=0.0001 + (seed % 4) * 0.0001,
        )
        return {
            "rollout_id": f"{role}_isaac_{index:04d}",
            "scenario_id": scenario_id,
            "seed": seed,
            "success": success,
            "env_native_rollout_success": success,
            "env_native_success_available": True,
            "env_native_max_consecutive_success_steps": 10 if success else 0,
            "failure_reason": "" if success else "ENV_NATIVE_STABILITY_WINDOW_NOT_REACHED",
            "rollout_log_ref": str(trace_path),
            "steps": 130,
        }

    baseline_rollouts = []
    candidate_rollouts = []
    for index, seed in enumerate(range(27000, 27050)):
        baseline_rollouts.append(rollout("baseline", seed, seed not in baseline_failures, index))
        candidate_rollouts.append(rollout("candidate", seed, seed not in candidate_failures, index))

    rollout_dir = child_dir / "external_rollouts"
    rollout_dir.mkdir(parents=True, exist_ok=True)
    baseline_rollouts_path = rollout_dir / "baseline_external_rollouts.json"
    candidate_rollouts_path = rollout_dir / "candidate_external_rollouts.json"
    script.write_json(
        baseline_rollouts_path,
        {
            "schema_version": script.ROLLOUT_SCHEMA_VERSION,
            "source_kind": "external_heldout_policy_eval",
            "policy_role": "baseline",
            "rollout_results": baseline_rollouts,
        },
    )
    script.write_json(
        candidate_rollouts_path,
        {
            "schema_version": script.ROLLOUT_SCHEMA_VERSION,
            "source_kind": "external_heldout_policy_eval",
            "policy_role": "candidate",
            "rollout_results": candidate_rollouts,
        },
    )
    gate = {
        "schema_version": script.V09_HELDOUT_CLOSURE_SCHEMA_VERSION,
        "policy_slice": script.V09_POLICY_SLICE_ID,
        "slice_id": script.V09_SLICE_ID,
        "runtime_backend": "isaac_runtime",
        "proof_runtime": "dedicated_isaac_connector_insertion_evaluator",
        "actual_rollouts_per_policy": 50,
        "baseline_success_rate": 0.88,
        "candidate_success_rate": 0.94,
        "curated_vs_uncurated_uplift": 0.06,
        "baseline_external_rollouts": str(baseline_rollouts_path),
        "candidate_external_rollouts": str(candidate_rollouts_path),
        "heldout_opened": True,
        "fresh_heldout_27000_27049_accessed": True,
        "mvp2_closed": False,
        "mvp2c_close_minimum_passed": False,
        "policy_uplift_proven": False,
        "proof_eligible": False,
        "blockers": [
            "Existing MVP-2 learning validator did not produce proof-eligible positive uplift >= 0.20."
        ],
    }
    gate["heldout_closure_gate_sha256"] = script._sha256_payload_excluding(
        gate,
        "heldout_closure_gate_sha256",
    )
    script.write_json(child_dir / "heldout_closure_gate_v0_9.json", gate)
    return gate


def test_v09a_requires_failed_v09_heldout_gate(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    with pytest.raises(ValueError, match="missing_v0_9_heldout_closure_gate"):
        script.build_v09a_heldout_uplift_shortfall_diagnosis(output_dir=tmp_path)


def test_v09a_classifies_baseline_ceiling_and_opened_heldout_cannot_close(
    tmp_path: Path,
) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_fake_v09a_failed_heldout_evidence(script, tmp_path)

    report = script.build_v09a_heldout_uplift_shortfall_diagnosis(output_dir=tmp_path)

    assert report["policy_slice"] == "v0_9a"
    assert report["source_policy_slice"] == "v0_9"
    assert report["paired_outcome_counts"] == {"B1_C1": 44, "B1_C0": 0, "B0_C1": 3, "B0_C0": 3}
    assert report["baseline_failure_seeds"] == [27002, 27009, 27016, 27022, 27041, 27045]
    assert report["candidate_failure_seeds"] == [27002, 27016, 27041]
    assert report["candidate_recovered_baseline_failure_seeds"] == [27009, 27022, 27045]
    assert report["common_failure_seeds"] == [27002, 27016, 27041]
    assert report["baseline_ceiling_compression"] is True
    assert report["candidate_non_regression"] is True
    assert report["max_possible_uplift_on_opened_heldout"] == pytest.approx(0.12)
    assert report["opened_heldout_can_no_longer_close_minimum"] is True
    assert report["failure_mix_did_not_create_sufficient_uncurated_heldout_gap"] is True
    assert report["mvp2_closed"] is False
    assert report["policy_uplift_proven"] is False
    assert report["same_heldout_reuse_allowed_for_closure"] is False
    assert report["recommended_downstream_slice"] == "v0_10_fresh_comparator_stress_slice"


def test_v09a_cli_runs_artifact_only_shortfall_diagnosis(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_fake_v09a_failed_heldout_evidence(script, tmp_path)

    result = script.main(
        [
            "--scenario-profile",
            "v0_6",
            "--policy-slice",
            "v0_9a",
            "--heldout-uplift-shortfall-diagnosis-only",
            "--output-dir",
            str(tmp_path),
        ]
    )

    child_dir = tmp_path / script.V09A_CHILD_OUTPUT_DIRNAME
    report = script.read_json(child_dir / "v0_9a_heldout_uplift_shortfall_diagnosis_report.json")
    evidence_manifest = script.read_json(tmp_path / "evidence_manifest.json")
    assert result == 0
    assert report["runtime_backend"] == "offline_artifact_diagnosis"
    assert evidence_manifest["proof_runtime"] == script.V09A_SLICE_ID
    assert evidence_manifest["mvp2_closed"] is False
    assert evidence_manifest["policy_uplift_proven"] is False
    assert evidence_manifest["fresh_heldout_27000_27049_accessed"] is True
    assert evidence_manifest["recommended_downstream_slice"] == "v0_10_fresh_comparator_stress_slice"


def _write_fake_v10_parent_evidence(script: Any, output_dir: Path) -> None:
    _write_fake_v09_parent_evidence(script, output_dir)
    script.build_v09_fresh_uncurated_mix_rebase_slice(output_dir=output_dir)
    _write_fake_v09a_failed_heldout_evidence(script, output_dir)
    script.build_v09a_heldout_uplift_shortfall_diagnosis(output_dir=output_dir)


def _write_fake_v10_authority_trace(
    script: Any,
    path: Path,
    *,
    policy_slice: str,
    scenario_id: str,
    seed: int,
    success: bool,
    authority_present: bool,
) -> None:
    if authority_present:
        diagnostics = {
            "policy_slice": policy_slice,
            "behavior_state_phase": "ALIGN",
            "behavior_state_phase_source": "shared_stateful_hysteresis_authority_v0_7e",
            "shared_hysteresis_authority_id": "shared_stateful_hysteresis_authority_v0_7e",
            "final_post_adapter_authority_id": "final_post_adapter_z_authority_gate_v0_7d",
            "final_post_adapter_xy_authority_id": "final_post_adapter_xy_authority_gate_v0_7o",
            "final_post_adapter_z_motion_allowed": False,
            "z_motion_block_reason": "final_post_adapter_align_z_blocked",
            "post_adapter_action_vector": [0.02, 0.02, 0.0, 0.0, 0.0, 0.0, 1.0],
            "no_mutation_after_final_post_adapter_authority": True,
            "early_centered_z_open_safe_entry_applied": False,
        }
    else:
        diagnostics = {
            "policy_slice": policy_slice,
            "behavior_state_phase": "ALIGN",
            "behavior_state_phase_source": "derived_v0_7a_2_runtime_rule",
            "z_motion_block_reason": "no_v06_controller",
            "post_adapter_action_vector": [0.05, -0.05, -0.16, 0.0, 0.0, 0.0, 1.0],
            "no_mutation_after_final_post_adapter_authority": False,
        }
    script.write_json(
        path,
        {
            "schema_version": "rdf_mvp2b_isaac_runtime_trace_v0.1.0",
            "runtime_backend": "isaac_runtime",
            "scenario": {"scenario_id": scenario_id, "seed": seed},
            "summary": {
                "success": success,
                "env_native_rollout_success": success,
                "env_native_max_consecutive_success_steps": 10 if success else 0,
                "failure_reason": "" if success else "ENV_NATIVE_STABILITY_WINDOW_NOT_REACHED",
                "steps": 2,
            },
            "trace": [
                {
                    "step": 0,
                    "phase": "APPROACH",
                    "behavior_state_phase": "ALIGN",
                    "insertion_depth_m": 0.0,
                    "relative_x_m": 0.004,
                    "relative_y_m": 0.003,
                    "lateral_error_m": 0.005,
                    "orientation_error_deg": 0.08,
                    "env_native_success": False,
                    "controller_action_diagnostics": diagnostics,
                },
                {
                    "step": 1,
                    "phase": "APPROACH",
                    "behavior_state_phase": "ALIGN",
                    "insertion_depth_m": 0.0 if not success else 0.025,
                    "relative_x_m": 0.004,
                    "relative_y_m": 0.004,
                    "lateral_error_m": 0.006,
                    "orientation_error_deg": 0.08,
                    "env_native_success": success,
                    "controller_action_diagnostics": diagnostics,
                },
            ],
        },
    )


def _write_fake_v10_failed_calibration_evidence(script: Any, output_dir: Path) -> None:
    _write_fake_v10_parent_evidence(script, output_dir)
    script.build_v10_fresh_comparator_stress_slice(output_dir=output_dir)

    v09_child = output_dir / script.V09_CHILD_OUTPUT_DIRNAME
    v09_trace_dir = (
        v09_child
        / "isaac_runtime_fresh_calibration_v0_9"
        / "isaac_runtime_heldout_rollout_traces"
    )
    v09_trace_dir.mkdir(parents=True, exist_ok=True)
    v09_rollout_dir = v09_child / "calibration_external_rollouts"
    v09_rollout_dir.mkdir(parents=True, exist_ok=True)
    v09_candidate_rollouts = []
    for index, seed in enumerate(range(30000, 30030)):
        scenario_id = f"calibration_{seed}"
        trace_path = v09_trace_dir / f"candidate_{index:04d}_{scenario_id}_isaac_trace.json"
        success = index < 27
        _write_fake_v10_authority_trace(
            script,
            trace_path,
            policy_slice="v0_9",
            scenario_id=scenario_id,
            seed=seed,
            success=success,
            authority_present=True,
        )
        v09_candidate_rollouts.append(
            {
                "rollout_id": f"candidate_isaac_{index:04d}",
                "scenario_id": scenario_id,
                "success": success,
                "env_native_rollout_success": success,
                "env_native_max_consecutive_success_steps": 10 if success else 0,
                "rollout_log_ref": str(trace_path),
            }
        )
    script.write_json(v09_rollout_dir / "candidate_calibration_rollouts_v0_9.json", v09_candidate_rollouts)

    v10_child = output_dir / script.V10_CHILD_OUTPUT_DIRNAME
    v10_trace_dir = (
        v10_child
        / "isaac_runtime_fresh_calibration_v0_10"
        / "isaac_runtime_heldout_rollout_traces"
    )
    v10_trace_dir.mkdir(parents=True, exist_ok=True)
    v10_rollout_dir = v10_child / "calibration_external_rollouts"
    v10_rollout_dir.mkdir(parents=True, exist_ok=True)
    candidate_rollouts = []
    baseline_rollouts = []
    for index, seed in enumerate(range(31000, 31030)):
        scenario_id = f"calibration_{seed}"
        candidate_success = seed == 31012
        for role in ("candidate", "baseline"):
            trace_path = v10_trace_dir / f"{role}_{index:04d}_{scenario_id}_isaac_trace.json"
            _write_fake_v10_authority_trace(
                script,
                trace_path,
                policy_slice="v0_10",
                scenario_id=scenario_id,
                seed=seed,
                success=candidate_success if role == "candidate" else False,
                authority_present=False,
            )
        candidate_rollouts.append(
            {
                "rollout_id": f"candidate_isaac_{index:04d}",
                "scenario_id": scenario_id,
                "success": candidate_success,
                "env_native_rollout_success": candidate_success,
                "env_native_max_consecutive_success_steps": 10 if candidate_success else 0,
                "rollout_log_ref": str(
                    v10_trace_dir / f"candidate_{index:04d}_{scenario_id}_isaac_trace.json"
                ),
            }
        )
        baseline_rollouts.append(
            {
                "rollout_id": f"baseline_isaac_{index:04d}",
                "scenario_id": scenario_id,
                "success": False,
                "env_native_rollout_success": False,
                "env_native_max_consecutive_success_steps": 0,
                "rollout_log_ref": str(
                    v10_trace_dir / f"baseline_{index:04d}_{scenario_id}_isaac_trace.json"
                ),
            }
        )
    script.write_json(v10_rollout_dir / "candidate_calibration_rollouts_v0_10.json", candidate_rollouts)
    script.write_json(v10_rollout_dir / "baseline_calibration_rollouts_v0_10.json", baseline_rollouts)
    gate = {
        "schema_version": script.V10_CALIBRATION_PRESIGNAL_SCHEMA_VERSION,
        "policy_slice": "v0_10",
        "slice_id": script.V10_SLICE_ID,
        "runtime_backend": "isaac_runtime",
        "passed": False,
        "failure_reason": "candidate_calibration_success_below_v0_10_minimum",
        "baseline_calibration_success_count": 0,
        "baseline_calibration_rollout_count": 30,
        "baseline_calibration_success_rate": 0.0,
        "candidate_calibration_success_count": 1,
        "candidate_calibration_rollout_count": 30,
        "candidate_calibration_success_rate": 1.0 / 30.0,
        "candidate_baseline_success_gap": 1.0 / 30.0,
        "heldout_allowed": False,
        "heldout_opened": False,
        "fresh_calibration_31000_31029_accessed": True,
        "fresh_heldout_32000_32049_accessed": False,
        "mvp2_closed": False,
        "policy_uplift_proven": False,
    }
    gate["calibration_presignal_gate_sha256"] = script._sha256_payload_excluding(
        gate,
        "calibration_presignal_gate_sha256",
    )
    script.write_json(v10_child / "calibration_presignal_gate_v0_10.json", gate)


def _write_fake_v10_gap_compression_evidence(script: Any, output_dir: Path) -> None:
    _write_fake_v10_parent_evidence(script, output_dir)
    script.build_v10_fresh_comparator_stress_slice(output_dir=output_dir)

    v10_child = output_dir / script.V10_CHILD_OUTPUT_DIRNAME
    v10_trace_dir = (
        v10_child
        / "isaac_runtime_fresh_calibration_v0_10"
        / "isaac_runtime_heldout_rollout_traces"
    )
    v10_trace_dir.mkdir(parents=True, exist_ok=True)
    v10_rollout_dir = v10_child / "calibration_external_rollouts"
    v10_rollout_dir.mkdir(parents=True, exist_ok=True)
    baseline_failure_seeds = {31007, 31010, 31017, 31018, 31022, 31024, 31026}
    candidate_failure_seeds = {31007, 31010, 31017, 31022, 31024}
    candidate_rollouts = []
    baseline_rollouts = []
    for index, seed in enumerate(range(31000, 31030)):
        scenario_id = f"calibration_{seed}"
        baseline_success = seed not in baseline_failure_seeds
        candidate_success = seed not in candidate_failure_seeds
        for role, success in (("baseline", baseline_success), ("candidate", candidate_success)):
            trace_path = v10_trace_dir / f"{role}_{index:04d}_{scenario_id}_isaac_trace.json"
            _write_fake_v10_authority_trace(
                script,
                trace_path,
                policy_slice="v0_10",
                scenario_id=scenario_id,
                seed=seed,
                success=success,
                authority_present=True,
            )
        candidate_rollouts.append(
            {
                "rollout_id": f"candidate_isaac_{index:04d}",
                "scenario_id": scenario_id,
                "seed": seed,
                "success": candidate_success,
                "env_native_rollout_success": candidate_success,
                "env_native_max_consecutive_success_steps": 10 if candidate_success else 0,
                "rollout_log_ref": str(
                    v10_trace_dir / f"candidate_{index:04d}_{scenario_id}_isaac_trace.json"
                ),
            }
        )
        baseline_rollouts.append(
            {
                "rollout_id": f"baseline_isaac_{index:04d}",
                "scenario_id": scenario_id,
                "seed": seed,
                "success": baseline_success,
                "env_native_rollout_success": baseline_success,
                "env_native_max_consecutive_success_steps": 10 if baseline_success else 0,
                "rollout_log_ref": str(
                    v10_trace_dir / f"baseline_{index:04d}_{scenario_id}_isaac_trace.json"
                ),
            }
        )
    script.write_json(v10_rollout_dir / "candidate_calibration_rollouts_v0_10.json", candidate_rollouts)
    script.write_json(v10_rollout_dir / "baseline_calibration_rollouts_v0_10.json", baseline_rollouts)
    gate = {
        "schema_version": script.V10_CALIBRATION_PRESIGNAL_SCHEMA_VERSION,
        "policy_slice": "v0_10",
        "slice_id": script.V10_SLICE_ID,
        "runtime_backend": "isaac_runtime",
        "passed": False,
        "failure_reason": "candidate_baseline_success_gap_below_v0_10_minimum",
        "baseline_calibration_success_count": 23,
        "baseline_calibration_rollout_count": 30,
        "baseline_calibration_success_rate": 23.0 / 30.0,
        "candidate_calibration_success_count": 25,
        "candidate_calibration_rollout_count": 30,
        "candidate_calibration_success_rate": 25.0 / 30.0,
        "candidate_baseline_success_gap": 2.0 / 30.0,
        "heldout_allowed": False,
        "heldout_opened": False,
        "fresh_calibration_31000_31029_accessed": True,
        "fresh_heldout_32000_32049_accessed": False,
        "mvp2_closed": False,
        "policy_uplift_proven": False,
        "baseline_calibration_rollout_path": str(
            v10_rollout_dir / "baseline_calibration_rollouts_v0_10.json"
        ),
        "candidate_calibration_rollout_path": str(
            v10_rollout_dir / "candidate_calibration_rollouts_v0_10.json"
        ),
    }
    gate["calibration_presignal_gate_sha256"] = script._sha256_payload_excluding(
        gate,
        "calibration_presignal_gate_sha256",
    )
    script.write_json(v10_child / "calibration_presignal_gate_v0_10.json", gate)


def test_v10_requires_v09a_shortfall_diagnosis(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    with pytest.raises(ValueError, match="missing_v0_9a_heldout_uplift_shortfall_diagnosis"):
        script.build_v10_fresh_comparator_stress_slice(output_dir=tmp_path)


def test_v10_builds_fresh_comparator_stress_views(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_fake_v10_parent_evidence(script, tmp_path)

    manifest = script.build_v10_fresh_comparator_stress_slice(output_dir=tmp_path)

    gate = manifest["comparator_stress_gate"]
    assert manifest["policy_slice"] == "v0_10"
    assert manifest["fresh_calibration_seed_range"] == [31000, 31029]
    assert manifest["fresh_heldout_seed_range"] == [32000, 32049]
    assert manifest["heldout_opened"] is False
    assert manifest["fresh_heldout_32000_32049_accessed"] is False
    assert gate["passed"] is True
    assert gate["baseline_failure_material_ratio_target"] == pytest.approx(0.70)
    assert 0.65 <= gate["baseline_actual_failure_material_ratio"] <= 0.75
    assert gate["candidate_rows_unchanged_from_v09"] is True
    assert gate["peer_fairness_mismatch_keys"] == []


def test_v10_cli_builds_artifact_only_comparator_stress(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_fake_v10_parent_evidence(script, tmp_path)

    result = script.main(
        [
            "--scenario-profile",
            "v0_6",
            "--policy-slice",
            "v0_10",
            "--fresh-comparator-stress-only",
            "--output-dir",
            str(tmp_path),
        ]
    )

    manifest = script.read_json(
        tmp_path / script.V10_CHILD_OUTPUT_DIRNAME / "v0_10_comparator_stress_manifest.json"
    )
    evidence_manifest = script.read_json(tmp_path / "evidence_manifest.json")
    assert result == 0
    assert manifest["proof_authority"] is False
    assert evidence_manifest["proof_runtime"] == script.V10_SLICE_ID
    assert evidence_manifest["fresh_heldout_32000_32049_accessed"] is False


def test_v10_fresh_manifest_uses_31000_calibration_and_sealed_32000_heldout(
    tmp_path: Path,
) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_fake_v10_parent_evidence(script, tmp_path)
    stress_manifest = script.build_v10_fresh_comparator_stress_slice(output_dir=tmp_path)

    fresh_manifest = script.build_v10_fresh_manifest(
        output_dir=tmp_path,
        stress_manifest=stress_manifest,
    )
    calibration_manifest = script._v10_runtime_manifest_for_split(
        fresh_manifest=fresh_manifest,
        split="calibration",
    )
    heldout_manifest = script._v10_runtime_manifest_for_split(
        fresh_manifest=fresh_manifest,
        split="held_out",
    )

    assert fresh_manifest["policy_slice"] == "v0_10"
    assert fresh_manifest["fresh_split_manifest"]["calibration"]["seed_range"] == [31000, 31029]
    assert fresh_manifest["fresh_split_manifest"]["held_out"]["seed_range"] == [32000, 32049]
    assert [row["seed"] for row in calibration_manifest["scenarios"]] == list(range(31000, 31030))
    assert [row["seed"] for row in heldout_manifest["scenarios"]] == list(range(32000, 32050))
    assert calibration_manifest["calibration_opened"] is True
    assert calibration_manifest["heldout_opened"] is False
    assert calibration_manifest["fresh_calibration_31000_31029_accessed"] is True
    assert calibration_manifest["fresh_heldout_32000_32049_accessed"] is False
    assert heldout_manifest["calibration_opened"] is True
    assert heldout_manifest["heldout_opened"] is True
    assert heldout_manifest["proof_authority"] is True
    assert heldout_manifest["fresh_calibration_31000_31029_accessed"] is True
    assert heldout_manifest["fresh_heldout_32000_32049_accessed"] is True


def test_v10_runtime_cli_rejects_clean_before_isaac(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    with pytest.raises(ValueError, match="fresh-comparator-stress-runtime.*do not pass --clean"):
        script.main(
            [
                "--scenario-profile",
                "v0_6",
                "--policy-slice",
                "v0_10",
                "--fresh-comparator-stress-runtime",
                "--clean",
                "--output-dir",
                str(tmp_path),
            ]
        )


def test_v10a_classifies_runtime_policy_slice_authority_lineage_missing(
    tmp_path: Path,
) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_fake_v10_failed_calibration_evidence(script, tmp_path)

    report = script.build_v10a_calibration_collapse_diagnosis(output_dir=tmp_path)

    assert report["policy_slice"] == "v0_10a"
    assert report["source_policy_slice"] == "v0_10"
    assert report["runtime_backend"] == "offline_artifact_diagnosis"
    assert report["v0_10_calibration_success"] == {"baseline": 0, "candidate": 1, "total": 30}
    assert report["v0_9_candidate_calibration_success"] == {"candidate": 27, "total": 30}
    assert report["candidate_weights_unchanged_from_v09"] is True
    assert report["candidate_authority_hashes_unchanged_from_v09"] is True
    assert report["v0_10_authority_diagnostics"]["shared_hysteresis_authority_count"] == 0
    assert report["v0_9_authority_diagnostics"]["shared_hysteresis_authority_count"] > 0
    assert report["primary_root_cause_class"] == "RUNTIME_POLICY_SLICE_AUTHORITY_LINEAGE_MISSING"
    assert report["recommended_downstream_slice"] == (
        "v0_10b_runtime_policy_slice_authority_lineage_repair"
    )
    assert report["fresh_heldout_32000_32049_accessed"] is False
    assert report["mvp2_closed"] is False
    assert report["policy_uplift_proven"] is False


def test_v10a_cli_runs_artifact_only_calibration_collapse_diagnosis(
    tmp_path: Path,
) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_fake_v10_failed_calibration_evidence(script, tmp_path)

    result = script.main(
        [
            "--scenario-profile",
            "v0_6",
            "--policy-slice",
            "v0_10a",
            "--fresh-comparator-calibration-diagnosis-only",
            "--output-dir",
            str(tmp_path),
        ]
    )

    report = script.read_json(
        tmp_path
        / script.V10A_CHILD_OUTPUT_DIRNAME
        / "v0_10a_calibration_collapse_diagnosis_report.json"
    )
    evidence_manifest = script.read_json(tmp_path / "evidence_manifest.json")
    assert result == 0
    assert report["primary_root_cause_class"] == "RUNTIME_POLICY_SLICE_AUTHORITY_LINEAGE_MISSING"
    assert evidence_manifest["proof_runtime"] == script.V10A_SLICE_ID
    assert evidence_manifest["recommended_downstream_slice"] == (
        "v0_10b_runtime_policy_slice_authority_lineage_repair"
    )
    assert evidence_manifest["fresh_heldout_32000_32049_accessed"] is False


def test_v10b_runtime_policy_slice_uses_v09_derived_authority_lineage(
    tmp_path: Path,
) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    evaluator = load_script("run_mvp2b_isaac_proof_evaluator")
    _write_fake_v10_failed_calibration_evidence(script, tmp_path)
    policy = script.read_json(
        tmp_path / script.V10_CHILD_OUTPUT_DIRNAME / "candidate_policy_artifact_v0_10.json"
    )

    assert policy["policy_slice"] == "v0_10"
    assert evaluator.V10_POLICY_SLICE_ID == "v0_10"
    assert evaluator.V10_POLICY_SLICE_ID in evaluator.V08H_DERIVED_POLICY_SLICE_IDS
    assert evaluator.V10_POLICY_SLICE_ID in evaluator.V07E_HYSTERESIS_RUNTIME_POLICY_SLICE_IDS
    assert evaluator.V10_POLICY_SLICE_ID in evaluator.V07B_BASE_SERVO_RUNTIME_POLICY_SLICE_IDS
    assert evaluator.V10_POLICY_SLICE_ID in evaluator.V07C_AUTHORITY_RUNTIME_POLICY_SLICE_IDS
    assert evaluator.V10_POLICY_SLICE_ID in evaluator.V07D_FINAL_AUTHORITY_RUNTIME_POLICY_SLICE_IDS


def test_v10c_classifies_calibration_gap_compression_by_baseline_floor(
    tmp_path: Path,
) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_fake_v10_gap_compression_evidence(script, tmp_path)

    report = script.build_v10c_calibration_gap_compression_diagnosis(output_dir=tmp_path)

    assert report["policy_slice"] == "v0_10c"
    assert report["source_policy_slice"] == "v0_10"
    assert report["paired_outcome_counts"] == {"B1_C1": 23, "B1_C0": 0, "B0_C1": 2, "B0_C0": 5}
    assert report["baseline_calibration_success_count"] == 23
    assert report["candidate_calibration_success_count"] == 25
    assert report["baseline_ceiling_compression"] is True
    assert report["candidate_non_regression"] is True
    assert report["shared_authority_success_floor_detected"] is True
    assert report["primary_root_cause_class"] == (
        "CALIBRATION_GAP_COMPRESSED_BY_BASELINE_SUCCESS_FLOOR"
    )
    assert report["recommended_downstream_slice"] == (
        "v0_11_attribution_preserving_low_floor_comparator_slice"
    )
    assert report["fresh_heldout_32000_32049_accessed"] is False
    assert report["mvp2_closed"] is False
    assert report["policy_uplift_proven"] is False


def test_v10c_cli_runs_artifact_only_gap_compression_diagnosis(
    tmp_path: Path,
) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_fake_v10_gap_compression_evidence(script, tmp_path)

    result = script.main(
        [
            "--scenario-profile",
            "v0_6",
            "--policy-slice",
            "v0_10c",
            "--fresh-comparator-gap-compression-diagnosis-only",
            "--output-dir",
            str(tmp_path),
        ]
    )

    report = script.read_json(
        tmp_path
        / script.V10C_CHILD_OUTPUT_DIRNAME
        / "v0_10c_calibration_gap_compression_diagnosis_report.json"
    )
    evidence_manifest = script.read_json(tmp_path / "evidence_manifest.json")
    assert result == 0
    assert report["primary_root_cause_class"] == (
        "CALIBRATION_GAP_COMPRESSED_BY_BASELINE_SUCCESS_FLOOR"
    )
    assert evidence_manifest["proof_runtime"] == script.V10C_SLICE_ID
    assert evidence_manifest["fresh_heldout_32000_32049_accessed"] is False


def _write_fake_v11_parent_evidence(script: Any, output_dir: Path) -> None:
    _write_fake_v10_gap_compression_evidence(script, output_dir)
    script.build_v10c_calibration_gap_compression_diagnosis(output_dir=output_dir)


def test_v11_requires_v10c_gap_compression_diagnosis(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    with pytest.raises(ValueError, match="missing_v0_10c_calibration_gap_compression_diagnosis"):
        script.build_v11_low_floor_comparator_slice(output_dir=tmp_path)


def test_v11_builds_low_floor_comparator_views(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_fake_v11_parent_evidence(script, tmp_path)

    manifest = script.build_v11_low_floor_comparator_slice(output_dir=tmp_path)

    gate = manifest["low_floor_comparator_gate"]
    assert manifest["policy_slice"] == "v0_11"
    assert manifest["fresh_calibration_seed_range"] == [33000, 33029]
    assert manifest["fresh_heldout_seed_range"] == [34000, 34049]
    assert manifest["heldout_opened"] is False
    assert manifest["fresh_heldout_34000_34049_accessed"] is False
    assert gate["passed"] is True
    assert gate["baseline_failure_material_ratio_target"] == pytest.approx(0.90)
    assert 0.85 <= gate["baseline_actual_failure_material_ratio"] <= 0.95
    assert gate["candidate_rows_unchanged_from_v10"] is True
    assert gate["peer_fairness_mismatch_keys"] == []


def test_v11_cli_builds_artifact_only_low_floor_comparator(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_fake_v11_parent_evidence(script, tmp_path)

    result = script.main(
        [
            "--scenario-profile",
            "v0_6",
            "--policy-slice",
            "v0_11",
            "--low-floor-comparator-only",
            "--output-dir",
            str(tmp_path),
        ]
    )

    manifest = script.read_json(
        tmp_path / script.V11_CHILD_OUTPUT_DIRNAME / "v0_11_low_floor_comparator_manifest.json"
    )
    evidence_manifest = script.read_json(tmp_path / "evidence_manifest.json")
    assert result == 0
    assert manifest["proof_authority"] is False
    assert evidence_manifest["proof_runtime"] == script.V11_SLICE_ID
    assert evidence_manifest["fresh_heldout_34000_34049_accessed"] is False


def test_v11_fresh_manifest_uses_33000_calibration_and_sealed_34000_heldout(
    tmp_path: Path,
) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_fake_v11_parent_evidence(script, tmp_path)
    low_floor_manifest = script.build_v11_low_floor_comparator_slice(output_dir=tmp_path)

    fresh_manifest = script.build_v11_fresh_manifest(
        output_dir=tmp_path,
        low_floor_manifest=low_floor_manifest,
    )
    calibration_manifest = script._v11_runtime_manifest_for_split(
        fresh_manifest=fresh_manifest,
        split="calibration",
    )
    heldout_manifest = script._v11_runtime_manifest_for_split(
        fresh_manifest=fresh_manifest,
        split="held_out",
    )

    assert fresh_manifest["policy_slice"] == "v0_11"
    assert fresh_manifest["fresh_split_manifest"]["calibration"]["seed_range"] == [33000, 33029]
    assert fresh_manifest["fresh_split_manifest"]["held_out"]["seed_range"] == [34000, 34049]
    assert [row["seed"] for row in calibration_manifest["scenarios"]] == list(range(33000, 33030))
    assert [row["seed"] for row in heldout_manifest["scenarios"]] == list(range(34000, 34050))
    assert calibration_manifest["calibration_opened"] is True
    assert calibration_manifest["heldout_opened"] is False
    assert calibration_manifest["fresh_calibration_33000_33029_accessed"] is True
    assert calibration_manifest["fresh_heldout_34000_34049_accessed"] is False
    assert heldout_manifest["calibration_opened"] is True
    assert heldout_manifest["heldout_opened"] is True
    assert heldout_manifest["proof_authority"] is True
    assert heldout_manifest["fresh_calibration_33000_33029_accessed"] is True
    assert heldout_manifest["fresh_heldout_34000_34049_accessed"] is True


def test_v11_runtime_cli_rejects_clean_before_isaac(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    with pytest.raises(ValueError, match="low-floor-comparator-runtime.*do not pass --clean"):
        script.main(
            [
                "--scenario-profile",
                "v0_6",
                "--policy-slice",
                "v0_11",
                "--low-floor-comparator-runtime",
                "--clean",
                "--output-dir",
                str(tmp_path),
            ]
        )


def test_v11_runtime_cli_rejects_fake_backend_flags(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    with pytest.raises(ValueError, match="requires actual Isaac runtime"):
        script.main(
            [
                "--scenario-profile",
                "v0_6",
                "--policy-slice",
                "v0_11",
                "--low-floor-comparator-runtime",
                "--skip-isaac",
                "--output-dir",
                str(tmp_path),
            ]
        )


def test_v11_runtime_policy_slice_uses_v10_derived_authority_lineage() -> None:
    evaluator = load_script("run_mvp2b_isaac_proof_evaluator")

    assert evaluator.V11_POLICY_SLICE_ID == "v0_11"
    assert evaluator.V11_POLICY_SLICE_ID in evaluator.V08H_DERIVED_POLICY_SLICE_IDS
    assert evaluator.V11_POLICY_SLICE_ID in evaluator.V07E_HYSTERESIS_RUNTIME_POLICY_SLICE_IDS
    assert evaluator.V11_POLICY_SLICE_ID in evaluator.V07B_BASE_SERVO_RUNTIME_POLICY_SLICE_IDS
    assert evaluator.V11_POLICY_SLICE_ID in evaluator.V07C_AUTHORITY_RUNTIME_POLICY_SLICE_IDS
    assert evaluator.V11_POLICY_SLICE_ID in evaluator.V07D_FINAL_AUTHORITY_RUNTIME_POLICY_SLICE_IDS


def _write_fake_v11_failed_calibration_evidence(script: Any, output_dir: Path) -> None:
    _write_fake_v11_parent_evidence(script, output_dir)
    script.build_v11_low_floor_comparator_slice(output_dir=output_dir)
    child_dir = output_dir / script.V11_CHILD_OUTPUT_DIRNAME
    rollout_dir = child_dir / "calibration_external_rollouts"
    rollout_dir.mkdir(parents=True, exist_ok=True)

    paired_outcomes = (
        ["B1_C1"] * 20
        + ["B1_C0"]
        + ["B0_C1"] * 5
        + ["B0_C0"] * 4
    )
    baseline_rollouts = []
    candidate_rollouts = []
    for index, outcome in enumerate(paired_outcomes):
        seed = 33000 + index
        baseline_success = outcome[1] == "1"
        candidate_success = outcome[4] == "1"
        scenario_id = f"calibration_{seed}"
        baseline_rollouts.append(
            {
                "rollout_id": f"baseline_isaac_{index:04d}",
                "scenario_id": scenario_id,
                "success": baseline_success,
                "env_native_rollout_success": baseline_success,
                "env_native_max_consecutive_success_steps": 10 if baseline_success else 0,
                "failure_reason": "" if baseline_success else "ENV_NATIVE_STABILITY_WINDOW_NOT_REACHED",
                "rollout_log_ref": str(
                    child_dir
                    / "isaac_runtime_fresh_calibration_v0_11"
                    / "isaac_runtime_heldout_rollout_traces"
                    / f"baseline_{index:04d}_calibration_{seed}_isaac_trace.json"
                ),
            }
        )
        candidate_rollouts.append(
            {
                "rollout_id": f"candidate_isaac_{index:04d}",
                "scenario_id": scenario_id,
                "success": candidate_success,
                "env_native_rollout_success": candidate_success,
                "env_native_max_consecutive_success_steps": 10 if candidate_success else 0,
                "failure_reason": "" if candidate_success else "ENV_NATIVE_STABILITY_WINDOW_NOT_REACHED",
                "rollout_log_ref": str(
                    child_dir
                    / "isaac_runtime_fresh_calibration_v0_11"
                    / "isaac_runtime_heldout_rollout_traces"
                    / f"candidate_{index:04d}_calibration_{seed}_isaac_trace.json"
                ),
            }
        )
    script.write_json(
        rollout_dir / "baseline_calibration_rollouts_v0_11.json",
        baseline_rollouts,
    )
    script.write_json(
        rollout_dir / "candidate_calibration_rollouts_v0_11.json",
        candidate_rollouts,
    )
    gate = {
        "schema_version": script.V11_CALIBRATION_PRESIGNAL_SCHEMA_VERSION,
        "policy_slice": "v0_11",
        "slice_id": script.V11_SLICE_ID,
        "runtime_backend": "isaac_runtime",
        "proof_runtime": "dedicated_isaac_connector_insertion_evaluator",
        "passed": False,
        "failure_reason": "baseline_calibration_success_floor_above_v0_11_maximum",
        "baseline_calibration_rollout_count": 30,
        "candidate_calibration_rollout_count": 30,
        "baseline_calibration_success_count": 21,
        "candidate_calibration_success_count": 25,
        "baseline_calibration_success_rate": 0.7,
        "candidate_calibration_success_rate": 0.833333333333,
        "candidate_baseline_success_gap": 0.133333333333,
        "baseline_calibration_success_floor_maximum": 0.65,
        "candidate_calibration_success_minimum": 0.80,
        "candidate_success_gap_minimum": 0.20,
        "attribution_preservation_gate_passed": True,
        "calibration_opened": True,
        "heldout_opened": False,
        "fresh_calibration_33000_33029_accessed": True,
        "fresh_heldout_32000_32049_accessed": False,
        "fresh_heldout_34000_34049_accessed": False,
        "mvp2_closed": False,
        "policy_uplift_proven": False,
    }
    script.write_json(child_dir / "calibration_presignal_gate_v0_11.json", gate)


def test_v11a_requires_v11_actual_calibration_evidence(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    with pytest.raises(ValueError, match="missing_v0_11_calibration_presignal_gate"):
        script.build_v11a_low_floor_baseline_persistence_diagnosis(output_dir=tmp_path)


def test_v11a_classifies_low_floor_baseline_persistence(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_fake_v11_failed_calibration_evidence(script, tmp_path)

    report = script.build_v11a_low_floor_baseline_persistence_diagnosis(output_dir=tmp_path)

    assert report["policy_slice"] == "v0_11a"
    assert report["source_policy_slice"] == "v0_11"
    assert report["baseline_calibration_success_count"] == 21
    assert report["candidate_calibration_success_count"] == 25
    assert report["candidate_baseline_success_gap"] == pytest.approx(0.133333333333)
    assert report["paired_outcome_counts"] == {"B1_C1": 20, "B1_C0": 1, "B0_C1": 5, "B0_C0": 4}
    assert report["candidate_recovered_baseline_failure_seeds"] == [
        33021,
        33022,
        33023,
        33024,
        33025,
    ]
    assert report["candidate_degraded_baseline_success_seeds"] == [33020]
    assert report["primary_root_cause_class"] == "LOW_FLOOR_BASELINE_RUNTIME_FLOOR_PERSISTENCE"
    assert report["recommended_downstream_slice"] == (
        "v0_12_baseline_floor_suppression_comparator"
    )
    assert report["fresh_heldout_34000_34049_accessed"] is False
    assert report["mvp2_closed"] is False
    assert report["policy_uplift_proven"] is False


def test_v11a_cli_runs_artifact_only_low_floor_baseline_diagnosis(
    tmp_path: Path,
) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_fake_v11_failed_calibration_evidence(script, tmp_path)

    result = script.main(
        [
            "--scenario-profile",
            "v0_6",
            "--policy-slice",
            "v0_11a",
            "--low-floor-baseline-diagnosis-only",
            "--output-dir",
            str(tmp_path),
        ]
    )

    report = script.read_json(
        tmp_path
        / script.V11A_CHILD_OUTPUT_DIRNAME
        / "v0_11a_low_floor_baseline_persistence_diagnosis.json"
    )
    evidence_manifest = script.read_json(tmp_path / "evidence_manifest.json")
    assert result == 0
    assert report["primary_root_cause_class"] == "LOW_FLOOR_BASELINE_RUNTIME_FLOOR_PERSISTENCE"
    assert evidence_manifest["proof_runtime"] == script.V11A_SLICE_ID
    assert evidence_manifest["fresh_heldout_34000_34049_accessed"] is False


def _write_fake_v12_parent_evidence(script: Any, output_dir: Path) -> None:
    _write_fake_v11_failed_calibration_evidence(script, output_dir)
    script.build_v11a_low_floor_baseline_persistence_diagnosis(output_dir=output_dir)


def test_v12_requires_v11a_low_floor_baseline_diagnosis(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    with pytest.raises(ValueError, match="missing_v0_11a_low_floor_baseline_persistence_diagnosis"):
        script.build_v12_baseline_floor_suppression_slice(output_dir=tmp_path)


def test_v12_builds_terminal_failure_window_comparator(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_fake_v12_parent_evidence(script, tmp_path)

    manifest = script.build_v12_baseline_floor_suppression_slice(output_dir=tmp_path)

    gate = manifest["baseline_floor_suppression_gate"]
    assert manifest["policy_slice"] == "v0_12"
    assert manifest["fresh_calibration_seed_range"] == [35000, 35029]
    assert manifest["fresh_heldout_seed_range"] == [36000, 36049]
    assert manifest["heldout_opened"] is False
    assert manifest["fresh_heldout_36000_36049_accessed"] is False
    assert gate["passed"] is True
    assert gate["baseline_failure_material_ratio_target"] == pytest.approx(0.90)
    assert 0.85 <= gate["baseline_actual_failure_material_ratio"] <= 0.95
    assert gate["candidate_rows_unchanged_from_v11"] is True
    assert gate["terminal_failure_window_report"]["failure_material_selection"] == (
        "terminal_failure_window_rows"
    )
    assert gate["terminal_failure_window_report"]["terminal_window_rows_per_trace"] == 24
    assert gate["peer_fairness_mismatch_keys"] == []


def test_v12_cli_builds_artifact_only_baseline_floor_suppression(
    tmp_path: Path,
) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_fake_v12_parent_evidence(script, tmp_path)

    result = script.main(
        [
            "--scenario-profile",
            "v0_6",
            "--policy-slice",
            "v0_12",
            "--baseline-floor-suppression-only",
            "--output-dir",
            str(tmp_path),
        ]
    )

    manifest = script.read_json(
        tmp_path
        / script.V12_CHILD_OUTPUT_DIRNAME
        / "v0_12_baseline_floor_suppression_manifest.json"
    )
    evidence_manifest = script.read_json(tmp_path / "evidence_manifest.json")
    assert result == 0
    assert manifest["proof_authority"] is False
    assert evidence_manifest["proof_runtime"] == script.V12_SLICE_ID
    assert evidence_manifest["fresh_heldout_36000_36049_accessed"] is False


def test_v12_fresh_manifest_uses_35000_calibration_and_sealed_36000_heldout(
    tmp_path: Path,
) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_fake_v12_parent_evidence(script, tmp_path)
    suppression_manifest = script.build_v12_baseline_floor_suppression_slice(output_dir=tmp_path)

    fresh_manifest = script.build_v12_fresh_manifest(
        output_dir=tmp_path,
        suppression_manifest=suppression_manifest,
    )
    calibration_manifest = script._v12_runtime_manifest_for_split(
        fresh_manifest=fresh_manifest,
        split="calibration",
    )
    heldout_manifest = script._v12_runtime_manifest_for_split(
        fresh_manifest=fresh_manifest,
        split="held_out",
    )

    assert fresh_manifest["policy_slice"] == "v0_12"
    assert fresh_manifest["fresh_split_manifest"]["calibration"]["seed_range"] == [35000, 35029]
    assert fresh_manifest["fresh_split_manifest"]["held_out"]["seed_range"] == [36000, 36049]
    assert fresh_manifest["fresh_heldout_34000_34049_accessed"] is False
    assert [row["seed"] for row in calibration_manifest["scenarios"]] == list(range(35000, 35030))
    assert [row["seed"] for row in heldout_manifest["scenarios"]] == list(range(36000, 36050))
    assert calibration_manifest["calibration_opened"] is True
    assert calibration_manifest["heldout_opened"] is False
    assert calibration_manifest["fresh_calibration_35000_35029_accessed"] is True
    assert calibration_manifest["fresh_heldout_36000_36049_accessed"] is False
    assert heldout_manifest["calibration_opened"] is True
    assert heldout_manifest["heldout_opened"] is True
    assert heldout_manifest["proof_authority"] is True
    assert heldout_manifest["fresh_calibration_35000_35029_accessed"] is True
    assert heldout_manifest["fresh_heldout_36000_36049_accessed"] is True


def test_v12_runtime_cli_rejects_clean_before_isaac(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    with pytest.raises(ValueError, match="baseline-floor-suppression-runtime.*do not pass --clean"):
        script.main(
            [
                "--scenario-profile",
                "v0_6",
                "--policy-slice",
                "v0_12",
                "--baseline-floor-suppression-runtime",
                "--clean",
                "--output-dir",
                str(tmp_path),
            ]
        )


def test_v12_runtime_cli_rejects_fake_backend_flags(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    with pytest.raises(ValueError, match="requires actual Isaac runtime"):
        script.main(
            [
                "--scenario-profile",
                "v0_6",
                "--policy-slice",
                "v0_12",
                "--baseline-floor-suppression-runtime",
                "--skip-isaac",
                "--output-dir",
                str(tmp_path),
            ]
        )


def _write_fake_v12_failed_calibration_evidence(script: Any, output_dir: Path) -> None:
    _write_fake_v12_parent_evidence(script, output_dir)
    script.build_v12_baseline_floor_suppression_slice(output_dir=output_dir)
    child_dir = output_dir / script.V12_CHILD_OUTPUT_DIRNAME
    trace_dir = (
        child_dir
        / "isaac_runtime_fresh_calibration_v0_12"
        / "isaac_runtime_heldout_rollout_traces"
    )
    trace_dir.mkdir(parents=True, exist_ok=True)
    baseline_rollouts = []
    candidate_rollouts = []
    for index, seed in enumerate(range(35000, 35030)):
        scenario_id = f"calibration_{seed}"
        success = index not in {10, 17, 23, 24, 25}
        for role in ("baseline", "candidate"):
            trace_path = trace_dir / f"{role}_{index:04d}_calibration_{seed}_isaac_trace.json"
            trace_rows = []
            for step in range(4):
                trace_rows.append(
                    {
                        "step": step,
                        "phase": "APPROACH",
                        "lateral_error_m": 0.009,
                        "insertion_depth_m": 0.0,
                        "relative_x_m": 0.001,
                        "relative_y_m": -0.002,
                        "orientation_error_deg": 0.1,
                        "env_native_success": False,
                        "env_native_success_mask": False,
                        "normalized_action": [0.01, -0.03, 0.0, 0.0, 0.0, 0.0],
                        "controller_action_diagnostics": {
                            "raw_action_before_authority": (
                                [0.02, -0.04, 0.05, 0.0, 0.0, 0.0, 1.0]
                                if role == "baseline"
                                else [0.05, -0.01, -0.02, 0.0, 0.0, 0.0, 1.0]
                            ),
                            "raw_action_after_authority": (
                                [0.02, -0.04, -0.001, 0.0, 0.0, 0.0, 1.0]
                                if role == "baseline"
                                else [0.05, -0.01, -0.001, 0.0, 0.0, 0.0, 1.0]
                            ),
                            "pre_controller_action_vector": (
                                [0.05, -0.05, -0.032, 0.0, 0.0, 0.0, 1.0]
                                if role == "baseline"
                                else [-0.05, 0.05, -0.032, 0.0, 0.0, 0.0, 1.0]
                            ),
                            "post_adapter_action_vector": [
                                0.01,
                                -0.03,
                                0.0,
                                0.0,
                                0.0,
                                0.0,
                                1.0,
                            ],
                            "xy_authority_applied": True,
                            "final_post_adapter_z_motion_allowed": False,
                            "policy_slice": "v0_12",
                        },
                    }
                )
            script.write_json(
                trace_path,
                {
                    "runtime_backend": "isaac_runtime",
                    "policy_role": role,
                    "scenario": {"scenario_id": scenario_id, "seed": seed},
                    "summary": {
                        "success": success,
                        "env_native_rollout_success": success,
                        "env_native_max_consecutive_success_steps": 10 if success else 0,
                        "failure_reason": ""
                        if success
                        else "ENV_NATIVE_STABILITY_WINDOW_NOT_REACHED",
                    },
                    "trace": trace_rows,
                },
            )
            rollout = {
                "rollout_id": f"{role}_isaac_{index:04d}",
                "scenario_id": scenario_id,
                "seed": seed,
                "success": success,
                "env_native_rollout_success": success,
                "env_native_max_consecutive_success_steps": 10 if success else 0,
                "failure_reason": ""
                if success
                else "ENV_NATIVE_STABILITY_WINDOW_NOT_REACHED",
                "rollout_log_ref": str(trace_path),
            }
            if role == "baseline":
                baseline_rollouts.append(rollout)
            else:
                candidate_rollouts.append(rollout)
    rollout_dir = child_dir / "calibration_external_rollouts"
    rollout_dir.mkdir(parents=True, exist_ok=True)
    script.write_json(
        rollout_dir / "baseline_calibration_rollouts_v0_12.json",
        baseline_rollouts,
    )
    script.write_json(
        rollout_dir / "candidate_calibration_rollouts_v0_12.json",
        candidate_rollouts,
    )
    gate = {
        "schema_version": script.V12_CALIBRATION_PRESIGNAL_SCHEMA_VERSION,
        "policy_slice": "v0_12",
        "slice_id": script.V12_SLICE_ID,
        "runtime_backend": "isaac_runtime",
        "proof_runtime": "dedicated_isaac_connector_insertion_evaluator",
        "passed": False,
        "failure_reason": "baseline_calibration_success_floor_above_v0_12_maximum",
        "baseline_calibration_rollout_count": 30,
        "candidate_calibration_rollout_count": 30,
        "baseline_calibration_success_count": 25,
        "candidate_calibration_success_count": 25,
        "baseline_calibration_success_rate": 0.833333333333,
        "candidate_calibration_success_rate": 0.833333333333,
        "candidate_baseline_success_gap": 0.0,
        "baseline_calibration_success_floor_maximum": 0.65,
        "candidate_calibration_success_minimum": 0.80,
        "candidate_success_gap_minimum": 0.20,
        "attribution_preservation_gate_passed": True,
        "calibration_opened": True,
        "heldout_opened": False,
        "fresh_calibration_35000_35029_accessed": True,
        "fresh_heldout_36000_36049_accessed": False,
        "mvp2_closed": False,
        "policy_uplift_proven": False,
    }
    script.write_json(child_dir / "calibration_presignal_gate_v0_12.json", gate)


def test_v12a_requires_v12_actual_calibration_evidence(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    with pytest.raises(ValueError, match="missing_v0_12_calibration_presignal_gate"):
        script.build_v12a_runtime_authority_dominance_diagnosis(output_dir=tmp_path)


def test_v12a_classifies_runtime_authority_dominance(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_fake_v12_failed_calibration_evidence(script, tmp_path)

    report = script.build_v12a_runtime_authority_dominance_diagnosis(output_dir=tmp_path)

    assert report["policy_slice"] == "v0_12a"
    assert report["source_policy_slice"] == "v0_12"
    assert report["primary_root_cause_class"] == "RUNTIME_AUTHORITY_DOMINATES_LEARNED_RESIDUAL_OUTCOME"
    assert report["paired_outcome_counts"] == {"B1_C1": 25, "B1_C0": 0, "B0_C1": 0, "B0_C0": 5}
    assert report["action_compression_report"]["post_adapter_delta_smaller_than_raw_delta"] is True
    assert report["recommended_downstream_slice"] == "v0_13_policy_influence_authority_ceiling_slice"
    assert report["fresh_heldout_36000_36049_accessed"] is False
    assert report["mvp2_closed"] is False
    assert report["policy_uplift_proven"] is False


def _write_fake_v13_parent_evidence(script: Any, output_dir: Path) -> None:
    _write_fake_v12_failed_calibration_evidence(script, output_dir)
    script.build_v12a_runtime_authority_dominance_diagnosis(output_dir=output_dir)


def test_v13_requires_v12a_runtime_authority_dominance_diagnosis(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    with pytest.raises(ValueError, match="missing_v0_12a_runtime_authority_dominance_diagnosis"):
        script.build_v13_policy_influence_authority_ceiling_slice(output_dir=tmp_path)


def test_v13_builds_policy_influence_authority_ceiling_slice(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_fake_v13_parent_evidence(script, tmp_path)

    manifest = script.build_v13_policy_influence_authority_ceiling_slice(output_dir=tmp_path)

    gate = manifest["policy_influence_authority_ceiling_gate"]
    config = manifest["policy_influence_authority_ceiling_config"]
    candidate = manifest["policy_artifacts"]["candidate"]
    baseline = manifest["policy_artifacts"]["baseline"]
    assert manifest["policy_slice"] == "v0_13"
    assert manifest["source_policy_slice"] == "v0_12a"
    assert manifest["fresh_calibration_seed_range"] == [37000, 37029]
    assert manifest["fresh_heldout_seed_range"] == [38000, 38049]
    assert manifest["heldout_opened"] is False
    assert manifest["fresh_heldout_38000_38049_accessed"] is False
    assert config["state_feedback_gain_ceiling"] == pytest.approx(0.5)
    assert config["z_progress_injection_enabled"] is False
    assert config["final_xy_state_feedback_replacement_enabled"] is False
    assert gate["passed"] is True
    assert gate["post_adapter_delta_retention_ratio"] >= 0.35
    assert gate["post_adapter_identical_fraction"] <= 0.50
    assert candidate["policy_slice"] == baseline["policy_slice"] == "v0_13"
    assert candidate["policy_influence_authority_ceiling_config_sha256"] == baseline[
        "policy_influence_authority_ceiling_config_sha256"
    ]
    assert candidate["selected_action_adapter_config"]["xy_state_feedback_gain"] == pytest.approx(0.5)
    assert baseline["selected_action_adapter_config"]["xy_state_feedback_gain"] == pytest.approx(0.5)
    assert candidate.get("early_centered_z_open_safe_entry_config") is None
    assert baseline.get("early_centered_z_open_safe_entry_config") is None


def test_v13_fresh_manifest_uses_37000_calibration_and_sealed_38000_heldout(
    tmp_path: Path,
) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_fake_v13_parent_evidence(script, tmp_path)
    ceiling_manifest = script.build_v13_policy_influence_authority_ceiling_slice(output_dir=tmp_path)

    fresh_manifest = script.build_v13_fresh_manifest(
        output_dir=tmp_path,
        ceiling_manifest=ceiling_manifest,
    )
    calibration_manifest = script._v13_runtime_manifest_for_split(
        fresh_manifest=fresh_manifest,
        split="calibration",
    )
    heldout_manifest = script._v13_runtime_manifest_for_split(
        fresh_manifest=fresh_manifest,
        split="held_out",
    )

    assert fresh_manifest["policy_slice"] == "v0_13"
    assert fresh_manifest["fresh_split_manifest"]["calibration"]["seed_range"] == [37000, 37029]
    assert fresh_manifest["fresh_split_manifest"]["held_out"]["seed_range"] == [38000, 38049]
    assert fresh_manifest["fresh_heldout_38000_38049_accessed"] is False
    assert [row["seed"] for row in calibration_manifest["scenarios"]] == list(range(37000, 37030))
    assert [row["seed"] for row in heldout_manifest["scenarios"]] == list(range(38000, 38050))
    assert calibration_manifest["calibration_opened"] is True
    assert calibration_manifest["heldout_opened"] is False
    assert calibration_manifest["fresh_calibration_37000_37029_accessed"] is True
    assert calibration_manifest["fresh_heldout_38000_38049_accessed"] is False
    assert heldout_manifest["calibration_opened"] is True
    assert heldout_manifest["heldout_opened"] is True
    assert heldout_manifest["proof_authority"] is True
    assert heldout_manifest["fresh_calibration_37000_37029_accessed"] is True
    assert heldout_manifest["fresh_heldout_38000_38049_accessed"] is True


def test_v13_cli_builds_artifact_only_policy_influence_ceiling(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_fake_v13_parent_evidence(script, tmp_path)

    result = script.main(
        [
            "--scenario-profile",
            "v0_6",
            "--policy-slice",
            "v0_13",
            "--policy-influence-authority-ceiling-only",
            "--output-dir",
            str(tmp_path),
        ]
    )

    manifest = script.read_json(
        tmp_path
        / script.V13_CHILD_OUTPUT_DIRNAME
        / "v0_13_policy_influence_authority_ceiling_manifest.json"
    )
    evidence_manifest = script.read_json(tmp_path / "evidence_manifest.json")
    assert result == 0
    assert manifest["proof_authority"] is False
    assert evidence_manifest["proof_runtime"] == script.V13_SLICE_ID
    assert evidence_manifest["fresh_heldout_38000_38049_accessed"] is False


def test_v13_runtime_cli_rejects_clean_before_isaac(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    with pytest.raises(ValueError, match="policy-influence-authority-ceiling-runtime.*do not pass --clean"):
        script.main(
            [
                "--scenario-profile",
                "v0_6",
                "--policy-slice",
                "v0_13",
                "--policy-influence-authority-ceiling-runtime",
                "--clean",
                "--output-dir",
                str(tmp_path),
            ]
        )


def test_v13_runtime_cli_rejects_fake_backend_flags(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    with pytest.raises(ValueError, match="requires actual Isaac runtime"):
        script.main(
            [
                "--scenario-profile",
                "v0_6",
                "--policy-slice",
                "v0_13",
                "--policy-influence-authority-ceiling-runtime",
                "--skip-isaac",
                "--output-dir",
                str(tmp_path),
            ]
        )


def test_v14_rejects_failure_rows_from_success_summary(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    success_trace = {
        "summary": {
            "success": True,
            "env_native_rollout_success": True,
            "failure_reason": "",
        },
        "trace": [],
    }
    trace_path = tmp_path / "misleading_failure_source.json"
    trace_path.write_text(json.dumps(success_trace), encoding="utf-8")
    row = {
        "accepted": False,
        "source_trace_role": "train_generation_failed_attempt",
        "runtime_trace_path": str(trace_path),
        "lateral_error_m": 0.0009,
        "behavior_state_phase": "ALIGN",
    }

    report = script.derive_v14_source_provenance_report([row], candidate_rows=[])

    assert report["passed"] is False
    assert "failure_row_source_trace_summary_success_true" in report["failure_reasons"]


def test_v14_row_balance_caps_terminal_failure_rows() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    success_rows = [{"accepted": True, "row_id": f"s{i}"} for i in range(100)]
    failure_rows = [
        {
            "accepted": False,
            "source_trace_role": "train_generation_failed_attempt",
            "source_trace_summary_success": False,
            "source_trace_summary_env_native_rollout_success": False,
            "source_trace_summary_failure_reason": "ENV_NATIVE_STABILITY_WINDOW_NOT_REACHED",
            "runtime_trace_path": f"trace_{trace_id}.json",
            "step": step,
            "behavior_state_phase": "ALIGN",
            "lateral_error_m": 0.0008,
        }
        for trace_id in range(12)
        for step in range(500)
    ]

    rows, report = script.build_v14_row_balanced_baseline_rows(
        success_rows=success_rows,
        failure_rows=failure_rows,
    )

    selected_failure_rows = [
        row for row in rows if row.get("uncurated_row_balance_is_failure_material") is True
    ]
    assert len(selected_failure_rows) == 100
    assert report["baseline_actual_failure_material_ratio"] == 0.5
    assert max(report["selected_failure_rows_per_trace"].values()) <= 300
    assert report["duplicate_failure_rows_allowed"] is False


def test_v14_artifact_only_builds_fresh_manifest_and_keeps_heldout_sealed(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_fake_v13_parent_evidence(script, tmp_path)

    manifest = script.build_v14_comparator_provenance_row_balance_slice(output_dir=tmp_path)

    gate = manifest["comparator_provenance_row_balance_gate"]
    assert gate["passed"] is True
    assert manifest["fresh_calibration_seed_range"] == [39000, 39029]
    assert manifest["fresh_heldout_seed_range"] == [40000, 40049]
    assert manifest["fresh_heldout_40000_40049_accessed"] is False
    assert manifest["heldout_opened"] is False
    assert manifest["mvp2_closed"] is False


def test_v14_cli_rejects_clean_before_isaac(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    with pytest.raises(ValueError, match="comparator-provenance-row-balance-runtime.*do not pass --clean"):
        script.main(
            [
                "--scenario-profile",
                "v0_6",
                "--policy-slice",
                "v0_14",
                "--comparator-provenance-row-balance-runtime",
                "--clean",
                "--output-dir",
                str(tmp_path),
            ]
        )


def test_v14_runtime_cli_rejects_fake_backend_flags(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    with pytest.raises(ValueError, match="requires actual Isaac runtime"):
        script.main(
            [
                "--scenario-profile",
                "v0_6",
                "--policy-slice",
                "v0_14",
                "--comparator-provenance-row-balance-runtime",
                "--skip-isaac",
                "--output-dir",
                str(tmp_path),
            ]
        )


def test_v14_runtime_manifest_marks_40000_40049_spent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    def fake_runtime(**_: Any) -> dict[str, Any]:
        return {
            "runtime_backend": "isaac_runtime",
            "heldout_opened": True,
            "fresh_heldout_40000_40049_accessed": True,
            "mvp2_closed": True,
            "policy_uplift_proven": True,
        }

    monkeypatch.setattr(script, "run_v14_comparator_provenance_row_balance_runtime", fake_runtime)

    exit_code = script.main(
        [
            "--scenario-profile",
            "v0_6",
            "--policy-slice",
            "v0_14",
            "--comparator-provenance-row-balance-runtime",
            "--output-dir",
            str(tmp_path),
        ]
    )

    manifest = script.read_json(tmp_path / "evidence_manifest.json")
    assert exit_code == 0
    assert manifest["fresh_heldout_40000_40049_accessed"] is True
    assert manifest["same_heldout_reuse_allowed_for_closure"] is False
    assert manifest["spent_heldout_ranges"] == [
        {
            "range": "40000-40049",
            "status": "spent_for_mvp2_v0_14_closure",
            "future_tuning_allowed": False,
            "future_closure_reuse_allowed": False,
            "reason": "Used by the v0_14 actual Isaac held-out closure gate.",
        }
    ]


def test_v14_runtime_cli_rejects_existing_spent_heldout_before_isaac(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    child_dir = tmp_path / script.V14_CHILD_OUTPUT_DIRNAME
    script.write_json(
        child_dir / "heldout_closure_gate_v0_14.json",
        {
            "schema_version": script.V14_HELDOUT_CLOSURE_SCHEMA_VERSION,
            "policy_slice": "v0_14",
            "fresh_heldout_40000_40049_accessed": True,
            "same_heldout_reuse_allowed_for_closure": False,
            "spent_heldout_ranges": [script._v14_spent_heldout_range_record()],
        },
    )

    with pytest.raises(
        ValueError,
        match="v0_14_heldout_40000_40049_already_spent_audit_only",
    ):
        script.main(
            [
                "--scenario-profile",
                "v0_6",
                "--policy-slice",
                "v0_14",
                "--comparator-provenance-row-balance-runtime",
                "--output-dir",
                str(tmp_path),
            ]
        )

    assert not (child_dir / "v0_14_fresh_manifest.json").exists()


def test_v12_runtime_policy_slice_uses_v11_derived_authority_lineage() -> None:
    evaluator = load_script("run_mvp2b_isaac_proof_evaluator")

    assert evaluator.V12_POLICY_SLICE_ID == "v0_12"
    assert evaluator.V12_POLICY_SLICE_ID in evaluator.V08H_DERIVED_POLICY_SLICE_IDS
    assert evaluator.V12_POLICY_SLICE_ID in evaluator.V07E_HYSTERESIS_RUNTIME_POLICY_SLICE_IDS
    assert evaluator.V12_POLICY_SLICE_ID in evaluator.V07B_BASE_SERVO_RUNTIME_POLICY_SLICE_IDS
    assert evaluator.V12_POLICY_SLICE_ID in evaluator.V07C_AUTHORITY_RUNTIME_POLICY_SLICE_IDS
    assert evaluator.V12_POLICY_SLICE_ID in evaluator.V07D_FINAL_AUTHORITY_RUNTIME_POLICY_SLICE_IDS


def test_v07a2_trace_row_phase_uses_env_native_mask() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    assert (
        script.derive_v07a2_behavior_state_phase(
            {"env_native_success_mask": True, "lateral_error_m": 0.2, "insertion_depth_m": 0.0}
        )
        == "HOLD"
    )
    assert (
        script.derive_v07a2_behavior_state_phase(
            {"env_native_success_mask": False, "lateral_error_m": 0.001, "insertion_depth_m": 0.024}
        )
        == "DESCEND"
    )
    assert (
        script.derive_v07a2_behavior_state_phase(
            {"env_native_success_mask": False, "lateral_error_m": 0.0011, "insertion_depth_m": 0.024}
        )
        == "ALIGN"
    )


def test_v07a2_trace_row_validation_fails_closed_for_bad_mask_or_missing_action() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    with pytest.raises(ValueError, match="env_native_mask_conflict"):
        script.trace_row_to_v07a2_train_row(
            {
                "step": 0,
                "env_native_success": True,
                "env_native_success_mask": False,
                "lateral_error_m": 0.0,
                "insertion_depth_m": 0.0,
                "relative_x_m": 0.0,
                "relative_y_m": 0.0,
                "orientation_error_deg": 0.0,
                "normalized_action": [0.0] * 6,
            },
            source_trace_path=Path("/tmp/train_success_19003_isaac_trace.json"),
            source_trace_sha256="sha",
            trajectory_id="train_success_19003",
            source_trace_role="candidate_success",
            accepted=True,
        )

    with pytest.raises(ValueError, match="normalized_action_missing"):
        script.trace_row_to_v07a2_train_row(
            {
                "step": 0,
                "env_native_success_mask": False,
                "lateral_error_m": 0.0,
                "insertion_depth_m": 0.0,
                "relative_x_m": 0.0,
                "relative_y_m": 0.0,
                "orientation_error_deg": 0.0,
            },
            source_trace_path=Path("/tmp/train_success_19003_isaac_trace.json"),
            source_trace_sha256="sha",
            trajectory_id="train_success_19003",
            source_trace_role="candidate_success",
            accepted=True,
        )


def test_v07a2_trace_action_normalization_extends_six_dim_action() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    row = script.trace_row_to_v07a2_train_row(
        {
            "step": 0,
            "env_native_success_mask": False,
            "lateral_error_m": 0.0,
            "insertion_depth_m": 0.0,
            "relative_x_m": 0.0,
            "relative_y_m": 0.0,
            "orientation_error_deg": 0.0,
            "normalized_action": [0.1, -0.1, -0.16, 0.0, 0.0, 0.0],
        },
        source_trace_path=Path("/tmp/train_success_19003_isaac_trace.json"),
        source_trace_sha256="sha",
        trajectory_id="train_success_19003",
        source_trace_role="candidate_success",
        accepted=True,
    )

    assert len(row["normalized_action"]) == len(script.ACTION_SCHEMA)
    assert row["normalized_action"][6] == 1.0


def test_v07a2_candidate_and_baseline_trace_views_use_parent_gate_paths(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    success_path = tmp_path / "isaac_runtime_heldout_rollout_traces" / "train_generation_probe_0000_train_success_19003_isaac_trace.json"
    failure_path = tmp_path / "isaac_runtime_train_generation_probe" / "train_generation_probe_0001_train_success_19004_isaac_trace.json"
    success_path.parent.mkdir(parents=True)
    failure_path.parent.mkdir(parents=True)
    write_v07a2_runtime_trace(script, success_path, scenario_id="train_success_19003", seed=19003, success=True)
    write_v07a2_runtime_trace(script, failure_path, scenario_id="train_success_19004", seed=19004, success=False)
    gate = {
        "passed": True,
        "runtime_backend": "isaac_runtime",
        "actual_train_generation_evidence": True,
        "generated_rollout_count": 2,
        "generated_success_count": 1,
        "generated_trace_paths": [str(success_path), str(failure_path)],
        "generated_success_trace_paths": [str(success_path)],
    }

    candidate_rows, candidate_report = script.prepare_v07a2_candidate_rows(parent_gate=gate)
    baseline_rows, baseline_report = script.prepare_v07a2_baseline_rows(parent_gate=gate)

    assert candidate_report["source_trace_paths"] == [str(success_path)]
    assert baseline_report["source_trace_paths"] == [str(success_path), str(failure_path)]
    assert baseline_report["baseline_noise_mix_ratio"] == 0.5
    assert candidate_report["legacy_heldout_path_label_detected"] is True
    assert candidate_report["legacy_heldout_path_label_interpretation"] == "directory_name_only_not_protected_seed_split"
    assert sum(1 for row in candidate_rows if row["behavior_state_phase"] == "HOLD") > 0
    assert {row["trajectory_id"] for row in baseline_rows} == {"train_success_19003", "train_success_19004"}


def test_v07a2_rejects_protected_heldout_seed_range(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    trace_path = tmp_path / "train_generation_probe_0000_train_success_21000_isaac_trace.json"
    write_v07a2_runtime_trace(script, trace_path, scenario_id="train_success_21000", seed=21000, success=True)
    gate = {
        "passed": True,
        "runtime_backend": "isaac_runtime",
        "actual_train_generation_evidence": True,
        "generated_rollout_count": 1,
        "generated_success_count": 1,
        "generated_trace_paths": [str(trace_path)],
        "generated_success_trace_paths": [str(trace_path)],
    }

    with pytest.raises(ValueError, match="protected_heldout_seed_range_access"):
        script.prepare_v07a2_candidate_rows(parent_gate=gate)


def test_v07a1_enriches_candidate_row_from_train_generation_trace_gate(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    trace_dir = tmp_path / "isaac_runtime_train_generation_probe"
    trace_dir.mkdir()
    trace_path = trace_dir / "train_generation_probe_0017_train_success_19000_isaac_trace.json"
    script.write_json(
        trace_path,
        {
            "trace": [
                {
                    "step": 0,
                    "env_native_success": True,
                    "env_native_success_mask": True,
                    "lateral_error_m": 0.0,
                    "insertion_depth_m": 0.024,
                }
            ]
        },
    )
    train_gate = {
        "generated_trace_paths": [str(trace_path)],
        "generated_success_trace_paths": [str(trace_path)],
    }
    row = {
        "trajectory_id": "mvp2c_train_success_19000",
        "step": 0,
        "lateral_error_m": 0.0,
        "insertion_depth_m": 0.024,
    }

    enriched, report = script.enrich_v07a1_candidate_rows_with_runtime_traces(
        rows=[row],
        train_generation_runtime_gate=train_gate,
    )

    assert enriched[0]["runtime_trace_path"] == str(trace_path)
    assert enriched[0]["runtime_trace_sha256"] == script._sha256_file(trace_path)
    hydrated = script.hydrate_v07a1_env_native_mask(enriched[0])
    assert hydrated["env_native_success"] is True
    assert report["candidate_trace_enriched_rows"] == 1


def test_v07a1_missing_trace_for_candidate_row_is_excluded_not_fabricated() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    enriched, report = script.enrich_v07a1_candidate_rows_with_runtime_traces(
        rows=[{"trajectory_id": "mvp2c_train_success_19999", "step": 0}],
        train_generation_runtime_gate={"generated_trace_paths": []},
    )

    assert enriched == []
    assert report["candidate_trace_missing_rows"] == 1
    assert report["candidate_trace_excluded_reason_counts"]["runtime_trace_missing"] == 1


def test_v07a1_ambiguous_duplicate_trace_mapping_fails_closed(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    first = tmp_path / "train_generation_probe_0001_train_success_19000_isaac_trace.json"
    second = tmp_path / "train_generation_probe_9999_train_success_19000_isaac_trace.json"
    for path in (first, second):
        script.write_json(path, {"trace": [{"step": 0, "env_native_success_mask": True}]})

    with pytest.raises(ValueError, match="runtime_trace_mapping_ambiguous"):
        script.enrich_v07a1_candidate_rows_with_runtime_traces(
            rows=[{"trajectory_id": "mvp2c_train_success_19000", "step": 0}],
            train_generation_runtime_gate={"generated_trace_paths": [str(first), str(second)]},
        )


def test_v07a1_hydrates_env_native_mask_from_hash_checked_runtime_trace(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    trace_path = tmp_path / "trace.json"
    trace_payload = {"trace": [{"step": 7, "env_native_success": True, "env_native_success_mask": True}]}
    trace_path.write_text(script.stable_json(trace_payload), encoding="utf-8")
    row = {
        "runtime_trace_path": str(trace_path),
        "runtime_trace_sha256": script._sha256_file(trace_path),
        "step": 7,
        "lateral_error_m": 0.2,
        "insertion_depth_m": 0.0,
    }

    hydrated = script.hydrate_v07a1_env_native_mask(row)

    assert hydrated["env_native_success"] is True
    assert hydrated["env_native_success_mask_source"] == "runtime_trace_path"


def test_v07a1_trace_mask_hydration_rejects_sha_mismatch(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    trace_path = tmp_path / "trace.json"
    trace_path.write_text(script.stable_json({"trace": [{"step": 1, "env_native_success": False}]}), encoding="utf-8")

    with pytest.raises(ValueError, match="runtime_trace_sha256_mismatch"):
        script.hydrate_v07a1_env_native_mask(
            {
                "runtime_trace_path": str(trace_path),
                "runtime_trace_sha256": "bad",
                "step": 1,
                "lateral_error_m": 0.0,
                "insertion_depth_m": 0.0,
            }
        )


def test_v07a1_direct_mask_conflict_fails_closed() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    with pytest.raises(ValueError, match="env_native_mask_conflict"):
        script.hydrate_v07a1_env_native_mask(
            {
                "env_native_success": True,
                "env_native_success_mask": False,
                "lateral_error_m": 0.0,
                "insertion_depth_m": 0.0,
            }
        )


def test_v07a1_trace_mask_hydration_rejects_duplicate_step(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    trace_path = tmp_path / "trace.json"
    trace_path.write_text(
        script.stable_json(
            {
                "trace": [
                    {"step": 3, "env_native_success": False},
                    {"step": 3, "env_native_success": True},
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="runtime_trace_step_match_invalid"):
        script.hydrate_v07a1_env_native_mask(
            {
                "runtime_trace_path": str(trace_path),
                "runtime_trace_sha256": script._sha256_file(trace_path),
                "step": 3,
                "lateral_error_m": 0.0,
                "insertion_depth_m": 0.0,
            }
        )


def test_v07a1_trace_mask_hydration_rejects_malformed_json(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    trace_path = tmp_path / "trace.json"
    trace_path.write_text("{not-json", encoding="utf-8")

    with pytest.raises(ValueError, match="runtime_trace_invalid_json"):
        script.hydrate_v07a1_env_native_mask(
            {
                "runtime_trace_path": str(trace_path),
                "runtime_trace_sha256": script._sha256_file(trace_path),
                "step": 1,
                "lateral_error_m": 0.0,
                "insertion_depth_m": 0.0,
            }
        )


def test_v07a1_trace_mask_hydration_rejects_invalid_row_step(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    trace_path = tmp_path / "trace.json"
    trace_path.write_text(script.stable_json({"trace": []}), encoding="utf-8")

    with pytest.raises(ValueError, match="runtime_trace_row_step_invalid"):
        script.hydrate_v07a1_env_native_mask(
            {
                "runtime_trace_path": str(trace_path),
                "runtime_trace_sha256": script._sha256_file(trace_path),
                "step": "bad",
                "lateral_error_m": 0.0,
                "insertion_depth_m": 0.0,
            }
        )


def test_v07a1_trace_mask_hydration_rejects_invalid_trace_step(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    trace_path = tmp_path / "trace.json"
    trace_path.write_text(script.stable_json({"trace": [{"step": "bad", "env_native_success": True}]}), encoding="utf-8")

    with pytest.raises(ValueError, match="runtime_trace_step_invalid"):
        script.hydrate_v07a1_env_native_mask(
            {
                "runtime_trace_path": str(trace_path),
                "runtime_trace_sha256": script._sha256_file(trace_path),
                "step": 1,
                "lateral_error_m": 0.0,
                "insertion_depth_m": 0.0,
            }
        )


def test_v07a1_synthetic_success_trace_yields_ten_hold_rows() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    rows = [
        {
            "env_native_success": index >= 5,
            "env_native_success_mask": index >= 5,
            "lateral_error_m": 0.0,
            "insertion_depth_m": 0.024,
            "phase": "SEAT" if index >= 5 else "APPROACH",
            "normalized_action": [0.0] * len(script.ACTION_SCHEMA),
            "trajectory_id": "synthetic_success_trace",
            "step": index,
        }
        for index in range(15)
    ]

    relabeled = [script.relabel_v07a1_training_row(row) for row in rows]

    assert sum(1 for row in relabeled if row["behavior_state_phase"] == "HOLD") == 10


def test_v07a1_candidate_and_baseline_report_share_same_rule_hash(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    config = script.build_v07a1_relabel_config(
        output_dir=tmp_path,
        parent_artifact_hashes={"parent_train_generation_runtime_gate_file_sha256": "abc"},
    )

    assert config["relabel_config_sha256"] == config["v0_7a_1_relabel_config_sha256"]
    assert config["behavior_phase_rule_version"] == script.V07A1_BEHAVIOR_PHASE_RULE_VERSION


def test_v07a1_rejects_old_v07a_relabel_config() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    old_config = {
        "schema_version": script.V07A_RELABEL_CONFIG_SCHEMA_VERSION,
        "slice_id": script.V07A_SLICE_ID,
        "seat_depth_threshold_m": 0.03,
        "relabel_config_sha256": "old",
    }

    with pytest.raises(ValueError, match="v0_7a_1_relabel_config_required"):
        script.validate_v07a1_relabel_config_contract(old_config)


def test_v07a1_rejects_stale_relabel_config_hash(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    config = script.build_v07a1_relabel_config(
        output_dir=tmp_path,
        parent_artifact_hashes={"parent_train_generation_runtime_gate_file_sha256": "abc"},
    )
    config["approach_lateral_gate_m"] = 999.0

    with pytest.raises(ValueError, match="v0_7a_1_relabel_config_hash_mismatch"):
        script.validate_v07a1_relabel_config_contract(config)


def test_v07a1_candidate_policy_artifact_declares_env_native_hold_rule(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    config = script.build_v07a1_relabel_config(
        output_dir=tmp_path,
        parent_artifact_hashes={"parent_train_generation_runtime_gate_file_sha256": "abc"},
    )

    artifact = script.build_v07a1_candidate_policy_artifact_payload(
        relabel_config=config,
        policy_artifact_sha256="policy",
        baseline_policy_artifact_available=False,
    )

    assert artifact["policy_slice"] == script.V07A1_POLICY_SLICE_ID
    assert artifact["behavior_phase_rule_version"] == script.V07A1_BEHAVIOR_PHASE_RULE_VERSION
    assert artifact["v0_7a_1_relabel_config_sha256"] == config["v0_7a_1_relabel_config_sha256"]
    assert artifact["relabel_config_sha256"] == config["relabel_config_sha256"]
    assert artifact["future_ab_ready"] is False


def test_v07a1_parent_proof_chain_requires_train_generation_gate_passed(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    parent_root = script._fixture_v07a1_parent_root(tmp_path)
    gate = script.read_json(parent_root / "train_generation_runtime_gate.json")
    gate["passed"] = False
    script.write_json(parent_root / "train_generation_runtime_gate.json", gate)

    with pytest.raises(ValueError, match="parent_train_generation_runtime_gate_not_passed"):
        script.validate_v07a1_parent_proof_chain(parent_root)


def test_v07a1_parent_proof_chain_requires_failed_v07a_evidence(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    parent_root = script._fixture_v07a1_parent_root(tmp_path)
    (parent_root / "v0_7a_behavior_state_phase_relabel" / "offline_train_fit_gate.json").unlink()

    with pytest.raises(ValueError, match="parent_v0_7a_fail_closed_evidence_missing"):
        script.validate_v07a1_parent_proof_chain(parent_root)


def test_v07a1_excludes_unauthenticated_generated_candidate_rows_with_counts() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    rows = [
        {
            "env_native_success_mask": True,
            "lateral_error_m": 0.0,
            "insertion_depth_m": 0.024,
            "normalized_action": [0.0] * len(script.ACTION_SCHEMA),
            "trajectory_id": "runtime_trace_1",
            "step": 0,
        },
        {
            "lateral_error_m": 0.0,
            "insertion_depth_m": 0.0,
            "normalized_action": [0.0] * len(script.ACTION_SCHEMA),
            "trajectory_id": "generated_no_mask",
            "step": 0,
        },
    ]

    prepared, report = script.prepare_v07a1_candidate_train_rows(rows)

    assert len(prepared) == 1
    assert report["candidate_parent_rows_total"] == 2
    assert report["candidate_authenticated_rows_used"] == 1
    assert report["candidate_unauthenticated_rows_excluded"] == 1
    assert report["candidate_invalid_evidence_rows_failed_closed"] == 0


def test_v07a1_missing_baseline_mask_is_report_only_not_fabricated() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    rows, report = script.prepare_v07a1_baseline_report_rows(
        [{"lateral_error_m": 0.0, "insertion_depth_m": 0.0}]
    )

    assert rows == []
    assert report["baseline_report_only"] is True
    assert report["baseline_report_only_status"] == "report_only_env_native_mask_missing"
    assert report["baseline_env_native_mask_missing_count"] == 1


def test_v07a1_offline_gate_allows_candidate_phase_e_when_baseline_policy_missing() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    rows = script._fixture_v07a1_candidate_rows_with_all_phases()
    gate = script.derive_v07a1_offline_train_fit_gate(
        candidate_rows=rows,
        candidate_predictions=script._fixture_v07a1_candidate_predictions_with_low_error(rows),
        candidate_policy_artifact_sha256="candidate-sha",
        relabel_config_sha256="config-sha",
        baseline_rows=[],
        baseline_predictions=[],
        baseline_policy_artifact_sha256=None,
        baseline_report={"baseline_report_only_status": "report_only_env_native_mask_missing"},
    )

    assert gate["passed"] is True
    assert gate["candidate_gate_passed"] is True
    assert gate["phase_e_candidate_expressibility_unblocked"] is True
    assert gate["future_ab_ready"] is False
    assert gate["future_calibration_blocked_reason"] == "missing_v0_7a_1_baseline_policy_artifact"


def test_v07a1_offline_gate_fails_candidate_without_hold_phase() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    rows = script._fixture_v07a1_candidate_rows_without_hold()
    gate = script.derive_v07a1_offline_train_fit_gate(
        candidate_rows=rows,
        candidate_predictions=script._fixture_v07a1_candidate_predictions_with_low_error(rows),
        candidate_policy_artifact_sha256="candidate-sha",
        relabel_config_sha256="config-sha",
    )

    assert gate["passed"] is False
    assert gate["candidate_gate_passed"] is False
    assert gate["phase_e_candidate_expressibility_unblocked"] is False
    assert gate["future_calibration_blocked_reason"] == "candidate_offline_fit_failed"


def test_v07a1_policy_slice_rejects_full_run(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    with pytest.raises(ValueError, match="policy-slice v0_7a_1 is only valid"):
        script.main(
            [
                "--scenario-profile",
                "v0_6",
                "--policy-slice",
                "v0_7a_1",
                "--output-dir",
                str(tmp_path / "rdf-v07a1-full-run-test"),
            ]
        )


def test_v07b_policy_slice_rejects_full_run_and_parses_recovery_mode(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    args = script.parse_args(
        [
            "--scenario-profile",
            "v0_6",
            "--policy-slice",
            "v0_7b",
            "--recovery-overlay-induction-only",
            "--output-dir",
            str(tmp_path),
        ]
    )
    assert args.policy_slice == "v0_7b"
    assert args.recovery_overlay_induction_only is True

    with pytest.raises(ValueError, match="policy-slice v0_7b is only valid"):
        script.main(
            [
                "--scenario-profile",
                "v0_6",
                "--policy-slice",
                "v0_7b",
                "--output-dir",
                str(tmp_path / "rdf-v07b-full-run-test"),
            ]
        )


def test_v07a1_expressibility_gate_blocks_without_offline_fit_gate(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    gate = script.run_v07a1_expressibility_sanity_runtime(
        output_dir=tmp_path,
        manifest={"manifest_sha256": "manifest"},
        device="cpu",
        headless=True,
        isaac_task="Isaac-Factory-PegInsert-Direct-v0",
        max_steps=150,
        action_scale=1.0,
    )

    assert gate["passed"] is False
    assert gate["runtime_backend"] == "isaac_runtime_not_started"
    assert gate["reason"] == "missing_passed_v0_7a_1_offline_train_fit_gate"
    assert (
        tmp_path
        / script.V07A1_CHILD_OUTPUT_DIRNAME
        / "expressibility_sanity_gate_v0_7a_1.json"
    ).exists()


def test_v07a2_expressibility_gate_blocks_without_offline_fit_gate(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    gate = script.run_v07a2_expressibility_sanity_runtime(
        output_dir=tmp_path,
        manifest={"manifest_sha256": "manifest"},
        device="cpu",
        headless=True,
        isaac_task="Isaac-Factory-PegInsert-Direct-v0",
        max_steps=150,
        action_scale=1.0,
    )

    assert gate["passed"] is False
    assert gate["runtime_backend"] == "isaac_runtime_not_started"
    assert gate["reason"] == "missing_passed_v0_7a_2_offline_train_fit_gate"
    assert (
        tmp_path
        / script.V07A2_CHILD_OUTPUT_DIRNAME
        / "expressibility_sanity_gate_v0_7a_2.json"
    ).exists()


def test_v07b_expressibility_gate_blocks_without_offline_residual_fit_gate(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    gate = script.run_v07b_expressibility_sanity_runtime(
        output_dir=tmp_path,
        manifest={"manifest_sha256": "manifest"},
        device="cpu",
        headless=True,
        isaac_task="Isaac-Factory-PegInsert-Direct-v0",
        max_steps=150,
        action_scale=1.0,
    )

    assert gate["passed"] is False
    assert gate["runtime_backend"] == "isaac_runtime_not_started"
    assert gate["reason"] == "missing_passed_v0_7b_offline_residual_fit_gate"
    assert (
        tmp_path
        / script.V07B_CHILD_OUTPUT_DIRNAME
        / "expressibility_sanity_gate_v0_7b.json"
    ).exists()


def test_v07a_parent_hash_validator_detects_mismatch(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    gate_path = tmp_path / "repair_probe_gate.json"
    script.write_json(
        gate_path,
        {
            "green_light_for_40_run_gate": True,
            "hard_stop": False,
            "heldout_21000_21049_accessed": False,
            "repair_probe_gate_sha256": "payload",
        },
    )

    result = script.validate_v07a_parent_artifact_hashes(
        {"repair_probe_gate": gate_path},
        {"parent_repair_probe_gate_file_sha256": "not-the-file-hash"},
    )

    assert result["passed"] is False
    assert "parent_repair_probe_gate_file_sha256" in result["mismatched_hashes"]


def test_v07a_parent_hash_validator_pins_selected_action_adapter(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    adapter_path = tmp_path / "selected_action_adapter.json"
    payload = {
        "calibration_only_selection_passed": True,
        "selector_score_pre_registered": True,
        "same_adapter_used_for_baseline_and_candidate": True,
        "heldout_excluded": False,
        "selected_adapter_frozen_before_heldout": True,
        "selected_adapter_id": "isaac_signed_xy_downward_servo_v0",
        "selected_adapter_config_sha256": "config-hash",
        "selected_adapter_sha256": "adapter-hash",
    }
    script.write_json(adapter_path, payload)

    result = script.validate_v07a_parent_artifact_hashes(
        {"selected_action_adapter": adapter_path},
        {
            "parent_selected_action_adapter_file_sha256": script._sha256_file(adapter_path),
            "parent_selected_action_adapter_payload_sha256": script._sha256_payload(payload),
        },
    )

    assert result["passed"] is False
    assert "selected_action_adapter_heldout_not_excluded" in result["semantic_issues"]
    assert result["observed_hashes"]["parent_selected_action_adapter_payload_sha256"]


def test_v07a_candidate_requires_all_behavior_phases() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    rows = [
        script.relabel_v07a_training_row(
            {
                "phase": "APPROACH",
                "lateral_error_m": 0.002,
                "insertion_depth_m": 0.0,
                "normalized_action": [0.0] * len(script.ACTION_SCHEMA),
            }
        ),
        script.relabel_v07a_training_row(
            {
                "phase": "CONTACT",
                "lateral_error_m": 0.0008,
                "insertion_depth_m": 0.010,
                "normalized_action": [0.0] * len(script.ACTION_SCHEMA),
            }
        ),
    ]

    coverage = script.evaluate_v07a_required_phase_coverage(candidate_rows=rows, baseline_rows=rows)

    assert coverage["passed"] is False
    assert coverage["missing_candidate_phases"] == ["HOLD"]


def test_v07a_train_view_hdf5_uses_behavior_feature_schema(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    rows = [
        script.relabel_v07a_training_row(
            {
                "trajectory_id": "t0",
                "step": 0,
                "phase": "APPROACH",
                "lateral_error_m": 0.002,
                "insertion_depth_m": 0.0,
                "relative_x_m": 0.002,
                "relative_y_m": 0.0,
                "orientation_error_deg": 0.0,
                "normalized_action": [0.0] * len(script.ACTION_SCHEMA),
                "accepted": True,
            }
        )
    ]
    config = script.build_v07a_relabel_config(output_dir=tmp_path, parent_artifact_hashes={})

    view = script.write_v07a_train_view_hdf5(
        path=tmp_path / "candidate_curated_train_v0_7a.hdf5",
        rows=rows,
        view_id="candidate_curated_v0_7a",
        relabel_config=config,
    )

    assert view["schema_version"] == script.V07A_HDF5_SCHEMA_VERSION
    assert view["feature_schema"] == script.FEATURE_SCHEMA_V07A
    assert view["phase_schema"] == list(script.BEHAVIOR_STATE_PHASES)


def test_v07a_policy_artifact_uses_behavior_feature_schema(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    rows = [
        script.relabel_v07a_training_row(
            {
                "trajectory_id": f"t{index}",
                "step": 0,
                "phase": phase,
                "lateral_error_m": lateral,
                "insertion_depth_m": depth,
                "relative_x_m": lateral,
                "relative_y_m": 0.0,
                "orientation_error_deg": 0.0,
                "normalized_action": action,
                "accepted": True,
            }
        )
        for index, (phase, lateral, depth, action) in enumerate(
            [
                ("APPROACH", 0.002, 0.0, [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0]),
                ("CONTACT", 0.0008, 0.01, [0.0, 0.0, -0.16, 0.0, 0.0, 0.0, 1.0]),
                ("SEAT", 0.0004, 0.03, [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0]),
            ]
        )
    ]
    config = script.build_v07a_relabel_config(output_dir=tmp_path, parent_artifact_hashes={})

    artifacts = script.write_v07a_policy_artifacts(
        output_dir=tmp_path,
        baseline_rows=rows,
        candidate_rows=rows,
        selected_adapter_id="isaac_delta_pose_direct_v0",
        selected_adapter_config={"adapter_mode": "global_action_scale"},
        relabel_config=config,
    )

    assert artifacts["candidate"]["feature_schema"] == script.FEATURE_SCHEMA_V07A
    assert artifacts["candidate"]["phase_schema"] == list(script.BEHAVIOR_STATE_PHASES)
    assert artifacts["candidate"]["behavior_state_phase_input"] is True


def test_v07a_offline_train_fit_gate_detects_align_z_collapse() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    rows = [
        script.relabel_v07a_training_row(
            {
                "trajectory_id": f"t{index}",
                "step": 0,
                "phase": phase,
                "lateral_error_m": lateral,
                "insertion_depth_m": depth,
                "relative_x_m": lateral,
                "relative_y_m": 0.0,
                "orientation_error_deg": 0.0,
                "normalized_action": action,
                "accepted": True,
            }
        )
        for index, (phase, lateral, depth, action) in enumerate(
            [
                ("APPROACH", 0.002, 0.0, [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0]),
                ("CONTACT", 0.0008, 0.01, [0.0, 0.0, -0.16, 0.0, 0.0, 0.0, 1.0]),
                ("SEAT", 0.0004, 0.03, [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0]),
            ]
        )
    ]
    collapsed_predictions = [[0.0, 0.0, -0.16, 0.0, 0.0, 0.0, 1.0] for _ in rows]

    gate = script.derive_v07a_offline_train_fit_gate(
        candidate_rows=rows,
        candidate_predictions=collapsed_predictions,
        baseline_rows=rows,
        baseline_predictions=collapsed_predictions,
        relabel_config_sha256="config",
        baseline_policy_artifact_sha256="baseline",
        candidate_policy_artifact_sha256="candidate",
    )

    assert gate["passed"] is False
    assert gate["failure_reason"] == "offline_train_fit_failed"
    assert gate["candidate_align_predicted_negative_z_rate"] == 1.0
    assert "baseline_same_metrics_report_only" in gate


def test_v07a_baseline_report_only_metrics_preserve_null_fields_when_phase_missing() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    action_dim = len(script.ACTION_SCHEMA)
    candidate_rows = [
        script.relabel_v07a_training_row(
            {
                "phase": "APPROACH",
                "trajectory_id": "candidate-align",
                "lateral_error_m": 0.002,
                "insertion_depth_m": 0.0,
                "normalized_action": [0.0] * action_dim,
            }
        ),
        script.relabel_v07a_training_row(
            {
                "phase": "APPROACH",
                "trajectory_id": "candidate-descend",
                "lateral_error_m": 0.0005,
                "insertion_depth_m": 0.01,
                "normalized_action": [0.0, 0.0, -0.16, 0.0, 0.0, 0.0, 0.0],
            }
        ),
        script.relabel_v07a_training_row(
            {
                "phase": "APPROACH",
                "trajectory_id": "candidate-hold",
                "lateral_error_m": 0.0005,
                "insertion_depth_m": 0.031,
                "normalized_action": [0.0] * action_dim,
            }
        ),
    ]
    baseline_rows = [
        script.relabel_v07a_training_row(
            {
                "phase": "APPROACH",
                "trajectory_id": "baseline-align",
                "lateral_error_m": 0.002,
                "insertion_depth_m": 0.0,
                "normalized_action": [0.0] * action_dim,
            }
        )
    ]

    gate = script.derive_v07a_offline_train_fit_gate(
        candidate_rows=candidate_rows,
        candidate_predictions=[row["normalized_action"] for row in candidate_rows],
        baseline_rows=baseline_rows,
        baseline_predictions=[row["normalized_action"] for row in baseline_rows],
        relabel_config_sha256="config-hash",
        baseline_policy_artifact_sha256="baseline-hash",
        candidate_policy_artifact_sha256="candidate-hash",
    )

    baseline_metrics = gate["baseline_same_metrics_report_only"]
    assert gate["passed"] is True
    assert baseline_metrics["metric_role"] == "baseline_report_only"
    assert baseline_metrics["metric_status"] == "report_only_required_phase_missing"
    assert baseline_metrics["phase_status"]["DESCEND"] == "missing"
    assert baseline_metrics["candidate_z_mae_max"] is None


def test_v07a_expressibility_gate_blocks_without_offline_fit_gate(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    gate = script.run_v07a_expressibility_sanity_runtime(
        output_dir=tmp_path,
        manifest={"manifest_sha256": "manifest"},
        device="cpu",
        headless=True,
        isaac_task="Isaac-Factory-PegInsert-Direct-v0",
        max_steps=150,
        action_scale=1.0,
    )

    assert gate["passed"] is False
    assert gate["runtime_backend"] == "isaac_runtime_not_started"
    assert gate["reason"] == "missing_passed_v0_7a_offline_train_fit_gate"
    assert (tmp_path / script.V07A_CHILD_OUTPUT_DIRNAME / "expressibility_sanity_gate_v0_7a.json").exists()


def test_v07a_policy_slice_flags_are_reflected_in_reproducible_command(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    args = script.parse_args(
        [
            "--output-dir",
            str(tmp_path),
            "--scenario-profile",
            "v0_6",
            "--policy-slice",
            "v0_7a",
            "--offline-relabel-only",
        ]
    )

    command = script._command_from_args(args)

    assert args.policy_slice == "v0_7a"
    assert args.offline_relabel_only is True
    assert "--policy-slice v0_7a" in command
    assert "--offline-relabel-only" in command


def test_v07a_offline_relabel_rejects_clean_flag(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    with pytest.raises(ValueError, match="offline-relabel-only must reuse existing v0_6 artifacts"):
        script.main(
            [
                "--output-dir",
                str(tmp_path),
                "--clean",
                "--scenario-profile",
                "v0_6",
                "--policy-slice",
                "v0_7a",
                "--offline-relabel-only",
            ]
        )


def test_v07a_policy_slice_full_run_is_rejected(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    with pytest.raises(ValueError, match="policy-slice v0_7a is only valid"):
        script.main(
            [
                "--output-dir",
                str(tmp_path),
                "--scenario-profile",
                "v0_6",
                "--policy-slice",
                "v0_7a",
                "--skip-isaac",
            ]
        )


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


def test_mvp2c_default_output_dir_uses_persistent_proof_evidence_storage() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    assert script.DEFAULT_OUTPUT_DIR == ROOT / "storage" / "proof_evidence" / "mvp2c_isaac_training_calibration"


def test_mvp2c_build_writes_evidence_manifest_with_file_hashes(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    output_dir = tmp_path / "mvp2c"

    report = script.build_mvp2c_isaac_training_calibration(output_dir=output_dir, clean=True, skip_isaac=True)

    manifest_path = output_dir / "evidence_manifest.json"
    assert manifest_path.exists()
    manifest = script.read_json(manifest_path)
    assert manifest["schema_version"] == "rdf_proof_evidence_manifest_v0.1.0"
    assert manifest["proof_slice"] == "mvp2c_isaac_training_calibration"
    assert manifest["scenario_profile"] == report["scenario_profile"]
    assert manifest["output_dir"] == str(output_dir)
    assert manifest["reproducible_command"] == report["reproducible_command"]
    files = {item["path"]: item for item in manifest["files"]}
    assert "evidence_manifest.json" not in files
    assert "scenario_manifest.json" in files
    assert "mvp2c_isaac_training_calibration_report.json" in files
    assert files["scenario_manifest.json"]["sha256"] == script._sha256_file(output_dir / "scenario_manifest.json")
    assert report["artifact_paths"]["evidence_manifest"] == str(manifest_path)


def test_mvp2c_train_generation_probe_only_writes_evidence_manifest(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    output_dir = tmp_path / "mvp2c_probe"

    exit_code = script.main(
        [
            "--output-dir",
            str(output_dir),
            "--clean",
            "--scenario-profile",
            "v0_6",
            "--train-generation-probe-only",
        ]
    )

    assert exit_code == 0
    manifest = script.read_json(output_dir / "evidence_manifest.json")
    assert manifest["proof_slice"] == "mvp2c_isaac_training_calibration"
    assert manifest["scenario_profile"] == "v0_6"
    files = {item["path"]: item for item in manifest["files"]}
    assert "train_generation_runtime_gate.json" in files
    assert "scenario_manifest.json" in files
    assert "evidence_manifest.json" not in files


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


def test_v06e_non_seated_convergence_uses_capture_radius_and_no_regression() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    converged = script.evaluate_v06e_non_seated_lateral_convergence(
        lateral_errors_m=[0.023, 0.018, 0.011, 0.004, 0.0028, 0.0027, 0.0028, 0.0029, 0.0028, 0.0029],
        capture_radius_m=0.003,
        last_k=5,
    )

    assert converged["non_seated_lateral_converged"] is True
    assert converged["near_band_m"] == 0.003
    assert converged["last_k_median_lateral_m"] <= 0.003
    assert converged["regression_detected"] is False

    regressed = script.evaluate_v06e_non_seated_lateral_convergence(
        lateral_errors_m=[0.0234, 0.012, 0.00276, 0.006, 0.010, 0.0143, 0.0142, 0.0144, 0.0143, 0.0141],
        capture_radius_m=0.003,
        last_k=5,
    )

    assert regressed["non_seated_lateral_converged"] is False
    assert regressed["regression_detected"] is True
    assert regressed["min_lateral_achieved_m"] == 0.00276


def test_v06e_repair_probe_gate_does_not_let_divergence_veto_env_native_pass() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    gate = script.evaluate_v06e_repair_probe_gate(
        {
            16023: {
                "env_native_rollout_success": True,
                "env_native_max_consecutive_success_steps": 10,
                "lateral_divergence_stopped": True,
            },
            16042: {
                "env_native_rollout_success": True,
                "env_native_max_consecutive_success_steps": 10,
                "lateral_divergence_stopped": False,
                "initial_lateral_error_m": 0.016754,
                "last_10_median_lateral_error_m": 0.000365,
            },
            16096: {
                "env_native_rollout_success": False,
                "env_native_max_consecutive_success_steps": 0,
                "lateral_errors_m": [0.023, 0.018, 0.011, 0.004, 0.0028, 0.0027, 0.0028, 0.0029, 0.0028, 0.0029],
            },
        },
        capture_radius_m=0.003,
    )

    assert gate["green_light_for_40_run_gate"] is True
    assert gate["hard_stop"] is False
    assert gate["seed_results"]["16042"]["seed_pass"] is True
    assert gate["seed_results"]["16042"]["divergence_diagnostic_authority"] == "report_only"


def test_v06e_repair_probe_gate_blocks_non_seated_lateral_regression() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    gate = script.evaluate_v06e_repair_probe_gate(
        {
            16023: {
                "env_native_rollout_success": True,
                "env_native_max_consecutive_success_steps": 10,
            },
            16042: {
                "env_native_rollout_success": True,
                "env_native_max_consecutive_success_steps": 10,
            },
            16096: {
                "env_native_rollout_success": False,
                "env_native_max_consecutive_success_steps": 0,
                "lateral_errors_m": [0.0234, 0.012, 0.00276, 0.006, 0.010, 0.0143, 0.0142, 0.0144, 0.0143, 0.0141],
            },
        },
        capture_radius_m=0.003,
    )

    assert gate["green_light_for_40_run_gate"] is False
    assert gate["hard_stop"] is True
    assert gate["seed_results"]["16096"]["seed_pass"] is False
    assert gate["seed_results"]["16096"]["convergence"]["regression_detected"] is True


def test_v06f_non_seated_convergence_uses_approach_gate_not_straight_down_capture() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    converged = script.evaluate_v06f_non_seated_lateral_convergence(
        lateral_errors_m=[0.016, 0.009, 0.003, 0.0012, 0.0009, 0.0008, 0.0009, 0.0009, 0.0008, 0.0009],
        capture_radius_m=0.0001,
        last_k=5,
    )

    assert converged["non_seated_lateral_converged"] is True
    assert converged["straight_down_capture_radius_m"] == 0.0001
    assert converged["near_band_m"] == 0.001
    assert converged["last_k_median_lateral_m"] <= 0.001
    assert converged["regression_detected"] is False

    regressed = script.evaluate_v06f_non_seated_lateral_convergence(
        lateral_errors_m=[0.023, 0.006, 0.0008, 0.002, 0.004, 0.006, 0.0065, 0.0063, 0.0064, 0.0062],
        capture_radius_m=0.0001,
        last_k=5,
    )

    assert regressed["non_seated_lateral_converged"] is False
    assert regressed["regression_detected"] is True


def test_v06f_repair_probe_gate_keeps_env_native_authority_and_uses_approach_convergence() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    gate = script.evaluate_v06f_repair_probe_gate(
        {
            16023: {
                "env_native_rollout_success": True,
                "env_native_max_consecutive_success_steps": 10,
                "max_insertion_depth_m": 0.03,
            },
            16042: {
                "env_native_rollout_success": True,
                "env_native_max_consecutive_success_steps": 10,
                "lateral_divergence_stopped": False,
                "max_insertion_depth_m": 0.03,
            },
            16096: {
                "env_native_rollout_success": False,
                "env_native_max_consecutive_success_steps": 0,
                "lateral_errors_m": [0.023, 0.009, 0.003, 0.0012, 0.0009, 0.0008, 0.0009, 0.0009, 0.0008, 0.0009],
                "max_insertion_depth_m": 0.0,
            },
        },
        capture_radius_m=0.0001,
    )

    assert gate["green_light_for_40_run_gate"] is True
    assert gate["hard_stop"] is False
    assert gate["straight_down_capture_radius_m"] == 0.0001
    assert gate["approach_lateral_gate_m"] == 0.001
    assert gate["seed_results"]["16042"]["divergence_diagnostic_authority"] == "report_only"
    assert gate["seed_results"]["16096"]["convergence"]["non_seated_lateral_converged"] is True


def test_v06f_repair_probe_gate_blocks_when_all_probe_seeds_never_descend() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    gate = script.evaluate_v06f_repair_probe_gate(
        {
            16023: {
                "env_native_rollout_success": False,
                "env_native_max_consecutive_success_steps": 0,
                "lateral_errors_m": [0.0003, 0.0002, 0.0002],
                "max_insertion_depth_m": 0.0,
            },
            16042: {
                "env_native_rollout_success": False,
                "env_native_max_consecutive_success_steps": 0,
                "lateral_errors_m": [0.0011, 0.0009, 0.0009],
                "max_insertion_depth_m": 0.0,
            },
            16096: {
                "env_native_rollout_success": False,
                "env_native_max_consecutive_success_steps": 0,
                "lateral_errors_m": [0.0012, 0.0008, 0.0008],
                "max_insertion_depth_m": 0.0,
            },
        },
        capture_radius_m=0.0001,
    )

    assert gate["green_light_for_40_run_gate"] is False
    assert gate["hard_stop"] is True
    assert gate["failure_mode"] == "all_probe_seeds_never_descended"


def test_v06f_repair_probe_gate_reads_nested_rdf_depth_for_never_descended_guard() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    gate = script.evaluate_v06f_repair_probe_gate(
        {
            16023: {
                "env_native_rollout_success": False,
                "env_native_max_consecutive_success_steps": 0,
                "lateral_errors_m": [0.0003, 0.0002, 0.0002],
                "max_insertion_depth_m": 0.0,
                "rdf_peg_in_hole_metric": {"summary": {"max_insertion_depth_m": 0.022}},
            },
            16042: {
                "env_native_rollout_success": True,
                "env_native_max_consecutive_success_steps": 10,
                "max_insertion_depth_m": 0.0,
                "rdf_peg_in_hole_metric": {"summary": {"max_insertion_depth_m": 0.025}},
            },
            16096: {
                "env_native_rollout_success": False,
                "env_native_max_consecutive_success_steps": 0,
                "lateral_errors_m": [0.014, 0.0008, 0.014],
                "max_insertion_depth_m": 0.0,
                "rdf_peg_in_hole_metric": {"summary": {"max_insertion_depth_m": 0.002}},
            },
        },
        capture_radius_m=0.0001,
    )

    assert gate["all_probe_seeds_never_descended"] is False
    assert gate["failure_mode"] == "repair_probe_not_green"
    assert gate["seed_results"]["16023"]["max_insertion_depth_m"] == 0.022
    assert gate["seed_results"]["16042"]["max_insertion_depth_m"] == 0.025
    assert gate["seed_results"]["16096"]["max_insertion_depth_m"] == 0.002


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


def test_v06f_reset_boundary_diagnosis_detects_asset_jump_and_depth_reset() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    diagnosis = script.summarize_v06f_reset_boundary_diagnosis(
        [
            {
                "step": 147,
                "phase": "SEAT",
                "insertion_depth_m": 0.022587,
                "fixed_asset_pose_w": {"position_m": [0.578435, -0.047545, 0.094409]},
                "held_asset_pose_w": {"position_m": [0.578545, -0.047745, 0.096821]},
            },
            {
                "step": 148,
                "phase": "APPROACH",
                "insertion_depth_m": 0.0,
                "fixed_asset_pose_w": {"position_m": [0.613180, 0.043170, 0.082577]},
                "held_asset_pose_w": {"position_m": [0.602522, 0.042215, 0.118676]},
            },
        ]
    )

    assert diagnosis["schema_version"] == "rdf_mvp2e_v06f_reset_boundary_diagnosis_v0.1.0"
    assert diagnosis["reset_like_jump_detected"] is True
    assert diagnosis["reset_like_jump_count"] == 1
    assert diagnosis["first_reset_like_jump"]["from_step"] == 147
    assert diagnosis["first_reset_like_jump"]["to_step"] == 148
    assert diagnosis["first_reset_like_jump"]["pre_reset_insertion_depth_m"] == 0.022587
    assert diagnosis["first_reset_like_jump"]["post_reset_insertion_depth_m"] == 0.0
    assert diagnosis["heldout_opened"] is False
    assert diagnosis["fixed_40_run_gate_opened"] is False


def test_v06f_reset_boundary_diagnosis_ignores_smooth_trace() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    diagnosis = script.summarize_v06f_reset_boundary_diagnosis(
        [
            {
                "step": 0,
                "phase": "APPROACH",
                "insertion_depth_m": 0.001,
                "fixed_asset_pose_w": {"position_m": [0.0, 0.0, 0.0]},
                "held_asset_pose_w": {"position_m": [0.0, 0.0, 0.1]},
            },
            {
                "step": 1,
                "phase": "INSERT",
                "insertion_depth_m": 0.002,
                "fixed_asset_pose_w": {"position_m": [0.0001, 0.0, 0.0]},
                "held_asset_pose_w": {"position_m": [0.0, 0.0001, 0.099]},
            },
        ]
    )

    assert diagnosis["reset_like_jump_detected"] is False
    assert diagnosis["reset_like_jump_count"] == 0
    assert diagnosis["first_reset_like_jump"] is None


def test_v06f_reset_boundary_diagnosis_ignores_cross_trace_file_boundaries() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    diagnosis = script.summarize_v06f_reset_boundary_diagnosis(
        [
            {
                "step": 149,
                "phase": "SEAT",
                "insertion_depth_m": 0.022,
                "fixed_asset_pose_w": {"position_m": [0.0, 0.0, 0.0]},
                "held_asset_pose_w": {"position_m": [0.0, 0.0, 0.1]},
            },
            {
                "step": 0,
                "phase": "APPROACH",
                "insertion_depth_m": 0.0,
                "fixed_asset_pose_w": {"position_m": [0.08, 0.0, 0.0]},
                "held_asset_pose_w": {"position_m": [0.08, 0.0, 0.1]},
            },
        ]
    )

    assert diagnosis["reset_like_jump_detected"] is False
    assert diagnosis["reset_like_jump_count"] == 0


def test_v06g_post_reset_rows_excluded_from_convergence_and_regression() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    trace_rows = []
    lateral_values = [0.023, 0.0027] + [0.0008] * 10 + [0.014] * 10
    for index, lateral in enumerate(lateral_values):
        jumped = index == 12
        trace_rows.append(
            {
                "step": index,
                "phase": "APPROACH" if jumped else "SEAT",
                "lateral_error_m": lateral,
                "insertion_depth_m": 0.0 if jumped else 0.022,
                "fixed_asset_pose_w": {"position_m": [0.0 if not jumped else 0.08, 0.0, 0.0]},
                "held_asset_pose_w": {"position_m": [0.0 if not jumped else 0.08, 0.0, 0.1]},
            }
        )

    untrimmed = script.evaluate_v06f_non_seated_lateral_convergence(
        lateral_errors_m=[row["lateral_error_m"] for row in trace_rows],
        capture_radius_m=0.0001,
    )
    trimmed = script.apply_v06g_post_reset_tail_exclusion(trace_rows)
    trimmed_convergence = script.evaluate_v06f_non_seated_lateral_convergence(
        lateral_errors_m=[row["lateral_error_m"] for row in trimmed["diagnostic_trace_rows"]],
        capture_radius_m=0.0001,
    )

    assert untrimmed["regression_detected"] is True
    assert untrimmed["non_seated_lateral_converged"] is False
    assert trimmed["post_reset_rows_excluded"] is True
    assert trimmed["first_excluded_row_index"] == 12
    assert trimmed["excluded_row_count"] == 10
    assert trimmed_convergence["regression_detected"] is False
    assert trimmed_convergence["non_seated_lateral_converged"] is True


def test_v06g_exclusion_is_recorded_in_repair_probe_gate_artifact(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    trace_dir = tmp_path / "traces"
    trace_dir.mkdir()

    def row(step: int, *, seed: int, lateral: float, depth: float, jumped: bool = False) -> dict[str, Any]:
        success = seed == 16042
        return {
            "step": step,
            "phase": "APPROACH" if jumped else "SEAT",
            "lateral_error_m": lateral,
            "env_native_success": success,
            "env_native_success_mask": success,
            "env_native_diagnostics_source": "factory_utils_base_target",
            "env_native_xy_dist_m": lateral,
            "env_native_z_disp_m": 0.0 if success else 0.02,
            "env_native_height_threshold_m": 0.001,
            "fixed_asset_pose_w": {"position_m": [0.0 if not jumped else 0.08, 0.0, 0.0]},
            "held_asset_pose_w": {"position_m": [0.0 if not jumped else 0.08, 0.0, 0.1]},
            "held_base_pose_w": {},
            "target_held_base_pose_w": {},
            "legacy_positive_z_disp_m": 0.0,
            "runtime_depth_feature_m": 0.0,
            "insertion_depth_m": depth,
        }

    traces = {
        16023: [row(step, seed=16023, lateral=0.0002, depth=0.022) for step in range(3)],
        16042: [row(step, seed=16042, lateral=0.0004, depth=0.02498) for step in range(10)],
        16096: (
            [row(0, seed=16096, lateral=0.023, depth=0.0), row(1, seed=16096, lateral=0.0027, depth=0.01)]
            + [row(step, seed=16096, lateral=0.0008, depth=0.022) for step in range(2, 12)]
            + [row(step, seed=16096, lateral=0.014, depth=0.0, jumped=(step == 12)) for step in range(12, 22)]
        ),
    }
    paths = []
    for seed, rows in traces.items():
        path = trace_dir / f"seed_{seed}.json"
        script.write_json(
            path,
            {
                "scenario": {"seed": seed},
                "summary": {
                    "env_native_rollout_success": seed == 16042,
                    "env_native_max_consecutive_success_steps": 10 if seed == 16042 else 0,
                },
                "trace": rows,
            },
        )
        paths.append(str(path))
    probe_result = script.BackendResult(
        runtime_gate={"passed": True},
        baseline_rollouts=[],
        candidate_rollouts=[],
        baseline_trace_paths=paths,
        candidate_trace_paths=[],
        runtime_backend="isaac_runtime",
        proof_runtime="isaac_scripted_expert_repair_probe",
        runtime_metadata={},
    )

    gate = script.derive_v06_repair_probe_gate_from_probe_result(
        probe_result,
        capture_radius_m=0.0001,
        gate_version="v0_6f",
    )

    exclusion = gate["v0_6g_post_reset_tail_handling"]
    assert exclusion["post_reset_rows_excluded"] is True
    assert exclusion["per_seed"]["16096"]["post_reset_rows_excluded"] is True
    assert exclusion["per_seed"]["16096"]["first_excluded_row_index"] == 12
    assert gate["seed_results"]["16096"]["convergence"]["regression_detected"] is False
    assert gate["seed_results"]["16096"]["convergence"]["non_seated_lateral_converged"] is True


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


def test_v06a_capture_radius_trial_schedule_samples_all_directions_before_next_delta() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    schedule = script.build_v06a_capture_radius_trial_schedule()

    assert schedule[:4] == [
        ("+x", 0.0001),
        ("-x", 0.0001),
        ("+y", 0.0001),
        ("-y", 0.0001),
    ]
    assert schedule[4:8] == [
        ("+x", 0.0002),
        ("-x", 0.0002),
        ("+y", 0.0002),
        ("-y", 0.0002),
    ]
    assert (("+x", 0.0)) not in schedule


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


def test_v06e_numeric_capture_preflight_rejects_approximate_branch_b(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    preflight = {
        "preflight_branch": "B",
        "inspection_method": "runtime_empirical_capture_radius_probe",
        "capture_radius_m": "approximate",
        "repair_probe_allowed": True,
        "capture_radius_probe_sha256": "abc",
    }
    probe = {
        "preflight_branch": "B",
        "inspection_method": "runtime_empirical_capture_radius_probe",
        "capture_radius_m": "approximate",
        "capture_radius_probe_sha256": "abc",
        "geometry_probe_seed": script.V06A_CAPTURE_RADIUS_PRIMARY_SEED,
        "directions": list(script.V06A_CAPTURE_RADIUS_DIRECTIONS),
        "offset_sweep_m": list(script.V06A_CAPTURE_RADIUS_OFFSET_SWEEP_M),
        "measurement": {"capture_radius_m": "approximate"},
    }

    resolved = script.validate_v06e_numeric_capture_radius_preflight(
        preflight=preflight,
        capture_radius_probe=probe,
    )

    assert resolved["repair_probe_allowed"] is False
    assert resolved["insert_parameter_freeze_allowed"] is False
    assert resolved["reason"] == "capture_radius_not_numeric"


def test_v06e_numeric_capture_preflight_accepts_geometry_isolated_numeric_probe() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    preflight = {
        "preflight_branch": "B",
        "inspection_method": "runtime_empirical_capture_radius_probe",
        "capture_radius_m": 0.0002,
        "repair_probe_allowed": True,
        "insert_parameter_freeze_allowed": True,
        "capture_radius_probe_sha256": "abc",
    }
    probe = {
        "preflight_branch": "B",
        "inspection_method": "runtime_empirical_capture_radius_probe",
        "capture_radius_m": 0.0002,
        "capture_radius_probe_sha256": "abc",
        "geometry_probe_seed": script.V06A_CAPTURE_RADIUS_PRIMARY_SEED,
        "geometry_isolated": True,
        "xy_correction_enabled": False,
        "yaw_correction_enabled": False,
        "z_push_mode": "straight_down_bounded",
        "directions": list(script.V06A_CAPTURE_RADIUS_DIRECTIONS),
        "offset_sweep_m": list(script.V06A_CAPTURE_RADIUS_OFFSET_SWEEP_M),
        "measurement": {"capture_radius_m": 0.0002},
    }

    resolved = script.validate_v06e_numeric_capture_radius_preflight(
        preflight=preflight,
        capture_radius_probe=probe,
    )

    assert resolved["repair_probe_allowed"] is True
    assert resolved["insert_parameter_freeze_allowed"] is True
    assert resolved["capture_radius_m"] == 0.0002
    assert resolved["capture_radius_probe_geometry_isolated"] is True


def test_v06e_controller_repair_config_derives_z_gate_from_capture_radius() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    config = script.build_v06e_controller_repair_config(capture_radius_m=0.003)

    assert config["controller_version"] == "v0_6_active_state_controller"
    assert config["capture_radius_m"] == 0.003
    assert config["align_lateral_gate_m"] == 0.003
    assert config["tol_align_source"] == "empirical_capture_radius_m"
    assert config["z_push_gate"] == "lateral_error_m <= capture_radius_m"
    assert config["retry_recover_withdraw_search"] is False
    assert config["force_reactive_control"] is False


def test_v06f_controller_repair_config_uses_approach_gate_not_raw_capture_radius() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    config = script.build_v06f_controller_repair_config(capture_radius_m=0.0001)

    assert config["schema_version"] == "rdf_mvp2e_v06f_controller_repair_config_v0.1.0"
    assert config["straight_down_capture_radius_m"] == 0.0001
    assert config["approach_lateral_gate_m"] == 0.001
    assert config["align_lateral_gate_m"] == 0.001
    assert config["z_push_gate"] == "lateral_error_m <= approach_lateral_gate_m"
    assert config["success_authority"] == "env_native_10_consecutive"
    assert config["proof_authority"] is False
    assert config["horizon_increase"] is False
    assert config["retry_enabled"] is False
    assert config["search_enabled"] is False
    assert config["force_control_enabled"] is False


def test_v06f_approach_gate_uses_capture_multiplier_above_floor() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    config = script.build_v06f_controller_repair_config(capture_radius_m=0.0004)

    assert config["straight_down_capture_radius_m"] == 0.0004
    assert config["approach_lateral_gate_m"] == 0.004
    assert config["approach_gate_floor_m"] == 0.001
    assert config["approach_gate_capture_multiplier"] == 10.0


def test_v06f_repair_probe_config_can_be_selected_without_opening_train_or_heldout() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    config = script.build_v06f_controller_repair_config(capture_radius_m=0.0001)

    assert config["controller_repair_version"] == "v0_6f"
    assert config["align_lateral_gate_m"] == 0.001
    assert config["proof_authority"] is False
    assert config["non_claims"]["real_robot_success"] is False


def test_v06h_controller_repair_config_changes_only_global_pacing_not_gate() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    config = script.build_v06h_controller_repair_config(capture_radius_m=0.0001)

    assert config["schema_version"] == "rdf_mvp2e_v06h_controller_repair_config_v0.1.0"
    assert config["controller_repair_version"] == "v0_6h"
    assert config["pacing_profile"] == "seat_by_deadline_global_v0_6h"
    assert config["approach_lateral_gate_m"] == 0.001
    assert config["align_lateral_gate_m"] == 0.001
    assert config["z_push_gate"] == "lateral_error_m <= approach_lateral_gate_m"
    assert config["z_action_scale"] == 32.0
    assert config["z_action_clip"] == 0.16
    assert config["horizon_increase"] is False
    assert config["per_seed_tuning"] is False
    assert config["retry_enabled"] is False
    assert config["search_enabled"] is False
    assert config["force_control_enabled"] is False
    assert config["proof_authority"] is False


def test_v06h_scripted_expert_policy_uses_global_pacing_config() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    repair_config = script.build_v06h_controller_repair_config(capture_radius_m=0.0001)
    policy = script._scripted_expert_probe_policy_artifact(
        selected_adapter_id="isaac_signed_xy_downward_servo_v0",
        selected_adapter_config={"z_action_scale": 24.0, "z_action_clip": 0.12},
        scenario_profile="v0_6",
        controller_repair_config=repair_config,
    )

    config = policy["selected_action_adapter_config"]
    assert config["controller_repair_version"] == "v0_6h"
    assert config["z_action_scale"] == 32.0
    assert config["z_action_clip"] == 0.16
    assert config["approach_lateral_gate_m"] == 0.001
    assert policy["train_generation_controller_config_sha256"]


def test_v06i_controller_repair_config_changes_only_global_xy_pacing_not_gate() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    config = script.build_v06i_controller_repair_config(capture_radius_m=0.0001)

    assert config["schema_version"] == "rdf_mvp2e_v06i_controller_repair_config_v0.1.0"
    assert config["controller_repair_version"] == "v0_6i"
    assert config["pacing_profile"] == "seat_by_deadline_global_xy_pacing_v0_6i"
    assert config["approach_lateral_gate_m"] == 0.001
    assert config["z_push_gate"] == "lateral_error_m <= approach_lateral_gate_m"
    assert config["z_action_scale"] == 32.0
    assert config["z_action_clip"] == 0.16
    assert config["xy_state_feedback_gain"] == 5.0
    assert config["xy_action_scale"] == 5.0
    assert config["xy_action_clip"] == 0.05
    assert config["horizon_increase"] is False
    assert config["per_seed_tuning"] is False
    assert config["retry_enabled"] is False
    assert config["search_enabled"] is False
    assert config["force_control_enabled"] is False


def test_v06h_repair_probe_gate_preserves_v06f_green_rule(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    trace_dir = tmp_path / "traces"
    trace_dir.mkdir()
    paths = []
    for seed, success, lateral_tail in [
        (16023, True, [0.0004] * 10),
        (16042, True, [0.0005] * 10),
        (16096, False, [0.023, 0.010, 0.001, 0.0007, 0.00065, 0.00066, 0.00067, 0.00066, 0.00065, 0.00066]),
    ]:
        rows = [
            {
                "step": index,
                "env_native_diagnostics_source": "factory_utils_base_target",
                "env_native_success": bool(success),
                "env_native_success_mask": bool(success),
                "env_native_xy_dist_m": 0.0005,
                "env_native_z_disp_m": 0.0002 if success else 0.02,
                "env_native_height_threshold_m": 0.001,
                "lateral_error_m": lateral_tail[min(index, len(lateral_tail) - 1)],
                "insertion_depth_m": 0.025 if success else 0.002,
                "runtime_depth_feature_m": 0.025 if success else 0.002,
                "legacy_positive_z_disp_m": 0.05,
                "relative_x_m": lateral_tail[min(index, len(lateral_tail) - 1)],
                "relative_y_m": 0.0,
                "orientation_error_deg": 0.0,
                "held_asset_pose_w": {"position_m": [0.0, 0.0, 0.0], "quaternion_wxyz": [1.0, 0.0, 0.0, 0.0]},
                "fixed_asset_pose_w": {"position_m": [0.0, 0.0, 0.0], "quaternion_wxyz": [1.0, 0.0, 0.0, 0.0]},
                "held_base_pose_w": {"position_m": [0.0, 0.0, 0.0], "quaternion_wxyz": [1.0, 0.0, 0.0, 0.0]},
                "target_held_base_pose_w": {
                    "position_m": [0.0, 0.0, 0.0],
                    "quaternion_wxyz": [1.0, 0.0, 0.0, 0.0],
                },
            }
            for index in range(10)
        ]
        path = trace_dir / f"probe_{seed}.json"
        script.write_json(
            path,
            {
                "scenario": {"seed": seed},
                "summary": {
                    "success": success,
                    "env_native_rollout_success": success,
                    "env_native_max_consecutive_success_steps": 10 if success else 0,
                    "env_native_success_available": True,
                    "failure_reason": "" if success else "ENV_NATIVE_STABILITY_WINDOW_NOT_REACHED",
                    "max_insertion_depth_m": 0.025 if success else 0.002,
                    "steps": 10,
                },
                "trace": rows,
            },
        )
        paths.append(str(path))

    probe_result = script.BackendResult(
        runtime_gate={"passed": True},
        baseline_rollouts=[],
        candidate_rollouts=[],
        baseline_trace_paths=paths,
        candidate_trace_paths=[],
        runtime_backend="isaac_runtime",
        proof_runtime="isaac_scripted_expert_repair_probe",
        runtime_metadata={},
    )

    gate = script.derive_v06_repair_probe_gate_from_probe_result(
        probe_result,
        capture_radius_m=0.0001,
        gate_version="v0_6h",
    )

    assert gate["repair_probe_gate_semantics"] == "v0_6f"
    assert gate["green_light_for_40_run_gate"] is True
    assert gate["seed_results"]["16096"]["convergence"]["non_seated_lateral_converged"] is True


def test_v06f_repair_probe_gate_validation_uses_authority_layer(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    trace_dir = tmp_path / "traces"
    trace_dir.mkdir()
    paths = []
    for seed, success, lateral_tail in [
        (16023, True, [0.0004] * 10),
        (16042, True, [0.016, 0.010, 0.004, 0.001, 0.0005, 0.00045, 0.00044, 0.00043, 0.00042, 0.00041]),
        (16096, False, [0.023, 0.010, 0.001, 0.0007, 0.00065, 0.00066, 0.00067, 0.00066, 0.00065, 0.00066]),
    ]:
        rows = [
            {
                "step": index,
                "env_native_diagnostics_source": "factory_utils_base_target",
                "env_native_success": bool(success),
                "env_native_success_mask": bool(success),
                "env_native_xy_dist_m": 0.0005,
                "env_native_z_disp_m": 0.0002 if success else 0.02,
                "env_native_height_threshold_m": 0.001,
                "lateral_error_m": lateral_tail[min(index, len(lateral_tail) - 1)],
                "insertion_depth_m": 0.025 if success else 0.002,
                "runtime_depth_feature_m": 0.025 if success else 0.002,
                "legacy_positive_z_disp_m": 0.05,
                "relative_x_m": lateral_tail[min(index, len(lateral_tail) - 1)],
                "relative_y_m": 0.0,
                "orientation_error_deg": 0.0,
                "held_asset_pose_w": {"position_m": [0.0, 0.0, 0.0], "quaternion_wxyz": [1.0, 0.0, 0.0, 0.0]},
                "fixed_asset_pose_w": {"position_m": [0.0, 0.0, 0.0], "quaternion_wxyz": [1.0, 0.0, 0.0, 0.0]},
                "held_base_pose_w": {"position_m": [0.0, 0.0, 0.0], "quaternion_wxyz": [1.0, 0.0, 0.0, 0.0]},
                "target_held_base_pose_w": {
                    "position_m": [0.0, 0.0, 0.0],
                    "quaternion_wxyz": [1.0, 0.0, 0.0, 0.0],
                },
            }
            for index in range(10)
        ]
        path = trace_dir / f"probe_{seed}.json"
        script.write_json(
            path,
            {
                "scenario": {"seed": seed},
                "summary": {
                    "success": success,
                    "env_native_rollout_success": success,
                    "env_native_max_consecutive_success_steps": 10 if success else 0,
                    "env_native_success_available": True,
                    "failure_reason": "" if success else "ENV_NATIVE_STABILITY_WINDOW_NOT_REACHED",
                    "max_insertion_depth_m": 0.025 if success else 0.002,
                    "steps": 10,
                },
                "trace": rows,
            },
        )
        paths.append(str(path))

    probe_result = script.BackendResult(
        runtime_gate={"passed": True},
        baseline_rollouts=[],
        candidate_rollouts=[],
        baseline_trace_paths=paths,
        candidate_trace_paths=[],
        runtime_backend="isaac_runtime",
        proof_runtime="isaac_scripted_expert_repair_probe",
        runtime_metadata={},
    )
    gate = script.derive_v06_repair_probe_gate_from_probe_result(
        probe_result,
        capture_radius_m=0.0001,
        gate_version="v0_6i",
    )
    preflight = {
        "chamfer_preflight_sha256": "preflight_hash",
        "repair_probe_allowed": True,
        "preflight_branch": "B",
    }
    gate["chamfer_preflight"] = dict(preflight)
    gate["v0_6a_post_repair_probe_gate"] = {"green_light_for_40_run_gate": True}
    gate["repair_probe_gate_sha256"] = script._sha256_payload_excluding(gate, "repair_probe_gate_sha256")

    validated = script.validate_v06_repair_probe_gate_artifact(gate, preflight=preflight)

    assert validated["green_light_for_40_run_gate"] is True
    assert validated["seed_results"]["16042"]["divergence_diagnostic_authority"] == "report_only"
    assert validated["seed_results"]["16042"]["lateral_divergence_stopped"] is False


def test_v06e_repair_probe_gate_from_probe_result_uses_capture_radius(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    trace_dir = tmp_path / "traces"
    trace_dir.mkdir()
    paths = []
    scenarios = [
        (16023, True, [0.002, 0.001, 0.0005]),
        (16042, True, [0.016, 0.004, 0.0004]),
        (16096, False, [0.023, 0.010, 0.0028, 0.0029, 0.0028, 0.0029, 0.0028, 0.0029, 0.0028, 0.0029]),
    ]
    for seed, success, lateral_values in scenarios:
        rows = [
            {
                "step": index,
                "phase": "APPROACH",
                "lateral_error_m": lateral,
                "env_native_success": success,
                "env_native_success_mask": success,
                "env_native_diagnostics_source": "factory_utils_base_target",
                "env_native_xy_dist_m": lateral,
                "env_native_z_disp_m": 0.0 if success else 0.02,
                "env_native_height_threshold_m": 0.001,
                "held_asset_pose_w": {},
                "fixed_asset_pose_w": {},
                "held_base_pose_w": {},
                "target_held_base_pose_w": {},
                "legacy_positive_z_disp_m": 0.0,
                "runtime_depth_feature_m": 0.0,
                "insertion_depth_m": 0.0,
            }
            for index, lateral in enumerate(lateral_values)
        ]
        path = trace_dir / f"seed_{seed}.json"
        script.write_json(
            path,
            {
                "scenario": {"seed": seed},
                "summary": {
                    "env_native_rollout_success": success,
                    "env_native_max_consecutive_success_steps": 10 if success else 0,
                },
                "trace": rows,
            },
        )
        paths.append(str(path))
    probe_result = script.BackendResult(
        runtime_gate={"passed": True},
        baseline_rollouts=[],
        candidate_rollouts=[],
        baseline_trace_paths=paths,
        candidate_trace_paths=[],
        runtime_backend="isaac_runtime",
        proof_runtime="isaac_scripted_expert_repair_probe",
        runtime_metadata={},
    )

    gate = script.derive_v06_repair_probe_gate_from_probe_result(
        probe_result,
        capture_radius_m=0.003,
    )

    assert gate["schema_version"] == "rdf_mvp2e_v06e_repair_probe_gate_v0.1.0"
    assert gate["green_light_for_40_run_gate"] is True
    assert gate["seed_results"]["16042"]["seed_pass"] is True
    assert gate["seed_results"]["16096"]["seed_pass"] is True


def test_v06f_repair_probe_gate_from_probe_result_embeds_reset_boundary_diagnosis(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    trace_dir = tmp_path / "traces"
    trace_dir.mkdir()
    paths = []
    scenarios = [
        (16023, False, [0.0002, 0.0107], [0.022587, 0.0]),
        (16042, True, [0.0004, 0.0004], [0.02498, 0.02498]),
        (16096, False, [0.0001, 0.0144], [0.002396, 0.0]),
    ]
    for seed, success, lateral_values, depth_values in scenarios:
        rows = []
        for index, (lateral, depth) in enumerate(zip(lateral_values, depth_values, strict=True)):
            jumped = index == 1 and seed in {16023, 16096}
            rows.append(
                {
                    "step": 147 + index,
                    "phase": "APPROACH" if jumped else "SEAT",
                    "lateral_error_m": lateral,
                    "env_native_success": success,
                    "env_native_success_mask": success,
                    "env_native_diagnostics_source": "factory_utils_base_target",
                    "env_native_xy_dist_m": lateral,
                    "env_native_z_disp_m": 0.0 if success else 0.02,
                    "env_native_height_threshold_m": 0.001,
                    "fixed_asset_pose_w": {
                        "position_m": [0.0 if not jumped else 0.08, 0.0, 0.0],
                    },
                    "held_asset_pose_w": {
                        "position_m": [0.0 if not jumped else 0.08, 0.0, 0.1],
                    },
                    "held_base_pose_w": {},
                    "target_held_base_pose_w": {},
                    "legacy_positive_z_disp_m": 0.0,
                    "runtime_depth_feature_m": 0.0,
                    "insertion_depth_m": depth,
                }
            )
        path = trace_dir / f"seed_{seed}.json"
        script.write_json(
            path,
            {
                "scenario": {"seed": seed},
                "summary": {
                    "env_native_rollout_success": success,
                    "env_native_max_consecutive_success_steps": 10 if success else 0,
                },
                "trace": rows,
            },
        )
        paths.append(str(path))
    probe_result = script.BackendResult(
        runtime_gate={"passed": True},
        baseline_rollouts=[],
        candidate_rollouts=[],
        baseline_trace_paths=paths,
        candidate_trace_paths=[],
        runtime_backend="isaac_runtime",
        proof_runtime="isaac_scripted_expert_repair_probe",
        runtime_metadata={},
    )

    gate = script.derive_v06_repair_probe_gate_from_probe_result(
        probe_result,
        capture_radius_m=0.0001,
        gate_version="v0_6f",
    )

    reset_diagnosis = gate["v0_6f_reset_boundary_diagnosis"]
    assert reset_diagnosis["reset_like_jump_detected"] is True
    assert reset_diagnosis["reset_like_jump_count"] == 2
    assert reset_diagnosis["recommended_next_step"] == "diagnose_episode_reset_boundary_before_controller_changes"


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


def test_v06_train_generation_probe_uses_repair_probe_approved_controller(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    captured: dict[str, Any] = {}

    class FakeIsaacTrainGenerationBackend:
        def __init__(self, **_: Any) -> None:
            pass

        def run_single_policy_probe(self, **kwargs: Any) -> Any:
            policy_artifact = kwargs["policy_artifact"]
            captured["selected_action_adapter_config"] = policy_artifact["selected_action_adapter_config"]
            return script.BackendResult(
                runtime_gate={"passed": True},
                baseline_rollouts=[],
                candidate_rollouts=[],
                baseline_trace_paths=[],
                candidate_trace_paths=[],
                runtime_backend="isaac_runtime",
                proof_runtime="dedicated_isaac_connector_insertion_evaluator",
                runtime_metadata={},
            )

    monkeypatch.setattr(script, "IsaacConnectorInsertionEvaluatorBackend", FakeIsaacTrainGenerationBackend)
    manifest = script.build_mvp2c_scenario_manifest(output_dir=tmp_path, scenario_profile="v0_6")
    approved_config = script.build_v06i_controller_repair_config(capture_radius_m=0.0001)

    script._run_isaac_train_generation_probe_direct(
        output_dir=tmp_path,
        manifest=manifest,
        selected_adapter_id="isaac_signed_xy_downward_servo_v0",
        selected_adapter_config={"xy_action_scale": 3.0, "z_action_scale": 32.0},
        device="cpu",
        headless=True,
        isaac_task="fake-task",
        max_steps=150,
        action_scale=1.0,
        min_success_count=20,
        success_trace_cap=40,
        controller_repair_config=approved_config,
    )

    config = captured["selected_action_adapter_config"]
    assert config["controller_repair_version"] == "v0_6i"
    assert config["controller_repair_config_sha256"] == approved_config["controller_repair_config_sha256"]
    assert config["xy_state_feedback_gain"] == 5.0
    assert config["z_push_gate"] == "lateral_error_m <= approach_lateral_gate_m"


def test_v06_existing_train_generation_gate_can_be_reused(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    gate = {
        "passed": True,
        "runtime_backend": "isaac_runtime",
        "proof_runtime": "isaac_scripted_expert_train_generation_probe",
        "actual_train_generation_evidence": True,
        "training_trajectory_source": "isaac_runtime_scripted_expert_rollout",
        "generated_rollout_count": 40,
        "generated_success_count": 28,
        "required_success_count": 20,
        "success_trace_cap": 40,
        "generated_success_trace_paths": [],
        "generated_trace_paths": [],
    }
    script.write_json(tmp_path / "train_generation_runtime_gate.json", gate)

    resolved = script.resolve_existing_v06_train_generation_runtime_gate(output_dir=tmp_path)

    assert resolved["reuse_allowed"] is True
    assert resolved["gate"]["generated_success_count"] == 28


def test_v06_preheldout_gates_block_heldout_until_expressibility_and_calibration_pass(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    status = script.resolve_v06_preheldout_gate_status(output_dir=tmp_path)

    assert status["heldout_allowed"] is False
    assert status["expressibility_sanity_gate"]["passed"] is False
    assert status["calibration_presignal_gate"]["passed"] is False
    assert "expressibility_sanity_gate" in status["missing_or_failed_gates"]
    assert "calibration_presignal_gate" in status["missing_or_failed_gates"]


def test_v06_expressibility_manifest_uses_first_five_success_train_seeds(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    manifest = script.build_mvp2c_scenario_manifest(output_dir=tmp_path, scenario_profile="v0_6")
    train_gate = {
        "generated_success_trace_paths": [
            f"/tmp/train_generation_probe_{index:04d}_train_success_{seed}_isaac_trace.json"
            for index, seed in enumerate([19003, 19012, 19129, 19021, 19030, 19002])
        ]
    }

    probe_manifest = script.build_v06_expressibility_sanity_manifest(
        manifest=manifest,
        train_generation_runtime_gate=train_gate,
    )

    assert [row["seed"] for row in probe_manifest["scenarios"]] == [19003, 19012, 19129, 19021, 19030]
    assert {row["split"] for row in probe_manifest["scenarios"]} == {"held_out"}
    assert probe_manifest["heldout_21000_21049_accessed"] is False


def test_v06_expressibility_gate_requires_two_of_five() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    probe_result = script.BackendResult(
        runtime_gate={"passed": True},
        baseline_rollouts=[
            {"success": True, "env_native_rollout_success": True},
            {"success": False, "env_native_rollout_success": False},
            {"success": True, "env_native_rollout_success": True},
            {"success": False, "env_native_rollout_success": False},
            {"success": False, "env_native_rollout_success": False},
        ],
        candidate_rollouts=[],
        baseline_trace_paths=["trace0", "trace1", "trace2", "trace3", "trace4"],
        candidate_trace_paths=[],
        runtime_backend="isaac_runtime",
        proof_runtime="dedicated_isaac_connector_insertion_evaluator",
        runtime_metadata={},
    )

    gate = script.derive_v06_expressibility_sanity_gate_from_probe_result(probe_result)

    assert gate["passed"] is True
    assert gate["success_count"] == 2
    assert gate["required_success_count"] == 2
    assert gate["heldout_opened"] is False


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
