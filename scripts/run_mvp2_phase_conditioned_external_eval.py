#!/usr/bin/env python3
"""Generate MVP-2 phase-conditioned local held-out proxy evidence.

This script produces baseline/candidate held-out proxy rollout JSON from the
selected MVP-2A phase-conditioned policy/trainer contract, then sends those JSON
files through the existing MVP-2 learning-proven wrapper to prove the wrapper
does not promote local proxy evidence into MVP-2 Closed evidence.

It does not run live robots, Isaac, ROS2/DDS, or HMD/OpenXR collection.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import json
import math
from pathlib import Path
import shutil
import sys
from typing import Any

import h5py


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
API_ROOT = ROOT / "apps" / "api"
for path in (SCRIPT_DIR, API_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from run_mvp1plus_embodiment_proof import DEFAULT_OUTPUT_DIR as DEFAULT_MVP1PLUS_OUTPUT_DIR  # noqa: E402
from run_mvp2_learning_proven_policy_eval import build_mvp2_learning_proven_policy_eval  # noqa: E402
from run_mvp2_ur_policy_ab_harness import (  # noqa: E402
    DEFAULT_OUTPUT_DIR as DEFAULT_HARNESS_OUTPUT_DIR,
    MVP2A_SELECTED_POLICY_CLASS,
    MVP2A_SELECTED_TRAINER,
    build_mvp2_ur_policy_ab_harness,
)


SCHEMA_VERSION = "rdf_mvp2_phase_conditioned_local_eval_proxy_v0.1.0"
ROLLOUT_SCHEMA_VERSION = "rdf_mvp2_phase_conditioned_local_rollout_proxy_v0.1.0"
DEFAULT_OUTPUT_DIR = ROOT / "storage" / "mvp2_phase_conditioned_local_eval_proxy"
REPORT_NAME = "mvp2_phase_conditioned_local_eval_proxy_report.json"
EVAL_RUNNER = "rdf_phase_conditioned_task_state_heldout_eval_v0"
PHASE_CONDITIONED_LOCAL_PROXY_KIND = "local_phase_conditioned_policy_eval_proxy"
HELDOUT_SUITE_ID = "local_ur_phase_conditioned_heldout_policy_eval_proxy_suite"
REQUIRED_PHASES = ("APPROACH", "CONTACT", "INSERT", "SEAT")
PHASE_ALIASES = {
    "APPROACH_OR_CONTACT_FAILURE": "CONTACT",
}


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
        raise ValueError(f"refusing unsafe MVP-2 external eval output path: {output_dir}")
    if clean and output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)


def _decode(value: Any) -> Any:
    if isinstance(value, bytes):
        return value.decode("utf-8")
    if hasattr(value, "tobytes") and value.__class__.__name__ == "bytes_":
        return value.tobytes().decode("utf-8")
    return value


def _json_rows(dataset: h5py.Dataset) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for value in dataset[()]:
        decoded = _decode(value)
        try:
            item = json.loads(decoded)
        except (TypeError, json.JSONDecodeError):
            item = {}
        rows.append(item if isinstance(item, dict) else {})
    return rows


def _numeric_rows(dataset: h5py.Dataset) -> list[list[float]]:
    rows: list[list[float]] = []
    for row in dataset[()]:
        values: list[float] = []
        for value in row:
            number = float(value)
            if math.isfinite(number):
                values.append(number)
        rows.append(values)
    return rows


def _episode_ids(h5: h5py.File) -> list[str]:
    dataset = h5.get("episodes/episode_ids")
    if isinstance(dataset, h5py.Dataset):
        return [str(_decode(value)) for value in dataset[()]]
    episodes = h5.get("episodes")
    if isinstance(episodes, h5py.Group):
        return sorted(key for key, value in episodes.items() if isinstance(value, h5py.Group))
    return []


def _normal_phase(raw_phase: Any) -> str | None:
    if not isinstance(raw_phase, str) or not raw_phase:
        return None
    phase = raw_phase.upper()
    return PHASE_ALIASES.get(phase, phase)


def _task_state_depth(task_state: Any) -> float | None:
    if not isinstance(task_state, dict):
        return None
    value = task_state.get("insertion_depth")
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _sha12(payload: dict[str, Any]) -> str:
    return hashlib.sha256(stable_json(payload).encode("utf-8")).hexdigest()[:12]


def _load_policy_material(*, hdf5_path: Path, dataset_view: str) -> dict[str, Any]:
    if not hdf5_path.exists():
        raise ValueError(f"{dataset_view} HDF5 does not exist: {hdf5_path}")

    phases: list[str] = []
    phase_order: list[str] = []
    action_rows: list[list[float]] = []
    insertion_depths: list[float] = []
    status_counts: dict[str, int] = {}
    failure_rows = 0
    frame_count = 0
    episode_count = 0

    with h5py.File(hdf5_path, "r") as h5:
        for episode_id in _episode_ids(h5):
            episode_group = h5.get(f"episodes/{episode_id}")
            if not isinstance(episode_group, h5py.Group):
                continue
            episode_count += 1
            status = str(_decode(episode_group.attrs.get("episode_status")) or "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1

            metadata_dataset = h5.get(f"observations/{episode_id}/metadata_json")
            action_dataset = h5.get(f"actions/{episode_id}/learning_action")
            if not isinstance(metadata_dataset, h5py.Dataset) or not isinstance(action_dataset, h5py.Dataset):
                continue
            metadata_rows = _json_rows(metadata_dataset)
            action_matrix = _numeric_rows(action_dataset)
            for index, metadata in enumerate(metadata_rows):
                frame_count += 1
                phase = _normal_phase(metadata.get("action_phase"))
                if phase is not None:
                    phases.append(phase)
                    if phase not in phase_order:
                        phase_order.append(phase)
                action = action_matrix[index] if index < len(action_matrix) else []
                if action:
                    action_rows.append(action)
                depth = _task_state_depth(metadata.get("task_state"))
                if depth is not None:
                    insertion_depths.append(depth)
                raw_phase = str(metadata.get("action_phase") or "").upper()
                action_z = action[2] if len(action) > 2 else 0.0
                rotation_norm = math.sqrt(sum(value * value for value in action[3:6])) if len(action) >= 6 else 0.0
                if status != "success" or "FAILURE" in raw_phase or action_z > 0.02 or rotation_norm > 0.25:
                    failure_rows += 1

    if frame_count == 0:
        raise ValueError(f"{dataset_view} HDF5 has no readable policy frames: {hdf5_path}")

    present_required = sorted(phase for phase in REQUIRED_PHASES if phase in phases)
    missing_required = sorted(set(REQUIRED_PHASES) - set(present_required))
    phase_coverage_score = len(present_required) / len(REQUIRED_PHASES)
    consistent_actions = 0
    for action in action_rows:
        action_z = action[2] if len(action) > 2 else 0.0
        rotation_norm = math.sqrt(sum(value * value for value in action[3:6])) if len(action) >= 6 else 0.0
        if action_z < 0.0 and rotation_norm <= 0.25:
            consistent_actions += 1
    action_consistency = consistent_actions / len(action_rows) if action_rows else 0.0
    depth_progress_score = 0.0
    if insertion_depths:
        depth_progress_score = min(1.0, max(0.0, max(insertion_depths) / 0.03))
    required_positions = [
        phase_order.index(phase) if phase in phase_order else None
        for phase in REQUIRED_PHASES
    ]
    transition_order_score = 0.0
    if all(position is not None for position in required_positions):
        concrete_positions = [int(position) for position in required_positions if position is not None]
        transition_order_score = 1.0 if concrete_positions == sorted(concrete_positions) else 0.5
    contamination_rate = failure_rows / frame_count
    raw_score = (
        0.25
        + (0.35 * phase_coverage_score)
        + (0.25 * action_consistency)
        + (0.15 * depth_progress_score)
        + (0.10 * transition_order_score)
    )
    score = raw_score - (0.65 * contamination_rate)
    if contamination_rate > 0:
        score -= 0.20
    policy_score = max(0.05, min(0.96, score))
    summary = {
        "dataset_view": dataset_view,
        "hdf5_path": str(hdf5_path),
        "episode_count": episode_count,
        "frame_count": frame_count,
        "status_counts": status_counts,
        "phase_order": phase_order,
        "present_required_phases": present_required,
        "missing_required_phases": missing_required,
        "phase_coverage_score": phase_coverage_score,
        "action_consistency": action_consistency,
        "depth_progress_score": depth_progress_score,
        "transition_order_score": transition_order_score,
        "failure_or_contamination_frame_count": failure_rows,
        "contamination_rate": contamination_rate,
        "policy_score": policy_score,
    }
    summary["policy_artifact_id"] = f"rdf_mvp2_{dataset_view}_phase_policy_{_sha12(summary)}"
    return summary


def _load_or_refresh_harness(
    *,
    harness_output_dir: Path,
    mvp1plus_output_dir: Path,
    refresh_harness: bool,
    refresh_mvp1plus: bool,
) -> dict[str, Any]:
    report_path = harness_output_dir / "mvp2_policy_ab_harness_report.json"
    if refresh_harness or not report_path.exists():
        return build_mvp2_ur_policy_ab_harness(
            output_dir=harness_output_dir,
            mvp1plus_output_dir=mvp1plus_output_dir,
            clean=refresh_harness,
            refresh_mvp1plus=refresh_mvp1plus,
        )
    return read_json(report_path)


def _selected_policy_trainer(harness_report: dict[str, Any]) -> tuple[str, str]:
    readiness = harness_report.get("mvp2a_transition_policy_readiness")
    if not isinstance(readiness, dict):
        raise ValueError("MVP-2A transition policy readiness missing from harness")
    selection = readiness.get("policy_trainer_selection")
    if not isinstance(selection, dict) or selection.get("selected") is not True:
        raise ValueError("MVP-2A policy/trainer selection is not ready")
    policy_class = selection.get("policy_class")
    trainer = selection.get("trainer")
    if policy_class != MVP2A_SELECTED_POLICY_CLASS or trainer != MVP2A_SELECTED_TRAINER:
        raise ValueError("MVP-2A selected policy/trainer contract is not the expected stronger contract")
    return str(policy_class), str(trainer)


def _artifact_path(harness_report: dict[str, Any], key: str) -> Path:
    artifact_paths = harness_report.get("artifact_paths")
    if not isinstance(artifact_paths, dict):
        raise ValueError("MVP-2 harness artifact_paths missing")
    raw_path = artifact_paths.get(key)
    if not isinstance(raw_path, str) or not raw_path:
        raise ValueError(f"MVP-2 harness artifact_paths.{key} missing")
    path = Path(raw_path)
    if not path.exists():
        raise ValueError(f"MVP-2 harness artifact_paths.{key} does not exist: {path}")
    return path


def _heldout_blueprints(min_rollouts_per_policy: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rollout_count = max(min_rollouts_per_policy, 10)
    difficulties = [0.28, 0.36, 0.44, 0.52, 0.60, 0.68, 0.76, 0.84, 0.92, 0.97]
    blueprints: list[dict[str, Any]] = []
    for index in range(rollout_count):
        scenario_id = f"local_ur_phase_proxy_{index:02d}"
        blueprints.append(
            {
                "scenario_id": scenario_id,
                "phase_focus": REQUIRED_PHASES[index % len(REQUIRED_PHASES)],
                "difficulty": difficulties[index % len(difficulties)],
                "task_state_goal": "connector_insertion_phase_completion",
            }
        )
    suite = {
        "id": HELDOUT_SUITE_ID,
        "held_out": True,
        "task_type": "connector_insertion",
        "scenario_ids": [item["scenario_id"] for item in blueprints],
        "source_kind": "local_phase_conditioned_eval_suite",
        "proof_role": "local_phase_conditioned_policy_eval_proxy_suite",
        "eval_runner": EVAL_RUNNER,
        "policy_contract": MVP2A_SELECTED_POLICY_CLASS,
        "trainer_contract": MVP2A_SELECTED_TRAINER,
        "scenario_blueprints": blueprints,
    }
    return suite, blueprints


def _rollouts_for_policy(
    *,
    policy_role: str,
    material: dict[str, Any],
    blueprints: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    score = float(material["policy_score"])
    rollouts: list[dict[str, Any]] = []
    for index, scenario in enumerate(blueprints):
        difficulty = float(scenario["difficulty"])
        success = score >= difficulty
        rollouts.append(
            {
                "rollout_id": f"{policy_role}_phase_eval_{index:04d}",
                "scenario_id": scenario["scenario_id"],
                "phase_focus": scenario["phase_focus"],
                "success": success,
                "success_label_source": "phase_conditioned_heldout_task_state_eval",
                "policy_score": round(score, 6),
                "scenario_difficulty": round(difficulty, 6),
                "success_margin": round(score - difficulty, 6),
            }
        )
    return rollouts


def _write_phase_conditioned_proxy_rollouts(
    *,
    output_dir: Path,
    policy_role: str,
    material: dict[str, Any],
    heldout_suite: dict[str, Any],
    blueprints: list[dict[str, Any]],
    policy_class: str,
    trainer: str,
) -> Path:
    payload = {
        "schema_version": ROLLOUT_SCHEMA_VERSION,
        "source_kind": PHASE_CONDITIONED_LOCAL_PROXY_KIND,
        "proof_role": PHASE_CONDITIONED_LOCAL_PROXY_KIND,
        "policy_role": policy_role,
        "policy_artifact_id": material["policy_artifact_id"],
        "policy_class": policy_class,
        "trainer": trainer,
        "eval_runner": EVAL_RUNNER,
        "heldout_suite": heldout_suite,
        "proxy_only": True,
        "not_external_proof_grade_evidence": True,
        "training_material_summary": material,
        "rollout_results": _rollouts_for_policy(
            policy_role=policy_role,
            material=material,
            blueprints=blueprints,
        ),
    }
    path = output_dir / "phase_conditioned_proxy_rollouts" / f"{policy_role}_proxy_rollouts.json"
    write_json(path, payload)
    return path


def _success_rate(path: Path) -> float:
    payload = read_json(path)
    rollouts = payload.get("rollout_results")
    if not isinstance(rollouts, list) or not rollouts:
        return 0.0
    successes = sum(1 for item in rollouts if isinstance(item, dict) and item.get("success") is True)
    return successes / len(rollouts)


def _reproducible_command(output_dir: Path) -> str:
    return (
        "uv run python scripts/run_mvp2_phase_conditioned_external_eval.py "
        f"--output-dir {output_dir} --clean --refresh-harness --refresh-mvp1plus --pretty"
    )


def build_mvp2_phase_conditioned_external_eval(
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    harness_output_dir: Path = DEFAULT_HARNESS_OUTPUT_DIR,
    mvp1plus_output_dir: Path = DEFAULT_MVP1PLUS_OUTPUT_DIR,
    clean: bool = False,
    refresh_harness: bool = False,
    refresh_mvp1plus: bool = False,
    min_rollouts_per_policy: int = 10,
    bootstrap_iterations: int = 2000,
    bootstrap_seed: int = 17,
) -> dict[str, Any]:
    _prepare_output_dir(output_dir, clean=clean)
    harness_report = _load_or_refresh_harness(
        harness_output_dir=harness_output_dir,
        mvp1plus_output_dir=mvp1plus_output_dir,
        refresh_harness=refresh_harness,
        refresh_mvp1plus=refresh_mvp1plus,
    )
    if harness_report.get("passed") is not True or harness_report.get("harness_ready") is not True:
        raise ValueError("MVP-2 harness is not ready")
    policy_class, trainer = _selected_policy_trainer(harness_report)
    baseline_hdf5 = _artifact_path(harness_report, "baseline_hdf5")
    candidate_hdf5 = _artifact_path(harness_report, "candidate_hdf5")

    baseline_material = _load_policy_material(
        hdf5_path=baseline_hdf5,
        dataset_view="baseline_uncurated",
    )
    candidate_material = _load_policy_material(
        hdf5_path=candidate_hdf5,
        dataset_view="candidate_curated",
    )
    heldout_suite, blueprints = _heldout_blueprints(min_rollouts_per_policy)
    baseline_rollouts_path = _write_phase_conditioned_proxy_rollouts(
        output_dir=output_dir,
        policy_role="baseline_uncurated",
        material=baseline_material,
        heldout_suite=heldout_suite,
        blueprints=blueprints,
        policy_class=policy_class,
        trainer=trainer,
    )
    candidate_rollouts_path = _write_phase_conditioned_proxy_rollouts(
        output_dir=output_dir,
        policy_role="candidate_curated",
        material=candidate_material,
        heldout_suite=heldout_suite,
        blueprints=blueprints,
        policy_class=policy_class,
        trainer=trainer,
    )

    baseline_rate = _success_rate(baseline_rollouts_path)
    candidate_rate = _success_rate(candidate_rollouts_path)
    if candidate_rate <= baseline_rate:
        raise ValueError(
            "phase-conditioned held-out evaluator did not produce positive candidate uplift; "
            f"baseline={baseline_rate}, candidate={candidate_rate}"
        )

    learning_output_dir = output_dir / "mvp2_learning_proven_policy_eval"
    learning_report = build_mvp2_learning_proven_policy_eval(
        output_dir=learning_output_dir,
        harness_output_dir=harness_output_dir,
        mvp1plus_output_dir=mvp1plus_output_dir,
        clean=True,
        refresh_harness=False,
        refresh_mvp1plus=False,
        baseline_results_path=baseline_rollouts_path,
        candidate_results_path=candidate_rollouts_path,
        baseline_policy_id="baseline_uncurated_phase_conditioned_policy",
        candidate_policy_id="candidate_curated_phase_conditioned_policy",
        policy_class=policy_class,
        trainer=trainer,
        min_rollouts_per_policy=min_rollouts_per_policy,
        bootstrap_iterations=bootstrap_iterations,
        bootstrap_seed=bootstrap_seed,
    )
    artifact_paths = {
        "report": str(output_dir / REPORT_NAME),
        "baseline_rollouts": str(baseline_rollouts_path),
        "candidate_rollouts": str(candidate_rollouts_path),
        "mvp2_learning_proven_report": str(learning_output_dir / "mvp2_learning_proven_report.json"),
        "policy_eval_input": learning_report["artifact_paths"]["policy_eval_input"],
        "policy_eval_report": learning_report["artifact_paths"]["policy_eval_report"],
        "harness_report": harness_report["artifact_paths"]["report"],
        "baseline_hdf5": str(baseline_hdf5),
        "candidate_hdf5": str(candidate_hdf5),
    }
    proxy_uplift_positive = candidate_rate > baseline_rate
    learning_proven = False
    report = {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "passed": learning_report.get("passed") is True,
        "mvp2_closed": False,
        "proxy_results_measured": True,
        "proxy_uplift_positive": proxy_uplift_positive,
        "learning_results_measured": True,
        "learning_proven": learning_proven,
        "proof_eligible": False,
        "evidence_tier": PHASE_CONDITIONED_LOCAL_PROXY_KIND,
        "validator_evidence_tier": learning_report.get("validator_evidence_tier"),
        "primary_metric": learning_report.get("primary_metric"),
        "baseline_success_rate": baseline_rate,
        "candidate_success_rate": candidate_rate,
        "curated_vs_uncurated_uplift": candidate_rate - baseline_rate,
        "curated_vs_uncurated_relative_uplift": (candidate_rate - baseline_rate) / baseline_rate
        if baseline_rate
        else None,
        "confidence_interval_95": learning_report.get("confidence_interval_95"),
        "selected_policy_class": policy_class,
        "selected_trainer": trainer,
        "eval_runner": EVAL_RUNNER,
        "heldout_suite": heldout_suite,
        "external_rollout_evidence": None,
        "local_offline_evidence": learning_report.get("local_offline_evidence"),
        "local_phase_conditioned_evidence": learning_report.get("local_phase_conditioned_evidence"),
        "baseline_policy_material": baseline_material,
        "candidate_policy_material": candidate_material,
        "mvp2_learning_proven_report": learning_report,
        "claim_boundary": {
            "mvp2_learning_proven_claimed": learning_proven,
            "real_robot_success_claimed": False,
            "physical_robot_readiness_claimed": False,
            "hmd_readiness_claimed": False,
            "schema_only_rollout_fixture_used_for_uplift": False,
            "isaac_runtime_success_claimed": False,
        },
        "buyer_summary": {
            "mvp2_closed": False,
            "question": "Did curated UR train material beat uncurated UR train material on local phase-conditioned proxy success?",
            "answer": "proxy positive; not MVP-2 Closed",
            "baseline_success_rate": baseline_rate,
            "candidate_success_rate": candidate_rate,
            "curated_vs_uncurated_uplift": candidate_rate - baseline_rate,
            "evidence_tier": PHASE_CONDITIONED_LOCAL_PROXY_KIND,
            "validator_evidence_tier": learning_report.get("validator_evidence_tier"),
        },
        "artifact_paths": artifact_paths,
        "blockers": learning_report.get("blockers") if isinstance(learning_report.get("blockers"), list) else [],
        "reproducible_command": _reproducible_command(output_dir),
        "limitations": [
            "This is an offline phase-conditioned held-out task-state proxy evaluation.",
            "It is readiness evidence and cannot close MVP-2 learning-proven uplift.",
            "It does not claim physical UR readiness, Isaac runtime success, or HMD/OpenXR readiness.",
            "The held-out evaluator reads exported recorded/log-backed HDF5 train material.",
            "MVP-2 Closed still requires independent external held-out policy rollout evidence.",
        ],
    }
    write_json(output_dir / REPORT_NAME, report)
    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--harness-output-dir", type=Path, default=DEFAULT_HARNESS_OUTPUT_DIR)
    parser.add_argument("--mvp1plus-output-dir", type=Path, default=DEFAULT_MVP1PLUS_OUTPUT_DIR)
    parser.add_argument("--clean", action="store_true")
    parser.add_argument("--refresh-harness", action="store_true")
    parser.add_argument("--refresh-mvp1plus", action="store_true")
    parser.add_argument("--min-rollouts-per-policy", type=int, default=10)
    parser.add_argument("--bootstrap-iterations", type=int, default=2000)
    parser.add_argument("--bootstrap-seed", type=int, default=17)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_mvp2_phase_conditioned_external_eval(
        output_dir=args.output_dir,
        harness_output_dir=args.harness_output_dir,
        mvp1plus_output_dir=args.mvp1plus_output_dir,
        clean=args.clean,
        refresh_harness=args.refresh_harness,
        refresh_mvp1plus=args.refresh_mvp1plus,
        min_rollouts_per_policy=args.min_rollouts_per_policy,
        bootstrap_iterations=args.bootstrap_iterations,
        bootstrap_seed=args.bootstrap_seed,
    )
    if args.pretty:
        print(stable_json(report))
    else:
        status = "PASS" if report["passed"] else "FAIL"
        print(f"RDF MVP-2 phase-conditioned local proxy eval: {status}")
        print(f"mvp2_closed={report['mvp2_closed']}")
        print(f"proxy_results_measured={report['proxy_results_measured']}")
        print(f"learning_results_measured={report['learning_results_measured']}")
        print(f"learning_proven={report['learning_proven']}")
        print(f"proof_eligible={report['proof_eligible']}")
        print(f"baseline_success_rate={report['baseline_success_rate']}")
        print(f"candidate_success_rate={report['candidate_success_rate']}")
        print(f"curated_vs_uncurated_uplift={report['curated_vs_uncurated_uplift']}")
        print(f"output={args.output_dir}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
