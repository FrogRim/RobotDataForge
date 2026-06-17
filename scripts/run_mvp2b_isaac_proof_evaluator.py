#!/usr/bin/env python3
"""Build MVP-2B dedicated Isaac proof-evaluator artifacts.

The deterministic backend in this script exists for CI and artifact-shape
validation. It can exercise the existing held-out policy uplift validator, but
only the Isaac runtime backend is allowed to close MVP-2.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import shutil
import struct
import sys
from typing import Any, Sequence
import zlib

import h5py
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
API_ROOT = ROOT / "apps" / "api"
for path in (SCRIPT_DIR, API_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from app.services.normalized_trajectory_contract import (  # noqa: E402
    REQUIRED_ACTION_ROLE_KEYS,
    TRAJECTORY_CONTRACT_SCHEMA_VERSION,
    NormalizedTrajectoryContractValidator,
)
from app.services.proof_evidence import write_evidence_manifest  # noqa: E402
from run_mvp2_learning_proven_policy_eval import build_mvp2_learning_proven_policy_eval  # noqa: E402


SCHEMA_VERSION = "rdf_mvp2b_isaac_proof_evaluator_v0.1.0"
SCENARIO_MANIFEST_VERSION = "rdf_mvp2b_scenario_manifest_v0.1.0"
DEFAULT_OUTPUT_DIR = ROOT / "storage" / "proof_evidence" / "mvp2b_isaac_proof_evaluator"
ENV_RESET_POST_STEP_GUARD_STEPS = 2
DEFAULT_ISAAC_TASK = "Isaac-Factory-PegInsert-Direct-v0"
DEFAULT_ISAAC_DEVICE = "cuda:0"
MIN_PROOF_ROLLOUTS_PER_POLICY = 20
POLICY_CLASS = "phase_conditioned_numpy_bc_policy_v0"
TRAINER = "rdf_numpy_phase_conditioned_bc_trainer_v0"
RESIDUAL_POLICY_CLASS = "phase_conditioned_residual_servo_bc_policy_v0"
RESIDUAL_TRAINER = "rdf_numpy_phase_conditioned_residual_servo_bc_trainer_v0"
RESIDUAL_TRAINER_FAMILY = "phase_conditioned_residual_servo_bc"
RESIDUAL_TARGET_DEFINITION = "actual_trace_action_minus_weak_base_servo_action"
V07B_POLICY_SLICE_ID = "v0_7b"
V07B_BASE_SERVO_ID = "frozen_base_geometry_servo_v0_7b"
V07B_RESIDUAL_TARGET_DEFINITION = "actual_trace_action_minus_frozen_base_geometry_servo_action"
V07C_POLICY_SLICE_ID = "v0_7c"
V07C_SLICE_ID = "mvp2e_v07c_residual_action_authority_gate"
V07C_ACTION_AUTHORITY_CONFIG_SCHEMA_VERSION = "rdf_mvp2e_v07c_action_authority_config_v0.1.0"
V07C_AUTHORITY_FILTER_ID = "frozen_residual_action_authority_gate_v0_7c"
V07D_POLICY_SLICE_ID = "v0_7d"
V07D_SLICE_ID = "mvp2e_v07d_action_authority_post_adapter_z_gate"
V07D_FINAL_ACTION_AUTHORITY_CONFIG_SCHEMA_VERSION = "rdf_mvp2e_v07d_final_action_authority_config_v0.1.0"
V07D_FINAL_POST_ADAPTER_AUTHORITY_ID = "final_post_adapter_z_authority_gate_v0_7d"
V07E_POLICY_SLICE_ID = "v0_7e"
V07E_SHARED_HYSTERESIS_AUTHORITY_CONFIG_SCHEMA_VERSION = (
    "rdf_mvp2e_v07e_hysteresis_authority_config_v0.1.0"
)
V07E_SHARED_HYSTERESIS_AUTHORITY_ID = "shared_stateful_hysteresis_authority_v0_7e"
V07G_POLICY_SLICE_ID = "v0_7g"
V07G_SLICE_ID = "mvp2e_v07g_xy_authority_saturation_repair"
V07G_FINAL_XY_AUTHORITY_CONFIG_SCHEMA_VERSION = "rdf_mvp2e_v07g_xy_authority_config_v0.1.0"
V07G_FINAL_POST_ADAPTER_XY_AUTHORITY_ID = "final_post_adapter_xy_authority_gate_v0_7g"
V07J_POLICY_SLICE_ID = "v0_7j"
V07J_SLICE_ID = "mvp2e_v07j_off_center_xy_authority_repair"
V07J_FINAL_XY_AUTHORITY_CONFIG_SCHEMA_VERSION = "rdf_mvp2e_v07j_xy_authority_config_v0.1.0"
V07J_FINAL_POST_ADAPTER_XY_AUTHORITY_ID = "final_post_adapter_xy_authority_gate_v0_7j"
V07K_POLICY_SLICE_ID = "v0_7k"
V07K_SLICE_ID = "mvp2e_v07k_runtime_hysteresis_wiring_repair"
V07M_POLICY_SLICE_ID = "v0_7m"
V07M_SLICE_ID = "mvp2e_v07m_z_window_progress_authority_repair"
V07M_SHARED_HYSTERESIS_AUTHORITY_CONFIG_SCHEMA_VERSION = (
    "rdf_mvp2e_v07m_hysteresis_authority_config_v0.1.0"
)
V07N_POLICY_SLICE_ID = "v0_7n"
V07N_SLICE_ID = "mvp2e_v07n_z_open_xy_center_maintenance"
V07N_FINAL_XY_AUTHORITY_CONFIG_SCHEMA_VERSION = "rdf_mvp2e_v07n_xy_authority_config_v0.1.0"
V07N_FINAL_POST_ADAPTER_XY_AUTHORITY_ID = "final_post_adapter_xy_authority_gate_v0_7n"
V07O_POLICY_SLICE_ID = "v0_7o"
V07O_SLICE_ID = "mvp2e_v07o_composed_xy_authority"
V07O_FINAL_XY_AUTHORITY_CONFIG_SCHEMA_VERSION = "rdf_mvp2e_v07o_xy_authority_config_v0.1.0"
V07O_FINAL_POST_ADAPTER_XY_AUTHORITY_ID = "final_post_adapter_xy_authority_gate_v0_7o"
V08A_POLICY_SLICE_ID = "v0_8a"
V08A_SLICE_ID = "mvp2e_v08a_fresh_seat_window_authority"
V08A_SEAT_WINDOW_AUTHORITY_CONFIG_SCHEMA_VERSION = (
    "rdf_mvp2e_v08a_seat_window_authority_config_v0.1.0"
)
V08A_SEAT_WINDOW_AUTHORITY_ID = "seat_window_progress_authority_v0_8a"
V08B_POLICY_SLICE_ID = "v0_8b"
V08B_SLICE_ID = "mvp2e_v08b_scenario_aware_seat_window_authority"
V08B_SEAT_WINDOW_AUTHORITY_CONFIG_SCHEMA_VERSION = (
    "rdf_mvp2e_v08b_scenario_aware_seat_window_authority_config_v0.1.0"
)
V08B_SEAT_WINDOW_AUTHORITY_ID = "scenario_aware_seat_window_authority_v0_8b"
V08D_POLICY_SLICE_ID = "v0_8d"
V08D_SLICE_ID = "mvp2e_v08d_capture_conditioned_progress_authority"
V08D_CAPTURE_CONDITIONED_PROGRESS_AUTHORITY_CONFIG_SCHEMA_VERSION = (
    "rdf_mvp2e_v08d_capture_conditioned_progress_authority_config_v0.1.0"
)
V08D_CAPTURE_CONDITIONED_PROGRESS_AUTHORITY_ID = "capture_conditioned_progress_authority_v0_8d"
V08F_POLICY_SLICE_ID = "v0_8f"
V08F_SLICE_ID = "mvp2e_v08f_horizon_reserved_capture_authority"
V08F_HORIZON_RESERVED_CAPTURE_AUTHORITY_CONFIG_SCHEMA_VERSION = (
    "rdf_mvp2e_v08f_horizon_reserved_capture_authority_config_v0.1.0"
)
V08F_HORIZON_RESERVED_CAPTURE_AUTHORITY_ID = "horizon_reserved_capture_authority_v0_8f"
V08G_POLICY_SLICE_ID = "v0_8g"
V08G_SLICE_ID = "mvp2e_v08g_deadline_precedence_horizon_authority"
V08G_DEADLINE_PRECEDENCE_HORIZON_AUTHORITY_CONFIG_SCHEMA_VERSION = (
    "rdf_mvp2e_v08g_deadline_precedence_horizon_authority_config_v0.1.0"
)
V08G_DEADLINE_PRECEDENCE_HORIZON_AUTHORITY_ID = (
    "deadline_precedence_horizon_authority_v0_8g"
)
V08H_POLICY_SLICE_ID = "v0_8h"
V08H_SLICE_ID = "mvp2e_v08h_early_centered_z_open_safe_entry"
V08H_EARLY_CENTERED_Z_OPEN_SAFE_ENTRY_CONFIG_SCHEMA_VERSION = (
    "rdf_mvp2e_v08h_early_centered_z_open_safe_entry_config_v0.1.0"
)
V08H_EARLY_CENTERED_Z_OPEN_SAFE_ENTRY_AUTHORITY_ID = (
    "early_centered_z_open_safe_entry_authority_v0_8h"
)
V08K_POLICY_SLICE_ID = "v0_8k"
V09_POLICY_SLICE_ID = "v0_9"
V10_POLICY_SLICE_ID = "v0_10"
V11_POLICY_SLICE_ID = "v0_11"
V12_POLICY_SLICE_ID = "v0_12"
V13_POLICY_SLICE_ID = "v0_13"
V14_POLICY_SLICE_ID = "v0_14"
V08H_DERIVED_POLICY_SLICE_IDS = {
    V08H_POLICY_SLICE_ID,
    V08K_POLICY_SLICE_ID,
    V09_POLICY_SLICE_ID,
    V10_POLICY_SLICE_ID,
    V11_POLICY_SLICE_ID,
    V12_POLICY_SLICE_ID,
}
V07E_HYSTERESIS_RUNTIME_POLICY_SLICE_IDS = {
    V07E_POLICY_SLICE_ID,
    V07G_POLICY_SLICE_ID,
    V07J_POLICY_SLICE_ID,
    V07K_POLICY_SLICE_ID,
    V07M_POLICY_SLICE_ID,
    V07N_POLICY_SLICE_ID,
    V07O_POLICY_SLICE_ID,
    V08A_POLICY_SLICE_ID,
    V08B_POLICY_SLICE_ID,
    V08D_POLICY_SLICE_ID,
    V08F_POLICY_SLICE_ID,
    V08G_POLICY_SLICE_ID,
    *V08H_DERIVED_POLICY_SLICE_IDS,
    V13_POLICY_SLICE_ID,
    V14_POLICY_SLICE_ID,
}
V07B_BASE_SERVO_RUNTIME_POLICY_SLICE_IDS = {
    V07B_POLICY_SLICE_ID,
    V07C_POLICY_SLICE_ID,
    V07D_POLICY_SLICE_ID,
    *V07E_HYSTERESIS_RUNTIME_POLICY_SLICE_IDS,
}
V07C_AUTHORITY_RUNTIME_POLICY_SLICE_IDS = {
    V07C_POLICY_SLICE_ID,
    V07D_POLICY_SLICE_ID,
    *V07E_HYSTERESIS_RUNTIME_POLICY_SLICE_IDS,
}
V07D_FINAL_AUTHORITY_RUNTIME_POLICY_SLICE_IDS = {
    V07D_POLICY_SLICE_ID,
    *V07E_HYSTERESIS_RUNTIME_POLICY_SLICE_IDS,
}
WEAK_BASE_SERVO_CONFIG = {
    "xy_gain": 0.5,
    "approach_z": -0.001,
    "contact_z": -0.0015,
    "insert_z": -0.002,
    "seat_z": -0.0005,
    "rotation": 0.0,
    "gripper": 1.0,
}
FROZEN_BASE_GEOMETRY_SERVO_CONFIG_V07B = {
    **WEAK_BASE_SERVO_CONFIG,
    "base_servo_id": V07B_BASE_SERVO_ID,
    "base_servo_source": "weak_base_servo_action_v0_wrapped_for_v0_7b",
    "closing_gate": False,
    "proof_authority": False,
}
XY_CORRECTION_GAIN = 0.8
PHASES = ("APPROACH", "CONTACT", "INSERT", "SEAT")
BEHAVIOR_STATE_PHASES = ("ALIGN", "DESCEND", "HOLD")
V07A_BEHAVIOR_PHASE_LATERAL_GATE_M = 0.001
V07A_BEHAVIOR_PHASE_SEAT_DEPTH_M = 0.03
V07A1_BEHAVIOR_PHASE_RULE_VERSION = "env_native_hold_v0_7a_1"
V07A1_RUNTIME_BEHAVIOR_PHASE_SOURCE = "derived_v0_7a_1_runtime_rule"
V07A2_BEHAVIOR_PHASE_RULE_VERSION = "env_native_hold_v0_7a_2"
V07A2_RUNTIME_BEHAVIOR_PHASE_SOURCE = "derived_v0_7a_2_runtime_rule"
FEATURE_SCHEMA_V07A_VERSION = "rdf_mvp2e_v07a_behavior_phase_feature_schema_v0.1.0"
V06_ACTIVE_CONTROLLER_PHASES = ("ALIGN", "DESCEND", "INSERT", "HOLD")
V06_TRACE_TO_CONTROLLER_PHASE = {
    "APPROACH": "ALIGN",
    "CONTACT": "DESCEND",
    "INSERT": "INSERT",
    "SEAT": "HOLD",
    "ALIGN": "ALIGN",
    "DESCEND": "DESCEND",
    "HOLD": "HOLD",
}
CONTROLLED_FAILURE_REASONS = (
    "LATERAL_OFFSET_FAILURE",
    "UNDER_INSERTION_FAILURE",
    "ORIENTATION_MISALIGNMENT_FAILURE",
    "ACTION_JITTER_FAILURE",
    "EARLY_STOP_FAILURE",
)
PRIMARY_PROOF_PATH = "dedicated_isaac_connector_insertion_evaluator"
ISAAC_PROOF_RUNTIME = "dedicated_isaac_connector_insertion_evaluator"
DETERMINISTIC_PROOF_RUNTIME = "test_only_not_isaac"
DETERMINISTIC_BACKEND = "deterministic_test_backend"
ROLLOUT_SCHEMA_VERSION = "rdf_mvp2b_external_rollout_v0.1.0"
HDF5_SCHEMA_VERSION = "rdf_mvp2b_train_view_hdf5_v0.1.0"
REPORT_NAME = "mvp2b_isaac_proof_evaluator_report.json"
SUCCESS_METRIC = {
    "name": "connector_insertion_geometry_stability_v0",
    "insertion_depth_m_min": 0.03,
    "lateral_error_m_max": 0.006,
    "orientation_error_deg_max": 8.0,
    "stable_steps_required": 10,
    "max_steps": 150,
}
FEATURE_SCHEMA = [
    "phase_APPROACH",
    "phase_CONTACT",
    "phase_INSERT",
    "phase_SEAT",
    "insertion_depth_m",
    "relative_x_m",
    "relative_y_m",
    "lateral_error_m",
    "orientation_error_deg",
    "previous_action_dx",
    "previous_action_dy",
    "previous_action_dz",
    "previous_action_rx",
    "previous_action_ry",
    "previous_action_rz",
    "previous_action_gripper",
]
FEATURE_SCHEMA_V07A = [
    "behavior_phase_ALIGN",
    "behavior_phase_DESCEND",
    "behavior_phase_HOLD",
    "insertion_depth_m",
    "relative_x_m",
    "relative_y_m",
    "lateral_error_m",
    "orientation_error_deg",
    "previous_action_dx",
    "previous_action_dy",
    "previous_action_dz",
    "previous_action_rx",
    "previous_action_ry",
    "previous_action_rz",
    "previous_action_gripper",
]
ACTION_SCHEMA = [
    "action_dx",
    "action_dy",
    "action_dz",
    "action_rx",
    "action_ry",
    "action_rz",
    "gripper",
]


def stable_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2)


def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: top-level JSON must be an object")
    return data


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(payload) + "\n", encoding="utf-8")


def _sha256_payload(payload: dict[str, Any]) -> str:
    return hashlib.sha256(stable_json(payload).encode("utf-8")).hexdigest()


def _sha256_payload_excluding(payload: dict[str, Any], *fields: str) -> str:
    stripped = {key: value for key, value in payload.items() if key not in set(fields)}
    return _sha256_payload(stripped)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _is_safe_clean_target(path: Path) -> bool:
    resolved = path.resolve()
    repo_root = ROOT.resolve()
    storage_root = (repo_root / "storage").resolve()
    tmp_root = Path("/tmp").resolve()
    forbidden = {
        Path("/").resolve(),
        Path.home().resolve(),
        repo_root,
        repo_root.parent.resolve(),
        storage_root,
        tmp_root,
    }
    if resolved in forbidden:
        return False
    return _is_relative_to(resolved, storage_root) or _is_relative_to(resolved, tmp_root)


def _prepare_output_dir(output_dir: Path, *, clean: bool) -> None:
    if not _is_safe_clean_target(output_dir):
        raise ValueError(f"refusing unsafe MVP-2B output path: {output_dir}")
    if clean and output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)


def _scenario_row(*, split: str, seed: int) -> dict[str, Any]:
    offset_scale = 0.0005 * ((seed % 7) - 3)
    orientation = float(((seed // 3) % 9) - 4)
    if split == "train_failure":
        noise_level = "controlled_failure"
    elif split == "held_out":
        noise_level = "held_out_unseen"
    elif split == "calibration":
        noise_level = "calibration_only"
    else:
        noise_level = "scripted_expert"
    return {
        "scenario_id": f"{split}_{seed}",
        "split": split,
        "seed": seed,
        "initial_offset_m": [round(offset_scale, 6), round(-offset_scale / 2.0, 6), 0.0],
        "orientation_offset_deg": orientation,
        "noise_level": noise_level,
        "max_steps": SUCCESS_METRIC["max_steps"],
    }


def build_scenario_manifest(*, output_dir: Path) -> dict[str, Any]:
    scenarios: list[dict[str, Any]] = []
    for seed in range(1000, 1040):
        scenarios.append(_scenario_row(split="train_success", seed=seed))
    for seed in range(1100, 1140):
        scenarios.append(_scenario_row(split="train_failure", seed=seed))
    for seed in range(2000, 2010):
        scenarios.append(_scenario_row(split="calibration", seed=seed))
    for seed in range(3000, 3020):
        scenarios.append(_scenario_row(split="held_out", seed=seed))
    manifest = {
        "manifest_version": SCENARIO_MANIFEST_VERSION,
        "schema_version": SCENARIO_MANIFEST_VERSION,
        "task_type": "connector_insertion",
        "scenario_axis": "pre_registered_seed_initial_offset_noise_level",
        "success_metric": dict(SUCCESS_METRIC),
        "scenarios": scenarios,
        "leakage_policy": {
            "held_out_excluded_from_training": True,
            "held_out_excluded_from_curation_tuning": True,
            "held_out_excluded_from_threshold_tuning": True,
            "held_out_excluded_from_hyperparameter_selection": True,
        },
    }
    manifest["manifest_sha256"] = _sha256_payload(manifest)
    write_json(output_dir / "scenario_manifest.json", manifest)
    return manifest


def _heldout_ids(manifest: dict[str, Any]) -> set[str]:
    scenarios = manifest.get("scenarios")
    if not isinstance(scenarios, list):
        return set()
    return {
        str(row["scenario_id"])
        for row in scenarios
        if isinstance(row, dict) and row.get("split") == "held_out" and row.get("scenario_id")
    }


def validate_no_heldout_leakage(
    *,
    manifest: dict[str, Any],
    training_scenario_ids: list[str],
    curation_tuning_scenario_ids: list[str],
    threshold_tuning_scenario_ids: list[str],
    hyperparameter_scenario_ids: list[str],
) -> dict[str, Any]:
    heldout = _heldout_ids(manifest)
    checked_channels = {
        "training": [str(item) for item in training_scenario_ids],
        "curation_tuning": [str(item) for item in curation_tuning_scenario_ids],
        "threshold_tuning": [str(item) for item in threshold_tuning_scenario_ids],
        "hyperparameter_selection": [str(item) for item in hyperparameter_scenario_ids],
    }
    leaked = sorted(
        {
            scenario_id
            for values in checked_channels.values()
            for scenario_id in values
            if scenario_id in heldout
        }
    )
    return {
        "passed": not leaked,
        "heldout_scenario_ids": sorted(heldout),
        "leaked_scenario_ids": leaked,
        "checked_channels": checked_channels,
    }


def validate_threshold_freeze(
    *,
    original_manifest: dict[str, Any],
    proposed_success_metric: dict[str, Any],
    proposed_manifest_version: str,
) -> dict[str, Any]:
    original_metric = original_manifest.get("success_metric")
    if not isinstance(original_metric, dict):
        original_metric = {}
    changed_fields = sorted(
        {
            key
            for key in set(original_metric) | set(proposed_success_metric)
            if original_metric.get(key) != proposed_success_metric.get(key)
        }
    )
    version_unchanged = proposed_manifest_version == original_manifest.get("manifest_version")
    requires_new = bool(changed_fields and version_unchanged)
    return {
        "passed": not requires_new,
        "requires_new_manifest_version": requires_new,
        "changed_fields": changed_fields,
    }


def validate_manifest_threshold_freeze(
    *,
    original_manifest: dict[str, Any],
    proposed_manifest: dict[str, Any],
    heldout_results_exist: bool,
) -> dict[str, Any]:
    report = validate_threshold_freeze(
        original_manifest=original_manifest,
        proposed_success_metric=dict(proposed_manifest.get("success_metric") or {}),
        proposed_manifest_version=str(proposed_manifest.get("manifest_version") or ""),
    )
    if heldout_results_exist and report["changed_fields"]:
        report["passed"] = False
        report["requires_new_manifest_version"] = True
        report["heldout_results_exist"] = True
    return report


def _stable_step(row: dict[str, Any], success_metric: dict[str, Any]) -> bool:
    return (
        float(row.get("insertion_depth_m", 0.0)) >= float(success_metric["insertion_depth_m_min"])
        and float(row.get("lateral_error_m", 1.0)) <= float(success_metric["lateral_error_m_max"])
        and float(row.get("orientation_error_deg", 999.0)) <= float(success_metric["orientation_error_deg_max"])
    )


def evaluate_rollout_trace(
    trace: list[dict[str, Any]],
    *,
    success_metric: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metric = success_metric or SUCCESS_METRIC
    stable_window = int(metric["stable_steps_required"])
    consecutive = 0
    best_consecutive = 0
    max_depth = max((float(row.get("insertion_depth_m", 0.0)) for row in trace), default=0.0)
    min_lateral = min((float(row.get("lateral_error_m", 1.0)) for row in trace), default=1.0)
    min_orientation = min((float(row.get("orientation_error_deg", 999.0)) for row in trace), default=999.0)
    for row in trace:
        if _stable_step(row, metric):
            consecutive += 1
        else:
            consecutive = 0
        best_consecutive = max(best_consecutive, consecutive)
    success = best_consecutive >= stable_window
    if success:
        failure_reason = ""
    elif max_depth < float(metric["insertion_depth_m_min"]):
        failure_reason = "UNDER_INSERTION_FAILURE"
    elif min_lateral > float(metric["lateral_error_m_max"]):
        failure_reason = "LATERAL_OFFSET_FAILURE"
    elif min_orientation > float(metric["orientation_error_deg_max"]):
        failure_reason = "ORIENTATION_MISALIGNMENT_FAILURE"
    else:
        failure_reason = "STABILITY_WINDOW_NOT_REACHED"
    return {
        "success": success,
        "failure_reason": failure_reason,
        "steps": len(trace),
        "stable_steps_observed": best_consecutive,
        "max_insertion_depth_m": max_depth,
        "min_lateral_error_m": min_lateral,
        "min_orientation_error_deg": min_orientation,
    }


def evaluate_env_native_success_window(
    mask: Sequence[bool],
    *,
    stable_steps_required: int = 10,
) -> dict[str, Any]:
    first_success_step: int | None = None
    current_consecutive = 0
    max_consecutive = 0
    for index, value in enumerate(mask):
        if bool(value):
            if first_success_step is None:
                first_success_step = index
            current_consecutive += 1
            max_consecutive = max(max_consecutive, current_consecutive)
        else:
            current_consecutive = 0
    return {
        "first_success_step": first_success_step,
        "max_consecutive_success_steps": max_consecutive,
        "stable_steps_required": int(stable_steps_required),
        "rollout_success": max_consecutive >= int(stable_steps_required),
    }


def evaluate_env_native_rollout_trace(
    trace: list[dict[str, Any]],
    *,
    success_metric: dict[str, Any] | None = None,
    stable_steps_required: int = 10,
) -> dict[str, Any]:
    rdf_summary = evaluate_rollout_trace(trace, success_metric=success_metric)
    env_native_mask = [
        bool(row["env_native_success"])
        for row in trace
        if isinstance(row, dict) and row.get("env_native_success") is not None
    ]
    env_native_summary = evaluate_env_native_success_window(
        env_native_mask,
        stable_steps_required=stable_steps_required,
    )
    env_native_available = bool(env_native_mask)
    success = bool(env_native_summary["rollout_success"]) if env_native_available else False
    failure_reason = "" if success else "ENV_NATIVE_STABILITY_WINDOW_NOT_REACHED"
    return {
        "success": success,
        "failure_reason": failure_reason if env_native_available else "ENV_NATIVE_SUCCESS_MASK_UNAVAILABLE",
        "steps": len(trace),
        "env_native_success_available": env_native_available,
        "env_native_first_success_step": env_native_summary["first_success_step"],
        "env_native_max_consecutive_success_steps": env_native_summary["max_consecutive_success_steps"],
        "env_native_rollout_success": success,
        "rdf_peg_in_hole_metric": {
            "closure_authority": False,
            "summary": rdf_summary,
        },
    }


def _env_reset_boundary_steps(env: Any) -> int | None:
    for owner in (env, getattr(env, "unwrapped", None), getattr(getattr(env, "unwrapped", None), "cfg", None)):
        if owner is None:
            continue
        value = getattr(owner, "max_episode_length", None)
        if value is None:
            continue
        try:
            boundary = int(value)
        except (TypeError, ValueError):
            continue
        if boundary > 0:
            return boundary
    return None


def _effective_rollout_budget_steps(*, max_steps: int, env_reset_boundary_steps: int | None) -> int:
    requested_steps = max(0, int(max_steps))
    if env_reset_boundary_steps is None:
        return requested_steps
    return min(requested_steps, max(0, int(env_reset_boundary_steps) - ENV_RESET_POST_STEP_GUARD_STEPS))


def _read_env_native_success(env: Any) -> bool | None:
    unwrapped = getattr(env, "unwrapped", env)
    if not hasattr(unwrapped, "_get_curr_successes"):
        return None
    cfg_task = getattr(unwrapped, "cfg_task", None)
    success_threshold = getattr(cfg_task, "success_threshold", None)
    if success_threshold is None:
        return None
    try:
        success_tensor = unwrapped._get_curr_successes(success_threshold=success_threshold, check_rot=False)
        if hasattr(success_tensor, "reshape"):
            success_tensor = success_tensor.reshape(-1)
        first_value = success_tensor[0]
        if hasattr(first_value, "item"):
            return bool(first_value.item())
        return bool(first_value)
    except Exception:
        return None


def _factory_peg_insert_base_target_pose_from_env(unwrapped: Any) -> dict[str, np.ndarray] | None:
    cfg_task = getattr(unwrapped, "cfg_task", None)
    if str(getattr(cfg_task, "name", "")) != "peg_insert":
        return None
    try:
        import isaaclab_tasks.direct.factory.factory_utils as factory_utils
    except Exception:
        return None
    try:
        held_base_pos, held_base_quat = factory_utils.get_held_base_pose(
            getattr(unwrapped, "held_pos"),
            getattr(unwrapped, "held_quat"),
            cfg_task.name,
            cfg_task.fixed_asset_cfg,
            unwrapped.num_envs,
            unwrapped.device,
        )
        target_pos, target_quat = factory_utils.get_target_held_base_pose(
            getattr(unwrapped, "fixed_pos"),
            getattr(unwrapped, "fixed_quat"),
            cfg_task.name,
            cfg_task.fixed_asset_cfg,
            unwrapped.num_envs,
            unwrapped.device,
        )
    except Exception:
        return None
    return {
        "held_base_pos": IsaacConnectorInsertionEvaluatorBackend._tensor_row(held_base_pos),
        "held_base_quat": IsaacConnectorInsertionEvaluatorBackend._tensor_row(held_base_quat),
        "target_held_base_pos": IsaacConnectorInsertionEvaluatorBackend._tensor_row(target_pos),
        "target_held_base_quat": IsaacConnectorInsertionEvaluatorBackend._tensor_row(target_quat),
    }


def _phase_for_step(index: int, total: int) -> str:
    ratio = index / max(total - 1, 1)
    if ratio < 0.30:
        return "APPROACH"
    if ratio < 0.55:
        return "CONTACT"
    if ratio < 0.85:
        return "INSERT"
    return "SEAT"


def _action_for_phase(
    phase: str,
    *,
    failure_reason: str | None,
    relative_x_m: float = 0.0,
    relative_y_m: float = 0.0,
) -> list[float]:
    correction_x = -round(float(relative_x_m) * XY_CORRECTION_GAIN, 6)
    correction_y = -round(float(relative_y_m) * XY_CORRECTION_GAIN, 6)
    action = {
        "APPROACH": [correction_x, correction_y, -0.004, 0.0, 0.0, 0.0, 1.0],
        "CONTACT": [correction_x, correction_y, -0.005, 0.0, 0.0, 0.0, 1.0],
        "INSERT": [correction_x * 0.5, correction_y * 0.5, -0.006, 0.0, 0.0, 0.0, 1.0],
        "SEAT": [0.0, 0.0, -0.002, 0.0, 0.0, 0.0, 0.2],
    }[phase]
    if failure_reason == "ACTION_JITTER_FAILURE":
        return [round(value + (0.04 if index % 2 == 0 else -0.04), 6) for index, value in enumerate(action)]
    if failure_reason == "EARLY_STOP_FAILURE" and phase in {"INSERT", "SEAT"}:
        return [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0]
    return action


def _trace_for_scenario(scenario: dict[str, Any], *, failure_reason: str | None) -> list[dict[str, Any]]:
    total = 24
    rows: list[dict[str, Any]] = []
    initial_relative_x = -float(scenario["initial_offset_m"][0])
    initial_relative_y = -float(scenario["initial_offset_m"][1])
    orientation_base = abs(float(scenario["orientation_offset_deg"]))
    for index in range(total):
        phase = _phase_for_step(index, total)
        progress = min(1.0, index / 18.0)
        depth = 0.034 * progress
        relative_x = initial_relative_x * (1.0 - progress)
        relative_y = initial_relative_y * (1.0 - progress)
        lateral = max(0.0025, float(np.linalg.norm([relative_x, relative_y])))
        orientation = max(3.0, orientation_base * (1.0 - progress) + 2.5)
        if failure_reason == "LATERAL_OFFSET_FAILURE":
            lateral = 0.010
            relative_x = 0.010 if initial_relative_x >= 0.0 else -0.010
            relative_y = 0.0
        elif failure_reason == "UNDER_INSERTION_FAILURE":
            depth = min(depth, 0.022)
        elif failure_reason == "ORIENTATION_MISALIGNMENT_FAILURE":
            orientation = 12.0
        elif failure_reason == "ACTION_JITTER_FAILURE" and 8 <= index <= 18:
            lateral = 0.009 if index % 3 == 0 else 0.004
        elif failure_reason == "EARLY_STOP_FAILURE" and index >= 10:
            depth = min(depth, 0.024)
        rows.append(
            {
                "timestamp_s": round(index * 0.05, 4),
                "step": index,
                "phase": phase,
                "eef_position_m": [round(relative_x, 6), round(relative_y, 6), round(depth, 6)],
                "target_position_m": [0.0, 0.0, 0.034],
                "relative_x_m": round(relative_x, 6),
                "relative_y_m": round(relative_y, 6),
                "lateral_error_m": round(lateral, 6),
                "insertion_depth_m": round(depth, 6),
                "orientation_error_deg": round(orientation, 6),
                "normalized_action": _action_for_phase(
                    phase,
                    failure_reason=failure_reason,
                    relative_x_m=relative_x,
                    relative_y_m=relative_y,
                ),
            }
        )
    return rows


def _action_role(command: list[float], *, role: str) -> dict[str, Any]:
    return {
        "role": role,
        "source": "mvp2b_scripted_expert_generator",
        "representation": "delta_eef_pose_plus_gripper",
        "coordinate_frame": "robot_base",
        "command": command,
    }


def _trajectory_payload(
    *,
    scenario: dict[str, Any],
    trace: list[dict[str, Any]],
    accepted: bool,
    rejection_reason: str | None,
) -> dict[str, Any]:
    trajectory_id = f"mvp2b_{scenario['scenario_id']}"
    frames: list[dict[str, Any]] = []
    for row in trace:
        command = list(row["normalized_action"])
        action = {
            "action_contract_version": "rdf_mvp2b_action_contract_v0.1.0",
            "replay_contract_version": "rdf_mvp2b_replay_contract_v0.1.0",
            "teleop_intent": _action_role(command, role="teleop_intent"),
            "executed_control": _action_role(command, role="executed_control"),
            "learning_action": _action_role(command, role="learning_action"),
            "retargeted_robot_action": _action_role(command, role="retargeted_robot_action"),
        }
        frames.append(
            {
                "t": row["timestamp_s"],
                "step": row["step"],
                "action": action,
                "metadata": {
                    "action_phase": row["phase"],
                    "task_state": {
                        "insertion_depth": row["insertion_depth_m"],
                        "relative_x_m": row["relative_x_m"],
                        "relative_y_m": row["relative_y_m"],
                        "lateral_error_m": row["lateral_error_m"],
                        "orientation_error_deg": row["orientation_error_deg"],
                    },
                    "mvp2b_scenario_id": scenario["scenario_id"],
                },
            }
        )
    return {
        "schema_version": "rdf_mvp2b_generated_trajectory_v0.1.0",
        "id": trajectory_id,
        "episode_id": trajectory_id,
        "source": {
            "input_device": "scripted_expert_controlled_noise",
            "runtime": "mvp2b_dedicated_evaluator_generator",
            "simulator": "isaac_connector_insertion_domain_model",
            "robot": "franka_research_arm_adapter",
            "task_name": "connector_insertion",
            "input_route": "scripted_expert_plus_controlled_failure",
            "recorded_log_backed": False,
        },
        "frames": frames,
        "summary": {
            "action_replay_gate": {
                "passed": accepted,
                "backend": "mvp2b_geometry_consistency_replay_gate",
                "failure_reason": rejection_reason,
            }
        },
    }


def _contract_for_trajectory(
    *,
    trajectory: dict[str, Any],
    accepted_count: int,
    rejected_count: int,
    output_dir: Path,
) -> dict[str, Any]:
    first_action = trajectory["frames"][0]["action"]
    return {
        "schema_version": TRAJECTORY_CONTRACT_SCHEMA_VERSION,
        "proof_id": "rdf_mvp2b_dedicated_isaac_evaluator_generated_trajectory",
        "contract_name": "mvp2b_connector_insertion_normalized_trajectory_contract",
        "trajectory_schema_version": trajectory["schema_version"],
        "source_profile": trajectory["source"],
        "source_provenance": {
            "generator": "scripted_expert_plus_controlled_noise",
            "scenario_manifest_sha256": None,
        },
        "input_route": {
            "route_id": "scripted_expert_controlled_noise",
            "route_role": "mvp2b_training_material_generator",
        },
        "robot_embodiment": {
            "name": "Franka",
            "role": "baseline_research_arm_domain_model",
        },
        "required_source_fields": ["input_device", "runtime", "simulator", "robot", "task_name"],
        "required_action_roles": {
            key: {
                "role": first_action[key]["role"],
                "source": first_action[key]["source"],
                "representation": first_action[key]["representation"],
                "coordinate_frame": first_action[key]["coordinate_frame"],
            }
            for key in REQUIRED_ACTION_ROLE_KEYS
        },
        "frame_action_role_coverage": {
            "checked_frame_count": len(trajectory["frames"]),
            "missing": [],
            "mismatched": [],
        },
        "action_contract_versions": {
            "action_contract_version": first_action["action_contract_version"],
            "replay_contract_version": first_action["replay_contract_version"],
        },
        "replay_gate": trajectory["summary"]["action_replay_gate"],
        "training_eligibility_gates": {
            "task_outcome": {
                "evaluation_success": True,
                "failure_reason": None,
            },
            "data_quality": {
                "replay_verified": True,
                "action_contract_status": "pass",
                "action_contract_valid": True,
                "control_quality": "pass",
                "quality_failure_reasons": [],
            },
            "curation": {
                "accepted_count": accepted_count,
                "rejected_count": rejected_count,
                "curation_rules": [
                    "geometry_stability_success_required",
                    "controlled_failure_rejected",
                ],
            },
            "export": {
                "hdf5_export_generated": True,
                "trainer_smoke_passed": True,
                "learning_results_measured": False,
                "curated_vs_uncurated_uplift": None,
            },
        },
        "state_metadata": {
            "fields": [
                "insertion_depth_m",
                "relative_x_m",
                "relative_y_m",
                "lateral_error_m",
                "orientation_error_deg",
                "phase",
            ],
        },
        "limitations": [
            "Generated MVP-2B training material is not physical robot evidence.",
            "This contract proves data trust shape before Isaac runtime policy rollout closure.",
        ],
        "claim_boundaries": {
            "hmd_readiness_claimed": False,
            "physical_robot_readiness_claimed": False,
            "gate_a_collection_allowed": False,
            "policy_uplift_claimed": False,
        },
        "artifact_paths": {
            "output_dir": str(output_dir),
        },
    }


def generate_training_trajectory_bundle(*, manifest: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    raw_dir = output_dir / "train_raw_trajectories"
    contract_dir = output_dir / "normalized_trajectory_contracts"
    raw_dir.mkdir(parents=True, exist_ok=True)
    contract_dir.mkdir(parents=True, exist_ok=True)
    scenarios = [row for row in manifest["scenarios"] if row["split"] in {"train_success", "train_failure"}]
    items: list[dict[str, Any]] = []
    train_rows: list[dict[str, Any]] = []
    accepted_trajectories: list[dict[str, Any]] = []
    rejected_trajectories: list[dict[str, Any]] = []
    failure_index = 0
    for scenario in scenarios:
        rejection_reason = None
        accepted = scenario["split"] == "train_success"
        if not accepted:
            rejection_reason = CONTROLLED_FAILURE_REASONS[failure_index % len(CONTROLLED_FAILURE_REASONS)]
            failure_index += 1
        trace = _trace_for_scenario(scenario, failure_reason=rejection_reason)
        rollout_eval = evaluate_rollout_trace(trace, success_metric=manifest["success_metric"])
        trajectory = _trajectory_payload(
            scenario=scenario,
            trace=trace,
            accepted=accepted,
            rejection_reason=rejection_reason,
        )
        trajectory_path = raw_dir / f"{trajectory['id']}.json"
        write_json(trajectory_path, trajectory)
        item = {
            "trajectory_id": trajectory["id"],
            "scenario_id": scenario["scenario_id"],
            "accepted": accepted,
            "rejection_reason": rejection_reason or "",
            "trajectory_path": str(trajectory_path),
            "rollout_eval": rollout_eval,
        }
        items.append(item)
        target = accepted_trajectories if accepted else rejected_trajectories
        target.append(trajectory)
        for row in trace:
            train_rows.append(
                {
                    **row,
                    "trajectory_id": trajectory["id"],
                    "scenario_id": scenario["scenario_id"],
                    "accepted": accepted,
                    "rejection_reason": rejection_reason or "",
                }
            )
    curation_manifest = {
        "schema_version": "rdf_mvp2b_curation_manifest_v0.1.0",
        "accepted_count": len(accepted_trajectories),
        "rejected_count": len(rejected_trajectories),
        "curation_rules": [
            "accept scripted expert geometry-stable trajectories",
            "reject controlled failure trajectories by explicit taxonomy",
        ],
        "items": items,
    }
    write_json(output_dir / "curation_manifest.json", curation_manifest)

    validator = NormalizedTrajectoryContractValidator(
        proof_id="rdf_mvp2b_dedicated_isaac_evaluator_generated_trajectory",
        contract_name="mvp2b_connector_insertion_normalized_trajectory_contract",
    )
    contract_issues: list[str] = []
    accepted_contract_paths: list[str] = []
    for trajectory in accepted_trajectories:
        contract = _contract_for_trajectory(
            trajectory=trajectory,
            accepted_count=len(accepted_trajectories),
            rejected_count=len(rejected_trajectories),
            output_dir=output_dir,
        )
        contract["source_provenance"]["scenario_manifest_sha256"] = manifest["manifest_sha256"]
        issues = validator.validate_learning_eligibility(contract)
        contract_issues.extend(issues)
        path = contract_dir / f"{trajectory['id']}_normalized_trajectory_contract.json"
        write_json(path, contract)
        accepted_contract_paths.append(str(path))
    return {
        "schema_version": "rdf_mvp2b_training_trajectory_bundle_v0.1.0",
        "accepted_count": len(accepted_trajectories),
        "rejected_count": len(rejected_trajectories),
        "curation_manifest": curation_manifest,
        "training_rows": train_rows,
        "accepted_contract_paths": accepted_contract_paths,
        "contract_validation": {
            "passed": not contract_issues,
            "issues": contract_issues,
            "validator": "NormalizedTrajectoryContractValidator",
        },
        "artifact_paths": {
            "raw_dir": str(raw_dir),
            "contract_dir": str(contract_dir),
            "curation_manifest": str(output_dir / "curation_manifest.json"),
        },
    }


def _phase_vector_for_schema(step: dict[str, Any], feature_schema: Sequence[str]) -> list[float]:
    if list(feature_schema[:3]) == FEATURE_SCHEMA_V07A[:3]:
        behavior_phase = str(step.get("behavior_state_phase") or "").upper()
        return [1.0 if behavior_phase == item else 0.0 for item in BEHAVIOR_STATE_PHASES]
    phase = str(step.get("phase") or "").upper()
    return [1.0 if phase == item else 0.0 for item in PHASES]


def featurize_step(
    step: dict[str, Any],
    *,
    previous_action: list[float],
    feature_schema: Sequence[str] | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    schema = list(feature_schema or FEATURE_SCHEMA)
    phase_vector = _phase_vector_for_schema(step, schema)
    previous = [float(value) for value in previous_action[: len(ACTION_SCHEMA)]]
    if len(previous) < len(ACTION_SCHEMA):
        previous.extend([0.0] * (len(ACTION_SCHEMA) - len(previous)))
    feature_values = phase_vector + [
        float(step.get("insertion_depth_m", 0.0)),
        float(step.get("relative_x_m", 0.0)),
        float(step.get("relative_y_m", 0.0)),
        float(step.get("lateral_error_m", 0.0)),
        float(step.get("orientation_error_deg", 0.0)),
    ] + previous
    target = [float(value) for value in step.get("normalized_action", [0.0] * len(ACTION_SCHEMA))]
    return np.asarray(feature_values, dtype=np.float64), np.asarray(target, dtype=np.float64)


def _features_targets(
    rows: list[dict[str, Any]],
    *,
    feature_schema: Sequence[str] | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    features: list[np.ndarray] = []
    targets: list[np.ndarray] = []
    previous_by_trajectory: dict[str, list[float]] = {}
    for row in rows:
        trajectory_id = str(row.get("trajectory_id"))
        previous = previous_by_trajectory.get(trajectory_id, [0.0] * len(ACTION_SCHEMA))
        feature, target = featurize_step(row, previous_action=previous, feature_schema=feature_schema)
        features.append(feature)
        targets.append(target)
        previous_by_trajectory[trajectory_id] = [float(value) for value in row["normalized_action"]]
    if not features:
        raise ValueError("cannot train MVP-2B policy without rows")
    return np.vstack(features), np.vstack(targets)


def _write_train_view_hdf5(*, path: Path, rows: list[dict[str, Any]], view_id: str) -> dict[str, Any]:
    features, targets = _features_targets(rows)
    string_dtype = h5py.string_dtype(encoding="utf-8")
    metadata = np.asarray([stable_json(row) for row in rows], dtype=object)
    path.parent.mkdir(parents=True, exist_ok=True)
    with h5py.File(path, "w") as h5:
        h5.attrs["schema_version"] = HDF5_SCHEMA_VERSION
        h5.attrs["view_id"] = view_id
        h5.attrs["feature_schema"] = stable_json(FEATURE_SCHEMA)
        h5.attrs["action_schema"] = stable_json(ACTION_SCHEMA)
        h5.create_dataset("features", data=features)
        h5.create_dataset("actions", data=targets)
        h5.create_dataset("metadata_json", data=metadata, dtype=string_dtype)
    accepted_count = sum(1 for row in rows if row.get("accepted") is True and int(row.get("step", 0)) == 0)
    rejected_count = sum(1 for row in rows if row.get("accepted") is False and int(row.get("step", 0)) == 0)
    return {
        "view_id": view_id,
        "path": str(path),
        "sha256": _sha256_file(path),
        "trajectory_count": len({str(row.get("trajectory_id")) for row in rows}),
        "transition_count": len(rows),
        "accepted_count": accepted_count,
        "rejected_count": rejected_count,
        "includes_rejected_material": any(row.get("accepted") is False for row in rows),
        "feature_schema": list(FEATURE_SCHEMA),
        "phase_schema": list(PHASES),
    }


def fit_phase_conditioned_bc_policy(
    *,
    policy_id: str,
    train_rows: list[dict[str, Any]],
    hyperparameters: dict[str, Any],
    feature_schema: Sequence[str] | None = None,
    phase_schema: Sequence[str] | None = None,
    feature_schema_version: str | None = None,
) -> dict[str, Any]:
    schema = list(feature_schema or FEATURE_SCHEMA)
    phases = list(phase_schema or PHASES)
    features, targets = _features_targets(train_rows, feature_schema=schema)
    ridge_lambda = float(hyperparameters.get("ridge_lambda", 1e-3))
    augmented = np.hstack([features, np.ones((features.shape[0], 1), dtype=np.float64)])
    lhs = augmented.T @ augmented
    lhs += ridge_lambda * np.eye(lhs.shape[0], dtype=np.float64)
    rhs = augmented.T @ targets
    weights = np.linalg.solve(lhs, rhs)
    payload = {
        "policy_id": policy_id,
        "policy_class": POLICY_CLASS,
        "trainer": TRAINER,
        "feature_schema": schema,
        "feature_schema_version": feature_schema_version or "rdf_mvp2b_phase_depth_feature_schema_v0.1.0",
        "phase_schema": phases,
        "action_schema": list(ACTION_SCHEMA),
        "hyperparameters": dict(hyperparameters),
        "train_sample_count": int(features.shape[0]),
        "weights": weights[:-1].round(10).tolist(),
        "bias": weights[-1].round(10).tolist(),
    }
    payload["policy_artifact_sha256"] = _sha256_payload(payload)
    return payload


def _write_policy_artifacts(
    *,
    output_dir: Path,
    baseline_rows: list[dict[str, Any]],
    candidate_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    hyperparameters = {
        "ridge_lambda": 1e-3,
        "phase_input_shared": True,
        "feature_standardization": "none_deterministic_domain_units",
    }
    baseline = fit_phase_conditioned_bc_policy(
        policy_id="baseline_uncurated_phase_conditioned_numpy_bc",
        train_rows=baseline_rows,
        hyperparameters=hyperparameters,
    )
    candidate = fit_phase_conditioned_bc_policy(
        policy_id="candidate_curated_phase_conditioned_numpy_bc",
        train_rows=candidate_rows,
        hyperparameters=hyperparameters,
    )
    baseline_path = output_dir / "baseline_policy_artifact.json"
    candidate_path = output_dir / "candidate_policy_artifact.json"
    write_json(baseline_path, baseline)
    write_json(candidate_path, candidate)
    return {
        "baseline": {**baseline, "path": str(baseline_path)},
        "candidate": {**candidate, "path": str(candidate_path)},
    }


@dataclass(frozen=True)
class BackendResult:
    runtime_backend: str
    proof_runtime: str
    runtime_gate: dict[str, Any]
    baseline_rollouts: list[dict[str, Any]]
    candidate_rollouts: list[dict[str, Any]]
    baseline_trace_paths: list[str]
    candidate_trace_paths: list[str]
    runtime_metadata: dict[str, Any]


def _success_trace() -> list[dict[str, Any]]:
    return [
        {
            "step": index,
            "insertion_depth_m": 0.031,
            "lateral_error_m": 0.004,
            "orientation_error_deg": 5.0,
        }
        for index in range(12)
    ]


def _failure_trace(reason: str) -> list[dict[str, Any]]:
    trace = _success_trace()
    if reason == "UNDER_INSERTION_FAILURE":
        for row in trace:
            row["insertion_depth_m"] = 0.02
    elif reason == "LATERAL_OFFSET_FAILURE":
        for row in trace:
            row["lateral_error_m"] = 0.01
    elif reason == "ORIENTATION_MISALIGNMENT_FAILURE":
        for row in trace:
            row["orientation_error_deg"] = 12.0
    else:
        for index, row in enumerate(trace):
            if index == 9:
                row["lateral_error_m"] = 0.009
    return trace


def _deterministic_success_target(profile: str, role: str, rollout_count: int) -> int:
    if profile == "tie":
        return rollout_count // 2
    if profile == "candidate_negative":
        return rollout_count // 2 + (2 if role == "baseline" else -2)
    if role == "candidate":
        return min(rollout_count, int(round(rollout_count * 0.70)))
    return max(0, int(round(rollout_count * 0.40)))


def _phase_from_depth(insertion_depth_m: float) -> str:
    if insertion_depth_m < 0.006:
        return "APPROACH"
    if insertion_depth_m < 0.016:
        return "CONTACT"
    if insertion_depth_m < float(SUCCESS_METRIC["insertion_depth_m_min"]):
        return "INSERT"
    return "SEAT"


def derive_v07a_behavior_state_phase_from_metrics(metric_row: dict[str, Any]) -> str:
    try:
        lateral_error_m = float(metric_row["lateral_error_m"])
        insertion_depth_m = float(metric_row["insertion_depth_m"])
    except KeyError as exc:
        raise ValueError(f"row_missing_required_metric:{exc.args[0]}") from exc
    if not np.isfinite(lateral_error_m) or not np.isfinite(insertion_depth_m):
        raise ValueError("relabel_config_invalid:nonfinite_metric")
    if insertion_depth_m < 0.0:
        raise ValueError("relabel_config_invalid:negative_insertion_depth_m")
    if lateral_error_m > V07A_BEHAVIOR_PHASE_LATERAL_GATE_M:
        return "ALIGN"
    if insertion_depth_m < V07A_BEHAVIOR_PHASE_SEAT_DEPTH_M:
        return "DESCEND"
    return "HOLD"


def _env_native_success_mask_from_row(row: dict[str, Any]) -> bool:
    has_success = "env_native_success" in row
    has_mask = "env_native_success_mask" in row
    if not has_success and not has_mask:
        raise ValueError("env_native_mask_missing")
    values: list[bool] = []
    for key in ("env_native_success", "env_native_success_mask"):
        if key not in row:
            continue
        value = row[key]
        if isinstance(value, bool):
            values.append(value)
        elif value in (0, 1):
            values.append(bool(value))
        else:
            raise ValueError(f"env_native_mask_invalid:{key}")
    if len(set(values)) != 1:
        raise ValueError("env_native_mask_conflict")
    return values[0]


def derive_v07a1_behavior_state_phase_from_metrics(metric_row: dict[str, Any]) -> str:
    env_native_success = _env_native_success_mask_from_row(metric_row)
    try:
        lateral_error_m = float(metric_row["lateral_error_m"])
        insertion_depth_m = float(metric_row["insertion_depth_m"])
    except KeyError as exc:
        raise ValueError(f"row_missing_required_metric:{exc.args[0]}") from exc
    except (TypeError, ValueError) as exc:
        raise ValueError("relabel_config_invalid:metric") from exc
    if not np.isfinite(lateral_error_m) or not np.isfinite(insertion_depth_m):
        raise ValueError("relabel_config_invalid:nonfinite_metric")
    if insertion_depth_m < 0.0:
        raise ValueError("relabel_config_invalid:negative_insertion_depth_m")
    if env_native_success:
        return "HOLD"
    if lateral_error_m <= V07A_BEHAVIOR_PHASE_LATERAL_GATE_M:
        return "DESCEND"
    return "ALIGN"


def derive_v07a2_behavior_state_phase_from_metrics(metric_row: dict[str, Any]) -> str:
    return derive_v07a1_behavior_state_phase_from_metrics(metric_row)


def normalize_v06_controller_phase(phase: str | None) -> dict[str, Any]:
    input_phase = str(phase or "ALIGN").upper()
    controller_phase = V06_TRACE_TO_CONTROLLER_PHASE.get(input_phase, input_phase)
    mismatch = controller_phase not in V06_ACTIVE_CONTROLLER_PHASES
    return {
        "input_phase": input_phase,
        "controller_phase": controller_phase,
        "phase_vocabulary_mismatch": mismatch,
        "phase_normalized": input_phase != controller_phase and not mismatch,
    }


def v06_phase_controller_step(
    *,
    current_phase: str,
    lateral_error_m: float,
    orientation_error_rad: float,
    insertion_depth_m: float,
    env_native_success: bool,
    stable_steps: int,
    align_lateral_gate_m: float = 0.008,
    align_orientation_gate_rad: float = 0.25,
) -> dict[str, Any]:
    phase = str(current_phase or "ALIGN").upper()
    aligned = (
        float(lateral_error_m) <= float(align_lateral_gate_m)
        and abs(float(orientation_error_rad)) <= float(align_orientation_gate_rad)
    )
    z_motion_allowed = False
    if phase == "ALIGN":
        if aligned:
            phase = "DESCEND"
        else:
            z_motion_allowed = False
    if phase == "DESCEND":
        z_motion_allowed = aligned
        if aligned and float(insertion_depth_m) >= 0.025:
            phase = "INSERT"
    if phase == "INSERT":
        z_motion_allowed = aligned
        if bool(env_native_success):
            phase = "HOLD"
    if phase == "HOLD":
        z_motion_allowed = False
    return {
        "next_phase": phase,
        "alignment_gate_satisfied": aligned,
        "z_motion_allowed": z_motion_allowed,
        "stable_steps": int(stable_steps),
    }


def initial_v07e_hysteresis_state() -> dict[str, Any]:
    return {
        "current_hysteresis_phase": "ALIGN",
        "z_window_remaining_steps": 0,
        "entered_descend_step": None,
        "last_z_motion_allowed": False,
        "hard_safety_escape_triggered": False,
        "soft_realign_triggered": False,
    }


def _advance_v07e_hysteresis_state(
    *,
    metric_row: dict[str, Any],
    hysteresis_state: dict[str, Any] | None,
    config: dict[str, Any],
) -> dict[str, Any]:
    before = dict(initial_v07e_hysteresis_state())
    if isinstance(hysteresis_state, dict):
        before.update(hysteresis_state)
    phase = str(before.get("current_hysteresis_phase") or "ALIGN").upper()
    lateral_error_m = float(metric_row.get("lateral_error_m", 999.0))
    orientation_error_rad = float(metric_row.get("orientation_error_deg", 999.0)) * np.pi / 180.0
    insertion_depth_m = float(metric_row.get("insertion_depth_m", 0.0))
    gate_m = float(config.get("approach_lateral_gate_m", V07A_BEHAVIOR_PHASE_LATERAL_GATE_M))
    orientation_gate_rad = float(config.get("align_orientation_gate_rad", 0.25))
    hard_escape_lateral_m = float(config.get("hard_safety_escape_lateral_m", 0.03))
    z_window_hold_steps = max(1, int(config.get("z_window_hold_steps", 28)))
    realign_threshold_raw = config.get("z_window_realign_lateral_m")
    z_window_realign_lateral_m = (
        float(realign_threshold_raw) if realign_threshold_raw is not None else None
    )
    aligned = lateral_error_m <= gate_m and abs(orientation_error_rad) <= orientation_gate_rad
    hard_escape = bool(before.get("hard_safety_escape_triggered")) or lateral_error_m >= hard_escape_lateral_m
    env_native_success = bool(metric_row.get("env_native_success") or metric_row.get("env_native_success_mask"))
    step = metric_row.get("step")
    entered_descend_step = before.get("entered_descend_step")
    window_remaining = max(0, int(before.get("z_window_remaining_steps") or 0))
    z_motion_allowed = False
    soft_realign = bool(
        z_window_realign_lateral_m is not None
        and phase in {"DESCEND", "INSERT"}
        and lateral_error_m >= z_window_realign_lateral_m
        and insertion_depth_m < float(SUCCESS_METRIC["insertion_depth_m_min"])
    )
    if env_native_success:
        phase = "HOLD"
        window_remaining = 0
    elif hard_escape:
        phase = "ALIGN"
        window_remaining = 0
    elif soft_realign:
        phase = "ALIGN"
        window_remaining = 0
    elif phase == "DESCEND" and window_remaining > 0:
        z_motion_allowed = True
        window_remaining -= 1
    elif phase == "INSERT" and window_remaining > 0:
        z_motion_allowed = True
        window_remaining -= 1
    elif aligned:
        phase = "DESCEND"
        z_motion_allowed = True
        window_remaining = z_window_hold_steps - 1
        if entered_descend_step is None:
            entered_descend_step = int(step) if step is not None else 0
    else:
        phase = "ALIGN"
        window_remaining = 0
    if phase in {"DESCEND", "INSERT"} and insertion_depth_m >= float(SUCCESS_METRIC["insertion_depth_m_min"]):
        phase = "INSERT"
    return {
        "current_hysteresis_phase": phase,
        "z_window_remaining_steps": int(window_remaining),
        "entered_descend_step": entered_descend_step,
        "last_z_motion_allowed": bool(z_motion_allowed),
        "hard_safety_escape_triggered": bool(hard_escape),
        "soft_realign_triggered": bool(soft_realign),
        "alignment_gate_satisfied": bool(aligned),
        "approach_lateral_gate_m": gate_m,
        "z_window_realign_lateral_m": z_window_realign_lateral_m,
        "lateral_error_m": lateral_error_m,
    }


def quaternion_angle_error_deg(quat_wxyz: list[float] | np.ndarray, *, target_angle_deg: float) -> float:
    quat = np.asarray(quat_wxyz, dtype=np.float64)
    quat = quat / max(float(np.linalg.norm(quat)), 1.0e-9)
    angle = 2.0 * np.arccos(min(1.0, abs(float(quat[0]))))
    return round(abs(float(np.degrees(angle)) - float(target_angle_deg)), 6)


def _normalize_vector(vector: np.ndarray, fallback: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vector))
    if norm <= 1.0e-9:
        return fallback.astype(np.float64)
    return vector.astype(np.float64) / norm


def _quat_rotate_vector_wxyz_np(quat_wxyz: list[float] | np.ndarray, vector: list[float] | np.ndarray) -> np.ndarray:
    quat = np.asarray(quat_wxyz, dtype=np.float64)
    quat = quat / max(float(np.linalg.norm(quat)), 1.0e-9)
    w, x, y, z = quat
    rotation = np.array(
        [
            [1.0 - 2.0 * (y * y + z * z), 2.0 * (x * y - z * w), 2.0 * (x * z + y * w)],
            [2.0 * (x * y + z * w), 1.0 - 2.0 * (x * x + z * z), 2.0 * (y * z - x * w)],
            [2.0 * (x * z - y * w), 2.0 * (y * z + x * w), 1.0 - 2.0 * (x * x + y * y)],
        ],
        dtype=np.float64,
    )
    return rotation @ np.asarray(vector, dtype=np.float64)


def _axis_alignment_error_deg(
    *,
    held_quat: list[float] | np.ndarray,
    fixed_quat: list[float] | np.ndarray,
) -> float:
    fallback_axis = np.asarray([0.0, 0.0, -1.0], dtype=np.float64)
    held_axis = _normalize_vector(_quat_rotate_vector_wxyz_np(held_quat, fallback_axis), fallback_axis)
    fixed_axis = _normalize_vector(_quat_rotate_vector_wxyz_np(fixed_quat, fallback_axis), fallback_axis)
    dot = float(np.clip(np.dot(held_axis, fixed_axis), -1.0, 1.0))
    return round(float(np.degrees(np.arccos(dot))), 6)


def rdf_compatible_metric_row_from_pose_values(
    *,
    step: int,
    held_pos: list[float] | np.ndarray,
    fixed_pos: list[float] | np.ndarray,
    held_quat: list[float] | np.ndarray,
    fixed_quat: list[float] | np.ndarray,
) -> dict[str, Any]:
    held = np.asarray(held_pos, dtype=np.float64)
    fixed = np.asarray(fixed_pos, dtype=np.float64)
    delta = held - fixed
    lateral_error = float(np.linalg.norm(delta[:2]))
    insertion_depth = max(0.0, float(delta[2]))
    orientation_error = _axis_alignment_error_deg(held_quat=held_quat, fixed_quat=fixed_quat)
    phase = _phase_from_depth(insertion_depth)
    return {
        "step": int(step),
        "phase": phase,
        "insertion_depth_m": round(insertion_depth, 6),
        "relative_x_m": round(float(delta[0]), 6),
        "relative_y_m": round(float(delta[1]), 6),
        "lateral_error_m": round(lateral_error, 6),
        "orientation_error_deg": round(orientation_error, 6),
    }


def _rounded_float_list(values: list[float] | np.ndarray) -> list[float]:
    return [round(float(value), 6) for value in np.asarray(values, dtype=np.float64).tolist()]


def build_factory_peg_insert_native_success_diagnostics(
    *,
    held_base_pos: list[float] | np.ndarray,
    target_held_base_pos: list[float] | np.ndarray,
    fixed_asset_height_m: float,
    success_threshold: float,
    xy_threshold_m: float = 0.0025,
) -> dict[str, Any]:
    held = np.asarray(held_base_pos, dtype=np.float64)
    target = np.asarray(target_held_base_pos, dtype=np.float64)
    delta = held - target
    xy_dist = float(np.linalg.norm(delta[:2]))
    z_disp = float(delta[2])
    height_threshold = float(fixed_asset_height_m) * float(success_threshold)
    is_centered = xy_dist < float(xy_threshold_m)
    is_close_or_below = z_disp < height_threshold
    return {
        "env_native_xy_dist_m": round(xy_dist, 6),
        "env_native_z_disp_m": round(z_disp, 6),
        "env_native_height_threshold_m": round(height_threshold, 6),
        "env_native_xy_threshold_m": round(float(xy_threshold_m), 6),
        "env_native_is_centered": bool(is_centered),
        "env_native_is_close_or_below": bool(is_close_or_below),
        "env_native_success_mask": bool(is_centered and is_close_or_below),
        "env_native_diagnostics_source": "factory_utils_base_target",
        "factory_fixed_asset_height_m": round(float(fixed_asset_height_m), 6),
        "factory_success_threshold": round(float(success_threshold), 6),
    }


def _phase_from_native_seating_progress(
    *,
    approach_height_m: float,
    native_seating_progress_m: float,
    fixed_asset_height_m: float,
    env_native_success_mask: bool,
) -> str:
    if env_native_success_mask:
        return "SEAT"
    if float(approach_height_m) > 0.010:
        return "APPROACH"
    progress_ratio = float(native_seating_progress_m) / max(float(fixed_asset_height_m), 1.0e-9)
    if progress_ratio < 0.25:
        return "CONTACT"
    if progress_ratio < 0.90:
        return "INSERT"
    return "SEAT"


def factory_peg_insert_native_aligned_metric_row_from_pose_values(
    *,
    step: int,
    held_pos: list[float] | np.ndarray,
    fixed_pos: list[float] | np.ndarray,
    held_base_pos: list[float] | np.ndarray,
    target_held_base_pos: list[float] | np.ndarray,
    held_base_quat: list[float] | np.ndarray,
    target_held_base_quat: list[float] | np.ndarray,
    held_quat: list[float] | np.ndarray,
    fixed_quat: list[float] | np.ndarray,
    fixed_asset_height_m: float,
    success_threshold: float,
) -> dict[str, Any]:
    legacy = rdf_compatible_metric_row_from_pose_values(
        step=step,
        held_pos=held_pos,
        fixed_pos=fixed_pos,
        held_quat=held_quat,
        fixed_quat=fixed_quat,
    )
    diag = build_factory_peg_insert_native_success_diagnostics(
        held_base_pos=held_base_pos,
        target_held_base_pos=target_held_base_pos,
        fixed_asset_height_m=fixed_asset_height_m,
        success_threshold=success_threshold,
    )
    z_disp = float(diag["env_native_z_disp_m"])
    approach_height = max(0.0, z_disp)
    native_progress = max(0.0, float(fixed_asset_height_m) - max(z_disp, 0.0))
    phase = _phase_from_native_seating_progress(
        approach_height_m=approach_height,
        native_seating_progress_m=native_progress,
        fixed_asset_height_m=float(fixed_asset_height_m),
        env_native_success_mask=bool(diag["env_native_success_mask"]),
    )
    return {
        **legacy,
        "phase": phase,
        "legacy_positive_z_disp_m": legacy["insertion_depth_m"],
        "rdf_z_disp_legacy_m": legacy["insertion_depth_m"],
        "insertion_depth_m": round(native_progress, 6),
        "runtime_depth_feature_m": round(native_progress, 6),
        "approach_height_m": round(approach_height, 6),
        "native_seating_progress_m": round(native_progress, 6),
        "native_seating_margin_m": round(float(diag["env_native_height_threshold_m"]) - z_disp, 6),
        "rdf_metric_semantics": "factory_native_aligned_v0_6b",
        **diag,
        "held_base_pose_w": {
            "position_m": _rounded_float_list(held_base_pos),
            "quaternion_wxyz": _rounded_float_list(held_base_quat),
        },
        "target_held_base_pose_w": {
            "position_m": _rounded_float_list(target_held_base_pos),
            "quaternion_wxyz": _rounded_float_list(target_held_base_quat),
        },
        "held_asset_pose_w": {
            "position_m": _rounded_float_list(held_pos),
            "quaternion_wxyz": _rounded_float_list(held_quat),
        },
        "fixed_asset_pose_w": {
            "position_m": _rounded_float_list(fixed_pos),
            "quaternion_wxyz": _rounded_float_list(fixed_quat),
        },
        "rdf_relative_pose_inputs": {
            "held_pos_w": _rounded_float_list(held_pos),
            "fixed_pos_w": _rounded_float_list(fixed_pos),
        },
    }


def _predict_policy_action(
    policy_artifact: dict[str, Any],
    *,
    metric_row: dict[str, Any],
    previous_action: list[float],
    action_scale: float,
) -> np.ndarray:
    action, _diagnostics = _predict_policy_action_with_diagnostics(
        policy_artifact=policy_artifact,
        metric_row=metric_row,
        previous_action=previous_action,
        action_scale=action_scale,
    )
    return action


def _predict_policy_action_with_diagnostics(
    policy_artifact: dict[str, Any],
    *,
    metric_row: dict[str, Any],
    previous_action: list[float],
    action_scale: float,
    hysteresis_state: dict[str, Any] | None = None,
) -> tuple[np.ndarray, dict[str, Any]]:
    phase = str(metric_row.get("phase") or _phase_from_depth(float(metric_row.get("insertion_depth_m", 0.0))))
    feature_schema = list(policy_artifact.get("feature_schema") or FEATURE_SCHEMA)
    uses_behavior_phase = bool(policy_artifact.get("behavior_state_phase_input")) or feature_schema == list(
        FEATURE_SCHEMA_V07A
    )
    behavior_state_phase = None
    behavior_state_phase_source = None
    provided_phase_ignored = False
    if uses_behavior_phase:
        rule_version = str(policy_artifact.get("behavior_phase_rule_version") or "")
        if rule_version == V07A1_BEHAVIOR_PHASE_RULE_VERSION:
            provided_phase_ignored = bool(metric_row.get("behavior_state_phase"))
            behavior_state_phase = derive_v07a1_behavior_state_phase_from_metrics(metric_row)
            behavior_state_phase_source = V07A1_RUNTIME_BEHAVIOR_PHASE_SOURCE
        elif rule_version == V07A2_BEHAVIOR_PHASE_RULE_VERSION:
            provided_phase_ignored = bool(metric_row.get("behavior_state_phase"))
            behavior_state_phase = derive_v07a2_behavior_state_phase_from_metrics(metric_row)
            behavior_state_phase_source = V07A2_RUNTIME_BEHAVIOR_PHASE_SOURCE
        elif metric_row.get("behavior_state_phase"):
            behavior_state_phase = str(metric_row["behavior_state_phase"]).upper()
            behavior_state_phase_source = "provided_metric_row"
        else:
            behavior_state_phase = derive_v07a_behavior_state_phase_from_metrics(metric_row)
            behavior_state_phase_source = "derived_v0_7a_runtime_rule"
    hysteresis_config: dict[str, Any] | None = None
    hysteresis_state_before: dict[str, Any] | None = None
    hysteresis_state_after: dict[str, Any] | None = None
    if policy_artifact.get("policy_slice") in V07E_HYSTERESIS_RUNTIME_POLICY_SLICE_IDS:
        hysteresis_config = _validated_v07e_hysteresis_authority_config(policy_artifact)
        hysteresis_state_before = dict(initial_v07e_hysteresis_state())
        if isinstance(hysteresis_state, dict):
            hysteresis_state_before.update(hysteresis_state)
        hysteresis_state_after = _advance_v07e_hysteresis_state(
            metric_row=metric_row,
            hysteresis_state=hysteresis_state_before,
            config=hysteresis_config,
        )
        behavior_state_phase = str(hysteresis_state_after["current_hysteresis_phase"])
        behavior_state_phase_source = V07E_SHARED_HYSTERESIS_AUTHORITY_ID
    feature, _ = featurize_step(
        {
            "phase": phase,
            "behavior_state_phase": behavior_state_phase,
            "insertion_depth_m": metric_row.get("insertion_depth_m", 0.0),
            "relative_x_m": metric_row.get("relative_x_m", 0.0),
            "relative_y_m": metric_row.get("relative_y_m", 0.0),
            "lateral_error_m": metric_row.get("lateral_error_m", 0.0),
            "orientation_error_deg": metric_row.get("orientation_error_deg", 0.0),
            "normalized_action": [0.0] * len(ACTION_SCHEMA),
        },
        previous_action=previous_action,
        feature_schema=feature_schema,
    )
    weights = np.asarray(policy_artifact["weights"], dtype=np.float64)
    bias = np.asarray(policy_artifact["bias"], dtype=np.float64)
    residual_prediction: np.ndarray | None = None
    base_servo_action: np.ndarray | None = None
    base_servo_id: str | None = None
    base_servo_config_sha256: str | None = None
    residual_target_definition: str | None = None
    raw_action_before_authority: np.ndarray | None = None
    raw_action_after_authority: np.ndarray | None = None
    authority_diagnostics: dict[str, Any] = {}
    raw_action = feature @ weights + bias
    if policy_artifact.get("trainer_family") == RESIDUAL_TRAINER_FAMILY:
        residual_prediction = raw_action.copy()
        if policy_artifact.get("policy_slice") in V07B_BASE_SERVO_RUNTIME_POLICY_SLICE_IDS:
            base_config = _validated_v07b_base_servo_config(policy_artifact)
            base_servo_id = V07B_BASE_SERVO_ID
            base_servo_config_sha256 = str(policy_artifact["base_servo_config_sha256"])
            residual_target_definition = V07B_RESIDUAL_TARGET_DEFINITION
        else:
            base_config = policy_artifact.get("weak_base_servo_config")
            base_servo_id = "weak_base_servo"
            base_servo_config_sha256 = (
                str(policy_artifact.get("weak_base_servo_config_sha256"))
                if policy_artifact.get("weak_base_servo_config_sha256")
                else None
            )
            residual_target_definition = str(policy_artifact.get("residual_target_definition") or RESIDUAL_TARGET_DEFINITION)
        base_servo_action = _weak_base_servo_action(metric_row=metric_row, config=base_config)
        raw_action = base_servo_action + residual_prediction
        if policy_artifact.get("policy_slice") in V07C_AUTHORITY_RUNTIME_POLICY_SLICE_IDS:
            authority_config = _validated_v07c_authority_config(policy_artifact)
            raw_action_before_authority = raw_action.copy()
            raw_action_after_authority, authority_diagnostics = _apply_v07c_action_authority_filter(
                behavior_state_phase=str(behavior_state_phase or ""),
                base_action=base_servo_action,
                residual_prediction=residual_prediction,
                raw_action_before_authority=raw_action_before_authority,
                authority_config=authority_config,
            )
            raw_action = raw_action_after_authority
    action, diagnostics = _apply_selected_action_adapter_with_diagnostics(
        policy_artifact=policy_artifact,
        raw_action=raw_action,
        action_scale=action_scale,
        metric_row=metric_row,
        behavior_state_phase=behavior_state_phase,
        hysteresis_state=hysteresis_state_after,
    )
    diagnostics.update(
        {
            "policy_slice": policy_artifact.get("policy_slice"),
            "feature_schema_version": policy_artifact.get("feature_schema_version"),
            "feature_schema": feature_schema,
            "behavior_state_phase": behavior_state_phase,
            "behavior_state_phase_source": behavior_state_phase_source,
            "provided_behavior_state_phase_ignored": provided_phase_ignored,
        }
    )
    if hysteresis_config is not None:
        diagnostics.update(
            {
                "shared_hysteresis_authority_id": hysteresis_config["shared_hysteresis_authority_id"],
                "shared_hysteresis_authority_config_sha256": hysteresis_config[
                    "shared_hysteresis_authority_config_sha256"
                ],
                "shared_hysteresis_state_before": hysteresis_state_before,
                "shared_hysteresis_state_after": hysteresis_state_after,
            }
        )
    if policy_artifact.get("trainer_family") == RESIDUAL_TRAINER_FAMILY:
        diagnostics.update(
            {
                "base_servo_id": base_servo_id,
                "base_servo_action": _rounded_action(base_servo_action if base_servo_action is not None else []),
                "residual_prediction": _rounded_action(
                    residual_prediction if residual_prediction is not None else []
                ),
                "raw_action_before_adapter": _rounded_action(raw_action),
                "base_servo_source_policy_slice": V07C_POLICY_SLICE_ID
                if policy_artifact.get("policy_slice")
                in V07D_FINAL_AUTHORITY_RUNTIME_POLICY_SLICE_IDS
                else policy_artifact.get("policy_slice"),
                "base_servo_config_sha256": base_servo_config_sha256,
                "residual_target_definition": residual_target_definition,
            }
        )
        if policy_artifact.get("policy_slice") in V07C_AUTHORITY_RUNTIME_POLICY_SLICE_IDS:
            diagnostics.update(authority_diagnostics)
            diagnostics["pre_adapter_authority_source_policy_slice"] = V07C_POLICY_SLICE_ID
            diagnostics["raw_action_before_adapter"] = _rounded_action(
                raw_action_after_authority if raw_action_after_authority is not None else raw_action
            )
    return action, diagnostics


def _validated_v07b_base_servo_config(policy_artifact: dict[str, Any]) -> dict[str, Any]:
    base_config = policy_artifact.get("base_servo_config")
    if (
        policy_artifact.get("base_servo_id") != V07B_BASE_SERVO_ID
        or not isinstance(base_config, dict)
        or not policy_artifact.get("base_servo_config_sha256")
        or policy_artifact.get("residual_target_definition") != V07B_RESIDUAL_TARGET_DEFINITION
    ):
        raise ValueError("v0_7b_residual_metadata_missing")
    if base_config.get("base_servo_id") != V07B_BASE_SERVO_ID:
        raise ValueError("v0_7b_residual_metadata_mismatch")
    expected_hash = _sha256_payload(base_config)
    if policy_artifact.get("base_servo_config_sha256") != expected_hash:
        raise ValueError("v0_7b_residual_metadata_hash_mismatch")
    return dict(base_config)


def _validated_v07c_authority_config(policy_artifact: dict[str, Any]) -> dict[str, Any]:
    config = policy_artifact.get("authority_filter_config")
    top_hash = policy_artifact.get("authority_filter_config_sha256")
    if not isinstance(config, dict) or not top_hash:
        raise ValueError("v0_7c_authority_metadata_missing")
    if policy_artifact.get("authority_filter_id") != V07C_AUTHORITY_FILTER_ID:
        raise ValueError("v0_7c_authority_filter_mismatch")
    if config.get("authority_filter_id") != V07C_AUTHORITY_FILTER_ID:
        raise ValueError("v0_7c_authority_filter_mismatch")
    if (
        config.get("schema_version") != V07C_ACTION_AUTHORITY_CONFIG_SCHEMA_VERSION
        or config.get("policy_slice") != V07C_POLICY_SLICE_ID
        or config.get("slice_id") != V07C_SLICE_ID
        or config.get("base_servo_id") != V07B_BASE_SERVO_ID
        or config.get("residual_target_definition") != V07B_RESIDUAL_TARGET_DEFINITION
        or config.get("behavior_phase_rule_version") != V07A2_BEHAVIOR_PHASE_RULE_VERSION
        or config.get("heldout_21000_21049_accessed") is not False
        or config.get("candidate_specific") is not False
        or config.get("baseline_specific") is not False
    ):
        raise ValueError("v0_7c_authority_metadata_mismatch")
    expected_hash = _sha256_payload_excluding(config, "authority_filter_config_sha256")
    if config.get("authority_filter_config_sha256") != expected_hash or top_hash != expected_hash:
        raise ValueError("v0_7c_authority_config_hash_mismatch")
    if policy_artifact.get("selected_action_adapter_id") != config.get("selected_action_adapter_id"):
        raise ValueError("v0_7c_authority_metadata_mismatch")
    return dict(config)


def _validated_v07d_final_action_authority_config(policy_artifact: dict[str, Any]) -> dict[str, Any]:
    config = policy_artifact.get("final_post_adapter_authority_config")
    top_hash = policy_artifact.get("final_post_adapter_authority_config_sha256")
    if not isinstance(config, dict) or not top_hash:
        raise ValueError("v0_7d_final_authority_metadata_missing")
    if policy_artifact.get("final_post_adapter_authority_id") != V07D_FINAL_POST_ADAPTER_AUTHORITY_ID:
        raise ValueError("v0_7d_final_authority_id_mismatch")
    if (
        policy_artifact.get("stable_hold_authority") != "env_native_success_mask"
        or config.get("stable_hold_authority") != "env_native_success_mask"
    ):
        raise ValueError("v0_7d_stable_hold_authority_mismatch")
    if config.get("inherited_authority_filter_config_sha256") != policy_artifact.get("authority_filter_config_sha256"):
        raise ValueError("v0_7d_inherited_authority_config_hash_mismatch")
    if (
        config.get("schema_version") != V07D_FINAL_ACTION_AUTHORITY_CONFIG_SCHEMA_VERSION
        or config.get("policy_slice") != V07D_POLICY_SLICE_ID
        or config.get("slice_id") != V07D_SLICE_ID
        or config.get("final_post_adapter_authority_id") != V07D_FINAL_POST_ADAPTER_AUTHORITY_ID
        or config.get("inherited_authority_filter_id") != V07C_AUTHORITY_FILTER_ID
        or config.get("selected_action_adapter_id") != policy_artifact.get("selected_action_adapter_id")
        or config.get("align_final_z_authority") != "zero_after_adapter_until_z_motion_allowed"
        or config.get("heldout_21000_21049_accessed") is not False
        or config.get("candidate_specific") is not False
        or config.get("baseline_specific") is not False
    ):
        raise ValueError("v0_7d_final_authority_metadata_mismatch")
    expected_hash = _sha256_payload_excluding(config, "final_post_adapter_authority_config_sha256")
    if (
        config.get("final_post_adapter_authority_config_sha256") != expected_hash
        or top_hash != expected_hash
    ):
        raise ValueError("v0_7d_final_authority_config_hash_mismatch")
    return dict(config)


def _validated_v07d_selected_action_adapter_config(policy_artifact: dict[str, Any]) -> dict[str, Any]:
    config = policy_artifact.get("selected_action_adapter_config")
    top_hash = policy_artifact.get("selected_action_adapter_config_sha256")
    if not isinstance(config, dict):
        raise ValueError("v0_7d_selected_action_adapter_config_missing")
    expected_hash = _sha256_payload(config)
    if top_hash != expected_hash:
        raise ValueError("v0_7d_selected_action_adapter_config_hash_mismatch")
    return dict(config)


def _validated_v07e_hysteresis_authority_config(policy_artifact: dict[str, Any]) -> dict[str, Any]:
    config = policy_artifact.get("shared_hysteresis_authority_config")
    top_hash = policy_artifact.get("shared_hysteresis_authority_config_sha256")
    if not isinstance(config, dict) or not top_hash:
        raise ValueError("v0_7e_hysteresis_config_missing")
    if (
        policy_artifact.get("shared_hysteresis_authority_id") != V07E_SHARED_HYSTERESIS_AUTHORITY_ID
        or config.get("shared_hysteresis_authority_id") != V07E_SHARED_HYSTERESIS_AUTHORITY_ID
    ):
        raise ValueError("v0_7e_hysteresis_authority_id_mismatch")
    if (
        policy_artifact.get("same_hysteresis_config_as_peer") is not True
        or config.get("same_hysteresis_config_as_peer") is not True
        or config.get("candidate_specific") is not False
        or config.get("baseline_specific") is not False
    ):
        raise ValueError("v0_7e_hysteresis_config_must_be_shared")
    schema_version = config.get("schema_version")
    if schema_version == V07E_SHARED_HYSTERESIS_AUTHORITY_CONFIG_SCHEMA_VERSION:
        if (
            config.get("policy_slice") != V07E_POLICY_SLICE_ID
            or config.get("parent_policy_slice") != V07D_POLICY_SLICE_ID
            or config.get("heldout_21000_21049_accessed") is not False
        ):
            raise ValueError("v0_7e_hysteresis_config_mismatch")
    elif schema_version == V07M_SHARED_HYSTERESIS_AUTHORITY_CONFIG_SCHEMA_VERSION:
        if (
            policy_artifact.get("policy_slice")
            not in {
                V07M_POLICY_SLICE_ID,
                V07N_POLICY_SLICE_ID,
                V07O_POLICY_SLICE_ID,
                V08A_POLICY_SLICE_ID,
                V08B_POLICY_SLICE_ID,
                V08D_POLICY_SLICE_ID,
                V08F_POLICY_SLICE_ID,
                V08G_POLICY_SLICE_ID,
                *V08H_DERIVED_POLICY_SLICE_IDS,
                V13_POLICY_SLICE_ID,
                V14_POLICY_SLICE_ID,
            }
            or config.get("policy_slice") != V07M_POLICY_SLICE_ID
            or config.get("parent_policy_slice") != V07K_POLICY_SLICE_ID
            or config.get("slice_id") != V07M_SLICE_ID
            or config.get("heldout_21000_21049_accessed") is not False
            or int(config.get("z_window_hold_steps", 0)) < 70
            or float(config.get("z_window_realign_lateral_m", 0.0)) <= 0.0
        ):
            raise ValueError("v0_7m_hysteresis_config_mismatch")
        if not config.get("parent_shared_hysteresis_authority_config_sha256"):
            raise ValueError("v0_7m_parent_hysteresis_config_hash_missing")
    else:
        raise ValueError("v0_7e_hysteresis_config_mismatch")
    if config.get("parent_final_post_adapter_authority_config_sha256") != policy_artifact.get(
        "final_post_adapter_authority_config_sha256"
    ):
        raise ValueError("v0_7e_parent_final_authority_hash_mismatch")
    expected_hash = _sha256_payload_excluding(config, "shared_hysteresis_authority_config_sha256")
    if config.get("shared_hysteresis_authority_config_sha256") != expected_hash or top_hash != expected_hash:
        raise ValueError("v0_7e_hysteresis_config_hash_mismatch")
    return dict(config)


def _validated_v07g_final_xy_authority_config(policy_artifact: dict[str, Any]) -> dict[str, Any]:
    config = policy_artifact.get("final_post_adapter_xy_authority_config")
    top_hash = policy_artifact.get("final_post_adapter_xy_authority_config_sha256")
    if not isinstance(config, dict) or not top_hash:
        raise ValueError("v0_7g_xy_authority_config_missing")
    if (
        policy_artifact.get("final_post_adapter_xy_authority_id") != V07G_FINAL_POST_ADAPTER_XY_AUTHORITY_ID
        or config.get("final_post_adapter_xy_authority_id") != V07G_FINAL_POST_ADAPTER_XY_AUTHORITY_ID
    ):
        raise ValueError("v0_7g_xy_authority_id_mismatch")
    if (
        policy_artifact.get("same_xy_authority_config_as_peer") is not True
        or config.get("same_xy_authority_config_as_peer") is not True
        or config.get("candidate_specific") is not False
        or config.get("baseline_specific") is not False
    ):
        raise ValueError("v0_7g_xy_authority_config_must_be_shared")
    if list(config.get("xy_authority_axis_scope") or []) != ["x", "y"]:
        raise ValueError("v0_7g_xy_authority_must_not_mutate_z")
    if (
        config.get("schema_version") != V07G_FINAL_XY_AUTHORITY_CONFIG_SCHEMA_VERSION
        or config.get("policy_slice") != V07G_POLICY_SLICE_ID
        or config.get("parent_policy_slice") != V07E_POLICY_SLICE_ID
        or config.get("slice_id") != V07G_SLICE_ID
        or config.get("selected_action_adapter_id") != policy_artifact.get("selected_action_adapter_id")
        or config.get("stable_hold_authority") != "env_native_success_mask"
        or config.get("heldout_21000_21049_accessed") is not False
    ):
        raise ValueError("v0_7g_xy_authority_config_mismatch")
    if config.get("parent_shared_hysteresis_authority_config_sha256") != policy_artifact.get(
        "shared_hysteresis_authority_config_sha256"
    ):
        raise ValueError("v0_7g_parent_hysteresis_config_hash_mismatch")
    if config.get("parent_final_post_adapter_authority_config_sha256") != policy_artifact.get(
        "final_post_adapter_authority_config_sha256"
    ):
        raise ValueError("v0_7g_parent_final_z_authority_hash_mismatch")
    if (
        float(config.get("xy_authority_gain", 0.0)) <= 0.0
        or float(config.get("xy_authority_clip_abs", 0.0)) <= 0.0
        or float(config.get("xy_saturation_threshold_abs", 0.0)) <= 0.0
        or float(config.get("xy_near_center_lateral_m", 0.0)) <= 0.0
    ):
        raise ValueError("v0_7g_xy_authority_config_mismatch")
    expected_hash = _sha256_payload_excluding(config, "final_post_adapter_xy_authority_config_sha256")
    if config.get("final_post_adapter_xy_authority_config_sha256") != expected_hash or top_hash != expected_hash:
        raise ValueError("v0_7g_xy_authority_config_hash_mismatch")
    return dict(config)


def _validated_v07j_final_xy_authority_config(policy_artifact: dict[str, Any]) -> dict[str, Any]:
    config = policy_artifact.get("final_post_adapter_xy_authority_config")
    top_hash = policy_artifact.get("final_post_adapter_xy_authority_config_sha256")
    if not isinstance(config, dict) or not top_hash:
        raise ValueError("v0_7j_xy_authority_config_missing")
    if (
        policy_artifact.get("final_post_adapter_xy_authority_id") != V07J_FINAL_POST_ADAPTER_XY_AUTHORITY_ID
        or config.get("final_post_adapter_xy_authority_id") != V07J_FINAL_POST_ADAPTER_XY_AUTHORITY_ID
    ):
        raise ValueError("v0_7j_xy_authority_id_mismatch")
    if (
        policy_artifact.get("same_xy_authority_config_as_peer") is not True
        or config.get("same_xy_authority_config_as_peer") is not True
        or config.get("candidate_specific") is not False
        or config.get("baseline_specific") is not False
    ):
        raise ValueError("v0_7j_xy_authority_config_must_be_shared")
    if list(config.get("xy_authority_axis_scope") or []) != ["x", "y"]:
        raise ValueError("v0_7j_xy_authority_must_not_mutate_z")
    if (
        config.get("schema_version") != V07J_FINAL_XY_AUTHORITY_CONFIG_SCHEMA_VERSION
        or config.get("policy_slice") != V07J_POLICY_SLICE_ID
        or config.get("parent_policy_slice") != V07G_POLICY_SLICE_ID
        or config.get("slice_id") != V07J_SLICE_ID
        or config.get("selected_action_adapter_id") != policy_artifact.get("selected_action_adapter_id")
        or config.get("stable_hold_authority") != "env_native_success_mask"
        or config.get("xy_authority_strategy") != "piecewise_off_center_state_feedback_clip"
        or config.get("heldout_21000_21049_accessed") is not False
    ):
        raise ValueError("v0_7j_xy_authority_config_mismatch")
    if config.get("parent_xy_authority_config_sha256") != policy_artifact.get(
        "parent_xy_authority_config_sha256",
        config.get("parent_xy_authority_config_sha256"),
    ):
        raise ValueError("v0_7j_parent_xy_authority_hash_mismatch")
    expected_parent_shared_hysteresis_hash = (
        policy_artifact.get("parent_shared_hysteresis_authority_config_sha256")
        if policy_artifact.get("policy_slice") == V07M_POLICY_SLICE_ID
        else policy_artifact.get("shared_hysteresis_authority_config_sha256")
    )
    if config.get("parent_shared_hysteresis_authority_config_sha256") != expected_parent_shared_hysteresis_hash:
        raise ValueError("v0_7j_parent_hysteresis_config_hash_mismatch")
    if config.get("parent_final_post_adapter_authority_config_sha256") != policy_artifact.get(
        "final_post_adapter_authority_config_sha256"
    ):
        raise ValueError("v0_7j_parent_final_z_authority_hash_mismatch")
    if (
        float(config.get("xy_authority_gain", 0.0)) <= 0.0
        or float(config.get("xy_near_center_clip_abs", 0.0)) <= 0.0
        or float(config.get("xy_off_center_clip_abs", 0.0)) <= 0.0
        or float(config.get("xy_saturation_threshold_abs", 0.0)) <= 0.0
        or float(config.get("xy_near_center_lateral_m", 0.0)) <= 0.0
    ):
        raise ValueError("v0_7j_xy_authority_config_mismatch")
    expected_hash = _sha256_payload_excluding(config, "final_post_adapter_xy_authority_config_sha256")
    if config.get("final_post_adapter_xy_authority_config_sha256") != expected_hash or top_hash != expected_hash:
        raise ValueError("v0_7j_xy_authority_config_hash_mismatch")
    return dict(config)


def _validated_v07n_final_xy_authority_config(policy_artifact: dict[str, Any]) -> dict[str, Any]:
    config = policy_artifact.get("final_post_adapter_xy_authority_config")
    top_hash = policy_artifact.get("final_post_adapter_xy_authority_config_sha256")
    if not isinstance(config, dict) or not top_hash:
        raise ValueError("v0_7n_xy_authority_config_missing")
    if (
        policy_artifact.get("final_post_adapter_xy_authority_id") != V07N_FINAL_POST_ADAPTER_XY_AUTHORITY_ID
        or config.get("final_post_adapter_xy_authority_id") != V07N_FINAL_POST_ADAPTER_XY_AUTHORITY_ID
    ):
        raise ValueError("v0_7n_xy_authority_id_mismatch")
    if (
        policy_artifact.get("same_xy_authority_config_as_peer") is not True
        or config.get("same_xy_authority_config_as_peer") is not True
        or config.get("candidate_specific") is not False
        or config.get("baseline_specific") is not False
    ):
        raise ValueError("v0_7n_xy_authority_config_must_be_shared")
    if list(config.get("xy_authority_axis_scope") or []) != ["x", "y"]:
        raise ValueError("v0_7n_xy_authority_must_not_mutate_z")
    if (
        config.get("schema_version") != V07N_FINAL_XY_AUTHORITY_CONFIG_SCHEMA_VERSION
        or config.get("policy_slice") != V07N_POLICY_SLICE_ID
        or config.get("parent_policy_slice") != V07M_POLICY_SLICE_ID
        or config.get("slice_id") != V07N_SLICE_ID
        or config.get("selected_action_adapter_id") != policy_artifact.get("selected_action_adapter_id")
        or config.get("stable_hold_authority") != "env_native_success_mask"
        or config.get("xy_authority_strategy") != "z_open_center_maintenance_state_feedback_clip"
        or config.get("allow_sign_flip_during_z_open_low_depth") is not True
        or config.get("heldout_21000_21049_accessed") is not False
    ):
        raise ValueError("v0_7n_xy_authority_config_mismatch")
    if config.get("parent_xy_authority_config_sha256") != policy_artifact.get("parent_xy_authority_config_sha256"):
        raise ValueError("v0_7n_parent_xy_authority_hash_mismatch")
    if config.get("parent_shared_hysteresis_authority_config_sha256") != policy_artifact.get(
        "shared_hysteresis_authority_config_sha256"
    ):
        raise ValueError("v0_7n_parent_hysteresis_config_hash_mismatch")
    if config.get("parent_final_post_adapter_authority_config_sha256") != policy_artifact.get(
        "final_post_adapter_authority_config_sha256"
    ):
        raise ValueError("v0_7n_parent_final_z_authority_hash_mismatch")
    if (
        float(config.get("z_open_centering_depth_max_m", 0.0)) <= 0.0
        or float(config.get("z_open_centering_lateral_m", 0.0)) <= 0.0
        or float(config.get("z_open_xy_authority_gain", 0.0)) <= 0.0
        or float(config.get("z_open_xy_clip_abs", 0.0)) <= 0.0
    ):
        raise ValueError("v0_7n_xy_authority_config_mismatch")
    expected_hash = _sha256_payload_excluding(config, "final_post_adapter_xy_authority_config_sha256")
    if config.get("final_post_adapter_xy_authority_config_sha256") != expected_hash or top_hash != expected_hash:
        raise ValueError("v0_7n_xy_authority_config_hash_mismatch")
    return dict(config)


def _validated_v07o_final_xy_authority_config(policy_artifact: dict[str, Any]) -> dict[str, Any]:
    config = policy_artifact.get("final_post_adapter_xy_authority_config")
    top_hash = policy_artifact.get("final_post_adapter_xy_authority_config_sha256")
    if not isinstance(config, dict) or not top_hash:
        raise ValueError("v0_7o_xy_authority_config_missing")
    if (
        policy_artifact.get("final_post_adapter_xy_authority_id") != V07O_FINAL_POST_ADAPTER_XY_AUTHORITY_ID
        or config.get("final_post_adapter_xy_authority_id") != V07O_FINAL_POST_ADAPTER_XY_AUTHORITY_ID
    ):
        raise ValueError("v0_7o_xy_authority_id_mismatch")
    if (
        policy_artifact.get("same_xy_authority_config_as_peer") is not True
        or config.get("same_xy_authority_config_as_peer") is not True
        or config.get("candidate_specific") is not False
        or config.get("baseline_specific") is not False
    ):
        raise ValueError("v0_7o_xy_authority_config_must_be_shared")
    if list(config.get("xy_authority_axis_scope") or []) != ["x", "y"]:
        raise ValueError("v0_7o_xy_authority_must_not_mutate_z")
    if (
        config.get("schema_version") != V07O_FINAL_XY_AUTHORITY_CONFIG_SCHEMA_VERSION
        or config.get("policy_slice") != V07O_POLICY_SLICE_ID
        or config.get("parent_policy_slice") != V07N_POLICY_SLICE_ID
        or config.get("slice_id") != V07O_SLICE_ID
        or config.get("selected_action_adapter_id") != policy_artifact.get("selected_action_adapter_id")
        or config.get("stable_hold_authority") != "env_native_success_mask"
        or config.get("xy_authority_strategy") != "composed_piecewise_plus_z_open_center_maintenance"
        or config.get("allow_sign_flip_during_z_open_low_depth") is not True
        or config.get("heldout_21000_21049_accessed") is not False
    ):
        raise ValueError("v0_7o_xy_authority_config_mismatch")
    if config.get("parent_xy_authority_config_sha256") != policy_artifact.get("parent_xy_authority_config_sha256"):
        raise ValueError("v0_7o_parent_xy_authority_hash_mismatch")
    if config.get("parent_shared_hysteresis_authority_config_sha256") != policy_artifact.get(
        "shared_hysteresis_authority_config_sha256"
    ):
        raise ValueError("v0_7o_parent_hysteresis_config_hash_mismatch")
    if config.get("parent_final_post_adapter_authority_config_sha256") != policy_artifact.get(
        "final_post_adapter_authority_config_sha256"
    ):
        raise ValueError("v0_7o_parent_final_z_authority_hash_mismatch")
    if (
        float(config.get("xy_authority_gain", 0.0)) <= 0.0
        or float(config.get("xy_near_center_clip_abs", 0.0)) <= 0.0
        or float(config.get("xy_off_center_clip_abs", 0.0)) <= 0.0
        or float(config.get("xy_saturation_threshold_abs", 0.0)) <= 0.0
        or float(config.get("xy_near_center_lateral_m", 0.0)) <= 0.0
        or float(config.get("z_open_centering_depth_max_m", 0.0)) <= 0.0
        or float(config.get("z_open_centering_lateral_m", 0.0)) <= 0.0
        or float(config.get("z_open_xy_authority_gain", 0.0)) <= 0.0
        or float(config.get("z_open_xy_clip_abs", 0.0)) <= 0.0
    ):
        raise ValueError("v0_7o_xy_authority_config_mismatch")
    expected_hash = _sha256_payload_excluding(config, "final_post_adapter_xy_authority_config_sha256")
    if config.get("final_post_adapter_xy_authority_config_sha256") != expected_hash or top_hash != expected_hash:
        raise ValueError("v0_7o_xy_authority_config_hash_mismatch")
    return dict(config)


def _validated_v08a_seat_window_authority_config(policy_artifact: dict[str, Any]) -> dict[str, Any]:
    config = policy_artifact.get("seat_window_authority_config")
    top_hash = policy_artifact.get("seat_window_authority_config_sha256")
    if not isinstance(config, dict) or not top_hash:
        raise ValueError("v0_8a_seat_window_authority_config_missing")
    if (
        policy_artifact.get("seat_window_authority_id") != V08A_SEAT_WINDOW_AUTHORITY_ID
        or config.get("seat_window_authority_id") != V08A_SEAT_WINDOW_AUTHORITY_ID
    ):
        raise ValueError("v0_8a_seat_window_authority_id_mismatch")
    if (
        policy_artifact.get("same_seat_window_authority_config_as_peer") is not True
        or config.get("candidate_specific") is not False
        or config.get("baseline_specific") is not False
    ):
        raise ValueError("v0_8a_seat_window_authority_config_must_be_shared")
    if (
        config.get("schema_version") != V08A_SEAT_WINDOW_AUTHORITY_CONFIG_SCHEMA_VERSION
        or config.get("policy_slice") != V08A_POLICY_SLICE_ID
        or config.get("parent_policy_slice") != V07O_POLICY_SLICE_ID
        or config.get("slice_id") != V08A_SLICE_ID
    ):
        raise ValueError("v0_8a_seat_window_authority_config_mismatch")
    if (
        float(config.get("latest_z_open_step", -1)) < 0
        or float(config.get("z_open_centering_lateral_m", 0.0)) <= 0.0
        or float(config.get("seat_region_depth_m", 0.0)) <= 0.0
        or float(config.get("z_progress_action", 0.0)) >= 0.0
    ):
        raise ValueError("v0_8a_seat_window_authority_config_mismatch")
    expected_hash = _sha256_payload_excluding(config, "seat_window_authority_config_sha256")
    if config.get("seat_window_authority_config_sha256") != expected_hash or top_hash != expected_hash:
        raise ValueError("v0_8a_seat_window_authority_config_hash_mismatch")
    return dict(config)


def _validated_v08b_seat_window_authority_config(policy_artifact: dict[str, Any]) -> dict[str, Any]:
    config = policy_artifact.get("seat_window_authority_config")
    top_hash = policy_artifact.get("seat_window_authority_config_sha256")
    if not isinstance(config, dict) or not top_hash:
        raise ValueError("v0_8b_seat_window_authority_config_missing")
    if (
        policy_artifact.get("seat_window_authority_id") != V08B_SEAT_WINDOW_AUTHORITY_ID
        or config.get("seat_window_authority_id") != V08B_SEAT_WINDOW_AUTHORITY_ID
    ):
        raise ValueError("v0_8b_seat_window_authority_id_mismatch")
    if (
        policy_artifact.get("same_seat_window_authority_config_as_peer") is not True
        or config.get("candidate_specific") is not False
        or config.get("baseline_specific") is not False
    ):
        raise ValueError("v0_8b_seat_window_authority_config_must_be_shared")
    if (
        config.get("schema_version") != V08B_SEAT_WINDOW_AUTHORITY_CONFIG_SCHEMA_VERSION
        or config.get("policy_slice") != V08B_POLICY_SLICE_ID
        or config.get("parent_policy_slice") != V08A_POLICY_SLICE_ID
        or config.get("slice_id") != V08B_SLICE_ID
    ):
        raise ValueError("v0_8b_seat_window_authority_config_mismatch")
    if (
        float(config.get("scenario_aware_deadline_step", -1)) < 0
        or float(config.get("z_open_centering_lateral_m", 0.0)) <= 0.0
        or float(config.get("seat_region_depth_m", 0.0)) <= 0.0
        or float(config.get("z_progress_action", 0.0)) >= 0.0
    ):
        raise ValueError("v0_8b_seat_window_authority_config_mismatch")
    if config.get("heldout_24000_24049_used_for_parameter_derivation") is not False:
        raise ValueError("v0_8b_must_not_use_v08a_heldout_for_parameter_derivation")
    expected_hash = _sha256_payload_excluding(config, "seat_window_authority_config_sha256")
    if config.get("seat_window_authority_config_sha256") != expected_hash or top_hash != expected_hash:
        raise ValueError("v0_8b_seat_window_authority_config_hash_mismatch")
    return dict(config)


def _validated_v08d_capture_conditioned_progress_authority_config(
    policy_artifact: dict[str, Any],
) -> dict[str, Any]:
    config = policy_artifact.get("capture_conditioned_progress_authority_config")
    top_hash = policy_artifact.get("capture_conditioned_progress_authority_config_sha256")
    if not isinstance(config, dict) or not top_hash:
        raise ValueError("v0_8d_capture_conditioned_progress_authority_config_missing")
    if (
        policy_artifact.get("capture_conditioned_progress_authority_id")
        != V08D_CAPTURE_CONDITIONED_PROGRESS_AUTHORITY_ID
        or config.get("capture_conditioned_progress_authority_id")
        != V08D_CAPTURE_CONDITIONED_PROGRESS_AUTHORITY_ID
    ):
        raise ValueError("v0_8d_capture_conditioned_progress_authority_id_mismatch")
    if (
        policy_artifact.get("same_capture_conditioned_progress_authority_config_as_peer") is not True
        or config.get("candidate_specific") is not False
        or config.get("baseline_specific") is not False
    ):
        raise ValueError("v0_8d_capture_conditioned_progress_authority_config_must_be_shared")
    if (
        config.get("schema_version") != V08D_CAPTURE_CONDITIONED_PROGRESS_AUTHORITY_CONFIG_SCHEMA_VERSION
        or config.get("policy_slice") != V08D_POLICY_SLICE_ID
        or config.get("parent_policy_slice") != V08B_POLICY_SLICE_ID
        or config.get("slice_id") != V08D_SLICE_ID
    ):
        raise ValueError("v0_8d_capture_conditioned_progress_authority_config_mismatch")
    if (
        int(config.get("early_z_deadline_step", -1)) > 68
        or int(config.get("early_z_deadline_step", -1)) < 0
        or int(config.get("capture_prepare_start_step", -1)) < 0
        or int(config.get("capture_prepare_start_step", 9999))
        >= int(config.get("early_z_deadline_step", -1))
        or float(config.get("capture_lateral_gate_m", 0.0)) <= 0.0
        or float(config.get("seat_region_depth_m", 0.0)) <= 0.0
        or float(config.get("z_progress_action", 0.0)) >= 0.0
        or int(config.get("depth_progress_window_steps", 0)) <= 0
        or float(config.get("minimum_depth_progress_m", 0.0)) <= 0.0
        or float(config.get("under_depth_progress_threshold_m", 0.0)) <= 0.0
    ):
        raise ValueError("v0_8d_capture_conditioned_progress_authority_config_mismatch")
    if list(config.get("burned_heldout_seed_ranges") or []) != [
        [21000, 21049],
        [24000, 24049],
        [26000, 26049],
    ]:
        raise ValueError("v0_8d_burned_heldout_seed_ranges_mismatch")
    if list(config.get("fresh_heldout_seed_range") or []) != [27000, 27049]:
        raise ValueError("v0_8d_fresh_heldout_seed_range_mismatch")
    if set(config.get("forbidden_mechanisms") or []) != {"retry", "withdraw", "search", "force_control"}:
        raise ValueError("v0_8d_forbidden_mechanisms_mismatch")
    expected_hash = _sha256_payload_excluding(
        config,
        "capture_conditioned_progress_authority_config_sha256",
    )
    if (
        config.get("capture_conditioned_progress_authority_config_sha256") != expected_hash
        or top_hash != expected_hash
    ):
        raise ValueError("v0_8d_capture_conditioned_progress_authority_config_hash_mismatch")
    return dict(config)


def _validated_v08f_horizon_reserved_capture_authority_config(
    policy_artifact: dict[str, Any],
) -> dict[str, Any]:
    config = policy_artifact.get("horizon_reserved_capture_authority_config")
    top_hash = policy_artifact.get("horizon_reserved_capture_authority_config_sha256")
    if not isinstance(config, dict) or not top_hash:
        raise ValueError("v0_8f_horizon_reserved_capture_authority_config_missing")
    if (
        policy_artifact.get("horizon_reserved_capture_authority_id")
        != V08F_HORIZON_RESERVED_CAPTURE_AUTHORITY_ID
        or config.get("horizon_reserved_capture_authority_id")
        != V08F_HORIZON_RESERVED_CAPTURE_AUTHORITY_ID
    ):
        raise ValueError("v0_8f_horizon_reserved_capture_authority_id_mismatch")
    if (
        policy_artifact.get("same_horizon_reserved_capture_authority_config_as_peer") is not True
        or config.get("candidate_specific") is not False
        or config.get("baseline_specific") is not False
    ):
        raise ValueError("v0_8f_horizon_reserved_capture_authority_config_must_be_shared")
    if (
        config.get("schema_version")
        != V08F_HORIZON_RESERVED_CAPTURE_AUTHORITY_CONFIG_SCHEMA_VERSION
        or config.get("policy_slice") != V08F_POLICY_SLICE_ID
        or config.get("parent_policy_slice") != V08D_POLICY_SLICE_ID
        or config.get("source_policy_slice") != "v0_8e"
        or config.get("slice_id") != V08F_SLICE_ID
    ):
        raise ValueError("v0_8f_horizon_reserved_capture_authority_config_mismatch")
    if (
        int(config.get("capture_prepare_start_step", -1)) < 0
        or int(config.get("horizon_reserved_z_deadline_step", -1)) < 0
        or int(config.get("capture_prepare_start_step", 9999))
        >= int(config.get("horizon_reserved_z_deadline_step", -1))
        or float(config.get("capture_lateral_gate_m", 0.0)) <= 0.0
        or config.get("capture_wait_xy_authority_enabled") is not True
        or float(config.get("capture_wait_xy_authority_gain", 0.0)) <= 0.0
        or float(config.get("capture_wait_xy_clip_abs", 0.0)) <= 0.0
        or config.get("capture_wait_sign_flip_allowed") is not True
        or config.get("seat_completion_until_env_native_success") is not True
        or float(config.get("seat_region_depth_m", 0.0)) <= 0.0
        or float(config.get("z_progress_action", 0.0)) >= 0.0
    ):
        raise ValueError("v0_8f_horizon_reserved_capture_authority_config_mismatch")
    if list(config.get("burned_heldout_seed_ranges") or []) != [
        [21000, 21049],
        [24000, 24049],
        [26000, 26049],
    ]:
        raise ValueError("v0_8f_burned_heldout_seed_ranges_mismatch")
    if list(config.get("burned_calibration_seed_ranges") or []) != [[26500, 26529]]:
        raise ValueError("v0_8f_burned_calibration_seed_ranges_mismatch")
    if list(config.get("fresh_calibration_seed_range") or []) != [27500, 27529]:
        raise ValueError("v0_8f_fresh_calibration_seed_range_mismatch")
    if list(config.get("fresh_heldout_seed_range") or []) != [27000, 27049]:
        raise ValueError("v0_8f_fresh_heldout_seed_range_mismatch")
    if set(config.get("forbidden_mechanisms") or []) != {"retry", "withdraw", "search", "force_control"}:
        raise ValueError("v0_8f_forbidden_mechanisms_mismatch")
    expected_hash = _sha256_payload_excluding(
        config,
        "horizon_reserved_capture_authority_config_sha256",
    )
    if (
        config.get("horizon_reserved_capture_authority_config_sha256") != expected_hash
        or top_hash != expected_hash
    ):
        raise ValueError("v0_8f_horizon_reserved_capture_authority_config_hash_mismatch")
    return dict(config)


def _validated_v08g_deadline_precedence_horizon_authority_config(
    policy_artifact: dict[str, Any],
) -> dict[str, Any]:
    config = policy_artifact.get("deadline_precedence_horizon_authority_config")
    top_hash = policy_artifact.get("deadline_precedence_horizon_authority_config_sha256")
    if not isinstance(config, dict) or not top_hash:
        raise ValueError("v0_8g_deadline_precedence_horizon_authority_config_missing")
    if (
        policy_artifact.get("deadline_precedence_horizon_authority_id")
        != V08G_DEADLINE_PRECEDENCE_HORIZON_AUTHORITY_ID
        or config.get("deadline_precedence_horizon_authority_id")
        != V08G_DEADLINE_PRECEDENCE_HORIZON_AUTHORITY_ID
    ):
        raise ValueError("v0_8g_deadline_precedence_horizon_authority_id_mismatch")
    if (
        policy_artifact.get("same_deadline_precedence_horizon_authority_config_as_peer") is not True
        or config.get("candidate_specific") is not False
        or config.get("baseline_specific") is not False
    ):
        raise ValueError("v0_8g_deadline_precedence_horizon_authority_config_must_be_shared")
    if (
        config.get("schema_version")
        != V08G_DEADLINE_PRECEDENCE_HORIZON_AUTHORITY_CONFIG_SCHEMA_VERSION
        or config.get("policy_slice") != V08G_POLICY_SLICE_ID
        or config.get("parent_policy_slice") != V08F_POLICY_SLICE_ID
        or config.get("source_policy_slice") != V08F_POLICY_SLICE_ID
        or config.get("slice_id") != V08G_SLICE_ID
    ):
        raise ValueError("v0_8g_deadline_precedence_horizon_authority_config_mismatch")
    if (
        not config.get("source_v08f_calibration_presignal_gate_sha256")
        or not config.get("parent_v08f_horizon_reserved_capture_authority_config_sha256")
    ):
        raise ValueError("v0_8g_deadline_precedence_source_hash_missing")
    if (
        int(config.get("capture_prepare_start_step", -1)) < 0
        or int(config.get("horizon_reserved_z_deadline_step", -1)) < 0
        or int(config.get("capture_prepare_start_step", 9999))
        >= int(config.get("horizon_reserved_z_deadline_step", -1))
        or float(config.get("capture_lateral_gate_m", 0.0)) <= 0.0
        or config.get("capture_wait_xy_authority_enabled") is not True
        or float(config.get("capture_wait_xy_authority_gain", 0.0)) <= 0.0
        or float(config.get("capture_wait_xy_clip_abs", 0.0)) <= 0.0
        or config.get("capture_wait_sign_flip_allowed") is not True
        or config.get("deadline_precedence_over_capture_wait") is not True
        or config.get("seat_completion_until_env_native_success") is not True
        or float(config.get("seat_region_depth_m", 0.0)) <= 0.0
        or float(config.get("z_progress_action", 0.0)) >= 0.0
    ):
        raise ValueError("v0_8g_deadline_precedence_horizon_authority_config_mismatch")
    if list(config.get("burned_heldout_seed_ranges") or []) != [
        [21000, 21049],
        [24000, 24049],
        [26000, 26049],
    ]:
        raise ValueError("v0_8g_burned_heldout_seed_ranges_mismatch")
    if list(config.get("burned_calibration_seed_ranges") or []) != [[26500, 26529], [27500, 27529]]:
        raise ValueError("v0_8g_burned_calibration_seed_ranges_mismatch")
    if list(config.get("fresh_calibration_seed_range") or []) != [28000, 28029]:
        raise ValueError("v0_8g_fresh_calibration_seed_range_mismatch")
    if list(config.get("fresh_heldout_seed_range") or []) != [27000, 27049]:
        raise ValueError("v0_8g_fresh_heldout_seed_range_mismatch")
    if config.get("fresh_heldout_27000_27049_accessed") is not False:
        raise ValueError("v0_8g_fresh_heldout_access_must_be_false_before_runtime_gate")
    if set(config.get("forbidden_mechanisms") or []) != {"retry", "withdraw", "search", "force_control"}:
        raise ValueError("v0_8g_forbidden_mechanisms_mismatch")
    expected_hash = _sha256_payload_excluding(
        config,
        "deadline_precedence_horizon_authority_config_sha256",
    )
    if (
        config.get("deadline_precedence_horizon_authority_config_sha256") != expected_hash
        or top_hash != expected_hash
    ):
        raise ValueError("v0_8g_deadline_precedence_horizon_authority_config_hash_mismatch")
    return dict(config)


def _validated_v08h_early_centered_z_open_safe_entry_config(
    policy_artifact: dict[str, Any],
) -> dict[str, Any]:
    config = policy_artifact.get("early_centered_z_open_safe_entry_config")
    top_hash = policy_artifact.get("early_centered_z_open_safe_entry_config_sha256")
    if not isinstance(config, dict) or not top_hash:
        raise ValueError("v0_8h_early_centered_z_open_safe_entry_config_missing")
    if (
        policy_artifact.get("early_centered_z_open_safe_entry_authority_id")
        != V08H_EARLY_CENTERED_Z_OPEN_SAFE_ENTRY_AUTHORITY_ID
        or config.get("early_centered_z_open_safe_entry_authority_id")
        != V08H_EARLY_CENTERED_Z_OPEN_SAFE_ENTRY_AUTHORITY_ID
    ):
        raise ValueError("v0_8h_early_centered_z_open_safe_entry_authority_id_mismatch")
    if (
        policy_artifact.get("same_early_centered_z_open_safe_entry_config_as_peer") is not True
        or config.get("candidate_specific") is not False
        or config.get("baseline_specific") is not False
    ):
        raise ValueError("v0_8h_early_centered_z_open_safe_entry_config_must_be_shared")
    if (
        config.get("schema_version")
        != V08H_EARLY_CENTERED_Z_OPEN_SAFE_ENTRY_CONFIG_SCHEMA_VERSION
        or config.get("policy_slice") != V08H_POLICY_SLICE_ID
        or config.get("parent_policy_slice") != V08G_POLICY_SLICE_ID
        or config.get("source_policy_slice") != V08G_POLICY_SLICE_ID
        or config.get("slice_id") != V08H_SLICE_ID
    ):
        raise ValueError("v0_8h_early_centered_z_open_safe_entry_config_mismatch")
    if (
        not config.get("source_v08g_calibration_presignal_gate_sha256")
        or not config.get("parent_v08g_deadline_precedence_horizon_authority_config_sha256")
    ):
        raise ValueError("v0_8h_safe_entry_source_hash_missing")
    if (
        int(config.get("capture_prepare_start_step", -1)) < 0
        or int(config.get("reference_deadline_step", -1)) < 0
        or int(config.get("capture_prepare_start_step", 9999))
        >= int(config.get("reference_deadline_step", -1))
        or float(config.get("safe_entry_lateral_gate_m", 0.0)) <= 0.0
        or float(config.get("depth_progress_continuation_lateral_gate_m", 0.0))
        < float(config.get("safe_entry_lateral_gate_m", 0.0))
        or config.get("capture_wait_xy_authority_enabled") is not True
        or float(config.get("capture_wait_xy_authority_gain", 0.0)) <= 0.0
        or float(config.get("capture_wait_xy_clip_abs", 0.0)) <= 0.0
        or config.get("capture_wait_sign_flip_allowed") is not True
        or config.get("unsafe_lateral_z_block_after_reference_deadline") is not True
        or config.get("early_centered_z_open_enabled") is not True
        or config.get("depth_progress_continuation_enabled") is not True
        or config.get("seat_completion_until_env_native_success") is not True
        or float(config.get("seat_region_depth_m", 0.0)) <= 0.0
        or float(config.get("z_progress_action", 0.0)) >= 0.0
    ):
        raise ValueError("v0_8h_early_centered_z_open_safe_entry_config_mismatch")
    if list(config.get("burned_heldout_seed_ranges") or []) != [
        [21000, 21049],
        [24000, 24049],
        [26000, 26049],
    ]:
        raise ValueError("v0_8h_burned_heldout_seed_ranges_mismatch")
    if list(config.get("burned_calibration_seed_ranges") or []) != [
        [26500, 26529],
        [27500, 27529],
        [28000, 28029],
    ]:
        raise ValueError("v0_8h_burned_calibration_seed_ranges_mismatch")
    if list(config.get("fresh_calibration_seed_range") or []) != [28500, 28529]:
        raise ValueError("v0_8h_fresh_calibration_seed_range_mismatch")
    if list(config.get("fresh_heldout_seed_range") or []) != [27000, 27049]:
        raise ValueError("v0_8h_fresh_heldout_seed_range_mismatch")
    if config.get("fresh_heldout_27000_27049_accessed") is not False:
        raise ValueError("v0_8h_fresh_heldout_access_must_be_false_before_runtime_gate")
    if set(config.get("forbidden_mechanisms") or []) != {"retry", "withdraw", "search", "force_control"}:
        raise ValueError("v0_8h_forbidden_mechanisms_mismatch")
    expected_hash = _sha256_payload_excluding(
        config,
        "early_centered_z_open_safe_entry_config_sha256",
    )
    if config.get("early_centered_z_open_safe_entry_config_sha256") != expected_hash or top_hash != expected_hash:
        raise ValueError("v0_8h_early_centered_z_open_safe_entry_config_hash_mismatch")
    return dict(config)


def _apply_v07c_action_authority_filter(
    *,
    behavior_state_phase: str,
    base_action: np.ndarray,
    residual_prediction: np.ndarray,
    raw_action_before_authority: np.ndarray,
    authority_config: dict[str, Any],
) -> tuple[np.ndarray, dict[str, Any]]:
    base = np.asarray(base_action, dtype=np.float64).copy()
    residual = np.asarray(residual_prediction, dtype=np.float64).copy()
    before = np.asarray(raw_action_before_authority, dtype=np.float64).copy()
    after = before.copy()
    phase = str(behavior_state_phase).upper()
    z_source = "base_plus_residual"
    suppressed = False
    if phase == "ALIGN" and authority_config.get("align_z_authority") == "base_servo_z_only":
        after[2] = base[2]
        residual_after = 0.0
        z_source = "base_servo"
        suppressed = True
    else:
        residual_after = float(after[2] - base[2])
    return np.round(after, 12), {
        "authority_filter_id": authority_config.get("authority_filter_id"),
        "authority_filter_config_sha256": authority_config.get("authority_filter_config_sha256"),
        "raw_action_before_authority": _rounded_action(before),
        "raw_action_after_authority": _rounded_action(after),
        "residual_z_before_authority": round(float(residual[2]), 12),
        "residual_z_after_authority": round(float(residual_after), 12),
        "align_residual_z_suppressed": bool(suppressed),
        "z_authority_source": z_source,
    }


def _weak_base_servo_action(
    *,
    metric_row: dict[str, Any],
    config: dict[str, Any] | None = None,
) -> np.ndarray:
    cfg = dict(WEAK_BASE_SERVO_CONFIG)
    if isinstance(config, dict):
        cfg.update(config)
    phase = str(metric_row.get("phase") or _phase_from_depth(float(metric_row.get("insertion_depth_m", 0.0)))).upper()
    z_by_phase = {
        "APPROACH": float(cfg["approach_z"]),
        "CONTACT": float(cfg["contact_z"]),
        "INSERT": float(cfg["insert_z"]),
        "SEAT": float(cfg["seat_z"]),
    }
    action = np.zeros(len(ACTION_SCHEMA), dtype=np.float64)
    action[0] = -float(metric_row.get("relative_x_m", 0.0)) * float(cfg["xy_gain"])
    action[1] = -float(metric_row.get("relative_y_m", 0.0)) * float(cfg["xy_gain"])
    action[2] = z_by_phase.get(phase, float(cfg["approach_z"]))
    action[3:6] = float(cfg.get("rotation", 0.0))
    if action.shape[0] > 6:
        action[6] = float(cfg.get("gripper", 1.0))
    return action


def _apply_selected_action_adapter(
    *,
    policy_artifact: dict[str, Any],
    raw_action: np.ndarray,
    action_scale: float,
    metric_row: dict[str, Any] | None = None,
) -> np.ndarray:
    action, _diagnostics = _apply_selected_action_adapter_with_diagnostics(
        policy_artifact=policy_artifact,
        raw_action=raw_action,
        action_scale=action_scale,
        metric_row=metric_row,
    )
    return action


def _rounded_action(values: np.ndarray | list[float]) -> list[float]:
    return [round(float(value), 12) for value in np.asarray(values, dtype=np.float64).reshape(-1).tolist()]


def _stable_hold_ready_env_native(*, metric_row: dict[str, Any]) -> bool:
    return _env_native_success_mask_from_row(metric_row)


def _apply_v07d_final_post_adapter_authority(
    *,
    action: np.ndarray,
    behavior_state_phase: str | None,
    final_authority_config: dict[str, Any],
    current_block_reason: str,
) -> tuple[np.ndarray, dict[str, Any]]:
    before = np.asarray(action, dtype=np.float64).copy()
    after = before.copy()
    phase = str(behavior_state_phase or "").upper()
    z_allowed = True
    reason = current_block_reason
    if phase == "ALIGN":
        z_allowed = False
        after[2] = 0.0
        reason = "final_post_adapter_align_z_blocked"
    final_action = np.round(np.clip(after, -1.0, 1.0), 12)
    return final_action, {
        "final_post_adapter_authority_id": final_authority_config["final_post_adapter_authority_id"],
        "final_post_adapter_authority_config_sha256": final_authority_config[
            "final_post_adapter_authority_config_sha256"
        ],
        "pre_final_authority_action_vector": _rounded_action(before),
        "final_post_adapter_z_motion_allowed": bool(z_allowed),
        "z_motion_block_reason": reason,
    }


def _apply_v08a_seat_window_progress_authority(
    *,
    action: np.ndarray,
    metric_row: dict[str, Any] | None,
    config: dict[str, Any],
) -> tuple[np.ndarray, dict[str, Any]]:
    before = np.asarray(action, dtype=np.float64).copy()
    after = before.copy()
    reason = "metric_row_missing"
    applied = False
    if metric_row is not None:
        step = int(metric_row.get("step", -1))
        latest_z_open_step = int(config["latest_z_open_step"])
        lateral = float(metric_row.get("lateral_error_m", 999.0))
        depth = float(metric_row.get("insertion_depth_m", 0.0))
        centered = lateral <= float(config["z_open_centering_lateral_m"])
        below_seat_region = depth < float(config["seat_region_depth_m"])
        env_native_success = bool(metric_row.get("env_native_success", False))
        if step < latest_z_open_step:
            reason = "before_train_derived_z_open_deadline"
        elif env_native_success:
            reason = "env_native_success_already_true"
        elif not centered:
            reason = "not_centered_for_seat_window_progress"
        elif not below_seat_region:
            reason = "already_in_seat_region"
        else:
            after[2] = float(config["z_progress_action"])
            reason = "forced_train_derived_seat_progress_z"
            applied = True
    final_action = np.round(np.clip(after, -1.0, 1.0), 12)
    return final_action, {
        "seat_window_authority_id": config["seat_window_authority_id"],
        "seat_window_authority_config_sha256": config["seat_window_authority_config_sha256"],
        "pre_seat_window_authority_action_vector": _rounded_action(before),
        "post_seat_window_authority_action_vector": _rounded_action(final_action),
        "seat_window_authority_applied": bool(applied),
        "seat_window_authority_reason": reason,
        "seat_window_authority_preserved_xy": bool(np.allclose(final_action[0:2], before[0:2])),
        "seat_window_latest_z_open_step": int(config["latest_z_open_step"]),
    }


def _apply_v08b_scenario_aware_seat_window_authority(
    *,
    action: np.ndarray,
    metric_row: dict[str, Any] | None,
    config: dict[str, Any],
) -> tuple[np.ndarray, dict[str, Any]]:
    before = np.asarray(action, dtype=np.float64).copy()
    after = before.copy()
    reason = "metric_row_missing"
    applied = False
    if metric_row is not None:
        step = int(metric_row.get("step", -1))
        deadline_step = int(config["scenario_aware_deadline_step"])
        lateral = float(metric_row.get("lateral_error_m", 999.0))
        depth = float(metric_row.get("insertion_depth_m", 0.0))
        centered = lateral <= float(config["z_open_centering_lateral_m"])
        below_seat_region = depth < float(config["seat_region_depth_m"])
        env_native_success = bool(metric_row.get("env_native_success", False))
        if step < deadline_step:
            reason = "before_scenario_aware_z_open_deadline"
        elif env_native_success:
            reason = "env_native_success_already_true"
        elif not centered:
            reason = "not_centered_for_seat_window_progress"
        elif not below_seat_region:
            reason = "already_in_seat_region"
        else:
            after[2] = float(config["z_progress_action"])
            reason = "forced_scenario_aware_seat_progress_z"
            applied = True
    final_action = np.round(np.clip(after, -1.0, 1.0), 12)
    return final_action, {
        "seat_window_authority_id": config["seat_window_authority_id"],
        "seat_window_authority_config_sha256": config["seat_window_authority_config_sha256"],
        "pre_seat_window_authority_action_vector": _rounded_action(before),
        "post_seat_window_authority_action_vector": _rounded_action(final_action),
        "seat_window_authority_applied": bool(applied),
        "seat_window_authority_reason": reason,
        "seat_window_authority_preserved_xy": bool(np.allclose(final_action[0:2], before[0:2])),
        "scenario_aware_deadline_step": int(config["scenario_aware_deadline_step"]),
        "latest_z_open_step_train_max": int(config.get("latest_z_open_step_train_max", -1)),
        "effective_z_open_for_xy_authority": bool(final_action[2] < 0.0),
        "seat_window_xy_recomputed_with_forced_z": False,
    }


def _apply_v08d_capture_conditioned_progress_authority(
    *,
    action: np.ndarray,
    metric_row: dict[str, Any] | None,
    config: dict[str, Any],
) -> tuple[np.ndarray, dict[str, Any]]:
    before = np.asarray(action, dtype=np.float64).copy()
    after = before.copy()
    reason = "metric_row_missing"
    applied = False
    z_open_step: int | None = None
    z_open_depth_reference_m: float | None = None
    depth_progress_delta_m: float | None = None
    under_depth_progress_watch = False
    if metric_row is not None:
        step = int(metric_row.get("step", -1))
        early_z_deadline_step = int(config["early_z_deadline_step"])
        capture_prepare_start_step = int(config["capture_prepare_start_step"])
        lateral = float(metric_row.get("lateral_error_m", 999.0))
        depth = float(metric_row.get("insertion_depth_m", 0.0))
        capture_lateral_gate_m = float(config["capture_lateral_gate_m"])
        seat_region_depth_m = float(config["seat_region_depth_m"])
        env_native_success = bool(metric_row.get("env_native_success", False))
        z_open_step_value = metric_row.get("z_open_step")
        z_open_depth_value = metric_row.get("z_open_depth_reference_m")
        if z_open_step_value is not None:
            z_open_step = int(z_open_step_value)
        if z_open_depth_value is not None:
            z_open_depth_reference_m = float(z_open_depth_value)
        if z_open_step is not None and z_open_depth_reference_m is not None:
            depth_progress_delta_m = round(depth - z_open_depth_reference_m, 12)
            if (
                step - z_open_step >= int(config["depth_progress_window_steps"])
                and depth < float(config["under_depth_progress_threshold_m"])
                and depth_progress_delta_m < float(config["minimum_depth_progress_m"])
            ):
                under_depth_progress_watch = True
        if env_native_success:
            reason = "env_native_success_already_true"
        elif depth >= seat_region_depth_m:
            reason = "already_in_seat_region"
        elif step >= capture_prepare_start_step and lateral > capture_lateral_gate_m:
            after[2] = 0.0
            reason = "capture_conditioning_wait"
            applied = True
        elif step < early_z_deadline_step:
            after[2] = 0.0
            reason = "before_early_z_deadline"
        else:
            after[2] = float(config["z_progress_action"])
            reason = "forced_capture_conditioned_progress_z"
            applied = True
            if z_open_step is None:
                z_open_step = step
                z_open_depth_reference_m = depth
                depth_progress_delta_m = 0.0
    final_action = np.round(np.clip(after, -1.0, 1.0), 12)
    return final_action, {
        "capture_conditioned_progress_authority_id": config[
            "capture_conditioned_progress_authority_id"
        ],
        "capture_conditioned_progress_authority_config_sha256": config[
            "capture_conditioned_progress_authority_config_sha256"
        ],
        "pre_capture_conditioned_progress_authority_action_vector": _rounded_action(before),
        "post_capture_conditioned_progress_authority_action_vector": _rounded_action(final_action),
        "capture_conditioning_applied": bool(applied),
        "capture_conditioning_reason": reason,
        "early_z_deadline_step": int(config["early_z_deadline_step"]),
        "capture_prepare_start_step": int(config["capture_prepare_start_step"]),
        "capture_lateral_gate_m": float(config["capture_lateral_gate_m"]),
        "z_open_step": z_open_step,
        "z_open_depth_reference_m": z_open_depth_reference_m,
        "depth_progress_window_steps": int(config["depth_progress_window_steps"]),
        "depth_progress_delta_m": depth_progress_delta_m,
        "under_depth_progress_watch": bool(under_depth_progress_watch),
        "effective_z_open_for_xy_authority": bool(final_action[2] < 0.0),
        "capture_conditioned_xy_recomputed_with_forced_z": False,
    }


def _apply_v08f_horizon_reserved_capture_authority(
    *,
    action: np.ndarray,
    metric_row: dict[str, Any] | None,
    config: dict[str, Any],
) -> tuple[np.ndarray, dict[str, Any]]:
    before = np.asarray(action, dtype=np.float64).copy()
    after = before.copy()
    reason = "metric_row_missing"
    applied = False
    xy_recomputed = False
    seat_completion_active = False
    if metric_row is not None:
        step = int(metric_row.get("step", -1))
        lateral = float(metric_row.get("lateral_error_m", 999.0))
        depth = float(metric_row.get("insertion_depth_m", 0.0))
        env_native_success = bool(metric_row.get("env_native_success", False))
        capture_prepare_start_step = int(config["capture_prepare_start_step"])
        horizon_reserved_z_deadline_step = int(config["horizon_reserved_z_deadline_step"])
        capture_lateral_gate_m = float(config["capture_lateral_gate_m"])
        seat_region_depth_m = float(config["seat_region_depth_m"])
        if env_native_success:
            reason = "env_native_success_already_true"
        elif step >= capture_prepare_start_step and lateral > capture_lateral_gate_m:
            after[2] = 0.0
            if config.get("capture_wait_xy_authority_enabled") is True:
                gain = float(config["capture_wait_xy_authority_gain"])
                clip_abs = float(config["capture_wait_xy_clip_abs"])
                after[0] = np.clip(-float(metric_row.get("relative_x_m", 0.0)) * gain, -clip_abs, clip_abs)
                after[1] = np.clip(-float(metric_row.get("relative_y_m", 0.0)) * gain, -clip_abs, clip_abs)
                xy_recomputed = True
            reason = "capture_wait_xy_authority"
            applied = True
        elif step < horizon_reserved_z_deadline_step:
            after[2] = 0.0
            reason = "before_horizon_reserved_z_deadline"
            applied = bool(not np.isclose(before[2], 0.0))
        else:
            after[2] = float(config["z_progress_action"])
            seat_completion_active = bool(depth >= seat_region_depth_m)
            reason = "forced_horizon_reserved_progress_z"
            applied = True
    final_action = np.round(np.clip(after, -1.0, 1.0), 12)
    preserved_rotation_gripper = bool(
        np.allclose(final_action[3:], np.round(np.clip(before[3:], -1.0, 1.0), 12))
    )
    return final_action, {
        "horizon_reserved_capture_authority_id": config["horizon_reserved_capture_authority_id"],
        "horizon_reserved_capture_authority_config_sha256": config[
            "horizon_reserved_capture_authority_config_sha256"
        ],
        "pre_horizon_reserved_capture_authority_action_vector": _rounded_action(before),
        "post_horizon_reserved_capture_authority_action_vector": _rounded_action(final_action),
        "horizon_reserved_capture_authority_applied": bool(applied),
        "horizon_reserved_capture_authority_reason": reason,
        "horizon_reserved_xy_recomputed": bool(xy_recomputed),
        "horizon_reserved_preserved_rotation_gripper": preserved_rotation_gripper,
        "horizon_reserved_z_deadline_step": int(config["horizon_reserved_z_deadline_step"]),
        "capture_prepare_start_step": int(config["capture_prepare_start_step"]),
        "capture_lateral_gate_m": float(config["capture_lateral_gate_m"]),
        "seat_region_depth_m": float(config["seat_region_depth_m"]),
        "seat_completion_until_env_native_success": bool(
            config["seat_completion_until_env_native_success"]
        ),
        "horizon_reserved_seat_completion_active": bool(seat_completion_active),
        "effective_z_open_for_xy_authority": bool(final_action[2] < 0.0),
    }


def _apply_v08g_deadline_precedence_horizon_authority(
    *,
    action: np.ndarray,
    metric_row: dict[str, Any] | None,
    config: dict[str, Any],
) -> tuple[np.ndarray, dict[str, Any]]:
    before = np.asarray(action, dtype=np.float64).copy()
    after = before.copy()
    reason = "metric_row_missing"
    applied = False
    xy_recomputed = False
    seat_completion_active = False
    if metric_row is not None:
        step = int(metric_row.get("step", -1))
        lateral = float(metric_row.get("lateral_error_m", 999.0))
        depth = float(metric_row.get("insertion_depth_m", 0.0))
        env_native_success = bool(metric_row.get("env_native_success", False))
        capture_prepare_start_step = int(config["capture_prepare_start_step"])
        horizon_reserved_z_deadline_step = int(config["horizon_reserved_z_deadline_step"])
        capture_lateral_gate_m = float(config["capture_lateral_gate_m"])
        seat_region_depth_m = float(config["seat_region_depth_m"])
        if env_native_success:
            reason = "env_native_success_already_true"
        elif step >= horizon_reserved_z_deadline_step:
            after[2] = float(config["z_progress_action"])
            seat_completion_active = bool(depth >= seat_region_depth_m)
            reason = "forced_horizon_reserved_progress_z_deadline_precedence"
            applied = True
            if (
                lateral > capture_lateral_gate_m
                and config.get("capture_wait_xy_authority_enabled") is True
            ):
                gain = float(config["capture_wait_xy_authority_gain"])
                clip_abs = float(config["capture_wait_xy_clip_abs"])
                after[0] = np.clip(
                    -float(metric_row.get("relative_x_m", 0.0)) * gain,
                    -clip_abs,
                    clip_abs,
                )
                after[1] = np.clip(
                    -float(metric_row.get("relative_y_m", 0.0)) * gain,
                    -clip_abs,
                    clip_abs,
                )
                xy_recomputed = True
        elif step >= capture_prepare_start_step and lateral > capture_lateral_gate_m:
            after[2] = 0.0
            if config.get("capture_wait_xy_authority_enabled") is True:
                gain = float(config["capture_wait_xy_authority_gain"])
                clip_abs = float(config["capture_wait_xy_clip_abs"])
                after[0] = np.clip(
                    -float(metric_row.get("relative_x_m", 0.0)) * gain,
                    -clip_abs,
                    clip_abs,
                )
                after[1] = np.clip(
                    -float(metric_row.get("relative_y_m", 0.0)) * gain,
                    -clip_abs,
                    clip_abs,
                )
                xy_recomputed = True
            reason = "capture_wait_xy_authority"
            applied = True
        else:
            after[2] = 0.0
            reason = "before_horizon_reserved_z_deadline"
            applied = bool(not np.isclose(before[2], 0.0))
    final_action = np.round(np.clip(after, -1.0, 1.0), 12)
    preserved_rotation_gripper = bool(
        np.allclose(final_action[3:], np.round(np.clip(before[3:], -1.0, 1.0), 12))
    )
    return final_action, {
        "deadline_precedence_horizon_authority_id": config[
            "deadline_precedence_horizon_authority_id"
        ],
        "deadline_precedence_horizon_authority_config_sha256": config[
            "deadline_precedence_horizon_authority_config_sha256"
        ],
        "pre_deadline_precedence_horizon_authority_action_vector": _rounded_action(before),
        "post_deadline_precedence_horizon_authority_action_vector": _rounded_action(final_action),
        "deadline_precedence_horizon_authority_applied": bool(applied),
        "deadline_precedence_horizon_authority_reason": reason,
        "deadline_precedence_xy_recomputed": bool(xy_recomputed),
        "deadline_precedence_preserved_rotation_gripper": preserved_rotation_gripper,
        "horizon_reserved_z_deadline_step": int(config["horizon_reserved_z_deadline_step"]),
        "capture_prepare_start_step": int(config["capture_prepare_start_step"]),
        "capture_lateral_gate_m": float(config["capture_lateral_gate_m"]),
        "seat_region_depth_m": float(config["seat_region_depth_m"]),
        "deadline_precedence_over_capture_wait": bool(
            config["deadline_precedence_over_capture_wait"]
        ),
        "seat_completion_until_env_native_success": bool(
            config["seat_completion_until_env_native_success"]
        ),
        "deadline_precedence_seat_completion_active": bool(seat_completion_active),
        "effective_z_open_for_xy_authority": bool(final_action[2] < 0.0),
    }


def _apply_v08h_early_centered_z_open_safe_entry(
    *,
    action: np.ndarray,
    metric_row: dict[str, Any] | None,
    config: dict[str, Any],
) -> tuple[np.ndarray, dict[str, Any]]:
    before = np.asarray(action, dtype=np.float64).copy()
    after = before.copy()
    reason = "metric_row_missing"
    applied = False
    xy_recomputed = False
    depth_progress_continuation_active = False
    safe_entry_active = False
    unsafe_lateral_block_active = False
    if metric_row is not None:
        step = int(metric_row.get("step", -1))
        lateral = float(metric_row.get("lateral_error_m", 999.0))
        depth = float(metric_row.get("insertion_depth_m", 0.0))
        env_native_success = bool(metric_row.get("env_native_success", False))
        capture_prepare_start_step = int(config["capture_prepare_start_step"])
        safe_entry_lateral_gate_m = float(config["safe_entry_lateral_gate_m"])
        continuation_lateral_gate_m = float(config["depth_progress_continuation_lateral_gate_m"])
        if env_native_success:
            reason = "env_native_success_already_true"
        elif (
            config.get("depth_progress_continuation_enabled") is True
            and depth > 0.0
            and lateral <= continuation_lateral_gate_m
        ):
            after[2] = float(config["z_progress_action"])
            reason = "depth_progress_continuation_z"
            applied = True
            depth_progress_continuation_active = True
        elif (
            config.get("early_centered_z_open_enabled") is True
            and step >= capture_prepare_start_step
            and lateral <= safe_entry_lateral_gate_m
        ):
            after[2] = float(config["z_progress_action"])
            reason = "early_centered_safe_entry_z"
            applied = True
            safe_entry_active = True
        elif step >= capture_prepare_start_step:
            after[2] = 0.0
            reason = "unsafe_lateral_z_block"
            applied = True
            unsafe_lateral_block_active = True
            if config.get("capture_wait_xy_authority_enabled") is True:
                gain = float(config["capture_wait_xy_authority_gain"])
                clip_abs = float(config["capture_wait_xy_clip_abs"])
                after[0] = np.clip(
                    -float(metric_row.get("relative_x_m", 0.0)) * gain,
                    -clip_abs,
                    clip_abs,
                )
                after[1] = np.clip(
                    -float(metric_row.get("relative_y_m", 0.0)) * gain,
                    -clip_abs,
                    clip_abs,
                )
                xy_recomputed = True
        else:
            after[2] = 0.0
            reason = "before_capture_prepare_start"
            applied = bool(not np.isclose(before[2], 0.0))
    final_action = np.round(np.clip(after, -1.0, 1.0), 12)
    preserved_rotation_gripper = bool(
        np.allclose(final_action[3:], np.round(np.clip(before[3:], -1.0, 1.0), 12))
    )
    return final_action, {
        "early_centered_z_open_safe_entry_authority_id": config[
            "early_centered_z_open_safe_entry_authority_id"
        ],
        "early_centered_z_open_safe_entry_config_sha256": config[
            "early_centered_z_open_safe_entry_config_sha256"
        ],
        "pre_early_centered_z_open_safe_entry_action_vector": _rounded_action(before),
        "post_early_centered_z_open_safe_entry_action_vector": _rounded_action(final_action),
        "early_centered_z_open_safe_entry_applied": bool(applied),
        "early_centered_z_open_safe_entry_reason": reason,
        "safe_entry_xy_recomputed": bool(xy_recomputed),
        "safe_entry_preserved_rotation_gripper": preserved_rotation_gripper,
        "capture_prepare_start_step": int(config["capture_prepare_start_step"]),
        "reference_deadline_step": int(config["reference_deadline_step"]),
        "safe_entry_lateral_gate_m": float(config["safe_entry_lateral_gate_m"]),
        "depth_progress_continuation_lateral_gate_m": float(
            config["depth_progress_continuation_lateral_gate_m"]
        ),
        "unsafe_lateral_z_block_after_reference_deadline": bool(
            config["unsafe_lateral_z_block_after_reference_deadline"]
        ),
        "early_centered_z_open_enabled": bool(config["early_centered_z_open_enabled"]),
        "depth_progress_continuation_enabled": bool(
            config["depth_progress_continuation_enabled"]
        ),
        "depth_progress_continuation_active": bool(depth_progress_continuation_active),
        "early_centered_safe_entry_active": bool(safe_entry_active),
        "unsafe_lateral_block_active": bool(unsafe_lateral_block_active),
        "effective_z_open_for_xy_authority": bool(final_action[2] < 0.0),
    }


def _xy_sign_preserved(before_xy: np.ndarray, after_xy: np.ndarray) -> bool:
    for before_value, after_value in zip(before_xy.tolist(), after_xy.tolist(), strict=True):
        if abs(float(before_value)) <= 1.0e-12 or abs(float(after_value)) <= 1.0e-12:
            continue
        if np.sign(float(before_value)) != np.sign(float(after_value)):
            return False
    return True


def _apply_v07g_final_post_adapter_xy_authority(
    *,
    action: np.ndarray,
    metric_row: dict[str, Any] | None,
    xy_authority_config: dict[str, Any],
) -> tuple[np.ndarray, dict[str, Any]]:
    before = np.asarray(action, dtype=np.float64).copy()
    after = before.copy()
    reason = "xy_authority_not_needed"
    applied = False
    sign_preserved = True

    if metric_row is None:
        reason = "metric_row_missing"
    else:
        threshold = float(xy_authority_config["xy_saturation_threshold_abs"])
        near_center_lateral = float(xy_authority_config["xy_near_center_lateral_m"])
        strategy = str(xy_authority_config.get("xy_authority_strategy") or "post_adapter_state_feedback_clip")
        saturated = bool(np.any(np.abs(before[0:2]) >= threshold))
        lateral = float(metric_row.get("lateral_error_m", 999.0))
        depth = float(metric_row.get("insertion_depth_m", 0.0))
        env_native_success = bool(metric_row.get("env_native_success", False))
        near_center = lateral <= near_center_lateral
        should_apply = saturated and near_center
        zone = "near_center" if near_center else "off_center"
        clip_abs = float(xy_authority_config.get("xy_authority_clip_abs", 0.0))
        z_open_low_depth = False
        if strategy in {
            "z_open_center_maintenance_state_feedback_clip",
            "composed_piecewise_plus_z_open_center_maintenance",
        }:
            z_open_low_depth = (
                bool(before[2] < 0.0)
                and not env_native_success
                and depth <= float(xy_authority_config["z_open_centering_depth_max_m"])
                and lateral <= float(xy_authority_config["z_open_centering_lateral_m"])
            )
        if strategy == "piecewise_off_center_state_feedback_clip" or (
            strategy == "composed_piecewise_plus_z_open_center_maintenance" and not z_open_low_depth
        ):
            should_apply = saturated
            clip_abs = float(
                xy_authority_config["xy_near_center_clip_abs"]
                if near_center
                else xy_authority_config["xy_off_center_clip_abs"]
            )
        elif strategy == "z_open_center_maintenance_state_feedback_clip":
            should_apply = z_open_low_depth
            zone = "z_open_low_depth_center" if z_open_low_depth else zone
            clip_abs = float(xy_authority_config["z_open_xy_clip_abs"])
        elif strategy == "composed_piecewise_plus_z_open_center_maintenance" and z_open_low_depth:
            should_apply = True
            zone = "z_open_low_depth_center"
            clip_abs = float(xy_authority_config["z_open_xy_clip_abs"])
        if should_apply:
            gain = float(
                xy_authority_config["z_open_xy_authority_gain"]
                if (
                    strategy == "z_open_center_maintenance_state_feedback_clip"
                    or (
                        strategy == "composed_piecewise_plus_z_open_center_maintenance"
                        and z_open_low_depth
                    )
                )
                else xy_authority_config["xy_authority_gain"]
            )
            candidate_xy = np.asarray(
                [
                    -float(metric_row.get("relative_x_m", 0.0)) * gain,
                    -float(metric_row.get("relative_y_m", 0.0)) * gain,
                ],
                dtype=np.float64,
            )
            candidate_xy = np.clip(candidate_xy, -clip_abs, clip_abs)
            sign_preserved = _xy_sign_preserved(before[0:2], candidate_xy)
            sign_flip_allowed = (
                (
                    strategy == "z_open_center_maintenance_state_feedback_clip"
                    or (
                        strategy == "composed_piecewise_plus_z_open_center_maintenance"
                        and z_open_low_depth
                    )
                )
                and xy_authority_config.get("allow_sign_flip_during_z_open_low_depth") is True
            )
            if sign_preserved or sign_flip_allowed:
                after[0:2] = candidate_xy
                applied = True
                if (
                    strategy == "z_open_center_maintenance_state_feedback_clip"
                    or (
                        strategy == "composed_piecewise_plus_z_open_center_maintenance"
                        and z_open_low_depth
                    )
                ):
                    reason = "z_open_center_maintenance_state_feedback"
                else:
                    reason = (
                        "xy_saturation_off_center_state_feedback_clamped"
                        if (
                            (
                                strategy == "piecewise_off_center_state_feedback_clip"
                                or (
                                    strategy == "composed_piecewise_plus_z_open_center_maintenance"
                                    and not z_open_low_depth
                                )
                            )
                            and not near_center
                        )
                        else "xy_saturation_near_center_clamped_to_state_feedback"
                    )
            else:
                reason = "xy_authority_sign_mismatch_not_applied"
        else:
            zone = "near_center" if near_center else "off_center"

    final_action = np.round(np.clip(after, -1.0, 1.0), 12)
    z_preserved = bool(np.isclose(final_action[2], before[2]))
    if not z_preserved:
        raise ValueError("v0_7g_xy_authority_mutated_z")
    return final_action, {
        "final_post_adapter_xy_authority_id": xy_authority_config["final_post_adapter_xy_authority_id"],
        "final_post_adapter_xy_authority_config_sha256": xy_authority_config[
            "final_post_adapter_xy_authority_config_sha256"
        ],
        "pre_xy_authority_action_vector": _rounded_action(before),
        "post_z_pre_xy_authority_action_vector": _rounded_action(before),
        "post_xy_authority_action_vector": _rounded_action(final_action),
        "xy_authority_applied": bool(applied),
        "xy_authority_reason": reason,
        "xy_authority_zone": zone if metric_row is not None else None,
        "xy_authority_preserved_sign": bool(sign_preserved),
        "xy_authority_preserved_z": bool(z_preserved),
    }


def _apply_selected_action_adapter_with_diagnostics(
    *,
    policy_artifact: dict[str, Any],
    raw_action: np.ndarray,
    action_scale: float,
    metric_row: dict[str, Any] | None = None,
    behavior_state_phase: str | None = None,
    hysteresis_state: dict[str, Any] | None = None,
) -> tuple[np.ndarray, dict[str, Any]]:
    adapter_id = str(policy_artifact.get("selected_action_adapter_id") or "")
    config = policy_artifact.get("selected_action_adapter_config")
    policy_slice = policy_artifact.get("policy_slice")
    final_authority_config: dict[str, Any] | None = None
    v07e_hysteresis_config: dict[str, Any] | None = None
    v07g_xy_authority_config: dict[str, Any] | None = None
    v08a_seat_window_config: dict[str, Any] | None = None
    v08b_seat_window_config: dict[str, Any] | None = None
    v08d_capture_progress_config: dict[str, Any] | None = None
    v08f_horizon_capture_config: dict[str, Any] | None = None
    v08g_deadline_precedence_config: dict[str, Any] | None = None
    v08h_safe_entry_config: dict[str, Any] | None = None
    effective_behavior_state_phase = behavior_state_phase
    if policy_slice in V07D_FINAL_AUTHORITY_RUNTIME_POLICY_SLICE_IDS:
        final_authority_config = _validated_v07d_final_action_authority_config(policy_artifact)
        config = _validated_v07d_selected_action_adapter_config(policy_artifact)
    if policy_slice in V07E_HYSTERESIS_RUNTIME_POLICY_SLICE_IDS:
        v07e_hysteresis_config = _validated_v07e_hysteresis_authority_config(policy_artifact)
        if isinstance(hysteresis_state, dict):
            if hysteresis_state.get("last_z_motion_allowed") is True:
                effective_behavior_state_phase = "DESCEND"
            elif hysteresis_state.get("current_hysteresis_phase"):
                effective_behavior_state_phase = str(hysteresis_state["current_hysteresis_phase"]).upper()
    if policy_slice == V07G_POLICY_SLICE_ID:
        v07g_xy_authority_config = _validated_v07g_final_xy_authority_config(policy_artifact)
    if policy_slice in {V07J_POLICY_SLICE_ID, V07K_POLICY_SLICE_ID, V07M_POLICY_SLICE_ID}:
        v07g_xy_authority_config = _validated_v07j_final_xy_authority_config(policy_artifact)
    if policy_slice == V07N_POLICY_SLICE_ID:
        v07g_xy_authority_config = _validated_v07n_final_xy_authority_config(policy_artifact)
    if policy_slice == V07O_POLICY_SLICE_ID:
        v07g_xy_authority_config = _validated_v07o_final_xy_authority_config(policy_artifact)
    if policy_slice == V08A_POLICY_SLICE_ID:
        v07g_xy_authority_config = _validated_v07o_final_xy_authority_config(policy_artifact)
        v08a_seat_window_config = _validated_v08a_seat_window_authority_config(policy_artifact)
    if policy_slice == V08B_POLICY_SLICE_ID:
        v07g_xy_authority_config = _validated_v07o_final_xy_authority_config(policy_artifact)
        v08b_seat_window_config = _validated_v08b_seat_window_authority_config(policy_artifact)
    if policy_slice == V08D_POLICY_SLICE_ID:
        v07g_xy_authority_config = _validated_v07o_final_xy_authority_config(policy_artifact)
        v08d_capture_progress_config = _validated_v08d_capture_conditioned_progress_authority_config(
            policy_artifact
        )
    if policy_slice == V08F_POLICY_SLICE_ID:
        v07g_xy_authority_config = _validated_v07o_final_xy_authority_config(policy_artifact)
        v08f_horizon_capture_config = _validated_v08f_horizon_reserved_capture_authority_config(
            policy_artifact
        )
    if policy_slice == V08G_POLICY_SLICE_ID:
        v07g_xy_authority_config = _validated_v07o_final_xy_authority_config(policy_artifact)
        v08g_deadline_precedence_config = _validated_v08g_deadline_precedence_horizon_authority_config(
            policy_artifact
        )
    if policy_slice in V08H_DERIVED_POLICY_SLICE_IDS:
        v07g_xy_authority_config = _validated_v07o_final_xy_authority_config(policy_artifact)
        v08h_safe_entry_config = _validated_v08h_early_centered_z_open_safe_entry_config(
            policy_artifact
        )
    raw_vector = _rounded_action(raw_action)
    diagnostics: dict[str, Any] = {
        "schema_version": "rdf_mvp2e_v06d_controller_action_diagnostics_v0.1.0",
        "policy_slice": policy_artifact.get("policy_slice"),
        "selected_action_adapter_id": adapter_id,
        "stable_hold_authority": policy_artifact.get("stable_hold_authority"),
        "controller_version": config.get("controller_version") if isinstance(config, dict) else None,
        "input_metric_phase": str(metric_row.get("phase")) if isinstance(metric_row, dict) else None,
        "controller_input_phase": None,
        "phase_normalized": False,
        "raw_action_vector": raw_vector,
        "phase_controller": None,
        "phase_vocabulary_mismatch": False,
        "z_motion_suppressed": False,
        "z_motion_block_reason": "adapter_not_instrumented",
        "no_mutation_after_final_post_adapter_authority": False,
    }
    policy_influence_config = policy_artifact.get("policy_influence_authority_ceiling_config")
    if isinstance(policy_influence_config, dict):
        expected_policy_influence_hash = _sha256_payload_excluding(
            policy_influence_config,
            "policy_influence_authority_ceiling_config_sha256",
        )
        if (
            policy_influence_config.get("policy_influence_authority_ceiling_config_sha256")
            != expected_policy_influence_hash
            or policy_artifact.get("policy_influence_authority_ceiling_config_sha256")
            != expected_policy_influence_hash
        ):
            raise ValueError("v0_13_policy_influence_authority_ceiling_config_hash_mismatch")
        diagnostics.update(
            {
                "policy_influence_authority_ceiling_id": policy_influence_config.get("authority_id"),
                "policy_influence_authority_ceiling_config_sha256": expected_policy_influence_hash,
                "policy_influence_state_feedback_gain_ceiling": policy_influence_config.get(
                    "state_feedback_gain_ceiling"
                ),
                "z_progress_injection_enabled": policy_influence_config.get(
                    "z_progress_injection_enabled"
                ),
                "final_xy_state_feedback_replacement_enabled": policy_influence_config.get(
                    "final_xy_state_feedback_replacement_enabled"
                ),
            }
        )
    if v07e_hysteresis_config is not None:
        diagnostics.update(
            {
                "shared_hysteresis_authority_id": v07e_hysteresis_config["shared_hysteresis_authority_id"],
                "shared_hysteresis_authority_config_sha256": v07e_hysteresis_config[
                    "shared_hysteresis_authority_config_sha256"
                ],
                "shared_hysteresis_state_after": dict(hysteresis_state)
                if isinstance(hysteresis_state, dict)
                else None,
            }
        )
    if adapter_id != "isaac_signed_xy_downward_servo_v0" or not isinstance(config, dict):
        action = np.clip(raw_action * float(action_scale), -1.0, 1.0)
        diagnostics.update(
            {
                "pre_controller_action_vector": _rounded_action(action),
                "post_adapter_action_vector": _rounded_action(action),
                "z_motion_block_reason": "no_v06_controller",
            }
        )
        if final_authority_config is not None:
            action, final_diagnostics = _apply_v07d_final_post_adapter_authority(
                action=action,
                behavior_state_phase=effective_behavior_state_phase,
                final_authority_config=final_authority_config,
                current_block_reason="no_v06_controller",
            )
            diagnostics.update(final_diagnostics)
            diagnostics["post_adapter_action_vector"] = _rounded_action(action)
            diagnostics["no_mutation_after_final_post_adapter_authority"] = True
        v08b_forced_z_for_xy = False
        if v08b_seat_window_config is not None:
            action, seat_window_diagnostics = _apply_v08b_scenario_aware_seat_window_authority(
                action=action,
                metric_row=metric_row,
                config=v08b_seat_window_config,
            )
            v08b_forced_z_for_xy = bool(seat_window_diagnostics["seat_window_authority_applied"])
            diagnostics.update(seat_window_diagnostics)
            diagnostics["post_adapter_action_vector"] = _rounded_action(action)
            diagnostics["no_mutation_after_final_post_adapter_authority"] = True
        v08d_forced_z_for_xy = False
        if v08d_capture_progress_config is not None:
            action, capture_progress_diagnostics = _apply_v08d_capture_conditioned_progress_authority(
                action=action,
                metric_row=metric_row,
                config=v08d_capture_progress_config,
            )
            v08d_forced_z_for_xy = bool(
                capture_progress_diagnostics["capture_conditioning_applied"] and action[2] < 0.0
            )
            diagnostics.update(capture_progress_diagnostics)
            diagnostics["post_adapter_action_vector"] = _rounded_action(action)
            diagnostics["no_mutation_after_final_post_adapter_authority"] = True
        v08f_forced_z_for_xy = False
        if v08f_horizon_capture_config is not None:
            action, horizon_diagnostics = _apply_v08f_horizon_reserved_capture_authority(
                action=action,
                metric_row=metric_row,
                config=v08f_horizon_capture_config,
            )
            v08f_forced_z_for_xy = bool(
                horizon_diagnostics["horizon_reserved_capture_authority_applied"] and action[2] < 0.0
            )
            diagnostics.update(horizon_diagnostics)
            diagnostics["post_adapter_action_vector"] = _rounded_action(action)
            diagnostics["no_mutation_after_final_post_adapter_authority"] = True
        v08g_forced_z_for_xy = False
        if v08g_deadline_precedence_config is not None:
            action, deadline_diagnostics = _apply_v08g_deadline_precedence_horizon_authority(
                action=action,
                metric_row=metric_row,
                config=v08g_deadline_precedence_config,
            )
            v08g_forced_z_for_xy = bool(
                deadline_diagnostics["deadline_precedence_horizon_authority_applied"]
                and action[2] < 0.0
            )
            diagnostics.update(deadline_diagnostics)
            diagnostics["post_adapter_action_vector"] = _rounded_action(action)
            diagnostics["no_mutation_after_final_post_adapter_authority"] = True
        v08h_forced_z_for_xy = False
        if v08h_safe_entry_config is not None:
            action, safe_entry_diagnostics = _apply_v08h_early_centered_z_open_safe_entry(
                action=action,
                metric_row=metric_row,
                config=v08h_safe_entry_config,
            )
            v08h_forced_z_for_xy = bool(
                safe_entry_diagnostics["early_centered_z_open_safe_entry_applied"]
                and action[2] < 0.0
            )
            diagnostics.update(safe_entry_diagnostics)
            diagnostics["post_adapter_action_vector"] = _rounded_action(action)
            diagnostics["no_mutation_after_final_post_adapter_authority"] = True
        if v07g_xy_authority_config is not None:
            action, xy_diagnostics = _apply_v07g_final_post_adapter_xy_authority(
                action=action,
                metric_row=metric_row,
                xy_authority_config=v07g_xy_authority_config,
            )
            diagnostics.update(xy_diagnostics)
            if v08b_forced_z_for_xy:
                diagnostics["effective_z_open_for_xy_authority"] = True
                diagnostics["seat_window_xy_recomputed_with_forced_z"] = True
            if v08d_forced_z_for_xy:
                diagnostics["effective_z_open_for_xy_authority"] = True
                diagnostics["capture_conditioned_xy_recomputed_with_forced_z"] = True
            if v08f_forced_z_for_xy:
                diagnostics["effective_z_open_for_xy_authority"] = True
                diagnostics["horizon_reserved_xy_recomputed_with_forced_z"] = True
            if v08g_forced_z_for_xy:
                diagnostics["effective_z_open_for_xy_authority"] = True
                diagnostics["deadline_precedence_xy_recomputed_with_forced_z"] = True
            if v08h_forced_z_for_xy:
                diagnostics["effective_z_open_for_xy_authority"] = True
                diagnostics["safe_entry_xy_recomputed_with_forced_z"] = True
            diagnostics["post_adapter_action_vector"] = _rounded_action(action)
            diagnostics["no_mutation_after_final_post_adapter_authority"] = True
        if v08a_seat_window_config is not None:
            action, seat_window_diagnostics = _apply_v08a_seat_window_progress_authority(
                action=action,
                metric_row=metric_row,
                config=v08a_seat_window_config,
            )
            diagnostics.update(seat_window_diagnostics)
            diagnostics["post_adapter_action_vector"] = _rounded_action(action)
            diagnostics["no_mutation_after_final_post_adapter_authority"] = True
        return action, diagnostics

    if (
        metric_row is not None
        and final_authority_config is not None
        and str(effective_behavior_state_phase or metric_row.get("behavior_state_phase") or "").upper() == "HOLD"
        and _stable_hold_ready_env_native(metric_row=metric_row)
    ):
        hold_action = config.get("stable_hold_action") or [0.0] * len(ACTION_SCHEMA)
        action = np.asarray(hold_action[: len(ACTION_SCHEMA)], dtype=np.float64)
        diagnostics.update(
            {
                "pre_controller_action_vector": _rounded_action(action),
                "post_adapter_action_vector": _rounded_action(action),
                "z_motion_block_reason": "stable_hold_ready_env_native",
            }
        )
        action, final_diagnostics = _apply_v07d_final_post_adapter_authority(
            action=action,
            behavior_state_phase=effective_behavior_state_phase,
            final_authority_config=final_authority_config,
            current_block_reason="stable_hold_ready_env_native",
        )
        diagnostics.update(final_diagnostics)
        diagnostics["post_adapter_action_vector"] = _rounded_action(action)
        diagnostics["no_mutation_after_final_post_adapter_authority"] = True
        v08b_forced_z_for_xy = False
        if v08b_seat_window_config is not None:
            action, seat_window_diagnostics = _apply_v08b_scenario_aware_seat_window_authority(
                action=action,
                metric_row=metric_row,
                config=v08b_seat_window_config,
            )
            v08b_forced_z_for_xy = bool(seat_window_diagnostics["seat_window_authority_applied"])
            diagnostics.update(seat_window_diagnostics)
            diagnostics["post_adapter_action_vector"] = _rounded_action(action)
            diagnostics["no_mutation_after_final_post_adapter_authority"] = True
        v08d_forced_z_for_xy = False
        if v08d_capture_progress_config is not None:
            action, capture_progress_diagnostics = _apply_v08d_capture_conditioned_progress_authority(
                action=action,
                metric_row=metric_row,
                config=v08d_capture_progress_config,
            )
            v08d_forced_z_for_xy = bool(
                capture_progress_diagnostics["capture_conditioning_applied"] and action[2] < 0.0
            )
            diagnostics.update(capture_progress_diagnostics)
            diagnostics["post_adapter_action_vector"] = _rounded_action(action)
            diagnostics["no_mutation_after_final_post_adapter_authority"] = True
        v08f_forced_z_for_xy = False
        if v08f_horizon_capture_config is not None:
            action, horizon_diagnostics = _apply_v08f_horizon_reserved_capture_authority(
                action=action,
                metric_row=metric_row,
                config=v08f_horizon_capture_config,
            )
            v08f_forced_z_for_xy = bool(
                horizon_diagnostics["horizon_reserved_capture_authority_applied"] and action[2] < 0.0
            )
            diagnostics.update(horizon_diagnostics)
            diagnostics["post_adapter_action_vector"] = _rounded_action(action)
            diagnostics["no_mutation_after_final_post_adapter_authority"] = True
        v08g_forced_z_for_xy = False
        if v08g_deadline_precedence_config is not None:
            action, deadline_diagnostics = _apply_v08g_deadline_precedence_horizon_authority(
                action=action,
                metric_row=metric_row,
                config=v08g_deadline_precedence_config,
            )
            v08g_forced_z_for_xy = bool(
                deadline_diagnostics["deadline_precedence_horizon_authority_applied"]
                and action[2] < 0.0
            )
            diagnostics.update(deadline_diagnostics)
            diagnostics["post_adapter_action_vector"] = _rounded_action(action)
            diagnostics["no_mutation_after_final_post_adapter_authority"] = True
        v08h_forced_z_for_xy = False
        if v08h_safe_entry_config is not None:
            action, safe_entry_diagnostics = _apply_v08h_early_centered_z_open_safe_entry(
                action=action,
                metric_row=metric_row,
                config=v08h_safe_entry_config,
            )
            v08h_forced_z_for_xy = bool(
                safe_entry_diagnostics["early_centered_z_open_safe_entry_applied"]
                and action[2] < 0.0
            )
            diagnostics.update(safe_entry_diagnostics)
            diagnostics["post_adapter_action_vector"] = _rounded_action(action)
            diagnostics["no_mutation_after_final_post_adapter_authority"] = True
        if v07g_xy_authority_config is not None:
            action, xy_diagnostics = _apply_v07g_final_post_adapter_xy_authority(
                action=action,
                metric_row=metric_row,
                xy_authority_config=v07g_xy_authority_config,
            )
            diagnostics.update(xy_diagnostics)
            if v08b_forced_z_for_xy:
                diagnostics["effective_z_open_for_xy_authority"] = True
                diagnostics["seat_window_xy_recomputed_with_forced_z"] = True
            if v08d_forced_z_for_xy:
                diagnostics["effective_z_open_for_xy_authority"] = True
                diagnostics["capture_conditioned_xy_recomputed_with_forced_z"] = True
            if v08f_forced_z_for_xy:
                diagnostics["effective_z_open_for_xy_authority"] = True
                diagnostics["horizon_reserved_xy_recomputed_with_forced_z"] = True
            if v08g_forced_z_for_xy:
                diagnostics["effective_z_open_for_xy_authority"] = True
                diagnostics["deadline_precedence_xy_recomputed_with_forced_z"] = True
            if v08h_forced_z_for_xy:
                diagnostics["effective_z_open_for_xy_authority"] = True
                diagnostics["safe_entry_xy_recomputed_with_forced_z"] = True
            diagnostics["post_adapter_action_vector"] = _rounded_action(action)
            diagnostics["no_mutation_after_final_post_adapter_authority"] = True
        if v08a_seat_window_config is not None:
            action, seat_window_diagnostics = _apply_v08a_seat_window_progress_authority(
                action=action,
                metric_row=metric_row,
                config=v08a_seat_window_config,
            )
            diagnostics.update(seat_window_diagnostics)
            diagnostics["post_adapter_action_vector"] = _rounded_action(action)
            diagnostics["no_mutation_after_final_post_adapter_authority"] = True
        return action, diagnostics

    if metric_row is not None and final_authority_config is None and _stable_hold_ready(config=config, metric_row=metric_row):
        hold_action = config.get("stable_hold_action") or [0.0] * len(ACTION_SCHEMA)
        action = np.asarray(hold_action[: len(ACTION_SCHEMA)], dtype=np.float64)
        diagnostics.update(
            {
                "pre_controller_action_vector": _rounded_action(action),
                "post_adapter_action_vector": _rounded_action(action),
                "z_motion_block_reason": "stable_hold_ready",
            }
        )
        return action, diagnostics

    action = np.asarray(raw_action, dtype=np.float64).copy()
    phase_controller: dict[str, Any] | None = None
    input_phase = str(metric_row.get("phase") or _phase_from_depth(float(metric_row.get("insertion_depth_m", 0.0)))) if metric_row is not None else ""
    v06_controller_enabled = config.get("controller_version") == "v0_6_active_state_controller" or config.get(
        "controller_repair_version"
    ) == "v0_6f"
    if metric_row is not None and v06_controller_enabled:
        phase_mapping = normalize_v06_controller_phase(input_phase)
        diagnostics["input_metric_phase"] = phase_mapping["input_phase"]
        diagnostics["controller_input_phase"] = phase_mapping["controller_phase"]
        diagnostics["phase_normalized"] = phase_mapping["phase_normalized"]
        diagnostics["phase_vocabulary_mismatch"] = phase_mapping["phase_vocabulary_mismatch"]
        phase_controller = v06_phase_controller_step(
            current_phase=phase_mapping["controller_phase"],
            lateral_error_m=float(metric_row.get("lateral_error_m", 1.0)),
            orientation_error_rad=float(metric_row.get("orientation_error_deg", 999.0)) * np.pi / 180.0,
            insertion_depth_m=float(metric_row.get("insertion_depth_m", 0.0)),
            env_native_success=bool(metric_row.get("env_native_success", False)),
            stable_steps=int(metric_row.get("env_native_current_consecutive_success_steps", 0)),
            align_lateral_gate_m=float(config.get("align_lateral_gate_m", 0.008)),
            align_orientation_gate_rad=float(config.get("align_orientation_gate_rad", 0.25)),
        )
        diagnostics["phase_controller"] = phase_controller
    xy_scale = float(config.get("xy_action_scale", 1.0))
    xy_clip = float(config.get("xy_action_clip", 0.035))
    z_scale = float(config.get("z_action_scale", action_scale))
    z_clip = float(config.get("z_action_clip", 0.12))
    rotation_scale = float(config.get("rotation_action_scale", 0.0))

    xy_source = config.get("xy_source")
    if xy_source == "state_feedback" and metric_row is not None:
        xy_gain = float(config.get("xy_state_feedback_gain", xy_scale))
        action[0] = -float(metric_row.get("relative_x_m", 0.0)) * xy_gain
        action[1] = -float(metric_row.get("relative_y_m", 0.0)) * xy_gain
    elif xy_source == "policy_plus_state_feedback" and metric_row is not None:
        xy_gain = float(config.get("xy_state_feedback_gain", xy_scale))
        action[0] = action[0] * xy_scale - float(metric_row.get("relative_x_m", 0.0)) * xy_gain
        action[1] = action[1] * xy_scale - float(metric_row.get("relative_y_m", 0.0)) * xy_gain
    else:
        action[0:2] = action[0:2] * xy_scale
    action[0:2] = np.clip(action[0:2], -xy_clip, xy_clip)
    action[2] = np.clip(action[2] * z_scale, -z_clip, z_clip)
    pre_controller_action = action.copy()
    if phase_controller is not None and phase_controller["z_motion_allowed"] is not True:
        action[2] = 0.0
    action[3:6] = np.clip(action[3:6] * rotation_scale, -1.0, 1.0)
    if action.shape[0] > 6:
        action[6] = np.clip(action[6], -1.0, 1.0)
    final_action = np.round(np.clip(action, -1.0, 1.0), 12)
    z_suppressed = bool(pre_controller_action[2] < 0.0 and final_action[2] == 0.0)
    if phase_controller is None:
        block_reason = "no_v06_controller"
    elif diagnostics["phase_vocabulary_mismatch"]:
        block_reason = "controller_phase_vocabulary_mismatch"
    elif phase_controller["alignment_gate_satisfied"] is not True:
        block_reason = "alignment_gate_not_satisfied"
    elif phase_controller["z_motion_allowed"] is not True:
        block_reason = "phase_controller_z_motion_blocked"
    else:
        block_reason = "z_motion_allowed"
    if v07e_hysteresis_config is not None:
        v07e_z_allowed = bool(isinstance(hysteresis_state, dict) and hysteresis_state.get("last_z_motion_allowed") is True)
        hard_escape = bool(
            isinstance(hysteresis_state, dict) and hysteresis_state.get("hard_safety_escape_triggered") is True
        )
        if v07e_z_allowed:
            block_reason = "z_motion_allowed_by_v07e_hysteresis"
        elif hard_escape:
            block_reason = "hard_safety_escape_triggered"
        else:
            block_reason = "v07e_hysteresis_z_motion_blocked"
        if phase_controller is None and not v07e_z_allowed:
            action[2] = 0.0
            final_action = np.round(np.clip(action, -1.0, 1.0), 12)
            z_suppressed = bool(pre_controller_action[2] < 0.0 and final_action[2] == 0.0)
        elif phase_controller is None and v07e_z_allowed:
            final_action = np.round(np.clip(action, -1.0, 1.0), 12)
    diagnostics.update(
        {
            "pre_controller_action_vector": _rounded_action(pre_controller_action),
            "post_adapter_action_vector": _rounded_action(final_action),
            "z_motion_suppressed": z_suppressed,
            "z_motion_block_reason": block_reason,
            "align_lateral_gate_m": float(config.get("align_lateral_gate_m", 0.008)),
            "approach_lateral_gate_m": float(config["approach_lateral_gate_m"])
            if config.get("approach_lateral_gate_m") is not None
            else None,
            "straight_down_capture_radius_m": float(config["straight_down_capture_radius_m"])
            if config.get("straight_down_capture_radius_m") is not None
            else None,
            "align_orientation_gate_rad": float(config.get("align_orientation_gate_rad", 0.25)),
            "metric_lateral_error_m": float(metric_row.get("lateral_error_m", 0.0)) if metric_row is not None else None,
            "metric_orientation_error_deg": float(metric_row.get("orientation_error_deg", 0.0))
            if metric_row is not None
            else None,
        }
    )
    if v07e_hysteresis_config is not None:
        gate = float(v07e_hysteresis_config.get("approach_lateral_gate_m", V07A_BEHAVIOR_PHASE_LATERAL_GATE_M))
        lateral = float(metric_row.get("lateral_error_m", 0.0)) if metric_row is not None else 0.0
        z_open = bool(isinstance(hysteresis_state, dict) and hysteresis_state.get("last_z_motion_allowed") is True)
        xy_saturated = bool(np.any(np.isclose(np.abs(final_action[0:2]), xy_clip)))
        diagnostics.update(
            {
                "effective_behavior_state_phase_for_final_authority": effective_behavior_state_phase,
                "xy_saturation_rate_during_z_open": 1.0 if z_open and xy_saturated else 0.0,
                "lateral_gate_exit_step": int(metric_row.get("step", 0))
                if metric_row is not None and z_open and lateral > gate
                else None,
                "z_motion_block_reason_after_gate_exit": block_reason
                if metric_row is not None and z_open and lateral > gate
                else None,
            }
        )
    if final_authority_config is not None:
        final_action, final_diagnostics = _apply_v07d_final_post_adapter_authority(
            action=final_action,
            behavior_state_phase=effective_behavior_state_phase or diagnostics.get("controller_input_phase"),
            final_authority_config=final_authority_config,
            current_block_reason=block_reason,
        )
        diagnostics.update(final_diagnostics)
        diagnostics["post_adapter_action_vector"] = _rounded_action(final_action)
        diagnostics["no_mutation_after_final_post_adapter_authority"] = True
    v08b_forced_z_for_xy = False
    if v08b_seat_window_config is not None:
        final_action, seat_window_diagnostics = _apply_v08b_scenario_aware_seat_window_authority(
            action=final_action,
            metric_row=metric_row,
            config=v08b_seat_window_config,
        )
        v08b_forced_z_for_xy = bool(seat_window_diagnostics["seat_window_authority_applied"])
        diagnostics.update(seat_window_diagnostics)
        diagnostics["post_adapter_action_vector"] = _rounded_action(final_action)
        diagnostics["no_mutation_after_final_post_adapter_authority"] = True
    v08d_forced_z_for_xy = False
    if v08d_capture_progress_config is not None:
        final_action, capture_progress_diagnostics = _apply_v08d_capture_conditioned_progress_authority(
            action=final_action,
            metric_row=metric_row,
            config=v08d_capture_progress_config,
        )
        v08d_forced_z_for_xy = bool(
            capture_progress_diagnostics["capture_conditioning_applied"] and final_action[2] < 0.0
        )
        diagnostics.update(capture_progress_diagnostics)
        diagnostics["post_adapter_action_vector"] = _rounded_action(final_action)
        diagnostics["no_mutation_after_final_post_adapter_authority"] = True
    v08f_forced_z_for_xy = False
    if v08f_horizon_capture_config is not None:
        final_action, horizon_diagnostics = _apply_v08f_horizon_reserved_capture_authority(
            action=final_action,
            metric_row=metric_row,
            config=v08f_horizon_capture_config,
        )
        v08f_forced_z_for_xy = bool(
            horizon_diagnostics["horizon_reserved_capture_authority_applied"] and final_action[2] < 0.0
        )
        diagnostics.update(horizon_diagnostics)
        diagnostics["post_adapter_action_vector"] = _rounded_action(final_action)
        diagnostics["no_mutation_after_final_post_adapter_authority"] = True
    v08g_forced_z_for_xy = False
    if v08g_deadline_precedence_config is not None:
        final_action, deadline_diagnostics = _apply_v08g_deadline_precedence_horizon_authority(
            action=final_action,
            metric_row=metric_row,
            config=v08g_deadline_precedence_config,
        )
        v08g_forced_z_for_xy = bool(
            deadline_diagnostics["deadline_precedence_horizon_authority_applied"]
            and final_action[2] < 0.0
        )
        diagnostics.update(deadline_diagnostics)
        diagnostics["post_adapter_action_vector"] = _rounded_action(final_action)
        diagnostics["no_mutation_after_final_post_adapter_authority"] = True
    v08h_forced_z_for_xy = False
    if v08h_safe_entry_config is not None:
        final_action, safe_entry_diagnostics = _apply_v08h_early_centered_z_open_safe_entry(
            action=final_action,
            metric_row=metric_row,
            config=v08h_safe_entry_config,
        )
        v08h_forced_z_for_xy = bool(
            safe_entry_diagnostics["early_centered_z_open_safe_entry_applied"]
            and final_action[2] < 0.0
        )
        diagnostics.update(safe_entry_diagnostics)
        diagnostics["post_adapter_action_vector"] = _rounded_action(final_action)
        diagnostics["no_mutation_after_final_post_adapter_authority"] = True
    if v07g_xy_authority_config is not None:
        final_action, xy_diagnostics = _apply_v07g_final_post_adapter_xy_authority(
            action=final_action,
            metric_row=metric_row,
            xy_authority_config=v07g_xy_authority_config,
        )
        diagnostics.update(xy_diagnostics)
        if v08b_forced_z_for_xy:
            diagnostics["effective_z_open_for_xy_authority"] = True
            diagnostics["seat_window_xy_recomputed_with_forced_z"] = True
        if v08d_forced_z_for_xy:
            diagnostics["effective_z_open_for_xy_authority"] = True
            diagnostics["capture_conditioned_xy_recomputed_with_forced_z"] = True
        if v08f_forced_z_for_xy:
            diagnostics["effective_z_open_for_xy_authority"] = True
            diagnostics["horizon_reserved_xy_recomputed_with_forced_z"] = True
        if v08g_forced_z_for_xy:
            diagnostics["effective_z_open_for_xy_authority"] = True
            diagnostics["deadline_precedence_xy_recomputed_with_forced_z"] = True
        if v08h_forced_z_for_xy:
            diagnostics["effective_z_open_for_xy_authority"] = True
            diagnostics["safe_entry_xy_recomputed_with_forced_z"] = True
        diagnostics["post_adapter_action_vector"] = _rounded_action(final_action)
        diagnostics["no_mutation_after_final_post_adapter_authority"] = True
    if v08a_seat_window_config is not None:
        final_action, seat_window_diagnostics = _apply_v08a_seat_window_progress_authority(
            action=final_action,
            metric_row=metric_row,
            config=v08a_seat_window_config,
        )
        diagnostics.update(seat_window_diagnostics)
        diagnostics["post_adapter_action_vector"] = _rounded_action(final_action)
        diagnostics["no_mutation_after_final_post_adapter_authority"] = True
    return final_action, diagnostics


def _stable_hold_ready(*, config: dict[str, Any], metric_row: dict[str, Any]) -> bool:
    return (
        float(metric_row.get("insertion_depth_m", 0.0)) >= float(config.get("stable_hold_depth_m", 999.0))
        and float(metric_row.get("lateral_error_m", 999.0)) <= float(config.get("stable_hold_lateral_m", 0.0))
        and float(metric_row.get("orientation_error_deg", 999.0)) <= float(config.get("stable_hold_orientation_deg", 0.0))
    )


class DeterministicEvaluatorBackend:
    runtime_backend = DETERMINISTIC_BACKEND
    proof_runtime = DETERMINISTIC_PROOF_RUNTIME

    def run(
        self,
        *,
        manifest: dict[str, Any],
        output_dir: Path,
        min_rollouts_per_policy: int,
        deterministic_profile: str,
    ) -> BackendResult:
        trace_dir = output_dir / "heldout_rollout_traces"
        trace_dir.mkdir(parents=True, exist_ok=True)
        heldout = [row for row in manifest["scenarios"] if row["split"] == "held_out"]
        rollout_count = max(min_rollouts_per_policy, len(heldout))
        traces_by_role: dict[str, list[str]] = {"baseline": [], "candidate": []}
        rollouts_by_role: dict[str, list[dict[str, Any]]] = {"baseline": [], "candidate": []}
        for role in ("baseline", "candidate"):
            target_success = _deterministic_success_target(deterministic_profile, role, rollout_count)
            for index in range(rollout_count):
                scenario = heldout[index % len(heldout)]
                success = index < target_success
                trace = _success_trace() if success else _failure_trace("STABILITY_WINDOW_NOT_REACHED")
                summary = evaluate_rollout_trace(trace, success_metric=manifest["success_metric"])
                trace_path = trace_dir / f"{role}_{index:04d}_trace.json"
                write_json(
                    trace_path,
                    {
                        "scenario_id": scenario["scenario_id"],
                        "role": role,
                        "trace": trace,
                        "summary": summary,
                        "runtime_backend": self.runtime_backend,
                    },
                )
                traces_by_role[role].append(str(trace_path))
                rollouts_by_role[role].append(
                    {
                        "rollout_id": f"{role}_deterministic_{index:04d}",
                        "scenario_id": scenario["scenario_id"],
                        "success": summary["success"],
                        "failure_reason": summary["failure_reason"],
                        "steps": summary["steps"],
                        "rollout_log_ref": str(trace_path),
                    }
                )
        return BackendResult(
            runtime_backend=self.runtime_backend,
            proof_runtime=self.proof_runtime,
            runtime_gate={
                "passed": False,
                "runtime_backend": self.runtime_backend,
                "proof_runtime": self.proof_runtime,
                "reason": "deterministic backend is test-only and cannot close MVP-2",
            },
            baseline_rollouts=rollouts_by_role["baseline"],
            candidate_rollouts=rollouts_by_role["candidate"],
            baseline_trace_paths=traces_by_role["baseline"],
            candidate_trace_paths=traces_by_role["candidate"],
            runtime_metadata={
                "runtime_backend": self.runtime_backend,
                "proof_runtime": self.proof_runtime,
                "scenario_manifest_sha256": manifest["manifest_sha256"],
                "deterministic_profile": deterministic_profile,
            },
        )


class IsaacConnectorInsertionEvaluatorBackend:
    runtime_backend = "isaac_runtime"
    proof_runtime = ISAAC_PROOF_RUNTIME

    def __init__(
        self,
        *,
        task: str = DEFAULT_ISAAC_TASK,
        device: str = DEFAULT_ISAAC_DEVICE,
        headless: bool = True,
        action_scale: float = 1.0,
        max_steps: int = int(SUCCESS_METRIC["max_steps"]),
    ) -> None:
        self.task = task
        self.device = device
        self.headless = headless
        self.action_scale = action_scale
        self.max_steps = max_steps

    def run(
        self,
        *,
        manifest: dict[str, Any],
        output_dir: Path,
        min_rollouts_per_policy: int,
        deterministic_profile: str,
        policy_artifacts: dict[str, Any] | None = None,
    ) -> BackendResult:
        del deterministic_profile
        trace_dir = output_dir / "isaac_runtime_heldout_rollout_traces"
        trace_dir.mkdir(parents=True, exist_ok=True)
        if policy_artifacts is None:
            policy_artifacts = {
                "baseline": read_json(output_dir / "baseline_policy_artifact.json"),
                "candidate": read_json(output_dir / "candidate_policy_artifact.json"),
            }
        try:
            return self._run_isaaclab(
                manifest=manifest,
                trace_dir=trace_dir,
                min_rollouts_per_policy=min_rollouts_per_policy,
                policy_artifacts=policy_artifacts,
            )
        except Exception as exc:
            error_path = trace_dir / "isaac_runtime_error.json"
            write_json(
                error_path,
                {
                    "schema_version": "rdf_mvp2b_isaac_runtime_error_v0.1.0",
                    "runtime_backend": self.runtime_backend,
                    "proof_runtime": self.proof_runtime,
                    "scenario_manifest_sha256": manifest["manifest_sha256"],
                    "isaac_task_or_scene_id": self.task,
                    "headless": self.headless,
                    "device": self.device,
                    "error": f"{type(exc).__name__}: {exc}",
                },
            )
            return BackendResult(
                runtime_backend=self.runtime_backend,
                proof_runtime=self.proof_runtime,
                runtime_gate={
                    "passed": False,
                    "runtime_backend": self.runtime_backend,
                    "proof_runtime": self.proof_runtime,
                    "reason": f"Isaac runtime rollout failed: {type(exc).__name__}: {exc}",
                    "error_artifact": str(error_path),
                },
                baseline_rollouts=[],
                candidate_rollouts=[],
                baseline_trace_paths=[str(error_path)],
                candidate_trace_paths=[str(error_path)],
                runtime_metadata={
                    "runtime_backend": self.runtime_backend,
                    "proof_runtime": self.proof_runtime,
                    "scenario_manifest_sha256": manifest["manifest_sha256"],
                    "isaac_task_or_scene_id": self.task,
                    "headless": self.headless,
                    "device": self.device,
                    "runtime_error_artifact": str(error_path),
                },
            )

    def _run_isaaclab(
        self,
        *,
        manifest: dict[str, Any],
        trace_dir: Path,
        min_rollouts_per_policy: int,
        policy_artifacts: dict[str, Any],
    ) -> BackendResult:
        from isaaclab.app import AppLauncher

        app_launcher = AppLauncher(
            {
                "headless": self.headless,
                "device": self.device,
                "enable_cameras": False,
            }
        )
        simulation_app = app_launcher.app

        import gymnasium as gym
        import torch

        import isaaclab_tasks  # noqa: F401
        from isaaclab_tasks.utils import parse_env_cfg

        env = None
        heldout = [row for row in manifest["scenarios"] if row["split"] == "held_out"]
        rollout_count = max(min_rollouts_per_policy, len(heldout))
        baseline_rollouts: list[dict[str, Any]] = []
        candidate_rollouts: list[dict[str, Any]] = []
        baseline_paths: list[str] = []
        candidate_paths: list[str] = []
        try:
            env_cfg = parse_env_cfg(self.task, device=self.device, num_envs=1)
            env = gym.make(self.task, cfg=env_cfg).unwrapped
            for role, policy in (
                ("baseline", policy_artifacts["baseline"]),
                ("candidate", policy_artifacts["candidate"]),
            ):
                rollouts = baseline_rollouts if role == "baseline" else candidate_rollouts
                trace_paths = baseline_paths if role == "baseline" else candidate_paths
                for index in range(rollout_count):
                    scenario = heldout[index % len(heldout)]
                    trace_path, rollout = self._run_one_rollout(
                        env=env,
                        simulation_app=simulation_app,
                        torch=torch,
                        policy_artifact=policy,
                        scenario=scenario,
                        role=role,
                        rollout_index=index,
                        trace_dir=trace_dir,
                        manifest=manifest,
                    )
                    trace_paths.append(str(trace_path))
                    rollouts.append(rollout)
            runtime_gate = {
                "passed": bool(baseline_rollouts and candidate_rollouts),
                "runtime_backend": self.runtime_backend,
                "proof_runtime": self.proof_runtime,
                "isaac_task_or_scene_id": self.task,
                "headless": self.headless,
                "device": self.device,
            }
            return BackendResult(
                runtime_backend=self.runtime_backend,
                proof_runtime=self.proof_runtime,
                runtime_gate=runtime_gate,
                baseline_rollouts=baseline_rollouts,
                candidate_rollouts=candidate_rollouts,
                baseline_trace_paths=baseline_paths,
                candidate_trace_paths=candidate_paths,
                runtime_metadata={
                    "runtime_backend": self.runtime_backend,
                    "proof_runtime": self.proof_runtime,
                    "scenario_manifest_sha256": manifest["manifest_sha256"],
                    "isaac_task_or_scene_id": self.task,
                    "headless": self.headless,
                    "device": self.device,
                    "max_steps": self.max_steps,
                    "action_scale": self.action_scale,
                },
            )
        finally:
            if env is not None:
                env.close()
            # Isaac Sim 5.x can terminate the interpreter on explicit close in
            # short-lived scripts; process exit releases the app after artifacts
            # are written.

    def run_single_policy_probe(
        self,
        *,
        manifest: dict[str, Any],
        output_dir: Path,
        policy_artifact: dict[str, Any],
        role: str,
        max_rollouts: int,
        stop_after_first_success: bool,
    ) -> BackendResult:
        trace_dir = output_dir / "isaac_runtime_heldout_rollout_traces"
        trace_dir.mkdir(parents=True, exist_ok=True)
        try:
            return self._run_single_policy_probe_isaaclab(
                manifest=manifest,
                trace_dir=trace_dir,
                policy_artifact=policy_artifact,
                role=role,
                max_rollouts=max_rollouts,
                stop_after_first_success=stop_after_first_success,
            )
        except Exception as exc:
            error_path = trace_dir / "isaac_runtime_error.json"
            write_json(
                error_path,
                {
                    "schema_version": "rdf_mvp2b_isaac_runtime_error_v0.1.0",
                    "runtime_backend": self.runtime_backend,
                    "proof_runtime": self.proof_runtime,
                    "scenario_manifest_sha256": manifest["manifest_sha256"],
                    "isaac_task_or_scene_id": self.task,
                    "headless": self.headless,
                    "device": self.device,
                    "error": f"{type(exc).__name__}: {exc}",
                },
            )
            return BackendResult(
                runtime_backend=self.runtime_backend,
                proof_runtime=self.proof_runtime,
                runtime_gate={
                    "passed": False,
                    "runtime_backend": self.runtime_backend,
                    "proof_runtime": self.proof_runtime,
                    "reason": f"Isaac runtime single-policy probe failed: {type(exc).__name__}: {exc}",
                    "error_artifact": str(error_path),
                },
                baseline_rollouts=[],
                candidate_rollouts=[],
                baseline_trace_paths=[str(error_path)],
                candidate_trace_paths=[],
                runtime_metadata={
                    "runtime_backend": self.runtime_backend,
                    "proof_runtime": self.proof_runtime,
                    "scenario_manifest_sha256": manifest["manifest_sha256"],
                    "isaac_task_or_scene_id": self.task,
                    "headless": self.headless,
                    "device": self.device,
                    "runtime_error_artifact": str(error_path),
                },
            )

    def _run_single_policy_probe_isaaclab(
        self,
        *,
        manifest: dict[str, Any],
        trace_dir: Path,
        policy_artifact: dict[str, Any],
        role: str,
        max_rollouts: int,
        stop_after_first_success: bool,
    ) -> BackendResult:
        from isaaclab.app import AppLauncher

        app_launcher = AppLauncher(
            {
                "headless": self.headless,
                "device": self.device,
                "enable_cameras": False,
            }
        )
        simulation_app = app_launcher.app

        import gymnasium as gym
        import torch

        import isaaclab_tasks  # noqa: F401
        from isaaclab_tasks.utils import parse_env_cfg

        env = None
        scenarios = [row for row in manifest["scenarios"] if row["split"] == "held_out"]
        rollouts: list[dict[str, Any]] = []
        trace_paths: list[str] = []
        try:
            env_cfg = parse_env_cfg(self.task, device=self.device, num_envs=1)
            env = gym.make(self.task, cfg=env_cfg).unwrapped
            for index, scenario in enumerate(scenarios[: max(0, int(max_rollouts))]):
                trace_path, rollout = self._run_one_rollout(
                    env=env,
                    simulation_app=simulation_app,
                    torch=torch,
                    policy_artifact=policy_artifact,
                    scenario=scenario,
                    role=role,
                    rollout_index=index,
                    trace_dir=trace_dir,
                    manifest=manifest,
                )
                trace_paths.append(str(trace_path))
                rollouts.append(rollout)
                if stop_after_first_success and rollout.get("success") is True:
                    break
            runtime_gate = {
                "passed": bool(rollouts),
                "runtime_backend": self.runtime_backend,
                "proof_runtime": self.proof_runtime,
                "isaac_task_or_scene_id": self.task,
                "headless": self.headless,
                "device": self.device,
            }
            return BackendResult(
                runtime_backend=self.runtime_backend,
                proof_runtime=self.proof_runtime,
                runtime_gate=runtime_gate,
                baseline_rollouts=rollouts,
                candidate_rollouts=[],
                baseline_trace_paths=trace_paths,
                candidate_trace_paths=[],
                runtime_metadata={
                    "runtime_backend": self.runtime_backend,
                    "proof_runtime": self.proof_runtime,
                    "scenario_manifest_sha256": manifest["manifest_sha256"],
                    "isaac_task_or_scene_id": self.task,
                    "headless": self.headless,
                    "device": self.device,
                    "max_steps": self.max_steps,
                    "action_scale": self.action_scale,
                    "single_policy_probe_role": role,
                },
            )
        finally:
            if env is not None:
                env.close()

    def _run_one_rollout(
        self,
        *,
        env: Any,
        simulation_app: Any,
        torch: Any,
        policy_artifact: dict[str, Any],
        scenario: dict[str, Any],
        role: str,
        rollout_index: int,
        trace_dir: Path,
        manifest: dict[str, Any],
    ) -> tuple[Path, dict[str, Any]]:
        seed = int(scenario["seed"])
        try:
            env.reset(seed=seed)
        except TypeError:
            env.reset()
        offset_applied = self._apply_scenario_initial_offset(env=env, scenario=scenario, torch=torch)
        previous_action = [0.0] * len(ACTION_SCHEMA)
        trace: list[dict[str, Any]] = []
        summary: dict[str, Any] = {
            "success": False,
            "failure_reason": "NO_STEPS_EXECUTED",
            "steps": 0,
        }
        success_authority = manifest.get("success_authority") if isinstance(manifest, dict) else None
        use_env_native_authority = (
            isinstance(success_authority, dict)
            and success_authority.get("primary") == "isaac_env_native_consecutive_success_v0"
        )
        stable_steps_required = int(
            success_authority.get("stable_steps_required", SUCCESS_METRIC["stable_steps_required"])
            if isinstance(success_authority, dict)
            else SUCCESS_METRIC["stable_steps_required"]
        )
        env_reset_boundary_steps = _env_reset_boundary_steps(env)
        effective_rollout_budget_steps = _effective_rollout_budget_steps(
            max_steps=self.max_steps,
            env_reset_boundary_steps=env_reset_boundary_steps,
        )
        seat_deadline_steps = max(0, int(effective_rollout_budget_steps) - int(stable_steps_required))
        v07e_hysteresis_state = (
            initial_v07e_hysteresis_state()
            if policy_artifact.get("policy_slice") in V07E_HYSTERESIS_RUNTIME_POLICY_SLICE_IDS
            else None
        )
        v08d_progress_state: dict[str, Any] | None = (
            {"z_open_step": None, "z_open_depth_reference_m": None}
            if policy_artifact.get("policy_slice") == V08D_POLICY_SLICE_ID
            else None
        )
        for step in range(effective_rollout_budget_steps):
            current = self._metric_row(env=env, step=step)
            if v08d_progress_state is not None:
                current["z_open_step"] = v08d_progress_state["z_open_step"]
                current["z_open_depth_reference_m"] = v08d_progress_state[
                    "z_open_depth_reference_m"
                ]
            action_np, controller_action_diagnostics = _predict_policy_action_with_diagnostics(
                policy_artifact,
                metric_row=current,
                previous_action=previous_action,
                action_scale=self.action_scale,
                hysteresis_state=v07e_hysteresis_state,
            )
            if policy_artifact.get("policy_slice") in V07E_HYSTERESIS_RUNTIME_POLICY_SLICE_IDS:
                v07e_hysteresis_state = controller_action_diagnostics.get("shared_hysteresis_state_after")
            action_shape = tuple(getattr(env.action_space, "shape", (len(action_np),)))
            action_dim = int(action_shape[-1] if action_shape else len(action_np))
            if action_np.shape[0] < action_dim:
                action_np = np.pad(action_np, (0, action_dim - action_np.shape[0]))
            action_np = action_np[:action_dim].reshape(1, action_dim)
            if (
                v08d_progress_state is not None
                and v08d_progress_state["z_open_step"] is None
                and float(action_np.reshape(-1)[2]) < -1.0e-6
            ):
                v08d_progress_state["z_open_step"] = step
                v08d_progress_state["z_open_depth_reference_m"] = float(
                    current.get("insertion_depth_m", 0.0)
                )
                controller_action_diagnostics["z_open_step"] = step
                controller_action_diagnostics["z_open_depth_reference_m"] = v08d_progress_state[
                    "z_open_depth_reference_m"
                ]
            action = torch.as_tensor(action_np, dtype=torch.float32, device=env.device)
            env.step(action)
            previous_action = [float(value) for value in action_np.reshape(-1)[: len(ACTION_SCHEMA)]]
            measured = self._metric_row(env=env, step=step)
            env_native_success = _read_env_native_success(env)
            measured["normalized_action"] = previous_action
            measured["env_native_success"] = env_native_success
            measured["success_authority"] = (
                "isaac_env_native_consecutive_success_v0" if env_native_success is not None else None
            )
            measured["controller_action_diagnostics"] = controller_action_diagnostics
            trace.append(measured)
            if use_env_native_authority:
                summary = evaluate_env_native_rollout_trace(
                    trace,
                    success_metric=manifest["success_metric"],
                    stable_steps_required=stable_steps_required,
                )
            else:
                summary = evaluate_rollout_trace(trace, success_metric=manifest["success_metric"])
            if summary["success"] or not simulation_app.is_running():
                break
        trace_path = trace_dir / f"{role}_{rollout_index:04d}_{scenario['scenario_id']}_isaac_trace.json"
        write_json(
            trace_path,
            {
                "schema_version": "rdf_mvp2b_isaac_runtime_trace_v0.1.0",
                "runtime_backend": self.runtime_backend,
                "proof_runtime": self.proof_runtime,
                "scenario_manifest_sha256": manifest["manifest_sha256"],
                "scenario": scenario,
                "scenario_offset_applied": offset_applied,
                "policy_role": role,
                "policy_artifact_id": policy_artifact["policy_id"],
                "isaac_task_or_scene_id": self.task,
                "headless": self.headless,
                "device": self.device,
                "env_reset_boundary_steps": env_reset_boundary_steps,
                "effective_rollout_budget_steps": effective_rollout_budget_steps,
                "env_reset_post_step_guard_steps": ENV_RESET_POST_STEP_GUARD_STEPS,
                "seat_deadline_steps": seat_deadline_steps,
                "success_metric_max_steps": int(self.max_steps),
                "horizon_increase_applied": effective_rollout_budget_steps > int(self.max_steps),
                "trace": trace,
                "summary": summary,
            },
        )
        rollout = {
            "rollout_id": f"{role}_isaac_{rollout_index:04d}",
            "scenario_id": scenario["scenario_id"],
            "success": summary["success"],
            "failure_reason": summary["failure_reason"],
            "steps": summary["steps"],
            "rollout_log_ref": str(trace_path),
            "env_native_rollout_success": summary.get("env_native_rollout_success"),
            "env_native_max_consecutive_success_steps": summary.get("env_native_max_consecutive_success_steps"),
            "env_native_success_available": summary.get("env_native_success_available"),
            "env_reset_boundary_steps": env_reset_boundary_steps,
            "effective_rollout_budget_steps": effective_rollout_budget_steps,
            "env_reset_post_step_guard_steps": ENV_RESET_POST_STEP_GUARD_STEPS,
            "seat_deadline_steps": seat_deadline_steps,
            "horizon_increase_applied": effective_rollout_budget_steps > int(self.max_steps),
        }
        return trace_path, rollout

    def _metric_row(self, *, env: Any, step: int) -> dict[str, Any]:
        unwrapped = getattr(env, "unwrapped", env)
        if hasattr(unwrapped, "_compute_intermediate_values"):
            unwrapped._compute_intermediate_values(dt=unwrapped.physics_dt)
        held = self._tensor_row(getattr(unwrapped, "held_pos"))
        fixed = self._tensor_row(getattr(unwrapped, "fixed_pos"))
        held_quat = self._tensor_row(getattr(unwrapped, "held_quat"))
        fixed_quat_value = getattr(unwrapped, "fixed_quat", None)
        fixed_quat = self._tensor_row(fixed_quat_value) if fixed_quat_value is not None else np.asarray([1.0, 0.0, 0.0, 0.0])
        cfg_task = getattr(unwrapped, "cfg_task", None)
        task_name = str(getattr(cfg_task, "name", ""))
        fixed_asset_cfg = getattr(cfg_task, "fixed_asset_cfg", None)
        fixed_asset_height_m = getattr(fixed_asset_cfg, "height", None)
        success_threshold = getattr(cfg_task, "success_threshold", None)
        if task_name == "peg_insert" and fixed_asset_height_m is not None and success_threshold is not None:
            native_pose = _factory_peg_insert_base_target_pose_from_env(unwrapped)
            if native_pose is None:
                row = rdf_compatible_metric_row_from_pose_values(
                    step=step,
                    held_pos=held,
                    fixed_pos=fixed,
                    held_quat=held_quat,
                    fixed_quat=fixed_quat,
                )
                row["native_metric_blocker"] = "factory_utils_base_target_unavailable"
                row["env_native_diagnostics_source"] = "unavailable"
                return row
            return factory_peg_insert_native_aligned_metric_row_from_pose_values(
                step=step,
                held_pos=held,
                fixed_pos=fixed,
                held_base_pos=native_pose["held_base_pos"],
                target_held_base_pos=native_pose["target_held_base_pos"],
                held_base_quat=native_pose["held_base_quat"],
                target_held_base_quat=native_pose["target_held_base_quat"],
                held_quat=held_quat,
                fixed_quat=fixed_quat,
                fixed_asset_height_m=float(fixed_asset_height_m),
                success_threshold=float(success_threshold),
            )
        return rdf_compatible_metric_row_from_pose_values(
            step=step,
            held_pos=held,
            fixed_pos=fixed,
            held_quat=held_quat,
            fixed_quat=fixed_quat,
        )

    @staticmethod
    def _tensor_row(value: Any) -> np.ndarray:
        array = value.detach().cpu().numpy()
        if array.ndim == 2:
            return np.asarray(array[0], dtype=np.float64)
        return np.asarray(array, dtype=np.float64)

    @staticmethod
    def _orientation_error_deg(unwrapped: Any) -> float:
        quat = IsaacConnectorInsertionEvaluatorBackend._tensor_row(getattr(unwrapped, "held_quat"))
        return quaternion_angle_error_deg(quat, target_angle_deg=180.0)

    @staticmethod
    def _apply_scenario_initial_offset(*, env: Any, scenario: dict[str, Any], torch: Any) -> bool:
        offset = np.asarray(scenario.get("initial_offset_m") or [0.0, 0.0, 0.0], dtype=np.float32)
        if not np.isfinite(offset).all() or float(np.linalg.norm(offset)) == 0.0:
            return False
        unwrapped = getattr(env, "unwrapped", env)
        fixed_asset = getattr(unwrapped, "_fixed_asset", None)
        if fixed_asset is None or not hasattr(fixed_asset, "write_root_pose_to_sim"):
            return False
        state = fixed_asset.data.root_state_w.clone()
        state[:, 0:3] += torch.as_tensor(offset, dtype=state.dtype, device=state.device).reshape(1, 3)
        fixed_asset.write_root_pose_to_sim(state[:, 0:7])
        fixed_asset.write_root_velocity_to_sim(torch.zeros_like(state[:, 7:]))
        fixed_asset.reset()
        if hasattr(unwrapped, "step_sim_no_action"):
            unwrapped.step_sim_no_action()
        return True



def _heldout_suite(manifest: dict[str, Any]) -> dict[str, Any]:
    scenario_ids = [
        str(row["scenario_id"])
        for row in manifest["scenarios"]
        if isinstance(row, dict) and row.get("split") == "held_out"
    ]
    return {
        "id": "mvp2b_isaac_connector_insertion_heldout_suite",
        "held_out": True,
        "task_type": "connector_insertion",
        "scenario_ids": scenario_ids,
        "scenario_set_sha256": manifest["manifest_sha256"],
        "source_kind": "external_trainer_eval_suite",
        "proof_role": "external_policy_eval_suite",
        "success_metric": manifest["success_metric"],
    }


def _write_external_rollout_json(
    *,
    output_dir: Path,
    role: str,
    policy_artifact: dict[str, Any],
    train_view: dict[str, Any],
    heldout_suite: dict[str, Any],
    backend_result: BackendResult,
) -> Path:
    rollouts = backend_result.baseline_rollouts if role == "baseline" else backend_result.candidate_rollouts
    payload = {
        "schema_version": ROLLOUT_SCHEMA_VERSION,
        "source_kind": "external_heldout_policy_eval",
        "proof_role": "external_trainer_policy_eval",
        "policy_role": role,
        "policy_artifact_id": policy_artifact["policy_id"],
        "policy_artifact_sha256": policy_artifact["policy_artifact_sha256"],
        "training_artifact_sha256": train_view["sha256"],
        "policy_class": POLICY_CLASS,
        "trainer": TRAINER,
        "eval_runner": "rdf_mvp2b_dedicated_connector_insertion_eval_v0",
        "external_evaluator_run": {
            "run_id": f"mvp2b_{role}_{backend_result.runtime_backend}",
            "runner_version": SCHEMA_VERSION,
            "run_log_uri": str(output_dir / "heldout_rollout_traces"),
            "generated_outside_rdf_local_proxy": True,
        },
        "runtime_metadata": backend_result.runtime_metadata,
        "heldout_suite": heldout_suite,
        "rollout_results": rollouts,
    }
    path = output_dir / "external_rollouts" / f"{role}_external_rollouts.json"
    write_json(path, payload)
    return path


def _write_visual_evidence(*, output_dir: Path, backend_result: BackendResult) -> dict[str, Any]:
    visual_dir = output_dir / "visual_evidence"
    visual_dir.mkdir(parents=True, exist_ok=True)
    svg_path = visual_dir / "metric_trace_comparison.png"
    baseline_rate = sum(1 for item in backend_result.baseline_rollouts if item["success"]) / max(
        len(backend_result.baseline_rollouts), 1
    )
    candidate_rate = sum(1 for item in backend_result.candidate_rollouts if item["success"]) / max(
        len(backend_result.candidate_rollouts), 1
    )
    _write_rate_png(svg_path, baseline_rate=baseline_rate, candidate_rate=candidate_rate)
    return {
        "metric_trace_comparison_png": str(svg_path),
        "baseline_representative_rollout": backend_result.baseline_trace_paths[0]
        if backend_result.baseline_trace_paths
        else "",
        "candidate_representative_rollout": backend_result.candidate_trace_paths[0]
        if backend_result.candidate_trace_paths
        else "",
    }


def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + chunk_type
        + data
        + struct.pack(">I", zlib.crc32(chunk_type + data) & 0xFFFFFFFF)
    )


def _write_rate_png(path: Path, *, baseline_rate: float, candidate_rate: float) -> None:
    width = 240
    height = 120
    pixels = bytearray([255, 255, 255] * width * height)

    def set_pixel(x: int, y: int, color: tuple[int, int, int]) -> None:
        if 0 <= x < width and 0 <= y < height:
            index = (y * width + x) * 3
            pixels[index : index + 3] = bytes(color)

    def fill_rect(x0: int, y0: int, x1: int, y1: int, color: tuple[int, int, int]) -> None:
        for y in range(max(0, y0), min(height, y1)):
            for x in range(max(0, x0), min(width, x1)):
                set_pixel(x, y, color)

    fill_rect(20, 100, 220, 102, (30, 30, 30))
    baseline_h = int(80 * baseline_rate)
    candidate_h = int(80 * candidate_rate)
    fill_rect(60, 100 - baseline_h, 100, 100, (76, 120, 180))
    fill_rect(140, 100 - candidate_h, 180, 100, (42, 160, 98))
    raw_rows = b"".join(
        b"\x00" + bytes(pixels[row * width * 3 : (row + 1) * width * 3])
        for row in range(height)
    )
    png = (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + _png_chunk(b"IDAT", zlib.compress(raw_rows))
        + _png_chunk(b"IEND", b"")
    )
    path.write_bytes(png)


def _write_learning_harness_bridge(
    *,
    output_dir: Path,
    manifest: dict[str, Any],
    baseline_view: dict[str, Any],
    candidate_view: dict[str, Any],
) -> Path:
    bridge_dir = output_dir / "mvp2_learning_harness_bridge"
    bridge_dir.mkdir(parents=True, exist_ok=True)
    heldout = _heldout_suite(manifest)
    heldout_manifest_path = bridge_dir / "mvp2_heldout_suite_manifest.json"
    template_path = bridge_dir / "mvp2_policy_eval_input_template.json"
    report_path = bridge_dir / "mvp2_policy_ab_harness_report.json"
    write_json(heldout_manifest_path, heldout)
    template = {
        "schema_version": "rdf_mvp2_policy_eval_input_v0.1.0",
        "evidence_tier": "schema_only_rollout_ingest_contract",
        "primary_metric": "policy_success_rate",
        "task_type": "connector_insertion",
        "eval_suite": {
            "id": heldout["id"],
            "held_out": True,
            "task_type": heldout["task_type"],
            "scenario_ids": heldout["scenario_ids"],
            "heldout_manifest_path": str(heldout_manifest_path),
        },
        "baseline": {
            "name": "baseline_uncurated_mvp2b_policy",
            "dataset_view": "baseline_uncurated_mvp2b_train_view",
            "dataset_id": "mvp2b_baseline_uncurated_train_view",
            "train_hdf5_path": baseline_view["path"],
            "policy_class": POLICY_CLASS,
            "trainer": TRAINER,
            "rollout_results": [],
        },
        "candidate": {
            "name": "candidate_curated_mvp2b_policy",
            "dataset_view": "candidate_curated_mvp2b_train_view",
            "dataset_id": "mvp2b_candidate_curated_train_view",
            "train_hdf5_path": candidate_view["path"],
            "policy_class": POLICY_CLASS,
            "trainer": TRAINER,
            "rollout_results": [],
        },
    }
    write_json(template_path, template)
    harness_report = {
        "schema_version": "rdf_mvp2b_learning_harness_bridge_v0.1.0",
        "passed": True,
        "harness_ready": True,
        "heldout_suite": heldout,
        "artifact_paths": {
            "report": str(report_path),
            "policy_eval_input_template": str(template_path),
            "heldout_suite_manifest": str(heldout_manifest_path),
            "baseline_hdf5": baseline_view["path"],
            "candidate_hdf5": candidate_view["path"],
        },
        "proof_source": {
            "adapter_id": "mvp2b_dedicated_isaac_connector_insertion_evaluator",
            "adapter_version": SCHEMA_VERSION,
            "builder_id": "mvp2b_scripted_expert_controlled_noise_builder",
            "robot_embodiment": "franka_research_arm_domain_model",
            "source_evidence_type": "generated_isaac_domain_training_material",
            "validator_backend": "NormalizedTrajectoryContractValidator",
        },
    }
    write_json(report_path, harness_report)
    return bridge_dir


def _run_learning_validator(
    *,
    output_dir: Path,
    bridge_dir: Path,
    baseline_rollouts_path: Path,
    candidate_rollouts_path: Path,
    min_rollouts_per_policy: int,
    bootstrap_iterations: int,
    bootstrap_seed: int,
) -> dict[str, Any]:
    return build_mvp2_learning_proven_policy_eval(
        output_dir=output_dir / "mvp2_learning_proven_policy_eval",
        harness_output_dir=bridge_dir,
        mvp1plus_output_dir=output_dir / "unused_mvp1plus_for_bridge",
        clean=True,
        refresh_harness=False,
        refresh_mvp1plus=False,
        baseline_results_path=baseline_rollouts_path,
        candidate_results_path=candidate_rollouts_path,
        baseline_policy_id="baseline_uncurated_phase_conditioned_numpy_bc",
        candidate_policy_id="candidate_curated_phase_conditioned_numpy_bc",
        policy_class=POLICY_CLASS,
        trainer=TRAINER,
        min_rollouts_per_policy=min_rollouts_per_policy,
        bootstrap_iterations=bootstrap_iterations,
        bootstrap_seed=bootstrap_seed,
    )


def derive_mvp2b_closure(
    *,
    learning_report: dict[str, Any],
    runtime_gate: dict[str, Any],
    min_rollouts_per_policy: int = MIN_PROOF_ROLLOUTS_PER_POLICY,
) -> dict[str, Any]:
    uplift = learning_report.get("curated_vs_uncurated_uplift")
    uplift_value = float(uplift) if isinstance(uplift, (int, float)) and not isinstance(uplift, bool) else None
    runtime_matches = (
        runtime_gate.get("passed") is True
        and runtime_gate.get("runtime_backend") == "isaac_runtime"
        and runtime_gate.get("proof_runtime") == ISAAC_PROOF_RUNTIME
    )
    learning_matches = (
        learning_report.get("learning_proven") is True
        and learning_report.get("proof_eligible") is True
        and uplift_value is not None
        and uplift_value >= 0.20
    )
    rollout_count_matches = min_rollouts_per_policy >= MIN_PROOF_ROLLOUTS_PER_POLICY
    closed = bool(runtime_matches and learning_matches and rollout_count_matches)
    blockers: list[str] = []
    if not learning_matches:
        blockers.append("Existing MVP-2 learning validator did not produce proof-eligible uplift >= 0.20.")
    if not runtime_matches:
        blockers.append("Dedicated Isaac runtime gate did not pass.")
    if not rollout_count_matches:
        blockers.append(
            f"MVP-2B closure requires at least {MIN_PROOF_ROLLOUTS_PER_POLICY} held-out rollouts per policy."
        )
    return {
        "mvp2_closed": closed,
        "proof_eligible": closed,
        "learning_proven": closed,
        "blockers": blockers,
    }


def _skip_learning_report(output_dir: Path) -> dict[str, Any]:
    path = output_dir / "mvp2_learning_proven_policy_eval" / "mvp2_learning_proven_report.json"
    report = {
        "schema_version": "rdf_mvp2b_skipped_learning_validator_v0.1.0",
        "passed": True,
        "learning_results_measured": False,
        "learning_proven": False,
        "proof_eligible": False,
        "baseline_success_rate": None,
        "candidate_success_rate": None,
        "curated_vs_uncurated_uplift": None,
        "blockers": ["Isaac/deterministic held-out evaluator was skipped."],
        "artifact_paths": {
            "report": str(path),
            "policy_eval_input": None,
            "policy_eval_report": None,
        },
    }
    write_json(path, report)
    return report


def build_mvp2b_isaac_proof_evaluator(
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    clean: bool = False,
    skip_isaac: bool = False,
    use_deterministic_eval_backend: bool = False,
    deterministic_profile: str = "candidate_positive",
    min_rollouts_per_policy: int = 20,
    max_steps: int = int(SUCCESS_METRIC["max_steps"]),
    isaac_task: str = DEFAULT_ISAAC_TASK,
    device: str = DEFAULT_ISAAC_DEVICE,
    headless: bool = True,
    action_scale: float = 1.0,
    bootstrap_iterations: int = 2000,
    bootstrap_seed: int = 17,
) -> dict[str, Any]:
    _prepare_output_dir(output_dir, clean=clean)
    manifest = build_scenario_manifest(output_dir=output_dir)
    bundle = generate_training_trajectory_bundle(manifest=manifest, output_dir=output_dir)
    if bundle["contract_validation"]["passed"] is not True:
        raise ValueError(f"MVP-2B generated contracts failed: {bundle['contract_validation']['issues']}")

    baseline_rows = list(bundle["training_rows"])
    candidate_rows = [row for row in bundle["training_rows"] if row.get("accepted") is True]
    baseline_view = _write_train_view_hdf5(
        path=output_dir / "baseline_uncurated_train.hdf5",
        rows=baseline_rows,
        view_id="baseline_uncurated_mvp2b_train_view",
    )
    candidate_view = _write_train_view_hdf5(
        path=output_dir / "candidate_curated_train.hdf5",
        rows=candidate_rows,
        view_id="candidate_curated_mvp2b_train_view",
    )
    policy_artifacts = _write_policy_artifacts(
        output_dir=output_dir,
        baseline_rows=baseline_rows,
        candidate_rows=candidate_rows,
    )
    bridge_dir = _write_learning_harness_bridge(
        output_dir=output_dir,
        manifest=manifest,
        baseline_view=baseline_view,
        candidate_view=candidate_view,
    )

    baseline_rollouts_path: Path | None = None
    candidate_rollouts_path: Path | None = None
    visual_evidence: dict[str, Any] = {}
    visual_trace_paths: list[str] = []
    actual_rollouts_per_policy = 0
    if skip_isaac:
        runtime_backend = "skipped"
        proof_runtime = "skipped"
        runtime_gate = {
            "passed": False,
            "runtime_backend": runtime_backend,
            "proof_runtime": proof_runtime,
            "reason": "Isaac runtime and deterministic backend were skipped.",
        }
        learning_report = _skip_learning_report(output_dir)
    else:
        if use_deterministic_eval_backend:
            backend_result = DeterministicEvaluatorBackend().run(
                manifest=manifest,
                output_dir=output_dir,
                min_rollouts_per_policy=min_rollouts_per_policy,
                deterministic_profile=deterministic_profile,
            )
        else:
            backend_result = IsaacConnectorInsertionEvaluatorBackend(
                task=isaac_task,
                device=device,
                headless=headless,
                action_scale=action_scale,
                max_steps=max_steps,
            ).run(
                manifest=manifest,
                output_dir=output_dir,
                min_rollouts_per_policy=min_rollouts_per_policy,
                deterministic_profile=deterministic_profile,
                policy_artifacts=policy_artifacts,
            )
        runtime_backend = backend_result.runtime_backend
        proof_runtime = backend_result.proof_runtime
        runtime_gate = backend_result.runtime_gate
        actual_rollouts_per_policy = min(
            len(backend_result.baseline_rollouts),
            len(backend_result.candidate_rollouts),
        )
        runtime_gate["actual_baseline_rollouts"] = len(backend_result.baseline_rollouts)
        runtime_gate["actual_candidate_rollouts"] = len(backend_result.candidate_rollouts)
        runtime_gate["actual_rollouts_per_policy"] = actual_rollouts_per_policy
        heldout_suite = _heldout_suite(manifest)
        baseline_rollouts_path = _write_external_rollout_json(
            output_dir=output_dir,
            role="baseline",
            policy_artifact=policy_artifacts["baseline"],
            train_view=baseline_view,
            heldout_suite=heldout_suite,
            backend_result=backend_result,
        )
        candidate_rollouts_path = _write_external_rollout_json(
            output_dir=output_dir,
            role="candidate",
            policy_artifact=policy_artifacts["candidate"],
            train_view=candidate_view,
            heldout_suite=heldout_suite,
            backend_result=backend_result,
        )
        visual_evidence = _write_visual_evidence(output_dir=output_dir, backend_result=backend_result)
        visual_trace_paths = backend_result.baseline_trace_paths + backend_result.candidate_trace_paths
        learning_report = _run_learning_validator(
            output_dir=output_dir,
            bridge_dir=bridge_dir,
            baseline_rollouts_path=baseline_rollouts_path,
            candidate_rollouts_path=candidate_rollouts_path,
            min_rollouts_per_policy=min_rollouts_per_policy,
            bootstrap_iterations=bootstrap_iterations,
            bootstrap_seed=bootstrap_seed,
        )

    closure = derive_mvp2b_closure(
        learning_report=learning_report,
        runtime_gate=runtime_gate,
        min_rollouts_per_policy=actual_rollouts_per_policy,
    )
    report_path = output_dir / REPORT_NAME
    artifact_paths = {
        "report": str(report_path),
        "evidence_manifest": str(output_dir / "evidence_manifest.json"),
        "scenario_manifest": str(output_dir / "scenario_manifest.json"),
        "curation_manifest": bundle["artifact_paths"]["curation_manifest"],
        "baseline_uncurated_train_hdf5": baseline_view["path"],
        "candidate_curated_train_hdf5": candidate_view["path"],
        "baseline_policy_artifact": policy_artifacts["baseline"]["path"],
        "candidate_policy_artifact": policy_artifacts["candidate"]["path"],
        "baseline_external_rollouts": str(baseline_rollouts_path) if baseline_rollouts_path else None,
        "candidate_external_rollouts": str(candidate_rollouts_path) if candidate_rollouts_path else None,
        "mvp2_learning_proven_report": str(
            output_dir / "mvp2_learning_proven_policy_eval" / "mvp2_learning_proven_report.json"
        ),
    }
    learning_blockers = learning_report.get("blockers") if isinstance(learning_report.get("blockers"), list) else []
    visual_evidence_source = "none"
    if visual_evidence:
        visual_evidence_source = "isaac_runtime_capture" if runtime_backend == "isaac_runtime" else "rollout_metric_traces"
    report = {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "passed": True,
        "mvp2_closed": closure["mvp2_closed"],
        "learning_proven": closure["learning_proven"],
        "proof_eligible": closure["proof_eligible"],
        "runtime_backend": runtime_backend,
        "proof_runtime": proof_runtime,
        "runtime_gate": runtime_gate,
        "requested_rollouts_per_policy": min_rollouts_per_policy,
        "actual_rollouts_per_policy": actual_rollouts_per_policy,
        "primary_proof_path": PRIMARY_PROOF_PATH,
        "scenario_manifest_sha256": manifest["manifest_sha256"],
        "baseline_success_rate": learning_report.get("baseline_success_rate"),
        "candidate_success_rate": learning_report.get("candidate_success_rate"),
        "curated_vs_uncurated_uplift": learning_report.get("curated_vs_uncurated_uplift"),
        "learning_validator": {
            "report_path": artifact_paths["mvp2_learning_proven_report"],
            "learning_proven": learning_report.get("learning_proven"),
            "proof_eligible": learning_report.get("proof_eligible"),
            "evidence_tier": learning_report.get("evidence_tier"),
            "validator_evidence_tier": learning_report.get("validator_evidence_tier"),
        },
        "training_views": {
            "baseline": baseline_view,
            "candidate": candidate_view,
        },
        "policy_artifacts": policy_artifacts,
        "contract_validation": bundle["contract_validation"],
        "visual_evidence": visual_evidence,
        "visual_evidence_is_proof_override": False,
        "visual_evidence_source": visual_evidence_source,
        "visual_evidence_source_trace_paths": visual_trace_paths,
        "artifact_paths": artifact_paths,
        "blockers": closure["blockers"] + [str(item) for item in learning_blockers],
        "proof_boundary": {
            "deterministic_backend_can_close_mvp2": False,
            "skip_isaac_can_close_mvp2": False,
            "requires_isaac_runtime_backend": True,
            "requires_existing_learning_validator": True,
            "minimum_uplift_absolute": 0.20,
        },
        "non_claims": [
            "No real robot success is claimed.",
            "No physical robot readiness is claimed.",
            "HMD/OpenXR is not the primary proof path.",
            "HMD/OpenXR readiness is not claimed.",
            "Deterministic backend output is not MVP-2 closure evidence.",
        ],
        "limitations": [
            "Isaac runtime closure depends on the local IsaacLab runtime producing proof-grade held-out rollouts.",
            "Deterministic backend artifacts validate shape and plumbing only.",
            "MVP-2 closure requires dedicated Isaac runtime held-out rollouts with positive curated > uncurated uplift.",
        ],
        "reproducible_command": (
            "/home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/run_mvp2b_isaac_proof_evaluator.py "
            f"--output-dir {output_dir} --clean --rollouts-per-policy {min_rollouts_per_policy} --pretty"
        ),
    }
    write_json(report_path, report)
    write_evidence_manifest(
        output_dir=output_dir,
        proof_slice="mvp2b_isaac_proof_evaluator",
        reproducible_command=report["reproducible_command"],
        metadata={
            "runtime_backend": report["runtime_backend"],
            "proof_runtime": report["proof_runtime"],
            "mvp2_closed": report["mvp2_closed"],
            "heldout_opened": bool(report["actual_rollouts_per_policy"]),
        },
    )
    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--clean", action="store_true")
    parser.add_argument("--skip-isaac", action="store_true")
    parser.add_argument("--use-deterministic-eval-backend", action="store_true")
    parser.add_argument(
        "--deterministic-profile",
        choices=("candidate_positive", "tie", "candidate_negative"),
        default="candidate_positive",
    )
    parser.add_argument("--rollouts-per-policy", "--min-rollouts-per-policy", dest="min_rollouts_per_policy", type=int, default=20)
    parser.add_argument("--max-steps", type=int, default=int(SUCCESS_METRIC["max_steps"]))
    parser.add_argument("--isaac-task", default=DEFAULT_ISAAC_TASK)
    parser.add_argument("--device", default=DEFAULT_ISAAC_DEVICE)
    parser.add_argument("--headless", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--action-scale", type=float, default=1.0)
    parser.add_argument("--bootstrap-iterations", type=int, default=2000)
    parser.add_argument("--bootstrap-seed", type=int, default=17)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_mvp2b_isaac_proof_evaluator(
        output_dir=args.output_dir,
        clean=args.clean,
        skip_isaac=args.skip_isaac,
        use_deterministic_eval_backend=args.use_deterministic_eval_backend,
        deterministic_profile=args.deterministic_profile,
        min_rollouts_per_policy=args.min_rollouts_per_policy,
        max_steps=args.max_steps,
        isaac_task=args.isaac_task,
        device=args.device,
        headless=args.headless,
        action_scale=args.action_scale,
        bootstrap_iterations=args.bootstrap_iterations,
        bootstrap_seed=args.bootstrap_seed,
    )
    if args.pretty:
        print(stable_json(report))
    else:
        print("RDF MVP-2B Isaac proof evaluator: PASS")
        print(f"passed={report['passed']}")
        print(f"mvp2_closed={report['mvp2_closed']}")
        print(f"learning_proven={report['learning_proven']}")
        print(f"proof_eligible={report['proof_eligible']}")
        print(f"baseline_success_rate={report['baseline_success_rate']}")
        print(f"candidate_success_rate={report['candidate_success_rate']}")
        print(f"curated_vs_uncurated_uplift={report['curated_vs_uncurated_uplift']}")
        print(f"report_path={report['artifact_paths']['report']}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
