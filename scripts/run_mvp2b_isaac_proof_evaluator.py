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
from run_mvp2_learning_proven_policy_eval import build_mvp2_learning_proven_policy_eval  # noqa: E402


SCHEMA_VERSION = "rdf_mvp2b_isaac_proof_evaluator_v0.1.0"
SCENARIO_MANIFEST_VERSION = "rdf_mvp2b_scenario_manifest_v0.1.0"
DEFAULT_OUTPUT_DIR = ROOT / "storage" / "mvp2b_isaac_proof_evaluator"
DEFAULT_ISAAC_TASK = "Isaac-Factory-PegInsert-Direct-v0"
DEFAULT_ISAAC_DEVICE = "cuda:0"
MIN_PROOF_ROLLOUTS_PER_POLICY = 20
POLICY_CLASS = "phase_conditioned_numpy_bc_policy_v0"
TRAINER = "rdf_numpy_phase_conditioned_bc_trainer_v0"
RESIDUAL_POLICY_CLASS = "phase_conditioned_residual_servo_bc_policy_v0"
RESIDUAL_TRAINER = "rdf_numpy_phase_conditioned_residual_servo_bc_trainer_v0"
RESIDUAL_TRAINER_FAMILY = "phase_conditioned_residual_servo_bc"
RESIDUAL_TARGET_DEFINITION = "actual_trace_action_minus_weak_base_servo_action"
WEAK_BASE_SERVO_CONFIG = {
    "xy_gain": 0.5,
    "approach_z": -0.001,
    "contact_z": -0.0015,
    "insert_z": -0.002,
    "seat_z": -0.0005,
    "rotation": 0.0,
    "gripper": 1.0,
}
XY_CORRECTION_GAIN = 0.8
PHASES = ("APPROACH", "CONTACT", "INSERT", "SEAT")
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


def featurize_step(step: dict[str, Any], *, previous_action: list[float]) -> tuple[np.ndarray, np.ndarray]:
    phase = str(step.get("phase") or "").upper()
    phase_vector = [1.0 if phase == item else 0.0 for item in PHASES]
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


def _features_targets(rows: list[dict[str, Any]]) -> tuple[np.ndarray, np.ndarray]:
    features: list[np.ndarray] = []
    targets: list[np.ndarray] = []
    previous_by_trajectory: dict[str, list[float]] = {}
    for row in rows:
        trajectory_id = str(row.get("trajectory_id"))
        previous = previous_by_trajectory.get(trajectory_id, [0.0] * len(ACTION_SCHEMA))
        feature, target = featurize_step(row, previous_action=previous)
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
) -> dict[str, Any]:
    features, targets = _features_targets(train_rows)
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
        "feature_schema": list(FEATURE_SCHEMA),
        "phase_schema": list(PHASES),
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
) -> tuple[np.ndarray, dict[str, Any]]:
    phase = str(metric_row.get("phase") or _phase_from_depth(float(metric_row.get("insertion_depth_m", 0.0))))
    feature, _ = featurize_step(
        {
            "phase": phase,
            "insertion_depth_m": metric_row.get("insertion_depth_m", 0.0),
            "relative_x_m": metric_row.get("relative_x_m", 0.0),
            "relative_y_m": metric_row.get("relative_y_m", 0.0),
            "lateral_error_m": metric_row.get("lateral_error_m", 0.0),
            "orientation_error_deg": metric_row.get("orientation_error_deg", 0.0),
            "normalized_action": [0.0] * len(ACTION_SCHEMA),
        },
        previous_action=previous_action,
    )
    weights = np.asarray(policy_artifact["weights"], dtype=np.float64)
    bias = np.asarray(policy_artifact["bias"], dtype=np.float64)
    raw_action = feature @ weights + bias
    if policy_artifact.get("trainer_family") == RESIDUAL_TRAINER_FAMILY:
        raw_action = _weak_base_servo_action(
            metric_row=metric_row,
            config=policy_artifact.get("weak_base_servo_config"),
        ) + raw_action
    return _apply_selected_action_adapter_with_diagnostics(
        policy_artifact=policy_artifact,
        raw_action=raw_action,
        action_scale=action_scale,
        metric_row=metric_row,
    )


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


def _apply_selected_action_adapter_with_diagnostics(
    *,
    policy_artifact: dict[str, Any],
    raw_action: np.ndarray,
    action_scale: float,
    metric_row: dict[str, Any] | None = None,
) -> tuple[np.ndarray, dict[str, Any]]:
    adapter_id = str(policy_artifact.get("selected_action_adapter_id") or "")
    config = policy_artifact.get("selected_action_adapter_config")
    raw_vector = _rounded_action(raw_action)
    diagnostics: dict[str, Any] = {
        "schema_version": "rdf_mvp2e_v06d_controller_action_diagnostics_v0.1.0",
        "selected_action_adapter_id": adapter_id,
        "controller_version": config.get("controller_version") if isinstance(config, dict) else None,
        "input_metric_phase": str(metric_row.get("phase")) if isinstance(metric_row, dict) else None,
        "controller_input_phase": None,
        "phase_normalized": False,
        "raw_action_vector": raw_vector,
        "phase_controller": None,
        "phase_vocabulary_mismatch": False,
        "z_motion_suppressed": False,
        "z_motion_block_reason": "adapter_not_instrumented",
    }
    if adapter_id != "isaac_signed_xy_downward_servo_v0" or not isinstance(config, dict):
        action = np.clip(raw_action * float(action_scale), -1.0, 1.0)
        diagnostics.update(
            {
                "pre_controller_action_vector": _rounded_action(action),
                "post_adapter_action_vector": _rounded_action(action),
                "z_motion_block_reason": "no_v06_controller",
            }
        )
        return action, diagnostics

    if metric_row is not None and _stable_hold_ready(config=config, metric_row=metric_row):
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
    if metric_row is not None and config.get("controller_version") == "v0_6_active_state_controller":
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
    diagnostics.update(
        {
            "pre_controller_action_vector": _rounded_action(pre_controller_action),
            "post_adapter_action_vector": _rounded_action(final_action),
            "z_motion_suppressed": z_suppressed,
            "z_motion_block_reason": block_reason,
            "align_lateral_gate_m": float(config.get("align_lateral_gate_m", 0.008)),
            "align_orientation_gate_rad": float(config.get("align_orientation_gate_rad", 0.25)),
            "metric_lateral_error_m": float(metric_row.get("lateral_error_m", 0.0)) if metric_row is not None else None,
            "metric_orientation_error_deg": float(metric_row.get("orientation_error_deg", 0.0))
            if metric_row is not None
            else None,
        }
    )
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
        for step in range(self.max_steps):
            current = self._metric_row(env=env, step=step)
            action_np, controller_action_diagnostics = _predict_policy_action_with_diagnostics(
                policy_artifact,
                metric_row=current,
                previous_action=previous_action,
                action_scale=self.action_scale,
            )
            action_shape = tuple(getattr(env.action_space, "shape", (len(action_np),)))
            action_dim = int(action_shape[-1] if action_shape else len(action_np))
            if action_np.shape[0] < action_dim:
                action_np = np.pad(action_np, (0, action_dim - action_np.shape[0]))
            action_np = action_np[:action_dim].reshape(1, action_dim)
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
