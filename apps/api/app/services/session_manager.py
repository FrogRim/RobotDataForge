from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def session_is_invalid(runtime_metrics: dict[str, Any], trajectory_frames: int | None = None) -> str | None:
    if float(runtime_metrics.get("hand_tracking_loss_rate", 0.0)) > 0.3:
        return "TRACKING_LOSS"
    if float(runtime_metrics.get("frame_drop_rate", 0.0)) > 0.3:
        return "FRAME_DROP"
    if runtime_metrics.get("session_crashed") is True or runtime_metrics.get("simulator_crash") is True:
        return "SIM_RUNTIME_ERROR"
    if trajectory_frames is not None and trajectory_frames < int(runtime_metrics.get("minimum_required_frames", 1)):
        return "NO_TRAJECTORY"
    if runtime_metrics.get("missing_required_object_state") is True:
        return "MISSING_REQUIRED_OBJECT_STATE"
    if runtime_metrics.get("missing_required_robot_state") is True:
        return "MISSING_REQUIRED_ROBOT_STATE"
    return None
