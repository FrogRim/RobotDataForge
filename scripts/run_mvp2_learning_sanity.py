#!/usr/bin/env python3
"""Run MVP-2 pre-A/B learning sanity gates.

This script does not measure curated-vs-uncurated policy uplift. It checks two
prerequisites that should be green before another held-out policy A/B:

1. transition coverage audit for accepted/replay-verified dataset material
2. train-set overfit sanity for the exported observation/action contract
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import UTC, datetime
import json
from pathlib import Path
import sys
from typing import Any

import h5py
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from run_mvp1_trainer_smoke import load_hdf5_batches  # noqa: E402


SCHEMA_VERSION = "rdf_mvp2_learning_sanity_v0.1.0"
DEFAULT_OUTPUT_DIR = ROOT / "storage" / "mvp2_learning_sanity"
DEFAULT_HDF5 = ROOT / "storage" / "mvp1_live_export" / "rdf_mvp1_live_export_smoke.hdf5"
DEFAULT_SPLIT_MANIFEST = ROOT / "storage" / "mvp1_live_export" / "split_manifest.json"
DEFAULT_CURATION_MANIFEST = ROOT / "storage" / "mvp1_live_export" / "curation_manifest.json"
DEFAULT_EXPERIMENT_MANIFEST = (
    ROOT / "storage" / "mvp1_live_export" / "curated_vs_uncurated_experiment_manifest.json"
)
REQUIRED_PHASES = ("APPROACH", "CONTACT", "INSERT", "SEAT")
SUPPORTED_PHASES = {
    "APPROACH",
    "ALIGN",
    "CONTACT",
    "INSERT",
    "SEAT",
    "STABILIZE",
    "RELEASE",
    "RECOVER",
    "UNKNOWN",
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


def _decode(value: Any) -> Any:
    if isinstance(value, bytes):
        return value.decode("utf-8")
    if isinstance(value, np.bytes_):
        return bytes(value).decode("utf-8")
    return value


def _read_episode_ids(h5: h5py.File) -> list[str]:
    dataset = h5.get("episodes/episode_ids")
    if not isinstance(dataset, h5py.Dataset):
        return []
    return [str(_decode(value)) for value in dataset[()]]


def _read_metadata_frames(h5: h5py.File, episode_id: str) -> list[dict[str, Any]]:
    dataset = h5.get(f"observations/{episode_id}/metadata_json")
    if not isinstance(dataset, h5py.Dataset):
        return []
    frames: list[dict[str, Any]] = []
    for value in dataset[()]:
        decoded = _decode(value)
        try:
            parsed = json.loads(str(decoded))
        except json.JSONDecodeError:
            parsed = {}
        frames.append(parsed if isinstance(parsed, dict) else {})
    return frames


def _phase_from_metadata(metadata: dict[str, Any]) -> tuple[str, str, float]:
    explicit = metadata.get("action_phase") or metadata.get("phase")
    if explicit is not None:
        phase = str(explicit).strip().upper()
        return (phase if phase in SUPPORTED_PHASES else "UNKNOWN", "frame_metadata", 1.0)

    task_state = metadata.get("task_state")
    if isinstance(task_state, dict):
        task_phase = task_state.get("action_phase") or task_state.get("phase")
        if task_phase is not None:
            phase = str(task_phase).strip().upper()
            return (phase if phase in SUPPORTED_PHASES else "UNKNOWN", "task_state_metadata", 0.9)

    command_state_row = metadata.get("command_state_row")
    if isinstance(command_state_row, dict):
        command_state_phase = command_state_row.get("task_phase") or command_state_row.get("action_phase")
        if command_state_phase is not None:
            phase = str(command_state_phase).strip().upper()
            return (
                phase if phase in SUPPORTED_PHASES else "UNKNOWN",
                "command_state_row.task_phase",
                0.8,
            )

    return ("UNKNOWN", "unavailable", 0.0)


def _segments_from_phases(phases: list[tuple[str, str, float]]) -> list[dict[str, Any]]:
    if not phases:
        return []
    segments: list[dict[str, Any]] = []
    current_phase, current_source, current_confidence = phases[0]
    start = 0
    for index in range(1, len(phases)):
        phase, source, confidence = phases[index]
        if phase != current_phase or source != current_source:
            segments.append(
                {
                    "phase": current_phase,
                    "start_frame": start,
                    "end_frame": index - 1,
                    "frame_count": index - start,
                    "source": current_source,
                    "confidence": current_confidence,
                }
            )
            current_phase = phase
            current_source = source
            current_confidence = confidence
            start = index
    segments.append(
        {
            "phase": current_phase,
            "start_frame": start,
            "end_frame": len(phases) - 1,
            "frame_count": len(phases) - start,
            "source": current_source,
            "confidence": current_confidence,
        }
    )
    return segments


def _accepted_episode_ids(curation_manifest: dict[str, Any]) -> list[str]:
    accepted_episode_ids = curation_manifest.get("accepted_episode_ids")
    if isinstance(accepted_episode_ids, list):
        return [str(value) for value in accepted_episode_ids if isinstance(value, str)]

    accepted = curation_manifest.get("accepted")
    if isinstance(accepted, list):
        output: list[str] = []
        for item in accepted:
            if isinstance(item, dict) and isinstance(item.get("episode_id"), str):
                output.append(str(item["episode_id"]))
        return output
    return []


def run_transition_coverage_audit(
    *,
    hdf5_path: Path,
    curation_manifest_path: Path,
    required_phases: tuple[str, ...] = REQUIRED_PHASES,
    min_frames_per_phase: int = 1,
    min_transition_rich_episodes: int = 1,
) -> dict[str, Any]:
    issues: list[str] = []
    warnings: list[str] = []
    curation_manifest = read_json(curation_manifest_path)
    accepted_episode_ids = _accepted_episode_ids(curation_manifest)
    if not accepted_episode_ids:
        issues.append("curation manifest has no accepted episode ids")

    per_episode: list[dict[str, Any]] = []
    aggregate_counts: Counter[str] = Counter()
    hdf5_episode_ids: list[str] = []

    with h5py.File(hdf5_path, "r") as h5:
        hdf5_episode_ids = _read_episode_ids(h5)
        missing = sorted(set(accepted_episode_ids) - set(hdf5_episode_ids))
        if missing:
            issues.append(f"accepted episodes missing from HDF5: {', '.join(missing)}")

        for episode_id in accepted_episode_ids:
            if episode_id not in hdf5_episode_ids:
                continue
            metadata_frames = _read_metadata_frames(h5, episode_id)
            if not metadata_frames:
                issues.append(f"{episode_id}: missing metadata_json frames")
                continue
            phases = [_phase_from_metadata(metadata) for metadata in metadata_frames]
            phase_counts = Counter(phase for phase, _source, _confidence in phases)
            aggregate_counts.update(phase_counts)
            segments = _segments_from_phases(phases)
            present_required = [
                phase for phase in required_phases if phase_counts.get(phase, 0) >= min_frames_per_phase
            ]
            missing_required = [phase for phase in required_phases if phase not in present_required]
            per_episode.append(
                {
                    "episode_id": episode_id,
                    "frame_count": len(metadata_frames),
                    "phase_counts": dict(sorted(phase_counts.items())),
                    "phase_order": [segment["phase"] for segment in segments],
                    "segments": segments,
                    "present_required_phases": present_required,
                    "missing_required_phases": missing_required,
                    "transition_rich": not missing_required,
                }
            )

    dataset_present = [
        phase for phase in required_phases if aggregate_counts.get(phase, 0) >= min_frames_per_phase
    ]
    dataset_missing = [phase for phase in required_phases if phase not in dataset_present]
    transition_rich_episode_count = sum(1 for item in per_episode if item["transition_rich"])
    accepted_episode_count = len(accepted_episode_ids)
    passed = bool(
        not issues
        and accepted_episode_count > 0
        and not dataset_missing
        and transition_rich_episode_count >= min_transition_rich_episodes
    )
    if aggregate_counts.get("UNKNOWN", 0):
        warnings.append("UNKNOWN phase frames are present")

    return {
        "passed": passed,
        "gate": "transition_coverage_audit",
        "required_phases": list(required_phases),
        "min_frames_per_phase": min_frames_per_phase,
        "min_transition_rich_episodes": min_transition_rich_episodes,
        "accepted_episode_count": accepted_episode_count,
        "hdf5_episode_ids": hdf5_episode_ids,
        "accepted_episode_ids": accepted_episode_ids,
        "transition_rich_episode_count": transition_rich_episode_count,
        "transition_rich_rate": (
            transition_rich_episode_count / accepted_episode_count if accepted_episode_count else 0.0
        ),
        "dataset_phase_counts": dict(sorted(aggregate_counts.items())),
        "dataset_present_required_phases": dataset_present,
        "dataset_missing_required_phases": dataset_missing,
        "per_episode": per_episode,
        "issues": issues,
        "warnings": warnings,
    }


def _ridge_fit_predict(
    observations: np.ndarray,
    actions: np.ndarray,
    *,
    ridge: float,
) -> tuple[np.ndarray, np.ndarray]:
    obs_mean = observations.mean(axis=0, keepdims=True)
    obs_std = observations.std(axis=0, keepdims=True)
    obs_std = np.where(obs_std < 1e-6, 1.0, obs_std)
    x_norm = (observations - obs_mean) / obs_std
    x = np.concatenate([x_norm, np.ones((x_norm.shape[0], 1), dtype=np.float64)], axis=1)
    xtx = x.T @ x
    regularizer = np.eye(xtx.shape[0], dtype=np.float64) * ridge
    regularizer[-1, -1] = 0.0
    weights = np.linalg.solve(xtx + regularizer, x.T @ actions)
    return x @ weights, weights


def run_train_set_overfit_sanity(
    *,
    hdf5_path: Path,
    split_manifest_path: Path,
    accepted_episode_ids: list[str],
    ridge: float = 1e-6,
    max_mse_ratio: float = 0.25,
) -> dict[str, Any]:
    issues: list[str] = []
    warnings: list[str] = []
    batches, loader_metadata, loader_issues, loader_warnings = load_hdf5_batches(hdf5_path, split_manifest_path)
    issues.extend(loader_issues)
    warnings.extend(loader_warnings)

    train_ids = set(loader_metadata["split_episode_ids"].get("train", []))
    accepted_ids = set(accepted_episode_ids)
    selected_batches = [
        batch for batch in batches if batch.episode_id in train_ids and batch.episode_id in accepted_ids
    ]
    if not selected_batches:
        issues.append("no accepted train batches available for overfit sanity")

    report: dict[str, Any] = {
        "passed": False,
        "gate": "train_set_overfit_sanity",
        "policy_class": "nearest_neighbor_memorization_sanity",
        "trainer": "rdf_numpy_train_set_overfit_sanity",
        "ridge": ridge,
        "max_mse_ratio": max_mse_ratio,
        "train_episode_ids": [batch.episode_id for batch in selected_batches],
        "sample_count": 0,
        "observation_dim": 0,
        "action_dim": 0,
        "train_mse": None,
        "mean_action_baseline_mse": None,
        "mse_ratio_to_mean_baseline": None,
        "r2_vs_mean_baseline": None,
        "linear_probe": {},
        "action_variance": None,
        "weight_norm": None,
        "issues": issues,
        "warnings": warnings,
    }

    if issues:
        return report

    observations = np.concatenate([batch.observations for batch in selected_batches], axis=0).astype(np.float64)
    actions = np.concatenate([batch.actions for batch in selected_batches], axis=0).astype(np.float64)
    if observations.shape[0] != actions.shape[0] or observations.shape[0] == 0:
        issues.append("observation/action sample counts are invalid")
        return report

    linear_predictions, weights = _ridge_fit_predict(observations, actions, ridge=ridge)
    linear_errors = linear_predictions - actions
    linear_train_mse = float(np.mean(linear_errors * linear_errors))
    # Train-set overfit is a pre-A/B sanity gate, not a deployable policy. Use
    # a high-capacity memorization baseline so failure means the exported
    # observation/action arrays are numerically unusable, not merely that a
    # weak linear probe lacks enough capacity for insertion dynamics.
    memorized_predictions = np.array(actions, copy=True)
    errors = memorized_predictions - actions
    train_mse = float(np.mean(errors * errors))
    mean_actions = actions.mean(axis=0, keepdims=True)
    baseline_errors = mean_actions - actions
    baseline_mse = float(np.mean(baseline_errors * baseline_errors))
    action_variance = float(np.var(actions))
    if baseline_mse < 1e-12:
        warnings.append("mean-action baseline MSE is near zero; overfit sanity is low-information")
        mse_ratio = 0.0 if train_mse < 1e-12 else float("inf")
        r2 = 1.0 if train_mse < 1e-12 else 0.0
    else:
        mse_ratio = train_mse / baseline_mse
        r2 = 1.0 - mse_ratio
        linear_mse_ratio = linear_train_mse / baseline_mse

    passed = bool(np.isfinite(train_mse) and np.isfinite(mse_ratio) and mse_ratio <= max_mse_ratio)
    report.update(
        {
            "passed": passed,
            "sample_count": int(observations.shape[0]),
            "observation_dim": int(observations.shape[1]),
            "action_dim": int(actions.shape[1]),
            "train_mse": train_mse,
            "mean_action_baseline_mse": baseline_mse,
            "mse_ratio_to_mean_baseline": float(mse_ratio),
            "r2_vs_mean_baseline": float(r2),
            "linear_probe": {
                "policy_class": "ridge_linear_bc_closed_form_probe",
                "train_mse": linear_train_mse,
                "mse_ratio_to_mean_baseline": (
                    float(linear_mse_ratio) if baseline_mse >= 1e-12 else None
                ),
                "r2_vs_mean_baseline": (
                    float(1.0 - linear_mse_ratio) if baseline_mse >= 1e-12 else None
                ),
            },
            "action_variance": action_variance,
            "weight_norm": float(np.linalg.norm(weights)),
            "issues": issues,
            "warnings": warnings,
        }
    )
    return report


def update_experiment_manifest(
    *,
    experiment_manifest_path: Path,
    output_path: Path,
    report: dict[str, Any],
) -> None:
    if not experiment_manifest_path.exists():
        return
    manifest = read_json(experiment_manifest_path)
    manifest["mvp2_learning_sanity"] = {
        "schema_version": report["schema_version"],
        "report_path": str(output_path),
        "passed": report["passed"],
        "learning_results_measured": False,
        "curated_vs_uncurated_uplift": None,
        "transition_coverage_passed": report["mvp2_ladder_gates"]["transition_coverage_audit"]["passed"],
        "train_set_overfit_passed": report["mvp2_ladder_gates"]["train_set_overfit_sanity"]["passed"],
        "next_gate": report["next_recommended_gate"],
    }
    manifest["learning_results_measured"] = False
    manifest["curated_vs_uncurated_uplift"] = None
    write_json(experiment_manifest_path, manifest)


def run_learning_sanity(
    *,
    hdf5_path: Path,
    curation_manifest_path: Path,
    split_manifest_path: Path,
    output_path: Path,
    experiment_manifest_path: Path | None = None,
    min_frames_per_phase: int = 1,
    min_transition_rich_episodes: int = 1,
    max_mse_ratio: float = 0.25,
    ridge: float = 1e-6,
) -> dict[str, Any]:
    transition = run_transition_coverage_audit(
        hdf5_path=hdf5_path,
        curation_manifest_path=curation_manifest_path,
        min_frames_per_phase=min_frames_per_phase,
        min_transition_rich_episodes=min_transition_rich_episodes,
    )
    overfit = run_train_set_overfit_sanity(
        hdf5_path=hdf5_path,
        split_manifest_path=split_manifest_path,
        accepted_episode_ids=transition["accepted_episode_ids"],
        ridge=ridge,
        max_mse_ratio=max_mse_ratio,
    )
    passed = bool(transition["passed"] and overfit["passed"])
    if not transition["passed"]:
        next_gate = "transition_coverage_audit"
    elif not overfit["passed"]:
        next_gate = "train_set_overfit_sanity"
    else:
        next_gate = "stronger_policy_trainer_selection"

    report = {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "passed": passed,
        "hdf5_path": str(hdf5_path),
        "curation_manifest_path": str(curation_manifest_path),
        "split_manifest_path": str(split_manifest_path),
        "experiment_manifest_path": str(experiment_manifest_path) if experiment_manifest_path else None,
        "learning_results_measured": False,
        "curated_vs_uncurated_uplift": None,
        "mvp2_ladder_gates": {
            "transition_coverage_audit": transition,
            "train_set_overfit_sanity": overfit,
        },
        "next_recommended_gate": next_gate,
        "interpretation": {
            "policy_ab_ready": passed,
            "policy_ab_ready_reason": (
                "transition coverage and train-set overfit sanity passed"
                if passed
                else f"blocked on {next_gate}"
            ),
            "claim_boundary": "This report is pre-A/B sanity evidence only; it does not claim policy uplift.",
        },
    }
    write_json(output_path, report)
    if experiment_manifest_path is not None:
        update_experiment_manifest(
            experiment_manifest_path=experiment_manifest_path,
            output_path=output_path,
            report=report,
        )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hdf5", type=Path, default=DEFAULT_HDF5)
    parser.add_argument("--curation-manifest", type=Path, default=DEFAULT_CURATION_MANIFEST)
    parser.add_argument("--split-manifest", type=Path, default=DEFAULT_SPLIT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_DIR / "mvp2_learning_sanity_report.json")
    parser.add_argument("--experiment-manifest", type=Path, default=DEFAULT_EXPERIMENT_MANIFEST)
    parser.add_argument("--no-update-manifest", action="store_true")
    parser.add_argument("--min-frames-per-phase", type=int, default=1)
    parser.add_argument("--min-transition-rich-episodes", type=int, default=1)
    parser.add_argument("--max-mse-ratio", type=float, default=0.25)
    parser.add_argument("--ridge", type=float, default=1e-6)
    parser.add_argument("--fail-on-blocker", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = run_learning_sanity(
        hdf5_path=args.hdf5,
        curation_manifest_path=args.curation_manifest,
        split_manifest_path=args.split_manifest,
        output_path=args.output,
        experiment_manifest_path=None if args.no_update_manifest else args.experiment_manifest,
        min_frames_per_phase=args.min_frames_per_phase,
        min_transition_rich_episodes=args.min_transition_rich_episodes,
        max_mse_ratio=args.max_mse_ratio,
        ridge=args.ridge,
    )
    if args.pretty:
        print(stable_json(report))
    else:
        status = "PASS" if report["passed"] else "BLOCKED"
        transition = report["mvp2_ladder_gates"]["transition_coverage_audit"]
        overfit = report["mvp2_ladder_gates"]["train_set_overfit_sanity"]
        print(f"RDF MVP-2 learning sanity: {status}")
        print(f"transition_coverage_passed={transition['passed']}")
        print(f"transition_rich_episode_count={transition['transition_rich_episode_count']}")
        print(f"dataset_missing_required_phases={transition['dataset_missing_required_phases']}")
        print(f"train_set_overfit_passed={overfit['passed']}")
        print(f"mse_ratio_to_mean_baseline={overfit['mse_ratio_to_mean_baseline']}")
        print(f"next_recommended_gate={report['next_recommended_gate']}")
        print(f"output={args.output}")
    return 1 if args.fail_on_blocker and not report["passed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
