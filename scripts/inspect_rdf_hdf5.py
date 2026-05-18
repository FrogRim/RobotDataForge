#!/usr/bin/env python3
"""Inspect an offline Robot Data Forge HDF5 export."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import h5py
import numpy as np


TOP_LEVEL_GROUPS = ("episodes", "observations", "states", "actions", "timestamps", "metadata", "evaluation")


def stable_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _decode(value: Any) -> Any:
    if isinstance(value, bytes):
        return value.decode("utf-8")
    if isinstance(value, np.bytes_):
        return bytes(value).decode("utf-8")
    return value


def read_json_dataset(dataset: h5py.Dataset) -> dict[str, Any]:
    value = _decode(dataset[()])
    if not value:
        return {}
    try:
        data = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def read_episode_ids(h5: h5py.File) -> list[str]:
    episodes = h5.get("episodes")
    if not isinstance(episodes, h5py.Group):
        return []
    if "episode_ids" in episodes:
        return [str(_decode(value)) for value in episodes["episode_ids"][()]]
    return sorted(key for key, value in episodes.items() if isinstance(value, h5py.Group))


def numeric_quality(dataset: h5py.Dataset) -> dict[str, int]:
    if not np.issubdtype(dataset.dtype, np.number):
        return {"nan_count": 0, "inf_count": 0}
    data = dataset[()]
    return {
        "nan_count": int(np.isnan(data).sum()) if np.issubdtype(data.dtype, np.floating) else 0,
        "inf_count": int(np.isinf(data).sum()) if np.issubdtype(data.dtype, np.floating) else 0,
    }


def action_jump_max(action: np.ndarray) -> float | None:
    if action.ndim != 2 or action.shape[0] < 2 or action.shape[1] == 0:
        return None
    finite_rows = action[np.isfinite(action).all(axis=1)]
    if finite_rows.shape[0] < 2:
        return None
    jumps = np.linalg.norm(np.diff(finite_rows, axis=0), axis=1)
    if jumps.size == 0:
        return None
    return float(np.max(jumps))


def timestamp_stats(values: np.ndarray) -> dict[str, Any]:
    if values.size == 0:
        return {
            "timestamp_count": 0,
            "timestamp_monotonic": True,
            "average_frame_interval": None,
            "frame_interval_jitter": None,
        }
    diffs = np.diff(values)
    if diffs.size == 0:
        average = None
        jitter = None
    else:
        average_value = float(np.mean(diffs))
        average = average_value
        jitter = float(np.max(np.abs(diffs - average_value)))
    return {
        "timestamp_count": int(values.size),
        "timestamp_monotonic": bool(np.all(diffs >= 0.0)) if diffs.size else True,
        "average_frame_interval": average,
        "frame_interval_jitter": jitter,
    }


def _group_fields(h5: h5py.File, group_name: str, episode_id: str) -> list[str]:
    group = h5.get(group_name)
    if not isinstance(group, h5py.Group):
        return []
    episode_group = group.get(episode_id)
    if not isinstance(episode_group, h5py.Group):
        return []
    return sorted(episode_group.keys())


def _numeric_dataset_reports(group: h5py.Group, prefix: str) -> dict[str, dict[str, int]]:
    reports: dict[str, dict[str, int]] = {}
    for key, value in group.items():
        path = f"{prefix}/{key}"
        if isinstance(value, h5py.Dataset):
            if np.issubdtype(value.dtype, np.number):
                reports[path] = numeric_quality(value)
        elif isinstance(value, h5py.Group):
            reports.update(_numeric_dataset_reports(value, path))
    return reports


def inspect_hdf5(path: Path) -> dict[str, Any]:
    warnings: list[str] = []
    issues: list[str] = []
    report: dict[str, Any] = {
        "path": str(path),
        "schema_version": None,
        "episode_count": 0,
        "episode_statuses": {},
        "episodes": {},
        "missing_fields": [],
        "warnings": warnings,
        "issues": issues,
    }

    with h5py.File(path, "r") as h5:
        report["schema_version"] = _decode(h5.attrs.get("schema_version"))
        missing_top = [name for name in TOP_LEVEL_GROUPS if name not in h5]
        if missing_top:
            issues.append(f"missing top-level groups: {', '.join(missing_top)}")
            report["missing_fields"].extend(f"/{name}" for name in missing_top)

        episode_ids = read_episode_ids(h5)
        report["episode_count"] = len(episode_ids)

        for episode_id in episode_ids:
            episode_report: dict[str, Any] = {
                "observation_fields": _group_fields(h5, "observations", episode_id),
                "state_fields": _group_fields(h5, "states", episode_id),
                "action_fields": _group_fields(h5, "actions", episode_id),
                "action_dimensions": {},
                "timestamp_count": 0,
                "timestamp_monotonic": None,
                "average_frame_interval": None,
                "frame_interval_jitter": None,
                "retargeting_action_jump_max": None,
                "tracking_loss_available": False,
                "evaluation_metrics_available": False,
                "evaluation_metric_keys": [],
                "lifecycle_metadata_available": False,
                "nan_inf": {},
            }

            episode_group = h5.get(f"episodes/{episode_id}")
            status = None
            if isinstance(episode_group, h5py.Group):
                status = _decode(episode_group.attrs.get("episode_status"))

            metadata_group = h5.get(f"metadata/{episode_id}")
            lifecycle = {}
            if isinstance(metadata_group, h5py.Group) and "lifecycle_json" in metadata_group:
                lifecycle = read_json_dataset(metadata_group["lifecycle_json"])
                episode_report["lifecycle_metadata_available"] = bool(lifecycle)
                status = status or lifecycle.get("episode_status")
            else:
                warnings.append(f"{episode_id}: lifecycle metadata missing")
                report["missing_fields"].append(f"/metadata/{episode_id}/lifecycle_json")

            status = str(status or "unknown")
            episode_report["episode_status"] = status
            report["episode_statuses"][status] = report["episode_statuses"].get(status, 0) + 1

            actions_group = h5.get(f"actions/{episode_id}")
            if isinstance(actions_group, h5py.Group):
                for field_name, dataset in actions_group.items():
                    if isinstance(dataset, h5py.Dataset) and np.issubdtype(dataset.dtype, np.number):
                        episode_report["action_dimensions"][field_name] = dataset.shape[1] if dataset.ndim == 2 else dataset.shape
                retargeted = actions_group.get("retargeted_robot_action")
                if isinstance(retargeted, h5py.Dataset):
                    episode_report["retargeting_action_jump_max"] = action_jump_max(retargeted[()])
                else:
                    warnings.append(f"{episode_id}: retargeted_robot_action missing")
                    report["missing_fields"].append(f"/actions/{episode_id}/retargeted_robot_action")
            else:
                issues.append(f"{episode_id}: actions group missing")
                report["missing_fields"].append(f"/actions/{episode_id}")

            timestamps = h5.get(f"timestamps/{episode_id}/t")
            if isinstance(timestamps, h5py.Dataset):
                episode_report.update(timestamp_stats(timestamps[()]))
            else:
                issues.append(f"{episode_id}: timestamps/t missing")
                report["missing_fields"].append(f"/timestamps/{episode_id}/t")

            evaluation_group = h5.get(f"evaluation/{episode_id}")
            metrics = {}
            if isinstance(evaluation_group, h5py.Group) and "metrics_json" in evaluation_group:
                metrics = read_json_dataset(evaluation_group["metrics_json"])
                episode_report["evaluation_metrics_available"] = bool(metrics)
                episode_report["evaluation_metric_keys"] = sorted(metrics.keys())
                episode_report["tracking_loss_available"] = "tracking_loss_after_warmup" in metrics or "tracking_loss_rate" in metrics
                if not metrics:
                    warnings.append(f"{episode_id}: evaluation metrics empty")
            else:
                warnings.append(f"{episode_id}: evaluation metrics missing")
                report["missing_fields"].append(f"/evaluation/{episode_id}/metrics_json")

            for group_name in ("observations", "states", "actions", "timestamps"):
                group = h5.get(f"{group_name}/{episode_id}")
                if isinstance(group, h5py.Group):
                    episode_report["nan_inf"].update(_numeric_dataset_reports(group, f"/{group_name}/{episode_id}"))

            for dataset_path, counts in episode_report["nan_inf"].items():
                if counts["nan_count"] or counts["inf_count"]:
                    warnings.append(
                        f"{episode_id}: {dataset_path} has nan={counts['nan_count']} inf={counts['inf_count']}"
                    )

            if episode_report["timestamp_monotonic"] is False:
                issues.append(f"{episode_id}: timestamps are not monotonic")

            report["episodes"][episode_id] = episode_report

    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect an RDF HDF5 export.")
    parser.add_argument("path", type=Path, help="Path to an RDF HDF5 export.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = inspect_hdf5(args.path)
    if args.pretty:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(stable_json(report))
    return 1 if report["issues"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
