from __future__ import annotations

from typing import Any


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


def _phase_from_frame(frame: dict[str, Any]) -> str | None:
    metadata = frame.get("metadata") or {}
    phase = metadata.get("action_phase") or metadata.get("phase")
    if phase is None:
        return None
    normalized = str(phase).strip().upper()
    return normalized if normalized in SUPPORTED_PHASES else "UNKNOWN"


def segment_actions(trajectory: dict[str, Any]) -> list[dict[str, Any]]:
    """Return explicit action segments without pretending to infer unavailable task phases."""

    frames = trajectory.get("frames") or []
    if not isinstance(frames, list) or not frames:
        return []

    phases = [_phase_from_frame(frame) for frame in frames]
    if all(phase is None for phase in phases):
        return [
            {
                "phase": "UNKNOWN",
                "start_frame": 0,
                "end_frame": len(frames) - 1,
                "confidence": 0.0,
                "source": "heuristic_unavailable",
                "metadata": {
                    "reason": "No frame metadata action_phase was available.",
                },
            }
        ]

    segments: list[dict[str, Any]] = []
    current_phase = phases[0] or "UNKNOWN"
    start = 0
    for index in range(1, len(frames)):
        phase = phases[index] or "UNKNOWN"
        if phase != current_phase:
            segments.append(
                {
                    "phase": current_phase,
                    "start_frame": start,
                    "end_frame": index - 1,
                    "confidence": 1.0 if phases[start] is not None else 0.5,
                    "source": "frame_metadata",
                    "metadata": {},
                }
            )
            current_phase = phase
            start = index
    segments.append(
        {
            "phase": current_phase,
            "start_frame": start,
            "end_frame": len(frames) - 1,
            "confidence": 1.0 if phases[start] is not None else 0.5,
            "source": "frame_metadata",
            "metadata": {},
        }
    )
    return segments
