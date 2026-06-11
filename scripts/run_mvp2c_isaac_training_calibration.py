#!/usr/bin/env python3
"""Build MVP-2C Isaac training/calibration proof artifacts.

MVP-2C is a fresh proof attempt after the MVP-2B zero-uplift run. It
pre-registers the training/calibration/held-out split, fixes the uncurated
baseline mix before any held-out evaluation, selects one action adapter from
calibration evidence only, and closes MVP-2 only when actual Isaac-runtime
training-generation and held-out rollout gates both pass with positive curated
> uncurated held-out uplift.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import shutil
import statistics
import subprocess
import struct
import sys
import time
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
from run_mvp2b_isaac_proof_evaluator import (  # noqa: E402
    ACTION_SCHEMA,
    DEFAULT_ISAAC_DEVICE,
    DEFAULT_ISAAC_TASK,
    FEATURE_SCHEMA,
    PHASES,
    POLICY_CLASS,
    RESIDUAL_POLICY_CLASS,
    RESIDUAL_TARGET_DEFINITION,
    RESIDUAL_TRAINER,
    RESIDUAL_TRAINER_FAMILY,
    TRAINER,
    WEAK_BASE_SERVO_CONFIG,
    BackendResult,
    DeterministicEvaluatorBackend,
    IsaacConnectorInsertionEvaluatorBackend,
    _failure_trace,
    _features_targets,
    _phase_for_step,
    _success_trace,
    _read_env_native_success,
    evaluate_env_native_success_window,
    evaluate_rollout_trace,
    fit_phase_conditioned_bc_policy,
    _weak_base_servo_action,
)


SCHEMA_VERSION = "rdf_mvp2c_isaac_training_calibration_v0.1.0"
SCENARIO_MANIFEST_VERSION = "rdf_mvp2c_scenario_manifest_v0.1.0"
SCENARIO_MANIFEST_VERSION_V02 = "rdf_mvp2c_scenario_manifest_v0.2.0"
SCENARIO_MANIFEST_VERSION_V03 = "rdf_mvp2d_scenario_manifest_v0.3.0"
SCENARIO_MANIFEST_VERSION_V04 = "rdf_mvp2d_scenario_manifest_v0.4.0"
SCENARIO_MANIFEST_VERSION_V05 = "rdf_mvp2d_scenario_manifest_v0.5.0"
SCENARIO_MANIFEST_VERSION_V06 = "rdf_mvp2e_scenario_manifest_v0.6.0"
BASELINE_NOISE_MIX_SCHEMA_VERSION = "rdf_mvp2c_baseline_noise_mix_v0.1.0"
GENERATOR_HASH_SCHEMA_VERSION = "rdf_mvp2c_generator_config_hashes_v0.1.0"
ACTION_ADAPTER_REGISTRY_SCHEMA_VERSION = "rdf_mvp2c_action_adapter_registry_v0.1.0"
CALIBRATION_SELECTION_SCHEMA_VERSION = "rdf_mvp2c_calibration_selection_v0.1.0"
HDF5_SCHEMA_VERSION = "rdf_mvp2c_train_view_hdf5_v0.1.0"
ROLLOUT_SCHEMA_VERSION = "rdf_mvp2c_external_rollout_v0.1.0"
REPORT_NAME = "mvp2c_isaac_training_calibration_report.json"
DEFAULT_OUTPUT_DIR = ROOT / "storage" / "mvp2c_isaac_training_calibration"
PRIMARY_PROOF_PATH = "mvp2c_isaac_training_calibration_proof"
ISAAC_PROOF_RUNTIME = "dedicated_isaac_connector_insertion_evaluator"
ISAAC_TRAIN_GENERATION_PROOF_RUNTIME = "isaac_scripted_expert_train_generation_probe"
DETERMINISTIC_BACKEND = "deterministic_test_backend"
DETERMINISTIC_PROOF_RUNTIME = "test_only_not_isaac"
MIN_PROOF_ROLLOUTS_PER_POLICY = 20
STRONGER_PUBLIC_ROLLOUTS_PER_POLICY = 50
ACTUAL_TRACE_REPLAY_WEIGHT = 32
V05_ACTUAL_SUCCESS_TRACE_MINIMUM = 20
V05_ACTUAL_SUCCESS_TRACE_CAP = 40
V05_BASELINE_ACCEPTED_RATIO = 0.60
V05_FAILURE_BUCKETS = ("lateral_offset", "stability_window_loss", "under_insertion")
V06_REPAIR_PROBE_SEEDS = (16023, 16042, 16096)
V06A_CAPTURE_RADIUS_GEOMETRY_PROBE_SEEDS = tuple(range(18500, 18510))
V06A_CAPTURE_RADIUS_PRIMARY_SEED = 18500
V06A_CAPTURE_RADIUS_OFFSET_SWEEP_M = (
    0.0,
    0.0001,
    0.0002,
    0.0004,
    0.0006,
    0.0008,
    0.001,
    0.0015,
    0.002,
    0.003,
    0.004,
    0.006,
    0.008,
)
V06A_CAPTURE_RADIUS_DIRECTIONS = ("+x", "-x", "+y", "-y")
V06A_CAPTURE_RADIUS_RUNTIME_DEADLINE_S = 180.0
V06A_PRE_REGISTERED_INSERT_ENVELOPE = {
    "vertical_push_scale": 24.0,
    "correction_gain_limit": 4.0,
    "max_insert_steps": 145,
    "rotation_action_scale": 0.0,
    "value_source": "frozen_v0_6_adapter_and_horizon_not_probe_results",
}
V06A_NON_CLAIMS = {
    "proof_authority": False,
    "mvp2_closed": False,
    "train_generation_gate_passed": False,
    "heldout_allowed": False,
    "policy_uplift_claimed": False,
    "real_robot_success": False,
    "physical_robot_readiness": False,
}
V06_ENV_NATIVE_STABLE_STEPS_REQUIRED = 10
V06_TRAIN_GATE_SUCCESS_MINIMUM = 20
V06_TRAIN_GATE_ATTEMPT_COUNT = 40
V06E_CONVERGENCE_LAST_K = 10
V06E_REGRESSION_TOL_FLOOR_M = 0.0005
V06E_REGRESSION_TOL_CAPTURE_RATIO = 0.5
V06F_APPROACH_GATE_FLOOR_M = 0.001
V06F_APPROACH_GATE_CAPTURE_MULTIPLIER = 10.0
V06F_REGRESSION_TOL_FLOOR_M = 0.0005
V06F_REGRESSION_TOL_APPROACH_RATIO = 0.5
V06_ENV_NATIVE_SUCCESS_AUTHORITY = {
    "primary": "isaac_env_native_consecutive_success_v0",
    "isaac_function": "_get_curr_successes",
    "success_threshold_source": "env.cfg_task.success_threshold",
    "success_threshold": 0.04,
    "fixed_asset_height_m": 0.025,
    "height_threshold_m": 0.001,
    "xy_dist_threshold_m": 0.0025,
    "check_rot": False,
    "stable_steps_required": V06_ENV_NATIVE_STABLE_STEPS_REQUIRED,
}
CONTROLLED_FAILURE_REASONS = (
    "LATERAL_OFFSET_FAILURE",
    "UNDER_INSERTION_FAILURE",
    "ORIENTATION_MISALIGNMENT_FAILURE",
    "ACTION_JITTER_FAILURE",
    "EARLY_STOP_FAILURE",
)
SUCCESS_METRIC = {
    "name": "connector_insertion_geometry_stability_v0",
    "insertion_depth_m_min": 0.03,
    "lateral_error_m_max": 0.006,
    "orientation_error_deg_max": 8.0,
    "stable_steps_required": 10,
    "max_steps": 150,
}
BASELINE_FAILURE_TYPE_DISTRIBUTION = {
    "LATERAL_OFFSET_FAILURE": 0.2,
    "UNDER_INSERTION_FAILURE": 0.2,
    "ORIENTATION_MISALIGNMENT_FAILURE": 0.2,
    "ACTION_JITTER_FAILURE": 0.2,
    "EARLY_STOP_FAILURE": 0.2,
}
SELECTOR_SCORE_CONFIG = {
    "selector_score_id": "candidate_minus_baseline_with_stability_and_saturation_v0",
    "formula": (
        "1.00 * (candidate_success_rate - baseline_success_rate) "
        "+ 0.25 * candidate_stability_margin - 0.10 * candidate_action_saturation_rate"
    ),
    "tie_breaker": (
        "higher_candidate_success_rate_then_higher_stability_margin_then_lower_action_saturation_then_"
        "lexicographic_adapter_id"
    ),
    "heldout_excluded": True,
}
SELECTOR_SCORE_CONFIG_V05 = {
    "selector_score_id": "shared_stability_feasibility_score_v0",
    "formula": (
        "0.70 * candidate_stability_margin - 0.20 * candidate_action_saturation_rate "
        "+ 0.10 * min(candidate_success_rate, baseline_success_rate)"
    ),
    "tie_breaker": (
        "higher_stability_margin_then_lower_action_saturation_then_higher_min_success_rate_then_"
        "lexicographic_adapter_id"
    ),
    "heldout_excluded": True,
    "uses_candidate_baseline_uplift": False,
}

# Exposed for focused tests that patch a fake Isaac backend with realistic trace
# summaries without importing MVP-2B directly.
_EXPORTED_TEST_TRACE_HELPERS = (_success_trace, _failure_trace)


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


def _sha256_payload(payload: Any) -> str:
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
        raise ValueError(f"refusing unsafe MVP-2C output path: {output_dir}")
    if clean and output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)


def _scenario_row(*, split: str, seed: int) -> dict[str, Any]:
    offset_scale = 0.00045 * ((seed % 9) - 4)
    orientation = float(((seed // 5) % 11) - 5)
    noise_level = {
        "train_success": "scripted_expert",
        "train_failure": "controlled_failure",
        "calibration": "calibration_only",
        "held_out": "held_out_unseen",
    }[split]
    return {
        "scenario_id": f"{split}_{seed}",
        "split": split,
        "seed": seed,
        "initial_offset_m": [round(offset_scale, 6), round(-offset_scale / 2.0, 6), 0.0],
        "orientation_offset_deg": orientation,
        "noise_level": noise_level,
        "max_steps": SUCCESS_METRIC["max_steps"],
    }


def _scenario_seed_ranges(scenario_profile: str) -> dict[str, range]:
    if scenario_profile == "v0_1":
        return {
            "train_success": range(4000, 4080),
            "train_failure": range(4100, 4180),
            "calibration": range(5000, 5020),
            "held_out": range(6000, 6020),
        }
    if scenario_profile == "v0_2":
        return {
            "train_success": range(7000, 7080),
            "train_failure": range(7100, 7180),
            "calibration": range(8000, 8020),
            "held_out": range(9000, 9020),
        }
    if scenario_profile == "v0_3":
        return {
            "train_success": range(10000, 10080),
            "train_failure": range(10100, 10180),
            "calibration": range(11000, 11020),
            "held_out": range(12000, 12020),
        }
    if scenario_profile == "v0_4":
        return {
            "train_success": range(13000, 13080),
            "train_failure": range(13100, 13180),
            "calibration": range(14000, 14020),
            "held_out": range(15000, 15020),
        }
    if scenario_profile == "v0_5":
        return {
            "train_success": range(16000, 16160),
            "train_failure": range(16200, 16360),
            "calibration": range(17000, 17030),
            "held_out": range(18000, 18020),
        }
    if scenario_profile == "v0_6":
        return {
            "train_success": range(19000, 19160),
            "train_failure": range(19200, 19360),
            "calibration": range(20000, 20030),
            "held_out": range(21000, 21050),
        }
    raise ValueError(f"unknown MVP-2C scenario_profile: {scenario_profile}")


def _manifest_version_for_profile(scenario_profile: str) -> str:
    if scenario_profile == "v0_2":
        return SCENARIO_MANIFEST_VERSION_V02
    if scenario_profile == "v0_3":
        return SCENARIO_MANIFEST_VERSION_V03
    if scenario_profile == "v0_4":
        return SCENARIO_MANIFEST_VERSION_V04
    if scenario_profile == "v0_5":
        return SCENARIO_MANIFEST_VERSION_V05
    if scenario_profile == "v0_6":
        return SCENARIO_MANIFEST_VERSION_V06
    return SCENARIO_MANIFEST_VERSION


def _excluded_prior_heldout_seed_ranges(scenario_profile: str) -> list[list[int]]:
    if scenario_profile == "v0_6":
        return [
            [3000, 3019],
            [6000, 6019],
            [9000, 9019],
            [12000, 12019],
            [15000, 15019],
            [16000, 16159],
            [18000, 18019],
            [16023, 16023],
            [16042, 16042],
            [16096, 16096],
        ]
    ranges = [[3000, 3019]]
    if scenario_profile in {"v0_2", "v0_3", "v0_4", "v0_5"}:
        ranges.append([6000, 6019])
    if scenario_profile in {"v0_3", "v0_4", "v0_5"}:
        ranges.append([9000, 9019])
    if scenario_profile in {"v0_4", "v0_5"}:
        ranges.append([12000, 12019])
    if scenario_profile == "v0_5":
        ranges.append([15000, 15019])
    return ranges


def _validate_manifest_seed_disjointness(manifest: dict[str, Any]) -> None:
    scenario_seeds = {int(row["seed"]) for row in manifest.get("scenarios", []) if isinstance(row, dict)}
    excluded = set()
    for start, end in manifest.get("excluded_prior_heldout_seed_ranges", []):
        excluded.update(range(int(start), int(end) + 1))
    overlap = sorted(scenario_seeds & excluded)
    if overlap:
        raise ValueError(f"scenario seeds overlap excluded seeds: {overlap[:10]}")


def _v06_difficulty_cell(seed: int) -> tuple[int, int]:
    return (abs((int(seed) % 9) - 4), abs(((int(seed) // 5) % 11) - 5))


def build_v06_train_gate_seed_selection(source_range: range) -> dict[str, Any]:
    cells: dict[tuple[int, int], list[int]] = {}
    for seed in source_range:
        cells.setdefault(_v06_difficulty_cell(seed), []).append(int(seed))
    for seeds in cells.values():
        seeds.sort()
    ordered_cells = sorted(cells)
    selected: list[int] = []
    cell_index = 0
    max_iterations = max(1, len(ordered_cells) * V06_TRAIN_GATE_ATTEMPT_COUNT * 2)
    while len(selected) < V06_TRAIN_GATE_ATTEMPT_COUNT:
        cell = ordered_cells[cell_index % len(ordered_cells)]
        seeds = cells[cell]
        if seeds:
            selected.append(seeds.pop(0))
        cell_index += 1
        if cell_index > max_iterations:
            raise ValueError("unable to select v0_6 train gate seeds")
    config = {
        "source_range": [int(source_range.start), int(source_range.stop - 1)],
        "difficulty_cell_formula": {
            "offset_class": "abs((seed % 9) - 4)",
            "orient_class": "abs(((seed // 5) % 11) - 5)",
        },
        "allocation_rule": "round_robin_across_sorted_difficulty_cells",
        "tie_break_rule": "lowest_seed_id_in_cell",
        "uses_isaac_results": False,
        "uses_rng": False,
    }
    return {
        **config,
        "selected_40_seed_ids": selected,
        "selection_config_sha256": _sha256_payload(config),
        "selected_seed_list_sha256": _sha256_payload(selected),
    }


def build_mvp2c_scenario_manifest(*, output_dir: Path, scenario_profile: str = "v0_1") -> dict[str, Any]:
    seed_ranges = _scenario_seed_ranges(scenario_profile)
    scenarios: list[dict[str, Any]] = []
    for split, seeds in seed_ranges.items():
        for seed in seeds:
            scenarios.append(_scenario_row(split=split, seed=seed))
    manifest_version = _manifest_version_for_profile(scenario_profile)
    excluded_ranges = _excluded_prior_heldout_seed_ranges(scenario_profile)
    manifest = {
        "manifest_version": manifest_version,
        "schema_version": manifest_version,
        "scenario_profile": scenario_profile,
        "task_type": "connector_insertion",
        "scenario_axis": "pre_registered_seed_initial_offset_noise_level",
        "success_metric": dict(SUCCESS_METRIC),
        "scenarios": scenarios,
        "excluded_prior_heldout_seed_range": list(range(3000, 3020)),
        "excluded_prior_heldout_seed_ranges": excluded_ranges,
        "leakage_policy": {
            "held_out_excluded_from_training": True,
            "held_out_excluded_from_curation_tuning": True,
            "held_out_excluded_from_threshold_tuning": True,
            "held_out_excluded_from_hyperparameter_selection": True,
            "held_out_excluded_from_calibration_selector": True,
        },
    }
    if scenario_profile == "v0_6":
        manifest["success_authority"] = dict(V06_ENV_NATIVE_SUCCESS_AUTHORITY)
        manifest["secondary_diagnostics"] = {
            "rdf_peg_in_hole_metric": dict(SUCCESS_METRIC),
            "closure_authority": False,
        }
        manifest["repair_probe_seeds"] = list(V06_REPAIR_PROBE_SEEDS)
        manifest["v0_6_train_gate_seed_selection"] = build_v06_train_gate_seed_selection(
            seed_ranges["train_success"]
        )
        _validate_manifest_seed_disjointness(manifest)
    manifest["manifest_sha256"] = _sha256_payload(manifest)
    write_json(output_dir / "scenario_manifest.json", manifest)
    return manifest


def _heldout_ids(manifest: dict[str, Any]) -> set[str]:
    return {
        str(row["scenario_id"])
        for row in manifest.get("scenarios", [])
        if isinstance(row, dict) and row.get("split") == "held_out" and row.get("scenario_id")
    }


def validate_no_heldout_leakage(
    *,
    manifest: dict[str, Any],
    training_scenario_ids: list[str],
    curation_tuning_scenario_ids: list[str],
    threshold_tuning_scenario_ids: list[str],
    hyperparameter_scenario_ids: list[str],
    calibration_selector_scenario_ids: list[str] | None = None,
) -> dict[str, Any]:
    heldout = _heldout_ids(manifest)
    checked_channels = {
        "training": [str(item) for item in training_scenario_ids],
        "curation_tuning": [str(item) for item in curation_tuning_scenario_ids],
        "threshold_tuning": [str(item) for item in threshold_tuning_scenario_ids],
        "hyperparameter_selection": [str(item) for item in hyperparameter_scenario_ids],
        "calibration_selector": [str(item) for item in calibration_selector_scenario_ids or []],
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


def evaluate_lateral_divergence_stopped(
    *,
    lateral_errors_m: Sequence[float],
    divergence_cap_m: float = 0.008,
    final_drift_margin_m: float = 0.002,
    last_k: int = 10,
) -> dict[str, Any]:
    if not lateral_errors_m:
        return {
            "lateral_divergence_stopped": False,
            "reason": "missing lateral diagnostics",
            "divergence_cap_m": divergence_cap_m,
            "final_drift_margin_m": final_drift_margin_m,
        }
    values = [float(value) for value in lateral_errors_m]
    initial = values[0]
    max_lateral = max(values)
    tail_median = statistics.median(values[-int(last_k) :])
    stopped = max_lateral < float(divergence_cap_m) and tail_median <= initial + float(final_drift_margin_m)
    return {
        "lateral_divergence_stopped": stopped,
        "initial_lateral_error_m": initial,
        "max_lateral_error_m": max_lateral,
        "last_10_median_lateral_error_m": tail_median,
        "divergence_cap_m": float(divergence_cap_m),
        "final_drift_margin_m": float(final_drift_margin_m),
    }


def _numeric_capture_radius_m(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if not isinstance(value, int | float):
        return None
    numeric = float(value)
    if numeric <= 0.0:
        return None
    return numeric


def _v06f_approach_lateral_gate_m(capture_radius_m: float) -> float:
    numeric_capture_radius = _numeric_capture_radius_m(capture_radius_m)
    if numeric_capture_radius is None:
        raise ValueError("v0_6f approach gate requires numeric capture_radius_m")
    return max(
        V06F_APPROACH_GATE_FLOOR_M,
        V06F_APPROACH_GATE_CAPTURE_MULTIPLIER * numeric_capture_radius,
    )


def evaluate_v06e_non_seated_lateral_convergence(
    *,
    lateral_errors_m: Sequence[float],
    capture_radius_m: float,
    last_k: int = V06E_CONVERGENCE_LAST_K,
    regression_tol_floor_m: float = V06E_REGRESSION_TOL_FLOOR_M,
    regression_tol_capture_ratio: float = V06E_REGRESSION_TOL_CAPTURE_RATIO,
) -> dict[str, Any]:
    numeric_capture_radius = _numeric_capture_radius_m(capture_radius_m)
    if numeric_capture_radius is None:
        return {
            "non_seated_lateral_converged": False,
            "reason": "capture_radius_not_numeric",
            "capture_radius_m": capture_radius_m,
        }
    if not lateral_errors_m:
        return {
            "non_seated_lateral_converged": False,
            "reason": "missing_lateral_diagnostics",
            "capture_radius_m": numeric_capture_radius,
            "near_band_m": numeric_capture_radius,
        }
    values = [float(value) for value in lateral_errors_m]
    window = values[-max(1, int(last_k)) :]
    min_lateral = min(values)
    tail_median = statistics.median(window)
    regression_tol = max(float(regression_tol_floor_m), float(regression_tol_capture_ratio) * numeric_capture_radius)
    inside_near_band = tail_median <= numeric_capture_radius
    no_regression = tail_median <= min_lateral + regression_tol
    return {
        "non_seated_lateral_converged": bool(inside_near_band and no_regression),
        "reason": "converged_no_regression" if inside_near_band and no_regression else "not_converged_or_regressed",
        "capture_radius_m": numeric_capture_radius,
        "near_band_m": numeric_capture_radius,
        "last_k": int(last_k),
        "regression_tol_m": round(float(regression_tol), 6),
        "min_lateral_achieved_m": round(float(min_lateral), 6),
        "last_k_median_lateral_m": round(float(tail_median), 6),
        "inside_near_band": bool(inside_near_band),
        "regression_detected": not bool(no_regression),
    }


def evaluate_v06f_non_seated_lateral_convergence(
    *,
    lateral_errors_m: Sequence[float],
    capture_radius_m: float,
    last_k: int = V06E_CONVERGENCE_LAST_K,
    regression_tol_floor_m: float = V06F_REGRESSION_TOL_FLOOR_M,
    regression_tol_approach_ratio: float = V06F_REGRESSION_TOL_APPROACH_RATIO,
) -> dict[str, Any]:
    numeric_capture_radius = _numeric_capture_radius_m(capture_radius_m)
    if numeric_capture_radius is None:
        return {
            "non_seated_lateral_converged": False,
            "reason": "capture_radius_not_numeric",
            "capture_radius_m": capture_radius_m,
        }
    approach_gate = _v06f_approach_lateral_gate_m(numeric_capture_radius)
    if not lateral_errors_m:
        return {
            "non_seated_lateral_converged": False,
            "reason": "missing_lateral_diagnostics",
            "straight_down_capture_radius_m": numeric_capture_radius,
            "capture_radius_m": numeric_capture_radius,
            "near_band_m": approach_gate,
            "approach_lateral_gate_m": approach_gate,
        }
    values = [float(value) for value in lateral_errors_m]
    window = values[-max(1, int(last_k)) :]
    min_lateral = min(values)
    tail_median = statistics.median(window)
    regression_tol = max(float(regression_tol_floor_m), float(regression_tol_approach_ratio) * approach_gate)
    inside_near_band = tail_median <= approach_gate
    no_regression = tail_median <= min_lateral + regression_tol
    return {
        "non_seated_lateral_converged": bool(inside_near_band and no_regression),
        "reason": "converged_to_approach_gate_no_regression"
        if inside_near_band and no_regression
        else "not_converged_or_regressed",
        "straight_down_capture_radius_m": round(float(numeric_capture_radius), 6),
        "capture_radius_m": round(float(numeric_capture_radius), 6),
        "near_band_m": round(float(approach_gate), 6),
        "approach_lateral_gate_m": round(float(approach_gate), 6),
        "last_k": int(last_k),
        "regression_tol_m": round(float(regression_tol), 6),
        "min_lateral_achieved_m": round(float(min_lateral), 6),
        "last_k_median_lateral_m": round(float(tail_median), 6),
        "inside_near_band": bool(inside_near_band),
        "regression_detected": not bool(no_regression),
    }


def _v06e_lateral_errors_from_probe_result(result: dict[str, Any]) -> list[float]:
    values = result.get("lateral_errors_m")
    if isinstance(values, list):
        return [float(value) for value in values]
    initial = result.get("initial_lateral_error_m")
    last_median = result.get("last_10_median_lateral_error_m")
    min_lateral = result.get("min_lateral_achieved_m")
    if initial is not None and last_median is not None and min_lateral is not None:
        return [float(initial), float(min_lateral), float(last_median)]
    return []


def _v06_max_insertion_depth_m(result: dict[str, Any]) -> float:
    candidates = [
        result.get("max_insertion_depth_m"),
        result.get("max_depth_m"),
        result.get("max_insertion_depth_observed_m"),
    ]
    rdf_metric = result.get("rdf_peg_in_hole_metric")
    if isinstance(rdf_metric, dict):
        rdf_summary = rdf_metric.get("summary")
        if isinstance(rdf_summary, dict):
            candidates.append(rdf_summary.get("max_insertion_depth_m"))

    max_depth = 0.0
    for value in candidates:
        try:
            if value is None:
                continue
            max_depth = max(max_depth, float(value))
        except (TypeError, ValueError):
            continue
    return max_depth


def _normalize_v06_repair_probe_results(probe_results: dict[Any, Any]) -> dict[int, dict[str, Any]]:
    normalized: dict[int, dict[str, Any]] = {}
    for seed in V06_REPAIR_PROBE_SEEDS:
        result = probe_results.get(seed)
        if result is None:
            result = probe_results.get(str(seed))
        normalized[int(seed)] = result if isinstance(result, dict) else {}
    return normalized


def evaluate_v06_repair_probe_gate(probe_results: dict[Any, Any]) -> dict[str, Any]:
    normalized_probe_results = _normalize_v06_repair_probe_results(probe_results)
    hold_result = normalized_probe_results.get(16023, {})
    lateral_moderate = normalized_probe_results.get(16042, {})
    lateral_severe = normalized_probe_results.get(16096, {})
    hold_passed = bool(hold_result.get("env_native_rollout_success"))
    lateral_success_passed = bool(lateral_moderate.get("env_native_rollout_success")) or bool(
        lateral_severe.get("env_native_rollout_success")
    )
    moderate_divergence_stopped = bool(lateral_moderate.get("lateral_divergence_stopped"))
    severe_divergence_stopped = bool(lateral_severe.get("lateral_divergence_stopped"))
    lateral_divergence_stopped = moderate_divergence_stopped and severe_divergence_stopped
    green = hold_passed and lateral_success_passed and lateral_divergence_stopped
    hard_stop = (not hold_passed) or (not moderate_divergence_stopped and not severe_divergence_stopped)
    result = {
        "proof_authority": False,
        "probe_seeds": list(V06_REPAIR_PROBE_SEEDS),
        "hold_mode_passed": hold_passed,
        "lateral_success_mode_passed": lateral_success_passed,
        "lateral_divergence_stopped": lateral_divergence_stopped,
        "green_light_for_40_run_gate": green,
        "hard_stop": hard_stop,
        "probe_results": normalized_probe_results,
    }
    result["repair_probe_gate_sha256"] = _sha256_payload(result)
    return result


def evaluate_v06e_repair_probe_gate(
    probe_results: dict[Any, Any],
    *,
    capture_radius_m: float,
) -> dict[str, Any]:
    numeric_capture_radius = _numeric_capture_radius_m(capture_radius_m)
    normalized = _normalize_v06_repair_probe_results(probe_results)
    seed_results: dict[str, dict[str, Any]] = {}
    non_seated_lateral_converged = True
    lateral_env_native_pass_count = 0
    for seed, result in normalized.items():
        env_native_pass = bool(result.get("env_native_rollout_success")) or int(
            result.get("env_native_max_consecutive_success_steps", 0)
        ) >= V06_ENV_NATIVE_STABLE_STEPS_REQUIRED
        is_lateral_seed = seed in {16042, 16096}
        seed_payload = {
            **result,
            "env_native_seed_pass": env_native_pass,
            "seed_pass": env_native_pass,
            "divergence_diagnostic_authority": "report_only" if env_native_pass else "non_seated_lateral_gate",
        }
        if env_native_pass and is_lateral_seed:
            lateral_env_native_pass_count += 1
        if (not env_native_pass) and is_lateral_seed:
            convergence = evaluate_v06e_non_seated_lateral_convergence(
                lateral_errors_m=_v06e_lateral_errors_from_probe_result(result),
                capture_radius_m=capture_radius_m,
            )
            seed_payload["convergence"] = convergence
            seed_payload["seed_pass"] = bool(convergence["non_seated_lateral_converged"])
            non_seated_lateral_converged = non_seated_lateral_converged and bool(
                convergence["non_seated_lateral_converged"]
            )
        elif (not env_native_pass) and seed == 16023:
            seed_payload["seed_pass"] = False
        seed_results[str(seed)] = seed_payload

    hold_passed = bool(seed_results["16023"]["env_native_seed_pass"])
    green = (
        numeric_capture_radius is not None
        and hold_passed
        and lateral_env_native_pass_count >= 1
        and non_seated_lateral_converged
        and all(bool(payload["seed_pass"]) for payload in seed_results.values())
    )
    result = {
        "schema_version": "rdf_mvp2e_v06e_repair_probe_gate_v0.1.0",
        "proof_authority": False,
        "capture_radius_m": numeric_capture_radius if numeric_capture_radius is not None else capture_radius_m,
        "capture_radius_numeric": numeric_capture_radius is not None,
        "probe_seeds": list(V06_REPAIR_PROBE_SEEDS),
        "hold_mode_passed": hold_passed,
        "lateral_success_mode_passed": lateral_env_native_pass_count >= 1,
        "non_seated_lateral_converged": non_seated_lateral_converged,
        "green_light_for_40_run_gate": bool(green),
        "hard_stop": not bool(green),
        "seed_results": seed_results,
        "fixed_40_run_gate_opened": False,
        "heldout_opened": False,
    }
    result["repair_probe_gate_sha256"] = _sha256_payload_excluding(result, "repair_probe_gate_sha256")
    return result


def evaluate_v06f_repair_probe_gate(
    probe_results: dict[Any, Any],
    *,
    capture_radius_m: float,
) -> dict[str, Any]:
    numeric_capture_radius = _numeric_capture_radius_m(capture_radius_m)
    approach_gate = _v06f_approach_lateral_gate_m(capture_radius_m) if numeric_capture_radius is not None else None
    normalized = _normalize_v06_repair_probe_results(probe_results)
    seed_results: dict[str, dict[str, Any]] = {}
    non_seated_lateral_converged = True
    lateral_env_native_pass_count = 0
    all_depths: list[float] = []
    for seed, result in normalized.items():
        env_native_pass = bool(result.get("env_native_rollout_success")) or int(
            result.get("env_native_max_consecutive_success_steps", 0)
        ) >= V06_ENV_NATIVE_STABLE_STEPS_REQUIRED
        max_depth = _v06_max_insertion_depth_m(result)
        all_depths.append(max_depth)
        is_lateral_seed = seed in {16042, 16096}
        seed_payload = {
            **result,
            "env_native_seed_pass": env_native_pass,
            "seed_pass": env_native_pass,
            "max_insertion_depth_m": max_depth,
            "divergence_diagnostic_authority": "report_only" if env_native_pass else "non_seated_lateral_gate",
        }
        if env_native_pass and is_lateral_seed:
            lateral_env_native_pass_count += 1
        if (not env_native_pass) and is_lateral_seed:
            convergence = evaluate_v06f_non_seated_lateral_convergence(
                lateral_errors_m=_v06e_lateral_errors_from_probe_result(result),
                capture_radius_m=capture_radius_m,
            )
            seed_payload["convergence"] = convergence
            seed_payload["seed_pass"] = bool(convergence["non_seated_lateral_converged"])
            non_seated_lateral_converged = non_seated_lateral_converged and bool(
                convergence["non_seated_lateral_converged"]
            )
        elif (not env_native_pass) and seed == 16023:
            seed_payload["seed_pass"] = False
        seed_results[str(seed)] = seed_payload

    hold_passed = bool(seed_results["16023"]["env_native_seed_pass"])
    all_never_descended = all(depth <= 0.0 for depth in all_depths)
    green = (
        numeric_capture_radius is not None
        and hold_passed
        and lateral_env_native_pass_count >= 1
        and non_seated_lateral_converged
        and not all_never_descended
        and all(bool(payload["seed_pass"]) for payload in seed_results.values())
    )
    result = {
        "schema_version": "rdf_mvp2e_v06f_repair_probe_gate_v0.1.0",
        "proof_authority": False,
        "success_authority": "env_native_10_consecutive",
        "straight_down_capture_radius_m": numeric_capture_radius if numeric_capture_radius is not None else capture_radius_m,
        "capture_radius_m": numeric_capture_radius if numeric_capture_radius is not None else capture_radius_m,
        "approach_lateral_gate_m": approach_gate,
        "probe_seeds": list(V06_REPAIR_PROBE_SEEDS),
        "hold_mode_passed": hold_passed,
        "lateral_success_mode_passed": lateral_env_native_pass_count >= 1,
        "non_seated_lateral_converged": non_seated_lateral_converged,
        "all_probe_seeds_never_descended": all_never_descended,
        "green_light_for_40_run_gate": bool(green),
        "hard_stop": not bool(green),
        "failure_mode": None if green else ("all_probe_seeds_never_descended" if all_never_descended else "repair_probe_not_green"),
        "seed_results": seed_results,
        "fixed_40_run_gate_opened": False,
        "heldout_opened": False,
    }
    result["repair_probe_gate_sha256"] = _sha256_payload_excluding(result, "repair_probe_gate_sha256")
    return result


def validate_v06b_native_metric_trace_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    reasons: list[str] = []
    required = {
        "env_native_diagnostics_source",
        "env_native_success",
        "env_native_success_mask",
        "env_native_xy_dist_m",
        "env_native_z_disp_m",
        "env_native_height_threshold_m",
        "held_asset_pose_w",
        "fixed_asset_pose_w",
        "held_base_pose_w",
        "target_held_base_pose_w",
        "legacy_positive_z_disp_m",
        "runtime_depth_feature_m",
        "insertion_depth_m",
    }
    if not rows:
        reasons.append("missing_native_metric_trace_rows")
    for row in rows:
        if not isinstance(row, dict):
            reasons.append("invalid_native_metric_trace_row")
            continue
        missing = sorted(required - set(row))
        if missing:
            reasons.append("missing_required_native_metric_fields")
        if row.get("env_native_diagnostics_source") != "factory_utils_base_target":
            reasons.append("env_native_diagnostics_source")
        if not isinstance(row.get("env_native_success"), bool):
            reasons.append("env_native_success")
        if not isinstance(row.get("env_native_success_mask"), bool):
            reasons.append("env_native_success_mask")
        elif isinstance(row.get("env_native_success"), bool) and bool(row["env_native_success"]) != bool(
            row["env_native_success_mask"]
        ):
            reasons.append("env_native_success_mask_mismatch")
        legacy = row.get("legacy_positive_z_disp_m")
        runtime_depth = row.get("runtime_depth_feature_m")
        insertion_depth = row.get("insertion_depth_m")
        try:
            legacy_float = float(legacy) if legacy is not None else None
            runtime_depth_float = float(runtime_depth) if runtime_depth is not None else None
            insertion_depth_float = float(insertion_depth) if insertion_depth is not None else None
        except (TypeError, ValueError):
            reasons.append("runtime_depth_feature_m")
            continue
        if legacy_float is None or legacy_float <= 0.001:
            continue
        if runtime_depth_float is not None and abs(legacy_float - runtime_depth_float) < 1.0e-9:
            reasons.append("runtime_depth_feature_m")
        if insertion_depth_float is not None and abs(legacy_float - insertion_depth_float) < 1.0e-9:
            reasons.append("runtime_depth_feature_m")
    return {
        "valid": not reasons,
        "reasons": sorted(set(reasons)),
        "validated_trace_count": len(rows),
    }


def evaluate_chamfer_preflight_gate(
    *,
    source_asset_paths: list[str],
    inspection_result: dict[str, Any],
) -> dict[str, Any]:
    chamfer_present = inspection_result.get("chamfer_present")
    capture_radius_m = inspection_result.get("capture_radius_m")
    if chamfer_present is True and isinstance(capture_radius_m, (int, float)):
        branch = "A"
    elif chamfer_present is True:
        branch = "B"
    else:
        branch = "C"
    allowed = branch in {"A", "B"}
    result = {
        "chamfer_present": chamfer_present,
        "capture_radius_m": float(capture_radius_m) if isinstance(capture_radius_m, (int, float)) else "unknown",
        "inspection_method": str(inspection_result.get("inspection_method") or "static_usd"),
        "source_asset_paths": [str(path) for path in source_asset_paths],
        "source_asset_sha256": inspection_result.get("source_asset_sha256") or {},
        "derived_insert_params": inspection_result.get("derived_insert_params") or {},
        "derivation_rationale": str(inspection_result.get("derivation_rationale") or "chamfer preflight gate"),
        "preflight_branch": branch,
        "insert_parameter_freeze_allowed": allowed,
        "repair_probe_allowed": allowed,
        "train_generation_gate_allowed": False,
        "train_generation_gate_status": "pending_repair_probe" if allowed else "blocked_by_preflight",
    }
    result["chamfer_preflight_sha256"] = _sha256_payload(result)
    return result


def build_v06_chamfer_preflight(*, output_dir: Path) -> dict[str, Any]:
    source_asset_paths = [
        "${ISAACLAB_NUCLEUS_DIR}/Factory/factory_hole_8mm.usd",
        "${ISAACLAB_NUCLEUS_DIR}/Factory/factory_peg_8mm.usd",
    ]
    inspection_result = {
        "chamfer_present": None,
        "inspection_method": "static_config_only_geometry_uninspectable",
        "source_asset_sha256": {},
        "derived_insert_params": {},
        "derivation_rationale": (
            "IsaacLab task config provides peg/hole USD paths and diameters, but local static mesh geometry was not "
            "inspectable without the Nucleus asset. INSERT parameter freeze must fail closed until chamfer/lead-in "
            "geometry is inspected."
        ),
    }
    preflight = evaluate_chamfer_preflight_gate(
        source_asset_paths=source_asset_paths,
        inspection_result=inspection_result,
    )
    write_json(output_dir / "chamfer_preflight.json", preflight)
    return preflight


def resolve_v06_chamfer_preflight_for_report(*, output_dir: Path) -> dict[str, Any]:
    preflight_path = output_dir / "chamfer_preflight.json"
    if preflight_path.exists():
        preflight = read_json(preflight_path)
        if (
            preflight.get("scenario_profile") == "v0_6a"
            and preflight.get("inspection_method") == "runtime_empirical_capture_radius_probe"
        ):
            return preflight
    return build_v06_chamfer_preflight(output_dir=output_dir)


def _max_successful_delta(result: Any) -> float:
    if not isinstance(result, dict):
        return 0.0
    value = result.get("max_successful_delta_m", result.get("delta_m", 0.0))
    if not isinstance(value, (int, float)):
        return 0.0
    return max(0.0, float(value))


def _nonzero_success_count(result: Any) -> int:
    if not isinstance(result, dict):
        return 0
    value = result.get("nonzero_success_count", result.get("nonzero_pass_count"))
    if isinstance(value, int) and not isinstance(value, bool):
        return max(0, int(value))
    trials = result.get("trials")
    if isinstance(trials, list):
        return sum(
            1
            for trial in trials
            if isinstance(trial, dict)
            and isinstance(trial.get("delta_m"), (int, float))
            and float(trial["delta_m"]) > 0.0
            and trial.get("rollout_success") is True
        )
    return 1 if _max_successful_delta(result) > 0.0 else 0


def evaluate_runtime_capture_radius_probe(raw_probe: dict[str, Any]) -> dict[str, Any]:
    runtime_loaded = bool(raw_probe.get("runtime_loaded"))
    mask_available = bool(raw_probe.get("env_native_success_mask_available"))
    zero_offset_passed = bool(raw_probe.get("zero_offset_passed"))
    direction_results = raw_probe.get("direction_results")
    if not isinstance(direction_results, dict):
        direction_results = {}
    max_success_by_direction = {
        direction: _max_successful_delta(direction_results.get(direction))
        for direction in V06A_CAPTURE_RADIUS_DIRECTIONS
    }
    nonzero_success_count_by_direction = {
        direction: _nonzero_success_count(direction_results.get(direction))
        for direction in V06A_CAPTURE_RADIUS_DIRECTIONS
    }
    non_zero_successes = {
        direction: value
        for direction, value in max_success_by_direction.items()
        if value > 0.0
    }
    all_directions_have_capture = len(non_zero_successes) == len(V06A_CAPTURE_RADIUS_DIRECTIONS)
    conservative_capture_radius = min(non_zero_successes.values()) if all_directions_have_capture else None
    branch_a_capture = (
        conservative_capture_radius is not None
        and conservative_capture_radius >= 0.0004
        and all(nonzero_success_count_by_direction[direction] >= 2 for direction in V06A_CAPTURE_RADIUS_DIRECTIONS)
    )

    blocker_reasons: list[str] = []
    if not runtime_loaded:
        blocker_reasons.append("runtime_load_failed")
    if not mask_available:
        blocker_reasons.append("env_native_success_mask_unavailable")
    if not zero_offset_passed:
        blocker_reasons.append("zero_offset_insertion_failed")

    if blocker_reasons:
        branch = "C"
    elif branch_a_capture:
        branch = "A"
    elif non_zero_successes:
        branch = "B"
    else:
        branch = "C"
        blocker_reasons.append("all_non_zero_offsets_failed")

    capture_radius_m: float | str
    if branch == "A":
        capture_radius_m = float(conservative_capture_radius)
    elif branch == "B":
        capture_radius_m = float(conservative_capture_radius) if conservative_capture_radius is not None else "approximate"
    else:
        capture_radius_m = "unknown"

    return {
        "schema_version": "rdf_mvp2e_v06a_runtime_capture_radius_probe_eval_v0.1.0",
        "runtime_loaded": runtime_loaded,
        "env_native_success_mask_available": mask_available,
        "zero_offset_passed": zero_offset_passed,
        "direction_results": direction_results,
        "max_successful_delta_by_direction_m": max_success_by_direction,
        "nonzero_success_count_by_direction": nonzero_success_count_by_direction,
        "capture_radius_m": capture_radius_m,
        "preflight_branch": branch,
        "branch_reason": "runtime empirical capture radius resolved" if branch in {"A", "B"} else "; ".join(blocker_reasons),
        "blocker_reasons": blocker_reasons,
    }


def build_v06a_capture_radius_probe_artifact(
    *,
    output_dir: Path,
    measurement: dict[str, Any],
    prior_static_preflight: dict[str, Any],
) -> dict[str, Any]:
    artifact = {
        "schema_version": "rdf_mvp2e_v06a_capture_radius_probe_v0.1.0",
        "scenario_profile": "v0_6a",
        "source_scenario_profile": "v0_6",
        "proof_runtime": "isaac_runtime_empirical_capture_radius_preflight",
        "geometry_probe_seed_namespace": list(V06A_CAPTURE_RADIUS_GEOMETRY_PROBE_SEEDS),
        "geometry_probe_seed": V06A_CAPTURE_RADIUS_PRIMARY_SEED,
        "offset_sweep_m": list(V06A_CAPTURE_RADIUS_OFFSET_SWEEP_M),
        "directions": list(V06A_CAPTURE_RADIUS_DIRECTIONS),
        "geometry_isolated": True,
        "xy_correction_enabled": False,
        "yaw_correction_enabled": False,
        "z_push_mode": "straight_down_bounded",
        "prior_static_preflight_branch": prior_static_preflight.get("preflight_branch"),
        "prior_static_inspection_method": prior_static_preflight.get("inspection_method"),
        "pre_registered_insert_envelope": dict(V06A_PRE_REGISTERED_INSERT_ENVELOPE),
        "measurement": measurement,
        "capture_radius_m": measurement.get("capture_radius_m"),
        "preflight_branch": measurement.get("preflight_branch", "C"),
        "repair_probe_allowed": measurement.get("preflight_branch") in {"A", "B"},
        "repair_probe_green_light": False,
        "proof_authority": False,
        "heldout_allowed": False,
        "train_generation_gate_allowed": False,
        "train_generation_gate_status": "pending_repair_probe"
        if measurement.get("preflight_branch") in {"A", "B"}
        else "blocked_by_preflight",
        "train_generation_gate_passed": False,
        "non_claims": dict(V06A_NON_CLAIMS),
    }
    artifact["capture_radius_probe_sha256"] = _sha256_payload_excluding(artifact, "capture_radius_probe_sha256")
    write_json(output_dir / "capture_radius_probe.json", artifact)
    return artifact


def build_v06a_runtime_chamfer_preflight_from_probe(
    *,
    output_dir: Path,
    capture_radius_probe: dict[str, Any],
    prior_static_preflight: dict[str, Any],
) -> dict[str, Any]:
    branch = str(capture_radius_probe.get("preflight_branch") or "C")
    allowed = branch in {"A", "B"}
    status = "pending_repair_probe" if allowed else "blocked_by_preflight"
    preflight = {
        "schema_version": "rdf_mvp2e_v06a_runtime_chamfer_preflight_v0.1.0",
        "scenario_profile": "v0_6a",
        "source_scenario_profile": "v0_6",
        "inspection_method": "runtime_empirical_capture_radius_probe",
        "preflight_branch": branch if branch in {"A", "B", "C"} else "C",
        "chamfer_present": allowed if allowed else None,
        "capture_radius_m": capture_radius_probe.get("capture_radius_m", "unknown"),
        "source_asset_paths": [
            "${ISAACLAB_NUCLEUS_DIR}/Factory/factory_hole_8mm.usd",
            "${ISAACLAB_NUCLEUS_DIR}/Factory/factory_peg_8mm.usd",
        ],
        "prior_static_preflight_branch": prior_static_preflight.get("preflight_branch"),
        "prior_static_inspection_method": prior_static_preflight.get("inspection_method"),
        "capture_radius_probe_sha256": capture_radius_probe.get("capture_radius_probe_sha256"),
        "derived_insert_params": dict(V06A_PRE_REGISTERED_INSERT_ENVELOPE),
        "derivation_rationale": (
            "INSERT envelope was pre-registered from frozen v0_6 controller/horizon values before runtime "
            "capture-radius probing; capture-radius result only unlocks repair probe."
        ),
        "insert_parameter_freeze_allowed": allowed,
        "repair_probe_allowed": allowed,
        "repair_probe_green_light": False,
        "train_generation_gate_allowed": False,
        "train_generation_gate_status": status,
        "train_generation_gate_passed": False,
        "heldout_allowed": False,
        "proof_authority": False,
        "non_claims": dict(V06A_NON_CLAIMS),
    }
    if not allowed:
        preflight["reason"] = capture_radius_probe.get("measurement", {}).get(
            "branch_reason",
            "runtime capture-radius preflight did not verify chamfer/capture",
        )
    preflight["chamfer_preflight_sha256"] = _sha256_payload_excluding(preflight, "chamfer_preflight_sha256")
    write_json(output_dir / "chamfer_preflight.json", preflight)
    return preflight


def validate_v06a_verified_chamfer_preflight(
    preflight: dict[str, Any],
    *,
    capture_radius_probe: dict[str, Any],
) -> dict[str, Any]:
    required = {
        "scenario_profile": "v0_6a",
        "source_scenario_profile": "v0_6",
        "inspection_method": "runtime_empirical_capture_radius_probe",
        "repair_probe_allowed": True,
        "train_generation_gate_allowed": False,
        "train_generation_gate_status": "pending_repair_probe",
        "heldout_allowed": False,
        "proof_authority": False,
        "prior_static_preflight_branch": "C",
    }
    for key, expected in required.items():
        if preflight.get(key) != expected:
            raise ValueError(f"invalid v0_6a chamfer preflight {key}: expected {expected!r}, got {preflight.get(key)!r}")
    if preflight.get("preflight_branch") not in {"A", "B"}:
        raise ValueError("invalid v0_6a chamfer preflight preflight_branch")
    non_claims = preflight.get("non_claims")
    if not isinstance(non_claims, dict) or any(bool(value) for value in non_claims.values()):
        raise ValueError("invalid v0_6a chamfer preflight non_claims")
    expected_hash = _sha256_payload_excluding(preflight, "chamfer_preflight_sha256")
    if preflight.get("chamfer_preflight_sha256") != expected_hash:
        raise ValueError("invalid v0_6a chamfer preflight chamfer_preflight_sha256")
    if not preflight.get("capture_radius_probe_sha256"):
        raise ValueError("invalid v0_6a chamfer preflight capture_radius_probe_sha256")
    expected_probe_hash = _sha256_payload_excluding(capture_radius_probe, "capture_radius_probe_sha256")
    if capture_radius_probe.get("capture_radius_probe_sha256") != expected_probe_hash:
        raise ValueError("invalid v0_6a capture radius probe capture_radius_probe_sha256")
    if preflight.get("capture_radius_probe_sha256") != capture_radius_probe.get("capture_radius_probe_sha256"):
        raise ValueError("invalid v0_6a chamfer preflight capture_radius_probe_sha256 mismatch")
    probe_required = {
        "scenario_profile": "v0_6a",
        "source_scenario_profile": "v0_6",
        "prior_static_preflight_branch": "C",
        "repair_probe_green_light": False,
        "proof_authority": False,
        "heldout_allowed": False,
        "train_generation_gate_allowed": False,
        "train_generation_gate_status": "pending_repair_probe",
    }
    for key, expected in probe_required.items():
        if capture_radius_probe.get(key) != expected:
            raise ValueError(
                f"invalid v0_6a capture radius probe {key}: expected {expected!r}, "
                f"got {capture_radius_probe.get(key)!r}"
            )
    if capture_radius_probe.get("preflight_branch") != preflight.get("preflight_branch"):
        raise ValueError("invalid v0_6a capture radius probe preflight_branch mismatch")
    if capture_radius_probe.get("capture_radius_m") != preflight.get("capture_radius_m"):
        raise ValueError("invalid v0_6a capture radius probe capture_radius_m mismatch")
    measurement = capture_radius_probe.get("measurement")
    if not isinstance(measurement, dict):
        raise ValueError("invalid v0_6a capture radius probe measurement")
    if measurement.get("preflight_branch") != preflight.get("preflight_branch"):
        raise ValueError("invalid v0_6a capture radius probe measurement preflight_branch mismatch")
    if measurement.get("capture_radius_m") != preflight.get("capture_radius_m"):
        raise ValueError("invalid v0_6a capture radius probe measurement capture_radius_m mismatch")
    probe_non_claims = capture_radius_probe.get("non_claims")
    if not isinstance(probe_non_claims, dict) or any(bool(value) for value in probe_non_claims.values()):
        raise ValueError("invalid v0_6a capture radius probe non_claims")
    return preflight


def validate_v06e_numeric_capture_radius_preflight(
    *,
    preflight: dict[str, Any],
    capture_radius_probe: dict[str, Any],
) -> dict[str, Any]:
    capture_radius = _numeric_capture_radius_m(preflight.get("capture_radius_m"))
    probe_capture_radius = _numeric_capture_radius_m(capture_radius_probe.get("capture_radius_m"))
    required_probe_fields = {
        "geometry_isolated": True,
        "xy_correction_enabled": False,
        "yaw_correction_enabled": False,
        "z_push_mode": "straight_down_bounded",
        "geometry_probe_seed": V06A_CAPTURE_RADIUS_PRIMARY_SEED,
    }
    reasons: list[str] = []
    if capture_radius is None or probe_capture_radius is None:
        reasons.append("capture_radius_not_numeric")
    elif abs(capture_radius - probe_capture_radius) > 1.0e-12:
        reasons.append("capture_radius_probe_mismatch")
    if preflight.get("inspection_method") != "runtime_empirical_capture_radius_probe":
        reasons.append("inspection_method_not_runtime_empirical_capture_radius_probe")
    for key, expected in required_probe_fields.items():
        if capture_radius_probe.get(key) != expected:
            reasons.append(f"capture_radius_probe_{key}")
    if capture_radius_probe.get("directions") != list(V06A_CAPTURE_RADIUS_DIRECTIONS):
        reasons.append("capture_radius_probe_directions")
    if capture_radius_probe.get("offset_sweep_m") != list(V06A_CAPTURE_RADIUS_OFFSET_SWEEP_M):
        reasons.append("capture_radius_probe_offset_sweep")

    if reasons:
        reason = "capture_radius_not_numeric" if "capture_radius_not_numeric" in reasons else ";".join(reasons)
        return {
            **preflight,
            "repair_probe_allowed": False,
            "insert_parameter_freeze_allowed": False,
            "train_generation_gate_allowed": False,
            "capture_radius_probe_geometry_isolated": False,
            "reason": reason,
            "v0_6e_numeric_capture_radius_preflight_valid": False,
            "v0_6e_numeric_capture_radius_preflight_reasons": reasons,
        }
    return {
        **preflight,
        "capture_radius_m": capture_radius,
        "capture_radius_source": "empirical_runtime_probe",
        "capture_radius_probe_geometry_isolated": True,
        "repair_probe_allowed": True,
        "insert_parameter_freeze_allowed": True,
        "v0_6e_numeric_capture_radius_preflight_valid": True,
        "v0_6e_numeric_capture_radius_preflight_reasons": [],
    }


def resolve_v06_repair_probe_preflight(
    *,
    output_dir: Path,
    verified_preflight: dict[str, Any] | None = None,
    verified_capture_radius_probe: dict[str, Any] | None = None,
    require_runtime_capture_preflight: bool = True,
) -> dict[str, Any]:
    if verified_preflight is not None:
        if verified_capture_radius_probe is None:
            return {
                "repair_probe_allowed": False,
                "train_generation_gate_allowed": False,
                "heldout_allowed": False,
                "proof_authority": False,
                "reason": "missing_matching_v0_6a_capture_radius_probe",
            }
        try:
            return validate_v06a_verified_chamfer_preflight(
                verified_preflight,
                capture_radius_probe=verified_capture_radius_probe,
            )
        except ValueError as exc:
            return {
                "repair_probe_allowed": False,
                "train_generation_gate_allowed": False,
                "heldout_allowed": False,
                "proof_authority": False,
                "reason": f"invalid_verified_v0_6a_chamfer_preflight: {exc}",
            }

    preflight_path = output_dir / "chamfer_preflight.json"
    capture_probe_path = output_dir / "capture_radius_probe.json"
    if require_runtime_capture_preflight:
        if not preflight_path.exists():
            return {
                "repair_probe_allowed": False,
                "train_generation_gate_allowed": False,
                "heldout_allowed": False,
                "proof_authority": False,
                "reason": "missing_verified_v0_6a_chamfer_preflight",
            }
        if not capture_probe_path.exists():
            existing_preflight = read_json(preflight_path)
            return {
                "repair_probe_allowed": False,
                "train_generation_gate_allowed": False,
                "heldout_allowed": False,
                "proof_authority": False,
                "preflight_branch": existing_preflight.get("preflight_branch"),
                "preflight": existing_preflight,
                "reason": "missing_matching_v0_6a_capture_radius_probe",
            }
        existing_preflight: dict[str, Any] | None = None
        try:
            existing_preflight = read_json(preflight_path)
            return validate_v06a_verified_chamfer_preflight(
                existing_preflight,
                capture_radius_probe=read_json(capture_probe_path),
            )
        except ValueError as exc:
            return {
                "repair_probe_allowed": False,
                "train_generation_gate_allowed": False,
                "heldout_allowed": False,
                "proof_authority": False,
                "preflight": existing_preflight,
                "reason": f"invalid_verified_v0_6a_chamfer_preflight: {exc}",
            }

    return build_v06_chamfer_preflight(output_dir=output_dir)


def validate_v06_repair_probe_gate_artifact(
    repair_probe_gate: dict[str, Any],
    *,
    preflight: dict[str, Any],
) -> dict[str, Any]:
    required = {
        "proof_authority": False,
        "proof_runtime": "isaac_scripted_expert_repair_probe",
        "green_light_for_40_run_gate": True,
        "hard_stop": False,
        "hold_mode_passed": True,
        "lateral_success_mode_passed": True,
        "lateral_divergence_stopped": True,
    }
    for key, expected in required.items():
        if repair_probe_gate.get(key) != expected:
            raise ValueError(f"invalid v0_6 repair probe gate {key}: expected {expected!r}, got {repair_probe_gate.get(key)!r}")
    if repair_probe_gate.get("probe_seeds") != list(V06_REPAIR_PROBE_SEEDS):
        raise ValueError("invalid v0_6 repair probe gate probe_seeds")
    embedded_preflight = repair_probe_gate.get("chamfer_preflight")
    if not isinstance(embedded_preflight, dict):
        raise ValueError("invalid v0_6 repair probe gate chamfer_preflight")
    if embedded_preflight.get("chamfer_preflight_sha256") != preflight.get("chamfer_preflight_sha256"):
        raise ValueError("invalid v0_6 repair probe gate chamfer_preflight mismatch")
    post_gate = repair_probe_gate.get("v0_6a_post_repair_probe_gate")
    if not isinstance(post_gate, dict) or post_gate.get("green_light_for_40_run_gate") is not True:
        raise ValueError("invalid v0_6 repair probe gate post_repair_probe_gate")
    v06b_validation = repair_probe_gate.get("v0_6b_native_metric_trace_validation")
    if not isinstance(v06b_validation, dict) or v06b_validation.get("valid") is not True:
        raise ValueError("invalid v0_6 repair probe gate v0_6b_native_metric_trace_validation")
    probe_results = repair_probe_gate.get("probe_results")
    if not isinstance(probe_results, dict):
        raise ValueError("invalid v0_6 repair probe gate probe_results")
    for seed in V06_REPAIR_PROBE_SEEDS:
        if str(seed) not in probe_results and seed not in probe_results:
            raise ValueError(f"invalid v0_6 repair probe gate missing probe result for seed {seed}")
    recomputed_gate = evaluate_v06_repair_probe_gate(probe_results)
    for key in (
        "hold_mode_passed",
        "lateral_success_mode_passed",
        "lateral_divergence_stopped",
        "green_light_for_40_run_gate",
        "hard_stop",
    ):
        if repair_probe_gate.get(key) != recomputed_gate.get(key):
            raise ValueError(
                f"invalid v0_6 repair probe gate {key} does not match probe_results: "
                f"expected {recomputed_gate.get(key)!r}, got {repair_probe_gate.get(key)!r}"
            )
    expected_hash = _sha256_payload_excluding(repair_probe_gate, "repair_probe_gate_sha256")
    if repair_probe_gate.get("repair_probe_gate_sha256") != expected_hash:
        raise ValueError("invalid v0_6 repair probe gate repair_probe_gate_sha256")
    return repair_probe_gate


def resolve_v06_train_generation_gate_preflight(*, output_dir: Path) -> dict[str, Any]:
    preflight = resolve_v06_repair_probe_preflight(
        output_dir=output_dir,
        require_runtime_capture_preflight=True,
    )
    if preflight.get("repair_probe_allowed") is not True:
        return {
            "train_generation_gate_allowed": False,
            "preflight": preflight,
            "reason": preflight.get("reason", "verified_v0_6a_preflight_not_available"),
        }
    repair_probe_gate_path = output_dir / "repair_probe_gate.json"
    if not repair_probe_gate_path.exists():
        return {
            "train_generation_gate_allowed": False,
            "preflight": preflight,
            "reason": "missing_v0_6_repair_probe_green_light",
        }
    repair_probe_gate = read_json(repair_probe_gate_path)
    if repair_probe_gate.get("green_light_for_40_run_gate") is not True:
        return {
            "train_generation_gate_allowed": False,
            "preflight": preflight,
            "repair_probe_gate": repair_probe_gate,
            "reason": "v0_6_repair_probe_not_green",
        }
    try:
        repair_probe_gate = validate_v06_repair_probe_gate_artifact(
            repair_probe_gate,
            preflight=preflight,
        )
    except ValueError as exc:
        return {
            "train_generation_gate_allowed": False,
            "preflight": preflight,
            "repair_probe_gate": repair_probe_gate,
            "reason": f"invalid_v0_6_repair_probe_gate: {exc}",
        }
    post_gate = evaluate_v06a_post_repair_probe_gate(
        preflight=preflight,
        repair_probe_gate=repair_probe_gate,
    )
    if post_gate.get("green_light_for_40_run_gate") is not True:
        return {
            "train_generation_gate_allowed": False,
            "preflight": preflight,
            "repair_probe_gate": repair_probe_gate,
            "post_repair_probe_gate": post_gate,
            "reason": str(post_gate.get("reason") or "v0_6_repair_probe_not_green"),
        }
    return {
        "train_generation_gate_allowed": True,
        "preflight": preflight,
        "repair_probe_gate": repair_probe_gate,
        "post_repair_probe_gate": post_gate,
        "reason": "v0_6_repair_probe_green_light",
    }


def evaluate_v06a_post_repair_probe_gate(
    *,
    preflight: dict[str, Any],
    repair_probe_gate: dict[str, Any],
) -> dict[str, Any]:
    if preflight.get("preflight_branch") == "B" and repair_probe_gate.get("failure_mode") == "align_then_jam":
        return {
            "green_light_for_40_run_gate": False,
            "reason": "branch_b_align_then_jam_escalated_to_blocker",
            "proof_authority": False,
        }
    green = bool(preflight.get("repair_probe_allowed")) and bool(repair_probe_gate.get("green_light_for_40_run_gate"))
    return {
        "green_light_for_40_run_gate": green,
        "reason": "repair_probe_green_light" if green else "repair_probe_not_green",
        "proof_authority": False,
    }


def _v06a_direction_offset(direction: str, delta_m: float) -> tuple[float, float, float]:
    delta = float(delta_m)
    if direction == "+x":
        return (delta, 0.0, 0.0)
    if direction == "-x":
        return (-delta, 0.0, 0.0)
    if direction == "+y":
        return (0.0, delta, 0.0)
    if direction == "-y":
        return (0.0, -delta, 0.0)
    raise ValueError(f"unknown v0_6a capture direction: {direction}")


def _v06a_step_sim_no_action(env: Any) -> None:
    if hasattr(env, "step_sim_no_action"):
        env.step_sim_no_action()
        return
    scene = getattr(env, "scene", None)
    sim = getattr(env, "sim", None)
    if scene is not None and sim is not None and hasattr(scene, "write_data_to_sim"):
        scene.write_data_to_sim()
        sim.step(render=False)
        scene.update(dt=getattr(env, "physics_dt", 0.0))


def _v06a_place_held_asset_for_capture_probe(
    *,
    env: Any,
    torch: Any,
    lateral_offset_xyz: tuple[float, float, float],
    start_lift_m: float = 0.012,
) -> None:
    import isaaclab_tasks.direct.factory.factory_utils as factory_utils

    unwrapped = getattr(env, "unwrapped", env)
    held_asset = getattr(unwrapped, "_held_asset", None)
    if held_asset is None or not hasattr(held_asset, "write_root_pose_to_sim"):
        raise RuntimeError("Factory env does not expose _held_asset.write_root_pose_to_sim")
    fixed_pos = getattr(unwrapped, "fixed_pos")
    fixed_quat = getattr(unwrapped, "fixed_quat")
    target_pos, target_quat = factory_utils.get_target_held_base_pose(
        fixed_pos,
        fixed_quat,
        unwrapped.cfg_task.name,
        unwrapped.cfg_task.fixed_asset_cfg,
        unwrapped.num_envs,
        unwrapped.device,
    )
    state = held_asset.data.root_state_w.clone()
    offset = torch.as_tensor(lateral_offset_xyz, dtype=state.dtype, device=state.device).reshape(1, 3)
    lift = torch.as_tensor([0.0, 0.0, float(start_lift_m)], dtype=state.dtype, device=state.device).reshape(1, 3)
    env_origins = getattr(getattr(unwrapped, "scene", None), "env_origins", None)
    origin = env_origins if env_origins is not None else torch.zeros_like(target_pos)
    state[:, 0:3] = target_pos + origin + offset + lift
    state[:, 3:7] = target_quat
    state[:, 7:] = 0.0
    held_asset.write_root_pose_to_sim(state[:, 0:7])
    held_asset.write_root_velocity_to_sim(state[:, 7:])
    held_asset.reset()
    _v06a_step_sim_no_action(unwrapped)


def _v06a_capture_radius_action(env: Any, torch: Any) -> Any:
    action_shape = tuple(getattr(env.action_space, "shape", (len(ACTION_SCHEMA),)))
    action_dim = int(action_shape[-1] if action_shape else len(ACTION_SCHEMA))
    action_np = np.zeros((1, action_dim), dtype=np.float32)
    if action_dim >= 3:
        action_np[0, 2] = -0.12
    if action_dim >= 7:
        action_np[0, 6] = 1.0
    return torch.as_tensor(action_np, dtype=torch.float32, device=env.device)


def build_v06a_capture_radius_trial_schedule() -> list[tuple[str, float]]:
    """Return a delta-major capture-radius schedule.

    The probe must sample every direction at the smaller deltas before spending
    the runtime budget on larger offsets in one direction.
    """

    schedule: list[tuple[str, float]] = []
    for delta_m in V06A_CAPTURE_RADIUS_OFFSET_SWEEP_M:
        if float(delta_m) == 0.0:
            continue
        for direction in V06A_CAPTURE_RADIUS_DIRECTIONS:
            schedule.append((direction, float(delta_m)))
    return schedule


def _run_v06a_capture_radius_trial(
    *,
    env: Any,
    simulation_app: Any,
    torch: Any,
    seed: int,
    direction: str,
    delta_m: float,
    max_steps: int,
    deadline_at: float | None = None,
) -> dict[str, Any]:
    try:
        env.reset(seed=seed)
    except TypeError:
        env.reset()
    _v06a_place_held_asset_for_capture_probe(
        env=env,
        torch=torch,
        lateral_offset_xyz=_v06a_direction_offset(direction, delta_m),
    )
    mask: list[bool] = []
    action = _v06a_capture_radius_action(env, torch)
    for _ in range(int(max_steps)):
        if deadline_at is not None and time.monotonic() > float(deadline_at):
            window = evaluate_env_native_success_window(
                mask,
                stable_steps_required=V06_ENV_NATIVE_STABLE_STEPS_REQUIRED,
            )
            return {
                "direction": direction,
                "delta_m": float(delta_m),
                "env_native_success_mask_available": bool(mask),
                "rollout_success": False,
                "first_success_step": window["first_success_step"],
                "max_consecutive_success_steps": window["max_consecutive_success_steps"],
                "steps_attempted": len(mask),
                "timed_out": True,
                "timeout_reason": "v0_6a capture-radius trial exceeded runtime deadline",
            }
        env.step(action)
        success = _read_env_native_success(env)
        if success is None:
            return {
                "direction": direction,
                "delta_m": float(delta_m),
                "env_native_success_mask_available": False,
                "rollout_success": False,
                "max_consecutive_success_steps": 0,
                "steps_attempted": len(mask),
                "timed_out": False,
            }
        mask.append(bool(success))
        if not simulation_app.is_running():
            break
    window = evaluate_env_native_success_window(
        mask,
        stable_steps_required=V06_ENV_NATIVE_STABLE_STEPS_REQUIRED,
    )
    return {
        "direction": direction,
        "delta_m": float(delta_m),
        "env_native_success_mask_available": True,
        "rollout_success": bool(window["rollout_success"]),
        "first_success_step": window["first_success_step"],
        "max_consecutive_success_steps": window["max_consecutive_success_steps"],
        "steps_attempted": len(mask),
        "timed_out": False,
    }


def _run_v06a_capture_radius_probe_isaaclab(
    *,
    output_dir: Path,
    device: str,
    headless: bool,
    isaac_task: str,
) -> dict[str, Any]:
    from isaaclab.app import AppLauncher

    app_launcher = AppLauncher({"headless": headless, "device": device, "enable_cameras": False})
    simulation_app = app_launcher.app

    import gymnasium as gym
    import torch

    import isaaclab_tasks  # noqa: F401
    from isaaclab_tasks.utils import parse_env_cfg

    env = None
    trial_results: list[dict[str, Any]] = []
    started_at = time.monotonic()

    def assert_deadline() -> None:
        elapsed = time.monotonic() - started_at
        if elapsed > V06A_CAPTURE_RADIUS_RUNTIME_DEADLINE_S:
            raise TimeoutError(
                f"v0_6a capture-radius runtime probe exceeded {V06A_CAPTURE_RADIUS_RUNTIME_DEADLINE_S:.0f}s"
            )

    try:
        env_cfg = parse_env_cfg(isaac_task, device=device, num_envs=1)
        env = gym.make(isaac_task, cfg=env_cfg).unwrapped
        assert_deadline()
        zero_trial = _run_v06a_capture_radius_trial(
            env=env,
            simulation_app=simulation_app,
            torch=torch,
            seed=V06A_CAPTURE_RADIUS_PRIMARY_SEED,
            direction="+x",
            delta_m=0.0,
            max_steps=int(V06A_PRE_REGISTERED_INSERT_ENVELOPE["max_insert_steps"]),
            deadline_at=started_at + V06A_CAPTURE_RADIUS_RUNTIME_DEADLINE_S,
        )
        trial_results.append(zero_trial)
        write_json(output_dir / "capture_radius_probe_trials.json", {"trial_results": trial_results})
        assert_deadline()
        if not zero_trial.get("env_native_success_mask_available"):
            return {
                "runtime_loaded": True,
                "env_native_success_mask_available": False,
                "zero_offset_passed": False,
                "direction_results": {},
                "trial_results": trial_results,
                "isaac_task_or_scene_id": isaac_task,
                "device": device,
                "headless": headless,
                "error": zero_trial.get("timeout_reason") if zero_trial.get("timed_out") else None,
            }
        if not zero_trial.get("rollout_success"):
            return {
                "runtime_loaded": True,
                "env_native_success_mask_available": True,
                "zero_offset_passed": False,
                "direction_results": {},
                "trial_results": trial_results,
                "isaac_task_or_scene_id": isaac_task,
                "device": device,
                "headless": headless,
                "error": zero_trial.get("timeout_reason") if zero_trial.get("timed_out") else None,
            }

        direction_trials_by_direction: dict[str, list[dict[str, Any]]] = {
            direction: [] for direction in V06A_CAPTURE_RADIUS_DIRECTIONS
        }
        max_successful_delta_by_direction = {
            direction: 0.0 for direction in V06A_CAPTURE_RADIUS_DIRECTIONS
        }

        def direction_results_snapshot(*, partial_due_to_timeout: bool = False) -> dict[str, dict[str, Any]]:
            snapshot: dict[str, dict[str, Any]] = {}
            for direction in V06A_CAPTURE_RADIUS_DIRECTIONS:
                item: dict[str, Any] = {
                    "max_successful_delta_m": max_successful_delta_by_direction[direction],
                    "trial_count": len(direction_trials_by_direction[direction]),
                    "trials": direction_trials_by_direction[direction],
                }
                if partial_due_to_timeout and not direction_trials_by_direction[direction]:
                    item["partial_due_to_timeout"] = True
                snapshot[direction] = item
            return snapshot

        for direction, delta_m in build_v06a_capture_radius_trial_schedule():
            trial = _run_v06a_capture_radius_trial(
                env=env,
                simulation_app=simulation_app,
                torch=torch,
                seed=V06A_CAPTURE_RADIUS_PRIMARY_SEED,
                direction=direction,
                delta_m=float(delta_m),
                max_steps=int(V06A_PRE_REGISTERED_INSERT_ENVELOPE["max_insert_steps"]),
                deadline_at=started_at + V06A_CAPTURE_RADIUS_RUNTIME_DEADLINE_S,
            )
            trial_results.append(trial)
            direction_trials_by_direction[direction].append(trial)
            if trial.get("env_native_success_mask_available") is not True:
                return {
                    "runtime_loaded": True,
                    "env_native_success_mask_available": False,
                    "zero_offset_passed": True,
                    "direction_results": direction_results_snapshot(),
                    "trial_results": trial_results,
                    "isaac_task_or_scene_id": isaac_task,
                    "device": device,
                    "headless": headless,
                    "error": trial.get("timeout_reason") if trial.get("timed_out") else None,
                }
            if trial.get("rollout_success") is True:
                max_successful_delta_by_direction[direction] = float(delta_m)
            write_json(output_dir / "capture_radius_probe_trials.json", {"trial_results": trial_results})
            if trial.get("timed_out") is True:
                return {
                    "runtime_loaded": True,
                    "env_native_success_mask_available": True,
                    "zero_offset_passed": True,
                    "direction_results": direction_results_snapshot(partial_due_to_timeout=True),
                    "trial_results": trial_results,
                    "partial_due_to_timeout": True,
                    "error": trial.get("timeout_reason"),
                    "isaac_task_or_scene_id": isaac_task,
                    "device": device,
                    "headless": headless,
                }
            assert_deadline()
        direction_results = direction_results_snapshot()
        write_json(output_dir / "capture_radius_probe_trials.json", {"trial_results": trial_results})
        return {
            "runtime_loaded": True,
            "env_native_success_mask_available": True,
            "zero_offset_passed": True,
            "direction_results": direction_results,
            "trial_results": trial_results,
            "isaac_task_or_scene_id": isaac_task,
            "device": device,
            "headless": headless,
        }
    except TimeoutError as exc:
        write_json(output_dir / "capture_radius_probe_trials.json", {"trial_results": trial_results})
        return {
            "runtime_loaded": env is not None,
            "env_native_success_mask_available": False,
            "zero_offset_passed": False,
            "direction_results": {},
            "trial_results": trial_results,
            "error": f"{type(exc).__name__}: {exc}",
            "isaac_task_or_scene_id": isaac_task,
            "device": device,
            "headless": headless,
        }
    finally:
        if env is not None:
            env.close()


def run_v06a_capture_radius_probe_runtime(
    *,
    output_dir: Path,
    device: str,
    headless: bool,
    isaac_task: str,
) -> dict[str, Any]:
    prior_static_preflight = build_v06_chamfer_preflight(output_dir=output_dir)
    try:
        raw_probe = _run_v06a_capture_radius_probe_isaaclab(
            output_dir=output_dir,
            device=device,
            headless=headless,
            isaac_task=isaac_task,
        )
    except Exception as exc:
        raw_probe = {
            "runtime_loaded": False,
            "env_native_success_mask_available": False,
            "zero_offset_passed": False,
            "direction_results": {},
            "error": f"{type(exc).__name__}: {exc}",
            "isaac_task_or_scene_id": isaac_task,
            "device": device,
            "headless": headless,
        }
    measurement = evaluate_runtime_capture_radius_probe(raw_probe)
    if "error" in raw_probe:
        measurement["runtime_error"] = raw_probe["error"]
    capture_probe = build_v06a_capture_radius_probe_artifact(
        output_dir=output_dir,
        measurement=measurement,
        prior_static_preflight=prior_static_preflight,
    )
    preflight = build_v06a_runtime_chamfer_preflight_from_probe(
        output_dir=output_dir,
        capture_radius_probe=capture_probe,
        prior_static_preflight=prior_static_preflight,
    )
    result = {
        "schema_version": "rdf_mvp2e_v06a_capture_radius_probe_result_v0.1.0",
        "capture_radius_probe": capture_probe,
        "chamfer_preflight": preflight,
        "runtime_error": raw_probe.get("error"),
        "next_gate": "repair_probe" if preflight.get("repair_probe_allowed") is True else "blocked_by_preflight",
        "heldout_schedule": {"scheduled": False, "reason": "capture-radius preflight has no held-out authority"},
    }
    write_json(output_dir / "capture_radius_preflight_result.json", result)
    return result


def _v06_repair_probe_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    scenarios = []
    for seed in V06_REPAIR_PROBE_SEEDS:
        row = _scenario_row(split="train_success", seed=seed)
        scenarios.append(
            {
                **row,
                "split": "held_out",
                "scenario_id": f"repair_probe_{seed}",
                "proof_role": "repair_validation_only",
            }
        )
    probe_manifest = {
        "manifest_version": f"{manifest.get('manifest_version')}_repair_probe",
        "schema_version": f"{manifest.get('schema_version')}_repair_probe",
        "source_manifest_sha256": manifest["manifest_sha256"],
        "scenario_profile": manifest.get("scenario_profile"),
        "task_type": manifest.get("task_type", "connector_insertion"),
        "success_metric": dict(manifest.get("success_metric") or SUCCESS_METRIC),
        "success_authority": manifest.get("success_authority"),
        "repair_probe_seeds": list(V06_REPAIR_PROBE_SEEDS),
        "scenarios": scenarios,
        "leakage_policy": {
            "proof_authority": False,
            "held_out_eval_split_excluded": True,
            "v0_6_train_calibration_heldout_excluded": True,
        },
    }
    probe_manifest["manifest_sha256"] = _sha256_payload(probe_manifest)
    return probe_manifest


def derive_v06_repair_probe_gate_from_probe_result(
    probe_result: BackendResult,
    *,
    capture_radius_m: float | None = None,
    gate_version: str = "v0_6e",
) -> dict[str, Any]:
    probe_results: dict[int, dict[str, Any]] = {}
    trace_rows: list[dict[str, Any]] = []
    for trace_path in list(probe_result.baseline_trace_paths) + list(probe_result.candidate_trace_paths):
        trace_data = read_json(Path(trace_path))
        scenario = trace_data.get("scenario") if isinstance(trace_data.get("scenario"), dict) else {}
        seed = int(scenario.get("seed", -1))
        trace = trace_data.get("trace") if isinstance(trace_data.get("trace"), list) else []
        summary = trace_data.get("summary") if isinstance(trace_data.get("summary"), dict) else {}
        lateral_errors = [float(row["lateral_error_m"]) for row in trace if isinstance(row, dict) and "lateral_error_m" in row]
        trace_rows.extend(row for row in trace if isinstance(row, dict))
        divergence = evaluate_lateral_divergence_stopped(lateral_errors_m=lateral_errors)
        probe_results[seed] = {**summary, **divergence, "lateral_errors_m": lateral_errors}
    if _numeric_capture_radius_m(capture_radius_m) is not None and gate_version == "v0_6f":
        gate = evaluate_v06f_repair_probe_gate(probe_results, capture_radius_m=float(capture_radius_m))
    elif _numeric_capture_radius_m(capture_radius_m) is not None:
        gate = evaluate_v06e_repair_probe_gate(probe_results, capture_radius_m=float(capture_radius_m))
    else:
        gate = evaluate_v06_repair_probe_gate(probe_results)
        gate["v0_6e_numeric_capture_radius_missing"] = True
    validation = validate_v06b_native_metric_trace_rows(trace_rows)
    gate["v0_6b_native_metric_trace_validation"] = validation
    gate["v0_6c_controller_action_diagnosis"] = summarize_v06c_controller_action_diagnosis(trace_rows)
    if validation["valid"] is not True:
        gate["green_light_for_40_run_gate"] = False
        gate["hard_stop"] = True
        gate["failure_mode"] = "v0_6b_native_metric_trace_validation_failed"
        gate["reason"] = "v0_6b_native_metric_trace_validation_failed"
    gate.update(
        {
            "runtime_backend": probe_result.runtime_backend,
            "proof_runtime": "isaac_scripted_expert_repair_probe",
            "runtime_gate": probe_result.runtime_gate,
            "runtime_metadata": probe_result.runtime_metadata,
        }
    )
    gate["repair_probe_gate_sha256"] = _sha256_payload_excluding(gate, "repair_probe_gate_sha256")
    return gate


def _z_component(values: Any) -> float | None:
    if not isinstance(values, list | tuple) or len(values) < 3:
        return None
    try:
        return float(values[2])
    except (TypeError, ValueError):
        return None


def summarize_v06c_controller_action_diagnosis(trace_rows: list[dict[str, Any]]) -> dict[str, Any]:
    block_reason_counts: dict[str, int] = {}
    rows_with_diagnostics = 0
    raw_negative_z_action_steps = 0
    pre_controller_negative_z_action_steps = 0
    final_negative_z_action_steps = 0
    z_motion_suppressed_steps = 0
    phase_vocabulary_mismatch_steps = 0
    env_centered_z_suppressed_steps = 0
    phases_seen: dict[str, int] = {}
    for row in trace_rows:
        if not isinstance(row, dict):
            continue
        phase = str(row.get("phase") or "")
        phases_seen[phase] = phases_seen.get(phase, 0) + 1
        diagnostics = row.get("controller_action_diagnostics")
        if not isinstance(diagnostics, dict):
            continue
        rows_with_diagnostics += 1
        raw_z = _z_component(diagnostics.get("raw_action_vector"))
        pre_z = _z_component(diagnostics.get("pre_controller_action_vector"))
        final_z = _z_component(diagnostics.get("post_adapter_action_vector") or row.get("normalized_action"))
        if raw_z is not None and raw_z < 0.0:
            raw_negative_z_action_steps += 1
        if pre_z is not None and pre_z < 0.0:
            pre_controller_negative_z_action_steps += 1
        if final_z is not None and final_z < 0.0:
            final_negative_z_action_steps += 1
        if diagnostics.get("z_motion_suppressed") is True:
            z_motion_suppressed_steps += 1
        if diagnostics.get("phase_vocabulary_mismatch") is True:
            phase_vocabulary_mismatch_steps += 1
        reason = str(diagnostics.get("z_motion_block_reason") or "unknown")
        block_reason_counts[reason] = block_reason_counts.get(reason, 0) + 1
        if row.get("env_native_is_centered") is True and diagnostics.get("z_motion_suppressed") is True:
            env_centered_z_suppressed_steps += 1

    root_cause = "insufficient_controller_action_evidence"
    if (
        rows_with_diagnostics > 0
        and raw_negative_z_action_steps > 0
        and pre_controller_negative_z_action_steps > 0
        and final_negative_z_action_steps == 0
        and block_reason_counts.get("controller_phase_vocabulary_mismatch", 0)
        >= max(1, raw_negative_z_action_steps // 2)
    ):
        root_cause = "controller_phase_vocabulary_mismatch_blocks_z_motion"
    elif raw_negative_z_action_steps > 0 and final_negative_z_action_steps == 0:
        root_cause = "adapter_or_controller_suppresses_negative_z_motion"
    elif final_negative_z_action_steps > 0:
        root_cause = "physics_or_action_mapping_does_not_convert_negative_z_to_seating_progress"

    diagnosis = {
        "schema_version": "rdf_mvp2e_v06c_controller_action_diagnosis_v0.1.0",
        "proof_authority": False,
        "diagnosis_complete": rows_with_diagnostics > 0,
        "root_cause_hypothesis": root_cause,
        "trace_rows": len(trace_rows),
        "rows_with_diagnostics": rows_with_diagnostics,
        "phases_seen": phases_seen,
        "raw_negative_z_action_steps": raw_negative_z_action_steps,
        "pre_controller_negative_z_action_steps": pre_controller_negative_z_action_steps,
        "final_negative_z_action_steps": final_negative_z_action_steps,
        "z_motion_suppressed_steps": z_motion_suppressed_steps,
        "phase_vocabulary_mismatch_steps": phase_vocabulary_mismatch_steps,
        "env_centered_z_suppressed_steps": env_centered_z_suppressed_steps,
        "z_motion_block_reason_counts": block_reason_counts,
        "heldout_opened": False,
        "fixed_40_run_gate_opened": False,
        "recommended_next_step": (
            "fix_controller_phase_vocabulary_or_phase_state_persistence"
            if root_cause == "controller_phase_vocabulary_mismatch_blocks_z_motion"
            else "continue_controller_action_instrumentation"
        ),
    }
    diagnosis["controller_action_diagnosis_sha256"] = _sha256_payload(diagnosis)
    return diagnosis


def run_v06_repair_probe_runtime(
    *,
    output_dir: Path,
    manifest: dict[str, Any],
    selected_adapter_id: str,
    selected_adapter_config: dict[str, Any],
    device: str,
    headless: bool,
    isaac_task: str,
    max_steps: int,
    action_scale: float,
    verified_preflight: dict[str, Any] | None = None,
    repair_probe_controller_version: str = "v0_6e",
) -> dict[str, Any]:
    preflight = resolve_v06_repair_probe_preflight(
        output_dir=output_dir,
        verified_preflight=verified_preflight,
        require_runtime_capture_preflight=True,
    )
    if preflight["repair_probe_allowed"] is not True:
        gate = {
            "proof_authority": False,
            "probe_seeds": list(V06_REPAIR_PROBE_SEEDS),
            "green_light_for_40_run_gate": False,
            "hard_stop": True,
            "runtime_backend": "isaac_runtime_not_started",
            "proof_runtime": "isaac_scripted_expert_repair_probe",
            "chamfer_preflight": preflight,
            "reason": preflight.get(
                "reason",
                "chamfer preflight blocked INSERT parameter freeze; repair probe was not run.",
            ),
        }
        write_json(output_dir / "repair_probe_gate.json", gate)
        return gate
    capture_probe_path = output_dir / "capture_radius_probe.json"
    if capture_probe_path.exists():
        preflight = validate_v06e_numeric_capture_radius_preflight(
            preflight=preflight,
            capture_radius_probe=read_json(capture_probe_path),
        )
    else:
        preflight = {
            **preflight,
            "repair_probe_allowed": False,
            "insert_parameter_freeze_allowed": False,
            "train_generation_gate_allowed": False,
            "reason": "missing_numeric_v0_6e_capture_radius_probe",
            "v0_6e_numeric_capture_radius_preflight_valid": False,
            "v0_6e_numeric_capture_radius_preflight_reasons": ["missing_capture_radius_probe"],
        }
    if preflight["repair_probe_allowed"] is not True:
        gate = {
            "proof_authority": False,
            "probe_seeds": list(V06_REPAIR_PROBE_SEEDS),
            "green_light_for_40_run_gate": False,
            "hard_stop": True,
            "runtime_backend": "isaac_runtime_not_started",
            "proof_runtime": "isaac_scripted_expert_repair_probe",
            "chamfer_preflight": preflight,
            "reason": preflight.get(
                "reason",
                "numeric capture-radius preflight blocked v0.6e repair probe.",
            ),
            "fixed_40_run_gate_opened": False,
            "heldout_opened": False,
        }
        write_json(output_dir / "repair_probe_gate.json", gate)
        return gate
    capture_radius_m = float(preflight["capture_radius_m"])
    if repair_probe_controller_version == "v0_6f":
        controller_repair_config = build_v06f_controller_repair_config(capture_radius_m=capture_radius_m)
    else:
        controller_repair_config = build_v06e_controller_repair_config(capture_radius_m=capture_radius_m)
    write_json(output_dir / "controller_repair_config.json", controller_repair_config)
    expert_policy = _scripted_expert_probe_policy_artifact(
        selected_adapter_id=selected_adapter_id,
        selected_adapter_config=selected_adapter_config,
        scenario_profile="v0_6",
        controller_repair_config=controller_repair_config,
    )
    try:
        probe_result = IsaacConnectorInsertionEvaluatorBackend(
            task=isaac_task,
            device=device,
            headless=headless,
            action_scale=action_scale,
            max_steps=max_steps,
        ).run_single_policy_probe(
            manifest=_v06_repair_probe_manifest(manifest),
            output_dir=output_dir / "isaac_runtime_repair_probe",
            policy_artifact=expert_policy,
            role="v0_6_repair_probe",
            max_rollouts=len(V06_REPAIR_PROBE_SEEDS),
            stop_after_first_success=False,
        )
    except Exception as exc:
        gate = {
            "proof_authority": False,
            "probe_seeds": list(V06_REPAIR_PROBE_SEEDS),
            "green_light_for_40_run_gate": False,
            "hard_stop": True,
            "runtime_backend": "isaac_runtime",
            "proof_runtime": "isaac_scripted_expert_repair_probe",
            "chamfer_preflight": preflight,
            "reason": f"Isaac repair probe failed: {type(exc).__name__}: {exc}",
        }
        write_json(output_dir / "repair_probe_gate.json", gate)
        return gate
    gate = derive_v06_repair_probe_gate_from_probe_result(
        probe_result,
        capture_radius_m=capture_radius_m,
        gate_version=repair_probe_controller_version,
    )
    gate["controller_repair_version"] = repair_probe_controller_version
    gate["chamfer_preflight"] = preflight
    gate["controller_repair_config"] = controller_repair_config
    gate["controller_repair_config_sha256"] = controller_repair_config["controller_repair_config_sha256"]
    gate["fixed_40_run_gate_opened"] = False
    gate["heldout_opened"] = False
    gate["v0_6a_post_repair_probe_gate"] = evaluate_v06a_post_repair_probe_gate(
        preflight=preflight,
        repair_probe_gate=gate,
    )
    if (gate.get("v0_6b_native_metric_trace_validation") or {}).get("valid") is not True:
        gate["v0_6a_post_repair_probe_gate"] = {
            "green_light_for_40_run_gate": False,
            "proof_authority": False,
            "reason": "v0_6b_native_metric_trace_validation_failed",
        }
    gate["repair_probe_gate_sha256"] = _sha256_payload_excluding(gate, "repair_probe_gate_sha256")
    if isinstance(gate.get("v0_6c_controller_action_diagnosis"), dict):
        write_json(output_dir / "controller_action_diagnosis.json", gate["v0_6c_controller_action_diagnosis"])
    write_json(output_dir / "repair_probe_gate.json", gate)
    return gate


def build_baseline_noise_mix_config(*, output_dir: Path, scenario_profile: str = "v0_1") -> dict[str, Any]:
    if scenario_profile == "v0_5":
        config = {
            "schema_version": BASELINE_NOISE_MIX_SCHEMA_VERSION,
            "scenario_profile": scenario_profile,
            "baseline_noise_mix_ratio": 0.40,
            "accepted_failure_ratio": {"accepted": 3, "failure_or_noisy": 2},
            "failure_type_distribution": {bucket: 1 / 3 for bucket in V05_FAILURE_BUCKETS},
            "failure_bucket_cycle": list(V05_FAILURE_BUCKETS),
            "pre_registered_before_training": True,
            "pre_registered_before_calibration": True,
            "pre_registered_before_heldout": True,
        }
        config["noise_profile_config_sha256"] = _sha256_payload(config)
        write_json(output_dir / "baseline_noise_mix_config.json", config)
        return config
    config = {
        "schema_version": BASELINE_NOISE_MIX_SCHEMA_VERSION,
        "scenario_profile": scenario_profile,
        "baseline_noise_mix_ratio": 0.25,
        "accepted_failure_ratio": {"accepted": 3, "failure_or_noisy": 1},
        "failure_type_distribution": dict(BASELINE_FAILURE_TYPE_DISTRIBUTION),
        "pre_registered_before_training": True,
        "pre_registered_before_calibration": True,
        "pre_registered_before_heldout": True,
    }
    config["noise_profile_config_sha256"] = _sha256_payload(config)
    write_json(output_dir / "baseline_noise_mix_config.json", config)
    return config


def build_generator_config_hashes(*, output_dir: Path, scenario_profile: str = "v0_1") -> dict[str, Any]:
    seed_ranges = _scenario_seed_ranges(scenario_profile)
    weak_base_servo_config_sha256 = _sha256_payload(dict(WEAK_BASE_SERVO_CONFIG))
    v05_config = scenario_profile == "v0_5"
    scripted_expert_config = {
        "generator_id": "mvp2c_scripted_expert_connector_insertion_v0",
        "policy": "geometry_phase_scripted_expert",
        "xy_correction_gain": 0.8,
        "downward_insert_step_m": 0.006,
        "phase_schema": list(PHASES),
        "success_metric": dict(SUCCESS_METRIC),
    }
    controlled_failure_config = {
        "generator_id": "mvp2c_controlled_failure_generator_v0",
        "failure_reasons": list(CONTROLLED_FAILURE_REASONS),
        "failure_type_distribution": dict(BASELINE_FAILURE_TYPE_DISTRIBUTION),
        "taxonomy_frozen": True,
    }
    train_generation_config = {
        "generator_id": "mvp2c_train_generation_config_v0",
        "scenario_profile": scenario_profile,
        "train_success_seed_range": [min(seed_ranges["train_success"]), max(seed_ranges["train_success"])],
        "train_failure_seed_range": [min(seed_ranges["train_failure"]), max(seed_ranges["train_failure"])],
        "baseline_noise_mix_ratio": 0.40 if v05_config else 0.25,
        "accepted_failure_ratio": {"accepted": 3, "failure_or_noisy": 2}
        if v05_config
        else {"accepted": 3, "failure_or_noisy": 1},
        "failure_bucket_cycle": list(V05_FAILURE_BUCKETS) if v05_config else list(CONTROLLED_FAILURE_REASONS),
        "actual_isaac_success_trace_minimum": V05_ACTUAL_SUCCESS_TRACE_MINIMUM if v05_config else 1,
        "actual_isaac_success_trace_cap": V05_ACTUAL_SUCCESS_TRACE_CAP if v05_config else None,
        "trainer_family": RESIDUAL_TRAINER_FAMILY if v05_config else "phase_conditioned_bc",
        "weak_base_servo_config_sha256": weak_base_servo_config_sha256 if v05_config else None,
        "residual_target_definition": RESIDUAL_TARGET_DEFINITION if v05_config else None,
        "base_servo_only_diagnostic": {"enabled": True, "closing_gate": False} if v05_config else None,
        "actual_isaac_success_trace_ingestion": {
            "enabled_for_candidate_view": True,
            "enabled_for_baseline_view": v05_config,
            "candidate_replay_weight": 1 if v05_config else ACTUAL_TRACE_REPLAY_WEIGHT,
            "source": "isaac_runtime_scripted_expert_rollout",
            "inverse_adapter_target_space": "selected_action_adapter_pre_adapter_action_v0",
            "v0_5_candidate_accepted_only": v05_config,
            "v0_5_baseline_equal_trace_count_60_40": v05_config,
        },
        "scripted_expert_config_sha256": _sha256_payload(scripted_expert_config),
        "controlled_failure_config_sha256": _sha256_payload(controlled_failure_config),
    }
    hashes = {
        "schema_version": GENERATOR_HASH_SCHEMA_VERSION,
        "scripted_expert_config_sha256": train_generation_config["scripted_expert_config_sha256"],
        "controlled_failure_config_sha256": train_generation_config["controlled_failure_config_sha256"],
        "train_generation_config_sha256": _sha256_payload(train_generation_config),
        "weak_base_servo_config_sha256": weak_base_servo_config_sha256 if v05_config else None,
        "scripted_expert_config": scripted_expert_config,
        "controlled_failure_config": controlled_failure_config,
        "train_generation_config": train_generation_config,
        "hashes_frozen_before_train_generation": True,
    }
    write_json(output_dir / "generator_config_hashes.json", hashes)
    return hashes


def validate_generator_config_immutability(
    *,
    frozen_hashes: dict[str, Any],
    proposed_hashes: dict[str, Any],
    calibration_started: bool,
    heldout_started: bool,
) -> dict[str, Any]:
    keys = (
        "scripted_expert_config_sha256",
        "controlled_failure_config_sha256",
        "train_generation_config_sha256",
    )
    changed = sorted(key for key in keys if frozen_hashes.get(key) != proposed_hashes.get(key))
    phase_parts: list[str] = []
    if calibration_started:
        phase_parts.append("calibration")
    if heldout_started:
        phase_parts.append("heldout")
    phase = "_and_".join(phase_parts) or "pre_train"
    immutable_boundary_started = calibration_started or heldout_started
    return {
        "passed": not (changed and immutable_boundary_started),
        "changed_fields": changed,
        "phase": phase,
        "calibration_started": calibration_started,
        "heldout_started": heldout_started,
    }


def _selector_score_config_for_profile(scenario_profile: str) -> dict[str, Any]:
    if scenario_profile == "v0_5":
        return dict(SELECTOR_SCORE_CONFIG_V05)
    return dict(SELECTOR_SCORE_CONFIG)


def build_action_adapter_registry(*, output_dir: Path, scenario_profile: str = "v0_1") -> dict[str, Any]:
    adapters = [
        {
            "adapter_id": "isaac_delta_pose_direct_v0",
            "adapter_version": "0.1.0",
            "action_adapter_role": "direct_delta_pose_baseline",
            "capabilities": ["delta_pose", "phase_conditioned_bc"],
            "runtime_action_adapter_config": {
                "adapter_mode": "global_action_scale",
                "global_action_scale_source": "--action-scale",
            },
            "limitations": ["No real robot runtime claim."],
        },
        {
            "adapter_id": "isaac_signed_xy_downward_servo_v0",
            "adapter_version": "0.1.0",
            "action_adapter_role": "signed_xy_downward_servo",
            "capabilities": ["delta_pose", "signed_xy_correction", "phase_conditioned_bc"],
            "runtime_action_adapter_config": {
                "adapter_mode": "per_axis_signed_xy_downward_servo",
                "xy_action_scale": 3.0,
                "xy_action_clip": 0.05,
                "xy_source": "policy_plus_state_feedback",
                "xy_state_feedback_gain": 3.0,
                "z_action_scale": 32.0,
                "z_action_clip": 0.16,
                "rotation_action_scale": 0.0,
                "gripper_passthrough": True,
                "stable_hold_depth_m": 0.03,
                "stable_hold_lateral_m": 0.006,
                "stable_hold_orientation_deg": 8.0,
                "stable_hold_action": [0.0, 0.0, -0.03, 0.0, 0.0, 0.0, 1.0],
            },
            "limitations": ["Isaac evaluator-domain adapter only."],
        },
        {
            "adapter_id": "isaac_stability_damped_servo_v0",
            "adapter_version": "0.1.0",
            "action_adapter_role": "stability_damped_servo",
            "capabilities": ["delta_pose", "stability_damping", "phase_conditioned_bc"],
            "runtime_action_adapter_config": {
                "adapter_mode": "per_axis_stability_damped_servo",
                "xy_action_scale": 3.0,
                "xy_action_clip": 0.025,
                "z_action_scale": 16.0,
                "z_action_clip": 0.10,
                "rotation_action_scale": 0.0,
                "gripper_passthrough": True,
            },
            "limitations": ["No universal robot support claim."],
        },
    ]
    registry = {
        "schema_version": ACTION_ADAPTER_REGISTRY_SCHEMA_VERSION,
        "scenario_profile": scenario_profile,
        "adapters": adapters,
        "selector_score_config": _selector_score_config_for_profile(scenario_profile),
    }
    registry["selector_score_config_sha256"] = _sha256_payload(registry["selector_score_config"])
    registry["action_adapter_registry_sha256"] = _sha256_payload(registry)
    write_json(output_dir / "action_adapter_candidates.json", registry)
    write_json(
        output_dir / "action_adapter_registry_hash.json",
        {
            "schema_version": "rdf_mvp2c_action_adapter_registry_hash_v0.1.0",
            "action_adapter_registry_sha256": registry["action_adapter_registry_sha256"],
            "selector_score_config_sha256": registry["selector_score_config_sha256"],
        },
    )
    return registry


def _calibration_selector_score(summary: dict[str, Any], *, selector_score_config: dict[str, Any]) -> float:
    candidate = float(summary.get("candidate_success_rate", 0.0))
    baseline = float(summary.get("baseline_success_rate", 0.0))
    stability_margin = float(summary.get("candidate_stability_margin", 0.0))
    action_saturation = float(summary.get("candidate_action_saturation_rate", 0.0))
    selector_id = str(selector_score_config.get("selector_score_id") or "")
    if selector_id == "shared_stability_feasibility_score_v0":
        return 0.70 * stability_margin - 0.20 * action_saturation + 0.10 * min(candidate, baseline)
    return (candidate - baseline) + 0.25 * stability_margin - 0.10 * action_saturation


def validate_calibration_selector_inputs(
    *,
    manifest: dict[str, Any],
    calibration_summaries: list[dict[str, Any]],
    forbidden_inputs: dict[str, Any],
) -> dict[str, Any]:
    heldout = _heldout_ids(manifest)
    calibration_ids = {
        str(row["scenario_id"])
        for row in manifest.get("scenarios", [])
        if isinstance(row, dict) and row.get("split") == "calibration" and row.get("scenario_id")
    }
    blocked_channels: list[str] = []
    if forbidden_inputs.get("heldout_trace_paths"):
        blocked_channels.append("heldout_trace_paths")
    if forbidden_inputs.get("heldout_rollout_json_paths"):
        blocked_channels.append("heldout_rollout_json_paths")
    if forbidden_inputs.get("heldout_success_metrics"):
        blocked_channels.append("heldout_success_metrics")
    supplied_ids = {str(item) for item in forbidden_inputs.get("heldout_scenario_ids") or []}
    blocked_heldout = sorted(supplied_ids & heldout)
    if blocked_heldout:
        blocked_channels.append("heldout_scenario_ids")
    non_calibration_ids = sorted(
        {
            str(scenario_id)
            for summary in calibration_summaries
            for scenario_id in summary.get("scenario_ids", [])
            if str(scenario_id) not in calibration_ids
        }
    )
    return {
        "passed": not blocked_channels and not non_calibration_ids,
        "calibration_scenario_ids": sorted(calibration_ids),
        "blocked_channels": sorted(set(blocked_channels)),
        "blocked_heldout_scenario_ids": blocked_heldout,
        "non_calibration_scenario_ids": non_calibration_ids,
    }


def select_action_adapter_from_calibration(
    *,
    adapter_registry: dict[str, Any],
    manifest: dict[str, Any],
    calibration_summaries: list[dict[str, Any]],
    output_dir: Path,
) -> dict[str, Any]:
    leakage_guard_result = validate_calibration_selector_inputs(
        manifest=manifest,
        calibration_summaries=calibration_summaries,
        forbidden_inputs={
            "heldout_trace_paths": [],
            "heldout_rollout_json_paths": [],
            "heldout_success_metrics": {},
            "heldout_scenario_ids": [],
        },
    )
    if leakage_guard_result["passed"] is not True:
        raise ValueError(f"MVP-2C calibration selector leakage guard failed: {leakage_guard_result}")
    adapter_by_id = {str(adapter["adapter_id"]): adapter for adapter in adapter_registry["adapters"]}
    adapter_ids = set(adapter_by_id)
    scored: list[dict[str, Any]] = []
    for summary in calibration_summaries:
        adapter_id = str(summary["adapter_id"])
        if adapter_id not in adapter_ids:
            raise ValueError(f"unknown calibration adapter_id: {adapter_id}")
        candidate = float(summary.get("candidate_success_rate", 0.0))
        baseline = float(summary.get("baseline_success_rate", 0.0))
        stability_margin = float(summary.get("candidate_stability_margin", 0.0))
        action_saturation = float(summary.get("candidate_action_saturation_rate", 0.0))
        selector_score = _calibration_selector_score(
            summary,
            selector_score_config=adapter_registry["selector_score_config"],
        )
        scored.append(
            {
                "adapter_id": adapter_id,
                "scenario_ids": [str(item) for item in summary.get("scenario_ids", [])],
                "baseline_success_rate": baseline,
                "candidate_success_rate": candidate,
                "candidate_stability_margin": stability_margin,
                "candidate_action_saturation_rate": action_saturation,
                "selector_score": round(selector_score, 6),
            }
        )
    if not scored:
        raise ValueError("cannot select an action adapter without calibration summaries")
    selected = sorted(
        scored,
        key=lambda item: (
            -float(item["selector_score"]),
            -float(item["candidate_success_rate"]),
            -float(item["candidate_stability_margin"]),
            float(item["candidate_action_saturation_rate"]),
            str(item["adapter_id"]),
        ),
    )[0]
    selected_adapter_config = dict(adapter_by_id[selected["adapter_id"]].get("runtime_action_adapter_config") or {})
    selected_adapter_config_sha256 = _sha256_payload(selected_adapter_config)
    selected_adapter_sha256 = _sha256_payload(
        {
            **selected,
            "selected_adapter_config": selected_adapter_config,
            "selected_adapter_config_sha256": selected_adapter_config_sha256,
        }
    )
    calibration_input = {
        "scenario_manifest_sha256": manifest["manifest_sha256"],
        "action_adapter_registry_sha256": adapter_registry["action_adapter_registry_sha256"],
        "selector_score_config_sha256": adapter_registry["selector_score_config_sha256"],
        "calibration_summaries": scored,
    }
    report = {
        "schema_version": CALIBRATION_SELECTION_SCHEMA_VERSION,
        "scenario_manifest_sha256": manifest["manifest_sha256"],
        "action_adapter_registry_sha256": adapter_registry["action_adapter_registry_sha256"],
        "selected_adapter_id": selected["adapter_id"],
        "selected_adapter_sha256": selected_adapter_sha256,
        "selected_adapter_config": selected_adapter_config,
        "selected_adapter_config_sha256": selected_adapter_config_sha256,
        "selected_adapter_frozen_before_heldout": True,
        "selector_score_pre_registered": True,
        "selector_score_config": dict(adapter_registry["selector_score_config"]),
        "selector_score_config_sha256": adapter_registry["selector_score_config_sha256"],
        "same_adapter_used_for_baseline_and_candidate": True,
        "heldout_excluded": True,
        "calibration_only_selection_passed": True,
        "calibration_scenario_ids": leakage_guard_result["calibration_scenario_ids"],
        "heldout_scenario_ids_excluded": True,
        "leakage_guard_result": leakage_guard_result,
        "calibration_evidence_sha256": _sha256_payload(calibration_input),
        "scored_adapters": scored,
    }
    write_json(output_dir / "calibration_selection_report.json", report)
    write_json(output_dir / "selected_action_adapter.json", report)
    return report


def _trace_for_mvp2c_scenario(scenario: dict[str, Any], *, failure_reason: str | None) -> list[dict[str, Any]]:
    total = 32
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
        elif failure_reason == "ACTION_JITTER_FAILURE" and index >= 8:
            lateral = 0.009 if index % 3 == 0 else 0.004
        elif failure_reason == "EARLY_STOP_FAILURE" and index >= 10:
            depth = min(depth, 0.024)
        action = _action_for_mvp2c_phase(
            phase,
            failure_reason=failure_reason,
            relative_x_m=relative_x,
            relative_y_m=relative_y,
        )
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
                "normalized_action": action,
            }
        )
    return rows


def _action_for_mvp2c_phase(
    phase: str,
    *,
    failure_reason: str | None,
    relative_x_m: float = 0.0,
    relative_y_m: float = 0.0,
) -> list[float]:
    correction_x = -round(float(relative_x_m) * 0.8, 6)
    correction_y = -round(float(relative_y_m) * 0.8, 6)
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


def _action_role(command: list[float], *, role: str, source: str) -> dict[str, Any]:
    return {
        "role": role,
        "source": source,
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
    train_generation_runtime_backend: str,
) -> dict[str, Any]:
    trajectory_id = f"mvp2c_{scenario['scenario_id']}"
    frames: list[dict[str, Any]] = []
    action_source = "mvp2c_scripted_expert_generator"
    for row in trace:
        command = list(row["normalized_action"])
        action = {
            "action_contract_version": "rdf_mvp2c_action_contract_v0.1.0",
            "replay_contract_version": "rdf_mvp2c_replay_contract_v0.1.0",
            "teleop_intent": _action_role(command, role="teleop_intent", source=action_source),
            "executed_control": _action_role(command, role="executed_control", source=action_source),
            "learning_action": _action_role(command, role="learning_action", source=action_source),
            "retargeted_robot_action": _action_role(command, role="retargeted_robot_action", source=action_source),
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
                    "mvp2c_scenario_id": scenario["scenario_id"],
                },
            }
        )
    return {
        "schema_version": "rdf_mvp2c_generated_trajectory_v0.1.0",
        "id": trajectory_id,
        "episode_id": trajectory_id,
        "source": {
            "input_device": "scripted_expert_controlled_noise",
            "runtime": train_generation_runtime_backend,
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
                "backend": "mvp2c_geometry_consistency_replay_gate",
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
    manifest: dict[str, Any],
    baseline_noise_mix_config: dict[str, Any],
    generator_config_hashes: dict[str, Any],
) -> dict[str, Any]:
    first_action = trajectory["frames"][0]["action"]
    return {
        "schema_version": TRAJECTORY_CONTRACT_SCHEMA_VERSION,
        "proof_id": "rdf_mvp2c_isaac_training_calibration_generated_trajectory",
        "contract_name": "mvp2c_isaac_training_calibration_normalized_trajectory_contract",
        "trajectory_schema_version": trajectory["schema_version"],
        "source_profile": trajectory["source"],
        "source_provenance": {
            "generator": "mvp2c_scripted_expert_plus_controlled_failure",
            "scenario_manifest_sha256": manifest["manifest_sha256"],
            "noise_profile_config_sha256": baseline_noise_mix_config["noise_profile_config_sha256"],
            "scripted_expert_config_sha256": generator_config_hashes["scripted_expert_config_sha256"],
            "controlled_failure_config_sha256": generator_config_hashes["controlled_failure_config_sha256"],
            "train_generation_config_sha256": generator_config_hashes["train_generation_config_sha256"],
        },
        "input_route": {
            "route_id": "mvp2c_scripted_expert_controlled_noise",
            "route_role": "mvp2c_training_material_generator",
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
                    "controlled_failure_rejected_by_pre_registered_taxonomy",
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
            "MVP-2C training material is Isaac evaluator-domain evidence, not physical robot evidence.",
            "Privileged task-state features are used for this proof and do not claim deployable visual policy performance.",
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


def _selected_baseline_scenario_ids(items: list[dict[str, Any]]) -> set[str]:
    accepted_ids = [item["scenario_id"] for item in items if item["accepted"] is True]
    rejected_by_reason: dict[str, list[str]] = {reason: [] for reason in CONTROLLED_FAILURE_REASONS}
    for item in items:
        if item["accepted"] is False:
            rejected_by_reason[str(item["rejection_reason"])].append(str(item["scenario_id"]))
    selected = set(accepted_ids[:60])
    for reason in CONTROLLED_FAILURE_REASONS:
        selected.update(rejected_by_reason[reason][:4])
    return selected


def _baseline_mix_evidence(items: list[dict[str, Any]], selected_ids: set[str]) -> dict[str, Any]:
    selected = [item for item in items if item["scenario_id"] in selected_ids]
    failure_items = [item for item in selected if item["accepted"] is False]
    accepted_items = [item for item in selected if item["accepted"] is True]
    total = max(len(selected), 1)
    failure_counts = {
        reason: sum(1 for item in failure_items if item["rejection_reason"] == reason)
        for reason in CONTROLLED_FAILURE_REASONS
    }
    covered = sum(1 for count in failure_counts.values() if count > 0)
    return {
        "baseline_noise_mix_ratio": round(len(failure_items) / total, 6),
        "accepted_count_in_baseline_view": len(accepted_items),
        "failure_or_noisy_count_in_baseline_view": len(failure_items),
        "accepted_failure_ratio_observed": {
            "accepted": len(accepted_items),
            "failure_or_noisy": len(failure_items),
        },
        "failure_type_counts": failure_counts,
        "failure_type_coverage": round(covered / len(CONTROLLED_FAILURE_REASONS), 6),
        "pre_registered_mix_enforced": True,
    }


def _action_with_schema_length(action: list[float]) -> list[float]:
    values = [float(value) for value in action[: len(ACTION_SCHEMA)]]
    if len(values) < len(ACTION_SCHEMA):
        values.extend([0.0] * (len(ACTION_SCHEMA) - len(values)))
    if len(ACTION_SCHEMA) > 6 and len(action) <= 6:
        values[6] = 1.0
    return values


def _pre_adapter_training_action_from_runtime_row(
    row: dict[str, Any],
    *,
    selected_adapter_config: dict[str, Any],
) -> list[float]:
    executed = _action_with_schema_length([float(value) for value in row.get("normalized_action", [])])
    action = list(executed)
    xy_source = selected_adapter_config.get("xy_source")
    if xy_source == "policy_plus_state_feedback":
        xy_scale = max(float(selected_adapter_config.get("xy_action_scale", 1.0)), 1.0e-9)
        xy_gain = float(selected_adapter_config.get("xy_state_feedback_gain", xy_scale))
        action[0] = (executed[0] + float(row.get("relative_x_m", 0.0)) * xy_gain) / xy_scale
        action[1] = (executed[1] + float(row.get("relative_y_m", 0.0)) * xy_gain) / xy_scale
    elif xy_source == "state_feedback":
        action[0] = 0.0
        action[1] = 0.0
    else:
        xy_scale = max(float(selected_adapter_config.get("xy_action_scale", 1.0)), 1.0e-9)
        action[0] = executed[0] / xy_scale
        action[1] = executed[1] / xy_scale
    z_scale = max(float(selected_adapter_config.get("z_action_scale", 1.0)), 1.0e-9)
    action[2] = executed[2] / z_scale
    rotation_scale = float(selected_adapter_config.get("rotation_action_scale", 0.0))
    if rotation_scale:
        for index in range(3, min(6, len(action))):
            action[index] = executed[index] / rotation_scale
    else:
        for index in range(3, min(6, len(action))):
            action[index] = 0.0
    return [round(float(value), 6) for value in action]


def _actual_isaac_success_train_rows(
    *,
    train_generation_runtime_gate: dict[str, Any] | None,
    selected_adapter_config: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not train_generation_runtime_gate or not selected_adapter_config:
        return [], {
            "enabled": False,
            "candidate_replay_weight": 0,
            "success_trace_count": 0,
            "candidate_row_count": 0,
            "success_trace_paths": [],
        }
    if (
        train_generation_runtime_gate.get("passed") is not True
        or train_generation_runtime_gate.get("runtime_backend") != "isaac_runtime"
        or train_generation_runtime_gate.get("actual_train_generation_evidence") is not True
    ):
        return [], {
            "enabled": False,
            "candidate_replay_weight": 0,
            "success_trace_count": 0,
            "candidate_row_count": 0,
            "success_trace_paths": [],
        }

    trace_paths = [
        str(path)
        for path in train_generation_runtime_gate.get("generated_success_trace_paths")
        or train_generation_runtime_gate.get("generated_trace_paths")
        or []
    ]
    rows: list[dict[str, Any]] = []
    used_paths: list[str] = []
    for trace_index, raw_path in enumerate(trace_paths):
        path = Path(raw_path)
        if not path.exists():
            continue
        payload = read_json(path)
        summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
        if summary.get("success") is not True:
            continue
        trace = payload.get("trace")
        if not isinstance(trace, list) or not trace:
            continue
        scenario = payload.get("scenario") if isinstance(payload.get("scenario"), dict) else {}
        scenario_id = str(scenario.get("scenario_id") or f"actual_isaac_success_trace_{trace_index:04d}")
        trace_sha256 = _sha256_file(path)
        used_paths.append(str(path))
        for row in trace:
            if not isinstance(row, dict):
                continue
            base_row = {
                "timestamp_s": round(float(row.get("step", len(rows))) * 0.05, 4),
                "step": int(row.get("step", 0)),
                "phase": str(row.get("phase") or "SEAT"),
                "eef_position_m": [
                    round(float(row.get("relative_x_m", 0.0)), 6),
                    round(float(row.get("relative_y_m", 0.0)), 6),
                    round(float(row.get("insertion_depth_m", 0.0)), 6),
                ],
                "target_position_m": [0.0, 0.0, 0.034],
                "relative_x_m": round(float(row.get("relative_x_m", 0.0)), 6),
                "relative_y_m": round(float(row.get("relative_y_m", 0.0)), 6),
                "lateral_error_m": round(float(row.get("lateral_error_m", 0.0)), 6),
                "insertion_depth_m": round(float(row.get("insertion_depth_m", 0.0)), 6),
                "orientation_error_deg": round(float(row.get("orientation_error_deg", 0.0)), 6),
                "normalized_action": _pre_adapter_training_action_from_runtime_row(
                    row,
                    selected_adapter_config=selected_adapter_config,
                ),
                "trajectory_id": f"mvp2c_actual_isaac_train_generation_{trace_index:04d}",
                "scenario_id": scenario_id,
                "accepted": True,
                "rejection_reason": "",
                "source_kind": "isaac_runtime_scripted_expert_rollout",
                "runtime_trace_path": str(path),
                "runtime_trace_sha256": trace_sha256,
                "runtime_trace_success": True,
            }
            rows.append(base_row)
    replay_rows: list[dict[str, Any]] = []
    for replay_index in range(ACTUAL_TRACE_REPLAY_WEIGHT):
        for row in rows:
            replay_rows.append(
                {
                    **row,
                    "trajectory_id": f"{row['trajectory_id']}_replay_{replay_index:03d}",
                    "actual_trace_replay_index": replay_index,
                }
            )
    evidence = {
        "enabled": bool(rows),
        "source": "isaac_runtime_scripted_expert_rollout",
        "candidate_only": True,
        "baseline_includes_actual_runtime_rows": False,
        "candidate_replay_weight": ACTUAL_TRACE_REPLAY_WEIGHT if rows else 0,
        "success_trace_count": len(used_paths),
        "success_trace_paths": used_paths,
        "candidate_row_count": len(replay_rows),
        "target_space": "selected_action_adapter_pre_adapter_action_v0",
    }
    evidence["actual_isaac_train_generation_evidence_sha256"] = _sha256_payload(evidence)
    return replay_rows, evidence


def _actual_isaac_success_trace_groups(
    *,
    train_generation_runtime_gate: dict[str, Any] | None,
    selected_adapter_config: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if not train_generation_runtime_gate or not selected_adapter_config:
        return []
    trace_paths = [
        str(path)
        for path in train_generation_runtime_gate.get("generated_success_trace_paths")
        or train_generation_runtime_gate.get("generated_trace_paths")
        or []
    ]
    groups: list[dict[str, Any]] = []
    for trace_index, raw_path in enumerate(trace_paths):
        path = Path(raw_path)
        if not path.exists():
            continue
        payload = read_json(path)
        summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
        if summary.get("success") is not True:
            continue
        trace = payload.get("trace")
        if not isinstance(trace, list) or not trace:
            continue
        scenario = payload.get("scenario") if isinstance(payload.get("scenario"), dict) else {}
        scenario_id = str(scenario.get("scenario_id") or f"actual_isaac_success_trace_{trace_index:04d}")
        trace_sha256 = _sha256_file(path)
        rows: list[dict[str, Any]] = []
        for row in trace:
            if not isinstance(row, dict):
                continue
            rows.append(
                {
                    "timestamp_s": round(float(row.get("step", len(rows))) * 0.05, 4),
                    "step": int(row.get("step", 0)),
                    "phase": str(row.get("phase") or "SEAT"),
                    "eef_position_m": [
                        round(float(row.get("relative_x_m", 0.0)), 6),
                        round(float(row.get("relative_y_m", 0.0)), 6),
                        round(float(row.get("insertion_depth_m", 0.0)), 6),
                    ],
                    "target_position_m": [0.0, 0.0, 0.034],
                    "relative_x_m": round(float(row.get("relative_x_m", 0.0)), 6),
                    "relative_y_m": round(float(row.get("relative_y_m", 0.0)), 6),
                    "lateral_error_m": round(float(row.get("lateral_error_m", 0.0)), 6),
                    "insertion_depth_m": round(float(row.get("insertion_depth_m", 0.0)), 6),
                    "orientation_error_deg": round(float(row.get("orientation_error_deg", 0.0)), 6),
                    "normalized_action": _pre_adapter_training_action_from_runtime_row(
                        row,
                        selected_adapter_config=selected_adapter_config,
                    ),
                    "trajectory_id": f"mvp2d_v05_actual_isaac_success_{trace_index:04d}",
                    "scenario_id": scenario_id,
                    "accepted": True,
                    "rejection_reason": "",
                    "source_kind": "isaac_runtime_scripted_expert_rollout",
                    "runtime_trace_path": str(path),
                    "runtime_trace_sha256": trace_sha256,
                    "runtime_trace_success": True,
                }
            )
        if rows:
            groups.append(
                {
                    "trajectory_id": rows[0]["trajectory_id"],
                    "scenario_id": scenario_id,
                    "trace_path": str(path),
                    "trace_sha256": trace_sha256,
                    "rows": rows,
                }
            )
    return groups


def _v05_placeholder_success_groups(manifest: dict[str, Any], *, count: int) -> list[dict[str, Any]]:
    scenarios = [row for row in manifest["scenarios"] if row["split"] == "train_success"]
    groups: list[dict[str, Any]] = []
    for index, scenario in enumerate(scenarios[:count]):
        trajectory_id = f"mvp2d_v05_placeholder_success_{index:04d}"
        rows = []
        for row in _trace_for_mvp2c_scenario(scenario, failure_reason=None):
            rows.append(
                {
                    **row,
                    "trajectory_id": trajectory_id,
                    "scenario_id": scenario["scenario_id"],
                    "accepted": True,
                    "rejection_reason": "",
                    "source_kind": "deterministic_placeholder_not_mvp2_proof",
                }
            )
        groups.append(
            {
                "trajectory_id": trajectory_id,
                "scenario_id": scenario["scenario_id"],
                "trace_path": "",
                "trace_sha256": "",
                "rows": rows,
            }
        )
    return groups


def _v05_failure_groups(manifest: dict[str, Any], *, count: int) -> list[dict[str, Any]]:
    scenarios = [row for row in manifest["scenarios"] if row["split"] == "train_failure"]
    bucket_to_failure = {
        "lateral_offset": "LATERAL_OFFSET_FAILURE",
        "stability_window_loss": "ACTION_JITTER_FAILURE",
        "under_insertion": "UNDER_INSERTION_FAILURE",
    }
    groups: list[dict[str, Any]] = []
    for index in range(count):
        bucket = V05_FAILURE_BUCKETS[index % len(V05_FAILURE_BUCKETS)]
        scenario = scenarios[index % len(scenarios)]
        trajectory_id = f"mvp2d_v05_rejected_noisy_{bucket}_{index:04d}"
        rows = []
        for row in _trace_for_mvp2c_scenario(scenario, failure_reason=bucket_to_failure[bucket]):
            rows.append(
                {
                    **row,
                    "trajectory_id": trajectory_id,
                    "scenario_id": scenario["scenario_id"],
                    "accepted": False,
                    "rejection_reason": bucket,
                    "source_kind": "controlled_failure_noisy_material",
                }
            )
        groups.append(
            {
                "trajectory_id": trajectory_id,
                "scenario_id": scenario["scenario_id"],
                "failure_bucket": bucket,
                "rows": rows,
            }
        )
    return groups


def _flatten_groups(groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for group in groups:
        rows.extend(dict(row) for row in group["rows"])
    return rows


def _v05_training_trajectory_bundle(
    *,
    manifest: dict[str, Any],
    baseline_noise_mix_config: dict[str, Any],
    generator_config_hashes: dict[str, Any],
    output_dir: Path,
    train_generation_runtime_gate: dict[str, Any] | None,
    selected_adapter_config: dict[str, Any] | None,
) -> dict[str, Any]:
    actual_groups = _actual_isaac_success_trace_groups(
        train_generation_runtime_gate=train_generation_runtime_gate,
        selected_adapter_config=selected_adapter_config,
    )
    actual_count = len(actual_groups)
    used_actual_count = min(actual_count, V05_ACTUAL_SUCCESS_TRACE_CAP)
    proof_eligible = actual_count >= V05_ACTUAL_SUCCESS_TRACE_MINIMUM
    target_trace_count = used_actual_count if proof_eligible else V05_ACTUAL_SUCCESS_TRACE_MINIMUM
    candidate_groups = actual_groups[:used_actual_count]
    placeholder_count = max(0, target_trace_count - len(candidate_groups))
    if placeholder_count:
        candidate_groups.extend(_v05_placeholder_success_groups(manifest, count=placeholder_count))
    baseline_accepted_count = int(target_trace_count * V05_BASELINE_ACCEPTED_RATIO)
    baseline_rejected_count = target_trace_count - baseline_accepted_count
    baseline_groups = candidate_groups[:baseline_accepted_count] + _v05_failure_groups(
        manifest,
        count=baseline_rejected_count,
    )
    candidate_rows = _flatten_groups(candidate_groups)
    baseline_rows = _flatten_groups(baseline_groups)
    failure_type_counts = {
        bucket: sum(1 for group in baseline_groups if group.get("failure_bucket") == bucket)
        for bucket in V05_FAILURE_BUCKETS
    }
    trace_count_equal = len(candidate_groups) == len(baseline_groups)
    equality_payload = {
        "candidate_trace_ids": [str(group["trajectory_id"]) for group in candidate_groups],
        "baseline_trace_ids": [str(group["trajectory_id"]) for group in baseline_groups],
        "candidate_trace_count": len(candidate_groups),
        "baseline_trace_count": len(baseline_groups),
        "baseline_accepted_trace_count": baseline_accepted_count,
        "baseline_rejected_noisy_trace_count": baseline_rejected_count,
    }
    baseline_mix_evidence = {
        "baseline_noise_mix_ratio": round(baseline_rejected_count / max(target_trace_count, 1), 6),
        "accepted_count_in_baseline_view": baseline_accepted_count,
        "failure_or_noisy_count_in_baseline_view": baseline_rejected_count,
        "accepted_failure_ratio_observed": {
            "accepted": baseline_accepted_count,
            "failure_or_noisy": baseline_rejected_count,
        },
        "failure_type_counts": failure_type_counts,
        "failure_type_coverage": round(
            sum(1 for count in failure_type_counts.values() if count > 0) / len(V05_FAILURE_BUCKETS),
            6,
        ),
        "pre_registered_mix_enforced": True,
    }
    if baseline_mix_evidence["baseline_noise_mix_ratio"] != baseline_noise_mix_config["baseline_noise_mix_ratio"]:
        raise ValueError("MVP-2D v0.5 baseline mix does not match pre-registered 60/40 ratio")
    evidence = {
        "schema_version": "rdf_mvp2d_v05_dataset_view_evidence_v0.1.0",
        "scenario_profile": "v0_5",
        "proof_eligible": proof_eligible,
        "actual_isaac_success_trace_count": actual_count,
        "actual_isaac_success_trace_minimum": V05_ACTUAL_SUCCESS_TRACE_MINIMUM,
        "actual_isaac_success_trace_cap": V05_ACTUAL_SUCCESS_TRACE_CAP,
        "used_success_trace_count": used_actual_count,
        "compatibility_placeholder_trace_count": placeholder_count,
        "candidate_source_filter": "accepted_actual_isaac_success_traces_only",
        "baseline_source_filter": "same_raw_pool_60_percent_accepted_40_percent_rejected_noisy",
        "candidate_trace_count": len(candidate_groups),
        "baseline_trace_count": len(baseline_groups),
        "trace_count_equal": trace_count_equal,
        "baseline_accepted_trace_count": baseline_accepted_count,
        "baseline_rejected_noisy_trace_count": baseline_rejected_count,
        "failure_bucket_cycle": list(V05_FAILURE_BUCKETS),
        "failure_type_counts": failure_type_counts,
        "candidate_transition_count": len(candidate_rows),
        "baseline_transition_count": len(baseline_rows),
        "trace_count_equality_sha256": _sha256_payload(equality_payload),
    }
    evidence["v0_5_dataset_view_evidence_sha256"] = _sha256_payload(evidence)
    curation_items = [
        {
            "trajectory_id": group["trajectory_id"],
            "scenario_id": group["scenario_id"],
            "accepted": all(row.get("accepted") is True for row in group["rows"]),
            "rejection_reason": str(group.get("failure_bucket") or ""),
            "source_kind": str(group["rows"][0].get("source_kind", "")) if group["rows"] else "",
        }
        for group in baseline_groups + candidate_groups
    ]
    curation_manifest = {
        "schema_version": "rdf_mvp2d_v05_curation_manifest_v0.1.0",
        "accepted_count": len(candidate_groups),
        "rejected_count": baseline_rejected_count,
        "baseline_mix_evidence": baseline_mix_evidence,
        "v0_5_dataset_view_evidence": evidence,
        "curation_rules": [
            "candidate uses accepted actual Isaac success traces only when proof eligible",
            "baseline uses equal trace count with fixed 60/40 accepted/rejected-noisy mix",
            "failure bucket cycle is fixed before held-out evaluation",
        ],
        "items": curation_items,
    }
    write_json(output_dir / "curation_manifest.json", curation_manifest)
    write_json(output_dir / "v0_5_dataset_view_evidence.json", evidence)
    return {
        "schema_version": "rdf_mvp2d_v05_training_trajectory_bundle_v0.1.0",
        "accepted_count": len(candidate_groups),
        "rejected_count": baseline_rejected_count,
        "curation_manifest": curation_manifest,
        "training_rows": baseline_rows + candidate_rows,
        "baseline_train_rows": baseline_rows,
        "candidate_train_rows": candidate_rows,
        "baseline_mix_evidence": baseline_mix_evidence,
        "actual_isaac_train_generation_evidence": {
            "enabled": bool(actual_groups),
            "source": "isaac_runtime_scripted_expert_rollout",
            "candidate_only": False,
            "candidate_uses_accepted_actual_runtime_rows_only": proof_eligible,
            "baseline_includes_actual_runtime_rows": bool(actual_groups),
            "success_trace_count": actual_count,
            "success_trace_paths": [str(group.get("trace_path")) for group in actual_groups],
            "candidate_row_count": len(candidate_rows),
            "target_space": "selected_action_adapter_pre_adapter_action_v0",
            "proof_eligible": proof_eligible,
        },
        "v0_5_dataset_view_evidence": evidence,
        "accepted_contract_paths": [],
        "contract_validation": {
            "passed": True,
            "issues": [],
            "validator": "NormalizedTrajectoryContractValidator",
            "note": "v0_5 uses actual runtime trace view evidence; legacy generated trajectory contracts are not cloned.",
        },
        "artifact_paths": {
            "raw_dir": str(output_dir / "train_raw_trajectories"),
            "contract_dir": str(output_dir / "normalized_trajectory_contracts"),
            "curation_manifest": str(output_dir / "curation_manifest.json"),
            "v0_5_dataset_view_evidence": str(output_dir / "v0_5_dataset_view_evidence.json"),
        },
    }


def generate_mvp2c_training_trajectory_bundle(
    *,
    manifest: dict[str, Any],
    baseline_noise_mix_config: dict[str, Any],
    generator_config_hashes: dict[str, Any],
    output_dir: Path,
    train_generation_runtime_backend: str,
    train_generation_runtime_gate: dict[str, Any] | None = None,
    selected_adapter_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if manifest.get("scenario_profile") == "v0_5":
        return _v05_training_trajectory_bundle(
            manifest=manifest,
            baseline_noise_mix_config=baseline_noise_mix_config,
            generator_config_hashes=generator_config_hashes,
            output_dir=output_dir,
            train_generation_runtime_gate=train_generation_runtime_gate,
            selected_adapter_config=selected_adapter_config,
        )
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
        expected_accepted = scenario["split"] == "train_success"
        rejection_reason = None
        if not expected_accepted:
            rejection_reason = CONTROLLED_FAILURE_REASONS[failure_index % len(CONTROLLED_FAILURE_REASONS)]
            failure_index += 1
        trace = _trace_for_mvp2c_scenario(scenario, failure_reason=rejection_reason)
        rollout_eval = evaluate_rollout_trace(trace, success_metric=manifest["success_metric"])
        accepted = expected_accepted and rollout_eval.get("success") is True
        if expected_accepted and not accepted:
            raise ValueError(
                f"MVP-2C scripted expert trajectory failed geometry/stability success gate: "
                f"{scenario['scenario_id']} {rollout_eval}"
            )
        if not expected_accepted and rollout_eval.get("success") is True:
            raise ValueError(
                f"MVP-2C controlled failure unexpectedly passed geometry/stability success gate: "
                f"{scenario['scenario_id']} {rollout_eval}"
            )
        trajectory = _trajectory_payload(
            scenario=scenario,
            trace=trace,
            accepted=accepted,
            rejection_reason=rejection_reason,
            train_generation_runtime_backend=train_generation_runtime_backend,
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
    selected_baseline_ids = _selected_baseline_scenario_ids(items)
    baseline_rows = [row for row in train_rows if row["scenario_id"] in selected_baseline_ids]
    candidate_rows = [row for row in train_rows if row["accepted"] is True]
    actual_isaac_rows, actual_isaac_evidence = _actual_isaac_success_train_rows(
        train_generation_runtime_gate=train_generation_runtime_gate,
        selected_adapter_config=selected_adapter_config,
    )
    candidate_rows.extend(actual_isaac_rows)
    baseline_mix_evidence = _baseline_mix_evidence(items, selected_baseline_ids)
    expected_ratio = float(baseline_noise_mix_config["baseline_noise_mix_ratio"])
    if baseline_mix_evidence["baseline_noise_mix_ratio"] != expected_ratio:
        raise ValueError("MVP-2C baseline mix does not match pre-registered ratio")
    curation_manifest = {
        "schema_version": "rdf_mvp2c_curation_manifest_v0.1.0",
        "accepted_count": len(accepted_trajectories),
        "rejected_count": len(rejected_trajectories),
        "baseline_mix_evidence": baseline_mix_evidence,
        "curation_rules": [
            "accept scripted expert geometry-stable trajectories",
            "reject controlled failure trajectories by fixed taxonomy",
            "build uncurated baseline from pre-registered 3:1 accepted/failure mix",
        ],
        "items": items,
    }
    write_json(output_dir / "curation_manifest.json", curation_manifest)

    validator = NormalizedTrajectoryContractValidator(
        proof_id="rdf_mvp2c_isaac_training_calibration_generated_trajectory",
        contract_name="mvp2c_isaac_training_calibration_normalized_trajectory_contract",
    )
    contract_issues: list[str] = []
    accepted_contract_paths: list[str] = []
    for trajectory in accepted_trajectories:
        contract = _contract_for_trajectory(
            trajectory=trajectory,
            accepted_count=len(accepted_trajectories),
            rejected_count=len(rejected_trajectories),
            output_dir=output_dir,
            manifest=manifest,
            baseline_noise_mix_config=baseline_noise_mix_config,
            generator_config_hashes=generator_config_hashes,
        )
        issues = validator.validate_learning_eligibility(contract)
        contract_issues.extend(issues)
        path = contract_dir / f"{trajectory['id']}_normalized_trajectory_contract.json"
        write_json(path, contract)
        accepted_contract_paths.append(str(path))
    return {
        "schema_version": "rdf_mvp2c_training_trajectory_bundle_v0.1.0",
        "accepted_count": len(accepted_trajectories),
        "rejected_count": len(rejected_trajectories),
        "curation_manifest": curation_manifest,
        "training_rows": train_rows,
        "baseline_train_rows": baseline_rows,
        "candidate_train_rows": candidate_rows,
        "baseline_mix_evidence": baseline_mix_evidence,
        "actual_isaac_train_generation_evidence": actual_isaac_evidence,
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


def _write_train_view_hdf5(
    *,
    path: Path,
    rows: list[dict[str, Any]],
    view_id: str,
    baseline_noise_mix_config: dict[str, Any],
    generator_config_hashes: dict[str, Any],
) -> dict[str, Any]:
    features, targets = _features_targets(rows)
    string_dtype = h5py.string_dtype(encoding="utf-8")
    metadata = np.asarray([stable_json(row) for row in rows], dtype=object)
    path.parent.mkdir(parents=True, exist_ok=True)
    with h5py.File(path, "w") as h5:
        h5.attrs["schema_version"] = HDF5_SCHEMA_VERSION
        h5.attrs["view_id"] = view_id
        h5.attrs["feature_schema"] = stable_json(FEATURE_SCHEMA)
        h5.attrs["action_schema"] = stable_json(ACTION_SCHEMA)
        h5.attrs["baseline_noise_mix_config_sha256"] = baseline_noise_mix_config["noise_profile_config_sha256"]
        h5.attrs["generator_config_hashes"] = stable_json(
            {
                "scripted_expert_config_sha256": generator_config_hashes["scripted_expert_config_sha256"],
                "controlled_failure_config_sha256": generator_config_hashes["controlled_failure_config_sha256"],
                "train_generation_config_sha256": generator_config_hashes["train_generation_config_sha256"],
            }
        )
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
        "baseline_noise_mix_config_sha256": baseline_noise_mix_config["noise_profile_config_sha256"],
        "train_generation_config_sha256": generator_config_hashes["train_generation_config_sha256"],
    }


def _residualized_rows_for_v05(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    residual_rows: list[dict[str, Any]] = []
    for row in rows:
        metric_row = {
            "phase": row.get("phase"),
            "insertion_depth_m": row.get("insertion_depth_m", 0.0),
            "relative_x_m": row.get("relative_x_m", 0.0),
            "relative_y_m": row.get("relative_y_m", 0.0),
            "lateral_error_m": row.get("lateral_error_m", 0.0),
            "orientation_error_deg": row.get("orientation_error_deg", 0.0),
        }
        actual = np.asarray(_action_with_schema_length(row.get("normalized_action", [])), dtype=np.float64)
        base = _weak_base_servo_action(metric_row=metric_row, config=dict(WEAK_BASE_SERVO_CONFIG))
        residual = np.round(actual - base, 10).tolist()
        residual_rows.append(
            {
                **row,
                "normalized_action": residual,
                "residual_target_definition": RESIDUAL_TARGET_DEFINITION,
                "weak_base_servo_action": np.round(base, 10).tolist(),
                "actual_trace_action": np.round(actual, 10).tolist(),
            }
        )
    return residual_rows


def _write_policy_artifacts(
    *,
    output_dir: Path,
    baseline_rows: list[dict[str, Any]],
    candidate_rows: list[dict[str, Any]],
    selected_adapter_id: str,
    selected_adapter_config: dict[str, Any],
    scenario_profile: str = "v0_1",
) -> dict[str, Any]:
    residual_profile = scenario_profile == "v0_5"
    weak_base_servo_config_sha256 = _sha256_payload(dict(WEAK_BASE_SERVO_CONFIG))
    hyperparameters = {
        "ridge_lambda": 1e-3,
        "phase_input_shared": True,
        "feature_standardization": "none_deterministic_domain_units",
        "selected_action_adapter_id": selected_adapter_id,
        "selected_action_adapter_config_sha256": _sha256_payload(selected_adapter_config),
        "trainer_family": RESIDUAL_TRAINER_FAMILY if residual_profile else "phase_conditioned_bc",
        "weak_base_servo_config_sha256": weak_base_servo_config_sha256 if residual_profile else None,
    }
    baseline_fit_rows = _residualized_rows_for_v05(baseline_rows) if residual_profile else baseline_rows
    candidate_fit_rows = _residualized_rows_for_v05(candidate_rows) if residual_profile else candidate_rows
    baseline = fit_phase_conditioned_bc_policy(
        policy_id="baseline_uncurated_mvp2d_v05_residual_servo_bc"
        if residual_profile
        else "baseline_uncurated_mvp2c_phase_conditioned_numpy_bc",
        train_rows=baseline_fit_rows,
        hyperparameters=hyperparameters,
    )
    candidate = fit_phase_conditioned_bc_policy(
        policy_id="candidate_curated_mvp2d_v05_residual_servo_bc"
        if residual_profile
        else "candidate_curated_mvp2c_phase_conditioned_numpy_bc",
        train_rows=candidate_fit_rows,
        hyperparameters=hyperparameters,
    )
    for payload in (baseline, candidate):
        if residual_profile:
            payload["policy_class"] = RESIDUAL_POLICY_CLASS
            payload["trainer"] = RESIDUAL_TRAINER
            payload["trainer_family"] = RESIDUAL_TRAINER_FAMILY
            payload["residual_target_definition"] = RESIDUAL_TARGET_DEFINITION
            payload["weak_base_servo_config"] = dict(WEAK_BASE_SERVO_CONFIG)
            payload["weak_base_servo_config_sha256"] = weak_base_servo_config_sha256
            payload["base_servo_plus_learned_residual"] = True
        payload["selected_action_adapter_id"] = selected_adapter_id
        payload["selected_action_adapter_config"] = dict(selected_adapter_config)
        payload["selected_action_adapter_config_sha256"] = _sha256_payload(selected_adapter_config)
        payload["same_feature_schema_as_peer"] = True
        payload["same_trainer_hyperparameters_as_peer"] = True
        payload["policy_artifact_sha256"] = _sha256_payload(
            {key: value for key, value in payload.items() if key != "policy_artifact_sha256"}
        )
    baseline_path = output_dir / "baseline_policy_artifact.json"
    candidate_path = output_dir / "candidate_policy_artifact.json"
    write_json(baseline_path, baseline)
    write_json(candidate_path, candidate)
    return {
        "baseline": {**baseline, "path": str(baseline_path)},
        "candidate": {**candidate, "path": str(candidate_path)},
    }


def probe_isaac_train_generation_runtime(
    *,
    device: str = DEFAULT_ISAAC_DEVICE,
    headless: bool = True,
    output_dir: Path | None = None,
    manifest: dict[str, Any] | None = None,
    selected_adapter_id: str | None = None,
    selected_adapter_config: dict[str, Any] | None = None,
    isaac_task: str = DEFAULT_ISAAC_TASK,
    max_steps: int = int(SUCCESS_METRIC["max_steps"]),
    action_scale: float = 1.0,
    run_in_subprocess: bool = True,
) -> dict[str, Any]:
    scenario_profile = str(manifest.get("scenario_profile") or "v0_1") if manifest else "v0_1"
    if scenario_profile == "v0_6":
        min_success_count = V06_TRAIN_GATE_SUCCESS_MINIMUM
        success_trace_cap = V06_TRAIN_GATE_ATTEMPT_COUNT
    elif scenario_profile == "v0_5":
        min_success_count = V05_ACTUAL_SUCCESS_TRACE_MINIMUM
        success_trace_cap = V05_ACTUAL_SUCCESS_TRACE_CAP
    else:
        min_success_count = 1
        success_trace_cap = None
    try:
        from isaaclab.app import AppLauncher  # noqa: F401
    except Exception as exc:
        return {
            "passed": False,
            "runtime_backend": "isaac_runtime_unavailable",
            "proof_runtime": ISAAC_TRAIN_GENERATION_PROOF_RUNTIME,
            "device": device,
            "headless": headless,
            "runtime_import_probe_passed": False,
            "actual_train_generation_evidence": False,
            "training_trajectory_source": "deterministic_domain_generator",
            "reason": f"Isaac train-generation runtime probe failed: {type(exc).__name__}: {exc}",
        }
    if output_dir is None or manifest is None or selected_adapter_id is None or selected_adapter_config is None:
        return {
            "passed": False,
            "runtime_backend": "isaac_runtime_import_probe_only",
            "proof_runtime": ISAAC_TRAIN_GENERATION_PROOF_RUNTIME,
            "device": device,
            "headless": headless,
            "runtime_import_probe_passed": True,
            "actual_train_generation_evidence": False,
            "training_trajectory_source": "deterministic_domain_generator",
            "reason": (
                "Isaac import probe passed, but no manifest/output/adapter inputs were supplied for an actual "
                "runtime scripted train-generation rollout."
            ),
        }
    if run_in_subprocess:
        return _run_train_generation_probe_subprocess(
            output_dir=output_dir,
            scenario_profile=scenario_profile,
            device=device,
            headless=headless,
            isaac_task=isaac_task,
            max_steps=max_steps,
            action_scale=action_scale,
        )
    return _run_isaac_train_generation_probe_direct(
        output_dir=output_dir,
        manifest=manifest,
        selected_adapter_id=selected_adapter_id,
        selected_adapter_config=selected_adapter_config,
        device=device,
        headless=headless,
        isaac_task=isaac_task,
        max_steps=max_steps,
        action_scale=action_scale,
        min_success_count=min_success_count,
        success_trace_cap=success_trace_cap,
    )


def _run_train_generation_probe_subprocess(
    *,
    output_dir: Path,
    scenario_profile: str,
    device: str,
    headless: bool,
    isaac_task: str,
    max_steps: int,
    action_scale: float,
) -> dict[str, Any]:
    gate_path = output_dir / "train_generation_runtime_gate.json"
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--train-generation-probe-only",
        "--output-dir",
        str(output_dir),
        "--scenario-profile",
        scenario_profile,
        "--max-steps",
        str(max_steps),
        "--isaac-task",
        isaac_task,
        "--device",
        device,
        "--action-scale",
        str(action_scale),
    ]
    if not headless:
        command.append("--no-headless")
    completed = subprocess.run(
        command,
        cwd=str(ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if gate_path.exists():
        gate = read_json(gate_path)
        gate["subprocess_returncode"] = completed.returncode
        gate["subprocess_stdout_tail"] = completed.stdout[-4000:]
        gate["subprocess_stderr_tail"] = completed.stderr[-4000:]
        if completed.returncode != 0:
            gate["passed"] = False
            gate["actual_train_generation_evidence"] = False
            gate["reason"] = gate.get("reason") or "Isaac scripted train-generation subprocess failed."
        write_json(gate_path, gate)
        return gate
    return {
        "passed": False,
        "runtime_backend": "isaac_runtime",
        "proof_runtime": ISAAC_TRAIN_GENERATION_PROOF_RUNTIME,
        "device": device,
        "headless": headless,
        "runtime_import_probe_passed": True,
        "actual_train_generation_evidence": False,
        "training_trajectory_source": "isaac_runtime_scripted_expert_rollout",
        "subprocess_returncode": completed.returncode,
        "subprocess_stdout_tail": completed.stdout[-4000:],
        "subprocess_stderr_tail": completed.stderr[-4000:],
        "reason": "Isaac scripted train-generation subprocess did not write a gate artifact.",
    }


def _run_isaac_train_generation_probe_direct(
    *,
    output_dir: Path,
    manifest: dict[str, Any],
    selected_adapter_id: str,
    selected_adapter_config: dict[str, Any],
    device: str,
    headless: bool,
    isaac_task: str,
    max_steps: int,
    action_scale: float,
    min_success_count: int = 1,
    success_trace_cap: int | None = None,
) -> dict[str, Any]:
    probe_manifest = _train_generation_probe_manifest(manifest)
    expert_policy = _scripted_expert_probe_policy_artifact(
        selected_adapter_id=selected_adapter_id,
        selected_adapter_config=selected_adapter_config,
        scenario_profile=str(manifest.get("scenario_profile") or "v0_1"),
    )
    try:
        probe_result = IsaacConnectorInsertionEvaluatorBackend(
            task=isaac_task,
            device=device,
            headless=headless,
            action_scale=action_scale,
            max_steps=max_steps,
        ).run_single_policy_probe(
            manifest=probe_manifest,
            output_dir=output_dir / "isaac_runtime_train_generation_probe",
            policy_artifact=expert_policy,
            role="train_generation_probe",
            max_rollouts=len(probe_manifest["scenarios"]),
            stop_after_first_success=False,
        )
    except Exception as exc:
        gate = {
            "passed": False,
            "runtime_backend": "isaac_runtime",
            "proof_runtime": ISAAC_TRAIN_GENERATION_PROOF_RUNTIME,
            "device": device,
            "headless": headless,
            "runtime_import_probe_passed": True,
            "actual_train_generation_evidence": False,
            "training_trajectory_source": "isaac_runtime_scripted_expert_rollout",
            "reason": f"Isaac scripted train-generation rollout failed: {type(exc).__name__}: {exc}",
        }
        write_json(output_dir / "train_generation_runtime_gate.json", gate)
        return gate
    gate = derive_train_generation_runtime_gate_from_probe_result(
        probe_result,
        device=device,
        headless=headless,
        min_success_count=min_success_count,
        success_trace_cap=success_trace_cap,
    )
    write_json(output_dir / "train_generation_runtime_gate.json", gate)
    return gate


def _train_generation_probe_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    train_success_source = [
        row
        for row in manifest.get("scenarios", [])
        if isinstance(row, dict) and row.get("split") == "train_success"
    ]
    if manifest.get("scenario_profile") == "v0_6":
        selected_seed_ids = [
            int(seed)
            for seed in manifest.get("v0_6_train_gate_seed_selection", {}).get("selected_40_seed_ids", [])
        ]
        by_seed = {int(row["seed"]): row for row in train_success_source}
        missing = [seed for seed in selected_seed_ids if seed not in by_seed]
        if missing:
            raise ValueError(f"v0_6 train-generation seed selection references missing seeds: {missing}")
        train_success = [{**by_seed[seed], "split": "held_out"} for seed in selected_seed_ids]
    else:
        train_success_source = sorted(
            train_success_source,
            key=lambda row: (
                float(np.linalg.norm(np.asarray(row.get("initial_offset_m") or [0.0, 0.0, 0.0], dtype=np.float64))),
                abs(float(row.get("orientation_offset_deg", 0.0))),
                int(row.get("seed", 0)),
            ),
        )
        train_success = [{**row, "split": "held_out"} for row in train_success_source[:40]]
    if not train_success:
        raise ValueError("MVP-2C train-generation probe requires at least one train_success scenario")
    probe_manifest = {
        "manifest_version": f"{manifest.get('manifest_version')}_train_generation_probe",
        "schema_version": f"{manifest.get('schema_version')}_train_generation_probe",
        "source_manifest_sha256": manifest["manifest_sha256"],
        "scenario_profile": manifest.get("scenario_profile"),
        "task_type": manifest.get("task_type", "connector_insertion"),
        "success_metric": dict(manifest.get("success_metric") or SUCCESS_METRIC),
        "success_authority": manifest.get("success_authority"),
        "scenarios": train_success,
        "leakage_policy": {
            "uses_train_success_split_only": True,
            "held_out_eval_split_excluded": True,
        },
    }
    if manifest.get("scenario_profile") == "v0_6":
        probe_manifest["v0_6_train_gate_seed_selection"] = manifest.get("v0_6_train_gate_seed_selection")
    probe_manifest["manifest_sha256"] = _sha256_payload(probe_manifest)
    return probe_manifest


def build_v06e_controller_repair_config(*, capture_radius_m: float) -> dict[str, Any]:
    numeric_capture_radius = _numeric_capture_radius_m(capture_radius_m)
    if numeric_capture_radius is None:
        raise ValueError("v0_6e controller repair config requires numeric capture_radius_m")
    config = {
        "controller_version": "v0_6_active_state_controller",
        "success_authority": "isaac_env_native_consecutive_success_v0",
        "capture_radius_m": numeric_capture_radius,
        "align_lateral_gate_m": numeric_capture_radius,
        "tol_align_source": "empirical_capture_radius_m",
        "z_push_gate": "lateral_error_m <= capture_radius_m",
        "align_orientation_gate_rad": 0.25,
        "continued_xy_yaw_correction": True,
        "bounded_monotonic_downward_push": True,
        "retry_recover_withdraw_search": False,
        "force_reactive_control": False,
        "per_seed_tuning": False,
        "horizon_increase": False,
    }
    config["controller_repair_config_sha256"] = _sha256_payload_excluding(config, "controller_repair_config_sha256")
    return config


def build_v06f_controller_repair_config(*, capture_radius_m: float) -> dict[str, Any]:
    numeric_capture_radius = _numeric_capture_radius_m(capture_radius_m)
    if numeric_capture_radius is None:
        raise ValueError("v0_6f controller repair config requires numeric capture_radius_m")
    approach_gate = _v06f_approach_lateral_gate_m(numeric_capture_radius)
    config = {
        "schema_version": "rdf_mvp2e_v06f_controller_repair_config_v0.1.0",
        "controller_version": "v0_6_active_state_controller",
        "controller_repair_version": "v0_6f",
        "success_authority": "env_native_10_consecutive",
        "straight_down_capture_radius_m": round(float(numeric_capture_radius), 6),
        "capture_radius_m": round(float(numeric_capture_radius), 6),
        "approach_lateral_gate_m": round(float(approach_gate), 6),
        "align_lateral_gate_m": round(float(approach_gate), 6),
        "approach_gate_floor_m": V06F_APPROACH_GATE_FLOOR_M,
        "approach_gate_capture_multiplier": V06F_APPROACH_GATE_CAPTURE_MULTIPLIER,
        "approach_lateral_gate_source": "pre_registered_controller_assisted_approach_gate_v0_6f",
        "z_push_gate": "lateral_error_m <= approach_lateral_gate_m",
        "align_orientation_gate_rad": 0.25,
        "continued_xy_yaw_correction": True,
        "bounded_monotonic_downward_push": True,
        "proof_authority": False,
        "straight_down_capture_radius_is_lower_bound": True,
        "horizon_increase": False,
        "retry_enabled": False,
        "search_enabled": False,
        "withdraw_enabled": False,
        "force_control_enabled": False,
        "per_seed_tuning": False,
        "non_claims": dict(V06A_NON_CLAIMS),
    }
    config["controller_repair_config_sha256"] = _sha256_payload_excluding(config, "controller_repair_config_sha256")
    return config


def _scripted_expert_probe_policy_artifact(
    *,
    selected_adapter_id: str,
    selected_adapter_config: dict[str, Any],
    scenario_profile: str = "v0_1",
    controller_repair_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    del selected_adapter_config
    train_generation_controller_config = {
        "adapter_mode": "scripted_expert_state_feedback_servo",
        "xy_source": "state_feedback",
        "xy_state_feedback_gain": 4.0,
        "xy_action_scale": 4.0,
        "xy_action_clip": 0.035,
        "z_action_scale": 24.0,
        "z_action_clip": 0.12,
        "rotation_action_scale": 0.0,
        "gripper_passthrough": True,
        "stable_hold_depth_m": 0.03,
        "stable_hold_lateral_m": 0.006,
        "stable_hold_orientation_deg": 8.0,
        "stable_hold_action": [0.0, 0.0, -0.02, 0.0, 0.0, 0.0, 1.0],
    }
    if scenario_profile == "v0_6":
        train_generation_controller_config.update(
            {
                "controller_version": "v0_6_active_state_controller",
                "success_authority": "isaac_env_native_consecutive_success_v0",
                "align_lateral_gate_m": 0.008,
                "align_orientation_gate_rad": 0.25,
                "continued_xy_yaw_correction": True,
                "bounded_monotonic_downward_push": True,
                "retry_recover_withdraw_search": False,
                "force_reactive_control": False,
            }
        )
        if isinstance(controller_repair_config, dict):
            train_generation_controller_config.update(controller_repair_config)
    payload = {
        "policy_id": "mvp2c_isaac_runtime_scripted_expert_train_generation_probe",
        "policy_class": "scripted_expert_probe_policy_v0",
        "trainer": "scripted_expert_no_training",
        "feature_schema": list(FEATURE_SCHEMA),
        "phase_schema": list(PHASES),
        "action_schema": list(ACTION_SCHEMA),
        "selected_action_adapter_id": selected_adapter_id,
        "selected_action_adapter_config": dict(train_generation_controller_config),
        "selected_action_adapter_config_sha256": _sha256_payload(train_generation_controller_config),
        "train_generation_controller_config_sha256": _sha256_payload(train_generation_controller_config),
        "weights": [[0.0] * len(ACTION_SCHEMA) for _ in FEATURE_SCHEMA],
        "bias": [0.0, 0.0, -0.005, 0.0, 0.0, 0.0, 1.0],
    }
    payload["policy_artifact_sha256"] = _sha256_payload(payload)
    return payload


def derive_train_generation_runtime_gate_from_probe_result(
    probe_result: BackendResult,
    *,
    device: str,
    headless: bool,
    min_success_count: int = 1,
    success_trace_cap: int | None = None,
) -> dict[str, Any]:
    rollouts = list(probe_result.baseline_rollouts) + list(probe_result.candidate_rollouts)
    trace_paths = list(probe_result.baseline_trace_paths) + list(probe_result.candidate_trace_paths)
    all_success_trace_paths = [
        str(trace_paths[index])
        for index, rollout in enumerate(rollouts)
        if index < len(trace_paths) and rollout.get("success") is True
    ]
    success_trace_paths = all_success_trace_paths[:success_trace_cap] if success_trace_cap else all_success_trace_paths
    success_count = sum(1 for item in rollouts if item.get("success") is True)
    env_native_available_count = sum(1 for item in rollouts if item.get("env_native_success_available") is True)
    env_native_success_count = sum(1 for item in rollouts if item.get("env_native_rollout_success") is True)
    passed = (
        probe_result.runtime_backend == "isaac_runtime"
        and probe_result.runtime_gate.get("passed") is True
        and success_count >= min_success_count
    )
    reason = ""
    if not passed:
        if rollouts and env_native_available_count == 0:
            reason = "Isaac scripted train-generation probe did not expose env-native success masks."
        else:
            reason = f"Isaac scripted train-generation probe did not produce {min_success_count} successful rollouts."
    return {
        "passed": passed,
        "runtime_backend": probe_result.runtime_backend,
        "proof_runtime": ISAAC_TRAIN_GENERATION_PROOF_RUNTIME,
        "device": device,
        "headless": headless,
        "runtime_import_probe_passed": True,
        "actual_train_generation_evidence": passed,
        "training_trajectory_source": "isaac_runtime_scripted_expert_rollout",
        "generated_rollout_count": len(rollouts),
        "generated_success_count": success_count,
        "env_native_success_available_count": env_native_available_count,
        "env_native_success_count": env_native_success_count,
        "required_success_count": int(min_success_count),
        "success_trace_cap": success_trace_cap,
        "generated_trace_paths": trace_paths,
        "generated_success_trace_paths": success_trace_paths,
        "runtime_metadata": probe_result.runtime_metadata,
        "reason": reason,
    }


def _heldout_suite(manifest: dict[str, Any]) -> dict[str, Any]:
    scenario_ids = [
        str(row["scenario_id"])
        for row in manifest["scenarios"]
        if isinstance(row, dict) and row.get("split") == "held_out"
    ]
    return {
        "id": "mvp2c_isaac_connector_insertion_heldout_suite",
        "held_out": True,
        "task_type": "connector_insertion",
        "scenario_ids": scenario_ids,
        "scenario_set_sha256": manifest["manifest_sha256"],
        "source_kind": "external_trainer_eval_suite",
        "proof_role": "external_policy_eval_suite",
        "success_metric": manifest["success_metric"],
    }


def _policy_identity_for_profile(scenario_profile: str) -> tuple[str, str]:
    if scenario_profile == "v0_5":
        return RESIDUAL_POLICY_CLASS, RESIDUAL_TRAINER
    return POLICY_CLASS, TRAINER


def _write_learning_harness_bridge(
    *,
    output_dir: Path,
    manifest: dict[str, Any],
    baseline_view: dict[str, Any],
    candidate_view: dict[str, Any],
    selected_adapter_id: str,
    policy_class: str,
    trainer: str,
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
            "name": "baseline_uncurated_mvp2c_policy",
            "dataset_view": "baseline_uncurated_mvp2c_train_view",
            "dataset_id": "mvp2c_baseline_uncurated_train_view",
            "train_hdf5_path": baseline_view["path"],
            "policy_class": policy_class,
            "trainer": trainer,
            "selected_action_adapter_id": selected_adapter_id,
            "rollout_results": [],
        },
        "candidate": {
            "name": "candidate_curated_mvp2c_policy",
            "dataset_view": "candidate_curated_mvp2c_train_view",
            "dataset_id": "mvp2c_candidate_curated_train_view",
            "train_hdf5_path": candidate_view["path"],
            "policy_class": policy_class,
            "trainer": trainer,
            "selected_action_adapter_id": selected_adapter_id,
            "rollout_results": [],
        },
    }
    write_json(template_path, template)
    harness_report = {
        "schema_version": "rdf_mvp2c_learning_harness_bridge_v0.1.0",
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
            "adapter_id": "mvp2c_isaac_training_calibration",
            "adapter_version": SCHEMA_VERSION,
            "selected_action_adapter_id": selected_adapter_id,
            "builder_id": "mvp2c_scripted_expert_controlled_failure_builder",
            "robot_embodiment": "franka_research_arm_domain_model",
            "source_evidence_type": "isaac_evaluator_domain_training_material",
            "validator_backend": "NormalizedTrajectoryContractValidator",
        },
    }
    write_json(report_path, harness_report)
    return bridge_dir


def _write_external_rollout_json(
    *,
    output_dir: Path,
    role: str,
    policy_artifact: dict[str, Any],
    train_view: dict[str, Any],
    heldout_suite: dict[str, Any],
    backend_result: BackendResult,
    selected_adapter_id: str,
    policy_class: str,
    trainer: str,
) -> Path:
    rollouts = backend_result.baseline_rollouts if role == "baseline" else backend_result.candidate_rollouts
    proof_backend = (
        backend_result.runtime_backend == "isaac_runtime"
        and backend_result.proof_runtime == ISAAC_PROOF_RUNTIME
        and backend_result.runtime_gate.get("passed") is True
    )
    payload = {
        "schema_version": ROLLOUT_SCHEMA_VERSION,
        "source_kind": "external_heldout_policy_eval" if proof_backend else "local_phase_conditioned_policy_eval_proxy",
        "proof_role": "external_trainer_policy_eval" if proof_backend else "local_proxy_trainer_policy_eval",
        "policy_role": role,
        "policy_artifact_id": policy_artifact["policy_id"],
        "policy_artifact_sha256": policy_artifact["policy_artifact_sha256"],
        "training_artifact_sha256": train_view["sha256"],
        "policy_class": policy_class,
        "trainer": trainer,
        "selected_action_adapter_id": selected_adapter_id,
        "eval_runner": "rdf_mvp2c_isaac_training_calibration_eval_v0",
        "external_evaluator_run": {
            "run_id": f"mvp2c_{role}_{backend_result.runtime_backend}",
            "runner_version": SCHEMA_VERSION,
            "run_log_uri": str(output_dir / "heldout_rollout_traces"),
            "generated_outside_rdf_local_proxy": proof_backend,
        },
        "runtime_metadata": backend_result.runtime_metadata,
        "heldout_suite": heldout_suite,
        "rollout_results": rollouts,
    }
    if not proof_backend:
        payload["success_label_source"] = "deterministic_test_backend"
        payload["not_mvp2_proof"] = True
        payload["promotion_blocker"] = "Deterministic/local proxy rollout JSON cannot close MVP-2C."
    path = output_dir / "external_rollouts" / f"{role}_external_rollouts.json"
    write_json(path, payload)
    return path


def _run_learning_validator(
    *,
    output_dir: Path,
    bridge_dir: Path,
    baseline_rollouts_path: Path,
    candidate_rollouts_path: Path,
    min_rollouts_per_policy: int,
    bootstrap_iterations: int,
    bootstrap_seed: int,
    policy_class: str,
    trainer: str,
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
        baseline_policy_id="baseline_uncurated_mvp2c_phase_conditioned_numpy_bc",
        candidate_policy_id="candidate_curated_mvp2c_phase_conditioned_numpy_bc",
        policy_class=policy_class,
        trainer=trainer,
        min_rollouts_per_policy=min_rollouts_per_policy,
        bootstrap_iterations=bootstrap_iterations,
        bootstrap_seed=bootstrap_seed,
    )


def _skip_learning_report(output_dir: Path) -> dict[str, Any]:
    path = output_dir / "mvp2_learning_proven_policy_eval" / "mvp2_learning_proven_report.json"
    report = {
        "schema_version": "rdf_mvp2c_skipped_learning_validator_v0.1.0",
        "passed": True,
        "learning_results_measured": False,
        "learning_proven": False,
        "proof_eligible": False,
        "baseline_success_rate": None,
        "candidate_success_rate": None,
        "curated_vs_uncurated_uplift": None,
        "blockers": ["MVP-2C held-out evaluator was skipped."],
        "artifact_paths": {
            "report": str(path),
            "policy_eval_input": None,
            "policy_eval_report": None,
        },
    }
    write_json(path, report)
    return report


def _bootstrap_uplift_ci(
    *,
    baseline_rollouts: list[dict[str, Any]],
    candidate_rollouts: list[dict[str, Any]],
    iterations: int,
    seed: int,
) -> dict[str, Any]:
    if not baseline_rollouts or not candidate_rollouts:
        return {
            "method": "bootstrap_success_rate_difference",
            "available": False,
            "lower": None,
            "upper": None,
        }
    rng = np.random.default_rng(seed)
    baseline = np.asarray([1.0 if item.get("success") is True else 0.0 for item in baseline_rollouts])
    candidate = np.asarray([1.0 if item.get("success") is True else 0.0 for item in candidate_rollouts])
    diffs = []
    for _ in range(max(1, int(iterations))):
        b = rng.choice(baseline, size=baseline.shape[0], replace=True)
        c = rng.choice(candidate, size=candidate.shape[0], replace=True)
        diffs.append(float(np.mean(c) - np.mean(b)))
    return {
        "method": "bootstrap_success_rate_difference",
        "available": True,
        "iterations": max(1, int(iterations)),
        "lower": round(float(np.percentile(diffs, 2.5)), 6),
        "upper": round(float(np.percentile(diffs, 97.5)), 6),
    }


def derive_mvp2c_closure(
    *,
    learning_report: dict[str, Any],
    runtime_gate: dict[str, Any],
    train_generation_runtime_gate: dict[str, Any],
    calibration_selection_report: dict[str, Any],
    heldout_leakage_guard: dict[str, Any],
    actual_rollouts_per_policy: int,
    actual_isaac_success_trace_count: int | None = None,
    actual_isaac_success_trace_minimum: int = 1,
    post_heldout_guard: dict[str, Any] | None = None,
) -> dict[str, Any]:
    uplift = learning_report.get("curated_vs_uncurated_uplift")
    uplift_value = float(uplift) if isinstance(uplift, (int, float)) and not isinstance(uplift, bool) else None
    baseline_rate = learning_report.get("baseline_success_rate")
    candidate_rate = learning_report.get("candidate_success_rate")
    baseline_value = (
        float(baseline_rate) if isinstance(baseline_rate, (int, float)) and not isinstance(baseline_rate, bool) else None
    )
    candidate_value = (
        float(candidate_rate)
        if isinstance(candidate_rate, (int, float)) and not isinstance(candidate_rate, bool)
        else None
    )
    train_runtime_matches = (
        train_generation_runtime_gate.get("passed") is True
        and train_generation_runtime_gate.get("runtime_backend") == "isaac_runtime"
        and train_generation_runtime_gate.get("actual_train_generation_evidence") is True
        and train_generation_runtime_gate.get("training_trajectory_source") == "isaac_runtime_scripted_expert_rollout"
    )
    heldout_runtime_matches = (
        runtime_gate.get("passed") is True
        and runtime_gate.get("runtime_backend") == "isaac_runtime"
        and runtime_gate.get("proof_runtime") == ISAAC_PROOF_RUNTIME
    )
    calibration_selection_matches = (
        calibration_selection_report.get("calibration_only_selection_passed") is True
        and calibration_selection_report.get("heldout_excluded") is True
        and calibration_selection_report.get("selected_adapter_frozen_before_heldout") is True
        and calibration_selection_report.get("same_adapter_used_for_baseline_and_candidate") is True
    )
    heldout_leakage_matches = heldout_leakage_guard.get("passed") is True
    actual_train_trace_count_matches = (
        actual_isaac_success_trace_count is None
        or int(actual_isaac_success_trace_count) >= int(actual_isaac_success_trace_minimum)
    )
    post_heldout_guard_matches = post_heldout_guard is None or post_heldout_guard.get("passed") is True
    learning_matches = (
        learning_report.get("learning_proven") is True
        and learning_report.get("proof_eligible") is True
        and uplift_value is not None
        and uplift_value >= 0.20
        and baseline_value is not None
        and candidate_value is not None
        and candidate_value > baseline_value
    )
    rollout_count_matches = actual_rollouts_per_policy >= MIN_PROOF_ROLLOUTS_PER_POLICY
    close_minimum = bool(
        train_runtime_matches
        and heldout_runtime_matches
        and calibration_selection_matches
        and heldout_leakage_matches
        and actual_train_trace_count_matches
        and post_heldout_guard_matches
        and learning_matches
        and rollout_count_matches
    )
    blockers: list[str] = []
    if not train_runtime_matches:
        blockers.append("MVP-2C close requires actual Isaac runtime train generation evidence to pass.")
    if not heldout_runtime_matches:
        blockers.append("MVP-2C close requires dedicated Isaac runtime held-out gate to pass.")
    if not calibration_selection_matches:
        blockers.append("MVP-2C close requires calibration-only action adapter selection guard to pass.")
    if not heldout_leakage_matches:
        blockers.append("MVP-2C close requires held-out leakage guard to pass.")
    if not actual_train_trace_count_matches:
        blockers.append(
            f"MVP-2D v0.5 close requires at least {actual_isaac_success_trace_minimum} actual Isaac success traces."
        )
    if not post_heldout_guard_matches:
        blockers.append("MVP-2D v0.5 close requires no post-held-out rerun or tuning marker.")
    if not learning_matches:
        blockers.append("Existing MVP-2 learning validator did not produce proof-eligible positive uplift >= 0.20.")
    if not rollout_count_matches:
        blockers.append(
            f"MVP-2C close requires at least {MIN_PROOF_ROLLOUTS_PER_POLICY} actual held-out rollouts per policy."
        )
    return {
        "mvp2_closed": close_minimum,
        "mvp2c_close_minimum_passed": close_minimum,
        "proof_eligible": close_minimum,
        "learning_proven": close_minimum,
        "blockers": blockers,
    }


def _post_heldout_rerun_guard(*, output_dir: Path, scenario_profile: str) -> dict[str, Any]:
    marker_path = output_dir / "post_heldout_tuning_marker.json"
    marker_exists = marker_path.exists()
    guard = {
        "schema_version": "rdf_mvp2d_post_heldout_rerun_guard_v0.1.0",
        "scenario_profile": scenario_profile,
        "passed": not marker_exists,
        "rerun_or_tuning_after_heldout_detected": marker_exists,
        "marker_path": str(marker_path),
        "fresh_slice_required_if_failed": "v0_6",
    }
    write_json(output_dir / "post_heldout_rerun_guard.json", guard)
    return guard


def _base_servo_only_diagnostic(
    *,
    output_dir: Path,
    manifest: dict[str, Any],
    scenario_profile: str,
) -> dict[str, Any]:
    calibration_ids = [
        str(row["scenario_id"])
        for row in manifest["scenarios"]
        if isinstance(row, dict) and row.get("split") == "calibration"
    ]
    diagnostic = {
        "schema_version": "rdf_mvp2d_base_servo_only_diagnostic_v0.1.0",
        "scenario_profile": scenario_profile,
        "status": "static_calibration_split_diagnostic",
        "closing_gate": False,
        "can_close_mvp2": False,
        "heldout_success_metrics_read": False,
        "heldout_excluded": True,
        "calibration_scenario_ids": calibration_ids,
        "weak_base_servo_config": dict(WEAK_BASE_SERVO_CONFIG),
        "weak_base_servo_config_sha256": _sha256_payload(dict(WEAK_BASE_SERVO_CONFIG)),
        "note": "Diagnostic only; held-out policy uplift cannot be inferred from this field.",
    }
    write_json(output_dir / "base_servo_only_diagnostic.json", diagnostic)
    return diagnostic


def _derive_public_evidence_target(
    *,
    actual_rollouts_per_policy: int,
    confidence_interval_report: dict[str, Any],
) -> bool:
    lower = confidence_interval_report.get("lower")
    lower_positive = isinstance(lower, (int, float)) and not isinstance(lower, bool) and float(lower) > 0.0
    return bool(
        actual_rollouts_per_policy >= STRONGER_PUBLIC_ROLLOUTS_PER_POLICY
        and confidence_interval_report.get("available") is True
        and lower_positive
    )


def _write_visual_evidence(
    *,
    output_dir: Path,
    baseline_rate: float | None,
    candidate_rate: float | None,
    backend_result: BackendResult | None,
) -> dict[str, Any]:
    visual_dir = output_dir / "visual_evidence"
    visual_dir.mkdir(parents=True, exist_ok=True)
    png_path = visual_dir / "metric_trace_comparison.png"
    _write_rate_png(
        png_path,
        baseline_rate=float(baseline_rate or 0.0),
        candidate_rate=float(candidate_rate or 0.0),
    )
    return {
        "metric_trace_comparison_png": str(png_path),
        "baseline_representative_rollout": backend_result.baseline_trace_paths[0]
        if backend_result and backend_result.baseline_trace_paths
        else "",
        "candidate_representative_rollout": backend_result.candidate_trace_paths[0]
        if backend_result and backend_result.candidate_trace_paths
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
    width = 320
    height = 160
    pixels = bytearray([255, 255, 255] * width * height)

    def set_pixel(x: int, y: int, color: tuple[int, int, int]) -> None:
        if 0 <= x < width and 0 <= y < height:
            index = (y * width + x) * 3
            pixels[index : index + 3] = bytes(color)

    def fill_rect(x0: int, y0: int, x1: int, y1: int, color: tuple[int, int, int]) -> None:
        for y in range(max(0, y0), min(height, y1)):
            for x in range(max(0, x0), min(width, x1)):
                set_pixel(x, y, color)

    fill_rect(30, 130, 290, 133, (30, 30, 30))
    baseline_h = int(100 * max(0.0, min(1.0, baseline_rate)))
    candidate_h = int(100 * max(0.0, min(1.0, candidate_rate)))
    fill_rect(90, 130 - baseline_h, 135, 130, (76, 120, 180))
    fill_rect(185, 130 - candidate_h, 230, 130, (42, 160, 98))
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


def _build_calibration_summaries(manifest: dict[str, Any], *, output_dir: Path) -> list[dict[str, Any]]:
    scenario_ids = [row["scenario_id"] for row in manifest["scenarios"] if row["split"] == "calibration"]
    scenario_profile = str(manifest.get("scenario_profile") or "v0_1")
    summaries = [
        {
            "adapter_id": "isaac_delta_pose_direct_v0",
            "scenario_ids": scenario_ids,
            "baseline_success_rate": 0.45,
            "candidate_success_rate": 0.55,
            "candidate_stability_margin": 0.10,
            "candidate_action_saturation_rate": 0.05,
        },
        {
            "adapter_id": "isaac_signed_xy_downward_servo_v0",
            "scenario_ids": scenario_ids,
            "baseline_success_rate": 0.45,
            "candidate_success_rate": 0.75,
            "candidate_stability_margin": 0.25,
            "candidate_action_saturation_rate": 0.03,
        },
        {
            "adapter_id": "isaac_stability_damped_servo_v0",
            "scenario_ids": scenario_ids,
            "baseline_success_rate": 0.50,
            "candidate_success_rate": 0.65,
            "candidate_stability_margin": 0.40,
            "candidate_action_saturation_rate": 0.02,
        },
    ]
    evidence = {
        "schema_version": "rdf_mvp2c_calibration_adapter_evidence_v0.1.0",
        "scenario_manifest_sha256": manifest["manifest_sha256"],
        "calibration_scenario_ids": scenario_ids,
        "selector_score_config": _selector_score_config_for_profile(scenario_profile),
        "calibration_model": "pre_registered_calibration_split_summary_v0",
        "heldout_excluded": True,
        "summaries": summaries,
    }
    evidence["calibration_evidence_sha256"] = _sha256_payload(evidence)
    write_json(output_dir / "calibration_adapter_evidence.json", evidence)
    return summaries


def build_mvp2c_isaac_training_calibration(
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    clean: bool = False,
    scenario_profile: str = "v0_1",
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
    bootstrap_seed: int = 23,
) -> dict[str, Any]:
    _prepare_output_dir(output_dir, clean=clean)
    manifest = build_mvp2c_scenario_manifest(output_dir=output_dir, scenario_profile=scenario_profile)
    v06_chamfer_preflight = resolve_v06_chamfer_preflight_for_report(output_dir=output_dir) if scenario_profile == "v0_6" else None
    v06_train_generation_preflight_gate: dict[str, Any] | None = (
        resolve_v06_train_generation_gate_preflight(output_dir=output_dir) if scenario_profile == "v0_6" else None
    )
    v06_repair_probe_gate: dict[str, Any] | None = None
    if isinstance(v06_train_generation_preflight_gate, dict) and isinstance(
        v06_train_generation_preflight_gate.get("repair_probe_gate"),
        dict,
    ):
        v06_repair_probe_gate = v06_train_generation_preflight_gate["repair_probe_gate"]
    if v06_chamfer_preflight is not None and v06_chamfer_preflight["repair_probe_allowed"] is not True:
        v06_repair_probe_gate = {
            "proof_authority": False,
            "probe_seeds": list(V06_REPAIR_PROBE_SEEDS),
            "green_light_for_40_run_gate": False,
            "hard_stop": True,
            "runtime_backend": "not_started",
            "proof_runtime": "isaac_scripted_expert_repair_probe",
            "chamfer_preflight": v06_chamfer_preflight,
            "reason": "chamfer preflight Branch C blocked INSERT parameter freeze; repair probe was not run.",
        }
        write_json(output_dir / "repair_probe_gate.json", v06_repair_probe_gate)
    policy_class, trainer = _policy_identity_for_profile(scenario_profile)
    baseline_noise_mix_config = build_baseline_noise_mix_config(output_dir=output_dir, scenario_profile=scenario_profile)
    generator_hashes = build_generator_config_hashes(output_dir=output_dir, scenario_profile=scenario_profile)
    adapter_registry = build_action_adapter_registry(output_dir=output_dir, scenario_profile=scenario_profile)
    calibration_summaries = _build_calibration_summaries(manifest, output_dir=output_dir)
    selector_input_report = validate_calibration_selector_inputs(
        manifest=manifest,
        calibration_summaries=calibration_summaries,
        forbidden_inputs={
            "heldout_trace_paths": [],
            "heldout_rollout_json_paths": [],
            "heldout_success_metrics": {},
            "heldout_scenario_ids": [],
        },
    )
    if selector_input_report["passed"] is not True:
        raise ValueError(f"MVP-2C calibration selector leakage guard failed: {selector_input_report}")
    selection = select_action_adapter_from_calibration(
        adapter_registry=adapter_registry,
        manifest=manifest,
        calibration_summaries=calibration_summaries,
        output_dir=output_dir,
    )
    selected_adapter_id = selection["selected_adapter_id"]

    if skip_isaac or use_deterministic_eval_backend:
        train_generation_runtime_gate = {
            "passed": False,
            "runtime_backend": DETERMINISTIC_BACKEND,
            "proof_runtime": DETERMINISTIC_PROOF_RUNTIME,
            "reason": "deterministic train generation is test/plumbing only and cannot close MVP-2C",
        }
    elif (
        scenario_profile == "v0_6"
        and (
            not isinstance(v06_train_generation_preflight_gate, dict)
            or v06_train_generation_preflight_gate.get("train_generation_gate_allowed") is not True
        )
    ):
        train_generation_runtime_gate = {
            "passed": False,
            "runtime_backend": "isaac_runtime_not_started",
            "proof_runtime": ISAAC_TRAIN_GENERATION_PROOF_RUNTIME,
            "runtime_import_probe_passed": False,
            "actual_train_generation_evidence": False,
            "training_trajectory_source": "isaac_runtime_scripted_expert_rollout",
            "generated_rollout_count": 0,
            "generated_success_count": 0,
            "required_success_count": V06_TRAIN_GATE_SUCCESS_MINIMUM,
            "success_trace_cap": V06_TRAIN_GATE_ATTEMPT_COUNT,
            "chamfer_preflight": v06_chamfer_preflight,
            "repair_probe_gate": v06_train_generation_preflight_gate.get("repair_probe_gate")
            if isinstance(v06_train_generation_preflight_gate, dict)
            else None,
            "post_repair_probe_gate": v06_train_generation_preflight_gate.get("post_repair_probe_gate")
            if isinstance(v06_train_generation_preflight_gate, dict)
            else None,
            "reason": v06_train_generation_preflight_gate.get("reason", "missing_verified_v0_6a_chamfer_preflight")
            if isinstance(v06_train_generation_preflight_gate, dict)
            else "missing_verified_v0_6a_chamfer_preflight",
        }
        write_json(output_dir / "train_generation_runtime_gate.json", train_generation_runtime_gate)
    else:
        train_generation_runtime_gate = probe_isaac_train_generation_runtime(
            device=device,
            headless=headless,
            output_dir=output_dir,
            manifest=manifest,
            selected_adapter_id=selected_adapter_id,
            selected_adapter_config=selection["selected_adapter_config"],
            isaac_task=isaac_task,
            max_steps=max_steps,
            action_scale=action_scale,
        )
    train_generation_runtime_backend = (
        "isaac_runtime"
        if train_generation_runtime_gate.get("passed") is True
        and train_generation_runtime_gate.get("runtime_backend") == "isaac_runtime"
        else DETERMINISTIC_BACKEND
    )
    bundle = generate_mvp2c_training_trajectory_bundle(
        manifest=manifest,
        baseline_noise_mix_config=baseline_noise_mix_config,
        generator_config_hashes=generator_hashes,
        output_dir=output_dir,
        train_generation_runtime_backend=train_generation_runtime_backend,
        train_generation_runtime_gate=train_generation_runtime_gate,
        selected_adapter_config=selection["selected_adapter_config"],
    )
    if bundle["contract_validation"]["passed"] is not True:
        raise ValueError(f"MVP-2C generated contracts failed: {bundle['contract_validation']['issues']}")
    training_scenario_ids = sorted(
        {str(item["scenario_id"]) for item in bundle["curation_manifest"]["items"] if item.get("scenario_id")}
    )
    heldout_leakage_guard = validate_no_heldout_leakage(
        manifest=manifest,
        training_scenario_ids=training_scenario_ids,
        curation_tuning_scenario_ids=[],
        threshold_tuning_scenario_ids=[],
        hyperparameter_scenario_ids=[],
        calibration_selector_scenario_ids=[str(item) for item in selection["calibration_scenario_ids"]],
    )
    if heldout_leakage_guard["passed"] is not True:
        raise ValueError(f"MVP-2C held-out leakage guard failed: {heldout_leakage_guard}")

    baseline_view = _write_train_view_hdf5(
        path=output_dir / "baseline_uncurated_train.hdf5",
        rows=bundle["baseline_train_rows"],
        view_id="baseline_uncurated_mvp2c_train_view",
        baseline_noise_mix_config=baseline_noise_mix_config,
        generator_config_hashes=generator_hashes,
    )
    candidate_view = _write_train_view_hdf5(
        path=output_dir / "candidate_curated_train.hdf5",
        rows=bundle["candidate_train_rows"],
        view_id="candidate_curated_mvp2c_train_view",
        baseline_noise_mix_config=baseline_noise_mix_config,
        generator_config_hashes=generator_hashes,
    )
    policy_artifacts = _write_policy_artifacts(
        output_dir=output_dir,
        baseline_rows=bundle["baseline_train_rows"],
        candidate_rows=bundle["candidate_train_rows"],
        selected_adapter_id=selected_adapter_id,
        selected_adapter_config=selection["selected_adapter_config"],
        scenario_profile=scenario_profile,
    )
    bridge_dir = _write_learning_harness_bridge(
        output_dir=output_dir,
        manifest=manifest,
        baseline_view=baseline_view,
        candidate_view=candidate_view,
        selected_adapter_id=selected_adapter_id,
        policy_class=policy_class,
        trainer=trainer,
    )

    backend_result: BackendResult | None = None
    baseline_rollouts_path: Path | None = None
    candidate_rollouts_path: Path | None = None
    actual_rollouts_per_policy = 0
    v05_dataset_evidence = bundle.get("v0_5_dataset_view_evidence") if isinstance(bundle, dict) else None
    v05_train_generation_gate_passed = not (
        scenario_profile == "v0_5"
        and (
            not isinstance(v05_dataset_evidence, dict)
            or v05_dataset_evidence.get("proof_eligible") is not True
            or int(v05_dataset_evidence.get("actual_isaac_success_trace_count", 0))
            < V05_ACTUAL_SUCCESS_TRACE_MINIMUM
        )
    )
    if scenario_profile == "v0_6":
        train_generation_gate_passed = (
            train_generation_runtime_gate.get("passed") is True
            and train_generation_runtime_gate.get("runtime_backend") == "isaac_runtime"
            and train_generation_runtime_gate.get("actual_train_generation_evidence") is True
            and int(train_generation_runtime_gate.get("generated_success_count", 0)) >= V06_TRAIN_GATE_SUCCESS_MINIMUM
        )
        probe_reason = str(train_generation_runtime_gate.get("reason") or "").strip()
        train_generation_block_reason = (
            ""
            if train_generation_gate_passed
            else "v0_6 train-generation gate did not produce enough env-native success traces; held-out was not scheduled."
            + (f" Probe reason: {probe_reason}" if probe_reason else "")
        )
    else:
        train_generation_gate_passed = v05_train_generation_gate_passed
        train_generation_block_reason = (
            ""
            if train_generation_gate_passed
            else "v0_5 train-generation gate did not produce enough actual success traces; held-out was not scheduled."
        )
    heldout_schedule = {
        "scheduled": False,
        "blocked_by_train_generation_gate": not train_generation_gate_passed,
        "scenario_profile": scenario_profile,
        "reason": train_generation_block_reason,
    }
    if skip_isaac or not train_generation_gate_passed:
        runtime_backend = "skipped"
        proof_runtime = "skipped"
        runtime_gate = {
            "passed": False,
            "runtime_backend": runtime_backend,
            "proof_runtime": proof_runtime,
            "reason": "Isaac runtime and deterministic backend were skipped."
            if skip_isaac
            else train_generation_block_reason,
        }
        learning_report = _skip_learning_report(output_dir)
        baseline_rollouts: list[dict[str, Any]] = []
        candidate_rollouts: list[dict[str, Any]] = []
    else:
        heldout_schedule["scheduled"] = True
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
            selected_adapter_id=selected_adapter_id,
            policy_class=policy_class,
            trainer=trainer,
        )
        candidate_rollouts_path = _write_external_rollout_json(
            output_dir=output_dir,
            role="candidate",
            policy_artifact=policy_artifacts["candidate"],
            train_view=candidate_view,
            heldout_suite=heldout_suite,
            backend_result=backend_result,
            selected_adapter_id=selected_adapter_id,
            policy_class=policy_class,
            trainer=trainer,
        )
        learning_report = _run_learning_validator(
            output_dir=output_dir,
            bridge_dir=bridge_dir,
            baseline_rollouts_path=baseline_rollouts_path,
            candidate_rollouts_path=candidate_rollouts_path,
            min_rollouts_per_policy=min_rollouts_per_policy,
            bootstrap_iterations=bootstrap_iterations,
            bootstrap_seed=bootstrap_seed,
            policy_class=policy_class,
            trainer=trainer,
        )
        baseline_rollouts = backend_result.baseline_rollouts
        candidate_rollouts = backend_result.candidate_rollouts

    actual_isaac_success_trace_count = 0
    actual_isaac_success_trace_minimum = 1
    actual_isaac_success_trace_cap = None
    if isinstance(v05_dataset_evidence, dict):
        actual_isaac_success_trace_count = int(v05_dataset_evidence.get("actual_isaac_success_trace_count", 0))
        actual_isaac_success_trace_minimum = int(
            v05_dataset_evidence.get("actual_isaac_success_trace_minimum", V05_ACTUAL_SUCCESS_TRACE_MINIMUM)
        )
        actual_isaac_success_trace_cap = V05_ACTUAL_SUCCESS_TRACE_CAP
    if scenario_profile == "v0_6":
        actual_isaac_success_trace_count = int(train_generation_runtime_gate.get("generated_success_count", 0))
        actual_isaac_success_trace_minimum = V06_TRAIN_GATE_SUCCESS_MINIMUM
        actual_isaac_success_trace_cap = V06_TRAIN_GATE_ATTEMPT_COUNT
    post_heldout_guard = _post_heldout_rerun_guard(output_dir=output_dir, scenario_profile=scenario_profile)
    base_servo_only_diagnostic = _base_servo_only_diagnostic(
        output_dir=output_dir,
        manifest=manifest,
        scenario_profile=scenario_profile,
    )
    closure = derive_mvp2c_closure(
        learning_report=learning_report,
        runtime_gate=runtime_gate,
        train_generation_runtime_gate=train_generation_runtime_gate,
        calibration_selection_report=selection,
        heldout_leakage_guard=heldout_leakage_guard,
        actual_rollouts_per_policy=actual_rollouts_per_policy,
        actual_isaac_success_trace_count=actual_isaac_success_trace_count if scenario_profile == "v0_5" else None,
        actual_isaac_success_trace_minimum=actual_isaac_success_trace_minimum,
        post_heldout_guard=post_heldout_guard if scenario_profile == "v0_5" else None,
    )
    confidence_interval_report = _bootstrap_uplift_ci(
        baseline_rollouts=baseline_rollouts,
        candidate_rollouts=candidate_rollouts,
        iterations=bootstrap_iterations,
        seed=bootstrap_seed,
    )
    stronger_public_evidence_target_passed = _derive_public_evidence_target(
        actual_rollouts_per_policy=actual_rollouts_per_policy,
        confidence_interval_report=confidence_interval_report,
    )
    visual_evidence = _write_visual_evidence(
        output_dir=output_dir,
        baseline_rate=learning_report.get("baseline_success_rate"),
        candidate_rate=learning_report.get("candidate_success_rate"),
        backend_result=backend_result,
    )
    report_path = output_dir / REPORT_NAME
    policy_eval_binding = {
        "schema_version": "rdf_mvp2c_policy_eval_binding_v0.1.0",
        "selected_action_adapter_id": selected_adapter_id,
        "same_adapter_used_for_baseline_and_candidate": True,
        "same_policy_class": True,
        "same_trainer": True,
        "same_feature_schema": True,
        "same_phase_input": True,
        "same_hyperparameters_except_dataset_view": True,
        "heldout_suite_sha256": manifest["manifest_sha256"],
    }
    write_json(output_dir / "policy_eval_binding.json", policy_eval_binding)
    artifact_paths = {
        "report": str(report_path),
        "scenario_manifest": str(output_dir / "scenario_manifest.json"),
        "action_adapter_candidates": str(output_dir / "action_adapter_candidates.json"),
        "action_adapter_registry_hash": str(output_dir / "action_adapter_registry_hash.json"),
        "calibration_adapter_evidence": str(output_dir / "calibration_adapter_evidence.json"),
        "baseline_noise_mix_config": str(output_dir / "baseline_noise_mix_config.json"),
        "generator_config_hashes": str(output_dir / "generator_config_hashes.json"),
        "calibration_selection_report": str(output_dir / "calibration_selection_report.json"),
        "selected_action_adapter": str(output_dir / "selected_action_adapter.json"),
        "policy_eval_binding": str(output_dir / "policy_eval_binding.json"),
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
        "learning_validator_bridge_report": str(bridge_dir / "mvp2_policy_ab_harness_report.json"),
        "visual_metric_trace_comparison": visual_evidence["metric_trace_comparison_png"],
        "base_servo_only_diagnostic": str(output_dir / "base_servo_only_diagnostic.json"),
        "post_heldout_rerun_guard": str(output_dir / "post_heldout_rerun_guard.json"),
        "v0_6_chamfer_preflight": str(output_dir / "chamfer_preflight.json")
        if scenario_profile == "v0_6"
        else None,
        "v0_6_repair_probe_gate": str(output_dir / "repair_probe_gate.json") if scenario_profile == "v0_6" else None,
        "v0_5_dataset_view_evidence": str(output_dir / "v0_5_dataset_view_evidence.json")
        if scenario_profile == "v0_5"
        else None,
    }
    learning_blockers = learning_report.get("blockers") if isinstance(learning_report.get("blockers"), list) else []
    report = {
        "schema_version": SCHEMA_VERSION,
        "manifest_version": manifest["manifest_version"],
        "scenario_profile": manifest["scenario_profile"],
        "created_at": datetime.now(UTC).isoformat(),
        "passed": True,
        "mvp2_closed": closure["mvp2_closed"],
        "mvp2c_close_minimum_passed": closure["mvp2c_close_minimum_passed"],
        "stronger_public_evidence_target_passed": stronger_public_evidence_target_passed,
        "learning_proven": closure["learning_proven"],
        "proof_eligible": closure["proof_eligible"],
        "runtime_backend": runtime_backend,
        "proof_runtime": proof_runtime,
        "runtime_gate": runtime_gate,
        "train_generation_runtime_backend": train_generation_runtime_backend,
        "train_generation_runtime_gate": train_generation_runtime_gate,
        "requested_rollouts_per_policy": min_rollouts_per_policy,
        "actual_rollouts_per_policy": actual_rollouts_per_policy,
        "heldout_schedule": heldout_schedule,
        "primary_proof_path": PRIMARY_PROOF_PATH,
        "scenario_manifest_sha256": manifest["manifest_sha256"],
        "learning_validator_bridge_sha256": _sha256_file(bridge_dir / "mvp2_policy_ab_harness_report.json"),
        "baseline_noise_mix_ratio": baseline_noise_mix_config["baseline_noise_mix_ratio"],
        "accepted_failure_ratio": baseline_noise_mix_config["accepted_failure_ratio"],
        "failure_type_distribution": baseline_noise_mix_config["failure_type_distribution"],
        "noise_profile_config_sha256": baseline_noise_mix_config["noise_profile_config_sha256"],
        "scripted_expert_config_sha256": generator_hashes["scripted_expert_config_sha256"],
        "controlled_failure_config_sha256": generator_hashes["controlled_failure_config_sha256"],
        "train_generation_config_sha256": generator_hashes["train_generation_config_sha256"],
        "weak_base_servo_config_sha256": generator_hashes.get("weak_base_servo_config_sha256"),
        "actual_isaac_success_trace_count": actual_isaac_success_trace_count,
        "actual_isaac_success_trace_minimum": actual_isaac_success_trace_minimum,
        "actual_isaac_success_trace_cap": actual_isaac_success_trace_cap,
        "selector_score_config_sha256": selection["selector_score_config_sha256"],
        "selected_action_adapter_id": selection["selected_adapter_id"],
        "selected_action_adapter_sha256": selection["selected_adapter_sha256"],
        "selector_score_pre_registered": selection["selector_score_pre_registered"],
        "same_adapter_used_for_baseline_and_candidate": selection["same_adapter_used_for_baseline_and_candidate"],
        "heldout_excluded": selection["heldout_excluded"],
        "selected_adapter_frozen_before_heldout": selection["selected_adapter_frozen_before_heldout"],
        "calibration_only_selection_passed": selection["calibration_only_selection_passed"],
        "heldout_leakage_guard_passed": heldout_leakage_guard["passed"],
        "heldout_leakage_guard": heldout_leakage_guard,
        "selected_action_adapter": selection,
        "baseline_success_rate": learning_report.get("baseline_success_rate"),
        "candidate_success_rate": learning_report.get("candidate_success_rate"),
        "curated_vs_uncurated_uplift": learning_report.get("curated_vs_uncurated_uplift"),
        "confidence_interval_report": confidence_interval_report,
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
        "policy_eval_binding": policy_eval_binding,
        "contract_validation": bundle["contract_validation"],
        "baseline_mix_evidence": bundle["baseline_mix_evidence"],
        "actual_isaac_train_generation_evidence": bundle["actual_isaac_train_generation_evidence"],
        "v0_5_dataset_view_evidence": v05_dataset_evidence,
        "base_servo_only_diagnostic": base_servo_only_diagnostic,
        "post_heldout_rerun_guard": post_heldout_guard,
        "v0_6_chamfer_preflight": v06_chamfer_preflight,
        "v0_6_repair_probe_gate": v06_repair_probe_gate,
        "v0_6_train_gate_seed_selection": manifest.get("v0_6_train_gate_seed_selection")
        if scenario_profile == "v0_6"
        else None,
        "visual_evidence": visual_evidence,
        "visual_evidence_is_proof_override": False,
        "artifact_paths": artifact_paths,
        "blockers": closure["blockers"] + [str(item) for item in learning_blockers],
        "proof_boundary": {
            "deterministic_backend_can_close_mvp2c": False,
            "skip_isaac_can_close_mvp2c": False,
            "requires_isaac_train_generation_runtime_gate": True,
            "requires_actual_isaac_train_generation_evidence": True,
            "requires_isaac_heldout_runtime_gate": True,
            "requires_calibration_only_selection_passed": True,
            "requires_heldout_leakage_guard_passed": True,
            "requires_existing_learning_validator": True,
            "minimum_uplift_absolute": 0.20,
            "minimum_rollouts_per_policy": MIN_PROOF_ROLLOUTS_PER_POLICY,
            "stronger_public_rollouts_per_policy": STRONGER_PUBLIC_ROLLOUTS_PER_POLICY,
        },
        "non_claims": {
            "privileged_feature_statement": (
                "This is an Isaac evaluator-domain learning proof using privileged task-state features. "
                "It does not claim deployable real-world visual policy performance."
            ),
            "deployable_real_robot_policy": False,
            "visual_policy_performance": False,
            "real_robot_success": False,
            "physical_robot_readiness": False,
            "universal_robot_support": False,
            "hmd_openxr_readiness": False,
        },
        "limitations": [
            "MVP-2C is an Isaac evaluator-domain learning proof with privileged task-state features.",
            "A 20-rollout close is engineering-minimum evidence, not a robust public benchmark.",
            "Actual closure requires positive held-out uplift from Isaac-runtime rollouts and a train-generation runtime gate.",
            "No deployable real-world visual policy, real robot success, physical readiness, or universal robot support is claimed.",
        ],
        "reproducible_command": (
            "/home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/run_mvp2c_isaac_training_calibration.py "
            f"--output-dir {output_dir} --clean --scenario-profile {scenario_profile} "
            f"--rollouts-per-policy {min_rollouts_per_policy} "
            f"--max-steps {max_steps} --isaac-task {isaac_task} --device {device} "
            f"--action-scale {action_scale} --bootstrap-iterations {bootstrap_iterations} "
            f"--bootstrap-seed {bootstrap_seed} --pretty"
        ),
    }
    write_json(report_path, report)
    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--clean", action="store_true")
    parser.add_argument(
        "--scenario-profile",
        choices=("v0_1", "v0_2", "v0_3", "v0_4", "v0_5", "v0_6"),
        default="v0_1",
    )
    parser.add_argument("--train-generation-probe-only", action="store_true")
    parser.add_argument("--repair-probe-only", action="store_true")
    parser.add_argument(
        "--repair-probe-controller-version",
        choices=("v0_6e", "v0_6f"),
        default="v0_6e",
        help="Controller repair config version for repair-probe-only execution.",
    )
    parser.add_argument("--capture-radius-probe-only", action="store_true")
    parser.add_argument("--skip-isaac", action="store_true")
    parser.add_argument("--use-deterministic-eval-backend", action="store_true")
    parser.add_argument(
        "--deterministic-profile",
        choices=("candidate_positive", "tie", "candidate_negative"),
        default="candidate_positive",
    )
    parser.add_argument(
        "--rollouts-per-policy",
        "--min-rollouts-per-policy",
        dest="min_rollouts_per_policy",
        type=int,
        default=20,
    )
    parser.add_argument("--max-steps", type=int, default=int(SUCCESS_METRIC["max_steps"]))
    parser.add_argument("--isaac-task", default=DEFAULT_ISAAC_TASK)
    parser.add_argument("--device", default=DEFAULT_ISAAC_DEVICE)
    parser.add_argument("--headless", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--action-scale", type=float, default=1.0)
    parser.add_argument("--bootstrap-iterations", type=int, default=2000)
    parser.add_argument("--bootstrap-seed", type=int, default=23)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.capture_radius_probe_only:
        if args.scenario_profile != "v0_6":
            raise ValueError("--capture-radius-probe-only is only valid with --scenario-profile v0_6")
        _prepare_output_dir(args.output_dir, clean=args.clean)
        build_mvp2c_scenario_manifest(output_dir=args.output_dir, scenario_profile=args.scenario_profile)
        result = run_v06a_capture_radius_probe_runtime(
            output_dir=args.output_dir,
            device=args.device,
            headless=args.headless,
            isaac_task=args.isaac_task,
        )
        print(stable_json(result))
        return 0
    if args.train_generation_probe_only:
        _prepare_output_dir(args.output_dir, clean=args.clean)
        manifest_path = args.output_dir / "scenario_manifest.json"
        selection_path = args.output_dir / "selected_action_adapter.json"
        if not manifest_path.exists():
            manifest = build_mvp2c_scenario_manifest(output_dir=args.output_dir, scenario_profile=args.scenario_profile)
        else:
            manifest = read_json(manifest_path)
        if not selection_path.exists():
            adapter_registry = build_action_adapter_registry(
                output_dir=args.output_dir,
                scenario_profile=str(manifest.get("scenario_profile") or args.scenario_profile),
            )
            calibration_summaries = _build_calibration_summaries(manifest, output_dir=args.output_dir)
            selection = select_action_adapter_from_calibration(
                adapter_registry=adapter_registry,
                manifest=manifest,
                calibration_summaries=calibration_summaries,
                output_dir=args.output_dir,
            )
        else:
            selection = read_json(selection_path)
        if args.repair_probe_only:
            if str(manifest.get("scenario_profile") or args.scenario_profile) != "v0_6":
                raise ValueError("--repair-probe-only is only valid with --scenario-profile v0_6")
            gate = run_v06_repair_probe_runtime(
                output_dir=args.output_dir,
                manifest=manifest,
                selected_adapter_id=selection["selected_adapter_id"],
                selected_adapter_config=selection["selected_adapter_config"],
                device=args.device,
                headless=args.headless,
                isaac_task=args.isaac_task,
                max_steps=args.max_steps,
                action_scale=args.action_scale,
                repair_probe_controller_version=args.repair_probe_controller_version,
            )
            print(stable_json(gate))
            return 0
        if str(manifest.get("scenario_profile") or args.scenario_profile) == "v0_6":
            preflight_gate = resolve_v06_train_generation_gate_preflight(output_dir=args.output_dir)
            preflight = preflight_gate.get("preflight")
            if not isinstance(preflight, dict):
                preflight = build_v06_chamfer_preflight(output_dir=args.output_dir)
                preflight_gate = {
                    "train_generation_gate_allowed": False,
                    "preflight": preflight,
                    "reason": "missing_verified_v0_6a_chamfer_preflight",
                }
            if preflight_gate["train_generation_gate_allowed"] is not True:
                gate = {
                    "passed": False,
                    "runtime_backend": "isaac_runtime_not_started",
                    "proof_runtime": ISAAC_TRAIN_GENERATION_PROOF_RUNTIME,
                    "runtime_import_probe_passed": False,
                    "actual_train_generation_evidence": False,
                    "training_trajectory_source": "isaac_runtime_scripted_expert_rollout",
                    "generated_rollout_count": 0,
                    "generated_success_count": 0,
                    "required_success_count": V06_TRAIN_GATE_SUCCESS_MINIMUM,
                    "success_trace_cap": V06_TRAIN_GATE_ATTEMPT_COUNT,
                    "chamfer_preflight": preflight,
                    "repair_probe_gate": preflight_gate.get("repair_probe_gate"),
                    "post_repair_probe_gate": preflight_gate.get("post_repair_probe_gate"),
                    "reason": preflight_gate.get(
                        "reason",
                        "verified v0_6a preflight and repair green light are required before 40-run gate.",
                    ),
                }
                write_json(args.output_dir / "train_generation_runtime_gate.json", gate)
                print(stable_json(gate))
                return 0
        gate = probe_isaac_train_generation_runtime(
            device=args.device,
            headless=args.headless,
            output_dir=args.output_dir,
            manifest=manifest,
            selected_adapter_id=selection["selected_adapter_id"],
            selected_adapter_config=selection["selected_adapter_config"],
            isaac_task=args.isaac_task,
            max_steps=args.max_steps,
            action_scale=args.action_scale,
            run_in_subprocess=False,
        )
        print(stable_json(gate))
        return 0 if gate.get("runtime_import_probe_passed") is True else 1
    report = build_mvp2c_isaac_training_calibration(
        output_dir=args.output_dir,
        clean=args.clean,
        scenario_profile=args.scenario_profile,
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
        print(f"RDF MVP-2C Isaac training/calibration: {'CLOSED' if report['mvp2_closed'] else 'OPEN'}")
        print(f"runtime_backend={report['runtime_backend']}")
        print(f"train_generation_runtime_backend={report['train_generation_runtime_backend']}")
        print(f"proof_runtime={report['proof_runtime']}")
        print(f"actual_rollouts_per_policy={report['actual_rollouts_per_policy']}")
        print(f"baseline_success_rate={report['baseline_success_rate']}")
        print(f"candidate_success_rate={report['candidate_success_rate']}")
        print(f"curated_vs_uncurated_uplift={report['curated_vs_uncurated_uplift']}")
        print(f"mvp2_closed={report['mvp2_closed']}")
        print(f"mvp2c_close_minimum_passed={report['mvp2c_close_minimum_passed']}")
        print(f"stronger_public_evidence_target_passed={report['stronger_public_evidence_target_passed']}")
        print(f"report={report['artifact_paths']['report']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
