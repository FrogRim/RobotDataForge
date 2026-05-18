#!/usr/bin/env python3
"""Run an MVP-1B trainer-loader smoke on an RDF HDF5 export.

This is not a policy uplift experiment. It only proves that the exported
dataset can be loaded into a deterministic behavior-cloning style trainer path
and can execute a dry-run plus one small optimization epoch without schema or
numeric failures.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

import h5py
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "rdf_mvp1_trainer_smoke_v0.1.0"
DEFAULT_READINESS_DIR = ROOT / "storage" / "mvp1_readiness"
OBSERVATION_FIELDS = (
    "end_effector_position",
    "object_position",
    "raw_xr_right_wrist_pose",
    "aligned_xr_right_wrist_pose",
)
ACTION_FIELD = "retargeted_robot_action"


@dataclass(frozen=True)
class EpisodeBatch:
    episode_id: str
    observations: np.ndarray
    actions: np.ndarray


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


def _matrix(h5: h5py.File, path: str) -> np.ndarray | None:
    dataset = h5.get(path)
    if not isinstance(dataset, h5py.Dataset):
        return None
    data = dataset[()]
    if not np.issubdtype(data.dtype, np.number):
        return None
    if data.ndim == 1:
        data = data.reshape(-1, 1)
    if data.ndim != 2:
        return None
    return np.asarray(data, dtype=np.float32)


def _finite_matrix(name: str, data: np.ndarray, issues: list[str]) -> bool:
    if data.size == 0:
        issues.append(f"{name} is empty")
        return False
    if not np.isfinite(data).all():
        issues.append(f"{name} contains non-finite values")
        return False
    return True


def _load_split_episode_ids(split_manifest_path: Path) -> dict[str, list[str]]:
    split_manifest = read_json(split_manifest_path)
    splits = split_manifest.get("splits")
    if not isinstance(splits, dict):
        return {}
    output: dict[str, list[str]] = {}
    for name, values in splits.items():
        if isinstance(values, list):
            output[str(name)] = [str(value) for value in values if isinstance(value, str)]
    return output


def load_hdf5_batches(
    hdf5_path: Path,
    split_manifest_path: Path,
) -> tuple[list[EpisodeBatch], dict[str, Any], list[str], list[str]]:
    issues: list[str] = []
    warnings: list[str] = []
    splits = _load_split_episode_ids(split_manifest_path)
    split_episode_ids = {
        episode_id
        for values in splits.values()
        for episode_id in values
    }

    batches: list[EpisodeBatch] = []
    with h5py.File(hdf5_path, "r") as h5:
        episode_ids = _read_episode_ids(h5)
        if not episode_ids:
            issues.append("HDF5 has no episode ids")
        missing_from_hdf5 = sorted(split_episode_ids - set(episode_ids))
        if missing_from_hdf5:
            issues.append(f"split references missing HDF5 episodes: {', '.join(missing_from_hdf5)}")

        for episode_id in episode_ids:
            obs_parts: list[np.ndarray] = []
            frame_count: int | None = None
            for field_name in OBSERVATION_FIELDS:
                matrix = _matrix(h5, f"observations/{episode_id}/{field_name}")
                if matrix is None:
                    issues.append(f"{episode_id}: missing numeric observation {field_name}")
                    continue
                if frame_count is None:
                    frame_count = matrix.shape[0]
                elif matrix.shape[0] != frame_count:
                    issues.append(f"{episode_id}: observation frame count mismatch for {field_name}")
                obs_parts.append(matrix)

            actions = _matrix(h5, f"actions/{episode_id}/{ACTION_FIELD}")
            if actions is None:
                issues.append(f"{episode_id}: missing numeric action {ACTION_FIELD}")
                continue
            if frame_count is None:
                frame_count = actions.shape[0]
            elif actions.shape[0] != frame_count:
                issues.append(f"{episode_id}: action frame count mismatch")
            if frame_count == 0:
                issues.append(f"{episode_id}: zero frames")
                continue

            timestamps = _matrix(h5, f"timestamps/{episode_id}/t")
            if timestamps is None:
                issues.append(f"{episode_id}: missing timestamps")
            elif timestamps.shape[0] != frame_count:
                issues.append(f"{episode_id}: timestamp frame count mismatch")
            elif not bool(np.all(np.diff(timestamps[:, 0]) >= 0.0)):
                issues.append(f"{episode_id}: timestamps not monotonic")

            if not obs_parts:
                continue
            observations = np.concatenate(obs_parts, axis=1)
            _finite_matrix(f"{episode_id}: observations", observations, issues)
            _finite_matrix(f"{episode_id}: actions", actions, issues)
            batches.append(EpisodeBatch(episode_id=episode_id, observations=observations, actions=actions))

    metadata = {
        "split_episode_ids": {name: values for name, values in sorted(splits.items())},
        "hdf5_episode_ids": [batch.episode_id for batch in batches],
        "observation_fields": list(OBSERVATION_FIELDS),
        "action_field": ACTION_FIELD,
    }
    return batches, metadata, issues, warnings


def _normalize(values: np.ndarray) -> tuple[np.ndarray, dict[str, Any]]:
    mean = values.mean(axis=0, keepdims=True)
    std = values.std(axis=0, keepdims=True)
    std = np.where(std < 1e-6, 1.0, std)
    return (values - mean) / std, {
        "mean_abs_max": float(np.max(np.abs(mean))) if mean.size else 0.0,
        "std_min": float(np.min(std)) if std.size else 0.0,
        "std_max": float(np.max(std)) if std.size else 0.0,
    }


def run_trainer_smoke(
    *,
    hdf5_path: Path,
    split_manifest_path: Path,
    output_path: Path,
    experiment_manifest_path: Path | None = None,
    learning_rate: float = 0.01,
) -> dict[str, Any]:
    batches, loader_metadata, issues, warnings = load_hdf5_batches(hdf5_path, split_manifest_path)

    train_ids = set(loader_metadata["split_episode_ids"].get("train", []))
    train_batches = [batch for batch in batches if batch.episode_id in train_ids]
    if not train_batches:
        issues.append("no train batches available")

    loader_smoke_passed = not issues and bool(batches)
    trainer_dry_run_passed = False
    one_epoch_smoke_passed = False
    trainer_report: dict[str, Any] = {
        "policy_class": "linear_bc_numpy_smoke",
        "trainer": "rdf_numpy_bc_trainer_smoke",
        "learning_rate": learning_rate,
        "train_episode_ids": [batch.episode_id for batch in train_batches],
        "batch_count": len(train_batches),
        "sample_count": 0,
        "observation_dim": 0,
        "action_dim": 0,
        "initial_loss": None,
        "final_loss": None,
        "loss_delta": None,
        "normalization": {},
    }

    if loader_smoke_passed and train_batches:
        observations = np.concatenate([batch.observations for batch in train_batches], axis=0).astype(np.float64)
        actions = np.concatenate([batch.actions for batch in train_batches], axis=0).astype(np.float64)
        if observations.shape[0] != actions.shape[0]:
            issues.append("train observation/action sample count mismatch")
        elif observations.shape[0] == 0 or observations.shape[1] == 0 or actions.shape[1] == 0:
            issues.append("train arrays have empty dimensions")
        else:
            x_norm, norm_stats = _normalize(observations)
            x = np.concatenate([x_norm, np.ones((x_norm.shape[0], 1), dtype=np.float64)], axis=1)
            y = actions
            weights = np.zeros((x.shape[1], y.shape[1]), dtype=np.float64)
            predictions = x @ weights
            error = predictions - y
            initial_loss = float(np.mean(error * error))
            gradient = (2.0 / x.shape[0]) * (x.T @ error)
            weights -= learning_rate * gradient
            final_error = (x @ weights) - y
            final_loss = float(np.mean(final_error * final_error))
            trainer_dry_run_passed = bool(np.isfinite(initial_loss) and np.isfinite(final_loss) and np.isfinite(gradient).all())
            one_epoch_smoke_passed = bool(trainer_dry_run_passed and final_loss <= initial_loss + 1e-9)
            if not trainer_dry_run_passed:
                issues.append("trainer dry-run produced non-finite values")
            if trainer_dry_run_passed and not one_epoch_smoke_passed:
                warnings.append("one epoch smoke did not reduce loss")
            trainer_report.update(
                {
                    "sample_count": int(x.shape[0]),
                    "observation_dim": int(observations.shape[1]),
                    "action_dim": int(actions.shape[1]),
                    "initial_loss": initial_loss,
                    "final_loss": final_loss,
                    "loss_delta": final_loss - initial_loss,
                    "normalization": norm_stats,
                    "gradient_norm": float(np.linalg.norm(gradient)),
                    "weight_norm": float(np.linalg.norm(weights)),
                }
            )

    report = {
        "schema_version": SCHEMA_VERSION,
        "passed": bool(loader_smoke_passed and (trainer_dry_run_passed or one_epoch_smoke_passed)),
        "created_at": datetime.now(UTC).isoformat(),
        "hdf5_path": str(hdf5_path),
        "split_manifest_path": str(split_manifest_path),
        "experiment_manifest_path": str(experiment_manifest_path) if experiment_manifest_path else None,
        "loader_smoke_passed": loader_smoke_passed,
        "trainer_dry_run_passed": trainer_dry_run_passed,
        "one_epoch_smoke_passed": one_epoch_smoke_passed,
        "learning_results_measured": False,
        "curated_vs_uncurated_uplift": None,
        "loader": loader_metadata,
        "trainer": trainer_report,
        "issues": issues,
        "warnings": warnings,
    }
    write_json(output_path, report)

    if experiment_manifest_path is not None:
        manifest = read_json(experiment_manifest_path)
        training_readiness = manifest.get("training_readiness")
        if not isinstance(training_readiness, dict):
            training_readiness = {}
        training_readiness.update(
            {
                "loader_smoke_passed": loader_smoke_passed,
                "trainer_dry_run_passed": trainer_dry_run_passed,
                "one_epoch_smoke_passed": one_epoch_smoke_passed,
                "policy_class": trainer_report["policy_class"],
                "trainer": trainer_report["trainer"],
                "report_path": str(output_path),
                "hdf5_path": str(hdf5_path),
                "split_manifest_path": str(split_manifest_path),
                "sample_count": trainer_report["sample_count"],
                "observation_dim": trainer_report["observation_dim"],
                "action_dim": trainer_report["action_dim"],
                "initial_loss": trainer_report["initial_loss"],
                "final_loss": trainer_report["final_loss"],
                "loss_delta": trainer_report["loss_delta"],
            }
        )
        manifest["training_readiness"] = training_readiness
        write_json(experiment_manifest_path, manifest)

    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hdf5", type=Path, default=DEFAULT_READINESS_DIR / "rdf_mvp1_curated_readiness.hdf5")
    parser.add_argument("--split-manifest", type=Path, default=DEFAULT_READINESS_DIR / "split_manifest.json")
    parser.add_argument(
        "--experiment-manifest",
        type=Path,
        default=DEFAULT_READINESS_DIR / "curated_vs_uncurated_experiment_manifest.json",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_READINESS_DIR / "trainer_smoke_report.json")
    parser.add_argument("--learning-rate", type=float, default=0.01)
    parser.add_argument("--no-update-manifest", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = run_trainer_smoke(
        hdf5_path=args.hdf5,
        split_manifest_path=args.split_manifest,
        output_path=args.output,
        experiment_manifest_path=None if args.no_update_manifest else args.experiment_manifest,
        learning_rate=args.learning_rate,
    )
    if args.pretty:
        print(stable_json(report))
    else:
        status = "PASS" if report["passed"] else "FAIL"
        print(f"RDF MVP-1 trainer smoke: {status}")
        print(f"loader_smoke_passed={report['loader_smoke_passed']}")
        print(f"trainer_dry_run_passed={report['trainer_dry_run_passed']}")
        print(f"one_epoch_smoke_passed={report['one_epoch_smoke_passed']}")
        print(f"output={args.output}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
