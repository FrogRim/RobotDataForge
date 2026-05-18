#!/usr/bin/env python3
"""Run an MVP-1C curated-vs-uncurated policy-uplift smoke experiment.

This script creates a repeatable measurement artifact for the MVP-1C loop, but
the default evidence tier is an offline proxy. It intentionally does not mark
full MVP-1C proof as achieved. Full proof requires real held-out policy
evaluation, not this state/action prediction smoke.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "rdf_mvp1c_policy_uplift_smoke_v0.1.0"
DEFAULT_READINESS_DIR = ROOT / "storage" / "mvp1_readiness"
REGULARIZATION_GRID = (1e-6, 1e-4, 1e-2, 1e-1, 1.0, 10.0, 100.0)


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


def _flatten_numeric(value: Any) -> list[float]:
    if value is None or isinstance(value, bool):
        return []
    if isinstance(value, (int, float)):
        return [float(value)]
    if isinstance(value, (list, tuple)):
        out: list[float] = []
        for item in value:
            out.extend(_flatten_numeric(item))
        return out
    return []


def _observation_vector(frame: dict[str, Any]) -> list[float]:
    metadata = frame.get("metadata") if isinstance(frame.get("metadata"), dict) else {}
    raw_xr = metadata.get("raw_xr") if isinstance(metadata.get("raw_xr"), dict) else {}
    aligned_xr = metadata.get("aligned_xr") if isinstance(metadata.get("aligned_xr"), dict) else {}
    vector: list[float] = []
    vector.extend(_flatten_numeric(frame.get("end_effector_position"))[:3])
    vector.extend(_flatten_numeric(frame.get("object_position"))[:3])
    vector.extend(_flatten_numeric(raw_xr.get("right_wrist_pose"))[:7])
    vector.extend(_flatten_numeric(aligned_xr.get("right_wrist_pose"))[:7])
    return vector


def _action_vector(frame: dict[str, Any]) -> list[float]:
    action = frame.get("action")
    if isinstance(action, dict):
        retargeted = action.get("retargeted_robot_action")
        if isinstance(retargeted, dict):
            command = _flatten_numeric(retargeted.get("command"))
            if command:
                return command
        applied = _flatten_numeric(action.get("applied"))
        if applied:
            return applied
        raw = _flatten_numeric(action.get("raw"))
        if raw:
            return raw
    return _flatten_numeric(action)


def _load_trajectories(trajectory_dir: Path) -> dict[str, dict[str, Any]]:
    trajectories: dict[str, dict[str, Any]] = {}
    for path in sorted(trajectory_dir.glob("*.json")):
        trajectory = read_json(path)
        episode_id = trajectory.get("episode_id")
        if isinstance(episode_id, str):
            trajectories[episode_id] = trajectory
    return trajectories


def _samples_for_episode_ids(
    trajectories: dict[str, dict[str, Any]],
    episode_ids: list[str],
) -> tuple[np.ndarray, np.ndarray, list[str]]:
    observations: list[list[float]] = []
    actions: list[list[float]] = []
    missing: list[str] = []
    for episode_id in episode_ids:
        trajectory = trajectories.get(episode_id)
        if trajectory is None:
            missing.append(episode_id)
            continue
        for frame in trajectory.get("frames") or []:
            if not isinstance(frame, dict):
                continue
            obs = _observation_vector(frame)
            act = _action_vector(frame)
            if obs and act:
                observations.append(obs)
                actions.append(act)
    return _matrix(observations), _matrix(actions), missing


def _matrix(rows: list[list[float]]) -> np.ndarray:
    width = max((len(row) for row in rows), default=0)
    data = np.full((len(rows), width), np.nan, dtype=np.float64)
    for row_index, row in enumerate(rows):
        if row:
            data[row_index, : len(row)] = np.asarray(row, dtype=np.float64)
    return data


def _fit_ridge(observations: np.ndarray, actions: np.ndarray, regularization: float) -> dict[str, Any]:
    mean = observations.mean(axis=0, keepdims=True)
    std = observations.std(axis=0, keepdims=True)
    std = np.where(std < 1e-6, 1.0, std)
    normalized = (observations - mean) / std
    design = np.concatenate([normalized, np.ones((normalized.shape[0], 1), dtype=np.float64)], axis=1)
    ridge = regularization * np.eye(design.shape[1], dtype=np.float64)
    weights = np.linalg.solve(design.T @ design + ridge, design.T @ actions)
    return {
        "mean": mean,
        "std": std,
        "weights": weights,
        "regularization": regularization,
    }


def _predict(model: dict[str, Any], observations: np.ndarray) -> np.ndarray:
    normalized = (observations - model["mean"]) / model["std"]
    design = np.concatenate([normalized, np.ones((normalized.shape[0], 1), dtype=np.float64)], axis=1)
    return design @ model["weights"]


def _mse(model: dict[str, Any], observations: np.ndarray, actions: np.ndarray) -> float:
    error = _predict(model, observations) - actions
    return float(np.mean(error * error))


def _score_from_mse(mse: float) -> float:
    return float(1.0 / (1.0 + mse))


def _train_and_evaluate(
    *,
    name: str,
    trajectories: dict[str, dict[str, Any]],
    train_ids: list[str],
    validation_ids: list[str],
    test_ids: list[str],
) -> tuple[dict[str, Any], list[str]]:
    issues: list[str] = []
    train_x, train_y, missing_train = _samples_for_episode_ids(trajectories, train_ids)
    val_x, val_y, missing_val = _samples_for_episode_ids(trajectories, validation_ids)
    test_x, test_y, missing_test = _samples_for_episode_ids(trajectories, test_ids)
    for label, missing in (("train", missing_train), ("validation", missing_val), ("test", missing_test)):
        if missing:
            issues.append(f"{name}: missing {label} episodes: {', '.join(missing)}")
    for label, x, y in (("train", train_x, train_y), ("validation", val_x, val_y), ("test", test_x, test_y)):
        if x.size == 0 or y.size == 0:
            issues.append(f"{name}: {label} samples are empty")
        elif x.shape[0] != y.shape[0]:
            issues.append(f"{name}: {label} observation/action row mismatch")
        elif not np.isfinite(x).all() or not np.isfinite(y).all():
            issues.append(f"{name}: {label} contains non-finite values")
    if issues:
        return {
            "name": name,
            "train_episode_ids": train_ids,
            "validation_episode_ids": validation_ids,
            "test_episode_ids": test_ids,
            "sample_count": {"train": int(train_x.shape[0]), "validation": int(val_x.shape[0]), "test": int(test_x.shape[0])},
            "validation_mse": None,
            "test_mse": None,
            "test_score": None,
            "selected_regularization": None,
        }, issues

    best: tuple[float, float, float, dict[str, Any]] | None = None
    for regularization in REGULARIZATION_GRID:
        model = _fit_ridge(train_x, train_y, regularization)
        validation_mse = _mse(model, val_x, val_y) if val_x.size else _mse(model, train_x, train_y)
        test_mse = _mse(model, test_x, test_y)
        if best is None or validation_mse < best[0]:
            best = (validation_mse, test_mse, regularization, model)
    assert best is not None
    validation_mse, test_mse, regularization, model = best
    return {
        "name": name,
        "policy_class": "linear_bc_ridge_state_action_proxy",
        "trainer": "rdf_numpy_ridge_bc_proxy",
        "train_episode_ids": train_ids,
        "validation_episode_ids": validation_ids,
        "test_episode_ids": test_ids,
        "sample_count": {"train": int(train_x.shape[0]), "validation": int(val_x.shape[0]), "test": int(test_x.shape[0])},
        "observation_dim": int(train_x.shape[1]),
        "action_dim": int(train_y.shape[1]),
        "selected_regularization": regularization,
        "validation_mse": validation_mse,
        "test_mse": test_mse,
        "test_score": _score_from_mse(test_mse),
        "weight_norm": float(np.linalg.norm(model["weights"])),
    }, []


def run_policy_uplift_smoke(
    *,
    readiness_dir: Path,
    output_path: Path,
    experiment_manifest_path: Path,
    update_manifest: bool = True,
) -> dict[str, Any]:
    manifest = read_json(experiment_manifest_path)
    split_manifest = read_json(readiness_dir / "split_manifest.json")
    splits = split_manifest.get("splits") if isinstance(split_manifest.get("splits"), dict) else {}
    train_ids = [str(value) for value in splits.get("train", [])]
    validation_ids = [str(value) for value in splits.get("validation", [])]
    test_ids = [str(value) for value in splits.get("test", [])]
    reserved_ids = set(validation_ids + test_ids)

    baseline_a_ids = [str(value) for value in manifest.get("baseline_a_uncurated_success_lifecycle_episode_ids", [])]
    baseline_b_ids = [str(value) for value in manifest.get("baseline_b_curated_accepted_episode_ids", [])]
    uncurated_train_ids = [episode_id for episode_id in baseline_a_ids if episode_id not in reserved_ids]
    curated_train_ids = [episode_id for episode_id in train_ids if episode_id in baseline_b_ids]

    trajectories = _load_trajectories(readiness_dir / "raw" / "trajectories")
    baseline_report, baseline_issues = _train_and_evaluate(
        name="uncurated_success_lifecycle",
        trajectories=trajectories,
        train_ids=uncurated_train_ids,
        validation_ids=validation_ids,
        test_ids=test_ids,
    )
    curated_report, curated_issues = _train_and_evaluate(
        name="curated_accepted",
        trajectories=trajectories,
        train_ids=curated_train_ids,
        validation_ids=validation_ids,
        test_ids=test_ids,
    )
    issues = baseline_issues + curated_issues

    baseline_score = baseline_report.get("test_score")
    curated_score = curated_report.get("test_score")
    proxy_delta = None
    proxy_relative_uplift = None
    proxy_positive = False
    if isinstance(baseline_score, (int, float)) and isinstance(curated_score, (int, float)):
        proxy_delta = float(curated_score - baseline_score)
        proxy_relative_uplift = float(proxy_delta / baseline_score) if baseline_score else None
        proxy_positive = proxy_delta > 0.0

    report = {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "passed": not issues,
        "proof_eligible": False,
        "evidence_tier": "offline_proxy_smoke",
        "primary_metric": "action_prediction_score",
        "metric_direction": "higher_is_better",
        "policy_class": "linear_bc_ridge_state_action_proxy",
        "trainer": "rdf_numpy_ridge_bc_proxy",
        "readiness_dir": str(readiness_dir),
        "experiment_manifest_path": str(experiment_manifest_path),
        "baseline": baseline_report,
        "candidate": curated_report,
        "curated_vs_uncurated_proxy_delta": proxy_delta,
        "curated_vs_uncurated_proxy_relative_uplift": proxy_relative_uplift,
        "proxy_uplift_positive": proxy_positive,
        "learning_results_measured": False,
        "curated_vs_uncurated_uplift": None,
        "issues": issues,
        "warnings": [
            "This is an offline action-prediction proxy, not held-out policy rollout evidence.",
            "Do not use this report to claim full MVP-1C customer/investor proof.",
        ],
    }
    write_json(output_path, report)

    if update_manifest:
        manifest["policy_uplift_smoke"] = {
            "schema_version": SCHEMA_VERSION,
            "report_path": str(output_path),
            "passed": report["passed"],
            "proof_eligible": False,
            "evidence_tier": report["evidence_tier"],
            "primary_metric": report["primary_metric"],
            "baseline_test_score": baseline_score,
            "candidate_test_score": curated_score,
            "curated_vs_uncurated_proxy_delta": proxy_delta,
            "curated_vs_uncurated_proxy_relative_uplift": proxy_relative_uplift,
            "proxy_uplift_positive": proxy_positive,
        }
        manifest["learning_results_measured"] = False
        manifest["curated_vs_uncurated_uplift"] = None
        write_json(experiment_manifest_path, manifest)

    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--readiness-dir", type=Path, default=DEFAULT_READINESS_DIR)
    parser.add_argument(
        "--experiment-manifest",
        type=Path,
        default=DEFAULT_READINESS_DIR / "curated_vs_uncurated_experiment_manifest.json",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_READINESS_DIR / "policy_uplift_smoke_report.json")
    parser.add_argument("--no-update-manifest", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = run_policy_uplift_smoke(
        readiness_dir=args.readiness_dir,
        output_path=args.output,
        experiment_manifest_path=args.experiment_manifest,
        update_manifest=not args.no_update_manifest,
    )
    if args.pretty:
        print(stable_json(report))
    else:
        status = "PASS" if report["passed"] else "FAIL"
        print(f"RDF MVP-1C policy uplift smoke: {status}")
        print(f"evidence_tier={report['evidence_tier']}")
        print(f"proof_eligible={report['proof_eligible']}")
        print(f"proxy_delta={report['curated_vs_uncurated_proxy_delta']}")
        print(f"proxy_uplift_positive={report['proxy_uplift_positive']}")
        print(f"learning_results_measured={report['learning_results_measured']}")
        print(f"curated_vs_uncurated_uplift={report['curated_vs_uncurated_uplift']}")
        print(f"output={args.output}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
