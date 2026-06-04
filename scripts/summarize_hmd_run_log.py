#!/usr/bin/env python3
"""Summarize the latest RDF HMD operator log and saved validation artifacts.

This script is intentionally read-only. It joins three evidence sources:

1. Terminal/operator log captured by `run_hmd_axis_debug.sh`.
2. Latest evaluator JSON under `storage/evaluations`.
3. Latest HMD motion mapping analysis JSON under `storage/hmd_motion_mapping`.

The output answers the operational question: can Gate A collection resume, or is
this still an input-quality/debug-only run?
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "rdf_hmd_run_log_summary_v0.1.0"
LOG_PATTERNS = (
    "AUTO_RECENTER_UNSTABLE_RIGHT_WRIST",
    "raw_wrist_spike_reacquire_pending",
    "raw_wrist_spike_reacquired",
    "raw_wrist_jump_warn",
    "TRACKING_LOSS",
    "RAW_WRIST_JUMP",
    "OPENXR_CREATE_INSTANCE_FAILED",
    "XR_SESSION_START",
)
INPUT_QUALITY_FAILURES = {"RAW_WRIST_JUMP", "TRACKING_LOSS"}


def _read_json(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.exists():
        return None
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    return value if isinstance(value, dict) else None


def _latest_file(root: Path, glob_pattern: str) -> Path | None:
    files = [path for path in root.glob(glob_pattern) if path.is_file()]
    if not files:
        return None
    return max(files, key=lambda path: path.stat().st_mtime)


def _count_log_patterns(log_file: Path | None) -> dict[str, int]:
    counts = {pattern: 0 for pattern in LOG_PATTERNS}
    if log_file is None or not log_file.exists():
        return counts
    text = log_file.read_text(encoding="utf-8", errors="replace")
    for pattern in LOG_PATTERNS:
        if pattern == "OPENXR_CREATE_INSTANCE_FAILED":
            counts[pattern] = text.count("xrCreateInstance failed")
        elif pattern == "XR_SESSION_START":
            counts[pattern] = text.count("XR session start")
        else:
            counts[pattern] = text.count(pattern)
    return counts


def _hypothesis_status(
    analysis: dict[str, Any] | None, hypothesis_id: str
) -> tuple[str | None, str | None]:
    if not analysis:
        return None, None
    trajectories = analysis.get("trajectories") or []
    if not trajectories or not isinstance(trajectories[0], dict):
        return None, None
    for item in trajectories[0].get("hypotheses") or []:
        if isinstance(item, dict) and item.get("id") == hypothesis_id:
            return item.get("status"), item.get("detail")
    return None, None


def _first_analysis_trajectory(analysis: dict[str, Any] | None) -> dict[str, Any]:
    if not analysis:
        return {}
    trajectories = analysis.get("trajectories") or []
    if trajectories and isinstance(trajectories[0], dict):
        return trajectories[0]
    return {}


def _classification(failure_reason: str | None) -> str:
    if failure_reason in INPUT_QUALITY_FAILURES:
        return "input_quality_failure"
    if failure_reason:
        return "task_or_other_failure"
    return "unknown_or_no_failure"


def build_summary(
    *,
    storage_root: Path,
    log_file: Path | None = None,
    trajectory_file: Path | None = None,
    evaluation_file: Path | None = None,
    analysis_file: Path | None = None,
    min_right_hand_tracked_rate: float = 0.95,
    min_xr_frame_valid_rate: float = 0.95,
) -> dict[str, Any]:
    storage_root = storage_root.resolve()
    log_file = log_file or _latest_file(storage_root, "logs/hmd_axis_debug/*.log")
    trajectory_file = trajectory_file or _latest_file(
        storage_root, "trajectories/*.json"
    )
    evaluation_file = evaluation_file or _latest_file(
        storage_root, "evaluations/*.json"
    )
    analysis_file = analysis_file or _latest_file(
        storage_root, "hmd_motion_mapping/latest_mapping_report.json"
    )
    if analysis_file is None:
        analysis_file = _latest_file(storage_root, "hmd_motion_mapping/*.json")

    evaluation = _read_json(evaluation_file)
    analysis = _read_json(analysis_file)
    trajectory = _read_json(trajectory_file)
    analysis_trajectory = _first_analysis_trajectory(analysis)

    metrics = (evaluation or {}).get("metrics") or {}
    raw_jump = metrics.get("raw_wrist_valid_to_valid_jump") or {}
    tracking_quality = analysis_trajectory.get("tracking_quality") or {}
    anchor_fallback = analysis_trajectory.get("anchor_fallback") or {}
    h9_status, h9_detail = _hypothesis_status(analysis, "H9")
    h13_status, h13_detail = _hypothesis_status(analysis, "H13")
    h14_status, h14_detail = _hypothesis_status(analysis, "H14")
    h15_status, h15_detail = _hypothesis_status(analysis, "H15")

    failure_reason = (evaluation or {}).get("failure_reason")
    failure_category = (evaluation or {}).get("failure_category")
    log_counts = _count_log_patterns(log_file)
    right_rate = tracking_quality.get("right_hand_tracked_rate")
    xr_rate = tracking_quality.get("xr_frame_valid_rate")

    reasons: list[str] = []
    if log_counts["AUTO_RECENTER_UNSTABLE_RIGHT_WRIST"] > 0:
        reasons.append("AUTO_RECENTER_UNSTABLE_RIGHT_WRIST_PRESENT")
    if log_counts["OPENXR_CREATE_INSTANCE_FAILED"] > 0:
        reasons.append("OPENXR_CREATE_INSTANCE_FAILED")
    if failure_reason == "RAW_WRIST_JUMP":
        reasons.append("RAW_WRIST_JUMP_INPUT_QUALITY_FAILURE")
    if failure_reason == "TRACKING_LOSS":
        reasons.append("TRACKING_LOSS_INPUT_QUALITY_FAILURE")
    if h13_status and h13_status != "PASS":
        reasons.append("H13_NOT_PASS")
    if isinstance(right_rate, int | float) and right_rate < min_right_hand_tracked_rate:
        reasons.append("RIGHT_HAND_TRACKED_RATE_LOW")
    if isinstance(xr_rate, int | float) and xr_rate < min_xr_frame_valid_rate:
        reasons.append("XR_FRAME_VALID_RATE_LOW")
    if evaluation_file is None or evaluation is None:
        reasons.append("NO_EVALUATION_ARTIFACT")
    if analysis_file is None or analysis is None:
        reasons.append("NO_HMD_MAPPING_ANALYSIS")

    axis_gain_reasons = {
        "AUTO_RECENTER_UNSTABLE_RIGHT_WRIST_PRESENT",
        "TRACKING_LOSS_INPUT_QUALITY_FAILURE",
        "H13_NOT_PASS",
        "RIGHT_HAND_TRACKED_RATE_LOW",
        "XR_FRAME_VALID_RATE_LOW",
    }
    axis_gain_allowed = not any(reason in axis_gain_reasons for reason in reasons)

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "storage_root": str(storage_root),
        "files": {
            "log": str(log_file) if log_file else None,
            "trajectory": str(trajectory_file) if trajectory_file else None,
            "evaluation": str(evaluation_file) if evaluation_file else None,
            "analysis": str(analysis_file) if analysis_file else None,
        },
        "log_counts": log_counts,
        "trajectory": {
            "id": (trajectory or {}).get("id"),
            "episode_id": (trajectory or {}).get("episode_id"),
            "frame_count": len((trajectory or {}).get("frames") or []),
            "episode_status": ((trajectory or {}).get("summary") or {}).get(
                "episode_status"
            ),
            "complete_reason": ((trajectory or {}).get("summary") or {}).get(
                "complete_reason"
            ),
            "warmup_dropped_frames": ((trajectory or {}).get("summary") or {}).get(
                "warmup_dropped_frames"
            ),
        },
        "evaluation": {
            "id": (evaluation or {}).get("id"),
            "episode_id": (evaluation or {}).get("episode_id"),
            "trajectory_id": (evaluation or {}).get("trajectory_id"),
            "success": (evaluation or {}).get("success"),
            "failure_reason": failure_reason,
            "failure_category": failure_category,
            "quality_score": (evaluation or {}).get("quality_score"),
            "tracking_loss_rate": metrics.get("tracking_loss_rate"),
            "tracking_loss_after_warmup": metrics.get("tracking_loss_after_warmup"),
            "raw_wrist_jump_fail": raw_jump.get("fail"),
            "raw_wrist_jump_threshold_m": raw_jump.get("threshold_m"),
            "raw_wrist_jump_max_m": raw_jump.get("max_m"),
            "raw_wrist_jump_count_over_threshold": raw_jump.get("count_over_threshold"),
            "raw_wrist_gate_state_counts": raw_jump.get("gate_state_counts"),
            "raw_wrist_gate_reason_counts": raw_jump.get("gate_reason_counts"),
        },
        "analysis": {
            "trajectory_id": analysis_trajectory.get("trajectory_id"),
            "right_hand_tracked_rate": right_rate,
            "xr_frame_valid_rate": xr_rate,
            "raw_wrist_jump_gt_10cm_valid_to_valid_count": anchor_fallback.get(
                "raw_wrist_jump_gt_10cm_valid_to_valid_count"
            ),
            "raw_wrist_jump_gt_10cm_valid_to_valid_max": anchor_fallback.get(
                "raw_wrist_jump_gt_10cm_valid_to_valid_max"
            ),
            "H9_status": h9_status,
            "H9_detail": h9_detail,
            "H13_status": h13_status,
            "H13_detail": h13_detail,
            "H14_status": h14_status,
            "H14_detail": h14_detail,
            "H15_status": h15_status,
            "H15_detail": h15_detail,
        },
        "classification": _classification(failure_reason),
        "decision": {
            "gate_a_collection_allowed": not reasons,
            "axis_gain_tuning_allowed": axis_gain_allowed,
            "reasons": reasons,
            "min_right_hand_tracked_rate": min_right_hand_tracked_rate,
            "min_xr_frame_valid_rate": min_xr_frame_valid_rate,
        },
    }


def _print_text_summary(summary: dict[str, Any]) -> None:
    decision = summary["decision"]
    evaluation = summary["evaluation"]
    analysis = summary["analysis"]
    log_counts = summary["log_counts"]

    print("[RDF][HMD_LOG_SUMMARY] files")
    for key, value in summary["files"].items():
        print(f"  {key}: {value}")
    print("[RDF][HMD_LOG_SUMMARY] key_metrics")
    print(f"  failure_reason={evaluation.get('failure_reason')}")
    print(f"  failure_category={evaluation.get('failure_category')}")
    print(f"  classification={summary.get('classification')}")
    print(f"  tracking_loss_rate={evaluation.get('tracking_loss_rate')}")
    print(f"  right_hand_tracked_rate={analysis.get('right_hand_tracked_rate')}")
    print(f"  xr_frame_valid_rate={analysis.get('xr_frame_valid_rate')}")
    print(f"  H13_status={analysis.get('H13_status')}")
    print(f"  raw_wrist_jump_max_m={evaluation.get('raw_wrist_jump_max_m')}")
    print(
        "  raw_wrist_jump_gt_10cm_valid_to_valid_count="
        f"{analysis.get('raw_wrist_jump_gt_10cm_valid_to_valid_count')}"
    )
    print("[RDF][HMD_LOG_SUMMARY] log_counts")
    for key, value in log_counts.items():
        print(f"  {key}={value}")
    print("[RDF][HMD_LOG_SUMMARY] decision")
    print(f"  gate_a_collection_allowed={decision['gate_a_collection_allowed']}")
    print(f"  axis_gain_tuning_allowed={decision['axis_gain_tuning_allowed']}")
    print(
        f"  reasons={','.join(decision['reasons']) if decision['reasons'] else 'none'}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storage-root", default="storage", type=Path)
    parser.add_argument("--log-file", type=Path)
    parser.add_argument("--trajectory-file", type=Path)
    parser.add_argument("--evaluation-file", type=Path)
    parser.add_argument("--analysis-file", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Print a human-readable summary instead of compact JSON.",
    )
    parser.add_argument("--min-right-hand-tracked-rate", type=float, default=0.95)
    parser.add_argument("--min-xr-frame-valid-rate", type=float, default=0.95)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = build_summary(
        storage_root=args.storage_root,
        log_file=args.log_file,
        trajectory_file=args.trajectory_file,
        evaluation_file=args.evaluation_file,
        analysis_file=args.analysis_file,
        min_right_hand_tracked_rate=args.min_right_hand_tracked_rate,
        min_xr_frame_valid_rate=args.min_xr_frame_valid_rate,
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    if args.pretty:
        _print_text_summary(summary)
    else:
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
