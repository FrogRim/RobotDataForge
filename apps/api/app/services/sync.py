from __future__ import annotations

from typing import Any

from app.utils.scoring import clamp01


def _frames(trajectory: dict[str, Any]) -> list[dict[str, Any]]:
    frames = trajectory.get("frames") or []
    return frames if isinstance(frames, list) else []


def _float_or_none(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _metadata_values(frames: list[dict[str, Any]], key: str) -> list[float]:
    values: list[float] = []
    for frame in frames:
        metadata = frame.get("metadata") or {}
        value = _float_or_none(metadata.get(key))
        if value is not None:
            values.append(value)
    return values


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * percentile)))
    return ordered[index]


def _timestamps(frames: list[dict[str, Any]]) -> list[float]:
    timestamps: list[float] = []
    for frame in frames:
        timestamp = _float_or_none(frame.get("t"))
        if timestamp is not None:
            timestamps.append(timestamp)
    return timestamps


def _tracking_loss_rate(frames: list[dict[str, Any]]) -> float:
    if not frames:
        return 1.0
    lost = 0
    for frame in frames:
        metadata = frame.get("metadata") or {}
        if metadata.get("right_hand_tracked") is False or metadata.get("xr_frame_valid") is False:
            lost += 1
    return lost / len(frames)


def _post_warmup_frames(trajectory: dict[str, Any], frames: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for index, frame in enumerate(frames):
        metadata = frame.get("metadata") or {}
        if metadata.get("recording_started_after_warmup") is True:
            return frames[index:]
    return frames


def compute_sync_metrics(trajectory: dict[str, Any]) -> dict[str, Any]:
    """Compute timestamp and runtime sync quality without inventing unavailable measurements."""

    frames = _frames(trajectory)
    post_warmup = _post_warmup_frames(trajectory, frames)
    timestamps = _timestamps(post_warmup)
    warnings: list[str] = []

    timestamp_monotonic = all(
        timestamps[index] >= timestamps[index - 1]
        for index in range(1, len(timestamps))
    )
    if not timestamps:
        warnings.append("missing_frame_timestamps")
    elif not timestamp_monotonic:
        warnings.append("timestamp_non_monotonic")

    intervals = [
        timestamps[index] - timestamps[index - 1]
        for index in range(1, len(timestamps))
        if timestamps[index] >= timestamps[index - 1]
    ]
    frame_interval_mean_ms = None
    frame_interval_jitter_ms = None
    inferred_frame_drop_rate = None
    if intervals:
        mean_interval = sum(intervals) / len(intervals)
        frame_interval_mean_ms = mean_interval * 1000.0
        frame_interval_jitter_ms = max(abs(interval - mean_interval) for interval in intervals) * 1000.0
        long_intervals = [interval for interval in intervals if interval > max(mean_interval * 2.5, mean_interval + 0.05)]
        inferred_frame_drop_rate = len(long_intervals) / len(intervals)

    latencies = _metadata_values(post_warmup, "input_latency_ms")
    sync_errors = _metadata_values(post_warmup, "sync_error_ms")
    clock_drifts = _metadata_values(post_warmup, "clock_drift_ms")

    summary = trajectory.get("summary") or {}
    runtime = summary.get("runtime_metrics") if isinstance(summary.get("runtime_metrics"), dict) else {}
    frame_drop_rate = _float_or_none(runtime.get("frame_drop_rate"))
    if frame_drop_rate is None:
        frame_drop_rate = inferred_frame_drop_rate
    if frame_drop_rate is None:
        warnings.append("frame_drop_rate_unavailable")

    hand_tracking_loss_rate = _tracking_loss_rate(frames)
    hand_tracking_loss_after_warmup = _tracking_loss_rate(post_warmup)
    if not sync_errors:
        warnings.append("sync_error_ms_unavailable")

    timestamp_source = "unknown"
    for frame in post_warmup:
        metadata = frame.get("metadata") or {}
        if metadata.get("timestamp_source"):
            timestamp_source = str(metadata["timestamp_source"])
            break

    quality_penalty = 0.0
    quality_penalty += min(hand_tracking_loss_after_warmup, 1.0) * 0.35
    quality_penalty += min(frame_drop_rate or 0.0, 1.0) * 0.25
    if frame_interval_jitter_ms is not None:
        quality_penalty += min(frame_interval_jitter_ms / 100.0, 1.0) * 0.2
    else:
        quality_penalty += 0.1
    if sync_errors:
        quality_penalty += min((_percentile(sync_errors, 0.95) or 0.0) / 100.0, 1.0) * 0.2
    else:
        quality_penalty += 0.1
    if not timestamp_monotonic:
        quality_penalty = 1.0

    return {
        "schema_version": "sync_metrics_v0.1.0",
        "frame_count": len(frames),
        "post_warmup_frame_count": len(post_warmup),
        "timestamp_count": len(timestamps),
        "timestamp_source": timestamp_source,
        "timestamp_monotonic": timestamp_monotonic,
        "frame_interval_mean_ms": frame_interval_mean_ms,
        "frame_interval_jitter_ms": frame_interval_jitter_ms,
        "frame_drop_rate": frame_drop_rate,
        "hand_tracking_loss_rate": hand_tracking_loss_rate,
        "hand_tracking_loss_after_warmup": hand_tracking_loss_after_warmup,
        "average_input_latency_ms": sum(latencies) / len(latencies) if latencies else None,
        "max_input_latency_ms": max(latencies) if latencies else None,
        "sync_error_ms_mean": sum(sync_errors) / len(sync_errors) if sync_errors else None,
        "sync_error_ms_p95": _percentile(sync_errors, 0.95),
        "sync_error_source": "frame_metadata" if sync_errors else "unavailable",
        "clock_drift_ms_mean": sum(clock_drifts) / len(clock_drifts) if clock_drifts else None,
        "quality_score": clamp01(1.0 - quality_penalty),
        "warnings": warnings,
    }
