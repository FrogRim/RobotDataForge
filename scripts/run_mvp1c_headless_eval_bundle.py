#!/usr/bin/env python3
"""Prepare MVP-1C headless curated-vs-uncurated policy-eval artifacts.

The bundle produced by this script is the bridge between data curation and a
real headless policy evaluator. It exports separate uncurated and curated train
datasets, writes a held-out suite manifest, and creates a policy-eval input
template for scripts/run_mvp1c_real_policy_eval.py.

It does not run a policy rollout and does not claim MVP-1C proof.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import shutil
import sys
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from export_rdf_to_hdf5 import ExportValidationError, export_hdf5, load_json  # noqa: E402
from inspect_rdf_hdf5 import inspect_hdf5  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_READINESS_DIR = ROOT / "storage" / "mvp1_readiness"
DEFAULT_OUTPUT_DIR = ROOT / "storage" / "mvp1c_headless_eval"
SCHEMA_VERSION = "rdf_mvp1c_headless_eval_bundle_v0.1.0"


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


def _trajectory_index(trajectories_dir: Path) -> dict[str, Path]:
    index: dict[str, Path] = {}
    for path in sorted(trajectories_dir.glob("*.json")):
        trajectory = load_json(path)
        episode_id = trajectory.get("episode_id")
        if isinstance(episode_id, str):
            index[episode_id] = path
    return index


def _evaluation_index(evaluations_dir: Path) -> tuple[dict[str, Path], dict[str, Path]]:
    by_episode: dict[str, Path] = {}
    by_trajectory: dict[str, Path] = {}
    for path in sorted(evaluations_dir.glob("*.json")):
        evaluation = load_json(path)
        episode_id = evaluation.get("episode_id")
        trajectory_id = evaluation.get("trajectory_id")
        if isinstance(episode_id, str):
            by_episode[episode_id] = path
        if isinstance(trajectory_id, str):
            by_trajectory[trajectory_id] = path
    return by_episode, by_trajectory


def _copy_episode_view(
    *,
    episode_ids: list[str],
    source_trajectories_dir: Path,
    source_evaluations_dir: Path,
    destination_dir: Path,
) -> tuple[list[str], list[str]]:
    copied: list[str] = []
    missing: list[str] = []
    trajectory_index = _trajectory_index(source_trajectories_dir)
    evaluation_by_episode, evaluation_by_trajectory = _evaluation_index(source_evaluations_dir)
    destination_trajectories = destination_dir / "trajectories"
    destination_evaluations = destination_dir / "evaluations"
    destination_trajectories.mkdir(parents=True, exist_ok=True)
    destination_evaluations.mkdir(parents=True, exist_ok=True)

    for episode_id in episode_ids:
        trajectory_path = trajectory_index.get(episode_id)
        if trajectory_path is None:
            missing.append(episode_id)
            continue
        trajectory = load_json(trajectory_path)
        shutil.copy2(trajectory_path, destination_trajectories / trajectory_path.name)
        copied.append(episode_id)

        trajectory_id = trajectory.get("id")
        evaluation_path = evaluation_by_episode.get(episode_id)
        if evaluation_path is None and isinstance(trajectory_id, str):
            evaluation_path = evaluation_by_trajectory.get(trajectory_id)
        if evaluation_path is not None:
            shutil.copy2(evaluation_path, destination_evaluations / evaluation_path.name)

    return copied, missing


def _write_split_manifest(path: Path, *, train_ids: list[str], validation_ids: list[str], test_ids: list[str]) -> dict[str, Any]:
    manifest = {
        "schema_version": "rdf_split_manifest_v0.1.0",
        "created_at": datetime.now(UTC).isoformat(),
        "strategy": "mvp1c_headless_train_eval_split",
        "splits": {
            "train": train_ids,
            "validation": validation_ids,
            "test": test_ids,
        },
        "held_out_definition": "Use validation/test scenario ids for headless policy rollout; replace fixture ids with real pose/clearance/connector variants for customer proof.",
    }
    write_json(path, manifest)
    return manifest


def _write_heldout_manifest(
    path: Path,
    *,
    validation_ids: list[str],
    test_ids: list[str],
    task_type: str,
) -> dict[str, Any]:
    manifest = {
        "schema_version": "rdf_mvp1c_heldout_suite_v0.1.0",
        "created_at": datetime.now(UTC).isoformat(),
        "id": f"{task_type}_heldout_v1",
        "task_type": task_type,
        "held_out": True,
        "split": "validation_plus_test",
        "validation_episode_ids": validation_ids,
        "test_episode_ids": test_ids,
        "scenario_ids": [f"scenario_for_{episode_id}" for episode_id in validation_ids + test_ids],
        "limitations": [
            "Readiness fixture ids are only a scaffold.",
            "Full MVP-1C proof needs real held-out pose/clearance/connector variants.",
        ],
    }
    write_json(path, manifest)
    return manifest


def _write_policy_eval_template(
    path: Path,
    *,
    task_type: str,
    heldout_manifest: dict[str, Any],
    baseline_hdf5: Path,
    candidate_hdf5: Path,
    baseline_train_ids: list[str],
    candidate_train_ids: list[str],
) -> dict[str, Any]:
    template = {
        "schema_version": "rdf_mvp1c_policy_eval_input_v0.1.0",
        "evidence_tier": "heldout_policy_eval",
        "primary_metric": "policy_success_rate",
        "task_type": task_type,
        "eval_suite": {
            "id": heldout_manifest["id"],
            "held_out": True,
            "split": heldout_manifest["split"],
            "task_type": task_type,
            "scenario_ids": heldout_manifest["scenario_ids"],
            "heldout_manifest_path": str(path.parent / "heldout_suite_manifest.json"),
        },
        "baseline": {
            "name": "uncurated_success_lifecycle_policy",
            "dataset_view": "uncurated_success_lifecycle",
            "dataset_id": "mvp1c_uncurated_success_lifecycle_train",
            "train_hdf5_path": str(baseline_hdf5),
            "train_episode_ids": baseline_train_ids,
            "policy_class": "TODO_ACT_OR_SELECTED_POLICY",
            "trainer": "TODO_HEADLESS_TRAINER",
            "rollout_results": [],
        },
        "candidate": {
            "name": "curated_accepted_policy",
            "dataset_view": "curated_accepted",
            "dataset_id": "mvp1c_curated_accepted_train",
            "train_hdf5_path": str(candidate_hdf5),
            "train_episode_ids": candidate_train_ids,
            "policy_class": "TODO_ACT_OR_SELECTED_POLICY",
            "trainer": "TODO_HEADLESS_TRAINER",
            "rollout_results": [],
        },
        "instructions": [
            "Train baseline and candidate policies from their HDF5 paths.",
            "Run both policies on the same held-out scenario_ids.",
            "Fill rollout_results with success booleans from headless Isaac held-out policy rollouts.",
            "Use real_heldout_policy_eval only if HMD live accepted trajectories are included.",
            "Then run scripts/run_mvp1c_real_policy_eval.py --input <this file>.",
        ],
    }
    write_json(path, template)
    return template


def _export_and_inspect(
    *,
    hdf5_path: Path,
    raw_dir: Path,
    inspection_path: Path,
) -> tuple[dict[str, Any] | None, list[str]]:
    issues: list[str] = []
    try:
        export_hdf5(
            output_path=hdf5_path,
            trajectories_dir=raw_dir / "trajectories",
            evaluations_dir=raw_dir / "evaluations",
            include_statuses={"success"},
        )
        inspection = inspect_hdf5(hdf5_path)
        write_json(inspection_path, inspection)
        issues.extend(str(issue) for issue in inspection.get("issues", []))
        return inspection, issues
    except (ExportValidationError, OSError, ValueError) as exc:
        issues.append(str(exc))
        return None, issues


def build_headless_eval_bundle(
    *,
    readiness_dir: Path,
    output_dir: Path,
    clean: bool = False,
    task_type: str = "peg_in_hole",
    prefer_replay_verified: bool = True,
) -> dict[str, Any]:
    if clean and output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    experiment_manifest = read_json(readiness_dir / "curated_vs_uncurated_experiment_manifest.json")
    replay_gate_path = readiness_dir / "replay_gate_manifest.json"
    replay_gate = read_json(replay_gate_path) if prefer_replay_verified and replay_gate_path.exists() else None
    split_manifest_path = (
        readiness_dir / "split_manifest_replay_verified.json"
        if replay_gate is not None and (readiness_dir / "split_manifest_replay_verified.json").exists()
        else readiness_dir / "split_manifest.json"
    )
    split_manifest = read_json(split_manifest_path)
    splits = split_manifest.get("splits") if isinstance(split_manifest.get("splits"), dict) else {}
    validation_ids = [str(value) for value in splits.get("validation", [])]
    test_ids = [str(value) for value in splits.get("test", [])]
    heldout_ids = set(validation_ids + test_ids)

    if replay_gate is not None:
        baseline_source_key = "baseline_a_replay_verified_success_lifecycle_episode_ids"
        candidate_source_key = "baseline_b_replay_verified_curated_accepted_episode_ids"
    else:
        baseline_source_key = "baseline_a_uncurated_success_lifecycle_episode_ids"
        candidate_source_key = "baseline_b_curated_accepted_episode_ids"
    baseline_ids = [str(value) for value in experiment_manifest.get(baseline_source_key, [])]
    candidate_ids = [str(value) for value in experiment_manifest.get(candidate_source_key, [])]
    baseline_train_ids = [episode_id for episode_id in baseline_ids if episode_id not in heldout_ids]
    candidate_train_ids = [episode_id for episode_id in candidate_ids if episode_id not in heldout_ids]

    source_raw = readiness_dir / "raw"
    baseline_raw = output_dir / "baseline_uncurated" / "raw"
    candidate_raw = output_dir / "candidate_curated" / "raw"
    baseline_copied, baseline_missing = _copy_episode_view(
        episode_ids=baseline_train_ids,
        source_trajectories_dir=source_raw / "trajectories",
        source_evaluations_dir=source_raw / "evaluations",
        destination_dir=baseline_raw,
    )
    candidate_copied, candidate_missing = _copy_episode_view(
        episode_ids=candidate_train_ids,
        source_trajectories_dir=source_raw / "trajectories",
        source_evaluations_dir=source_raw / "evaluations",
        destination_dir=candidate_raw,
    )

    baseline_split_path = output_dir / "baseline_uncurated" / "split_manifest.json"
    candidate_split_path = output_dir / "candidate_curated" / "split_manifest.json"
    _write_split_manifest(
        baseline_split_path,
        train_ids=baseline_copied,
        validation_ids=validation_ids,
        test_ids=test_ids,
    )
    _write_split_manifest(
        candidate_split_path,
        train_ids=candidate_copied,
        validation_ids=validation_ids,
        test_ids=test_ids,
    )

    baseline_hdf5 = output_dir / "baseline_uncurated" / "mvp1c_uncurated_success_lifecycle_train.hdf5"
    candidate_hdf5 = output_dir / "candidate_curated" / "mvp1c_curated_accepted_train.hdf5"
    baseline_inspection, baseline_export_issues = _export_and_inspect(
        hdf5_path=baseline_hdf5,
        raw_dir=baseline_raw,
        inspection_path=output_dir / "baseline_uncurated" / "hdf5_inspection.json",
    )
    candidate_inspection, candidate_export_issues = _export_and_inspect(
        hdf5_path=candidate_hdf5,
        raw_dir=candidate_raw,
        inspection_path=output_dir / "candidate_curated" / "hdf5_inspection.json",
    )

    heldout_manifest = _write_heldout_manifest(
        output_dir / "heldout_suite_manifest.json",
        validation_ids=validation_ids,
        test_ids=test_ids,
        task_type=task_type,
    )
    template = _write_policy_eval_template(
        output_dir / "policy_eval_input_template.json",
        task_type=task_type,
        heldout_manifest=heldout_manifest,
        baseline_hdf5=baseline_hdf5,
        candidate_hdf5=candidate_hdf5,
        baseline_train_ids=baseline_copied,
        candidate_train_ids=candidate_copied,
    )

    issues: list[str] = []
    warnings: list[str] = [
        "This bundle prepares headless eval artifacts but does not run policy rollouts.",
        "Do not claim MVP-1C until policy_eval_input_template.json is filled with real held-out rollout results and ingested.",
    ]
    if replay_gate is not None and replay_gate.get("pool_ready_for_policy_ab") is not True:
        gate_blockers = replay_gate.get("pool_blockers")
        if isinstance(gate_blockers, list) and gate_blockers:
            issues.append(f"replay gate pool is not ready: {', '.join(str(item) for item in gate_blockers)}")
        else:
            issues.append("replay gate pool is not ready")
    if baseline_missing:
        issues.append(f"baseline missing episodes: {', '.join(baseline_missing)}")
    if candidate_missing:
        issues.append(f"candidate missing episodes: {', '.join(candidate_missing)}")
    if not baseline_copied:
        issues.append("baseline train set is empty")
    if not candidate_copied:
        issues.append("candidate train set is empty")
    if not validation_ids and not test_ids:
        issues.append("held-out validation/test ids are empty")
    issues.extend(f"baseline export: {issue}" for issue in baseline_export_issues)
    issues.extend(f"candidate export: {issue}" for issue in candidate_export_issues)

    report = {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "passed": not issues,
        "proof_eligible": False,
        "replay_gate_used": replay_gate is not None,
        "replay_gate_manifest_path": str(replay_gate_path) if replay_gate is not None else None,
        "replay_gate_pool_ready": replay_gate.get("pool_ready_for_policy_ab") if replay_gate is not None else None,
        "replay_gate_pool_blockers": replay_gate.get("pool_blockers", []) if replay_gate is not None else [],
        "source_split_manifest_path": str(split_manifest_path),
        "readiness_dir": str(readiness_dir),
        "output_dir": str(output_dir),
        "baseline": {
            "dataset_view": "uncurated_success_lifecycle",
            "source_episode_id_field": baseline_source_key,
            "train_episode_ids": baseline_copied,
            "hdf5_path": str(baseline_hdf5),
            "split_manifest_path": str(baseline_split_path),
            "inspection": baseline_inspection,
        },
        "candidate": {
            "dataset_view": "curated_accepted",
            "source_episode_id_field": candidate_source_key,
            "train_episode_ids": candidate_copied,
            "hdf5_path": str(candidate_hdf5),
            "split_manifest_path": str(candidate_split_path),
            "inspection": candidate_inspection,
        },
        "heldout_suite_manifest_path": str(output_dir / "heldout_suite_manifest.json"),
        "policy_eval_input_template_path": str(output_dir / "policy_eval_input_template.json"),
        "next_commands": [
            "Train baseline policy with baseline.hdf5_path.",
            "Train candidate policy with candidate.hdf5_path.",
            "Run both policies headlessly on heldout_suite_manifest_path scenarios.",
            f"Fill {output_dir / 'policy_eval_input_template.json'} with rollout_results.",
            f"uv run python scripts/run_mvp1c_real_policy_eval.py --input {output_dir / 'policy_eval_input_template.json'} --pretty",
            "uv run python scripts/run_mvp1_proof_audit.py --pretty",
        ],
        "template": template,
        "issues": issues,
        "warnings": warnings,
    }
    write_json(output_dir / "headless_eval_bundle_report.json", report)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--readiness-dir", type=Path, default=DEFAULT_READINESS_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--task-type", default="peg_in_hole", choices=("peg_in_hole", "connector_insertion"))
    parser.add_argument("--clean", action="store_true")
    parser.add_argument(
        "--ignore-replay-gate",
        action="store_true",
        help="Use legacy curation ids even if replay_gate_manifest.json is present.",
    )
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_headless_eval_bundle(
        readiness_dir=args.readiness_dir,
        output_dir=args.output_dir,
        clean=args.clean,
        task_type=args.task_type,
        prefer_replay_verified=not args.ignore_replay_gate,
    )
    if args.pretty:
        print(stable_json(report))
    else:
        status = "PASS" if report["passed"] else "FAIL"
        print(f"RDF MVP-1C headless eval bundle: {status}")
        print(f"proof_eligible={report['proof_eligible']}")
        print(f"baseline_hdf5={report['baseline']['hdf5_path']}")
        print(f"candidate_hdf5={report['candidate']['hdf5_path']}")
        print(f"heldout_suite_manifest={report['heldout_suite_manifest_path']}")
        print(f"policy_eval_input_template={report['policy_eval_input_template_path']}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
