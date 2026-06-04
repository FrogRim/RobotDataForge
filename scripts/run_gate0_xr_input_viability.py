#!/usr/bin/env python3
"""Gate 0 XR input stream viability diagnostic.

This report intentionally evaluates Quest/OpenXR handtracking stream quality
without treating task success as evidence. Gate A collection remains blocked
unless Gate 0 passes.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import json
import math
from pathlib import Path
import sys
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from rdf_input_sources import (  # noqa: E402
    INPUT_TRUTH_CLASSIFICATION_SCHEMA_VERSION,
    InputSourceAdapter,
    UnsupportedInputSourceAdapter,
    WRIST_POSE_SAMPLE_SCHEMA_VERSION,
    WristPoseSample,
    adapter_for_trajectory_source,
    classify_input_truth,
)

SCHEMA_VERSION = "rdf_gate0_xr_input_viability_report_v0.1.0"
DEFAULT_STORAGE_ROOT = Path("storage")
DEFAULT_JUMP_THRESHOLD_M = 0.10
DEFAULT_WRIST_DELTA_P95_MAX_M = 0.03
DEFAULT_WRIST_DELTA_MAX_M = 0.10
DEFAULT_MIN_TRACKED_RATE = 0.95
DEFAULT_MIN_XR_VALID_RATE = 0.95
DEFAULT_MAX_FRAME_DROP_RATE = 0.05
DEFAULT_MAX_INPUT_LATENCY_MS = 80.0
DEFAULT_FRAME_DROP_FACTOR = 1.5
LOG_PATTERNS = {
    "AUTO_RECENTER_UNSTABLE_RIGHT_WRIST": "AUTO_RECENTER_UNSTABLE_RIGHT_WRIST",
    "TRACKING_LOSS": "TRACKING_LOSS",
    "RAW_WRIST_JUMP": "RAW_WRIST_JUMP",
    "raw_wrist_spike_reacquire_pending": "raw_wrist_spike_reacquire_pending",
}


@dataclass(frozen=True)
class Gate0Thresholds:
    min_right_hand_tracked_rate: float = DEFAULT_MIN_TRACKED_RATE
    min_xr_frame_valid_rate: float = DEFAULT_MIN_XR_VALID_RATE
    max_raw_wrist_jump_count: int = 0
    max_tracking_loss_count: int = 0
    max_tracking_loss_duration_ms: float = 0.0
    max_auto_recenter_unstable_count: int = 0
    max_wrist_position_delta_p95_m: float = DEFAULT_WRIST_DELTA_P95_MAX_M
    max_wrist_position_delta_max_m: float = DEFAULT_WRIST_DELTA_MAX_M
    max_frame_drop_rate: float = DEFAULT_MAX_FRAME_DROP_RATE
    max_input_latency_ms: float = DEFAULT_MAX_INPUT_LATENCY_MS
    wrist_jump_threshold_m: float = DEFAULT_JUMP_THRESHOLD_M
    frame_drop_factor: float = DEFAULT_FRAME_DROP_FACTOR

    def as_dict(self) -> dict[str, Any]:
        return {
            "min_right_hand_tracked_rate": self.min_right_hand_tracked_rate,
            "min_xr_frame_valid_rate": self.min_xr_frame_valid_rate,
            "max_raw_wrist_jump_count": self.max_raw_wrist_jump_count,
            "max_tracking_loss_count": self.max_tracking_loss_count,
            "max_tracking_loss_duration_ms": self.max_tracking_loss_duration_ms,
            "max_auto_recenter_unstable_count": self.max_auto_recenter_unstable_count,
            "max_wrist_position_delta_p95_m": self.max_wrist_position_delta_p95_m,
            "max_wrist_position_delta_max_m": self.max_wrist_position_delta_max_m,
            "max_frame_drop_rate": self.max_frame_drop_rate,
            "max_input_latency_ms": self.max_input_latency_ms,
            "wrist_jump_threshold_m": self.wrist_jump_threshold_m,
            "frame_drop_factor": self.frame_drop_factor,
        }


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def latest_trajectory_path(storage_root: Path) -> Path | None:
    trajectory_dir = storage_root / "trajectories"
    if not trajectory_dir.exists():
        return None
    candidates = sorted(
        trajectory_dir.glob("*.json"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    for candidate in candidates:
        try:
            read_json(candidate)
        except (OSError, json.JSONDecodeError):
            continue
        return candidate
    return None


def _float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if math.isfinite(result):
        return result
    return None


def _adapter_for_payload(
    payload: dict[str, Any],
) -> tuple[InputSourceAdapter, str]:
    source = payload.get("source") or {}
    if not source.get("input_device") or not source.get("runtime"):
        return (
            UnsupportedInputSourceAdapter(
                reason="unknown_input_source",
                source=source,
            ),
            "unknown_source",
        )
    adapter = adapter_for_trajectory_source(source)
    if adapter is not None:
        return adapter, "matched_source"
    return (
        UnsupportedInputSourceAdapter(
            reason="unsupported_input_source",
            source=source,
        ),
        "unsupported_source",
    )


def _input_source_summary(
    adapter: InputSourceAdapter,
    *,
    adapter_status: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    return {
        "source_id": None if adapter_status != "matched_source" else adapter.source_id,
        "adapter": None
        if adapter_status != "matched_source"
        else adapter.__class__.__name__,
        "adapter_status": adapter_status,
        "sample_schema_version": WRIST_POSE_SAMPLE_SCHEMA_VERSION,
        "trajectory_source": payload.get("source") or {},
    }


def _right_wrist_xyz(sample: WristPoseSample) -> list[float] | None:
    return sample.position_xyz


def _frame_time(frame: dict[str, Any], fallback_index: int) -> float:
    parsed = _float(frame.get("t"))
    if parsed is not None:
        return parsed
    return float(fallback_index)


def _distance(left: list[float], right: list[float]) -> float:
    return math.sqrt(sum((float(a) - float(b)) ** 2 for a, b in zip(left, right)))


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(float(value) for value in values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[int(position)]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _valid_sample(sample: WristPoseSample) -> bool:
    return sample.sample_valid


def _time_intervals(times: list[float]) -> list[float]:
    return [max(0.0, times[index] - times[index - 1]) for index in range(1, len(times))]


def _median_dt(times: list[float]) -> float:
    intervals = [value for value in _time_intervals(times) if value > 0.0]
    return _percentile(intervals, 0.5) if intervals else 0.0


def _tracking_loss_segments(
    frames: list[dict[str, Any]], times: list[float], samples: list[WristPoseSample]
) -> list[dict[str, Any]]:
    if not frames:
        return []
    dt = _median_dt(times) or 0.0
    segments: list[dict[str, Any]] = []
    start: int | None = None
    for index, frame in enumerate(frames):
        invalid = not _valid_sample(samples[index])
        if invalid and start is None:
            start = index
        if start is not None and (not invalid or index == len(frames) - 1):
            end = index - 1 if not invalid else index
            duration_sec = max(0.0, times[end] - times[start]) + dt
            segments.append(
                {
                    "start_frame": int(frames[start].get("step", start)),
                    "end_frame": int(frames[end].get("step", end)),
                    "start_index": start,
                    "end_index": end,
                    "duration_ms": round(duration_sec * 1000.0, 6),
                }
            )
            start = None
    return segments


def _wrist_delta_events(
    frames: list[dict[str, Any]],
    threshold_m: float,
    samples: list[WristPoseSample],
) -> tuple[list[float], list[dict[str, Any]]]:
    deltas: list[float] = []
    events: list[dict[str, Any]] = []
    previous_xyz: list[float] | None = None
    previous_step: int | None = None
    for index, frame in enumerate(frames):
        sample = samples[index]
        if not _valid_sample(sample):
            continue
        xyz = _right_wrist_xyz(sample)
        if xyz is None:
            continue
        step = int(frame.get("step", index))
        if previous_xyz is not None:
            delta = _distance(previous_xyz, xyz)
            deltas.append(delta)
            if delta > threshold_m:
                events.append(
                    {
                        "from_step": previous_step,
                        "to_step": step,
                        "delta_m": round(delta, 6),
                        "threshold_m": threshold_m,
                    }
                )
        previous_xyz = xyz
        previous_step = step
    return deltas, events


def _log_counts(log_file: Path | None) -> dict[str, int]:
    counts = {name: 0 for name in LOG_PATTERNS}
    if log_file is None or not log_file.exists():
        return counts
    text = log_file.read_text(encoding="utf-8", errors="replace")
    for name, pattern in LOG_PATTERNS.items():
        counts[name] = text.count(pattern)
    return counts


def _action_hold_summary(
    frames: list[dict[str, Any]], samples: list[WristPoseSample]
) -> dict[str, Any]:
    reasons: Counter[str] = Counter()
    held_steps: list[int] = []
    for index, (frame, sample) in enumerate(zip(frames, samples, strict=False)):
        if sample.action_hold:
            held_steps.append(int(frame.get("step", index)))
            reasons[str(sample.hold_reason or "unspecified")] += 1
    return {
        "hold_frame_count": len(held_steps),
        "hold_reasons": dict(sorted(reasons.items())),
        "held_steps": held_steps,
    }


def _tracking_epochs(
    frames: list[dict[str, Any]], samples: list[WristPoseSample]
) -> dict[str, Any]:
    observed: list[int] = []
    derived_epoch = 0
    previous_valid: bool | None = None
    for sample in samples:
        explicit = sample.tracking_epoch_id
        if explicit is not None:
            observed.append(explicit)
            continue
        valid = _valid_sample(sample)
        if previous_valid is False and valid:
            derived_epoch += 1
        observed.append(derived_epoch)
        previous_valid = valid
    return {
        "epoch_ids": sorted(set(observed)),
        "frame_epoch_ids": observed,
        "epoch_count": len(set(observed)),
        "source": "metadata.tracking_epoch_id"
        if any(sample.tracking_epoch_id is not None for sample in samples)
        else "derived_from_validity",
    }


def _input_truth_classifications(
    samples: list[WristPoseSample],
    *,
    warn_m: float,
    reject_m: float,
) -> list[dict[str, Any]]:
    classifications: list[dict[str, Any]] = []
    previous_valid_position: list[float] | None = None
    for sample in samples:
        classification = classify_input_truth(
            sample,
            previous_valid_position_xyz=previous_valid_position,
            raw_wrist_jump_warn_m=warn_m,
            raw_wrist_jump_reject_m=reject_m,
        )
        classifications.append(classification.as_dict())
        if sample.sample_valid and sample.position_xyz is not None:
            previous_valid_position = list(sample.position_xyz)
    return classifications


def _frame_classification_summary(
    classifications: list[dict[str, Any]],
) -> dict[str, Any]:
    truth_state_counts: Counter[str] = Counter()
    primary_reason_counts: Counter[str] = Counter()
    reason_counts: Counter[str] = Counter()
    action_hold_required_count = 0
    resume_block_count = 0
    recenter_block_count = 0
    for classification in classifications:
        truth_state_counts[str(classification.get("truth_state") or "unknown")] += 1
        primary_reason_counts[
            str(classification.get("primary_reason") or "UNKNOWN")
        ] += 1
        for reason in classification.get("frame_reason_codes") or []:
            reason_counts[str(reason)] += 1
        if classification.get("action_hold_required") is True:
            action_hold_required_count += 1
        if classification.get("resume_block") is True:
            resume_block_count += 1
        if classification.get("recenter_block") is True:
            recenter_block_count += 1
    return {
        "truth_state_counts": dict(sorted(truth_state_counts.items())),
        "primary_reason_counts": dict(sorted(primary_reason_counts.items())),
        "reason_counts": dict(sorted(reason_counts.items())),
        "action_hold_required_count": action_hold_required_count,
        "resume_block_count": resume_block_count,
        "recenter_block_count": recenter_block_count,
    }


def _epoch_classification_summary(
    tracking_epochs: dict[str, Any],
    classifications: list[dict[str, Any]],
) -> dict[str, Any]:
    frame_epoch_ids = list(tracking_epochs.get("frame_epoch_ids") or [])
    epochs: dict[int, dict[str, Any]] = {}
    for index, classification in enumerate(classifications):
        epoch_id = int(frame_epoch_ids[index]) if index < len(frame_epoch_ids) else 0
        epoch = epochs.setdefault(
            epoch_id,
            {
                "tracking_epoch_id": epoch_id,
                "valid_count": 0,
                "invalid_count": 0,
                "unsafe_count": 0,
                "epoch_reason_codes": set(),
                "transition_reason": None,
            },
        )
        truth_state = str(classification.get("truth_state") or "unknown")
        if truth_state == "valid":
            epoch["valid_count"] += 1
        elif truth_state == "invalid":
            epoch["invalid_count"] += 1
        elif truth_state == "unsafe":
            epoch["unsafe_count"] += 1
        for reason in classification.get("frame_reason_codes") or []:
            epoch["epoch_reason_codes"].add(str(reason))
        primary_reason = str(classification.get("primary_reason") or "")
        if (
            epoch["transition_reason"] is None
            and primary_reason
            and primary_reason
            not in {
                "INPUT_TRUTH_OK",
                "TIMESTAMP_FALLBACK_INDEX",
                "TRACKING_CONFIDENCE_NOT_AVAILABLE",
            }
        ):
            epoch["transition_reason"] = primary_reason

    ordered_epochs: list[dict[str, Any]] = []
    for epoch_id in sorted(epochs):
        epoch = epochs[epoch_id]
        ordered_epochs.append(
            {
                "tracking_epoch_id": epoch["tracking_epoch_id"],
                "valid_count": epoch["valid_count"],
                "invalid_count": epoch["invalid_count"],
                "unsafe_count": epoch["unsafe_count"],
                "epoch_reason_codes": sorted(epoch["epoch_reason_codes"]),
                "transition_reason": epoch["transition_reason"],
            }
        )
    return {
        "epoch_count": len(ordered_epochs),
        "epochs": ordered_epochs,
    }


def build_report(
    *,
    trajectory_path: Path | str | None = None,
    storage_root: Path | str = DEFAULT_STORAGE_ROOT,
    log_file: Path | str | None = None,
    test_type: str | None = None,
    thresholds: Gate0Thresholds | None = None,
) -> dict[str, Any]:
    thresholds = thresholds or Gate0Thresholds()
    storage_root = Path(storage_root)
    if trajectory_path is None:
        trajectory_path = latest_trajectory_path(storage_root)
    trajectory_path = Path(trajectory_path) if trajectory_path is not None else None
    if trajectory_path is None or not trajectory_path.exists():
        return {
            "schema_version": SCHEMA_VERSION,
            "gate0_pass": False,
            "gate_a_collection_allowed": False,
            "test_type": test_type or "unknown",
            "failure_reasons": ["NO_TRAJECTORY"],
            "metrics": {},
            "H13": {"status": "FAIL", "reason": "NO_TRAJECTORY"},
            "thresholds": thresholds.as_dict(),
        }

    payload = read_json(trajectory_path)
    frames = list(payload.get("frames") or [])
    total = len(frames)
    adapter, adapter_status = _adapter_for_payload(payload)
    samples = [
        adapter.sample_from_frame(frame, fallback_index=index)
        for index, frame in enumerate(frames)
    ]
    times = [_frame_time(frame, index) for index, frame in enumerate(frames)]
    intervals = _time_intervals(times)
    median_dt = _median_dt(times)
    right_hand_tracked_count = sum(1 for sample in samples if sample.tracked)
    xr_frame_valid_count = sum(1 for sample in samples if sample.frame_valid)
    loss_segments = _tracking_loss_segments(frames, times, samples)
    wrist_deltas, jump_events = _wrist_delta_events(
        frames, thresholds.wrist_jump_threshold_m, samples
    )
    classifications = _input_truth_classifications(
        samples,
        warn_m=thresholds.wrist_jump_threshold_m,
        reject_m=max(thresholds.wrist_jump_threshold_m, 0.15),
    )
    tracking_epoch_summary = _tracking_epochs(frames, samples)
    frame_drop_count = sum(
        1
        for value in intervals
        if median_dt > 0.0 and value > median_dt * thresholds.frame_drop_factor
    )
    latencies = [
        float(sample.input_latency_ms)
        for sample in samples
        if sample.input_latency_ms is not None
    ]
    log_counts = _log_counts(Path(log_file) if log_file is not None else None)
    auto_recenter_unstable_count = log_counts["AUTO_RECENTER_UNSTABLE_RIGHT_WRIST"]

    right_hand_tracked_rate = right_hand_tracked_count / total if total else 0.0
    xr_frame_valid_rate = xr_frame_valid_count / total if total else 0.0
    tracking_loss_duration_ms = sum(segment["duration_ms"] for segment in loss_segments)
    wrist_delta_p95 = _percentile(wrist_deltas, 0.95)
    wrist_delta_max = max(wrist_deltas) if wrist_deltas else 0.0
    frame_drop_rate = frame_drop_count / len(intervals) if intervals else 0.0
    input_latency_summary = {
        "mean": round(_mean(latencies), 6),
        "p95": round(_percentile(latencies, 0.95), 6),
        "max": round(max(latencies), 6) if latencies else 0.0,
        "count": len(latencies),
    }

    metrics = {
        "right_hand_tracked_rate": round(right_hand_tracked_rate, 6),
        "xr_frame_valid_rate": round(xr_frame_valid_rate, 6),
        "raw_wrist_jump_count": len(jump_events),
        "tracking_loss_count": len(loss_segments),
        "tracking_loss_duration_ms": round(tracking_loss_duration_ms, 6),
        "auto_recenter_unstable_count": auto_recenter_unstable_count,
        "wrist_position_delta_p95": round(wrist_delta_p95, 6),
        "wrist_position_delta_max": round(wrist_delta_max, 6),
        "frame_drop_rate": round(frame_drop_rate, 6),
        "input_latency_ms": input_latency_summary,
        "frame_count": total,
        "median_frame_dt_sec": round(median_dt, 6),
        "frame_drop_count": frame_drop_count,
    }

    failures: list[str] = []
    if right_hand_tracked_rate < thresholds.min_right_hand_tracked_rate:
        failures.append("RIGHT_HAND_TRACKED_RATE_LOW")
    if xr_frame_valid_rate < thresholds.min_xr_frame_valid_rate:
        failures.append("XR_FRAME_VALID_RATE_LOW")
    if len(jump_events) > thresholds.max_raw_wrist_jump_count:
        failures.append("RAW_WRIST_JUMP")
    if len(loss_segments) > thresholds.max_tracking_loss_count:
        failures.append("TRACKING_LOSS")
    if tracking_loss_duration_ms > thresholds.max_tracking_loss_duration_ms:
        if "TRACKING_LOSS" not in failures:
            failures.append("TRACKING_LOSS")
    if auto_recenter_unstable_count > thresholds.max_auto_recenter_unstable_count:
        failures.append("AUTO_RECENTER_UNSTABLE_RIGHT_WRIST")
    if wrist_delta_p95 > thresholds.max_wrist_position_delta_p95_m:
        failures.append("WRIST_POSITION_DELTA_P95_HIGH")
    if wrist_delta_max > thresholds.max_wrist_position_delta_max_m:
        if "RAW_WRIST_JUMP" not in failures:
            failures.append("RAW_WRIST_JUMP")
    if frame_drop_rate > thresholds.max_frame_drop_rate:
        failures.append("FRAME_DROP_RATE_HIGH")
    if input_latency_summary["max"] > thresholds.max_input_latency_ms:
        failures.append("INPUT_LATENCY_HIGH")
    if adapter_status == "unsupported_source":
        failures.append("UNSUPPORTED_INPUT_SOURCE")
    if adapter_status == "unknown_source":
        failures.append("UNKNOWN_INPUT_SOURCE")

    # Deduplicate while preserving first-seen reason order.
    failure_reasons = list(dict.fromkeys(failures))
    h13_status = "FAIL" if len(jump_events) else "PASS"
    test_type_from_payload = (payload.get("summary") or {}).get("gate0_test_type")
    gate0_pass = not failure_reasons and total > 0
    return {
        "schema_version": SCHEMA_VERSION,
        "trajectory_path": str(trajectory_path),
        "trajectory_id": payload.get("id"),
        "episode_id": payload.get("episode_id"),
        "test_type": test_type or test_type_from_payload or "unspecified",
        "gate0_pass": gate0_pass,
        "gate_a_collection_allowed": gate0_pass,
        "failure_reasons": failure_reasons,
        "input_source": _input_source_summary(
            adapter,
            adapter_status=adapter_status,
            payload=payload,
        ),
        "metrics": metrics,
        "H13": {
            "id": "H13",
            "name": "valid_to_valid_raw_wrist_jump",
            "status": h13_status,
            "threshold_m": thresholds.wrist_jump_threshold_m,
            "count_over_threshold": len(jump_events),
            "max_m": round(wrist_delta_max, 6),
            "events": jump_events,
        },
        "tracking_loss_segments": loss_segments,
        "log_counts": log_counts,
        "action_hold": _action_hold_summary(frames, samples),
        "tracking_epochs": tracking_epoch_summary,
        "classification_schema_version": INPUT_TRUTH_CLASSIFICATION_SCHEMA_VERSION,
        "frame_classification_summary": _frame_classification_summary(
            classifications
        ),
        "epoch_classification_summary": _epoch_classification_summary(
            tracking_epoch_summary,
            classifications,
        ),
        "thresholds": thresholds.as_dict(),
        "notes": [
            "Gate 0 evaluates XR input viability only; task success is not used.",
            "Gate A collection must remain blocked while gate0_pass is false.",
            "Bad tracking frames are reported and held, not interpolated into training data.",
        ],
    }


def _print_report(report: dict[str, Any]) -> None:
    print("[RDF][GATE0] XR Input Stream Viability")
    print(f"[RDF][GATE0] test_type={report.get('test_type')}")
    print(
        f"[RDF][GATE0] PASS={report.get('gate0_pass')} "
        f"gate_a_collection_allowed={report.get('gate_a_collection_allowed')}"
    )
    metrics = report.get("metrics") or {}
    for key in (
        "right_hand_tracked_rate",
        "xr_frame_valid_rate",
        "raw_wrist_jump_count",
        "tracking_loss_count",
        "tracking_loss_duration_ms",
        "auto_recenter_unstable_count",
        "wrist_position_delta_p95",
        "wrist_position_delta_max",
        "frame_drop_rate",
    ):
        if key in metrics:
            print(f"[RDF][GATE0] {key}={metrics[key]}")
    if "input_latency_ms" in metrics:
        print(f"[RDF][GATE0] input_latency_ms={metrics['input_latency_ms']}")
    h13 = report.get("H13") or {}
    print(
        f"[RDF][GATE0] H13={h13.get('status')} "
        f"count={h13.get('count_over_threshold')} max_m={h13.get('max_m')}"
    )
    reasons = report.get("failure_reasons") or []
    print("[RDF][GATE0] failure_reasons=" + (",".join(reasons) if reasons else "none"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--trajectory", type=Path, default=None)
    parser.add_argument(
        "--latest",
        action="store_true",
        help="Use latest trajectory under storage root, including zero-frame diagnostics.",
    )
    parser.add_argument("--log-file", type=Path, default=None)
    parser.add_argument(
        "--test-type",
        choices=(
            "static",
            "slow_motion",
            "recenter",
            "tracking_reacquire",
            "unspecified",
        ),
        default=None,
    )
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument(
        "--min-right-hand-tracked-rate", type=float, default=DEFAULT_MIN_TRACKED_RATE
    )
    parser.add_argument(
        "--min-xr-frame-valid-rate", type=float, default=DEFAULT_MIN_XR_VALID_RATE
    )
    parser.add_argument(
        "--max-wrist-delta-p95-m", type=float, default=DEFAULT_WRIST_DELTA_P95_MAX_M
    )
    parser.add_argument(
        "--max-wrist-delta-max-m", type=float, default=DEFAULT_WRIST_DELTA_MAX_M
    )
    parser.add_argument(
        "--max-frame-drop-rate", type=float, default=DEFAULT_MAX_FRAME_DROP_RATE
    )
    parser.add_argument(
        "--max-input-latency-ms", type=float, default=DEFAULT_MAX_INPUT_LATENCY_MS
    )
    parser.add_argument(
        "--wrist-jump-threshold-m", type=float, default=DEFAULT_JUMP_THRESHOLD_M
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    trajectory_path = args.trajectory
    if args.latest or trajectory_path is None:
        trajectory_path = latest_trajectory_path(args.storage_root)
    thresholds = Gate0Thresholds(
        min_right_hand_tracked_rate=args.min_right_hand_tracked_rate,
        min_xr_frame_valid_rate=args.min_xr_frame_valid_rate,
        max_wrist_position_delta_p95_m=args.max_wrist_delta_p95_m,
        max_wrist_position_delta_max_m=args.max_wrist_delta_max_m,
        max_frame_drop_rate=args.max_frame_drop_rate,
        max_input_latency_ms=args.max_input_latency_ms,
        wrist_jump_threshold_m=args.wrist_jump_threshold_m,
    )
    report = build_report(
        trajectory_path=trajectory_path,
        storage_root=args.storage_root,
        log_file=args.log_file,
        test_type=args.test_type,
        thresholds=thresholds,
    )
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
        )
    if args.pretty:
        _print_report(report)
    else:
        print(json.dumps(report, sort_keys=True))
    return 0 if report.get("gate0_pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
